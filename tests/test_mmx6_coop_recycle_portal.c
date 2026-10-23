/* Actual plugin + real original guard bytes + bounded external native-contract
 * doubles. This validates ownership/wiring, not native portal/load gameplay.
 * Arguments are owner-supplied original EXE and raw disc; no payload bundled. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mod_plugins.h"
#undef PSX_MOD_CONSTRUCTOR
#define PSX_MOD_CONSTRUCTOR(name) static void name(void)
#include "../src/mods/mmx6_coop_plugin.c"
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
static uint8_t ram[0x200000],original[0x200000];
static unsigned probes,actions,worlds,returned,setup_calls,transition_calls;
static int refuse_admission;
static const uint32_t portal=0x8008EF48u;
static const unsigned resources[]={0x14,0x1C,0x24,0x28,0x38,0x3C,0xA8};
uint8_t psx_mod_read_byte(uint32_t a){return ram[a&0x1FFFFFu];}
uint16_t psx_mod_read_half(uint32_t a){return psx_mod_read_byte(a)|(uint16_t)psx_mod_read_byte(a+1)<<8;}
uint32_t psx_mod_read_word(uint32_t a){return psx_mod_read_half(a)|(uint32_t)psx_mod_read_half(a+2)<<16;}
void psx_mod_write_byte(uint32_t a,uint8_t v){ram[a&0x1FFFFFu]=v;}
void psx_mod_write_half(uint32_t a,uint16_t v){psx_mod_write_byte(a,(uint8_t)v);psx_mod_write_byte(a+1,(uint8_t)(v>>8));}
void psx_mod_write_word(uint32_t a,uint32_t v){for(unsigned i=0;i<4;++i)psx_mod_write_byte(a+i,(uint8_t)(v>>(i*8)));}
void psx_mod_write_code_word(uint32_t a,uint32_t v){psx_mod_write_word(a,v);}
uint16_t sio_get_pad_buttons_slot(int slot){CHECK(slot==1);return 0xFFFF;}
uint16_t mmx6_diagnostics_p2(unsigned consumer,uint16_t buttons,int contaminated){
    CHECK(consumer<6 && !buttons && !contaminated);return buttons;
}
#ifdef MMX6_COOP_INPUT_TAINT_API
void psx_session_input_taint_add(uint32_t flags){(void)flags;CHECK(0);}
#endif
int psx_mod_netplay_is_active(void){return 0;}
int psx_mod_netplay_has_state_digest(void){return 1;}
int psx_mod_texture_banks_supported(void){return 1;}
int psx_mod_local_view_scope(void){return 0;}
int psx_mod_widescreen_x_margin(void){return 0;}
void psx_mod_counter_add(const char *name,uint32_t value){(void)name;(void)value;}
void gpu_set_gp0_source(uint32_t address){(void)address;CHECK(0);}
void gpu_write_gp0(uint32_t value){(void)value;CHECK(0);}
const uint16_t *gpu_get_vram(void){CHECK(0);return NULL;}

/* Deliberately separated centers, away from boundaries. The real guest's
 * direction-sensitive box algorithm is not reimplemented by this fixture. */
static int native_contact(void){
    return !psx_mod_read_byte(PLAYER+0x61) && psx_mod_read_word(PLAYER+0x54) &&
        (int16_t)psx_mod_read_half(PLAYER+10)==1540;
}
static void native_action(CPUState *cpu){
    ++actions;
    if(!refuse_admission && native_contact()) {
        psx_mod_write_byte(portal+5,2);psx_mod_write_byte(portal+6,0);
        psx_mod_write_half(portal+0x84,psx_mod_read_half(PLAYER+10));
    }
    cpu->gpr[2]=0x12345678;
}
static void native_portal_world(void){
    CHECK(zero_world && inside && stage_call && psx_mod_read_byte(PLAYER+2)==1);
    ++worlds;
    /* 20C60 executes the native player before the enemy update20C78.
     * Source3B870 receives41h: PLAY1C=1 and body phase3 before restore. */
    if(psx_mod_read_byte(PLAY+0x0F)==0x41) {
        psx_mod_write_byte(PLAY+0x1C,1);psx_mod_write_byte(PLAYER+4,3);
    }
    unsigned phase=psx_mod_read_byte(portal+6);
    if(!phase) {
        ++setup_calls;
        CHECK(psx_mod_read_word(PLAYER+0x68)==0x801EF123u);
        psx_mod_write_word(portal+0x88,psx_mod_read_word(PLAYER+0x68));
        psx_mod_write_word(PLAYER+0x68,0);psx_mod_write_byte(PLAYER+5,2);
        const unsigned flags[]={0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x19};
        for(unsigned i=0;i<sizeof flags/sizeof flags[0];++i)psx_mod_write_byte(PLAY+flags[i],2);
        psx_mod_write_byte(portal+6,1);psx_mod_write_half(portal+0x7C,0);
    } else if(phase==1) {
        unsigned tick=psx_mod_read_half(portal+0x7C)+1;
        psx_mod_write_half(portal+0x7C,(uint16_t)tick);
        if(tick>=29) {
            ++transition_calls;psx_mod_write_byte(PLAY+0x0F,0x41);
            psx_mod_write_byte(portal+6,2);
        }
    } else if(phase==2) {
        CHECK(psx_mod_read_byte(PLAYER+4)==3 && psx_mod_read_byte(PLAY+0x1C));
        psx_mod_write_word(PLAYER+0x68,psx_mod_read_word(portal+0x88));
        const unsigned flags[]={0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,0x19};
        for(unsigned i=0;i<sizeof flags/sizeof flags[0];++i)psx_mod_write_byte(PLAY+flags[i],0);
        psx_mod_write_byte(portal+6,3);
    }
}
void psx_dispatch_call(CPUState *cpu,uint32_t address,uint32_t ret){
    (void)ret;
    if(address==0x8002D654u) {
        ++probes;CHECK(scene_call && cpu->gpr[4]==portal && cpu->gpr[5]==PLAYER);
        CHECK(state_track.count>=2);
#ifdef MMX6_COOP_MODERN_STATE
        uint32_t digest=state_digest();scene_call=0;
        CHECK(state_digest()!=digest);scene_call=1;CHECK(!snapshot_ready());
#endif
        cpu->gpr[2]=(uint32_t)native_contact();return;
    }
    if(address==0x800EC780u) {
        CHECK(scene_call && inside && zero_projected);
        CHECK(!psx_mod_try_function_replacement(cpu,address));
        CHECK(psx_mod_read_byte(PLAYER+2)==1 && psx_mod_read_word(SCRATCH+0x1C)==assembly);
        native_action(cpu);return;
    }
    if(address==0x8001E9ECu) {
        if(psx_mod_read_byte(PLAY+1)==1) {
            /* Native1EB48 fade-idle ->1E32C selects next major8 and returns;
             * it does not call new-stage initialization on this C stack. */
            CHECK(inside && zero_world && psx_mod_read_byte(PLAYER+4)==3);
            psx_mod_write_byte(PLAY,8);psx_mod_write_byte(PLAY+1,0);
            psx_mod_write_byte(PLAY+12,20);psx_mod_write_byte(PLAY+13,1);
            psx_mod_write_byte(PLAY+0x0F,0);return;
        }
        native_portal_world();return;
    }
    if(address==0x8003A980u || address==0x8003B954u)return;
    if(address==0x8003BA04u) {
        if(cpu->gpr[5]==1)++returned;
        CHECK(cpu->gpr[5]==3);return; /* No old-stage inbound. */
    }
    if(address==0x8003674Cu) {psx_mod_write_byte(PLAYER+4,3);return;}
    CHECK(0);
}
static void load_original(const char *exe_path,const char *disc_path){
    FILE *exe=fopen(exe_path,"rb");CHECK(exe);uint8_t header[2048];
    CHECK(fread(header,1,sizeof header,exe)==sizeof header && !memcmp(header,"PS-X EXE",8));
    CHECK(le32(header+0x18)==0x80010000u && le32(header+0x1C)==0x7F000u);
    CHECK(fread(original+0x10000,1,0x7F000,exe)==0x7F000 && fgetc(exe)==EOF);CHECK(!fclose(exe));
    psx_sha256_ctx hash;uint8_t digest[32];char actual[65];static const char hex[]="0123456789abcdef";
    psx_sha256_init(&hash);psx_sha256_update(&hash,header,sizeof header);
    psx_sha256_update(&hash,original+0x10000,0x7F000);psx_sha256_final(&hash,digest);
    for(unsigned i=0;i<32;++i){actual[i*2]=hex[digest[i]>>4];actual[i*2+1]=hex[digest[i]&15];}actual[64]=0;
    CHECK(!strcmp(actual,"dd4bea378ac7ad5266d9b44f779097f3bbfe473eac31703566dec5495e6a1046"));
    FILE *disc=fopen(disc_path,"rb");CHECK(disc);
    /* Only selected member6, bounded by the frozen archive descriptor. */
    for(unsigned at=0;at<42944;at+=2048) {
        unsigned count=42944-at;if(count>2048)count=2048;
        CHECK(!fseek(disc,(long)(211185u+153u+at/2048u)*2352+24,SEEK_SET));
        CHECK(fread(original+0xE9860+at,1,count,disc)==count);
    }
    CHECK(!fclose(disc));
    psx_sha256_compute(original+0xE9860,42944,digest);
    for(unsigned i=0;i<32;++i){actual[i*2]=hex[digest[i]>>4];actual[i*2+1]=hex[digest[i]&15];}
    CHECK(!strcmp(actual,"c7b195e3e3968ebbd6c177cf023e47b35a9a816382c9b54ca157a80b393468f5"));
}
static void setup(CPUState *cpu){
    memcpy(ram,original,sizeof ram);memset(&p2,0,sizeof p2);memset(&p1,0,sizeof p1);
    memset(cpu,0,sizeof *cpu);mmx6_coop_lifecycle_init(&life);
    state_track.count=state_track.error=0;inside=scene_call=zero_world=zero_projected=failed=0;
    ready=enrolled=stage_call=1;scene_owner=scene_phase=0;pause_owner=-1;
    probes=actions=worlds=returned=setup_calls=transition_calls=0;refuse_admission=0;
    assets=0x9F100000u;assembly=0x9F120000u;palette_source=0x9F124000u;active_palette=0x9F128000u;
    menu_memory=0x9F140000u;menu_assembly=0x9F180000u;diagnostic=0x9F080000u;
    memset(ram+(diagnostic&0x1FFFFFu),0,0x2000);
    previous_input=p2_edges=0;p2_start_previous=zero_menu_loaded=0;frame_count=0;
    for(unsigned i=0;i<7;++i)psx_mod_write_word(SCRATCH+resources[i],0x80100000u+i*0x1000u);
    memset(zero_overlay,0x5A,sizeof zero_overlay);
    memset(ram+(OVERLAY&0x1FFFFFu),0x11,OVERLAY_SIZE);
    memset(p2.shots,0x22,sizeof p2.shots);memset(p2.trails,0x33,sizeof p2.trails);memset(p2.effects,0x44,sizeof p2.effects);
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+1,0);psx_mod_write_byte(PLAY+12,4);
    psx_mod_write_byte(PLAY+13,0);psx_mod_write_byte(PLAY+0x0F,0);
    psx_mod_write_byte(PLAY+0x10,0);psx_mod_write_byte(PLAY+0x1C,0);psx_mod_write_byte(0x80097424u,0);
    psx_mod_write_byte(PLAYER,1);psx_mod_write_byte(PLAYER+2,0);psx_mod_write_byte(PLAYER+3,1);
    psx_mod_write_byte(PLAYER+4,1);psx_mod_write_byte(PLAYER+5,2);psx_mod_write_byte(PLAYER+0x5C,32);
    psx_mod_write_word(PLAYER+8,1200u<<16);psx_mod_write_word(PLAYER+12,1584u<<16);
    psx_mod_write_word(PLAYER+0x54,0x80075B9Cu);psx_mod_write_word(PLAYER+0x68,0x801F1234u);
    p2.body[0]=p2.body[2]=p2.body[3]=p2.body[4]=1;p2.body[5]=2;p2.body[0x5C]=24;
    put32(p2.body+8,1540u<<16);put32(p2.body+12,1584u<<16);
    put32(p2.body+0x54,0x80075B9Cu);put32(p2.body+0x68,0x801EF123u);
    psx_mod_write_byte(portal,0x41);psx_mod_write_byte(portal+1,0x1C);psx_mod_write_byte(portal+2,1);
    psx_mod_write_byte(portal+4,1);psx_mod_write_byte(portal+5,1);psx_mod_write_byte(portal+6,0);
    psx_mod_write_word(portal+0x10,0x800F2B0Cu);psx_mod_write_word(portal+0x50,0x800F38BCu);
    psx_mod_write_word(portal+0x54,0x800F38C0u);psx_mod_write_word(portal+0x68,0x800F38B8u);
    cpu->gpr[4]=portal;cpu->gpr[31]=0x800EC70Cu;
    psx_mod_clear_function_replacements();CHECK(psx_mod_set_function_replacement(0x800EC780,recycle_portal_contact));
    CHECK(recycle_portal_source());
}
static void rejected(CPUState *cpu){
    uint8_t *before=malloc(sizeof ram);CHECK(before);memcpy(before,ram,sizeof ram);
    CHECK(!recycle_portal_contact(cpu,0x800EC780u));
    CHECK(!probes && !actions && !scene_owner && !memcmp(before,ram,sizeof ram));free(before);
}
int main(int argc,char **argv){
    CHECK(argc==3);load_original(argv[1],argv[2]);CPUState cpu;setup(&cpu);
    native_action(&cpu);CHECK(psx_mod_read_byte(portal+5)==1);actions=0; /* Native P1-only negative control. */
    uint8_t body[sizeof p2.body];capture(PLAYER,body,sizeof body);PlayerContext private_before=p2;
    CHECK(psx_mod_try_function_replacement(&cpu,0x800EC780));
    CHECK(probes==2 && actions==1 && cpu.gpr[2]==0x12345678 && cpu.pc==cpu.gpr[31]);
    CHECK(psx_mod_read_byte(portal+5)==2 && psx_mod_read_half(portal+0x84)==1540);
    CHECK(!memcmp(body,ram+(PLAYER&0x1FFFFF),sizeof body));
    CHECK(!memcmp(&private_before,&p2,sizeof p2));
    CHECK(psx_mod_read_byte(OVERLAY)==0x11 && psx_mod_read_byte(OVERLAY+OVERLAY_SIZE-1)==0x11);
    CHECK(scene_owner==2 && scene_phase==1 && !scene_call && !inside && !zero_projected && !state_track.count);
    CHECK(!psx_mod_read_byte(PLAY+0x0F) && !psx_mod_read_byte(PLAY+0x10)); /* Native deferred writes only. */
    for(unsigned i=0;i<7;++i)CHECK(psx_mod_read_word(SCRATCH+resources[i])==0x80100000u+i*0x1000u);
#ifdef MMX6_COOP_MODERN_STATE
    HostState host;state_capture(&host);CHECK(host.owner==2 && host.scene_phase==1);
#endif
    scene_tick(&cpu);CHECK(scene_phase==2 && !returned);stage_call=0;
    for(unsigned i=0;i<31;++i){CHECK(stage_tick(&cpu,0x8001E9EC));CHECK(!returned && scene_phase<=3);}
    CHECK(worlds==31 && setup_calls==1 && transition_calls==1 && scene_owner==2);
    CHECK(p2.body[4]==3 && le32(p2.body+0x68)==0x801EF123u);
    CHECK(psx_mod_read_word(PLAYER+0x68)==0x801F1234u);
    CHECK(psx_mod_read_byte(PLAY+0x0F)==0x41 && psx_mod_read_byte(PLAY+0x1C));
    psx_mod_write_byte(PLAY+1,1);CHECK(stage_tick(&cpu,0x8001E9EC));
    CHECK(!enrolled && scene_owner==2 && !inside && !zero_projected && !zero_world && !returned);
    CHECK(worlds==31 && psx_mod_read_byte(PLAY)==8 && psx_mod_read_byte(PLAY+12)==20 && psx_mod_read_byte(PLAY+13)==1);
    native_player_init(&cpu,0x8003BD24);CHECK(!scene_owner && !scene_phase && !enrolled);
    setup(&cpu);psx_mod_write_half(PLAYER+10,1540);CHECK(!recycle_portal_contact(&cpu,0x800EC780));
    CHECK(probes==1 && !actions && !scene_owner);native_action(&cpu);CHECK(actions==1); /* P1 tie. */
    setup(&cpu);put32(p2.body+8,1400u<<16);CHECK(!recycle_portal_contact(&cpu,0x800EC780));
    CHECK(probes==2 && !actions && !scene_owner && !scene_call && !inside);
    setup(&cpu);refuse_admission=1;CHECK(recycle_portal_contact(&cpu,0x800EC780));
    CHECK(actions==1 && !scene_owner); /* Probe success alone never arms ownership. */
    setup(&cpu);p2.body[0x61]=1;CHECK(!recycle_portal_contact(&cpu,0x800EC780));
    CHECK(probes==2 && !actions && !scene_owner && !scene_call && !inside);
    const unsigned excluded[]={MMX6_COOP_ABSENT,MMX6_COOP_DYING,MMX6_COOP_FALLEN,MMX6_COOP_JOINING,MMX6_COOP_LEAVING};
    for(unsigned seat=0;seat<2;++seat)for(unsigned i=0;i<sizeof excluded/sizeof excluded[0];++i){setup(&cpu);life.status[seat]=excluded[i];rejected(&cpu);}
    const unsigned body_offsets[]={0,3,4,0x5C,0x7A,0xD0,0xD4};
    for(unsigned i=0;i<sizeof body_offsets/sizeof body_offsets[0];++i){setup(&cpu);p2.body[body_offsets[i]]=i<4?0:1;rejected(&cpu);}
    const unsigned play_offsets[]={1,13,0x0F,0x10,0x1C};
    for(unsigned i=0;i<sizeof play_offsets/sizeof play_offsets[0];++i){setup(&cpu);psx_mod_write_byte(PLAY+play_offsets[i],1);rejected(&cpu);}
    for(unsigned i=0;i<sizeof recycle_portal_code/sizeof recycle_portal_code[0];++i){setup(&cpu);psx_mod_write_byte(recycle_portal_code[i].first,psx_mod_read_byte(recycle_portal_code[i].first)^1);rejected(&cpu);}
    setup(&cpu);cpu.gpr[31]++;rejected(&cpu);setup(&cpu);cpu.gpr[4]++;rejected(&cpu);
    setup(&cpu);psx_mod_write_byte(PLAY+12,5);rejected(&cpu);
    setup(&cpu);psx_mod_write_word(portal+0x10,0x800F2B04);rejected(&cpu);
    setup(&cpu);psx_mod_write_byte(portal+2,2);rejected(&cpu);
    setup(&cpu);scene_owner=1;CHECK(!recycle_portal_contact(&cpu,0x800EC780) && !probes);
    int *blocked[]={&inside,&zero_world,&zero_projected,&failed,&scene_call};
    for(unsigned i=0;i<sizeof blocked/sizeof blocked[0];++i){setup(&cpu);*blocked[i]=1;CHECK(!recycle_portal_contact(&cpu,0x800EC780) && !probes);}
    setup(&cpu);stage_call=0;rejected(&cpu);setup(&cpu);ready=0;rejected(&cpu);
    setup(&cpu);enrolled=0;rejected(&cpu);setup(&cpu);scene_phase=1;rejected(&cpu);
    setup(&cpu);p2.body[2]=0;rejected(&cpu);setup(&cpu);psx_mod_write_byte(PLAYER+2,1);rejected(&cpu);
    for(unsigned flags=0;flags<256;++flags){setup(&cpu);psx_mod_write_byte(0x800F2B0Cu,(uint8_t)flags);CHECK(recycle_portal_source()==(flags<=1));}
    for(unsigned offset=1;offset<8;++offset){setup(&cpu);psx_mod_write_byte(0x800F2B0Cu+offset,psx_mod_read_byte(0x800F2B0Cu+offset)^1);rejected(&cpu);}
    puts("Recycle portal actual-plugin guarded contact, deferred owner and single-world fixture PASS; native gameplay unverified");return 0;
}
