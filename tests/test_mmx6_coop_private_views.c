/* Actual plugin host restoration against explicit draw/sandbox contracts.
 * No real renderer, GPU checkpoint, watchdog or native-game qualification. */
#include "cpu_state.h"
#include "mmx6_coop_private_view_sdk_fixture.h"
static unsigned view_native_calls,view_gpu_words,view_callback_calls,view_refuse,view_abort;
static int view_native(CPUState *,uint32_t,uint32_t);
static int view_gpu(uint32_t,unsigned);
static unsigned arrival_probe,arrival_camera_calls;
static int32_t arrival_target;
static uint8_t arrival_body[0x158];
static unsigned weather_probe,weather_world_updates,weather_draws;
static uint32_t weather_x,weather_y;
#define MMX6_TEST_NETPLAY_ACTIVE mmx6_view_sdk.online
#define MMX6_TEST_DISPATCH_CALL view_native
#define MMX6_TEST_PRIVATE_VIEW_GPU view_gpu
#define main unused_private_effects_fixture_main
#include "test_mmx6_coop_private_effects.c"
#undef main

static void disturb_host(void) {
    p2.body[0x5C]=7;p1.body[0x5C]=8;join_phase=3;previous_input=0x1234;
    memset(saved_overlay,0x91,sizeof saved_overlay);memset(saved_play,0x92,sizeof saved_play);
    memset(saved_camera,0x93,sizeof saved_camera);memset(saved_resources,0x94,sizeof saved_resources);
    saved_palette_dirty=1;ride_call=7;pickup_call=6;solid_call=5;zero_projected=1;
}
static int view_native(CPUState *cpu,uint32_t address,uint32_t ret) {
    (void)ret;++view_native_calls;
    if(address==VIEW_DRAW_OT) { cpu->gpr[2]=0xC0DE;return 1; }
    if(address==0x80066150u)return 1;
    if(address==0x8002927Cu || address==0x8002935Cu || address==0x800293CCu) {
        if(arrival_probe) {
            CHECK(private_draw && private_seat==1);
            CHECK(psx_mod_read_word(PLAYER+12)==(uint32_t)arrival_target);
            CHECK(psx_mod_read_word(PLAYER+0x1C)==(uint32_t)arrival_target);
            ++arrival_camera_calls;
        }
        return 1;
    }
    CHECK(address==0x80025FB0u && private_draw);
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
    return 1;
}
static int model_transaction(CPUState *cpu,PSXModRenderPassFn callback,void *user,uint32_t eye) {
    /* Only this unit model restores its guest RAM/CPU. Real SDK restoration
     * and publication require separate runtime tests. */
    static uint8_t guest_ram[sizeof ram];CPUState saved=*cpu;
    memcpy(guest_ram,ram,sizeof ram);
    int ok;
    if(view_abort) { disturb_host();inside=1;state_track.count=2;state_track.error=1;ok=0; }
    else ok=callback(cpu,user,eye);
    memcpy(ram,guest_ram,sizeof ram);*cpu=saved;return ok;
}
static void prepare_view(CPUState *cpu,int online,int split) {
    setup(cpu);mmx6_view_sdk_reset();mmx6_view_sdk.online=online;
    view_native_calls=view_gpu_words=view_callback_calls=view_refuse=view_abort=0;
    arrival_probe=arrival_camera_calls=0;
    weather_probe=weather_world_updates=weather_draws=0;
    inside=player_call=stage_call=zero_world=world_render=hud_call=ride_call=pickup_call=solid_call=0;
    private_draw=private_seat=view_call=zero_projected=0;local_split=split;independent_views=1;
    view_buffer=VIEW_BUFFER;view_pending=view_valid=1;view_menu_history=0;
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
static void defaults_and_scope(void) {
    CPUState cpu;prepare_view(&cpu,0,0);mmx6_view_sdk_reset();
    char value[24];CHECK(psx_mod_current_option_value("cameras",value,sizeof value) && !strcmp(value,"unified"));
    CHECK(!psx_mod_current_option_value("unknown",value,sizeof value));
    CHECK(!psx_mod_current_option_value("local_cameras",value,2));
    independent_activate();CHECK(!independent_views && !local_split && !mmx6_view_sdk.pair_enabled && !mmx6_view_sdk.aspect_calls);
    mmx6_view_sdk.local_cameras="split";independent_activate();
    CHECK(independent_views && local_split && mmx6_view_sdk.pair_enabled && mmx6_view_sdk.aspect_calls==1);
    PSXModStereoFrame pair={sizeof pair,1,0,0,320,240};PSXModRenderPass rect={sizeof rect,0,0,0,320,240};
    CHECK(!psx_mod_render_local_pair(&cpu,&pair,forbidden_callback,NULL)); /* no modeled backend */
    mmx6_view_sdk.transaction=model_transaction;
    CHECK(!psx_mod_render_local_view(&cpu,&rect,forbidden_callback,NULL)); /* offline */
    mmx6_view_sdk.online=1;CHECK(!psx_mod_set_local_pair_presentation(1));
    CHECK(!psx_mod_render_local_pair(&cpu,&pair,forbidden_callback,NULL)); /* netplay */
    mmx6_view_sdk.cameras="independent";independent_activate();
    CHECK(independent_views && !local_split && !mmx6_view_sdk.pair_enabled);
}
static void reentry(void) {
    CPUState cpu;prepare_view(&cpu,0,1);
    view_call=1;CHECK(!independent_present(&cpu,VIEW_DRAW_OT));
    view_call=0;private_draw=1;CHECK(!independent_present(&cpu,VIEW_DRAW_OT));
    private_draw=0;state_track.count=1;CHECK(!independent_present(&cpu,VIEW_DRAW_OT));
    state_track.count=0;state_track.error=1;CHECK(!independent_present(&cpu,VIEW_DRAW_OT));
    CHECK(!view_native_calls && !mmx6_view_sdk.pair_calls && !mmx6_view_sdk.view_calls && view_pending);
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
        independent_world_begin();CHECK(!view_pending && !view_valid && !view_native_calls);
    }
}
static void arrival_refusals(void) {
    const Mmx6CoopStatus blocked[]={MMX6_COOP_LEAVING,MMX6_COOP_ABSENT,MMX6_COOP_DYING,MMX6_COOP_FALLEN};
    for(unsigned i=0;i<sizeof blocked/sizeof blocked[0];++i) {
        CPUState cpu;prepare_view(&cpu,0,1);life.status[1]=blocked[i];
        independent_world_begin();CHECK(!view_pending && !view_valid && !view_native_calls);
    }
    for(unsigned gate=0;gate<5;++gate) {
        CPUState cpu;prepare_view(&cpu,0,1);life.status[1]=MMX6_COOP_JOINING;
        if(gate==0)scene_owner=1;else if(gate==1)pause_owner=0;
        else if(gate==2)psx_mod_write_byte(PLAY+0x1C,1);
        else if(gate==3)psx_mod_write_byte(PLAY+1,2);else life.status[0]=MMX6_COOP_DYING;
        independent_world_begin();CHECK(!view_pending && !view_valid && !view_native_calls);
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
        if(boundary==4 || boundary==5 || boundary==7) {
            CHECK(!view_pending && !view_valid && !view_menu_history);continue;
        }
        CHECK(view_pending && view_valid && !view_menu_history);
        for(unsigned layer=0;layer<3;++layer) {
            uint8_t actual[0x54];capture(VIEW_CAMERA+layer*0x54,actual,sizeof actual);
            CHECK(!memcmp(view_cameras[1]+layer*0x54,actual,8));
            CHECK(!memcmp(view_cameras[1]+layer*0x54+0x1C,actual+0x1C,0x38));
            CHECK(!memcmp(view_cameras[1]+layer*0x54+8,
                boundary?actual+8:prior+layer*0x54+8,0x14));
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
int main(void) {
    defaults_and_scope();reentry();native_arrival(0,1);native_arrival(1,0);arrival_refusals();
    native_nova_views(0,1);native_nova_views(1,0);
    native_menu_camera_history(0,1);native_menu_camera_history(1,0);
    native_shared_weather_frames(0,1);native_shared_weather_frames(1,0);
    presentation_restore(0,1,0,0);presentation_restore(0,1,1,0);presentation_restore(0,1,0,1);
    presentation_restore(1,0,0,0);presentation_restore(1,0,1,0);presentation_restore(1,0,0,1);
    clear_banks();puts("private-view typed defaults, scope, callback/abort host restoration and reentry contracts passed (modeled rendering)");return 0;
}
