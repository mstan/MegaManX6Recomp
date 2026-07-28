#include "mod_plugins.h"

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

static void mmx6_widescreen_activate(void) {
    char aspect[16];

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
