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
static unsigned ride_probe,ride_overlap,ride_ticks,ride_seat;
static unsigned door_native_probe,door_ticks,door_draws,door_subtype_allowed;
static unsigned icon_packet_probe,dash_packet_probe;
static unsigned render_replacement_probe;
static unsigned working_palette_probe,working_palette_probe_calls;
static unsigned death_packet_probe,death_origin_probe,nova_probe;
static unsigned scene_transport_probe;
static unsigned clear_probe,clear_worlds,clear_zero_worlds,clear_fades;
static unsigned clear_constructors[2],clear_body_ticks[2],clear_poses[2],clear_outgoing[2],clear_pose_limit[2];
static unsigned clear_air_ticks,clear_air_limit;
static uint16_t pad_buttons=0xFFFF;
static const unsigned resource_offsets[7]={0x14,0x1C,0x24,0x28,0x38,0x3C,0xA8};
#ifdef MMX6_TEST_SESSION_RESOURCES
/* Only the lifecycle fixture uses the real SDK-owned arenas and extents.
 * Existing projection fixtures retain their independent RAM contract. */
uint8_t *mmx6_test_session_pointer(uint32_t address);
#endif
static uint8_t *memory(uint32_t a){
#ifdef MMX6_TEST_SESSION_RESOURCES
    if ((a&0x1FFFFFFFu)>=0x1F000000u && (a&0x1FFFFFFFu)<0x1F800000u)
        return mmx6_test_session_pointer(a);
    if ((a&0x1FFFFFFFu)>=0x00800000u && (a&0x1FFFFFFFu)<0x01000000u)
        return mmx6_test_session_pointer(a);
#endif
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
int psx_mod_netplay_is_active(void){
#ifdef MMX6_TEST_NETPLAY_ACTIVE
    return MMX6_TEST_NETPLAY_ACTIVE;
#else
    return 0;
#endif
}
int psx_mod_netplay_has_state_digest(void){return 1;}
int psx_mod_texture_banks_supported(void){return texture_support;}
int psx_mod_local_view_scope(void){return 0;}
int psx_mod_widescreen_x_margin(void){return 0;}
void psx_mod_counter_add(const char *name,uint32_t count){(void)name;(void)count;}
int psx_mod_read_disc_file(const char *name,void *data,uint32_t size,uint32_t *out){(void)name;(void)data;(void)size;(void)out;CHECK(0);return 0;}
const uint16_t *gpu_get_vram(void){return test_vram;}
void gpu_write_gp0(uint32_t value){
#ifdef MMX6_TEST_PRIVATE_VIEW_GPU
    if(MMX6_TEST_PRIVATE_VIEW_GPU(value,0))return;
#endif
    CHECK(menu_vram_probe);
    if(!gp0_upload_stage){CHECK(value==0xA0000000);gp0_upload_stage=1;return;}
    if(gp0_upload_stage==1){gp0_upload_x=value&0xFFFF;gp0_upload_y=value>>16;gp0_upload_stage=2;return;}
    if(gp0_upload_stage==2){gp0_upload_width=value&0xFFFF;gp0_upload_left=gp0_upload_width*(value>>16);gp0_upload_at=0;CHECK(gp0_upload_left && !(gp0_upload_left&1));gp0_upload_stage=3;return;}
    for(unsigned i=0;i<2;++i){unsigned x=gp0_upload_x+gp0_upload_at%gp0_upload_width,y=gp0_upload_y+gp0_upload_at/gp0_upload_width;
        CHECK(x<1024 && y<512 && gp0_upload_left);test_vram[y*1024+x]=(uint16_t)(value>>(i*16));++gp0_upload_at;--gp0_upload_left;}
    if(!gp0_upload_left)gp0_upload_stage=0;
}
void gpu_set_gp0_source(uint32_t address){
#ifdef MMX6_TEST_PRIVATE_VIEW_GPU
    if(MMX6_TEST_PRIVATE_VIEW_GPU(address,1))return;
#endif
    CHECK(menu_vram_probe && !address && !gp0_upload_stage);
}
#ifndef MMX6_TEST_SESSION_RESOURCES
int psx_mod_define_texture_bank(uint16_t id,uint32_t width,uint32_t height,const uint16_t *pixels){
    CHECK(id>=0x6000 && id<0x7000 && width==height && (width==16 || width==256));
    bank_first[id-0x6000]=pixels[0];return 1;
}
#endif
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
    if(dash_packet_probe && actor==0x80091298u) {
        /* Original Zero follow frame43: common tile0 at page5/UV0,B0,
         * packed flags4 select C3 from the actor's base C2 palette. */
        q[1]=0x7D000000u;q[3]=0x7803B000u;
        memset(q+4,0,6*sizeof *q);
    } else if(death_packet_probe && actor==0x800CD410u) {
        /* Original unflipped FX11 frame113 uses page27/UV E0,F0 and CLUT7802.
         * Keep this external packet independent of the ownership predicate. */
        q[1]=0x7D000000u;q[3]|=0xF0E0u;
        memset(q+4,0,6*sizeof *q);
    } else if(zero_ui_effect(actor)) {
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
    psx_mod_write_word(mode+4,dash_packet_probe && actor==0x80091298u?0xE1000025u:
        death_packet_probe && actor==0x800CD410u?0xE1000027u:zero_ui_effect(actor)?0xE100003Eu:
        icon_packet_probe==2 && actor>=0x800950A0u && actor<0x800964A0u?0xE100002Eu:0xE1000040u);
    unsigned priority=psx_mod_read_byte(actor+0x16);
    uint32_t tail=0x8008EB08u+(psx_mod_read_word(SCRATCH)&1u)*128+(priority>>4)*32+(priority&7)*4;
    uint32_t previous=psx_mod_read_word(tail);
    psx_mod_write_word(previous,(psx_mod_read_word(previous)&0xFF000000u)|(mode&0xFFFFFFu));
    psx_mod_write_word(tail,at);
    psx_mod_write_word(SCRATCH+0x100,at+40);psx_mod_write_word(SCRATCH+0x104,mode+8);
    psx_mod_write_word(SCRATCH+0x124,++native_budget);
}
static uint32_t original_door_predicate(uint32_t actor) {
    /* External original80050C88..80050DFC contract, not the plugin's gate:
     * signed authored centers, horizontal overlap and vertical containment.
     * In particular, a merely overlapping vertical box is insufficient. */
    if(psx_mod_read_byte(PLAYER+0xA4) || (psx_mod_read_byte(PLAYER+0x5C)&0x80) ||
       psx_mod_read_byte(PLAYER+5)==3 || psx_mod_read_byte(PLAYER+
           (psx_mod_read_byte(PLAYER+2)?0x8E:0x7A)))return 0;
    int x=(int16_t)psx_mod_read_half(PLAYER+10),dx=(int16_t)psx_mod_read_half(actor+10);
    if(x>dx)return 0;
    uint32_t a=psx_mod_read_word(actor+0x68),p=psx_mod_read_word(PLAYER+0x68);
    CHECK(a>=0x80010000u && a<=0x801FFFFCu && p>=0x80010000u && p<=0x801FFFFCu);
    int ac=(int16_t)(dx+(int8_t)psx_mod_read_byte(a));
    int pc=(int16_t)(x+(int8_t)psx_mod_read_byte(p));
    int distance=(int16_t)(ac>pc?ac-pc:pc-ac);
    if(distance>psx_mod_read_byte(a+2)+psx_mod_read_byte(p+2))return 0;
    int ay=(int16_t)psx_mod_read_half(actor+14)+(int8_t)psx_mod_read_byte(a+1);
    int py=(int16_t)psx_mod_read_half(PLAYER+14)+(int8_t)psx_mod_read_byte(p+1);
    return (int16_t)(py-psx_mod_read_byte(p+3))>=(int16_t)(ay-psx_mod_read_byte(a+3)) &&
        (int16_t)(py+psx_mod_read_byte(p+3))<=(int16_t)(ay+psx_mod_read_byte(a+3));
}
void psx_dispatch_call(CPUState *cpu,uint32_t address,uint32_t ret){
    (void)ret;CHECK(call_count<512 && state_track.count);calls[call_count++]=address;
    if(clear_probe) {
        /* Independent bounded native contracts: 1EA28 tests resident state3,
         * 3B870 starts native25 only for actual clear10; native25 eventually
         * calls outgoing1 and 3674C retires that body. Different character
         * lengths intentionally force the final-body world handoff. */
        unsigned seat=psx_mod_read_byte(PLAYER+2);
        CHECK(seat<2 && zero_projected==(int)seat);
        if(seat)projected();
        if(address==0x8001E9ECu) {
            CHECK(stage_call && zero_world==(int)seat && cpu->gpr[4]==PLAY);++clear_worlds;
            if(seat)++clear_zero_worlds;
            psx_mod_write_word(PLAY+0x90,psx_mod_read_word(PLAY+0x90)+1);
            if(psx_mod_read_byte(PLAY+1)) {
                CHECK(psx_mod_read_byte(PLAYER+4)==3 && p2.body[4]==3);
                psx_mod_write_byte(PLAY,12);return;
            }
            if(psx_mod_read_byte(PLAYER+4)==3) {
                CHECK(p2.body[4]==3);++clear_fades;
                psx_mod_write_byte(PLAY+1,1);return;
            }
            guest(cpu,0x80034DCCu,0,0);
            uint32_t caller=cpu->gpr[31];cpu->gpr[31]=0x80020C70u;
            controller(cpu,0x8002012Cu);cpu->gpr[31]=caller;
            /* Native reward producer follows the player pass, as in 20C40. */
            if(clear_worlds==2)psx_mod_write_byte(PLAY+0x0F,0x10);
            return;
        }
        if(address==0x8003B870u) {
            CHECK(psx_mod_read_byte(PLAY+0x0F)==0x10);
            CHECK(!clear_constructors[seat]++);
            psx_mod_write_byte(PLAYER+5,25);psx_mod_write_byte(PLAYER+6,0);
            psx_mod_write_byte(PLAY+0x1C,1);return;
        }
        if(address==0x80034DCCu) {
            ++clear_body_ticks[seat];unsigned action=psx_mod_read_byte(PLAYER+5);
            if(action==6) {
                CHECK(seat==1 && !clear_constructors[seat]);
                if(++clear_air_ticks>=clear_air_limit)psx_mod_write_byte(PLAYER+5,2);
            } else if((action==2 || action==20) && (psx_mod_read_byte(PLAY+0x0F)&0x10u)) {
                guest(cpu,0x8003B870u,PLAYER,0);
            } else if(action==25 && ++clear_poses[seat]>=clear_pose_limit[seat]) {
                psx_mod_write_byte(PLAYER+5,1);psx_mod_write_byte(PLAYER+6,0);
            } else if(action==1 && ++clear_outgoing[seat]==2) {
                psx_mod_write_byte(PLAYER+3,0);psx_mod_write_byte(PLAYER+4,3);
                psx_mod_write_byte(PLAYER+5,0);
            }
            return;
        }
        CHECK(address==0x8003CD44u || address==0x8002012Cu || address==0x8002F288u ||
              address==0x80020D74u || address==0x80020DC8u);
        return;
    }
    if(scene_transport_probe) {
        /* Bounded original beam/cancellation contracts; these do not rebuild
         * or repair fixed actor metadata on the plugin's behalf. */
        CHECK(scene_call && scene_owner && inside);
        unsigned passenger=scene_transport_probe-1;
        CHECK(psx_mod_read_byte(PLAYER+2)==passenger && zero_projected==(int)passenger);
        if(address==0x8003A980u) {
            psx_mod_write_byte(PLAYER+0xCF,1);psx_mod_write_byte(PLAYER+0x84,0);
            psx_mod_write_byte(PLAYER+0x8C,0);return;
        }
        if(address==0x8003BA04u) { psx_mod_write_byte(PLAYER+0x46,0);return; }
        if(address==0x8003B954u) {
            psx_mod_write_word(PLAYER+0x20,0);psx_mod_write_word(PLAYER+0x24,8u<<16);
            psx_mod_write_word(PLAYER+0x68,0);psx_mod_write_byte(PLAYER+0x67,1);
            psx_mod_write_byte(PLAYER+5,1);psx_mod_write_byte(PLAYER+6,0);return;
        }
        if(address==0x8003674Cu) {
            psx_mod_write_byte(PLAYER+3,0);psx_mod_write_byte(PLAYER+4,3);
            psx_mod_write_byte(PLAYER+5,0);psx_mod_write_byte(PLAYER+6,0);return;
        }
        if(address==0x80017A04u)return;
        if(address==0x8003AD18u) {
            psx_mod_write_byte(PLAYER+4,1);psx_mod_write_byte(PLAYER+5,2);
            psx_mod_write_byte(PLAYER+0x67,0);return;
        }
        if(address==0x8003CCBCu) {
            psx_mod_write_word(PLAYER+0x68,passenger?0x80073D54u:0x80073D50u);return;
        }
        CHECK(0);
    }
    if(door_native_probe) {
        if(address==0x8003CCBCu) {
            CHECK(cpu->gpr[4]==PLAYER);
            psx_mod_write_word(cpu->gpr[4]+0x68,psx_mod_read_byte(cpu->gpr[4]+2)?0x80073D54u:0x80073D50u);
            return;
        }
        if(address==0x80050DFCu) {
            /* Bounded original outer/phase contracts: draw/shared state once,
             * negative ACK admission, resident-only movement and release. */
            uint32_t actor=cpu->gpr[4];++door_ticks;++door_draws;
            unsigned phase=psx_mod_read_byte(actor+5);
            if(phase==1 && (int8_t)psx_mod_read_byte(PLAYER+0xD4)<0) {
                psx_mod_write_byte(PLAYER+0xD4,0xFE);psx_mod_write_word(PLAYER+0x68,0);
                psx_mod_write_byte(PLAY+0x10,1);psx_mod_write_byte(PLAY+0x12,1);
                psx_mod_write_byte(actor+5,2);
            } else if(phase==3) {
                psx_mod_write_word(PLAYER+8,psx_mod_read_word(PLAYER+8)+psx_mod_read_word(actor+0x84));
                if(psx_mod_read_half(0x80097202u)==psx_mod_read_half(0x8009721Eu)) {
                    psx_mod_write_byte(PLAYER+0xD4,0);guest(cpu,0x8003CCBCu,PLAYER,0);
                    psx_mod_write_byte(actor+5,4);
                    psx_mod_write_byte(PLAY+0x10,0);psx_mod_write_byte(PLAY+0x12,0);
                    psx_mod_write_word(PLAY+0x90,psx_mod_read_word(PLAY+0x90)+1);
                }
            } else if(phase==4 && !psx_mod_read_byte(PLAYER+0xD0) &&
                      !psx_mod_read_byte(PLAYER+0xD4) && !psx_mod_read_byte(PLAYER+0xE0))
                psx_mod_write_byte(PLAY+0x1C,0);
            cpu->gpr[2]=0xD008;return;
        }
        if(address==0x80050C88u) {
            if(!door_eligibility(cpu,address))cpu->gpr[2]=original_door_predicate(cpu->gpr[4]);
            return;
        }
        CHECK(address==0x80050250u && cpu->gpr[6]==PLAYER);
        ++door_ticks;++door_draws; /* Native collision/draw precede admission. */
        if(door_subtype_allowed) {
            uint32_t ra=cpu->gpr[31];cpu->gpr[31]=0x80050368u;
            uint32_t hit=guest(cpu,0x80050C88u,cpu->gpr[4],0);cpu->gpr[31]=ra;
            if(hit) { psx_mod_write_byte(PLAY+0x1C,1);psx_mod_write_byte(PLAYER+0xD4,1); }
        }
        cpu->gpr[2]=0xD007;return;
    }
    if(nova_probe)CHECK(psx_mod_read_byte(PLAY+0x1C)==1);
    if(ride_probe) {
        unsigned seat=psx_mod_read_byte(PLAYER+2);
        if(address==0x8002DCF4u) {
            CHECK(cpu->gpr[4]==PLAYER && cpu->gpr[5]==RIDE &&
                psx_mod_read_word(RIDE+0x68)==0x800F3A48u);
            cpu->gpr[2]=!!(ride_overlap&(1u<<seat));return;
        }
        if(address==0x8003CD44u) {
            CHECK(seat==1 && zero_projected);
            uint16_t held=psx_mod_read_half(0x800C456C),pressed=psx_mod_read_half(0x800C4570);
            psx_mod_write_half(PLAYER+0x7C,(uint16_t)((held&0x1000?4:0)|(held&0x40?0x80:0)));
            psx_mod_write_half(PLAYER+0x80,(uint16_t)(pressed&0x40?0x80:0));return;
        }
        if(address==0x80020A08u) {
            /* External native boarding/dismount contract, not game evidence.
             * The plugin must select context; only this model sets D5/pose. */
            ++ride_ticks;ride_seat=seat;
            if(!(psx_mod_read_byte(RIDE+0x97)&0x40)) {
                if(ride_overlap&(1u<<seat)) {
                    psx_mod_write_byte(PLAYER+0xD5,1);
                    psx_mod_write_byte(RIDE+0x97,0x40);
                }
            } else if((psx_mod_read_half(PLAYER+0x7C)&7)==4 &&
                      (psx_mod_read_half(PLAYER+0x80)&0x80)) {
                psx_mod_write_byte(PLAYER+0xD5,0);psx_mod_write_byte(RIDE+0x97,0);
            }
            psx_mod_write_byte(PLAY+0x26,0x5A);cpu->gpr[2]=77;return;
        }
        CHECK(0);
    }
    if(death_origin_probe && address==0x8002C530u){cpu->gpr[2]=0x800CD410u;return;}
    if(death_origin_probe && address==0x80047E34u){
        CHECK(psx_mod_read_word(PLAYER+8)==400u*65536u && psx_mod_read_word(PLAYER+12)==1000u*65536u);
        CHECK(psx_mod_read_word(SCRATCH+0x1C)==assembly);
        uint32_t actor=cpu->gpr[4];
        psx_mod_write_byte(actor,0x21);psx_mod_write_byte(actor+1,0x11);psx_mod_write_byte(actor+3,1);
        psx_mod_write_word(actor+0x3C,assembly+psx_mod_read_word(assembly+4));
        psx_mod_write_half(actor+0x42,0x7802);cpu->gpr[2]=0x8899;return;
    }
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
    if(working_palette_probe && address==0x8003C4ECu) {
        /* Original8003C63C..C690 ordinary Zero contract. This models the
         * native external selector; full engine/native art remains QA. */
        CHECK(inside && zero_projected && psx_mod_read_byte(PLAYER+2)==1);
        CHECK(psx_mod_read_word(SCRATCH+0x24)==palette_source &&
              psx_mod_read_word(SCRATCH+0x28)==active_palette);
        for(unsigned i=0;i<32;++i)psx_mod_write_byte(active_palette+i,
            psx_mod_read_byte(palette_source+i));
        psx_mod_write_byte(0x800C4560,psx_mod_read_byte(0x800C4560)|1);
        ++working_palette_probe_calls;return;
    }
    if(shared_probe && address==0x8002C398u) {
        memset(memory(0x80091298u),0,0x70);cpu->gpr[2]=0x80091298u;return;
    }
    if(shared_probe && (address==0x80049100u || address==0x801EE254u || address==0x8004AE1Cu)) {
        ++shared_probe_calls;CHECK(shared_fx_call);
#ifdef MMX6_COOP_MODERN_STATE
        CHECK(!snapshot_ready());
#endif
        if(shared_probe_seat)projected();
        else {
            CHECK(!zero_projected && !zero_world && psx_mod_read_byte(PLAYER+2)==0);
            CHECK(psx_mod_read_word(OVERLAY)==0x11223344 && psx_mod_read_word(SCRATCH+0x1C)==0x80030100u);
        }
        /* Original80049100 reads canonical PLAYER both at initialization
         * and on subsequent follow updates. Check the allocating context,
         * without reproducing its character/pose-dependent offset table. */
        if(address==0x80049100u) {
            psx_mod_write_word(cpu->gpr[4]+8,psx_mod_read_word(PLAYER+8));
            psx_mod_write_word(cpu->gpr[4]+12,psx_mod_read_word(PLAYER+12));
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
    shared_clear_reset();clear_probe=clear_worlds=clear_zero_worlds=clear_fades=0;
    memset(clear_constructors,0,sizeof clear_constructors);memset(clear_body_ticks,0,sizeof clear_body_ticks);
    memset(clear_poses,0,sizeof clear_poses);memset(clear_outgoing,0,sizeof clear_outgoing);
    clear_air_ticks=clear_air_limit=0;
    shared_fx_call=shared_fx_allocate_call=0;memset(shared_effect_owners,0,sizeof shared_effect_owners);
    shared_probe=shared_probe_seat=shared_probe_delete=shared_probe_calls=0;
    ride_probe=ride_overlap=ride_ticks=ride_seat=ride_call=0;
    door_native_probe=door_ticks=door_draws=both_doors=scene_call=0;both_door_reset();door_subtype_allowed=1;
    icon_packet_probe=dash_packet_probe=render_replacement_probe=0;
    death_packet_probe=death_origin_probe=effect_call=nova_probe=scene_transport_probe=0;memset(death_effect,0,sizeof death_effect);
    working_palette_probe=working_palette_probe_calls=0;working_palette_assets_ready=0;
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
static void check_retired_fixed_pools(const PlayerContext *before,const PlayerContext *after) {
    for(unsigned i=0;i<sizeof after->shots;++i)CHECK(!after->shots[i]);
    for(unsigned i=0;i<sizeof after->trails;++i)
        CHECK(after->trails[i]==((i%0x60==3 || i%0x60==4)?0:before->trails[i]));
    for(unsigned i=0;i<sizeof after->effects;++i)
        CHECK(after->effects[i]==((i%0x50==3 || i%0x50==4)?0:before->effects[i]));
}
static void scene_passengers_keep_native_fixed_effects(void) {
    for(unsigned passenger=0;passenger<2;++passenger) {
        CPUState cpu;setup(&cpu);
        /* Model the already-earned original native constructor in each seat,
         * with distinct resource identities and active pre-scene combat. */
        PlayerContext primary=p2;
        primary.body[2]=0;primary.body[0xE7]=1;
        primary.body[0x70]=p2.body[0x70]=8;
        put32(primary.body+8,144u<<16);put32(primary.body+0x18,144u<<16);
        put32(primary.body+0x38,0x80040000u);put32(primary.body+0x3C,0x80041000u);
        primary.body[0x40]=primary.body[0x41]=0;primary.effects[0xA0]=0x21;
        for(unsigned i=0;i<3;++i) {
            uint8_t *t=primary.trails+i*0x60;
            put32(t+0x38,0x80040000u);put32(t+0x3C,0x80041000u);
        }
        project_player(&primary);
        PlayerContext active=passenger?p2:primary;
        memset(active.shots,0x6D,sizeof active.shots);active.body[0x8C]=1;
        for(unsigned i=0;i<3;++i) {
            uint8_t *t=active.trails+i*0x60;t[3]=t[4]=1;t[5]=2;
            put32(t+8,le32(active.body+8));put32(t+12,le32(active.body+12));
            put32(t+0x18,le32(active.body+8));put32(t+0x1C,le32(active.body+12));
            t[0x54]=3;t[0x56]=8;t[0x58]=(uint8_t)((5-i)*2);
            uint8_t *e=active.effects+i*0x50;
            if(e[0])e[3]=e[4]=1;
        }
        if(passenger)p2=active;else project_player(&active);
        PlayerContext leader;
        if(passenger)capture_player(&leader);else leader=p2;
        psx_mod_write_half(0x80097206u,980);psx_mod_write_byte(PLAY+0x1C,1);
        scene_transport_probe=passenger+1;
        scene_begin(passenger^1,0x80050250u);
        CHECK(scene_owner==(passenger^1)+1 && scene_phase==1);
        scene_tick(&cpu);CHECK(scene_phase==2);
        PlayerContext retired;
        if(passenger)retired=p2;else capture_player(&retired);
        check_retired_fixed_pools(&active,&retired);
        CHECK(!retired.body[0x8C] && retired.body[0x5C]==32);
        scene_tick(&cpu);CHECK(scene_phase==3);
        unsigned calls_before=call_count;scene_tick(&cpu);
        CHECK(scene_phase==3 && call_count==calls_before); /* Native lock still owns the destination. */
        psx_mod_write_byte(PLAY+0x1C,0);
        scene_tick(&cpu);CHECK(scene_phase==4);
        for(unsigned n=0;n<12 && scene_owner;++n)scene_tick(&cpu);
        CHECK(!scene_owner && !scene_phase && !state_track.count && !state_track.error && !failed);
        if(passenger)retired=p2;else capture_player(&retired);
        check_retired_fixed_pools(&active,&retired);
        CHECK(retired.body[4]==1 && retired.body[5]==2 && !retired.body[0x8C] && retired.body[0x5C]==32);
        PlayerContext unchanged;
        if(passenger)capture_player(&unchanged);else unchanged=p2;
        CHECK(!memcmp(&leader,&unchanged,sizeof leader));
        CHECK(life.status[0]==MMX6_COOP_ALIVE && life.status[1]==MMX6_COOP_ALIVE);
        /* A fresh native marker must use the retained constructor, including
         * slot-specific parents/tails. No observer or fixture repairs it. */
        scene_transport_probe=0;
        if(passenger)enter_zero();
        psx_mod_write_byte(PLAYER+0x8C,1);native_trails();
        for(unsigned i=0;i<3;++i) {
            uint32_t t=TRAILS+i*0x60;
            CHECK(psx_mod_read_byte(t)==0x11 && psx_mod_read_byte(t+2)==i);
            CHECK(psx_mod_read_byte(t+3)==1 && psx_mod_read_byte(t+4)==1 && !psx_mod_read_byte(t+5));
            CHECK(psx_mod_read_word(t+0x50)==(i?TRAILS+(i-1)*0x60:PLAYER));
            CHECK(psx_mod_read_half(t+0x42)==0x780D+i && psx_mod_read_byte(t+0x16)==4);
            CHECK(psx_mod_read_half(t+0x58)==(5-i)*2);
            CHECK(psx_mod_read_word(t+8)==psx_mod_read_word(PLAYER+8) && psx_mod_read_word(t+12)==psx_mod_read_word(PLAYER+12));
            CHECK(psx_mod_read_word(t+0x38)==psx_mod_read_word(PLAYER+0x38));
        }
        if(!passenger) {
            psx_mod_write_byte(PLAYER+0x9C,2);native_attached();
            CHECK(psx_mod_read_byte(EFFECTS+3)==1 && psx_mod_read_byte(EFFECTS+4)==1);
            psx_mod_write_byte(PLAYER+5,0x23);psx_mod_write_byte(PLAYER+6,1);native_attached();
            CHECK(psx_mod_read_byte(EFFECTS+0xA0)==0x21 && psx_mod_read_byte(EFFECTS+0xA3)==1);
        }
        if(passenger)leave_zero();
    }
    /* Voluntary Zero departure uses the same host cancellation helper. */
    CPUState cpu;setup(&cpu);PlayerContext active=p2;
    memset(active.shots,0x27,sizeof active.shots);
    for(unsigned i=0;i<3;++i){active.trails[i*0x60+3]=active.trails[i*0x60+4]=1;
        if(active.effects[i*0x50])active.effects[i*0x50+3]=active.effects[i*0x50+4]=1;}
    p2=active;clear_p2_combat();check_retired_fixed_pools(&active,&p2);
}
static void native_nova_body(unsigned phase) {
    psx_mod_write_byte(PLAYER+5,0x22);psx_mod_write_byte(PLAYER+6,(uint8_t)phase);
    psx_mod_write_byte(PLAYER+0xE7,4);psx_mod_write_byte(PLAYER+0xE0,1);
    psx_mod_write_byte(PLAYER+0x7A,1);psx_mod_write_byte(PLAYER+0xCC,0);
    psx_mod_write_byte(PLAYER+0xD0,0);psx_mod_write_byte(PLAYER+0xD3,0);
    psx_mod_write_byte(PLAYER+0xD4,0);psx_mod_write_byte(PLAYER+0xD5,0);
    psx_mod_write_byte(PLAY+0x1C,1);
}
enum { NOVA_BLOCKED_CASES=29 };
static void block_native_nova(unsigned gate) {
    switch(gate) {
    case 0:psx_mod_write_byte(PLAYER+5,0x21);break; /* Ultimate hover is not Nova. */
    case 1:psx_mod_write_byte(PLAYER+0xE7,1);break;
    case 2:psx_mod_write_byte(PLAYER+2,1);break;
    case 3:psx_mod_write_byte(PLAYER+6,3);break;
    case 4:psx_mod_write_byte(PLAYER+0xE0,0);break; /* Native recovery boundary. */
    case 5:psx_mod_write_byte(PLAY+0x1C,2);break;
    case 6:psx_mod_write_byte(PLAYER+0xD0,1);break;
    case 7:psx_mod_write_byte(PLAYER+0xD4,1);break;
    case 8:psx_mod_write_byte(PLAYER+0xD5,255);break;
    case 9:psx_mod_write_byte(PLAY+0x10,1);break;
    case 10:scene_owner=1;break;
    case 11:pause_owner=1;break;
    case 12:life.status[0]=MMX6_COOP_DYING;break;
    case 13:life.status[1]=MMX6_COOP_DYING;break;
    case 14:psx_mod_write_byte(PLAY+0x0F,1);break;
    case 15:psx_mod_write_byte(0x8008EAFCu,1);break;
    case 16:p2.body[0xD0]=1;break;
    case 17:p2.body[0xD5]=255;break;
    case 18:psx_mod_write_byte(PLAYER+0xCC,1);break;
    case 19:psx_mod_write_byte(PLAYER+0xD3,1);break;
    case 20:p2.body[0xD3]=1;break;
    case 21:p2.body[0x5C]=0x80;break;
    case 22:failed=1;break;
    case 23:enrolled=0;break;
    case 24:psx_mod_write_byte(PLAY,9);break;
    case 25:psx_mod_write_byte(PLAY+1,2);break;
    case 26:psx_mod_write_byte(PLAYER+0x5C,0x80);break;
    case 27:p2.body[0xCC]=1;break;
    case 28:life.status[1]=MMX6_COOP_JOINING;break;
    default:CHECK(0);
    }
}
static void native_nova_guest_update(void) {
    for(unsigned phase=0;phase<3;++phase) {
        CPUState cpu;setup(&cpu);native_nova_body(phase);
        PlayerContext primary;capture_player(&primary);
        uint8_t play[0xE0],after_play[0xE0];capture(PLAY,play,sizeof play);
        uint32_t zero_x=le32(p2.body+8);
        nova_probe=1;controller(&cpu,0);nova_probe=0;
        CHECK(occurrences(0x8003CD44)==1 && occurrences(0x80034DCC)==1 &&
              occurrences(0x8002012C)==1 && occurrences(0x8002F288)==1 &&
              occurrences(0x80020D74)==1 && occurrences(0x80020DC8)==1);
        CHECK(le32(p2.body+8)==zero_x+3*65536 && p2.body[0x5C]==32);
        PlayerContext after;capture_player(&after);CHECK(!memcmp(&primary,&after,sizeof primary));
        capture(PLAY,after_play,sizeof after_play);CHECK(!memcmp(play,after_play,sizeof play));
        CHECK(!inside && !zero_projected && !state_track.count && !state_track.error);
    }
    for(unsigned gate=0;gate<NOVA_BLOCKED_CASES;++gate) {
        CPUState cpu;setup(&cpu);native_nova_body(0);block_native_nova(gate);
        uint32_t zero_x=le32(p2.body+8);controller(&cpu,0);
        CHECK(!call_count && le32(p2.body+8)==zero_x && !inside && !state_track.count);
    }
    /* Retaining pit checks matters now that the guest can move during Nova. */
    CPUState cpu;setup(&cpu);native_nova_body(1);private_draw=0;
    psx_mod_write_word(PLAYER+12,800u<<16);
    psx_mod_write_half(0x800971F8u+0x20,700);cpu.gpr[4]=0x800971F8u;
    camera_pits(&cpu,0);CHECK(p2.body[0x5C]==0x80 && psx_mod_read_byte(PLAYER+0x5C)==32);
    CHECK(psx_mod_read_byte(PLAY+0x1C)==1);
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
static void deferred_dash_effect_uses_allocating_body(void) {
    CPUState cpu;setup(&cpu);stage_call=0;shared_probe=1;
    const uint32_t actor=0x80091298u,table=0x800FA640u;
    psx_mod_write_word(PLAYER+8,32u<<16);psx_mod_write_word(PLAYER+12,1115u<<16);
    put32(p2.body+8,168u<<16);put32(p2.body+12,1114u<<16);
    PlayerContext primary,after;capture_player(&primary);
    inside=1;enter_zero();CHECK(shared_effect_allocate(&cpu,0x8002C398u));
    CHECK(cpu.gpr[2]==actor && shared_effect_owners[0]==2);
    leave_zero_context(1);inside=0;
    psx_mod_write_byte(actor,0x21);psx_mod_write_byte(actor+1,1);
    psx_mod_write_word(SCRATCH+0x88,table);psx_mod_write_word(table+4,0x80049100u);
    cpu.gpr[31]=0x80020438u;cpu.gpr[4]=actor;shared_probe_seat=1;
    CHECK(shared_effect_callback(&cpu,0x80049100u));
    CHECK(psx_mod_read_word(actor+8)==168u<<16 && psx_mod_read_word(actor+12)==1114u<<16);
    capture_player(&after);CHECK(!memcmp(&primary,&after,sizeof primary));
    CHECK(shared_probe_calls==1 && cpu.gpr[2]==0x1234 && !inside && !zero_projected && !state_track.count);
    put32(p2.body+8,208u<<16);CHECK(shared_effect_callback(&cpu,0x80049100u));
    CHECK(psx_mod_read_word(actor+8)==208u<<16 && psx_mod_read_word(PLAYER+8)==32u<<16);
    cpu.gpr[31]=0x80020434u;CHECK(!shared_effect_callback(&cpu,0x80049100u));
    cpu.gpr[31]=0x80020438u;psx_mod_write_word(table+4,0x80010000u);
    CHECK(!shared_effect_callback(&cpu,0x80049100u));psx_mod_write_word(table+4,0x80049100u);
    shared_probe_delete=1;CHECK(shared_effect_callback(&cpu,0x80049100u));CHECK(!shared_effect_owners[0]);
    CHECK(shared_effect_allocate(&cpu,0x8002C398u));CHECK(shared_effect_owners[0]==1);
    psx_mod_write_byte(actor,0x21);psx_mod_write_byte(actor+1,1);
    shared_probe_delete=shared_probe_seat=0;CHECK(shared_effect_callback(&cpu,0x80049100u));
    CHECK(psx_mod_read_word(actor+8)==32u<<16 && psx_mod_read_word(actor+12)==1115u<<16);
    CHECK(shared_probe_calls==4 && !shared_fx_call && !shared_fx_allocate_call && !state_track.count && !state_track.error);
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
    /* Reject coordinates outside the native (0,480,256,32) upload. */
    CHECK(!zero_atlas_effect_bank(0x2C,0x77FF,0,0) && !zero_atlas_effect_bank(0x2C,0x8000,0,0));
}
static void deferred_dash_effect_retains_zero_atlas(void) {
    CPUState cpu;setup(&cpu);const uint32_t actor=0x80091298u;
    PlayerContext primary,after;capture_player(&primary);
    psx_mod_write_word(assembly+4,0xCC);
    psx_mod_write_byte(actor,0x21);psx_mod_write_byte(actor+1,1);psx_mod_write_byte(actor+3,1);
    psx_mod_write_word(actor+0x3C,assembly+0xCC);psx_mod_write_half(actor+0x42,0x7802);
    shared_effect_owners[0]=2;cpu.gpr[4]=actor;dash_packet_probe=1;
    memset(test_vram,0xBB,sizeof test_vram);
    for(unsigned y=176;y<192;++y)for(unsigned x=320;x<324;++x)
        test_zero_ui[y*1024+x]=0x1111;
    psx_mod_write_half(active_palette+3*32+2,0x4321);
    CHECK(render_survivor(&cpu,0x800232D4u));
    CHECK(!failed && draw_count==1 && drawn[0]==actor && bank_count==1 && bank_first[0]==0x4321);
    CHECK(banks[0].tile==0xB000 && world_packets==packets+40);
    uint16_t pixels[256];CHECK(mmx6_pixels_decode(banks[0].pixels,banks[0].pixel_bytes,256,pixels));
    for(unsigned i=0;i<256;++i)CHECK(pixels[i]==0x4321);
    capture_player(&after);CHECK(!memcmp(&primary,&after,sizeof primary));
    CHECK(psx_mod_read_word(SCRATCH+0x100)==0x800A0000 && !world_render && !state_track.count);
    shared_effect_owners[0]=1;CHECK(!render_survivor(&cpu,0x800232D4u));
    shared_effect_owners[0]=2;psx_mod_write_word(actor+0x3C,assembly);
    CHECK(!render_survivor(&cpu,0x800232D4u));
    psx_mod_write_word(actor+0x3C,assembly+0xCC);psx_mod_write_byte(actor+1,3);
    CHECK(!render_survivor(&cpu,0x800232D4u));
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
static void deferred_death_effect_retains_zero_source(void){
    CPUState cpu;setup(&cpu);const uint32_t actor=0x800CD410u;
    PlayerContext resident;capture_player(&resident);
    psx_mod_write_word(assembly+4,0x200);
    project_player(&p2);psx_mod_write_word(SCRATCH+0x1C,assembly);
    death_origin_probe=1;cpu.gpr[31]=0x8003DB0Cu;
    CHECK(death_effect_allocate(&cpu,0x8002C530u) && cpu.gpr[2]==actor);
    CHECK(death_effect[0].valid && death_effect[0].owner==2);
    project_player(&resident);psx_mod_write_word(SCRATCH+0x1C,0x80030000u);
    cpu.gpr[4]=actor;CHECK(death_effect_init(&cpu,0x80047E34u));
    CHECK(cpu.gpr[2]==0x8899 && !death_effect[0].valid && death_effect[0].owner==2);
    CHECK(psx_mod_read_word(PLAYER+8)==144u*65536u && psx_mod_read_word(SCRATCH+0x1C)==0x80030000u);
    CHECK(zero_death_effect(actor) && !zero_death_effect(actor+1) && !zero_death_effect(0x800CF810u));
    life.status[1]=MMX6_COOP_FALLEN; /* Burst outlives Zero's body callback. */
    memset(test_vram,0xBB,sizeof test_vram);
    for(unsigned y=240;y<256;++y)for(unsigned x=504;x<508;++x)test_zero_ui[y*1024+x]=0x1111;
    psx_mod_write_half(active_palette+2*32+2,0x4321);
    death_packet_probe=1;
    CHECK(render_survivor(&cpu,0x800232D4u));
    CHECK(!failed && draw_count==1 && bank_count==1 && bank_first[0]==0x4321);
    CHECK(banks[0].tile==0xF0E0u && world_packets==packets+40 && !world_render && !state_track.count);
    uint32_t expanded=packets+PLAYER_PACKET_BYTES;
    CHECK(psx_mod_read_word(expanded+4)==0x35000000u); /* Original raw texture command retained. */
    CHECK(psx_mod_read_word(SCRATCH+0x100)==0x800A0000u);
    uint16_t before=banks[0].id;
    psx_mod_write_half(active_palette+2*32+2,0x5678);
    CHECK(render_survivor(&cpu,0x800232D4u) && bank_count==2 && banks[1].id!=before && bank_first[1]==0x5678);
    CHECK(bank_first[0]==0x4321); /* Prior packets keep immutable colors. */
    death_effect[0].owner=1;CHECK(!zero_death_effect(actor) && !render_survivor(&cpu,0x800232D4u));
    death_effect[0].owner=2;psx_mod_write_byte(actor+1,0x12);CHECK(!zero_death_effect(actor));
    psx_mod_write_byte(actor+1,0x11);psx_mod_write_word(actor+0x3C,assembly);CHECK(!zero_death_effect(actor));
    psx_mod_write_word(actor+0x3C,assembly+0x200);CHECK(zero_death_effect(actor));
    cpu.gpr[31]=0x80020000u;
    CHECK(death_effect_allocate(&cpu,0x8002C530u) && !death_effect[0].owner && !death_effect[0].valid);
    CHECK(!zero_death_effect(actor)); /* Unrelated reuse never inherits Zero. */
    cpu.gpr[31]=0x8003DB8Cu;
    CHECK(death_effect_allocate(&cpu,0x8002C530u) && death_effect[0].owner==1);
    death_origin_probe=death_packet_probe=0;
}
static void native_shared_dialogue_palette(void) {
    for(unsigned alternate=0;alternate<2;++alternate) {
        CPUState cpu;setup(&cpu);
        unsigned first=alternate?0x5E:0x15;
        uint32_t resident=psx_mod_read_word(SCRATCH+0x28),offset=first*32;
        uint8_t baseline[64],private_before[64],original[64],speaker[32],actual[64];
        for(unsigned i=0;i<64;++i) {
            baseline[i]=(uint8_t)(i+1);private_before[i]=(uint8_t)(i+81);
            original[i]=(uint8_t)(i+151);
        }
        for(unsigned i=0;i<32;++i)speaker[i]=(uint8_t)(255-i);
        project(resident+offset,baseline,64);project(active_palette+offset,private_before,64);
        project(0x8006E408u,original,64);project(0x8006E484u,speaker,32);
        psx_mod_write_half(0x80090D6Au,(uint16_t)alternate);
        psx_mod_write_byte(resident+offset-1,0xA7);psx_mod_write_byte(resident+offset+64,0xB8);
        enter_zero();
        /* Original constructor backs up the projected private bank first. */
        project(0x800E33D8u,private_before,64);
        cpu.gpr[4]=first;cpu.gpr[5]=0x8006E408u;cpu.gpr[6]=2;
        cpu.gpr[31]=alternate?0x800219B0u:0x8002199Cu;
        CPUState before=cpu;
        dialogue_palette_load(&cpu,0x8002B3D4u);
        CHECK(!memcmp(&before,&cpu,sizeof cpu));
        capture(0x800E33D8u,actual,64);CHECK(!memcmp(actual,baseline,64));
        capture(resident+offset,actual,64);CHECK(!memcmp(actual,original,64));
        capture(active_palette+offset,actual,64);CHECK(!memcmp(actual,private_before,64));
        /* Model only the external native loader's documented memcpy/dirty
         * contract. The hook leaves it to execute, with registers intact. */
        project(active_palette+offset,original,64);psx_mod_write_byte(0x800C4560u,1);
        cpu.gpr[4]=first+1;cpu.gpr[5]=0x8006E484u;cpu.gpr[6]=1;
        for(unsigned later=0;later<2;++later) {
            cpu.gpr[31]=later?0x800225D8u:(alternate?0x8002289Cu:0x80022884u);
            dialogue_palette_load(&cpu,0x8002B3D4u);
            capture(resident+offset,actual,64);
            CHECK(!memcmp(actual,original,32) && !memcmp(actual+32,speaker,32));
        }
        project(resident+offset,original,64);cpu.gpr[31]=0x80020000u;
        dialogue_palette_load(&cpu,0x8002B3D4u);
        capture(resident+offset,actual,64);CHECK(!memcmp(actual,original,64));
        cpu.gpr[31]=0x800225D8u;cpu.gpr[6]=2;
        dialogue_palette_load(&cpu,0x8002B3D4u);
        capture(resident+offset,actual,64);CHECK(!memcmp(actual,original,64));
        cpu.gpr[4]=first;cpu.gpr[5]=0x800E33D8u;cpu.gpr[6]=2;
        cpu.gpr[31]=alternate?0x800221D4u:0x800221BCu;
        dialogue_palette_load(&cpu,0x8002B3D4u);
        capture(resident+offset,actual,64);CHECK(!memcmp(actual,baseline,64));
        CHECK(psx_mod_read_byte(resident+offset-1)==0xA7 && psx_mod_read_byte(resident+offset+64)==0xB8);
        project(active_palette+offset,baseline,64);leave_zero();
        CHECK(psx_mod_read_byte(0x800C4560u)==0x73 && !zero_projected);
        cpu.gpr[5]=0x8006E408u;cpu.gpr[31]=alternate?0x800219B0u:0x8002199Cu;
        dialogue_palette_load(&cpu,0x8002B3D4u);
        capture(resident+offset,actual,64);CHECK(!memcmp(actual,baseline,64));
    }
}
static void native_working_palette_class_and_load_events(void) {
    CPUState cpu;setup(&cpu);
    const unsigned member_bytes=2048+0x4000,dat_bytes=2048+2*member_bytes;
    uint8_t *dat=calloc(dat_bytes,1);CHECK(dat);
    for(unsigned record=1;record<=2;++record) {
        unsigned first=2048+(record-1)*member_bytes;
        put32(dat+record*8,first/2048);put32(dat+record*8+4,member_bytes);
        put32(dat+first,1);put32(dat+first+4,member_bytes);
        put32(dat+first+8,5);put32(dat+first+12,record==1?0x3C00:0x4000);
        for(unsigned row=0;row<512;++row)for(unsigned c=1;c<16;++c) {
            unsigned value=record==2?0x2222:0x3333;
            if(row==2 && c==5)value=record==2?0xFFFF:0x4321;
            if(row==2 && c==13)value=0xE566;
            if(row>=13 && row<=15)value=row==13?0x8032:row==14?0x800E:0x8009;
            unsigned at=first+2048+row*32+c*2;
            dat[at]=(uint8_t)value;dat[at+1]=(uint8_t)(value>>8);
        }
    }
    /* Synthetic archive/table metadata; no original asset bytes bundled. */
    for(unsigned i=0;i<184;++i)psx_mod_write_byte(0x8006DA88u+i,0);
    psx_mod_write_half(0x8006DA88u,1);psx_mod_write_half(0x8006DAE4u,2);
    psx_mod_write_half(0x8006DA8Cu,1);psx_mod_write_half(0x8006DAE8u,1);
    CHECK(working_palette_prepare(dat,dat_bytes,2));
    for(unsigned row=0;row<83;++row)for(unsigned c=0;c<16;++c)
        psx_mod_write_half(palette_source+row*32+c*2,c?0x805E:0);
    uint8_t source_before[2656];capture(palette_source,source_before,sizeof source_before);
    /* The old wholesale type9 -> working policy gives this red beam and
     * colored/black trails; actual native type5 must replace those rows. */
    project(active_palette,source_before,sizeof source_before);
    CHECK(psx_mod_read_half(active_palette+2*32+10)==0x805E);
    working_palette_probe=1;cpu.gpr[31]=0x800140F0u;
    cpu.gpr[4]=1;cpu.gpr[5]=1;cpu.gpr[6]=0;
    CPUState saved_cpu=cpu;PlayerContext resident;capture_player(&resident);
    CHECK(!working_palette_native_load(&cpu,0x80014F70u) && !failed);
    CHECK(working_palette_probe_calls==1 && !memcmp(&cpu,&saved_cpu,sizeof cpu));
    PlayerContext after;capture_player(&after);CHECK(!memcmp(&resident,&after,sizeof after));
    CHECK(!inside && !zero_projected && !state_track.count && !state_track.error);
    CHECK(psx_mod_read_word(SCRATCH+0x28)==0x80030300u &&
          psx_mod_read_byte(0x800C4560)==0x72);
    uint8_t source_after[2656];capture(palette_source,source_after,sizeof source_after);
    CHECK(!memcmp(source_before,source_after,sizeof source_before));
    CHECK(psx_mod_read_half(active_palette+2)==0x805E); /* Native current body. */
    CHECK(psx_mod_read_half(active_palette+2*32+10)==0xFFFF &&
          psx_mod_read_half(active_palette+2*32+26)==0xE566);
    for(unsigned row=13;row<=15;++row)for(unsigned c=1;c<16;++c)
        CHECK(psx_mod_read_half(active_palette+row*32+c*2)==
              (row==13?0x8032:row==14?0x800E:0x8009));
    for(unsigned y=0;y<256;++y)for(unsigned x=768;x<1024;++x)
        test_zero_ui[y*1024+x]=0x5555;
    uint16_t beam=zero_atlas_effect_bank(0x2Cu,0x7802u,0xD0C0u,0);
    CHECK(beam==0x6000 && bank_first[0]==0xFFFF);
    for(unsigned row=13;row<=15;++row) {
        uint16_t bank=sprite_bank(assets,0,(uint16_t)(0x7800+row),0);
        CHECK(bank && bank_first[bank-0x6000]==(row==13?0x8032:row==14?0x800E:0x8009));
    }
    /* Palette mutations create new retained colors, never repaint old IDs. */
    psx_mod_write_half(active_palette+2*32+10,0x1234);
    uint16_t changed=zero_atlas_effect_bank(0x2Cu,0x7802u,0xD0C0u,0);
    CHECK(changed!=beam && bank_first[changed-0x6000]==0x1234 && bank_first[0]==0xFFFF);
    psx_mod_write_byte(PLAY+0x0C,1);cpu.gpr[31]=0x800140F0u;
    CHECK(!working_palette_native_load(&cpu,0x80014F70u) && !failed);
    CHECK(working_palette_probe_calls==2 && psx_mod_read_half(active_palette+2*32+10)==0x4321);
    CHECK(psx_mod_read_half(active_palette+0x3C02)==0x2222); /* Partial payload tail preserved. */
    /* Native stage13 can change a selector without changing stage/section. */
    psx_mod_write_half(0x8006DAE8u,2);
    CHECK(!working_palette_native_load(&cpu,0x80014F70u) && !failed);
    CHECK(working_palette_probe_calls==3 && psx_mod_read_half(active_palette+2*32+10)==0xFFFF);
    /* Unrelated loader calls, unrelated projections and record0 never reseed. */
    uint8_t preserved[0x4000];capture(active_palette,preserved,sizeof preserved);
    cpu.gpr[31]=0x800140F4u;CHECK(!working_palette_native_load(&cpu,0x80014F70u));
    CHECK(working_palette_probe_calls==3);
    cpu.gpr[31]=0x800140F0u;inside=1;CHECK(!working_palette_native_load(&cpu,0x80014F70u));inside=0;
    inside=1;enter_zero();cpu.gpr[31]=0x80014124u;cpu.gpr[4]=2;
    psx_mod_write_word(SCRATCH+0x24,0x80050000u);
    psx_mod_write_word(SCRATCH+0x28,0x80054000u);
    psx_mod_write_byte(0x800C4560u,0x3A);
    for(unsigned i=0;i<32;++i)psx_mod_write_byte(0x80054000u+i,0xA5);
    CHECK(!working_palette_native_load(&cpu,0x80014F70u) && !failed);
    CHECK(working_palette_probe_calls==4 && inside && zero_projected);
    CHECK(psx_mod_read_word(SCRATCH+0x24)==0x80050000u &&
          psx_mod_read_word(SCRATCH+0x28)==0x80054000u &&
          psx_mod_read_byte(0x800C4560u)==0x3A);
    for(unsigned i=0;i<32;++i)CHECK(psx_mod_read_byte(0x80054000u+i)==0xA5);
    leave_zero();inside=0;cpu.gpr[31]=0x800140F0u;
    psx_mod_write_byte(PLAY+0x0D,1);cpu.gpr[4]=0;
    CHECK(!working_palette_native_load(&cpu,0x80014F70u) && !failed && working_palette_probe_calls==4);
    uint8_t now[0x4000];capture(active_palette,now,sizeof now);CHECK(!memcmp(now,preserved,sizeof now));
    CHECK(!working_palette_seed(1)); /* No fabricated initial base for record0. */
    psx_mod_write_byte(PLAY+0x0D,2);CHECK(!working_palette_seed(0));
    psx_mod_write_byte(PLAY+0x0D,0);psx_mod_write_byte(PLAY+0x0C,23);CHECK(!working_palette_seed(0));
    psx_mod_write_byte(PLAY+0x0C,255);CHECK(!working_palette_seed(0));
    /* Typed bounds/selector failure must not write current working memory. */
    unsigned second=2048+member_bytes;
    put32(dat+second+8,9);CHECK(!working_palette_prepare(dat,dat_bytes,2) && !working_palette_assets_ready);
    put32(dat+second+8,5);put32(dat+second+12,0x3FE0);
    CHECK(!working_palette_prepare(dat,dat_bytes,2));put32(dat+second+12,0x4000);
    CHECK(!working_palette_prepare(dat,dat_bytes-1,2));
    CHECK(working_palette_prepare(dat,dat_bytes,2));
    psx_mod_write_byte(PLAY+0x0C,0);psx_mod_write_half(0x8006DAE4u,256);
    CHECK(!working_palette_seed(0));
    capture(active_palette,now,sizeof now);CHECK(!memcmp(now,preserved,sizeof now));
    free(dat);clear_banks();working_palette_assets_ready=working_palette_probe=0;
}

/* Source-bound native upload contract with authored LZ/palette bytes, not ROM.
 * First16 tiles are index1; next16 are index2. Original80017B04 places both
 * rows atv64..95. This fails on the pre-fix plugin's origin0 placement. */
static void native_working_palette_rectangle(void) {
    CPUState cpu;setup(&cpu);size_t offset;
    CHECK(working_palette_clut_offset(0x7800,&offset) && offset==0);
    CHECK(working_palette_clut_offset(0x780F,&offset) && offset==0x1E0);
    CHECK(working_palette_clut_offset(0x7840,&offset) && offset==0x200);
    CHECK(working_palette_clut_offset(0x7849,&offset) && offset==0x320);
    CHECK(working_palette_clut_offset(0x7FCF,&offset) && offset==0x3FE0);
    CHECK(!working_palette_clut_offset(0x77CF,&offset));
    CHECK(!working_palette_clut_offset(0x7810,&offset));
    CHECK(!working_palette_clut_offset(0x783F,&offset));
    CHECK(!working_palette_clut_offset(0x8000,&offset));
    for(unsigned y=0;y<16;++y)for(unsigned x=0;x<4;++x)test_zero_ui[y*1024+x]=0x1111;
    psx_mod_write_half(active_palette+0x322,0x1357);
    psx_mod_write_half(active_palette+0x922,0x2468);
    uint16_t bank=zero_atlas_effect_bank(0,0x7849,0,0);
    CHECK(bank && bank_first[bank-0x6000]==0x1357);
    psx_mod_write_half(active_palette+0x322,0x579B);
    uint16_t changed=zero_atlas_effect_bank(0,0x7849,0,0);
    CHECK(changed && changed!=bank && bank_first[changed-0x6000]==0x579B);
    CHECK(bank_first[bank-0x6000]==0x1357);
    CHECK(!zero_atlas_effect_bank(0,0x7810,0,0));
    clear_banks();
}
static void yammar_native_upload_coordinates(void) {
    CPUState cpu;setup(&cpu);
    static uint8_t graphics[0x200];memset(graphics,0,sizeof graphics);
    zero_compressed=graphics;compressed_size=sizeof graphics;
    put32(graphics+0x10,0x100);
    for(unsigned i=0;i<23;++i)put32(graphics+0x100+i*4,0x0200005Cu);
    /* Alias points at the same compressed stream with ordinary origin0. */
    put32(graphics+0x40,0x0200011Cu);
    put32(graphics+0x80,0x001000F0u);
    const uint16_t two_rows[]={0x5800,0x1111,0x0001,1023,0x2222,0x0001,1023,0,0};
    const uint16_t one_tile[]={0x6000,0x1111,0x0001,63,0,0};
    for(unsigned i=0;i<sizeof two_rows/sizeof *two_rows;++i){
        graphics[0x15C+i*2]=(uint8_t)two_rows[i];graphics[0x15D+i*2]=(uint8_t)(two_rows[i]>>8);
    }
    for(unsigned i=0;i<sizeof one_tile/sizeof *one_tile;++i){
        graphics[0x170+i*2]=(uint8_t)one_tile[i];graphics[0x171+i*2]=(uint8_t)(one_tile[i]>>8);
    }
    /* Native CLUT7849=(144,481), within original256-word upload rows.
     * Poison the old full-VRAM-stride lookup so this tests the native
     * layout rather than reproducing the retained renderer arithmetic. */
    for(unsigned c=0;c<16;++c)psx_mod_write_half(active_palette+0x920+c*2,0x7654);
    for(unsigned c=0;c<16;++c)psx_mod_write_half(active_palette+0x320+c*2,0);
    psx_mod_write_half(active_palette+0x320+2,0x1234);
    psx_mod_write_half(active_palette+0x320+4,0x4321);
    const uint32_t table=assets+0x100,alias=assets+0x40;
    uint16_t tile=sprite_bank(table,0,0x7849,0x4000);CHECK(tile);
    uint16_t pixels[256];CHECK(mmx6_pixels_decode(banks[tile-0x6000].pixels,banks[tile-0x6000].pixel_bytes,256,pixels));
    for(unsigned i=0;i<256;++i)CHECK(pixels[i]==0x1234);
    uint16_t lower=sprite_bank(table,1,0x7849,0x5000);CHECK(lower && lower!=tile);
    CHECK(mmx6_pixels_decode(banks[lower-0x6000].pixels,banks[lower-0x6000].pixel_bytes,256,pixels));
    for(unsigned i=0;i<256;++i)CHECK(pixels[i]==0x4321);
    static uint16_t page[65536];
    uint16_t full=sprite_bank(table,22,0x7849,UINT16_MAX);CHECK(full);
    CHECK(mmx6_pixels_decode(banks[full-0x6000].pixels,banks[full-0x6000].pixel_bytes,65536,page));
    for(unsigned y=0;y<256;++y)for(unsigned x=0;x<256;++x)
        CHECK(page[y*256+x]==(y>=64 && y<80?0x1234:y>=80 && y<96?0x4321:0));
    CHECK(banks[full-0x6000].source==assets+0x15C && banks[full-0x6000].tile==UINT16_MAX);
    unsigned count=bank_count;CHECK(sprite_bank(table,3,0x7849,UINT16_MAX)==full && bank_count==count);
    /* Both source aliases must retain their actual distinct placement. */
    uint16_t normal=sprite_bank(alias,0,0x7849,UINT16_MAX);CHECK(normal && normal!=full);
    CHECK(mmx6_pixels_decode(banks[normal-0x6000].pixels,banks[normal-0x6000].pixel_bytes,65536,page));
    CHECK(page[0]==0x1234 && page[16*256]==0x4321 && !page[64*256]);
    count=bank_count;CHECK(sprite_bank(table,2,0x7849,UINT16_MAX)==full &&
        sprite_bank(alias,0,0x7849,UINT16_MAX)==normal && bank_count==count);
    clear_banks();normal=sprite_bank(alias,0,0x7849,UINT16_MAX);full=sprite_bank(table,0,0x7849,UINT16_MAX);
    CHECK(normal && full && normal!=full);
    CHECK(mmx6_pixels_decode(banks[full-0x6000].pixels,banks[full-0x6000].pixel_bytes,65536,page));
    CHECK(!page[0] && page[64*256]==0x1234 && page[80*256]==0x4321);
    /* Palette changes append a new immutable bank; old pixels never repaint. */
    psx_mod_write_half(active_palette+0x320+2,0x5678);
    uint16_t changed=sprite_bank(table,0,0x7849,UINT16_MAX);CHECK(changed && changed!=full);
    CHECK(mmx6_pixels_decode(banks[full-0x6000].pixels,banks[full-0x6000].pixel_bytes,65536,page));
    CHECK(page[64*256]==0x1234);
    CHECK(mmx6_pixels_decode(banks[changed-0x6000].pixels,banks[changed-0x6000].pixel_bytes,65536,page));
    CHECK(page[64*256]==0x5678);
    count=bank_count;bank_count=4096;
    CHECK(sprite_bank(table,0,0x7849,UINT16_MAX)==changed && bank_count==4096);bank_count=count;
    /* Ordinary body/trail source remains origin0 and its native palette. */
    uint16_t body=sprite_bank(assets+0x80,0,0x7800,0);CHECK(body && bank_first[body-0x6000]==0x0101);
    uint16_t trail=sprite_bank(assets+0x80,0,0x780D,0);CHECK(trail && bank_first[trail-0x6000]==0x1111);
    CHECK(!sprite_bank(table,23,0x7849,0x4000));
    CHECK(!sprite_bank(table,0,0x77FF,0x4000));
    /* Invalid/incomplete resource identity uses safe default classification. */
    put32(graphics+0x10,UINT32_MAX);CHECK(sprite_bank(assets+0x80,0,0x7800,0)==body);
    put32(graphics+0x10,0x100);compressed_size=0x15D;
    CHECK(!sprite_bank(table,0,0x7849,0x4000));
    compressed_size=sizeof graphics;CHECK(sprite_bank(table,0,0x7849,0x4000));
    clear_banks();
}
static void ride_setup(CPUState *cpu) {
    setup(cpu);ride_probe=1;life.status[0]=life.status[1]=MMX6_COOP_ALIVE;
    static const unsigned fields[]={0xCC,0xCD,0xD0,0xD5,0x8E,0x7A,0xE0,0xA4,0x79};
    for(unsigned i=0;i<sizeof fields/sizeof fields[0];++i)psx_mod_write_byte(PLAYER+fields[i],0);
    psx_mod_write_word(PLAYER+0x68,0x80073D50);put32(p2.body+0x68,0x80073D54);
    psx_mod_write_byte(PLAY+12,4);psx_mod_write_byte(RIDE,0x41);psx_mod_write_byte(RIDE+4,1);
    psx_mod_write_byte(RIDE+0x70,8);psx_mod_write_word(RIDE+0x10,0x800F2B1C);
    psx_mod_write_word(RIDE+0x68,0x800F3A44);psx_mod_write_word(0x80071380,0x800F2414);
    psx_mod_write_word(0x800F2414,0x27BDFFE8);psx_mod_write_word(0x800EE924,0x27BDFFD8);
    psx_mod_write_word(0x800EEA74,0x24050012);cpu->gpr[31]=0x80020C60;
}
static void native_shared_ride_ownership(void) {
    CPUState cpu;ride_setup(&cpu);ride_overlap=2;PlayerContext x;capture_player(&x);
    uint8_t pad[6];capture(0x800C456C,pad,sizeof pad);
    CHECK(ride_tick(&cpu,0x80020A08) && ride_ticks==1 && ride_seat==1 && p2.body[0xD5]==1);
    PlayerContext after;capture_player(&after);CHECK(!memcmp(&x,&after,sizeof x));
    uint8_t restored[6];capture(0x800C456C,restored,sizeof restored);
    CHECK(!memcmp(pad,restored,sizeof pad) && !previous_input && !ride_call && !state_track.count);
    CHECK(psx_mod_read_byte(PLAY+0x26)==0x5A && psx_mod_read_word(RIDE+0x68)==0x800F3A44);
    p2.body[0xD5]=255;p2.body[5]=0x12; /* Native 3A268 consume boundary. */
    pad_buttons=(uint16_t)~0x4010u;previous_input=0x1040;
    CHECK(ride_tick(&cpu,0x80020A08) && ride_ticks==2 && p2.body[0xD5]==255);
    CHECK(!p2.body[0x80] && previous_input==0x1040); /* Held Jump is not a fresh edge. */
    previous_input=0;CHECK(ride_tick(&cpu,0x80020A08) && ride_ticks==3 && !p2.body[0xD5]);
    CHECK(ride_seat==1 && !psx_mod_read_byte(PLAYER+0xD5) && !ride_call && !state_track.count);
    ride_setup(&cpu);ride_overlap=3;CHECK(ride_tick(&cpu,0x80020A08) && ride_seat==0 && ride_ticks==1);
    CHECK(psx_mod_read_byte(PLAYER+0xD5)==1 && !p2.body[0xD5]);
    ride_setup(&cpu);ride_overlap=2;p2.body[0x8E]=1;
    CHECK(ride_tick(&cpu,0x80020A08) && ride_seat==0 && !p2.body[0xD5]);
    ride_setup(&cpu);ride_overlap=2;p2.body[0xD5]=254;
    CHECK(ride_owner()==RIDE_NONE && ride_tick(&cpu,0x80020A08) && ride_seat==0 && p2.body[0xD5]==254);
    ride_setup(&cpu);p2.body[0xD5]=255;p2.body[5]=0x12;psx_mod_write_byte(RIDE+0x97,0x40);
    psx_mod_write_word(RIDE+8,123);psx_mod_write_word(RIDE+12,456);ride_sync_rider();
    CHECK(le32(p2.body+8)==123 && le32(p2.body+12)==456 && !ride_ticks);
    ride_setup(&cpu);psx_mod_write_byte(PLAYER+0xD5,255);psx_mod_write_byte(RIDE+0x97,0x40);
    enter_zero();zero_world=inside=1;
    CHECK(ride_tick(&cpu,0x80020A08) && ride_ticks==1 && ride_seat==0);
    CHECK(zero_projected && zero_world && psx_mod_read_byte(PLAYER+2)==1 && !psx_mod_read_byte(PLAYER+0xD5));
    zero_world=0;leave_zero_context(1);inside=0;CHECK(!ride_call && !state_track.count);
    ride_setup(&cpu);p2.body[0xD5]=255;psx_mod_write_byte(PLAYER+0xD5,255);
    CHECK(!ride_tick(&cpu,0x80020A08) && failed && !ride_ticks && !ride_call);
    ride_setup(&cpu);psx_mod_write_byte(PLAY+12,1);CHECK(!ride_tick(&cpu,0x80020A08) && !call_count);
    ride_probe=0;
}
static void shared_clear_setup(CPUState *cpu) {
    setup(cpu);stage_call=0;
    PlayerContext primary=p2;primary.body[2]=0;primary.body[0xE7]=1;
    project_player(&primary);
    psx_mod_write_byte(PLAY+12,1);psx_mod_write_byte(PLAY+13,0);
    const uint32_t boss=0x800CE000u;
    psx_mod_write_word(PLAY+0x20,boss);
    psx_mod_write_byte(boss,1);psx_mod_write_byte(boss+1,49);
    psx_mod_write_byte(boss+2,0);psx_mod_write_byte(boss+4,2);
    psx_mod_write_byte(boss+0x5C,0);psx_mod_write_word(boss+0x10,0x800F66C0u);
    cpu->gpr[31]=0x800F5544u;cpu->gpr[4]=20;
}
static void native_shared_clear_admission_and_departure(void) {
    CPUState cpu;
    for(unsigned negative=0;negative<10;++negative) {
        shared_clear_setup(&cpu);uint32_t boss=psx_mod_read_word(PLAY+0x20);
        if(negative==0)cpu.gpr[31]-=4;
        if(negative==1)cpu.gpr[4]=19;
        if(negative==2)psx_mod_write_byte(PLAY+12,0);
        if(negative==3)psx_mod_write_byte(boss+1,48);
        if(negative==4)psx_mod_write_byte(boss+2,1);
        if(negative==5)psx_mod_write_byte(boss+4,1);
        if(negative==6)psx_mod_write_byte(boss+0x5C,1);
        if(negative==7)psx_mod_write_word(boss+0x10,0x800F66C8u);
        if(negative==8)life.status[1]=MMX6_COOP_ABSENT;
        if(negative==9){life.status[0]=MMX6_COOP_FALLEN;psx_mod_write_byte(PLAYER+0x5C,0);}
        CHECK(!shared_clear_admit(&cpu,0x8003D308u));
        CHECK(!clear_phase && !clear_members && !clear_started && !call_count);
    }
    /* Existing ordinary script/door scene still takes its native passenger
     * path; no script number alone is treated as earned stage completion. */
    shared_clear_setup(&cpu);cpu.gpr[31]=0x80050290u;
    script_begin(&cpu,0x8003D308u);CHECK(scene_owner==1 && scene_phase==1 && !clear_phase);
    for(unsigned projected=0;projected<2;++projected) {
        shared_clear_setup(&cpu);
        if(projected)enter_zero();
        script_begin(&cpu,0x8003D308u);
        CHECK(clear_phase==CLEAR_ADMITTED && clear_members==3 && !clear_started && !scene_owner);
        if(projected)leave_zero();
        shared_clear_tick(&cpu,0);CHECK(clear_phase==CLEAR_PRELUDE && !call_count);
        /* Both bodies stay visible until the original reward sets clear10. */
        CHECK(psx_mod_read_byte(PLAYER+3)==1 && p2.body[3]==1);
        clear_probe=1;clear_pose_limit[0]=projected?6:2;clear_pose_limit[1]=projected?2:6;
        if(!projected){p2.body[5]=6;clear_air_limit=6;}
        cpu.gpr[4]=PLAY;
        psx_mod_write_byte(PLAYER+5,20);psx_mod_write_byte(PLAYER+0x7A,1);
        uint32_t old_input[3];for(unsigned i=0;i<3;++i){old_input[i]=0xA100u+i;psx_mod_write_half(0x800C456C+i*2,(uint16_t)old_input[i]);}
        for(unsigned frame=0;frame<24 && psx_mod_read_byte(PLAY)==10;++frame) {
            CHECK(stage_tick(&cpu,0x8001E9ECu));
            CHECK(!inside && !stage_call && !zero_projected && !zero_world && !state_track.count && !state_track.error);
            CHECK(psx_mod_read_byte(PLAY+0x38)==0 && psx_mod_read_byte(PLAY+0x5E)==0);
            for(unsigned i=0;i<3;++i)CHECK(psx_mod_read_half(0x800C456C+i*2)==old_input[i]);
            if(clear_worlds==1) {
                CHECK(clear_phase==CLEAR_PRELUDE && !clear_started);
                CHECK(psx_mod_read_byte(PLAYER+3)==1 && p2.body[3]==1);
                CHECK(clear_body_ticks[0]==1 && clear_body_ticks[1]==1);
            }
        }
        CHECK(psx_mod_read_byte(PLAY)==12 && !enrolled && !clear_phase && !clear_members && !clear_started);
        CHECK(clear_constructors[0]==1 && clear_constructors[1]==1 && clear_fades==1);
        CHECK(clear_poses[0]==clear_pose_limit[0] && clear_poses[1]==clear_pose_limit[1]);
        CHECK(clear_outgoing[0]==2 && clear_outgoing[1]==2);
        CHECK(projected?!clear_zero_worlds:clear_zero_worlds>0);
        CHECK(psx_mod_read_word(PLAY+0x90)==clear_worlds); /* One actual world per stage callback. */
    }
    shared_clear_setup(&cpu);script_begin(&cpu,0x8003D308u);
    native_player_init(&cpu,0x8003BD24u);
    CHECK(!clear_phase && !clear_members && !clear_started && !enrolled);
    clear_probe=0;
}
enum { TEST_DOOR=0x800C12C4u,TEST_DOOR_BOX=0x80074000u,TEST_X_BOX=0x80074004u,TEST_ZERO_BOX=0x80074008u };
static void door_setup(CPUState *cpu,unsigned both,int x,int zero) {
    setup(cpu);both_doors=both;door_native_probe=1;
    life.status[0]=life.status[1]=MMX6_COOP_ALIVE;
    const unsigned fields[]={0xA4,0x7A,0xD0,0xD4,0xE0};
    for(unsigned i=0;i<sizeof fields/sizeof fields[0];++i)psx_mod_write_byte(PLAYER+fields[i],0);
    psx_mod_write_word(PLAYER+8,(uint32_t)x<<16);put32(p2.body+8,(uint32_t)zero<<16);
    psx_mod_write_word(PLAYER+0x68,TEST_X_BOX);put32(p2.body+0x68,TEST_ZERO_BOX);
    psx_mod_write_word(TEST_DOOR+8,500u<<16);psx_mod_write_word(TEST_DOOR+12,1000u<<16);
    psx_mod_write_word(TEST_DOOR+0x68,TEST_DOOR_BOX);
    psx_mod_write_byte(TEST_DOOR,0x49);psx_mod_write_byte(TEST_DOOR+1,8);
    psx_mod_write_word(TEST_DOOR+0x10,0x800FA2ACu);
    /* Different authored centers and heights exercise each actual box. */
    psx_mod_write_word(TEST_DOOR_BOX,0x281000FCu); /* x=-4,y=0,w=16,h=40 */
    psx_mod_write_word(TEST_X_BOX,0x10080000u);
    psx_mod_write_word(TEST_ZERO_BOX,0x14080002u); /* x=2,w=8,h=20 */
    cpu->gpr[4]=TEST_DOOR;cpu->gpr[6]=PLAYER;cpu->gpr[31]=0x80020C60;
}
static void check_door_result(CPUState *cpu,unsigned owner,unsigned phase) {
    uint32_t x=psx_mod_read_word(PLAYER+8),y=psx_mod_read_word(PLAYER+12);
    uint32_t zx=le32(p2.body+8),zy=le32(p2.body+12);
    uint8_t hp=p2.body[0x5C],xhp=psx_mod_read_byte(PLAYER+0x5C);
    CHECK(door_begin(cpu,0x80050250u) && cpu->gpr[2]==0xD007);
    CHECK(door_ticks==1 && door_draws==1 && occurrences(0x80050250u)==1);
    CHECK(scene_owner==owner && scene_phase==phase);
    CHECK(psx_mod_read_word(PLAYER+8)==x && psx_mod_read_word(PLAYER+12)==y &&
        le32(p2.body+8)==zx && le32(p2.body+12)==zy && p2.body[0x5C]==hp &&
        psx_mod_read_byte(PLAYER+0x5C)==xhp);
    CHECK(!inside && !zero_projected && !scene_call && !state_track.count && !state_track.error && !failed);
    CHECK(psx_mod_read_word(OVERLAY)==0x11223344 &&
        psx_mod_read_word(SCRATCH+0x1C)==0x80030100u);
}
static void native_either_both_door_admission(void) {
    CPUState cpu;
    /* Actual native menu preview: inside/Zero projection bypasses the outer
     * door callback. No tag35 frame exists, but native AI/drawing still runs.
     * The read-only preview must not set PLAYER+D4 or shared PLAY+1C. */
    for(unsigned both=0;both<2;++both) {
        door_setup(&cpu,both,400,480);pause_owner=1;inside=zero_world=1;
        enter_zero();CHECK(!door_begin(&cpu,0x80050250u));
        CHECK(guest(&cpu,0x80050250u,TEST_DOOR,0)==0xD007);
        CHECK(!psx_mod_read_byte(PLAYER+0xD4) && !psx_mod_read_byte(PLAY+0x1C));
        zero_world=0;leave_zero_context(1);inside=0;
        CHECK(!p2.body[0xD4] && !scene_owner && !scene_phase &&
            door_ticks==1 && door_draws==1 && !state_track.count);
        pause_owner=-1;door_ticks=door_draws=call_count=0;
        /* Closing the menu restores original active-world admission. */
        if(both)check_door_result(&cpu,0,0);
        else check_door_result(&cpu,2,1);
    }
    /* Default Either admits either real native overlap, with transport. */
    door_setup(&cpu,0,480,400);check_door_result(&cpu,1,1);
    CHECK(psx_mod_read_byte(PLAYER+0xD4) && !p2.body[0xD4] && occurrences(0x80050C88u)==2);
    door_setup(&cpu,0,400,480);check_door_result(&cpu,2,1);
    CHECK(!psx_mod_read_byte(PLAYER+0xD4) && p2.body[0xD4] && occurrences(0x80050C88u)==3);
    /* Both must veto the native admission for either distant living actor,
     * while still updating/drawing the door exactly once. */
    door_setup(&cpu,1,480,400);check_door_result(&cpu,0,0);
    CHECK(!psx_mod_read_byte(PLAYER+0xD4) && !p2.body[0xD4] && !psx_mod_read_byte(PLAY+0x1C));
    door_setup(&cpu,1,400,480);check_door_result(&cpu,0,0);
    CHECK(!psx_mod_read_byte(PLAYER+0xD4) && !p2.body[0xD4]);
    door_setup(&cpu,1,480,480);check_door_result(&cpu,1,0);
    CHECK(psx_mod_read_byte(PLAYER+0xD4)==1 && p2.body[0xD4]==1 &&
        both_door_traversal_active());
    /* Permissions come from the real native admission. Other scenes/menu
     * phases cannot opt the private player into world-scene execution. */
    pause_owner=1;CHECK(!both_door_traversal_active());pause_owner=-1;
    scene_phase=1;CHECK(!both_door_traversal_active());scene_phase=0;
    unsigned before=call_count;scene_tick(&cpu);
    CHECK(scene_owner==1 && !scene_phase && call_count==before && !scene_passenger(1));
    psx_mod_write_byte(PLAYER+0xD4,0);psx_mod_write_byte(PLAY+0x1C,0);scene_tick(&cpu);
    CHECK(scene_owner==1); /* The other admitted native request still owns the barrier. */
    p2.body[0xD4]=0;scene_tick(&cpu);
    CHECK(!scene_owner && !scene_phase && call_count==before);
    script_begin(&cpu,0x8003D308u);CHECK(scene_owner==1 && scene_phase==1); /* Door-only exception. */
    /* Every non-ALIVE seat is excluded, never revived or teleported. */
    for(unsigned status=MMX6_COOP_LEAVING;status<=MMX6_COOP_FALLEN;++status) {
        door_setup(&cpu,1,480,400);life.status[1]=(Mmx6CoopStatus)status;
        check_door_result(&cpu,1,0);CHECK(life.status[1]==status && !p2.body[0xD4]);
        door_setup(&cpu,1,400,480);life.status[0]=(Mmx6CoopStatus)status;
        check_door_result(&cpu,2,0);CHECK(life.status[0]==status && !psx_mod_read_byte(PLAYER+0xD4));
    }
    door_setup(&cpu,1,480,480);life.status[0]=life.status[1]=MMX6_COOP_FALLEN;
    check_door_result(&cpu,0,0);CHECK(!psx_mod_read_byte(PLAYER+0xD4));
    /* Native prerequisites remain authoritative even when both overlap. */
    for(unsigned gate=0;gate<10;++gate) {
        door_setup(&cpu,1,480,480);
        switch(gate) {
        case 0:p2.body[0xA4]=1;break;
        case 1:p2.body[0x5C]=0x80;break;
        case 2:p2.body[5]=3;break;
        case 3:p2.body[0x8E]=1;break;
        case 4:psx_mod_write_byte(PLAYER+0x7A,1);break;
        case 5:put32(p2.body+8,501u<<16);break;
        case 6:put32(p2.body+12,1021u<<16);break; /* Overlap, not containment. */
        case 7:put32(p2.body+0x68,0);break;
        case 8:put32(p2.body+8,469u<<16);break; /* Signed offset makes separation25 > widths24. */
        case 9:p2.body[0]=0;break;
        }
        check_door_result(&cpu,0,0);CHECK(!psx_mod_read_byte(PLAYER+0xD4) && !p2.body[0xD4]);
    }
    door_setup(&cpu,1,480,470);put32(p2.body+12,1020u<<16);check_door_result(&cpu,1,0);
    door_setup(&cpu,1,480,480);door_subtype_allowed=0;check_door_result(&cpu,0,0);
    CHECK(occurrences(0x80050C88u)==2); /* Preprobes cannot bypass native subtype refusal. */
    /* A predicate elsewhere has no policy gate or fabricated native result. */
    door_setup(&cpu,1,480,400);cpu.gpr[31]=0x80050368u;
    CHECK(!door_eligibility(&cpu,0x80050C88u));
    uint32_t context[6]={0x80050250u,TEST_DOOR,0,0,1,1};
    STATE_WORDS(frame,35,context,6);scene_call=1;
    cpu.gpr[31]=0x8005036Cu;CHECK(!door_eligibility(&cpu,0x80050C88u));
    cpu.gpr[31]=0x80050368u;cpu.gpr[4]=TEST_DOOR+0x70;CHECK(!door_eligibility(&cpu,0x80050C88u));
    cpu.gpr[4]=TEST_DOOR;CHECK(door_eligibility(&cpu,0x80050C88u) && !cpu.gpr[2]);
    context[3]=1;STATE_UPDATE(frame,context);CHECK(!door_eligibility(&cpu,0x80050C88u));
    STATE_POP(frame);scene_call=door_native_probe=0;
}
static void native_both_door_ack_motion_and_release(void) {
    CPUState cpu;
    for(unsigned trailing=0;trailing<2;++trailing) {
        door_setup(&cpu,1,480,480);check_door_result(&cpu,1,0);
        CHECK(both_door_actor==TEST_DOOR && both_door_members==3);
        psx_mod_write_byte(TEST_DOOR+5,1);
        psx_mod_write_byte(PLAYER+0xD4,0xFF); /* Only primary earned its native acknowledgement. */
        CHECK(door_update(&cpu,0x80050DFCu));
        CHECK(psx_mod_read_byte(TEST_DOOR+5)==1 && p2.body[0xD4]==1 &&
              psx_mod_read_byte(PLAYER+0xD4)==0xFF && !psx_mod_read_byte(PLAY+0x10));
        p2.body[0xD4]=0xFF; /* Original second controller now acknowledges independently. */
        CHECK(door_update(&cpu,0x80050DFCu));
        CHECK(psx_mod_read_byte(TEST_DOOR+5)==2 && psx_mod_read_byte(PLAYER+0xD4)==0xFE &&
              p2.body[0xD4]==0xFE && !psx_mod_read_word(PLAYER+0x68) && !le32(p2.body+0x68));
        psx_mod_write_byte(TEST_DOOR+5,3);psx_mod_write_word(TEST_DOOR+0x84,0x18000u);
        psx_mod_write_word(PLAYER+8,(trailing?490u:480u)<<16);
        put32(p2.body+8,(trailing?480u:490u)<<16);
        psx_mod_write_half(0x80097202u,100);psx_mod_write_half(0x8009721Eu,200);
        uint32_t x=psx_mod_read_word(PLAYER+8),z=le32(p2.body+8),draws=door_draws;
        CHECK(door_update(&cpu,0x80050DFCu));
        CHECK(psx_mod_read_word(PLAYER+8)==x+0x18000u && le32(p2.body+8)==z+0x18000u &&
              door_draws==draws+1 && psx_mod_read_byte(TEST_DOOR+5)==3);
        CHECK(psx_mod_read_byte(PLAY+0x10)==1 && psx_mod_read_byte(PLAY+0x12)==1);
        psx_mod_write_half(0x80097202u,200);
        CHECK(door_update(&cpu,0x80050DFCu));
        CHECK(!psx_mod_read_byte(PLAYER+0xD4) && !p2.body[0xD4] &&
              psx_mod_read_word(PLAYER+0x68)==0x80073D50u && le32(p2.body+0x68)==0x80073D54u &&
              psx_mod_read_byte(TEST_DOOR+5)==4 && psx_mod_read_word(PLAY+0x90)==1);
        CHECK(door_update(&cpu,0x80050DFCu));scene_tick(&cpu);
        CHECK(!scene_owner && !both_door_actor && !both_door_members &&
              !inside && !zero_projected && !scene_call && !state_track.count && !state_track.error);
    }
    /* A generic phase-zero scene or another door has no authenticated authority. */
    door_setup(&cpu,1,480,480);scene_owner=1;
    CHECK(!both_door_traversal_active() && !door_update(&cpu,0x80050DFCu));
    for(unsigned invalid=0;invalid<3;++invalid) {
        door_setup(&cpu,1,480,480);check_door_result(&cpu,1,0);
        if(invalid==0)psx_mod_write_byte(TEST_DOOR,0);
        if(invalid==1)psx_mod_write_byte(TEST_DOOR+1,9);
        if(invalid==2)psx_mod_write_word(TEST_DOOR+0x10,0x800FA2B0u);
        CHECK(!both_door_traversal_active());scene_tick(&cpu);
        CHECK(failed && !both_door_actor && !both_door_origin && !both_door_members &&
              psx_mod_read_byte(PLAYER+0xD4)==1 && p2.body[0xD4]==1 && !scene_phase);
    }
}
int main(void){CHECK(PLAYER_MODE_OFFSET+PLAYER_PACKET_LIMIT*8u<=FRAME_ARENA);
    controller_pair_and_restoration();scene_passengers_keep_native_fixed_effects();native_nova_guest_update();lifetime_and_gates();menu_freeze_and_select_resume();native_menu_campaign_authority();draw_order_retained_packets_and_survivor();borrowed_menu_retains_primary_pools();borrowed_menu_restores_primary_sprite_sheet();native_giga_backup_survives_private_callbacks();clear_banks();
    deferred_shared_effect_owner_context();
    deferred_dash_effect_uses_allocating_body();
    deferred_ui_effect_retains_owner_atlas();clear_banks();
    arrival_draw_precedes_stage_callback();clear_banks();
    deferred_icon_effect_retains_zero_source();clear_banks();
    deferred_dash_effect_retains_zero_atlas();clear_banks();
    private_giga_shots_retain_zero_source();
    deferred_death_effect_retains_zero_source();clear_banks();
    native_shared_dialogue_palette();
    native_working_palette_class_and_load_events();
    native_working_palette_rectangle();
    yammar_native_upload_coordinates();
    native_shared_ride_ownership();
    native_shared_clear_admission_and_departure();
    native_either_both_door_admission();
    native_both_door_ack_motion_and_release();
    puts("private native effects actual-plugin call order, gates, lifetime projection and retained packet ownership PASS");return 0;}
