#include "mod_plugins.h"
#include "gpu.h"
#include "cpu_state.h"
#include "mmx6_adaptive_background.h"

#include <string.h>

/* Default-off Custom Renderer. Native producers stay within their ring/budget;
 * the host replaces each layer's tile lists with a continuous expanded view.
 * Visible actors share the live view; scene triggers retain native reach. */
#define PKG "mmx6.enhancement.widescreen"
#define FEATURE "widescreen"

static void mmx6_bg_view_begin(CPUState *cpu, uint32_t address) {
    (void)address;
    mmx6_adaptive_background_begin(cpu->gpr[4]);
    gpu_ws_bg2d_begin_view_layer(cpu->gpr[4], psx_mod_read_word(0x1f800108u), 6u);
}
static void mmx6_bg_view_end(CPUState *cpu, uint32_t address) {
    (void)address;
    uint32_t packet = psx_mod_read_word(0x1f800108u);
    gpu_ws_bg2d_end_view_layer(cpu->gpr[4], packet);
    mmx6_adaptive_background_end(cpu->gpr[4], packet);
}
/* The four object renderers select screen coordinates when their camera
 * selector is negative: +0x14 for sprite objects, +0x37 for polygon objects.
 * Finalize a producer's packet range when the next producer starts (or when
 * the driver reaches its final OT setup). All use 0x28-byte packet slots.
 * This preserves dialogue composites as one centered group without confusing
 * foreground props in the same packet arena with UI. */
static uint32_t ui_packet_begin;
static int ui_packet_pending, ui_packet_screen;
static void mmx6_finish_ui_packets(uint32_t end) {
    if (ui_packet_pending && end >= ui_packet_begin &&
        end - ui_packet_begin <= 1000u * 0x28u) {
        for (uint32_t p = ui_packet_begin; p < end; p += 0x28u) {
            psx_mod_tag_world_primitive(p, !ui_packet_screen);
            if (ui_packet_screen) gpu_ws_tag_hud_prim(p, 0);
        }
    }
    ui_packet_pending = 0;
}
static void mmx6_object_view_begin(CPUState *cpu, uint32_t address) {
    uint32_t packet = psx_mod_read_word(0x1f800100u);
    mmx6_finish_ui_packets(packet);
    unsigned selector = (address == 0x800232d4u || address == 0x800239ccu)
                      ? 0x14u : 0x37u;
    ui_packet_screen = (int8_t)psx_mod_read_byte(cpu->gpr[4] + selector) < 0;
    ui_packet_pending = 1;
    ui_packet_begin = packet;
}
static void mmx6_object_view_end(CPUState *cpu, uint32_t address) {
    (void)cpu; (void)address;
    mmx6_finish_ui_packets(psx_mod_read_word(0x1f800100u));
}
static int mmx6_native_enemy(unsigned category, unsigned type) {
    /* Type0E owns the room's rain generator, children and shared weather
     * index at 800F6BA0. Initializing the next room early corrupts this one. */
    return psx_mod_read_byte(0x800ccedcu) == 6u && category < 3u &&
           (type == 0x0au || type == 0x0eu);
}
/* Retail common bounds classifiers: 8002CBFC returns outside-view for actor
 * lifetime decisions; 8002CCB0 sets object+3 for drawing. Both copy a1 as the
 * horizontal radius and use a2 only vertically. Widen both with the same
 * constant envelope, so an actor cannot disappear while its sprite is in the
 * revealed view. Negative camera selectors denote screen-space UI. */
static void mmx6_actor_view_bounds(CPUState *cpu, uint32_t address) {
    /* Rainy Turtloid's type0A water pursuer uses the common lifetime helper
     * at 800EAD64. Its native 64px guard is part of the encounter, not just
     * rendering. Keep drawing visible survivors, but never extend pursuit. */
    uint32_t actor = cpu->gpr[4];
    if (address == 0x8002cbfcu &&
        actor >= 0x8008ef48u && actor < 0x80090c88u &&
        (actor - 0x8008ef48u) % 0x9cu == 0 &&
        mmx6_native_enemy(0, psx_mod_read_byte(actor + 1u))) return;
    int32_t margin = psx_mod_widescreen_x_margin();
    if (margin > 0 && (int8_t)psx_mod_read_byte(cpu->gpr[4] + 0x14u) >= 0)
        cpu->gpr[5] += (uint32_t)margin;
}
/* Retail's fixed-radius draw classifiers duplicate 8002CCB0 with radii
 * (32,32) and (96,80). Doors use the former; frozen actors use the latter.
 * Delegate to that native parameterized helper and its existing wide hook,
 * keeping the vertical test, live display width and screen-space UI native. */
static int mmx6_fixed_actor_view_filter(CPUState *cpu, uint32_t address) {
    if (psx_mod_widescreen_x_margin() <= 0 ||
        (int8_t)psx_mod_read_byte(cpu->gpr[4] + 0x14u) < 0) return 0;
    cpu->gpr[5] = address == 0x8002cb50u ? 32u : 96u;
    cpu->gpr[6] = address == 0x8002cb50u ? 32u : 80u;
    uint32_t caller = cpu->gpr[31];
    psx_dispatch_call(cpu, 0x8002ccb0u, caller);
    return 1;
}
static int mmx6_intro_scene(void) {
    return psx_mod_read_byte(0x800ccedcu) == 0 &&
           psx_mod_read_byte(0x800cceddu) == 0;
}
/* Intro type8 initializes its sprite independently, then phase0 at 800F9334
 * takes control of X immediately. Hold only that phase until its placement
 * enters the original scan rectangle. Native animation/drawing continues.
 * Keep this guard after shrinking to 4:3: an already-previewed actor must not
 * start a cutscene merely because the window changed size. */
static int mmx6_intro_npc_start_filter(CPUState *cpu, uint32_t address) {
    (void)address;
    uint32_t actor = cpu->gpr[4];
    if (!mmx6_intro_scene() || psx_mod_read_byte(actor + 1u) != 8u ||
        psx_mod_read_byte(actor + 2u) != 0u ||
        psx_mod_read_byte(actor + 4u) != 1u ||
        psx_mod_read_byte(actor + 5u) != 0u) return 0;
    uint32_t record = psx_mod_read_word(actor + 0x10u);
    if ((record & 0xffe00000u) != 0x80000000u ||
        psx_mod_read_byte(record + 1u) != 8u ||
        (psx_mod_read_byte(record + 3u) & 15u) != 5u) return 0;
    int x = (int16_t)psx_mod_read_half(record + 4u);
    int y = (int16_t)psx_mod_read_half(record + 6u);
    int camera_x = (int16_t)psx_mod_read_half(0x80097202u);
    int camera_y = (int16_t)psx_mod_read_half(0x80097206u);
    return x <= camera_x - 48 || x >= camera_x + 368 ||
           y <= camera_y - 48 || y >= camera_y + 288;
}
static uint32_t resize_state;
static int supplemental_scan;
/* Categories 0..2 are difficulty-gated enemies. Other categories allocate
 * event, NPC and effect pools whose constructors may immediately take control
 * of X. Intro enemy 0x30 is the boss, also started by placement activation.
 * Audited visible exceptions: resident type8 doors trigger on player contact;
 * intro type2 breakable blocks have ordinary damage/lifetime logic; intro
 * type8 NPCs have a separate guarded sequence phase. Other scene controllers
 * remain native. Retail scans retain offsets, difficulty and latch rules. */
static int mmx6_extra_placement_filter(CPUState *cpu, uint32_t address) {
    (void)address;
    if (!supplemental_scan) return 0;
    uint32_t record = cpu->gpr[4];
    unsigned category = psx_mod_read_byte(record + 3u) & 15u;
    unsigned type = psx_mod_read_byte(record + 1u);
    int intro = mmx6_intro_scene();
    int boss = intro && type == 0x30;
    if (category < 3u && !boss && !mmx6_native_enemy(category, type)) return 0;
    if (category == 4u && (type == 8u || (intro && type == 2u))) return 0;
    if (intro && category == 5u && type == 8u &&
        psx_mod_read_byte(record + 2u) == 0u) return 0;
    cpu->gpr[2] = 1; /* Native eligibility result: defer this placement. */
    return 1;
}
static int signed_bound(int value) {
    return value < -32768 ? -32768 : value > 32767 ? 32767 : value;
}
/* The generated scan widens respawn-reset bounds for visible ordinary actors.
 * Restore retail reset semantics for native encounters only: inactive records,
 * outside the closed native reset rectangle, advance 10/30/50 -> 20/40/60.
 * Active and permanent-disabled placements remain untouched. */
static void mmx6_reset_native_placements(int x, int y) {
    if (psx_mod_read_byte(0x800ccedcu) != 6u) return;
    unsigned area = psx_mod_read_byte(0x800cceddu);
    if (area > 1) return;
    uint32_t p = psx_mod_read_word(0x8007349cu + 6u * 8u + area * 4u);
    for (unsigned i = 0; i < 2048u && mmx6_ram_range(p, 8u); ++i, p += 8u) {
        unsigned flags = psx_mod_read_byte(p + 3u);
        if (flags == 15u) break;
        if ((psx_mod_read_byte(p) & 0x81u) ||
            !mmx6_native_enemy(flags & 15u, psx_mod_read_byte(p + 1u))) continue;
        int px = (int16_t)psx_mod_read_half(p + 4u);
        int py = (int16_t)psx_mod_read_half(p + 6u);
        unsigned latch = flags & 0xf0u;
        if ((px < x - 48 || px > x + 368 || py < y - 48 || py > y + 288) &&
            (latch == 0x10u || latch == 0x30u || latch == 0x50u))
            psx_mod_write_byte(p + 3u, (uint8_t)(flags + 0x10u));
    }
}
/* Keep retail activation unmodified. Scan the revealed strips separately so
 * enemies can become visible on movement or stationary resize, while script
 * controllers wait for the original scan to reach them. No persistent pending
 * list: restored saves and changing aspect use the same guest placement flags. */
static void mmx6_resize_placement_scan(CPUState *cpu, uint32_t address) {
    (void)address;
    int margin = psx_mod_widescreen_x_margin();
    /* Preserve the existing allocation layout for earlier review saves. */
    psx_mod_write_word(resize_state, 0x58365253u);
    psx_mod_write_word(resize_state + 4u, (uint32_t)margin);
    if (margin <= 0) return;
    int x = (int16_t)psx_mod_read_half(0x80097202u);
    int y = (int16_t)psx_mod_read_half(0x80097206u);
    mmx6_reset_native_placements(x, y);
    CPUState saved = *cpu;
    for (unsigned side = 0; side < 2; ++side) {
        *cpu = saved;
        cpu->gpr[29] -= 32u;
        uint32_t arg = cpu->gpr[29] + 16u;
        uint32_t original_arg = psx_mod_read_word(arg);
        cpu->gpr[4] = (uint32_t)signed_bound(side ? x - 48 - margin : x + 368);
        cpu->gpr[5] = (uint32_t)signed_bound(side ? x - 48 : x + 368 + margin);
        cpu->gpr[6] = (uint32_t)signed_bound(y - 48);
        cpu->gpr[7] = (uint32_t)signed_bound(y + 288);
        psx_mod_write_word(arg, side ? 2u : 1u);
        cpu->gpr[31] = side ? 0x80029dccu : 0x80029d84u;
        supplemental_scan = 1;
        psx_dispatch_call(cpu, 0x80029f38u, cpu->gpr[31]);
        supplemental_scan = 0;
        psx_mod_write_word(arg, original_arg);
        /* Keep hardware completion deadlines and all globally charged cycles;
         * restore the interrupted caller's registers and load pipeline. */
        if (cpu->muldiv_ts_done > saved.muldiv_ts_done) saved.muldiv_ts_done = cpu->muldiv_ts_done;
        if (cpu->gte_ts_done > saved.gte_ts_done) saved.gte_ts_done = cpu->gte_ts_done;
    }
    *cpu = saved;
}
static void mmx6_widescreen_activate(void) {
    char aspect[16], camera[16];
    if (!mmx6_adaptive_background_activate()) return;
    resize_state = psx_mod_alloc_guest_memory(8u, 4u);
    if (resize_state)
        (void)psx_mod_register_function_entry_plugin("mmx6.widescreen", 0x80029d18u, mmx6_resize_placement_scan);
    (void)psx_mod_register_function_filter_plugin("mmx6.widescreen", 0x80029e7cu, mmx6_extra_placement_filter);
    (void)psx_mod_register_function_filter_plugin("mmx6.widescreen", 0x8002cb50u, mmx6_fixed_actor_view_filter);
    (void)psx_mod_register_function_filter_plugin("mmx6.widescreen", 0x8002cd6cu, mmx6_fixed_actor_view_filter);
    (void)psx_mod_register_function_filter_plugin("mmx6.widescreen", 0x800f9334u, mmx6_intro_npc_start_filter);
    if (!psx_mod_option_value(PKG, FEATURE, "camera", camera, sizeof camera))
        strcpy(camera, "edges");
    /* SLUS-01395 v1.1 FUN_8002820C clamps layer0+0xA between +0x1E
     * (minimum) and +0x1C (maximum). This is read-only host presentation. */
    if (strcmp(camera, "edges") == 0) {
        gpu_ws_set_view_anchor(0x80097202u, 0x80097216u, 0x80097214u, 0x800971F8u);
    }
    (void)psx_mod_register_function_entry_plugin("mmx6.widescreen", 0x800270d0u, mmx6_bg_view_begin);
    (void)psx_mod_register_function_entry_plugin("mmx6.widescreen", 0x80026eccu, mmx6_bg_view_end);
    static const uint32_t object_renderers[] = {
        0x800232d4u, 0x800239ccu, 0x80023ed8u, 0x800241d4u
    };
    for (unsigned i = 0; i < sizeof object_renderers / sizeof object_renderers[0]; i++)
        (void)psx_mod_register_function_entry_plugin("mmx6.widescreen",
            object_renderers[i], mmx6_object_view_begin);
    (void)psx_mod_register_function_entry_plugin("mmx6.widescreen", 0x80022e44u, mmx6_object_view_end);
    /* Applies to both edge-anchored and original centered widescreen. */
    (void)psx_mod_register_function_entry_plugin("mmx6.widescreen", 0x8002cbfcu, mmx6_actor_view_bounds);
    (void)psx_mod_register_function_entry_plugin("mmx6.widescreen", 0x8002ccb0u, mmx6_actor_view_bounds);

    /* Fit follows the live drawable with no aspect ceiling. Fixed choices
     * request the same renderer at an explicit aspect. */
    if (!psx_mod_option_value(PKG, FEATURE, "aspect", aspect, sizeof aspect))
        strcpy(aspect, "Fit");
    unsigned numerator = strcmp(aspect, "21:9") == 0 ? 21u :
        strcmp(aspect, "32:9") == 0 ? 32u : 16u;
    (void)psx_mod_set_fixed_display_aspect(numerator, 9u);
    if (strcmp(aspect, "16:9") && strcmp(aspect, "21:9") && strcmp(aspect, "32:9"))
        (void)psx_mod_set_adaptive_display_aspect(0u, 0u);
}

PSX_MOD_CONSTRUCTOR(mmx6_register_widescreen_plugin) {
    (void)psx_mod_register_activation_plugin(
        "mmx6.widescreen", mmx6_widescreen_activate);
}
