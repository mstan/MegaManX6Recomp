#ifndef MMX6_COOP_ROSTER_H
#define MMX6_COOP_ROSTER_H

#include <stdint.h>

enum {
    MMX6_COOP_CHARACTER_X = 0,
    MMX6_COOP_CHARACTER_ZERO = 1,
    MMX6_COOP_FORM_X = 0,
    MMX6_COOP_FORM_FALCON = 1,
    MMX6_COOP_FORM_SHADOW = 2,
    MMX6_COOP_FORM_BLADE = 3,
    MMX6_COOP_FORM_ULTIMATE = 4,
    MMX6_COOP_FORM_ZERO = 5,
    MMX6_COOP_NATIVE_BLACK_ZERO = 0x20
};

/* Read by the caller only after original P1 initialization has completed.
 * PLAYER+02/+E7 and PLAY+38/+5E must describe the same native actor.
 * flags is the unchanged PLAY+5F byte. The resolver never grants/removes an
 * unlock, writes native state, samples input, or accesses mounted assets. */
typedef struct {
    uint8_t body_character, body_form;
    uint8_t campaign_character, campaign_form;
    uint8_t flags;
} Mmx6CoopRosterNative;

/* Source-owned archive IDs, not loaded pointers or proof of asset residency.
 * Overlay type is the original BIN member's leading type word (3C/3D).
 * The caller must validate actual asset bytes/types/lengths separately.
 * Serialize/hash named fields explicitly; never the C object representation. */
typedef struct {
    uint8_t character, form;
    uint8_t bin_member, bin_type, dat_member;
    uint8_t portrait_index, portrait_graphics, portrait_palette;
} Mmx6CoopRosterActor;

typedef struct {
    uint8_t resolved; /* Exactly 1 only after successful resolution. */
    Mmx6CoopRosterActor seat[2]; /* Native campaign P1, then private P2. */
} Mmx6CoopRoster;

typedef enum {
    MMX6_COOP_ROSTER_OK,
    MMX6_COOP_ROSTER_INVALID_ARGUMENT,
    MMX6_COOP_ROSTER_INVALID_CHARACTER,
    MMX6_COOP_ROSTER_INVALID_FORM,
    MMX6_COOP_ROSTER_CHARACTER_FORM_MISMATCH,
    MMX6_COOP_ROSTER_NATIVE_IDENTITY_MISMATCH,
    MMX6_COOP_ROSTER_BLACK_ZERO_UNSUPPORTED,
    MMX6_COOP_ROSTER_NOT_RESOLVED,
    MMX6_COOP_ROSTER_RESOURCE_MISMATCH,
    MMX6_COOP_ROSTER_COUNTERPART_MISMATCH
} Mmx6CoopRosterReason;

/* Native X/form0..4 -> private Zero5; native Zero5 -> private base X0.
 * Every accepted roster includes Zero. PLAY+5F bit20 would select the native
 * Black Zero variant when that actor is projected, so both directions refuse
 * it until its resource/behavior closure is implemented. Other availability
 * bits do not gate this resolver: original campaign selection owns them, and
 * the existing early-game private Zero policy does not require its unlock.
 * On any failure a non-NULL out is cleared, including stale prior success. */
Mmx6CoopRosterReason mmx6_coop_roster_resolve(const Mmx6CoopRosterNative *native,
                                            Mmx6CoopRoster *out);

/* Checks canonical actor resources and the fixed counterpart policy only.
 * To compare against current guest identity/flags, resolve those native reads
 * again. This does not assert callback readiness or freeze campaign progress. */
Mmx6CoopRosterReason mmx6_coop_roster_validate(const Mmx6CoopRoster *roster);
const char *mmx6_coop_roster_reason(Mmx6CoopRosterReason reason);

#endif
