/* Actual plugin setup boundary against isolated RAM plus pinned original code.
 * No native game routine is emulated and no gameplay/progression pass follows. */
#include "cpu_state.h"
#include <stdarg.h>
static void checkpoint_test_refusal_log(const char *format,...);
#define MMX6_CHECKPOINT_REFUSAL_LOG(...) checkpoint_test_refusal_log(__VA_ARGS__)
static int checkpoint_native_model(CPUState *cpu,uint32_t target,uint32_t ret);
#define MMX6_TEST_GUEST_DISPATCH checkpoint_native_model
#define main diagnostic_tests
#include "test_mmx6_coop_diagnostics.c"
#undef main
/* These checkpoint calls execute in the shared world, never a private draw. */
int psx_mod_local_view_scope(void) { return 0; }
static uint8_t original_ram[0x200000],before_ram[0x200000];
static uint16_t checkpoint_vram[1024*512];
static unsigned before_doors_probe,equipment_probe,equipment_calls;
static unsigned scene_fatal_probe,scene_lock_calls,scene_release_calls;
static unsigned refight_stub,refight_probe_calls,refight_action_calls,refight_refuse;
static unsigned refight_post_solid,refight_admission_fault;
static unsigned gate_contact_probe,gate_contact_calls[2],gate_contact_hit;
static unsigned northpole_pickup_scan_probe,northpole_pickup_scan_calls;
static unsigned mounted_probe,mounted_scan_calls,mounted_init_calls,mounted_scan_fault;
static uint8_t mounted_source_bin[40334],mounted_init_seed[0xB0];
static unsigned refusal_logs;
static char refusal_log[512];
static unsigned intro_scan_probe,intro_scan_calls,intro_scan_allocations,intro_canonical_cycles;
static unsigned amazon_scan_probe,amazon_scan_calls,amazon_visibility_calls;
static void checkpoint_test_refusal_log(const char *format,...) {
    va_list args;va_start(args,format);
    CHECK(vsnprintf(refusal_log,sizeof refusal_log,format,args)>0);
    va_end(args);++refusal_logs;
}
static int checkpoint_native_model(CPUState *cpu,uint32_t target,uint32_t ret) {
    (void)ret;
    if(gate_contact_probe && target==0x80030ECCu) {
        /* External native-call boundary only: do not model contact damage. */
        unsigned seat=psx_mod_read_byte(PLAYER+2);CHECK(seat<2);
        CHECK(cpu->gpr[4]==0x80093C98u && inside);
        ++gate_contact_calls[seat];++guest_calls;
        cpu->gpr[2]=seat==gate_contact_hit;return 1;
    }
    if(mounted_probe && target==0x80029F38u) {
        CHECK(cpu->gpr[4]==31 && cpu->gpr[5]==33 && cpu->gpr[6]==353 && cpu->gpr[7]==355);
        CHECK(!psx_mod_read_word(cpu->gpr[29]+16));++mounted_scan_calls;++guest_calls;
        if(!mounted_scan_fault) { /* External native allocation boundary only. */
            uint32_t a=0x8009B7B0u;psx_mod_write_byte(a,0x41);psx_mod_write_byte(a+1,30);
            psx_mod_write_byte(a+2,1);psx_mod_write_word(a+0x10,0x800F2588u);
            psx_mod_write_byte(0x800F2588u,1);
        }
        return 1;
    }
    if(mounted_probe && target==0x800EBF64u) {
        CHECK(cpu->gpr[4]==0x800CD340u && !cpu->gpr[5] && checkpoint_pending.phase==3);
        /* Supplied native constructor result; this is not gameplay emulation. */
        project(0x800CD340u,mounted_init_seed,sizeof mounted_init_seed);
        ++mounted_init_calls;++guest_calls;return 1;
    }
    if(northpole_pickup_scan_probe && target==0x80029F38u) {
        /* External original allocation boundary only; the constructor is a
         * separate later native observation, never supplied by this scan. */
        CHECK(cpu->gpr[4]==5167 && cpu->gpr[5]==5170 && cpu->gpr[6]==671 && cpu->gpr[7]==674);
        CHECK(!psx_mod_read_word(cpu->gpr[29]+0x10));
        uint32_t a=0x8008EF48u;psx_mod_write_byte(a,1);psx_mod_write_byte(a+1,47);
        psx_mod_write_byte(a+2,1);psx_mod_write_byte(a+4,0);psx_mod_write_word(a+0x10,0x800F6104u);
        ++northpole_pickup_scan_calls;++guest_calls;return 1;
    }
    if(amazon_scan_probe && target==0x80029F38u) {
        /* Original scanner boundary only: leave allocation/AI to native QA. */
        CHECK(inside && !private_draw && state_track.count);
        CHECK(cpu->gpr[4]==202 && cpu->gpr[5]==618 && cpu->gpr[6]==186 && cpu->gpr[7]==522);
        CHECK(psx_mod_read_word(0x800734A4u)==0x800F6540u && psx_mod_read_byte(0x800F654Bu)==15);
        CHECK(!psx_mod_read_word(cpu->gpr[29]+0x10));++amazon_scan_calls;return 1;
    }
    if(amazon_scan_probe && target==0x8002CCB0u) {
        CHECK(inside && cpu->gpr[4]==0x800C1220u && cpu->gpr[5]==32 && cpu->gpr[6]==32);
        ++amazon_visibility_calls;
        /* External native view classifier contract, not actor movement. */
        psx_mod_write_byte(cpu->gpr[4]+3,psx_mod_read_half(VIEW_CAMERA+10)==250);
        return 1;
    }
    if(intro_scan_probe && target==0x80029D18u) {
        /* Original canonical scan contract: active-bit81 is checked before
         * any outside-rectangle latch reset. An inactive initial flags0
         * placement outside P1's entrance also remains flags0. */
        CHECK(psx_mod_read_word(0x8007349Cu)==0x800FA214u);
        uint8_t flags=psx_mod_read_byte(0x800FA394u);
        CHECK(!flags || (flags&0x81u));++intro_canonical_cycles;return 1;
    }
    if(intro_scan_probe && target==0x80029F38u) {
        /* External ORIGINAL scanner/allocator contract only, not execution
         * of a native event: honor the actual placement's admitted bit. */
        CHECK(inside && !private_draw && state_track.count);
        CHECK(cpu->gpr[4]==4692 && cpu->gpr[5]==5108 && cpu->gpr[6]==656 && cpu->gpr[7]==992);
        CHECK(psx_mod_read_word(0x8007349Cu)==0x800FA394u && psx_mod_read_byte(0x800FA39Fu)==15);
        CHECK(!psx_mod_read_word(cpu->gpr[29]+0x10));++intro_scan_calls;
        if(!(psx_mod_read_byte(0x800FA394u)&1u)) {
            uint32_t actor=0x8008EF48u;
            psx_mod_write_byte(0x800FA394u,1);psx_mod_write_byte(0x800FA397u,0x10);
            psx_mod_write_byte(actor,1);psx_mod_write_byte(actor+1,0);psx_mod_write_byte(actor+2,3);
            psx_mod_write_byte(actor+4,1);psx_mod_write_word(actor+0x10,0x800FA394u);
            psx_mod_write_word(actor+8,4960u<<16);psx_mod_write_word(actor+12,736u<<16);
            psx_mod_write_byte(actor+0x14,0);++intro_scan_allocations;
        }
        return 1;
    }
    if(scene_fatal_probe && (target==0x8003D308u || target==0x8003D330u)) {
        /* External original-call contract only. Native beam/death outcomes
         * below are explicitly supplied by the test, never the fixture. */
        CHECK(zero_projected && cpu->gpr[4]==0x14 && cpu->gpr[5]==0x40);
        if(target==0x8003D308u) {
            CHECK(!scene_owner && p2.body[0x5C]==32);++scene_lock_calls;
            script_begin(cpu,target);psx_mod_write_byte(PLAYER+5,20);
            psx_mod_write_byte(PLAYER+0x7A,1);psx_mod_write_byte(PLAY+0x1C,1);
        } else {
            CHECK(scene_owner==2);++scene_release_calls;
            psx_mod_write_byte(PLAYER+5,2);psx_mod_write_byte(PLAYER+0x7A,0);
            psx_mod_write_byte(PLAY+0x1C,0);
        }
        ++guest_calls;return 1;
    }
    if(refight_stub && (target==0x800EC430u || target==0x800EC860u)) {
        uint32_t actor=cpu->gpr[4];CHECK(scene_call && actor==0x800C1220u);
        uint32_t box=psx_mod_read_word(PLAYER+0x68);
        int x=(int16_t)psx_mod_read_half(PLAYER+10),y=(int16_t)psx_mod_read_half(PLAYER+14);
        int oy=(int8_t)psx_mod_read_byte(box+1),radius=psx_mod_read_byte(box+2),height=psx_mod_read_byte(box+3);
        unsigned action=psx_mod_read_byte(PLAYER+5);
        int hit=box && (action==2 || action==4 || action==20 || action==3) &&
            x-radius>=1872 && x+radius<=1904 && abs(1256-y-oy)<=8+height;
        if(target==0x800EC430u){++refight_probe_calls;cpu->gpr[2]=(uint32_t)hit;return 1;}
        CHECK(inside && zero_projected && psx_mod_read_byte(PLAYER+2)==1);++refight_action_calls;
        if(hit && !refight_refuse) {
            psx_mod_write_half(PLAYER+10,1888);psx_mod_write_half(PLAYER+14,(uint16_t)(1256-height));
            psx_mod_write_byte(PLAYER+0xD0,1);psx_mod_write_byte(PLAYER+0xD1,20);
            psx_mod_write_byte(PLAYER+0xD2,psx_mod_read_byte(PLAYER+0x15));
            psx_mod_write_byte(PLAYER+0x7A,1);psx_mod_write_byte(PLAY+0x1C,1);
            psx_mod_write_byte(actor+6,1);
            /* External full-callback contract from EC934 then ECBD0/31DA8:
             * native pedestal contact can replace the intermediate Y snap,
             * preserving the original fixed-point fraction. */
            if(refight_post_solid)psx_mod_write_half(PLAYER+14,1226);
            if(refight_admission_fault==1)psx_mod_write_byte(PLAYER+0xD0,0);
            if(refight_admission_fault==2)psx_mod_write_byte(PLAYER+0xD1,19);
            if(refight_admission_fault==3)psx_mod_write_byte(PLAYER+0xD2,psx_mod_read_byte(PLAYER+0x15)^1u);
            if(refight_admission_fault==4)psx_mod_write_byte(PLAYER+0x7A,0);
            if(refight_admission_fault==5)psx_mod_write_byte(PLAY+0x1C,0);
            if(refight_admission_fault==6)psx_mod_write_byte(actor+6,0);
            if(refight_admission_fault==7)psx_mod_write_half(PLAYER+10,1887);
        }
        psx_mod_write_byte(PLAY+0x66,0x5A);cpu->gpr[2]=0x12345678;return 1;
    }
    if(equipment_probe && target==0x8003D718u) {
        /* Typed external native contract only: source3D718 copies these
         * fields for admitted form1/5; this is not native gameplay execution. */
        CHECK(cpu->gpr[4]==PLAYER && !cpu->gpr[5] && psx_mod_read_byte(PLAY+0x60)==255);
        CHECK(checkpoint_pending.phase>=2 && psx_mod_read_byte(PLAY)==10);
        unsigned character=psx_mod_read_byte(PLAYER+2);CHECK(character<2);
        psx_mod_write_byte(PLAYER+0xE7,psx_mod_read_byte(PLAY+0x5E));
        psx_mod_write_word(PLAYER+0xEC,psx_mod_read_word(PLAY+0x74+character*4));
        psx_mod_write_byte(PLAYER+0xC9,psx_mod_read_byte(PLAY+0x60));
        ++equipment_calls;++guest_calls;return 1;
    }
    if(!before_doors_probe)return 0;
    const int explosion=before_doors_probe==2;
    CHECK(target==0x80029F38u && cpu->gpr[4]==(explosion?4528:5376) && cpu->gpr[5]==(explosion?4944:5792) &&
        cpu->gpr[6]==(explosion?656:208) && cpu->gpr[7]==(explosion?992:544) && !psx_mod_read_word(cpu->gpr[29]+0x10));
    CHECK(checkpoint_pending.phase==3 && psx_mod_read_byte(diagnostic+0xAD)==1);
    CHECK(psx_mod_read_word(PLAYER+8)==(explosion?4736u:5692u)<<16 &&
        le32(p2.body+8)==(explosion?4760u:5716u)<<16);
    CHECK(psx_mod_read_word(0x800971F8u+8)==(explosion?4576u:5424u)<<16 &&
        psx_mod_read_word(0x800971F8u+12)==(explosion?704u:256u)<<16);
    /* External native scanner contract only: allocate an original slot. Its
     * native init/grounding are deliberately NOT supplied by this model. */
    /* The real scanner first calls29E7C: low difficulty0 placement enters
     * lifetime10 at29EF8 unless PLAY+68==3 takes the no-change admission. */
    if(explosion)psx_mod_write_byte(0x800FA387u,psx_mod_read_byte(PLAY+0x68)==3?0:0x10);
    uint32_t a=explosion?0x8008EF48u:0x800C1220u;
    psx_mod_write_byte(a,1);psx_mod_write_byte(a+1,explosion?0:8);psx_mod_write_byte(a+2,explosion?1:2);
    psx_mod_write_word(a+0x10,explosion?0x800FA384u:0x800FA2A4u);
    psx_mod_write_half(a+10,explosion?4672:5744);psx_mod_write_half(a+14,explosion?736:384);
    psx_mod_write_byte(explosion?0x800FA384u:0x800FA2A4u,1);++guest_calls;return 1;
}
#ifdef MMX6_COOP_CHECKPOINT_TAINT_API
#define checkpoint_test_taint diagnostic_test_taint
#endif
const uint16_t *gpu_get_vram(void){return checkpoint_vram;}
void gpu_set_gp0_source(uint32_t source){(void)source;}
void gpu_write_gp0(uint32_t value){(void)value;}
#ifdef MMX6_COOP_AGREED_CHECKPOINT
static uint8_t before_doors_ram[0x200000];
static uint8_t portal_source_ram[0x200000],northpole_source_ram[0x200000];
static uint8_t gate_enemy_source_ram[0x200000],refight_source_ram[0x200000];
static const char *test_lab_option="off";
static const char *test_lab_contact_option="off";
static const char *test_lab_hp_option[2]={"off","off"};
static const char *test_lab_earned_option="off";
static const char *test_lab_fatal_option="off";
static const char *test_lab_hatch_stagger_option="off";
static unsigned test_lab_ready=1,test_lab_failed,test_lab_selected=1;
static PSXHostSelection test_lab_profile;
int psx_mod_option_value(const char *package,const char *feature,const char *option,char *out,uint32_t size) {
    CHECK(!strcmp(package,"mmx6.local-coop") && !strcmp(feature,"prototype"));
    CHECK(!strcmp(option,"lab_checkpoint") || !strcmp(option,"lab_contact_protection") || !strcmp(option,"lab_earned_weapons") ||
        !strcmp(option,"lab_starting_hp_p1") || !strcmp(option,"lab_starting_hp_p2") || !strcmp(option,"lab_fatal") ||
        !strcmp(option,"lab_hatch_stagger"));
    const char *value=!strcmp(option,"lab_checkpoint")?test_lab_option:
        !strcmp(option,"lab_contact_protection")?test_lab_contact_option:
        !strcmp(option,"lab_earned_weapons")?test_lab_earned_option:
        !strcmp(option,"lab_fatal")?test_lab_fatal_option:
        !strcmp(option,"lab_hatch_stagger")?test_lab_hatch_stagger_option:
        test_lab_hp_option[!strcmp(option,"lab_starting_hp_p2")];
    CHECK(size>strlen(value));strcpy(out,value);return 1;
}
int psx_netplay_host_profile_ready(void){return (int)test_lab_ready;}
int psx_netplay_host_profile_failed(void){return (int)test_lab_failed;}
int psx_netplay_host_profile_selection(PSXHostSelection *out){*out=test_lab_profile;return (int)test_lab_selected;}
#endif

static void setup_checkpoint(CPUState *cpu,unsigned stage,unsigned section,unsigned cp) {
    refusal_logs=0;refusal_log[0]=0;
    memcpy(test_ram,original_ram,sizeof test_ram);memset(test_diagnostic,0,sizeof test_diagnostic);
    memset(cpu,0,sizeof *cpu);memset(&p2,0x32,sizeof p2);diagnostic=0x9F080000u;
    inside=stage_call=player_call=zero_world=zero_projected=scene_owner=scene_phase=failed=0;
    ready=enrolled=1;pause_owner=-1;zero_menu_loaded=0;guest_calls=0;test_online=0;independent_views=0;
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
    /* Individual tests select their actual Recycle/first-hatch options after
     * this shared CP2 factory. Do not apply fixture-specific choices here. */
    const char *fatal=test_lab_fatal_option;
    if(!strcmp(fatal,"capsule_owner_p1") || !strcmp(fatal,"boss_admission_p1") || !strcmp(fatal,"armor_p1"))test_lab_fatal_option="off";
    const char *stagger=test_lab_hatch_stagger_option;test_lab_hatch_stagger_option="off";
    test_lab_option="intro_cp2";setup_checkpoint(cpu,0,0,2);test_online=online;
    test_lab_fatal_option=fatal;test_lab_hatch_stagger_option=stagger;
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
static void starting_hp_pending(CPUState *cpu,int online) {
    setup_agreed(cpu,online);CHECK(!checkpoint_starting_hp_applied);
    CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
    psx_mod_write_byte(PLAY,10);
    /* Only external native healthy/grounded initialization is modeled. The
     * actual plugin completion, authority and allowed writes are exercised. */
    memset(p2.body,0,sizeof p2.body);p2.body[0]=p2.body[3]=p2.body[4]=p2.body[2]=1;p2.body[5]=2;
    p2.body[0x5C]=p2.body[0x5D]=p2.body[0x5E]=32;p2.body[0x70]=8;put32(p2.body+0x68,0x80073D54u);
    for(unsigned i=0;i<sizeof p2.body;++i)psx_mod_write_byte(PLAYER+i,0);
    psx_mod_write_byte(PLAYER,1);psx_mod_write_byte(PLAYER+3,1);psx_mod_write_byte(PLAYER+4,1);psx_mod_write_byte(PLAYER+5,2);
    for(unsigned i=0x5C;i<=0x5E;++i)psx_mod_write_byte(PLAYER+i,32);
    psx_mod_write_byte(PLAYER+0x70,8);psx_mod_write_word(PLAYER+0x68,0x80073D50u);
    psx_mod_write_byte(PLAY+0x5B,32);psx_mod_write_byte(PLAY+0x5C,32);
}
static void fatal_ready(CPUState *cpu,int online,unsigned seat) {
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";
    test_lab_earned_option=test_lab_contact_option="off";
    clear_phase=clear_members=clear_started=0;
    test_lab_fatal_option=seat?"p2":"p1";
    starting_hp_pending(cpu,online);checkpoint_complete(cpu);
    CHECK(checkpoint_lab_completed() && !checkpoint_pending.phase && !checkpoint_fatal_state);
}
static void agreed_native_fatal(CPUState *cpu) {
    for(int online=0;online<=1;++online)for(unsigned seat=0;seat<2;++seat)for(unsigned support=0;support<2;++support) {
        fatal_ready(cpu,online,seat);
        /* Real Turtloid idle can be actor-supported with terrain contact zero. */
        if(support) {psx_mod_write_byte(PLAYER+0x70,0);psx_mod_write_byte(PLAYER+0x71,8);p2.body[0x70]=0;p2.body[0x71]=8;}
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_fatal_state); /* Held first chord is not a new edge. */
        CHECK(!checkpoint_lab_boundary(cpu,0) && checkpoint_fatal_state==CHECKPOINT_FATAL_ARMED);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext expected=p2;
        Mmx6CoopLifecycle expected_life=life;uint8_t receipt[sizeof test_diagnostic];
        memcpy(receipt,test_diagnostic,sizeof receipt);
        if(seat)expected.body[0x5C]=0x80;else before_ram[(PLAYER+0x5C)&0x1FFFFF]=0x80;
        receipt[0xC8]=(uint8_t)((seat+1)|(CHECKPOINT_FATAL_CONSUMED<<3));
        unsigned calls=guest_calls;
        CHECK(!checkpoint_lab_boundary(cpu,6) && checkpoint_fatal_state==CHECKPOINT_FATAL_CONSUMED);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&expected,&p2,sizeof p2));
        CHECK(!memcmp(&expected_life,&life,sizeof life) && !memcmp(receipt,test_diagnostic,sizeof receipt));
        CHECK(guest_calls==calls && checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        if(seat)p2.body[0x5C]=7;else psx_mod_write_byte(PLAYER+0x5C,7);
        for(unsigned edge=0;edge<4;++edge)CHECK(!checkpoint_lab_boundary(cpu,edge&1?6:0));
        CHECK((seat?p2.body[0x5C]:psx_mod_read_byte(PLAYER+0x5C))==7);
    }
    for(unsigned support=0;support<2;++support)for(unsigned bad=0;bad<12;++bad) {
        fatal_ready(cpu,1,0);
        if(support) {psx_mod_write_byte(PLAYER+0x70,0);psx_mod_write_byte(PLAYER+0x71,8);p2.body[0x70]=0;p2.body[0x71]=8;}
        CHECK(!checkpoint_lab_boundary(cpu,0));
        if(bad==0)pause_owner=0;if(bad==1)scene_owner=1;if(bad==2)p2.body[5]=3;
        if(bad==3)p2.body[0xD0]=1;if(bad==4) {psx_mod_write_byte(PLAYER+0x70,0);psx_mod_write_byte(PLAYER+0x71,0);}
        if(bad==5)test_lab_ready=0;if(bad==6)test_lab_failed=1;if(bad==7)test_lab_selected=0;
        if(bad==8)test_lab_profile.qualification[0]^=1;
        if(bad==9)psx_mod_write_byte(diagnostic+0xA8,CHECKPOINT_INITIALIZING);
        if(bad==10)p2.body[0x67]=1;if(bad==11)p2.body[4]=2;
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_fatal_state);
        pause_owner=-1;scene_owner=0;p2.body[4]=1;p2.body[5]=2;p2.body[0x67]=p2.body[0xD0]=0;
        psx_mod_write_byte(PLAYER+0x70,support?0:8);psx_mod_write_byte(PLAYER+0x71,support?8:0);
        test_lab_ready=test_lab_selected=1;test_lab_failed=0;
        if(bad==8)test_lab_profile.qualification[0]^=1;
        psx_mod_write_byte(diagnostic+0xA8,CHECKPOINT_COMPLETE);
        CHECK(!checkpoint_lab_boundary(cpu,6) && psx_mod_read_byte(PLAYER+0x5C)==32 && p2.body[0x5C]==32);
        CHECK(!checkpoint_lab_boundary(cpu,0));CHECK(!checkpoint_lab_boundary(cpu,6));
        CHECK(psx_mod_read_byte(PLAYER+0x5C)==0x80 && p2.body[0x5C]==32);
    }
    test_lab_fatal_option="invalid";setup_agreed(cpu,0);CHECK(failed);
    test_lab_fatal_option="p1";test_lab_option="off";checkpoint_reset();CHECK(failed);
    test_lab_fatal_option="off";test_lab_option="off";failed=0;checkpoint_reset();
    CHECK(!checkpoint_fatal_option && !checkpoint_fatal_state);
    starting_hp_pending(cpu,0);checkpoint_complete(cpu);
    CHECK(!checkpoint_lab_boundary(cpu,0));CHECK(!checkpoint_lab_boundary(cpu,6));
    CHECK(psx_mod_read_byte(PLAYER+0x5C)==32 && p2.body[0x5C]==32);
}
static void agreed_scene_fatal(CPUState *cpu) {
    for(int online=0;online<=1;++online)for(unsigned option=3;option<=4;++option) {
        test_lab_hp_option[0]=test_lab_hp_option[1]="off";
        test_lab_earned_option=test_lab_contact_option="off";
        test_lab_fatal_option=option==3?"scene_before_release":"scene_during_arrival";
        starting_hp_pending(cpu,online);checkpoint_complete(cpu);
        CHECK(checkpoint_fatal_option==option && checkpoint_lab_completed());
        scene_fatal_probe=1;scene_lock_calls=scene_release_calls=0;
        CHECK(!checkpoint_lab_boundary(cpu,6) && !scene_lock_calls);
        CHECK(!checkpoint_lab_boundary(cpu,0));CHECK(!checkpoint_lab_boundary(cpu,6));
        CHECK(scene_lock_calls==1 && !scene_release_calls && scene_owner==2 && scene_phase==1);
        CHECK(checkpoint_fatal_state==CHECKPOINT_FATAL_SCENE_LOCKED && p2.body[0x5C]==32);
        CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        for(unsigned held=0;held<3;++held)CHECK(!checkpoint_lab_boundary(cpu,6));
        CHECK(scene_lock_calls==1 && !scene_release_calls && p2.body[0x5C]==32);
        /* Supply actual outgoing completion; the fixture may not write it. */
        scene_phase=3;psx_mod_write_byte(PLAYER+4,3);
        CHECK(!checkpoint_lab_boundary(cpu,0));
        if(option==3) {
            CHECK(!scene_release_calls && p2.body[0x5C]==0x80 &&
                checkpoint_fatal_state==CHECKPOINT_FATAL_SCENE_WAIT_DEATH);
            CHECK(life.status[1]==MMX6_COOP_ALIVE);
            CHECK(!checkpoint_lab_boundary(cpu,0) && !scene_release_calls);
            /* Only the external native death result enables original release. */
            p2.body[0x5C]=0;p2.body[4]=2;life.status[1]=MMX6_COOP_DYING;
            CHECK(!checkpoint_lab_boundary(cpu,0));CHECK(scene_release_calls==1);
        } else {
            CHECK(scene_release_calls==1 && p2.body[0x5C]==32 &&
                checkpoint_fatal_state==CHECKPOINT_FATAL_SCENE_WAIT_ARRIVAL);
            CHECK(!checkpoint_lab_boundary(cpu,0) && p2.body[0x5C]==32);
            /* Only the external incoming phase permits the fatal request. */
            scene_phase=4;psx_mod_write_byte(PLAYER+4,1);
            CHECK(!checkpoint_lab_boundary(cpu,0));CHECK(p2.body[0x5C]==0x80);
            CHECK(life.status[1]==MMX6_COOP_ALIVE);
        }
        CHECK(checkpoint_fatal_state==CHECKPOINT_FATAL_CONSUMED);
        for(unsigned edge=0;edge<4;++edge)CHECK(!checkpoint_lab_boundary(cpu,edge&1?6:0));
        CHECK(scene_lock_calls==1 && scene_release_calls==1);
        scene_fatal_probe=0;
    }
    /* Loss of agreed authority consumes an active request without mutation. */
    test_lab_fatal_option="scene_before_release";starting_hp_pending(cpu,1);checkpoint_complete(cpu);
    scene_fatal_probe=1;CHECK(!checkpoint_lab_boundary(cpu,0));CHECK(!checkpoint_lab_boundary(cpu,6));
    scene_phase=3;psx_mod_write_byte(PLAYER+4,3);test_lab_ready=0;
    CHECK(!checkpoint_lab_boundary(cpu,0) && checkpoint_fatal_state==CHECKPOINT_FATAL_CONSUMED);
    CHECK(p2.body[0x5C]==32);scene_fatal_probe=0;test_lab_ready=1;
    test_lab_option="turtloid_cp1";checkpoint_reset();CHECK(failed);
    test_lab_fatal_option="off";test_lab_option="off";failed=0;checkpoint_reset();
}
static void agreed_starting_hp(CPUState *cpu) {
    CHECK(!checkpoint_starting_hp_parse("off") && checkpoint_starting_hp_parse("1")==1 && checkpoint_starting_hp_parse("32")==32);
    CHECK(checkpoint_starting_hp_parse("99999999999999999999999999")==33);
    const char *invalid[]={"0","00","01","33","-1","+1","1x",""};
    for(unsigned i=0;i<sizeof invalid/sizeof invalid[0];++i) {
        test_lab_hp_option[0]=invalid[i];test_lab_hp_option[1]="off";setup_agreed(cpu,1);CHECK(failed);
    }
    test_lab_hp_option[0]="17";test_lab_hp_option[1]="23";
    for(int online=0;online<=1;++online) {
        for(unsigned bad=0;bad<16;++bad) {
            starting_hp_pending(cpu,online);CHECK(checkpoint_starting_hp_status()==1);
            if(bad==0)enrolled=0;if(bad==1)ready=0;if(bad==2)inside=1;
            if(bad==3)zero_projected=1;if(bad==4)private_draw=1;if(bad==5)pause_owner=0;
            if(bad==6)p2.body[0x70]=0;if(bad==7)p2.body[5]=0;if(bad==8)p2.body[0x5C]=31;
            if(bad==9)psx_mod_write_byte(PLAYER+0x5C,31);if(bad==10)p2.body[0x5E]=31;
            if(bad==11)psx_mod_write_byte(PLAY+0x5B,40);if(bad==12)p2.body[0x5D]=31;
            if(bad==13)life.status[1]=MMX6_COOP_FALLEN;if(bad==14)psx_mod_write_byte(PLAYER+2,1);
            if(bad==15) {psx_mod_write_byte(PLAYER+2,1);p2.body[2]=0;} /* Complete inverse roster stays refused. */
            unsigned x=psx_mod_read_byte(PLAYER+0x5C),z=p2.body[0x5C];
            CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !checkpoint_starting_hp_applied);
            CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_INITIALIZING && psx_mod_read_byte(PLAYER+0x5C)==x && p2.body[0x5C]==z);
            private_draw=0;pause_owner=-1;
        }
        starting_hp_pending(cpu,online);PlayerContext expected=p2;expected.body[0x5C]=23;
        memcpy(before_ram,test_ram,sizeof test_ram);before_ram[(PLAYER+0x5C)&0x1FFFFF]=17;
        unsigned calls=guest_calls;CHECK(!checkpoint_stage_boundary(cpu));
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&expected,&p2,sizeof p2) && guest_calls==calls);
        CHECK(checkpoint_starting_hp_applied==1 && !checkpoint_pending.phase && psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE);
        CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        diagnostics(0);CHECK(psx_mod_read_word(diagnostic+0xC0)==0x03171102u);
        /* Hits, native boundary, FALLEN/revival and even a repeated finish
         * never restore the setup HP. No per-frame damage compensation. */
        psx_mod_write_byte(PLAYER+0x5C,5);p2.body[0x5C]=6;
        CHECK(!checkpoint_stage_boundary(cpu) && psx_mod_read_byte(PLAYER+0x5C)==5 && p2.body[0x5C]==6);
        psx_mod_write_byte(PLAY+12,20);life.status[0]=MMX6_COOP_FALLEN;checkpoint_complete(cpu);
        life.status[0]=MMX6_COOP_ALIVE;checkpoint_complete(cpu);
        CHECK(psx_mod_read_byte(PLAYER+0x5C)==5 && p2.body[0x5C]==6 && checkpoint_starting_hp_applied==1);
        starting_hp_pending(cpu,online);psx_mod_write_byte(0x8003BE74u,0);CHECK(!checkpoint_stage_boundary(cpu));
        CHECK(!checkpoint_starting_hp_applied && psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE);
        starting_hp_pending(cpu,online);psx_mod_write_byte(diagnostic+0xBC,0);CHECK(!checkpoint_stage_boundary(cpu));
        CHECK(!checkpoint_starting_hp_applied && psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_FORBIDDEN);
        if(online) {
            starting_hp_pending(cpu,1);test_lab_profile.qualification[0]^=1;CHECK(!checkpoint_stage_boundary(cpu));
            CHECK(!checkpoint_starting_hp_applied && !checkpoint_pending.phase);
        }
    }
    test_lab_hp_option[0]="1";test_lab_hp_option[1]="off";starting_hp_pending(cpu,1);
    CHECK(!checkpoint_stage_boundary(cpu) && psx_mod_read_byte(PLAYER+0x5C)==1 && p2.body[0x5C]==32 &&
        life.status[0]==MMX6_COOP_ALIVE && life.status[1]==MMX6_COOP_ALIVE);
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";starting_hp_pending(cpu,1);
    CHECK(!checkpoint_stage_boundary(cpu) && psx_mod_read_byte(PLAYER+0x5C)==32 && p2.body[0x5C]==32 && !checkpoint_starting_hp_applied);
    test_lab_hp_option[0]="1";test_lab_option="off";setup_checkpoint(cpu,0,0,2);CHECK(failed);
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";setup_agreed(cpu,1);checkpoint_reset();
    CHECK(!checkpoint_starting_hp[0] && !checkpoint_starting_hp[1] && !checkpoint_starting_hp_applied);
}
static void agreed_subtank_prerequisite(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        setup_agreed(cpu,online);test_lab_option="intro_subtank_cp2";checkpoint_reset();
        separate_subtanks=0;memcpy(before_ram,test_ram,sizeof test_ram);
        CHECK(checkpoint_lab_option==20 && checkpoint_lab_index()==2 && checkpoint_lab_nonce()==0x4C535432u);
        CHECK(!checkpoint_lab_boundary(cpu,6));
        CHECK(!checkpoint_pending.phase && !memcmp(before_ram,test_ram,sizeof test_ram));
        CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_FORBIDDEN);
        setup_agreed(cpu,online);test_lab_option="intro_subtank_cp2";checkpoint_reset();
        separate_subtanks=1;subtank_seeded=0;memset(zero_subtanks,0,sizeof zero_subtanks);
        psx_mod_write_byte(PLAY+0x63,0x81);psx_mod_write_byte(PLAY+0x64,0x86);
        psx_mod_write_byte(PLAY+0x6B,4);
        CHECK(checkpoint_lab_boundary(cpu,6));
        CHECK(checkpoint_pending.index==2 && checkpoint_pending.nonce==0x4C535432u && checkpoint_pending.phase==1);
        CHECK(psx_mod_read_byte(PLAY)==8 && psx_mod_read_byte(PLAY+0x63)==0x90 && psx_mod_read_byte(PLAY+0x64)==0x86);
        CHECK(subtank_seeded && zero_subtanks[0]==0x88 && zero_subtanks[1]==0x86 && subtank_found==0x10);
        CHECK(psx_mod_read_byte(PLAY+0x6B)==0x14);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(checkpoint_pending.phase==2 && psx_mod_read_byte(PLAY+0x1D)==2);
        psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu));
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE);
        CHECK(psx_mod_read_byte(PLAY+0x63)==0x90 && zero_subtanks[0]==0x88 && psx_mod_read_byte(PLAY+0x6B)==0x14);
        /* Consumed request never replenishes a spent native/private bank. */
        psx_mod_write_byte(PLAY+0x63,0x80);zero_subtanks[0]=0x80;
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
        CHECK(psx_mod_read_byte(PLAY+0x63)==0x80 && zero_subtanks[0]==0x80);
    }
    separate_subtanks=subtank_seeded=subtank_found=0;memset(zero_subtanks,0,sizeof zero_subtanks);
    test_lab_option="off";checkpoint_reset();
}
static void agreed_turtloid_boundary(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        setup_agreed(cpu,online);test_lab_option="turtloid_rain_cp1";checkpoint_reset();
        CHECK(checkpoint_lab_option==8 && checkpoint_lab_index()==32 && checkpoint_lab_nonce()==0x4C545231u);
        CHECK(checkpoint_lab_boundary(cpu,6));CHECK(checkpoint_pending.index==32 && checkpoint_pending.nonce==0x4C545231u);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(psx_mod_read_byte(PLAY+12)==6 && !psx_mod_read_byte(PLAY+13) && psx_mod_read_byte(PLAY+0x1D)==1);
        psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu));
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && psx_mod_read_word(diagnostic+0xB8)==0x80072588u);
    }
    test_lab_option="off";checkpoint_reset();
}
static void agreed_heatnix_boundary(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        setup_agreed(cpu,online);test_lab_option="heatnix_cp7";checkpoint_reset();
        CHECK(checkpoint_lab_option==17 && checkpoint_lab_index()==20 && checkpoint_lab_nonce()==0x4C484E37u);
        CHECK(checkpoint_lab_boundary(cpu,6));CHECK(checkpoint_pending.index==20 && checkpoint_pending.nonce==0x4C484E37u);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(psx_mod_read_byte(PLAY+12)==3 && !psx_mod_read_byte(PLAY+13) && psx_mod_read_byte(PLAY+0x1D)==7);
        psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu));
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && psx_mod_read_word(diagnostic+0xB8)==0x800723D8u);
    }
    test_lab_option="off";checkpoint_reset();
}
static void agreed_magma_start_boundary(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        setup_agreed(cpu,online);test_lab_option="heatnix_cp0";checkpoint_reset();
        CHECK(checkpoint_lab_option==19 && checkpoint_lab_index()==13 && checkpoint_lab_nonce()==0x4C484E30u);
        CHECK(checkpoint_lab_boundary(cpu,6));CHECK(checkpoint_pending.index==13 && checkpoint_pending.nonce==0x4C484E30u);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(psx_mod_read_byte(PLAY+12)==3 && !psx_mod_read_byte(PLAY+13) && psx_mod_read_byte(PLAY+0x1D)==0);
        psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu));
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && psx_mod_read_word(diagnostic+0xB8)==0x800722DCu);
    }
    test_lab_option="off";checkpoint_reset();
}
static void agreed_sigma_boundary(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        setup_agreed(cpu,online);test_lab_option="sigma_cp1";checkpoint_reset();
        CHECK(checkpoint_lab_option==18 && checkpoint_lab_index()==78 && checkpoint_lab_nonce()==0x4C534731u);
        CHECK(checkpoint_lab_boundary(cpu,6));CHECK(checkpoint_pending.index==78 && checkpoint_pending.nonce==0x4C534731u);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(psx_mod_read_byte(PLAY+12)==12 && psx_mod_read_byte(PLAY+13)==1 && psx_mod_read_byte(PLAY+0x1D)==1);
        psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu));
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && psx_mod_read_word(diagnostic+0xB8)==0x80072C00u);
    }
    test_lab_option="off";checkpoint_reset();
}
static void agreed_alternate_boundary(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        setup_agreed(cpu,online);test_lab_option="alternate_boss_cp1";checkpoint_reset();
        CHECK(checkpoint_lab_option==9 && checkpoint_lab_index()==106 && checkpoint_lab_nonce()==0x4C414231u);
        CHECK(checkpoint_lab_boundary(cpu,6));CHECK(checkpoint_pending.index==106 && checkpoint_pending.nonce==0x4C414231u);
        /* The ordinary loader owns mode8/9; no door, boss, hit or availability flag is authored. */
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(psx_mod_read_byte(PLAY+12)==20 && psx_mod_read_byte(PLAY+13)==1 && psx_mod_read_byte(PLAY+0x1D)==1);
        psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu));
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && psx_mod_read_word(diagnostic+0xB8)==0x80072FF0u);
    }
    test_lab_option="off";checkpoint_reset();
}
/* The original CP4 is a reachability prerequisite only. No boss/child,
 * progress, HP, action, world collision or successful contact is seeded. */
static void agreed_gate_homing_boundary(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        setup_agreed(cpu,online);test_lab_option="gate_homing_cp4";checkpoint_reset();
        CHECK(checkpoint_lab_option==25 && checkpoint_lab_index()==98 && checkpoint_lab_nonce()==0x4C474834u);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;CPUState registers=*cpu;
        CHECK(checkpoint_lab_boundary(cpu,6) && checkpoint_pending.index==98 && checkpoint_pending.nonce==0x4C474834u);
        before_ram[PLAY&0x1FFFFF]=8;before_ram[(PLAY+12)&0x1FFFFF]=18;before_ram[(PLAY+13)&0x1FFFFF]=0;
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) && !memcmp(&registers,cpu,sizeof *cpu) && !guest_calls);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(psx_mod_read_byte(PLAY+12)==18 && !psx_mod_read_byte(PLAY+13) && psx_mod_read_byte(PLAY+0x1D)==4);
        psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_lab_completed());
        CHECK(psx_mod_read_word(diagnostic+0xB8)==0x80072ED0u && psx_mod_read_word(diagnostic+0xA4)==1);
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
        CHECK(!checkpoint_sequence_state && !checkpoint_sequence_cursor && !checkpoint_sequence_release);
    }
    test_lab_option="off";checkpoint_reset();
}
/* Only the authored Laser CP1 entry is requested. Beam admission, geometry,
 * collision and view isolation remain original native outcomes. */
static void agreed_laser_boundary(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        setup_agreed(cpu,online);test_lab_option="laser_cp1";checkpoint_reset();
        const Mmx6Checkpoint *entry=&checkpoint_inventory[38];
        CHECK(checkpoint_lab_option==26 && checkpoint_lab_index()==38 && checkpoint_lab_nonce()==0x4C4C5331u);
        CHECK(entry->stage==7 && !entry->section && entry->checkpoint==1 && entry->table==0x800731C8u &&
            entry->record==0x80072660u && entry->hash==0xD9C638CFu);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;CPUState registers=*cpu;
        CHECK(checkpoint_lab_boundary(cpu,6) && checkpoint_pending.index==38 && checkpoint_pending.nonce==0x4C4C5331u);
        before_ram[PLAY&0x1FFFFF]=8;before_ram[(PLAY+12)&0x1FFFFF]=7;before_ram[(PLAY+13)&0x1FFFFF]=0;
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) &&
            !memcmp(&registers,cpu,sizeof *cpu) && !guest_calls && checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(psx_mod_read_byte(PLAY+12)==7 && !psx_mod_read_byte(PLAY+13) && psx_mod_read_byte(PLAY+0x1D)==1);
        psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_lab_completed());
        CHECK(psx_mod_read_word(diagnostic+0xB8)==0x80072660u && psx_mod_read_word(diagnostic+0xA4)==1 &&
            psx_mod_read_word(diagnostic+0xB4)==1);
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase);
        for(unsigned bad=0;bad<3;++bad) {
            setup_agreed(cpu,online);test_lab_option="laser_cp1";checkpoint_reset();
            if(bad==0)psx_mod_write_byte(0x80072660u,psx_mod_read_byte(0x80072660u)^1u);
            if(bad==1)psx_mod_write_byte(PLAY+12,4); /* This alias admits only original Intro. */
            if(bad==2)checkpoint_lab_state=CHECKPOINT_LAB_CONSUMED;
            memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;registers=*cpu;
            CHECK(!(bad==2?checkpoint_request(7,0,0,0x4C4C5331u,CHECKPOINT_AGREED):checkpoint_lab_boundary(cpu,6)));
            CHECK(psx_mod_read_byte(diagnostic+0xA9)==(bad==0?CHECKPOINT_SOURCE:bad==1?CHECKPOINT_ORDER:CHECKPOINT_UNKNOWN));
            CHECK(!checkpoint_pending.phase && !checkpoint_test_taint && !guest_calls &&
                !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) && !memcmp(&registers,cpu,sizeof *cpu));
        }
    }
    test_lab_option="off";checkpoint_reset();
}
/* Exercise the real SDK callback type even when the plugin constructor is
 * disabled in this unit producer. A third callback argument is an ABI error. */
static void sequence_input_call(CPUState *cpu,uint32_t address) {
    PSXModFunctionEntryCallback callback=checkpoint_sequence_input;
    callback(cpu,address);
}
static void sequence_first_complete(CPUState *cpu,int online) {
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";
    test_lab_earned_option=test_lab_fatal_option=test_lab_contact_option="off";
    setup_agreed(cpu,online);test_lab_option="alternate_sequence_cp1";checkpoint_reset();
    CHECK(checkpoint_lab_option==24 && checkpoint_lab_index()==106 && checkpoint_lab_nonce()==0x4C414231u);
    CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
    psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_lab_receipt_complete());
    cpu->gpr[29]=0x801FFF00u;psx_mod_write_word(cpu->gpr[29]+16,0x80012220u);
    CHECK(psx_mod_read_word(0x80012C44u)==0x8FBF0010u); /* Pinned original EXE. */
    /* External native story/Map observations, not fixture-produced outcomes. */
    psx_mod_write_byte(PLAY+0x43B,1);psx_mod_write_byte(PLAY+0x5F,17);
    psx_mod_write_byte(PLAY,4);psx_mod_write_byte(PLAY+1,4);psx_mod_write_byte(PLAY+2,0);
    psx_mod_write_byte(PLAY+12,13);psx_mod_write_byte(PLAY+0x27,0);
    psx_mod_write_byte(PLAY+0x2A,0);psx_mod_write_byte(0x80097424u,0);
}
static void sequence_responsive_map(CPUState *cpu) {
    memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;CPUState registers=*cpu;
    sequence_input_call(cpu,0x80012C44u);
    CHECK(checkpoint_sequence_state==CHECKPOINT_SEQUENCE_MAP);
    CHECK(psx_mod_read_byte(diagnostic+0xC9)==CHECKPOINT_SEQUENCE_MAP &&
        psx_mod_read_byte(diagnostic+0xCA)==1 && !psx_mod_read_byte(diagnostic+0xCB));
    CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) && !memcmp(&registers,cpu,sizeof *cpu));
    /* Diagnostic edits cannot grant, deny or advance the actual sequence. */
    psx_mod_write_byte(diagnostic+0xC9,255);psx_mod_write_byte(diagnostic+0xCA,255);psx_mod_write_byte(diagnostic+0xCB,255);
    sequence_input_call(cpu,0x80012C44u);CHECK(checkpoint_sequence_state==CHECKPOINT_SEQUENCE_MAP);
    psx_mod_write_byte(PLAY+0x2A,7);sequence_input_call(cpu,0x80012C44u);
    CHECK(checkpoint_sequence_state==CHECKPOINT_SEQUENCE_MAP && !checkpoint_sequence_cursor);
    /* Retained native Map4 response was PLAY27 0->1; +2A alone cannot qualify. */
    psx_mod_write_byte(PLAY+0x27,1);memcpy(before_ram,test_ram,sizeof test_ram);
    sequence_input_call(cpu,0x80012C44u);
    CHECK(checkpoint_sequence_state==CHECKPOINT_SEQUENCE_RESPONSIVE);
    CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) && !memcmp(&registers,cpu,sizeof *cpu));
}
static void sequence_ordinary_mission(CPUState *cpu) {
    psx_mod_write_byte(PLAY+12,4);psx_mod_write_byte(PLAY+13,0);mode9(cpu);
    checkpoint_native_entry(cpu,0x8001E1BCu);CHECK(checkpoint_sequence_state==CHECKPOINT_SEQUENCE_MISSION);
    CHECK(psx_mod_read_byte(diagnostic+0xC9)==CHECKPOINT_SEQUENCE_MISSION &&
        psx_mod_read_byte(diagnostic+0xCA)==2 && !psx_mod_read_byte(diagnostic+0xCB));
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+1,0);
    /* External ordinary native body initialization after the new mission. */
    for(unsigned seat=0;seat<2;++seat) {
        uint8_t body[sizeof p2.body]={0};body[0]=body[3]=body[4]=1;body[2]=(uint8_t)seat;body[5]=2;
        body[0x5C]=body[0x5D]=body[0x5E]=32;body[0x70]=8;put32(body+0x68,0x80073D50u+seat*4u);
        if(seat)memcpy(p2.body,body,sizeof body);else project(PLAYER,body,sizeof body);
    }
    CHECK(checkpoint_before_doors_idle(0) && checkpoint_before_doors_idle(1));
}
static void agreed_alternate_sequence(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        sequence_first_complete(cpu,online);sequence_responsive_map(cpu);sequence_ordinary_mission(cpu);
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_sequence_release); /* Held UI chord is not a request. */
        CHECK(!checkpoint_lab_boundary(cpu,0) && checkpoint_sequence_release);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;CPUState registers=*cpu;Mmx6CoopLifecycle living=life;
        CHECK(checkpoint_lab_boundary(cpu,6) && checkpoint_sequence_state==CHECKPOINT_SEQUENCE_USED);
        before_ram[PLAY&0x1FFFFF]=8;before_ram[(PLAY+12)&0x1FFFFF]=20;before_ram[(PLAY+13)&0x1FFFFF]=1;
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2));
        CHECK(!memcmp(&living,&life,sizeof life) && !memcmp(&registers,cpu,sizeof *cpu) && !guest_calls);
        CHECK(checkpoint_pending.index==106 && checkpoint_pending.nonce==0x4C414231u && psx_mod_read_word(diagnostic+0xA4)==2);
        CHECK(psx_mod_read_byte(PLAY+0x43B)==1 && psx_mod_read_byte(PLAY+0x5F)==17);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);psx_mod_write_byte(PLAY,10);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_lab_receipt_complete() && checkpoint_lab_completed());
        for(unsigned edge=0;edge<4;++edge)CHECK(!checkpoint_lab_boundary(cpu,edge&1?6:0));
        /* Even another actual Map/mission cannot grant a third request. */
        psx_mod_write_byte(PLAY,4);psx_mod_write_byte(PLAY+1,4);psx_mod_write_byte(PLAY+12,13);psx_mod_write_byte(PLAY+0x27,0);
        sequence_input_call(cpu,0x80012C44u);psx_mod_write_byte(PLAY+0x27,1);
        sequence_input_call(cpu,0x80012C44u);
        psx_mod_write_byte(PLAY+12,4);psx_mod_write_byte(PLAY+13,0);mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
        CHECK(checkpoint_sequence_state==CHECKPOINT_SEQUENCE_USED && psx_mod_read_word(diagnostic+0xA4)==2);
    }
    for(int online=0;online<=1;++online) {
        sequence_first_complete(cpu,online);
        /* Actual native Map withdrawal: neither body's enrolled/draw/state nor
         * the last diagnostic publication is authority for a world actor. */
        enrolled=arrival_pair=0;scene_owner=1;scene_phase=3;
        psx_mod_write_byte(PLAYER+3,0);psx_mod_write_byte(PLAYER+4,3);
        p2.body[3]=0;p2.body[4]=3;
        sequence_responsive_map(cpu);
        CHECK(!enrolled && !arrival_pair && scene_owner==1 && scene_phase==3);
    }
    for(unsigned bad=0;bad<18;++bad) {
        sequence_first_complete(cpu,1);
        if(bad==0)psx_mod_write_byte(PLAY+1,3);if(bad==1)psx_mod_write_byte(PLAY+2,1);
        if(bad==2)psx_mod_write_byte(0x80097424u,1);if(bad==3)psx_mod_write_byte(PLAY+0x27,24);
        if(bad==4)cpu->gpr[29]|=1;if(bad==5)psx_mod_write_word(cpu->gpr[29]+16,0x80000000u);
        if(bad==6)inside=1;if(bad==7)zero_projected=1;if(bad==8)test_lab_ready=0;
        if(bad==9)test_lab_selected=0;if(bad==10)test_lab_profile.qualification[0]^=1;
        if(bad==11)psx_mod_write_word(diagnostic+0xA4,2);
        if(bad==13)psx_mod_write_word(0x80012C44u,0); /* Actual RAM word guard. */
        if(bad==14)cpu->gpr[29]=0x80200000u;
        if(bad==15)psx_mod_write_byte(PLAY+12,20);
        if(bad==16) { /* A fresh app/Map without prior receipt still has no authority. */
            enrolled=0;checkpoint_reset();memset(test_diagnostic,0,sizeof test_diagnostic);
        }
        if(bad==17)ready=0;
        memcpy(before_ram,test_ram,sizeof test_ram);CPUState registers=*cpu;PlayerContext partner=p2;
        sequence_input_call(cpu,bad==12?0x80012C40u:0x80012C44u);
        CHECK(!checkpoint_sequence_state && !checkpoint_sequence_release);
        CHECK(psx_mod_read_byte(diagnostic+0xCA)==1 && psx_mod_read_byte(diagnostic+0xCB));
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) && !memcmp(&registers,cpu,sizeof *cpu));
    }
    for(unsigned bad=0;bad<10;++bad) {
        sequence_first_complete(cpu,1);sequence_responsive_map(cpu);sequence_ordinary_mission(cpu);
        CHECK(!checkpoint_lab_boundary(cpu,0) && checkpoint_sequence_release);
        if(bad==0)psx_mod_write_byte(PLAY+12,0);if(bad==1)psx_mod_write_byte(PLAY+0x1D,1);
        if(bad==2)scene_owner=1;if(bad==3)pause_owner=0;if(bad==4)p2.body[0x5C]=0;
        if(bad==5)p2.body[0x67]=1;if(bad==6)test_lab_selected=0;if(bad==7)psx_mod_write_byte(PLAY,9);
        if(bad==8)psx_mod_write_word(diagnostic+0xA4,2);if(bad==9)zero_projected=1;
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;CPUState registers=*cpu;
        CHECK(!checkpoint_lab_boundary(cpu,6) && checkpoint_sequence_state!=CHECKPOINT_SEQUENCE_USED);
        CHECK(!checkpoint_sequence_release);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) && !memcmp(&registers,cpu,sizeof *cpu));
    }
    for(unsigned bad=0;bad<8;++bad) {
        sequence_first_complete(cpu,1);sequence_responsive_map(cpu);
        psx_mod_write_byte(PLAY+12,4);psx_mod_write_byte(PLAY+13,0);mode9(cpu);
        if(bad==0)checkpoint_sequence_state=CHECKPOINT_SEQUENCE_MAP;
        if(bad==1)cpu->gpr[31]=0;if(bad==2)cpu->gpr[4]=0;
        if(bad==3)psx_mod_write_byte(PLAY,8);if(bad==4)psx_mod_write_byte(PLAY+12,5);
        if(bad==5)psx_mod_write_byte(PLAY+0x1D,1);if(bad==6)inside=1;
        memcpy(before_ram,test_ram,sizeof test_ram);CPUState registers=*cpu;PlayerContext partner=p2;
        checkpoint_native_entry(cpu,bad==7?0x8001E1B8u:0x8001E1BCu);
        CHECK(checkpoint_sequence_state!=CHECKPOINT_SEQUENCE_MISSION && !checkpoint_sequence_release);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) && !memcmp(&registers,cpu,sizeof *cpu));
        unsigned refusal=psx_mod_read_byte(diagnostic+0xCB);
        CHECK(psx_mod_read_byte(diagnostic+0xCA)==2 && refusal);
        psx_mod_write_byte(PLAY,10);
        sequence_input_call(cpu,0x80012C44u); /* Routine mission input cannot hide the mode9 failure. */
        CHECK(psx_mod_read_byte(diagnostic+0xCA)==2 && psx_mod_read_byte(diagnostic+0xCB)==refusal);
    }
    test_lab_option="off";checkpoint_reset();
}
static void setup_earned(CPUState *cpu,int online) {
    test_lab_earned_option="all";setup_agreed(cpu,online);equipment_probe=1;equipment_calls=0;
    cpu->gpr[29]=0x801FFF00u;
    memset(p2.body,0,sizeof p2.body);
    for(unsigned i=0;i<sizeof p2.body;++i)psx_mod_write_byte(PLAYER+i,0);
    for(unsigned seat=0;seat<2;++seat) {
        uint8_t body[sizeof p2.body]={0};
        body[0]=body[3]=body[4]=1;body[2]=(uint8_t)seat;body[5]=2;
        body[0x5C]=body[0x5D]=body[0x5E]=32;body[0x70]=8;body[0xE7]=(uint8_t)(seat?5:1);
        put32(body+0x68,0x80073D50u+seat*4u);put32(body+0xEC,seat?0x00405060u:0x00102030u);
        if(seat)memcpy(p2.body,body,sizeof body);else project(PLAYER,body,sizeof body);
    }
    psx_mod_write_byte(PLAY+0x38,0);psx_mod_write_byte(PLAY+0x5E,1);psx_mod_write_byte(PLAY+0x60,0);
    psx_mod_write_byte(PLAY+0x5B,32);psx_mod_write_byte(PLAY+0x5C,32);
    psx_mod_write_word(PLAY+0x74,0x00102030u);psx_mod_write_word(PLAY+0x78,0x00405060u);
}
/* F86 reachability only: immutable row93 and original mode8/9 transaction. */
static void agreed_fortress_cp3_boundary(CPUState *cpu) {
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";
    test_lab_contact_option=test_lab_fatal_option="off";
    for(int online=0;online<=1;++online)for(unsigned loaded=0;loaded<=1;++loaded) {
        setup_earned(cpu,online);test_lab_option="secretlab2a_cp3";
        test_lab_earned_option="off";checkpoint_reset();equipment_probe=equipment_calls=0;
        CHECK(!failed && checkpoint_lab_option==22 && checkpoint_lab_index()==93 &&
            checkpoint_lab_nonce()==0x4C463933u && checkpoint_source(&checkpoint_inventory[93]));
        psx_mod_write_byte(PLAY+12,(uint8_t)(loaded?4:0));
        psx_mod_write_byte(PLAY+0x60,0xFF);psx_mod_write_byte(PLAYER+0xC8,3);p2.body[0xC8]=5;
        psx_mod_write_byte(PLAYER+0xC9,0xFF);p2.body[0xC9]=0xFF;
        psx_mod_write_half(PLAYER+0xB2,288);p2.body[0xB2]=240;
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(checkpoint_lab_boundary(cpu,6) && checkpoint_pending.index==93 &&
            checkpoint_pending.nonce==0x4C463933u && checkpoint_pending.authority==CHECKPOINT_AGREED);
        before_ram[PLAY&0x1FFFFF]=8;before_ram[(PLAY+12)&0x1FFFFF]=17;
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body) &&
            !equipment_calls && !guest_calls && !checkpoint_earned_weapons_applied);
        CHECK(psx_mod_read_word(diagnostic+0xB8)==0x80072E1Cu &&
            checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(checkpoint_pending.phase==2 && psx_mod_read_byte(PLAY+0x1D)==3 &&
            psx_mod_read_word(diagnostic+0xB4)==1 && !equipment_calls && !guest_calls);
        psx_mod_write_byte(PLAY,10);memcpy(before_ram,test_ram,sizeof test_ram);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_lab_completed() &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body));
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
    }
    for(unsigned bad=0;bad<5;++bad) {
        setup_earned(cpu,1);test_lab_option="secretlab2a_cp3";test_lab_earned_option="off";
        checkpoint_reset();equipment_probe=equipment_calls=0;
        psx_mod_write_byte(PLAY+12,(uint8_t)(bad==2?18:4));
        if(bad==0)psx_mod_write_byte(PLAY+13,1);
        if(bad==1)psx_mod_write_byte(PLAY+0x1D,1);
        if(bad==3)test_lab_profile.qualification[0]^=1;
        if(bad==4)psx_mod_write_byte(0x80072E1Cu,psx_mod_read_byte(0x80072E1Cu)^1u);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !checkpoint_test_taint &&
            !equipment_calls && !guest_calls && !memcmp(before_ram,test_ram,sizeof test_ram) &&
            !memcmp(&body,&p2,sizeof body));
        CHECK(psx_mod_read_byte(diagnostic+0xA9)==(bad==3?CHECKPOINT_FORBIDDEN:
            bad==4?CHECKPOINT_SOURCE:CHECKPOINT_ORDER));
    }
    for(unsigned unsafe=0;unsafe<4;++unsafe) {
        setup_earned(cpu,1);test_lab_option="secretlab2a_cp3";test_lab_earned_option="off";
        checkpoint_reset();psx_mod_write_byte(PLAY+12,4);
        if(unsafe==0)pause_owner=0;if(unsafe==1)zero_projected=1;
        if(unsafe==2)p2.body[5]=7;if(unsafe==3)life.status[1]=MMX6_COOP_FALLEN;
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !checkpoint_test_taint &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body));
    }
    setup_earned(cpu,1);test_lab_option="secretlab2a_cp3";test_lab_earned_option="off";checkpoint_reset();
    checkpoint_lab_state=CHECKPOINT_LAB_CONSUMED;
    CHECK(!checkpoint_request(17,0,3,0x4C463932u,CHECKPOINT_AGREED) && !checkpoint_pending.phase &&
        psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_UNKNOWN);
    test_lab_option="off";test_lab_earned_option="off";equipment_probe=0;failed=0;checkpoint_reset();
}

static void earned_pending(CPUState *cpu,int online,unsigned campaign) {
    setup_earned(cpu,online);psx_mod_write_byte(PLAY+0x60,(uint8_t)campaign);
    CHECK(checkpoint_lab_boundary(cpu,6) && checkpoint_pending.phase==1 && psx_mod_read_byte(PLAY)==8);
    CHECK(!equipment_calls && !checkpoint_earned_weapons_applied && psx_mod_read_byte(PLAY+0x60)==campaign);
    mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);psx_mod_write_byte(PLAY,10);
    CHECK(checkpoint_pending.phase==2 && !equipment_calls && !psx_mod_read_byte(PLAYER+0xC9) && !p2.body[0xC9]);
}
/* Fixed original record only; external native completion is modeled, not boss gameplay. */
static void agreed_wolfang_boundary(CPUState *cpu) {
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";
    test_lab_contact_option=test_lab_fatal_option="off";
    for(int online=0;online<=1;++online)for(unsigned earned=0;earned<=1;++earned) {
        setup_earned(cpu,online);test_lab_option="refight_wolfang_cp3";
        test_lab_earned_option=earned?"all":"off";checkpoint_reset();
        CHECK(!failed && checkpoint_lab_option==21 && checkpoint_lab_index()==62 &&
            checkpoint_lab_nonce()==0x4C574633u && checkpoint_source(&checkpoint_inventory[62]));
        psx_mod_write_byte(PLAY+0x60,0x40);psx_mod_write_byte(PLAYER+0xC8,3);p2.body[0xC8]=5;
        psx_mod_write_half(PLAYER+0xB2,288);p2.body[0xB2]=240;p2.body[0xB3]=0;
        uint8_t primary[sizeof p2.body];capture(PLAYER,primary,sizeof primary);PlayerContext zero=p2;
        CHECK(checkpoint_lab_boundary(cpu,6) && checkpoint_pending.index==62 &&
            checkpoint_pending.nonce==0x4C574633u && !equipment_calls && !checkpoint_earned_weapons_applied);
        CHECK(psx_mod_read_byte(PLAY)==8 && psx_mod_read_byte(PLAY+12)==12 && !psx_mod_read_byte(PLAY+13));
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(checkpoint_pending.phase==2 && psx_mod_read_byte(PLAY+0x1D)==3 &&
            psx_mod_read_word(diagnostic+0xB8)==0x800729C0u && !equipment_calls && !guest_calls);
        CHECK(!memcmp(&zero,&p2,sizeof zero));uint8_t unchanged[sizeof p2.body];capture(PLAYER,unchanged,sizeof unchanged);
        CHECK(!memcmp(primary,unchanged,sizeof primary)); /* No custom placement or body initialization. */
        psx_mod_write_byte(PLAY,10);
        if(earned) {
            /* Native damage after CP3 entry: display/history may lag actual HP. */
            psx_mod_write_byte(PLAYER+0x5C,28);psx_mod_write_byte(PLAYER+0x5D,26);
            p2.body[0x5C]=24;p2.body[0x5D]=25;
        }
        capture(PLAYER,primary,sizeof primary);zero=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_lab_completed());
        primary[0xC9]=zero.body[0xC9]=(uint8_t)(255*earned);capture(PLAYER,unchanged,sizeof unchanged);
        CHECK(!memcmp(primary,unchanged,sizeof primary) && !memcmp(&zero,&p2,sizeof zero));
        CHECK(equipment_calls==2*earned && checkpoint_earned_weapons_applied==earned &&
            psx_mod_read_byte(PLAYER+0xC9)==255*earned && p2.body[0xC9]==255*earned);
        CHECK(psx_mod_read_byte(PLAY+0x60)==0x40 && psx_mod_read_byte(PLAYER+0x5C)==(earned?28:32) &&
            p2.body[0x5C]==(earned?24:32) && psx_mod_read_byte(PLAYER+0x5E)==32 && p2.body[0x5E]==32 &&
            psx_mod_read_byte(PLAY+0x5B)==32 && psx_mod_read_byte(PLAY+0x5C)==32 && psx_mod_read_byte(PLAYER+0xC8)==3 && p2.body[0xC8]==5 &&
            psx_mod_read_half(PLAYER+0xB2)==288 && p2.body[0xB2]==240 && !p2.body[0xB3]);
        CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX && !state_track.count && !state_track.error);
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6) && !checkpoint_stage_boundary(cpu));
        CHECK(equipment_calls==2*earned);
    }
    for(unsigned bad=0;bad<4;++bad) {
        setup_earned(cpu,1);test_lab_option="refight_wolfang_cp3";checkpoint_reset();
        checkpoint_lab_state=CHECKPOINT_LAB_CONSUMED;
        if(bad==0)psx_mod_write_byte(0x800729C0u,psx_mod_read_byte(0x800729C0u)^1u);
        if(bad==1)test_lab_profile.qualification[0]^=1;
        if(bad==3)psx_mod_write_byte(0x8003D718u,0);
        CHECK(!checkpoint_request(12,0,3,0x4C574633u^(bad==2),CHECKPOINT_AGREED));
        CHECK(!checkpoint_pending.phase && !equipment_calls && !guest_calls &&
            psx_mod_read_byte(PLAY)==10 && !psx_mod_read_byte(diagnostic+0xBC));
        CHECK(psx_mod_read_byte(diagnostic+0xA9)==(bad==1?CHECKPOINT_FORBIDDEN:bad==2?CHECKPOINT_UNKNOWN:CHECKPOINT_SOURCE));
    }
    setup_earned(cpu,0);test_lab_option="refight_wolfang_cp3";checkpoint_reset();
    CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);psx_mod_write_byte(0x800729C0u,0);
    checkpoint_native_entry(cpu,0x8001E1BCu);
    CHECK(!checkpoint_pending.phase && !psx_mod_read_byte(PLAY+0x1D) && !equipment_calls &&
        psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE);
    for(unsigned seat=0;seat<2;++seat) {
        test_lab_earned_option="off";test_lab_hp_option[0]=test_lab_hp_option[1]="off";
        setup_agreed(cpu,0);test_lab_option="refight_wolfang_cp3";test_lab_hp_option[seat]="15";checkpoint_reset();
        CHECK(failed && !checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !guest_calls);
    }
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";test_lab_earned_option="off";
    test_lab_option="off";failed=0;equipment_probe=0;checkpoint_reset();
}
/* F130: original CP6 constructor precedes the existing one-shot grant. */
static void agreed_ground_boundary(CPUState *cpu) {
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";
    test_lab_contact_option=test_lab_fatal_option="off";
    for(int online=0;online<=1;++online)for(unsigned earned=0;earned<=1;++earned) {
        setup_earned(cpu,online);test_lab_option="refight_ground_cp6";
        test_lab_earned_option=earned?"all":"off";checkpoint_reset();
        CHECK(!failed && checkpoint_lab_option==23 && checkpoint_lab_index()==65 &&
            checkpoint_lab_nonce()==0x4C475236u && checkpoint_source(&checkpoint_inventory[65]));
        psx_mod_write_byte(PLAY+0x60,0x40);psx_mod_write_byte(PLAYER+0xC8,3);p2.body[0xC8]=5;
        psx_mod_write_half(PLAYER+0xB2,288);p2.body[0xB2]=240;p2.body[0xB3]=0;
        uint8_t primary[sizeof p2.body];capture(PLAYER,primary,sizeof primary);PlayerContext zero=p2;
        CHECK(checkpoint_lab_boundary(cpu,6) && checkpoint_pending.index==65 &&
            checkpoint_pending.nonce==0x4C475236u && !equipment_calls && !checkpoint_earned_weapons_applied);
        CHECK(psx_mod_read_byte(PLAY)==8 && psx_mod_read_byte(PLAY+12)==12 && !psx_mod_read_byte(PLAY+13));
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(checkpoint_pending.phase==2 && psx_mod_read_byte(PLAY+0x1D)==6 &&
            psx_mod_read_word(diagnostic+0xB8)==0x80072A2Cu && !equipment_calls && !guest_calls);
        CHECK(!memcmp(&zero,&p2,sizeof zero));uint8_t unchanged[sizeof p2.body];capture(PLAYER,unchanged,sizeof unchanged);
        CHECK(!memcmp(primary,unchanged,sizeof primary)); /* No custom placement or body initialization. */
        psx_mod_write_byte(PLAY,10);
        if(earned) {
            /* Native damage after CP6 entry: display/history may lag actual HP. */
            psx_mod_write_byte(PLAYER+0x5C,28);psx_mod_write_byte(PLAYER+0x5D,26);
            p2.body[0x5C]=24;p2.body[0x5D]=25;
        }
        capture(PLAYER,primary,sizeof primary);zero=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_lab_completed());
        primary[0xC9]=zero.body[0xC9]=(uint8_t)(255*earned);capture(PLAYER,unchanged,sizeof unchanged);
        CHECK(!memcmp(primary,unchanged,sizeof primary) && !memcmp(&zero,&p2,sizeof zero));
        CHECK(equipment_calls==2*earned && checkpoint_earned_weapons_applied==earned &&
            psx_mod_read_byte(PLAYER+0xC9)==255*earned && p2.body[0xC9]==255*earned);
        CHECK(psx_mod_read_byte(PLAY+0x60)==0x40 && psx_mod_read_byte(PLAYER+0x5C)==(earned?28:32) &&
            p2.body[0x5C]==(earned?24:32) && psx_mod_read_byte(PLAYER+0x5E)==32 && p2.body[0x5E]==32 &&
            psx_mod_read_byte(PLAY+0x5B)==32 && psx_mod_read_byte(PLAY+0x5C)==32 && psx_mod_read_byte(PLAYER+0xC8)==3 && p2.body[0xC8]==5 &&
            psx_mod_read_half(PLAYER+0xB2)==288 && p2.body[0xB2]==240 && !p2.body[0xB3]);
        CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX && !state_track.count && !state_track.error);
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6) && !checkpoint_stage_boundary(cpu));
        CHECK(equipment_calls==2*earned);
        enter_zero();CHECK(psx_mod_read_byte(PLAY+0x60)==0x40u);leave_zero();
        CHECK(psx_mod_read_byte(PLAY+0x60)==0x40u);
        /* A later native constructor may clear flags; this option never
         * regrants across a route or reuses its consumed equipment receipt. */
        psx_mod_write_byte(PLAYER+0xC9,0);p2.body[0xC9]=0;
        psx_mod_write_byte(PLAY+0x1D,1);
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_lab_boundary(cpu,0) &&
            !checkpoint_lab_boundary(cpu,6) && equipment_calls==2*earned &&
            !psx_mod_read_byte(PLAYER+0xC9) && !p2.body[0xC9]);
    }
    for(unsigned bad=0;bad<4;++bad) {
        setup_earned(cpu,1);test_lab_option="refight_ground_cp6";checkpoint_reset();
        checkpoint_lab_state=CHECKPOINT_LAB_CONSUMED;
        if(bad==0)psx_mod_write_byte(0x80072A2Cu,psx_mod_read_byte(0x80072A2Cu)^1u);
        if(bad==1)test_lab_profile.qualification[0]^=1;
        if(bad==3)psx_mod_write_byte(0x8003D718u,0);
        CHECK(!checkpoint_request(12,0,6,0x4C475236u^(bad==2),CHECKPOINT_AGREED));
        CHECK(!checkpoint_pending.phase && !equipment_calls && !guest_calls &&
            psx_mod_read_byte(PLAY)==10 && !psx_mod_read_byte(diagnostic+0xBC));
        CHECK(psx_mod_read_byte(diagnostic+0xA9)==(bad==1?CHECKPOINT_FORBIDDEN:bad==2?CHECKPOINT_UNKNOWN:CHECKPOINT_SOURCE));
    }
    /* Keep the new option at the ordinary fresh-intro origin only. */
    for(unsigned bad=0;bad<3;++bad) {
        setup_earned(cpu,1);test_lab_option="refight_ground_cp6";checkpoint_reset();
        if(bad==0)psx_mod_write_byte(PLAY+12,4);
        if(bad==1)psx_mod_write_byte(PLAY+13,1);
        if(bad==2)psx_mod_write_byte(PLAY+0x1D,1);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase &&
            !equipment_calls && !guest_calls && !checkpoint_test_taint &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_ORDER &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body));
    }
    for(unsigned unsafe=0;unsafe<4;++unsafe) {
        setup_earned(cpu,1);test_lab_option="refight_ground_cp6";checkpoint_reset();
        if(unsafe==0)pause_owner=0;if(unsafe==1)zero_projected=1;
        if(unsafe==2)p2.body[5]=7;if(unsafe==3)life.status[1]=MMX6_COOP_FALLEN;
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase &&
            !equipment_calls && !guest_calls && !checkpoint_test_taint &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body));
    }
    setup_earned(cpu,0);test_lab_option="refight_ground_cp6";checkpoint_reset();
    CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);psx_mod_write_byte(0x80072A2Cu,0);
    checkpoint_native_entry(cpu,0x8001E1BCu);
    CHECK(!checkpoint_pending.phase && !psx_mod_read_byte(PLAY+0x1D) && !equipment_calls &&
        psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE);
    for(unsigned seat=0;seat<2;++seat) {
        test_lab_earned_option="off";test_lab_hp_option[0]=test_lab_hp_option[1]="off";
        setup_agreed(cpu,0);test_lab_option="refight_ground_cp6";test_lab_hp_option[seat]="15";checkpoint_reset();
        CHECK(failed && !checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !guest_calls);
    }
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";test_lab_earned_option="off";
    test_lab_option="off";failed=0;equipment_probe=0;checkpoint_reset();
}
static void agreed_earned_weapons(CPUState *cpu) {
    CHECK(!checkpoint_earned_weapons_option && !checkpoint_earned_weapons_applied);
    for(int online=0;online<=1;++online)for(unsigned variant=0;variant<2;++variant) {
        unsigned campaign=variant?0x40u:0u;earned_pending(cpu,online,campaign);
        uint8_t primary[sizeof p2.body];capture(PLAYER,primary,sizeof primary);PlayerContext zero=p2;CPUState registers=*cpu;
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE);
        CHECK(equipment_calls==2 && checkpoint_earned_weapons_applied && !checkpoint_earned_weapons_reason);
        CHECK(psx_mod_read_byte(PLAY+0x60)==campaign && psx_mod_read_byte(PLAYER+0xC9)==255 && p2.body[0xC9]==255);
        primary[0xC9]=zero.body[0xC9]=255;
        uint8_t after[sizeof primary];capture(PLAYER,after,sizeof after);
        CHECK(!memcmp(primary,after,sizeof after) && !memcmp(&zero,&p2,sizeof zero) && !memcmp(&registers,cpu,sizeof registers));
        CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        /* A subsequent real projection must capture restored campaign state,
         * not consume the previous native grant's stale saved_play backup. */
        enter_zero();CHECK(psx_mod_read_byte(PLAY+0x60)==campaign);leave_zero();
        CHECK(psx_mod_read_byte(PLAY+0x60)==campaign && p2.body[0xC9]==255);
        diagnostics(0);CHECK(psx_mod_read_word(diagnostic+0xC4)==0x00030101u);
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6) && equipment_calls==2);
#ifdef MMX6_COOP_MODERN_STATE
        HostState saved;state_capture(&saved);CHECK(saved.earned_applied==1 && saved.earned_reason==0);
        uint8_t encoded[65536];StateIO write={STATE_WRITE,1,encoded,NULL,sizeof encoded,0,0};state_core(&write,&saved);CHECK(write.ok);
        HostState loaded={0};StateIO read={STATE_READ,1,NULL,encoded,write.pos,0,0};state_core(&read,&loaded);CHECK(read.ok && loaded.earned_applied==1);
        checkpoint_earned_weapons_applied=0;state_commit(&loaded);CHECK(checkpoint_earned_weapons_applied==1);
        loaded.earned_applied=2;write=(StateIO){STATE_COUNT,1,NULL,NULL,0,0,0};state_core(&write,&loaded);CHECK(!write.ok);
#endif
        p2.body[0xC9]=0;checkpoint_complete(cpu);CHECK(!p2.body[0xC9] && equipment_calls==2);
        checkpoint_reset();CHECK(!checkpoint_earned_weapons_applied && !checkpoint_earned_weapons_reason);
    }
    for(unsigned bad=0;bad<11;++bad) {
        earned_pending(cpu,1,0x40u);
        if(bad==0)test_lab_ready=0;
        if(bad==1)psx_mod_write_byte(0x8003D718u,psx_mod_read_byte(0x8003D718u)^1);
        if(bad==2)psx_mod_write_byte(PLAYER+0xE7,2);
        if(bad==3)p2.body[0xE7]=1;
        if(bad==4)psx_mod_write_byte(PLAY+0x5E,2);
        if(bad==5)cpu->gpr[29]=0;if(bad==6)cpu->gpr[29]|=1;
        if(bad==7)p2.body[0x70]=0;if(bad==8)enrolled=0;
        if(bad==9)p2.body[0x5E]=31;if(bad==10)p2.body[5]=0;
        CHECK(!checkpoint_stage_boundary(cpu) && !equipment_calls && !checkpoint_earned_weapons_applied);
        CHECK(psx_mod_read_byte(PLAY+0x60)==0x40u && !psx_mod_read_byte(PLAYER+0xC9) && !p2.body[0xC9]);
    }
    for(unsigned seat=0;seat<2;++seat)for(unsigned bad=0;bad<6;++bad) {
        earned_pending(cpu,1,0x40u);
        if(bad<2) {if(seat)p2.body[0x5C]=(uint8_t)(bad?0x80:0);else psx_mod_write_byte(PLAYER+0x5C,(uint8_t)(bad?0x80:0));}
        if(bad==2)life.status[seat]=MMX6_COOP_DYING;
        if(bad==3)life.status[seat]=MMX6_COOP_JOINING;
        if(bad>=4) {if(seat)p2.body[0x5D]=(uint8_t)(bad==4?0:0x80);else psx_mod_write_byte(PLAYER+0x5D,(uint8_t)(bad==4?0:0x80));}
        uint8_t health[6]={psx_mod_read_byte(PLAYER+0x5C),psx_mod_read_byte(PLAYER+0x5D),psx_mod_read_byte(PLAYER+0x5E),p2.body[0x5C],p2.body[0x5D],p2.body[0x5E]};
        CHECK(!checkpoint_stage_boundary(cpu) && !equipment_calls && !checkpoint_earned_weapons_applied);
        CHECK(psx_mod_read_byte(PLAYER+0x5C)==health[0] && psx_mod_read_byte(PLAYER+0x5D)==health[1] &&
            psx_mod_read_byte(PLAYER+0x5E)==health[2] && p2.body[0x5C]==health[3] &&
            p2.body[0x5D]==health[4] && p2.body[0x5E]==health[5]);
    }
    /* Either HP seed keeps BOTH heroes' original full-health admission,
     * including the unseeded companion, before either factory can run. */
    for(unsigned seeded=0;seeded<2;++seeded)for(unsigned damaged=0;damaged<2;++damaged) {
        test_lab_hp_option[0]=test_lab_hp_option[1]="off";test_lab_hp_option[seeded]="17";
        earned_pending(cpu,1,0x40u);
        if(damaged)p2.body[0x5C]=24;else psx_mod_write_byte(PLAYER+0x5C,28);
        CHECK(!checkpoint_stage_boundary(cpu) && !equipment_calls && !checkpoint_earned_weapons_applied &&
            !checkpoint_starting_hp_applied && checkpoint_pending.phase==2);
        CHECK(psx_mod_read_byte(PLAYER+0x5C)==(damaged?32:28) && p2.body[0x5C]==(damaged?24:32));
    }
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";
    /* Grant before HP seed: native technique/resources/capacities survive,
     * and the independent explicitly selected starting HP is applied once. */
    test_lab_hp_option[0]="17";test_lab_hp_option[1]="23";earned_pending(cpu,1,0x40u);
    CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_earned_weapons_applied && checkpoint_starting_hp_applied && equipment_calls==2);
    CHECK(psx_mod_read_byte(PLAYER+0x5C)==17 && p2.body[0x5C]==23 &&
          psx_mod_read_byte(PLAYER+0x5D)==32 && p2.body[0x5D]==32 &&
          psx_mod_read_byte(PLAY+0x60)==0x40u && psx_mod_read_byte(PLAYER+0xC9)==255 && p2.body[0xC9]==255);
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";
    test_lab_earned_option="invalid";setup_agreed(cpu,1);CHECK(failed && !checkpoint_earned_weapons_option);
    test_lab_option="off";test_lab_earned_option="all";checkpoint_reset();CHECK(failed && !checkpoint_lab_option);
    setup_earned(cpu,1);psx_mod_write_byte(diagnostic+0x51,255);psx_mod_write_byte(diagnostic+0x50,9);
    diagnostic_inventory_setup(cpu);CHECK(!equipment_calls && !checkpoint_earned_weapons_applied && !psx_mod_read_byte(PLAY+0x60));
    equipment_probe=0;test_lab_earned_option="off";setup_agreed(cpu,1);
    CHECK(!checkpoint_earned_weapons_option && !checkpoint_earned_weapons_applied);
}
static void apply_protected_checkpoint(CPUState *cpu,int online) {
    test_lab_contact_option="on";setup_agreed(cpu,online);
    CHECK(checkpoint_contact_protection_option==1 && !checkpoint_contact_protection_mask());
    CHECK(checkpoint_contact_protection_status()==1); /* Selected != applied. */
    CHECK(checkpoint_lab_boundary(cpu,6) && !checkpoint_contact_protection_mask());
    mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
    CHECK(!checkpoint_contact_protection_mask());
    psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu));
    CHECK(checkpoint_contact_protection_mask()==3 && checkpoint_contact_protection_status()==15);
}
static void protected_contact_unchanged(CPUState *cpu,unsigned resident) {
    psx_mod_write_byte(PLAYER+2,(uint8_t)resident);
    memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
    uint8_t published[sizeof test_diagnostic];memcpy(published,test_diagnostic,sizeof published);
    CPUState expected=*cpu;expected.gpr[2]=0;unsigned calls=guest_calls;
    CHECK(player_contact(cpu,0x80030ECCu)==1 && !memcmp(cpu,&expected,sizeof expected));
    CHECK(guest_calls==calls && !memcmp(before_ram,test_ram,sizeof test_ram) &&
        !memcmp(&partner,&p2,sizeof partner) && !memcmp(published,test_diagnostic,sizeof published));
}
static void agreed_contact_protection(CPUState *cpu) {
    test_lab_contact_option="off";setup_agreed(cpu,1);
    CHECK(!checkpoint_contact_protection_option && !checkpoint_contact_protection_status());
    inside=1;cpu->gpr[2]=77;CHECK(!player_contact(cpu,0x80030ECCu) && cpu->gpr[2]==77);inside=0;
    CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
    psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu));
    CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && !checkpoint_contact_protection_mask());
    test_lab_contact_option="invalid";setup_agreed(cpu,1);
    CHECK(failed && !checkpoint_contact_protection_option && !checkpoint_contact_protection_mask());
    for(int online=0;online<=1;++online) {
        apply_protected_checkpoint(cpu,online);protected_contact_unchanged(cpu,0);
        /* P1 protection does not disappear with the guest's native transport
         * body or voluntary absence. No lifecycle transition is fabricated. */
        for(unsigned status=MMX6_COOP_ALIVE;status<=MMX6_COOP_FALLEN;++status) {
            life.status[1]=(Mmx6CoopStatus)status;
            unsigned present=status==MMX6_COOP_ALIVE || status==MMX6_COOP_LEAVING || status==MMX6_COOP_JOINING;
            CHECK(checkpoint_contact_protection_mask()==(present?3u:1u));
            protected_contact_unchanged(cpu,0);
            if(present) {
                inside=player_call=stage_call=zero_projected=1;
                protected_contact_unchanged(cpu,1);
                inside=player_call=stage_call=zero_projected=0;
            }
        }
        life.status[1]=MMX6_COOP_ALIVE;
        life.status[0]=MMX6_COOP_FALLEN;CHECK(checkpoint_contact_protection_mask()==2);
        zero_world=zero_projected=1;protected_contact_unchanged(cpu,1);zero_world=zero_projected=0;
        life.status[0]=MMX6_COOP_ALIVE;
        /* The contact-only branch must not intercept enemy damage or terrain,
         * nor accept an address different from the registered30ECC contract. */
        inside=1;cpu->gpr[2]=77;
        CHECK(!enemy_hit(cpu,0x80031474u) && !solid_player_collision(cpu,0x80031DA8u));
        CHECK(!player_contact(cpu,0x80031474u) && cpu->gpr[2]==77);inside=0;
        for(unsigned bad=0;bad<18;++bad) {
            apply_protected_checkpoint(cpu,online);
            if(bad==0)checkpoint_contact_protection_option=0;
            if(bad==1)checkpoint_lab_state=CHECKPOINT_LAB_ARMED;
            if(bad==2)checkpoint_pending.phase=1;
            if(bad==3)psx_mod_write_byte(diagnostic+0xA8,CHECKPOINT_FAILED);
            if(bad==4)psx_mod_write_byte(diagnostic+0xBD,CHECKPOINT_OFFLINE);
            if(bad==5)psx_mod_write_byte(diagnostic+0xBC,0);
            if(bad==6)psx_mod_write_word(diagnostic+0xB0,1);
            if(bad==7)psx_mod_write_word(diagnostic+0xB4,2);
            if(bad==8)psx_mod_write_byte(PLAY+0x1D,0);
            if(bad==9)psx_mod_write_byte(PLAY+12,1);
            if(bad==10)scene_owner=1;
            if(bad==11)clear_phase=1;
            if(bad==12)pause_owner=0;
            if(bad==13)private_draw=1;
            if(bad==14)view_call=1;
            if(bad==15)psx_mod_write_byte(PLAY,12);
            if(bad==16)enrolled=0;
            if(bad==17)failed=1;
            CHECK(!checkpoint_contact_protection_mask());
            /* Reset synthetic test-only guards before the next initializer. */
            checkpoint_pending.phase=0;scene_owner=clear_phase=private_draw=view_call=0;pause_owner=-1;
        }
        apply_protected_checkpoint(cpu,online);
        diagnostics(0);CHECK(psx_mod_read_byte(diagnostic+0xAF)==15);
        life.status[1]=MMX6_COOP_ABSENT;diagnostics(0);CHECK(psx_mod_read_byte(diagnostic+0xAF)==7);
        if(online) {
            test_lab_profile.qualification[0]^=1;CHECK(!checkpoint_contact_protection_mask());
            inside=1;cpu->gpr[2]=77;CHECK(!player_contact(cpu,0x80030ECCu) && cpu->gpr[2]==77);inside=0;
        }
    }
    test_lab_contact_option="on";setup_agreed(cpu,1);
    psx_mod_write_byte(0x80030ECCu,psx_mod_read_byte(0x80030ECCu)^1);
    CHECK(!checkpoint_lab_boundary(cpu,6) && psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE);
    CHECK(!checkpoint_contact_protection_mask());
    setup_agreed(cpu,1);CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);
    psx_mod_write_byte(0x80030FB4u,psx_mod_read_byte(0x80030FB4u)^1);
    checkpoint_native_entry(cpu,0x8001E1BCu);
    CHECK(!checkpoint_pending.phase && psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE &&
        !checkpoint_contact_protection_mask());
    /* An ordinary offline mailbox initializer is not negotiated authority,
     * even if the protection option was selected before launch. */
    setup_agreed(cpu,0);psx_mod_write_byte(diagnostic+0x50,8);
    CHECK(checkpoint_stage_boundary(cpu));mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
    psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu));
    CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && !checkpoint_contact_protection_mask());
    test_lab_contact_option="off";setup_agreed(cpu,1);checkpoint_reset();
    CHECK(!checkpoint_contact_protection_option && !checkpoint_contact_protection_status());
}
static void agreed_checkpoint_boundary(CPUState *cpu) {
    const Mmx6Checkpoint *entry=&checkpoint_inventory[2];
    CHECK(entry->stage==0 && entry->section==0 && entry->checkpoint==2 && entry->campaign==1 &&
        entry->table==0x80073134u && entry->record==0x80072150u && entry->hash==0x9CF23C0Au);
    /* Configured destination alone must never race the parent's normal intro
     * P2-walk/P1-jump baseline. Only a fresh accepted native chord arms it. */
    setup_agreed(cpu,1);CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_pending.phase && !checkpoint_lab_state);
    CHECK(!checkpoint_lab_boundary(cpu,2) && !checkpoint_lab_boundary(cpu,4) && !checkpoint_lab_boundary(cpu,7) && !checkpoint_lab_state);
    checkpoint_lab_option=0;memcpy(before_ram,test_ram,sizeof test_ram);
    CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_lab_state && !memcmp(before_ram,test_ram,sizeof test_ram));
    for(int online=0;online<=1;++online)for(unsigned loaded=0;loaded<=1;++loaded) {
        setup_agreed(cpu,online);
        if(loaded) {
            /* Model native card Load: Recycle CP0, Zero/P1 and acquired X/P2.
             * The checkpoint request must retain both bodies and card fields. */
            psx_mod_write_byte(PLAY+12,4);psx_mod_write_byte(PLAYER+2,1);p2.body[2]=0;
        }
        PlayerContext body=p2;memcpy(before_ram,test_ram,sizeof test_ram);
        pause_owner=1;CHECK(!checkpoint_lab_boundary(cpu,6));
        CHECK(checkpoint_lab_state==CHECKPOINT_LAB_ARMED && !checkpoint_pending.phase && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram));
        CHECK(psx_mod_read_byte(diagnostic+0xBE)==1);
        CHECK(!checkpoint_lab_boundary(cpu,0) && checkpoint_lab_state==CHECKPOINT_LAB_ARMED);
        pause_owner=-1;p2.body[5]=7;CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_pending.phase);
        p2.body[5]=2;psx_mod_write_byte(PLAYER+0x5C,0);
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_pending.phase);
        psx_mod_write_byte(PLAYER+0x5C,32);p2.body[0x5C]=0;
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_pending.phase);
        p2.body[0x5C]=32;psx_mod_write_byte(PLAYER+0x70,0);
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_pending.phase);
        psx_mod_write_byte(PLAYER+0x70,8);p2.body[0x70]=0;
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_pending.phase);
        p2.body[0x70]=8;CHECK(checkpoint_lab_boundary(cpu,0));
        before_ram[PLAY&0x1FFFFF]=8;before_ram[(PLAY+12)&0x1FFFFF]=0;
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
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
        CHECK(psx_mod_read_word(diagnostic+0xA4)==1 && checkpoint_lab_state==CHECKPOINT_LAB_CONSUMED);
    }
    /* Identical selected profile is a prerequisite, never inferred from
     * active netplay, a version string or the compile-time lab flag. */
    for(unsigned wrong=0;wrong<7;++wrong)for(unsigned loaded=0;loaded<=1;++loaded) {
        setup_agreed(cpu,1);if(loaded)psx_mod_write_byte(PLAY+12,4);
        memcpy(before_ram,test_ram,sizeof test_ram);
        if(wrong==0)test_lab_ready=0;if(wrong==1)test_lab_failed=1;
        if(wrong==2)test_lab_selected=0;if(wrong==3)test_lab_profile.profile[0]^=1;
        if(wrong==4)++test_lab_profile.revision;if(wrong==5)test_lab_profile.flags=0;
        if(wrong==6)test_lab_profile.qualification[0]^=1;
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !checkpoint_test_taint);
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_REJECTED && psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_FORBIDDEN);
    }
    for(unsigned loaded=0;loaded<=1;++loaded) {
        setup_agreed(cpu,1);if(loaded)psx_mod_write_byte(PLAY+12,4);
        psx_mod_write_byte(checkpoint_code[0].first,0);
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !checkpoint_test_taint);
        CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE);
    }
    setup_agreed(cpu,1);CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);test_lab_ready=0;
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
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_pending.phase);
        CHECK(checkpoint_lab_boundary(cpu,6));
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
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
        CHECK(psx_mod_read_word(diagnostic+0xA4)==1);
        if(online) {
            setup_agreed(cpu,1);test_lab_option="amazon_cp0";checkpoint_reset();
            psx_mod_write_byte(diagnostic+0x50,8);rejected_checkpoint(cpu,CHECKPOINT_FORBIDDEN);
        }
    }
    setup_agreed(cpu,1);test_lab_option="amazon_cp0";checkpoint_reset();test_lab_ready=0;
    memcpy(before_ram,test_ram,sizeof test_ram);
    CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !checkpoint_test_taint &&
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
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_pending.phase);
        CHECK(checkpoint_lab_boundary(cpu,6));
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
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
        CHECK(psx_mod_read_word(diagnostic+0xA4)==1);
        if(online) {
            setup_agreed(cpu,1);test_lab_option="amazon_cp2";checkpoint_reset();
            psx_mod_write_byte(diagnostic+0x50,8);rejected_checkpoint(cpu,CHECKPOINT_FORBIDDEN);
        }
    }
    setup_agreed(cpu,1);test_lab_option="amazon_cp2";checkpoint_reset();test_lab_ready=0;
    memcpy(before_ram,test_ram,sizeof test_ram);
    CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !checkpoint_test_taint &&
        !memcmp(before_ram,test_ram,sizeof test_ram));
    CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_FORBIDDEN);
    test_lab_option="off";checkpoint_reset();
}
static void agreed_recycle_boundary(CPUState *cpu) {
    const Mmx6Checkpoint *entry=&checkpoint_inventory[27];
    CHECK(entry->stage==4 && entry->section==1 && entry->checkpoint==2 && entry->campaign==1 &&
        entry->table==0x80073198u && entry->record==0x800724D4u && entry->hash==0x6F78ABDCu);
    for(int online=0;online<=1;++online)for(unsigned protection=0;protection<=1;++protection)
    for(unsigned loaded=0;loaded<=1;++loaded) {
        test_lab_contact_option=protection?"on":"off";setup_agreed(cpu,online);
        test_lab_option="recycle_cp2";checkpoint_reset();
        psx_mod_write_byte(PLAY+12,loaded?4:0); /* Model real native mission arrival only. */
        CHECK(checkpoint_lab_option==6 && checkpoint_lab_index()==27 &&
            checkpoint_lab_nonce()==CHECKPOINT_LAB_RECYCLE_NONCE &&
            checkpoint_lab_nonce()==0x4C435232u && checkpoint_source(entry));
        /* Destination/nonce cannot be mixed with an existing agreed choice. */
        checkpoint_lab_state=CHECKPOINT_LAB_CONSUMED;
        CHECK(!checkpoint_request(4,1,2,CHECKPOINT_LAB_INVESTIGATOR_NONCE,CHECKPOINT_AGREED));
        CHECK(!checkpoint_request(1,0,2,CHECKPOINT_LAB_RECYCLE_NONCE,CHECKPOINT_AGREED));
        CHECK(!checkpoint_pending.phase && !checkpoint_test_taint && !guest_calls &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_UNKNOWN);
        checkpoint_reset();memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(!checkpoint_lab_boundary(cpu,0));
        pause_owner=0;CHECK(!checkpoint_lab_boundary(cpu,6) && checkpoint_lab_state==CHECKPOINT_LAB_ARMED);
        CHECK(!checkpoint_pending.phase && !guest_calls && !memcmp(before_ram,test_ram,sizeof test_ram));
        pause_owner=-1;CHECK(checkpoint_lab_boundary(cpu,0));
        before_ram[PLAY&0x1FFFFF]=8;before_ram[(PLAY+12)&0x1FFFFF]=4;before_ram[(PLAY+13)&0x1FFFFF]=1;
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body) && !guest_calls);
        CHECK(checkpoint_pending.phase==1 && checkpoint_pending.index==27 &&
            checkpoint_pending.authority==CHECKPOINT_AGREED && checkpoint_pending.nonce==0x4C435232u &&
            psx_mod_read_word(diagnostic+0xB8)==0x800724D4u &&
            psx_mod_read_byte(diagnostic+0xBC)==1 && psx_mod_read_byte(diagnostic+0xBD)==1 &&
            psx_mod_read_byte(diagnostic+0xBE)==2 && checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        mode9(cpu);memcpy(before_ram,test_ram,sizeof test_ram);CPUState saved=*cpu;
        checkpoint_native_entry(cpu,0x8001E1BCu);before_ram[(PLAY+0x1D)&0x1FFFFF]=2;
        CHECK(checkpoint_pending.phase==2 && psx_mod_read_word(diagnostic+0xB4)==1 &&
            !memcmp(&saved,cpu,sizeof saved) && !memcmp(before_ram,test_ram,sizeof test_ram) &&
            !memcmp(&body,&p2,sizeof body) && !guest_calls);
        /* Original mode9 dispatch owns5920/326, camera and natural landing.
         * This plain fixture never places, scans or manufactures grounded readiness. */
        psx_mod_write_byte(PLAY,10);memcpy(before_ram,test_ram,sizeof test_ram);
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase &&
            psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE &&
            !psx_mod_read_byte(diagnostic+0xAD) && !psx_mod_read_byte(diagnostic+0xAE) &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body) && !guest_calls);
        CHECK(checkpoint_contact_protection_status()==(protection?15u:0u));
        psx_mod_write_byte(PLAY+0x1D,0); /* Model a later ordinary native retry. */
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6) &&
            psx_mod_read_word(diagnostic+0xA4)==1 && psx_mod_read_word(diagnostic+0xB4)==1);
    }
    test_lab_contact_option="off";
    /* The exact Recycle root/table/record and native initializer are required
     * both before the request and again at the original mode9 entry. */
    const uint32_t corrupt[]={0x80073324u,0x800731A0u,0x800724D4u,0x8001E1BCu};
    for(unsigned i=0;i<sizeof corrupt/sizeof corrupt[0];++i)for(unsigned loaded=0;loaded<=1;++loaded) {
        setup_agreed(cpu,1);test_lab_option="recycle_cp2";checkpoint_reset();
        psx_mod_write_byte(PLAY+12,loaded?4:0);
        psx_mod_write_byte(corrupt[i],psx_mod_read_byte(corrupt[i])^1);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !checkpoint_test_taint &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body));
    }
    setup_agreed(cpu,1);test_lab_option="recycle_cp2";checkpoint_reset();
    CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);
    psx_mod_write_byte(0x800724D4u,psx_mod_read_byte(0x800724D4u)^1);
    checkpoint_native_entry(cpu,0x8001E1BCu);
    CHECK(!checkpoint_pending.phase && !psx_mod_read_byte(PLAY+0x1D) &&
        psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE && !guest_calls);
    setup_agreed(cpu,1);test_lab_option="recycle_cp2";checkpoint_reset();++test_lab_profile.revision;
    CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !checkpoint_test_taint &&
        psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_FORBIDDEN);
    setup_agreed(cpu,1);test_lab_option="recycle_cp2";checkpoint_reset();
    psx_mod_write_byte(diagnostic+0x50,8);rejected_checkpoint(cpu,CHECKPOINT_FORBIDDEN);
    test_lab_option="off";checkpoint_reset();CHECK(!checkpoint_lab_option && !checkpoint_lab_state);
}
static void portal_test_body(unsigned seat,unsigned x,unsigned y) {
    uint8_t body[sizeof p2.body]={0};body[0]=body[3]=body[4]=1;body[2]=(uint8_t)seat;
    body[5]=2;body[0x5C]=32;body[0x70]=8;put32(body+0x68,0x80073D50u+seat*4u);
    put32(body+8,x<<16);put32(body+0x18,x<<16);put32(body+12,y<<16);put32(body+0x1C,y<<16);
    if(seat)memcpy(p2.body,body,sizeof body);
    else for(unsigned i=0;i<sizeof body;++i)psx_mod_write_byte(PLAYER+i,body[i]);
}
static void setup_portal_prerequisite(CPUState *cpu,int online,int variant) {
    const char *options[]={"recycle_portal_cp2","recycle_distant_cp2","recycle_fallen_cp2","recycle_fallen_guest_cp2"};
    const unsigned option_numbers[]={7,10,12,13};
    const uint32_t nonces[]={0x4C525032u,0x4C525044u,0x4C524631u,0x4C524632u};
    CHECK(variant>=0 && variant<4);
    setup_agreed(cpu,online);test_lab_option=options[variant];checkpoint_reset();
    independent_views=variant==1;
    CHECK(checkpoint_lab_option==option_numbers[variant] && checkpoint_lab_index()==23 && checkpoint_lab_nonce()==nonces[variant]);
    CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
    CHECK(checkpoint_pending.phase==2 && psx_mod_read_word(diagnostic+0xB8)==0x80072444u);
    memcpy(test_ram,portal_source_ram,sizeof test_ram);
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+12,4);psx_mod_write_byte(PLAY+13,0);
    psx_mod_write_byte(PLAY+0x1D,2);psx_mod_write_word(PLAY+0x90,10);
    portal_test_body(0,480,1595);portal_test_body(1,504,1594);
    psx_mod_write_word(0x800971F8u+8,328u<<16);psx_mod_write_word(0x800971F8u+12,1424u<<16);
    const uint16_t bounds[]={1264,320,1424,1424,1264,320,1424,1424};
    for(unsigned i=0;i<8;++i)psx_mod_write_half(0x800971F8u+0x1C+i*2,bounds[i]);
    CHECK(checkpoint_portal_source());uint32_t meta,desc;
    CHECK(checkpoint_portal_assets(&meta,&desc));
    CHECK(variant>=2?checkpoint_fallen_portal_ground(meta,desc):checkpoint_portal_ground(meta,desc));
}
static void portal_test_native_ready(void) {
    portal_test_body(0,checkpoint_portal_x(0),checkpoint_portal_floor(0)-21u);portal_test_body(1,1506,1594);
    psx_mod_write_word(0x800971F8u+8,1264u<<16);psx_mod_write_word(PLAY+0x90,12);
    uint32_t a=0x8008EF48u;psx_mod_write_byte(a,1);psx_mod_write_byte(a+1,0x1C);
    psx_mod_write_byte(a+2,1);psx_mod_write_byte(a+4,1);psx_mod_write_byte(a+5,1);
    psx_mod_write_word(a+0x10,0x800F2B0Cu);psx_mod_write_word(a+8,1552u<<16);
    psx_mod_write_word(a+12,1584u<<16);psx_mod_write_word(a+0x68,0x800F38B8u);
    a=0x800C1220u;psx_mod_write_byte(a,1);psx_mod_write_byte(a+1,26);psx_mod_write_byte(a+2,4);
    psx_mod_write_byte(a+4,1);psx_mod_write_word(a+0x10,0x800F2E24u);
    psx_mod_write_word(a+8,1424u<<16);psx_mod_write_word(a+12,1604u<<16);
    a+=0xA4u;psx_mod_write_word(a,0x013B0441u);psx_mod_write_byte(a+4,1);psx_mod_write_byte(a+7,1);
    psx_mod_write_word(a+0x10,0x800F2B7Cu);psx_mod_write_word(a+8,1360u<<16);
    psx_mod_write_word(a+12,1600u<<16);psx_mod_write_word(a+0x68,0x80078910u);psx_mod_write_byte(a+0x70,8);
}
static void gate_enemy_test_vy(unsigned seat,int32_t vy) {
    if(seat)put32(p2.body+0x24,(uint32_t)vy);
    else psx_mod_write_word(PLAYER+0x24,(uint32_t)vy);
}
static void setup_gate_homing_right_prerequisite(CPUState *cpu,int online) {
    const char *protection=test_lab_contact_option;test_lab_contact_option="off";
    setup_agreed(cpu,online);test_lab_contact_option=protection;
    test_lab_option="gate_homing_right_cp4";checkpoint_reset();
    CHECK(checkpoint_lab_option==27 && checkpoint_lab_index()==98 && checkpoint_lab_nonce()==0x4C475234u);
    CHECK(checkpoint_inventory[98].stage==18 && !checkpoint_inventory[98].section && checkpoint_inventory[98].checkpoint==4 &&
        checkpoint_inventory[98].table==0x800732ACu && checkpoint_inventory[98].record==0x80072ED0u && checkpoint_inventory[98].hash==0xF191CA1Eu);
    CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
    CHECK(checkpoint_pending.phase==2 && psx_mod_read_word(diagnostic+0xB8)==0x80072ED0u);
    memcpy(test_ram,gate_enemy_source_ram,sizeof test_ram);
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+12,18);psx_mod_write_byte(PLAY+13,0);
    psx_mod_write_byte(PLAY+0x1D,4);psx_mod_write_word(PLAY+0x90,10);
    /* External original arrival observations, not simulated native physics. */
    portal_test_body(0,2992,1083);portal_test_body(1,3016,1082);
    psx_mod_write_byte(PLAYER+0x5C,23);p2.body[0x5C]=27; /* Ordinary damage is allowed. */
}
static void agreed_gate_homing_right_prerequisite(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        setup_gate_homing_right_prerequisite(cpu,online);
        p2.body[5]=0;memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;CPUState registers=*cpu;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) && !memcmp(&registers,cpu,sizeof *cpu));
        p2.body[5]=2;partner=p2;
        put32(partner.body+8,3130u<<16);put32(partner.body+0x18,3130u<<16);
        put32(partner.body+12,1082u<<16);put32(partner.body+0x1C,1082u<<16);
        uint32_t meta,desc;CHECK(checkpoint_gate_enemy_assets(&meta,&desc) && checkpoint_gate_homing_ground(meta,desc));
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 && psx_mod_read_byte(diagnostic+0xAD)==1);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) &&
            !memcmp(&registers,cpu,sizeof *cpu) && !guest_calls);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        psx_mod_write_word(PLAY+0x90,12);CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && checkpoint_lab_completed());
        CHECK(psx_mod_read_byte(diagnostic+0xAD)==2 && psx_mod_read_word(diagnostic+0xA4)==1 &&
            psx_mod_read_word(diagnostic+0xB4)==1 && psx_mod_read_word(diagnostic+0xB0)==0x4C475234u &&
            psx_mod_read_byte(PLAYER+0x5C)==23 && p2.body[0x5C]==27);
        put32(p2.body+8,3144u<<16);partner=p2;
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6) && !checkpoint_stage_boundary(cpu) &&
            !memcmp(&partner,&p2,sizeof p2)); /* Never place again after native movement/retry. */
        const uint32_t corrupt[]={0x80097438u,0x80100000u,0x80120000u,0x80073D54u};
        for(unsigned bad=0;bad<sizeof corrupt/sizeof corrupt[0];++bad) {
            setup_gate_homing_right_prerequisite(cpu,online);psx_mod_write_byte(corrupt[bad],psx_mod_read_byte(corrupt[bad])^1u);
            memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;registers=*cpu;
            CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE &&
                !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) && !memcmp(&registers,cpu,sizeof *cpu) && !guest_calls);
        }
        for(unsigned bad=0;bad<2;++bad) {
            setup_agreed(cpu,online);test_lab_option="gate_homing_right_cp4";checkpoint_reset();
            if(bad)psx_mod_write_byte(PLAY+12,4);else checkpoint_lab_state=CHECKPOINT_LAB_CONSUMED;
            memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;registers=*cpu;
            CHECK(!(bad?checkpoint_lab_boundary(cpu,6):checkpoint_request(18,0,4,0x4C474834u,CHECKPOINT_AGREED)));
            CHECK(psx_mod_read_byte(diagnostic+0xA9)==(bad?CHECKPOINT_ORDER:CHECKPOINT_UNKNOWN) && !checkpoint_pending.phase &&
                !checkpoint_test_taint && !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) && !memcmp(&registers,cpu,sizeof *cpu));
        }
    }
    test_lab_option="off";checkpoint_reset();
}
static void gate_contact_actor(void) {
    const uint32_t child=0x80093C98u,parent=child+0xA0u,boss=0x8008EF48u;
    psx_mod_write_byte(child,1);psx_mod_write_byte(child+1,26);psx_mod_write_byte(child+2,13);
    psx_mod_write_byte(child+4,1);psx_mod_write_byte(child+5,1);
    psx_mod_write_word(child+0x7C,parent);psx_mod_write_word(child+0x50,0x800F76C0u);
    psx_mod_write_byte(child+0x60,4);psx_mod_write_byte(child+0x62,0);
    /* Parent may already be inactive: native flight outlives its producer. */
    psx_mod_write_byte(parent+1,26);psx_mod_write_byte(parent+2,1);
    psx_mod_write_byte(boss,1);psx_mod_write_byte(boss+1,59);psx_mod_write_byte(boss+4,1);
    psx_mod_write_word(PLAY+0x20,boss);psx_mod_write_word(0x800F7800u,boss);
    psx_mod_write_word(SCRATCH+0x80,0x800F5F88u);psx_mod_write_word(SCRATCH+0x84,0x800F60BCu);
}
static void agreed_gate_contact_protection(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        test_lab_contact_option="gate_homing_only";
        setup_gate_homing_right_prerequisite(cpu,online);
        CHECK(!failed && checkpoint_contact_protection_option==2);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        psx_mod_write_word(PLAY+0x90,12);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_lab_completed());
        CHECK(checkpoint_contact_protection_mask()==3);
        gate_contact_actor();CHECK(gate_homing_source(0x80093C98u));
        cpu->gpr[4]=0x80093C98u;
        CHECK(!checkpoint_contact_protected(cpu->gpr[4]));
        /* Native P1 accepted once, or P1 miss then native P2 once. No AI replay. */
        for(unsigned seat=0;seat<2;++seat) {
            gate_contact_probe=1;gate_contact_hit=seat;gate_contact_calls[0]=gate_contact_calls[1]=0;
            unsigned calls=guest_calls;memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
            CPUState expected=*cpu;expected.gpr[2]=1;
            CHECK(player_contact(cpu,0x80030ECCu) && cpu->gpr[2]==1);
            CHECK(gate_contact_calls[0]==1 && gate_contact_calls[1]==seat && guest_calls==calls+1+seat);
            CHECK(!memcmp(cpu,&expected,sizeof expected) && !memcmp(before_ram,test_ram,sizeof test_ram) &&
                  !memcmp(&partner,&p2,sizeof partner));
            gate_contact_probe=0;
        }
        /* Each invalid identity/source remains protected, with no native call. */
        const uint32_t corrupt[]={0x80093C99u,0x80093C9Au,0x80093CE8u,0x80093CF8u,
            0x80093CFAu,0x80093D3Au,0x8008EF49u,0x800F7800u,SCRATCH+0x80u,
            0x800F1944u,0x800F3EFCu,0x800F3DC0u,0x800F3DD0u,0x800F76C0u};
        for(unsigned i=0;i<sizeof corrupt/sizeof corrupt[0];++i) {
            uint8_t old=psx_mod_read_byte(corrupt[i]);psx_mod_write_byte(corrupt[i],old^1u);
            CHECK(checkpoint_contact_protected(cpu->gpr[4])==3);protected_contact_unchanged(cpu,0);
            psx_mod_write_byte(corrupt[i],old);
        }
        psx_mod_write_byte(0x80093C9Au,2); /* Unrelated orb, even on the same source boss. */
        CHECK(checkpoint_contact_protected(cpu->gpr[4])==3);protected_contact_unchanged(cpu,0);
        checkpoint_contact_protection_option=1;gate_contact_actor();
        CHECK(checkpoint_contact_protected(cpu->gpr[4])==3);protected_contact_unchanged(cpu,0);
        checkpoint_contact_protection_option=0;CHECK(!checkpoint_contact_protected(cpu->gpr[4]));
        test_lab_contact_option="off";
        setup_agreed(cpu,online);test_lab_contact_option="gate_homing_only";checkpoint_reset();
        CHECK(failed && checkpoint_lab_option==1); /* This value cannot authorize any other checkpoint. */
        test_lab_contact_option="off";
    }
    setup_agreed(cpu,1);
}
static void setup_gate_enemy_prerequisite(CPUState *cpu,int online) {
    setup_agreed(cpu,online);test_lab_option="secretlab2b_enemy_cp0";checkpoint_reset();
    CHECK(checkpoint_lab_option==14 && checkpoint_lab_index()==94 && checkpoint_lab_nonce()==0x4C474531u);
    CHECK(strlen(test_lab_option)==21 && sizeof "secretlab2b_enemy_cp0"<=32);
    CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
    CHECK(checkpoint_pending.phase==2 && psx_mod_read_word(diagnostic+0xB8)==0x80072E40u);
    memcpy(test_ram,gate_enemy_source_ram,sizeof test_ram);
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+12,18);psx_mod_write_byte(PLAY+13,0);
    psx_mod_write_byte(PLAY+0x1D,0);psx_mod_write_word(PLAY+0x90,10);
    psx_mod_write_byte(PLAY+0x5B,32);psx_mod_write_byte(PLAY+0x5C,32);
    portal_test_body(0,152,123);portal_test_body(1,176,122);
    for(unsigned i=0x5D;i<=0x5E;++i){psx_mod_write_byte(PLAYER+i,32);p2.body[i]=32;}
    const uint32_t pools[][3]={{0x8008EF48u,0x80090C88u,0x9C},
        {0x80093C98u,0x80095098u,0xA0},{0x800950A0u,0x800964A0u,0xA0},{0x800C1220u,0x800C4560u,0xA4}};
    /* External input states only: no native update or spawn is emulated. */
    for(unsigned pool=0;pool<4;++pool)for(uint32_t a=pools[pool][0];a<pools[pool][1];a+=pools[pool][2])
        psx_mod_write_byte(a,0);
    psx_mod_write_word(0x800971F8u+8,0);psx_mod_write_word(0x800971F8u+12,0);
    psx_mod_write_word(0x800971F8u+0x14,0);psx_mod_write_word(0x800971F8u+0x18,0);
    const uint16_t bounds[]={1600,0,0,0,1600,0,0,0};
    for(unsigned i=0;i<8;++i)psx_mod_write_half(0x800971F8u+0x1C+i*2,bounds[i]);
    uint32_t meta,desc;CHECK(checkpoint_gate_enemy_source() && checkpoint_gate_enemy_inactive());
    CHECK(checkpoint_gate_enemy_assets(&meta,&desc) && checkpoint_gate_enemy_ground(meta,desc));
    CHECK(checkpoint_gate_enemy_original_arrival());
}
static void gate_enemy_test_native_standing(void) {
    /* A later real observation is supplied, not the physics that produces it. */
    psx_mod_write_word(PLAYER+12,123u<<16);psx_mod_write_word(PLAYER+0x1C,123u<<16);
    put32(p2.body+12,122u<<16);put32(p2.body+0x1C,122u<<16);
    psx_mod_write_word(0x800971F8u+8,408u<<16);psx_mod_write_word(0x800971F8u+0x14,400u<<16);
    psx_mod_write_word(PLAY+0x90,12);
}
static void agreed_gate_enemy_prerequisite(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
      for(unsigned velocities=0;velocities<4;++velocities) {
        setup_gate_enemy_prerequisite(cpu,online);
        gate_enemy_test_vy(0,velocities&1u?-0x80000:0);gate_enemy_test_vy(1,velocities&2u?-0x80000:0);
        p2.body[5]=1;memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
        p2.body[5]=2;partner=p2;CPUState registers=*cpu;Mmx6CoopLifecycle lifecycle=life;
        memcpy(before_ram,test_ram,sizeof test_ram);
        const unsigned positions[]={8,0x18,12,0x1C};
        for(unsigned i=0;i<4;++i) {
            uint32_t value=(i<2?560u:121u)<<16;
            for(unsigned n=0;n<4;++n)before_ram[(PLAYER+positions[i]+n)&0x1FFFFF]=(uint8_t)(value>>(n*8));
        }
        put32(partner.body+8,576u<<16);put32(partner.body+0x18,576u<<16);
        put32(partner.body+12,121u<<16);put32(partner.body+0x1C,121u<<16);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner) &&
            !memcmp(&registers,cpu,sizeof registers) && !memcmp(&lifecycle,&life,sizeof life));
        CHECK(psx_mod_read_byte(diagnostic+0xAD)==1 && !psx_mod_read_byte(diagnostic+0xAE));
        psx_mod_write_word(PLAY+0x90,12); /* Clock alone is not native standing. */
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        gate_enemy_test_native_standing();psx_mod_write_word(PLAY+0x90,11);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        psx_mod_write_word(PLAY+0x90,12);memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
            psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && psx_mod_read_byte(diagnostic+0xAD)==2 &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
        CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX && checkpoint_gate_enemy_inactive());
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6) && psx_mod_read_word(diagnostic+0xA4)==1);
      }
      const uint32_t corrupt[]={0x8003D850u,0x8003AD18u,0x800EA3B0u,0x800E9BDCu,0x800E9D70u,
          0x80097438u,0x80100000u,0x80120000u,0x80073D50u,0x8006DA44u,0x800F5CE4u};
      for(unsigned i=0;i<sizeof corrupt/sizeof corrupt[0];++i) {
        setup_gate_enemy_prerequisite(cpu,online);psx_mod_write_byte(corrupt[i],psx_mod_read_byte(corrupt[i])^0x40);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
      }
      for(unsigned phase=2;phase<=3;++phase)for(unsigned seat=0;seat<2;++seat)for(unsigned below=0;below<2;++below) {
        setup_gate_enemy_prerequisite(cpu,online);
        if(phase==3){CHECK(!checkpoint_stage_boundary(cpu));gate_enemy_test_native_standing();}
        gate_enemy_test_vy(seat,below?-0x80001:1);memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==phase && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
      }
      for(unsigned bad=0;bad<12;++bad) {
        setup_gate_enemy_prerequisite(cpu,online);
        if(bad==0)p2.body[0]=0;if(bad==1)p2.body[4]=2;if(bad==2)p2.body[0x5C]=0x80;
        if(bad==3)p2.body[0x5D]=31;if(bad==4)p2.body[2]=0;if(bad==5)p2.body[0x70]=0;
        if(bad==6)put32(p2.body+0x68,0);if(bad==7)life.status[0]=MMX6_COOP_FALLEN;
        if(bad==8)psx_mod_write_byte(PLAYER+0x5C,31);if(bad==9)psx_mod_write_word(PLAYER+0x20,1);
        if(bad==10)psx_mod_write_word(0x800971F8u+8,33u<<16);
        if(bad==11)psx_mod_write_half(0x800971F8u+0x1C,1601);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
      }
      for(unsigned phase=2;phase<=3;++phase)for(unsigned admitted=0;admitted<3;++admitted) {
        setup_gate_enemy_prerequisite(cpu,online);
        if(phase==3){CHECK(!checkpoint_stage_boundary(cpu));gate_enemy_test_native_standing();}
        if(admitted==0)psx_mod_write_byte(0x800F5CE0u,1);
        if(admitted==1)psx_mod_write_byte(0x800F5CE3u,0x10);
        if(admitted==2){psx_mod_write_byte(0x8008EF48u,1);psx_mod_write_word(0x8008EF48u+0x10,0x800F5CE0u);}
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_UNSAFE &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
      }
      const uint32_t hostile_pools[]={0x8008EF48u,0x80093C98u,0x800950A0u,0x800C1220u};
      for(unsigned i=0;i<4;++i) {
        setup_gate_enemy_prerequisite(cpu,online);uint32_t a=hostile_pools[i];
        psx_mod_write_byte(a,1);psx_mod_write_word(a+8,576u<<16);psx_mod_write_word(a+12,121u<<16);
        CHECK(!checkpoint_gate_enemy_clear() && !checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2);
      }
      setup_gate_enemy_prerequisite(cpu,online);uint32_t meta,desc;
      CHECK(checkpoint_gate_enemy_assets(&meta,&desc));
      unsigned cell=psx_mod_read_byte(0x80097438u+(112u>>8)*25u+(592u>>8));
      unsigned air_at=cell*512u+((112u>>4)&15u)*32u+((592u>>4)&15u)*2u;
      unsigned floor_at=cell*512u+((144u>>4)&15u)*32u+((592u>>4)&15u)*2u;
      uint16_t air_tile=psx_mod_read_half(meta+air_at),floor_tile=psx_mod_read_half(meta+floor_at);
      psx_mod_write_half(meta+air_at,floor_tile);CHECK(!checkpoint_gate_enemy_ground(meta,desc));
      psx_mod_write_half(meta+air_at,air_tile);psx_mod_write_half(meta+floor_at,air_tile);
      CHECK(!checkpoint_gate_enemy_ground(meta,desc)); /* Full floor, not just original pose, is required. */
    }
    setup_gate_enemy_prerequisite(cpu,0);
    psx_mod_write_word(0x8008EF48u+0x10,0x800F5CE0u); /* Inactive stale slot is not a live enemy. */
    CHECK(checkpoint_gate_enemy_inactive());
    for(unsigned combo=0;combo<3;++combo) {
        setup_agreed(cpu,1);test_lab_option="secretlab2b_enemy_cp0";
        if(combo<2)test_lab_hp_option[combo]="1";else test_lab_earned_option="all";
        checkpoint_reset();CHECK(failed);
        test_lab_hp_option[0]=test_lab_hp_option[1]="off";test_lab_earned_option="off";
    }
    test_lab_option="off";checkpoint_reset();CHECK(!checkpoint_lab_option && !checkpoint_pending.phase);
}
#include "test_mmx6_coop_refight_fixture.inc"
#include "test_mmx6_coop_recycle_departure.inc"
static void agreed_portal_prerequisite(CPUState *cpu) {
    for(int online=0;online<=1;++online)for(int distant=0;distant<=1;++distant) {
        setup_portal_prerequisite(cpu,online,distant);p2.body[5]=1; /* Native guest beam has not finished. */
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;CPUState registers=*cpu;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
        p2.body[5]=2;partner=p2;put32(partner.body+8,1506u<<16);put32(partner.body+0x18,1506u<<16);
        put32(partner.body+12,1593u<<16);put32(partner.body+0x1C,1593u<<16);
        const unsigned positions[]={8,0x18,12,0x1C};
        for(unsigned i=0;i<4;++i){uint32_t value=(i<2?checkpoint_portal_x(0):checkpoint_portal_floor(0)-23u)<<16;
            for(unsigned n=0;n<4;++n)before_ram[(PLAYER+positions[i]+n)&0x1FFFFF]=(uint8_t)(value>>(n*8));}
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 && !guest_calls);
        CHECK(!memcmp(&registers,cpu,sizeof registers) && !memcmp(before_ram,test_ram,sizeof test_ram) &&
            !memcmp(&partner,&p2,sizeof partner) && psx_mod_read_byte(diagnostic+0xAD)==1 &&
            !psx_mod_read_byte(diagnostic+0xAE)); /* No scanner call, camera/actor/HP/result write. */
        memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
        portal_test_native_ready();psx_mod_write_word(PLAY+0x90,11);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3); /* Real settling required. */
        psx_mod_write_word(PLAY+0x90,12);psx_mod_write_byte(0x800C1220u+0xA4u+5,1);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3); /* Reploid must stay idle. */
        psx_mod_write_byte(0x800C1220u+0xA4u+5,0);memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
            psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && psx_mod_read_byte(diagnostic+0xAD)==2 &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6) && psx_mod_read_word(diagnostic+0xA4)==1);
        const uint32_t corrupt[]={0x80097438u,0x80100000u,0x80120000u,0x800F2B0Cu,0x80051924u};
        for(unsigned i=0;i<sizeof corrupt/sizeof corrupt[0];++i) {
            setup_portal_prerequisite(cpu,online,distant);psx_mod_write_byte(corrupt[i],psx_mod_read_byte(corrupt[i])^0x40);
            memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;
            CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
                psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE &&
                !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
        }
    }
    setup_portal_prerequisite(cpu,1,1);independent_views=0;
    memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext saved=p2;
    CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
        psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_FORBIDDEN &&
        !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&saved,&p2,sizeof saved));
    test_lab_option="off";checkpoint_reset();
}
static void portal_test_character(unsigned seat,unsigned character,unsigned y) {
    if(seat) {p2.body[2]=(uint8_t)character;put32(p2.body+0x68,0x80073D50u+character*4u);put32(p2.body+12,y<<16);}
    else {psx_mod_write_byte(PLAYER+2,(uint8_t)character);psx_mod_write_word(PLAYER+0x68,0x80073D50u+character*4u);psx_mod_write_word(PLAYER+12,y<<16);}
}
static void agreed_portal_native_heights(CPUState *cpu) {
    for(int online=0;online<=1;++online)for(int distant=0;distant<=1;++distant)for(unsigned inverse=0;inverse<=1;++inverse) {
        setup_portal_prerequisite(cpu,online,distant);
        for(unsigned seat=0;seat<2;++seat)portal_test_character(seat,seat^inverse,1595u-(seat^inverse));
        CHECK(checkpoint_portal_original_arrival());
        /* Exact native character, standing box and height are all necessary. */
        psx_mod_write_word(PLAYER+12,(1595u-(inverse^1u))<<16);CHECK(!checkpoint_portal_original_arrival());
        portal_test_character(0,inverse,1595u-inverse);
        psx_mod_write_word(PLAYER+0x68,0x80073D50u+(inverse^1u)*4u);CHECK(!checkpoint_portal_original_arrival());
        portal_test_character(0,2,1595u-inverse);CHECK(!checkpoint_portal_original_arrival());
        portal_test_character(0,inverse,1595u-inverse);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        CHECK(psx_mod_read_word(PLAYER+12)==(checkpoint_portal_floor(0)-23u)<<16 && le32(p2.body+12)==1593u<<16);
        /* Native settlement is supplied externally, never by the prerequisite. */
        portal_test_native_ready();
        for(unsigned seat=0;seat<2;++seat)portal_test_character(seat,seat^inverse,checkpoint_portal_floor(seat)-21u-(seat^inverse));
        CHECK(checkpoint_portal_ready());
        put32(p2.body+12,(checkpoint_portal_floor(1)-21u-(inverse^1u)+1u)<<16);CHECK(!checkpoint_portal_ready());
        portal_test_character(1,inverse^1u,checkpoint_portal_floor(1)-21u-(inverse^1u));
        put32(p2.body+0x68,0x80073D50u+inverse*4u);CHECK(!checkpoint_portal_ready());
        portal_test_character(1,2,1595);CHECK(!checkpoint_portal_ready());
        portal_test_character(1,inverse^1u,checkpoint_portal_floor(1)-21u-(inverse^1u));
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && checkpoint_lab_completed());
    }
    test_lab_option="off";checkpoint_reset();
}
static void mounted_fatal_ready(CPUState *cpu,int online,unsigned seat,unsigned inverse) {
    int armor_only=!strcmp(test_lab_fatal_option,"armor_p1");
    clear_phase=clear_members=clear_started=join_phase=arrival_pair=scene_call=ride_call=view_call=private_draw=0;
    both_door_reset();test_lab_hatch_stagger_option="off";
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";
    test_lab_earned_option=test_lab_contact_option="off";test_lab_fatal_option=armor_only?"armor_p1":seat?"p2":"p1";
    setup_portal_prerequisite(cpu,online,0);
    CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
    portal_test_native_ready();CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_lab_completed());
    /* External original portal/boarding state only. No native death, FX,
     * cleanup or result is supplied by this actual-plugin boundary test. */
    psx_mod_write_byte(PLAY+12,20);psx_mod_write_byte(PLAY+13,1);psx_mod_write_byte(PLAY+0x1D,0);
    portal_test_body(0,32,352);portal_test_body(1,56,352);
    for(unsigned s=0;s<2;++s)portal_test_character(s,s^inverse,352);
    if(seat) {p2.body[5]=0x12;p2.body[0xD5]=255;p2.body[0x67]=1;put32(p2.body+0x68,0);}
    else {psx_mod_write_byte(PLAYER+5,0x12);psx_mod_write_byte(PLAYER+0xD5,255);
        psx_mod_write_byte(PLAYER+0x67,1);psx_mod_write_word(PLAYER+0x68,0);}
    for(unsigned i=0;i<0xB0;++i)psx_mod_write_byte(RIDE+i,0);
    psx_mod_write_byte(RIDE,0x41);psx_mod_write_byte(RIDE+1,1);psx_mod_write_byte(RIDE+4,1);
    psx_mod_write_byte(RIDE+0x5C,32);psx_mod_write_byte(RIDE+0x97,0x40);psx_mod_write_byte(RIDE+0xA8,8);
    psx_mod_write_word(RIDE+0x10,0x800F2588u);psx_mod_write_word(RIDE+0x68,0x800F2F28u);
    const uint32_t words[][2]={
        {0x80071384u,0x800F01A4u},{0x800F01A4u,0x27BDFFE8u},
        {0x800F2F34u,0x800EBF64u},{0x800F2F38u,0x800EFC54u},
        {0x800EFC54u,0x27BDFFE0u},{0x800F2F58u,0x800EC6B4u},
        {0x800EC6B4u,0x27BDFFD8u},{0x800EC7B0u,0x24422F2Cu},
        {0x800EC804u,0x24050012u},{0x800EC830u,0x24020002u},
        {0x800EC834u,0x24020001u},{0x800EC838u,0xA22200D5u},
        {0x800F2F28u,0x1D0F0300u},{0x800F2F2Cu,0x0A0F1600u},
        {0x800F2588u,0x03011E81u},{0x800F258Cu,0x01620020u},
        {0x800EFCC8u,0x2402FF80u},{0x800EFCCCu,0xA102005Cu},{0x800EFCD0u,0xA202005Cu},
        {0x800EFD80u,0x8203005Cu},{0x800EFDC8u,0xA202005Cu},
        {0x800F00CCu,0xA08000D5u},{0x800F00DCu,0x0C00F32Fu}
    };
    for(unsigned i=0;i<sizeof words/sizeof words[0];++i)psx_mod_write_word(words[i][0],words[i][1]);
    CHECK(checkpoint_lab_receipt_complete() && !checkpoint_lab_completed());
    CHECK(ride_source()==RIDE_ALTERNATE && ride_owner()==seat && checkpoint_mounted_fatal_ready(seat));
}
static void agreed_mounted_native_fatal(CPUState *cpu) {
    for(int online=0;online<=1;++online)for(unsigned seat=0;seat<2;++seat)for(unsigned inverse=0;inverse<2;++inverse) {
        mounted_fatal_ready(cpu,online,seat,inverse);
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_fatal_state); /* Old held chord cannot fire. */
        CHECK(!checkpoint_lab_boundary(cpu,0) && checkpoint_fatal_state==CHECKPOINT_FATAL_ARMED);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext expected=p2;Mmx6CoopLifecycle expected_life=life;
        CPUState expected_cpu=*cpu;uint8_t receipt[sizeof test_diagnostic];memcpy(receipt,test_diagnostic,sizeof receipt);
        if(seat)expected.body[0x5C]=0x80;else before_ram[(PLAYER+0x5C)&0x1FFFFF]=0x80;
        before_ram[(RIDE+0x5C)&0x1FFFFF]=0x80;receipt[0xC8]=(uint8_t)((seat+1)|(CHECKPOINT_FATAL_CONSUMED<<3));
        unsigned calls=guest_calls;
        CHECK(!checkpoint_lab_boundary(cpu,6) && checkpoint_fatal_state==CHECKPOINT_FATAL_CONSUMED);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&expected,&p2,sizeof p2));
        CHECK(!memcmp(&expected_life,&life,sizeof life) && !memcmp(&expected_cpu,cpu,sizeof *cpu));
        CHECK(!memcmp(receipt,test_diagnostic,sizeof receipt) && guest_calls==calls);
        CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        if(seat)p2.body[0x5C]=7;else psx_mod_write_byte(PLAYER+0x5C,7);
        psx_mod_write_byte(RIDE+0x5C,9);
        for(unsigned edge=0;edge<4;++edge)CHECK(!checkpoint_lab_boundary(cpu,edge&1?6:0));
        CHECK((seat?p2.body[0x5C]:psx_mod_read_byte(PLAYER+0x5C))==7 && psx_mod_read_byte(RIDE+0x5C)==9);
    }
    for(unsigned bad=0;bad<24;++bad) {
        mounted_fatal_ready(cpu,1,1,0);CHECK(!checkpoint_lab_boundary(cpu,0));
        PlayerContext healthy=p2;Mmx6CoopLifecycle healthy_life=life;
        uint8_t primary[0x158],armor[0xB0];capture(PLAYER,primary,sizeof primary);capture(RIDE,armor,sizeof armor);
        if(bad==0)psx_mod_write_word(0x800EFCCCu,0); /* Exact HP-only native pair. */
        if(bad==1)psx_mod_write_word(RIDE+0x10,0x800F2590u);
        if(bad==2)psx_mod_write_byte(RIDE+4,2);
        if(bad==3)p2.body[0xD5]=1; /* Request not yet consumed. */
        if(bad==4)p2.body[0xD5]=254; /* Unsupported secondary slot. */
        if(bad==5)psx_mod_write_byte(PLAYER+0xD5,255); /* Two claims. */
        if(bad==6)psx_mod_write_byte(RIDE+0xA8,0);
        if(bad==7)psx_mod_write_byte(RIDE+0x97,0xC0);
        if(bad==8)psx_mod_write_byte(RIDE+0x5C,0);
        if(bad==9)psx_mod_write_byte(PLAYER+5,3); /* Partner must be idle. */
        if(bad==10)psx_mod_write_byte(PLAY+13,0);
        if(bad==11)psx_mod_write_byte(diagnostic+0xAD,1);
        if(bad==12)psx_mod_write_word(diagnostic+0xB0,0);
        if(bad==13)checkpoint_lab_option=10; /* No other option's receipt exception. */
        if(bad==14)pause_owner=0;if(bad==15)scene_owner=1;if(bad==16)life.wipe=1;
        if(bad==17)join_phase=1;if(bad==18)scene_call=1;if(bad==19)test_lab_ready=0;
        if(bad==20)p2.body[4]=2;if(bad==21)p2.body[5]=2;
        if(bad==22)psx_mod_write_byte(RIDE,0x40);
        if(bad==23) { /* Ordinary on-foot fatal readiness must not gain this post-portal exception. */
            p2.body[5]=2;p2.body[0xD5]=p2.body[0x67]=0;put32(p2.body+0x68,0x80073D54u);
        }
        CHECK(!checkpoint_mounted_fatal_ready(1));
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext expected=p2;Mmx6CoopLifecycle expected_life=life;
        CPUState expected_cpu=*cpu;uint8_t receipt[sizeof test_diagnostic];memcpy(receipt,test_diagnostic,sizeof receipt);
        receipt[0xC8]=2;unsigned calls=guest_calls;
        CHECK(!checkpoint_lab_boundary(cpu,6) && checkpoint_fatal_state==CHECKPOINT_FATAL_RELEASE);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&expected,&p2,sizeof p2));
        CHECK(!memcmp(&expected_life,&life,sizeof life) && !memcmp(&expected_cpu,cpu,sizeof *cpu));
        CHECK(!memcmp(receipt,test_diagnostic,sizeof receipt) && guest_calls==calls);
        /* Restoring eligibility while still held must not replay the edge. */
        project(PLAYER,primary,sizeof primary);project(RIDE,armor,sizeof armor);p2=healthy;life=healthy_life;
        psx_mod_write_word(0x800EFCCCu,0xA102005Cu);psx_mod_write_byte(PLAY+13,1);
        psx_mod_write_byte(diagnostic+0xAD,2);psx_mod_write_word(diagnostic+0xB0,CHECKPOINT_LAB_PORTAL_NONCE);
        checkpoint_lab_option=7;pause_owner=-1;scene_owner=join_phase=scene_call=0;test_lab_ready=1;
        CHECK(checkpoint_mounted_fatal_ready(1));
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_fatal_state);
        CHECK(p2.body[0x5C]==32 && psx_mod_read_byte(RIDE+0x5C)==32);
        CHECK(!checkpoint_lab_boundary(cpu,0));CHECK(!checkpoint_lab_boundary(cpu,6));
        CHECK(p2.body[0x5C]==0x80 && psx_mod_read_byte(RIDE+0x5C)==0x80);
    }
    test_lab_fatal_option=test_lab_option="off";checkpoint_reset();
}
static void agreed_mounted_armor_only(CPUState *cpu) {
    for(int online=0;online<=1;++online)for(unsigned inverse=0;inverse<2;++inverse) {
        test_lab_fatal_option="armor_p1";mounted_fatal_ready(cpu,online,0,inverse);
        CHECK(checkpoint_fatal_option==7 && !checkpoint_mounted_fatal_ready(1));
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_fatal_state);
        CHECK(!checkpoint_lab_boundary(cpu,0) && checkpoint_fatal_state==CHECKPOINT_FATAL_ARMED);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;Mmx6CoopLifecycle living=life;
        CPUState registers=*cpu;uint8_t receipt[sizeof test_diagnostic];memcpy(receipt,test_diagnostic,sizeof receipt);
        before_ram[(RIDE+0x5C)&0x1FFFFF]=0x80;receipt[0xC8]=(uint8_t)(7|(CHECKPOINT_FATAL_CONSUMED<<3));
        unsigned calls=guest_calls;
        CHECK(!checkpoint_lab_boundary(cpu,6) && checkpoint_fatal_state==CHECKPOINT_FATAL_CONSUMED);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2));
        CHECK(!memcmp(&living,&life,sizeof life) && !memcmp(&registers,cpu,sizeof *cpu));
        CHECK(!memcmp(receipt,test_diagnostic,sizeof receipt) && guest_calls==calls);
        CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        CHECK(psx_mod_read_byte(PLAYER+0x5C)==32 && p2.body[0x5C]==32);
        CHECK(psx_mod_read_byte(PLAYER+0xD5)==255 && psx_mod_read_byte(PLAYER+5)==18);
        psx_mod_write_byte(RIDE+0x5C,9);
        for(unsigned edge=0;edge<4;++edge)CHECK(!checkpoint_lab_boundary(cpu,edge&1?6:0));
        CHECK(psx_mod_read_byte(RIDE+0x5C)==9 && psx_mod_read_byte(PLAYER+0x5C)==32);
    }
    for(unsigned bad=0;bad<24;++bad) {
        test_lab_fatal_option="armor_p1";mounted_fatal_ready(cpu,1,0,0);
        CHECK(!checkpoint_lab_boundary(cpu,0));
        if(bad==0)checkpoint_lab_option=9;
        if(bad==1){psx_mod_write_byte(PLAYER+0xD5,0);p2.body[0xD5]=255;}
        if(bad==2)psx_mod_write_byte(RIDE+0x5C,0);if(bad==3)psx_mod_write_byte(RIDE+0x5C,128);
        if(bad==4)psx_mod_write_byte(PLAYER+0x5C,0);if(bad==5)psx_mod_write_byte(PLAYER+0x5C,128);
        if(bad==6)psx_mod_write_byte(PLAYER+4,2);if(bad==7)psx_mod_write_byte(PLAYER+5,2);
        if(bad==8)psx_mod_write_byte(PLAYER+0xD5,1);if(bad==9)p2.body[5]=3;
        if(bad==10)scene_owner=1;if(bad==11)join_phase=1;if(bad==12)life.status[1]=MMX6_COOP_JOINING;
        if(bad==13)arrival_pair=1;if(bad==14)psx_mod_write_word(0x800F00CCu,0);
        if(bad==15)test_lab_selected=0;if(bad==16)test_lab_profile.flags^=PSX_HOST_PROFILE_PORTABLE;
        if(bad==17)test_lab_profile.qualification[0]^=1;if(bad==18)psx_mod_write_byte(diagnostic+0xAD,1);
        if(bad==19)pause_owner=0;if(bad==20)psx_mod_write_byte(RIDE+0x97,0xC0);
        if(bad==21)psx_mod_write_byte(RIDE+0xA8,0);if(bad==22)psx_mod_write_byte(PLAY+13,0);
        if(bad==23)++test_lab_profile.revision;
        CHECK(!checkpoint_mounted_fatal_ready(0));
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;Mmx6CoopLifecycle living=life;CPUState registers=*cpu;
        unsigned calls=guest_calls;
        CHECK(!checkpoint_lab_boundary(cpu,6) && checkpoint_fatal_state==CHECKPOINT_FATAL_RELEASE);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2));
        CHECK(!memcmp(&living,&life,sizeof life) && !memcmp(&registers,cpu,sizeof *cpu) && guest_calls==calls);
        CHECK(!checkpoint_lab_boundary(cpu,6)); /* Rejected held edge cannot fire later. */
        /* The next factory restores transient refusal fields, not an outcome. */
        pause_owner=-1;scene_owner=join_phase=arrival_pair=0;test_lab_ready=test_lab_selected=1;test_lab_failed=0;
    }
    test_lab_fatal_option="armor_p1";test_lab_option="intro_cp2";checkpoint_reset();CHECK(failed);
    test_lab_fatal_option=test_lab_option="off";failed=0;checkpoint_reset();
}
static void capsule_fatal_ready(CPUState *cpu,int online) {
    clear_phase=clear_members=clear_started=join_phase=arrival_pair=scene_call=0;both_door_reset();
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";
    test_lab_earned_option=test_lab_contact_option="off";test_lab_fatal_option="capsule_owner_p1";
    setup_portal_prerequisite(cpu,online,0);
    CHECK(!failed && checkpoint_fatal_option==5 && !checkpoint_fatal_state);
    CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
    portal_test_native_ready();CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_lab_completed());
    /* External actual-admission precondition only. No capsule routine,
     * native death or survivor release is emulated by this unit fixture. */
    scene_owner=1;scene_phase=0;psx_mod_write_word(diagnostic+0x74,0x80051924u);
    /* Accepted F52 LOCAL row159: D0=255,D4=0,7A=1,PLAY10=0,PLAY1C=1. */
    psx_mod_write_byte(PLAYER+5,20);psx_mod_write_byte(PLAYER+0xD0,255);psx_mod_write_byte(PLAYER+0x7A,1);
    psx_mod_write_byte(PLAYER+0xD4,0);psx_mod_write_byte(PLAY+0x10,0);psx_mod_write_byte(PLAY+0x1C,1);
    psx_mod_write_byte(0x800C1225u,1);psx_mod_write_byte(0x800C1226u,0);
    CHECK(checkpoint_capsule_fatal_ready());
}
static void agreed_capsule_fatal(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        capsule_fatal_ready(cpu,online);
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_fatal_state); /* Old held chord cannot fire. */
        CHECK(!checkpoint_lab_boundary(cpu,0) && checkpoint_fatal_state==CHECKPOINT_FATAL_ARMED);
        memcpy(before_ram,test_ram,sizeof test_ram);before_ram[(PLAYER+0x5C)&0x1FFFFF]=0x80;
        PlayerContext expected=p2;Mmx6CoopLifecycle expected_life=life;
        uint8_t receipt[sizeof test_diagnostic];memcpy(receipt,test_diagnostic,sizeof receipt);receipt[0xC8]=21;
        unsigned calls=guest_calls;CHECK(!checkpoint_lab_boundary(cpu,6));
        CHECK(checkpoint_fatal_state==CHECKPOINT_FATAL_CONSUMED && !memcmp(before_ram,test_ram,sizeof test_ram));
        CHECK(!memcmp(&expected,&p2,sizeof p2) && !memcmp(&expected_life,&life,sizeof life));
        CHECK(!memcmp(receipt,test_diagnostic,sizeof receipt) && calls==guest_calls);
        CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        psx_mod_write_byte(PLAYER+0x5C,7);
        for(unsigned edge=0;edge<4;++edge)CHECK(!checkpoint_lab_boundary(cpu,edge&1?6:0));
        CHECK(psx_mod_read_byte(PLAYER+0x5C)==7); /* Once, including later native HP changes. */
    }
    for(unsigned bad=0;bad<17;++bad) {
        capsule_fatal_ready(cpu,1);CHECK(!checkpoint_lab_boundary(cpu,0));
        if(bad==0)scene_owner=2;if(bad==1)scene_phase=1;
        if(bad==2)psx_mod_write_byte(PLAYER+5,2);
        if(bad==3){psx_mod_write_byte(PLAYER+0xD0,0);psx_mod_write_byte(PLAYER+0x7A,0);
            psx_mod_write_byte(PLAY+0x1C,0);psx_mod_write_byte(0x8008EAFCu,0);}
        if(bad==4)psx_mod_write_word(diagnostic+0x74,0x8003D308u);
        if(bad==5)psx_mod_write_word(0x800C1230u,0x800F2E2Cu);
        if(bad==6)psx_mod_write_byte(0x800C1221u,25);
        if(bad==7)psx_mod_write_byte(0x800C1222u,3);
        if(bad==8)psx_mod_write_byte(0x800C1224u,2);
        if(bad==9)psx_mod_write_byte(0x800C1225u,0);
        if(bad==10)psx_mod_write_byte(0x800C1226u,1);
        if(bad==11)life.status[1]=MMX6_COOP_FALLEN;
        if(bad==12)test_lab_ready=0;
        if(bad==13)psx_mod_write_byte(diagnostic+0xA8,CHECKPOINT_INITIALIZING);
        if(bad==14)zero_projected=1;
        if(bad==15)state_track.count=1;
        if(bad==16)psx_mod_write_byte(PLAY+0x1D,1);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext expected=p2;
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_fatal_state);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&expected,&p2,sizeof p2));
        CHECK(!checkpoint_lab_boundary(cpu,6) && psx_mod_read_byte(PLAYER+0x5C)==32);
    }
    state_track.count=state_track.error=0;zero_projected=scene_owner=scene_phase=0;test_lab_ready=1;
    test_lab_fatal_option="capsule_owner_p1";test_lab_option="intro_cp2";failed=0;checkpoint_reset();CHECK(failed);
    test_lab_fatal_option="off";test_lab_option="off";failed=0;checkpoint_reset();
}
static void boss_admission_fatal_ready(CPUState *cpu,int online,unsigned phase) {
    clear_phase=clear_members=clear_started=join_phase=arrival_pair=scene_call=0;both_door_reset();
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";
    test_lab_earned_option=test_lab_contact_option="off";test_lab_fatal_option="boss_admission_p1";
    setup_agreed(cpu,online);test_lab_option="alternate_boss_cp1";checkpoint_reset();
    CHECK(!failed && checkpoint_fatal_option==6 && checkpoint_lab_boundary(cpu,6));
    mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
    psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_lab_completed());
    /* Actual admission observations supplied externally; no emulated death. */
    scene_owner=1;scene_phase=phase;life.status[0]=life.status[1]=MMX6_COOP_ALIVE;
    psx_mod_write_byte(PLAYER,1);psx_mod_write_byte(PLAYER+2,0);psx_mod_write_byte(PLAYER+4,1);
    psx_mod_write_byte(PLAYER+5,20);psx_mod_write_byte(PLAYER+0x5C,32);
    p2.body[0]=1;p2.body[4]=phase?3:1;p2.body[0x5C]=32;
    psx_mod_write_word(0x800FA0B0u,0x24027948u);psx_mod_write_word(0x800FA0C0u,0xA6420042u);
    psx_mod_write_word(PLAY+0x20,0x8008EF48u);
    psx_mod_write_byte(0x8008EF48u,0x41);psx_mod_write_byte(0x8008EF49u,53);
    psx_mod_write_byte(0x8008EF4Au,0);psx_mod_write_byte(0x8008EF4Cu,1);psx_mod_write_byte(0x8008EF4Du,2);
    psx_mod_write_byte(0x8008EF48u+0x5C,0);psx_mod_write_byte(0x8008EF48u+0x42,0x48);psx_mod_write_byte(0x8008EF48u+0x43,0x79);
    CHECK(checkpoint_boss_admission_fatal_ready());
}
static void agreed_boss_admission_fatal(CPUState *cpu) {
    for(int online=0;online<=1;++online)for(unsigned phase=0;phase<=3;phase+=3) {
        boss_admission_fatal_ready(cpu,online,phase);
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_fatal_state);
        CHECK(!checkpoint_lab_boundary(cpu,0) && checkpoint_fatal_state==CHECKPOINT_FATAL_ARMED);
        memcpy(before_ram,test_ram,sizeof test_ram);before_ram[(PLAYER+0x5C)&0x1FFFFF]=0x80;
        PlayerContext partner=p2;Mmx6CoopLifecycle expected_life=life;unsigned calls=guest_calls;
        CHECK(!checkpoint_lab_boundary(cpu,6) && checkpoint_fatal_state==CHECKPOINT_FATAL_CONSUMED);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2));
        CHECK(!memcmp(&expected_life,&life,sizeof life) && guest_calls==calls);
        CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        psx_mod_write_byte(PLAYER+0x5C,7);
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
        CHECK(psx_mod_read_byte(PLAYER+0x5C)==7);
    }
    for(unsigned bad=0;bad<9;++bad) {
        boss_admission_fatal_ready(cpu,1,3);CHECK(!checkpoint_lab_boundary(cpu,0));
        if(bad==0)scene_owner=2;if(bad==1)scene_phase=4;
        if(bad==2)psx_mod_write_byte(PLAYER+5,2);
        if(bad==3)psx_mod_write_byte(0x8008EF48u+0x5C,48);
        if(bad==4)psx_mod_write_byte(0x8008EF49u,55);
        if(bad==5)psx_mod_write_byte(0x8008EF48u+0x42,0x49);
        if(bad==6)psx_mod_write_word(0x800FA0B0u,0);
        if(bad==7)life.status[1]=MMX6_COOP_FALLEN;
        if(bad==8)psx_mod_write_word(PLAY+0x20,0x8008EF49u);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_fatal_state);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2));
        CHECK(!checkpoint_lab_boundary(cpu,6) && psx_mod_read_byte(PLAYER+0x5C)==32);
    }
    test_lab_fatal_option="off";test_lab_option="off";scene_owner=scene_phase=0;checkpoint_reset();
}
static void fallen_portal_native_fall(void) {
    /* External observations only, not an emulation of native physics/death.
     * The production prerequisite must observe these; it never writes them. */
    unsigned fallen=checkpoint_fallen_portal_seat();
    for(unsigned seat=0;seat<2;++seat) {
        portal_test_body(seat,seat==fallen?1312:1506,seat==fallen?1594:1595-seat);
        if(seat==fallen) {
            if(seat) {
                p2.body[5]=6;p2.body[0x67]=1;p2.body[0x70]=0;
                put32(p2.body+0x1C,1593u<<16);put32(p2.body+0x24,(uint32_t)-65536);
            } else {
                psx_mod_write_byte(PLAYER+5,6);psx_mod_write_byte(PLAYER+0x67,1);psx_mod_write_byte(PLAYER+0x70,0);
                psx_mod_write_word(PLAYER+0x1C,1593u<<16);psx_mod_write_word(PLAYER+0x24,(uint32_t)-65536);
            }
        }
    }
    psx_mod_write_word(PLAY+0x90,12);
}
static void fallen_portal_test_vy(unsigned seat,int32_t vy) {
    if(seat)put32(p2.body+0x24,(uint32_t)vy);
    else psx_mod_write_word(PLAYER+0x24,(uint32_t)vy);
}
static void fallen_portal_block_pit(uint32_t meta,uint32_t desc) {
    unsigned tile=0;
    while(tile*4u+4u<=PORTAL_SETUP_DESC_BYTES && psx_mod_read_byte(desc+tile*4u)!=0x38)++tile;
    CHECK(tile*4u+4u<=PORTAL_SETUP_DESC_BYTES);
    unsigned x=1312,y=1600;
    uint32_t cell=PORTAL_SETUP_LAYOUT+(y>>8)*PORTAL_SETUP_WIDTH+(x>>8);
    psx_mod_write_byte(cell,1);
    unsigned at=512u+((y>>4)&15u)*32u+((x>>4)&15u)*2u;
    psx_mod_write_half(meta+at,(uint16_t)tile);
}
static void agreed_fallen_portal_prerequisite(CPUState *cpu) {
    for(int online=0;online<=1;++online)for(int variant=2;variant<=3;++variant) {
      /* Both original standing velocities, independently for each seat and
       * both fallen-seat orders. Full snapshots below also bind their VY. */
      for(unsigned velocities=0;velocities<4;++velocities) {
        setup_portal_prerequisite(cpu,online,variant);
        int32_t vy[2]={velocities&1u?-0x80000:0,velocities&2u?-0x80000:0};
        fallen_portal_test_vy(0,vy[0]);fallen_portal_test_vy(1,vy[1]);
        CHECK(!failed && checkpoint_fallen_portal_source());
        CHECK(variant!=3 || strlen(test_lab_option)==24); /* Full name and NUL fit the32-byte parser. */
        p2.body[5]=1;memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 &&
              !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2));
        p2.body[5]=2;partner=p2;CPUState registers=*cpu;Mmx6CoopLifecycle lifecycle=life;
        memcpy(before_ram,test_ram,sizeof test_ram);
        for(unsigned seat=0;seat<2;++seat) {
            uint32_t x=(seat==checkpoint_fallen_portal_seat()?1312u:1506u)<<16,y=1593u<<16;
            if(seat) {
                put32(partner.body+8,x);put32(partner.body+0x18,x);
                put32(partner.body+12,y);put32(partner.body+0x1C,y);
            } else {
                const unsigned positions[]={8,0x18,12,0x1C};
                for(unsigned i=0;i<4;++i) {
                    uint32_t value=i<2?x:y;
                    for(unsigned n=0;n<4;++n)before_ram[(PLAYER+positions[i]+n)&0x1FFFFF]=(uint8_t)(value>>(n*8));
                }
            }
        }
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 && !guest_calls &&
              !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) &&
              !memcmp(&registers,cpu,sizeof registers) && !memcmp(&lifecycle,&life,sizeof life));
        CHECK(psx_mod_read_byte(diagnostic+0xAD)==1 && !psx_mod_read_byte(diagnostic+0xAE));
        /* Advancing a clock without actual native fall cannot complete. */
        psx_mod_write_word(PLAY+0x90,12);memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 &&
              !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2));
        fallen_portal_native_fall();psx_mod_write_word(PLAY+0x90,11);
        fallen_portal_test_vy(checkpoint_fallen_portal_seat()^1u,vy[checkpoint_fallen_portal_seat()^1u]);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3); /* Two updates required. */
        psx_mod_write_word(PLAY+0x90,12);memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
              psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && psx_mod_read_byte(diagnostic+0xAD)==2 &&
              !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) &&
              !memcmp(&lifecycle,&life,sizeof life)); /* Includes all HP, velocity, ground and lifecycle bytes. */
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
      }
        /* The source envelope is inclusive; positive/upward and the first
         * value below it must neither place actors nor complete setup. */
        for(unsigned phase=2;phase<=3;++phase)for(unsigned seat=0;seat<2;++seat)
          for(unsigned below=0;below<2;++below) {
            if(phase==3 && seat==(unsigned)(variant==3))continue;
            setup_portal_prerequisite(cpu,online,variant);
            if(phase==3) {
                CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
                fallen_portal_native_fall();
            }
            fallen_portal_test_vy(seat,below?-0x80001:1);
            memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
            CPUState registers=*cpu;Mmx6CoopLifecycle lifecycle=life;
            CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==phase && !guest_calls &&
                  !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) &&
                  !memcmp(&registers,cpu,sizeof registers) && !memcmp(&lifecycle,&life,sizeof life));
        }
        PlayerContext partner;Mmx6CoopLifecycle lifecycle;

        const uint32_t corrupt[]={0x800282F0u,0x80029580u,0x80029658u,0x8002D2B0u,
            0x8003D87Cu,0x8003AD3Cu,0x80073D50u,0x80073D54u,0x800F2E24u,
            0x80097438u,0x80100000u,0x80120000u};
        for(unsigned phase=2;phase<=3;++phase)for(unsigned i=0;i<sizeof corrupt/sizeof corrupt[0];++i) {
            setup_portal_prerequisite(cpu,online,variant);
            if(phase==3)CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
            psx_mod_write_byte(corrupt[i],psx_mod_read_byte(corrupt[i])^0x40);
            memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;lifecycle=life;
            CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
                  psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE &&
                  !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof p2) &&
                  !memcmp(&lifecycle,&life,sizeof life));
        }
        setup_portal_prerequisite(cpu,online,variant);uint32_t meta,desc;
        CHECK(checkpoint_portal_assets(&meta,&desc));fallen_portal_block_pit(meta,desc);
        CHECK(!checkpoint_fallen_portal_ground(meta,desc));
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase &&
              psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE);

        for(unsigned bad=0;bad<16;++bad) {
            setup_portal_prerequisite(cpu,online,variant);
            CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);fallen_portal_native_fall();
            unsigned seat=checkpoint_fallen_portal_seat();uint8_t b[sizeof p2.body];
            if(seat)memcpy(b,p2.body,sizeof b);else capture(PLAYER,b,sizeof b);
            if(bad==0)b[0x67]=0;if(bad==1)b[0x70]=8;
            if(bad==2)put32(b+12,1593u<<16);if(bad==3)put32(b+0x24,0);
            if(bad==4)put32(b+0x24,65536);if(bad==5)put32(b+8,1313u<<16);
            if(bad==6)put32(b+12,1688u<<16);if(bad==7)b[0x5C]=0x80;
            if(bad==13)b[0]=0;if(bad==14)b[4]=2;if(bad==15)b[0x5C]=0;
            if(seat)memcpy(p2.body,b,sizeof b);else project(PLAYER,b,sizeof b);
            /* Native fatal/dying may precede the lifecycle publication. */
            if(bad==7 || bad==14)CHECK(life.status[seat]==MMX6_COOP_ALIVE);
            if(bad==8)life.status[seat]=MMX6_COOP_FALLEN;
            if(bad==9) {if(seat)psx_mod_write_byte(PLAYER+0x70,0);else p2.body[0x70]=0;}
            if(bad==10)psx_mod_write_half(0x800971F8u+14,1423);
            if(bad==11) {portal_test_native_ready();fallen_portal_native_fall();psx_mod_write_byte(0x8008EF48u+5,2);}
            if(bad==12) {if(seat)psx_mod_write_word(PLAYER+8,1507u<<16);else put32(p2.body+8,1507u<<16);}
            memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;lifecycle=life;
            CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 && !guest_calls &&
                  psx_mod_read_byte(diagnostic+0xAD)==1 && !memcmp(before_ram,test_ram,sizeof test_ram) &&
                  !memcmp(&partner,&p2,sizeof p2) && !memcmp(&lifecycle,&life,sizeof life));
        }
    }
    for(unsigned variant=0;variant<2;++variant)for(unsigned bad=0;bad<3;++bad) {
        test_lab_hp_option[0]=bad==0?"1":"off";test_lab_hp_option[1]=bad==1?"1":"off";
        test_lab_earned_option=bad==2?"all":"off";setup_agreed(cpu,1);
        test_lab_option=variant?"recycle_fallen_guest_cp2":"recycle_fallen_cp2";checkpoint_reset();
        CHECK(failed && !checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase);
    }
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";test_lab_earned_option="off";
    test_lab_option="off";checkpoint_reset();
}
static void setup_northpole_prerequisite_option(CPUState *cpu,int online,int pickup) {
    setup_agreed(cpu,online);test_lab_option=pickup?"northpole_pickup_support":"northpole_ice_cp3";checkpoint_reset();
    CHECK(checkpoint_lab_option==(pickup?28u:11u) && checkpoint_lab_index()==10 && checkpoint_lab_nonce()==(pickup?0x4C4E5031u:0x4C4E4933u));
    CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
    CHECK(checkpoint_pending.phase==2 && psx_mod_read_word(diagnostic+0xB8)==0x80072270u);
    memcpy(test_ram,northpole_source_ram,sizeof test_ram);
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+12,2);psx_mod_write_byte(PLAY+13,0);
    psx_mod_write_byte(PLAY+0x1D,3);psx_mod_write_word(PLAY+0x90,10);
    portal_test_body(0,4800,1300);portal_test_body(1,4824,1300);
    psx_mod_write_word(0x800971F8u+8,4640u<<16);psx_mod_write_word(0x800971F8u+12,1264u<<16);
    const uint16_t bounds[]={4976,4640,1456,1264,4976,4640,1456,1264};
    for(unsigned i=0;i<8;++i)psx_mod_write_half(0x800971F8u+0x1C+i*2,bounds[i]);
    uint32_t meta,desc;CHECK(checkpoint_northpole_source());
    CHECK(checkpoint_northpole_assets(&meta,&desc) && checkpoint_northpole_ground(meta,desc));
}
static void setup_northpole_prerequisite(CPUState *cpu,int online) {
    setup_northpole_prerequisite_option(cpu,online,0);
}
static void mounted_cp1_setup(CPUState *cpu,unsigned online) {
    test_lab_hp_option[0]=test_lab_hp_option[1]="off";
    test_lab_fatal_option=test_lab_earned_option=test_lab_contact_option=test_lab_hatch_stagger_option="off";
    setup_agreed(cpu,(int)online);test_lab_option="alternate_mounted_cp1";checkpoint_reset();
    CHECK(checkpoint_lab_option==29 && checkpoint_lab_index()==106 && checkpoint_lab_nonce()==0x4C4D4131u);
    CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
    psx_mod_write_byte(PLAY,10);memcpy(test_ram+0xE9860,mounted_source_bin,sizeof mounted_source_bin);
    /* External original CP1 on-foot arrival, not produced by the fixture. */
    for(unsigned seat=0;seat<2;++seat) {
        uint8_t body[0x158]={0};body[0]=body[3]=body[4]=1;body[2]=(uint8_t)seat;body[5]=2;
        body[0x5C]=body[0x5D]=body[0x5E]=32;body[0x70]=8;put32(body+0x68,0x80073D50u+seat*4u);
        if(seat)memcpy(p2.body,body,sizeof body);else project(PLAYER,body,sizeof body);
    }
    cpu->gpr[29]=0x801FFF00u;cpu->gpr[6]=0x12345678;cpu->gpr[7]=0x87654321;
    psx_mod_write_word(cpu->gpr[29]+16,0xCAFEBABEu);
    psx_mod_write_word(SCRATCH+0x8C,0x800F2940u);
    psx_mod_write_word(PLAYER+8,3024u<<16);psx_mod_write_word(PLAYER+12,395u<<16);
    put32(p2.body+8,3048u<<16);put32(p2.body+12,394u<<16);
    CHECK(checkpoint_mounted_source());mounted_probe=1;mounted_scan_calls=mounted_init_calls=mounted_scan_fault=0;
    memset(mounted_init_seed,0,sizeof mounted_init_seed);mounted_init_seed[0]=0x41;mounted_init_seed[1]=1;
    mounted_init_seed[3]=mounted_init_seed[4]=1;mounted_init_seed[6]=7;mounted_init_seed[0x5C]=32;
    put32(mounted_init_seed+0x10,0x800F2588u);put32(mounted_init_seed+0x68,0x800F2F28u);
    put32(mounted_init_seed+0x20,0x1234);put32(mounted_init_seed+0x24,0x5678); /* Native-result sentinels: fixture must preserve. */
}
static void agreed_mounted_prerequisite(CPUState *cpu) {
    for(unsigned online=0;online<2;++online) {
        mounted_cp1_setup(cpu,online);uint8_t hero[0x158],camera[0x54];capture(PLAYER,hero,sizeof hero);
        capture(0x800971F8u,camera,sizeof camera);PlayerContext partner=p2;CPUState registers=*cpu;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 && mounted_scan_calls==1 && !mounted_init_calls);
        CHECK(!memcmp(&registers,cpu,sizeof registers));CHECK(!psx_mod_read_byte(0x800CD340u));
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 && mounted_scan_calls==1); /* Wait for actual native callback. */
        /* External original EBEE8/2C9D4 observation, never fixture-generated. */
        memset(test_ram+0x9B7B0,0,0x30);psx_mod_write_byte(0x800F2588u,0x81);
        psx_mod_write_word(0x800CD340u,0x01010141u); /* Restore does not assign old draw byte3. */psx_mod_write_word(0x800CD350u,0x800F2588u);
        psx_mod_write_word(0x800CD348u,32u<<16);psx_mod_write_word(0x800CD34Cu,354u<<16);
        memcpy(before_ram,test_ram,sizeof test_ram);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 && !mounted_init_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&registers,cpu,sizeof registers));
        /* Separate ordinary F01A4/EBF64 result, never called by the fixture. */
        project(0x800CD340u,mounted_init_seed,sizeof mounted_init_seed);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==4 && !mounted_init_calls);
        uint8_t expected[0xB0];memcpy(expected,mounted_init_seed,sizeof expected);
        for(unsigned off=8;off<=0x18;off+=0x10) {put32(expected+off,3088u<<16);put32(expected+off+4,384u<<16);}
        CHECK(!memcmp(test_ram+0xCD340,expected,sizeof expected));
        CHECK(!memcmp(test_ram+(PLAYER&0x1FFFFF),hero,sizeof hero) && !memcmp(&partner,&p2,sizeof partner));
        CHECK(!memcmp(test_ram+0x971F8,camera,sizeof camera) && !memcmp(&registers,cpu,sizeof registers));
        psx_mod_write_word(PLAY+0x90,psx_mod_read_word(PLAY+0x90)+2);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==4); /* Never manufacture ground. */
        psx_mod_write_byte(0x800CD3E8u,8); /* External ordinary native support. */
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && checkpoint_lab_receipt_complete());
        psx_mod_write_word(0x800CD348u,3100u<<16);CHECK(!checkpoint_stage_boundary(cpu));
        CHECK(psx_mod_read_word(0x800CD348u)==3100u<<16 && mounted_scan_calls==1 && !mounted_init_calls);
        CHECK(!psx_mod_read_byte(PLAYER+0xD5) && !p2.body[0xD5]);
    }
    for(unsigned bad=0;bad<10;++bad) {
        mounted_cp1_setup(cpu,1);
        if(bad==0)psx_mod_write_byte(0x800EBEE8u,0);if(bad==1)psx_mod_write_byte(0x800F2F28u,1);
        if(bad==2)psx_mod_write_word(0x800F29B8u,0);if(bad==3)psx_mod_write_byte(0x800CD340u,1);
        if(bad==4)psx_mod_write_byte(PLAYER+0xD5,255);if(bad==5)psx_mod_write_byte(0x800F2588u,0x81);
        if(bad==6)cpu->gpr[29]|=1;if(bad==7)mounted_scan_fault=1;if(bad==8)checkpoint_pending.nonce^=1;
        if(bad==9)psx_mod_write_word(SCRATCH+0x8C,0x800F2944u);
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !mounted_init_calls);
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_FAILED);
    }
    mounted_probe=0;
    for(unsigned bad=0;bad<3;++bad) {
        test_lab_fatal_option=test_lab_earned_option="off";test_lab_hp_option[0]="off";
        setup_agreed(cpu,0);test_lab_option="alternate_mounted_cp1";
        if(bad==0)test_lab_fatal_option="p1";if(bad==1)test_lab_earned_option="all";
        if(bad==2)test_lab_hp_option[0]="1";checkpoint_reset();CHECK(failed);
    }
    test_lab_fatal_option=test_lab_earned_option="off";test_lab_hp_option[0]="off";
    test_lab_option="off";checkpoint_reset();CHECK(!checkpoint_lab_option);
}

static void agreed_inami_surface_alias(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        setup_agreed(cpu,online);test_lab_option="inami_surface_cp3";checkpoint_reset();
        CHECK(checkpoint_lab_option==30 && checkpoint_lab_index()==34 && checkpoint_lab_nonce()==0x4C495733u);
        CHECK(checkpoint_inventory[34].record==0x800725D0u && checkpoint_hash(0x800725D0u,0x800725F4u)==0x38A62A8Au);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext old_partner=p2;CPUState old_cpu=*cpu;
        CHECK(!checkpoint_request(6,0,3,0x4C495732u,CHECKPOINT_AGREED) && !checkpoint_pending.phase &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&old_partner,&p2,sizeof p2) && !memcmp(&old_cpu,cpu,sizeof *cpu));
        CHECK(checkpoint_lab_boundary(cpu,6) && checkpoint_pending.phase==1 && checkpoint_pending.index==34);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(checkpoint_pending.phase==2 && psx_mod_read_byte(PLAY+12)==6 && !psx_mod_read_byte(PLAY+13) &&
            psx_mod_read_byte(PLAY+0x1D)==3 && psx_mod_read_word(diagnostic+0xB4)==1);
        psx_mod_write_byte(PLAY,10);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_lab_completed() && !checkpoint_pending.phase);
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
    }
    test_lab_option="off";checkpoint_reset();
}
static void agreed_northpole_pickup(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        setup_agreed(cpu,online);test_lab_option="northpole_pickup_support";checkpoint_reset();
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext old_partner=p2;CPUState old_cpu=*cpu;
        CHECK(!checkpoint_request(2,0,3,0x4C4E4933u,CHECKPOINT_AGREED) && !checkpoint_pending.phase &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&old_partner,&p2,sizeof p2) && !memcmp(&old_cpu,cpu,sizeof *cpu));
        setup_northpole_prerequisite_option(cpu,online,1);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        portal_test_body(0,5016,1595);portal_test_body(1,5120,1594);psx_mod_write_word(PLAY+0x90,12);
        uint32_t parent=0x800C1220u,child=parent+0xA4u,item=0x8008EF48u;
        psx_mod_write_byte(parent,0x41);psx_mod_write_byte(parent+1,7);psx_mod_write_byte(parent+2,0);
        psx_mod_write_byte(parent+4,1);psx_mod_write_byte(parent+6,8);psx_mod_write_word(parent+0x10,0x800F60D4u);
        psx_mod_write_word(parent+8,4992u<<16);psx_mod_write_word(parent+12,1376u<<16);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==4);
        cpu->gpr[29]=0x80018000u; /* External original caller stack. */
        psx_mod_write_word(SCRATCH+0x80,0x800F61E4u);CHECK(checkpoint_northpole_pickup_source());
        psx_mod_write_word(SCRATCH+0x80,0x800F6654u);CHECK(!checkpoint_northpole_pickup_source());
        psx_mod_write_word(SCRATCH+0x80,0x800F61E4u);
        const uint32_t corrupt[]={0x800F6105u,0x800F6108u,0x800F62A0u,0x80029F38u,0x8002BBF4u,0x8007347Cu,0x8004E5D8u,0x800788F8u,0x8004D7B8u,0x800EC63Cu};
        for(unsigned i=0;i<sizeof corrupt/sizeof corrupt[0];++i) {
            uint8_t old=psx_mod_read_byte(corrupt[i]);psx_mod_write_byte(corrupt[i],old^1u);
            CHECK(!checkpoint_northpole_pickup_source());psx_mod_write_byte(corrupt[i],old);
        }
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;CPUState registers=*cpu;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==4 && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner) && !memcmp(&registers,cpu,sizeof registers));
        /* Supplied ordinary admission/native child observation, not a spawn or
         * movement model. Only an actual original phase6 child is eligible. */
        psx_mod_write_byte(parent+6,9);psx_mod_write_byte(child,0x51);psx_mod_write_byte(child+1,7);
        psx_mod_write_byte(child+2,12);psx_mod_write_byte(child+4,1);psx_mod_write_byte(child+6,6);
        psx_mod_write_word(child+0x7C,parent);psx_mod_write_word(child+0x68,child+0x80);
        psx_mod_write_word(child+0x80,0x18180000u);psx_mod_write_word(child+8,5112u<<16);psx_mod_write_word(child+12,1456u<<16);
        CHECK(checkpoint_northpole_pickup_child(child));
        psx_mod_write_byte(child+6,3);CHECK(!checkpoint_northpole_pickup_child(child));psx_mod_write_byte(child+6,6);
        psx_mod_write_word(item,0);psx_mod_write_word(item+0x10,0);
        northpole_pickup_scan_probe=1;northpole_pickup_scan_calls=0;
        registers=*cpu;CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==5 && northpole_pickup_scan_calls==1);
        CHECK(!memcmp(&registers,cpu,sizeof registers));northpole_pickup_scan_probe=0;
        memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==5 &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
        /* Native constructor result is supplied separately. The prerequisite
         * does not manufacture its box, resources, health or motion. */
        psx_mod_write_byte(item+4,1);psx_mod_write_word(item+0x30,0x800787C0u);psx_mod_write_word(item+0x68,0x800787F0u);
        psx_mod_write_word(child+0x98,0x25000000u);psx_mod_write_word(child+0x9C,0x86000000u);
        memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;registers=*cpu;
        const unsigned pos[]={8,12,0x18,0x1C};
        for(unsigned i=0;i<4;++i) {
            uint32_t p1=(i&1u?1411u:5095u)<<16,it=(i&1u?1422u:5129u)<<16;
            put32(before_ram+((PLAYER+pos[i])&0x1FFFFFu),p1);
            put32(before_ram+((item+pos[i])&0x1FFFFFu),it);
            put32(partner.body+pos[i],(i&1u?1410u:5103u)<<16);
        }
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && checkpoint_lab_completed() &&
            psx_mod_read_byte(diagnostic+0xAD)==3 && northpole_pickup_scan_calls==1);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner) && !memcmp(&registers,cpu,sizeof registers));
        psx_mod_write_word(item+8,5000u<<16);CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
        CHECK(psx_mod_read_word(item+8)==5000u<<16 && northpole_pickup_scan_calls==1);
    }
    for(unsigned prerequisite=0;prerequisite<4;++prerequisite) {
        setup_agreed(cpu,1);test_lab_option="northpole_pickup_support";
        test_lab_fatal_option=prerequisite==0?"p1":"off";
        test_lab_earned_option=prerequisite==1?"all":"off";
        test_lab_hp_option[0]=prerequisite==2?"10":"off";test_lab_hp_option[1]=prerequisite==3?"12":"off";
        checkpoint_reset();CHECK(failed && !checkpoint_pending.phase);
        test_lab_fatal_option="off";test_lab_earned_option="off";test_lab_hp_option[0]=test_lab_hp_option[1]="off";
    }
    test_lab_option="off";checkpoint_reset();
}
static void agreed_northpole_prerequisite(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        setup_northpole_prerequisite(cpu,online);p2.body[5]=1;
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;CPUState registers=*cpu;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
        p2.body[5]=2;partner=p2;put32(partner.body+8,5120u<<16);put32(partner.body+0x18,5120u<<16);
        put32(partner.body+12,1593u<<16);put32(partner.body+0x1C,1593u<<16);
        const unsigned positions[]={8,0x18,12,0x1C};
        for(unsigned i=0;i<4;++i) {uint32_t value=(i<2?5016u:1594u)<<16;
            for(unsigned n=0;n<4;++n)before_ram[(PLAYER+positions[i]+n)&0x1FFFFF]=(uint8_t)(value>>(n*8));}
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 && !guest_calls);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner) &&
            !memcmp(&registers,cpu,sizeof registers)); /* Exactly position/previous-position, no native call. */
        portal_test_body(0,5016,1595);portal_test_body(1,5120,1594);psx_mod_write_word(PLAY+0x90,12);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3); /* No fabricated producer. */
        uint32_t a=0x800C1220u;psx_mod_write_byte(a,0x41);psx_mod_write_byte(a+1,7);
        psx_mod_write_byte(a+4,1);psx_mod_write_byte(a+6,8);psx_mod_write_word(a+0x10,0x800F60D4u);
        psx_mod_write_word(a+8,4992u<<16);psx_mod_write_word(a+12,1376u<<16);
        psx_mod_write_word(PLAY+0x90,11);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        psx_mod_write_word(PLAY+0x90,12);
        uint32_t meta,desc;CHECK(checkpoint_northpole_assets(&meta,&desc));
        psx_mod_write_half(meta+37960,0x09C3);CHECK(!checkpoint_northpole_assets(&meta,&desc));
        psx_mod_write_half(meta+37962,0x09C4);CHECK(!checkpoint_northpole_assets(&meta,&desc));
        psx_mod_write_half(meta+37964,0x092E);CHECK(checkpoint_northpole_assets(&meta,&desc));
        checkpoint_pending.phase=2;CHECK(!checkpoint_northpole_assets(&meta,&desc));checkpoint_pending.phase=3;
        psx_mod_write_half(PLAYER+10,4832);CHECK(!checkpoint_northpole_assets(&meta,&desc));psx_mod_write_half(PLAYER+10,5016);
        uint16_t preserved=psx_mod_read_half(meta+37966);
        psx_mod_write_half(meta+37966,preserved^1u);CHECK(!checkpoint_northpole_assets(&meta,&desc));psx_mod_write_half(meta+37966,preserved);
        CHECK(checkpoint_northpole_assets(&meta,&desc) && checkpoint_northpole_ground(meta,desc));
        uint32_t reploid=0x800C12C4u;psx_mod_write_word(reploid,0x01160441u);psx_mod_write_word(reploid+4,0x01000001u);
        psx_mod_write_word(reploid+0x10,0x800F608Cu);psx_mod_write_word(reploid+8,5096u<<16);psx_mod_write_word(reploid+12,1600u<<16);
        psx_mod_write_word(reploid+0x68,0x8007891Cu);psx_mod_write_byte(reploid+0x70,8);psx_mod_write_byte(reploid+0x84,1);
        CHECK(checkpoint_northpole_reploid_miss(reploid) && checkpoint_northpole_clear());
        put32(p2.body+8,5114u<<16);CHECK(!checkpoint_northpole_reploid_miss(reploid) && !checkpoint_northpole_clear());put32(p2.body+8,5120u<<16);
        psx_mod_write_byte(reploid+0x84,0);CHECK(!checkpoint_northpole_clear());psx_mod_write_byte(reploid+0x84,1);
        CHECK(checkpoint_northpole_clear());
        memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
            psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && psx_mod_read_byte(diagnostic+0xAD)==2 &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
        const uint32_t corrupt[]={0x80097438u,0x80100000u,0x80120000u,0x800ED150u,0x80073D50u,0x800F04B0u,0x800F6DF4u};
        for(unsigned i=0;i<sizeof corrupt/sizeof corrupt[0];++i) {
            setup_northpole_prerequisite(cpu,online);psx_mod_write_byte(corrupt[i],psx_mod_read_byte(corrupt[i])^0x40);
            memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;
            CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
                psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE &&
                !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
        }
        const uint32_t hostile_pools[]={0x8008EF48u,0x80093C98u};
        for(unsigned i=0;i<2;++i) {
            setup_northpole_prerequisite(cpu,online);a=hostile_pools[i];
            psx_mod_write_byte(a,1);psx_mod_write_half(a+10,5120);psx_mod_write_half(a+14,1590);
            memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;
            CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls &&
                !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
        }
    }
    test_lab_option="off";checkpoint_reset();
}
static void agreed_recycle_loaded_origin_rejections(CPUState *cpu) {
    const char *options[]={"intro_cp2","amazon_cp0","amazon_cp2","intro_before_doors",
        "intro_before_explosion","recycle_cp2","recycle_portal_cp2","recycle_distant_cp2",
        "recycle_fallen_cp2","recycle_fallen_guest_cp2","secretlab2b_enemy_cp0","refight_wolfang_cp3","alternate_boss_cp1"};
    const uint8_t origins[][3]={{4,0,0},{4,0,1},{4,1,0},{4,1,2},{4,2,0},{3,0,0},{0,1,0},{0,0,1},{12,0,3},{1,0,0}};
    for(unsigned option=0;option<sizeof options/sizeof options[0];++option)for(unsigned i=0;i<sizeof origins/sizeof origins[0];++i) {
        if((option==0 || option==5 || option==6 || option==11 || option==12) && i==0)continue; /* Only aliases1/6/7/9/21 at Recycle4/0/0. */
        setup_agreed(cpu,1);test_lab_option=options[option];checkpoint_reset();
        psx_mod_write_byte(PLAY+12,origins[i][0]);psx_mod_write_byte(PLAY+13,origins[i][1]);
        psx_mod_write_byte(PLAY+0x1D,origins[i][2]);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(!checkpoint_lab_boundary(cpu,6) && checkpoint_lab_state==CHECKPOINT_LAB_CONSUMED &&
            !checkpoint_pending.phase && !checkpoint_test_taint && !guest_calls &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_ORDER &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body));
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
    }
    /* Alias7 admits only its existing source-qualified CP2 transaction after
     * modeled native card/mission arrival. No armor/part/body fields change. */
    for(int online=0;online<=1;++online)for(unsigned inverse=0;inverse<=1;++inverse) {
        setup_agreed(cpu,online);test_lab_option="recycle_portal_cp2";checkpoint_reset();psx_mod_write_byte(PLAY+12,4);
        if(inverse){psx_mod_write_byte(PLAYER+2,1);p2.body[2]=0;} /* Existing acquired inverse roster. */
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(checkpoint_lab_boundary(cpu,6) && checkpoint_pending.index==23 &&
            checkpoint_pending.nonce==0x4C525032u && checkpoint_pending.authority==CHECKPOINT_AGREED);
        before_ram[PLAY&0x1FFFFF]=8;
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body) && !guest_calls);
        CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX && psx_mod_read_word(diagnostic+0xB8)==0x80072444u);
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(checkpoint_pending.phase==2 && psx_mod_read_byte(PLAY+0x1D)==2 &&
            psx_mod_read_word(diagnostic+0xB4)==1 && !guest_calls);
    }
    /* Alias9 skips only the failed crusher approach after actual native
     * Recycle arrival. The original CP1 initializer still selects its boss
     * from untouched card-owned progress; no armor, HP or weapon grant. */
    for(int online=0;online<=1;++online)for(unsigned inverse=0;inverse<=1;++inverse) {
        test_lab_earned_option=test_lab_hp_option[0]=test_lab_hp_option[1]="off";
        setup_agreed(cpu,online);test_lab_option="alternate_boss_cp1";checkpoint_reset();
        equipment_probe=equipment_calls=0;
        psx_mod_write_byte(PLAY+12,4);psx_mod_write_byte(PLAY+0x43B,1);
        psx_mod_write_byte(PLAY+0x38,(uint8_t)inverse);
        psx_mod_write_byte(PLAYER+2,(uint8_t)inverse);p2.body[2]=(uint8_t)(inverse^1u);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(!checkpoint_earned_weapons_option && !checkpoint_starting_hp_mask());
        CHECK(checkpoint_lab_boundary(cpu,6) && checkpoint_pending.index==106 &&
            checkpoint_pending.nonce==CHECKPOINT_LAB_ALTERNATE_NONCE &&
            checkpoint_pending.authority==CHECKPOINT_AGREED);
        before_ram[PLAY&0x1FFFFF]=8;before_ram[(PLAY+12)&0x1FFFFF]=20;
        before_ram[(PLAY+13)&0x1FFFFF]=1;
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body) &&
            !equipment_calls && !guest_calls && psx_mod_read_byte(PLAY+0x43B)==1);
        CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX &&
            psx_mod_read_word(diagnostic+0xB8)==0x80072FF0u);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(checkpoint_pending.phase==2 && psx_mod_read_byte(PLAY+0x1D)==1 &&
            psx_mod_read_word(diagnostic+0xB4)==1 && !equipment_calls && !guest_calls &&
            psx_mod_read_byte(PLAY+0x43B)==1);
        psx_mod_write_byte(PLAY,10);memcpy(before_ram,test_ram,sizeof test_ram);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_lab_completed() &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body));
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
    }
    for(unsigned corrupt=0;corrupt<2;++corrupt) {
        setup_agreed(cpu,1);test_lab_option="alternate_boss_cp1";checkpoint_reset();
        psx_mod_write_byte(PLAY+12,4);
        if(corrupt)psx_mod_write_byte(0x80072FF0u,psx_mod_read_byte(0x80072FF0u)^1u);
        else test_lab_profile.qualification[0]^=1;
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !checkpoint_test_taint &&
            !guest_calls && psx_mod_read_byte(diagnostic+0xA9)==(corrupt?CHECKPOINT_SOURCE:CHECKPOINT_FORBIDDEN) &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body));
    }
    /* Alias21 consumes the same original CP3 transaction after native card
     * Load/mission arrival. Acquired weapons are input prerequisites here;
     * neither roster receives an equipment/health/result grant. */
    for(int online=0;online<=1;++online)for(unsigned inverse=0;inverse<=1;++inverse) {
        test_lab_earned_option=test_lab_hp_option[0]=test_lab_hp_option[1]="off";
        setup_agreed(cpu,online);test_lab_option="refight_wolfang_cp3";checkpoint_reset();
        equipment_probe=equipment_calls=0;
        psx_mod_write_byte(PLAY+12,4);psx_mod_write_byte(PLAY+0x60,0xFF);
        psx_mod_write_byte(PLAY+0x38,(uint8_t)inverse);
        psx_mod_write_byte(PLAY+0x5E,(uint8_t)(inverse?5:1));
        psx_mod_write_byte(PLAYER+2,(uint8_t)inverse);p2.body[2]=(uint8_t)(inverse^1u);
        psx_mod_write_byte(PLAYER+0xE7,(uint8_t)(inverse?5:1));p2.body[0xE7]=(uint8_t)(inverse?1:5);
        psx_mod_write_byte(PLAYER+0xC9,0xFF);p2.body[0xC9]=0xFF;
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(!checkpoint_earned_weapons_option && !checkpoint_starting_hp_mask());
        CHECK(checkpoint_lab_boundary(cpu,6) && checkpoint_pending.index==62 &&
            checkpoint_pending.nonce==0x4C574633u && checkpoint_pending.authority==CHECKPOINT_AGREED);
        before_ram[PLAY&0x1FFFFF]=8;before_ram[(PLAY+12)&0x1FFFFF]=12;
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body) &&
            !equipment_calls && !guest_calls && !checkpoint_earned_weapons_applied);
        CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX &&
            psx_mod_read_word(diagnostic+0xB8)==0x800729C0u);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
        CHECK(checkpoint_pending.phase==2 && psx_mod_read_byte(PLAY+0x1D)==3 &&
            psx_mod_read_word(diagnostic+0xB4)==1 && !equipment_calls && !guest_calls);
        psx_mod_write_byte(PLAY,10);memcpy(before_ram,test_ram,sizeof test_ram);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_lab_completed() &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body) &&
            !equipment_calls && !guest_calls && !checkpoint_earned_weapons_applied);
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
    }
    for(unsigned corrupt=0;corrupt<2;++corrupt) {
        setup_agreed(cpu,1);test_lab_option="refight_wolfang_cp3";checkpoint_reset();
        equipment_probe=equipment_calls=0;
        psx_mod_write_byte(PLAY+12,4);
        if(corrupt)psx_mod_write_byte(0x800729C0u,psx_mod_read_byte(0x800729C0u)^1u);
        else test_lab_profile.qualification[0]^=1;
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !checkpoint_test_taint &&
            !equipment_calls && !guest_calls &&
            psx_mod_read_byte(diagnostic+0xA9)==(corrupt?CHECKPOINT_SOURCE:CHECKPOINT_FORBIDDEN) &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body));
    }
    /* Loaded origin retains transient safety waits, then consumes the same
     * chord once only when native bodies and callback context settle. */
    const unsigned loaded_aliases[]={6,7,9};
    for(unsigned a=0;a<3;++a)for(unsigned unsafe=0;unsafe<12;++unsafe) {
        unsigned alias=loaded_aliases[a];
        setup_agreed(cpu,1);test_lab_option=alias==6?"recycle_cp2":alias==7?"recycle_portal_cp2":"alternate_boss_cp1";checkpoint_reset();psx_mod_write_byte(PLAY+12,4);
        if(unsafe==0)pause_owner=0;if(unsafe==1)private_draw=1;if(unsafe==2)zero_projected=1;
        if(unsafe==3)psx_mod_write_byte(PLAYER+5,7);if(unsafe==4)p2.body[0x67]=1;
        if(unsafe==5)state_track.count=1;if(unsafe==6)scene_owner=1;
        if(unsafe==7)life.status[0]=MMX6_COOP_FALLEN;if(unsafe==8)life.status[1]=MMX6_COOP_FALLEN;
        if(unsafe==9)p2.body[5]=7;
        if(unsafe==10)psx_mod_write_byte(PLAYER+0x70,0);if(unsafe==11)p2.body[0x70]=0;
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(!checkpoint_lab_boundary(cpu,6) && checkpoint_lab_state==CHECKPOINT_LAB_ARMED &&
            !checkpoint_pending.phase && !checkpoint_test_taint && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body));
        pause_owner=-1;private_draw=zero_projected=scene_owner=0;state_track.count=0;
        psx_mod_write_byte(PLAYER+5,2);p2.body[5]=2;p2.body[0x67]=0;
        life.status[0]=life.status[1]=MMX6_COOP_ALIVE;
        psx_mod_write_byte(PLAYER+0x70,8);p2.body[0x70]=8;
        CHECK(checkpoint_lab_boundary(cpu,0) && checkpoint_pending.index==(alias==6?27u:alias==7?23u:106u) &&
            checkpoint_pending.nonce==(alias==6?CHECKPOINT_LAB_RECYCLE_NONCE:alias==7?CHECKPOINT_LAB_PORTAL_NONCE:CHECKPOINT_LAB_ALTERNATE_NONCE));
        CHECK(!checkpoint_lab_boundary(cpu,6)); /* Pending and consumed cannot rearm. */
    }
    /* Current profile remains required at both admission and mode9. */
    setup_agreed(cpu,1);test_lab_option="recycle_cp2";checkpoint_reset();psx_mod_write_byte(PLAY+12,4);
    ++test_lab_profile.revision;
    CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !checkpoint_test_taint &&
        psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_FORBIDDEN);
    setup_agreed(cpu,1);test_lab_option="recycle_cp2";checkpoint_reset();psx_mod_write_byte(PLAY+12,4);
    CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);test_lab_ready=0;
    checkpoint_native_entry(cpu,0x8001E1BCu);
    CHECK(!checkpoint_pending.phase && !psx_mod_read_byte(PLAY+0x1D) && !guest_calls &&
        psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_FORBIDDEN);
    test_lab_option="off";checkpoint_reset();
}
static void setup_position_prerequisite(CPUState *cpu,int online,int explosion) {
    setup_agreed(cpu,online);test_lab_option=explosion?"intro_before_explosion":"intro_before_doors";checkpoint_reset();
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
    psx_mod_write_word(PLAY+0x90,100);before_doors_probe=explosion?2:1;
    cpu->gpr[29]=0x801FFF00u;cpu->gpr[6]=0x11223344u;cpu->gpr[7]=0x55667788u;
    psx_mod_write_word(cpu->gpr[29]+0x10,0xAABBCCDDu);
    CHECK(checkpoint_lab_option==(explosion?5:4) && checkpoint_lab_index()==1 &&
        checkpoint_lab_nonce()==(explosion?CHECKPOINT_LAB_BEFORE_EXPLOSION_NONCE:CHECKPOINT_LAB_BEFORE_DOORS_NONCE));
    CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
    CHECK(checkpoint_pending.phase==2 && psx_mod_read_byte(PLAY+0x1D)==1);
    psx_mod_write_byte(PLAY,10);
    psx_mod_write_word(PLAYER+8,2112u<<16);psx_mod_write_word(PLAYER+12,1115u<<16);
    put32(p2.body+8,2136u<<16);put32(p2.body+12,1114u<<16);
}
static void setup_before_doors(CPUState *cpu,int online) {
    setup_position_prerequisite(cpu,online,0);
}
static void hatch_stagger_ready(CPUState *cpu,int online) {
    test_lab_hatch_stagger_option="on";both_doors=1;
    setup_before_doors(cpu,online);CHECK(checkpoint_hatch_stagger_option && !failed);
    CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
    psx_mod_write_word(PLAY+0x90,102);psx_mod_write_byte(0x800C1224u,1);
    psx_mod_write_word(0x800C1288u,0x80078DC8u);
    CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_lab_completed());before_doors_probe=0;
    /* External native traversal precondition, not an emulated hatch or a
     * gameplay claim. The actual plugin produced the completed CP1 receipt. */
    both_door_actor=0x800C1220u;both_door_origin=0x800FA2A4u;both_door_members=3;
    scene_owner=1;scene_phase=0;psx_mod_write_byte(both_door_actor+5,3);
    psx_mod_write_word(PLAYER+8,5768u<<16);psx_mod_write_word(PLAYER+0x68,0);put32(p2.body+0x68,0);
    psx_mod_write_byte(PLAYER+0x5C,32);p2.body[0x5C]=32;
    psx_mod_write_byte(PLAY+0x1D,2);
    CHECK(checkpoint_lab_receipt_complete() && !checkpoint_lab_completed());
    CHECK(psx_mod_read_byte(diagnostic+0xC8)==64 && !checkpoint_hatch_stagger_state);
}
static void agreed_hatch_stagger(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        hatch_stagger_ready(cpu,online);memcpy(before_ram,test_ram,sizeof test_ram);
        PlayerContext expected=p2;put32(expected.body+8,5744u<<16);put32(expected.body+12,394u<<16);
        put32(expected.body+0x18,5744u<<16);put32(expected.body+0x1C,394u<<16);
        uint8_t receipt[sizeof test_diagnostic];memcpy(receipt,test_diagnostic,sizeof receipt);receipt[0xC8]=192;
        Mmx6CoopLifecycle expected_life=life;unsigned calls=guest_calls;
        CHECK(!checkpoint_lab_boundary(cpu,0) && checkpoint_hatch_stagger_state==1);
        CHECK(!memcmp(&expected,&p2,sizeof p2) && !memcmp(before_ram,test_ram,sizeof test_ram));
        CHECK(!memcmp(receipt,test_diagnostic,sizeof receipt) && !memcmp(&life,&expected_life,sizeof life));
        CHECK(guest_calls==calls && checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        put32(p2.body+8,5750u<<16);checkpoint_hatch_stagger_boundary();
        CHECK(le32(p2.body+8)==5750u<<16 && psx_mod_read_byte(diagnostic+0xC8)==192); /* Exactly once. */
    }
    for(unsigned bad=0;bad<18;++bad) {
        hatch_stagger_ready(cpu,1);
        if(bad==0)psx_mod_write_byte(both_door_actor+5,2);
        if(bad==1)put32(p2.body+0x68,0x80073D54u);
        if(bad==2)psx_mod_write_word(PLAYER+0x68,0x80073D50u);
        if(bad==3)p2.body[0x5C]=0;
        if(bad==4)life.status[0]=MMX6_COOP_FALLEN;
        if(bad==5)psx_mod_write_word(PLAYER+8,(5768u<<16)-1);
        if(bad==6)both_door_origin=0x800FA2ACu;
        if(bad==7)test_lab_ready=0;
        if(bad==8)psx_mod_write_byte(diagnostic+0xAD,1);
        if(bad==9)zero_projected=1;
        if(bad==10)both_doors=0;
        if(bad==11)psx_mod_write_byte(PLAY+0x1D,3);
        if(bad==12)psx_mod_write_byte(diagnostic+0xA8,CHECKPOINT_INITIALIZING);
        if(bad==13)both_door_members=1;
        if(bad==14)psx_mod_write_byte(both_door_actor+4,2);
        if(bad==15)checkpoint_hatch_stagger_option=0;
        if(bad==16)state_track.count=1;
        if(bad==17)state_track.error=1;
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext expected=p2;
        checkpoint_hatch_stagger_boundary();CHECK(!checkpoint_hatch_stagger_state);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&expected,&p2,sizeof p2));
    }
    state_track.count=state_track.error=0;zero_projected=0;test_lab_ready=1;both_door_reset();scene_owner=0;
    test_lab_hatch_stagger_option="on";test_lab_option="intro_before_doors";both_doors=0;failed=0;
    checkpoint_reset();CHECK(failed); /* Policy is fixed before frame0, never live-selected. */
    both_doors=1;test_lab_hatch_stagger_option="invalid";failed=0;checkpoint_reset();CHECK(failed);
    test_lab_hatch_stagger_option="on";test_lab_fatal_option="capsule_owner_p1";
    test_lab_option="recycle_portal_cp2";failed=0;checkpoint_reset();CHECK(failed);
    test_lab_fatal_option="off";
    test_lab_hatch_stagger_option="off";test_lab_option="off";failed=0;checkpoint_reset();
    CHECK(!checkpoint_hatch_stagger_option && !checkpoint_hatch_stagger_state);
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
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6) && !checkpoint_stage_boundary(cpu));
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
static void agreed_before_explosion_boundary(CPUState *cpu) {
    uint32_t meta,desc;const uint32_t actor=0x8008EF48u,cam=0x800971F8u;
    for(int online=0;online<=1;++online)for(unsigned difficulty=0;difficulty<=3;difficulty+=3) {
        setup_position_prerequisite(cpu,online,1);
        psx_mod_write_byte(PLAY+0x68,(uint8_t)difficulty);
        CHECK(checkpoint_before_explosion_source() && checkpoint_before_doors_assets(&meta,&desc));
        CHECK(checkpoint_before_explosion_ground(meta,desc));
        /* Real CP1 arrival/idle must precede the one-shot pose. */
        p2.body[0x67]=1;CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls);
        p2.body[0x67]=0;pause_owner=1;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls);pause_owner=-1;
        uint32_t box=le32(p2.body+0x68);put32(p2.body+0x68,0);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls);put32(p2.body+0x68,box);
        uint32_t published=psx_mod_read_word(0x1F800008u);psx_mod_write_word(0x1F800008u,0);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls);
        psx_mod_write_word(0x1F800008u,published);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext saved=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 && guest_calls==1);
        CHECK(cpu->gpr[6]==0x11223344u && cpu->gpr[7]==0x55667788u &&
            psx_mod_read_word(cpu->gpr[29]+0x10)==0xAABBCCDDu && !state_track.count && !state_track.error);
        put32(saved.body+8,4760u<<16);put32(saved.body+12,842u<<16);
        put32(saved.body+0x18,4760u<<16);put32(saved.body+0x1C,842u<<16);
        CHECK(!memcmp(&saved,&p2,sizeof p2));
        for(unsigned at=0;at<sizeof test_ram;++at) {
            const unsigned c=cam&0x1FFFFFu,p=PLAYER&0x1FFFFFu;
            int allowed=(at>=p+8 && at<p+16) || (at>=p+0x18 && at<p+0x20) ||
                (at>=c+8 && at<c+16) || (at>=c+0x14 && at<c+0x2C) ||
                at==c+0x47 || at==c+0x4C || at==c+0x54+0x4C || at==c+0xA8+0x4C ||
                (at>=0x8EF48u && at<0x8EF48u+0x9Cu) || at==0xFA384u || at==0xFA387u;
            CHECK(test_ram[at]==before_ram[at] || allowed);
        }
        CHECK(psx_mod_read_word(PLAYER+12)==843u<<16 && psx_mod_read_word(cam+0x14)==4576u<<16 &&
            psx_mod_read_word(cam+0x18)==704u<<16 && psx_mod_read_half(cam+0x1C)==5120 &&
            psx_mod_read_half(cam+0x1E)==1968 && psx_mod_read_half(cam+0x20)==704 &&
            psx_mod_read_half(cam+0x22)==704 && psx_mod_read_half(cam+0x24)==5120 &&
            psx_mod_read_half(cam+0x26)==1968 && psx_mod_read_half(cam+0x28)==704 &&
            psx_mod_read_half(cam+0x2A)==704);
        CHECK(psx_mod_read_byte(PLAYER+0x5C)==29 && p2.body[0x5C]==31 &&
            psx_mod_read_byte(PLAYER+0x70)==8 && p2.body[0x70]==8 &&
            !psx_mod_read_byte(PLAYER+0xD4) && !p2.body[0xD4] && psx_mod_read_byte(PLAY+0x1D)==1 &&
            !psx_mod_read_byte(cam+0x34) && !psx_mod_read_byte(cam+0x37) &&
            psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_INITIALIZING &&
            psx_mod_read_byte(diagnostic+0xAD)==1 && psx_mod_read_byte(diagnostic+0xAE)==1 &&
            psx_mod_read_word(diagnostic+0xB0)==CHECKPOINT_LAB_BEFORE_EXPLOSION_NONCE);
        CHECK(psx_mod_read_word(0x800FA384u)==(difficulty==3?0x00010001u:0x10010001u) &&
            checkpoint_before_explosion_source());
        /* Allocated alone is insufficient. The fixture does not initialize,
         * move, damage or trigger this actor; model native init separately. */
        psx_mod_write_word(PLAY+0x90,102);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        psx_mod_write_byte(actor+4,1);psx_mod_write_byte(actor+5,2);psx_mod_write_byte(actor+6,1);
        psx_mod_write_word(actor+0x30,0x800FAA34u);psx_mod_write_word(actor+0x68,0x800FA99Cu);
        psx_mod_write_half(actor+0x7C,88);psx_mod_write_half(actor+0x80,736);psx_mod_write_byte(actor+0x82,1);
        psx_mod_write_word(PLAY+0x90,101);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        psx_mod_write_word(PLAY+0x90,102);p2.body[0x70]=0;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);p2.body[0x70]=8;
        psx_mod_write_word(actor+0x10,0x800FA38Cu);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);psx_mod_write_word(actor+0x10,0x800FA384u);
        psx_mod_write_byte(actor+1,1);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);psx_mod_write_byte(actor+1,0);
        psx_mod_write_byte(actor+5,4);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);psx_mod_write_byte(actor+5,2);
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && guest_calls==1);
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && psx_mod_read_byte(diagnostic+0xAD)==2 &&
            checkpoint_lab_state==CHECKPOINT_LAB_CONSUMED && checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        psx_mod_write_word(PLAYER+8,2112u<<16);put32(p2.body+8,2136u<<16);
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6) && !checkpoint_stage_boundary(cpu));
        CHECK(psx_mod_read_word(PLAYER+8)==2112u<<16 && le32(p2.body+8)==2136u<<16 && guest_calls==1);
        /* Exact source, actor placement and current profile remain required. */
        setup_position_prerequisite(cpu,online,1);psx_mod_write_byte(before_explosion_code[0].first,0);
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE);
        CHECK(refusal_logs==1 && strstr(refusal_log,"explosion-code-hash[0]") &&
            strstr(refusal_log,"phase=2 index=1 address=0x80029F38") && strstr(refusal_log,"expected=0x72A44816"));
        CHECK(!checkpoint_stage_boundary(cpu) && refusal_logs==1); /* Cleared pending request cannot log again. */
        setup_position_prerequisite(cpu,online,1);psx_mod_write_byte(0x800FA384u,2);
        memcpy(before_ram,test_ram,sizeof test_ram);saved=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE);
        CHECK(refusal_logs==1 && strstr(refusal_log,"explosion-placement-word0-mask-FFFFFFFE[0]") &&
            strstr(refusal_log,"address=0x800FA384 actual=0x00010002 expected=0x00010000"));
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&saved,&p2,sizeof p2));
        /* First original checkpoint mismatch wins over a later explosion
         * mismatch. Logging adds no guest or participant mutation. */
        setup_position_prerequisite(cpu,online,1);psx_mod_write_word(0x8007114Cu,0);
        psx_mod_write_byte(before_explosion_code[0].first,0);
        memcpy(before_ram,test_ram,sizeof test_ram);saved=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE);
        CHECK(refusal_logs==1 && strstr(refusal_log,"checkpoint-pointer[0]") &&
            strstr(refusal_log,"address=0x8007114C actual=0x00000000 expected=0x8001E914"));
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&saved,&p2,sizeof p2));
        /* Post-ready collision publication failure has its own refusal,
         * distinct from immutable native source and allocation guards. */
        setup_position_prerequisite(cpu,online,1);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        psx_mod_write_word(PLAY+0x90,102);
        psx_mod_write_byte(actor+4,1);psx_mod_write_byte(actor+5,2);psx_mod_write_byte(actor+6,1);
        psx_mod_write_word(actor+0x30,0x800FAA34u);psx_mod_write_word(actor+0x68,0x800FA99Cu);
        psx_mod_write_half(actor+0x7C,88);psx_mod_write_half(actor+0x80,736);psx_mod_write_byte(actor+0x82,1);
        CHECK(checkpoint_before_explosion_ready() && !refusal_logs);
        psx_mod_write_word(0x1F800008u,0);memcpy(before_ram,test_ram,sizeof test_ram);saved=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && guest_calls==1 &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE);
        CHECK(refusal_logs==1 && strstr(refusal_log,"post-ready-meta-lower-bound[0]") &&
            strstr(refusal_log,"phase=3 index=1 address=0x1F800008 actual=0x00000000 expected=0x80010000"));
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&saved,&p2,sizeof p2));
        CHECK(!checkpoint_stage_boundary(cpu) && refusal_logs==1);
        /* Lifetime admission is allowed only after the genuine primary scan,
         * and only exactly as produced by the original difficulty branch. */
        setup_position_prerequisite(cpu,online,1);psx_mod_write_byte(0x800FA387u,0x10);
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE);
        for(unsigned wrong=0;wrong<8;++wrong) {
            setup_position_prerequisite(cpu,online,1);psx_mod_write_byte(PLAY+0x68,0);
            CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
            if(wrong==0)psx_mod_write_byte(0x800FA387u,0); /* Missing native lifetime transition. */
            if(wrong==1)psx_mod_write_byte(0x800FA387u,0x20); /* Later lifetime is not this setup. */
            if(wrong==2)psx_mod_write_byte(0x800FA387u,0x11); /* No arbitrary difficulty nibble. */
            if(wrong==3)psx_mod_write_byte(0x800FA384u,3); /* No extra allocation/header flag. */
            if(wrong==4)psx_mod_write_byte(0x800FA385u,1); /* Exact native type0. */
            if(wrong==5)psx_mod_write_byte(0x800FA386u,0); /* Exact subtype1. */
            if(wrong==6)psx_mod_write_half(0x800FA388u,4673); /* Exact authored X. */
            if(wrong==7)psx_mod_write_half(0x800FA38Au,737); /* Exact authored Y. */
            CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && guest_calls==1 &&
                psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE && refusal_logs==1);
        }
        setup_position_prerequisite(cpu,online,1);psx_mod_write_byte(before_explosion_code[1].first,0);
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE &&
            strstr(refusal_log,"explosion-code-hash[1]")); /* Gate bytes themselves remain pinned. */
        setup_position_prerequisite(cpu,online,1);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        CHECK(!refusal_logs); /* Normal placement/waiting never emits a refusal. */
        checkpoint_reset();CHECK(!checkpoint_pending.phase && !psx_mod_read_byte(diagnostic+0xAD));
    }
    setup_position_prerequisite(cpu,1,1);test_lab_ready=0;
    CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
        psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_FORBIDDEN);
    before_doors_probe=0;setup_agreed(cpu,1);test_lab_option="intro_before_explosion";checkpoint_reset();
    checkpoint_lab_state=CHECKPOINT_LAB_CONSUMED;
    CHECK(!checkpoint_request(0,0,1,CHECKPOINT_LAB_BEFORE_DOORS_NONCE,CHECKPOINT_AGREED) &&
        psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_UNKNOWN && !checkpoint_pending.phase);
    checkpoint_reset();psx_mod_write_byte(diagnostic+0x50,8);psx_mod_write_byte(diagnostic+0x53,1);
    rejected_checkpoint(cpu,CHECKPOINT_FORBIDDEN);
    test_lab_option="off";checkpoint_reset();
    CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !checkpoint_lab_option);
}
#endif
#if defined(MMX6_COOP_AGREED_CHECKPOINT) && defined(MMX6_COOP_MODERN_STATE)
static void guest_intro_geometry_admission(CPUState *cpu) {
    setup_agreed(cpu,0);memcpy(test_ram,before_doors_ram,sizeof test_ram);
    memset(test_ram+(0x8008EF48u&0x1FFFFFu),0,0x1D40);
    memset(p2.body,0,sizeof p2.body);p2.body[0]=p2.body[3]=p2.body[4]=1;
    p2.body[2]=1;p2.body[5]=2;p2.body[0x5C]=32;
    put32(p2.body+8,4900u<<16);put32(p2.body+12,874u<<16);
    enrolled=independent_views=1;failed=private_draw=inside=zero_world=scene_owner=clear_phase=0;
    pause_owner=-1;life.status[0]=life.status[1]=MMX6_COOP_ALIVE;
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+1,0);
    psx_mod_write_byte(PLAY+12,0);psx_mod_write_byte(PLAY+13,0);
    psx_mod_write_byte(PLAY+0x10,0);psx_mod_write_byte(PLAY+0x1C,0);
    psx_mod_write_word(PLAYER+8,144u<<16);psx_mod_write_word(PLAYER+12,1115u<<16);
    psx_mod_write_byte(VIEW_CAMERA+4,1);psx_mod_write_byte(VIEW_CAMERA+0x44,1);
    psx_mod_write_half(VIEW_CAMERA+0x30,160);psx_mod_write_half(VIEW_CAMERA+0x32,160);
    psx_mod_write_half(VIEW_CAMERA+0x2C,96);intro_camera_valid=1;
    psx_mod_write_word(VIEW_CAMERA+8,0);psx_mod_write_word(VIEW_CAMERA+12,944u<<16);
    psx_mod_write_word(VIEW_CAMERA+0x14,0);psx_mod_write_word(VIEW_CAMERA+0x18,944u<<16);
    const uint16_t limits[]={5120,0,704,704};
    for(unsigned i=0;i<4;++i){intro_camera_requests[i*2]=(uint8_t)limits[i];intro_camera_requests[i*2+1]=(uint8_t)(limits[i]>>8);}
    CHECK(intro_geometry_source());uint8_t camera[0x54],primary[0x158];
    capture(VIEW_CAMERA,camera,sizeof camera);capture(PLAYER,primary,sizeof primary);
    cpu->gpr[29]=0x801FFF00u;cpu->gpr[6]=0x11223344u;cpu->gpr[7]=0x55667788u;
    psx_mod_write_word(cpu->gpr[29]+0x10,0xAABBCCDDu);
    intro_scan_probe=1;intro_scan_calls=intro_scan_allocations=intro_canonical_cycles=0;
    unsigned list_bytes=0;
    while(list_bytes<0x210 && psx_mod_read_byte(0x800FA214u+list_bytes+3)!=15)list_bytes+=8;
    CHECK(list_bytes<0x210);list_bytes+=8; /* Exact original terminal record included. */
    for(unsigned cycle=0;cycle<2;++cycle) {
        guest(cpu,0x80029D18u,0,0);
        uint8_t placements[0x210];capture(0x800FA214u,placements,list_bytes);
        uint32_t root=psx_mod_read_word(0x8007349Cu),sentinel=psx_mod_read_word(0x800FA39Cu);
        guest_placement_scan(cpu,0x80029D18u);
        CHECK(psx_mod_read_word(0x8007349Cu)==root && psx_mod_read_word(0x800FA39Cu)==sentinel);
        for(unsigned i=0;i<list_bytes;++i) {
            uint32_t at=0x800FA214u+i;
            if(at<0x800FA394u || at>=0x800FA39Cu)CHECK(psx_mod_read_byte(at)==placements[i]);
        }
    }
    CHECK(intro_canonical_cycles==2 && intro_scan_calls==2 && intro_scan_allocations==1);
    CHECK(cpu->gpr[6]==0x11223344u && cpu->gpr[7]==0x55667788u && psx_mod_read_word(cpu->gpr[29]+0x10)==0xAABBCCDDu);
    CHECK(!inside && !state_track.count && !state_track.error);
    uint8_t actual[0x158];capture(PLAYER,actual,sizeof actual);CHECK(!memcmp(primary,actual,sizeof primary));
    capture(VIEW_CAMERA,actual,sizeof camera);CHECK(!memcmp(camera,actual,sizeof camera));
    cpu->gpr[4]=0x8008EF48u;cpu->gpr[31]=0x800EA3D8u;cpu->gpr[2]=99;
    CHECK(intro_guest_geometry_lifetime(cpu,0x8002CBFCu) && !cpu->gpr[2]);
    put32(p2.body+8,500u<<16);cpu->gpr[2]=99;
    CHECK(!intro_guest_geometry_lifetime(cpu,0x8002CBFCu) && cpu->gpr[2]==99);
    intro_guest_placement_scan(cpu,0x80029D18u);CHECK(intro_scan_calls==2);
    put32(p2.body+8,4900u<<16);private_draw=1;
    intro_guest_placement_scan(cpu,0x80029D18u);CHECK(intro_scan_calls==2);private_draw=0;
    psx_mod_write_word(0x8008EF48u+0x10,0x800FA384u);
    CHECK(!intro_guest_geometry_lifetime(cpu,0x8002CBFCu));
    uint8_t original=psx_mod_read_byte(0x80029D18u);psx_mod_write_byte(0x80029D18u,original^1u);
    intro_guest_placement_scan(cpu,0x80029D18u);CHECK(intro_scan_calls==2);
    psx_mod_write_byte(0x80029D18u,original);psx_mod_write_byte(PLAY+12,1);
    intro_guest_placement_scan(cpu,0x80029D18u);CHECK(intro_scan_calls==2);
    intro_scan_probe=0;
}
static void guest_amazon_support_admission(CPUState *cpu) {
    setup_agreed(cpu,0);memcpy(test_ram,original_ram,sizeof test_ram);
    memset(p2.body,0,sizeof p2.body);p2.body[0]=p2.body[4]=1;p2.body[2]=1;p2.body[5]=2;p2.body[0x5C]=32;
    put32(p2.body+8,410u<<16);put32(p2.body+12,330u<<16);
    enrolled=ready=independent_views=1;failed=private_draw=inside=zero_world=scene_owner=clear_phase=0;
    pause_owner=-1;life.status[0]=life.status[1]=MMX6_COOP_ALIVE;
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+1,0);psx_mod_write_byte(PLAY+12,1);psx_mod_write_byte(PLAY+13,0);
    psx_mod_write_byte(PLAY+0x10,0);psx_mod_write_byte(PLAY+0x1C,0);
    psx_mod_write_byte(VIEW_CAMERA+4,1);psx_mod_write_byte(VIEW_CAMERA+0x44,1);
    psx_mod_write_half(VIEW_CAMERA+0x30,160);psx_mod_write_half(VIEW_CAMERA+0x32,160);psx_mod_write_half(VIEW_CAMERA+0x2C,96);
    const uint16_t limits[]={1200,0,720,208};
    for(unsigned i=0;i<4;++i)psx_mod_write_half(VIEW_CAMERA+0x1C+i*2,limits[i]);
    psx_mod_write_word(VIEW_CAMERA+8,0);psx_mod_write_word(VIEW_CAMERA+12,224u<<16);
    psx_mod_write_word(0x800F6540u,0x00000700u);psx_mod_write_word(0x800F6544u,0x017C0220u);
    psx_mod_write_word(0x800F6548u,0x00000700u);
    const uint32_t code[][2]={{0x800EC268u,0x0C00B131u},{0x800EC280u,0xA0A20001u},
        {0x800EC030u,0x0C00B2FFu},{0x800EC044u,0x24050020u},{0x800EC048u,0x0C00B32Cu},
        {0x800EC04Cu,0x24060020u},{0x800EC060u,0x24050020u},{0x800EC064u,0x0C00B32Cu}};
    for(unsigned i=0;i<sizeof code/sizeof code[0];++i)psx_mod_write_word(code[i][0],code[i][1]);
    CHECK(amazon_support_source());
    cpu->gpr[29]=0x801FFF00u;cpu->gpr[6]=0x11223344u;cpu->gpr[7]=0x55667788u;
    psx_mod_write_word(cpu->gpr[29]+0x10,0xAABBCCDDu);
    uint8_t original[0x54];capture(VIEW_CAMERA,original,sizeof original);
    amazon_scan_probe=1;amazon_scan_calls=amazon_visibility_calls=0;
    guest_placement_scan(cpu,0x80029D18u);
    CHECK(amazon_scan_calls==1 && psx_mod_read_word(0x800734A4u)==0x800F6368u && psx_mod_read_word(0x800F6548u)==0x00000700u);
    CHECK(cpu->gpr[6]==0x11223344u && cpu->gpr[7]==0x55667788u && psx_mod_read_word(cpu->gpr[29]+0x10)==0xAABBCCDDu);
    uint8_t actual[0x54];capture(VIEW_CAMERA,actual,sizeof actual);CHECK(!memcmp(actual,original,sizeof actual));
    put32(p2.body+8,300u<<16);amazon_guest_placement_scan(cpu,0x80029D18u);CHECK(amazon_scan_calls==1);
    put32(p2.body+8,410u<<16);private_draw=1;amazon_guest_placement_scan(cpu,0x80029D18u);CHECK(amazon_scan_calls==1);private_draw=0;
    uint32_t actor=0x800C1220u;psx_mod_write_byte(actor,1);psx_mod_write_byte(actor+1,1);psx_mod_write_byte(actor+4,1);
    psx_mod_write_word(actor+0x10,0x800F6540u);psx_mod_write_word(actor+0x30,0x800F73D4u);psx_mod_write_word(actor+0x68,0x800F73ECu);
    psx_mod_write_word(actor+8,544u<<16);psx_mod_write_word(actor+12,380u<<16);psx_mod_write_byte(actor+0x14,0);
    cpu->gpr[4]=actor;cpu->gpr[31]=0x800EC038u;cpu->gpr[2]=99;
    CHECK(guest_geometry_lifetime(cpu,0x8002CBFCu) && !cpu->gpr[2]);
    put32(p2.body+8,184u<<16);cpu->gpr[2]=99;CHECK(!guest_geometry_lifetime(cpu,0x8002CBFCu) && cpu->gpr[2]==99);
    put32(p2.body+8,410u<<16);cpu->gpr[31]=0x800EC06Cu;cpu->gpr[5]=cpu->gpr[6]=32;
    CHECK(amazon_guest_support_visibility(cpu,0x8002CCB0u) && psx_mod_read_byte(actor+3)==1 && amazon_visibility_calls==2);
    capture(VIEW_CAMERA,actual,sizeof actual);CHECK(!memcmp(actual,original,sizeof actual));
    CHECK(!inside && !state_track.count && !state_track.error);
    psx_mod_write_word(actor+0x10,0x800F6548u);CHECK(!amazon_guest_support_visibility(cpu,0x8002CCB0u));
    psx_mod_write_word(0x800EC268u,0);CHECK(!amazon_support_source());
    amazon_scan_probe=0;
}
#endif
int main(int argc,char **argv) {
    const char *source=argc==2?argv[1]:getenv("MMX6_CONTENT_EXE");
    if(!source || !*source){puts("SKIP: MMX6_CONTENT_EXE must name the original USA v1.1 EXE");return 77;}
    CHECK(argc<=2);FILE *file=fopen(source,"rb");CHECK(file);
    CHECK(!fseek(file,0x800,SEEK_SET));CHECK(fread(original_ram+0x10000,1,0x7F000,file)==0x7F000);
    CHECK(fgetc(file)==EOF);fclose(file);
    CHECK(!diagnostic_tests());CPUState cpu;
    CHECK(!checkpoint_contact_protection_option && !checkpoint_contact_protection_mask() &&
        !checkpoint_contact_protection_status()); /* Normal/production compile paths included. */
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
#ifdef MMX6_COOP_MODERN_STATE
    guest_intro_geometry_admission(&cpu);
    guest_amazon_support_admission(&cpu);
#endif
    fixture=getenv("MMX6_PORTAL_SETUP_RAM");
    if(!fixture || !*fixture){puts("SKIP: MMX6_PORTAL_SETUP_RAM must name external original source materialization");return 77;}
    file=fopen(fixture,"rb");CHECK(file);CHECK(fread(header,1,4,file)==4 && !memcmp(header,"RPS1",4));
    CHECK(fread(portal_source_ram,1,sizeof portal_source_ram,file)==sizeof portal_source_ram && fgetc(file)==EOF);fclose(file);
    fixture=getenv("MMX6_NORTHPOLE_SETUP_RAM");
    if(!fixture || !*fixture){puts("SKIP: MMX6_NORTHPOLE_SETUP_RAM must name external original source materialization");return 77;}
    file=fopen(fixture,"rb");CHECK(file);CHECK(fread(header,1,4,file)==4 && !memcmp(header,"NPI1",4));
    CHECK(fread(northpole_source_ram,1,sizeof northpole_source_ram,file)==sizeof northpole_source_ram && fgetc(file)==EOF);fclose(file);
    fixture=getenv("MMX6_GATE_ENEMY_SETUP_RAM");
    if(!fixture || !*fixture){puts("SKIP: MMX6_GATE_ENEMY_SETUP_RAM must name external original source materialization");return 77;}
    file=fopen(fixture,"rb");CHECK(file);CHECK(fread(header,1,4,file)==4 && !memcmp(header,"RPS1",4));
    CHECK(fread(gate_enemy_source_ram,1,sizeof gate_enemy_source_ram,file)==sizeof gate_enemy_source_ram && fgetc(file)==EOF);fclose(file);
    fixture=getenv("MMX6_REFIGHT_SETUP_RAM");
    if(!fixture || !*fixture){puts("SKIP: MMX6_REFIGHT_SETUP_RAM must name external original refight source");return 77;}
    file=fopen(fixture,"rb");CHECK(file);CHECK(fread(header,1,4,file)==4 && !memcmp(header,"RPS1",4));
    CHECK(fread(refight_source_ram,1,sizeof refight_source_ram,file)==sizeof refight_source_ram && fgetc(file)==EOF);fclose(file);
    agreed_refight_prerequisite(&cpu);agreed_refight_distant_prerequisite(&cpu);
    agreed_refight_earned_weapons(&cpu);refight_owner_projection(&cpu);
    recycle_departure_final_order(&cpu);
    agreed_gate_enemy_prerequisite(&cpu);agreed_gate_homing_right_prerequisite(&cpu);
    /* Existing raw-disc input; read only original BIN28 sectors. */
    const char *disc=getenv("MMX6_CONTENT_DISC");
    if(!disc || !*disc){puts("SKIP: MMX6_CONTENT_DISC original raw disc required");return 77;}
    file=fopen(disc,"rb");CHECK(file);
    for(unsigned at=0;at<sizeof mounted_source_bin;) {
        unsigned n=sizeof mounted_source_bin-at;if(n>2048)n=2048;
        CHECK(!fseek(file,(long)((211185u+591u+at/2048u)*2352u+24u),SEEK_SET));
        CHECK(fread(mounted_source_bin+at,1,n,file)==n);at+=n;
    }
    fclose(file);agreed_mounted_prerequisite(&cpu);
    agreed_northpole_prerequisite(&cpu);agreed_northpole_pickup(&cpu);agreed_inami_surface_alias(&cpu);
    agreed_checkpoint_boundary(&cpu);agreed_amazon_boundary(&cpu);agreed_investigator_boundary(&cpu);
    agreed_recycle_boundary(&cpu);agreed_recycle_loaded_origin_rejections(&cpu);
    agreed_portal_prerequisite(&cpu);agreed_portal_native_heights(&cpu);
    agreed_fallen_portal_prerequisite(&cpu);
    agreed_before_doors_boundary(&cpu);
    agreed_before_explosion_boundary(&cpu);
    agreed_contact_protection(&cpu);agreed_gate_contact_protection(&cpu);
    agreed_starting_hp(&cpu);agreed_subtank_prerequisite(&cpu);agreed_turtloid_boundary(&cpu);agreed_heatnix_boundary(&cpu);agreed_magma_start_boundary(&cpu);agreed_sigma_boundary(&cpu);agreed_alternate_boundary(&cpu);agreed_gate_homing_boundary(&cpu);agreed_laser_boundary(&cpu);agreed_alternate_sequence(&cpu);
    agreed_earned_weapons(&cpu);agreed_wolfang_boundary(&cpu);agreed_ground_boundary(&cpu);agreed_fortress_cp3_boundary(&cpu);agreed_native_fatal(&cpu);agreed_mounted_native_fatal(&cpu);agreed_mounted_armor_only(&cpu);agreed_scene_fatal(&cpu);agreed_capsule_fatal(&cpu);agreed_boss_admission_fatal(&cpu);agreed_hatch_stagger(&cpu);
#endif
    puts("private checkpoint actual-plugin ordering, inventory, reset and rejection PASS");return 0;
}
