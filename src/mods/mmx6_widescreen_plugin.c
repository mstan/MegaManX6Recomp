#include "mod_plugins.h"
#include "gpu.h"
#include "cpu_state.h"

#include <string.h>

/*
 * Mega Man X6's widescreen hooks (full_2d gameplay classification, the widened
 * bg2d tile loop + streamer, reveal-clear, HUD corner-anchor range, intro-stage
 * cull relaxes) live in generated/runtime code and are identity at 4:3. Only
 * their player-facing ACTIVATION moves here, out of generic recomp-ui Settings
 * and into the mod catalog — game.toml sets [widescreen] offer = false so the
 * launcher no longer carries an aspect row for this title.
 *
 * The package declares one choice option instead of the two Settings rows it
 * replaces (aspect + a separate experimental 21:9 row), so 16:9 and 21:9 are
 * presented as what they are: two settings of one experimental enhancement.
 */
#define PKG "mmx6.enhancement.widescreen"
#define FEATURE "widescreen"

static void mmx6_bg_view_begin(CPUState *cpu, uint32_t address) {
    (void)address;
    gpu_ws_bg2d_begin_view_layer(cpu->gpr[4], psx_mod_read_word(0x1f800108u), 6u);
}
static void mmx6_bg_view_end(CPUState *cpu, uint32_t address) {
    (void)address;
    gpu_ws_bg2d_end_view_layer(cpu->gpr[4], psx_mod_read_word(0x1f800108u));
}
/* The four object renderers select screen coordinates when their camera
 * selector is negative: +0x14 for sprite objects, +0x37 for polygon objects.
 * Finalize a producer's packet range when the next producer starts (or when
 * the driver reaches its final OT setup). All use 0x28-byte packet slots.
 * This preserves dialogue composites as one centered group without confusing
 * foreground props in the same packet arena with UI. */
static uint32_t ui_packet_begin;
static int ui_packet_pending;
static void mmx6_finish_ui_packets(uint32_t end) {
    if (ui_packet_pending && end >= ui_packet_begin &&
        end - ui_packet_begin <= 1000u * 0x28u) {
        for (uint32_t p = ui_packet_begin; p < end; p += 0x28u)
            gpu_ws_tag_hud_prim(p, 0);
    }
    ui_packet_pending = 0;
}
static void mmx6_object_view_begin(CPUState *cpu, uint32_t address) {
    uint32_t packet = psx_mod_read_word(0x1f800100u);
    mmx6_finish_ui_packets(packet);
    unsigned selector = (address == 0x800232d4u || address == 0x800239ccu)
                      ? 0x14u : 0x37u;
    ui_packet_pending = (int8_t)psx_mod_read_byte(cpu->gpr[4] + selector) < 0;
    ui_packet_begin = packet;
}
static void mmx6_object_view_end(CPUState *cpu, uint32_t address) {
    (void)cpu; (void)address;
    mmx6_finish_ui_packets(psx_mod_read_word(0x1f800100u));
}
static void mmx6_widescreen_activate(void) {
    char aspect[16], camera[16];
    if (!psx_mod_option_value(PKG, FEATURE, "camera", camera, sizeof camera))
        strcpy(camera, "edges");
    /* SLUS-01395 v1.1 FUN_8002820C clamps layer0+0xA between +0x1E
     * (minimum) and +0x1C (maximum). This is read-only host presentation. */
    if (strcmp(camera, "edges") == 0) {
        gpu_ws_set_view_anchor(0x80097202u, 0x80097216u, 0x80097214u, 0x800971F8u);
        (void)psx_mod_register_function_entry_plugin("mmx6.widescreen", 0x800270d0u, mmx6_bg_view_begin);
        (void)psx_mod_register_function_entry_plugin("mmx6.widescreen", 0x80026eccu, mmx6_bg_view_end);
        static const uint32_t object_renderers[] = {
            0x800232d4u, 0x800239ccu, 0x80023ed8u, 0x800241d4u
        };
        for (unsigned i = 0; i < sizeof object_renderers / sizeof object_renderers[0]; i++)
            (void)psx_mod_register_function_entry_plugin("mmx6.widescreen",
                object_renderers[i], mmx6_object_view_begin);
        (void)psx_mod_register_function_entry_plugin("mmx6.widescreen", 0x80022e44u, mmx6_object_view_end);
    }

    /* Fall back to the manifest default rather than guessing wide, so a failed
     * read can only ever under-apply. 21:9 is requested as ADAPTIVE (follows
     * the window up to that cap) because a hard 21:9 letterboxes players whose
     * display is narrower; the fixed selection sets the initial window, which
     * is why it is applied first in both branches. */
    if (!psx_mod_option_value(PKG, FEATURE, "aspect", aspect, sizeof aspect))
        strcpy(aspect, "16:9");

    (void)psx_mod_set_fixed_display_aspect(16u, 9u);
    if (strcmp(aspect, "21:9") == 0)
        (void)psx_mod_set_adaptive_display_aspect(21u, 9u);
}

PSX_MOD_CONSTRUCTOR(mmx6_register_widescreen_plugin) {
    (void)psx_mod_register_activation_plugin(
        "mmx6.widescreen", mmx6_widescreen_activate);
}
