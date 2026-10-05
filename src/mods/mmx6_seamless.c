/* SLUS-01395 Seamless Loading. ROCK_X6.DAT/BIN resources are uncompressed and
 * streamed sector by sector into RAM, VRAM and SPU RAM by the game's own CD
 * callbacks. When a verified load starts, this adapter drives those original
 * callbacks synchronously with sectors from the prepared resident pack, and
 * drains the game's deferred VRAM/SPU queue as the original main loop would.
 * Guest clocks, CD timing, XA music/voice streaming and audio pacing are not
 * changed. Anything outside the verified contract runs the original loader. */
#include "mmx6_seamless_callers.h"
#include "mmx6_seamless_store.h"
#include "mod_plugins.h"
#include "cpu_state.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern uint64_t psx_cycle_count;

/* Original loader state (see docs/SEAMLESS_LOADING.md). */
#define STATUS        0x8009509Cu /* u8: 0 idle, 1 reading, 2 complete, 0x80/0xC0 error */
#define QUEUE_PENDING 0x8008EC08u /* u8: deferred VRAM/SPU jobs outstanding */
#define REQ_REMAIN    0x800E01A8u
#define REQ_LBA       0x800E01B4u
#define REQ_PACKED    0x800E01C0u
#define REQ_CALLBACKS 0x800E01D0u
#define DAT_TABLE     0x800E0398u
#define BIN_TABLE     0x800E0B58u
#define FN_RAW_START  0x80014E60u /* Setmode/Setloc/ReadN for whole-file reads */
#define FN_PACK_START 0x80015230u /* Setmode/Setloc/ReadN for packed resources */
#define FN_RAW_CB     0x800165A4u
#define FN_PACK_CB    0x8001531Cu
#define FN_DRAIN      0x80015C5Cu /* deferred LoadImage / SPU transfer queue */
#define FN_DRAWSYNC   0x80066150u
#define FN_CDREADY    0x80064894u
#define FN_GETSECTOR  0x80064CB4u
#define LOADER_LO     0x80014D50u /* callers allowed to reach the CD shims */
#define LOADER_HI     0x80016704u
#define SECTOR_BYTES  2340u       /* Setmode 0xA0: header + subheader + data + EDC/ECC */
#define SECTOR_READ   2060u       /* header + subheader + 2048 data bytes */

static int ready, trace, retail, disabled;
static int pumping, pump_error;
static unsigned frame;
static uint8_t sector[SECTOR_BYTES];
static uint32_t cursor, sector_lba;

static uint32_t r32(uint32_t a) { return psx_mod_read_word(a); }
static uint8_t r8(uint32_t a) { return psx_mod_read_byte(a); }
static void count(const char *name) { psx_mod_counter_add(name, 1); }
static uint8_t bcd(unsigned v) { return (uint8_t)(((v / 10) << 4) | (v % 10)); }

/* Run an original guest routine to completion from a filter callback. */
static void call_guest(CPUState *cpu, uint32_t fn, uint32_t a0) {
    (void)psx_mod_call_guest(cpu, fn, cpu->gpr[31], a0, 0, 0, 0);
}

/* Archive base LBA from the game's own descriptor table, which it built from
 * the mounted disc at boot. Every entry must agree with the resident header. */
static int archive_base(unsigned archive, uint32_t table, uint32_t *base) {
    uint32_t offset, size, b;
    unsigned n = mmx6_seamless_member_count(archive);
    if (!n || !mmx6_seamless_member(archive, 0, &offset, &size)) return 0;
    b = r32(table) - offset;
    for (unsigned i = 0; i < n; i++) {
        if (!mmx6_seamless_member(archive, i, &offset, &size) ||
            r32(table + i * 8u) != b + offset || r32(table + i * 8u + 4u) != size) return 0;
    }
    *base = b;
    return 1;
}

static void load_sector(uint32_t lba, const unsigned char *data, int last) {
    unsigned msf = lba + 150u;
    memset(sector, 0, sizeof sector);
    sector[0] = bcd(msf / 4500u); sector[1] = bcd(msf / 75u % 60u); sector[2] = bcd(msf % 75u);
    sector[3] = 2;
    sector[6] = sector[10] = last ? 0x89 : 0x08; /* data; last file sector adds EOR|EOF */
    memcpy(sector + 12, data, 2048);
    cursor = 0;
    sector_lba = lba;
}

/* CdGetSector(dst, words): the original is a CD-ROM DMA from the sector buffer,
 * so deliver the words with the same RAM-side effects. */
static int get_sector_filter(CPUState *cpu, uint32_t address) {
    (void)address;
    if (!pumping || cpu->gpr[31] < LOADER_LO || cpu->gpr[31] >= LOADER_HI) return 0;
    uint32_t dst = cpu->gpr[4] & 0x1FFFFFFCu, bytes = cpu->gpr[5] * 4u;
    if (!bytes || bytes > SECTOR_BYTES - cursor ||
        !psx_mod_dma_write_ram(0x80000000u | dst, sector + cursor, bytes, (int)sector_lba)) {
        pump_error = 1;
        cpu->gpr[2] = 0;
        return 1;
    }
    cursor += bytes;
    cpu->gpr[2] = 1;
    return 1;
}

/* CdReady(1, 0) inside the original data-ready callbacks: a sector is ready. */
static int cd_ready_filter(CPUState *cpu, uint32_t address) {
    (void)address;
    if (!pumping || cpu->gpr[31] < LOADER_LO || cpu->gpr[31] >= LOADER_HI) return 0;
    cpu->gpr[2] = 1;
    return 1;
}

static int pump(CPUState *cpu, int packed) {
    uint32_t dat_base, bin_base, base, sectors, lba = r32(REQ_LBA), remain = r32(REQ_REMAIN);
    unsigned archive;
    if (!archive_base(MMX6_SEAMLESS_DAT, DAT_TABLE, &dat_base) ||
        !archive_base(MMX6_SEAMLESS_BIN, BIN_TABLE, &bin_base)) {
        count("mmx6.seamless.reject_table");
        return 0;
    }
    if (lba - dat_base < mmx6_seamless_archive_sectors(MMX6_SEAMLESS_DAT)) {
        archive = MMX6_SEAMLESS_DAT; base = dat_base;
    } else if (lba - bin_base < mmx6_seamless_archive_sectors(MMX6_SEAMLESS_BIN)) {
        archive = MMX6_SEAMLESS_BIN; base = bin_base;
    } else {
        count("mmx6.seamless.reject_lba");
        return 0;
    }
    sectors = mmx6_seamless_archive_sectors(archive);
    if (!packed && (!remain || (remain + 2047u) / 2048u > sectors - (lba - base))) {
        count("mmx6.seamless.reject_size");
        return 0;
    }
    if (!mmx6_seamless_guard_ok()) {
        count("mmx6.seamless.reject_guard");
        return 0;
    }
    /* The original start routines' guest-visible effects, without driving the
     * drive: the drive stays paused and the callbacks issue their own Pause. */
    psx_mod_write_byte(STATUS, 0);
    psx_mod_write_word(REQ_CALLBACKS, 0);
    if (!packed) psx_mod_write_word(REQ_LBA, lba - 1u);
    psx_mod_write_byte(STATUS, 1);
    unsigned served = 0, drains = 0, first = frame;
    uint64_t start = psx_cycle_count, in_callbacks = 0, in_drain = 0, in_sync = 0, t;
    pumping = 1; pump_error = 0;
    for (uint32_t s = lba - base; r8(STATUS) == 1; s++, served++) {
        if (s >= sectors || pump_error) { pump_error = 1; break; }
        load_sector(base + s, mmx6_seamless_sector(archive, s), s + 1u == sectors);
        t = psx_cycle_count;
        call_guest(cpu, packed ? FN_PACK_CB : FN_RAW_CB, 0);
        in_callbacks += psx_cycle_count - t;
        if (cursor != SECTOR_READ) { pump_error = 1; break; }
        if (r8(QUEUE_PENDING)) {
            t = psx_cycle_count;
            call_guest(cpu, FN_DRAIN, 0);
            in_drain += psx_cycle_count - t; t = psx_cycle_count;
            call_guest(cpu, FN_DRAWSYNC, 0);
            in_sync += psx_cycle_count - t;
            ++drains;
        }
    }
    pumping = 0;
    if (pump_error || r8(STATUS) != 2 || r8(QUEUE_PENDING)) {
        /* Leave the game's own timeout/retry path to recover with the drive. */
        disabled = 1;
        count("mmx6.seamless.pump_failed");
        fprintf(stderr, "mmx6 seamless: load at lba %u failed after %u sectors (status %02X); "
                        "original loading for the rest of this session\n", lba, served, r8(STATUS));
        return 1;
    }
    count(packed ? "mmx6.seamless.packed_loads" : "mmx6.seamless.raw_loads");
    psx_mod_counter_add("mmx6.seamless.sectors", served);
    if (trace) {
        fprintf(stdout, "mmx6 seamless: %s %s lba=%u sectors=%u drains=%u frames=%u..%u "
                        "cycles=%llu (callbacks %llu, queue %llu, drawsync %llu)\n",
                packed ? "packed" : "raw", archive ? "BIN" : "DAT", lba, served, drains, first, frame,
                (unsigned long long)(psx_cycle_count - start), (unsigned long long)in_callbacks,
                (unsigned long long)in_drain, (unsigned long long)in_sync);
        fflush(stdout);
    }
    return 1;
}

static int contains(const uint32_t *list, unsigned n, uint32_t value) {
    for (unsigned i = 0; i < n; i++) if (list[i] == value) return 1;
    return 0;
}

/* Only loads the game waits on behind its loading screen are served. Each
 * original call site is followed by a blocking wait (80015EC0, 80016178 or
 * 8001494C). The two gameplay actors that stream in the background
 * (800528F4 packed, 80052E44 -> 80016858/80014B78 overlay) keep the original
 * asynchronous CD timing: they overlap play, so serving them at once would
 * only move their queue work into a gameplay hitch and change spawn timing.
 * Unknown callers use the original loader. */
static int blocking_request(CPUState *cpu, int packed) {
    const uint32_t ra = cpu->gpr[31], sp = cpu->gpr[29];
    if (packed) {
        /* 80014F70 calls 80015230 last; its frame saves the caller's ra at +40. */
        if (ra < 0x80014F70u || ra >= FN_PACK_START) return 0;
        return contains(mmx6_seamless_pack_callers, sizeof mmx6_seamless_pack_callers / 4,
                        r32(sp + 40u));
    }
    if (ra == 0x80016938u)  /* from 80016858, whose frame saves its caller's ra at +28 */
        return contains(mmx6_seamless_bin_callers, sizeof mmx6_seamless_bin_callers / 4,
                        r32(sp + 28u));
    return contains(mmx6_seamless_raw_callers, sizeof mmx6_seamless_raw_callers / 4, ra);
}

static int start_filter(CPUState *cpu, uint32_t address) {
    if (!ready || retail || disabled || pumping || !psx_mod_game_started()) return 0;
    const int packed = (address & 0x1FFFFFFFu) == (FN_PACK_START & 0x1FFFFFFFu);
    /* The raw start routine is also a retry target; packed retries restart
     * through 80014F70 -> 80015230 instead. */
    if (!packed && r32(REQ_PACKED)) return 0;
    if (!blocking_request(cpu, packed)) {
        count("mmx6.seamless.background_original");
        if (trace) {
            fprintf(stdout, "mmx6 seamless: original %s load lba=%u ra=%08X frame=%u\n",
                    packed ? "packed" : "raw", r32(REQ_LBA), cpu->gpr[31], frame);
            fflush(stdout);
        }
        return 0;
    }
    return pump(cpu, packed);
}

static void tick(void) { ++frame; }

static void activate(void) {
    const char *s = getenv("MMX6_SEAMLESS_TRACE");
    trace = s && !strcmp(s, "1");
    s = getenv("MMX6_SEAMLESS_RETAIL");
    retail = s && !strcmp(s, "1");
    ready = mmx6_seamless_prepare();
}

PSX_MOD_CONSTRUCTOR(mmx6_register_seamless) {
    (void)psx_mod_register_activation_plugin("mmx6.seamless", activate);
    (void)psx_mod_register_vblank_plugin("mmx6.seamless", tick);
    (void)psx_mod_register_function_filter_plugin("mmx6.seamless", FN_RAW_START, start_filter);
    (void)psx_mod_register_function_filter_plugin("mmx6.seamless", FN_PACK_START, start_filter);
    (void)psx_mod_register_function_filter_plugin("mmx6.seamless", FN_CDREADY, cd_ready_filter);
    (void)psx_mod_register_function_filter_plugin("mmx6.seamless", FN_GETSECTOR, get_sector_filter);
}
