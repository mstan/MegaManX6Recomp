/* Actual plugin host restoration against explicit draw/sandbox contracts.
 * No real renderer, GPU checkpoint, watchdog or native-game qualification. */
#if defined(__has_include)
#if __has_include("debug_native_entry_context.h")
#ifndef PSX_NATIVE_ENTRY_CONTEXT_SERVICE
#define PSX_NATIVE_ENTRY_CONTEXT_SERVICE 1
#endif
#include "debug_native_entry_context.h"
#endif
#endif
#include "cpu_state.h"
#include "mmx6_coop_private_view_sdk_fixture.h"
static unsigned attack_camera_probe,attack_camera_calls;
static unsigned rearm_probe,rearm_calls;
static unsigned view_native_calls,view_gpu_words,view_callback_calls,view_refuse,view_abort;
static int view_native(CPUState *,uint32_t,uint32_t);
static int view_gpu(uint32_t,unsigned);
static unsigned arrival_probe,arrival_camera_calls;
static unsigned character_probe,character_calls;
static int32_t arrival_target;
static uint8_t arrival_body[0x158];
static unsigned weather_probe,weather_world_updates,weather_draws;
static uint32_t weather_x,weather_y;
static unsigned scenery_probe,scenery_draws[2];
static uint32_t scenery_y;
static unsigned quake_probe,quake_camera_calls,quake_draws[2];
static unsigned intro_camera_probe,intro_camera_calls;
static unsigned personal_view_probe,personal_view_draws[2],personal_view_clears[2],personal_view_cameras;
static unsigned personal_fade_at[2];
static uint32_t personal_fade_words[2][4],personal_resident_menu,personal_resident_palette;
static unsigned entering_view_probe,entering_view_draws[2];
static uint8_t quake_before[0x54],quake_after[0x54];
static const uint8_t quake_fields[]={0x36,0x37,0x3A,0x3B,0x3C,0x3D,0x3E,0x3F,0x45,0x46};
#define MMX6_TEST_NETPLAY_ACTIVE mmx6_view_sdk.online
#define MMX6_TEST_DISPATCH_CALL view_native
#define MMX6_TEST_PRIVATE_VIEW_GPU view_gpu
#define main unused_private_effects_fixture_main
#include "test_mmx6_coop_private_effects.c"
#undef main

#if PSX_DEBUG_NATIVE_CONTEXT_AVAILABLE
static PSXDebugNativeContextProvider view_registered_context;
static unsigned view_context_registrations,view_context_refuse;
int psx_debug_native_context_register(uint32_t id,PSXDebugNativeContextProvider provider,void *opaque) {
    CHECK(id==VIEW_CONTEXT_PROVIDER && provider==private_view_entry_context && !opaque);
    ++view_context_registrations;
    if(view_context_refuse)return 0;
    view_registered_context=provider;return 1;
}
#endif

static void disturb_host(void) {
    p2.body[0x5C]=7;p1.body[0x5C]=8;join_phase=3;previous_input=0x1234;
    memset(saved_overlay,0x91,sizeof saved_overlay);memset(saved_play,0x92,sizeof saved_play);
    memset(saved_camera,0x93,sizeof saved_camera);memset(saved_resources,0x94,sizeof saved_resources);
    saved_palette_dirty=1;ride_call=7;pickup_call=6;solid_call=5;zero_projected=1;
}
static int view_native(CPUState *cpu,uint32_t address,uint32_t ret) {
    (void)ret;++view_native_calls;
    if(address==0x80029D18u && rearm_probe) {
        ++rearm_calls;CHECK(inside && state_track.count>=3 && !state_track.error);
        for(unsigned i=0;i<5 && rearm_probe<5;++i) {
            uint32_t at=0x800FA214u+i*8u;unsigned flags=psx_mod_read_byte(at+3),latch=flags&0xF0u;
            if(!(psx_mod_read_byte(at)&0x81u) && (latch==0x10 || latch==0x30 || latch==0x50))
                psx_mod_write_byte(at+3,(uint8_t)(flags+0x10u));
        }
        if(rearm_probe==2)psx_mod_write_byte(0x800FA214u,1); /* native allocation wins */
        if(rearm_probe==3)psx_mod_write_byte(0x800FA214u,0x80); /* permanent disable wins */
        if(rearm_probe==4)psx_mod_write_word(0x8007349Cu,0x800FB000u); /* room change wins */
        cpu->gpr[2]=0x42;return 1;
    }
    if(address==0x8002012Cu && attack_camera_probe) {
        ++attack_camera_calls;
        int dx=(int16_t)(psx_mod_read_half(PLAYER+10)-psx_mod_read_half(VIEW_CAMERA+10));
        /* Original801EE010..58 rejects before advancing PLAYER+7. */
        if((uint16_t)(dx+16)<353u)psx_mod_write_byte(PLAYER+7,(uint8_t)(psx_mod_read_byte(PLAYER+7)+1));
        CHECK(psx_mod_read_half(VIEW_CAMERA+14)==538);
        return 1;
    }
    if(address==CHARACTER_UPDATE && character_probe) {
        ++character_calls;
        unsigned phase=psx_mod_read_byte(PLAY+2);
        uint16_t edge=psx_mod_read_half(CHARACTER_PAD+4);
        if(phase==4)psx_mod_write_byte(PLAY+2,5);
        if(phase==5 && (edge&0x840u)) {
            unsigned form=psx_mod_read_byte(CHARACTER_LIST+psx_mod_read_byte(PLAY+0x30));
            psx_mod_write_byte(PLAY+0x5E,(uint8_t)form);
            psx_mod_write_byte(PLAY+0x38,form==5);
            psx_mod_write_byte(PLAY+2,7);
        } else if(phase==5 && (edge&0x10u))psx_mod_write_byte(PLAY+2,9);
        return 1;
    }
    if(address==VIEW_DRAW_OT) { cpu->gpr[2]=0xC0DE;return 1; }
    if(address==0x80066150u)return 1;
    if(address==0x8006663Cu) {
        CHECK(private_draw && cpu->gpr[4]==view_buffer+0x70u && cpu->gpr[5]==32);
        /* Original ClearOTagR: first terminator, then31 backward links. */
        for(unsigned i=0;i<32;++i)psx_mod_write_word(cpu->gpr[4]+i*4u,
            i?(cpu->gpr[4]+(i-1u)*4u)&0xFFFFFFu:0xFFFFFFu);
        if(personal_view_probe)++personal_view_clears[private_seat];return 1;
    }
    if(address==0x80026028u && personal_view_probe) {
        CHECK(private_draw && personal_pass && personal_rendering && personal_seat==private_seat);
        CHECK(cpu->gpr[4]==PERSONAL_MENU && psx_mod_read_byte(PLAYER+2)==private_seat);
        CHECK(!memcmp(memory(PERSONAL_MENU),personal_menu[private_seat].native,0x3C));
        CHECK(psx_mod_read_byte(PERSONAL_WEAPON)==personal_menu[private_seat].original_weapon);
        CHECK(psx_mod_read_word(SCRATCH+0x3C)==(private_seat?menu_assembly:personal_resident_menu));
        CHECK(psx_mod_read_word(SCRATCH+0x28)==(private_seat?active_palette:personal_resident_palette));
        CHECK(psx_mod_read_word(view_buffer+0x70u)==0xFFFFFFu);
        CHECK(psx_mod_read_word(view_buffer+0xECu)==((view_buffer+0xE8u)&0xFFFFFFu));
        /* Real native draw consumes its own font/menu atlas and working
         * palette. This unit observes the modeled transfer, not GL pixels. */
        CHECK(test_vram[256u*1024u+896u]==(uint16_t)(0x1100u+private_seat*0x100u));
        CHECK(test_vram[256u*1024u+960u]==(uint16_t)(0x1101u+private_seat*0x100u));
        CHECK(test_vram[480u*1024u]==psx_mod_read_half(psx_mod_read_word(SCRATCH+0x28)));
        psx_mod_write_word(0x800C1200u,0xA0B00000u+private_seat);
        cpu->gpr[8]=0xDEAD0000u+private_seat;
        ++personal_view_draws[private_seat];return 1;
    }
    if(address==0x8002927Cu || address==0x8002935Cu || address==0x800293CCu) {
        if(personal_view_probe)++personal_view_cameras;
        CHECK(life.status[private_seat]==MMX6_COOP_ALIVE || life.status[private_seat]==MMX6_COOP_JOINING);
        if(intro_camera_probe && address==0x8002927Cu) {
            CHECK(private_draw && private_seat==1);
            /* Native camera callee contract: consume the authored request
             * limits and clamp this view, rather than an unused publication. */
            if(intro_camera_probe==1) {
                CHECK(psx_mod_read_half(VIEW_CAMERA+0x28)==704 && psx_mod_read_half(VIEW_CAMERA+0x2A)==704);
                psx_mod_write_half(VIEW_CAMERA+0x20,704);psx_mod_write_half(VIEW_CAMERA+0x22,704);
                psx_mod_write_word(VIEW_CAMERA+12,704u<<16);
            } else {
                CHECK(psx_mod_read_half(VIEW_CAMERA+0x28)==944 && psx_mod_read_half(VIEW_CAMERA+0x2A)==896);
                /* Exact original2912C BGEZ branch: preserve its signed
                 * PLAYER.Y-CAMERA.Y-offset result, even far from target896.
                 * This fixture must not replace the native formula. */
                int16_t value=(int16_t)(psx_mod_read_half(PLAYER+14)-psx_mod_read_half(VIEW_CAMERA+14)-psx_mod_read_half(VIEW_CAMERA+0x2C));
                CHECK(value==75);psx_mod_write_half(VIEW_CAMERA+0x22,(uint16_t)value);
            }
            ++intro_camera_calls;
        }
        if(quake_probe && address==0x8002927Cu) {
            CHECK(private_draw && private_seat==1);
            /* Native camera must receive the world's input, not its already
             * decremented result. This explicit callee contract reproduces
             * the observed 8->7 versus incorrect 7->6 regression. */
            CHECK((psx_mod_read_byte(VIEW_CAMERA+0x34)&0x11)==(quake_before[0x34]&0x11));
            CHECK((psx_mod_read_byte(VIEW_CAMERA+0x34)&~0x11u)==0x80u);
            for(unsigned i=0;i<sizeof quake_fields;++i) {
                unsigned at=quake_fields[i];CHECK(psx_mod_read_byte(VIEW_CAMERA+at)==quake_before[at]);
                psx_mod_write_byte(VIEW_CAMERA+at,quake_after[at]);
            }
            psx_mod_write_byte(VIEW_CAMERA+0x34,quake_after[0x34]);
            psx_mod_write_word(VIEW_CAMERA+12,le32(quake_after+12));
            ++quake_camera_calls;
        }
        if(arrival_probe) {
            CHECK(private_draw && private_seat==1);
            CHECK(psx_mod_read_word(PLAYER+12)==(uint32_t)arrival_target);
            CHECK(psx_mod_read_word(PLAYER+0x1C)==(uint32_t)arrival_target);
            ++arrival_camera_calls;
        }
        return 1;
    }
    CHECK(address==0x80025FB0u && private_draw);
    if(entering_view_probe) {
        CHECK(!personal_initialized && (psx_mod_read_byte(PLAY+1)==1 ||
            (psx_mod_read_byte(PLAY+1)==2 && personal_active && !personal_menu[0].native[4] && personal_menu[0].native[5]<=1)));
        CHECK(psx_mod_read_word(view_buffer+0x70u)==0xFFFFFFu);
        CHECK(psx_mod_read_word(view_buffer+0xECu)==((view_buffer+0xE8u)&0xFFFFFFu));
        for(unsigned i=0;i<sizeof view_cameras[0];++i)
            if(i%0x54u!=0x4Cu)CHECK(psx_mod_read_byte(VIEW_CAMERA+i)==view_cameras[private_seat][i]);
        ++entering_view_draws[private_seat];
    }
    if(scenery_probe) {
        CHECK(psx_mod_read_word(VIEW_CAMERA+0x54+12)==scenery_y);
        ++scenery_draws[private_seat];
    }
    if(quake_probe) {
        CHECK(psx_mod_read_word(VIEW_CAMERA+12)==le32(quake_after+12));
        CHECK(psx_mod_read_byte(VIEW_CAMERA+0x34)==quake_after[0x34]);
        for(unsigned i=0;i<sizeof quake_fields;++i)
            CHECK(psx_mod_read_byte(VIEW_CAMERA+quake_fields[i])==quake_after[quake_fields[i]]);
        ++quake_draws[private_seat];
    }
    if(weather_probe) {
        CHECK(psx_mod_read_word(VIEW_CAMERA+0x54+8)==weather_x);
        CHECK(psx_mod_read_word(VIEW_CAMERA+0x54+12)==weather_y);
        CHECK(psx_mod_read_byte(VIEW_CAMERA+0x54+0x4C)==1);
        ++weather_draws;
    }
    if(arrival_probe)CHECK(!memcmp(p2.body,arrival_body,sizeof arrival_body));
    ++view_callback_calls;disturb_host();if(view_refuse)failed=1;return 1;
}
static int view_gpu(uint32_t value,unsigned source) {
    if(!private_draw)return 0;
    if(source)CHECK(!value);else ++view_gpu_words;
    if(!source && personal_view_probe) {
        unsigned *at=&personal_fade_at[private_seat];
        if(*at || (value>>24)==0xE1u) {
            CHECK(*at<4);personal_fade_words[private_seat][(*at)++]=value;
        }
    }
    return 1;
}
static int model_transaction(CPUState *cpu,PSXModRenderPassFn callback,void *user,uint32_t eye) {
    /* Only this unit model restores its guest RAM/CPU. Real SDK restoration
     * and publication require separate runtime tests. */
    static uint8_t guest_ram[sizeof ram];CPUState saved=*cpu;
    static uint16_t guest_vram[1024*512];
    memcpy(guest_ram,ram,sizeof ram);
    /* Explicit unit checkpoint only. This does not exercise the renderer's
     * real GL upload journal or prove its physical GPU restoration. */
    if(personal_view_probe)memcpy(guest_vram,test_vram,sizeof test_vram);
    int ok;
    if(view_abort) { disturb_host();inside=1;state_track.count=2;state_track.error=1;ok=0; }
    else ok=callback(cpu,user,eye);
    memcpy(ram,guest_ram,sizeof ram);
    if(personal_view_probe)memcpy(test_vram,guest_vram,sizeof test_vram);
    *cpu=saved;return ok;
}
static void prepare_view(CPUState *cpu,int online,int split) {
    setup(cpu);mmx6_view_sdk_reset();mmx6_view_sdk.online=online;
    /* The patterned resource fixture is an idle player, not a script hold. */
    psx_mod_write_byte(PLAYER+0xD0,0);psx_mod_write_byte(PLAYER+0xD4,0);
    psx_mod_write_byte(PLAYER+0x7A,0);
    view_native_calls=view_gpu_words=view_callback_calls=view_refuse=view_abort=0;
    arrival_probe=arrival_camera_calls=0;
    weather_probe=weather_world_updates=weather_draws=0;
    scenery_probe=scenery_draws[0]=scenery_draws[1]=0;
    quake_probe=quake_camera_calls=quake_draws[0]=quake_draws[1]=0;
    intro_camera_probe=intro_camera_calls=intro_camera_valid=0;
    personal_view_probe=personal_view_cameras=0;
    entering_view_probe=0;memset(entering_view_draws,0,sizeof entering_view_draws);
    memset(personal_view_draws,0,sizeof personal_view_draws);memset(personal_view_clears,0,sizeof personal_view_clears);
    memset(personal_fade_at,0,sizeof personal_fade_at);memset(personal_fade_words,0,sizeof personal_fade_words);
    memset(intro_camera_requests,0,sizeof intro_camera_requests);
    view_quake_valid=0;
    inside=player_call=stage_call=zero_world=world_render=hud_call=ride_call=pickup_call=solid_call=0;
    private_draw=private_seat=view_call=zero_projected=0;local_split=split;independent_views=1;
    if(online && split)CHECK(psx_mod_set_render_pass_netplay(1));
    view_buffer=VIEW_BUFFER;view_pending=view_valid=1;view_menu_history=0;
    view_menu_stage=psx_mod_read_byte(PLAY+12);view_menu_section=psx_mod_read_byte(PLAY+13);
    view_menu_checkpoint=psx_mod_read_byte(PLAY+0x1D);
    psx_mod_write_word(0x8009B7A0u,view_buffer);
    psx_mod_write_half(view_buffer+0x18,320);psx_mod_write_half(view_buffer+0x1A,240);
    cpu->gpr[31]=0x80012128u;cpu->gpr[4]=view_buffer+0xEC;
    mmx6_view_sdk.transaction=model_transaction;
}
static void context_equal(const PrivateViewContext *expected) {
    PrivateViewContext actual;memset(&actual,0,sizeof actual);private_context_save(&actual);
    CHECK(!memcmp(expected,&actual,sizeof actual));
}
static void presentation_restore(int online,int split,unsigned refuse,unsigned abort) {
    CPUState cpu;prepare_view(&cpu,online,split);
    PrivateViewContext before;memset(&before,0,sizeof before);private_context_save(&before);
    view_refuse=refuse;view_abort=abort;
    uint8_t camera[sizeof view_cameras[1]];memcpy(camera,view_cameras[1],sizeof camera);
    CHECK(independent_present(&cpu,VIEW_DRAW_OT));
    CHECK(cpu.gpr[2]==0xC0DE && !view_call && !private_draw && !view_pending);
    context_equal(&before);
    if(refuse || abort)CHECK(!memcmp(camera,view_cameras[1],sizeof camera));
    CHECK(split?mmx6_view_sdk.pair_calls==1:mmx6_view_sdk.view_calls==1);
    if(!abort)CHECK(view_callback_calls==(split && !refuse?2u:1u));
    CHECK(!mmx6_view_sdk.busy);
}
static int forbidden_callback(CPUState *cpu,void *user,uint32_t eye) {
    (void)cpu;(void)user;(void)eye;CHECK(0);return 0;
}
static void native_stage_layout_before_enrollment(void) {
    static const uint8_t modes[]={8,9,10,20};
    for(int online=0;online<2;++online)for(int split=0;split<2;++split)
        for(unsigned i=0;i<sizeof modes/sizeof *modes;++i) {
            CPUState cpu;prepare_view(&cpu,online,split);
            if(split)CHECK(psx_mod_set_local_pair_presentation(1));
            enrolled=arrival_pair=view_pending=view_valid=0;
            psx_mod_write_byte(PLAY,modes[i]);
            CPUState original=cpu;uint32_t digest=state_digest();
            static uint8_t original_ram[sizeof ram];memcpy(original_ram,ram,sizeof ram);
            CHECK(!independent_present(&cpu,VIEW_DRAW_OT));
            CHECK(mmx6_view_sdk.pair_enabled==(!online && split));
            CHECK(!view_native_calls && !view_callback_calls && !mmx6_view_sdk.pair_calls);
            CHECK(!memcmp(&original,&cpu,sizeof cpu) && !memcmp(original_ram,ram,sizeof ram));
            CHECK(state_digest()==digest && !view_pending && !view_valid && !enrolled && !arrival_pair);
        }
}
static void retained_presentation_lifetime(void) {
    for(unsigned gate=0;gate<6;++gate) {
        CPUState cpu;prepare_view(&cpu,1,1);CHECK(psx_mod_set_local_pair_presentation(1));
        view_pending=0;
        if(gate==0)psx_mod_write_byte(PLAY,20);
        if(gate==1)enrolled=0;
        if(gate==2)failed=1;
        if(gate==3)independent_views=0;
        if(gate==4) { psx_mod_write_byte(PLAY,20);view_pending=1;view_buffer=VIEW_BUFFER+VIEW_STRIDE; }
        if(gate==5) {
            failed=1;personal_active=personal_initialized=1;
            personal_menu[0].native[4]=personal_menu[0].native[5]=1;
            CHECK(personal_menus_active());
        }
        uint8_t cameras[sizeof view_cameras];memcpy(cameras,view_cameras,sizeof cameras);
        CHECK(!independent_present(&cpu,VIEW_DRAW_OT) && !mmx6_view_sdk.pair_enabled);
        CHECK(!view_native_calls && !memcmp(cameras,view_cameras,sizeof cameras));
        personal_reset();enrolled=independent_views=1;failed=0;psx_mod_write_byte(PLAY,10);
        view_buffer=VIEW_BUFFER;view_pending=1;
        CHECK(independent_present(&cpu,VIEW_DRAW_OT) && mmx6_view_sdk.pair_enabled);
    }
    for(unsigned phase=0;phase<3;++phase) {
        CPUState cpu;prepare_view(&cpu,1,1);CHECK(psx_mod_set_local_pair_presentation(1));
        psx_mod_write_byte(PLAY+1,(uint8_t)phase);view_pending=view_valid=0;
        life.status[0]=MMX6_COOP_FALLEN;
        CHECK(!independent_present(&cpu,VIEW_DRAW_OT) && mmx6_view_sdk.pair_enabled);
    }
}
static void local_survivor_uses_current_native_screen(void) {
    for(unsigned seat=0;seat<2;++seat) {
        CPUState cpu;prepare_view(&cpu,0,1);
        life.status[seat]=MMX6_COOP_FALLEN;
        independent_survivor_begin();
        CHECK(mmx6_view_sdk.pair_enabled && view_valid && view_pending);
        if(!seat) {
            inside=zero_world=1;
            CHECK(world_draw_filter(&cpu,0x80025FB0u));
            CHECK(!view_native_calls); /* No stage draw using Zero's resource projection. */
            inside=zero_world=0;
        }
        independent_world_begin();CHECK(view_pending && view_valid);
        CHECK(!memcmp(view_cameras[0],memory(VIEW_CAMERA),sizeof view_cameras[0]));
        CHECK(!memcmp(view_cameras[0],view_cameras[1],sizeof view_cameras[0]));
        uint32_t digest=state_digest();
        CHECK(independent_present(&cpu,VIEW_DRAW_OT) && mmx6_view_sdk.pair_enabled);
        CHECK(mmx6_view_sdk.pair_calls==1 && state_digest()==digest && !failed);
    }
    CPUState cpu;prepare_view(&cpu,0,1);independent_survivor_begin();
    CHECK(view_valid); /* Two living heroes keep their independent views. */
}
static void defaults_and_scope(void) {
    CPUState cpu;prepare_view(&cpu,0,0);mmx6_view_sdk_reset();
    char value[24];CHECK(psx_mod_current_option_value("cameras",value,sizeof value) && !strcmp(value,"unified"));
    CHECK(!psx_mod_current_option_value("unknown",value,sizeof value));
    CHECK(!psx_mod_current_option_value("local_cameras",value,2));
    independent_activate();CHECK(!independent_views && local_split && mmx6_view_sdk.pair_enabled && mmx6_view_sdk.aspect_calls==1);
    mmx6_view_sdk.local_cameras="split";independent_activate();
    CHECK(independent_views && local_split && mmx6_view_sdk.pair_enabled && mmx6_view_sdk.aspect_calls==2);
    PSXModStereoFrame pair={sizeof pair,1,0,0,320,240};PSXModRenderPass rect={sizeof rect,0,0,0,320,240};
    CHECK(!psx_mod_render_local_pair(&cpu,&pair,forbidden_callback,NULL)); /* no modeled backend */
    mmx6_view_sdk.transaction=model_transaction;
    CHECK(!psx_mod_render_local_view(&cpu,&rect,forbidden_callback,NULL)); /* offline */
    mmx6_view_sdk.online=1;CHECK(!psx_mod_set_local_pair_presentation(1));
    CHECK(!psx_mod_render_local_pair(&cpu,&pair,forbidden_callback,NULL)); /* netplay */
    mmx6_view_sdk.cameras="independent";independent_activate();
    CHECK(independent_views && !local_split && !mmx6_view_sdk.pair_enabled && !mmx6_view_sdk.netplay_allowed);
    mmx6_view_sdk.cameras="split";independent_activate();
    CHECK(independent_views && local_split && mmx6_view_sdk.pair_enabled && mmx6_view_sdk.netplay_allowed);
    mmx6_view_sdk_reset();mmx6_view_sdk.online=1;independent_activate();
    CHECK(independent_views && !local_split && !mmx6_view_sdk.pair_enabled && !mmx6_view_sdk.netplay_allowed);
    /* A legacy shared choice and missing option both retain an own-HUD view;
     * offline shared camera preferences remain covered above. */
    mmx6_view_sdk.cameras="option-not-readable-in-this-sdk";
    CHECK(!psx_mod_current_option_value("cameras",value,sizeof value));independent_activate();
    CHECK(independent_views && !local_split && !mmx6_view_sdk.pair_enabled);
}
static void native_placement_rearm_belongs_to_both_views(void) {
    for(unsigned variant=1;variant<=6;++variant) {
        CPUState cpu;prepare_view(&cpu,0,1);rearm_probe=variant;rearm_calls=0;
        psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+1,0);
        psx_mod_write_byte(PLAY+12,0);psx_mod_write_byte(PLAY+13,0);
        psx_mod_write_byte(PLAY+0x10,0);psx_mod_write_byte(PLAY+0x1C,0);
        p2.body[0]=p2.body[4]=1;p2.body[5]=2;p2.body[0x5C]=32;
        p2.body[0xCC]=p2.body[0xE0]=0;put32(p2.body+8,2160u<<16);put32(p2.body+12,1114u<<16);
        if(variant==6)put32(p2.body+8,144u<<16);
        psx_mod_write_word(VIEW_CAMERA+8,0);psx_mod_write_word(VIEW_CAMERA+12,896u<<16);
        psx_mod_write_byte(VIEW_CAMERA+4,1);psx_mod_write_byte(VIEW_CAMERA+0x44,1);
        psx_mod_write_half(VIEW_CAMERA+0x30,160);psx_mod_write_half(VIEW_CAMERA+0x32,160);
        psx_mod_write_half(VIEW_CAMERA+0x2C,96);
        psx_mod_write_half(VIEW_CAMERA+0x1C,3000);psx_mod_write_half(VIEW_CAMERA+0x1E,0);
        psx_mod_write_half(VIEW_CAMERA+0x20,1500);psx_mod_write_half(VIEW_CAMERA+0x22,0);
        psx_mod_write_word(0x8007349Cu,0x800FA214u);psx_mod_write_word(0x8002A2F4u,0xA2420003u);
        const uint8_t flags[]={0x10,0x30,0x50,0x20,0x30};
        for(unsigned i=0;i<5;++i) {
            uint32_t at=0x800FA214u+i*8u;
            psx_mod_write_word(at,(uint32_t)flags[i]<<24|0x100u|(i==2?1u:i==4?0x80u:0u));
            psx_mod_write_half(at+4,i==1?4000:2160);psx_mod_write_half(at+6,1080);
        }
        psx_mod_write_word(0x800FA214u+40u,0x0F000000u);
        CHECK(guest_placement_scan(&cpu,0x80029D18u));
        CHECK(rearm_calls==1 && cpu.gpr[2]==0x42 && !inside && !state_track.count && !state_track.error);
        CHECK(psx_mod_read_byte(0x800FA217u)==(variant==1 || variant==5?0x10:0x20));
        CHECK(psx_mod_read_byte(0x800FA21Fu)==0x40); /* outside both views rearms */
        CHECK(psx_mod_read_byte(0x800FA227u)==0x50); /* active stays active */
        CHECK(psx_mod_read_byte(0x800FA22Fu)==0x20); /* already rearmed stays so */
        CHECK(psx_mod_read_byte(0x800FA237u)==0x30); /* disabled stays disabled */
    }
    rearm_probe=0;
}
#ifdef MMX6_COOP_VIEW_ENTRY_CONTEXT
static void native_camera_context(void) {
    CPUState cpu;prepare_view(&cpu,0,1);
    PSXDebugNativeContextWords out,sentinel;memset(&sentinel,0xA5,sizeof sentinel);
    out=sentinel;
    CHECK(!private_view_entry_context(0x80025FB0u,&out,NULL)); /* canonical entry */
    CHECK(!private_view_entry_context(0x80026D44u,&out,NULL));
    CHECK(!memcmp(&out,&sentinel,sizeof out));
    private_draw=1;private_seat=2;
    CHECK(!private_view_entry_context(0x80025FB0u,&out,NULL));
    private_seat=0;view_valid=0;
    CHECK(!private_view_entry_context(0x80025FB0u,&out,NULL));view_valid=1;
    CHECK(!private_view_entry_context(0x8002927Cu,&out,NULL));
    CHECK(!private_view_entry_context(0,&out,NULL));
    CHECK(!private_view_entry_context(0x80025FB0u,NULL,NULL));
    CHECK(!memcmp(&out,&sentinel,sizeof out));
    for(unsigned seat=0;seat<2;++seat) {
        private_seat=seat;frame_count=1234;
        uint8_t *camera=view_cameras[seat];memset(camera,0,sizeof view_cameras[seat]);
        uint32_t x=0x11C00010u+seat,y=0x02C40020u-seat;
        put32(camera+8,x);put32(camera+12,y);camera[0x34]=seat?0x10:1;
        camera[0x37]=(uint8_t)(8-seat);camera[0x46]=(uint8_t)(4+seat);camera[0x3F]=seat?0x84:4;
        PrivateViewContext before;memset(&before,0,sizeof before);private_context_save(&before);
        uint8_t cameras[sizeof view_cameras];memcpy(cameras,view_cameras,sizeof cameras);
        static uint8_t before_ram[sizeof ram],before_extra[sizeof extra];
        memcpy(before_ram,ram,sizeof ram);memcpy(before_extra,extra,sizeof extra);
        CPUState prior_cpu=cpu;unsigned calls_before=view_native_calls,words_before=view_gpu_words;
        out=sentinel;
#if PSX_DEBUG_NATIVE_CONTEXT_AVAILABLE
        CHECK(private_view_entry_context(0x80025FB0u,&out,NULL));
        CHECK(out.state0==1234 && out.state1==x && out.state2==y);
        CHECK(out.flags==(1u | seat<<1 | (seat?8u:4u) | (uint32_t)(8-seat)<<8 |
            (uint32_t)(4+seat)<<16 | (uint32_t)(seat?0x84u:4u)<<24));
        put32(camera+0x54+8,x+17);put32(camera+0x54+12,y+23);
        CHECK(private_view_entry_context(0x80026D44u,&out,NULL));
        CHECK(out.flags==(0x81u | seat<<1) && out.state0==1234 &&
              out.state1==x+17 && out.state2==y+23);
        put32(camera+0x54+8,0);put32(camera+0x54+12,0);
#else
        CHECK(!private_view_entry_context(0x80025FB0u,&out,NULL));
        CHECK(!private_view_entry_context(0x80026D44u,&out,NULL));
        CHECK(!memcmp(&out,&sentinel,sizeof out)); /* production unavailable */
#endif
        context_equal(&before);
        CHECK(!memcmp(cameras,view_cameras,sizeof cameras) && !memcmp(before_ram,ram,sizeof ram) &&
            !memcmp(before_extra,extra,sizeof extra) && !memcmp(&prior_cpu,&cpu,sizeof cpu));
        CHECK(private_draw==1 && private_seat==seat && frame_count==1234 && view_valid &&
            view_native_calls==calls_before && view_gpu_words==words_before);
    }
    private_draw=0;
#if PSX_DEBUG_NATIVE_CONTEXT_AVAILABLE
    mmx6_view_sdk_reset();mmx6_view_sdk.local_cameras="split";view_context_refuse=1;
    view_registered_context=NULL;unsigned registrations=view_context_registrations;
    independent_activate();
    CHECK(view_context_registrations==registrations+1 && !view_registered_context &&
        independent_views && local_split && !failed); /* optional failure */
    view_context_refuse=0;independent_activate();
    CHECK(view_registered_context==private_view_entry_context && !failed);
    out=sentinel;CHECK(!view_registered_context(0x80025FB0u,&out,NULL));
#endif
}
#endif
static void reentry(void) {
    CPUState cpu;prepare_view(&cpu,0,1);
    view_call=1;CHECK(!independent_present(&cpu,VIEW_DRAW_OT));
    view_call=0;private_draw=1;CHECK(!independent_present(&cpu,VIEW_DRAW_OT));
    private_draw=0;state_track.count=1;CHECK(!independent_present(&cpu,VIEW_DRAW_OT));
    state_track.count=0;state_track.error=1;CHECK(!independent_present(&cpu,VIEW_DRAW_OT));
    CHECK(!view_native_calls && !mmx6_view_sdk.pair_calls && !mmx6_view_sdk.view_calls && view_pending);
}
static void prepare_door_view(CPUState *cpu,int online,int split,unsigned phase) {
    prepare_view(cpu,online,split);
    both_doors=1;scene_owner=1;scene_phase=0;both_door_members=3;
    both_door_actor=0x800C1220u;both_door_origin=0x800FA2A4u;
    both_door_extents[0][0]=both_door_extents[1][0]=-11;both_door_extents[0][1]=both_door_extents[1][1]=11;
    psx_mod_write_byte(both_door_actor,1);psx_mod_write_byte(both_door_actor+1,8);
    psx_mod_write_byte(both_door_actor+4,1);psx_mod_write_byte(both_door_actor+5,(uint8_t)phase);
    psx_mod_write_word(both_door_actor+0x10,both_door_origin);
    psx_mod_write_byte(PLAYER+0xD4,phase==1?1:0xFE);p2.body[0xD4]=phase==1?1:0xFE;
    psx_mod_write_byte(PLAY+0x10,1);
    psx_mod_write_byte(PLAY+0x1C,1); /* Original door hold persists through traversal. */
    frame_count=1;view_pending=view_valid=0;
}
static void admitted_door_views(int online,int split) {
    for(unsigned both=0;both<2;++both)for(unsigned phase=1;phase<=3;++phase)for(unsigned owner=1;owner<=2;++owner) {
        CPUState cpu;prepare_door_view(&cpu,online,split,phase);scene_owner=owner;
        both_doors=both;
        CHECK(independent_door_context());independent_world_begin();CHECK(view_valid && view_pending);
        PrivateViewContext before;memset(&before,0,sizeof before);private_context_save(&before);
        CHECK(independent_present(&cpu,VIEW_DRAW_OT));context_equal(&before);
        CHECK(both_door_members==3 && scene_owner==owner && !scene_phase && !failed);
        CHECK(psx_mod_read_byte(PLAY+0x10)==1 && psx_mod_read_byte(PLAY+0x1C)==1 &&
            frame_count==1 && !state_track.count && !state_track.error);
    }
    for(unsigned gate=0;gate<18;++gate) {
        CPUState cpu;prepare_door_view(&cpu,online,split,2);
        switch(gate) {
        case 0:both_door_members=0;break;
        case 1:both_door_members=1;break;
        case 2:scene_phase=1;break;
        case 3:psx_mod_write_byte(both_door_actor,0);break;
        case 4:psx_mod_write_word(both_door_actor+0x10,both_door_origin+8);break;
        case 5:psx_mod_write_byte(both_door_actor+1,7);break;
        case 6:psx_mod_write_byte(both_door_actor+4,2);break;
        case 7:psx_mod_write_byte(both_door_actor+5,0);break;
        case 8:psx_mod_write_byte(both_door_actor+5,4);break;
        case 9:psx_mod_write_byte(PLAYER+0xD4,0);p2.body[0xD4]=0;break;
        case 10:life.status[0]=MMX6_COOP_DYING;break;
        case 11:life.status[1]=MMX6_COOP_JOINING;break;
        case 12:pause_owner=0;psx_mod_write_byte(PLAY+1,1);break;
        case 13:scene_owner=0;break; /* A world hold without an authenticated door refuses. */
        case 14:psx_mod_write_byte(PLAY+1,2);break;
        case 15:clear_phase=1;break;
        case 16:psx_mod_write_byte(PLAY,9);break;
        case 17:both_door_actor+=4;break;
        }
        independent_world_begin();CHECK(!view_valid && !view_pending && !view_native_calls);
    }
}
static void native_door_scene_handoff(int online,int split) {
    for(unsigned both=0;both<2;++both)for(unsigned owner=1;owner<=2;++owner)
    for(unsigned gate=0;gate<7;++gate) {
        CPUState cpu;prepare_door_view(&cpu,online,split,4);both_doors=both;scene_owner=owner;
        psx_mod_write_byte(PLAYER+0xD4,0);p2.body[0xD4]=0;
        /* Closed door by itself still requires its original identity. */
        if(owner==1)psx_mod_write_byte(PLAYER+0x7A,1);else p2.body[0x7A]=1;
        if(gate==1)psx_mod_write_byte(both_door_actor+5,3);
        else if(gate==2)psx_mod_write_byte(PLAYER+0xD4,1);
        else if(gate==3)p2.body[0xD4]=1;
        else if(gate==4)psx_mod_write_word(both_door_actor+0x10,both_door_origin+8);
        else if(gate==5)both_door_members=0;
        else if(gate==6)psx_mod_write_byte(both_door_actor+4,2);
        CHECK(independent_scene_context()==!gate);
        if(gate)continue;
        CHECK(!independent_door_context());independent_world_begin();CHECK(view_valid && view_pending);
        PrivateViewContext before;memset(&before,0,sizeof before);private_context_save(&before);
        CHECK(independent_present(&cpu,VIEW_DRAW_OT));context_equal(&before);
        CHECK(both_door_members==3 && scene_owner==owner && !scene_phase && !failed);
        CHECK(psx_mod_read_byte(PLAY+0x10)==1 && psx_mod_read_byte(PLAY+0x1C)==1);
    }
    for(unsigned owner=1;owner<=2;++owner) {
        CPUState cpu;prepare_door_view(&cpu,online,split,4);scene_owner=owner;
        psx_mod_write_byte(PLAYER+0xD4,0);p2.body[0xD4]=0;
        if(owner==1)psx_mod_write_byte(PLAYER+0xD0,20);else p2.body[0xD0]=20;
        /* A current story request survives retirement of the old door slot
         * and an omitted world producer, without advancing its simulation. */
        psx_mod_write_byte(both_door_actor,0);
        psx_mod_write_word(VIEW_CAMERA+8,700u<<16);
        put32(view_cameras[1]+8,100u<<16);view_pending=0;
        CHECK(independent_door_story_context());
        PrivateViewContext before;memset(&before,0,sizeof before);private_context_save(&before);
        CHECK(independent_present(&cpu,VIEW_DRAW_OT));context_equal(&before);
        CHECK(view_valid && le32(view_cameras[0]+8)==700u<<16 &&
            le32(view_cameras[1]+8)==700u<<16);
        CHECK(scene_owner==owner && both_door_members==3 && !scene_phase && frame_count==1);
        CHECK(psx_mod_read_byte(PLAY+0x10)==1 && psx_mod_read_byte(PLAY+0x1C)==1);
    }
}
static void native_scene_keeps_private_panes(int online,int split) {
    for(unsigned owner=1;owner<=2;++owner)for(unsigned phase=0;phase<4;++phase)
    for(unsigned projected=0;projected<=(owner==2);++projected) {
        CPUState cpu;prepare_view(&cpu,online,split);mmx6_view_sdk.local_port=1;
        scene_owner=owner;scene_phase=phase;both_door_actor=0;
        psx_mod_write_byte(PLAY+0x10,1);psx_mod_write_byte(PLAY+0x1C,1);
        psx_mod_write_word(VIEW_CAMERA+8,700u<<16);
        psx_mod_write_word(VIEW_CAMERA+12,560u<<16);
        put32(view_cameras[1]+8,100u<<16);put32(view_cameras[1]+12,200u<<16);
        frame_count=1;view_frame=0;view_valid=1;view_pending=0;
        /* P2-owned native scenes actually draw while its stage/world call
         * is projected; a resident-only fixture misses the shared-HUD fallback. */
        inside=zero_world=zero_projected=(int)projected;
        CHECK(independent_scene_context());independent_world_begin();
        CHECK(view_valid && view_pending);
        CHECK(le32(view_cameras[0]+8)==700u<<16);
        CHECK(le32(view_cameras[1]+8)==(phase?700u:100u)<<16);
        /* Presentation belongs to the common call after that stage returns. */
        inside=zero_world=zero_projected=0;
        PrivateViewContext before;memset(&before,0,sizeof before);private_context_save(&before);
        CHECK(independent_present(&cpu,VIEW_DRAW_OT));context_equal(&before);
        CHECK(!private_draw && scene_owner==owner && scene_phase==phase);
        CHECK(view_callback_calls==(split?2u:1u) && !state_track.count && !failed);
    }
    CPUState cpu;prepare_view(&cpu,online,split);scene_owner=1;scene_phase=0;
    psx_mod_write_byte(PLAYER+0xD0,0);psx_mod_write_byte(PLAYER+0xD4,0);
    psx_mod_write_byte(PLAYER+0x7A,0);
    CHECK(!independent_scene_context());independent_world_begin();
    CHECK(!view_pending && !view_valid); /* Unattributed holds stay refused. */
}
static void native_arrival(int online,int split) {
    CPUState cpu;prepare_view(&cpu,online,split);
    mmx6_view_sdk.local_port=1;
    life.status[1]=MMX6_COOP_JOINING;join_phase=1;
    arrival_target=join_y=1000*65536;
    put32(p2.body+12,(uint32_t)(-40*65536));
    put32(p2.body+0x1C,(uint32_t)(-40*65536));
    p2.body[5]=0;memcpy(arrival_body,p2.body,sizeof arrival_body);
    uint8_t primary[0x158];capture(PLAYER,primary,sizeof primary);
    view_pending=view_valid=0;frame_count=1;
    independent_world_begin();CHECK(view_pending && view_valid);
    PrivateViewContext before;memset(&before,0,sizeof before);private_context_save(&before);
    arrival_probe=1;
    CHECK(independent_present(&cpu,VIEW_DRAW_OT) && arrival_camera_calls==3);
    CHECK(life.status[1]==MMX6_COOP_JOINING && join_phase==1);
    CHECK(!memcmp(p2.body,arrival_body,sizeof arrival_body));
    uint8_t actual[0x158];capture(PLAYER,actual,sizeof actual);CHECK(!memcmp(actual,primary,sizeof actual));
    context_equal(&before);CHECK(frame_count==1 && !state_track.count && !state_track.error);
}
static void native_nova_views(int online,int split) {
    for(unsigned phase=0;phase<3;++phase) {
        CPUState cpu;prepare_view(&cpu,online,split);native_nova_body(phase);
        mmx6_view_sdk.local_port=1;view_pending=view_valid=0;frame_count=1;
        independent_world_begin();CHECK(view_pending && view_valid);
        PrivateViewContext before;memset(&before,0,sizeof before);private_context_save(&before);
        CHECK(independent_present(&cpu,VIEW_DRAW_OT));context_equal(&before);
        CHECK(psx_mod_read_byte(PLAY+0x1C)==1 && primary_nova_active());
        CHECK(frame_count==1 && !state_track.count && !state_track.error);
    }
    for(unsigned gate=0;gate<NOVA_BLOCKED_CASES;++gate) {
        CPUState cpu;prepare_view(&cpu,online,split);native_nova_body(0);block_native_nova(gate);
        if(gate==10) {
            /* A real scene retains its panes under the scene contract,
             * independently of the narrower Nova-only admission. */
            CHECK(!primary_nova_active());independent_world_begin();
            CHECK(view_pending && view_valid);continue;
        }
        independent_world_begin();CHECK(!view_pending && !view_valid && !view_native_calls);
    }
}
static void native_giga_views(int online,int split) {
    for(unsigned armor=1;armor<=3;++armor) {
        CPUState cpu;prepare_view(&cpu,online,split);native_nova_body(0);
        psx_mod_write_byte(PLAYER+0xE7,(uint8_t)armor);
        psx_mod_write_byte(PLAYER+5,armor==1?0x24:armor==2?0x25:0x4D);
        psx_mod_write_byte(PLAYER+0xE0,2);
        view_valid=1;view_frame=0;frame_count=1;
        psx_mod_write_word(VIEW_CAMERA+8,700u<<16);
        put32(view_cameras[1]+8,100u<<16);
        CHECK(independent_giga_context() && coop_world_hold());
        independent_world_begin();CHECK(view_pending && view_valid);
        CHECK(le32(view_cameras[1]+8)==100u<<16);
        PrivateViewContext before;memset(&before,0,sizeof before);private_context_save(&before);
        CHECK(independent_present(&cpu,VIEW_DRAW_OT));context_equal(&before);
        CHECK(psx_mod_read_byte(PLAY+0x1C)==1 && coop_world_hold());
        uint32_t guest_camera=le32(view_cameras[1]+8);
        /* Native recovery releases its own lock. Camera history survives. */
        psx_mod_write_byte(PLAY+0x1C,0);psx_mod_write_byte(PLAYER+5,2);
        psx_mod_write_byte(PLAYER+0xE0,0);psx_mod_write_byte(PLAYER+0x7A,0);
        frame_count=2;independent_world_begin();CHECK(view_pending && view_valid);
        CHECK(le32(view_cameras[1]+8)==guest_camera && !independent_giga_context());
        CHECK(!state_track.count && !state_track.error && !failed);
    }
}
static void native_heal_views(int online,int split) {
    for(unsigned pool=0;pool<2;++pool)for(unsigned owner=0;owner<2;++owner)for(unsigned gate=0;gate<6;++gate) {
        CPUState cpu;prepare_view(&cpu,online,split);
        const uint32_t actor=pool?0x800C1220u:0x8008EF48u;
        psx_mod_write_byte(actor,9);psx_mod_write_byte(actor+4,2);
        psx_mod_write_byte(actor+1,pool?4:47);
        unsigned count=pool?0x7F:0x83,timer=pool?0x80:0x84,period=pool?4:2;
        psx_mod_write_byte(actor+6,0);psx_mod_write_byte(actor+count,16);
        psx_mod_write_byte(actor+timer,(uint8_t)period);pickup_owners[0]=(PickupOwner){actor,(uint8_t)owner};
        for(unsigned at=0x10;at<=0x17;++at)psx_mod_write_byte(PLAY+at,1);
        psx_mod_write_byte(PLAY+0x19,1);
        if(gate==1)pickup_owners[0].actor=0;
        else if(gate==2)psx_mod_write_byte(actor+4,1);
        else if(gate==3)psx_mod_write_byte(actor+timer,0);
        else if(gate==4)psx_mod_write_byte(PLAY+0x19,0);
        else if(gate==5)pickup_owners[0].actor+=4;
        view_valid=1;view_frame=0;frame_count=1;
        psx_mod_write_word(VIEW_CAMERA+8,700u<<16);put32(view_cameras[1]+8,100u<<16);
        CHECK(independent_heal_context()==!gate);independent_world_begin();
        if(gate) {CHECK(!view_pending && !view_valid);continue;}
        CHECK(view_pending && view_valid && le32(view_cameras[1]+8)==100u<<16);
        PrivateViewContext before;memset(&before,0,sizeof before);private_context_save(&before);
        CHECK(independent_present(&cpu,VIEW_DRAW_OT));context_equal(&before);
        CHECK(psx_mod_read_byte(actor+timer)==period && psx_mod_read_byte(actor+count)==16);
        for(unsigned at=0x10;at<=0x17;++at)CHECK(psx_mod_read_byte(PLAY+at)==1);
        CHECK(psx_mod_read_byte(PLAY+0x19)==1);
        uint32_t guest_camera=le32(view_cameras[1]+8);
        if(!pool)for(unsigned unused=0;unused<=8;unused+=8) {
            psx_mod_write_byte(actor+count,(uint8_t)unused);psx_mod_write_byte(actor+6,1);
            ++frame_count;CHECK(independent_heal_context());
            independent_world_begin();CHECK(view_valid && view_pending);
            CHECK(le32(view_cameras[1]+8)==guest_camera);
            PrivateViewContext terminal;memset(&terminal,0,sizeof terminal);private_context_save(&terminal);
            CHECK(independent_present(&cpu,VIEW_DRAW_OT));context_equal(&terminal);
            CHECK(psx_mod_read_byte(actor+6)==1 && psx_mod_read_byte(PLAY+0x10)==1);
        }
        for(unsigned at=0x10;at<=0x17;++at)psx_mod_write_byte(PLAY+at,0);
        psx_mod_write_byte(PLAY+0x19,0);psx_mod_write_byte(actor+4,3);
        ++frame_count;independent_world_begin();CHECK(view_pending && view_valid);
        CHECK(le32(view_cameras[1]+8)==guest_camera && !independent_heal_context());
    }
}
static void arrival_refusals(void) {
    const Mmx6CoopStatus blocked[]={MMX6_COOP_LEAVING,MMX6_COOP_ABSENT};
    for(unsigned i=0;i<sizeof blocked/sizeof blocked[0];++i) {
        CPUState cpu;prepare_view(&cpu,0,1);life.status[1]=blocked[i];
        frame_count=1;view_frame=0;
        uint8_t retained[sizeof view_cameras[1]];memcpy(retained,view_cameras[1],sizeof retained);
        independent_world_begin();CHECK(view_pending && view_valid);
        CHECK(independent_present(&cpu,VIEW_DRAW_OT) && !failed);
        for(unsigned layer=0;layer<3;++layer)
            CHECK(!memcmp(view_cameras[1]+layer*0x54+8,retained+layer*0x54+8,0x14));
        /* Absence retains an established camera, never a stale stage's pair. */
        prepare_view(&cpu,0,1);life.status[1]=blocked[i];view_valid=0;
        independent_world_begin();CHECK(!view_pending && !view_valid && !view_native_calls);
    }
    /* Both local panes use the survivor's current native world, including
     * after a restore invalidates camera history. Each HUD stays personal. */
    const Mmx6CoopStatus dead[]={MMX6_COOP_DYING,MMX6_COOP_FALLEN};
    for(unsigned seat=0;seat<2;++seat)for(unsigned i=0;i<2;++i) {
        CPUState cpu;prepare_view(&cpu,0,1);life.status[seat]=dead[i];
        mmx6_view_sdk.local_port=seat;frame_count=1;view_frame=0;
        uint8_t retained[sizeof view_cameras[0]];memcpy(retained,memory(VIEW_CAMERA),sizeof retained);
        independent_world_begin();CHECK(view_pending && view_valid);
        CHECK(independent_present(&cpu,VIEW_DRAW_OT) && mmx6_view_sdk.pair_enabled && !failed);
        for(unsigned layer=0;layer<3;++layer)
            CHECK(!memcmp(view_cameras[seat]+layer*0x54+8,retained+layer*0x54+8,0x14));
        prepare_view(&cpu,0,1);life.status[seat]=dead[i];view_valid=0;
        independent_world_begin();CHECK(view_pending && view_valid && !view_native_calls);
    }
    for(unsigned gate=0;gate<5;++gate) {
        CPUState cpu;prepare_view(&cpu,0,1);life.status[1]=MMX6_COOP_JOINING;
        if(gate==0) {
            scene_owner=1; /* No native script or body hold authorizes it. */
            psx_mod_write_byte(PLAYER+0xD0,0);psx_mod_write_byte(PLAYER+0xD4,0);
            psx_mod_write_byte(PLAYER+0x7A,0);
        } else if(gate==1){pause_owner=0;psx_mod_write_byte(PLAY+1,1);}
        else if(gate==2)psx_mod_write_byte(PLAY+0x1C,1);
        else if(gate==3)psx_mod_write_byte(PLAY+1,2);else life.status[0]=MMX6_COOP_LEAVING;
        independent_world_begin();CHECK(!view_pending && !view_valid && !view_native_calls);
    }
}
static void native_personal_menu_presentation(int online,int split) {
    CPUState cpu;prepare_view(&cpu,online,split);personal_view_probe=1;
    personal_active=personal_initialized=1;personal_eligible=3;pause_owner=0;
    personal_seat=1; /* The previous simulation pass may have been P2. */
    psx_mod_write_byte(PLAY+1,2);view_pending=0; /* No world render was queued. */
    personal_resident_menu=psx_mod_read_word(SCRATCH+0x3C);
    personal_resident_palette=psx_mod_read_word(SCRATCH+0x28);
    for(unsigned seat=0;seat<2;++seat) {
        memset(personal_menu[seat].native,(int)(0x20u+seat),sizeof personal_menu[seat].native);
        personal_menu[seat].native[4]=1;personal_menu[seat].native[5]=1;
        personal_menu[seat].native[0x14]=(uint8_t)(2+seat);
        personal_menu[seat].original_weapon=(uint8_t)(4+seat);
        for(unsigned i=0;i<sizeof personal_regions/sizeof *personal_regions;++i) {
            const PersonalMenuRegion *r=&personal_regions[i];
            uint32_t base=menu_memory+(seat?0:MENU_BYTES)+r->offset;
            for(unsigned n=0;n<r->w*r->h;++n)
                psx_mod_write_half(base+n*2u,(uint16_t)(0x1100u+seat*0x100u+i));
        }
        uint32_t palette=seat?active_palette:personal_resident_palette;
        for(unsigned n=0;n<0x2000;++n)psx_mod_write_half(palette+n*2u,(uint16_t)(0x2100u+seat*0x100u+n));
    }
    personal_write(0);memset(test_vram,0x5A,sizeof test_vram);
    psx_mod_write_byte(0x80097424u,1);psx_mod_write_byte(0x800C483Cu,0x47);
    psx_mod_write_word(0x800CF96Cu,0xE1000045u);psx_mod_write_word(0x800C8860u,0x81);
    mmx6_view_sdk.local_port=1;
    PrivateViewContext before;memset(&before,0,sizeof before);private_context_save(&before);
    static uint8_t saved_ram[sizeof ram],saved_extra[sizeof extra];
    static uint16_t saved_vram[1024*512];
    memcpy(saved_ram,ram,sizeof ram);memcpy(saved_extra,extra,sizeof extra);memcpy(saved_vram,test_vram,sizeof test_vram);
    CPUState expected=cpu;expected.gpr[2]=0xC0DE;
    uint32_t digest=state_digest();unsigned uploads=menu_view_uploads;
    CHECK(independent_present(&cpu,VIEW_DRAW_OT));
    CHECK(!memcmp(&cpu,&expected,sizeof cpu) && state_digest()==digest);context_equal(&before);
    CHECK(!memcmp(saved_ram,ram,sizeof ram) && !memcmp(saved_extra,extra,sizeof extra));
    CHECK(!memcmp(saved_vram,test_vram,sizeof test_vram)); /* Modeled checkpoint only. */
    CHECK(!view_pending && !view_call && !personal_pass && !personal_rendering && !zero_projected);
    unsigned panes=(!online || split)?2u:1u;
    CHECK(menu_view_uploads-uploads==panes*9u && !personal_view_cameras && !view_callback_calls);
    CHECK((panes==2?mmx6_view_sdk.pair_calls:mmx6_view_sdk.view_calls)==1);
    for(unsigned seat=0;seat<2;++seat) {
        unsigned drawn=panes==2 || seat==1;
        CHECK(personal_view_draws[seat]==drawn && personal_view_clears[seat]==drawn);
        CHECK(personal_fade_at[seat]==drawn*4u);
        if(drawn) {
            CHECK(personal_fade_words[seat][0]==0xE1000045u);
            CHECK(personal_fade_words[seat][1]==0x62474747u && personal_fade_words[seat][2]==0);
            CHECK(personal_fade_words[seat][3]==(320u|(240u<<16)));
        }
    }
}
static void native_entering_pause_views(int online,int split) {
    for(unsigned init=0;init<3;++init)for(int owner=0;owner<2;++owner)for(unsigned slot=0;slot<2;++slot) {
        CPUState cpu;prepare_view(&cpu,online,split);personal_view_probe=entering_view_probe=1;
        memset(view_cameras[0],0x31,sizeof view_cameras[0]);
        memset(view_cameras[1],0x57,sizeof view_cameras[1]);
        uint8_t cameras[sizeof view_cameras];memcpy(cameras,view_cameras,sizeof cameras);
        pause_owner=owner;independent_menu_begin();CHECK(view_menu_history);
        psx_mod_write_byte(PLAY+1,1);personal_active=personal_initialized=0;
        if(init) {
            /* Native personal_begin assigns canonical authority0 even when
             * only Zero lives; it is not the identity of the living opener. */
            if(init==2)life.status[0]=MMX6_COOP_FALLEN;
            pause_owner=0;personal_active=1;personal_eligible=init==2?2:3;
            personal_menu[0].native[4]=0;personal_menu[0].native[5]=(uint8_t)slot;
            psx_mod_write_byte(PLAY+1,2);
        }
        psx_mod_write_byte(0x80097424u,1);psx_mod_write_word(0x800C8860u,0x81);
        view_buffer=VIEW_BUFFER+slot*VIEW_STRIDE;
        psx_mod_write_word(0x8009B7A0u,view_buffer);cpu.gpr[4]=view_buffer+0xECu;
        psx_mod_write_half(view_buffer+0x18u,320);psx_mod_write_half(view_buffer+0x1Au,240);
        psx_mod_write_byte(0x800C483Cu+slot*16u,0x47);
        psx_mod_write_word(0x800CF96Cu+slot*8u,0xE1000045u);
        mmx6_view_sdk.local_port=slot;view_pending=0;inside=zero_world=zero_projected=1;
        if(init) { personal_pass=1;personal_seat=0;zero_world=zero_projected=0; }
        uint32_t digest=state_digest();CPUState original=cpu;
        independent_world_begin();CHECK(view_pending && view_valid && view_menu_history);
        CHECK(state_digest()==digest && !memcmp(&cpu,&original,sizeof cpu));
        CHECK(!memcmp(cameras,view_cameras,sizeof cameras) && !view_native_calls);
        inside=zero_world=zero_projected=personal_pass=0;
        PrivateViewContext context;memset(&context,0,sizeof context);private_context_save(&context);
        digest=state_digest();original=cpu;
        digest=state_digest();original.gpr[2]=0xC0DE;
        CHECK(independent_present(&cpu,VIEW_DRAW_OT));context_equal(&context);
        CHECK(state_digest()==digest && !memcmp(&cpu,&original,sizeof cpu));
        CHECK(!memcmp(cameras,view_cameras,sizeof cameras) && !personal_view_cameras);
        for(unsigned seat=0;seat<2;++seat) {
            unsigned drawn=split || seat==slot;
            CHECK(entering_view_draws[seat]==drawn && personal_view_clears[seat]==drawn);
            CHECK(personal_fade_at[seat]==drawn*4u);
            if(drawn) {
                CHECK(personal_fade_words[seat][0]==0xE1000045u);
                CHECK(personal_fade_words[seat][1]==0x62474747u && personal_fade_words[seat][2]==0);
                CHECK(personal_fade_words[seat][3]==(320u|(240u<<16)));
            }
        }
    }
    for(unsigned bad=0;bad<9;++bad) {
        CPUState cpu;prepare_view(&cpu,online,split);pause_owner=0;
        if(bad!=0)independent_menu_begin();
        psx_mod_write_byte(PLAY+1,1);
        if(bad==1)psx_mod_write_byte(PLAY+12,(uint8_t)(view_menu_stage+1));
        if(bad==2)psx_mod_write_byte(PLAY+13,(uint8_t)(view_menu_section+1));
        if(bad==3)psx_mod_write_byte(PLAY+0x1D,(uint8_t)(view_menu_checkpoint+1));
        if(bad==4)pause_owner=-1;
        if(bad==5)pause_owner=2;
        if(bad==6)psx_mod_write_byte(PLAY+0x10,1);
        if(bad==7)psx_mod_write_byte(PLAY+0x1C,1);
        if(bad==8)clear_phase=1;
        independent_world_begin();CHECK(!view_pending && !view_native_calls);
    }
    for(unsigned bad=0;bad<5;++bad) {
        CPUState cpu;prepare_view(&cpu,online,split);pause_owner=0;independent_menu_begin();
        life.status[0]=MMX6_COOP_FALLEN;personal_active=1;personal_initialized=0;personal_eligible=2;
        personal_menu[0].native[4]=0;personal_menu[0].native[5]=1;psx_mod_write_byte(PLAY+1,2);
        if(bad==0)personal_active=0;
        if(bad==1)personal_initialized=1;
        if(bad==2)personal_menu[0].native[4]=1;
        if(bad==3)personal_menu[0].native[5]=2;
        if(bad==4)personal_eligible=1; /* Dead canonical authority is not eligible. */
        independent_world_begin();CHECK(!view_pending && !view_native_calls);
    }
}
static void native_personal_resume_camera_history(int online,int split) {
    CPUState cpu;prepare_view(&cpu,online,split);personal_view_probe=1;
    memset(view_cameras[1],0x53,sizeof view_cameras[1]);
    memset(memory(VIEW_CAMERA),0x27,sizeof view_cameras[0]);
    uint8_t positions[3][0x14];
    for(unsigned layer=0;layer<3;++layer)memcpy(positions[layer],view_cameras[1]+layer*0x54+8,0x14);
    frame_count=11;view_frame=10;pause_owner=0;independent_menu_begin();CHECK(view_menu_history);
    personal_active=personal_initialized=1;personal_eligible=3;
    personal_menu[0].native[4]=personal_menu[1].native[4]=2;
    personal_menu[0].native[5]=personal_menu[1].native[5]=3;
    psx_mod_write_byte(PLAY+1,2);inside=personal_pass=1;personal_seat=0;
    mmx6_view_sdk.local_port=1;
    for(unsigned first_world=0;first_world<2;++first_world) {
        if(first_world) {
            personal_reset();psx_mod_write_byte(PLAY+1,0);++frame_count;
            CHECK(pause_owner==0); /* Native opener flag has not cleared yet. */
        }
        uint32_t digest=state_digest();CPUState original=cpu;
        independent_world_begin();CHECK(view_pending && view_valid && !view_menu_history);
        CHECK(!memcmp(&cpu,&original,sizeof cpu) && state_digest()==digest);
        for(unsigned layer=0;layer<3;++layer)
            CHECK(!memcmp(positions[layer],view_cameras[1]+layer*0x54+8,0x14));
        inside=personal_pass=0;
        PrivateViewContext context;memset(&context,0,sizeof context);private_context_save(&context);
        digest=state_digest();original=cpu;original.gpr[2]=0xC0DE;
        CHECK(independent_present(&cpu,VIEW_DRAW_OT));context_equal(&context);
        CHECK(!memcmp(&cpu,&original,sizeof cpu) && state_digest()==digest && !personal_view_cameras);
        for(unsigned layer=0;layer<3;++layer)
            CHECK(!memcmp(positions[layer],view_cameras[1]+layer*0x54+8,0x14));
    }
    CHECK(personal_view_clears[1]==1 && personal_view_draws[0]==0 && personal_view_draws[1]==0);
}
static void native_initial_mode9_arrival_view(int online,int split) {
    CPUState cpu;prepare_view(&cpu,online,split);mmx6_view_sdk.local_port=1;
    arrival_pair=1;life.status[1]=MMX6_COOP_JOINING;join_phase=0;
    psx_mod_write_byte(PLAY,9);psx_mod_write_byte(PLAY+1,0);psx_mod_write_byte(PLAY+0x10,1);
    p2.body[5]=0;put32(p2.body+12,(uint32_t)(-40*65536));put32(p2.body+0x1C,(uint32_t)(-40*65536));
    arrival_target=join_y=1000*65536;memcpy(arrival_body,p2.body,sizeof arrival_body);
    view_pending=view_valid=0;frame_count=1;
    static uint8_t saved_ram[sizeof ram];memcpy(saved_ram,ram,sizeof ram);
    CPUState expected=cpu;uint32_t digest=state_digest();
    CHECK(!world_draw_filter(&cpu,0x80025FB0u));
    CHECK(view_pending && view_valid && !view_native_calls);
    CHECK(!memcmp(&cpu,&expected,sizeof cpu) && !memcmp(saved_ram,ram,sizeof ram) && state_digest()==digest);
    CHECK(life.status[0]==MMX6_COOP_ALIVE && life.status[1]==MMX6_COOP_JOINING && arrival_pair==1);
    arrival_probe=1;PrivateViewContext context;memset(&context,0,sizeof context);private_context_save(&context);
    expected.gpr[2]=0xC0DE;
    CHECK(independent_present(&cpu,VIEW_DRAW_OT) && arrival_camera_calls==3);context_equal(&context);
    CHECK(!memcmp(&cpu,&expected,sizeof cpu) && state_digest()==digest);
    CHECK(!memcmp(saved_ram,ram,sizeof ram) && !memcmp(arrival_body,p2.body,sizeof arrival_body));
}
static void native_surviving_guest_world_view(int online,int split) {
    const Mmx6CoopStatus dead[]={MMX6_COOP_DYING,MMX6_COOP_FALLEN};
    for(unsigned i=0;i<sizeof dead/sizeof *dead;++i) {
        CPUState cpu;prepare_view(&cpu,online,split);mmx6_view_sdk.local_port=1;
        life.status[0]=dead[i];life.status[1]=MMX6_COOP_ALIVE;
        memset(view_cameras[0],0x1C,sizeof view_cameras[0]);view_cameras[0][0x34]=0;
        uint8_t retained[sizeof view_cameras[0]];memcpy(retained,view_cameras[0],sizeof retained);
        memset(memory(VIEW_CAMERA),0x6D,sizeof view_cameras[0]);psx_mod_write_byte(VIEW_CAMERA+0x34,0);
        frame_count=11;view_frame=0;view_pending=0;inside=zero_world=zero_projected=1;
        static uint8_t saved_ram[sizeof ram];memcpy(saved_ram,ram,sizeof ram);
        CPUState original=cpu;uint32_t digest=state_digest();
        independent_world_begin();CHECK(view_pending && view_valid && !view_native_calls);
        if(!online)memcpy(retained,memory(VIEW_CAMERA),sizeof retained);
        CHECK(!memcmp(retained,view_cameras[0],sizeof retained));
        CHECK(!memcmp(saved_ram,ram,sizeof ram) && !memcmp(&original,&cpu,sizeof cpu) && state_digest()==digest);
        CHECK(inside && zero_world && zero_projected); /* Draw-only recording within the survivor's one pass. */
        inside=zero_world=zero_projected=0;
        PrivateViewContext context;memset(&context,0,sizeof context);private_context_save(&context);
        digest=state_digest();original.gpr[2]=0xC0DE;
        CHECK(independent_present(&cpu,VIEW_DRAW_OT));context_equal(&context);
        CHECK(!memcmp(retained,view_cameras[0],sizeof retained) && !memcmp(&original,&cpu,sizeof cpu));
        CHECK(!memcmp(saved_ram,ram,sizeof ram) && state_digest()==digest && !failed);
    }
    /* A normal two-living-body projected/nested world remains forbidden. */
    CPUState cpu;prepare_view(&cpu,online,split);inside=zero_world=zero_projected=1;
    independent_world_begin();CHECK(!view_pending && !view_valid && !view_native_calls);
}
static void native_scene_and_retry_retire_camera_history(int online,int split) {
    for(unsigned boundary=0;boundary<2;++boundary) {
        CPUState cpu;prepare_view(&cpu,online,split);
        view_menu_history=view_quake_valid=intro_camera_valid=1;
        memset(intro_camera_requests,0x53,sizeof intro_camera_requests);
        if(boundary)native_player_init(&cpu,0x8003BD24u);
        else { scene_owner=1;scene_phase=0;scene_tick(&cpu);CHECK(!scene_owner); }
        CHECK(!view_valid && !view_pending && !view_menu_history && !view_quake_valid && !intro_camera_valid);
        for(unsigned i=0;i<sizeof intro_camera_requests;++i)CHECK(!intro_camera_requests[i]);
    }
}
static void native_menu_camera_history(int online,int split) {
    for(int owner=0;owner<2;++owner)for(unsigned boundary=0;boundary<8;++boundary) {
        CPUState cpu;prepare_view(&cpu,online,split);
        memset(view_cameras[1],0x53,sizeof view_cameras[1]);
        memset(ram+(VIEW_CAMERA&0x1FFFFFu),0x27,sizeof view_cameras[0]);
        uint8_t prior[sizeof view_cameras[1]];memcpy(prior,view_cameras[1],sizeof prior);
        view_frame=10;frame_count=11;pause_owner=owner;
        independent_menu_begin();CHECK(view_menu_history);
        psx_mod_write_byte(PLAY+1,2);
        for(unsigned frame=0;frame<20;++frame) {
            ++frame_count;independent_world_begin();
            CHECK(!view_pending && view_valid && view_menu_history && !view_native_calls);
            CHECK(!memcmp(prior,view_cameras[1],sizeof prior));
        }
        if(boundary==1)psx_mod_write_byte(PLAY+12,1);
        if(boundary==2)psx_mod_write_byte(PLAY+13,1);
        if(boundary==3)psx_mod_write_byte(PLAY+0x1D,1);
        if(boundary==4)scene_owner=1;
        if(boundary==5)life.status[1]=MMX6_COOP_ABSENT;
        if(boundary==6)independent_invalidate(); /* current-build load */
        if(boundary==7)psx_mod_write_byte(PLAY+0x1C,1);
        psx_mod_write_byte(PLAY+1,0);pause_owner=-1;++frame_count;
        independent_world_begin();
        if(boundary==4 || boundary==7) {
            CHECK(!view_pending && !view_valid && !view_menu_history);continue;
        }
        CHECK(view_pending && view_valid && !view_menu_history);
        for(unsigned layer=0;layer<3;++layer) {
            uint8_t actual[0x54];capture(VIEW_CAMERA+layer*0x54,actual,sizeof actual);
            CHECK(!memcmp(view_cameras[1]+layer*0x54,actual,8));
            CHECK(!memcmp(view_cameras[1]+layer*0x54+0x1C,actual+0x1C,0x38));
            CHECK(!memcmp(view_cameras[1]+layer*0x54+8,
                boundary && boundary!=5?actual+8:prior+layer*0x54+8,0x14));
        }
        PrivateViewContext saved;memset(&saved,0,sizeof saved);private_context_save(&saved);
        CHECK(independent_present(&cpu,VIEW_DRAW_OT));context_equal(&saved);
    }
    CPUState cpu;prepare_view(&cpu,online,split);
    view_frame=1;frame_count=50;memset(view_cameras[1],0x53,sizeof view_cameras[1]);
    independent_world_begin();uint8_t canonical[sizeof view_cameras[1]];
    capture(VIEW_CAMERA,canonical,sizeof canonical);
    CHECK(!memcmp(canonical,view_cameras[1],sizeof canonical)); /* unexplained gap still resets */
}
static void native_quake_inputs(int online,int split) {
    for(unsigned retiring=0;retiring<2;++retiring) {
        CPUState cpu;prepare_view(&cpu,online,split);
        mmx6_view_sdk.local_port=1; /* The one-view NET case exercises Zero. */
        frame_count=71;view_frame=70;memset(quake_before,0,sizeof quake_before);
        quake_before[0x34]=0x91;quake_before[0x36]=9;quake_before[0x37]=retiring?1:8;
        quake_before[0x3A]=1;quake_before[0x3B]=0;quake_before[0x3C]=2;quake_before[0x3D]=2;
        quake_before[0x3E]=0x82;quake_before[0x3F]=0x84;quake_before[0x45]=2;quake_before[0x46]=4;
        put32(quake_before+12,704u*65536);
        project(VIEW_CAMERA,quake_before,sizeof quake_before);
        CPUState original_cpu=cpu;uint32_t original_digest=state_digest();
        independent_camera_begin(&cpu,0x8002927Cu);
        CHECK(view_quake_valid && view_quake_frame==71 && !memcmp(&cpu,&original_cpu,sizeof cpu));
        CHECK(!memcmp(view_quake_input,quake_before,sizeof quake_before) && state_digest()==original_digest);
        memcpy(quake_after,quake_before,sizeof quake_after);
        quake_after[0x36]=8;quake_after[0x37]=retiring?0:7;
        quake_after[0x34]=retiring?0x90:0x91;
        quake_after[0x3A]=0;quake_after[0x3B]=2;quake_after[0x3F]=4;
        put32(quake_after+12,(retiring?704u:708u)*65536);
        /* One canonical original camera update has already completed before
         * original25FB0. Its result is authoritative and must not be edited. */
        project(VIEW_CAMERA,quake_after,sizeof quake_after);
        psx_mod_write_byte(VIEW_CAMERA+0x44,1);
        independent_world_begin();CHECK(view_pending && view_valid && view_frame==71);
        uint8_t canonical[0xFC];capture(VIEW_CAMERA,canonical,sizeof canonical);
        PrivateViewContext before;memset(&before,0,sizeof before);private_context_save(&before);
        quake_probe=1;CHECK(independent_present(&cpu,VIEW_DRAW_OT));quake_probe=0;
        context_equal(&before);uint8_t actual[sizeof canonical];capture(VIEW_CAMERA,actual,sizeof actual);
        CHECK(!memcmp(canonical,actual,sizeof canonical));
        CHECK(quake_camera_calls==1 && quake_draws[1]==1 && quake_draws[0]==(unsigned)split);
        CHECK(le32(view_cameras[1]+12)==le32(quake_after+12));
        CHECK(view_cameras[1][0x37]==quake_after[0x37] && view_cameras[1][0x34]==quake_after[0x34]);
        /* A nested draw entry cannot overwrite the canonical pre-update
         * witness. Stale or missing active inputs fail rather than tick twice. */
        uint8_t saved[sizeof view_quake_input];memcpy(saved,view_quake_input,sizeof saved);
        private_draw=1;independent_camera_begin(&cpu,0x8002927Cu);private_draw=0;
        CHECK(!memcmp(saved,view_quake_input,sizeof saved));
        ++view_frame;CHECK(!independent_quake_input());
        view_quake_valid=0;view_cameras[0][0x34]=0;
        CHECK(independent_quake_input());
    }
}
static void native_shared_weather_frames(int online,int split) {
    CPUState cpu;prepare_view(&cpu,online,split);
    psx_mod_write_byte(PLAY+12,6);psx_mod_write_byte(PLAY+13,0);
    psx_mod_write_byte(VIEW_CAMERA+0x54+4,5);
    /* Original waiting weather has a blank atlas at X320. Its native state
     * then starts rain and cycles five Y origins, without moving either hero.
     * Both private draw callbacks must see that world's frame, not the blank
     * origin saved when the guest camera was first initialized. */
    memset(view_cameras[1],0,sizeof view_cameras[1]);
    put32(view_cameras[1]+0x54+8,320u*65536);
    put32(view_cameras[1]+8,123u*65536);
    put32(view_cameras[1]+2*0x54+8,47u*65536);
    view_frame=10;frame_count=11;
    for(unsigned phase=0;phase<7;++phase) {
        weather_x=(phase==6?320u:0u)*65536;
        weather_y=(phase==6?0u:(phase%5)*256u)*65536;
        ++weather_world_updates; /* explicit native-once producer model */
        psx_mod_write_word(VIEW_CAMERA+0x54+8,weather_x);
        psx_mod_write_word(VIEW_CAMERA+0x54+12,weather_y);
        psx_mod_write_byte(VIEW_CAMERA+0x54+0x4C,1);
        independent_world_begin();CHECK(view_pending && view_valid);
        CHECK(le32(view_cameras[1]+8)==123u*65536);
        CHECK(le32(view_cameras[1]+2*0x54+8)==47u*65536);
        weather_probe=1;CHECK(independent_present(&cpu,VIEW_DRAW_OT));weather_probe=0;
        CHECK(weather_world_updates==phase+1 && weather_draws==(phase+1)*(split?2u:1u));
        CHECK(psx_mod_read_word(VIEW_CAMERA+0x54+8)==weather_x);
        CHECK(psx_mod_read_word(VIEW_CAMERA+0x54+12)==weather_y);
        CHECK(frame_count==11+phase);++frame_count;
    }
    /* An unrelated authored room/mode keeps its own guest camera history. */
    for(unsigned other=0;other<3;++other) {
        prepare_view(&cpu,online,split);view_frame=10;frame_count=11;
        psx_mod_write_byte(PLAY+12,other==0?7:6);
        psx_mod_write_byte(PLAY+13,other==1?1:0);
        psx_mod_write_byte(VIEW_CAMERA+0x54+4,other==2?4:5);
        put32(view_cameras[1]+0x54+8,99u*65536);
        psx_mod_write_word(VIEW_CAMERA+0x54+8,0);
        independent_world_begin();CHECK(le32(view_cameras[1]+0x54+8)==99u*65536);
    }
}
static void native_shared_scenery_y(int online,int split) {
    for(unsigned area=0;area<3;++area) {
        CPUState cpu;prepare_view(&cpu,online,split);mmx6_view_sdk.local_port=1;
        psx_mod_write_byte(PLAY+12,area==2?3:area?20:4);psx_mod_write_byte(PLAY+13,area==1?1:0);
        if(area==2) {
            const uint32_t boss=0x8008EF48u;
            psx_mod_write_word(PLAY+0x20,boss);psx_mod_write_byte(boss,65);
            psx_mod_write_byte(boss+1,52);psx_mod_write_byte(boss+2,0);
            psx_mod_write_byte(boss+4,1);psx_mod_write_word(boss+0x10,0x800F36C8u);
        }
        psx_mod_write_byte(VIEW_CAMERA+0x54+4,9);
        psx_mod_write_word(VIEW_CAMERA+12,224u<<16);
        put32(view_cameras[1]+12,1200u<<16); /* independent foreground history */
        put32(view_cameras[1]+0x54+8,99u<<16);
        put32(view_cameras[1]+0x54+12,900u<<16); /* stale shared animation */
        put32(view_cameras[1]+2*0x54+12,700u<<16);
        view_frame=10;frame_count=11;
        const unsigned ys[]={224,210,193}; /* retained original offset32/46/63 */
        for(unsigned phase=0;phase<3;++phase) {
            scenery_y=ys[phase]<<16;
            unsigned previous=phase?ys[phase-1]:226;
            psx_mod_write_word(VIEW_CAMERA+0x54+12,scenery_y);
            psx_mod_write_word(VIEW_CAMERA+0x54+0x18,previous<<16);
            uint8_t canonical[0xFC];capture(VIEW_CAMERA,canonical,sizeof canonical);
            independent_world_begin();CHECK(view_pending && view_valid);
            CHECK(le32(view_cameras[1]+12)==1200u<<16);
            CHECK(le32(view_cameras[1]+0x54+8)==99u<<16);
            CHECK(le32(view_cameras[1]+0x54+12)==scenery_y);
            CHECK(le32(view_cameras[1]+0x54+0x18)==previous<<16);
            CHECK(le32(view_cameras[1]+2*0x54+12)==700u<<16);
            PrivateViewContext before;memset(&before,0,sizeof before);private_context_save(&before);
            scenery_probe=1;CHECK(independent_present(&cpu,VIEW_DRAW_OT));scenery_probe=0;
            context_equal(&before);uint8_t actual[0xFC];capture(VIEW_CAMERA,actual,sizeof actual);
            CHECK(!memcmp(actual,canonical,sizeof actual));
            CHECK(scenery_draws[1]==phase+1 && scenery_draws[0]==(split?phase+1:0));
            CHECK(frame_count==11+phase);++frame_count;
        }
    }
    for(unsigned other=0;other<4;++other) {
        CPUState cpu;prepare_view(&cpu,online,split);view_frame=10;frame_count=11;
        psx_mod_write_byte(PLAY+12,other==3?3:other==0?6:20);
        psx_mod_write_byte(PLAY+13,(other==1 || other==3)?0:1);
        psx_mod_write_byte(VIEW_CAMERA+0x54+4,other==2?4:9);
        put32(view_cameras[1]+0x54+12,900u<<16);
        psx_mod_write_word(VIEW_CAMERA+0x54+12,193u<<16);
        independent_world_begin();CHECK(le32(view_cameras[1]+0x54+12)==900u<<16);
    }
}
static void native_intro_camera_volumes(void) {
    CPUState cpu;prepare_view(&cpu,0,1);
    static const uint32_t code[][2]={
        {0x80052134u,0x3C028009u},{0x80052138u,0x244570A0u},
        {0x80052140u,0x84A4000Au},{0x8005216Cu,0x84A4000Eu},
        {0x800521A0u,0xA0830047u},{0x800521BCu,0xA4820026u},
        {0x800521D8u,0xA4820024u},{0x800521F4u,0xA482002Au},
        {0x80052210u,0xA4820028u}};
    static const uint16_t records[]={2272,2303,1040,1135,65535,65535,944,65535,
                                    2128,2159,1040,1135,1968,65535,65535,65535,
                                    3616,3647,1040,1135,65535,5120,704,65535,
                                    4000,4031,752,815,65535,65535,65535,704,
                                    5200,5231,752,895,5008,65535,256,65535,
                                    5248,5279,352,479,65535,5424,65535,65535,
                                    5216,5247,352,479,65535,5120,65535,65535,
                                    2112,2143,1040,1135,65535,65535,896,65535};
    for(unsigned i=0;i<sizeof code/sizeof code[0];++i)psx_mod_write_word(code[i][0],code[i][1]);
    psx_mod_write_word(0x80079D70u,0x800791F0u);
    for(unsigned i=0;i<sizeof records/sizeof records[0];++i)psx_mod_write_half(0x800791F0u+i*2,records[i]);
    CHECK(independent_intro_camera_source());
    psx_mod_write_byte(PLAY+12,0);psx_mod_write_byte(PLAY+13,0);
    psx_mod_write_word(PLAYER+8,144u<<16);psx_mod_write_word(PLAYER+12,1115u<<16);
    const uint16_t initial[]={1968,0,944,944};
    for(unsigned i=0;i<4;++i) {
        psx_mod_write_half(VIEW_CAMERA+0x1C+i*2,initial[i]);
        psx_mod_write_half(VIEW_CAMERA+0x24+i*2,initial[i]);
    }
    psx_mod_write_word(VIEW_CAMERA+12,944u<<16);
    uint8_t canonical[0x54];capture(VIEW_CAMERA,canonical,sizeof canonical);
    put32(p2.body+8,3615u<<16);put32(p2.body+12,1040u<<16);
    independent_camera_begin(&cpu,0x8002927Cu);CHECK(intro_camera_valid && le32(intro_camera_requests+4)==le32(canonical+0x28));
    put32(p2.body+8,3616u<<16);independent_camera_begin(&cpu,0x8002927Cu);
    CHECK((intro_camera_requests[0]|intro_camera_requests[1]<<8)==5120);
    CHECK((intro_camera_requests[4]|intro_camera_requests[5]<<8)==944);
    CHECK((intro_camera_requests[6]|intro_camera_requests[7]<<8)==704);
    put32(p2.body+8,4000u<<16);put32(p2.body+12,751u<<16);
    independent_camera_begin(&cpu,0x8002927Cu);CHECK((intro_camera_requests[4]|intro_camera_requests[5]<<8)==944);
    put32(p2.body+8,4031u<<16);put32(p2.body+12,815u<<16);
    independent_camera_begin(&cpu,0x8002927Cu);CHECK((intro_camera_requests[4]|intro_camera_requests[5]<<8)==704);
    uint8_t actual[0x54];capture(VIEW_CAMERA,actual,sizeof actual);CHECK(!memcmp(actual,canonical,sizeof actual));
    put32(p2.body+8,4065u<<16);put32(p2.body+12,794u<<16);
    independent_camera_begin(&cpu,0x8002927Cu); /* Outside volumes keeps authored history. */
    view_pending=view_valid=0;frame_count=1;independent_world_begin();
    CHECK(le32(view_cameras[0]+12)==944u<<16);
    intro_camera_probe=1;CHECK(independent_present(&cpu,VIEW_DRAW_OT));intro_camera_probe=0;
    CHECK(intro_camera_calls==1 && le32(view_cameras[1]+12)==704u<<16);
    capture(VIEW_CAMERA,actual,sizeof actual);CHECK(!memcmp(actual,canonical,sizeof actual));
    /* The next real intro row leaves fixed factory704 for dynamic256..704,
     * and the later boss-approach rows remain authoritative as well. */
    put32(p2.body+8,5200u<<16);put32(p2.body+12,794u<<16);
    independent_camera_begin(&cpu,0x8002927Cu);
    CHECK((intro_camera_requests[2]|intro_camera_requests[3]<<8)==5008);
    CHECK((intro_camera_requests[6]|intro_camera_requests[7]<<8)==256);
    CHECK((intro_camera_requests[4]|intro_camera_requests[5]<<8)==704);
    put32(p2.body+8,5248u<<16);put32(p2.body+12,395u<<16);
    independent_camera_begin(&cpu,0x8002927Cu);CHECK((intro_camera_requests[0]|intro_camera_requests[1]<<8)==5424);
    put32(p2.body+8,5216u<<16);independent_camera_begin(&cpu,0x8002927Cu);
    CHECK((intro_camera_requests[0]|intro_camera_requests[1]<<8)==5120);
    /* Native CP1 reinitialization resets the prior factory history. Its real
     * row7 then requests896; current limits still belong to native28EBC. */
    native_player_init(&cpu,0x8003BD24u);enrolled=1;
    life.status[0]=life.status[1]=MMX6_COOP_ALIVE;
    const uint16_t cp1[]={5120,1968,944,944};
    for(unsigned i=0;i<4;++i) {
        psx_mod_write_half(VIEW_CAMERA+0x1C+i*2,cp1[i]);
        psx_mod_write_half(VIEW_CAMERA+0x24+i*2,cp1[i]);
    }
    psx_mod_write_half(VIEW_CAMERA+0x2C,96);psx_mod_write_word(VIEW_CAMERA+12,944u<<16);
    put32(p2.body+8,2112u<<16);put32(p2.body+12,1115u<<16);
    independent_camera_begin(&cpu,0x8002927Cu);
    CHECK((intro_camera_requests[6]|intro_camera_requests[7]<<8)==896);
    view_pending=view_valid=0;frame_count=2;independent_world_begin();
    intro_camera_probe=2;CHECK(independent_present(&cpu,VIEW_DRAW_OT));intro_camera_probe=0;
    CHECK((view_cameras[1][0x22]|view_cameras[1][0x23]<<8)==75);
    frame_count=3;independent_world_begin();
    CHECK((view_cameras[1][0x22]|view_cameras[1][0x23]<<8)==75);
    CHECK((view_cameras[1][0x2A]|view_cameras[1][0x2B]<<8)==896);
    /* Conversely, P1's later native request cannot leak into an outside guest. */
    intro_camera_valid=0;memset(intro_camera_requests,0,sizeof intro_camera_requests);
    put32(p2.body+8,168u<<16);put32(p2.body+12,1114u<<16);
    independent_camera_begin(&cpu,0x8002927Cu);
    psx_mod_write_half(VIEW_CAMERA+0x28,704);psx_mod_write_half(VIEW_CAMERA+0x2A,704);
    frame_count=4;independent_world_begin();CHECK((view_cameras[1][0x28]|view_cameras[1][0x29]<<8)==944);
    CHECK((view_cameras[1][0x2A]|view_cameras[1][0x2B]<<8)==944);
    HostState retained;state_capture(&retained);
    native_player_init(&cpu,0x8003BD24u);
    CHECK(!intro_camera_valid);for(unsigned i=0;i<sizeof intro_camera_requests;++i)CHECK(!intro_camera_requests[i]);
    state_commit(&retained);CHECK(intro_camera_valid && !memcmp(intro_camera_requests,retained.intro_camera_requests,8));
    psx_mod_write_word(0x80052138u,0);independent_camera_begin(&cpu,0x8002927Cu);
    CHECK(!intro_camera_valid);psx_mod_write_word(0x80052138u,0x244570A0u);
    psx_mod_write_byte(PLAY+12,1);independent_camera_begin(&cpu,0x8002927Cu);
    CHECK(!intro_camera_valid);for(unsigned i=0;i<sizeof intro_camera_requests;++i)CHECK(!intro_camera_requests[i]);
}
static void native_sequential_character_selection(void) {
    for(unsigned first_zero=0;first_zero<2;++first_zero)for(unsigned black=0;black<2;++black) {
        CPUState cpu;setup(&cpu);cpu.gpr[4]=PLAY;
        memset(&character_selection,0,sizeof character_selection);character_select_call=0;
        psx_mod_write_word(CHARACTER_UPDATE,0x27BDFFE8u);
        psx_mod_write_word(CHARACTER_UPDATE+0xC,0x80820002u);
        psx_mod_write_word(CHARACTER_UPDATE+0x10,0x24630F40u);
        const uint8_t native[]={0,1,5,2,3,4};
        project(CHARACTER_LIST,native,sizeof native);psx_mod_write_byte(CHARACTER_COUNT,6);
        psx_mod_write_byte(PLAY+0x5F,0x3F);psx_mod_write_byte(PLAY+0x69,255);
        psx_mod_write_byte(PLAY+0x38,0);psx_mod_write_byte(PLAY+0x5E,0);
        partner_x_armor=0;pad_buttons=0xFFFF;psx_mod_write_half(CHARACTER_PAD,0);
        character_native_roster();CHECK(character_selection.count==7);
        character_probe=1;psx_mod_write_byte(PLAY+2,4);
        CHECK(character_select(&cpu,CHARACTER_UPDATE));
        CHECK(psx_mod_read_byte(PLAY+2)==5 && !character_selection.seat);
        psx_mod_write_byte(PLAY+0x30,first_zero?(uint8_t)(2+black):0);
        psx_mod_write_half(CHARACTER_PAD,0x40);
        pad_buttons=(uint16_t)~0x4000u; /* P2 holds confirm during P1's turn. */
        CHECK(character_select(&cpu,CHARACTER_UPDATE));
        CHECK(character_selection.seat==1 && psx_mod_read_byte(PLAY+2)==5 && !character_selection.valid);
        CHECK(psx_mod_read_byte(CHARACTER_COUNT)==(first_zero?5:2));
        for(unsigned i=0;i<psx_mod_read_byte(CHARACTER_COUNT);++i)
            CHECK((psx_mod_read_byte(CHARACTER_LIST+i)==5)!=first_zero);
        psx_mod_write_half(CHARACTER_PAD,0);
        CHECK(character_select(&cpu,CHARACTER_UPDATE)); /* A held P2 button is consumed. */
        CHECK(!character_selection.valid && psx_mod_read_byte(PLAY+2)==5);
        pad_buttons=0xFFFF;CHECK(character_select(&cpu,CHARACTER_UPDATE));
        psx_mod_write_byte(PLAY+0x30,first_zero?4:(uint8_t)black);
        pad_buttons=(uint16_t)~0x4000u;CHECK(character_select(&cpu,CHARACTER_UPDATE));
        CHECK(character_selection.valid && !character_selection.active && psx_mod_read_byte(PLAY+2)==7);
        CHECK(character_selection.forms[0]==(first_zero?5:0) && character_selection.forms[1]==(first_zero?4:5));
        CHECK(character_selection.black==black && selected_zero_black()==black);
        CHECK(psx_mod_read_byte(PLAY+0x38)==first_zero && psx_mod_read_byte(PLAY+0x5E)==(first_zero?5:0));
        CHECK(psx_mod_read_byte(PLAY+0x5F)==0x3F && psx_mod_read_byte(CHARACTER_COUNT)==7);
        CHECK(character_select(&cpu,CHARACTER_UPDATE));CHECK(psx_mod_read_byte(CHARACTER_COUNT)==7);
        HostState retained;state_capture(&retained);memset(&character_selection,0,sizeof character_selection);
        state_commit(&retained);CHECK(character_selection.valid && character_selection.black==black);
        psx_mod_write_word(0x80022910u,0x30420020u);cpu.gpr[2]=0x3F;
        character_zero_variant(&cpu,0x80022910u);CHECK((cpu.gpr[2]&0x20u)==black*0x20u);
        psx_mod_write_word(0x801ED574u,0x30420020u);psx_mod_write_word(0x801ED56Cu,0x9062005Fu);
        psx_mod_write_word(OVERLAY,0x3Cu);cpu.gpr[2]=black?0:0x20;
        uint32_t x_value=cpu.gpr[2];character_zero_variant(&cpu,0x801ED574u);CHECK(cpu.gpr[2]==x_value);
        psx_mod_write_word(OVERLAY,0x3Du);character_zero_variant(&cpu,0x801ED574u);
        CHECK((cpu.gpr[2]&0x20u)==black*0x20u);
        CHECK(psx_mod_read_byte(PLAY+0x5F)==0x3F);
    }
    /* A new campaign without Zero unlocked still offers ordinary Zero. */
    memset(&character_selection,0,sizeof character_selection);
    psx_mod_write_byte(PLAY+0x5F,0);psx_mod_write_byte(CHARACTER_LIST,0);psx_mod_write_byte(CHARACTER_COUNT,1);
    character_native_roster();CHECK(character_selection.count==2 && character_selection.roster[1]==5);
    CHECK(psx_mod_read_byte(PLAY+0x5F)==0);
    {
        CPUState cpu;setup(&cpu);cpu.gpr[4]=PLAY;
        memset(&character_selection,0,sizeof character_selection);
        psx_mod_write_word(CHARACTER_UPDATE,0x27BDFFE8u);
        psx_mod_write_word(CHARACTER_UPDATE+0xC,0x80820002u);
        psx_mod_write_word(CHARACTER_UPDATE+0x10,0x24630F40u);
        psx_mod_write_byte(PLAY+0x5F,0);psx_mod_write_byte(PLAY+0x5E,0);
        psx_mod_write_byte(CHARACTER_LIST,0);psx_mod_write_byte(CHARACTER_COUNT,1);
        character_native_roster();psx_mod_write_byte(PLAY+2,4);
        psx_mod_write_half(CHARACTER_PAD,0);pad_buttons=0xFFFF;
        CHECK(character_select(&cpu,CHARACTER_UPDATE));
        psx_mod_write_half(CHARACTER_PAD,0x40);CHECK(character_select(&cpu,CHARACTER_UPDATE));
        CHECK(character_selection.seat==1);
        psx_mod_write_half(CHARACTER_PAD,0);pad_buttons=(uint16_t)~0x1000u;
        CHECK(character_select(&cpu,CHARACTER_UPDATE));
        CHECK(!character_selection.seat && character_selection.active && psx_mod_read_byte(PLAY+2)==5);
        CHECK(psx_mod_read_byte(CHARACTER_COUNT)==2 && !character_selection.valid);
        psx_mod_write_half(CHARACTER_PAD,0x10);pad_buttons=0xFFFF;
        CHECK(character_select(&cpu,CHARACTER_UPDATE));
        CHECK(!character_selection.active && psx_mod_read_byte(PLAY+2)==9 && !character_selection.valid);
        CHECK(psx_mod_read_byte(PLAY+0x5F)==0);
    }
    character_probe=0;memset(&character_selection,0,sizeof character_selection);pad_buttons=0xFFFF;
}
static void private_beam_pool_uses_own_simulation_camera(void) {
    CPUState cpu;setup(&cpu);
    independent_views=1;zero_projected=1;
    project_player(&p2);psx_mod_write_byte(PLAYER+2,1);psx_mod_write_byte(PLAYER+4,1);
    psx_mod_write_byte(PLAYER+0x14,0);psx_mod_write_byte(PLAYER+7,0);
    psx_mod_write_word(PLAYER+8,344u<<16);psx_mod_write_word(PLAYER+12,634u<<16);
    psx_mod_write_byte(VIEW_CAMERA+4,1);
    psx_mod_write_half(VIEW_CAMERA+0x30,160);psx_mod_write_half(VIEW_CAMERA+0x32,160);psx_mod_write_half(VIEW_CAMERA+0x2C,96);
    psx_mod_write_half(VIEW_CAMERA+0x1C,4096);psx_mod_write_half(VIEW_CAMERA+0x1E,0);
    psx_mod_write_half(VIEW_CAMERA+0x20,4096);psx_mod_write_half(VIEW_CAMERA+0x22,0);
    psx_mod_write_word(VIEW_CAMERA+8,0);psx_mod_write_word(VIEW_CAMERA+12,538u<<16);
    uint8_t camera[0xFC];capture(VIEW_CAMERA,camera,sizeof camera);
    attack_camera_probe=1;attack_camera_calls=0;private_attack_tick(&cpu);
    CHECK(attack_camera_calls==1 && psx_mod_read_byte(PLAYER+7)==1);
    CHECK(!memcmp(camera,memory(VIEW_CAMERA),sizeof camera) && !state_track.count);
    independent_views=0;psx_mod_write_byte(PLAYER+7,0);private_attack_tick(&cpu);
    CHECK(attack_camera_calls==2 && !psx_mod_read_byte(PLAYER+7));
    CHECK(!memcmp(camera,memory(VIEW_CAMERA),sizeof camera) && !state_track.count);
    attack_camera_probe=zero_projected=0;
}
int main(void) {
    local_survivor_uses_current_native_screen();
    private_beam_pool_uses_own_simulation_camera();
    native_sequential_character_selection();
    defaults_and_scope();
    native_stage_layout_before_enrollment();
    retained_presentation_lifetime();
#ifdef MMX6_COOP_VIEW_ENTRY_CONTEXT
    native_camera_context();
#endif
    reentry();native_arrival(0,1);native_arrival(1,0);arrival_refusals();
    admitted_door_views(0,1);admitted_door_views(1,0);admitted_door_views(1,1);
    native_scene_keeps_private_panes(0,1);native_scene_keeps_private_panes(1,0);
    native_nova_views(0,1);native_nova_views(1,0);
    native_door_scene_handoff(0,1);native_door_scene_handoff(1,0);
    native_giga_views(0,1);native_giga_views(1,0);
    native_heal_views(0,1);native_heal_views(1,0);
    native_personal_menu_presentation(0,0);native_personal_menu_presentation(0,1);
    native_personal_menu_presentation(1,0);native_personal_menu_presentation(1,1);
    native_entering_pause_views(0,1);native_entering_pause_views(1,0);
    native_personal_resume_camera_history(0,1);native_personal_resume_camera_history(1,0);
    native_initial_mode9_arrival_view(0,1);native_initial_mode9_arrival_view(1,0);
    native_surviving_guest_world_view(0,1);native_surviving_guest_world_view(1,0);
    native_scene_and_retry_retire_camera_history(0,1);
    native_scene_and_retry_retire_camera_history(1,0);
    native_menu_camera_history(0,1);native_menu_camera_history(1,0);
    native_shared_weather_frames(0,1);native_shared_weather_frames(1,0);
    native_shared_scenery_y(0,1);native_shared_scenery_y(1,0);native_shared_scenery_y(1,1);
    native_quake_inputs(0,1);native_quake_inputs(1,0);native_quake_inputs(1,1);
    native_intro_camera_volumes();native_placement_rearm_belongs_to_both_views();
    presentation_restore(0,1,0,0);presentation_restore(0,1,1,0);presentation_restore(0,1,0,1);
    presentation_restore(1,0,0,0);presentation_restore(1,0,1,0);presentation_restore(1,0,0,1);
    presentation_restore(1,1,0,0);presentation_restore(1,1,1,0);presentation_restore(1,1,0,1);
    clear_banks();puts("private-view typed defaults, scope, callback/abort host restoration and reentry contracts passed (modeled rendering)");return 0;
}
