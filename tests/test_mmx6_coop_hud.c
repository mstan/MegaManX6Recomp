/* Actual plugin with bounded original native sprite/G4 packet contracts.
 * This verifies translation/ownership wiring, not original art or composition. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mod_plugins.h"
#undef PSX_MOD_CONSTRUCTOR
#define PSX_MOD_CONSTRUCTOR(name) static void name(void)
#include "../src/mods/mmx6_coop_plugin.c"
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
static uint8_t ram[0x200000],extra[0x300000];
static uint16_t vram[1024*512],ui_pixels[1024*512],retained_color;
static uint32_t calls[8],tags[8];
static unsigned call_count,tag_count,definitions,option_reads;
static const char *selected_layout;
static uint8_t *mem(uint32_t a){
    if(a>=0x9F000000u && a<0x9F300000u)return extra+a-0x9F000000u;
    return ram+(a&0x1FFFFFu);
}
uint8_t psx_mod_read_byte(uint32_t a){return *mem(a);}
uint16_t psx_mod_read_half(uint32_t a){return psx_mod_read_byte(a)|(uint16_t)psx_mod_read_byte(a+1)<<8;}
uint32_t psx_mod_read_word(uint32_t a){return psx_mod_read_half(a)|(uint32_t)psx_mod_read_half(a+2)<<16;}
void psx_mod_write_byte(uint32_t a,uint8_t v){*mem(a)=v;}
void psx_mod_write_half(uint32_t a,uint16_t v){psx_mod_write_byte(a,(uint8_t)v);psx_mod_write_byte(a+1,(uint8_t)(v>>8));}
void psx_mod_write_word(uint32_t a,uint32_t v){for(unsigned i=0;i<4;++i)psx_mod_write_byte(a+i,(uint8_t)(v>>(i*8)));}
int psx_mod_option_value(const char *package,const char *feature,const char *option,char *out,uint32_t cap){
    CHECK(!strcmp(package,"mmx6.local-coop") && !strcmp(feature,"prototype") && !strcmp(option,"hud_layout"));
    ++option_reads;CHECK(cap>=32);out[0]=0;
    if(!selected_layout)return 0;
    CHECK(strlen(selected_layout)<cap);strcpy(out,selected_layout);return 1;
}
const uint16_t *gpu_get_vram(void){return vram;}
int psx_mod_define_texture_bank(uint16_t id,uint32_t width,uint32_t height,const uint16_t *pixels){
    CHECK(id==0x7000+definitions && width==16 && height==16);retained_color=pixels[0];++definitions;return 1;
}
void psx_mod_tag_hud_primitive(uint32_t packet,int anchor){CHECK(anchor==-1 && tag_count<8);tags[tag_count++]=packet;}
static void sprite(int x,int y){
    uint32_t at=psx_mod_read_word(SCRATCH+0x108),mode=psx_mod_read_word(SCRATCH+0x10C);
    psx_mod_write_word(at,0x03000000u|((mode+8)&0xFFFFFF));psx_mod_write_word(at+4,0x7C808080);
    psx_mod_write_half(at+8,(uint16_t)x);psx_mod_write_half(at+10,(uint16_t)y);psx_mod_write_word(at+12,0x78410000);
    psx_mod_write_word(mode,0x01000000u|(at&0xFFFFFF));psx_mod_write_word(mode+4,0xE1000000);
    psx_mod_write_word(SCRATCH+0x108,at+16);psx_mod_write_word(SCRATCH+0x10C,mode+8);
}
static void bar(int x,int y,int amount){
    uint32_t at=psx_mod_read_word(SCRATCH+0x110);psx_mod_write_word(at,0x08000000u);
    for(unsigned i=0;i<4;++i){
        psx_mod_write_word(at+4+i*8,(i?0:0x38000000u)|0x00604020u);
        psx_mod_write_half(at+8+i*8,(uint16_t)(x+(i&1)*3));
        psx_mod_write_half(at+10+i*8,(uint16_t)(y-amount+(i>>1)*amount));
    }
    psx_mod_write_word(SCRATCH+0x110,at+36);
}
void psx_dispatch_call(CPUState *cpu,uint32_t address,uint32_t ret){
    (void)ret;CHECK(call_count<8 && hud_call && state_track.count);calls[call_count++]=address;
    if(address==0x80024F90u && cpu->gpr[4]==0x8008EF48u){
        CHECK(private_draw && private_seat && !hud_seat && cpu->gpr[5]==1);
        CHECK(psx_mod_read_byte(PLAYER+2)==0 && psx_mod_read_byte(PLAYER+0x5C)==23);
        CHECK(psx_mod_read_word(SCRATCH+0x1C)==0x80030000 && psx_mod_read_word(SCRATCH+0x3C)==0x80030100);
        bar(284,80,17);return; /* Native24F90 emits bars, not icons. */
    }
    if(address==0x80024CC0u){
        unsigned index=call_count-1,kind=psx_mod_read_byte(PLAY+0x25);
        CHECK(private_draw && private_seat && !hud_seat && psx_mod_read_byte(PLAYER+2)==0);
        CHECK((index==0 && cpu->gpr[4]==14 && cpu->gpr[5]==59) ||
              (index==1 && cpu->gpr[4]==15 && cpu->gpr[5]==60) ||
              (index==3 && cpu->gpr[4]==(kind==0?7u:kind==1?16u:17u) && cpu->gpr[5]==(kind==0?163u:kind==1?0u:162u)));
        sprite(280+(int)(index==1)*16,16);return;
    }
    if(address==0x800244C0u){
        CHECK(!hud_seat && psx_mod_read_byte(PLAYER+2)==0 && psx_mod_read_byte(PLAYER+0x5C)==23);
        CHECK(psx_mod_read_word(SCRATCH+0x1C)==0x80030000 && psx_mod_read_word(SCRATCH+0x3C)==0x80030100);
        cpu->gpr[2]=0x12345678;return; /* Original P1/boss path remains once. */
    }
    CHECK(hud_seat==1 && psx_mod_read_byte(PLAYER+2)==1);
    CHECK(psx_mod_read_word(SCRATCH+0x1C)==assembly && psx_mod_read_word(SCRATCH+0x3C)==menu_assembly);
    if(address==0x80024F90u){CHECK(psx_mod_read_byte(PLAYER+0x5C)==11);sprite(18,16);bar(22,80,11);}
    else if(address==0x800249D4u){CHECK(psx_mod_read_byte(PLAYER+0x93)==2 && psx_mod_read_half(PLAYER+0xAC)==7);sprite(27,34);bar(31,80,7);}
    else CHECK(0);
}
static void setup(CPUState *cpu,const char *layout){
    memset(ram,0,sizeof ram);memset(extra,0,sizeof extra);memset(cpu,0,sizeof *cpu);memset(&p2,0,sizeof p2);
    memset(ui_banks,0,sizeof ui_banks);ui_bank_count=definitions=call_count=tag_count=option_reads=0;
    memset(vram,0,sizeof vram);for(unsigned i=0;i<1024*512;++i)ui_pixels[i]=0x1111;
    vram[481*1024+16+1]=0x5678;zero_ui_pixels=ui_pixels;selected_layout=layout;
    active_palette=0x9F120000;psx_mod_write_half(active_palette+0x220+2,0x1234);
    mmx6_coop_lifecycle_init(&life);state_track.count=state_track.error=0;
    enrolled=1;failed=inside=zero_world=hud_call=hud_seat=private_draw=private_seat=0;p2_hud_fade=128;
    hud_packets=0x9F000000;assembly=0x9F100000;menu_assembly=0x9F110000;menu_memory=0x9F200000;
    p2.body[0]=p2.body[2]=p2.body[3]=p2.body[4]=1;p2.body[5]=2;p2.body[0x5C]=11;p2.body[0x93]=2;p2.body[0xAC]=7;
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+0x1F,1);
    psx_mod_write_byte(PLAYER,1);psx_mod_write_byte(PLAYER+0x5C,23);
    psx_mod_write_word(SCRATCH+0x1C,0x80030000);psx_mod_write_word(SCRATCH+0x3C,0x80030100);
    for(unsigned i=0;i<3;++i)psx_mod_write_word(SCRATCH+0x108+i*4,0x80040000+i*0x1000);
    cpu->gpr[4]=PLAYER;cpu->gpr[3]=0x87654321;
}
static void layout_case(const char *layout,int dx,int dy){
    CPUState cpu;setup(&cpu,layout);uint8_t before[0x158];capture(PLAYER,before,sizeof before);PlayerContext private_before=p2;
    CHECK(draw_coop_hud(&cpu,0x800244C0));
    CHECK(call_count==3 && calls[0]==0x800244C0 && calls[1]==0x80024F90 && calls[2]==0x800249D4);
    CHECK(option_reads==1 && tag_count==6 && definitions==1 && retained_color==0x1234);
    CHECK(cpu.gpr[2]==0x12345678 && cpu.gpr[3]==0x87654321);
    CHECK(!memcmp(before,mem(PLAYER),sizeof before) && !memcmp(&p2,&private_before,sizeof p2));
    for(unsigned i=0;i<3;++i)CHECK(psx_mod_read_word(SCRATCH+0x108+i*4)==0x80040000+i*0x1000);
    CHECK(psx_mod_read_word(SCRATCH+0x1C)==0x80030000 && psx_mod_read_word(SCRATCH+0x3C)==0x80030100);
    for(unsigned tile=0;tile<2;++tile){
        uint32_t at=hud_packets+0x3000+tile*80;int x=(tile?27:18)+dx,y=(tile?34:16)+dy;
        CHECK(psx_mod_read_word(hud_packets+tile*16)==(at&0xFFFFFF));
        CHECK((int16_t)psx_mod_read_half(at+8)==x && (int16_t)psx_mod_read_half(at+10)==y);
        CHECK((int16_t)psx_mod_read_half(at+20)==x+16 && (int16_t)psx_mod_read_half(at+22)==y);
        CHECK((int16_t)psx_mod_read_half(at+32)==x && (int16_t)psx_mod_read_half(at+34)==y+16);
    }
    for(unsigned i=0;i<2;++i){uint32_t at=hud_packets+0x2000+i*36;int x=(i?31:22)+dx,y=80+dy,amount=i?7:11;
        for(unsigned v=0;v<4;++v){CHECK((int16_t)psx_mod_read_half(at+8+v*8)==x+(int)(v&1)*3);
            CHECK((int16_t)psx_mod_read_half(at+10+v*8)==y-amount+(int)(v>>1)*amount);}
        CHECK((psx_mod_read_word(at+4)&0xFFFFFF)==0x604020);
    }
    CHECK(!failed && !hud_call && !hud_seat && !state_track.count && !state_track.error);
}
int main(void){
    layout_case(NULL,0,104);layout_case("stacked",0,104);layout_case("side_by_side",56,0);
    layout_case("unknown",0,104);layout_case("SIDE_BY_SIDE",0,104);layout_case("",0,104);
    /* Zero-owned native world/menu: original P1 HUD still runs once using
     * stored X, then private Zero; restore the already projected resident. */
    CPUState owner_cpu;setup(&owner_cpu,"side_by_side");capture(PLAYER,p1.body,sizeof p1.body);
    project(PLAYER,p2.body,sizeof p2.body);zero_world=1;saved_resources[1]=0x80030000;saved_resources[5]=0x80030100;
    psx_mod_write_word(SCRATCH+0x1C,assembly);psx_mod_write_word(SCRATCH+0x3C,menu_assembly);
    CHECK(draw_coop_hud(&owner_cpu,0x800244C0) && call_count==3 && !memcmp(mem(PLAYER),p2.body,sizeof p2.body));
    CHECK(psx_mod_read_word(SCRATCH+0x1C)==assembly && psx_mod_read_word(SCRATCH+0x3C)==menu_assembly);
    CHECK(p1.body[2]==0 && p1.body[0x5C]==23 && !hud_call && !state_track.count);
    CPUState cpu;setup(&cpu,"side_by_side");psx_mod_write_word(SCRATCH,1);CHECK(draw_coop_hud(&cpu,0x800244C0));
    CHECK(psx_mod_read_word(hud_packets+0x8000)==((hud_packets+0xB000)&0xFFFFFF) && !psx_mod_read_word(hud_packets));
    setup(&cpu,"side_by_side");life.status[1]=MMX6_COOP_LEAVING;p2_hud_fade=64;
    CHECK(draw_coop_hud(&cpu,0x800244C0) && p2_hud_fade==56);
    CHECK((psx_mod_read_word(hud_packets+0x3000+4)&0xFFFFFF)==0x383838);
    CHECK((psx_mod_read_word(hud_packets+0x2000+4)&0xFFFFFF)==0x2A1C0E);
    setup(&cpu,"side_by_side");life.status[1]=MMX6_COOP_ABSENT;p2_hud_fade=8;
    CHECK(draw_coop_hud(&cpu,0x800244C0) && call_count==1 && !p2_hud_fade && !option_reads);
    setup(&cpu,"side_by_side");psx_mod_write_byte(PLAY+0x1F,0);CHECK(draw_coop_hud(&cpu,0x800244C0) && call_count==1 && !tag_count);
    setup(&cpu,"stacked");CHECK(draw_coop_hud(&cpu,0x800244C0));
    call_count=tag_count=0;psx_mod_write_half(active_palette+0x220+2,0x4321);CHECK(draw_coop_hud(&cpu,0x800244C0));
    CHECK(definitions==2 && retained_color==0x4321); /* Actual CLUT change receives a fresh immutable bank. */
    /* A private guest pane never invokes the full P1/shared HUD and
     * ignores the shared stacked/side-by-side offset. Fallen HP stays owned. */
    setup(&cpu,"stacked");private_draw=private_seat=1;life.status[1]=MMX6_COOP_FALLEN;
    CHECK(draw_coop_hud(&cpu,0x800244C0) && call_count==2 && calls[0]==0x80024F90 && calls[1]==0x800249D4);
    CHECK(!option_reads && (int16_t)psx_mod_read_half(hud_packets+0x3000+8)==18 &&
        (int16_t)psx_mod_read_half(hud_packets+0x3000+10)==16 && retained_color==0x1234);
    /* Boss packets retain their native atlas and right-hand position in a
     * guest pane. Hero conversion must neither overwrite nor translate them,
     * including a projected Zero world and all three native badge branches. */
    for(unsigned kind=0;kind<3;++kind){
        unsigned projected=kind==1;
        setup(&cpu,"side_by_side");private_draw=private_seat=1;
        psx_mod_write_byte(PLAY+0x24,1);psx_mod_write_word(PLAY+0x20,0x8008EF48u);
        psx_mod_write_byte(PLAY+0x25,(uint8_t)kind);psx_mod_write_byte(PLAY+0x8C,32);
        if(projected){
            capture(PLAYER,p1.body,sizeof p1.body);project(PLAYER,p2.body,sizeof p2.body);zero_world=1;
            saved_resources[1]=0x80030000;saved_resources[5]=0x80030100;
            psx_mod_write_word(SCRATCH+0x1C,assembly);psx_mod_write_word(SCRATCH+0x3C,menu_assembly);
        }
        uint8_t resident[sizeof p2.body];capture(PLAYER,resident,sizeof resident);
        CHECK(draw_coop_hud(&cpu,0x800244C0));
        CHECK(call_count==6 && calls[0]==0x80024CC0u && calls[1]==0x80024CC0u && calls[2]==0x80024F90u && calls[3]==0x80024CC0u && calls[4]==0x80024F90u && calls[5]==0x800249D4u);
        CHECK(!memcmp(resident,mem(PLAYER),sizeof resident) && !hud_call && !hud_seat && !failed);
        CHECK(!state_track.count && !state_track.error && !option_reads);
        CHECK(psx_mod_read_word(SCRATCH+0x108)==0x80040030u && psx_mod_read_word(SCRATCH+0x10C)==0x80041018u && psx_mod_read_word(SCRATCH+0x110)==0x80042024u);
        CHECK(psx_mod_read_word(0x80040004u)==0x7C808080u && psx_mod_read_word(0x8004000Cu)==0x78410000u);
        CHECK(psx_mod_read_half(0x80040008u)==280 && psx_mod_read_half(0x8004000Au)==16);
        CHECK(psx_mod_read_half(0x80042008u)==284 && psx_mod_read_half(0x8004200Au)==63 && psx_mod_read_word(0x80042004u)==0x38604020u);
        CHECK(definitions==1 && tag_count==6);
    }
    setup(&cpu,"stacked");private_draw=private_seat=1;
    psx_mod_write_byte(PLAY+0x24,1);psx_mod_write_word(PLAY+0x20,0x8008EF48u);psx_mod_write_byte(PLAY+0x1F,0);
    CHECK(draw_coop_hud(&cpu,0x800244C0) && !call_count && !definitions && !tag_count);
    setup(&cpu,"stacked");private_draw=1;private_seat=0;
    CHECK(!draw_coop_hud(&cpu,0x800244C0) && !call_count);
    setup(&cpu,"side_by_side");psx_mod_write_word(SCRATCH+0x108,hud_packets+1);
    psx_mod_write_word(SCRATCH+0x10C,hud_packets+0x1000);psx_mod_write_word(SCRATCH+0x110,hud_packets+0x2000);
    hud_zero_packets(hud_packets);CHECK(failed && !option_reads && !tag_count && !definitions);
    for(unsigned gate=0;gate<4;++gate){setup(&cpu,"side_by_side");if(gate==0)hud_call=1;else if(gate==1)enrolled=0;else if(gate==2)failed=1;else psx_mod_write_byte(PLAY,4);
        CHECK(!draw_coop_hud(&cpu,0x800244C0) && !call_count && !option_reads);}
    setup(&cpu,NULL);for(unsigned icon=0;icon<6;++icon){cpu.gpr[4]=icon;hud_seat=0;CHECK(!hud_icon(&cpu,0));hud_seat=1;CHECK(hud_icon(&cpu,0)==(icon==3 || icon==4));}
    puts("HUD layout actual-plugin offsets, native packet ownership, anchors and gates PASS");return 0;
}
