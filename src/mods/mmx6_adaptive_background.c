#include "mmx6_adaptive_background.h"
#include "mmx6_adaptive_assets.h"
#include "mod_plugins.h"
#include "gpu.h"
#include <stdio.h>
#include <stdlib.h>

/* Separate 1MiB per layer per guest display buffer. At 32 bytes per packet,
 * each slice holds 2048 columns x16 rows: the full 32768px signed-coordinate
 * viewport. Capacity is a checked storage invariant, never an aspect cap.
 * Metadata lives beside packets so a saved pending OT is self-contained. */
#define LAYER_BYTES (1024u * 1024u)
#define ARENA_BYTES (6u * LAYER_BYTES)
static uint32_t arena;
static int intro_banks;
static int weather_bank;
#define INTRO_BANK 0x6001u
#define FACTORY_BANK 0x6002u
#define WEATHER_BANK 0x6003u

static int load_intro_banks(uint16_t id) {
    if (id != INTRO_BANK && id != FACTORY_BANK) return 0;
    if (intro_banks) return intro_banks > 0;
    intro_banks = -1;
    uint32_t size = 0;
    if (!psx_mod_read_disc_file("ROCK_X6.DAT", NULL, 0, &size) || size > 128u * 1024u * 1024u) return 0;
    uint8_t *data = (uint8_t *)malloc(size);
    uint16_t *pixels = (uint16_t *)calloc(1024u * 512u, sizeof(uint16_t));
    int ok = 0;
    if (data && pixels && psx_mod_read_disc_file("ROCK_X6.DAT", data, size, &size)) {
        const uint8_t *opening = mmx6_intro_asset(data, size, 0x10000u);
        const uint8_t *factory = mmx6_intro_asset(data, size, 0x16u);
        if (opening && factory) {
            mmx6_unpack_intro_bank(pixels, opening, 0);
            ok = psx_mod_define_texture_bank(INTRO_BANK, 1024u, 512u, pixels);
            mmx6_unpack_intro_bank(pixels, factory, 1);
            ok = psx_mod_define_texture_bank(FACTORY_BANK, 1024u, 512u, pixels) && ok;
        }
    }
    free(pixels); free(data);
    intro_banks = ok ? 1 : -1;
    if (!ok) fprintf(stderr, "MMX6 Custom Renderer: original intro texture assets unavailable\n");
    return ok;
}

static int load_background_bank(uint16_t id) {
    if (id != WEATHER_BANK) return load_intro_banks(id);
    if (weather_bank) return 1;
    if (psx_mod_read_byte(0x800ccedcu) != 6u ||
        psx_mod_read_byte(0x800cceddu) != 0u) return 0;
    /* Turtloid uploads all five rain frames with the stage textures. Its
     * controller (800ED510) only selects a row and animates the live CLUT;
     * the indices are static. Retain those uploaded indices for the existing
     * immutable-bank batching path, keeping palette fades and OT order live.
     * The CPU VRAM mirror contains guest uploads and is restored by snapshots,
     * so a restored pending weather packet can resolve this bank as well. */
    weather_bank = psx_mod_define_texture_bank(WEATHER_BANK, 1024u, 512u, gpu_get_vram());
    return weather_bank;
}

/* The intro's foreground switches texture ownership inside a shared pillar
 * at x=2048, its near background at x=1088. The native texture-swap flag is
 * insufficient: a wide view sees both regions at once, in either direction.
 * Only the distant opening panorama repeats; the near layer contains authored
 * factory machinery beyond the wreckage, which must never be reflected. */
static int intro_panorama_width(unsigned layer) {
    if (layer == 0 || psx_mod_read_byte(0x800ccedcu) != 0 ||
        psx_mod_read_byte(0x800cceddu) != 0) return 0;
    const uint32_t far = 0x800972a0u;
    if (psx_mod_read_byte(far + 4u) != 3 ||
        psx_mod_read_half(far + 0x40u) != 0 ||
        psx_mod_read_half(far + 0x42u) != 640 ||
        (int8_t)psx_mod_read_byte(far + 0x52u) >= 0) return 0;
    return layer == 2 ? 640 : 0;
}

int mmx6_adaptive_background_activate(void) {
    arena = psx_mod_alloc_gpu_dma_memory(ARENA_BYTES, 32u);
    if (!arena) {
        fprintf(stderr, "MMX6 Custom Renderer: background arena allocation failed\n");
        return 0;
    }
    gpu_ws_bg2d_set_host_arena(arena, ARENA_BYTES);
    psx_mod_set_texture_bank_resolver(load_background_bank);
    psx_mod_set_texture_bank_batching(1);
    return 1;
}

void mmx6_adaptive_background_begin(unsigned layer) {
    if (layer) return;
    /* Ladder/event locks are internal to this continuous stage. Its original
     * map bounds include the final tower and boss room; the initial camera
     * maximum (5120) stops before them and is not the scene's right edge. */
    int lo = psx_mod_read_byte(0x80097245u) * 256;
    int hi = (psx_mod_read_byte(0x80097246u) + 1) * 256 - 320;
    gpu_ws_set_view_bounds_override(intro_panorama_width(2) != 0, lo, hi);
}

/* Retail intro scroll functions derive X from foreground X / 2 and X / 4.
 * Apply that same mapping to the host camera's left edge. Copying a full-speed
 * foreground shift (then clamping each layer separately) changes parallax when
 * the view approaches an edge. This also preserves the original artwork at
 * the stage's left edge as the viewport expands. */
static int floor_div(int value, int divisor) {
    return value >= 0 ? value / divisor : -((-value + divisor - 1) / divisor);
}
static WsViewAnchor parallax_view(WsViewAnchor foreground, int divisor, int camera) {
    int extra = (foreground.left + foreground.right +
                 foreground.pad_left + foreground.pad_right) / 2;
    int origin = floor_div(camera, divisor) -
                 floor_div(camera - foreground.left, divisor) + foreground.pad_left;
    WsViewAnchor v = {origin, 2 * extra - origin, origin - extra,
                      foreground.pad_left, foreground.pad_right};
    return v;
}
static WsViewAnchor intro_parallax_view(WsViewAnchor foreground, unsigned layer, int camera) {
    return parallax_view(foreground, layer == 1 ? 2 : 4, camera);
}

/* Amazon's independent half-speed layer is an atlas of separate panoramas.
 * The jungle occupies x=[0,896), the first cave panel x=[768,1408).
 * Reflect the selected panel, never the empty atlas gutter or the next room's
 * artwork. Foreground and the full-speed near scenery remain authored maps. */
static int amazon_panorama(unsigned layer, int sx, int sy, int *origin) {
    uint32_t b = 0x800972a0u;
    if (layer != 2 || psx_mod_read_byte(0x800ccedcu) != 1u ||
        psx_mod_read_byte(0x800cceddu) != 0u ||
        psx_mod_read_byte(b + 4u) != 1u || psx_mod_read_byte(b + 0x4bu) != 8u ||
        psx_mod_read_half(b + 0x40u) || psx_mod_read_half(b + 0x42u) ||
        (int8_t)psx_mod_read_byte(b + 0x52u) >= 0) return 0;
    if (sy >= 0 && sy < 512 && sx < 896) { *origin = 0; return 896; }
    if (sy >= 768 && sy < 1024 && sx < 1408) { *origin = 768; return 640; }
    return 0;
}

void mmx6_adaptive_background_end(unsigned layer, uint32_t native_packet) {
    WsViewAnchor view;
    if (!arena || layer >= 3 || !gpu_ws_bg2d_get_view(layer, &view)) return;
    if (view.left <= 0 && view.right <= 0) return;
    if (psx_mod_read_half(0x80090d6au)) return; /* Native 512px title mode. */
    uint32_t buffer = psx_mod_read_word(0x1f800000u);
    if (buffer > 1) return;
    uint32_t b = 0x800971f8u + layer * 0x54u;
    if (!psx_mod_read_byte(b + 3u)) return;
    int sx = (int16_t)psx_mod_read_half(b + 10u);
    int sy = (int16_t)psx_mod_read_half(b + 14u);
    int parent = (int8_t)psx_mod_read_byte(b + 0x52u);
    if (parent >= 0 && parent < 3) {
        uint32_t p = 0x800971f8u + (unsigned)parent * 0x54u;
        sx += (int16_t)psx_mod_read_half(p + 10u);
        sy += (int16_t)psx_mod_read_half(p + 14u);
    }
    if (layer && parent < 0 && intro_panorama_width(2)) {
        WsViewAnchor foreground;
        if (gpu_ws_bg2d_get_view(0, &foreground))
            view = intro_parallax_view(foreground, layer,
                (int16_t)psx_mod_read_half(0x80097202u));
    }
    int panorama_origin = 0;
    int amazon_width = amazon_panorama(layer, sx, sy, &panorama_origin);
    /* Recycle Lab's distant machinery scrolls at half foreground speed.
     * At the room's left edge the foreground view shifts right as the camera
     * moves, but copying that full shift to this layer pulls its artwork away
     * from the left side and leaves a growing black strip. */
    int recycle_half_scroll = layer == 2 && parent < 0 &&
        psx_mod_read_byte(0x800ccedcu) == 4u &&
        psx_mod_read_byte(0x800cceddu) == 0u &&
        psx_mod_read_byte(b + 4u) == 4u;
    if (amazon_width || recycle_half_scroll) {
        WsViewAnchor foreground;
        if (gpu_ws_bg2d_get_view(0, &foreground))
            view = parallax_view(foreground, 2,
                (int16_t)psx_mod_read_half(0x80097202u));
    }
    /* Turtloid layer1 mode5 is an externally selected 320px weather frame,
     * not a world map. X=320 selects the blank frame; rows select animation
     * artwork. Revealing adjacent cells exposes inactive rain at the left
     * edge. Repeat only the selected native frame, with screen-space phase. */
    int weather = layer == 1 && parent < 0 &&
        psx_mod_read_byte(0x800ccedcu) == 6u && psx_mod_read_byte(0x800cceddu) == 0u &&
        psx_mod_read_byte(b + 4u) == 5u;
    /* Weapon Center's mode5 backdrop is a selected screen-space panorama.
     * Ilumina's independently animated parts are screen-space too. Keep the
     * native 320px panel centered with them and reflect only that panel into
     * the reveal, never the empty neighboring cells of its atlas. */
    int illumina = layer == 2 && parent < 0 &&
        psx_mod_read_byte(0x800ccedcu) == 8u && psx_mod_read_byte(0x800cceddu) == 0u &&
        psx_mod_read_byte(b + 4u) == 5u;
    if (weather || illumina) {
        WsViewAnchor world;
        if (gpu_ws_bg2d_get_view(0, &world)) {
            int extra = (world.left + world.right + world.pad_left + world.pad_right) / 2;
            view = (WsViewAnchor){extra - world.pad_left, extra - world.pad_right,
                                  0, world.pad_left, world.pad_right};
        }
    }
    Mmx6TileMap map = {
        psx_mod_read_word(0x1f800004u), psx_mod_read_word(0x1f800008u),
        psx_mod_read_word(0x1f80000cu), psx_mod_read_byte(0x800cd338u),
        psx_mod_read_half(0x8008ec10u), layer,
        psx_mod_read_byte(b + 0x4du), psx_mod_read_byte(b + 0x4eu)
    };
    if (!mmx6_ram_range(map.map, 1) || !mmx6_ram_range(map.metatiles, 512) ||
        !mmx6_ram_range(map.descriptors, 4)) return;
    int left = (view.left + 15) / 16, right = (view.right + 15) / 16;
    if (left + 21 + right > 2048 || left > 2048 || right > 2027) {
        fprintf(stderr, "MMX6 Custom Renderer: viewport exceeds signed packet coordinates\n");
        return;
    }
    uint32_t cursor = arena + (buffer * 3u + layer) * LAYER_BYTES;
    uint32_t limit = cursor + LAYER_BYTES;
    /* Native packets are initialized as raw SPRT_16; retain the template's
     * command/color bits, replacing only this tile's semi-transparency bit. */
    uint32_t color = psx_mod_read_word(native_packet + 4u);
    if ((color >> 24 & 0xfdu) != 0x7du) color = 0x7d808080u;
    int start_col = sx / 16, start_row = sy / 16;
    int screen_x = -(sx & 15), screen_y = -(sy & 15);
    int panorama_width = parent < 0 ? intro_panorama_width(layer) : 0;
    if (amazon_width) panorama_width = amazon_width;
    if (illumina) {
        panorama_origin = start_col * 16;
        panorama_width = 320;
    }
    int intro = psx_mod_read_byte(0x800ccedcu) == 0 && psx_mod_read_byte(0x800cceddu) == 0;
    int banks = intro && psx_mod_texture_banks_supported() && load_intro_banks(INTRO_BANK);
    int rain_bank = weather && psx_mod_texture_banks_supported() && load_background_bank(WEATHER_BANK);
    /* Replace this layer's current OT lists, including its central 21 columns.
     * Mixing unchanged native columns with reflected extras leaves a moving
     * gap at the panorama edge. Keep the other display buffer and guest ring
     * untouched. All fallible setup/capacity checks precede this operation. */
    for (unsigned g = layer; g <= layer + 3u; g += 3u) for (unsigned i = 0; i < 17u; ++i) {
        uint32_t offset = buffer * 408u + g * 68u + i * 4u;
        uint32_t head = 0x80090e78u + offset;
        psx_mod_write_word(head, 0);
        psx_mod_write_word(0x8008ec18u + offset, head);
    }
    for (int row = 0; row < 16; ++row) {
        for (int col = -left; col < 21 + right; ++col) {
            int tile_x = (start_col + col) * 16, flipped = 0;
            if (weather) tile_x = start_col * 16 + ((col % 20 + 20) % 20) * 16;
            int factory = layer == 0 ? tile_x >= 2048 : layer == 1 ? tile_x >= 1088 : tile_x >= 1280;
            if (panorama_width) {
                factory = 0;
                tile_x = panorama_origin + mmx6_mirror_tile_x(
                    tile_x - panorama_origin, panorama_width, &flipped);
            }
            uint16_t tile = mmx6_map_tile(&map, tile_x,
                (start_row + row) * 16, psx_mod_read_byte, psx_mod_read_half);
            if (!tile) continue;
            uint32_t desc_addr = map.descriptors + (tile & 0x3fffu) * 4u;
            if (!mmx6_ram_range(desc_addr, 4)) continue;
            uint32_t desc = psx_mod_read_word(desc_addr);
            unsigned bucket = (desc >> 24) & 0x3fu;
            if ((desc >> 24) == 255u || bucket >= 17u) continue;
            if (cursor > limit - 32u) return; /* No guest-buffer overrun. */
            unsigned group = layer + ((tile & 0x8000u) ? 3u : 0u);
            uint32_t tail_slot = 0x8008ec18u + buffer * 408u + group * 68u + bucket * 4u;
            uint32_t tail = psx_mod_read_word(tail_slot);
            if (!mmx6_ram_range(tail, 4) && !(tail >= arena && tail < arena + ARENA_BYTES))
                continue;
            int x = screen_x + col * 16, y = screen_y + row * 16;
            psx_mod_write_word(cursor, 0x03000000u);
            psx_mod_write_word(cursor + 4u, (color & ~0x02000000u) |
                ((tile & 0x4000u) ? 0x02000000u : 0u));
            psx_mod_write_word(cursor + 8u, (uint16_t)x | ((uint32_t)(uint16_t)y << 16));
            psx_mod_write_word(cursor + 12u, mmx6_tile_uvclut(desc));
            uint16_t bank = banks && bucket < 12u ? (factory ? FACTORY_BANK : INTRO_BANK) : 0;
            if (rain_bank) bank = WEATHER_BANK;
            psx_mod_write_word(cursor + 16u, bank ? (uint16_t)view.shift | (uint32_t)bank << 16 : (uint32_t)view.shift);
            psx_mod_write_word(cursor + 20u, (uint32_t)view.pad_left);
            psx_mod_write_word(cursor + 24u, (uint32_t)view.pad_right);
            psx_mod_write_word(cursor + 28u, (bank ? GPU_WS_BG2D_BANK_PACKET_MAGIC : GPU_WS_BG2D_PACKET_MAGIC) |
                (flipped ? GPU_WS_BG2D_MIRROR_X : 0u));
            psx_mod_write_word(tail, (psx_mod_read_word(tail) & 0xff000000u) | (cursor & 0xffffffu));
            psx_mod_write_word(tail_slot, cursor);
            cursor += 32u;
        }
    }
}
