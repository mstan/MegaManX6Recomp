/* Actual plugin host restoration against explicit draw/sandbox contracts.
 * No real renderer, GPU checkpoint, watchdog or native-game qualification. */
#include "cpu_state.h"
#include "mmx6_coop_private_view_sdk_fixture.h"
static unsigned view_native_calls,view_gpu_words,view_callback_calls,view_refuse,view_abort;
static int view_native(CPUState *,uint32_t,uint32_t);
static int view_gpu(uint32_t,unsigned);
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
    if(address==0x80066150u || address==0x8002927Cu || address==0x8002935Cu || address==0x800293CCu)return 1;
    CHECK(address==0x80025FB0u && private_draw);
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
    inside=player_call=stage_call=zero_world=world_render=hud_call=ride_call=pickup_call=solid_call=0;
    private_draw=private_seat=view_call=zero_projected=0;local_split=split;independent_views=1;
    view_buffer=VIEW_BUFFER;view_pending=view_valid=1;
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
int main(void) {
    defaults_and_scope();reentry();
    presentation_restore(0,1,0,0);presentation_restore(0,1,1,0);presentation_restore(0,1,0,1);
    presentation_restore(1,0,0,0);presentation_restore(1,0,1,0);presentation_restore(1,0,0,1);
    clear_banks();puts("private-view typed defaults, scope, callback/abort host restoration and reentry contracts passed (modeled rendering)");return 0;
}
