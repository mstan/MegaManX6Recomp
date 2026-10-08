/* Original call sites of loads the game blocks on behind its loading screen
 * (return addresses, i.e. jal + 8). Each is followed by 80015EC0, 80016178 or
 * 8001494C. Background actor loads (800528F4, 80052E44/80014B78) are absent
 * by design. Shared by the adapter and the mod compatibility matrix test. */
#pragma once
#include <stdint.h>

/* after jal 80014F70 (packed start); read from 80014F70's frame at sp+40 */
static const uint32_t mmx6_seamless_pack_callers[] = {
    0x80013C54u, 0x80013C6Cu, 0x80013D90u, 0x8001407Cu, 0x800140A8u, 0x800140F0u,
    0x80014124u, 0x800141D8u, 0x80014494u, 0x800144C4u, 0x80016094u, 0x800162D8u,
    0x8001DCBCu};
/* after jal 80016858 (BIN start); read from 80016858's frame at sp+28 */
static const uint32_t mmx6_seamless_bin_callers[] = {
    0x80013CE4u, 0x80013CF8u, 0x80013D5Cu, 0x80013E48u, 0x80013E84u};
/* after jal 80014E60 in 8001494C, 80015EC0, 80016178 and 8001642C */
static const uint32_t mmx6_seamless_raw_callers[] = {
    0x80014A90u, 0x80016070u, 0x800162B4u, 0x80016504u};
/* 8001642C's own callers are all blocking: 80014330, 80014390, 80014424,
 * 80014440 (stage start), 800173B8 (8001731C), 8001D4D0 (8001D460). */
