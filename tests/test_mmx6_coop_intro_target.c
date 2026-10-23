/* Actual plugin against isolated RAM and the source-proven action1 leaf's
 * observable contract. No native runtime/gameplay pass is claimed. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mod_plugins.h"
#undef PSX_MOD_CONSTRUCTOR
#define PSX_MOD_CONSTRUCTOR(name) static void name(void)
#include "../src/mods/mmx6_coop_plugin.c"
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
static uint8_t ram[0x200000],before[0x200000];
static unsigned calls;
static const uint32_t enemy=0x8008EF48;
uint8_t psx_mod_read_byte(uint32_t a){return ram[a&0x1FFFFF];}
uint16_t psx_mod_read_half(uint32_t a){return psx_mod_read_byte(a)|((uint16_t)psx_mod_read_byte(a+1)<<8);}
uint32_t psx_mod_read_word(uint32_t a){return psx_mod_read_half(a)|((uint32_t)psx_mod_read_half(a+2)<<16);}
void psx_mod_write_byte(uint32_t a,uint8_t v){ram[a&0x1FFFFF]=v;}
void psx_mod_write_half(uint32_t a,uint16_t v){psx_mod_write_byte(a,(uint8_t)v);psx_mod_write_byte(a+1,(uint8_t)(v>>8));}
void psx_mod_write_word(uint32_t a,uint32_t v){for(unsigned i=0;i<4;++i)psx_mod_write_byte(a+i,(uint8_t)(v>>(i*8)));}
static void native_leaf(CPUState *cpu){
    int d=(int16_t)psx_mod_read_half(cpu->gpr[4]+10)-(int16_t)psx_mod_read_half(PLAYER+10);
    if(d<0)d=-d;
    if(psx_mod_read_byte(cpu->gpr[4]+2) && d<112)psx_mod_write_byte(cpu->gpr[4]+5,2);
    cpu->gpr[2]=0x12345678;
}
void psx_dispatch_call(CPUState *cpu,uint32_t address,uint32_t ret){
    (void)ret;CHECK(address==0x800EB14C && intro_target_call && state_track.count==2);
    CHECK(!psx_mod_try_function_replacement(cpu,address)); /* Re-entry executes original once. */
    CHECK(psx_mod_read_half(PLAYER+8)==0x1357 && psx_mod_read_word(PLAYER+12)==0x24681000);
    ++calls;native_leaf(cpu);
}
static void setup(CPUState *cpu){
    memset(ram,0,sizeof ram);memset(&p2,0,sizeof p2);memset(cpu,0,sizeof *cpu);
    mmx6_coop_lifecycle_init(&life);ready=enrolled=1;failed=inside=zero_world=zero_projected=0;
    scene_owner=scene_phase=0;intro_target_call=0;state_track.count=state_track.error=0;calls=0;
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAYER+3,1);psx_mod_write_byte(PLAYER+4,1);
    psx_mod_write_byte(PLAYER+5,2);psx_mod_write_byte(PLAYER+0x5C,32);
    psx_mod_write_word(PLAYER+8,(144u<<16)|0x1357);psx_mod_write_word(PLAYER+12,0x24681000);
    p2.body[3]=p2.body[4]=1;p2.body[5]=2;p2.body[0x5C]=32;put32(p2.body+8,400u<<16);
    psx_mod_write_byte(enemy,1);psx_mod_write_byte(enemy+1,1);psx_mod_write_byte(enemy+2,1);
    psx_mod_write_byte(enemy+4,1);psx_mod_write_byte(enemy+5,1);psx_mod_write_half(enemy+10,416);
    psx_mod_write_word(0x8006DC6C,0x800FA424);psx_mod_write_word(0x800FA428,0x800EAFB0);
    psx_mod_write_word(0x800FAB4C,0x800EAC8C);psx_mod_write_word(0x800FAB5C,0x800EB14C);
    for(unsigned i=0;i<sizeof intro_near_words/sizeof intro_near_words[0];++i)
        psx_mod_write_word(0x800EB14C+i*4,intro_near_words[i]);
    cpu->gpr[4]=enemy;cpu->gpr[31]=0x800EACD4;
    psx_mod_clear_function_replacements();
    CHECK(psx_mod_set_function_replacement(0x800EB14C,intro_near_target));
}
static void rejected(CPUState *cpu){
    memcpy(before,ram,sizeof ram);CHECK(!intro_near_target(cpu,0x800EB14C));
    CHECK(!calls && !memcmp(before,ram,sizeof ram) && !state_track.count && !intro_target_call);
}
int main(void){
    CPUState cpu;setup(&cpu);native_leaf(&cpu);
    CHECK(psx_mod_read_byte(enemy+5)==1); /* Native negative control: P1 is272 away. */
    memcpy(before,ram,sizeof ram);PlayerContext saved=p2;
    CHECK(psx_mod_try_function_replacement(&cpu,0x800EB14C));CHECK(calls==1 && cpu.gpr[2]==0x12345678);
    CHECK(cpu.pc==cpu.gpr[31]);
    CHECK(psx_mod_read_byte(enemy+5)==2);before[(enemy+5)&0x1FFFFF]=2;
    CHECK(!memcmp(before,ram,sizeof ram) && !memcmp(&saved,&p2,sizeof p2));
    CHECK(!state_track.count && !intro_target_call);
    setup(&cpu);put32(p2.body+8,688u<<16);rejected(&cpu); /* Equal distance: P1. */
    setup(&cpu);put32(p2.body+8,304u<<16);CHECK(intro_near_target(&cpu,0x800EB14C));
    CHECK(psx_mod_read_byte(enemy+5)==1); /* Exact112 remains outside native strict range. */
    setup(&cpu);life.status[0]=MMX6_COOP_FALLEN;psx_mod_write_half(PLAYER+10,416);
    CHECK(intro_near_target(&cpu,0x800EB14C) && calls==1); /* Ineligible closer X ignored. */
    const unsigned status[]={MMX6_COOP_ABSENT,MMX6_COOP_DYING,MMX6_COOP_FALLEN,MMX6_COOP_JOINING};
    for(unsigned i=0;i<sizeof status/sizeof status[0];++i){setup(&cpu);life.status[1]=status[i];rejected(&cpu);}
    const unsigned offsets[]={3,4,0x5C,0x7A,0xD0,0xD4};
    for(unsigned i=0;i<sizeof offsets/sizeof offsets[0];++i){setup(&cpu);p2.body[offsets[i]]=i<3?0:1;rejected(&cpu);}
    int *guards[]={&inside,&zero_world,&zero_projected,&intro_target_call,&failed};
    for(unsigned i=0;i<sizeof guards/sizeof guards[0];++i){setup(&cpu);*guards[i]=1;memcpy(before,ram,sizeof ram);CHECK(!intro_near_target(&cpu,0x800EB14C));CHECK(!calls && !memcmp(before,ram,sizeof ram));*guards[i]=0;}
    const unsigned play_offsets[]={1,12,13,0x10,0x1C};
    for(unsigned i=0;i<sizeof play_offsets/sizeof play_offsets[0];++i){setup(&cpu);psx_mod_write_byte(PLAY+play_offsets[i],1);rejected(&cpu);}
    setup(&cpu);scene_owner=1;rejected(&cpu);setup(&cpu);scene_phase=1;rejected(&cpu);
    for(unsigned i=0;i<sizeof intro_near_words/sizeof intro_near_words[0];++i){setup(&cpu);psx_mod_write_word(0x800EB14C+i*4,intro_near_words[i]^1);rejected(&cpu);}
    setup(&cpu);cpu.gpr[4]=enemy+1;rejected(&cpu);
    setup(&cpu);psx_mod_write_byte(enemy+1,2);rejected(&cpu);
    setup(&cpu);psx_mod_write_word(0x800FAB5C,0x800EB150);rejected(&cpu);
    puts("intro target actual-plugin projection, native negative control and guards PASS");return 0;
}
