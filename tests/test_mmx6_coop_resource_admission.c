/* Reuse actual-plugin RAM/dispatch doubles without modifying the independent
 * private-effects fixture. Its disc-reader double fails if called: every
 * rejected enrollment must stop before I/O, projection or native dispatch. */
#define main mmx6_existing_private_effects_main
#include "test_mmx6_coop_private_effects.c"
#undef main

static uint32_t admission_fingerprint(const uint8_t *bytes,size_t count) {
    uint32_t h=2166136261u;size_t i;
    for(i=0;i<count;++i)h=(h^bytes[i])*16777619u;
    return h;
}
static void native_identity(unsigned character,unsigned form,unsigned campaign,
                            unsigned campaign_form,unsigned flags) {
    psx_mod_write_byte(PLAYER+2,(uint8_t)character);
    psx_mod_write_byte(PLAYER+0xE7,(uint8_t)form);
    psx_mod_write_byte(PLAY+0x38,(uint8_t)campaign);
    psx_mod_write_byte(PLAY+0x5E,(uint8_t)campaign_form);
    psx_mod_write_byte(PLAY+0x5F,(uint8_t)flags);
}
static void refused_enrollment(unsigned cached,unsigned character,unsigned form,
                                unsigned campaign,unsigned campaign_form,unsigned flags) {
    CPUState cpu,before_cpu;PlayerContext before_p2;
    uint32_t ram_before,extra_before;
    setup(&cpu);ready=(int)cached;enrolled=0;
    native_identity(character,form,campaign,campaign_form,flags);
    cpu.gpr[31]=0x80020C70u;before_cpu=cpu;before_p2=p2;
    ram_before=admission_fingerprint(ram,sizeof ram);
    extra_before=admission_fingerprint(extra,sizeof extra);
    controller(&cpu,0x8002012C);
    CHECK(failed && !enrolled && !inside && !zero_projected && !state_track.count);
    CHECK(!call_count && !memcmp(&before_cpu,&cpu,sizeof cpu));
    CHECK(!memcmp(&before_p2,&p2,sizeof p2));
    CHECK(ram_before==admission_fingerprint(ram,sizeof ram));
    CHECK(extra_before==admission_fingerprint(extra,sizeof extra));
    CHECK(psx_mod_read_byte(PLAY+0x5F)==flags);
}
int main(void) {
    unsigned cached,form;
    /* Keep the unchanged actual-plugin effects/restoration checks too. */
    CHECK(mmx6_existing_private_effects_main()==0);
    for(cached=0;cached<2;++cached) {
        refused_enrollment(cached,1,5,1,5,0x10); /* Valid but unfinished X/P2. */
        refused_enrollment(cached,0,1,0,0,1); /* Init/parts not yet consistent. */
        refused_enrollment(cached,0,5,0,5,0); /* Impossible native form pair. */
        refused_enrollment(cached,2,0,0,0,0); /* Invalid native character. */
        refused_enrollment(cached,0,0,0,0,0x3F); /* P2 would select BlackZero. */
        refused_enrollment(cached,1,5,1,5,0x30); /* Native BlackZero/P1. */
    }
    for(form=0;form<5;++form) {
        CPUState cpu;Mmx6CoopRoster r;setup(&cpu);
        native_identity(0,form,0,form,0x1F);
        CHECK(fixed_roster(&r));
        CHECK(r.seat[0].form==form && r.seat[1].form==5);
        CHECK(!failed && !call_count && psx_mod_read_byte(PLAY+0x5F)==0x1F);
    }
    {
        CPUState cpu;Mmx6CoopRoster r;PlayerContext before;
        Mmx6CoopRosterNative n={1,5,1,5,0x10};setup(&cpu);before=p2;
        CHECK(mmx6_coop_roster_resolve(&n,&r)==MMX6_COOP_ROSTER_OK);
        CHECK(!load_assets(&r)); /* Direct entry cannot bypass public admission. */
        CHECK(!call_count && !memcmp(&before,&p2,sizeof p2));
        enroll(&cpu,&r);CHECK(failed && !call_count && !zero_projected);
        CHECK(!memcmp(&before,&p2,sizeof p2));
    }
    clear_banks();
    puts("actual-plugin cached/fresh roster refusal before disc/native/RAM/private mutation PASS");
    return 0;
}
