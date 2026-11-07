/* SLUS-01395 draw-only private views. Shared simulation and the authoritative
 * image are never replaced by a peer's presentation transaction. */
#ifdef MMX6_COOP_MODERN_STATE
#include "psx_netplay.h"
#include "gpu_render.h"
#if defined(__has_include)
#if __has_include("debug_native_entry_context.h")
#include "debug_native_entry_context.h"
#define MMX6_COOP_VIEW_ENTRY_CONTEXT 1
#endif
#endif
enum { VIEW_CAMERA=0x800971F8u, VIEW_BUFFER=0x800C4578u,
       VIEW_STRIDE=0xF0u, VIEW_DRAW_OT=0x80066744u };
static uint8_t view_cameras[2][0xFC];
static uint32_t view_frame, view_buffer, view_ot[32];
static unsigned view_valid, view_pending;
static unsigned view_menu_history;
static uint8_t view_menu_stage,view_menu_section,view_menu_checkpoint;
static uint8_t view_quake_input[0x54];
static uint32_t view_quake_frame;
static unsigned view_quake_valid;
static void independent_invalidate(void) { view_valid=view_pending=view_menu_history=view_quake_valid=0; }

/* Native PL00/font rectangles, as used by menu_vram. Capture the resident
 * character once before the other native initializer; every own-menu upload
 * below is journalled by the private render transaction. */
typedef struct { unsigned x,y,w,h,offset; } PersonalMenuRegion;
static const PersonalMenuRegion personal_regions[]={
    {896,256,64,256,0}, {960,256,64,256,0x8000},
    {256,496,64,16,0x10000}, {384,0,64,16,MENU_PORTRAIT},
    {448,0,64,16,MENU_PORTRAIT+0x800},
    {512,0,64,16,MENU_PORTRAIT+0x1000},
    {576,0,64,16,MENU_PORTRAIT+0x1800},
    {0,510,256,1,MENU_PORTRAIT_COLORS}
};
static void personal_menu_prepare_assets(CPUState *cpu) {
    if(!menu_memory || zero_projected)return;
    guest(cpu,0x80066150u,0,0);
    const uint16_t *vram=gpu_get_vram();
    for(unsigned i=0;i<sizeof personal_regions/sizeof *personal_regions;++i) {
        const PersonalMenuRegion *r=&personal_regions[i];
        uint32_t dst=menu_memory+MENU_BYTES+r->offset;
        for(unsigned y=0;y<r->h;++y)for(unsigned x=0;x<r->w;++x)
            psx_mod_write_half(dst+2u*(y*r->w+x),vram[(r->y+y)*1024u+r->x+x]);
    }
}
static void personal_menu_assets(CPUState *cpu,unsigned seat) {
    (void)cpu;
    if(!private_draw || seat>1 || !menu_memory)return;
    uint16_t pixels[64*256];
    for(unsigned i=0;i<sizeof personal_regions/sizeof *personal_regions;++i) {
        const PersonalMenuRegion *r=&personal_regions[i];
        uint32_t source=menu_memory+(seat?0:MENU_BYTES)+r->offset;
        for(unsigned n=0;n<r->w*r->h;++n)pixels[n]=psx_mod_read_half(source+n*2u);
        gr_vram_transfer_in((int)r->x,(int)r->y,(int)r->w,(int)r->h,pixels);
    }
    /* Native menu updates select colors in the currently projected working
     * bank. Include cursor, font and portrait rows; a resident GPU CLUT is not
     * the other character's palette. */
    uint32_t source=psx_mod_read_word(SCRATCH+0x28);
    for(unsigned n=0;n<256u*32u;++n)pixels[n]=psx_mod_read_half(source+n*2u);
    gr_vram_transfer_in(0,480,256,32,pixels);
}
static void private_menu_fade(uint32_t buffer) {
    unsigned shade=personal_menu_fade(buffer);
    if(!shade)return;
    unsigned parity=buffer==VIEW_BUFFER+VIEW_STRIDE;
    /* Original135C0/135C4 and13640 publish this exact subtractive draw mode. */
    uint32_t mode=psx_mod_read_word(0x800CF96Cu+parity*8u);
    if((mode>>24)!=0xE1u)mode=0xE1000045u;
    gpu_set_gp0_source(0);gpu_write_gp0(mode);
    gpu_write_gp0(0x62000000u|shade|(shade<<8)|(shade<<16));
    gpu_write_gp0(0);
    gpu_write_gp0(psx_mod_read_half(buffer+0x18u)|
                  (uint32_t)psx_mod_read_half(buffer+0x1Au)<<16);
}


static int independent_intro_camera_source(void) {
    /* SLUS-01395 original5211C inclusive body/record test and request writes.
     * All eight intro rows include factory entry/exit, the later boss
     * approach and CP1's dynamic896 request. Keeping only factory rows2/3
     * would incorrectly pin this view at704 after leaving that region. */
    static const uint32_t code[][2]={
        {0x80052134u,0x3C028009u},{0x80052138u,0x244570A0u},
        {0x80052140u,0x84A4000Au},{0x8005216Cu,0x84A4000Eu},
        {0x800521A0u,0xA0830047u},{0x800521BCu,0xA4820026u},
        {0x800521D8u,0xA4820024u},{0x800521F4u,0xA482002Au},
        {0x80052210u,0xA4820028u}};
    for(unsigned i=0;i<sizeof code/sizeof code[0];++i)
        if(psx_mod_read_word(code[i][0])!=code[i][1])return 0;
    return psx_mod_read_word(0x80079D70u)==0x800791F0u &&
        checkpoint_hash(0x800791F0u,0x80079270u)==0x1498A845u;
}
static void independent_intro_camera_requests(void) {
    if(psx_mod_read_byte(PLAY+12) || psx_mod_read_byte(PLAY+13)) {
        intro_camera_valid=0;memset(intro_camera_requests,0,sizeof intro_camera_requests);return;
    }
    if(!independent_intro_camera_source()) {
        intro_camera_valid=0;memset(intro_camera_requests,0,sizeof intro_camera_requests);return;
    }
    if(!intro_camera_valid) {
        capture(VIEW_CAMERA+0x24,intro_camera_requests,sizeof intro_camera_requests);
        intro_camera_valid=1;
    }
    int x=(int16_t)(le32(p2.body+8)>>16),y=(int16_t)(le32(p2.body+12)>>16);
    for(uint32_t record=0x800791F0u;record<0x80079270u;record+=16) {
        /* 5214C/52160/52178/5218C reject strictly outside both inclusive
         * ranges. FFFF in a request field means leave that limit alone. */
        if(x<(int)psx_mod_read_half(record) || x>(int)psx_mod_read_half(record+2) ||
           y<(int)psx_mod_read_half(record+4) || y>(int)psx_mod_read_half(record+6))continue;
        static const uint8_t offsets[]={2,0,6,4};
        for(unsigned i=0;i<4;++i) {
            uint16_t value=psx_mod_read_half(record+8+i*2);
            if(value==0xFFFFu)continue;
            unsigned at=offsets[i];intro_camera_requests[at]=(uint8_t)value;
            intro_camera_requests[at+1]=(uint8_t)(value>>8);
        }
    }
}
static int independent_intro_background(void) {
    return private_draw && psx_mod_read_byte(PLAY+12)==0 && psx_mod_read_byte(PLAY+13)==0;
}
static void independent_background_begin(CPUState *cpu,uint32_t address) {
    (void)address;
    if(!independent_intro_background())return;
    mmx6_adaptive_background_begin(cpu->gpr[4]);
    gpu_ws_bg2d_begin_view_layer(cpu->gpr[4],psx_mod_read_word(SCRATCH+0x108),6u);
}
static void independent_background_end(CPUState *cpu,uint32_t address) {
    (void)address;
    if(independent_intro_background())
        mmx6_private_background_end(cpu->gpr[4],psx_mod_read_word(SCRATCH+0x108));
}

/* The canonical native camera advances the shared quake before world drawing.
 * Give the other native camera that same input, rather than a second tick of
 * the canonical result. This cache is draw-only, never serialized or digested. */
static void independent_camera_begin(CPUState *cpu,uint32_t address) {
    (void)cpu;(void)address;
    if(private_draw)return;
    view_quake_valid=0;
    if(!independent_views || !enrolled || failed || inside || zero_world ||
       psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1))return;
    if(!scene_owner && !clear_phase && pause_owner<0 &&
       life.status[0]==MMX6_COOP_ALIVE && life.status[1]==MMX6_COOP_ALIVE)
        independent_intro_camera_requests();
    capture(VIEW_CAMERA,view_quake_input,sizeof view_quake_input);
    view_quake_frame=frame_count;view_quake_valid=1;
}
static int independent_quake_input(void) {
    /* All remaining authored camera fields and per-hero position history
     * still come from independent_world_begin. Original 29A6C/29AFC own these
     * two timers, step counters/steps, phases and amplitudes only. */
    static const uint8_t offsets[]={0x36,0x37,0x3A,0x3B,0x3C,0x3D,0x3E,0x3F,0x45,0x46};
    if(!view_quake_valid || view_quake_frame!=view_frame)
        return !(view_cameras[0][0x34]&0x11u);
    psx_mod_write_byte(VIEW_CAMERA+0x34,(psx_mod_read_byte(VIEW_CAMERA+0x34)&~0x11u) |
        (view_quake_input[0x34]&0x11u));
    for(unsigned i=0;i<sizeof offsets;++i)
        psx_mod_write_byte(VIEW_CAMERA+offsets[i],view_quake_input[offsets[i]]);
    return 1;
}

#ifdef MMX6_COOP_VIEW_ENTRY_CONTEXT
enum { VIEW_CONTEXT_PROVIDER=0x36564350u }; /* Diagnostic PCV6, not semantic state. */
static int private_view_entry_context(uint32_t function,PSXDebugNativeContextWords *out,void *opaque) {
    (void)opaque;
#if PSX_DEBUG_NATIVE_CONTEXT_AVAILABLE
    if(!out || !private_draw || private_seat>1 || !view_valid)return 0;
    if(function==0x80026D44u) {
        /* Draw-entry evidence for the shared layer1 phase actually supplied
         * to this view. Host-owned cached words only; no guest access/calls.
         * Bit7 identifies this additive layer context, distinct from the
         * existing 25FB0 foreground/quake context below. */
        const uint8_t *layer=view_cameras[private_seat]+0x54;
        out->flags=0x81u | private_seat<<1;
        out->state0=frame_count;out->state1=le32(layer+8);out->state2=le32(layer+12);
        return 1;
    }
    if(function!=0x80025FB0u)return 0;
    /* Only host-owned words: Zero's native camera updates are captured into
     * this array before 25FB0. No guest reads/calls, allocation or mutation.
     * flags: bit0 private, bit1 seat, bits2/3 vertical/horizontal quake;
     * bytes1/2/3 are native vertical timer37/amplitude46/phase3F verbatim. */
    const uint8_t *camera=view_cameras[private_seat];
    out->flags=1u | private_seat<<1 | (uint32_t)(camera[0x34]&1u)<<2 |
        (uint32_t)(camera[0x34]&0x10u)>>1 | (uint32_t)camera[0x37]<<8 |
        (uint32_t)camera[0x46]<<16 | (uint32_t)camera[0x3F]<<24;
    out->state0=frame_count;out->state1=le32(camera+8);out->state2=le32(camera+12);
    return 1;
#else
    (void)function;(void)out;return 0;
#endif
}
#endif

/* A native personal menu suspends the world but diagnostics keep publishing.
 * Preserve the guest camera's history, never a stale rendered image. A scene,
 * life, room/checkpoint or load boundary still discards that history. */
static int independent_menu_context(void) {
    if(!enrolled || failed || scene_owner || psx_mod_read_byte(PLAY)!=10)return 0;
    for(unsigned seat=0;seat<2;++seat)
        if(life.status[seat]!=MMX6_COOP_ALIVE &&
           (!view_valid || (life.status[seat]!=MMX6_COOP_DYING &&
                            life.status[seat]!=MMX6_COOP_FALLEN)))return 0;
    return life.status[0]==MMX6_COOP_ALIVE || life.status[1]==MMX6_COOP_ALIVE;
}
static void independent_menu_begin(void) {
    if(private_draw || !independent_views || !view_valid || view_menu_history ||
       pause_owner<0 || !independent_menu_context() ||
       (psx_mod_read_byte(PLAY+1)!=0 && psx_mod_read_byte(PLAY+1)!=2))return;
    view_menu_stage=psx_mod_read_byte(PLAY+12);
    view_menu_section=psx_mod_read_byte(PLAY+13);
    view_menu_checkpoint=psx_mod_read_byte(PLAY+0x1D);
    view_menu_history=1;
}

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
        scene_call,zero_projected,unit_choices_call,target_projection_call,
        personal_pass,personal_seat,personal_rendering;
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
    SAVE_VIEW_FLAG(zero_projected);SAVE_VIEW_FLAG(unit_choices_call);SAVE_VIEW_FLAG(target_projection_call);
    SAVE_VIEW_FLAG(personal_pass);SAVE_VIEW_FLAG(personal_seat);SAVE_VIEW_FLAG(personal_rendering);
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
    RESTORE_VIEW_FLAG(zero_projected);RESTORE_VIEW_FLAG(unit_choices_call);RESTORE_VIEW_FLAG(target_projection_call);
    RESTORE_VIEW_FLAG(personal_pass);RESTORE_VIEW_FLAG(personal_seat);RESTORE_VIEW_FLAG(personal_rendering);
#undef RESTORE_VIEW_FLAG
    state_track.count=s->track_count;state_track.error=s->track_error;
}
/* Both doors own the native scene lock while each admitted body earns its
 * acknowledgement and traverses. They still have two living native views.
 * A released body, reused actor or later dialogue cannot lend that permission
 * to an unrelated shared scene. This changes drawing only. */
static int independent_door_context(void) {
    if(!both_door_traversal_active() || both_door_members!=3 ||
       life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_ALIVE ||
       psx_mod_read_byte(both_door_actor+4)!=1 ||
       (!psx_mod_read_byte(PLAYER+0xD4) && !p2.body[0xD4]))return 0;
    unsigned phase=psx_mod_read_byte(both_door_actor+5);
    return phase>=1 && phase<=3;
}
static int independent_scene_context(void) {
    if(!scene_owner || scene_owner>2 || both_door_actor)return 0;
    /* Use serialized scene/body state, including after current-build load.
     * Diagnostic event history must never authorize presentation. */
    if(scene_phase || scene_shared_locked())return 1;
    return scene_owner==2?(p2.body[0xD0] || p2.body[0xD4] || p2.body[0x7A]):
        (psx_mod_read_byte(PLAYER+0xD0) || psx_mod_read_byte(PLAYER+0xD4) ||
         psx_mod_read_byte(PLAYER+0x7A));
}
static int independent_heatnix_scenery(void) {
    if(psx_mod_read_byte(PLAY+12)!=3 || psx_mod_read_byte(PLAY+13))return 0;
    uint32_t actor=psx_mod_read_word(PLAY+0x20);
    return actor>=0x8008EF48u && actor<0x80090C88u && !((actor-0x8008EF48u)%0x9Cu) &&
        psx_mod_read_byte(actor) && psx_mod_read_byte(actor+1)==52 &&
        !psx_mod_read_byte(actor+2) && psx_mod_read_byte(actor+4)==1 &&
        psx_mod_read_word(actor+0x10)==0x800F36C8u;
}
static void independent_world_begin(void) {
    if(private_draw || !independent_views || (personal_pass && personal_seat))return;
    view_pending=0;
    int returning=personal_resuming_world();
    int initial=arrival_pair && !zero_projected && life.status[0]==MMX6_COOP_ALIVE &&
        life.status[1]==MMX6_COOP_JOINING && !psx_mod_read_byte(PLAY+1) &&
        (psx_mod_read_byte(PLAY)==9 || psx_mod_read_byte(PLAY)==10);
    /* The living guest can host the one native world after P1 falls. Record
     * that world's authored metadata/empty OT before drawing; the dead P1
     * camera remains retained and the common presenter runs after projection. */
    int guest_host=inside && zero_world && !personal_pass &&
        (life.status[0]==MMX6_COOP_DYING || life.status[0]==MMX6_COOP_FALLEN) &&
        life.status[1]==MMX6_COOP_ALIVE && psx_mod_read_byte(PLAY)==10 &&
        !psx_mod_read_byte(PLAY+1);
    int menu_history=view_menu_history && independent_menu_context() &&
        psx_mod_read_byte(PLAY+12)==view_menu_stage &&
        psx_mod_read_byte(PLAY+13)==view_menu_section &&
        psx_mod_read_byte(PLAY+0x1D)==view_menu_checkpoint;
    int door_views=independent_door_context();
    /* A shared story camera does not merge the heroes' HUD ownership. Draw
     * that camera in both panes while each pane retains its own native HUD.
     * The simulation still owns all withdrawal and scene/hold decisions. */
    int scene_views=independent_scene_context();
    /* A P2-owned script draws its one native world inside Zero's projected
     * stage call. Queue that authored world now; the common presenter runs
     * after projection restores, with each pane's own HUD. Rejecting it here
     * exposes the canonical stacked HUD during warning/dialogue frames. */
    int scene_host=scene_views && scene_owner==2 && inside && zero_world && !personal_pass;
    if(!enrolled || failed || (inside && !(returning && personal_pass && !personal_seat) && !initial && !guest_host && !scene_host) ||
       (zero_world && !guest_host && !scene_host) || (scene_owner && !door_views && !scene_views) || clear_phase ||
       (pause_owner>=0 && psx_mod_read_byte(PLAY+1) && !returning) ||
       (psx_mod_read_byte(PLAY)!=10 && !initial) ||
       (psx_mod_read_byte(PLAY+1) && !returning) ||
       (psx_mod_read_byte(PLAY+0x10) && !door_views && !scene_views && !initial) ||
       (coop_world_hold() && !door_views && !scene_views && !returning && !initial) ||
       (life.status[0]!=MMX6_COOP_ALIVE &&
        (!view_valid || (life.status[0]!=MMX6_COOP_DYING && life.status[0]!=MMX6_COOP_FALLEN))) ||
       (life.status[1]!=MMX6_COOP_ALIVE && life.status[1]!=MMX6_COOP_JOINING &&
        (!view_valid || (life.status[1]!=MMX6_COOP_DYING && life.status[1]!=MMX6_COOP_FALLEN)))) {
        if(!menu_history || (pause_owner<0 && psx_mod_read_byte(PLAY+1)!=2))
            independent_invalidate();
        return;
    }
    uint32_t buffer=psx_mod_read_word(0x8009B7A0u);
    if(buffer!=VIEW_BUFFER && buffer!=VIEW_BUFFER+VIEW_STRIDE)return;
    if(scene_views && scene_phase) {
        capture(VIEW_CAMERA,view_cameras[0],sizeof view_cameras[0]);
        memcpy(view_cameras[1],view_cameras[0],sizeof view_cameras[0]);
        view_valid=1;view_menu_history=0;
        for(unsigned i=0;i<32;++i)view_ot[i]=psx_mod_read_word(buffer+0x70+i*4);
        view_frame=frame_count;view_buffer=buffer;view_pending=1;
        return;
    }
    int fresh=!view_valid || (!menu_history && frame_count!=view_frame+1);
    if(fresh) {
        if(!view_valid || life.status[0]==MMX6_COOP_ALIVE)
            capture(VIEW_CAMERA,view_cameras[0],sizeof view_cameras[0]);
        if(!view_valid || life.status[1]==MMX6_COOP_ALIVE || life.status[1]==MMX6_COOP_JOINING)
            memcpy(view_cameras[1],view_cameras[0],sizeof view_cameras[0]);
        view_valid=1;
    }
    view_menu_history=0;
    /* Always take authored room/mode/atlas fields from this world's update.
     * Only the other camera's current/previous positions retain its history. */
    for(unsigned layer=0;layer<3;++layer) {
        /* Turtloid's original weather controller (800ED510) owns layer1
         * mode5 X/Y as blank/rain and five-frame atlas selectors. They are
         * shared animation metadata, not this hero's camera position. */
        if(layer==1 && psx_mod_read_byte(PLAY+12)==6 &&
           !psx_mod_read_byte(PLAY+13) && psx_mod_read_byte(VIEW_CAMERA+0x54+4)==5) {
            capture(VIEW_CAMERA+0x54,view_cameras[1]+0x54,0x54);
            continue;
        }
        uint8_t position[0x14],limits[16];memcpy(position,view_cameras[1]+layer*0x54+8,sizeof position);
        int intro=layer==0 && intro_camera_valid && !psx_mod_read_byte(PLAY+12) && !psx_mod_read_byte(PLAY+13);
        if(intro)memcpy(limits,view_cameras[1]+0x1C,sizeof limits);
        capture(VIEW_CAMERA+layer*0x54,view_cameras[1]+layer*0x54,0x54);
        if(intro) {
            /* Native2927C consumes requests24..2B and owns the current
             * limits1C..23. Keep its per-view interpolation history; after
             * load/invalidation, start at the restored authored limits. */
            memcpy(view_cameras[1]+0x1C,fresh?intro_camera_requests:limits,8);
            memcpy(view_cameras[1]+0x24,intro_camera_requests,8);
            view_cameras[1][0x47]=2;
        }
        /* Recycle's original 46F10 owns mode9's autonomous Y. Native
         * 297BC updates only X for the viewing hero, so retaining the old
         * guest Y freezes this shared controller in that pane. Publish its
         * current/previous Y once; keep the hero's X and other layer history.
         * Original Heatnix EF0FC likewise owns mode9 Y during its boss phases
         * (8B1/3 -> -2; 8B2/4 -> +2). Qualify that actual authored boss;
         * unrelated Magma controllers keep their ordinary camera history.
         * Native 297BC still computes each viewing hero's X independently. */
        unsigned stage=psx_mod_read_byte(PLAY+12),section=psx_mod_read_byte(PLAY+13);
        if(layer==1 && view_cameras[1][0x54+4]==9 &&
           ((stage==4 && section==0) || (stage==20 && section==1) ||
            independent_heatnix_scenery())) {
            memcpy(position+4,view_cameras[1]+0x54+12,4);
            memcpy(position+0x10,view_cameras[1]+0x54+0x18,4);
        }
        memcpy(view_cameras[1]+layer*0x54+8,position,sizeof position);
    }
    /* A fallen hero retains its last view and own HUD while the survivor
     * continues. Never aim a camera at its retiring/death body. */
    if(life.status[0]==MMX6_COOP_ALIVE)
        capture(VIEW_CAMERA,view_cameras[0],sizeof view_cameras[0]);
    for(unsigned i=0;i<32;++i)view_ot[i]=psx_mod_read_word(buffer+0x70+i*4);
    view_frame=frame_count;view_buffer=buffer;view_pending=1;
}
static int private_draw_image(CPUState *cpu,void *user,uint32_t unused) {
    (void)user;(void)unused;
    int menu=personal_menus_active(),returning=personal_resuming_world();
    if(!menu)project(VIEW_CAMERA,view_cameras[private_seat],sizeof view_cameras[0]);
    if(!menu && !returning && pause_owner<0 && private_seat &&
       (!scene_owner || !scene_phase || independent_door_context()) &&
       (life.status[1]==MMX6_COOP_ALIVE || life.status[1]==MMX6_COOP_JOINING)) {
        if(!independent_quake_input())return 0;
        uint8_t body[sizeof p2.body];capture(PLAYER,body,sizeof body);
        project(PLAYER,p2.body,sizeof p2.body);
        /* The native incoming beam starts above the room. Keep its camera
         * on the real landing point while drawing the actual beam body. The
         * projection is draw-only and never changes either player's update. */
        if(life.status[1]==MMX6_COOP_JOINING) {
            psx_mod_write_word(PLAYER+12,(uint32_t)join_y);
            psx_mod_write_word(PLAYER+0x1C,(uint32_t)join_y);
        }
        /* Original three camera updates only. Native pit/player clamping and
         * any authored scratch changes are sandboxed, never gameplay ticks. */
        guest(cpu,0x8002927C,0,0);guest(cpu,0x8002935C,0,0);guest(cpu,0x800293CC,0,0);
        capture(VIEW_CAMERA,view_cameras[1],sizeof view_cameras[1]);
        project(PLAYER,body,sizeof body);
    }
    if(menu || returning)
        guest(cpu,0x8006663Cu,view_buffer+0x70u,32); /* Original12150 ClearOTagR. */
    else for(unsigned i=0;i<32;++i)psx_mod_write_word(view_buffer+0x70+i*4,view_ot[i]);
    /* The retail ring currently belongs to the canonical camera. Rebuild it
     * from this pane's authored map before native streaming/packet emission. */
    for(unsigned layer=0;layer<3;++layer)psx_mod_write_byte(VIEW_CAMERA+layer*0x54+0x4C,1);
    gpu_set_gp0_source(0);
    gpu_write_gp0(0x02000000u|psx_mod_read_byte(view_buffer+0x2D)|
        (uint32_t)psx_mod_read_byte(view_buffer+0x2E)<<8|(uint32_t)psx_mod_read_byte(view_buffer+0x2F)<<16);
    gpu_write_gp0(psx_mod_read_half(view_buffer+0x14)|(uint32_t)psx_mod_read_half(view_buffer+0x16)<<16);
    gpu_write_gp0(psx_mod_read_half(view_buffer+0x18)|(uint32_t)psx_mod_read_half(view_buffer+0x1A)<<16);
    if(menu) {
        if(!personal_menu_draw(cpu,private_seat))return 0;
    } else guest(cpu,0x80025FB0,0,0);
    if(failed || inside || world_render || hud_call || state_track.count || state_track.error)return 0;
    guest(cpu,VIEW_DRAW_OT,view_buffer+0xEC,0);guest(cpu,0x80066150,0,0);
    private_menu_fade(view_buffer);
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
    if(view_call || private_draw || inside || zero_world || failed ||
       state_track.count || state_track.error || cpu->gpr[31]!=0x80012128u)return 0;
    int menu=personal_menus_active();
    uint32_t buffer=psx_mod_read_word(0x8009B7A0u);
    if((buffer!=VIEW_BUFFER && buffer!=VIEW_BUFFER+VIEW_STRIDE) || cpu->gpr[4]!=buffer+0xEC)return 0;
    if(!local_split && !psx_mod_netplay_is_active())
        (void)psx_mod_set_local_pair_presentation(menu);
    if(menu) { view_pending=1;view_buffer=buffer; }
    if(!view_pending || view_buffer!=buffer)return 0;
    view_call=1;view_pending=0;
    uint32_t result=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    guest(cpu,0x80066150,0,0);
    PSXModRenderPass rect={sizeof rect,0,psx_mod_read_half(view_buffer+0x14),
        psx_mod_read_half(view_buffer+0x16),psx_mod_read_half(view_buffer+0x18),psx_mod_read_half(view_buffer+0x1A)};
    PrivateViewContext context;private_context_save(&context);
    uint8_t previous_camera[sizeof view_cameras[1]];memcpy(previous_camera,view_cameras[1],sizeof previous_camera);
    unsigned door_phase=independent_door_context()?psx_mod_read_byte(both_door_actor+5):0;
    uint32_t before=state_digest();int committed;
    if(local_split || (menu && !psx_mod_netplay_is_active())) {
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
    if(committed && door_phase>=1 && door_phase<=3) {
        static const char *const phases[]={"mmx6.coop.private-door-ack",
            "mmx6.coop.private-door-opening","mmx6.coop.private-door-traversal"};
        psx_mod_counter_add(phases[door_phase-1],1);
    }
    view_call=0;cpu->gpr[2]=result;return 1;
}
static void independent_activate(void) {
    char option[24];int online=psx_mod_netplay_is_active();
    local_split=!online && psx_mod_current_option_value("local_cameras",option,sizeof option) && !strcmp(option,"split");
    /* Every online peer presents its own HUD in a private render transaction.
     * Older stored shared-view choices must not expose the canonical stacked
     * HUD. A selected online split still gives each pane its own meters. */
    int own_view=online;
    if(online && psx_mod_current_option_value("cameras",option,sizeof option)) {
        local_split=!strcmp(option,"split");
        own_view=!local_split;
    }
    independent_views=local_split || own_view;
    if(independent_views && !mmx6_adaptive_background_activate())failed=1;
    private_draw=private_seat=view_valid=view_pending=view_call=view_menu_history=0;
    view_frame=view_buffer=0;memset(view_cameras,0,sizeof view_cameras);
    view_quake_valid=view_quake_frame=0;memset(view_quake_input,0,sizeof view_quake_input);
#ifdef MMX6_COOP_VIEW_ENTRY_CONTEXT
    if(independent_views)(void)psx_debug_native_context_register(VIEW_CONTEXT_PROVIDER,private_view_entry_context,NULL);
#endif
    if(independent_views)(void)psx_mod_set_fixed_display_aspect(4,3);
    /* The session reset revokes this SDK permission. Request it only for
     * the explicitly selected online pair, before enabling its canvas. */
    if(online && local_split)(void)psx_mod_set_render_pass_netplay(1);
    (void)psx_mod_set_local_pair_presentation((int)local_split);
    if(!psx_mod_set_function_replacement(VIEW_DRAW_OT,independent_present))failed=1;
}
#else
/* Older SDKs retain the working shared renderer. */
static void independent_invalidate(void) {}
static void personal_menu_prepare_assets(CPUState *cpu) { (void)cpu; }
static void personal_menu_assets(CPUState *cpu,unsigned seat) { (void)cpu;(void)seat; }
static void independent_menu_begin(void) {}
static void independent_world_begin(void) {}
static void independent_camera_begin(CPUState *cpu,uint32_t address) { (void)cpu;(void)address; }
static void independent_background_begin(CPUState *cpu,uint32_t address) { (void)cpu;(void)address; }
static void independent_background_end(CPUState *cpu,uint32_t address) { (void)cpu;(void)address; }
static void independent_activate(void) { independent_views=local_split=private_draw=private_seat=0; }
#endif
