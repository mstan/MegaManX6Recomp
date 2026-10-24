/* Actual plugin against isolated RAM/packets and source-proven native helper
 * contracts from COOP_R9_EFFECT_CLOSURE.json. The bounded helper models are
 * external guest contracts: this tests plugin projection/call/render wiring,
 * not native execution or gameplay qualification. No disc bytes are bundled. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mod_plugins.h"
#undef PSX_MOD_CONSTRUCTOR
#define PSX_MOD_CONSTRUCTOR(name) static void name(void)
#include "../src/mods/mmx6_coop_plugin.c"
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
enum { TRAILS=0x800972F8u,EFFECTS=0x800911A8u,MODES_AT=120000u };
static uint8_t ram[0x200000],extra[0x300000];
static uint8_t previous_frame[FRAME_ARENA];
static uint16_t test_vram[1024*512],bank_first[4096];
static uint16_t test_zero_ui[1024*512];
static uint32_t calls[512],drawn[128],tagged[256];
static unsigned call_count,draw_count,tag_count;
static int texture_support=1,marker_override=2,terminal_player,stage_driver;
static int menu_probe;
static unsigned menu_vram_probe,gp0_upload_stage,gp0_upload_left,gp0_upload_x,gp0_upload_y,gp0_upload_width,gp0_upload_at;
static uint16_t original_menu_vram[1024*512];
static uint16_t menu_input[3];
static unsigned native_budget;
static unsigned shared_probe,shared_probe_seat,shared_probe_delete,shared_probe_calls;
static unsigned icon_packet_probe;
static unsigned render_replacement_probe;
static uint16_t pad_buttons=0xFFFF;
static const unsigned resource_offsets[7]={0x14,0x1C,0x24,0x28,0x38,0x3C,0xA8};
static uint8_t *memory(uint32_t a){
    if(a>=0x9F000000u && a<0x9F300000u)return extra+a-0x9F000000u;
    return ram+(a&0x1FFFFFu);
}
uint8_t psx_mod_read_byte(uint32_t a){return *memory(a);}
uint16_t psx_mod_read_half(uint32_t a){return (uint16_t)(psx_mod_read_byte(a)|(uint16_t)psx_mod_read_byte(a+1)<<8);}
uint32_t psx_mod_read_word(uint32_t a){return psx_mod_read_half(a)|(uint32_t)psx_mod_read_half(a+2)<<16;}
void psx_mod_write_byte(uint32_t a,uint8_t v){*memory(a)=v;}
void psx_mod_write_half(uint32_t a,uint16_t v){psx_mod_write_byte(a,(uint8_t)v);psx_mod_write_byte(a+1,(uint8_t)(v>>8));}
void psx_mod_write_word(uint32_t a,uint32_t v){for(unsigned i=0;i<4;++i)psx_mod_write_byte(a+i,(uint8_t)(v>>(i*8)));}
void psx_mod_write_code_word(uint32_t a,uint32_t v){psx_mod_write_word(a,v);}
uint16_t sio_get_pad_buttons_slot(int slot){CHECK(slot==1);return pad_buttons;}
uint16_t mmx6_diagnostics_p2(unsigned consumer,uint16_t buttons,int contaminated){
    CHECK(consumer<6 && buttons==(uint16_t)~pad_buttons && !contaminated);
    return buttons;
}
#ifdef MMX6_COOP_INPUT_TAINT_API
void psx_session_input_taint_add(uint32_t flags){(void)flags;CHECK(0);}
#endif
int psx_mod_netplay_is_active(void){return 0;}
int psx_mod_netplay_has_state_digest(void){return 1;}
int psx_mod_texture_banks_supported(void){return texture_support;}
int psx_mod_local_view_scope(void){return 0;}
int psx_mod_widescreen_x_margin(void){return 0;}
void psx_mod_counter_add(const char *name,uint32_t count){(void)name;(void)count;}
int psx_mod_read_disc_file(const char *name,void *data,uint32_t size,uint32_t *out){(void)name;(void)data;(void)size;(void)out;CHECK(0);return 0;}
const uint16_t *gpu_get_vram(void){return test_vram;}
void gpu_write_gp0(uint32_t value){
    CHECK(menu_vram_probe);
    if(!gp0_upload_stage){CHECK(value==0xA0000000);gp0_upload_stage=1;return;}
    if(gp0_upload_stage==1){gp0_upload_x=value&0xFFFF;gp0_upload_y=value>>16;gp0_upload_stage=2;return;}
    if(gp0_upload_stage==2){gp0_upload_width=value&0xFFFF;gp0_upload_left=gp0_upload_width*(value>>16);gp0_upload_at=0;CHECK(gp0_upload_left && !(gp0_upload_left&1));gp0_upload_stage=3;return;}
    for(unsigned i=0;i<2;++i){unsigned x=gp0_upload_x+gp0_upload_at%gp0_upload_width,y=gp0_upload_y+gp0_upload_at/gp0_upload_width;
        CHECK(x<1024 && y<512 && gp0_upload_left);test_vram[y*1024+x]=(uint16_t)(value>>(i*16));++gp0_upload_at;--gp0_upload_left;}
    if(!gp0_upload_left)gp0_upload_stage=0;
}
void gpu_set_gp0_source(uint32_t address){CHECK(menu_vram_probe && !address && !gp0_upload_stage);}
int psx_mod_define_texture_bank(uint16_t id,uint32_t width,uint32_t height,const uint16_t *pixels){
    CHECK(id>=0x6000 && id<0x7000 && width==height && (width==16 || width==256));
    bank_first[id-0x6000]=pixels[0];return 1;
}
void psx_mod_tag_world_primitive(uint32_t p,int world){CHECK(world==1 && tag_count<256);tagged[tag_count++]=p;}
static unsigned occurrences(uint32_t address){unsigned n=0;for(unsigned i=0;i<call_count;++i)n+=calls[i]==address;return n;}
static void copy_position(uint32_t dst,uint32_t src){psx_mod_write_word(dst+8,psx_mod_read_word(src+0x18));psx_mod_write_word(dst+12,psx_mod_read_word(src+0x1C));}
static void reset_trail(uint32_t a,unsigned index){
    psx_mod_write_byte(a+3,1);psx_mod_write_byte(a+4,1);psx_mod_write_byte(a+5,0);
    psx_mod_write_half(a+0x54,3);psx_mod_write_half(a+0x56,8);psx_mod_write_half(a+0x58,(uint16_t)((5-index)*2));
    psx_mod_write_word(a+8,psx_mod_read_word(PLAYER+8));psx_mod_write_word(a+12,psx_mod_read_word(PLAYER+12));
}
static void native_trails(void){
    for(unsigned i=0;i<3;++i){
        uint32_t a=TRAILS+i*0x60,parent=psx_mod_read_word(a+0x50);
        CHECK(parent==(i?a-0x60:PLAYER));
        psx_mod_write_byte(a+0x47,psx_mod_read_byte(PLAYER+0x47));
        psx_mod_write_byte(a+0x15,psx_mod_read_byte(PLAYER+0x15));
        psx_mod_write_word(a+0x38,psx_mod_read_word(PLAYER+0x38));psx_mod_write_word(a+0x3C,psx_mod_read_word(PLAYER+0x3C));
        psx_mod_write_word(a+0x18,psx_mod_read_word(a+8));psx_mod_write_word(a+0x1C,psx_mod_read_word(a+12));
        int marker=(int8_t)psx_mod_read_byte(PLAYER+0x8C);
        if(!psx_mod_read_byte(a+4)){if(marker>0)reset_trail(a,i);else if(marker<0)psx_mod_write_byte(PLAYER+0x8C,0);continue;}
        if(!marker){psx_mod_write_byte(a+3,0);psx_mod_write_byte(a+4,0);continue;}
        unsigned phase=psx_mod_read_byte(a+5);CHECK(phase<3);
        if(phase && marker>0){reset_trail(a,i);continue;}
        if(!phase){
            unsigned n=psx_mod_read_half(a+0x54);if(n)psx_mod_write_half(a+0x54,(uint16_t)(n-1));else{copy_position(a,parent);psx_mod_write_half(a+0x54,3);}
            if(marker<0)psx_mod_write_byte(a+5,1);
        }else if(phase==1){
            unsigned n=psx_mod_read_half(a+0x56);if(n){psx_mod_write_half(a+0x56,(uint16_t)(n-1));if((n-1)&1)copy_position(a,parent);}else psx_mod_write_byte(a+5,2);
        }else{
            unsigned n=psx_mod_read_half(a+0x58);if(n){copy_position(a,parent);psx_mod_write_half(a+0x58,(uint16_t)(n-1));}
            else{psx_mod_write_byte(a+3,0);psx_mod_write_byte(a+4,0);if(i==2)psx_mod_write_byte(PLAYER+0x8C,0);}
        }
    }
}
static void native_attached(void){
    for(unsigned i=0;i<3;++i){
        uint32_t a=EFFECTS+i*0x50;if(i==2 && !psx_mod_read_byte(a))continue;
        psx_mod_write_word(a+8,psx_mod_read_word(PLAYER+8));psx_mod_write_word(a+12,psx_mod_read_word(PLAYER+12));
        unsigned kind=psx_mod_read_byte(a+2),lo=psx_mod_read_byte(PLAYER+0x9B),hi=psx_mod_read_byte(PLAYER+0x9C);
        if(kind==3){
            int visible=psx_mod_read_byte(PLAYER+5)==0x23 && (int8_t)psx_mod_read_byte(PLAYER+6)>0;
            psx_mod_write_byte(a+3,(uint8_t)visible);continue;
        }
        if(!psx_mod_read_byte(a+4)){if(lo==(kind?1:2)||hi==(kind?1:2)){psx_mod_write_byte(a+3,1);psx_mod_write_byte(a+4,1);}}
        else if(!lo && !hi){psx_mod_write_byte(a+3,0);psx_mod_write_byte(a+4,0);}
    }
}
static void projected(void){
    CHECK(psx_mod_read_byte(PLAYER+2)==1 && psx_mod_read_byte(PLAY+0x38)==1 && psx_mod_read_byte(PLAY+0x5E)==5);
    CHECK(psx_mod_read_word(SCRATCH+0x14)==assets && psx_mod_read_word(SCRATCH+0x1C)==assembly);
    CHECK(psx_mod_read_word(SCRATCH+0x28)==active_palette && psx_mod_read_word(OVERLAY)==0x44444444u);
}
static void native_draw(uint32_t actor){
    /* Native23300..2330C returns without packets when its budget is spent. */
    if(psx_mod_read_word(SCRATCH+0x124)>=1000)return;
    CHECK(draw_count<128);drawn[draw_count++]=actor;
    uint32_t at=psx_mod_read_word(SCRATCH+0x100),mode=psx_mod_read_word(SCRATCH+0x104);
    uint32_t arena=packets+(psx_mod_read_word(SCRATCH)&1u)*FRAME_ARENA;
    CHECK(at>=arena && at+40<=arena+40000 && mode==arena+MODES_AT+(at-arena)/5);
    uint32_t q[10]={0x09000000u|((mode+8)&0xFFFFFFu),0x2C808080u,0x0014000Au,0,0x0014001Au,0x00000010u,0x0024000Au,0x00001000u,0x0024001Au,0x00001010u};
    q[3]=(uint32_t)psx_mod_read_half(actor+0x42)<<16;
    if(zero_ui_effect(actor)) {
        q[1]=0x7D000000u;q[3]|=0x5040u;
        memset(q+4,0,6*sizeof *q);
    } else if(icon_packet_probe && actor>=0x800950A0u && actor<0x800964A0u) {
        /* Model original type44 output independently of the retention guard. */
        if(icon_packet_probe==2) {
            q[1]=0x7D000000u;q[3]|=0xD0C0u;
            memset(q+4,0,6*sizeof *q);
        } else {
            q[1]=0x2F808080u;
            q[3]|=0xC0D0u;q[5]=0x002CC0C0u;q[7]=0xD0D0u;q[9]=0xD0C0u;
        }
    } else if(zero_icon_effect(actor)) {
        q[1]=0x2F808080u; /* Original raw+semitransparent flipped FT4. */
        q[3]|=0xC0D0u;q[5]=0x002CC0C0u;q[7]=0xD0D0u;q[9]=0xD0C0u;
    }
    for(unsigned i=0;i<10;++i)psx_mod_write_word(at+i*4,q[i]);
    psx_mod_write_word(mode,0x01000000u|(at&0xFFFFFFu));
    psx_mod_write_word(mode+4,zero_ui_effect(actor)?0xE100003Eu:
        icon_packet_probe==2 && actor>=0x800950A0u && actor<0x800964A0u?0xE100002Eu:0xE1000040u);
    unsigned priority=psx_mod_read_byte(actor+0x16);
    uint32_t tail=0x8008EB08u+(psx_mod_read_word(SCRATCH)&1u)*128+(priority>>4)*32+(priority&7)*4;
    uint32_t previous=psx_mod_read_word(tail);
    psx_mod_write_word(previous,(psx_mod_read_word(previous)&0xFF000000u)|(mode&0xFFFFFFu));
    psx_mod_write_word(tail,at);
    psx_mod_write_word(SCRATCH+0x100,at+40);psx_mod_write_word(SCRATCH+0x104,mode+8);
    psx_mod_write_word(SCRATCH+0x124,++native_budget);
}
void psx_dispatch_call(CPUState *cpu,uint32_t address,uint32_t ret){
    (void)ret;CHECK(call_count<512 && state_track.count);calls[call_count++]=address;
    if(menu_vram_probe && address==0x80066150u)return;
#ifdef MMX6_TEST_DISPATCH_CALL
    if(MMX6_TEST_DISPATCH_CALL(cpu,address,ret))return;
#endif
    /* SDK dispatch runs entry hooks and replacements on nested guest calls
     * too. A private type44 draw must not start a second private packet pass
     * through render_survivor and overwrite the body/curtain append cursor. */
    if(render_replacement_probe && address==0x800232D4u) {
        render(cpu,address);
        if(render_survivor(cpu,address))return;
    }
    if(shared_probe && address==0x8002C398u) {
        memset(memory(0x80091298u),0,0x70);cpu->gpr[2]=0x80091298u;return;
    }
    if(shared_probe && (address==0x801EE254u || address==0x8004AE1Cu)) {
        ++shared_probe_calls;CHECK(shared_fx_call);
#ifdef MMX6_COOP_MODERN_STATE
        CHECK(!snapshot_ready());
#endif
        if(shared_probe_seat)projected();
        else {
            CHECK(!zero_projected && !zero_world && psx_mod_read_byte(PLAYER+2)==0);
            CHECK(psx_mod_read_word(OVERLAY)==0x11223344 && psx_mod_read_word(SCRATCH+0x1C)==0x80030100u);
        }
        psx_mod_write_byte(PLAYER+0xD8,0x4C);
        psx_mod_write_byte(cpu->gpr[4]+4,1);
        psx_mod_write_word(PLAY+0x90,psx_mod_read_word(PLAY+0x90)+1);
        if(shared_probe_delete)psx_mod_write_byte(cpu->gpr[4],0);
        cpu->gpr[2]=0x1234;return;
    }
#ifdef MMX6_COOP_MODERN_STATE
    CHECK(!snapshot_ready());
    if(address==0x800232D4u){
        unsigned found=0;
        for(unsigned i=0;i<state_track.count;++i){
            Mmx6StateFrame *f=&state_track.frame[i];if(f->tag!=17 && f->tag!=18)continue;
            CHECK(f->words && f->bytes==16u);
            uint32_t before=state_digest();f->saved[4]^=1;CHECK(state_digest()!=before);f->saved[4]^=1;
            CHECK(state_digest()==before);++found;
        }
        CHECK(found==1); /* Saved resident mode cursor is typed future state. */
    }
#endif
    if(address==0x800232D4u){native_draw(cpu->gpr[4]);return;}
    if(address==0x8001E9ECu && menu_probe){
        CHECK(stage_call);
        if(menu_probe==1){CHECK(zero_world && inside);projected();}
        else CHECK(!zero_world && !inside && psx_mod_read_byte(PLAYER+2)==0);
        for(unsigned i=0;i<3;++i)menu_input[i]=psx_mod_read_half(0x800C456C+i*2);
        cpu->gpr[2]=0x51554954u;
        return;
    }
    if(address==0x8001E9ECu){
        CHECK(stage_driver && zero_world && inside);projected();
        psx_mod_write_word(PLAY+0x90,psx_mod_read_word(PLAY+0x90)+1);
        const uint32_t order[]={0x8003CD44u,0x80034DCCu,0x8002012Cu,0x8002F288u,0x80020D74u,0x80020DC8u};
        for(unsigned i=0;i<6;++i)guest(cpu,order[i],i==3?PLAYER:0,0);
        return;
    }
    projected();
    if(address==0x8003CD44u)return;
    if(address==0x80034DCCu){
        psx_mod_write_word(PLAYER+0x18,psx_mod_read_word(PLAYER+8));
        psx_mod_write_word(PLAYER+8,psx_mod_read_word(PLAYER+8)+65536);
        if(marker_override!=2)psx_mod_write_byte(PLAYER+0x8C,(uint8_t)marker_override);
        if(terminal_player){psx_mod_write_byte(PLAYER+4,3);psx_mod_write_byte(PLAYER+0x8C,0);psx_mod_write_byte(PLAYER+0x9B,0);psx_mod_write_byte(PLAYER+0x9C,0);}
    }else if(address==0x8002012Cu){
        psx_mod_write_byte(0x800950A0+6,(uint8_t)(psx_mod_read_byte(0x800950A0+6)+1));
        uint32_t saved_ra=cpu->gpr[31];cpu->gpr[31]=0x80020C70u;controller(cpu,address);cpu->gpr[31]=saved_ra;
    }else if(address==0x8002F288u){
        CHECK(cpu->gpr[4]==PLAYER);psx_mod_write_word(PLAYER+8,psx_mod_read_word(PLAYER+8)+2*65536);
    }else if(address==0x80020D74u){
        CHECK(psx_mod_read_word(PLAYER+8)==le32(p2.body+8)+3*65536);native_attached();
    }else if(address==0x80020DC8u){native_trails();}
    else if(address!=0x80017A04u)CHECK(0);
}
static void clear_banks(void){for(unsigned i=0;i<bank_count;++i){free(banks[i].pixels);memset(&banks[i],0,sizeof banks[i]);}bank_count=0;}
static void setup(CPUState *cpu){
    clear_banks();memset(ram,0,sizeof ram);memset(extra,0,sizeof extra);memset(&p2,0,sizeof p2);memset(cpu,0,sizeof *cpu);
    memset(test_vram,0,sizeof test_vram);memset(bank_first,0,sizeof bank_first);memset(zero_overlay,0x44,sizeof zero_overlay);
    mmx6_coop_lifecycle_init(&life);state_track.count=state_track.error=0;
    inside=failed=player_call=zero_world=world_render=scene_owner=scene_phase=zero_projected=0;
    shared_fx_call=shared_fx_allocate_call=0;memset(shared_effect_owners,0,sizeof shared_effect_owners);
    shared_probe=shared_probe_seat=shared_probe_delete=shared_probe_calls=0;
    icon_packet_probe=render_replacement_probe=0;
    ready=enrolled=stage_call=1;pause_owner=-1;zero_menu_loaded=0;join_phase=0;previous_input=p2_edges=0;p2_start_previous=0;
    texture_support=1;marker_override=2;terminal_player=stage_driver=0;call_count=draw_count=tag_count=native_budget=0;
    pad_buttons=0xFFFF;
    menu_probe=0;memset(menu_input,0,sizeof menu_input);
    menu_vram_probe=gp0_upload_stage=gp0_upload_left=0;
    assets=0x9F000000u;assembly=0x9F010000u;palette_source=0x9F020000u;active_palette=0x9F024000u;
    packets=0x9F100000u;diagnostic=0x9F080000u;menu_memory=0x9F200000u;menu_assembly=menu_memory+0x14000;
    world_packets=0;zero_ui_pixels=test_zero_ui;memset(test_zero_ui,0,sizeof test_zero_ui);
    static uint8_t compressed[64];zero_compressed=compressed;compressed_size=sizeof compressed;memset(compressed,0,sizeof compressed);
    put32(compressed,0x100020);const uint16_t stream[]={0x6000,0x1111,0x0001,63,0,0};
    for(unsigned i=0;i<6;++i){compressed[32+i*2]=(uint8_t)stream[i];compressed[33+i*2]=(uint8_t)(stream[i]>>8);}
    p2.body[0]=p2.body[2]=p2.body[3]=p2.body[4]=1;p2.body[5]=2;p2.body[0x5C]=32;p2.body[0xE7]=5;
    put32(p2.body+8,400u<<16);put32(p2.body+12,1000u<<16);put32(p2.body+0x18,399u<<16);put32(p2.body+0x1C,1000u<<16);
    put32(p2.body+0x38,assets);put32(p2.body+0x3C,assembly);p2.body[0x40]=0;p2.body[0x41]=5;p2.body[0x42]=0;p2.body[0x43]=0x78;
    for(unsigned i=0;i<3;++i){
        uint8_t *trail=p2.trails+i*0x60;trail[0]=0x11;trail[2]=(uint8_t)i;trail[0x16]=4;trail[0x42]=(uint8_t)(13+i);trail[0x43]=0x78;
        put32(trail+0x50,i?TRAILS+(i-1)*0x60:PLAYER);put32(trail+0x38,assets);put32(trail+0x3C,assembly);
        for(unsigned c=0;c<16;++c)psx_mod_write_half(active_palette+(13+i)*32+c*2,(uint16_t)(0x1110+i*16+c));
        uint8_t *effect=p2.effects+i*0x50;effect[2]=(uint8_t)(i==2?3:i);if(i<2)effect[0]=0x21;
    }
    for(unsigned c=0;c<16;++c)psx_mod_write_half(active_palette+c*2,(uint16_t)(0x0100+c));
    PlayerContext resident;memset(&resident,0xB3,sizeof resident);resident.body[0]=resident.body[3]=resident.body[4]=1;
    resident.body[2]=0;resident.body[5]=2;resident.body[0x67]=0;resident.body[0x70]=8;resident.body[0x5C]=32;
    put32(resident.body+8,144u<<16);put32(resident.body+12,1000u<<16);project_player(&resident);
    for(unsigned i=0;i<7;++i)psx_mod_write_word(SCRATCH+resource_offsets[i],0x80030000u+i*0x100);
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+0x38,0);psx_mod_write_byte(PLAY+0x5E,0);
    psx_mod_write_byte(0x800C4560,0x72);psx_mod_write_word(OVERLAY,0x11223344);
    psx_mod_write_word(SCRATCH+0x100,0x800A0000);psx_mod_write_word(SCRATCH+0x104,0x800A8000);
    for(unsigned i=0;i<0x100;++i)psx_mod_write_byte(0x800A8000+i,0xE7);
    for(unsigned i=0;i<64;++i){psx_mod_write_word(0x8008EB08+i*4,0x800B0000+i*4);psx_mod_write_word(0x800B0000+i*4,0x00FFFFFF);}
    cpu->gpr[31]=0x80020C70;cpu->gpr[4]=PLAYER;cpu->gpr[3]=0x12345678;cpu->pc=0x80010000;
    begin_world_draw(cpu,0x80025FB0u);
}
static void controller_pair_and_restoration(void){
    CPUState cpu;setup(&cpu);PlayerContext resident;capture_player(&resident);uint8_t play[0xE0],camera[0x100];capture(PLAY,play,sizeof play);capture(0x800971F8,camera,sizeof camera);
    marker_override=1;p2.body[0x9C]=1;controller(&cpu,0x8002012C);
    const uint32_t expected[]={0x8003CD44u,0x80034DCCu,0x8002012Cu,0x8002F288u,0x80020D74u,0x80020DC8u};
    CHECK(call_count==6 && !memcmp(calls,expected,sizeof expected));
    PlayerContext after;capture_player(&after);CHECK(!memcmp(&after,&resident,sizeof resident));
    uint8_t current[0xE0];capture(PLAY,current,sizeof current);CHECK(!memcmp(play,current,sizeof play));
    uint8_t cam[0x100];capture(0x800971F8,cam,sizeof cam);CHECK(!memcmp(camera,cam,sizeof camera));
    CHECK(psx_mod_read_word(OVERLAY)==0x11223344 && psx_mod_read_byte(0x800C4560)==0x72);
    for(unsigned i=0;i<7;++i)CHECK(psx_mod_read_word(SCRATCH+resource_offsets[i])==0x80030000u+i*0x100);
    CHECK(p2.shots[6]==1 && p2.effects[0x50+3] && le32(p2.effects+0x50+8)==403u<<16);
    for(unsigned i=0;i<3;++i){CHECK(p2.trails[i*0x60+3] && le32(p2.trails+i*0x60+8)==403u<<16);CHECK(le32(p2.trails+i*0x60+0x50)==(i?TRAILS+(i-1)*0x60:PLAYER));}
    CHECK(!inside && !zero_projected && !state_track.count && !state_track.error && cpu.gpr[3]==0x12345678);
}
static void lifetime_and_gates(void){
    CPUState cpu;setup(&cpu);marker_override=1;controller(&cpu,0);marker_override=-1;
    for(unsigned tick=0;tick<21;++tick)controller(&cpu,0);
    for(unsigned i=0;i<3;++i)CHECK(!p2.trails[i*0x60+3] && !p2.trails[i*0x60+4]);
    CHECK(!p2.body[0x8C]);
    marker_override=1;controller(&cpu,0);CHECK(p2.trails[3]);marker_override=0;controller(&cpu,0);CHECK(!p2.trails[3]);
    p2.effects[3]=p2.effects[4]=1;p2.effects[0x53]=p2.effects[0x54]=1;p2.body[0x9B]=p2.body[0x9C]=0;controller(&cpu,0);
    CHECK(!p2.effects[3] && !p2.effects[4] && !p2.effects[0x53] && !p2.effects[0x54]);
    for(unsigned gate=0;gate<10;++gate){
        setup(&cpu);if(gate==0)inside=1;else if(gate==1)failed=1;else if(gate==2)scene_owner=1;
        else if(gate==3)psx_mod_write_byte(PLAY+0x10,1);else if(gate==4)psx_mod_write_byte(PLAY+0x1C,1);
        else if(gate==5)life.status[1]=MMX6_COOP_ABSENT;else if(gate==6)life.status[1]=MMX6_COOP_FALLEN;
        else if(gate==7)cpu.gpr[31]=0x80021600;else if(gate==8)psx_mod_write_byte(PLAY+1,2);
        else{life.status[1]=MMX6_COOP_JOINING;p2.body[0x46]=1;}
        controller(&cpu,0);CHECK(!occurrences(0x80020D74) && !occurrences(0x80020DC8));
    }
    for(unsigned departing=0;departing<2;++departing){
        setup(&cpu);life.status[1]=departing?MMX6_COOP_LEAVING:MMX6_COOP_DYING;
        terminal_player=1;p2.trails[3]=p2.trails[4]=1;controller(&cpu,0);
        CHECK(occurrences(0x80020DC8)==1 && life.status[1]==(departing?MMX6_COOP_ABSENT:MMX6_COOP_FALLEN) && !p2.trails[3]);
        controller(&cpu,0);CHECK(occurrences(0x80020DC8)==1);
    }
    setup(&cpu);life.status[0]=MMX6_COOP_FALLEN;psx_mod_write_byte(PLAYER+4,3);stage_driver=1;stage_call=0;marker_override=1;cpu.gpr[4]=PLAY;
    CHECK(stage_tick(&cpu,0x8001E9EC));CHECK(occurrences(0x8001E9EC)==1 && occurrences(0x80020D74)==1 && occurrences(0x80020DC8)==1);
    CHECK(psx_mod_read_word(PLAY+0x90)==1 && !inside && !zero_world && !stage_call && !state_track.count);
}
static void menu_freeze_and_select_resume(void){
    CPUState cpu;setup(&cpu);life.status[1]=MMX6_COOP_ABSENT;pad_buttons=0xFFFE;
    life.select_armed=1;PlayerContext before=p2;
    for(unsigned phase=1;phase<=3;++phase){
        psx_mod_write_byte(PLAY+1,(uint8_t)phase);controller(&cpu,0);
        CHECK(!call_count && life.select_previous && !life.rejoin_pending);
    }
    CHECK(!memcmp(&p2,&before,sizeof p2) && !life.select_frames);
    psx_mod_write_byte(PLAY+1,0);controller(&cpu,0); /* Held UI Select is not a fresh rejoin. */
    CHECK(life.status[1]==MMX6_COOP_ABSENT && !life.rejoin_pending && !call_count);
    pad_buttons=0xFFFF;controller(&cpu,0);CHECK(!life.select_previous && !call_count);
    life.status[1]=MMX6_COOP_ALIVE;controller(&cpu,0); /* Fixture restores eligibility; no join success is claimed. */
    CHECK(occurrences(0x80034DCC)==1 && occurrences(0x8002012C)==1 && occurrences(0x8002F288)==1);
    CHECK(occurrences(0x80020D74)==1 && occurrences(0x80020DC8)==1);
    setup(&cpu);inside=1;psx_mod_write_byte(PLAY+1,2);pad_buttons=0xFFFE;
    controller(&cpu,0);CHECK(!call_count && !life.select_previous); /* Native owned-menu context is already inside. */
}
static void native_menu_campaign_authority(void){
    CPUState cpu;setup(&cpu);stage_call=0;pause_owner=1;zero_menu_loaded=1;menu_probe=1;
    psx_mod_write_byte(PLAY+1,2);
    /* An earlier gameplay Select may remain in native previous-input state.
     * The personal menu must receive Right/Start/Cross while Select cannot
     * reach the original Quit branch's held or rising-edge word. */
    previous_input=0x0100;pad_buttons=(uint16_t)~0x4029u;
    const uint16_t resident_input[3]={0xBEEF,0x1234,0x5678};
    for(unsigned i=0;i<3;++i)psx_mod_write_half(0x800C456C+i*2,resident_input[i]);
    PlayerContext resident;capture_player(&resident);
    CHECK(stage_tick(&cpu,0x8001E9EC));
    CHECK(call_count==1 && menu_input[0]==0x2840 && menu_input[1]==0x0100 && menu_input[2]==0x2840);
    CHECK(previous_input==0x2840 && life.select_previous && !life.select_frames);
    for(unsigned i=0;i<3;++i)CHECK(psx_mod_read_half(0x800C456C+i*2)==resident_input[i]);
    PlayerContext after;capture_player(&after);CHECK(!memcmp(&after,&resident,sizeof resident));
    CHECK(!inside && !zero_world && !stage_call && !state_track.count && !failed);

    /* P1 remains the campaign authority: its original Select edge reaches
     * the native menu unchanged, independently of P2's held Select. */
    setup(&cpu);stage_call=0;pause_owner=0;menu_probe=2;psx_mod_write_byte(PLAY+1,2);
    pad_buttons=0xFFFE;psx_mod_write_half(0x800C456C,0x0100);psx_mod_write_half(0x800C4570,0x0100);
    CHECK(stage_tick(&cpu,0x8001E9EC));
    CHECK(call_count==1 && menu_input[0]==0x0100 && menu_input[2]==0x0100 && life.select_previous);

    /* When P2 owns the ordinary survivor world, Select keeps its gameplay
     * meaning. The restriction is the owned personal-menu boundary only. */
    setup(&cpu);stage_call=0;menu_probe=1;life.status[0]=MMX6_COOP_FALLEN;
    psx_mod_write_byte(PLAYER+4,3);pad_buttons=0xFFFE;
    CHECK(stage_tick(&cpu,0x8001E9EC));
    CHECK(call_count==1 && menu_input[0]==0x0100 && menu_input[2]==0x0100 && pause_owner==-1);
    CHECK(!inside && !zero_world && !stage_call && !state_track.count && !failed);
}
static void draw_order_retained_packets_and_survivor(void){
    CPUState cpu;setup(&cpu);for(unsigned i=0;i<3;++i){p2.trails[i*0x60+3]=1;p2.effects[i*0x50+3]=1;}
    p2.shots[3]=1;put32(p2.shots+0x38,assets);put32(p2.shots+0x3C,assembly);p2.shots[0x42]=0;p2.shots[0x43]=0x78;
    PlayerContext resident;capture_player(&resident);render(&cpu,0x800232D4);
    const uint32_t expected[]={PLAYER,TRAILS+0xC0,TRAILS+0x60,TRAILS,0x800950A0u};
    CHECK(draw_count==5 && !memcmp(drawn,expected,sizeof expected)); /* Native Zero skips attached glows. */
    CHECK(tag_count==10 && bank_count==4); /* body+shot share actual pixels, three distinct native trail palettes. */
    CHECK(psx_mod_read_word(SCRATCH+0x100)==0x800A0000 && psx_mod_read_word(SCRATCH+0x104)==0x800A8000);
    for(unsigned i=0;i<0x100;++i)CHECK(psx_mod_read_byte(0x800A8000+i)==0xE7);
    for(unsigned i=0;i<5;++i){
        uint32_t at=packets+i*40,expanded=packets+40000+i*80,mode=packets+MODES_AT+i*8;
        CHECK(psx_mod_read_word(at)==(expanded&0xFFFFFFu));CHECK(psx_mod_read_word(mode)==(0x01000000u|(at&0xFFFFFFu)));
        /* The later shot shares body's priority0, so native tail append
         * retargets body's final GT3 across the intervening priority4 trails. */
        uint32_t next=i==0?packets+MODES_AT+4*8:mode+8;
        CHECK((psx_mod_read_word(expanded+40)&0xFFFFFFu)==(next&0xFFFFFFu));
    }
    CHECK(bank_first[1]==0x1131 && bank_first[2]==0x1121 && bank_first[3]==0x1111);
    uint32_t trail_tail=0x8008EB08+4*4;CHECK(psx_mod_read_word(trail_tail)==packets+40000+3*80+40);
    uint32_t second_tag=packets+40000+1*80+40;CHECK((psx_mod_read_word(second_tag)&0xFFFFFFu)==((packets+MODES_AT+2*8)&0xFFFFFFu));
    PlayerContext after;capture_player(&after);CHECK(!memcmp(&resident,&after,sizeof after) && !inside && !state_track.count && !failed);
    capture(packets,previous_frame,sizeof previous_frame);
    psx_mod_write_word(SCRATCH,1);begin_world_draw(&cpu,0x80025FB0u);
    psx_mod_write_word(SCRATCH+0x124,0);native_budget=0;draw_count=tag_count=0;
    render(&cpu,0x800232D4);CHECK(draw_count==5 && bank_count==4 && !failed);
    CHECK(!memcmp(previous_frame,memory(packets),sizeof previous_frame)); /* Opposite DMA frame stays intact. */
    CHECK(psx_mod_read_word(packets+FRAME_ARENA)==((packets+FRAME_ARENA+40000)&0xFFFFFFu));
    CHECK(psx_mod_read_word(SCRATCH+0x100)==0x800A0000 && psx_mod_read_word(SCRATCH+0x104)==0x800A8000);
    for(unsigned gate=0;gate<7;++gate){setup(&cpu);if(gate==0)inside=1;else if(gate==1)failed=1;else if(gate==2)life.status[1]=MMX6_COOP_ABSENT;else if(gate==3)life.status[1]=MMX6_COOP_FALLEN;else if(gate==4)texture_support=0;else if(gate==5)enrolled=0;else p2.body[3]=0;render(&cpu,0);CHECK(!draw_count);}
    setup(&cpu);p2.trails[3]=p2.trails[0x63]=p2.trails[0xC3]=1;enter_zero();inside=zero_world=1;world_packets=packets;
    cpu.gpr[4]=TRAILS+0xC0;CHECK(render_survivor(&cpu,0x800232D4));
    CHECK(draw_count==1 && drawn[0]==TRAILS+0xC0 && world_packets==packets+40);
    cpu.gpr[4]=TRAILS+0x60;CHECK(render_survivor(&cpu,0x800232D4));CHECK(world_packets==packets+80);
    cpu.gpr[4]=TRAILS+1;CHECK(!render_survivor(&cpu,0x800232D4));
    cpu.gpr[4]=EFFECTS;CHECK(!render_survivor(&cpu,0x800232D4)); /* Zero's world does not draw X glows. */
    cpu.gpr[4]=0x8008EF48;CHECK(!render_survivor(&cpu,0x800232D4));
    CHECK(psx_mod_read_word(SCRATCH+0x100)==0x800A0000 && psx_mod_read_word(SCRATCH+0x104)==0x800A8000);
    zero_world=inside=0;leave_zero();CHECK(!state_track.count && !world_render && !failed);
    setup(&cpu);psx_mod_write_word(SCRATCH+0x124,1001);render(&cpu,0);CHECK(!failed && !draw_count); /* Native budget exhaustion remains a no-output return. */
    setup(&cpu);psx_mod_write_word(SCRATCH+0x124,0x80000000u);render(&cpu,0);CHECK(failed && !draw_count); /* Negative budget would bypass native's signed comparison. */
}
static void borrowed_menu_retains_primary_pools(void){
    CPUState cpu;setup(&cpu);PlayerContext primary;capture_player(&primary);
    memset(primary.shots,0,sizeof primary.shots);memset(primary.trails,0,sizeof primary.trails);memset(primary.effects,0,sizeof primary.effects);
    put32(primary.body+0x38,0x80040000);put32(primary.body+0x3C,0x80041000);primary.body[0x16]=4;primary.body[0x42]=0;primary.body[0x43]=0x78;primary.body[0x47]=0;
    for(unsigned i=0;i<64;++i)psx_mod_write_byte(0x80040000+i,zero_compressed[i]);
    for(unsigned i=0;i<2;++i){uint8_t *effect=primary.effects+i*0x50;effect[0]=0x21;effect[3]=effect[4]=1;effect[0x16]=4;
        put32(effect+0x3C,0x80045000);effect[0x42]=2;effect[0x43]=0x78;}
    primary.trails[0]=0x11;primary.trails[3]=primary.trails[4]=1;primary.trails[0x16]=4;
    put32(primary.trails+0x38,0x80040000);put32(primary.trails+0x3C,0x80041000);primary.trails[0x42]=0;primary.trails[0x43]=0x78;
    primary.shots[0]=2;primary.shots[3]=primary.shots[4]=1;primary.shots[0x16]=4;
    put32(primary.shots+0x38,0x80040000);primary.shots[0x42]=0;primary.shots[0x43]=0x78;
    project_player(&primary);enter_zero();inside=zero_world=1;pause_owner=1;world_packets=packets;
    PlayerContext zero_before;capture_player(&zero_before);cpu.gpr[4]=PLAYER;
    CHECK(render_survivor(&cpu,0x800232D4) && draw_count==6 && !failed);
    const uint32_t expected[]={PLAYER,PLAYER,EFFECTS,EFFECTS+0x50,TRAILS,0x800950A0};
    CHECK(!memcmp(drawn,expected,sizeof expected));PlayerContext after;capture_player(&after);
    CHECK(!memcmp(&zero_before,&after,sizeof after) && !memcmp(&p1,&primary,sizeof primary));
    CHECK(!render_x_death && !world_render && !state_track.count && !state_track.error);
    zero_world=inside=0;leave_zero();
}
static void borrowed_menu_restores_primary_sprite_sheet(void){
    CPUState cpu;setup(&cpu);menu_vram_probe=1;
    for(unsigned i=0;i<1024*512;++i)test_vram[i]=original_menu_vram[i]=(uint16_t)(i*13u+7u);
    for(unsigned i=0;i<MENU_BYTES;i+=2)psx_mod_write_half(menu_memory+i,(uint16_t)(i^0xA55A));
    menu_vram(&cpu,1);CHECK(zero_menu_loaded && !gp0_upload_stage);
    for(unsigned y=0;y<256;++y)for(unsigned x=320;x<384;++x){
        CHECK(test_vram[y*1024+x]==original_menu_vram[y*1024+x]);test_vram[y*1024+x]=0x55AA;
    }
    /* Model the original borrowed Zero upload, without changing X's cached
     * animation frame. Switching back must restore those exact native pixels. */
    menu_vram(&cpu,0);CHECK(!zero_menu_loaded && !gp0_upload_stage);
    CHECK(!memcmp(test_vram,original_menu_vram,sizeof test_vram));
    CHECK(!state_track.count && !state_track.error);
}
static void native_giga_backup_survives_private_callbacks(void){
    CPUState cpu;setup(&cpu);uint32_t expected[16];
    for(unsigned i=0;i<16;++i){
        expected[i]=0x12340000u+i*0x010101u;
        psx_mod_write_word(0x80090CD0u+i*4,expected[i]);
    }
    enter_zero();
    /* Original Zero801EA7A4 phase1 copies this exact shared16-word table
     * into writable overlay801EF974, then temporarily fills it withFF. */
    for(unsigned i=0;i<16;++i){
        psx_mod_write_word(0x801EF974u+i*4,psx_mod_read_word(0x80090CD0u+i*4));
        psx_mod_write_word(0x80090CD0u+i*4,UINT32_MAX);
    }
    leave_zero();
    enter_zero();
    /* Original801EA888 phase2 consumes the earlier callback's backup. */
    for(unsigned i=0;i<16;++i)
        psx_mod_write_word(0x80090CD0u+i*4,psx_mod_read_word(0x801EF974u+i*4));
    leave_zero();
    for(unsigned i=0;i<16;++i)CHECK(psx_mod_read_word(0x80090CD0u+i*4)==expected[i]);
    CHECK(!zero_projected && !state_track.count && !state_track.error && !failed);
}
static void deferred_shared_effect_owner_context(void) {
    CPUState cpu;setup(&cpu);stage_call=0;shared_probe=1;
    const uint32_t actor=0x80091298u,table=0x800FA640u;
    PlayerContext primary;capture_player(&primary);
    inside=1;enter_zero();CHECK(shared_effect_allocate(&cpu,0x8002C398u));
    CHECK(cpu.gpr[2]==actor && shared_effect_owners[0]==2);
    leave_zero_context(1);inside=0;
    psx_mod_write_byte(actor,1);psx_mod_write_byte(actor+1,26);
    psx_mod_write_word(SCRATCH+0x88,table);psx_mod_write_word(table+26*4,0x801EE254u);
    cpu.gpr[31]=0x80020438u;cpu.gpr[4]=actor;shared_probe_seat=1;
    CHECK(shared_effect_callback(&cpu,0x801EE254u));
    CHECK(shared_probe_calls==1 && cpu.gpr[2]==0x1234 && p2.body[0xD8]==0x4C);
    CHECK(psx_mod_read_byte(actor+4)==1 && psx_mod_read_word(actor+0x50)==0);
    PlayerContext after;capture_player(&after);CHECK(!memcmp(&primary,&after,sizeof primary));
    CHECK(psx_mod_read_word(OVERLAY)==0x11223344 && !inside && !zero_projected && !shared_fx_call && !shared_fx_allocate_call && !state_track.count);
    CHECK(psx_mod_read_word(PLAY+0x90)==1);
    cpu.gpr[31]=0x80020434u;CHECK(!shared_effect_callback(&cpu,0x801EE254u));
    cpu.gpr[31]=0x80020438u;cpu.gpr[4]=actor+1;CHECK(!shared_effect_callback(&cpu,0x801EE254u));
    cpu.gpr[4]=actor;psx_mod_write_word(table+26*4,0x80010000u);CHECK(!shared_effect_callback(&cpu,0x801EE254u));
    psx_mod_write_word(table+26*4,0x801EE254u);shared_probe_delete=1;
    CHECK(shared_effect_callback(&cpu,0x801EE254u));CHECK(!shared_effect_owners[0]);
    CHECK(shared_effect_allocate(&cpu,0x8002C398u));CHECK(shared_effect_owners[0]==1);
    psx_mod_write_byte(actor,1);psx_mod_write_byte(actor+1,17);
    psx_mod_write_word(table+17*4,0x8004AE1Cu);shared_probe_delete=0;shared_probe_seat=0;
    inside=1;enter_zero();zero_world=1;
    psx_mod_write_byte(OVERLAY+0x5900,0x6D);
    PlayerContext zero;capture_player(&zero);
    cpu.gpr[4]=actor;cpu.gpr[31]=0x80020438u;
    CHECK(shared_effect_callback(&cpu,0x8004AE1Cu));
    capture_player(&after);CHECK(!memcmp(&zero,&after,sizeof zero));
    CHECK(inside && zero_world && zero_projected && psx_mod_read_byte(OVERLAY+0x5900)==0x6D);
    CHECK(psx_mod_read_word(SCRATCH+0x1C)==assembly && p1.body[0xD8]==0x4C);
    zero_world=0;leave_zero_context(1);inside=0;
    CHECK(psx_mod_read_byte(PLAYER+0xD8)==0x4C && !state_track.count && !state_track.error);
    CHECK(shared_probe_calls==3);
    native_player_init(&cpu,0x8003BD24u);
    for(unsigned i=0;i<96;++i)CHECK(!shared_effect_owners[i]);
}
static void deferred_ui_effect_retains_owner_atlas(void){
    CPUState cpu;setup(&cpu);uint32_t actor=0x80091298u;
    psx_mod_write_byte(actor,1);psx_mod_write_byte(actor+1,17);psx_mod_write_byte(actor+3,1);
    psx_mod_write_word(menu_assembly,0xCC);
    psx_mod_write_byte(actor+0x16,0x37);psx_mod_write_word(actor+0x3C,menu_assembly+0xCC);
    psx_mod_write_half(actor+0x42,0x7E50);shared_effect_owners[0]=2;
    /* Deliberately different resident X tiles/CLUT and private Zero source. */
    memset(test_vram,0xBB,sizeof test_vram);
    for(unsigned y=0;y<16;++y)for(unsigned x=0;x<4;++x)
        test_zero_ui[(256+80+y)*1024+896+16+x]=0x1111;
    psx_mod_write_half(menu_memory+0x10000+((505-496)*64+1)*2,0x1234);
    cpu.gpr[4]=actor;
    CHECK(render_survivor(&cpu,0x800232D4u));
    CHECK(draw_count==1 && drawn[0]==actor && bank_count==1 && bank_first[0]==0x1234);
    CHECK(world_packets==packets+40 && psx_mod_read_word(SCRATCH+0x100)==0x800A0000);
    uint8_t first[80];capture(packets+PLAYER_PACKET_BYTES,first,sizeof first);
    /* P2's normal body draw appends instead of overwriting the shared actor. */
    cpu.gpr[4]=PLAYER;render(&cpu,0x800232D4u);
    CHECK(!failed && world_packets==packets+80 && bank_count==2);
    CHECK(!memcmp(first,memory(packets+PLAYER_PACKET_BYTES),sizeof first));
    CHECK(!state_track.count && !state_track.error && !world_render);
    psx_mod_write_word(actor+0x3C,menu_assembly);cpu.gpr[4]=actor;
    CHECK(!render_survivor(&cpu,0x800232D4u)); /* Table base is not the resolved native assembly. */
    psx_mod_write_word(actor+0x3C,menu_assembly+0xCC);
    shared_effect_owners[0]=1;cpu.gpr[4]=actor;CHECK(!render_survivor(&cpu,0x800232D4u));
    shared_effect_owners[0]=2;psx_mod_write_byte(actor+1,26);CHECK(!render_survivor(&cpu,0x800232D4u));
    psx_mod_write_byte(actor+1,17);psx_mod_write_word(actor+0x3C,assembly);CHECK(!render_survivor(&cpu,0x800232D4u));
    /* A full FT4 retains its original UVs in a complete source page. */
    uint16_t full=zero_ui_effect_bank(0x3E,0x7E50,UINT16_MAX);CHECK(full);
    unsigned count=bank_count;CHECK(zero_ui_effect_bank(0x3E,0x7E50,UINT16_MAX)==full && bank_count==count);
    CHECK(!zero_ui_effect_bank(0xBE,0x7E50,0) && !zero_ui_effect_bank(0x3E,0x7800,0));
}
static void arrival_draw_precedes_stage_callback(void){
    CPUState cpu;setup(&cpu);stage_call=0;world_packets=0;
    /* Original arrival draws before the first ordinary stage callback. */
    begin_world_draw(&cpu,0x80025FB0u);render(&cpu,0x800232D4u);
    CHECK(!failed && draw_count==1 && bank_count==1 && world_packets==packets+40);
    psx_mod_write_word(SCRATCH,1);begin_world_draw(&cpu,0x80025FB0u);
    CHECK(world_packets==packets+FRAME_ARENA && !stage_call && !state_track.count);
}
static void deferred_icon_effect_retains_zero_source(void){
    CPUState cpu;setup(&cpu);uint32_t actor=0x80091298u;
    psx_mod_write_word(assembly+0x3C,0xCC);
    psx_mod_write_byte(actor,1);psx_mod_write_byte(actor+1,26);psx_mod_write_byte(actor+3,1);
    psx_mod_write_word(actor+0x3C,assembly+0xCC);psx_mod_write_half(actor+0x42,0x7802);
    shared_effect_owners[0]=2;cpu.gpr[4]=actor;
    memset(test_vram,0xBB,sizeof test_vram);
    for(unsigned y=0;y<256;++y)for(unsigned x=0;x<64;++x)
        test_zero_ui[y*1024+768+x]=0x1111;
    psx_mod_write_half(active_palette+2*32+2,0x4321);
    CHECK(render_survivor(&cpu,0x800232D4u));
    CHECK(!failed && draw_count==1 && bank_count==1 && bank_first[0]==0x4321);
    CHECK(banks[0].tile==UINT16_MAX && world_packets==packets+40);
    uint32_t expanded=packets+PLAYER_PACKET_BYTES;
    CHECK(psx_mod_read_word(expanded+4)==0x37808080u);
    CHECK((psx_mod_read_word(expanded+12)&0xFFFFu)==0xC0D0u);
    CHECK((psx_mod_read_word(expanded+24)&0xFFFFu)==0xC0C0u);
    CHECK((psx_mod_read_word(expanded+36)&0xFFFFu)==0xD0D0u);
    CHECK(psx_mod_read_word(SCRATCH+0x100)==0x800A0000 && !world_render && !state_track.count);
    uint16_t old=banks[0].id;
    psx_mod_write_half(active_palette+2*32+2,0x5678);
    uint16_t fresh=zero_atlas_effect_bank(0x2C,0x7802,UINT16_MAX,0);
    CHECK(fresh && fresh!=old && bank_first[fresh-0x6000]==0x5678);
    shared_effect_owners[0]=1;CHECK(!render_survivor(&cpu,0x800232D4u));
    shared_effect_owners[0]=2;psx_mod_write_word(actor+0x3C,assembly);
    CHECK(!render_survivor(&cpu,0x800232D4u));
    CHECK(!zero_atlas_effect_bank(0x2C,0x77FF,0,0) && !zero_atlas_effect_bank(0x2C,0x7A00,0,0));
}
static void private_giga_shots_retain_zero_source(void){
    for(unsigned primitive=1;primitive<=2;++primitive){
        CPUState cpu;setup(&cpu);const uint32_t actor=0x800950A0u;
        PlayerContext resident;capture_player(&resident);
        psx_mod_write_word(assembly+0x3C,0xCC);
        memset(p2.shots,0,sizeof p2.shots);
        p2.shots[0]=0x21;p2.shots[1]=44;p2.shots[3]=1;
        put32(p2.shots+0x3C,assembly+0xCC);p2.shots[0x42]=2;p2.shots[0x43]=0x78;
        memset(test_vram,0xBB,sizeof test_vram);
        for(unsigned y=0;y<256;++y)for(unsigned x=768;x<1024;++x)
            test_zero_ui[y*1024+x]=0x1111;
        psx_mod_write_half(active_palette+2*32+2,0x4321);
        icon_packet_probe=primitive;render_replacement_probe=1;
        p2.shots[0x16]=0x11; /* Original personal Giga bucket. */
        render(&cpu,0x800232D4u);
        CHECK(!failed && draw_count==2 && drawn[1]==actor && bank_count==2);
        CHECK(bank_first[1]==0x4321 && banks[1].tile==(primitive==1?UINT16_MAX:0xD0C0));
        uint32_t expanded=packets+PLAYER_PACKET_BYTES+80;
        CHECK(psx_mod_read_word(packets+40)==(expanded&0xFFFFFFu));
        CHECK(psx_mod_read_word(expanded+4)==(primitive==1?0x37808080u:0x35000000u));
        CHECK(world_packets==packets+80 && !state_track.count && !world_render);
        PlayerContext after;capture_player(&after);CHECK(!memcmp(&resident,&after,sizeof after));
        project_player(&p2);CHECK(zero_icon_effect(actor));
        inside=zero_world=1;cpu.gpr[4]=actor;
        CHECK(render_survivor(&cpu,0x800232D4u) && !failed && draw_count==3);
        CHECK(world_packets==packets+120 && bank_count==2 && !state_track.count);
        inside=zero_world=0;
        CHECK(!zero_icon_effect(actor+1) && !zero_icon_effect(0x800964A0u));
        psx_mod_write_byte(actor+1,26);CHECK(!zero_icon_effect(actor));
        psx_mod_write_byte(actor+1,44);psx_mod_write_byte(actor,0);CHECK(!zero_icon_effect(actor));
        psx_mod_write_byte(actor,0x21);psx_mod_write_word(actor+0x3C,assembly);CHECK(!zero_icon_effect(actor));
        psx_mod_write_word(actor+0x3C,assembly+0xCC);
        render_x_death=1;CHECK(!zero_icon_effect(actor));render_x_death=0;
        psx_mod_write_byte(PLAYER+2,0);CHECK(!zero_icon_effect(actor));
        CHECK(!render_survivor(&cpu,0x800232D4u));
        project_player(&resident);render_replacement_probe=0;clear_banks();
    }
}
int main(void){CHECK(PLAYER_MODE_OFFSET+PLAYER_PACKET_LIMIT*8u<=FRAME_ARENA);
    controller_pair_and_restoration();lifetime_and_gates();menu_freeze_and_select_resume();native_menu_campaign_authority();draw_order_retained_packets_and_survivor();borrowed_menu_retains_primary_pools();borrowed_menu_restores_primary_sprite_sheet();native_giga_backup_survives_private_callbacks();clear_banks();
    deferred_shared_effect_owner_context();
    deferred_ui_effect_retains_owner_atlas();clear_banks();
    arrival_draw_precedes_stage_callback();clear_banks();
    deferred_icon_effect_retains_zero_source();clear_banks();
    private_giga_shots_retain_zero_source();
    puts("private native effects actual-plugin call order, gates, lifetime projection and retained packet ownership PASS");return 0;}
