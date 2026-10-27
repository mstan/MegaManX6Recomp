/* Actual plugin setup boundary against isolated RAM plus pinned original code.
 * No native game routine is emulated and no gameplay/progression pass follows. */
#include "mod_plugins.h"
static int checkpoint_native_model(CPUState *cpu,uint32_t target,uint32_t ret);
#define MMX6_TEST_GUEST_DISPATCH checkpoint_native_model
#define main diagnostic_tests
#include "test_mmx6_coop_diagnostics.c"
#undef main
static uint8_t original_ram[0x200000],before_ram[0x200000];
static uint16_t checkpoint_vram[1024*512];
static unsigned before_doors_probe;
static int checkpoint_native_model(CPUState *cpu,uint32_t target,uint32_t ret) {
    (void)ret;
    if(!before_doors_probe)return 0;
    CHECK(target==0x80029F38u && cpu->gpr[4]==5376 && cpu->gpr[5]==5792 &&
        cpu->gpr[6]==208 && cpu->gpr[7]==544 && !psx_mod_read_word(cpu->gpr[29]+0x10));
    CHECK(checkpoint_pending.phase==3 && psx_mod_read_byte(diagnostic+0xAD)==1);
    CHECK(psx_mod_read_word(PLAYER+8)==5692u<<16 && le32(p2.body+8)==5716u<<16);
    CHECK(psx_mod_read_word(0x800971F8u+8)==5424u<<16 && psx_mod_read_word(0x800971F8u+12)==256u<<16);
    /* External native scanner contract only: allocate an original slot. Its
     * native init/grounding are deliberately NOT supplied by this model. */
    uint32_t a=0x800C1220u;
    psx_mod_write_byte(a,1);psx_mod_write_byte(a+1,8);psx_mod_write_byte(a+2,2);
    psx_mod_write_word(a+0x10,0x800FA2A4u);
    psx_mod_write_half(a+10,5744);psx_mod_write_half(a+14,384);
    psx_mod_write_byte(0x800FA2A4u,1);++guest_calls;return 1;
}
#ifdef MMX6_COOP_CHECKPOINT_TAINT_API
#define checkpoint_test_taint diagnostic_test_taint
#endif
const uint16_t *gpu_get_vram(void){return checkpoint_vram;}
void gpu_set_gp0_source(uint32_t source){(void)source;}
void gpu_write_gp0(uint32_t value){(void)value;}
#ifdef MMX6_COOP_AGREED_CHECKPOINT
static uint8_t before_doors_ram[0x200000];
static const char *test_lab_option="off";
static unsigned test_lab_ready=1,test_lab_failed,test_lab_selected=1;
static PSXHostSelection test_lab_profile;
int psx_mod_option_value(const char *package,const char *feature,const char *option,char *out,uint32_t size) {
    CHECK(!strcmp(package,"mmx6.local-coop") && !strcmp(feature,"prototype") && !strcmp(option,"lab_checkpoint"));
    CHECK(size>strlen(test_lab_option));strcpy(out,test_lab_option);return 1;
}
int psx_netplay_host_profile_ready(void){return (int)test_lab_ready;}
int psx_netplay_host_profile_failed(void){return (int)test_lab_failed;}
int psx_netplay_host_profile_selection(PSXHostSelection *out){*out=test_lab_profile;return (int)test_lab_selected;}
#endif

static void setup_checkpoint(CPUState *cpu,unsigned stage,unsigned section,unsigned cp) {
    memcpy(test_ram,original_ram,sizeof test_ram);memset(test_diagnostic,0,sizeof test_diagnostic);
    memset(cpu,0,sizeof *cpu);memset(&p2,0x32,sizeof p2);diagnostic=0x9F080000u;
    inside=stage_call=player_call=zero_world=zero_projected=scene_owner=scene_phase=failed=0;
    ready=enrolled=1;pause_owner=-1;zero_menu_loaded=0;guest_calls=0;test_online=0;
    state_track.count=state_track.error=0;mmx6_coop_lifecycle_init(&life);checkpoint_reset();
#ifdef MMX6_COOP_CHECKPOINT_TAINT_API
    checkpoint_test_taint=0; /* Test isolation only; the game never clears SDK taint. */
#endif
    p2.body[0]=p2.body[3]=p2.body[4]=1;p2.body[5]=2;p2.body[0x5C]=32;
    psx_mod_write_byte(PLAYER+4,1);psx_mod_write_byte(PLAYER+0x5C,32);
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+1,0);psx_mod_write_byte(PLAY+0x10,0);
    psx_mod_write_byte(PLAY+0x1C,0);psx_mod_write_byte(PLAY+0x1D,2);
    psx_mod_write_byte(diagnostic+0x51,(uint8_t)stage);
    psx_mod_write_byte(diagnostic+0x52,(uint8_t)section);
    psx_mod_write_byte(diagnostic+0x53,(uint8_t)cp);
    psx_mod_write_word(diagnostic+0x54,1234);psx_mod_write_byte(diagnostic+0x50,8);
}
static void rejected_checkpoint(CPUState *cpu,unsigned reason) {
    memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext saved=p2;
    CHECK(!checkpoint_stage_boundary(cpu));CHECK(!checkpoint_pending.phase && !guest_calls);
    CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&saved,&p2,sizeof p2));
    CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_REJECTED);
    CHECK(psx_mod_read_byte(diagnostic+0xA9)==reason);
    CHECK(!psx_mod_read_byte(diagnostic+0x50) && !psx_mod_read_byte(diagnostic+0xBC));
#ifdef MMX6_COOP_CHECKPOINT_TAINT_API
    CHECK(!checkpoint_test_taint);
#endif
}
static void mode9(CPUState *cpu) {
    psx_mod_write_byte(PLAY,9);psx_mod_write_byte(PLAY+0x1D,0);
    cpu->gpr[31]=0x8001E720;cpu->gpr[4]=PLAY;
}
#ifdef MMX6_COOP_AGREED_CHECKPOINT
static void setup_agreed(CPUState *cpu,int online) {
    test_lab_option="intro_cp2";setup_checkpoint(cpu,0,0,2);test_online=online;
    const uint8_t expected[32]=MMX6_HOST_LAB_QUALIFICATION_BYTES;
    memset(&test_lab_profile,0,sizeof test_lab_profile);
    strcpy(test_lab_profile.profile,MMX6_HOST_LAB_PROFILE);test_lab_profile.revision=MMX6_HOST_LAB_REVISION;
    test_lab_profile.flags=PSX_HOST_PROFILE_DIRECT_LOOPBACK;
    memcpy(test_lab_profile.qualification,expected,sizeof expected);
    test_lab_ready=test_lab_selected=1;test_lab_failed=0;
    psx_mod_write_byte(diagnostic+0x50,0);psx_mod_write_byte(PLAY+0x1D,0);
    psx_mod_write_byte(PLAYER+5,2);psx_mod_write_byte(PLAYER+0x67,0);psx_mod_write_byte(PLAYER+0x70,8);
    psx_mod_write_byte(PLAYER,1);
    p2.body[0x67]=0;p2.body[0x70]=8;
    CHECK(checkpoint_lab_option==1 && !checkpoint_lab_state && !checkpoint_lab_previous);
}
static void agreed_checkpoint_boundary(CPUState *cpu) {
    /* Configured destination alone must never race the parent's normal intro
     * P2-walk/P1-jump baseline. Only a fresh accepted native chord arms it. */
    setup_agreed(cpu,1);CHECK(!checkpoint_lab_boundary(0) && !checkpoint_pending.phase && !checkpoint_lab_state);
    CHECK(!checkpoint_lab_boundary(2) && !checkpoint_lab_boundary(4) && !checkpoint_lab_boundary(7) && !checkpoint_lab_state);
    checkpoint_lab_option=0;memcpy(before_ram,test_ram,sizeof test_ram);
    CHECK(!checkpoint_lab_boundary(6) && !checkpoint_lab_state && !memcmp(before_ram,test_ram,sizeof test_ram));
    for(int online=0;online<=1;++online) {
        setup_agreed(cpu,online);PlayerContext body=p2;memcpy(before_ram,test_ram,sizeof test_ram);
        pause_owner=1;CHECK(!checkpoint_lab_boundary(6));
        CHECK(checkpoint_lab_state==CHECKPOINT_LAB_ARMED && !checkpoint_pending.phase && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram));
        CHECK(psx_mod_read_byte(diagnostic+0xBE)==1);
        CHECK(!checkpoint_lab_boundary(0) && checkpoint_lab_state==CHECKPOINT_LAB_ARMED);
        pause_owner=-1;p2.body[5]=7;CHECK(!checkpoint_lab_boundary(0) && !checkpoint_pending.phase);
        p2.body[5]=2;CHECK(checkpoint_lab_boundary(0));
        before_ram[PLAY&0x1FFFFF]=8;
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof p2) && !guest_calls);
        CHECK(checkpoint_pending.phase==1 && checkpoint_pending.index==2 && checkpoint_pending.authority==CHECKPOINT_AGREED &&
            checkpoint_pending.nonce==CHECKPOINT_LAB_NONCE && checkpoint_lab_state==CHECKPOINT_LAB_CONSUMED);
        CHECK(psx_mod_read_byte(diagnostic+0xBD)==1 && psx_mod_read_byte(diagnostic+0xBE)==2 &&
            psx_mod_read_byte(diagnostic+0xBC)==1 && psx_mod_read_word(diagnostic+0xA4)==1 &&
            checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(checkpoint_pending.phase==2 && psx_mod_read_byte(PLAY+0x1D)==2 && psx_mod_read_word(diagnostic+0xB4)==1);
        psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase);
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE);
        psx_mod_write_byte(PLAY+0x1D,0); /* Test a later native retry, not a game write. */
        CHECK(!checkpoint_lab_boundary(0) && !checkpoint_lab_boundary(6));
        CHECK(psx_mod_read_word(diagnostic+0xA4)==1 && checkpoint_lab_state==CHECKPOINT_LAB_CONSUMED);
    }
    /* Identical selected profile is a prerequisite, never inferred from
     * active netplay, a version string or the compile-time lab flag. */
    for(unsigned wrong=0;wrong<7;++wrong) {
        setup_agreed(cpu,1);memcpy(before_ram,test_ram,sizeof test_ram);
        if(wrong==0)test_lab_ready=0;if(wrong==1)test_lab_failed=1;
        if(wrong==2)test_lab_selected=0;if(wrong==3)test_lab_profile.profile[0]^=1;
        if(wrong==4)++test_lab_profile.revision;if(wrong==5)test_lab_profile.flags=0;
        if(wrong==6)test_lab_profile.qualification[0]^=1;
        CHECK(!checkpoint_lab_boundary(6) && !checkpoint_pending.phase && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !checkpoint_test_taint);
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_REJECTED && psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_FORBIDDEN);
    }
    setup_agreed(cpu,1);psx_mod_write_byte(checkpoint_code[0].first,0);
    CHECK(!checkpoint_lab_boundary(6) && !checkpoint_pending.phase && !checkpoint_test_taint);
    CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE);
    setup_agreed(cpu,1);CHECK(checkpoint_lab_boundary(6));mode9(cpu);test_lab_ready=0;
    checkpoint_native_entry(cpu,0x8001E1BCu);CHECK(!checkpoint_pending.phase && !psx_mod_read_byte(PLAY+0x1D));
    CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_FORBIDDEN);
    setup_agreed(cpu,1);psx_mod_write_byte(diagnostic+0x50,8);
    rejected_checkpoint(cpu,CHECKPOINT_FORBIDDEN); /* Configured lab never authorizes online command8. */
    test_lab_option="off";checkpoint_reset();CHECK(!checkpoint_lab_option && !checkpoint_lab_state && !checkpoint_lab_previous);
}
static void agreed_amazon_boundary(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        setup_agreed(cpu,online);test_lab_option="amazon_cp0";checkpoint_reset();
        CHECK(checkpoint_lab_option==2 && checkpoint_lab_index()==3 &&
            checkpoint_lab_nonce()==CHECKPOINT_LAB_AMAZON_NONCE);
        /* A consumed chord cannot authorize a different destination or nonce. */
        checkpoint_lab_state=CHECKPOINT_LAB_CONSUMED;
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(!checkpoint_request(0,0,2,CHECKPOINT_LAB_NONCE,CHECKPOINT_AGREED));
        CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_UNKNOWN &&
            !checkpoint_pending.phase && !checkpoint_test_taint && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof p2));
        CHECK(!checkpoint_request(1,0,0,CHECKPOINT_LAB_NONCE,CHECKPOINT_AGREED));
        CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_UNKNOWN && !checkpoint_pending.phase);
        CHECK(!checkpoint_request(0,0,2,CHECKPOINT_LAB_AMAZON_NONCE,CHECKPOINT_AGREED));
        CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_UNKNOWN && !checkpoint_pending.phase &&
            !checkpoint_test_taint && !memcmp(before_ram,test_ram,sizeof test_ram));
        checkpoint_reset();memcpy(before_ram,test_ram,sizeof test_ram);
        CHECK(!checkpoint_lab_boundary(0) && !checkpoint_pending.phase);
        CHECK(checkpoint_lab_boundary(6));
        before_ram[PLAY&0x1FFFFF]=8;before_ram[(PLAY+12)&0x1FFFFF]=1;
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof p2) && !guest_calls);
        CHECK(checkpoint_pending.phase==1 && checkpoint_pending.index==3 &&
            checkpoint_pending.authority==CHECKPOINT_AGREED &&
            checkpoint_pending.nonce==CHECKPOINT_LAB_AMAZON_NONCE &&
            psx_mod_read_word(diagnostic+0xB8)==0x80072174u &&
            checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(checkpoint_pending.phase==2 && !psx_mod_read_byte(PLAY+0x1D) &&
            psx_mod_read_word(diagnostic+0xB4)==1 && !guest_calls);
        psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase);
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE);
        CHECK(!checkpoint_lab_boundary(0) && !checkpoint_lab_boundary(6));
        CHECK(psx_mod_read_word(diagnostic+0xA4)==1);
        if(online) {
            setup_agreed(cpu,1);test_lab_option="amazon_cp0";checkpoint_reset();
            psx_mod_write_byte(diagnostic+0x50,8);rejected_checkpoint(cpu,CHECKPOINT_FORBIDDEN);
        }
    }
    setup_agreed(cpu,1);test_lab_option="amazon_cp0";checkpoint_reset();test_lab_ready=0;
    memcpy(before_ram,test_ram,sizeof test_ram);
    CHECK(!checkpoint_lab_boundary(6) && !checkpoint_pending.phase && !checkpoint_test_taint &&
        !memcmp(before_ram,test_ram,sizeof test_ram));
    CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_FORBIDDEN);
    test_lab_option="off";checkpoint_reset();
}
static void agreed_investigator_boundary(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        setup_agreed(cpu,online);test_lab_option="amazon_cp2";checkpoint_reset();
        CHECK(checkpoint_lab_option==3 && checkpoint_lab_index()==5 &&
            checkpoint_lab_nonce()==CHECKPOINT_LAB_INVESTIGATOR_NONCE);
        /* A consumed chord cannot authorize a different destination or nonce. */
        checkpoint_lab_state=CHECKPOINT_LAB_CONSUMED;
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(!checkpoint_request(0,0,2,CHECKPOINT_LAB_NONCE,CHECKPOINT_AGREED));
        CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_UNKNOWN &&
            !checkpoint_pending.phase && !checkpoint_test_taint && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof p2));
        CHECK(!checkpoint_request(1,0,2,CHECKPOINT_LAB_NONCE,CHECKPOINT_AGREED));
        CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_UNKNOWN && !checkpoint_pending.phase);
        CHECK(!checkpoint_request(0,0,2,CHECKPOINT_LAB_INVESTIGATOR_NONCE,CHECKPOINT_AGREED));
        CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_UNKNOWN && !checkpoint_pending.phase &&
            !checkpoint_test_taint && !memcmp(before_ram,test_ram,sizeof test_ram));
        CHECK(!checkpoint_request(1,0,0,CHECKPOINT_LAB_AMAZON_NONCE,CHECKPOINT_AGREED));
        CHECK(!checkpoint_request(1,0,2,CHECKPOINT_LAB_AMAZON_NONCE,CHECKPOINT_AGREED));
        CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_UNKNOWN && !checkpoint_pending.phase &&
            !checkpoint_test_taint && !memcmp(before_ram,test_ram,sizeof test_ram));
        checkpoint_reset();memcpy(before_ram,test_ram,sizeof test_ram);
        CHECK(!checkpoint_lab_boundary(0) && !checkpoint_pending.phase);
        CHECK(checkpoint_lab_boundary(6));
        before_ram[PLAY&0x1FFFFF]=8;before_ram[(PLAY+12)&0x1FFFFF]=1;
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof p2) && !guest_calls);
        CHECK(checkpoint_pending.phase==1 && checkpoint_pending.index==5 &&
            checkpoint_pending.authority==CHECKPOINT_AGREED &&
            checkpoint_pending.nonce==CHECKPOINT_LAB_INVESTIGATOR_NONCE &&
            psx_mod_read_word(diagnostic+0xB8)==0x800721BCu &&
            checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(checkpoint_pending.phase==2 && psx_mod_read_byte(PLAY+0x1D)==2 &&
            psx_mod_read_word(diagnostic+0xB4)==1 && !guest_calls);
        psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase);
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE);
        CHECK(!checkpoint_lab_boundary(0) && !checkpoint_lab_boundary(6));
        CHECK(psx_mod_read_word(diagnostic+0xA4)==1);
        if(online) {
            setup_agreed(cpu,1);test_lab_option="amazon_cp2";checkpoint_reset();
            psx_mod_write_byte(diagnostic+0x50,8);rejected_checkpoint(cpu,CHECKPOINT_FORBIDDEN);
        }
    }
    setup_agreed(cpu,1);test_lab_option="amazon_cp2";checkpoint_reset();test_lab_ready=0;
    memcpy(before_ram,test_ram,sizeof test_ram);
    CHECK(!checkpoint_lab_boundary(6) && !checkpoint_pending.phase && !checkpoint_test_taint &&
        !memcmp(before_ram,test_ram,sizeof test_ram));
    CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_FORBIDDEN);
    test_lab_option="off";checkpoint_reset();
}
static void setup_before_doors(CPUState *cpu,int online) {
    setup_agreed(cpu,online);test_lab_option="intro_before_doors";checkpoint_reset();
    memcpy(test_ram,before_doors_ram,sizeof test_ram);
    memset(test_ram+(PLAYER&0x1FFFFFu),0,sizeof p2.body);
    memset(p2.body,0,sizeof p2.body);
    p2.body[0]=p2.body[3]=p2.body[4]=1;p2.body[2]=1;p2.body[5]=2;
    p2.body[0x5C]=31;p2.body[0x70]=8;put32(p2.body+0x68,0x80073D54u);
    psx_mod_write_byte(PLAYER,1);psx_mod_write_byte(PLAYER+3,1);
    psx_mod_write_byte(PLAYER+4,1);psx_mod_write_byte(PLAYER+5,2);
    psx_mod_write_byte(PLAYER+0x5C,29);psx_mod_write_byte(PLAYER+0x70,8);
    psx_mod_write_word(PLAYER+0x68,0x80073D50u);
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+0x1D,0);
    psx_mod_write_word(PLAY+0x90,100);before_doors_probe=1;
    cpu->gpr[29]=0x801FFF00u;cpu->gpr[6]=0x11223344u;cpu->gpr[7]=0x55667788u;
    psx_mod_write_word(cpu->gpr[29]+0x10,0xAABBCCDDu);
    CHECK(checkpoint_lab_option==4 && checkpoint_lab_index()==1 &&
        checkpoint_lab_nonce()==CHECKPOINT_LAB_BEFORE_DOORS_NONCE);
    CHECK(checkpoint_lab_boundary(6));mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
    CHECK(checkpoint_pending.phase==2 && psx_mod_read_byte(PLAY+0x1D)==1);
    psx_mod_write_byte(PLAY,10);
    psx_mod_write_word(PLAYER+8,2112u<<16);psx_mod_write_word(PLAYER+12,1115u<<16);
    put32(p2.body+8,2136u<<16);put32(p2.body+12,1114u<<16);
}
static int before_doors_write_allowed(unsigned at) {
    const unsigned p=PLAYER&0x1FFFFFu,c=0x800971F8u&0x1FFFFFu;
    return (at>=p+8 && at<p+16) || (at>=p+0x18 && at<p+0x20) ||
        (at>=c+8 && at<c+16) || (at>=c+0x14 && at<c+0x2C) || at==c+0x47 ||
        at==c+0x4C || at==c+0x54+0x4C || at==c+0xA8+0x4C ||
        (at>=0xC1220u && at<0xC1220u+0xA4u) || at==0xFA2A4u;
}
static void agreed_before_doors_boundary(CPUState *cpu) {
    uint32_t meta,desc;
    for(int online=0;online<=1;++online) {
        setup_before_doors(cpu,online);
        CHECK(checkpoint_before_doors_source() && checkpoint_before_doors_assets(&meta,&desc));
        CHECK(checkpoint_before_doors_ground(meta,desc));
        pause_owner=1;CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls);
        pause_owner=-1;p2.body[0x67]=1;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls);
        p2.body[0x67]=0;put32(p2.body+0x68,0);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls);
        put32(p2.body+0x68,0x80073D54u);
        /* Missing live assets wait; a wrong original source cancels before pose. */
        uint32_t saved_meta=psx_mod_read_word(0x1F800008u);psx_mod_write_word(0x1F800008u,0);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls);
        psx_mod_write_word(0x1F800008u,saved_meta);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext saved=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 && guest_calls==1);
        CHECK(cpu->gpr[6]==0x11223344u && cpu->gpr[7]==0x55667788u &&
            psx_mod_read_word(cpu->gpr[29]+0x10)==0xAABBCCDDu && !state_track.count && !state_track.error);
        put32(saved.body+8,5716u<<16);put32(saved.body+12,394u<<16);
        put32(saved.body+0x18,5716u<<16);put32(saved.body+0x1C,394u<<16);
        CHECK(!memcmp(&saved,&p2,sizeof p2));
        for(unsigned i=0;i<sizeof test_ram;++i)
            CHECK(test_ram[i]==before_ram[i] || before_doors_write_allowed(i));
        CHECK(psx_mod_read_byte(PLAYER+0x5C)==29 && p2.body[0x5C]==31 &&
            psx_mod_read_byte(PLAYER+0x70)==8 && p2.body[0x70]==8 &&
            !psx_mod_read_byte(PLAYER+0xD4) && !p2.body[0xD4] &&
            psx_mod_read_byte(PLAY+0x1D)==1 && psx_mod_read_byte(diagnostic+0xAD)==1 &&
            psx_mod_read_byte(diagnostic+0xAE)==1 &&
            psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_INITIALIZING);
        psx_mod_write_word(PLAY+0x90,101);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 && guest_calls==1);
        psx_mod_write_word(PLAY+0x90,102);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3); /* Native door not initialized. */
        psx_mod_write_byte(0x800C1224u,1);psx_mod_write_word(0x800C1288u,0x80078DC8u);
        p2.body[0x70]=0;CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        p2.body[0x70]=8;psx_mod_write_word(0x800C1230u,0x800FA2ACu);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3); /* Wrong placement identity. */
        psx_mod_write_word(0x800C1230u,0x800FA2A4u);
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && guest_calls==1);
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && psx_mod_read_byte(diagnostic+0xAD)==2);
        CHECK(checkpoint_lab_state==CHECKPOINT_LAB_CONSUMED && checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        /* Ordinary retry/another accepted chord cannot place again. */
        psx_mod_write_word(PLAYER+8,2112u<<16);put32(p2.body+8,2136u<<16);
        CHECK(!checkpoint_lab_boundary(0) && !checkpoint_lab_boundary(6) && !checkpoint_stage_boundary(cpu));
        CHECK(psx_mod_read_word(PLAYER+8)==2112u<<16 && le32(p2.body+8)==2136u<<16 && guest_calls==1);
        setup_before_doors(cpu,online);psx_mod_write_byte(before_doors_code[0].first,0);
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE && psx_mod_read_byte(diagnostic+0xAD)==0);
        setup_before_doors(cpu,online);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        checkpoint_reset();CHECK(!checkpoint_pending.phase && !psx_mod_read_byte(diagnostic+0xAD));
    }
    setup_before_doors(cpu,1);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
    test_lab_ready=0;CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && guest_calls==1 &&
        psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_FORBIDDEN);
    before_doors_probe=0;setup_agreed(cpu,1);test_lab_option="intro_before_doors";checkpoint_reset();
    psx_mod_write_byte(diagnostic+0x50,8);psx_mod_write_byte(diagnostic+0x51,0);
    psx_mod_write_byte(diagnostic+0x52,0);psx_mod_write_byte(diagnostic+0x53,1);
    rejected_checkpoint(cpu,CHECKPOINT_FORBIDDEN); /* No online command8 exception. */
    before_doors_probe=0;test_lab_option="off";checkpoint_reset();
}
#endif
int main(int argc,char **argv) {
    const char *source=argc==2?argv[1]:getenv("MMX6_CONTENT_EXE");
    if(!source || !*source){puts("SKIP: MMX6_CONTENT_EXE must name the original USA v1.1 EXE");return 77;}
    CHECK(argc<=2);FILE *file=fopen(source,"rb");CHECK(file);
    CHECK(!fseek(file,0x800,SEEK_SET));CHECK(fread(original_ram+0x10000,1,0x7F000,file)==0x7F000);
    CHECK(fgetc(file)==EOF);fclose(file);
    CHECK(!diagnostic_tests());CPUState cpu;
    unsigned campaign=0;for(unsigned i=0;i<115;++i)campaign+=checkpoint_inventory[i].campaign;
    CHECK(campaign==94);
    setup_checkpoint(&cpu,0,0,1);test_online=1;rejected_checkpoint(&cpu,CHECKPOINT_FORBIDDEN);
#ifdef PSX_NO_DEBUG_TOOLS
    for(unsigned i=0;i<115;++i){const Mmx6Checkpoint *entry=&checkpoint_inventory[i];
        setup_checkpoint(&cpu,entry->stage,entry->section,entry->checkpoint);
        rejected_checkpoint(&cpu,CHECKPOINT_FORBIDDEN);}
#else
    setup_checkpoint(&cpu,255,0,0);rejected_checkpoint(&cpu,CHECKPOINT_UNKNOWN);
    setup_checkpoint(&cpu,0,1,0);rejected_checkpoint(&cpu,CHECKPOINT_UNKNOWN);
    setup_checkpoint(&cpu,0,0,3);rejected_checkpoint(&cpu,CHECKPOINT_UNKNOWN);
    setup_checkpoint(&cpu,0,0,1);psx_mod_write_word(diagnostic+0x54,0);rejected_checkpoint(&cpu,CHECKPOINT_UNKNOWN);
    for(unsigned i=0;i<115;++i){const Mmx6Checkpoint *entry=&checkpoint_inventory[i];
        setup_checkpoint(&cpu,entry->stage,entry->section,entry->checkpoint);
        if(!entry->campaign){rejected_checkpoint(&cpu,CHECKPOINT_NAMESPACE);continue;}
        CHECK(checkpoint_source(entry));
        memcpy(before_ram,test_ram,sizeof test_ram);
        before_ram[PLAY&0x1FFFFF]=8;before_ram[(PLAY+12)&0x1FFFFF]=entry->stage;
        before_ram[(PLAY+13)&0x1FFFFF]=entry->section;
        PlayerContext saved=p2;CHECK(stage_tick(&cpu,0x8001E9EC));
        CHECK(!guest_calls && !memcmp(&saved,&p2,sizeof p2)); /* No stale original world pass or HP grant. */
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram)); /* Only mode/stage/section changed. */
        CHECK(checkpoint_pending.phase==1 && psx_mod_read_byte(PLAY)==8);
        CHECK(psx_mod_read_byte(PLAY+0x1D)==2); /* Mode8, not the fixture, owns its reset. */
        CHECK(psx_mod_read_byte(diagnostic+0xBC)==1);
#ifdef MMX6_COOP_CHECKPOINT_TAINT_API
        CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
#endif
        mode9(&cpu);memcpy(before_ram,test_ram,sizeof test_ram);
        before_ram[(PLAY+0x1D)&0x1FFFFF]=entry->checkpoint;
        checkpoint_native_entry(&cpu,0x8001E1BC);
        CHECK(checkpoint_pending.phase==2 && psx_mod_read_byte(PLAY+0x1D)==entry->checkpoint);
        CHECK(!guest_calls && psx_mod_read_word(diagnostic+0xB4)==1);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&saved,&p2,sizeof p2));
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_INITIALIZING);
        /* Observer leaves original initializer execution to normal dispatch. */
        psx_mod_write_byte(PLAY,10);enrolled=0;
        CHECK(!stage_tick(&cpu,0x8001E9EC) && !checkpoint_pending.phase && !guest_calls);
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE);
    }
    setup_checkpoint(&cpu,0,0,1);inside=1;rejected_checkpoint(&cpu,CHECKPOINT_UNSAFE);
    setup_checkpoint(&cpu,0,0,1);pause_owner=1;rejected_checkpoint(&cpu,CHECKPOINT_UNSAFE);
    setup_checkpoint(&cpu,0,0,1);state_track.count=1;rejected_checkpoint(&cpu,CHECKPOINT_UNSAFE);
    for(unsigned i=0;i<sizeof checkpoint_code/sizeof checkpoint_code[0];++i){
        setup_checkpoint(&cpu,0,0,1);psx_mod_write_byte(checkpoint_code[i].first,0);
        rejected_checkpoint(&cpu,CHECKPOINT_SOURCE);}
    setup_checkpoint(&cpu,0,0,1);psx_mod_write_word(0x80073300,0);rejected_checkpoint(&cpu,CHECKPOINT_SOURCE);
    setup_checkpoint(&cpu,0,0,1);psx_mod_write_byte(0x8007212C,0xFE);rejected_checkpoint(&cpu,CHECKPOINT_SOURCE);
    setup_checkpoint(&cpu,0,0,1);inside=1;diagnostic_setup(&cpu);
    CHECK(psx_mod_read_byte(diagnostic+0x50)==8 && !checkpoint_pending.phase && !guest_calls);
    for(unsigned bad=0;bad<6;++bad){
        setup_checkpoint(&cpu,0,0,1);CHECK(checkpoint_stage_boundary(&cpu));mode9(&cpu);
        if(bad==0)cpu.gpr[31]^=4;if(bad==1)cpu.gpr[4]^=4;
        if(bad==2)psx_mod_write_byte(PLAY,8);if(bad==3)psx_mod_write_byte(PLAY+12,1);
        if(bad==4)psx_mod_write_byte(PLAY+0x1D,2);if(bad==5)state_track.count=1;
        unsigned cp=psx_mod_read_byte(PLAY+0x1D);memcpy(before_ram,test_ram,sizeof test_ram);
        checkpoint_native_entry(&cpu,0x8001E1BC);
        CHECK(!checkpoint_pending.phase && psx_mod_read_byte(PLAY+0x1D)==cp && !guest_calls);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram));
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_FAILED);
    }
    setup_checkpoint(&cpu,0,0,1);CHECK(checkpoint_stage_boundary(&cpu));mode9(&cpu);
    checkpoint_native_entry(&cpu,0x8001E1BC);checkpoint_native_entry(&cpu,0x8001E1BC);
    CHECK(!checkpoint_pending.phase && psx_mod_read_word(diagnostic+0xB4)==1 && !guest_calls);
    setup_checkpoint(&cpu,0,0,1);CHECK(checkpoint_stage_boundary(&cpu));failed=1;
    CHECK(!checkpoint_stage_boundary(&cpu) && !checkpoint_pending.phase);
    CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_PLUGIN_FAILED);
    setup_checkpoint(&cpu,0,0,1);CHECK(checkpoint_stage_boundary(&cpu));mode9(&cpu);test_online=1;
    checkpoint_native_entry(&cpu,0x8001E1BC);
    CHECK(!checkpoint_pending.phase && !psx_mod_read_byte(PLAY+0x1D) && !guest_calls);
    setup_checkpoint(&cpu,0,0,1);CHECK(checkpoint_stage_boundary(&cpu));checkpoint_reset();
    CHECK(!checkpoint_pending.phase && !psx_mod_read_byte(diagnostic+0xBC));
#ifdef MMX6_COOP_CHECKPOINT_TAINT_API
    CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
#endif
    setup_checkpoint(&cpu,0,0,1);checkpoint_reset();
    CHECK(!checkpoint_pending.phase && !psx_mod_read_byte(diagnostic+0x50));
#endif
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    const char *fixture=getenv("MMX6_BEFORE_DOORS_RAM");
    if(!fixture || !*fixture){puts("SKIP: MMX6_BEFORE_DOORS_RAM must name the external original pre-door RAM fixture");return 77;}
    file=fopen(fixture,"rb");CHECK(file);uint8_t header[4];
    CHECK(fread(header,1,4,file)==4 && !memcmp(header,"BCD1",4));
    CHECK(fread(before_doors_ram,1,sizeof before_doors_ram,file)==sizeof before_doors_ram && fgetc(file)==EOF);fclose(file);
    agreed_checkpoint_boundary(&cpu);agreed_amazon_boundary(&cpu);agreed_investigator_boundary(&cpu);
    agreed_before_doors_boundary(&cpu);
#endif
    puts("private checkpoint actual-plugin ordering, inventory, reset and rejection PASS");return 0;
}
