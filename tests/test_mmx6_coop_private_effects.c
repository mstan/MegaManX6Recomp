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
static uint32_t expected_follower_x;
static int texture_support=1,marker_override=2,terminal_player,stage_driver;
static int menu_probe;
static unsigned menu_vram_probe,gp0_upload_stage,gp0_upload_left,gp0_upload_x,gp0_upload_y,gp0_upload_width,gp0_upload_at;
static uint16_t original_menu_vram[1024*512];
static uint16_t menu_input[3];
static unsigned native_budget;
static unsigned boss_scan_probe,boss_scan_type[2],boss_scan_cookie[2],boss_scan_present[2],boss_scan_calls[2];
static unsigned shared_probe,shared_probe_seat,shared_probe_delete,shared_probe_calls;
static unsigned surface_probe,surface_end,surface_bounds_calls,surface_ticks;
static unsigned falcon_flight_probe;
static unsigned muzzle_probe,muzzle_expected_seat,muzzle_calls;
static unsigned ride_probe,ride_overlap,ride_ticks,ride_seat,ride_primary_character,ride_character;
static unsigned ride_camera_fatal,ride_query_calls,ride_query_bad,ride_reboards;
static unsigned door_native_probe,door_ticks,door_draws,door_subtype_allowed;
static unsigned icon_packet_probe,dash_packet_probe,armor_packet_probe,falcon_packet_probe;
static unsigned render_replacement_probe;
static unsigned working_palette_probe,working_palette_probe_calls;
static unsigned death_packet_probe,death_origin_probe,nova_probe;
static unsigned scene_transport_probe,capsule_native_probe;
static unsigned scene_release_on_input;
static unsigned projected_death_probe;
static unsigned scene_survivor_worlds,scene_corpse_updates[2],scene_native_retries;
static unsigned voluntary_transport_probe;
static unsigned paired_arrival_fixture_probe,arrival_landed,arrival_ticks[2],arrival_births;
static unsigned clear_probe,clear_worlds,clear_zero_worlds,clear_fades;
static unsigned clear_constructors[2],clear_body_ticks[2],clear_poses[2],clear_outgoing[2],clear_pose_limit[2];
static unsigned clear_air_ticks,clear_air_limit,clear_air_seat;
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
    /* External safe-boundary release contract, at the same point as the
     * agreed LAB callback: after diagnostic setup, before original world. */
    if(consumer==MMX6_INPUT_STAGE && scene_release_on_input) {
        CHECK(scene_owner_fatal() && scene_phase==3);
        psx_mod_write_byte(PLAY+0x1C,0);scene_release_on_input=0;
    }
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
uint64_t psx_mod_spu_private_voice_owner(unsigned slot){CHECK(slot<24);return 0;}
int psx_mod_spu_private_voice_volume_owned(uint64_t owner,unsigned slot,uint16_t left,uint16_t right){
    (void)owner;(void)slot;(void)left;(void)right;CHECK(0);return 0;
}
int psx_mod_spu_private_voice_stop_owned(uint64_t owner,uint32_t mask){(void)owner;(void)mask;CHECK(0);return 0;}
int psx_mod_forget_texture_bank_range(uint16_t first,uint32_t count){CHECK(first==0x7000 && count==4096);return 1;}
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
    if(falcon_packet_probe && actor==0x80091298u) {
        /* Original DAT87 header1C flight frame0 selects jet tile8 at page5
         * with fixed7802, independently of the retention admission guard. */
        q[1]=0x7D000000u;q[3]=0x78020080u;memset(q+4,0,6*sizeof *q);
    } else if(armor_packet_probe) {
        /* Original25984 + DAT88 header5 frame0: page5/UV C0,0,
         * packed flags0 select fixed CLUT7843 (working slot19). This
         * armor uses the upper tiles of actor+38's compressed body frame.
         * DAT88 frame0 uploads14 tiles; armor selects {12,13,7..11}. */
        q[1]=0x7D000000u;q[3]=0x784300C0u;
        memset(q+4,0,6*sizeof *q);
    } else if(dash_packet_probe && actor==0x80091298u) {
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
    psx_mod_write_word(mode+4,(armor_packet_probe || falcon_packet_probe)?0xE1000025u:dash_packet_probe && actor==0x80091298u?0xE1000025u:
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
    if(projected_death_probe && address==0x80034DCCu) {
        CHECK(zero_world && zero_projected && player_call);
        for(unsigned i=0x12;i<=0x1C;++i)psx_mod_write_byte(PLAY+i,1);
        psx_mod_write_byte(PLAYER+4,2);psx_mod_write_byte(PLAYER+0x5C,0);
        return;
    }
    if(boss_scan_probe && address==0x8002BCCCu) {
        /* Allocator result may reuse the exact kind/origin/address. */
        cpu->gpr[2]=cpu->gpr[4];return;
    }
    if(boss_scan_probe && address==0x80031474u) {
        unsigned seat=(unsigned)!!zero_projected;uint32_t actor=cpu->gpr[4],shot=0x800950A0u;
        ++boss_scan_calls[seat];
        /* Original31474 clears65 on no overlap and maps duplicate126 to0.
         * Original315CC stamps the seat's cookie before defense rejection. */
        if(!boss_scan_present[seat]) {psx_mod_write_byte(actor+0x65,0);cpu->gpr[2]=0;return;}
        unsigned cookie=boss_scan_cookie[seat];
        if(cookie && psx_mod_read_byte(actor+0x65)==cookie){cpu->gpr[2]=0;return;}
        psx_mod_write_byte(actor+0x65,(uint8_t)cookie);
        if(psx_mod_read_word(actor+0x58)==0x8007433Cu){cpu->gpr[2]=127;return;}
        psx_mod_write_byte(shot+1,(uint8_t)boss_scan_type[seat]);
        cpu->gpr[7]=shot;cpu->gpr[8]=actor;cpu->gpr[5]=2;
        boss_balance_damage(cpu,0x800318F4u);
        psx_mod_write_byte(actor+0x5C,(uint8_t)(psx_mod_read_byte(actor+0x5C)-cpu->gpr[5]));
        cpu->gpr[2]=boss_scan_type[seat]+1;return;
    }
    if(paired_arrival_fixture_probe) {
        unsigned seat=psx_mod_read_byte(PLAYER+2);
        if(address==0x8001E9ECu) {
            CHECK(stage_call && arrival_pair);
            for(unsigned i=0;i<6;i+=2)CHECK(!(psx_mod_read_half(0x800C456C+i)&0x0800));
            return;
        }
        if(address==0x8003BD24u) {
            psx_mod_write_byte(PLAYER,1);psx_mod_write_byte(PLAYER+2,psx_mod_read_byte(PLAY+0x38));
            psx_mod_write_word(PLAYER+0x38,assets);psx_mod_write_word(PLAYER+0x3C,assembly);
            psx_mod_write_byte(PLAYER+0x5C,32);++arrival_births;return;
        }
        CHECK(cpu->gpr[4]==PLAYER || address==0x80034DCCu ||
              address==0x8002012Cu || address==0x80020D74u || address==0x80020DC8u);
        if(address==0x8003D718u) {psx_mod_write_byte(PLAYER+0xE7,5);return;}
        if(address==0x8003D630u) {
            for(unsigned i=0;i<9;++i)psx_mod_write_half(PLAYER+0xA8u+i*2u,288);
            return;
        }
        if(address==0x8003AD18u){psx_mod_write_byte(PLAYER+5,2);return;}
        if(address==0x8003A980u){psx_mod_write_byte(PLAYER+0x8C,0);return;}
        if(address==0x8003BA04u){psx_mod_write_byte(PLAYER+0x46,0);return;}
        if(address==0x8003CCBCu){psx_mod_write_word(PLAYER+0x68,0x80073D54u);return;}
        if(address==0x8003D850u){
            CHECK(seat==1 && zero_projected);
            psx_mod_write_byte(PLAYER+5,0);psx_mod_write_byte(PLAYER+6,0);
            psx_mod_write_byte(PLAYER+0x67,255);psx_mod_write_word(PLAYER+0x24,0xFFF80000u);return;
        }
        if(address==0x80034DCCu) {
            for(unsigned i=0;i<8;i+=2)CHECK(!psx_mod_read_half(PLAYER+0x7C+i));
            ++arrival_ticks[seat];
            if(arrival_landed&(1u<<seat)) {
                psx_mod_write_byte(PLAYER+5,2);psx_mod_write_byte(PLAYER+0x67,0);
                psx_mod_write_byte(PLAYER+0x70,8);
            }
            /* Native Zero arrival clears hold/camera flags internally; none
             * may escape its private projection into X's shared world. */
            if(seat){psx_mod_write_byte(PLAY+0x1C,0);psx_mod_write_word(0x80097202u,999);}
            return;
        }
        CHECK(address==0x8002012Cu || address==0x8002F288u ||
              address==0x80020D74u || address==0x80020DC8u);
        return;
    }
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
                CHECK(seat==clear_air_seat && !clear_constructors[seat]);
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
    if(ride_probe && address==0x80030234u) {
        CHECK(cpu->gpr[4]==RIDE);++ride_query_calls;
        unsigned x=cpu->gpr[5],y=cpu->gpr[6];
        unsigned tracked=0;
        for(unsigned i=0;i<state_track.count;++i)if(state_track.frame[i].tag==116) {
            const Mmx6StateFrame *frame=&state_track.frame[i];uint32_t q[10];
            CHECK(frame->words && frame->bytes==sizeof q);memcpy(q,frame->saved,sizeof q);
            CHECK(q[7]==x && q[8]==y);tracked=1;
        }
        CHECK(tracked); /* Future-restored query progress is digest/snapshot-owned. */
        cpu->gpr[2]=y>=416?0x38u:0;
        if(ride_query_bad==1 && y<416)cpu->gpr[2]=0x38;
        if(ride_query_bad==2 && y==416 && x>=3232)cpu->gpr[2]=0;
        return;
    }
    if(scene_transport_probe) {
        /* Bounded original beam/cancellation contracts; these do not rebuild
         * or repair fixed actor metadata on the plugin's behalf. */
        unsigned passenger=scene_transport_probe-1;
        if(address==0x8001E9ECu) {
            CHECK(stage_call);
            if(life.wipe) {
                CHECK(psx_mod_read_byte(PLAYER+4)==3);
                psx_mod_write_byte(PLAY+1,1);++scene_native_retries;return;
            }
            CHECK(zero_world==passenger && psx_mod_read_byte(PLAYER+2)==passenger);
            CHECK(psx_mod_read_byte(PLAYER+4)==1); /* Original retry gate precedes player_tick. */
            ++scene_survivor_worlds;
            psx_mod_write_word(PLAY+0x90,psx_mod_read_word(PLAY+0x90)+1);
            unsigned before=call_count;CHECK(player_tick(cpu,0x80034DCCu));
            CHECK(call_count==before); /* Scene owns this incoming body, not ordinary native movement. */
            return;
        }
        if(address==0x80034DCCu && psx_mod_read_byte(PLAYER+2)==(passenger^1u)) {
            CHECK(inside && psx_mod_read_byte(PLAYER+4)==2);
            ++scene_corpse_updates[passenger^1u];psx_mod_write_byte(PLAYER+4,3);return;
        }
        CHECK(inside && ((scene_call && scene_owner) || voluntary_transport_probe));
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
        if(address==0x8003A268u && ride_probe) {
            CHECK(psx_mod_read_byte(PLAYER+0xD5)==1 && psx_mod_read_byte(RIDE)&1u);
            CHECK(psx_mod_read_word(PLAYER+8)==psx_mod_read_word(RIDE+8) &&
                psx_mod_read_word(PLAYER+12)==psx_mod_read_word(RIDE+12));
            ++ride_reboards;psx_mod_write_byte(PLAYER+5,0x12);psx_mod_write_byte(PLAYER+0xD5,255);
            psx_mod_write_byte(PLAYER+0x67,1);psx_mod_write_word(PLAYER+0x68,0);return;
        }
        CHECK(0);
    }
    if(capsule_native_probe) {
        if(capsule_native_probe==2) {
            uint32_t actor=cpu->gpr[4];
            CHECK(scene_call && solid_call && inside);
            if(address==0x80051890u) {
                CHECK(zero_projected && psx_mod_read_byte(PLAYER+2)==0);
                /* External original outer order: phase consumes previous
                 * contact, then31DA8 produces the next. No mocked grant
                 * runs when the owner did not have top contact. */
                if(psx_mod_read_byte(actor+5)==6 && (psx_mod_read_byte(actor+0x72)&8u)) {
                    psx_mod_write_byte(PLAYER+0xE2,1);psx_mod_write_byte(actor+5,7);
                }
                CHECK(!solid_player_collision(cpu,0x80031DA8u));
                psx_mod_write_byte(actor+0x72,8);psx_mod_write_byte(actor+0x76,1);
                psx_mod_write_byte(PLAYER+0x71,8);cpu->gpr[2]=0xCAFE;return;
            }
            CHECK(address==0x80031DA8u && psx_mod_read_byte(PLAYER+2)==1);
            psx_mod_write_byte(actor+0x72,2);psx_mod_write_byte(PLAYER+0x71,2);return;
        }
        /* External original51924->3D308 request and shared capsule locks. */
        CHECK(address==0x80051924u);
        psx_mod_write_byte(PLAYER+0xD0,20);
        for(unsigned n=0;n<4;++n) {
            const unsigned offsets[]={0x12,0x13,0x16,0x17};
            psx_mod_write_byte(PLAY+offsets[n],1);
        }
        cpu->gpr[2]=1;return;
    }
    if(door_native_probe) {
        if(address==0x8002CB50u) {
            CHECK(scene_call && inside==zero_projected && cpu->gpr[4]==0x800C12C4u && cpu->gpr[5]==PLAY && cpu->gpr[6]==PLAYER);
            ++door_draws;cpu->gpr[2]=0xD008;return;
        }
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
        unsigned character=psx_mod_read_byte(PLAYER+2),seat=character!=ride_primary_character;
        if(address==0x8002DCF4u) {
            CHECK(cpu->gpr[4]==PLAYER && cpu->gpr[5]==RIDE &&
                psx_mod_read_word(RIDE+0x68)==(psx_mod_read_byte(RIDE+1)==1?0x800F2F2Cu:0x800F3A48u));
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
            ++ride_ticks;ride_seat=seat;ride_character=character;
            if(ride_camera_fatal && psx_mod_read_byte(PLAYER+0xD5) &&
               (psx_mod_read_byte(RIDE+0xA8)&1u) &&
               (int16_t)psx_mod_read_half(RIDE+10)-(int16_t)psx_mod_read_half(0x80097202u)<32) {
                /* Original BIN28 EFCCC/EFCD0/EFD68, not a plugin repair. */
                psx_mod_write_byte(PLAYER+0x5C,128);psx_mod_write_byte(RIDE+0x5C,128);
                psx_mod_write_byte(RIDE,0);cpu->gpr[2]=77;return;
            }
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
    if(surface_probe && (address==0x8002CBFCu || address==0x8002CCB0u)) {
        /* External original uint16 half-open320x240 bounds contract. */
        uint32_t a=cpu->gpr[4],rx=cpu->gpr[5],ry=cpu->gpr[6];
        int dx=(int16_t)(psx_mod_read_half(a+10)-psx_mod_read_half(0x80097202u));
        int dy=(int16_t)(psx_mod_read_half(a+14)-psx_mod_read_half(0x80097206u));
        unsigned outside=(uint16_t)(dx+rx)>=320u+rx*2u || (uint16_t)(dy+ry)>=240u+ry*2u;
        if(address==0x8002CCB0u)psx_mod_write_byte(a+3,(uint8_t)!outside);
        ++surface_bounds_calls;cpu->gpr[2]=outside;return;
    }
    if(surface_probe && address==0x80049A14u) {
        uint32_t a=cpu->gpr[4];CHECK(shared_fx_call==1 && zero_projected);
        CHECK(psx_mod_read_byte(PLAYER+2)==1);
        ++surface_ticks;
        if(psx_mod_read_byte(a+4)==2){psx_mod_write_byte(a,0);cpu->gpr[2]=0x309;return;}
        CHECK(psx_mod_read_byte(PLAYER+0xDF)==1);
        cpu->gpr[31]=0x80049CA0u;cpu->gpr[5]=cpu->gpr[6]=32;
        CHECK(guest_geometry_lifetime(cpu,0x8002CBFCu));
        if(cpu->gpr[2]){psx_mod_write_byte(a+4,2);cpu->gpr[2]=0x309;return;}
        psx_mod_write_byte(a+4,1);
        /* Original animation command releases only the allocating actor's DF;
         * its later negative animation-end selects state2, then real free. */
        if(surface_end){psx_mod_write_byte(PLAYER+0xDF,0);psx_mod_write_byte(a+4,2);}
        cpu->gpr[31]=0x80049D68u;cpu->gpr[5]=cpu->gpr[6]=32;
        CHECK(amazon_guest_support_visibility(cpu,0x8002CCB0u));
        cpu->gpr[2]=0x309;return;
    }
    if(shared_probe && address==0x8002C398u) {
        memset(memory(0x80091298u),0,0x70);cpu->gpr[2]=0x80091298u;return;
    }
    if(falcon_flight_probe && address==0x8004B3A0u) {
        CHECK(shared_fx_call && zero_projected && psx_mod_read_byte(PLAYER+2)==0);
        CHECK(psx_mod_read_byte(PLAYER+0xE7)==1 && psx_mod_read_word(SCRATCH+0x1C)==assembly);
        uint32_t actor=cpu->gpr[4];
        if(psx_mod_read_byte(PLAYER+5)!=0x23){psx_mod_write_byte(actor,0);return;}
        /* External original4B3D0..4B46C contract: no compression pointer;
         * distinct jet assembly, body-derived pose and the flyer's origin. */
        psx_mod_write_byte(actor+3,1);psx_mod_write_byte(actor+4,1);
        psx_mod_write_word(actor+0x3C,assembly+psx_mod_read_word(assembly+0x1C));
        psx_mod_write_half(actor+0x40,0x0500);psx_mod_write_half(actor+0x42,0x7802);
        psx_mod_write_byte(actor+0x16,3);
        psx_mod_write_byte(actor+0x47,psx_mod_read_byte(PLAYER+0x47)-0x42);
        psx_mod_write_word(actor+8,psx_mod_read_word(PLAYER+8));
        psx_mod_write_word(actor+12,psx_mod_read_word(PLAYER+12));
        cpu->gpr[2]=0x1823;return;
    }
    if(muzzle_probe && address==0x80049478u) {
        /* External original49854 contract: the deferred shot is allocated
         * in the resident pool and increments the resident counter. It has
         * no explicit owner pointer. This witnesses wrong-seat projection. */
        CHECK(shared_fx_call && (unsigned)!!zero_projected==muzzle_expected_seat);
        CHECK(psx_mod_read_byte(PLAYER+2)==0 && !psx_mod_read_byte(PLAYER+0xE7));
        const uint32_t shot=0x800950A0u;
        CHECK(!psx_mod_read_byte(shot));
        psx_mod_write_byte(shot,0x21);psx_mod_write_byte(shot+1,0x12);
        psx_mod_write_byte(shot+3,1);psx_mod_write_byte(shot+4,1);
        psx_mod_write_word(shot+8,psx_mod_read_word(PLAYER+8));
        psx_mod_write_word(shot+0x3C,psx_mod_read_word(SCRATCH+0x1C));
        psx_mod_write_byte(PLAYER+0x98,psx_mod_read_byte(PLAYER+0x98)+1);
        psx_mod_write_byte(OVERLAY+0x5900,0x6D);
        psx_mod_write_byte(cpu->gpr[4],0);++muzzle_calls;
        cpu->gpr[2]=0x1234;return;
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
    if(address==0x8002619Cu) {
        CHECK(world_render && cpu->gpr[4]==PLAYER && !psx_mod_read_byte(PLAYER+2));
        CHECK(psx_mod_read_word(SCRATCH+0x1C)==assembly);
        /* Original2619C's action1/frame7E exclusion applies except form4.
         * The plugin calls the actual native gate, not its own pose copy. */
        if(psx_mod_read_byte(PLAYER+0xE7)!=4 && psx_mod_read_byte(PLAYER+5)==1 &&
           psx_mod_read_byte(PLAYER+0x47)==0x7E)return;
        armor_packet_probe=1;native_draw(PLAYER);armor_packet_probe=0;return;
    }
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
        expected_follower_x=psx_mod_read_word(PLAYER+8)+3*65536;
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
        CHECK(psx_mod_read_word(PLAYER+8)==expected_follower_x);native_attached();
    }else if(address==0x80020DC8u){native_trails();}
    else if(address!=0x80017A04u)CHECK(0);
}
static void clear_banks(void){for(unsigned i=0;i<bank_count;++i){free(banks[i].pixels);memset(&banks[i],0,sizeof banks[i]);}bank_count=0;}
static void setup(CPUState *cpu){
    private_actor=default_private_actor;
    clear_banks();memset(ram,0,sizeof ram);memset(extra,0,sizeof extra);memset(&p2,0,sizeof p2);memset(cpu,0,sizeof *cpu);
    memset(test_vram,0,sizeof test_vram);memset(bank_first,0,sizeof bank_first);memset(zero_overlay,0x44,sizeof zero_overlay);
    mmx6_coop_lifecycle_init(&life);state_track.count=state_track.error=0;
    boss_balance_enabled=boss_balance_allocate_call=boss_balance_pending_actor=0;memset(boss_balance,0,sizeof boss_balance);
    inside=failed=player_call=zero_world=world_render=scene_owner=scene_phase=zero_projected=0;
    shared_clear_reset();clear_probe=clear_worlds=clear_zero_worlds=clear_fades=0;
    memset(clear_constructors,0,sizeof clear_constructors);memset(clear_body_ticks,0,sizeof clear_body_ticks);
    memset(clear_poses,0,sizeof clear_poses);memset(clear_outgoing,0,sizeof clear_outgoing);
    clear_air_ticks=clear_air_limit=clear_air_seat=0;
    shared_fx_call=shared_fx_allocate_call=0;memset(shared_effect_owners,0,sizeof shared_effect_owners);
    surface_probe=surface_end=surface_bounds_calls=surface_ticks=0;
    shared_probe=shared_probe_seat=shared_probe_delete=shared_probe_calls=falcon_flight_probe=0;
    muzzle_probe=muzzle_expected_seat=muzzle_calls=0;
    ride_probe=ride_overlap=ride_ticks=ride_seat=ride_call=ride_primary_character=ride_character=0;
    ride_camera_fatal=ride_query_calls=ride_query_bad=ride_reboards=0;
    door_native_probe=door_ticks=door_draws=both_doors=scene_call=0;both_door_reset();door_subtype_allowed=1;
    icon_packet_probe=dash_packet_probe=armor_packet_probe=falcon_packet_probe=render_replacement_probe=0;
    death_packet_probe=death_origin_probe=effect_call=nova_probe=scene_transport_probe=voluntary_transport_probe=capsule_native_probe=0;memset(death_effect,0,sizeof death_effect);
    projected_death_probe=0;
    scene_survivor_worlds=scene_native_retries=0;memset(scene_corpse_updates,0,sizeof scene_corpse_updates);
    working_palette_probe=working_palette_probe_calls=0;working_palette_assets_ready=0;
    private_terrain_pending=0;
    ready=enrolled=stage_call=1;pause_owner=-1;zero_menu_loaded=0;join_phase=arrival_pair=0;previous_input=p2_edges=0;p2_start_previous=0;
    paired_arrival_fixture_probe=arrival_landed=arrival_births=0;memset(arrival_ticks,0,sizeof arrival_ticks);
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
    boss_balance_independent=0;boss_scan_probe=0;
}
/* The real native driver separates input from its post-world terrain and
 * follower tail. Preserve that boundary in these existing full-frame cases. */
static void controller_frame(CPUState *cpu,uint32_t address){
    uint32_t caller=cpu->gpr[31];
    int canonical=caller==0x80020C70u && !inside && !zero_world;
    controller(cpu,address);
    if(canonical){
        cpu->gpr[31]=0x80020CD0u;
        private_terrain_after_world(cpu,0x8002927Cu);
        cpu->gpr[31]=caller;
    }
}
static void controller_pair_and_restoration(void){
    CPUState cpu;setup(&cpu);PlayerContext resident;capture_player(&resident);uint8_t play[0xE0],camera[0x100];capture(PLAY,play,sizeof play);capture(0x800971F8,camera,sizeof camera);
    marker_override=1;p2.body[0x9C]=1;controller_frame(&cpu,0x8002012C);
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
static void scene_owner_death_preserves_living_passenger(void) {
    for(unsigned passenger=0;passenger<2;++passenger)for(unsigned incoming=0;incoming<2;++incoming)
    for(unsigned late_release=0;late_release<2;++late_release) {
        if(incoming && late_release)continue;
        CPUState cpu;setup(&cpu);
        PlayerContext primary=p2;primary.body[2]=0;
        primary.body[0x70]=p2.body[0x70]=8;project_player(&primary);
        psx_mod_write_half(0x80097206u,980);
        psx_mod_write_byte(PLAY+0x1C,1);scene_transport_probe=passenger+1;
        unsigned owner=passenger^1u;
        scene_begin(owner,0x8003D308u);scene_tick(&cpu);scene_tick(&cpu);
        CHECK(scene_phase==3 && life.status[passenger]==MMX6_COOP_ALIVE);
        if(incoming) {psx_mod_write_byte(PLAY+0x1C,0);scene_tick(&cpu);CHECK(scene_phase==4);}
        uint32_t destination_x=incoming?(owner?le32(p2.body+8):psx_mod_read_word(PLAYER+8)):le32(scene_body+8);
        if(owner) {
            p2.body[4]=2;p2.body[0x5C]=p2.body[0x70]=0;
            p2.body[0xD0]=p2.body[0xD4]=p2.body[0x7A]=255;
        } else {
            psx_mod_write_byte(PLAYER+4,2);psx_mod_write_byte(PLAYER+0x5C,0);psx_mod_write_byte(PLAYER+0x70,0);
            psx_mod_write_byte(PLAYER+0xD0,255);psx_mod_write_byte(PLAYER+0xD4,255);psx_mod_write_byte(PLAYER+0x7A,255);
        }
        mmx6_coop_fatal(&life,owner);
        if(!incoming) {
            unsigned before=call_count;scene_tick(&cpu);
            CHECK(scene_phase==3 && call_count==before); /* Original shared script still owns release. */
            if(late_release)scene_release_on_input=1;
            else psx_mod_write_byte(PLAY+0x1C,0);
        } else {
            psx_mod_write_byte(PLAY+0x1C,1);scene_tick(&cpu);
            CHECK(scene_phase>=4); /* A fatal hold cannot withdraw the incoming passenger again. */
            psx_mod_write_byte(PLAY+0x1C,0);
        }
        stage_call=0;
        for(unsigned n=0;n<12 && scene_owner;++n)CHECK(stage_tick(&cpu,0x8001E9ECu));
        CHECK(!scene_owner && !scene_phase && !life.wipe && !failed && !state_track.count && !state_track.error);
        CHECK(scene_survivor_worlds && scene_corpse_updates[owner]==1 && !scene_native_retries && !scene_release_on_input);
        CHECK(psx_mod_read_word(PLAY+0x90)==scene_survivor_worlds && !psx_mod_read_byte(PLAY+1));
        uint8_t body[sizeof scene_body];if(passenger)memcpy(body,p2.body,sizeof body);else capture(PLAYER,body,sizeof body);
        CHECK(body[3] && body[4]==1 && body[5]==2 && body[0x5C]==32 && !body[0x67]);
        CHECK(le32(body+8)==destination_x && le32(body+12)==le32(scene_body+12));
        CHECK(life.status[passenger]==MMX6_COOP_ALIVE && life.status[owner]==MMX6_COOP_FALLEN);
    }
    CPUState cpu;setup(&cpu);projected_death_probe=1;
    enter_zero();zero_world=inside=1;
    CHECK(player_tick(&cpu,0x80034DCCu));
    CHECK(life.status[0]==MMX6_COOP_ALIVE && life.status[1]==MMX6_COOP_DYING && !life.wipe);
    for(unsigned i=0x12;i<=0x1C;++i)CHECK(!psx_mod_read_byte(PLAY+i));
    zero_world=inside=0;leave_zero();
    /* An actual team death keeps the original freeze/retry contract. */
    setup(&cpu);projected_death_probe=1;life.status[0]=MMX6_COOP_FALLEN;
    enter_zero();zero_world=inside=1;CHECK(player_tick(&cpu,0x80034DCCu));
    CHECK(life.wipe==2);for(unsigned i=0x12;i<=0x1C;++i)CHECK(psx_mod_read_byte(PLAY+i)==1);
    zero_world=inside=0;leave_zero();
    for(unsigned negative=0;negative<5;++negative) {
        setup(&cpu);scene_owner=2;scene_phase=3;scene_body[4]=1;scene_body[0x5C]=32;
        life.status[1]=MMX6_COOP_FALLEN;
        if(negative==1) {life.status[0]=MMX6_COOP_FALLEN;life.wipe=2;}
        if(negative==2) life.status[1]=MMX6_COOP_ALIVE; /* Normal victory/departure retirement. */
        if(negative==3) psx_mod_write_byte(PLAYER+0x5C,0x80);
        if(negative==4) clear_phase=1;
        CHECK(scene_owner_fatal()==(negative==0));
    }
    for(unsigned owner=0;owner<2;++owner) {
        setup(&cpu);scene_owner=owner+1;scene_phase=3;scene_transport_probe=(owner^1u)+1;
        scene_body[4]=1;scene_body[0x5C]=32;life.status[0]=life.status[1]=MMX6_COOP_FALLEN;life.wipe=(uint8_t)(owner+1);
        psx_mod_write_byte(PLAYER+4,3);psx_mod_write_byte(PLAYER+0x5C,0);p2.body[4]=3;p2.body[0x5C]=0;
        stage_call=0;CHECK(stage_tick(&cpu,0x8001E9ECu));
        CHECK(scene_native_retries==1 && psx_mod_read_byte(PLAY+1)==1 && life.wipe==owner+1);
    }
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
        nova_probe=1;controller_frame(&cpu,0);nova_probe=0;
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
        uint32_t zero_x=le32(p2.body+8);controller_frame(&cpu,0);
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
    CPUState cpu;setup(&cpu);marker_override=1;controller_frame(&cpu,0);marker_override=-1;
    for(unsigned tick=0;tick<21;++tick)controller_frame(&cpu,0);
    for(unsigned i=0;i<3;++i)CHECK(!p2.trails[i*0x60+3] && !p2.trails[i*0x60+4]);
    CHECK(!p2.body[0x8C]);
    marker_override=1;controller_frame(&cpu,0);CHECK(p2.trails[3]);marker_override=0;controller_frame(&cpu,0);CHECK(!p2.trails[3]);
    p2.effects[3]=p2.effects[4]=1;p2.effects[0x53]=p2.effects[0x54]=1;p2.body[0x9B]=p2.body[0x9C]=0;controller_frame(&cpu,0);
    CHECK(!p2.effects[3] && !p2.effects[4] && !p2.effects[0x53] && !p2.effects[0x54]);
    for(unsigned gate=0;gate<10;++gate){
        setup(&cpu);if(gate==0)inside=1;else if(gate==1)failed=1;else if(gate==2)scene_owner=1;
        else if(gate==3)psx_mod_write_byte(PLAY+0x10,1);else if(gate==4)psx_mod_write_byte(PLAY+0x1C,1);
        else if(gate==5)life.status[1]=MMX6_COOP_ABSENT;else if(gate==6)life.status[1]=MMX6_COOP_FALLEN;
        else if(gate==7)cpu.gpr[31]=0x80021600;else if(gate==8)psx_mod_write_byte(PLAY+1,2);
        else{life.status[1]=MMX6_COOP_JOINING;p2.body[0x46]=1;}
        controller_frame(&cpu,0);CHECK(!occurrences(0x80020D74) && !occurrences(0x80020DC8));
    }
    for(unsigned departing=0;departing<2;++departing){
        setup(&cpu);life.status[1]=departing?MMX6_COOP_LEAVING:MMX6_COOP_DYING;
        terminal_player=1;p2.trails[3]=p2.trails[4]=1;controller_frame(&cpu,0);
        CHECK(occurrences(0x80020DC8)==1 && life.status[1]==(departing?MMX6_COOP_ABSENT:MMX6_COOP_FALLEN) && !p2.trails[3]);
        controller_frame(&cpu,0);CHECK(occurrences(0x80020DC8)==1);
    }
    setup(&cpu);life.status[0]=MMX6_COOP_FALLEN;psx_mod_write_byte(PLAYER+4,3);stage_driver=1;stage_call=0;marker_override=1;cpu.gpr[4]=PLAY;
    CHECK(stage_tick(&cpu,0x8001E9EC));CHECK(occurrences(0x8001E9EC)==1 && occurrences(0x80020D74)==1 && occurrences(0x80020DC8)==1);
    CHECK(psx_mod_read_word(PLAY+0x90)==1 && !inside && !zero_world && !stage_call && !state_track.count);
}
static void menu_freeze_and_select_resume(void){
    CPUState cpu;setup(&cpu);life.status[1]=MMX6_COOP_ABSENT;pad_buttons=0xFFFE;
    life.select_armed=1;PlayerContext before=p2;
    for(unsigned phase=1;phase<=3;++phase){
        psx_mod_write_byte(PLAY+1,(uint8_t)phase);controller_frame(&cpu,0);
        CHECK(!call_count && life.select_previous && !life.rejoin_pending);
    }
    CHECK(!memcmp(&p2,&before,sizeof p2) && !life.select_frames);
    psx_mod_write_byte(PLAY+1,0);controller_frame(&cpu,0); /* Held UI Select is not a fresh rejoin. */
    CHECK(life.status[1]==MMX6_COOP_ABSENT && !life.rejoin_pending && !call_count);
    pad_buttons=0xFFFF;controller_frame(&cpu,0);CHECK(!life.select_previous && !call_count);
    life.status[1]=MMX6_COOP_ALIVE;controller_frame(&cpu,0); /* Fixture restores eligibility; no join success is claimed. */
    CHECK(occurrences(0x80034DCC)==1 && occurrences(0x8002012C)==1 && occurrences(0x8002F288)==1);
    CHECK(occurrences(0x80020D74)==1 && occurrences(0x80020DC8)==1);
    setup(&cpu);inside=1;psx_mod_write_byte(PLAY+1,2);pad_buttons=0xFFFE;
    controller_frame(&cpu,0);CHECK(!call_count && !life.select_previous); /* Native owned-menu context is already inside. */
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
static void native_X_armor_compressed_frame_and_survivor(void) {
    for(unsigned form=0;form<=4;++form) {
        CPUState cpu;setup(&cpu);
        private_actor.character=MMX6_COOP_CHARACTER_X;private_actor.form=form;
        p2.body[2]=0;p2.body[0xE7]=(uint8_t)form;p2.body[0xDC]=5;
        /* The actual14-tile body stream contains both generic and armor
         * shapes. Poison static/common pixels and shared VRAM so neither
         * can stand in for the native compressed upper tiles. */
        put32(zero_compressed,0x00E00020u);
        zero_compressed[38]=0x7F;zero_compressed[39]=3; /* Native word-LZ repeat895. */
        for(unsigned y=0;y<16;++y)for(unsigned x=0;x<4;++x) {
            test_zero_ui[y*1024+368+x]=0x3333;
            test_vram[y*1024+368+x]=0x2222;
        }
        psx_mod_write_half(active_palette+0x260+2,0x5A31);
        PlayerContext resident;capture_player(&resident);PlayerContext guest_before=p2;
        uint32_t sprites=psx_mod_read_word(SCRATCH+0x1C);
        render(&cpu,0x800232D4u);
        CHECK(draw_count==(form?2u:1u) && occurrences(0x8002619Cu)==!!form);
        CHECK(bank_count==(form?2u:1u) && !failed);
        if(form) {
            CHECK(bank_first[1]==0x5A31 && banks[1].tile==0x00C0);
            CHECK(banks[1].character==MMX6_COOP_CHARACTER_X);
            /* Native same-priority append preserves the base body's tail. */
            CHECK((psx_mod_read_word(packets+PLAYER_PACKET_BYTES+40)&0xFFFFFFu)==
                ((packets+PLAYER_MODE_OFFSET+8)&0xFFFFFFu));
        }
        PlayerContext after;capture_player(&after);
        CHECK(!memcmp(&resident,&after,sizeof resident) && !memcmp(&p2,&guest_before,sizeof p2));
        CHECK(psx_mod_read_word(SCRATCH+0x1C)==sprites && !state_track.count && !state_track.error);
        if(form==2) {
            /* A private-owned native world calls body and armor separately.
             * The armor replacement appends once and restores both cursors. */
            enter_zero();inside=zero_world=1;world_packets=packets;
            psx_mod_write_word(SCRATCH+0x124,0);native_budget=0;draw_count=0;
            cpu.gpr[4]=PLAYER;
            CHECK(render_survivor(&cpu,0x800232D4u));
            CHECK(world_packets==packets+40 && draw_count==1);
            CHECK(render_armor_survivor(&cpu,0x8002619Cu));
            CHECK(world_packets==packets+80 && draw_count==2 && !failed);
            CHECK(psx_mod_read_word(SCRATCH+0x100)==0x800A0000 &&
                  psx_mod_read_word(SCRATCH+0x104)==0x800A8000);
            psx_mod_write_byte(PLAYER+5,1);psx_mod_write_byte(PLAYER+0x47,0x7E);
            CHECK(render_armor_survivor(&cpu,0x8002619Cu));
            CHECK(world_packets==packets+80 && draw_count==2); /* Native beam gate. */
            leave_zero();inside=zero_world=0;
            CHECK(!render_armor_survivor(&cpu,0x8002619Cu));
        }
    }
    CPUState cpu;setup(&cpu);render(&cpu,0x800232D4u);
    CHECK(!occurrences(0x8002619Cu)); /* Ordinary native Zero retains its path. */
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
static void distant_zero_saber_uses_native_owner_visibility(void) {
    CPUState cpu;setup(&cpu);surface_probe=1;independent_views=1;
    const uint32_t actor=0x800950A0u,camera=0x800971F8u;
    put32(p2.body+8,4100u<<16);put32(p2.body+12,411u<<16);
    psx_mod_write_word(camera+8,3488u<<16);psx_mod_write_word(camera+12,224u<<16);
    psx_mod_write_half(camera+0x1C,7360);psx_mod_write_half(camera+0x1E,3488);
    psx_mod_write_half(camera+0x20,224);psx_mod_write_half(camera+0x22,224);
    p2.shots[0]=0x21;p2.shots[1]=24;p2.shots[4]=1;
    put32(p2.shots+8,4100u<<16);put32(p2.shots+12,411u<<16);
    put32(p2.shots+0x3C,le32(p2.body+0x3C));p2.shots[0x41]=p2.body[0x41];
    put32(zero_overlay+0x3704,0xACC20008u);put32(zero_overlay+0x3710,0xACC3000Cu);
    put32(zero_overlay+0x390C,0x24050080u);put32(zero_overlay+0x3910,0x0C00B32Cu);
    put32(zero_overlay+0x3914,0x24060080u);
    inside=1;enter_zero();cpu.gpr[4]=actor;cpu.gpr[5]=cpu.gpr[6]=128;cpu.gpr[31]=0x801ED918u;
    CHECK(guest(&cpu,0x8002CCB0u,actor,128)==1 && !psx_mod_read_byte(actor+3));
    uint8_t before_actor[0xA0],expected_actor[0xA0],before_camera[0x54];
    capture(actor,before_actor,sizeof before_actor);memcpy(expected_actor,before_actor,sizeof expected_actor);expected_actor[3]=1;
    capture(camera,before_camera,sizeof before_camera);CPUState expected=cpu;expected.gpr[2]=0;
    CHECK(amazon_guest_support_visibility(&cpu,0x8002CCB0u));
    CHECK(!memcmp(&cpu,&expected,sizeof cpu) && !memcmp(expected_actor,memory(actor),sizeof expected_actor));
    CHECK(!memcmp(before_camera,memory(camera),sizeof before_camera) && !view_call && !state_track.count);
    for(unsigned bad=0;bad<7;++bad) {
        cpu=expected;cpu.gpr[31]=0x801ED918u;cpu.gpr[4]=actor;
        psx_mod_write_byte(actor+1,24);psx_mod_write_word(actor+0x38,0);psx_mod_write_word(actor+0x3C,le32(p2.body+0x3C));
        psx_mod_write_word(0x801ED910u,0x0C00B32Cu);zero_projected=1;view_call=0;
        if(bad==0)cpu.gpr[31]+=4;
        if(bad==1)cpu.gpr[4]++;
        if(bad==2)psx_mod_write_byte(actor+1,23);
        if(bad==3)psx_mod_write_word(actor+0x38,assets);
        if(bad==4)psx_mod_write_word(actor+0x3C,0x80040000u);
        if(bad==5)psx_mod_write_word(0x801ED910u,0);
        if(bad==6)zero_projected=0;
        expected=cpu;CHECK(!amazon_guest_support_visibility(&cpu,0x8002CCB0u));CHECK(!memcmp(&cpu,&expected,sizeof cpu));
        CHECK(!memcmp(before_camera,memory(camera),sizeof before_camera));
    }
    zero_projected=1;leave_zero();inside=0;
}
static void distant_surface_keeps_original_owner_view_and_retirement(void) {
    CPUState cpu;setup(&cpu);stage_call=0;shared_probe=surface_probe=1;independent_views=1;
    const uint32_t actor=0x80091298u,camera=0x800971F8u,table=0x800F5728u;
    psx_mod_write_word(PLAYER+8,3520u<<16);psx_mod_write_word(PLAYER+12,395u<<16);
    psx_mod_write_byte(PLAYER+0xDF,0x55);
    put32(p2.body+8,3908u<<16);put32(p2.body+12,411u<<16);p2.body[0xDF]=1;
    psx_mod_write_byte(camera+4,1);psx_mod_write_byte(camera+0x44,1);
    psx_mod_write_word(camera+8,3488u<<16);psx_mod_write_word(camera+12,224u<<16);
    psx_mod_write_half(camera+0x30,160);psx_mod_write_half(camera+0x32,160);psx_mod_write_half(camera+0x2C,96);
    psx_mod_write_half(camera+0x1C,7360);psx_mod_write_half(camera+0x1E,3488);
    psx_mod_write_half(camera+0x20,224);psx_mod_write_half(camera+0x22,224);
    psx_mod_write_word(0x80049C98u,0x0C00B2FFu);psx_mod_write_word(0x80049CD4u,0xA24000DFu);
    psx_mod_write_word(0x80049D60u,0x0C00B32Cu);
    inside=1;enter_zero();CHECK(shared_effect_allocate(&cpu,0x8002C398u));leave_zero_context(1);inside=0;
    CHECK(shared_effect_owners[0]==2);
    psx_mod_write_byte(actor,0x41);psx_mod_write_byte(actor+1,3);psx_mod_write_byte(actor+2,9);
    psx_mod_write_word(actor+0x30,0x8007789Cu);psx_mod_write_word(actor+8,3907u<<16);
    psx_mod_write_word(actor+12,424u<<16);psx_mod_write_word(SCRATCH+0x88,table);
    psx_mod_write_word(table+3*4,0x80049A14u);
    /* The exact same original bounds reject this allocation in P1's view. */
    cpu.gpr[4]=actor;cpu.gpr[5]=cpu.gpr[6]=32;
    CHECK(guest(&cpu,0x8002CBFCu,actor,32)==1);
    PlayerContext primary,after;capture_player(&primary);uint8_t view[0x54];capture(camera,view,sizeof view);
    cpu.gpr[31]=0x80020438u;CPUState expected=cpu;expected.gpr[2]=0x309;
    CHECK(shared_effect_callback(&cpu,0x80049A14u));
    CHECK(!memcmp(&cpu,&expected,sizeof cpu) && psx_mod_read_byte(actor+4)==1 && psx_mod_read_byte(actor+3)==1);
    CHECK(p2.body[0xDF]==1 && surface_bounds_calls==3 && surface_ticks==1);
    capture_player(&after);CHECK(!memcmp(&primary,&after,sizeof primary));
    CHECK(!memcmp(view,memory(camera),sizeof view) && !zero_projected && !inside && !shared_fx_call);
    /* Wrong caller, slot, native dispatch and source fail without mutation. */
    cpu.gpr[31]=0x80020434u;expected=cpu;CHECK(!shared_effect_callback(&cpu,0x80049A14u));CHECK(!memcmp(&cpu,&expected,sizeof cpu));
    cpu.gpr[31]=0x80020438u;cpu.gpr[4]=actor+1;expected=cpu;
    CHECK(!shared_effect_callback(&cpu,0x80049A14u));CHECK(!memcmp(&cpu,&expected,sizeof cpu));cpu.gpr[4]=actor;
    psx_mod_write_word(table+12,0x80010000u);CHECK(!shared_effect_callback(&cpu,0x80049A14u));psx_mod_write_word(table+12,0x80049A14u);
    psx_mod_write_word(0x80049C98u,0);CHECK(!shared_effect_callback(&cpu,0x80049A14u));psx_mod_write_word(0x80049C98u,0x0C00B2FFu);
    shared_effect_owners[0]=1;shared_fx_call=1;cpu.gpr[31]=0x80049CA0u;expected=cpu;
    CHECK(!shared_effect_view_bounds(&cpu,0x8002CBFCu));CHECK(!memcmp(&cpu,&expected,sizeof cpu));
    shared_fx_call=0;shared_effect_owners[0]=2;cpu.gpr[31]=0x80020438u;
    surface_end=1;CHECK(shared_effect_callback(&cpu,0x80049A14u));
    CHECK(psx_mod_read_byte(actor+4)==2 && p2.body[0xDF]==0 && psx_mod_read_byte(PLAYER+0xDF)==0x55);
    CHECK(shared_effect_callback(&cpu,0x80049A14u));
    CHECK(!psx_mod_read_byte(actor) && !shared_effect_owners[0] && surface_ticks==3);
    capture_player(&after);CHECK(!memcmp(&primary,&after,sizeof primary));
    CHECK(!memcmp(view,memory(camera),sizeof view) && !state_track.count && !state_track.error && !failed);
}
static void deferred_falcon_flight_tracks_owner_and_body_pixels(void) {
    CPUState cpu;setup(&cpu);shared_probe=1;
    private_actor.character=MMX6_COOP_CHARACTER_X;private_actor.form=MMX6_COOP_FORM_FALCON;
    p2.body[2]=0;p2.body[0xE7]=1;p2.body[5]=0x23;p2.body[0x47]=0x42;
    static uint8_t graphics[0x400];memset(graphics,0,sizeof graphics);
    zero_compressed=graphics;compressed_size=sizeof graphics;
    put32(p2.body+0x38,assets+0x100);put32(graphics+0x100+0x42*4,0x01400280u);
    const uint16_t stream[]={0x6000,0x1111,0x0001,1279,0,0};
    for(unsigned i=0;i<sizeof stream/sizeof *stream;++i){
        graphics[0x380+i*2]=(uint8_t)stream[i];graphics[0x381+i*2]=(uint8_t)(stream[i]>>8);
    }
    psx_mod_write_word(assembly+0x1C,0x400);psx_mod_write_half(active_palette+2*32+2,0x1234);
    memset(test_vram,0xBB,sizeof test_vram);memset(test_zero_ui,0xCC,sizeof test_zero_ui);
    psx_mod_write_byte(PLAYER+2,1); /* Idle Zero must not delete the flyer's jet. */
    psx_mod_write_byte(PLAY+0x38,1);psx_mod_write_byte(PLAY+0x5E,5);
    PlayerContext primary;capture_player(&primary);
    inside=1;enter_zero();CHECK(shared_effect_allocate(&cpu,0x8002C398u));
    const uint32_t actor=0x80091298u,table=0x800F699Cu;
    CHECK(cpu.gpr[2]==actor && shared_effect_owners[0]==2);leave_zero();inside=0;
    psx_mod_write_byte(actor,1);psx_mod_write_byte(actor+1,18);
    psx_mod_write_word(SCRATCH+0x88,table);psx_mod_write_word(table+18*4,0x8004B3A0u);
    cpu.gpr[4]=actor;cpu.gpr[31]=0x80020438u;shared_probe=0;falcon_flight_probe=1;
    CHECK(shared_effect_callback(&cpu,0x8004B3A0u));
    CHECK(cpu.gpr[2]==0x1823 && psx_mod_read_word(actor+8)==400u*65536u);
    CHECK(psx_mod_read_word(actor+0x3C)==assembly+0x400 && !psx_mod_read_word(actor+0x38));
    CHECK(private_falcon_flight_effect(actor));falcon_packet_probe=1;
    CHECK(render_survivor(&cpu,0x800232D4u));
    CHECK(draw_count==1 && bank_count==1 && bank_first[0]==0x1234 && !failed);
    CHECK(banks[0].tile==0x0080 && banks[0].source==assets+0x380);
    PlayerContext after;capture_player(&after);CHECK(!memcmp(&primary,&after,sizeof primary));
    CHECK(psx_mod_read_word(SCRATCH+0x1C)==0x80030100u && !state_track.count && !state_track.error);
    psx_mod_write_word(actor+0x3C,assembly);CHECK(!private_falcon_flight_effect(actor));
    psx_mod_write_word(actor+0x3C,assembly+0x400);
    p2.body[5]=7;CHECK(shared_effect_callback(&cpu,0x8004B3A0u));
    CHECK(!psx_mod_read_byte(actor) && !shared_effect_owners[0] && !private_falcon_flight_effect(actor));
    CHECK(!render_survivor(&cpu,0x800232D4u));clear_banks();
}
static void deferred_X_muzzle_retains_shot_pool_and_counter(void) {
    for(unsigned inverse=0;inverse<2;++inverse)for(unsigned borrowed=0;borrowed<2;++borrowed) {
        CPUState cpu;setup(&cpu);stage_call=0;shared_probe=1;
        Mmx6CoopRosterNative native={(uint8_t)inverse,(uint8_t)(inverse?5:0),
            (uint8_t)inverse,(uint8_t)(inverse?5:0),0};
        Mmx6CoopRoster roster;CHECK(mmx6_coop_roster_resolve(&native,&roster)==MMX6_COOP_ROSTER_OK);
        CHECK(private_roster_bind(&roster));
        psx_mod_write_byte(PLAYER+2,(uint8_t)inverse);
        psx_mod_write_byte(PLAYER+0xE7,(uint8_t)(inverse?5:0));
        psx_mod_write_byte(PLAY+0x38,(uint8_t)inverse);
        psx_mod_write_byte(PLAY+0x5E,(uint8_t)(inverse?5:0));
        p2.body[2]=(uint8_t)(inverse^1u);p2.body[0xE7]=(uint8_t)(inverse?0:5);
        memset(memory(0x800950A0u),0,sizeof p2.shots);memset(p2.shots,0,sizeof p2.shots);
        psx_mod_write_byte(PLAYER+0x98,0);p2.body[0x98]=0;
        const uint32_t actor=0x80091298u,table=0x800F699Cu;
        if(inverse){inside=1;enter_zero();}
        CHECK(shared_effect_allocate(&cpu,0x8002C398u));
        CHECK(shared_effect_owners[0]==inverse+1);
        if(inverse){leave_zero_context(1);inside=0;}
        psx_mod_write_byte(actor,0x21);psx_mod_write_byte(actor+1,2);psx_mod_write_byte(actor+2,0x12);
        psx_mod_write_word(SCRATCH+0x88,table);psx_mod_write_word(table+8,0x80049478u);
        cpu.gpr[31]=0x80020438u;cpu.gpr[4]=actor;
        /* Reject a reused slot, a different dispatch or an unowned effect
         * before any native helper is called. */
        shared_effect_owners[0]=0;CHECK(!shared_effect_callback(&cpu,0x80049478u));
        shared_effect_owners[0]=(uint8_t)(inverse+1);
        cpu.gpr[31]=0x80020434u;CHECK(!shared_effect_callback(&cpu,0x80049478u));cpu.gpr[31]=0x80020438u;
        cpu.gpr[4]=actor+1;CHECK(!shared_effect_callback(&cpu,0x80049478u));cpu.gpr[4]=actor;
        psx_mod_write_byte(actor+1,1);CHECK(!shared_effect_callback(&cpu,0x80049478u));psx_mod_write_byte(actor+1,2);
        psx_mod_write_word(table+8,0x80049100u);CHECK(!shared_effect_callback(&cpu,0x80049478u));
        psx_mod_write_word(table+8,0x80049478u);
        PlayerContext primary,private_before=p2,after;capture_player(&primary);
        if(borrowed){inside=1;enter_zero();zero_world=1;}
        muzzle_probe=1;muzzle_expected_seat=inverse;
        CHECK(shared_effect_callback(&cpu,0x80049478u));
        CHECK(cpu.gpr[2]==0x1234 && muzzle_calls==1 && !shared_effect_owners[0]);
        CHECK((unsigned)!!inside==borrowed && (unsigned)!!zero_projected==borrowed && (unsigned)!!zero_world==borrowed);
        if(borrowed){zero_world=0;leave_zero_context(1);inside=0;}
        capture_player(&after);
        if(inverse) {
            CHECK(!memcmp(&primary,&after,sizeof primary));
            CHECK(p2.body[0x98]==1 && p2.shots[0]==0x21 && p2.shots[1]==0x12 && !le32(p2.shots+0x7C));
            CHECK(le32(p2.shots+8)==le32(p2.body+8) && le32(p2.shots+0x3C)==assembly);
            CHECK(zero_overlay[0x5900]==0x6D && psx_mod_read_word(OVERLAY)==0x11223344u);
        } else {
            CHECK(!memcmp(&private_before,&p2,sizeof p2));
            CHECK(after.body[0x98]==1 && after.shots[0]==0x21 && after.shots[1]==0x12 && !le32(after.shots+0x7C));
            CHECK(le32(after.shots+8)==le32(after.body+8));
            CHECK(psx_mod_read_byte(OVERLAY+0x5900)==0x6D);
        }
        CHECK(!shared_fx_call && !shared_fx_allocate_call && !state_track.count && !state_track.error && !failed);
    }
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
static void private_native_weapon_atlas_retains_zero_source(void){
    for(unsigned kind=33;kind<=34;++kind){
        CPUState cpu;setup(&cpu);const uint32_t actor=0x800950A0u;
        PlayerContext resident,after;capture_player(&resident);
        /* Original DAT85 assembly headers34h/38h select these uncompressed
         * ceiling-ice/rising-flame frames. The native packet has no compressed
         * table; its page0 must retain Zero's pixels instead of X's VRAM. */
        unsigned header=kind==33?0x34u:0x38u;
        uint16_t clut=kind==33?0x7843u:0x7804u;
        unsigned palette_at=kind==33?0x260u:0x80u;
        uint16_t expected=kind==33?0x4321u:0x1234u;
        unsigned index=kind==33?1u:2u;
        psx_mod_write_word(assembly+header,0xCC);
        memset(p2.shots,0,sizeof p2.shots);
        p2.shots[0]=0x21;p2.shots[1]=(uint8_t)kind;p2.shots[3]=1;
        put32(p2.shots+0x3C,assembly+0xCC);
        p2.shots[0x42]=(uint8_t)clut;p2.shots[0x43]=(uint8_t)(clut>>8);
        memset(test_vram,0xBB,sizeof test_vram);
        for(unsigned y=0;y<16;++y)for(unsigned x=0;x<4;++x)
            test_zero_ui[y*1024+x]=(uint16_t)(index*0x1111u);
        psx_mod_write_half(active_palette+palette_at+index*2,expected);
        render_replacement_probe=1;
        render(&cpu,0x800232D4u);
        CHECK(!failed && draw_count==2 && drawn[1]==actor && bank_count==2);
        CHECK(bank_first[1]==expected);
        uint16_t pixels[256*256];
        CHECK(mmx6_pixels_decode(banks[1].pixels,banks[1].pixel_bytes,256*256,pixels));
        for(unsigned y=0;y<16;++y)for(unsigned x=0;x<16;++x)
            CHECK(pixels[y*256+x]==expected);
        CHECK(psx_mod_read_word(packets+40)==((packets+PLAYER_PACKET_BYTES+80)&0xFFFFFFu));
        capture_player(&after);CHECK(!memcmp(&resident,&after,sizeof resident));
        CHECK(!state_track.count && !world_render);
        project_player(&p2);CHECK(zero_native_weapon_effect(actor));
        CHECK(!zero_native_weapon_effect(actor+1) && !zero_native_weapon_effect(0x800964A0u));
        psx_mod_write_byte(actor,0);CHECK(!zero_native_weapon_effect(actor));
        psx_mod_write_byte(actor,0x21);psx_mod_write_byte(actor+1,42);
        CHECK(!zero_native_weapon_effect(actor));psx_mod_write_byte(actor+1,(uint8_t)kind);
        psx_mod_write_word(actor+0x3C,assembly);CHECK(!zero_native_weapon_effect(actor));
        psx_mod_write_word(actor+0x3C,assembly+0xCC);psx_mod_write_word(actor+0x38,assets);
        CHECK(!zero_native_weapon_effect(actor));psx_mod_write_word(actor+0x38,0);
        render_x_death=1;CHECK(!zero_native_weapon_effect(actor));render_x_death=0;
        psx_mod_write_byte(PLAYER+2,0);CHECK(!zero_native_weapon_effect(actor));
        project_player(&resident);
        render_replacement_probe=0;clear_banks();
    }
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
static void native_shared_boss_palette(void) {
    const unsigned routes[]={0,1,2,255};
    for(unsigned r=0;r<sizeof routes/sizeof *routes;++r) {
        CPUState cpu;setup(&cpu);
        uint32_t resident=psx_mod_read_word(SCRATCH+0x28),source=0x80160000u;
        unsigned offset=routes[r]?(routes[r]==1?0x100:0x180):0;
        uint8_t expected[256],baseline[256],private_before[256],actual[256];
        memset(baseline,0x4C,sizeof baseline);memset(private_before,0x9D,sizeof private_before);
        for(unsigned i=0;i<0x280;++i)psx_mod_write_byte(source+i,(uint8_t)(i*13u+r*29u));
        capture(source+offset,expected,sizeof expected);
        project(resident+0xB00,baseline,sizeof baseline);
        project(active_palette+0xB00,private_before,sizeof private_before);
        psx_mod_write_byte(resident+0xAFF,0xA7);psx_mod_write_byte(resident+0xC00,0xB8);
        psx_mod_write_word(SCRATCH+0x30,source);psx_mod_write_byte(PLAY+0x43B,(uint8_t)routes[r]);
        /* The real failure occurs when the guest admits this shared boss
         * after the primary is fallen, with its private palette projected. */
        life.status[0]=MMX6_COOP_FALLEN;psx_mod_write_byte(PLAYER+4,3);psx_mod_write_byte(PLAYER+0x5C,0);
        enter_zero();zero_world=1;
        cpu.gpr[4]=0x58;cpu.gpr[5]=source+offset;cpu.gpr[6]=8;cpu.gpr[31]=0x80052F4Cu;
        CPUState before=cpu;
        shared_palette_load(&cpu,0x8002B3D4u);
        CHECK(!memcmp(&cpu,&before,sizeof cpu));
        capture(resident+0xB00,actual,sizeof actual);CHECK(!memcmp(actual,expected,sizeof actual));
        capture(active_palette+0xB00,actual,sizeof actual);CHECK(!memcmp(actual,private_before,sizeof actual));
        CHECK(psx_mod_read_byte(resident+0xAFF)==0xA7 && psx_mod_read_byte(resident+0xC00)==0xB8);
        CHECK(saved_palette_dirty==0x73);
        /* Native2B3D4 still executes its original private memcpy/dirty
         * contract; leave_zero must retain publication for the shared upload. */
        project(active_palette+0xB00,expected,sizeof expected);psx_mod_write_byte(0x800C4560u,1);
        zero_world=0;leave_zero_context(1);
        CHECK(psx_mod_read_byte(0x800C4560u)==0x73 && !zero_projected && !state_track.count);
        enter_zero();
        for(unsigned bad=0;bad<5;++bad) {
            project(resident+0xB00,baseline,sizeof baseline);saved_palette_dirty=0x72;
            cpu=before;
            if(bad==0)cpu.gpr[31]+=4;
            if(bad==1)cpu.gpr[4]++;
            if(bad==2)cpu.gpr[6]--;
            if(bad==3)cpu.gpr[5]++;
            if(bad==4){psx_mod_write_word(SCRATCH+0x30,0x801FFF80u);cpu.gpr[5]=0x801FFF80u+offset;}
            shared_palette_load(&cpu,0x8002B3D4u);
            capture(resident+0xB00,actual,sizeof actual);CHECK(!memcmp(actual,baseline,sizeof actual));
            CHECK(saved_palette_dirty==0x72);
        }
        leave_zero();
    }
}
static void native_shared_weather_palette(void) {
    const uint32_t callers[]={0x800ED728u,0x800ED804u,0x800ED8D8u};
    for(unsigned c=0;c<sizeof callers/sizeof *callers;++c) {
        CPUState cpu;setup(&cpu);
        uint32_t resident=psx_mod_read_word(SCRATCH+0x28);
        uint8_t expected[32],baseline[32],private_before[32],actual[32];
        memset(baseline,0x4C,sizeof baseline);memset(private_before,0x9D,sizeof private_before);
        for(unsigned i=0;i<sizeof expected;++i)expected[i]=(uint8_t)(i*13u+c*29u);
        project(0x800F6BC4u,expected,sizeof expected);
        project(resident+0xC60,baseline,sizeof baseline);
        project(active_palette+0xC60,private_before,sizeof private_before);
        psx_mod_write_byte(resident+0xC5F,0xA7);psx_mod_write_byte(resident+0xC80,0xB8);
        psx_mod_write_byte(PLAY+12,6);psx_mod_write_byte(PLAY+13,0);
        life.status[0]=MMX6_COOP_FALLEN;psx_mod_write_byte(PLAYER+4,3);psx_mod_write_byte(PLAYER+0x5C,0);
        enter_zero();zero_world=1;
        cpu.gpr[4]=0x63;cpu.gpr[5]=0x800F6BC4u;cpu.gpr[6]=1;cpu.gpr[31]=callers[c];
        CPUState before=cpu;
        shared_palette_load(&cpu,0x8002B3D4u);
        CHECK(!memcmp(&cpu,&before,sizeof cpu));
        capture(resident+0xC60,actual,sizeof actual);CHECK(!memcmp(actual,expected,sizeof actual));
        capture(active_palette+0xC60,actual,sizeof actual);CHECK(!memcmp(actual,private_before,sizeof actual));
        CHECK(psx_mod_read_byte(resident+0xC5F)==0xA7 && psx_mod_read_byte(resident+0xC80)==0xB8);
        CHECK(saved_palette_dirty==0x73);
        /* The original loader still performs its private copy and marks
         * dirty; restoring the resident world must retain publication. */
        project(active_palette+0xC60,expected,sizeof expected);psx_mod_write_byte(0x800C4560u,1);
        zero_world=0;leave_zero_context(1);
        CHECK(psx_mod_read_word(SCRATCH+0x28)==resident && psx_mod_read_byte(0x800C4560u)==0x73);
        CHECK(!zero_projected && !state_track.count);
        capture(resident+0xC60,actual,sizeof actual);CHECK(!memcmp(actual,expected,sizeof actual));
        capture(active_palette+0xC60,actual,sizeof actual);CHECK(!memcmp(actual,expected,sizeof actual));
        enter_zero();
        for(unsigned bad=0;bad<6;++bad) {
            project(resident+0xC60,baseline,sizeof baseline);saved_palette_dirty=0x72;
            psx_mod_write_byte(PLAY+12,6);psx_mod_write_byte(PLAY+13,0);cpu=before;
            if(bad==0)psx_mod_write_byte(PLAY+12,5);
            if(bad==1)psx_mod_write_byte(PLAY+13,1);
            if(bad==2)cpu.gpr[31]+=4;
            if(bad==3)cpu.gpr[4]++;
            if(bad==4)cpu.gpr[5]++;
            if(bad==5)cpu.gpr[6]++;
            shared_palette_load(&cpu,0x8002B3D4u);
            capture(resident+0xC60,actual,sizeof actual);CHECK(!memcmp(actual,baseline,sizeof actual));
            capture(active_palette+0xC60,actual,sizeof actual);CHECK(!memcmp(actual,expected,sizeof actual));
            CHECK(psx_mod_read_byte(resident+0xC5F)==0xA7 && psx_mod_read_byte(resident+0xC80)==0xB8);
            CHECK(saved_palette_dirty==0x72);
        }
        leave_zero();
    }
}
static void native_shared_portrait_palette(void) {
    static const struct { uint32_t caller,slot; unsigned palette; } cases[]={
        {0x80021CC4u,0x1E0u,0}, {0x80021E64u,0x1F0u,2},
        {0x80022950u,0x1E0u,3}, {0x80022950u,0x1F0u,1}
    };
    for(unsigned c=0;c<sizeof cases/sizeof *cases;++c) {
        CPUState cpu;setup(&cpu);
        uint32_t resident=psx_mod_read_word(SCRATCH+0x28),source=0x80160000u;
        unsigned offset=cases[c].slot*32u;
        uint8_t baseline[0x4000],private_before[0x4000],expected[0x4000],actual[0x4000];
        memset(baseline,0x4C,sizeof baseline);memset(private_before,0x9D,sizeof private_before);
        for(unsigned i=0;i<0x800;++i)psx_mod_write_byte(source+i,(uint8_t)(i*13u+(i>>9)*29u));
        memcpy(expected,baseline,sizeof expected);
        capture(source+cases[c].palette*0x200u,expected+offset,512);
        project(resident,baseline,sizeof baseline);project(active_palette,private_before,sizeof private_before);
        psx_mod_write_byte(resident-1,0xA7);psx_mod_write_byte(resident+0x4000,0xB8);
        psx_mod_write_word(SCRATCH+0xA8,source);
        psx_mod_write_half(0x800E33C6u,(uint16_t)(cases[c].palette*0x11u));
        enter_zero();zero_world=1;
        cpu.gpr[4]=cases[c].slot;cpu.gpr[5]=source+cases[c].palette*0x200u;
        cpu.gpr[6]=16;cpu.gpr[31]=cases[c].caller;
        CPUState before=cpu;
        shared_palette_load(&cpu,0x8002B3D4u);
        CHECK(!memcmp(&cpu,&before,sizeof cpu));
        capture(resident,actual,sizeof actual);CHECK(!memcmp(actual,expected,sizeof actual));
        capture(active_palette,actual,sizeof actual);CHECK(!memcmp(actual,private_before,sizeof actual));
        CHECK(saved_palette_dirty==0x73 && psx_mod_read_byte(resident-1)==0xA7 &&
            psx_mod_read_byte(resident+0x4000)==0xB8);
        /* Native2B3D4 still copies exactly once into the projected bank;
         * restoration must leave the correct resident row for17C40. The
         * untouched half proves left510/right511 do not share ownership. */
        project(active_palette+offset,expected+offset,512);psx_mod_write_byte(0x800C4560u,1);
        zero_world=0;leave_zero_context(1);
        CHECK(!zero_projected && !state_track.count && psx_mod_read_word(SCRATCH+0x28)==resident);
        CHECK(psx_mod_read_byte(0x800C4560u)==0x73);
        capture(resident,actual,sizeof actual);CHECK(!memcmp(actual,expected,sizeof actual));
        memcpy(private_before+offset,expected+offset,512);
        capture(active_palette,actual,sizeof actual);CHECK(!memcmp(actual,private_before,sizeof actual));
        enter_zero();
        for(unsigned bad=0;bad<8;++bad) {
            project(resident,baseline,sizeof baseline);saved_palette_dirty=0x72;cpu=before;
            psx_mod_write_word(SCRATCH+0xA8,source);
            psx_mod_write_half(0x800E33C6u,(uint16_t)(cases[c].palette*0x11u));
            uint32_t address=0x8002B3D4u;
            if(bad==0)cpu.gpr[31]+=4;
            if(bad==1)cpu.gpr[4]++;
            if(bad==2)cpu.gpr[6]--;
            if(bad==3)cpu.gpr[5]++;
            if(bad==4)cpu.gpr[5]=source+0x800u;
            if(bad==5)psx_mod_write_word(SCRATCH+0xA8,source+1);
            if(bad==6)psx_mod_write_word(SCRATCH+0xA8,0x801FFA00u);
            if(bad==7)address+=4;
            CPUState denied=cpu;
            shared_palette_load(&cpu,address);
            CHECK(!memcmp(&cpu,&denied,sizeof cpu));
            capture(resident,actual,sizeof actual);CHECK(!memcmp(actual,baseline,sizeof actual));
            CHECK(saved_palette_dirty==0x72);
        }
        leave_zero();
        project(resident,baseline,sizeof baseline);cpu=before;
        shared_palette_load(&cpu,0x8002B3D4u); /* Resident calls remain native. */
        capture(resident,actual,sizeof actual);CHECK(!memcmp(actual,baseline,sizeof actual));
    }
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
        shared_palette_load(&cpu,0x8002B3D4u);
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
            shared_palette_load(&cpu,0x8002B3D4u);
            capture(resident+offset,actual,64);
            CHECK(!memcmp(actual,original,32) && !memcmp(actual+32,speaker,32));
        }
        project(resident+offset,original,64);cpu.gpr[31]=0x80020000u;
        shared_palette_load(&cpu,0x8002B3D4u);
        capture(resident+offset,actual,64);CHECK(!memcmp(actual,original,64));
        cpu.gpr[31]=0x800225D8u;cpu.gpr[6]=2;
        shared_palette_load(&cpu,0x8002B3D4u);
        capture(resident+offset,actual,64);CHECK(!memcmp(actual,original,64));
        cpu.gpr[4]=first;cpu.gpr[5]=0x800E33D8u;cpu.gpr[6]=2;
        cpu.gpr[31]=alternate?0x800221D4u:0x800221BCu;
        shared_palette_load(&cpu,0x8002B3D4u);
        capture(resident+offset,actual,64);CHECK(!memcmp(actual,baseline,64));
        CHECK(psx_mod_read_byte(resident+offset-1)==0xA7 && psx_mod_read_byte(resident+offset+64)==0xB8);
        project(active_palette+offset,baseline,64);leave_zero();
        CHECK(psx_mod_read_byte(0x800C4560u)==0x73 && !zero_projected);
        cpu.gpr[5]=0x8006E408u;cpu.gpr[31]=alternate?0x800219B0u:0x8002199Cu;
        shared_palette_load(&cpu,0x8002B3D4u);
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
    /* A native Zero campaign load precedes new-body initialization. Cached
     * old Zero/P2 resources belong to X/P1 and must not veto or recolor it. */
    psx_mod_write_byte(PLAY+0x0C,0);psx_mod_write_byte(PLAY+0x38,1);
    psx_mod_write_byte(PLAY,8);cpu.gpr[31]=0x80014124u;cpu.gpr[4]=2;
    unsigned old_calls=working_palette_probe_calls;CPUState before_load=cpu;
    CHECK(!working_palette_native_load(&cpu,0x80014F70u) && !failed);
    CHECK(working_palette_probe_calls==old_calls && !memcmp(&cpu,&before_load,sizeof cpu));
    capture(active_palette,now,sizeof now);CHECK(!memcmp(now,preserved,sizeof now));
    psx_mod_write_byte(PLAY,10);
    CHECK(!working_palette_native_load(&cpu,0x80014F70u) && failed);
    failed=0;psx_mod_write_byte(PLAY+0x38,0);cpu.gpr[31]=0x800140F0u;cpu.gpr[4]=1;
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
static void ray_native_upload_coordinates(void) {
    CPUState cpu;setup(&cpu);
    Mmx6CoopRosterNative native={1,5,1,5,0};Mmx6CoopRoster roster;
    CHECK(mmx6_coop_roster_resolve(&native,&roster)==MMX6_COOP_ROSTER_OK);
    CHECK(private_roster_bind(&roster));
    static uint8_t graphics[0x240];memset(graphics,0,sizeof graphics);
    zero_compressed=graphics;compressed_size=sizeof graphics;
    put32(graphics+0x24,0x100);
    for(unsigned i=0;i<26;++i)put32(graphics+0x100+i*4,0x02000068u);
    /* Same compressed stream, ordinary origin0, encountered in either order. */
    put32(graphics+0x40,0x02000128u);
    const uint16_t two_rows[]={0x5800,0x1111,0x0001,1023,0x2222,0x0001,1023,0,0};
    for(unsigned i=0;i<sizeof two_rows/sizeof *two_rows;++i){
        graphics[0x168+i*2]=(uint8_t)two_rows[i];graphics[0x169+i*2]=(uint8_t)(two_rows[i]>>8);
    }
    for(unsigned c=0;c<16;++c)psx_mod_write_half(active_palette+32+c*2,0);
    psx_mod_write_half(active_palette+34,0x1234);psx_mod_write_half(active_palette+36,0x4321);
    const uint32_t table=assets+0x100,alias=assets+0x40;
    uint16_t pixels[256];static uint16_t page[65536];
    /* Sample the actual Ray UV rows32..63, including a late frame alias. */
    uint16_t upper=sprite_bank(table,17,0x7801,0x2000);CHECK(upper);
    CHECK(mmx6_pixels_decode(banks[upper-0x6000].pixels,banks[upper-0x6000].pixel_bytes,256,pixels));
    for(unsigned i=0;i<256;++i)CHECK(pixels[i]==0x1234);
    uint16_t lower=sprite_bank(table,5,0x7801,0x3000);CHECK(lower && lower!=upper);
    CHECK(mmx6_pixels_decode(banks[lower-0x6000].pixels,banks[lower-0x6000].pixel_bytes,256,pixels));
    for(unsigned i=0;i<256;++i)CHECK(pixels[i]==0x4321);
    uint16_t full=sprite_bank(table,25,0x7801,UINT16_MAX);CHECK(full);
    CHECK(mmx6_pixels_decode(banks[full-0x6000].pixels,banks[full-0x6000].pixel_bytes,65536,page));
    for(unsigned y=0;y<256;++y)for(unsigned x=0;x<256;++x)
        CHECK(page[y*256+x]==(y>=32 && y<48?0x1234:y>=48 && y<64?0x4321:0));
    unsigned count=bank_count;
    CHECK(sprite_bank(table,0,0x7801,UINT16_MAX)==full && bank_count==count);
    uint16_t normal=sprite_bank(alias,0,0x7801,UINT16_MAX);CHECK(normal && normal!=full);
    CHECK(mmx6_pixels_decode(banks[normal-0x6000].pixels,banks[normal-0x6000].pixel_bytes,65536,page));
    CHECK(page[0]==0x1234 && page[16*256]==0x4321 && !page[32*256]);
    count=bank_count;
    CHECK(sprite_bank(table,1,0x7801,UINT16_MAX)==full &&
        sprite_bank(alias,0,0x7801,UINT16_MAX)==normal && bank_count==count);
    clear_banks();normal=sprite_bank(alias,0,0x7801,UINT16_MAX);full=sprite_bank(table,0,0x7801,UINT16_MAX);
    CHECK(normal && full && normal!=full);
    CHECK(mmx6_pixels_decode(banks[full-0x6000].pixels,banks[full-0x6000].pixel_bytes,65536,page));
    CHECK(!page[0] && page[32*256]==0x1234 && page[48*256]==0x4321);
    psx_mod_write_half(active_palette+34,0x5678);
    uint16_t changed=sprite_bank(table,0,0x7801,UINT16_MAX);CHECK(changed && changed!=full);
    CHECK(mmx6_pixels_decode(banks[full-0x6000].pixels,banks[full-0x6000].pixel_bytes,65536,page));
    CHECK(page[32*256]==0x1234);
    CHECK(mmx6_pixels_decode(banks[changed-0x6000].pixels,banks[changed-0x6000].pixel_bytes,65536,page));
    CHECK(page[32*256]==0x5678);
    CHECK(!sprite_bank(table,26,0x7801,0x2000));
    CHECK(!sprite_bank(table,0,0x7810,0x2000));
    private_actor=default_private_actor;CHECK(!x_ray_upload_table());
    CHECK(private_roster_bind(&roster));
    put32(graphics+0x100+25*4,0x02000069u);CHECK(!x_ray_upload_table());
    put32(graphics+0x100+25*4,0x02000068u);
    put32(graphics+0x24,UINT32_MAX);CHECK(!x_ray_upload_table());
    put32(graphics+0x24,0x100);clear_banks();compressed_size=0x169;
    CHECK(!sprite_bank(table,0,0x7801,0x2000));
    compressed_size=sizeof graphics;CHECK(sprite_bank(table,0,0x7801,0x2000));
    clear_banks();
}
static void shadow_native_upload_coordinates(void) {
    CPUState cpu;setup(&cpu);
    Mmx6CoopRosterNative native={1,5,1,5,2};Mmx6CoopRoster roster;
    CHECK(mmx6_coop_roster_resolve_partner(&native,MMX6_COOP_FORM_SHADOW,0xF0,&roster)==MMX6_COOP_ROSTER_OK);
    CHECK(private_roster_bind(&roster));
    static uint8_t graphics[0x180];memset(graphics,0,sizeof graphics);
    zero_compressed=graphics;compressed_size=sizeof graphics;
    put32(graphics+8,0x100);
    for(unsigned i=0;i<18;++i)put32(graphics+0x100+i*4,0x01000048u);
    /* Same source with ordinary origin0 exposes a source-only cache hit. */
    put32(graphics+0x40,0x01000108u);
    const uint16_t stream[]={0x6000,0x1111,0x0001,1023,0,0};
    for(unsigned i=0;i<sizeof stream/sizeof *stream;++i){
        graphics[0x148+i*2]=(uint8_t)stream[i];graphics[0x149+i*2]=(uint8_t)(stream[i]>>8);
    }
    psx_mod_write_half(active_palette+0x322,0x1234);
    psx_mod_write_half(active_palette+0x922,0x7654); /* Poison the wrong linear CLUT row. */
    const uint32_t table=assets+0x100,alias=assets+0x40;
    static uint16_t page[65536];uint16_t pixels[256];
    uint16_t normal=sprite_bank(alias,0,0x7849,UINT16_MAX);CHECK(normal);
    CHECK(mmx6_pixels_decode(banks[normal-0x6000].pixels,banks[normal-0x6000].pixel_bytes,65536,page));
    CHECK(page[0]==0x1234 && !page[32*256]);
    /* Original type45 frame8 uses tile6 at native UV(96,32), not row0. */
    uint16_t native_bank=sprite_bank(table,8,0x7849,0x2060);CHECK(native_bank);
    CHECK(mmx6_pixels_decode(banks[native_bank-0x6000].pixels,banks[native_bank-0x6000].pixel_bytes,256,pixels));
    for(unsigned i=0;i<256;++i)CHECK(pixels[i]==0x1234);
    uint16_t full=sprite_bank(table,17,0x7849,UINT16_MAX);CHECK(full && full!=normal);
    CHECK(mmx6_pixels_decode(banks[full-0x6000].pixels,banks[full-0x6000].pixel_bytes,65536,page));
    for(unsigned y=0;y<256;++y)for(unsigned x=0;x<256;++x)
        CHECK(page[y*256+x]==(y>=32 && y<48?0x1234:0));
    unsigned count=bank_count;
    CHECK(sprite_bank(table,0,0x7849,UINT16_MAX)==full && bank_count==count);
    psx_mod_write_half(active_palette+0x322,0x5678);
    uint16_t changed=sprite_bank(table,14,0x7849,0x20A0);CHECK(changed && changed!=native_bank);
    CHECK(mmx6_pixels_decode(banks[changed-0x6000].pixels,banks[changed-0x6000].pixel_bytes,256,pixels));
    for(unsigned i=0;i<256;++i)CHECK(pixels[i]==0x5678);
    CHECK(mmx6_pixels_decode(banks[native_bank-0x6000].pixels,banks[native_bank-0x6000].pixel_bytes,256,pixels));
    for(unsigned i=0;i<256;++i)CHECK(pixels[i]==0x1234);
    CHECK(!sprite_bank(table,18,0x7849,0x2000));
    put32(graphics+0x100+17*4,0x01000049u);CHECK(!x_shadow_upload_table());
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
/* Known original BIN28 type1 contract, not a fabricated second vehicle.
 * The native callback model above still owns every D5/occupied result. */
static const uint32_t alternate_ride_words[][2]={
    {0x80071384u,0x800F01A4u},{0x800F01A4u,0x27BDFFE8u},
    {0x800F2F34u,0x800EBF64u},{0x800F2F38u,0x800EFC54u},
    {0x800EFC54u,0x27BDFFE0u},{0x800F2F58u,0x800EC6B4u},
    {0x800EC6B4u,0x27BDFFD8u},{0x800EC7B0u,0x24422F2Cu},
    {0x800EC804u,0x24050012u},{0x800EC830u,0x24020002u},
    {0x800EC834u,0x24020001u},{0x800EC838u,0xA22200D5u},
    {0x800F2F28u,0x1D0F0300u},{0x800F2F2Cu,0x0A0F1600u},
    {0x800F2588u,0x03011E00u},{0x800F258Cu,0x01620020u}
};
static void ride_binding_setup(CPUState *cpu,unsigned kind,unsigned primary) {
    ride_setup(cpu);ride_primary_character=primary;
    Mmx6CoopRosterNative native={(uint8_t)primary,(uint8_t)(primary?5:0),
        (uint8_t)primary,(uint8_t)(primary?5:0),0};
    Mmx6CoopRoster roster;CHECK(mmx6_coop_roster_resolve(&native,&roster)==MMX6_COOP_ROSTER_OK);
    CHECK(private_roster_bind(&roster));
    psx_mod_write_byte(PLAYER+2,(uint8_t)primary);psx_mod_write_byte(PLAYER+0xE7,(uint8_t)(primary?5:0));
    psx_mod_write_byte(PLAY+0x38,(uint8_t)primary);psx_mod_write_byte(PLAY+0x5E,(uint8_t)(primary?5:0));
    p2.body[2]=private_actor.character;p2.body[0xE7]=private_actor.form;
    psx_mod_write_byte(RIDE+0x5C,32);
    if(kind==RIDE_ALTERNATE) {
        psx_mod_write_byte(PLAY+12,20);psx_mod_write_byte(PLAY+13,1);psx_mod_write_byte(RIDE+1,1);
        psx_mod_write_word(RIDE+0x10,0x800F2588u);psx_mod_write_word(RIDE+0x68,0x800F2F28u);
        psx_mod_write_byte(RIDE+0x70,0);psx_mod_write_byte(RIDE+0x71,0);psx_mod_write_byte(RIDE+0xA8,8);
        for(unsigned i=0;i<sizeof alternate_ride_words/sizeof alternate_ride_words[0];++i)
            psx_mod_write_word(alternate_ride_words[i][0],alternate_ride_words[i][1]);
        psx_mod_write_byte(0x800F2588u,0x81); /* Actual native allocated record. */
    }
    CHECK(ride_source()==(int)kind);
}
static void native_both_ride_bindings_and_rosters(void) {
    CPUState cpu;
    for(unsigned kind=RIDE_RECYCLE;kind<=RIDE_ALTERNATE;++kind)for(unsigned primary=0;primary<2;++primary) {
        ride_binding_setup(&cpu,kind,primary);ride_overlap=2;
        PlayerContext before,after;capture_player(&before);uint8_t input[6],restored[6];capture(0x800C456C,input,6);
        uint32_t box=psx_mod_read_word(RIDE+0x68);
        CHECK(ride_tick(&cpu,0x80020A08u) && ride_ticks==1 && ride_seat==1 && ride_character==(primary^1u));
        capture_player(&after);capture(0x800C456C,restored,6);
        CHECK(!memcmp(&before,&after,sizeof before) && !memcmp(input,restored,6));
        CHECK(p2.body[0xD5]==1 && !psx_mod_read_byte(PLAYER+0xD5) && psx_mod_read_word(RIDE+0x68)==box);
        CHECK(!previous_input && !ride_call && !state_track.count && !zero_projected);
        p2.body[0xD5]=255;p2.body[5]=0x12;
        psx_mod_write_word(RIDE+8,32u<<16);psx_mod_write_word(RIDE+12,352u<<16);ride_sync_rider();
        CHECK(le32(p2.body+8)==(32u<<16) && le32(p2.body+12)==(352u<<16) && ride_owner()==1 && ride_ticks==1);
        ride_binding_setup(&cpu,kind,primary);ride_overlap=3;
        CHECK(ride_tick(&cpu,0x80020A08u) && ride_seat==0 && ride_character==primary);
        CHECK(psx_mod_read_byte(PLAYER+0xD5)==1 && !p2.body[0xD5]);
        ride_binding_setup(&cpu,kind,primary);p2.body[0xD5]=254;ride_overlap=2;
        CHECK(ride_owner()==RIDE_NONE && ride_tick(&cpu,0x80020A08u) && !psx_mod_read_byte(PLAYER+0xD5) && p2.body[0xD5]==254);
        /* Each binding uses its original native ground field. Unrelated
         * contact bytes cannot admit an airborne first-slot vehicle. */
        ride_binding_setup(&cpu,kind,primary);ride_overlap=2;
        psx_mod_write_byte(RIDE+(kind==RIDE_ALTERNATE?0xA8:0x70),0);
        psx_mod_write_byte(RIDE+(kind==RIDE_ALTERNATE?0x70:0xA8),8);
        CHECK(!ride_entry(&cpu,1) && !call_count);
        ride_binding_setup(&cpu,kind,primary);psx_mod_write_byte(PLAYER+0xD5,255);
        psx_mod_write_byte(PLAYER+5,0x12);psx_mod_write_byte(PLAYER+0x67,1);psx_mod_write_byte(RIDE+0x97,0x40);
        CHECK(safe_join_landing());psx_mod_write_byte(RIDE+(kind==RIDE_ALTERNATE?0xA8:0x70),0);
        CHECK(!safe_join_landing());
    }
    for(unsigned i=0;i<sizeof alternate_ride_words/sizeof alternate_ride_words[0];++i) {
        ride_binding_setup(&cpu,RIDE_ALTERNATE,0);
        uint32_t at=alternate_ride_words[i][0],mask=at==0x800F2588u?2u:1u;
        psx_mod_write_word(at,psx_mod_read_word(at)^mask);
        CHECK(!ride_source() && !ride_tick(&cpu,0x80020A08u) && !call_count && !failed);
    }
    const uint8_t known_flags[]={0,1,0x81},unknown_flags[]={2,0x80,0x82,0x83,0xFF};
    for(unsigned i=0;i<sizeof known_flags;++i) {
        ride_binding_setup(&cpu,RIDE_ALTERNATE,1);psx_mod_write_byte(0x800F2588u,known_flags[i]);
        CHECK(ride_source()==RIDE_ALTERNATE);
    }
    for(unsigned i=0;i<sizeof unknown_flags;++i) {
        ride_binding_setup(&cpu,RIDE_ALTERNATE,1);psx_mod_write_byte(0x800F2588u,unknown_flags[i]);
        CHECK(!ride_source() && !ride_tick(&cpu,0x80020A08u) && !call_count && !failed);
    }
    ride_binding_setup(&cpu,RIDE_ALTERNATE,0);psx_mod_write_byte(PLAY+13,0);
    CHECK(!ride_tick(&cpu,0x80020A08u) && !call_count);
    ride_binding_setup(&cpu,RIDE_ALTERNATE,0);psx_mod_write_word(RIDE+0x10,0x800F2590u);
    CHECK(!ride_tick(&cpu,0x80020A08u) && !call_count);
    ride_binding_setup(&cpu,RIDE_ALTERNATE,0);psx_mod_write_byte(RIDE+1,0);
    CHECK(!ride_tick(&cpu,0x80020A08u) && !call_count);ride_probe=0;
}
static void withdrawn_ride_setup(CPUState *cpu,unsigned passenger) {
    ride_binding_setup(cpu,RIDE_ALTERNATE,0);
    uint8_t rider[0x158],owner[0x158];
    ride_body(passenger,rider);ride_body(passenger^1u,owner);
    rider[4]=rider[3]=1;rider[5]=0x12;rider[0xD5]=255;rider[0x67]=1;
    put32(rider+0x68,0);put32(rider+8,3121u<<16);put32(rider+12,384u<<16);
    memcpy(scene_body,rider,sizeof rider);
    rider[4]=3;rider[3]=0;rider[5]=0;put32(rider+12,152u<<16);
    owner[4]=owner[3]=1;owner[5]=2;owner[0xD5]=owner[0x67]=0;owner[0x70]=8;
    owner[0xD0]=owner[0xD4]=owner[0x7A]=0;owner[0x14]=rider[0x14]=0;
    put32(owner+8,(3232u<<16)+0x6800u);put32(owner+12,(passenger?395u:394u)<<16);
    put32(owner+0x68,passenger?0x80073D50u:0x80073D54u);
    psx_mod_write_word(0x80073D50u,0x130B0200u);psx_mod_write_word(0x80073D54u,0x130B0300u);
    if(passenger) {memcpy(p2.body,rider,sizeof rider);project(PLAYER,owner,sizeof owner);}
    else {project(PLAYER,rider,sizeof rider);memcpy(p2.body,owner,sizeof owner);}
    for(unsigned off=8;off<=0x18;off+=0x10) {
        psx_mod_write_word(RIDE+off,3121u<<16);psx_mod_write_word(RIDE+off+4,384u<<16);
    }
    psx_mod_write_byte(RIDE+0x97,0x40);psx_mod_write_byte(RIDE+0xA8,9);
    psx_mod_write_byte(RIDE+0x14,0);psx_mod_write_half(RIDE+0xA4,0);
    psx_mod_write_half(0x80097202u,3168);psx_mod_write_half(0x80097206u,232);
    scene_owner=(passenger^1u)+1;scene_phase=3;stage_call=0;
    CHECK(ride_owner()==passenger && ride_scene_withdrawn(passenger));
}
static void native_withdrawn_vehicle_scene_transport(void) {
    CPUState cpu;
    for(unsigned passenger=0;passenger<2;++passenger) {
        withdrawn_ride_setup(&cpu,passenger);ride_camera_fatal=1;
        uint8_t before[0xB0],after[0xB0];capture(RIDE,before,sizeof before);
        PlayerContext primary,partner=p2;capture_player(&primary);
        CHECK(ride_tick(&cpu,0x80020A08u) && !ride_ticks && !ride_call && !state_track.count);
        capture(RIDE,after,sizeof after);CHECK(!memcmp(before,after,sizeof before));
        PlayerContext unchanged;capture_player(&unchanged);CHECK(!memcmp(&primary,&unchanged,sizeof primary) && !memcmp(&partner,&p2,sizeof p2));
        /* Real incoming placement uses the grounded owner's full footbox,
         * not the withdrawn mounted body's zero box or camera position. */
        scene_transport_probe=passenger+1;cpu.gpr[6]=0xA2A2A2A2u;
        scene_tick(&cpu);CHECK(scene_phase==4 && ride_query_calls && cpu.gpr[6]==0xA2A2A2A2u);
        for(unsigned off=8;off<=0x18;off+=0x10) {
            put32(before+off,(3232u<<16)+0x6800u);put32(before+off+4,384u<<16);
        }
        capture(RIDE,after,sizeof after);CHECK(!memcmp(before,after,sizeof before));
        /* Hurt/airborne owner AFTER the grounded placement cannot move or
         * strand the retained vehicle; the already-earned beam finishes. */
        if(passenger) {psx_mod_write_byte(PLAYER+5,17);psx_mod_write_byte(PLAYER+0x67,1);psx_mod_write_byte(PLAYER+0x70,0);psx_mod_write_byte(PLAYER+0x5C,12);}
        else {p2.body[5]=17;p2.body[0x67]=1;p2.body[0x70]=0;p2.body[0x5C]=12;}
        for(unsigned n=0;n<40 && scene_owner;++n) {
            /* Real shared-solid follow runs between beam updates in the
             * opposite actor's native world. Action18 alone cannot authorize
             * it: resetting incomingY to384 repeatedly stalls at392<394. */
            uint8_t beam_before[0x158],beam_after[0x158];ride_body(passenger,beam_before);
            if(!passenger) {enter_zero();zero_world=inside=1;ride_sync_rider();zero_world=0;leave_zero_context(1);inside=0;}
            else ride_sync_rider();
            ride_body(passenger,beam_after);CHECK(!memcmp(beam_before,beam_after,sizeof beam_before));
            scene_tick(&cpu);
        }
        CHECK(!scene_owner && !scene_phase && ride_reboards==1 && !failed && !state_track.count && !state_track.error);
        uint8_t rider[0x158];ride_body(passenger,rider);
        CHECK(rider[4]==1 && rider[5]==0x12 && rider[0xD5]==255 && rider[0x5C]==32 && !le32(rider+0x68));
        CHECK(le32(rider+8)==psx_mod_read_word(RIDE+8) && le32(rider+12)==psx_mod_read_word(RIDE+12));
        capture(RIDE,after,sizeof after);CHECK(!memcmp(before,after,sizeof before));
        scene_transport_probe=0;
        CHECK(ride_tick(&cpu,0x80020A08u) && ride_ticks==1 && psx_mod_read_byte(RIDE)==0x41 && psx_mod_read_byte(RIDE+0x5C)==32);
        /* Outside co-op withdrawal the same original wall/camera fatal
         * policy must execute, including its native HP/retirement result. */
        withdrawn_ride_setup(&cpu,passenger);scene_owner=scene_phase=0;ride_camera_fatal=1;
        if(passenger) {p2.body[4]=p2.body[3]=1;p2.body[5]=0x12;put32(p2.body+12,384u<<16);}
        else {psx_mod_write_byte(PLAYER+4,1);psx_mod_write_byte(PLAYER+3,1);psx_mod_write_byte(PLAYER+5,0x12);psx_mod_write_word(PLAYER+12,384u<<16);}
        CHECK(ride_tick(&cpu,0x80020A08u) && ride_ticks==1 && !psx_mod_read_byte(RIDE) && psx_mod_read_byte(RIDE+0x5C)==128);
    }
    for(unsigned bad=0;bad<6;++bad) {
        withdrawn_ride_setup(&cpu,0);
        if(bad==0)psx_mod_write_byte(RIDE+0x5C,0);
        if(bad==1)psx_mod_write_byte(RIDE+0x5C,128);
        if(bad==2)psx_mod_write_byte(RIDE+0x97,0xC0);
        if(bad==3)psx_mod_write_byte(RIDE+0x91,1);
        if(bad==4)psx_mod_write_byte(RIDE+0x92,1);
        if(bad==5)psx_mod_write_half(RIDE+0xA4,0x400);
        CHECK(!ride_scene_withdrawn(0));
        CHECK(ride_tick(&cpu,0x80020A08u) && ride_ticks==1); /* Native unhealthy/fuse path never intercepted. */
    }
    for(unsigned bad=0;bad<4;++bad) {
        withdrawn_ride_setup(&cpu,0);uint8_t before[0xB0],after[0xB0];capture(RIDE,before,sizeof before);
        scene_transport_probe=1;
        if(bad==0)p2.body[0x67]=1; /* Wait for actual landing, never invent it. */
        if(bad==1)put32(p2.body+0x68,0);
        if(bad==2)ride_query_bad=1; /* Vehicle head clearance blocked. */
        if(bad==3)ride_query_bad=2; /* Owner foot fits but wider vehicle lacks support. */
        scene_tick(&cpu);capture(RIDE,after,sizeof after);
        CHECK(scene_phase==3 && !memcmp(before,after,sizeof before) && !ride_reboards && !state_track.count && !state_track.error);
    }
    withdrawn_ride_setup(&cpu,0);scene_body[5]=2;scene_body[0xD5]=0;
    uint8_t owner[0x158],before[0xB0],after[0xB0];memcpy(owner,p2.body,sizeof owner);capture(RIDE,before,sizeof before);
    CHECK(!ride_scene_withdrawn(0) && ride_scene_place(&cpu,0,owner));
    capture(RIDE,after,sizeof after);CHECK(!memcmp(before,after,sizeof before) && !ride_query_calls);
    ride_probe=scene_transport_probe=0;
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
static void shared_clear_recycle_setup(CPUState *cpu) {
    shared_clear_setup(cpu);uint32_t boss=psx_mod_read_word(PLAY+0x20);
    psx_mod_write_byte(PLAY+12,4);psx_mod_write_byte(PLAY+13,1);
    psx_mod_write_byte(boss+1,56);psx_mod_write_word(boss+0x10,0x800F7E48u);
    cpu->gpr[31]=0x800F430Cu;
    psx_mod_write_word(0x800F4300u,0x24040014u);
    psx_mod_write_word(0x800F4304u,0x0C00F4C2u);
    psx_mod_write_word(0x800F4308u,0xA06000CAu);
}
static void sigma_hold_setup(CPUState *cpu,unsigned later) {
    setup(cpu);stage_call=0;
    psx_mod_write_byte(PLAYER+0xD0,0);psx_mod_write_byte(PLAYER+0xD4,0);
    psx_mod_write_byte(PLAYER+0x7A,0);
    const uint32_t actor=0x8008EF48u;
    const uint32_t guards[][2]={
        {0x800F5920u,0x800EDE18u},{0x800F5924u,0x800F2154u},
        {0x800F6674u,0x800EDE88u},{0x800F6E18u,0x800EFC90u},
        {0x800EDECCu,0x00808021u},{0x800EDEECu,0x90650015u},
        {0x800EDEF0u,0x24040014u},{0x800EDEF4u,0x0C00F4C2u},
        {0x800EDEF8u,0xA06000CAu},{0x800EFCA4u,0x00808821u},
        {0x800EFDB4u,0xA2220004u},{0x800EFDDCu,0xA2320005u},
        {0x800EFDF0u,0x92650015u},{0x800EFDF4u,0x0C00F4C2u},
        {0x800EFDF8u,0x24040014u}};
    for(unsigned i=0;i<sizeof guards/sizeof guards[0];++i)
        psx_mod_write_word(guards[i][0],guards[i][1]);
    psx_mod_write_byte(PLAY+12,12);psx_mod_write_byte(PLAY+13,1);
    psx_mod_write_word(PLAY+0x20,later?0:actor);
    psx_mod_write_byte(actor,0x41);psx_mod_write_byte(actor+1,(uint8_t)(later?62:61));
    psx_mod_write_byte(actor+4,(uint8_t)(later?1:2));
    psx_mod_write_byte(actor+5,(uint8_t)(later?2:0));
    psx_mod_write_word(actor+0x10,later?0u:0x800F57ECu);
    cpu->gpr[31]=later?0x800EFDFCu:0x800EDEFCu;
    cpu->gpr[later?17:16]=actor;cpu->gpr[4]=20;
}
static void native_sigma_transition_retains_living_pair(void) {
    CPUState cpu;
    for(unsigned later=0;later<2;++later) {
        for(unsigned negative=0;negative<34;++negative) {
            sigma_hold_setup(&cpu,later);const uint32_t actor=0x8008EF48u;
            if(negative==0)cpu.gpr[31]=later?0x800F21F4u:0x800ECDCCu;
            if(negative==1)cpu.gpr[4]=19;
            if(negative==2)psx_mod_write_byte(PLAY+12,11);
            if(negative==3)psx_mod_write_byte(PLAY+13,0);
            if(negative==4)cpu.gpr[later?17:16]=actor+4;
            if(negative==5)psx_mod_write_byte(actor,0);
            if(negative==6)psx_mod_write_byte(actor+1,(uint8_t)(later?61:62));
            if(negative==7)psx_mod_write_byte(actor+2,1);
            if(negative==8)psx_mod_write_byte(actor+4,(uint8_t)(later?0:1));
            if(negative==9)psx_mod_write_byte(actor+5,3);
            if(negative==10)psx_mod_write_byte(actor+0x5C,1);
            if(negative==11)psx_mod_write_word(actor+0x10,0x800F57E4u);
            if(negative==12)ready=0;
            if(negative==13)enrolled=0;
            if(negative==14)failed=1;
            if(negative==15)scene_call=1;
            if(negative==16)zero_projected=1;
            if(negative==17)private_draw=1;
            if(negative==18)world_render=1;
            if(negative==19)pause_owner=0;
            if(negative==20)life.status[0]=MMX6_COOP_FALLEN;
            if(negative==21)life.status[1]=MMX6_COOP_ABSENT;
            if(negative==22)psx_mod_write_byte(PLAYER+0x5C,0);
            if(negative==23)p2.body[0x5C]=0;
            if(negative==24)psx_mod_write_byte(PLAYER+3,0);
            if(negative==25)p2.body[3]=0;
            if(negative==26)psx_mod_write_word(0x800F5920u,0);
            if(negative==27)psx_mod_write_word(0x800F5924u,0);
            if(negative==28)psx_mod_write_word(0x800F6674u,0);
            if(negative==29)psx_mod_write_word(0x800F6E18u,0);
            if(negative==30)psx_mod_write_word(later?0x800EFCA4u:0x800EDECCu,0);
            if(negative==31)psx_mod_write_word(later?0x800EFDF4u:0x800EDEF4u,0);
            if(negative==32)psx_mod_write_word(later?0x800EFDF8u:0x800EDEF8u,0);
            if(negative==33)scene_owner=1;
            CHECK(!sigma_transition_in_place(&cpu,0x8003D308u));
            CHECK(!call_count && !clear_phase);
            private_draw=0;
        }
        sigma_hold_setup(&cpu,later);
        CHECK(!sigma_transition_in_place(&cpu,0x8003D330u));
        CHECK(sigma_transition_in_place(&cpu,0x8003D308u));
        CPUState saved_cpu=cpu;PlayerContext saved_guest=p2;uint8_t owner[sizeof p2.body];
        capture(PLAYER,owner,sizeof owner);
        script_begin(&cpu,0x8003D308u);
        CHECK(scene_owner==1 && !scene_phase && !clear_phase && !call_count);
        CHECK(!memcmp(&cpu,&saved_cpu,sizeof cpu) && !memcmp(&p2,&saved_guest,sizeof p2));
        uint8_t after[sizeof owner];capture(PLAYER,after,sizeof after);
        CHECK(!memcmp(after,owner,sizeof owner));
        /* Original command's shared lock is external to this callback.
         * Hold it over multiple world ticks, then let native release win. */
        psx_mod_write_byte(PLAY+0x1C,1);
        for(unsigned frame=0;frame<8;++frame) {
            scene_tick(&cpu);
            CHECK(scene_owner==1 && !scene_phase && !call_count && !failed);
            CHECK(!memcmp(&p2,&saved_guest,sizeof p2));
        }
        script_begin(&cpu,0x8003D308u); /* A chained command keeps phase0. */
        CHECK(scene_owner==1 && !scene_phase && !call_count);
        psx_mod_write_byte(PLAY+0x1C,0);scene_tick(&cpu);
        CHECK(!scene_owner && !scene_phase && !call_count && !failed);
        CHECK(!memcmp(&p2,&saved_guest,sizeof p2) && !state_track.count);
    }
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
    shared_clear_recycle_setup(&cpu);cpu.gpr[31]=0x80050290u;
    script_begin(&cpu,0x8003D308u);CHECK(scene_owner==1 && scene_phase==1 && !clear_phase);
    for(unsigned negative=0;negative<26;++negative) {
        shared_clear_recycle_setup(&cpu);uint32_t boss=psx_mod_read_word(PLAY+0x20);
        if(negative==0)cpu.gpr[31]=0x800F5544u;
        if(negative==1)cpu.gpr[4]=19;
        if(negative==2)psx_mod_write_byte(PLAY+12,1);
        if(negative==3)psx_mod_write_byte(PLAY+13,0);
        if(negative==4)psx_mod_write_byte(boss+1,49);
        if(negative==5)psx_mod_write_byte(boss+2,1);
        if(negative==6)psx_mod_write_byte(boss+4,1);
        if(negative==7)psx_mod_write_byte(boss+0x5C,1);
        if(negative==8)psx_mod_write_word(boss+0x10,0x800F7E50u);
        if(negative==9)psx_mod_write_byte(boss,0);
        if(negative==10)life.status[1]=MMX6_COOP_ABSENT;
        if(negative==11)life.status[0]=MMX6_COOP_FALLEN;
        if(negative==12)psx_mod_write_byte(PLAYER+0x5C,0);
        if(negative==13)p2.body[0x5C]=0;
        if(negative==14)psx_mod_write_word(0x800F4300u,0x24040013u);
        if(negative==15)psx_mod_write_word(0x800F4304u,0x0C00F4CCu);
        if(negative==16)psx_mod_write_word(0x800F4308u,0xA06000CBu);
        if(negative==17)scene_owner=1;
        if(negative==18)scene_call=1;
        if(negative==19)enrolled=0;
        if(negative==20)ready=0;
        if(negative==21)failed=1;
        if(negative==22)psx_mod_write_byte(PLAY,9);
        if(negative==23)psx_mod_write_byte(PLAY+1,1);
        if(negative==24)psx_mod_write_word(PLAY+0x20,boss+1);
        CHECK(!shared_clear_admit(&cpu,negative==25?0x8003D330u:0x8003D308u));
        CHECK(!clear_phase && !clear_members && !clear_started && !call_count);
    }
    for(unsigned recycle=0;recycle<2;++recycle)for(unsigned projected=0;projected<2;++projected) {
        if(recycle)shared_clear_recycle_setup(&cpu);else shared_clear_setup(&cpu);
        if(projected)enter_zero();
        script_begin(&cpu,0x8003D308u);
        CHECK(clear_phase==CLEAR_ADMITTED && clear_members==3 && !clear_started && !scene_owner);
        if(projected)leave_zero();
        shared_clear_tick(&cpu,0);CHECK(clear_phase==CLEAR_PRELUDE && !call_count);
        /* Both bodies stay visible until the original reward sets clear10. */
        CHECK(psx_mod_read_byte(PLAYER+3)==1 && p2.body[3]==1);
        clear_probe=1;clear_pose_limit[0]=projected?6:2;clear_pose_limit[1]=projected?2:6;
        clear_air_seat=projected?0:1;clear_air_limit=6;
        p2.body[5]=clear_air_seat==1?6:2;
        cpu.gpr[4]=PLAY;
        psx_mod_write_byte(PLAYER+5,clear_air_seat==0?6:20);psx_mod_write_byte(PLAYER+0x7A,1);
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
    psx_mod_write_word(0x80073D50u,0x160B0000u);psx_mod_write_word(0x80073D54u,0x160C0000u);
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
        /* Native camera equality alone is insufficient until both full boxes clear. */
        CHECK(door_update(&cpu,0x80050DFCu) && psx_mod_read_byte(TEST_DOOR+5)==3);
        psx_mod_write_word(PLAYER+8,550u<<16);put32(p2.body+8,552u<<16);
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
static void native_hatch_missing_box_clearance(void) {
    for(unsigned inverse=0;inverse<2;++inverse)for(unsigned negative=0;negative<2;++negative)
    for(unsigned corpse=0;corpse<2;++corpse) {
        CPUState cpu;door_setup(&cpu,1,480,480);
        if(inverse) {psx_mod_write_byte(PLAYER+2,1);psx_mod_write_byte(PLAYER+0x8E,0);p2.body[2]=0;}
        check_door_result(&cpu,1,0);
        CHECK(both_door_extents[0][0]<0 && both_door_extents[1][1]>0);
        psx_mod_write_byte(TEST_DOOR+5,3);
        uint32_t velocity=negative?0xFFFF5C00u:0xA400u;
        psx_mod_write_word(TEST_DOOR+0x84,velocity);
        psx_mod_write_word(PLAYER+8,(negative?450u:550u)<<16);put32(p2.body+8,500u<<16);
        psx_mod_write_word(PLAYER+0x68,0);put32(p2.body+0x68,0);
        psx_mod_write_byte(PLAYER+0xD4,0xFE);p2.body[0xD4]=0xFE;
        psx_mod_write_half(0x80097202u,200);psx_mod_write_half(0x8009721Eu,200);
        uint32_t x=psx_mod_read_word(PLAYER+8),z=le32(p2.body+8),camera=psx_mod_read_word(0x80097202u),draws=door_draws;
        CHECK(door_update(&cpu,0x80050DFCu));
        CHECK(psx_mod_read_byte(TEST_DOOR+5)==3 && psx_mod_read_word(PLAYER+8)==x+velocity && le32(p2.body+8)==z+velocity);
        CHECK(!psx_mod_read_word(PLAYER+0x68) && !le32(p2.body+0x68) && p2.body[0x5C]==32 && psx_mod_read_byte(PLAYER+0x5C)==32);
        CHECK(door_draws==draws+1 && psx_mod_read_word(0x80097202u)==camera && !psx_mod_read_word(PLAY+0x90));
        if(corpse) {life.status[1]=MMX6_COOP_FALLEN;p2.body[4]=3;p2.body[0x5C]=0;}
        else put32(p2.body+8,(negative?448u:552u)<<16);
        CHECK(door_update(&cpu,0x80050DFCu));
        CHECK(psx_mod_read_byte(TEST_DOOR+5)==4 && psx_mod_read_word(PLAY+0x90)==1 && door_draws==draws+2);
        CHECK(!psx_mod_read_byte(PLAYER+0xD4));
        if(corpse)CHECK(life.status[1]==MMX6_COOP_FALLEN && p2.body[0x5C]==0);
        else CHECK(!p2.body[0xD4] && p2.body[0x5C]==32);
    }
}
static void arrival_setup(CPUState *cpu) {
    setup(cpu);enrolled=0;paired_arrival_fixture_probe=1;
    psx_mod_write_byte(PLAY+0x1D,2); /* Ordinary original CP2; no opening HELP. */
    psx_mod_write_byte(PLAY+0x5E,1);psx_mod_write_byte(PLAY+0x1C,1);
    for(unsigned i=0x0F;i<=0x1B;++i)psx_mod_write_byte(PLAY+i,0);
    psx_mod_write_byte(PLAYER+5,0);psx_mod_write_byte(PLAYER+6,0);
    psx_mod_write_byte(PLAYER+0xE7,0); /* Original parts have not landed. */
    psx_mod_write_byte(PLAYER+0xCE,3);
    psx_mod_write_byte(PLAYER+0x67,255);psx_mod_write_word(PLAYER+0x24,0xFFF80000u);
    const unsigned fields[]={0xD0,0xD4,0xD5,0xE0};
    for(unsigned i=0;i<4;++i)psx_mod_write_byte(PLAYER+fields[i],0);
    psx_mod_write_word(PLAYER+0x68,0x80073D50u);
    for(unsigned box=0;box<2;++box){psx_mod_write_byte(0x80073D50u+box*4,0);psx_mod_write_byte(0x80073D52u+box*4,10);}
    psx_mod_write_word(0x80073ACCu,0x80035144u);
    psx_mod_write_word(0x8003D850u,0x27BDFFE8u);psx_mod_write_word(0x8003D860u,0x0C00EE81u);
    psx_mod_write_word(0x8003D880u,0xAE020024u);psx_mod_write_word(0x800351B4u,0x0C00EE81u);
    psx_mod_write_word(0x8003D730u,0x90C4005Eu);psx_mod_write_word(0x8003D73Cu,0xA0A400E7u);
    psx_mod_write_word(0x8003525Cu,0x0C00EB46u);
}
static void native_paired_arrival_barrier(void) {
    CPUState cpu;
    for(unsigned first=0;first<2;++first) {
        arrival_setup(&cpu);
        uint32_t x=psx_mod_read_word(PLAYER+8),y=psx_mod_read_word(PLAYER+12);
        uint32_t camera=psx_mod_read_word(0x80097202u),clock=psx_mod_read_word(PLAY+0x90);
        CHECK(paired_arrival(&cpu) && arrival_pair && enrolled && arrival_births==1);
        CHECK(life.status[1]==MMX6_COOP_JOINING && !join_phase && p2.body[5]==0 && p2.body[0xCE]==3);
        CHECK(psx_mod_read_word(PLAYER+8)==x && psx_mod_read_word(PLAYER+12)==y &&
              le32(p2.body+8)==x+(24u<<16) && le32(p2.body+12)==y);
        CHECK(psx_mod_read_byte(PLAY+0x1C)==1 && psx_mod_read_word(0x80097202u)==camera &&
              psx_mod_read_word(PLAY+0x90)==clock && !inside && !zero_projected && !state_track.count);
        for(unsigned i=0;i<6;i+=2)psx_mod_write_half(0x800C456C+i,0x0800);
        stage_call=0;CHECK(stage_tick(&cpu,0x8001E9ECu));stage_call=1;
        for(unsigned i=0;i<6;i+=2)CHECK(psx_mod_read_half(0x800C456C+i)==0x0800);
        CHECK(pause_owner<0 && !state_track.count && !state_track.error);
        arrival_landed=1u<<first;
        for(unsigned i=0;i<8;i+=2)psx_mod_write_half(PLAYER+0x7C+i,0xFFFF);
        CHECK(player_tick(&cpu,0x80034DCCu));
        CHECK(paired_arrival(&cpu) && arrival_pair && life.status[1]==MMX6_COOP_JOINING);
        CHECK(arrival_ticks[0]==1 && arrival_ticks[1]==2);
        arrival_landed=3;
        CHECK(player_tick(&cpu,0x80034DCCu));
        /* Both idle alone do not release overlapping or fractional feet. */
        put32(p2.body+8,x+(10u<<16));
        CHECK(paired_arrival(&cpu) && arrival_pair);
        put32(p2.body+8,x+(24u<<16));put32(p2.body+12,y+1);
        CHECK(paired_arrival(&cpu) && arrival_pair);
        put32(p2.body+12,y);
        CHECK(paired_arrival(&cpu) && !arrival_pair && life.status[1]==MMX6_COOP_ALIVE);
        CHECK(arrival_births==1 && !paired_arrival(&cpu));
        arrival_pair=1;native_player_init(&cpu,0x8003BD24u);CHECK(!arrival_pair && !enrolled);
    }
    for(unsigned invalid=0;invalid<7;++invalid) {
        arrival_setup(&cpu);
        if(invalid==0)psx_mod_write_word(0x800351B4u,0);
        if(invalid==1)psx_mod_write_byte(PLAY+1,2);
        if(invalid==2)psx_mod_write_byte(PLAYER+5,19);
        if(invalid==3)psx_mod_write_byte(PLAYER+0xD0,1);
        if(invalid==4)psx_mod_write_byte(PLAYER+0x67,0);
        if(invalid==5)psx_mod_write_byte(PLAY+0x5E,5);
        if(invalid==6)psx_mod_write_byte(PLAY+0x10,1);
        CHECK(!paired_arrival(&cpu) && !arrival_pair && !enrolled && !arrival_births && !failed);
    }
    arrival_setup(&cpu);CHECK(paired_arrival(&cpu));
    psx_mod_write_byte(PLAYER+4,2);psx_mod_write_byte(PLAYER+0x5C,0);
    CHECK(player_tick(&cpu,0x80034DCCu));CHECK(!paired_arrival(&cpu));
    CHECK(!arrival_pair && life.status[0]==MMX6_COOP_DYING &&
        life.status[1]==MMX6_COOP_ALIVE && p2.body[5]==0);
    arrival_setup(&cpu);CHECK(paired_arrival(&cpu));p2.body[4]=2;p2.body[0x5C]=0;
    CHECK(!paired_arrival(&cpu) && !arrival_pair && life.status[1]==MMX6_COOP_DYING);
    /* Source-authored New Game HELP can request script20 while X still
     * beams in. A future request is not yet visible in D0 at admission. */
    arrival_setup(&cpu);psx_mod_write_byte(PLAY+0x1D,0);psx_mod_write_half(PLAY+0x9E,0);
    CHECK(!paired_arrival(&cpu) && !arrival_pair && !enrolled && !arrival_births);
    psx_mod_write_half(PLAY+0x9E,1);psx_mod_write_byte(PLAYER+0xD0,1);
    CHECK(!paired_arrival(&cpu) && !arrival_pair && !enrolled);
    psx_mod_write_byte(PLAYER+0xD0,0);psx_mod_write_byte(PLAYER+5,20);
    CHECK(!paired_arrival(&cpu) && !arrival_pair && !enrolled);
    /* A true later CP0 native arrival after that authored conversation is
     * consumed has no pending automatic HELP and can use the native pair. */
    psx_mod_write_byte(PLAYER+5,0);
    CHECK(paired_arrival(&cpu) && arrival_pair && enrolled && arrival_births==1);
}
static void native_scene_preserves_incoming_guest(void) {
    CPUState cpu;
    for(unsigned voluntary=0;voluntary<2;++voluntary) {
        if(!voluntary) {
            arrival_setup(&cpu);CHECK(paired_arrival(&cpu));
            arrival_landed=1;CHECK(player_tick(&cpu,0x80034DCCu));
            CHECK(arrival_pair && !join_phase && life.status[1]==MMX6_COOP_JOINING);
            memset(returning_body,0,sizeof returning_body); /* No Select departure ever occurred. */
        } else {
            setup(&cpu);p2.body[0x5C]=23;scene_transport_probe=2;voluntary_transport_probe=1;
            inside=1;life.status[1]=MMX6_COOP_LEAVING;start_leave(&cpu);
            enter_zero();guest(&cpu,0x8003674Cu,PLAYER,0);leave_zero();
            mmx6_coop_teleport_done(&life);CHECK(life.status[1]==MMX6_COOP_ABSENT);
            start_join(&cpu);inside=0;voluntary_transport_probe=0;
            CHECK(join_phase==1 && life.status[1]==MMX6_COOP_JOINING && returning_body[0x5C]==23);
        }
        uint8_t saved_return[sizeof returning_body];memcpy(saved_return,returning_body,sizeof saved_return);
        psx_mod_write_byte(PLAYER+5,20);psx_mod_write_byte(PLAYER+0xD0,1);
        psx_mod_write_byte(PLAYER+0xD4,0);
        psx_mod_write_byte(PLAYER+0x7A,1);psx_mod_write_byte(PLAY+0x1C,1);
        psx_mod_write_half(0x80097206u,980);
        scene_begin(0,0x800FE988u);CHECK(scene_owner==1 && scene_phase==1);
        PlayerContext owner;capture_player(&owner);
        uint8_t play[sizeof saved_play],camera[sizeof saved_camera];
        capture(PLAY,play,sizeof play);capture(0x800971F8u,camera,sizeof camera);
        if(!voluntary) {
            static const uint32_t expected[]={0x80034DCCu,0x8002012Cu,0x8002F288u,0x80020D74u,0x80020DC8u};
            for(unsigned tick=0;tick<2;++tick) {
                unsigned before=call_count,updates=arrival_ticks[1];scene_tick(&cpu);
                CHECK(scene_phase==1 && arrival_pair && !join_phase && life.status[1]==MMX6_COOP_JOINING &&
                    call_count-before==5 && !memcmp(calls+before,expected,sizeof expected) &&
                    arrival_ticks[1]==updates+1 && p2.body[0]==1 && p2.body[2]==1 && p2.body[0x5C]==32 &&
                    p2.body[0xE7]==5 && le32(p2.body+0x38)==assets && le32(p2.body+0x3C)==assembly);
                PlayerContext unchanged;capture_player(&unchanged);CHECK(!memcmp(&owner,&unchanged,sizeof owner));
                uint8_t current_play[sizeof play],current_camera[sizeof camera];
                capture(PLAY,current_play,sizeof play);capture(0x800971F8u,current_camera,sizeof camera);
                CHECK(!memcmp(play,current_play,sizeof play) && !memcmp(camera,current_camera,sizeof camera) &&
                    !memcmp(saved_return,returning_body,sizeof saved_return) && !inside && !zero_projected &&
                    !state_track.count && !state_track.error && !failed);
            }
            arrival_landed=3;scene_tick(&cpu);
            CHECK(scene_phase==1 && !arrival_pair && life.status[1]==MMX6_COOP_ALIVE &&
                arrival_grounded(p2.body) && arrival_births==1);
            paired_arrival_fixture_probe=0;
        }
        scene_transport_probe=2;
        scene_tick(&cpu);CHECK(scene_phase==2 && !join_phase && life.status[1]==MMX6_COOP_ALIVE);
        CHECK(p2.body[0]==1 && p2.body[2]==1 && p2.body[0x5C]==(voluntary?23:32) &&
            p2.body[0xE7]==5 && le32(p2.body+0x38)==assets && le32(p2.body+0x3C)==assembly);
        scene_tick(&cpu);CHECK(scene_phase==3);
        scene_tick(&cpu);CHECK(scene_phase==3); /* Original owner intro still locked. */
        psx_mod_write_byte(PLAYER+5,2);psx_mod_write_byte(PLAYER+0xD0,0);
        psx_mod_write_byte(PLAYER+0x7A,0);psx_mod_write_byte(PLAY+0x1C,0);
        scene_tick(&cpu);CHECK(scene_phase==4);
        for(unsigned n=0;n<12 && scene_owner;++n)scene_tick(&cpu);
        CHECK(!scene_owner && !scene_phase && !arrival_pair && life.status[1]==MMX6_COOP_ALIVE &&
            p2.body[0]==1 && p2.body[2]==1 && p2.body[0x5C]==(voluntary?23:32) && p2.body[0xE7]==5 &&
            le32(p2.body+0x38)==assets && le32(p2.body+0x3C)==assembly &&
            le32(p2.body+0x68)==0x80073D54u && !memcmp(saved_return,returning_body,sizeof saved_return) &&
            !inside && !zero_projected && !state_track.count && !state_track.error && !failed);
    }
    arrival_setup(&cpu);CHECK(paired_arrival(&cpu));memset(returning_body,0,sizeof returning_body);
    scene_begin(0,0x800FE988u);psx_mod_write_word(0x800351B4u,0);
    uint8_t incoming[sizeof p2.body];memcpy(incoming,p2.body,sizeof incoming);
    scene_tick(&cpu);
    CHECK(failed && scene_phase==1 && arrival_pair && life.status[1]==MMX6_COOP_JOINING &&
        !memcmp(incoming,p2.body,sizeof incoming) && !inside && !zero_projected && !state_track.count);
    arrival_setup(&cpu);CHECK(paired_arrival(&cpu));scene_begin(0,0x800FE988u);
    p2.body[4]=2;p2.body[0x5C]=0;scene_tick(&cpu);
    CHECK(!failed && !arrival_pair && scene_owner==1 && !scene_phase &&
        life.status[1]==MMX6_COOP_DYING && p2.body[4]==2 && !p2.body[0x5C]);
}
static void native_scene_after_nonpaired_enrollment(void) {
    for(unsigned stale=0;stale<2;++stale) {
        CPUState cpu;arrival_setup(&cpu);
        /* External native idle input for the actual late-enrollment path.
         * Its completed native init below is the sole saved-body producer. */
        psx_mod_write_byte(PLAYER+5,2);psx_mod_write_byte(PLAYER+0x67,0);
        psx_mod_write_byte(PLAYER+0x70,8);psx_mod_write_byte(PLAYER+0xE7,1);
        psx_mod_write_byte(PLAY+0x1C,0);psx_mod_write_half(0x80097206u,980);
        memset(returning_body,stale?0xA5:0,sizeof returning_body);
        if(stale){returning_body[2]=0;returning_body[0x5C]=9;returning_body[0xE7]=1;}
        Mmx6CoopRosterNative native={0,1,0,1,0};Mmx6CoopRoster roster;
        CHECK(mmx6_coop_roster_resolve(&native,&roster)==MMX6_COOP_ROSTER_OK);
        PlayerContext owner;capture_player(&owner);
        uint8_t play[sizeof saved_play],camera[sizeof saved_camera];
        capture(PLAY,play,sizeof play);capture(0x800971F8u,camera,sizeof camera);
        unsigned before=call_count;inside=1;enroll(&cpu,&roster,0);inside=0;
        static const uint32_t expected[]={0x8003BD24u,0x8003D718u,0x8003D630u,
            0x8003AD18u,0x8003A980u,0x8003BA04u};
        CHECK(call_count-before==6 && !memcmp(calls+before,expected,sizeof expected) && arrival_births==1 &&
            enrolled && !arrival_pair && join_phase==1 && life.status[1]==MMX6_COOP_JOINING &&
            returning_body[0]==1 && returning_body[2]==1 && returning_body[4]==1 && returning_body[5]==2 &&
            returning_body[0x5C]==32 && returning_body[0xE7]==5 &&
            le32(returning_body+0x38)==assets && le32(returning_body+0x3C)==assembly);
        for(unsigned i=0;i<9;++i)CHECK(returning_body[0xA8+i*2]==0x20 && returning_body[0xA9+i*2]==1);
        PlayerContext unchanged;capture_player(&unchanged);CHECK(!memcmp(&owner,&unchanged,sizeof owner));
        uint8_t current_play[sizeof play],current_camera[sizeof camera];
        capture(PLAY,current_play,sizeof play);capture(0x800971F8u,current_camera,sizeof camera);
        CHECK(!memcmp(play,current_play,sizeof play) && !memcmp(camera,current_camera,sizeof camera));
        uint8_t saved_return[sizeof returning_body];memcpy(saved_return,returning_body,sizeof saved_return);
        paired_arrival_fixture_probe=0;scene_transport_probe=2;
        psx_mod_write_byte(PLAYER+5,20);psx_mod_write_byte(PLAYER+0xD0,1);
        psx_mod_write_byte(PLAYER+0xD4,0);psx_mod_write_byte(PLAYER+0x7A,1);
        psx_mod_write_byte(PLAY+0x1C,1);scene_begin(0,0x800FE988u);
        capture_player(&owner);capture(PLAY,play,sizeof play);capture(0x800971F8u,camera,sizeof camera);
        scene_tick(&cpu);CHECK(scene_phase==2 && !join_phase && life.status[1]==MMX6_COOP_ALIVE);
        CHECK(p2.body[0]==1 && p2.body[2]==1 && p2.body[0x5C]==32 && p2.body[0xE7]==5);
        capture_player(&unchanged);capture(PLAY,current_play,sizeof play);
        capture(0x800971F8u,current_camera,sizeof camera);
        CHECK(!memcmp(&owner,&unchanged,sizeof owner) && !memcmp(play,current_play,sizeof play) &&
            !memcmp(camera,current_camera,sizeof camera));
        scene_tick(&cpu);CHECK(scene_phase==3);
        before=call_count;scene_tick(&cpu);CHECK(scene_phase==3 && call_count==before);
        psx_mod_write_byte(PLAYER+5,2);psx_mod_write_byte(PLAYER+0xD0,0);
        psx_mod_write_byte(PLAYER+0x7A,0);psx_mod_write_byte(PLAY+0x1C,0);
        capture_player(&owner);capture(PLAY,play,sizeof play);
        scene_tick(&cpu);CHECK(scene_phase==4);
        for(unsigned n=0;n<12 && scene_owner;++n)scene_tick(&cpu);
        CHECK(!scene_owner && !scene_phase && !arrival_pair && life.status[1]==MMX6_COOP_ALIVE &&
            p2.body[0]==1 && p2.body[2]==1 && p2.body[0x5C]==32 && p2.body[0xE7]==5 &&
            le32(p2.body+0x38)==assets && le32(p2.body+0x3C)==assembly &&
            le32(p2.body+0x68)==0x80073D54u && !memcmp(saved_return,returning_body,sizeof saved_return) &&
            !inside && !zero_projected && !state_track.count && !state_track.error && !failed);
        for(unsigned i=0;i<9;++i)CHECK(p2.body[0xA8+i*2]==0x20 && p2.body[0xA9+i*2]==1);
        capture(0x800971F8u,current_camera,sizeof camera);CHECK(!memcmp(camera,current_camera,sizeof camera));
        capture_player(&unchanged);capture(PLAY,current_play,sizeof play);
        CHECK(!memcmp(&owner,&unchanged,sizeof owner) && !memcmp(play,current_play,sizeof play));
    }
}
static void native_refight_return_preserves_living_personal_resources(void) {
    CPUState cpu;arrival_setup(&cpu);
    /* Real return boundary: the prior boss CP2 is still loaded, while its
     * native death callback has selected authored hub CP10. The outgoing
     * guest is hidden/state3 but remains living with independently used HP,
     * weapon and energy. Fresh native body initialization must still run. */
    psx_mod_write_byte(PLAY,9);psx_mod_write_byte(PLAY+12,12);
    psx_mod_write_byte(PLAY+13,0);psx_mod_write_byte(PLAY+0x1D,10);
    psx_mod_write_byte(0x800CC868u,2);
    cpu.gpr[31]=0x8001E720u;cpu.gpr[4]=PLAY;
    p2.body[2]=1;p2.body[3]=0;p2.body[4]=3;
    p2.body[0x5C]=p2.body[0x5D]=23;p2.body[0x5E]=32;p2.body[0x93]=3;
    put32(p2.body+8,0x11110000);put32(p2.body+12,0x22220000);
    for(unsigned i=0;i<9;++i){p2.body[0xA8+i*2]=(uint8_t)(73+i);p2.body[0xA9+i*2]=0;}
    checkpoint_native_entry(&cpu,0x8001E1BCu);
    CHECK(refight_return_checkpoint==10 && returning_body[0x5C]==23);
    native_player_init(&cpu,0x8003BD24u);
    CHECK(!enrolled && refight_return_checkpoint==10);
    psx_mod_write_byte(PLAY,10);psx_mod_write_word(PLAYER+8,1888u<<16);
    psx_mod_write_word(PLAYER+12,1216u<<16);
    Mmx6CoopRosterNative native={0,1,0,1,0};Mmx6CoopRoster roster;
    CHECK(mmx6_coop_roster_resolve(&native,&roster)==MMX6_COOP_ROSTER_OK);
    PlayerContext owner;capture_player(&owner);
    inside=1;enroll(&cpu,&roster,0);inside=0;
    CHECK(!refight_return_checkpoint && enrolled && arrival_births==1 && join_phase==1 &&
        p2.body[2]==1 && p2.body[0x5C]==23 && p2.body[0x5D]==23 && p2.body[0x5E]==32 &&
        p2.body[0x93]==3 && p2.body[0xE7]==5 && le32(p2.body+0x38)==assets &&
        le32(p2.body+8)==1912u<<16 && le32(p2.body+12)!=0x22220000);
    for(unsigned i=0;i<9;++i)CHECK(p2.body[0xA8+i*2]==73+i && !p2.body[0xA9+i*2]);
    PlayerContext unchanged;capture_player(&unchanged);CHECK(!memcmp(&owner,&unchanged,sizeof owner));
    CHECK(!zero_projected && !state_track.count && !state_track.error && !failed);

    /* Ordinary retries, invalid return relationships and nonliving guests
     * retain the existing fresh-native-resource behavior. */
    for(unsigned fault=0;fault<6;++fault) {
        arrival_setup(&cpu);refight_return_checkpoint=0;
        psx_mod_write_byte(PLAY,9);psx_mod_write_byte(PLAY+12,12);
        psx_mod_write_byte(PLAY+13,0);psx_mod_write_byte(PLAY+0x1D,10);
        psx_mod_write_byte(0x800CC868u,2);cpu.gpr[31]=0x8001E720u;cpu.gpr[4]=PLAY;
        p2.body[2]=1;p2.body[0x5C]=23;
        if(fault==0)life.status[1]=MMX6_COOP_FALLEN;
        if(fault==1)life.status[1]=MMX6_COOP_ABSENT;
        if(fault==2)life.wipe=1;
        if(fault==3)psx_mod_write_byte(0x800CC868u,10);
        if(fault==4)psx_mod_write_byte(PLAY+0x1D,2);
        if(fault==5)cpu.gpr[31]=0;
        checkpoint_native_entry(&cpu,0x8001E1BCu);
        CHECK(!refight_return_checkpoint);
    }
}
static void native_checkpoint_preserves_completed_voluntary_absence(void) {
    for(unsigned held=0;held<2;++held) {
        CPUState cpu;arrival_setup(&cpu);
        p2.body[0x5C]=23;
        for(unsigned i=0;i<9;++i){p2.body[0xA8+i*2]=73;p2.body[0xA9+i*2]=0;}
        memcpy(returning_body,p2.body,sizeof returning_body);
        returning_body[3]=returning_body[4]=1;returning_body[5]=2;
        p2.body[3]=0;p2.body[4]=3;p2.body[5]=p2.body[6]=0;
        life.status[1]=MMX6_COOP_ABSENT;
        life.select_previous=(uint8_t)held;life.select_armed=(uint8_t)!held;
        PlayerContext absent=p2;
        uint8_t saved_return[sizeof returning_body];memcpy(saved_return,returning_body,sizeof saved_return);
        unsigned before=call_count;
        native_player_init(&cpu,0x8003BD24u);
        CHECK(!enrolled && !arrival_pair && life.status[0]==MMX6_COOP_ALIVE &&
            life.status[1]==MMX6_COOP_ABSENT && life.select_previous==held &&
            life.select_armed==!held);
        /* Exercise actual enrollment through the original incoming-beam
         * dispatcher, not a replacement lifecycle-only model. No guest birth
         * or beam is authorized for this deliberately absent participant. */
        CHECK(!paired_arrival(&cpu));
        CHECK(enrolled && !arrival_pair && !join_phase && !arrival_births && call_count==before &&
            life.status[1]==MMX6_COOP_ABSENT && !memcmp(&absent,&p2,sizeof p2) &&
            !memcmp(saved_return,returning_body,sizeof saved_return));
        if(held)CHECK(mmx6_coop_join_input(&life,1,1,1)==MMX6_COOP_NO_ACTION);
        CHECK(mmx6_coop_join_input(&life,0,1,1)==MMX6_COOP_NO_ACTION);
        CHECK(mmx6_coop_join_input(&life,1,1,1)==MMX6_COOP_JOIN);
        voluntary_transport_probe=1;scene_transport_probe=2;inside=1;
        start_join(&cpu);
        inside=0;voluntary_transport_probe=0;
        CHECK(life.status[1]==MMX6_COOP_JOINING && join_phase==1 && p2.body[0x5C]==23 &&
            p2.body[2]==1 && !memcmp(saved_return,returning_body,sizeof saved_return));
        for(unsigned i=0;i<9;++i)CHECK(p2.body[0xA8+i*2]==73 && !p2.body[0xA9+i*2]);
        CHECK(!zero_projected && !state_track.count && !state_track.error && !failed);
    }
}
static void native_guest_weather_window(void) {
    for(unsigned variant=0;variant<32;++variant) {
        CPUState cpu;setup(&cpu);private_draw=0;
        const uint32_t actor=0x8008EF48u;uint32_t window=0x800F5E90u,address=0x800EB310u;
        psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+12,6);
        psx_mod_write_byte(actor,65);psx_mod_write_byte(actor+1,14);
        psx_mod_write_word(0x800EB304u,0x84C670AAu);psx_mod_write_word(address,0x84830000u);
        int low=1248,high=1631,primary=1120,guest_x=1257;
        if(variant==1)primary=1400;
        if(variant==2)guest_x=1170;
        if(variant==3)guest_x=1631;
        if(variant==4)guest_x=1248;
        if(variant==5)guest_x=1632;
        if(variant==6)guest_x=1247;
        if(variant==7)life.status[1]=MMX6_COOP_ABSENT;
        if(variant==8)life.status[1]=MMX6_COOP_FALLEN;
        if(variant==9)zero_world=1;
        if(variant==10)inside=1;
        if(variant==11)private_draw=1;
        if(variant==12)scene_owner=1;
        if(variant==13)pause_owner=0;
        if(variant==14)psx_mod_write_byte(PLAY+12,0);
        if(variant==15)psx_mod_write_byte(PLAY+13,1);
        if(variant==16)psx_mod_write_word(address,0);
        if(variant==17)psx_mod_write_word(0x800EB304u,0);
        if(variant==18)psx_mod_write_byte(actor+1,13);
        if(variant==19)window+=2;
        if(variant==20)psx_mod_write_byte(0x800F6BA0u,7);
        if(variant==21)p2.body[0x7A]=1;
        if(variant==22)p2.body[3]=0;
        if(variant==23)p2.body[0x5C]=0;
        if(variant==24)ready=0;
        if(variant==25)enrolled=0;
        if(variant==26)failed=1;
        if(variant==27)address+=4;
        if(variant==28)p2.body[4]=2;
        if(variant==29)primary=-100;
        if(variant==30){low=1631;high=1248;}
        if(variant==31){window+=4;psx_mod_write_byte(0x800F6BA0u,1);low=-150;high=-10;primary=100;guest_x=-80;}
        psx_mod_write_half(window,(uint16_t)low);psx_mod_write_half(window+2,(uint16_t)high);
        put32(p2.body+8,(uint32_t)guest_x*65536u);cpu.gpr[4]=window;cpu.gpr[6]=(uint32_t)primary;cpu.gpr[17]=actor;
        CPUState expected=cpu;PlayerContext before=p2;unsigned calls_before=call_count;
        if(variant==0 || variant==3 || variant==4 || variant==29 || variant==31)expected.gpr[6]=(uint32_t)guest_x;
        static uint8_t before_ram[sizeof ram],before_extra[sizeof extra];
        memcpy(before_ram,ram,sizeof ram);memcpy(before_extra,extra,sizeof extra);
        weather_window_target(&cpu,address);
        CHECK(!memcmp(&cpu,&expected,sizeof cpu) && !memcmp(&p2,&before,sizeof p2));
        CHECK(!memcmp(ram,before_ram,sizeof ram) && !memcmp(extra,before_extra,sizeof extra));
        CHECK(call_count==calls_before && !state_track.count && !state_track.error);
    }
    private_draw=0;
}
static void native_optional_boss_damage_budget(void) {
    CPUState cpu;setup(&cpu);
    const uint32_t actor=BOSS_BALANCE_POOL;
    psx_mod_write_byte(PLAY,10);psx_mod_write_word(PLAY+0x20,actor);
    psx_mod_write_byte(PLAY+0x24,48);
    psx_mod_write_byte(actor,65);psx_mod_write_byte(actor+1,56);
    psx_mod_write_byte(actor+4,1);psx_mod_write_byte(actor+0x5C,48);
    psx_mod_write_word(actor+0x10,0x800F7E48u);
    cpu.gpr[8]=actor;cpu.gpr[5]=8;boss_balance_enabled=0;
    memset(boss_balance,0,sizeof boss_balance);
    boss_balance_damage(&cpu,0x800318F4u);
    CHECK(cpu.gpr[5]==8 && !boss_balance[0].recognized);
    for(unsigned character=0;character<2;++character) {
        memset(boss_balance,0,sizeof boss_balance);boss_balance_enabled=1;
        psx_mod_write_byte(PLAYER+2,(uint8_t)character);
        unsigned spent=0;
        for(unsigned hit=0;hit<10;++hit) {
            cpu.gpr[5]=1;boss_balance_damage(&cpu,0x800318F4u);
            spent+=cpu.gpr[5];
        }
        CHECK(spent==(character?4u:5u) && !boss_balance[0].remainder);
    }
    memset(boss_balance,0,sizeof boss_balance);
    psx_mod_write_byte(PLAYER+2,0);cpu.gpr[5]=1;
    boss_balance_damage(&cpu,0x800318F4u);CHECK(cpu.gpr[5]==0);
    cpu.gpr[5]=0;boss_balance_damage(&cpu,0x800318F4u);
    CHECK(boss_balance[0].remainder==5); /* No admitted damage, no carry use. */
    psx_mod_write_byte(PLAYER+2,1);cpu.gpr[5]=1;
    boss_balance_damage(&cpu,0x800318F4u);CHECK(cpu.gpr[5]==0);
    psx_mod_write_byte(PLAYER+2,0);cpu.gpr[5]=1;
    boss_balance_damage(&cpu,0x800318F4u);
    CHECK(cpu.gpr[5]==1 && boss_balance[0].remainder==4);
#ifdef MMX6_COOP_MODERN_STATE
    HostState saved;state_capture(&saved);boss_balance[0].remainder=0;
    state_commit(&saved);CHECK(boss_balance[0].remainder==4);
#endif
    memset(boss_balance,0,sizeof boss_balance);
    psx_mod_write_byte(PLAYER+2,1);psx_mod_write_byte(actor+0x5C,1);
    cpu.gpr[5]=127;boss_balance_damage(&cpu,0x800318F4u);
    CHECK(cpu.gpr[5]==50 && boss_balance[0].remainder==8); /* Before lethal clipping. */
    private_draw=1;cpu.gpr[5]=8;boss_balance_damage(&cpu,0x800318F4u);
    CHECK(cpu.gpr[5]==8 && boss_balance[0].remainder==8);private_draw=0;
    cpu.gpr[8]=actor+BOSS_BALANCE_STRIDE;
    psx_mod_write_byte(cpu.gpr[8],65);psx_mod_write_byte(cpu.gpr[8]+1,15);
    psx_mod_write_byte(cpu.gpr[8]+4,1);psx_mod_write_byte(cpu.gpr[8]+0x5C,10);
    cpu.gpr[5]=8;boss_balance_damage(&cpu,0x800318F4u);
    CHECK(cpu.gpr[5]==8 && !boss_balance[1].recognized);
    boss_balance_enabled=0;boss_balance_pending_actor=0;memset(boss_balance,0,sizeof boss_balance);
}

static void native_optional_boss_shared_cooldown(void) {
    CPUState cpu;setup(&cpu);const uint32_t actor=BOSS_BALANCE_POOL;
    const BossCooldownSite *site=NULL;
    for(unsigned i=0;i<sizeof boss_cooldown_sites/sizeof boss_cooldown_sites[0];++i)
        if(boss_cooldown_sites[i].address==0x800ED020u)site=&boss_cooldown_sites[i];
    CHECK(site!=NULL);
    for(unsigned j=0;j<7;++j)psx_mod_write_word(site->address-24u+j*4u,site->words[j]);
    psx_mod_write_byte(PLAY,10);psx_mod_write_word(PLAY+0x20,actor);psx_mod_write_byte(PLAY+0x24,48);
    psx_mod_write_byte(actor,65);psx_mod_write_byte(actor+1,61);psx_mod_write_byte(actor+4,1);
    psx_mod_write_byte(actor+0x5C,48);psx_mod_write_word(actor+0x10,0x800F57ECu);
    boss_balance_enabled=1;cpu.gpr[8]=actor;cpu.gpr[5]=2;
    boss_balance_damage(&cpu,0x800318F4u);CHECK(boss_balance_pending_actor==actor);
#ifdef MMX6_COOP_MODERN_STATE
    HostState saved;state_capture(&saved);boss_balance_pending_actor=0;
    state_commit(&saved);CHECK(boss_balance_pending_actor==actor);
#endif
    psx_mod_write_word(actor+0x58,0x8007433Cu);
    for(unsigned i=0;i<sizeof boss_cooldown_sites/sizeof boss_cooldown_sites[0];++i) {
        const BossCooldownSite *actual=&boss_cooldown_sites[i];
        for(unsigned j=0;j<7;++j)psx_mod_write_word(actual->address-24u+j*4u,actual->words[j]);
        unsigned base=(actual->words[6]>>21)&31u,value=(actual->words[6]>>16)&31u;
        CHECK(base!=value);cpu.gpr[base]=actor;cpu.gpr[value]=30;boss_balance_pending_actor=actor;
        boss_balance_shared_cooldown(&cpu,actual->address);
        CHECK(cpu.gpr[value]==15 && !boss_balance_pending_actor);
    }
#ifdef MMX6_COOP_MODERN_STATE
    HostState invalid;state_capture(&invalid);invalid.boss_balance_pending_actor=actor+1;
    StateIO bad={STATE_HASH,1,NULL,NULL,0,0,2166136261u};state_core(&bad,&invalid);CHECK(!bad.ok);
#endif
    boss_balance_pending_actor=actor;
    cpu.gpr[16]=actor;cpu.gpr[2]=30;psx_mod_write_word(actor+0x58,0x8007433Cu);
    boss_balance_shared_cooldown(&cpu,site->address);CHECK(cpu.gpr[2]==15 && !boss_balance_pending_actor);
    cpu.gpr[2]=30;boss_balance_shared_cooldown(&cpu,site->address);CHECK(cpu.gpr[2]==30); /* No accepted hit. */
    boss_balance_pending_actor=actor;cpu.gpr[2]=2;
    boss_balance_shared_cooldown(&cpu,site->address);CHECK(cpu.gpr[2]==1 && !boss_balance_pending_actor);
    boss_balance_pending_actor=actor;cpu.gpr[2]=10000;
    boss_balance_shared_cooldown(&cpu,site->address);CHECK(cpu.gpr[2]==10000 && !boss_balance_pending_actor);
    boss_balance_pending_actor=actor;cpu.gpr[2]=30;
    psx_mod_write_word(site->address-4u,site->words[5]^1u);
    boss_balance_shared_cooldown(&cpu,site->address);CHECK(cpu.gpr[2]==30); /* Another overlay. */
    psx_mod_write_word(site->address-4u,site->words[5]);psx_mod_write_word(actor+0x58,0x8007591Cu);
    boss_balance_shared_cooldown(&cpu,site->address);CHECK(cpu.gpr[2]==30); /* Ordinary AI clock. */
    psx_mod_write_word(actor+0x58,0x8007433Cu);boss_balance_enabled=0;
    boss_balance_shared_cooldown(&cpu,site->address);CHECK(cpu.gpr[2]==30);
    boss_balance_pending_actor=0;memset(boss_balance,0,sizeof boss_balance);
}

static void native_capsule_keeps_living_passenger(void) {
    for(unsigned seat=0;seat<2;++seat) {
        CPUState cpu;setup(&cpu);capsule_native_probe=1;
        life.status[0]=life.status[1]=MMX6_COOP_ALIVE;
        /* setup() deliberately poisons resident fields with B3. This case
         * starts from genuine idle bodies, without unrelated script locks. */
        const unsigned locks[]={0xD0,0xD4,0x7A};
        for(unsigned n=0;n<3;++n) {psx_mod_write_byte(PLAYER+locks[n],0);p2.body[locks[n]]=0;}
        psx_mod_write_byte(PLAYER+3,1);psx_mod_write_byte(PLAYER+4,1);
        psx_mod_write_byte(PLAYER+0x5C,32);p2.body[3]=p2.body[4]=1;p2.body[0x5C]=32;
        uint32_t actor=0x800C1220u;cpu.gpr[4]=actor;
        psx_mod_write_word(actor+8,1424u<<16);psx_mod_write_word(actor+12,1604u<<16);
        psx_mod_write_word(PLAYER+8,(seat?1600u:1424u)<<16);
        psx_mod_write_word(PLAYER+12,1595u<<16);
        put32(p2.body+8,(seat?1424u:1600u)<<16);put32(p2.body+12,1594u<<16);
        CHECK(interaction_begin(&cpu,0x80051924u));
        CHECK(scene_owner==seat+1 && !scene_phase && !failed && !state_track.count);
        unsigned before=call_count;
        for(unsigned tick=0;tick<20;++tick) {
            scene_tick(&cpu);
            CHECK(scene_owner==seat+1 && !scene_phase && call_count==before);
            CHECK(psx_mod_read_byte(PLAYER+3) && psx_mod_read_byte(PLAYER+4)==1 &&
                  p2.body[3] && p2.body[4]==1 && !failed);
        }
        /* The original owner finishes the capsule; no synthetic landing or
         * passenger constructor is needed to release the shared owner. */
        if(seat)p2.body[0xD0]=0;else psx_mod_write_byte(PLAYER+0xD0,0);
        for(unsigned n=0;n<4;++n) {
            const unsigned offsets[]={0x12,0x13,0x16,0x17};
            psx_mod_write_byte(PLAY+offsets[n],0);
        }
        scene_tick(&cpu);CHECK(!scene_owner && !scene_phase && call_count==before && !failed);
    }
}
static void native_default_private_boss_cookies(void) {
    CPUState cpu;setup(&cpu);const uint32_t actor=BOSS_BALANCE_POOL;
    boss_scan_probe=1;boss_balance_enabled=boss_balance_independent=0;
    psx_mod_write_byte(PLAYER+0xCC,0);p2.body[0xCC]=0;
    memset(boss_scan_calls,0,sizeof boss_scan_calls);
    boss_scan_present[0]=boss_scan_present[1]=1;
    boss_scan_cookie[0]=boss_scan_cookie[1]=42;boss_scan_type[0]=0;boss_scan_type[1]=44;
    psx_mod_write_byte(PLAY,10);psx_mod_write_word(PLAY+0x20,actor);psx_mod_write_byte(PLAY+0x24,48);
    psx_mod_write_byte(actor,65);psx_mod_write_byte(actor+1,56);psx_mod_write_byte(actor+4,1);
    psx_mod_write_byte(actor+0x5C,48);psx_mod_write_word(actor+0x10,0x800F7E48u);
    psx_mod_write_word(actor+0x58,0x8007555Cu);psx_mod_write_byte(actor+0x65,91);
    cpu.gpr[4]=actor;CHECK(enemy_hit(&cpu,0x80031474u) && cpu.gpr[2]==1);
    CHECK(psx_mod_read_byte(actor+0x5C)==46 && boss_balance[0].cookies[0]==42);
    /* The other owner uses the same native token; it is independently new. */
    cpu.gpr[4]=actor;CHECK(enemy_hit(&cpu,0x80031474u) && cpu.gpr[2]==45);
    CHECK(psx_mod_read_byte(actor+0x5C)==44 && boss_balance[0].cookies[1]==42);
    cpu.gpr[4]=actor;CHECK(enemy_hit(&cpu,0x80031474u) && !cpu.gpr[2]);
    CHECK(psx_mod_read_byte(actor+0x5C)==44 && psx_mod_read_byte(actor+0x65)==91);
    /* A fresh primary shot must not rearm the still-overlapping guest one. */
    boss_scan_cookie[0]=43;cpu.gpr[4]=actor;enemy_hit(&cpu,0x80031474u);
    CHECK(psx_mod_read_byte(actor+0x5C)==42);
    cpu.gpr[4]=actor;enemy_hit(&cpu,0x80031474u);
    CHECK(!cpu.gpr[2] && psx_mod_read_byte(actor+0x5C)==42);
    /* Native no-overlap clears only that owner's memory. The unchanged
     * persistent guest allocation may then make a fresh valid recontact. */
    boss_scan_present[0]=boss_scan_present[1]=0;cpu.gpr[4]=actor;enemy_hit(&cpu,0x80031474u);
    CHECK(!boss_balance[0].cookies[0] && !boss_balance[0].cookies[1]);
    boss_scan_present[1]=1;cpu.gpr[4]=actor;enemy_hit(&cpu,0x80031474u);
    CHECK(cpu.gpr[2]==45 && psx_mod_read_byte(actor+0x5C)==40 && boss_scan_cookie[1]==42);
    /* Token zero keeps the original repeatable-contact contract. */
    boss_scan_cookie[1]=0;
    for(unsigned n=0;n<2;++n){cpu.gpr[4]=actor;enemy_hit(&cpu,0x80031474u);CHECK(cpu.gpr[2]==45);}
    CHECK(psx_mod_read_byte(actor+0x5C)==36 && !boss_balance_pending_actor);
    /* Default shared immunity still ends the scan at the original P1
     * rejection; this correctness fix does not opt into private cooldowns. */
    boss_scan_present[0]=1;boss_scan_cookie[0]=44;psx_mod_write_word(actor+0x58,0x8007433Cu);
    unsigned guest_calls=boss_scan_calls[1];cpu.gpr[4]=actor;enemy_hit(&cpu,0x80031474u);
    CHECK(cpu.gpr[2]==127 && boss_scan_calls[1]==guest_calls && psx_mod_read_byte(actor+0x5C)==36);
#ifdef MMX6_COOP_MODERN_STATE
    HostState saved;state_capture(&saved);uint32_t digest=state_digest();
    boss_balance[0].cookies[1]=77;CHECK(state_digest()!=digest);state_commit(&saved);
    CHECK(boss_balance[0].cookies[1]==0 && state_digest()==digest);
    StateIO valid={STATE_HASH,1,NULL,NULL,0,0,2166136261u};state_core(&valid,&saved);CHECK(valid.ok);
    saved.boss_balance[0].recognized=0;StateIO bad={STATE_HASH,1,NULL,NULL,0,0,2166136261u};state_core(&bad,&saved);CHECK(!bad.ok);
#endif
    /* Original allocation invalidates stale cookies even when an identical
     * boss record reuses this address; changed source identity does too. */
    cpu.gpr[4]=actor;CHECK(boss_balance_allocate(&cpu,0x8002BCCCu) && cpu.gpr[2]==actor);
    CHECK(!boss_balance[0].cookies[0] && !boss_balance[0].recognized);
    BossBalanceState *state=boss_balance_actor(actor);CHECK(state);state->cookies[0]=44;
    psx_mod_write_word(actor+0x10,0x800F7E50u);CHECK(boss_balance_actor(actor)==state && !state->cookies[0]);
    private_draw=1;cpu.gpr[4]=actor;CHECK(!enemy_hit(&cpu,0x80031474u));private_draw=0;
    boss_scan_probe=0;memset(boss_balance,0,sizeof boss_balance);
}
static void native_capsule_owner_contact_transaction(void) {
    CPUState cpu;setup(&cpu);capsule_native_probe=2;
    private_actor.character=MMX6_COOP_CHARACTER_X;private_actor.form=0;
    life.status[0]=life.status[1]=MMX6_COOP_ALIVE;
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+1,0);
    psx_mod_write_byte(PLAYER+2,1);psx_mod_write_byte(PLAYER+4,1);
    psx_mod_write_byte(PLAYER+0x5C,32);psx_mod_write_byte(PLAYER+0xE2,0);psx_mod_write_byte(PLAYER+0xE5,0);
    p2.body[0]=p2.body[3]=p2.body[4]=1;p2.body[2]=p2.body[0xE2]=p2.body[0xE5]=0;p2.body[0x5C]=32;
    uint32_t a=0x800C1220u;cpu.gpr[4]=a;
    psx_mod_write_byte(a,1);psx_mod_write_byte(a+1,26);psx_mod_write_byte(a+2,4);
    psx_mod_write_byte(a+4,1);psx_mod_write_byte(a+5,6);psx_mod_write_word(a+0x10,0x800F2E24u);
    SolidContact *c=solid_contact(a);CHECK(c);c->sides=c->carried=0;
    CHECK(capsule_owner_update(&cpu,0x80051890u) && cpu.gpr[2]==0xCAFE);
    CHECK(c->sides==8 && c->carried==1 && !p2.body[0xE2] && psx_mod_read_byte(a+5)==6);
    CHECK(psx_mod_read_byte(a+0x72)==2 && psx_mod_read_byte(PLAYER+0x71)==2 && p2.body[0x71]==8);
    CHECK(!scene_owner && !inside && !solid_call && !scene_call && !zero_projected && !state_track.count);
    /* Next original update consumes that same owner's retained contact. */
    CHECK(capsule_owner_update(&cpu,0x80051890u) && p2.body[0xE2]==1 && psx_mod_read_byte(a+5)==7);
    CHECK(scene_owner==2 && !scene_phase && !psx_mod_read_byte(PLAYER+0xE2));
    /* A subsequent owner-world update preserves the same transaction and
     * leaves its caller's live projection/guards intact. */
    inside=1;enter_zero();zero_world=1;
    CHECK(capsule_owner_update(&cpu,0x80051890u) && zero_projected && inside && !solid_call && !scene_call);
    zero_world=0;leave_zero_context(1);inside=0;
    CHECK(c->sides==8 && psx_mod_read_byte(a+0x72)==2 && !state_track.count && !state_track.error);
    scene_owner=0;psx_mod_write_byte(a+5,5);unsigned before=call_count;
    CHECK(!capsule_owner_update(&cpu,0x80051890u) && call_count==before);
    capsule_native_probe=0;
}
static void native_optional_private_boss_cooldowns(void) {
    CPUState cpu;setup(&cpu);const uint32_t actor=BOSS_BALANCE_POOL;
    boss_balance_enabled=boss_balance_independent=boss_scan_probe=1;
    psx_mod_write_byte(PLAYER+0xCC,0);p2.body[0xCC]=0;
    memset(boss_scan_calls,0,sizeof boss_scan_calls);
    boss_scan_present[0]=boss_scan_present[1]=1;
    boss_scan_cookie[0]=boss_scan_cookie[1]=42;boss_scan_type[0]=0;boss_scan_type[1]=24;
    psx_mod_write_byte(PLAY,10);psx_mod_write_word(PLAY+0x20,actor);psx_mod_write_byte(PLAY+0x24,48);
    psx_mod_write_byte(actor,65);psx_mod_write_byte(actor+1,61);psx_mod_write_byte(actor+4,1);
    psx_mod_write_byte(actor+0x5C,48);psx_mod_write_word(actor+0x10,0x800F57ECu);psx_mod_write_word(actor+0x58,0x8007591Cu);
    const BossCooldownSite *site=NULL;
    for(unsigned i=0;i<sizeof boss_cooldown_sites/sizeof boss_cooldown_sites[0];++i)if(boss_cooldown_sites[i].address==0x800ED020u)site=&boss_cooldown_sites[i];
    CHECK(site);
    for(unsigned j=0;j<7;++j)psx_mod_write_word(site->address-24+j*4,site->words[j]);
    cpu.gpr[4]=actor;CHECK(enemy_hit(&cpu,0x80031474u)==1 && cpu.gpr[2]==1);
    CHECK(boss_scan_calls[0]==1 && !boss_scan_calls[1] && boss_balance_pending_actor==actor);
    BossBalanceState *state=&boss_balance[0];
    CHECK(state->cookies[0]==42 && state->cookies[1]==0 && psx_mod_read_byte(actor+0x65)==0);
    psx_mod_write_word(actor+0x58,0x8007433Cu);cpu.gpr[16]=actor;cpu.gpr[2]=30;
    boss_balance_shared_cooldown(&cpu,site->address);psx_mod_write_half(actor+0x86,(uint16_t)cpu.gpr[2]);
    CHECK(state->clocks[0]==15 && !state->clocks[1] && cpu.gpr[2]==1 && state->vulnerable_table==0x8007591Cu);
    cpu.gpr[4]=actor;CHECK(enemy_hit(&cpu,0x80031474u)==1 && cpu.gpr[2]==25);
    CHECK(boss_scan_calls[0]==1 && boss_scan_calls[1]==1 && state->clocks[0]==14);
    CHECK(state->cookies[1]==42 && state->hit_owner==1 && state->hit_melee);
    psx_mod_write_word(actor+0x58,0x8007433Cu);cpu.gpr[16]=actor;cpu.gpr[2]=30;
    boss_balance_shared_cooldown(&cpu,site->address);psx_mod_write_half(actor+0x86,(uint16_t)cpu.gpr[2]);
    CHECK(state->clocks[0]==14 && state->clocks[1]==4 && cpu.gpr[2]==4);
#ifdef MMX6_COOP_MODERN_STATE
    HostState saved;state_capture(&saved);state->clocks[0]=0;state->cookies[1]=0;state_commit(&saved);
    CHECK(state->clocks[0]==14 && state->clocks[1]==4 && state->cookies[1]==42);
    saved.boss_balance[0].timer_offset=255;StateIO bad={STATE_HASH,1,NULL,NULL,0,0,2166136261u};state_core(&bad,&saved);CHECK(!bad.ok);
#endif
    /* Positive own recovery blocks without consuming the blade's token. */
    for(unsigned n=0;n<3;++n){cpu.gpr[4]=actor;CHECK(enemy_hit(&cpu,0x80031474u));}
    CHECK(state->clocks[1]==1 && boss_scan_calls[1]==1);
    psx_mod_write_half(actor+0x86,1);cpu.gpr[4]=actor;enemy_hit(&cpu,0x80031474u);
    CHECK(state->clocks[1]==0 && boss_scan_calls[1]==2 && !boss_balance_pending_actor);
    CHECK(psx_mod_read_word(actor+0x58)==0x8007433Cu && psx_mod_read_half(actor+0x86)==1); /* Duplicate retains original cleanup tick. */
    /* Native30-frame standard air/finisher/fresh melee paths cap at4. */
    const unsigned kinds[3]={27,26,24};
    for(unsigned k=0;k<3;++k) {
        state->clocks[1]=0;psx_mod_write_word(actor+0x58,0x8007591Cu);psx_mod_write_half(actor+0x86,0);
        boss_scan_type[1]=kinds[k];boss_scan_cookie[1]=50+k;cpu.gpr[4]=actor;enemy_hit(&cpu,0x80031474u);
        CHECK(boss_balance_pending_actor==actor && state->hit_owner==1 && state->hit_melee);
        psx_mod_write_word(actor+0x58,0x8007433Cu);cpu.gpr[16]=actor;cpu.gpr[2]=30;
        boss_balance_shared_cooldown(&cpu,site->address);CHECK(state->clocks[1]==4);
    }
    boss_balance_pending_actor=actor;state->hit_owner=1;state->hit_melee=1;cpu.gpr[16]=actor;cpu.gpr[2]=2;
    boss_balance_shared_cooldown(&cpu,site->address);CHECK(state->clocks[1]==1); /* Original2 remains shorter1. */
    /* Authored long/scripted protection cannot be bypassed by a ready seat. */
    state->clocks[0]=15;state->clocks[1]=0;psx_mod_write_half(actor+0x86,10000);psx_mod_write_word(actor+0x58,0x8007433Cu);
    boss_scan_cookie[1]=77;cpu.gpr[4]=actor;enemy_hit(&cpu,0x80031474u);
    CHECK(!boss_balance_pending_actor && psx_mod_read_half(actor+0x86)==10000 && psx_mod_read_word(actor+0x58)==0x8007433Cu);
    private_draw=1;state->clocks[0]=10;cpu.gpr[4]=actor;CHECK(!enemy_hit(&cpu,0x80031474u) && state->clocks[0]==10);private_draw=0;
    boss_balance_enabled=boss_balance_independent=boss_scan_probe=0;boss_balance_pending_actor=0;memset(boss_balance,0,sizeof boss_balance);
}

/* Exercise the actual enter/leave implementation for both descriptors,
 * including an X overlay byte at the Zero-only writable-backup offset. */
static void opposite_resource_identity_projection(void) {
    CPUState cpu={0};
    for(unsigned character=0;character<2;++character) {
        setup(&cpu);
        Mmx6CoopRosterNative native={(uint8_t)character,(uint8_t)(character?5:0),
            (uint8_t)character,(uint8_t)(character?5:0),0};
        Mmx6CoopRoster roster;CHECK(mmx6_coop_roster_resolve(&native,&roster)==MMX6_COOP_ROSTER_OK);
        CHECK(private_roster_bind(&roster));
        psx_mod_write_byte(PLAYER+2,(uint8_t)character);
        psx_mod_write_byte(PLAYER+0xE7,(uint8_t)(character?5:0));
        psx_mod_write_byte(PLAY+0x38,(uint8_t)character);
        psx_mod_write_byte(PLAY+0x5E,(uint8_t)(character?5:0));
        p2.body[2]=private_actor.character;p2.body[0xE7]=private_actor.form;
        memset(zero_giga_backup,0xA7,sizeof zero_giga_backup);
        enter_zero();
        CHECK(psx_mod_read_byte(PLAY+0x38)==(character^1u));
        CHECK(psx_mod_read_byte(PLAY+0x5E)==(character?0:5));
        CHECK(psx_mod_read_byte(PLAYER+2)==(character^1u));
        CHECK(psx_mod_read_byte(OVERLAY+ZERO_GIGA_BACKUP_OFFSET)==(character?0x44:0xA7));
        psx_mod_write_byte(OVERLAY+ZERO_GIGA_BACKUP_OFFSET,0x6B);
        psx_mod_write_byte(PLAY+0x60,0x79);
        leave_zero_context(1);
        CHECK(psx_mod_read_byte(PLAYER+2)==character);
        CHECK(psx_mod_read_byte(PLAY+0x38)==character);
        CHECK(psx_mod_read_byte(PLAY+0x5E)==(character?5:0));
        CHECK(psx_mod_read_byte(PLAY+0x60)==0x79);
        CHECK(zero_giga_backup[0]==(character?0xA7:0x6B));
        if(character) {enter_zero();CHECK(psx_mod_read_byte(OVERLAY+ZERO_GIGA_BACKUP_OFFSET)==0x6B);leave_zero();}
        CHECK(!state_track.count && !state_track.error);
    }
    setup(&cpu);Mmx6CoopRoster invalid={0};
    CHECK(!private_roster_bind(&invalid));
    CHECK(private_actor.character==MMX6_COOP_CHARACTER_ZERO && private_actor.form==MMX6_COOP_FORM_ZERO);
    for(unsigned form=0;form<=3;++form) {
        setup(&cpu);partner_x_armor=form;
        psx_mod_write_byte(PLAYER+2,1);psx_mod_write_byte(PLAYER+0xE7,5);
        psx_mod_write_byte(PLAY+0x38,1);psx_mod_write_byte(PLAY+0x5E,5);
        psx_mod_write_byte(PLAY+0x5F,7);psx_mod_write_byte(PLAY+0x69,255);
        Mmx6CoopRoster selected;CHECK(fixed_roster(&selected) && selected.seat[1].form==form && private_roster_bind(&selected));
        enter_zero();CHECK(psx_mod_read_byte(PLAY+0x38)==0 && psx_mod_read_byte(PLAY+0x5E)==form);
        leave_zero();CHECK(psx_mod_read_byte(PLAY+0x38)==1 && psx_mod_read_byte(PLAY+0x5E)==5 && psx_mod_read_byte(PLAY+0x69)==255);
        /* Availability changes cannot poll/switch the already-bound actor. */
        psx_mod_write_byte(PLAY+0x5F,0);psx_mod_write_byte(PLAY+0x69,0);
        enter_zero();CHECK(psx_mod_read_byte(PLAY+0x5E)==form);leave_zero();
    }
    setup(&cpu);partner_x_armor=MMX6_COOP_FORM_SHADOW;
    psx_mod_write_byte(PLAYER+2,1);psx_mod_write_byte(PLAYER+0xE7,5);
    psx_mod_write_byte(PLAY+0x38,1);psx_mod_write_byte(PLAY+0x5E,5);
    psx_mod_write_byte(PLAY+0x5F,0x10);psx_mod_write_byte(PLAY+0x69,0xE0);
    Mmx6CoopRoster fallback;CHECK(fixed_roster(&fallback) && fallback.seat[1].form==0 && private_roster_bind(&fallback));
    psx_mod_write_byte(PLAY+0x5F,0x12);psx_mod_write_byte(PLAY+0x69,0xF0);
    enter_zero();CHECK(psx_mod_read_byte(PLAY+0x5E)==0);leave_zero(); /* Earned during this stage, no live rebind. */
    enrolled=0;CHECK(fixed_roster(&fallback) && fallback.seat[1].form==2 && private_roster_bind(&fallback));
    enter_zero();CHECK(psx_mod_read_byte(PLAY+0x5E)==2);leave_zero(); /* Next original reinit admission. */
    partner_x_armor=0;
}
/* R23 actual operand callback fixture. Native producer/words are checked
 * independently against original BIN24 by the existing Python source test. */
static uint8_t gate_target_before[sizeof ram];
static void gate_target_setup(CPUState *cpu,uint32_t address) {
    setup(cpu);private_draw=target_projection_call=0;
    const uint32_t boss=0x8008EF48u,parent=0x80093C98u,child=parent+0xA0u;
    psx_mod_write_byte(PLAY+12,18);psx_mod_write_byte(PLAY+13,0);
    psx_mod_write_word(PLAY+0x20,boss);psx_mod_write_word(0x800F7800u,boss);
    psx_mod_write_word(SCRATCH+0x80u,0x800F5F88u);psx_mod_write_word(SCRATCH+0x84u,0x800F60BCu);
    psx_mod_write_word(0x800F6074u,0x800F49F0u);psx_mod_write_word(0x800F6124u,0x800F0A24u);
    psx_mod_write_word(0x800F772Cu,0x800F3BFCu);psx_mod_write_word(0x800F7730u,0x800F3D74u);
    for(unsigned i=0;i<sizeof gate_homing_target_words/sizeof gate_homing_target_words[0];++i)
        psx_mod_write_word(0x800F3EFCu+4u*i,gate_homing_target_words[i]);
    for(unsigned i=0;i<sizeof gate_homing_producer_words/sizeof gate_homing_producer_words[0];++i)
        psx_mod_write_word(0x800F1944u+4u*i,gate_homing_producer_words[i]);
    psx_mod_write_byte(boss,0x41);psx_mod_write_byte(boss+1,59);psx_mod_write_byte(boss+4,1);
    psx_mod_write_byte(parent,0x41);psx_mod_write_byte(parent+1,26);psx_mod_write_byte(parent+2,1);
    psx_mod_write_byte(child,0x41);psx_mod_write_byte(child+1,26);psx_mod_write_byte(child+2,13);psx_mod_write_byte(child+4,1);
    psx_mod_write_byte(child+5,address==0x800F3F08u?0:1);psx_mod_write_word(child+0x7C,parent);
    psx_mod_write_word(child+8,3200u<<16);psx_mod_write_word(child+12,1000u<<16);
    psx_mod_write_word(PLAYER+8,1000u<<16);psx_mod_write_word(PLAYER+12,1000u<<16);
    psx_mod_write_byte(PLAYER+0x7A,0);psx_mod_write_byte(PLAYER+0xD0,0);psx_mod_write_byte(PLAYER+0xD4,0);
    /* P1 remains farther even after the signedY positive moves P2 to-250:
     * 2200^2 > 20^2+1250^2. Both heroes stay eligible. */
    put32(p2.body+8,3220u<<16);put32(p2.body+12,1020u<<16);
    cpu->gpr[17]=child;cpu->pc=address;
    cpu->gpr[2]=address==0x800F3F54u?0x80090000u:PLAYER;cpu->gpr[3]=1000;cpu->gpr[4]=1000;cpu->gpr[5]=1000;
}
static unsigned gate_target_ordinal;
static int gate_target_bad=-1;
static void gate_target_check(CPUState *cpu,uint32_t address,int changed,unsigned reg,int value) {
    memcpy(gate_target_before,ram,sizeof ram);PlayerContext partner=p2;CPUState expected=*cpu;
    unsigned calls_before=call_count;
    if(changed) {
        CHECK(intro_target_eligible(0) && intro_target_eligible(1));
        int x=(int16_t)psx_mod_read_half(cpu->gpr[17]+10),y=(int16_t)psx_mod_read_half(cpu->gpr[17]+14);
        int64_t px=(int16_t)psx_mod_read_half(PLAYER+10),py=(int16_t)psx_mod_read_half(PLAYER+14);
        int64_t gx=(int16_t)(le32(p2.body+8)>>16),gy=(int16_t)(le32(p2.body+12)>>16);
        CHECK((gx-x)*(gx-x)+(gy-y)*(gy-y)<(px-x)*(px-x)+(py-y)*(py-y));
        expected.gpr[reg]=(uint32_t)(int32_t)value;
    }
    unsigned ordinal=++gate_target_ordinal;
    PSXModFunctionEntryCallback callback=gate_homing_target;callback(cpu,address);
    if(memcmp(&expected,cpu,sizeof *cpu)) {
        fprintf(stderr,"Gate operand mismatch call=%u bad=%d site=%08X changed=%d expectedreg=%u value=%08X CPUbytes=%u\n",
            ordinal,gate_target_bad,address,changed,reg,(uint32_t)(int32_t)value,(unsigned)sizeof *cpu);
        fprintf(stderr,"eligible=%d/%d ready=%u enrolled=%u failed=%u inside=%d zero=%d/%d private=%d scene=%u/%u pause=%d mode=%u/%u stage=%u/%u child=%08X parent=%08X boss=%08X\n",
            intro_target_eligible(0),intro_target_eligible(1),ready,enrolled,failed,inside,zero_world,zero_projected,private_draw,scene_owner,scene_phase,pause_owner,
            psx_mod_read_byte(PLAY),psx_mod_read_byte(PLAY+1),psx_mod_read_byte(PLAY+12),psx_mod_read_byte(PLAY+13),cpu->gpr[17],psx_mod_read_word(cpu->gpr[17]+0x7C),psx_mod_read_word(PLAY+0x20));
        for(unsigned i=0;i<32;++i) {
            if(expected.gpr[i]!=cpu->gpr[i])fprintf(stderr,"gpr[%u] expected=%08X actual=%08X\n",i,expected.gpr[i],cpu->gpr[i]);
            if(expected.gte_data[i]!=cpu->gte_data[i])fprintf(stderr,"gte_data[%u] expected=%08X actual=%08X\n",i,expected.gte_data[i],cpu->gte_data[i]);
            if(expected.gte_ctrl[i]!=cpu->gte_ctrl[i])fprintf(stderr,"gte_ctrl[%u] expected=%08X actual=%08X\n",i,expected.gte_ctrl[i],cpu->gte_ctrl[i]);
        }
        if(expected.pc!=cpu->pc)fprintf(stderr,"pc expected=%08X actual=%08X\n",expected.pc,cpu->pc);
        if(expected.hi!=cpu->hi)fprintf(stderr,"hi expected=%08X actual=%08X\n",expected.hi,cpu->hi);
        if(expected.lo!=cpu->lo)fprintf(stderr,"lo expected=%08X actual=%08X\n",expected.lo,cpu->lo);
        const uint8_t *before=(const uint8_t*)&expected,*after=(const uint8_t*)cpu;
        for(unsigned i=0;i<sizeof *cpu;++i)if(before[i]!=after[i])fprintf(stderr,"CPUbyte[%u] expected=%02X actual=%02X\n",i,before[i],after[i]);
    }
    CHECK(!memcmp(&expected,cpu,sizeof *cpu));
    CHECK(!memcmp(gate_target_before,ram,sizeof ram) && !memcmp(&partner,&p2,sizeof p2));
    CHECK(call_count==calls_before && !state_track.count && !state_track.error);
}
static void native_gate_continuous_target_operands(void) {
    gate_target_ordinal=0;gate_target_bad=-1;
    CPUState cpu;const uint32_t sites[]={0x800F3F08u,0x800F3F54u,0x800F3FB4u,0x800F3FC4u};
    const unsigned regs[]={3,5,4,3};
    for(unsigned i=0;i<4;++i) {
        gate_target_setup(&cpu,sites[i]);gate_target_check(&cpu,sites[i],1,regs[i],i==1?1020:3220);
    }
    gate_target_setup(&cpu,0x800F3F54u);
    gate_target_check(&cpu,0x800F3F54u,1,5,1020);
    /* Target moves after emission: next native read receives its new signedY,
     * not the launch coordinate. Native +/-1 motion itself stays original. */
    put32(p2.body+12,(uint32_t)(-250*65536));cpu.gpr[5]=1000;
    gate_target_check(&cpu,0x800F3F54u,1,5,-250);
    /* Native flight need not keep its parent active/healthy or in phase1. */
    psx_mod_write_byte(0x80093C98u,0);psx_mod_write_byte(0x80093C9Cu,2);
    psx_mod_write_byte(0x80093CF4u,0);cpu.gpr[5]=1000;
    gate_target_check(&cpu,0x800F3F54u,1,5,-250);
    for(unsigned bad=0;bad<26;++bad) {
        gate_target_bad=(int)bad;
        gate_target_setup(&cpu,0x800F3F54u);uint32_t child=cpu.gpr[17],address=0x800F3F54u;
        if(bad==0)ready=0;if(bad==1)enrolled=0;if(bad==2)inside=1;if(bad==3)zero_world=1;
        if(bad==4)zero_projected=1;if(bad==5)private_draw=1;if(bad==6)scene_owner=1;
        if(bad==7)pause_owner=0;if(bad==8)psx_mod_write_byte(PLAY+12,17);
        if(bad==9)psx_mod_write_byte(PLAY+13,1);if(bad==10)life.status[1]=MMX6_COOP_ABSENT;
        if(bad==11)p2.body[0xD4]=1;if(bad==12)p2.body[0x5C]=0;
        if(bad==13)cpu.gpr[17]=child+1;if(bad==14)psx_mod_write_byte(child+2,12);
        if(bad==15)psx_mod_write_word(child+0x7C,child);if(bad==16)psx_mod_write_byte(0x80093C9Au,2);
        if(bad==17)psx_mod_write_byte(0x8008EF49u,55);if(bad==18)psx_mod_write_word(0x800F7800u,0);
        if(bad==19)psx_mod_write_word(0x800F3F4Cu,0);if(bad==20)psx_mod_write_word(0x800F1944u,0);
        if(bad==21)cpu.gpr[2]=PLAYER+4;if(bad==22)psx_mod_write_word(SCRATCH+0x84u,0);
        if(bad==23) { /* Next native BEQ is not one of the four operand hooks. */
            address=0x800F3F58u;
            for(unsigned i=0;i<4;++i)CHECK(address!=sites[i]);
        }
        if(bad==24)psx_mod_write_word(PLAYER+8,3201u<<16); /* Nearby P1 retains priority. */
        if(bad==25) {psx_mod_write_word(PLAYER+8,3180u<<16);psx_mod_write_word(PLAYER+12,1020u<<16);} /* Equal distance: P1. */
        gate_target_check(&cpu,address,0,0,0);
    }
    gate_target_bad=-2;
    gate_target_setup(&cpu,0x800F3FC4u);cpu.gpr[2]=PLAYER+4;
    gate_target_check(&cpu,0x800F3FC4u,0,0,0);
    gate_target_bad=-3;
    gate_target_setup(&cpu,0x800F3FB4u);psx_mod_write_byte(cpu.gpr[17]+6,1);
    gate_target_check(&cpu,0x800F3FB4u,0,0,0);
}
int main(void){
    opposite_resource_identity_projection();CHECK(PLAYER_MODE_OFFSET+PLAYER_PACKET_LIMIT*8u<=FRAME_ARENA);
    native_gate_continuous_target_operands();
    native_guest_weather_window();
    scene_owner_death_preserves_living_passenger();
    controller_pair_and_restoration();scene_passengers_keep_native_fixed_effects();native_nova_guest_update();lifetime_and_gates();menu_freeze_and_select_resume();native_menu_campaign_authority();draw_order_retained_packets_and_survivor();borrowed_menu_retains_primary_pools();borrowed_menu_restores_primary_sprite_sheet();native_giga_backup_survives_private_callbacks();clear_banks();
    deferred_shared_effect_owner_context();
    distant_surface_keeps_original_owner_view_and_retirement();
    deferred_falcon_flight_tracks_owner_and_body_pixels();
    deferred_X_muzzle_retains_shot_pool_and_counter();
    deferred_dash_effect_uses_allocating_body();
    deferred_ui_effect_retains_owner_atlas();clear_banks();
    arrival_draw_precedes_stage_callback();clear_banks();
    deferred_icon_effect_retains_zero_source();clear_banks();
    deferred_dash_effect_retains_zero_atlas();clear_banks();
    private_giga_shots_retain_zero_source();
    private_native_weapon_atlas_retains_zero_source();
    deferred_death_effect_retains_zero_source();clear_banks();
    native_X_armor_compressed_frame_and_survivor();clear_banks();
    distant_zero_saber_uses_native_owner_visibility();
    native_shared_boss_palette();
    native_shared_weather_palette();
    native_shared_portrait_palette();
    native_shared_dialogue_palette();
    native_working_palette_class_and_load_events();
    native_working_palette_rectangle();
    yammar_native_upload_coordinates();
    ray_native_upload_coordinates();
    shadow_native_upload_coordinates();
    native_shared_ride_ownership();native_both_ride_bindings_and_rosters();native_withdrawn_vehicle_scene_transport();
    native_shared_clear_admission_and_departure();
    native_sigma_transition_retains_living_pair();
    native_capsule_keeps_living_passenger();native_capsule_owner_contact_transaction();
    native_either_both_door_admission();
    native_both_door_ack_motion_and_release();native_hatch_missing_box_clearance();
    native_paired_arrival_barrier();
    native_scene_preserves_incoming_guest();
    native_scene_after_nonpaired_enrollment();
    native_checkpoint_preserves_completed_voluntary_absence();
    native_refight_return_preserves_living_personal_resources();
    native_optional_boss_damage_budget();native_optional_boss_shared_cooldown();native_default_private_boss_cookies();native_optional_private_boss_cooldowns();
    puts("private native effects actual-plugin call order, gates, lifetime projection and retained packet ownership PASS");return 0;}
