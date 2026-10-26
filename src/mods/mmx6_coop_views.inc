/* SLUS-01395 draw-only private views. Shared simulation and the authoritative
 * image are never replaced by a peer's presentation transaction. */
#ifdef MMX6_COOP_MODERN_STATE
#include "psx_netplay.h"
enum { VIEW_CAMERA=0x800971F8u, VIEW_BUFFER=0x800C4578u,
       VIEW_STRIDE=0xF0u, VIEW_DRAW_OT=0x80066744u };
static uint8_t view_cameras[2][0xFC];
static uint32_t view_frame, view_buffer, view_ot[32];
static unsigned view_valid, view_pending;
static void independent_invalidate(void) { view_valid=view_pending=0; }

/* Immutable texture banks may grow while drawing. All mutable co-op host
 * context is restored after each pane, and again after an aborted callback.
 * CPU, guest memory, devices and VRAM are restored by the runtime sandbox. */
typedef struct {
    HostState core;
    PlayerContext first;
    uint8_t overlay[OVERLAY_SIZE],play[sizeof saved_play],camera[sizeof saved_camera];
    uint32_t resources[7];
    uint8_t palette_dirty;
    int inside,player_call,stage_call,zero_world,world_render,hud_call,
        render_x_death,effect_call,shared_fx_call,shared_fx_allocate_call,
        pickup_call,solid_call,solid_allocate_call,ride_call,
        scene_call,zero_projected,unit_choices_call,intro_target_call;
    unsigned track_count,track_error;
} PrivateViewContext;

static void private_context_save(PrivateViewContext *s) {
    state_capture(&s->core);s->first=p1;
    memcpy(s->overlay,saved_overlay,sizeof saved_overlay);
    memcpy(s->play,saved_play,sizeof saved_play);memcpy(s->camera,saved_camera,sizeof saved_camera);
    memcpy(s->resources,saved_resources,sizeof saved_resources);s->palette_dirty=saved_palette_dirty;
#define SAVE_VIEW_FLAG(name) s->name=name
    SAVE_VIEW_FLAG(inside);SAVE_VIEW_FLAG(player_call);SAVE_VIEW_FLAG(stage_call);
    SAVE_VIEW_FLAG(zero_world);SAVE_VIEW_FLAG(world_render);SAVE_VIEW_FLAG(hud_call);
    SAVE_VIEW_FLAG(render_x_death);SAVE_VIEW_FLAG(effect_call);SAVE_VIEW_FLAG(shared_fx_call);
    SAVE_VIEW_FLAG(shared_fx_allocate_call);SAVE_VIEW_FLAG(pickup_call);SAVE_VIEW_FLAG(solid_call);
    SAVE_VIEW_FLAG(solid_allocate_call);SAVE_VIEW_FLAG(ride_call);SAVE_VIEW_FLAG(scene_call);
    SAVE_VIEW_FLAG(zero_projected);SAVE_VIEW_FLAG(unit_choices_call);SAVE_VIEW_FLAG(intro_target_call);
#undef SAVE_VIEW_FLAG
    s->track_count=state_track.count;s->track_error=state_track.error;
}
static void private_context_restore(const PrivateViewContext *s) {
    state_commit(&s->core);p1=s->first;
    memcpy(saved_overlay,s->overlay,sizeof saved_overlay);
    memcpy(saved_play,s->play,sizeof saved_play);memcpy(saved_camera,s->camera,sizeof saved_camera);
    memcpy(saved_resources,s->resources,sizeof saved_resources);saved_palette_dirty=s->palette_dirty;
#define RESTORE_VIEW_FLAG(name) name=s->name
    RESTORE_VIEW_FLAG(inside);RESTORE_VIEW_FLAG(player_call);RESTORE_VIEW_FLAG(stage_call);
    RESTORE_VIEW_FLAG(zero_world);RESTORE_VIEW_FLAG(world_render);RESTORE_VIEW_FLAG(hud_call);
    RESTORE_VIEW_FLAG(render_x_death);RESTORE_VIEW_FLAG(effect_call);RESTORE_VIEW_FLAG(shared_fx_call);
    RESTORE_VIEW_FLAG(shared_fx_allocate_call);RESTORE_VIEW_FLAG(pickup_call);RESTORE_VIEW_FLAG(solid_call);
    RESTORE_VIEW_FLAG(solid_allocate_call);RESTORE_VIEW_FLAG(ride_call);RESTORE_VIEW_FLAG(scene_call);
    RESTORE_VIEW_FLAG(zero_projected);RESTORE_VIEW_FLAG(unit_choices_call);RESTORE_VIEW_FLAG(intro_target_call);
#undef RESTORE_VIEW_FLAG
    state_track.count=s->track_count;state_track.error=s->track_error;
}
static void independent_world_begin(void) {
    if(private_draw || !independent_views)return;
    view_pending=0;
    if(!enrolled || failed || inside || zero_world || scene_owner || pause_owner>=0 ||
       psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
       psx_mod_read_byte(PLAY+0x10) || psx_mod_read_byte(PLAY+0x1C) ||
       life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_ALIVE) {
        view_valid=0;return;
    }
    uint32_t buffer=psx_mod_read_word(0x8009B7A0u);
    if(buffer!=VIEW_BUFFER && buffer!=VIEW_BUFFER+VIEW_STRIDE)return;
    if(!view_valid || frame_count!=view_frame+1) {
        capture(VIEW_CAMERA,view_cameras[0],sizeof view_cameras[0]);
        memcpy(view_cameras[1],view_cameras[0],sizeof view_cameras[0]);
        view_valid=1;
    }
    /* Always take authored room/mode/atlas fields from this world's update.
     * Only the other camera's current/previous positions retain its history. */
    for(unsigned layer=0;layer<3;++layer) {
        uint8_t position[0x14];memcpy(position,view_cameras[1]+layer*0x54+8,sizeof position);
        capture(VIEW_CAMERA+layer*0x54,view_cameras[1]+layer*0x54,0x54);
        memcpy(view_cameras[1]+layer*0x54+8,position,sizeof position);
    }
    capture(VIEW_CAMERA,view_cameras[0],sizeof view_cameras[0]);
    for(unsigned i=0;i<32;++i)view_ot[i]=psx_mod_read_word(buffer+0x70+i*4);
    view_frame=frame_count;view_buffer=buffer;view_pending=1;
}
static int private_draw_image(CPUState *cpu,void *user,uint32_t unused) {
    (void)user;(void)unused;
    project(VIEW_CAMERA,view_cameras[private_seat],sizeof view_cameras[0]);
    if(private_seat) {
        uint8_t body[sizeof p2.body];capture(PLAYER,body,sizeof body);
        project(PLAYER,p2.body,sizeof p2.body);
        /* Original three camera updates only. Native pit/player clamping and
         * any authored scratch changes are sandboxed, never gameplay ticks. */
        guest(cpu,0x8002927C,0,0);guest(cpu,0x8002935C,0,0);guest(cpu,0x800293CC,0,0);
        capture(VIEW_CAMERA,view_cameras[1],sizeof view_cameras[1]);
        project(PLAYER,body,sizeof body);
    }
    for(unsigned i=0;i<32;++i)psx_mod_write_word(view_buffer+0x70+i*4,view_ot[i]);
    /* The retail ring currently belongs to the canonical camera. Rebuild it
     * from this pane's authored map before native streaming/packet emission. */
    for(unsigned layer=0;layer<3;++layer)psx_mod_write_byte(VIEW_CAMERA+layer*0x54+0x4C,1);
    gpu_set_gp0_source(0);
    gpu_write_gp0(0x02000000u|psx_mod_read_byte(view_buffer+0x2D)|
        (uint32_t)psx_mod_read_byte(view_buffer+0x2E)<<8|(uint32_t)psx_mod_read_byte(view_buffer+0x2F)<<16);
    gpu_write_gp0(psx_mod_read_half(view_buffer+0x14)|(uint32_t)psx_mod_read_half(view_buffer+0x16)<<16);
    gpu_write_gp0(psx_mod_read_half(view_buffer+0x18)|(uint32_t)psx_mod_read_half(view_buffer+0x1A)<<16);
    guest(cpu,0x80025FB0,0,0);
    if(failed || inside || world_render || hud_call || state_track.count || state_track.error)return 0;
    guest(cpu,VIEW_DRAW_OT,view_buffer+0xEC,0);guest(cpu,0x80066150,0,0);
    return !failed;
}
static int private_draw_pair(CPUState *cpu,void *user,uint32_t seat) {
    PrivateViewContext context;private_context_save(&context);
    private_seat=seat;private_draw=1;
    int ok=private_draw_image(cpu,user,0);
    private_context_restore(&context);private_draw=0;
    return ok;
}
static int independent_present(CPUState *cpu,uint32_t address) {
    if(!view_pending || view_call || private_draw || inside || zero_world || failed ||
       state_track.count || state_track.error ||
       cpu->gpr[31]!=0x80012128u || cpu->gpr[4]!=view_buffer+0xEC ||
       psx_mod_read_word(0x8009B7A0u)!=view_buffer)return 0;
    view_call=1;view_pending=0;
    uint32_t result=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    guest(cpu,0x80066150,0,0);
    PSXModRenderPass rect={sizeof rect,0,psx_mod_read_half(view_buffer+0x14),
        psx_mod_read_half(view_buffer+0x16),psx_mod_read_half(view_buffer+0x18),psx_mod_read_half(view_buffer+0x1A)};
    PrivateViewContext context;private_context_save(&context);
    uint8_t previous_camera[sizeof view_cameras[1]];memcpy(previous_camera,view_cameras[1],sizeof previous_camera);
    uint32_t before=state_digest();int committed;
    if(local_split) {
        PSXModStereoFrame pair={sizeof pair,1,rect.x,rect.y,rect.w,rect.h};
        committed=psx_mod_render_local_pair(cpu,&pair,private_draw_pair,NULL);
    } else {
        int port=psx_netplay_local_port();private_seat=port==1?1:0;private_draw=1;
        committed=psx_mod_render_local_view(cpu,&rect,private_draw_image,NULL);
    }
    private_context_restore(&context);private_draw=0;
    if(!committed)memcpy(view_cameras[1],previous_camera,sizeof previous_camera);
    if(state_digest()!=before)psx_mod_counter_add("mmx6.coop.private-state-leak",1);
    psx_mod_counter_add(committed?"mmx6.coop.private-committed":"mmx6.coop.private-refused",1);
    view_call=0;cpu->gpr[2]=result;return 1;
}
static void independent_activate(void) {
    char option[24];int online=psx_mod_netplay_is_active();
    local_split=!online && psx_mod_current_option_value("local_cameras",option,sizeof option) && !strcmp(option,"split");
    independent_views=local_split || (online && psx_mod_current_option_value("cameras",option,sizeof option) && !strcmp(option,"independent"));
    private_draw=private_seat=view_valid=view_pending=view_call=0;
    view_frame=view_buffer=0;memset(view_cameras,0,sizeof view_cameras);
    if(independent_views)(void)psx_mod_set_fixed_display_aspect(4,3);
    (void)psx_mod_set_local_pair_presentation((int)local_split);
    if(!psx_mod_set_function_replacement(VIEW_DRAW_OT,independent_present))failed=1;
}
#else
/* Older SDKs retain the working shared renderer. */
static void independent_invalidate(void) {}
static void independent_world_begin(void) {}
static void independent_activate(void) { independent_views=local_split=private_draw=private_seat=0; }
#endif
