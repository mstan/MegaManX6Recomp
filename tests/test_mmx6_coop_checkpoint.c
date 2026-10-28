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
static uint8_t original_ram[0x200000],before_ram[0x200000];
static uint16_t checkpoint_vram[1024*512];
static unsigned before_doors_probe,equipment_probe,equipment_calls;
static unsigned refusal_logs;
static char refusal_log[512];
static void checkpoint_test_refusal_log(const char *format,...) {
    va_list args;va_start(args,format);
    CHECK(vsnprintf(refusal_log,sizeof refusal_log,format,args)>0);
    va_end(args);++refusal_logs;
}
static int checkpoint_native_model(CPUState *cpu,uint32_t target,uint32_t ret) {
    (void)ret;
    if(equipment_probe && target==0x8003D718u) {
        /* Typed external native contract only: source3D718 copies these
         * fields for admitted form1/5; this is not native gameplay execution. */
        CHECK(cpu->gpr[4]==PLAYER && !cpu->gpr[5] && psx_mod_read_byte(PLAY+0x60)==255);
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
static uint8_t portal_source_ram[0x200000];
static const char *test_lab_option="off";
static const char *test_lab_contact_option="off";
static const char *test_lab_hp_option[2]={"off","off"};
static const char *test_lab_earned_option="off";
static unsigned test_lab_ready=1,test_lab_failed,test_lab_selected=1;
static PSXHostSelection test_lab_profile;
int psx_mod_option_value(const char *package,const char *feature,const char *option,char *out,uint32_t size) {
    CHECK(!strcmp(package,"mmx6.local-coop") && !strcmp(feature,"prototype"));
    CHECK(!strcmp(option,"lab_checkpoint") || !strcmp(option,"lab_contact_protection") || !strcmp(option,"lab_earned_weapons") ||
        !strcmp(option,"lab_starting_hp_p1") || !strcmp(option,"lab_starting_hp_p2"));
    const char *value=!strcmp(option,"lab_checkpoint")?test_lab_option:
        !strcmp(option,"lab_contact_protection")?test_lab_contact_option:
        !strcmp(option,"lab_earned_weapons")?test_lab_earned_option:
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
static void agreed_starting_hp(CPUState *cpu) {
    CHECK(!checkpoint_starting_hp_parse("off") && checkpoint_starting_hp_parse("1")==1 && checkpoint_starting_hp_parse("32")==32);
    const char *invalid[]={"0","00","01","33","-1","+1","1x","","99999999999999999999999999"};
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
        psx_mod_write_byte(PLAY+12,20);life.status[0]=MMX6_COOP_FALLEN;checkpoint_complete();
        life.status[0]=MMX6_COOP_ALIVE;checkpoint_complete();
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
static void setup_earned(CPUState *cpu,int online) {
    test_lab_earned_option="all";setup_agreed(cpu,online);equipment_probe=1;equipment_calls=0;
    cpu->gpr[29]=0x801FFF00u;
    psx_mod_write_byte(PLAY+0x38,0);psx_mod_write_byte(PLAY+0x5E,1);psx_mod_write_byte(PLAY+0x60,0);
    psx_mod_write_word(PLAY+0x74,0x00102030u);psx_mod_write_word(PLAY+0x78,0x00405060u);
    psx_mod_write_byte(PLAYER+2,0);p2.body[2]=1;
    psx_mod_write_byte(PLAYER+0xE7,1);p2.body[0xE7]=5;
    psx_mod_write_word(PLAYER+0xEC,0x00102030u);put32(p2.body+0xEC,0x00405060u);
    psx_mod_write_byte(PLAYER+0xC9,0);p2.body[0xC9]=0;
}
static void agreed_earned_weapons(CPUState *cpu) {
    CHECK(!checkpoint_earned_weapons_option && !checkpoint_earned_weapons_applied);
    for(int online=0;online<=1;++online) {
        setup_earned(cpu,online);CHECK(checkpoint_equipment_source() && checkpoint_earned_weapons_option);
        uint8_t primary[sizeof p2.body];capture(PLAYER,primary,sizeof primary);PlayerContext zero=p2;CPUState registers=*cpu;
        CHECK(checkpoint_lab_boundary(cpu,6) && checkpoint_pending.phase==1 && psx_mod_read_byte(PLAY)==8);
        CHECK(equipment_calls==2 && checkpoint_earned_weapons_applied && !checkpoint_earned_weapons_reason);
        CHECK(psx_mod_read_byte(PLAY+0x60)==255 && psx_mod_read_byte(PLAYER+0xC9)==255 && p2.body[0xC9]==255);
        primary[0xC9]=zero.body[0xC9]=255;
        uint8_t after[sizeof primary];capture(PLAYER,after,sizeof after);
        CHECK(!memcmp(primary,after,sizeof after) && !memcmp(&zero,&p2,sizeof zero) && !memcmp(&registers,cpu,sizeof registers));
        CHECK(checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6) && equipment_calls==2);
        mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);psx_mod_write_byte(PLAY,10);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_earned_weapons_applied && equipment_calls==2);

#ifdef MMX6_COOP_MODERN_STATE
        HostState saved;state_capture(&saved);CHECK(saved.earned_applied==1 && saved.earned_reason==0);
        uint8_t encoded[65536];StateIO write={STATE_WRITE,1,encoded,NULL,sizeof encoded,0,0};state_core(&write,&saved);CHECK(write.ok);
        HostState loaded={0};StateIO read={STATE_READ,1,NULL,encoded,write.pos,0,0};state_core(&read,&loaded);CHECK(read.ok && loaded.earned_applied==1);
        checkpoint_earned_weapons_applied=0;state_commit(&loaded);CHECK(checkpoint_earned_weapons_applied==1);
        loaded.earned_applied=2;write=(StateIO){STATE_COUNT,1,NULL,NULL,0,0,0};state_core(&write,&loaded);CHECK(!write.ok);

#endif
        checkpoint_reset();CHECK(!checkpoint_earned_weapons_applied && !checkpoint_earned_weapons_reason);
    }
    for(unsigned bad=0;bad<7;++bad) {
        setup_earned(cpu,1);
        if(bad==0)test_lab_ready=0;
        if(bad==1)psx_mod_write_byte(0x8003D718u,psx_mod_read_byte(0x8003D718u)^1);
        if(bad==2)psx_mod_write_byte(PLAYER+0xE7,2);
        if(bad==3)p2.body[0xE7]=1;
        if(bad==4)psx_mod_write_byte(PLAY+0x5E,2);
        if(bad==5)cpu->gpr[29]=0;
        if(bad==6)cpu->gpr[29]|=1;
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !equipment_calls && !checkpoint_earned_weapons_applied);
        CHECK(!psx_mod_read_byte(PLAY+0x60) && !psx_mod_read_byte(PLAYER+0xC9) && !p2.body[0xC9] && !checkpoint_test_taint);
    }
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
    /* Configured destination alone must never race the parent's normal intro
     * P2-walk/P1-jump baseline. Only a fresh accepted native chord arms it. */
    setup_agreed(cpu,1);CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_pending.phase && !checkpoint_lab_state);
    CHECK(!checkpoint_lab_boundary(cpu,2) && !checkpoint_lab_boundary(cpu,4) && !checkpoint_lab_boundary(cpu,7) && !checkpoint_lab_state);
    checkpoint_lab_option=0;memcpy(before_ram,test_ram,sizeof test_ram);
    CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_lab_state && !memcmp(before_ram,test_ram,sizeof test_ram));
    for(int online=0;online<=1;++online) {
        setup_agreed(cpu,online);PlayerContext body=p2;memcpy(before_ram,test_ram,sizeof test_ram);
        pause_owner=1;CHECK(!checkpoint_lab_boundary(cpu,6));
        CHECK(checkpoint_lab_state==CHECKPOINT_LAB_ARMED && !checkpoint_pending.phase && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram));
        CHECK(psx_mod_read_byte(diagnostic+0xBE)==1);
        CHECK(!checkpoint_lab_boundary(cpu,0) && checkpoint_lab_state==CHECKPOINT_LAB_ARMED);
        pause_owner=-1;p2.body[5]=7;CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_pending.phase);
        p2.body[5]=2;CHECK(checkpoint_lab_boundary(cpu,0));
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
        CHECK(!checkpoint_lab_boundary(cpu,0) && !checkpoint_lab_boundary(cpu,6));
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
        CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !checkpoint_test_taint);
        CHECK(psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_REJECTED && psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_FORBIDDEN);
    }
    setup_agreed(cpu,1);psx_mod_write_byte(checkpoint_code[0].first,0);
    CHECK(!checkpoint_lab_boundary(cpu,6) && !checkpoint_pending.phase && !checkpoint_test_taint);
    CHECK(psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE);
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
static void setup_portal_prerequisite(CPUState *cpu,int online) {
    setup_agreed(cpu,online);test_lab_option="recycle_portal_cp2";checkpoint_reset();
    CHECK(checkpoint_lab_option==7 && checkpoint_lab_index()==23 && checkpoint_lab_nonce()==0x4C525032u);
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
    CHECK(checkpoint_portal_assets(&meta,&desc) && checkpoint_portal_ground(meta,desc));
}
static void portal_test_native_ready(void) {
    portal_test_body(0,1506,1595);portal_test_body(1,1506,1594);
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
static void agreed_portal_prerequisite(CPUState *cpu) {
    for(int online=0;online<=1;++online) {
        setup_portal_prerequisite(cpu,online);p2.body[5]=1; /* Native guest beam has not finished. */
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;CPUState registers=*cpu;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls);
        CHECK(!memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
        p2.body[5]=2;partner=p2;put32(partner.body+8,1506u<<16);put32(partner.body+0x18,1506u<<16);
        put32(partner.body+12,1593u<<16);put32(partner.body+0x1C,1593u<<16);
        const unsigned positions[]={8,0x18,12,0x1C};
        for(unsigned i=0;i<4;++i){uint32_t value=(i<2?1506u:1593u)<<16;
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
            setup_portal_prerequisite(cpu,online);psx_mod_write_byte(corrupt[i],psx_mod_read_byte(corrupt[i])^0x40);
            memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;
            CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
                psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE &&
                !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
        }
    }
    test_lab_option="off";checkpoint_reset();
}
static void agreed_recycle_loaded_origin_rejections(CPUState *cpu) {
    const char *options[]={"intro_cp2","amazon_cp0","amazon_cp2","intro_before_doors",
        "intro_before_explosion","recycle_cp2","recycle_portal_cp2"};
    const uint8_t origins[][3]={{4,0,0},{4,0,1},{4,1,0},{4,1,2},{4,2,0},{3,0,0},{0,1,0},{0,0,1}};
    for(unsigned option=0;option<sizeof options/sizeof options[0];++option)for(unsigned i=0;i<sizeof origins/sizeof origins[0];++i) {
        if(option==5 && i==0)continue; /* The one new accepted origin. */
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
    /* Loaded origin retains transient safety waits, then consumes the same
     * chord once only when native bodies and callback context settle. */
    for(unsigned unsafe=0;unsafe<7;++unsafe) {
        setup_agreed(cpu,1);test_lab_option="recycle_cp2";checkpoint_reset();psx_mod_write_byte(PLAY+12,4);
        if(unsafe==0)pause_owner=0;if(unsafe==1)private_draw=1;if(unsafe==2)zero_projected=1;
        if(unsafe==3)psx_mod_write_byte(PLAYER+5,7);if(unsafe==4)p2.body[0x67]=1;
        if(unsafe==5)state_track.count=1;if(unsafe==6)scene_owner=1;
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext body=p2;
        CHECK(!checkpoint_lab_boundary(cpu,6) && checkpoint_lab_state==CHECKPOINT_LAB_ARMED &&
            !checkpoint_pending.phase && !checkpoint_test_taint && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&body,&p2,sizeof body));
        pause_owner=-1;private_draw=zero_projected=scene_owner=0;state_track.count=0;
        psx_mod_write_byte(PLAYER+5,2);p2.body[0x67]=0;
        CHECK(checkpoint_lab_boundary(cpu,0) && checkpoint_pending.index==27 &&
            checkpoint_pending.nonce==CHECKPOINT_LAB_RECYCLE_NONCE);
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
    fixture=getenv("MMX6_PORTAL_SETUP_RAM");
    if(!fixture || !*fixture){puts("SKIP: MMX6_PORTAL_SETUP_RAM must name external original source materialization");return 77;}
    file=fopen(fixture,"rb");CHECK(file);CHECK(fread(header,1,4,file)==4 && !memcmp(header,"RPS1",4));
    CHECK(fread(portal_source_ram,1,sizeof portal_source_ram,file)==sizeof portal_source_ram && fgetc(file)==EOF);fclose(file);
    agreed_checkpoint_boundary(&cpu);agreed_amazon_boundary(&cpu);agreed_investigator_boundary(&cpu);
    agreed_recycle_boundary(&cpu);agreed_recycle_loaded_origin_rejections(&cpu);
    agreed_portal_prerequisite(&cpu);
    agreed_before_doors_boundary(&cpu);
    agreed_before_explosion_boundary(&cpu);
    agreed_contact_protection(&cpu);
    agreed_starting_hp(&cpu);agreed_turtloid_boundary(&cpu);
    agreed_earned_weapons(&cpu);
#endif
    puts("private checkpoint actual-plugin ordering, inventory, reset and rejection PASS");return 0;
}
