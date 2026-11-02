#include "mmx6_coop_roster.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { \
    fprintf(stderr,"line %d: %s\n",__LINE__,#x); exit(1); \
} } while (0)

/* Expected records from original80013BF0 and portrait arithmetic163/164+2*i,
 * pinned in COOP_OPPOSITE_ROSTER_PLAN.json. No original binary is needed. */
static const struct {
    uint8_t character, form, bin, type, dat, portrait;
} native_forms[] = {
    {0,0,0,0x3C,86,0}, {0,1,0,0x3C,87,3}, {0,2,0,0x3C,88,4},
    {0,3,0,0x3C,89,5}, {0,4,0,0x3C,86,2}, {1,5,1,0x3D,85,1}
};

static Mmx6CoopRosterNative native(unsigned form, unsigned flags) {
    Mmx6CoopRosterNative n;
    n.body_character=n.campaign_character=native_forms[form].character;
    n.body_form=n.campaign_form=(uint8_t)form;
    n.flags=(uint8_t)flags;
    return n;
}

static Mmx6CoopRoster resolved(unsigned form) {
    Mmx6CoopRoster roster;
    Mmx6CoopRosterNative n=native(form,0);
    CHECK(mmx6_coop_roster_resolve(&n,&roster)==MMX6_COOP_ROSTER_OK);
    CHECK(mmx6_coop_roster_validate(&roster)==MMX6_COOP_ROSTER_OK);
    return roster;
}

static void actor_matches(const Mmx6CoopRosterActor *actor,unsigned form) {
    CHECK(actor->character==native_forms[form].character);
    CHECK(actor->form==native_forms[form].form);
    CHECK(actor->bin_member==native_forms[form].bin);
    CHECK(actor->bin_type==native_forms[form].type);
    CHECK(actor->dat_member==native_forms[form].dat);
    CHECK(actor->portrait_index==native_forms[form].portrait);
    CHECK(actor->portrait_graphics==163+2*native_forms[form].portrait);
    CHECK(actor->portrait_palette==164+2*native_forms[form].portrait);
}

static void refusal(Mmx6CoopRosterNative n,Mmx6CoopRosterReason expected) {
    Mmx6CoopRosterNative before=n;
    Mmx6CoopRoster roster=resolved(5), empty;
    memset(&empty,0,sizeof empty);
    CHECK(mmx6_coop_roster_resolve(&n,&roster)==expected);
    CHECK(!memcmp(&n,&before,sizeof n));
    CHECK(!memcmp(&roster,&empty,sizeof roster));
    CHECK(mmx6_coop_roster_validate(&roster)==MMX6_COOP_ROSTER_NOT_RESOLVED);
}

static void native_resolution(void) {
    unsigned form,flags,other;
    for (form=0;form<6;++form) for (flags=0;flags<256;++flags) {
        Mmx6CoopRosterNative n=native(form,flags),before=n;
        Mmx6CoopRoster roster;
        if (flags & 0x20u) {
            /* P1 or projected P2 is Zero: shared bit selects unsupported art.
             * Do not clear it, even when no Zero availability bit is set. */
            refusal(n,MMX6_COOP_ROSTER_BLACK_ZERO_UNSUPPORTED);
            continue;
        }
        CHECK(mmx6_coop_roster_resolve(&n,&roster)==MMX6_COOP_ROSTER_OK);
        CHECK(!memcmp(&n,&before,sizeof n));
        CHECK(roster.resolved==1);
        CHECK(mmx6_coop_roster_validate(&roster)==MMX6_COOP_ROSTER_OK);
        actor_matches(&roster.seat[0],form);
        actor_matches(&roster.seat[1],form==5?0:5);
    }
    /* Two independently valid native identities must agree exactly. X form
     * differences are not silently normalized or copied into the counterpart. */
    for (form=0;form<6;++form) for (other=0;other<6;++other) if (form!=other) {
        Mmx6CoopRosterNative n=native(form,0);
        n.campaign_character=native_forms[other].character;
        n.campaign_form=(uint8_t)other;
        refusal(n,MMX6_COOP_ROSTER_NATIVE_IDENTITY_MISMATCH);
    }
    /* Base and Ultimate intentionally share DAT86, but form/portrait differ. */
    {
        Mmx6CoopRoster base=resolved(0),ultimate=resolved(4),opposite=resolved(5);
        CHECK(base.seat[0].dat_member==ultimate.seat[0].dat_member);
        CHECK(base.seat[0].form!=ultimate.seat[0].form);
        CHECK(base.seat[0].portrait_graphics!=ultimate.seat[0].portrait_graphics);
        CHECK(opposite.seat[1].form==0 && opposite.seat[1].dat_member==86);
    }
}

static void invalid_native(void) {
    unsigned value,form;
    for (value=2;value<256;++value) {
        Mmx6CoopRosterNative n=native(0,0);
        n.body_character=(uint8_t)value;
        refusal(n,MMX6_COOP_ROSTER_INVALID_CHARACTER);
        n=native(0,0);n.campaign_character=(uint8_t)value;
        refusal(n,MMX6_COOP_ROSTER_INVALID_CHARACTER);
    }
    for (value=6;value<256;++value) {
        Mmx6CoopRosterNative n=native(0,0);
        n.body_form=(uint8_t)value;
        refusal(n,MMX6_COOP_ROSTER_INVALID_FORM);
        n=native(0,0);n.campaign_form=(uint8_t)value;
        refusal(n,MMX6_COOP_ROSTER_INVALID_FORM);
    }
    for (form=0;form<6;++form) {
        Mmx6CoopRosterNative n=native(form,0);
        n.body_character^=1u;
        refusal(n,MMX6_COOP_ROSTER_CHARACTER_FORM_MISMATCH);
        n=native(form,0);n.campaign_character^=1u;
        refusal(n,MMX6_COOP_ROSTER_CHARACTER_FORM_MISMATCH);
    }
    {
        Mmx6CoopRoster roster=resolved(5),empty;
        Mmx6CoopRosterNative n=native(0,0),before=n;
        memset(&empty,0,sizeof empty);
        CHECK(mmx6_coop_roster_resolve(NULL,&roster)==MMX6_COOP_ROSTER_INVALID_ARGUMENT);
        CHECK(!memcmp(&roster,&empty,sizeof roster));
        CHECK(mmx6_coop_roster_resolve(&n,NULL)==MMX6_COOP_ROSTER_INVALID_ARGUMENT);
        CHECK(!memcmp(&n,&before,sizeof n));
        CHECK(mmx6_coop_roster_resolve(NULL,NULL)==MMX6_COOP_ROSTER_INVALID_ARGUMENT);
        CHECK(mmx6_coop_roster_validate(NULL)==MMX6_COOP_ROSTER_INVALID_ARGUMENT);
    }
}

static void canonical_validation(void) {
    unsigned form,seat,field,value;
    for (form=0;form<6;++form) for (seat=0;seat<2;++seat) {
        for (field=0;field<6;++field) {
            Mmx6CoopRoster roster=resolved(form);
            Mmx6CoopRosterActor *a=&roster.seat[seat];
            /* Each source-bound resource field independently rejects damage. */
            switch (field) {
            case 0: a->bin_member^=1u;break;
            case 1: a->bin_type^=1u;break;
            case 2: a->dat_member^=1u;break;
            case 3: a->portrait_index^=1u;break;
            case 4: a->portrait_graphics^=1u;break;
            case 5: a->portrait_palette^=1u;break;
            }
            CHECK(mmx6_coop_roster_validate(&roster)==MMX6_COOP_ROSTER_RESOURCE_MISMATCH);
        }
        {
            Mmx6CoopRoster roster=resolved(form);
            roster.seat[seat].character=2;
            CHECK(mmx6_coop_roster_validate(&roster)==MMX6_COOP_ROSTER_INVALID_CHARACTER);
            roster=resolved(form);roster.seat[seat].form=6;
            CHECK(mmx6_coop_roster_validate(&roster)==MMX6_COOP_ROSTER_INVALID_FORM);
            roster=resolved(form);roster.seat[seat].character^=1u;
            CHECK(mmx6_coop_roster_validate(&roster)==MMX6_COOP_ROSTER_CHARACTER_FORM_MISMATCH);
        }
    }
    for (value=0;value<256;++value) if (value!=1) {
        Mmx6CoopRoster roster=resolved(5);
        roster.resolved=(uint8_t)value;
        CHECK(mmx6_coop_roster_validate(&roster)==MMX6_COOP_ROSTER_NOT_RESOLVED);
    }
    {
        Mmx6CoopRoster roster=resolved(5),ultimate=resolved(4);
        roster.seat[1]=ultimate.seat[0]; /* Native resources, unsupported partner choice. */
        CHECK(mmx6_coop_roster_validate(&roster)==MMX6_COOP_ROSTER_COUNTERPART_MISMATCH);
        roster=resolved(0);roster.seat[1]=roster.seat[0];
        CHECK(mmx6_coop_roster_validate(&roster)==MMX6_COOP_ROSTER_COUNTERPART_MISMATCH);
    }
}

static void earned_partner_armors(void) {
    for(unsigned choice=0;choice<=3;++choice)for(unsigned flags=0;flags<8;++flags)for(unsigned parts=0;parts<256;++parts) {
        Mmx6CoopRosterNative n=native(5,flags),before=n;Mmx6CoopRoster r;
        unsigned expected=((choice==1 && (flags&1)) || (choice==2 && (flags&2) && (parts&0xF0)==0xF0) ||
            (choice==3 && (flags&4) && (parts&15)==15))?choice:0;
        CHECK(mmx6_coop_roster_resolve_partner(&n,choice,(uint8_t)parts,&r)==MMX6_COOP_ROSTER_OK);
        CHECK(!memcmp(&n,&before,sizeof n) && mmx6_coop_roster_validate(&r)==MMX6_COOP_ROSTER_OK);
        actor_matches(&r.seat[0],5);actor_matches(&r.seat[1],expected);
    }
    for(unsigned form=0;form<5;++form)for(unsigned choice=0;choice<=3;++choice) {
        Mmx6CoopRosterNative n=native(form,7);Mmx6CoopRoster r;
        CHECK(mmx6_coop_roster_resolve_partner(&n,choice,255,&r)==MMX6_COOP_ROSTER_OK);
        actor_matches(&r.seat[0],form);actor_matches(&r.seat[1],5);
    }
    Mmx6CoopRosterNative n=native(5,7);Mmx6CoopRoster r,empty={0};
    CHECK(mmx6_coop_roster_resolve_partner(&n,4,255,&r)==MMX6_COOP_ROSTER_INVALID_FORM && !memcmp(&r,&empty,sizeof r));
}
int main(void) {
    unsigned reason;
    native_resolution();invalid_native();canonical_validation();earned_partner_armors();
    CHECK(!strcmp(mmx6_coop_roster_reason(MMX6_COOP_ROSTER_BLACK_ZERO_UNSUPPORTED),
                  "black_zero_unsupported"));
    for (reason=0;reason<=MMX6_COOP_ROSTER_COUNTERPART_MISMATCH;++reason)
        CHECK(strcmp(mmx6_coop_roster_reason((Mmx6CoopRosterReason)reason),
                     "unknown_roster_reason"));
    CHECK(!strcmp(mmx6_coop_roster_reason((Mmx6CoopRosterReason)999),"unknown_roster_reason"));
    puts("X6 canonical roster: native identity/flags, exact resources, opposite/base-X policy, refusals PASS");
    return 0;
}
