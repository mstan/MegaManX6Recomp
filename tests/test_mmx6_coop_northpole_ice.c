/* The actual plugin, isolated native-call contracts, and original code guards.
 * Native gameplay, collision geometry and artwork still require runtime QA. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mod_plugins.h"
#undef PSX_MOD_CONSTRUCTOR
#define PSX_MOD_CONSTRUCTOR(name) static void name(void)
#include "../src/mods/mmx6_coop_plugin.c"
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
static uint8_t ram[0x200000],before[0x200000];
static const uint32_t parent_actor=0x800C1220u,child_actor=0x800C12C4u;
static unsigned prefixes,contacts,effects,terrain_calls,contact_bits=8,terrain_ground=8,retire_in_prefix;
uint8_t psx_mod_read_byte(uint32_t a){return ram[a&0x1FFFFF];}
uint16_t psx_mod_read_half(uint32_t a){return psx_mod_read_byte(a)|((uint16_t)psx_mod_read_byte(a+1)<<8);}
uint32_t psx_mod_read_word(uint32_t a){return psx_mod_read_half(a)|((uint32_t)psx_mod_read_half(a+2)<<16);}
void psx_mod_write_byte(uint32_t a,uint8_t v){ram[a&0x1FFFFF]=v;}
void psx_mod_write_half(uint32_t a,uint16_t v){psx_mod_write_byte(a,(uint8_t)v);psx_mod_write_byte(a+1,(uint8_t)(v>>8));}
void psx_mod_write_word(uint32_t a,uint32_t v){for(unsigned i=0;i<4;++i)psx_mod_write_byte(a+i,(uint8_t)(v>>(i*8)));}
static void native_gate(uint32_t actor){
    int second=(int16_t)psx_mod_read_half(actor+10)>=5312;
    if((int16_t)psx_mod_read_half(PLAYER+10)>=(second?5345:5137) &&
       (int16_t)psx_mod_read_half(PLAYER+14)>=(second?1489:1473)) {
        psx_mod_write_half(0x8009721C,second?5328:4976);
        psx_mod_write_half(0x8009721E,second?5328:4976);psx_mod_write_byte(actor+6,9);
    }
}
void psx_dispatch_call(CPUState *cpu,uint32_t address,uint32_t ret){
    (void)ret;
    if(address==0x8002BFD0){
        CHECK(solid_allocate_call);memset(ram+(child_actor&0x1FFFFF),0,0xA4);
        cpu->gpr[2]=child_actor;return;
    }
    if(address==0x800ED150){CHECK(target_projection_call);CHECK(!northpole_ice_admission(cpu,address));native_gate(cpu->gpr[4]);}
    else if(address==0x800EBF18){
        CHECK(target_projection_call && !inside && !northpole_ice_live(cpu,address));
        CHECK(psx_mod_read_half(PLAYER+10)==5080 && psx_mod_read_byte(PLAYER+2)==0);
        CHECK(psx_mod_read_byte(0x800950A0)==0xA5); /* Canonical attack pool during original prefix. */
        ++prefixes;psx_mod_write_byte(0x800950A1,(uint8_t)prefixes);
        psx_mod_write_byte(child_actor+0x84,(uint8_t)(psx_mod_read_byte(child_actor+0x84)+1));
        if(retire_in_prefix)psx_mod_write_byte(child_actor+4,2);
    }else if(address==0x80031DA8){
        CHECK(inside && psx_mod_read_byte(PLAYER+2)==1 && !psx_mod_read_byte(0x800CD340));
        CHECK(psx_mod_read_half(PLAYER+10)==5160 && psx_mod_read_byte(child_actor+0x72)==2);
        ++contacts;psx_mod_write_half(PLAYER+10,5161);
        psx_mod_write_byte(child_actor+0x72,(uint8_t)contact_bits);psx_mod_write_byte(child_actor+0x76,3);
    }else if(address==0x8002F288){
        ++terrain_calls;CHECK(cpu->gpr[4]==0x800F76EC && psx_mod_read_byte(0x800F76EE)==1);
        CHECK(psx_mod_read_half(0x800F76F6)==5161);psx_mod_write_byte(0x800F775C,(uint8_t)terrain_ground);
    }else if(address==0x800477E4){
        ++effects;CHECK(cpu->gpr[4]==3 && cpu->gpr[5]==0x800F6B8C && cpu->gpr[6]==child_actor);
    }else CHECK(0);
    cpu->gpr[2]=0x12345678;
}
static void setup(CPUState *cpu){
    memset(ram,0,sizeof ram);memset(&p2,0,sizeof p2);memset(cpu,0,sizeof *cpu);
    memset(zero_solid_contacts,0,sizeof zero_solid_contacts);mmx6_coop_lifecycle_init(&life);
    ready=enrolled=1;failed=inside=zero_world=zero_projected=private_draw=target_projection_call=0;
    scene_owner=scene_phase=0;state_track.count=state_track.error=0;
    prefixes=contacts=effects=terrain_calls=retire_in_prefix=0;contact_bits=8;terrain_ground=8;
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+12,2);
    psx_mod_write_byte(PLAYER+3,1);psx_mod_write_byte(PLAYER+4,1);psx_mod_write_byte(PLAYER+5,2);
    psx_mod_write_byte(PLAYER+0x5C,32);psx_mod_write_word(PLAYER+8,(5080u<<16)|0x1234);
    psx_mod_write_word(PLAYER+12,(1480u<<16)|0x5678);
    p2.body[2]=p2.body[3]=p2.body[4]=1;p2.body[5]=2;p2.body[0x5C]=32;
    put32(p2.body+8,5160u<<16);put32(p2.body+12,1480u<<16);
    psx_mod_write_byte(parent_actor,0x51);psx_mod_write_byte(parent_actor+1,7);
    psx_mod_write_byte(parent_actor+4,1);psx_mod_write_byte(parent_actor+6,8);
    psx_mod_write_half(parent_actor+10,4992);psx_mod_write_half(parent_actor+14,1376);
    psx_mod_write_word(SCRATCH+0x94,0x800F6554);psx_mod_write_word(0x800F6570,0x800ECDE8);
    psx_mod_write_word(0x800F6BA0,0x800EBF18);psx_mod_write_word(0x800F6BF8,0x800ED150);
    const char *path=getenv("MMX6_NORTHPOLE_MEMBER");CHECK(path);FILE *f=fopen(path,"rb");CHECK(f);
    const unsigned spans[][2]={{0x800EBF18,0x2C4},{0x800ED150,0x9C}};
    for(unsigned i=0;i<2;++i){CHECK(!fseek(f,(long)(spans[i][0]-0x800E9860),SEEK_SET));
        CHECK(fread(ram+(spans[i][0]&0x1FFFFF),1,spans[i][1],f)==spans[i][1]);}
    CHECK(!fclose(f));CHECK(northpole_ice_source());cpu->gpr[4]=parent_actor;
}
static void child(CPUState *cpu){
    setup(cpu);cpu->gpr[4]=child_actor;psx_mod_write_byte(parent_actor+6,9);
    psx_mod_write_byte(parent_actor+7,2);psx_mod_write_byte(parent_actor+0x89,1);
    psx_mod_write_byte(child_actor,0x41);psx_mod_write_byte(child_actor+1,7);
    psx_mod_write_byte(child_actor+2,12);psx_mod_write_byte(child_actor+3,1);
    psx_mod_write_byte(child_actor+4,1);psx_mod_write_byte(child_actor+6,6);psx_mod_write_byte(child_actor+7,3);
    psx_mod_write_half(child_actor+10,5160);psx_mod_write_half(child_actor+14,1400);
    psx_mod_write_word(child_actor+0x7C,parent_actor);psx_mod_write_word(child_actor+0x68,child_actor+0x80);
    psx_mod_write_word(child_actor+0x80,0x18180000);psx_mod_write_byte(child_actor+0x72,1);
    psx_mod_write_byte(child_actor+0x76,5);zero_solid_contacts[1]=(SolidContact){2,0};
    psx_mod_write_byte(0x800950A0,0xA5);psx_mod_write_byte(0x800CD340,1);
}
int main(void){
    if(!getenv("MMX6_NORTHPOLE_MEMBER")){puts("SKIP: original MMX6_NORTHPOLE_MEMBER required");return 77;}
    CPUState cpu;setup(&cpu);native_gate(parent_actor);CHECK(psx_mod_read_byte(parent_actor+6)==8);
    memcpy(before,ram,sizeof ram);CHECK(northpole_ice_admission(&cpu,0x800ED150));
    CHECK(psx_mod_read_byte(parent_actor+6)==9 && psx_mod_read_half(0x8009721C)==4976);
    CHECK(!memcmp(before+(PLAYER&0x1FFFFF),ram+(PLAYER&0x1FFFFF),0x158));CHECK(!target_projection_call && !state_track.count);
    setup(&cpu);psx_mod_write_half(PLAYER+10,5140);memcpy(before,ram,sizeof ram);
    CHECK(!northpole_ice_admission(&cpu,0x800ED150) && !memcmp(before,ram,sizeof ram));
    setup(&cpu);put32(p2.body+12,1472u<<16);CHECK(!northpole_ice_admission(&cpu,0x800ED150));
    setup(&cpu);psx_mod_write_byte(0x800ED160,0);CHECK(!northpole_ice_admission(&cpu,0x800ED150));
    setup(&cpu);psx_mod_write_half(parent_actor+10,5344);put32(p2.body+8,5345u<<16);put32(p2.body+12,1489u<<16);
    CHECK(northpole_ice_admission(&cpu,0x800ED150) && psx_mod_read_half(0x8009721C)==5328);
    child(&cpu);uint8_t primary[0x158];capture(PLAYER,primary,sizeof primary);
    CHECK(northpole_ice_live(&cpu,0x800EBF18));CHECK(prefixes==1 && contacts==1 && !terrain_calls && !effects);
    CHECK(!memcmp(primary,ram+(PLAYER&0x1FFFFF),sizeof primary) && psx_mod_read_byte(0x800950A1)==1);
    CHECK((le32(p2.body+8)>>16)==5161 && zero_solid_contacts[1].sides==8 && zero_solid_contacts[1].carried==3);
    CHECK(psx_mod_read_byte(child_actor+0x72)==1 && psx_mod_read_byte(child_actor+0x76)==5 && psx_mod_read_byte(0x800CD340)==1);
    CHECK(!inside && !target_projection_call && !state_track.count && !state_track.error);
    child(&cpu);contact_bits=4;CHECK(northpole_ice_live(&cpu,0x800EBF18));
    CHECK(prefixes==1 && contacts==1 && terrain_calls==1 && effects==1 && psx_mod_read_byte(child_actor+4)==4);
    CHECK(psx_mod_read_byte(parent_actor+7)==1 && !psx_mod_read_byte(parent_actor+0x89));
    child(&cpu);contact_bits=4;terrain_ground=0;CHECK(northpole_ice_live(&cpu,0x800EBF18));
    CHECK(terrain_calls==1 && !effects && psx_mod_read_byte(child_actor+4)==1 && psx_mod_read_byte(parent_actor+7)==2);
    child(&cpu);retire_in_prefix=1;CHECK(northpole_ice_live(&cpu,0x800EBF18));CHECK(prefixes==1 && !contacts);
    child(&cpu);p2.body[0xE5]=1;CHECK(northpole_ice_live(&cpu,0x800EBF18));CHECK(prefixes==1 && !contacts);
    child(&cpu);zero_world=1;CHECK(!northpole_ice_live(&cpu,0x800EBF18) && !prefixes);
    child(&cpu);zero_solid_contacts[1]=(SolidContact){0xFF,0x7F};
    CHECK(solid_allocate(&cpu,0x8002BFD0) && cpu.gpr[2]==child_actor);
    CHECK(!zero_solid_contacts[1].sides && !zero_solid_contacts[1].carried && !solid_allocate_call);
    CHECK(!state_track.count && !state_track.error);
    puts("North Pole guest admission and missed-contact ownership regression PASS");return 0;
}
