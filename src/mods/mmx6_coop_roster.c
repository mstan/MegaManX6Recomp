#include "mmx6_coop_roster.h"
#include <stddef.h>
#include <string.h>

/* Original SLUS-01395 v1.1: character loader80013BF0, native form/parts
 * initializer8003D718, portrait selector800228AC and loader80014314.
 * Full source/asset identities: COOP_SEAT_CHARACTER_AUDIT.json and
 * COOP_OPPOSITE_ROSTER_PLAN.json. No game bytes are bundled here. */
static const Mmx6CoopRosterActor forms[6] = {
    {0,0,0,0x3C,86,0,163,164}, /* Base X. */
    {0,1,0,0x3C,87,3,169,170}, /* Falcon. */
    {0,2,0,0x3C,88,4,171,172}, /* Shadow. */
    {0,3,0,0x3C,89,5,173,174}, /* Blade. */
    {0,4,0,0x3C,86,2,167,168}, /* Ultimate shares DAT86, not form0 behavior. */
    {1,5,1,0x3D,85,1,165,166}  /* Ordinary Zero. */
};

static Mmx6CoopRosterReason identity(uint8_t character, uint8_t form) {
    if (character > MMX6_COOP_CHARACTER_ZERO)
        return MMX6_COOP_ROSTER_INVALID_CHARACTER;
    if (form > MMX6_COOP_FORM_ZERO)
        return MMX6_COOP_ROSTER_INVALID_FORM;
    if (forms[form].character != character)
        return MMX6_COOP_ROSTER_CHARACTER_FORM_MISMATCH;
    return MMX6_COOP_ROSTER_OK;
}

Mmx6CoopRosterReason mmx6_coop_roster_resolve(const Mmx6CoopRosterNative *native,
                                            Mmx6CoopRoster *out) {
    Mmx6CoopRosterReason reason;
    if (out) memset(out,0,sizeof *out);
    if (!native || !out) return MMX6_COOP_ROSTER_INVALID_ARGUMENT;
    reason=identity(native->body_character,native->body_form);
    if (reason!=MMX6_COOP_ROSTER_OK) return reason;
    reason=identity(native->campaign_character,native->campaign_form);
    if (reason!=MMX6_COOP_ROSTER_OK) return reason;
    if (native->body_character!=native->campaign_character ||
        native->body_form!=native->campaign_form)
        return MMX6_COOP_ROSTER_NATIVE_IDENTITY_MISMATCH;
    if (native->flags & MMX6_COOP_NATIVE_BLACK_ZERO)
        return MMX6_COOP_ROSTER_BLACK_ZERO_UNSUPPORTED;
    out->seat[0]=forms[native->body_form];
    out->seat[1]=forms[native->body_character==MMX6_COOP_CHARACTER_ZERO ?
                       MMX6_COOP_FORM_X : MMX6_COOP_FORM_ZERO];
    out->resolved=1;
    return MMX6_COOP_ROSTER_OK;
}

Mmx6CoopRosterReason mmx6_coop_roster_resolve_partner(const Mmx6CoopRosterNative *native,
    unsigned requested_x_form,uint8_t parts,Mmx6CoopRoster *out) {
    Mmx6CoopRosterReason reason=mmx6_coop_roster_resolve(native,out);
    if(reason!=MMX6_COOP_ROSTER_OK)return reason;
    if(requested_x_form>MMX6_COOP_FORM_BLADE) {
        memset(out,0,sizeof *out);return MMX6_COOP_ROSTER_INVALID_FORM;
    }
    if(native->body_character==MMX6_COOP_CHARACTER_ZERO) {
        unsigned form=MMX6_COOP_FORM_X;
        if((requested_x_form==MMX6_COOP_FORM_FALCON && (native->flags&1u)) ||
           (requested_x_form==MMX6_COOP_FORM_SHADOW && (native->flags&2u) && (parts&0xF0u)==0xF0u) ||
           (requested_x_form==MMX6_COOP_FORM_BLADE && (native->flags&4u) && (parts&0x0Fu)==0x0Fu))form=requested_x_form;
        out->seat[1]=forms[form];
    }
    return MMX6_COOP_ROSTER_OK;
}
static int same_resources(const Mmx6CoopRosterActor *a,
                          const Mmx6CoopRosterActor *b) {
    return a->bin_member==b->bin_member && a->bin_type==b->bin_type &&
        a->dat_member==b->dat_member && a->portrait_index==b->portrait_index &&
        a->portrait_graphics==b->portrait_graphics &&
        a->portrait_palette==b->portrait_palette;
}

Mmx6CoopRosterReason mmx6_coop_roster_validate(const Mmx6CoopRoster *roster) {
    unsigned seat;
    if (!roster) return MMX6_COOP_ROSTER_INVALID_ARGUMENT;
    if (roster->resolved!=1) return MMX6_COOP_ROSTER_NOT_RESOLVED;
    for (seat=0;seat<2;++seat) {
        const Mmx6CoopRosterActor *actor=&roster->seat[seat];
        Mmx6CoopRosterReason reason=identity(actor->character,actor->form);
        if (reason!=MMX6_COOP_ROSTER_OK) return reason;
        if (!same_resources(actor,&forms[actor->form]))
            return MMX6_COOP_ROSTER_RESOURCE_MISMATCH;
    }
    if (roster->seat[1].character!=(roster->seat[0].character ^ 1u) ||
        (roster->seat[0].character==MMX6_COOP_CHARACTER_ZERO ?
         roster->seat[1].form>MMX6_COOP_FORM_BLADE : roster->seat[1].form!=MMX6_COOP_FORM_ZERO))
        return MMX6_COOP_ROSTER_COUNTERPART_MISMATCH;
    return MMX6_COOP_ROSTER_OK;
}

const char *mmx6_coop_roster_reason(Mmx6CoopRosterReason reason) {
    switch (reason) {
    case MMX6_COOP_ROSTER_OK: return "ok";
    case MMX6_COOP_ROSTER_INVALID_ARGUMENT: return "invalid_argument";
    case MMX6_COOP_ROSTER_INVALID_CHARACTER: return "invalid_character";
    case MMX6_COOP_ROSTER_INVALID_FORM: return "invalid_form";
    case MMX6_COOP_ROSTER_CHARACTER_FORM_MISMATCH: return "character_form_mismatch";
    case MMX6_COOP_ROSTER_NATIVE_IDENTITY_MISMATCH: return "native_identity_mismatch";
    case MMX6_COOP_ROSTER_BLACK_ZERO_UNSUPPORTED: return "black_zero_unsupported";
    case MMX6_COOP_ROSTER_NOT_RESOLVED: return "not_resolved";
    case MMX6_COOP_ROSTER_RESOURCE_MISMATCH: return "resource_mismatch";
    case MMX6_COOP_ROSTER_COUNTERPART_MISMATCH: return "counterpart_mismatch";
    default: return "unknown_roster_reason";
    }
}
