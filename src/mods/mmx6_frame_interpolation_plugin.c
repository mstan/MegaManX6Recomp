#include "mod_plugins.h"

/*
 * Keep Mega Man X6's guest cadence completely stock. These callbacks only
 * select how frequently PSXrecomp's OpenGL presentation thread blends between
 * the two most recent completed game frames.
 */
static void mmx6_frame_rate_set(unsigned frames_per_second) {
    (void)psx_mod_set_frame_interpolation_blend(
        PSX_MOD_FRAME_INTERPOLATION_MOTION_ADAPTIVE);
    (void)psx_mod_set_frame_interpolation(frames_per_second);
}

static void mmx6_frame_rate_60_activate(void) {
    mmx6_frame_rate_set(60u);
}

static void mmx6_frame_rate_120_activate(void) {
    mmx6_frame_rate_set(120u);
}

static void mmx6_frame_rate_144_activate(void) {
    mmx6_frame_rate_set(144u);
}

static void mmx6_frame_rate_165_activate(void) {
    mmx6_frame_rate_set(165u);
}

static void mmx6_frame_rate_display_activate(void) {
    mmx6_frame_rate_set(0u);
}

PSX_MOD_CONSTRUCTOR(mmx6_register_frame_interpolation_plugin) {
    (void)psx_mod_register_activation_plugin(
        "mmx6.framerate.60", mmx6_frame_rate_60_activate);
    (void)psx_mod_register_activation_plugin(
        "mmx6.framerate.120", mmx6_frame_rate_120_activate);
    (void)psx_mod_register_activation_plugin(
        "mmx6.framerate.144", mmx6_frame_rate_144_activate);
    (void)psx_mod_register_activation_plugin(
        "mmx6.framerate.165", mmx6_frame_rate_165_activate);
    (void)psx_mod_register_activation_plugin(
        "mmx6.framerate.uncapped", mmx6_frame_rate_display_activate);
}
