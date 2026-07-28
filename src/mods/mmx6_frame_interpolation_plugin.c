#include "mod_plugins.h"

#include <stdlib.h>
#include <string.h>

/*
 * Presentation-only frame interpolation, moved out of generic recomp-ui
 * Settings into the mod catalog (game.toml sets
 * [video] offer_frame_interpolation = false).
 *
 * Deliberately psx_mod_set_frame_interpolation and NOT
 * psx_mod_set_native_vblank_rate: the former blends between completed guest
 * frames and leaves VBlank, logic, timers, and audio at their stock cadence,
 * while the latter changes whole-machine realtime speed. Conflating the two is
 * how "smoother" turns into "the game runs fast", so this package exposes only
 * the presentation half.
 */
#define PKG "mmx6.enhancement.frame-interpolation"
#define FEATURE "frame-interpolation"

static void mmx6_frame_interpolation_activate(void) {
    char rate[16];
    unsigned long fps = 0ul;   /* 0 = follow the measured display refresh */

    /* An unreadable or unrecognised value falls back to the manifest default
     * ("display"), which is the conservative choice: it follows the monitor
     * instead of pinning a rate the panel may not support. */
    if (psx_mod_option_value(PKG, FEATURE, "rate", rate, sizeof rate) &&
        strcmp(rate, "display") != 0) {
        char* end = rate;
        const unsigned long parsed = strtoul(rate, &end, 10);
        if (end != rate && *end == '\0') fps = parsed;
    }

    (void)psx_mod_set_frame_interpolation((uint32_t)fps);
}

PSX_MOD_CONSTRUCTOR(mmx6_register_frame_interpolation_plugin) {
    (void)psx_mod_register_activation_plugin(
        "mmx6.frame-interpolation", mmx6_frame_interpolation_activate);
}
