/* Local co-op development plugin. Not part of the preloaded release catalog.
 * The native world still runs once. A second player pass projects a host-owned
 * context into the game's singleton player addresses, then restores P1.
 * Resource evidence: SLUS-01395 USA v1.1, Tweaks workbook IngameTable and
 * FilesIndex; instruction boundaries verified against the original executable.
 */
#include "mod_plugins.h"
#include "mod_netplay.h"
#include "mmx6_coop_host_lab.h"
#include "mmx6_coop_host_lab_contract.h"
#include "mmx6_diagnostics.h"
#if defined(__has_include)
#if __has_include("session_input_taint.h")
#include "session_input_taint.h"
#define MMX6_COOP_INPUT_TAINT_API 1
#endif
#endif
#if defined(__has_include)
#if __has_include("mod_snapshot.h")
#define MMX6_COOP_MODERN_STATE 1
#include "mod_snapshot.h"
#include "psx_sha256.h"
#endif
#endif
#include "cpu_state.h"
#include "sio.h"
#include "gpu.h"
#include "mmx6_coop_assets.h"
#include "mmx6_coop_resources.h"
#include "mmx6_coop_lifecycle.h"
#include "mmx6_coop_sprite_packet.h"
#include "mmx6_coop_pixel_codec.h"
#include "mmx6_coop_effect_diagnostic.h"
#include "mmx6_coop_box_diagnostic.h"
#include "mmx6_adaptive_background.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PLAYER 0x800970A0u
#define PLAY 0x800CCED0u
#define RIDE 0x800CD340u
#define OVERLAY 0x801EA000u
#define OVERLAY_SIZE 0xB000u
#define SCRATCH 0x1F800000u
#define ASSET_SPACE 0x80000u
#define FRAME_ARENA 0x20000u
/* Native 800232D4 emits one 40-byte sprite plus one 8-byte mode tag per
 * primitive, with a shared 1000-primitive budget. Expanded GT3 pairs occupy
 * the middle 80000 bytes; retain mode tags in this same owned frame arena. */
enum { PLAYER_PACKET_LIMIT=1000, PLAYER_PACKET_BYTES=PLAYER_PACKET_LIMIT*40,
       PLAYER_MODE_OFFSET=PLAYER_PACKET_BYTES*3 };

typedef struct {
    uint8_t body[0x158];
    uint8_t shots[0x1400];
    uint8_t trails[0x120];
    uint8_t effects[0xF0];
} PlayerContext;
typedef struct {
    uint32_t source;
    uint16_t id,tile;
    uint8_t character;
    uint8_t colors[32];
    uint32_t pixel_bytes;
    uint8_t *pixels; /* Canonical immutable encoded pixels; never serialize this pointer. */
} SpriteBank;
static PlayerContext p2, p1;
/* Resource identity belongs to the projected actor, independently of seat.
 * Native roster admission binds one descriptor for every private helper. */
static const Mmx6CoopRosterActor default_private_actor={1,5,1,0x3D,85,1,165,166};
static Mmx6CoopRosterActor private_actor={1,5,1,0x3D,85,1,165,166};
static unsigned partner_x_armor; /* Immutable prototype choice; no live switch. */
static int private_roster_bind(const Mmx6CoopRoster *roster) {
    if(mmx6_coop_roster_validate(roster)!=MMX6_COOP_ROSTER_OK)return 0;
    private_actor=roster->seat[1];
    return 1;
}
static uint8_t saved_overlay[OVERLAY_SIZE], zero_overlay[OVERLAY_SIZE];
/* Original Zero Giga801EA7A4/801EA888 retains16 shared words80090CD0 in
 * writable overlay801EF974 across player callbacks. Keep that data separate
 * from the immutable executable image and its source/asset identity. */
enum { ZERO_GIGA_BACKUP_OFFSET=0x5974, ZERO_GIGA_BACKUP_BYTES=64 };
static uint8_t zero_giga_backup[ZERO_GIGA_BACKUP_BYTES];
static uint8_t saved_play[0xE0], saved_camera[0x100];
/* Only energy is private. Native P1 RAM remains the campaign/card authority;
 * found tanks and the Weapon Tank retain their original shared ownership. */
static unsigned separate_subtanks,subtank_seeded,subtank_found;
static unsigned checkpoint_fatal_option,checkpoint_fatal_state;
static unsigned checkpoint_hatch_stagger_option,checkpoint_hatch_stagger_state;
static uint8_t zero_subtanks[2];
static uint8_t *zero_compressed;
static size_t compressed_size;
static uint32_t assets, assembly, palette_source, active_palette, packets, diagnostic;
static uint32_t saved_resources[7], frame_count;
static uint32_t menu_memory, menu_assembly;
enum { MENU_PORTRAIT=0x10800, MENU_PORTRAIT_COLORS=0x12800, MENU_BYTES=0x12A00,
       MENU_PLAYER_BACKUP=MENU_BYTES*2, MENU_STORAGE_BYTES=MENU_PLAYER_BACKUP+0x8000 };
static uint8_t saved_portrait_colors[0x200];
static int zero_menu_loaded;
static uint8_t saved_palette_dirty;
static uint16_t previous_input, p2_edges;
static SpriteBank banks[4096];
static unsigned bank_count;
static int inside, ready, enrolled, failed;
static Mmx6CoopLifecycle life;
static uint8_t returning_body[0x158];
/* A real fortress refight return keeps a living guest's personal resources.
 * The existing return body owns the saved bytes; this is the authored target
 * checkpoint, consumed once after fresh native body/parts initialization. */
static unsigned refight_return_checkpoint;
static unsigned join_phase;
/* Fresh native arrival only; voluntary Select returns retain join_phase. */
static unsigned arrival_pair;
static int32_t join_y;
static int player_call, stage_call, zero_world, world_render;
static int pause_owner = -1, p2_start_previous;
static uint32_t world_packets;
static uint32_t hud_packets;
static int hud_call, hud_seat;
/* Stack Zero's native meters below X in the same left-anchored column. */
enum { P2_HUD_Y=104 };
static unsigned p2_hud_fade=128;
static uint16_t *zero_ui_pixels;
typedef struct { uint16_t page, clut, uv, id, colors[16]; } UiBank;
static UiBank ui_banks[4096];
static unsigned ui_bank_count;
static int render_x_death, effect_call;
/* Native shared112-byte effects outlive their creating player callback. */
static uint8_t shared_effect_owners[96]; /* 0 unowned, 1 primary, 2 private counterpart. */
static int shared_fx_call,shared_fx_allocate_call;
typedef struct { uint32_t x,y,assembly; uint8_t layer,valid,owner; } DeathEffectOrigin;
static DeathEffectOrigin death_effect[96];
typedef struct { uint32_t actor; uint8_t seat; } PickupOwner;
static PickupOwner pickup_owners[128];
static int pickup_call;
/* Native stage solids and X's Ice Burst keep one player's contact at +72/+76.
 * Keep Zero's copy on the host; +73/+77 still belong to the ride armor. */
typedef struct { uint8_t sides, carried; } SolidContact;
enum { STAGE_SOLID_CONTACTS=80, WEAPON_SOLID_CONTACTS=32,
       SOLID_CONTACTS=STAGE_SOLID_CONTACTS+WEAPON_SOLID_CONTACTS };
static SolidContact zero_solid_contacts[SOLID_CONTACTS];
static int solid_call, solid_allocate_call;
static int ride_call;
/* Scene transport is independent of voluntary absence and death. The owner
 * occupies the native singleton for the one world pass until control returns. */
static unsigned scene_owner, scene_phase;
static uint8_t scene_body[0x158];
static int32_t scene_y;
static int scene_call, zero_projected;
static unsigned clear_phase,clear_members,clear_started;
/* Immutable committed gameplay choice; Either retains the original policy. */
static unsigned both_doors;
/* The actual door and living roster authenticated by its native overlap.
 * A generic scene with phase zero is not permission for dual traversal. */
static uint32_t both_door_actor;
static uint32_t both_door_origin;
static unsigned both_door_members;
static int16_t both_door_extents[2][2]; /* Authored full native left/right offsets. */
static int unit_choices_call;
static int target_projection_call;
/* Elective independent presentation. The canonical world still runs once. */
static unsigned independent_views, local_split, private_draw, private_seat, view_call;
/* Intro camera-volume requests belong to the entering hero. Unlike draw
 * position history, these authored limits survive a current-build load. */
static uint8_t intro_camera_requests[8];
static unsigned intro_camera_valid;
static void independent_invalidate(void);
static void independent_menu_begin(void);
static void independent_world_begin(void);
#include "mmx6_coop_state_track.h"
#ifdef MMX6_COOP_MODERN_STATE
static uint8_t snapshot_asset_sha[32];
static int snapshot_asset_valid;
static void snapshot_assets_loaded(const Mmx6AssetView *views,unsigned count);
#endif

static int scene_passenger(unsigned seat) { return scene_phase && scene_owner!=seat+1; }
static int both_door_slot(uint32_t actor) {
    return actor>=0x800C1220u && actor<0x800C4560u &&
        !((actor-0x800C1220u)%0xA4u);
}
static int both_door_source_valid(void) {
    return both_door_slot(both_door_actor) &&
        (psx_mod_read_byte(both_door_actor)&1u) &&
        psx_mod_read_byte(both_door_actor+1)==8 &&
        psx_mod_read_word(both_door_actor+0x10)==both_door_origin;
}
/* Both ALIVE actors produce phase0 together only after authenticated Both
 * door admission. Other native scenes use the existing passenger phases. */
static int both_door_traversal_active(void) {
    return both_doors && both_door_actor && both_door_members && both_door_source_valid() &&
        scene_owner && !scene_phase && pause_owner<0;
}
static void both_door_reset(void) {
    both_door_actor=both_door_origin=both_door_members=0;
    memset(both_door_extents,0,sizeof both_door_extents);
}

static void put32(uint8_t *p, uint32_t v) {
    for (unsigned i=0;i<4;++i) p[i]=(uint8_t)(v>>(8*i));
}

static uint32_t le32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1]<<8) |
           ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}
static void capture(uint32_t addr, void *data, size_t n) {
    uint8_t *p = data;
    for (size_t i=0;i<n;++i) p[i]=psx_mod_read_byte(addr+(uint32_t)i);
}
static void project(uint32_t addr, const void *data, size_t n) {
    const uint8_t *p = data;
    for (size_t i=0;i<n;++i) psx_mod_write_byte(addr+(uint32_t)i,p[i]);
}
static void capture_player(PlayerContext *p) {
    capture(PLAYER,p->body,sizeof p->body);
    capture(0x800950A0,p->shots,sizeof p->shots);
    capture(0x800972F8,p->trails,sizeof p->trails);
    capture(0x800911A8,p->effects,sizeof p->effects);
}
static void project_player(const PlayerContext *p) {
    project(PLAYER,p->body,sizeof p->body);
    project(0x800950A0,p->shots,sizeof p->shots);
    project(0x800972F8,p->trails,sizeof p->trails);
    project(0x800911A8,p->effects,sizeof p->effects);
}
static void code_bank(const uint8_t *p) {
    for (unsigned i=0;i<OVERLAY_SIZE;i+=4) {
        uint32_t v=le32(p+i);
        if (psx_mod_read_word(OVERLAY+i)!=v)
            psx_mod_write_code_word(OVERLAY+i,v);
    }
}
static uint32_t guest(CPUState *cpu, uint32_t address, uint32_t a0, uint32_t a1) {
    /* Preserve the caller's architectural registers, not elapsed guest time.
     * Dispatch handles nested calls, interrupts and compiled/interpreted code. */
    uint32_t saved[102];
    memcpy(saved,cpu->gpr,32*4);
    memcpy(saved+32,cpu->gte_data,32*4);
    memcpy(saved+64,cpu->gte_ctrl,32*4);
    saved[96]=cpu->pc;saved[97]=cpu->hi;saved[98]=cpu->lo;
    saved[99]=address;saved[100]=a0;saved[101]=a1;
    STATE_WORDS(frame,1,saved,102);
    if (!mmx6_state_can_call()) {
        if(!failed)fprintf(stderr,"mmx6 co-op: invalid host callback stack; reactivation required\n");
        failed=1;STATE_POP(frame);return 0;
    }
    cpu->pc=0; cpu->gpr[4]=a0; cpu->gpr[5]=a1;
    psx_dispatch_call(cpu,address,saved[31]);
    uint32_t result=cpu->gpr[2];
    memcpy(cpu->gpr,saved,32*4);
    memcpy(cpu->gte_data,saved+32,32*4);
    memcpy(cpu->gte_ctrl,saved+64,32*4);
    cpu->pc=saved[96]; cpu->hi=saved[97]; cpu->lo=saved[98];
    STATE_POP(frame);
    return result;
}

#include "mmx6_coop_jump_audio.inc"
#include "mmx6_coop_intro_target.inc"
#include "mmx6_coop_weather.inc"

static int unit_choices(CPUState *cpu, uint32_t address) {
    /* ROCK_X6.BIN member 16 shares its load address with stage overlays.
     * Match the native list builder before touching its menu-local table. */
    if (unit_choices_call || failed || cpu->gpr[4]!=PLAY ||
        psx_mod_read_word(address)!=0x3C05800Fu ||
        psx_mod_read_word(address+0x10)!=0xA0601CB0u ||
        psx_mod_read_word(address+0x104)!=0x03E00008u) return 0;
    unit_choices_call=1;
    cpu->gpr[2]=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    unit_choices_call=0;
    /* Keep the original unlocked list and its original order/confirmation. */
    return 1;
}

static uint8_t *disc_file(const char *name, uint32_t *size) {
    uint8_t *p;
    if (!psx_mod_read_disc_file(name,NULL,0,size) || !*size) return NULL;
    p=malloc(*size);
    if (!p) return NULL;
    if (!psx_mod_read_disc_file(name,p,*size,size)) { free(p); return NULL; }
    return p;
}
static int ui_upload(const Mmx6AssetView *asset) {
    /* Native DAT loader 8001574C: 64-word by 16-row strips, with placement
     * from 8006E2EC and strip progression from 8001004C. Preserve the actual
     * original graphic pixels in host memory; never manufacture HUD art. */
    unsigned type=asset->type&255, layout=(asset->type>>8)&255;
    if (type>=13 || (layout!=0 && layout!=2) || asset->size%2048) return 0;
    unsigned x=psx_mod_read_half(0x8006E2EC+type*4);
    unsigned y=psx_mod_read_half(0x8006E2EEu+type*4), base_y=y&256;
    for (size_t at=0;at<asset->size;at+=2048) {
        if (x+64>1024 || y+16>512) return 0;
        for (unsigned r=0;r<16;++r) for (unsigned c=0;c<64;++c) {
            const uint8_t *p=asset->data+at+(r*64+c)*2;
            zero_ui_pixels[(y+r)*1024+x+c]=(uint16_t)(p[0]|p[1]<<8);
        }
        if (y==base_y+240) { x+=64; y=layout==2?176:base_y; }
        else y+=16;
    }
    return 1;
}
static int fixed_roster(Mmx6CoopRoster *roster) {
    Mmx6CoopRosterNative native={psx_mod_read_byte(PLAYER+2),psx_mod_read_byte(PLAYER+0xE7),
        psx_mod_read_byte(PLAY+0x38),psx_mod_read_byte(PLAY+0x5E),psx_mod_read_byte(PLAY+0x5F)};
    Mmx6CoopRosterReason identity=mmx6_coop_roster_resolve_partner(&native,partner_x_armor,psx_mod_read_byte(PLAY+0x69),roster);
    if (identity!=MMX6_COOP_ROSTER_OK) {
        fprintf(stderr,"mmx6 co-op: native roster refused (%s)\n",mmx6_coop_roster_reason(identity));
        return 0;
    }
    Mmx6CoopResourcesReason admission=mmx6_coop_resources_fixed_runtime_admit(roster);
    if (admission!=MMX6_COOP_RESOURCES_OK) {
        fprintf(stderr,"mmx6 co-op: native roster refused (%s)\n",mmx6_coop_resources_reason(admission));
        return 0;
    }
    return 1;
}
#include "mmx6_coop_working_palette.inc"
static int load_assets(const Mmx6CoopRoster *roster) {
    uint32_t bin_size=0,n=0;
    Mmx6CoopResourceViews v;
    /* Bind resources to the validated native counterpart, never its seat number. */
    if (mmx6_coop_resources_fixed_runtime_admit(roster)!=MMX6_COOP_RESOURCES_OK) return 0;
    if(ready && private_actor.character==roster->seat[1].character &&
       private_actor.form==roster->seat[1].form)return 1;
    if(ready) {
        /* A native stage/character handoff has retired the previous actor.
         * Keep SDK allocations, replace only owned immutable payloads. */
        if(enrolled || zero_projected || zero_world)return 0;
        jump_audio_release_character();
        free(zero_compressed);zero_compressed=NULL;compressed_size=0;
        free(zero_ui_pixels);zero_ui_pixels=NULL;
        ready=0;zero_menu_loaded=0;ui_bank_count=0;memset(ui_banks,0,sizeof ui_banks);
#ifdef MMX6_COOP_MODERN_STATE
        if(!psx_mod_forget_texture_bank_range(0x7000u,4096))return 0;
#endif
    }
    uint8_t *bin=disc_file("ROCK_X6.BIN",&bin_size);
    if (!bin) return 0;
    uint8_t *file=disc_file("ROCK_X6.DAT",&n);
    if (!file) { free(bin);return 0; }
    Mmx6CoopResourcesReason reason=mmx6_coop_resource_prepare(roster,1,bin,bin_size,file,n,ASSET_SPACE,&v);
    if (reason==MMX6_COOP_RESOURCES_OK && (v.overlay.size>sizeof zero_overlay ||
        v.overlay.size<ZERO_GIGA_BACKUP_OFFSET+ZERO_GIGA_BACKUP_BYTES))
        reason=MMX6_COOP_RESOURCES_INVALID_OVERLAY;
    if (reason!=MMX6_COOP_RESOURCES_OK) {
        fprintf(stderr,"mmx6 co-op: resources refused (%s)\n",mmx6_coop_resources_reason(reason));
        free(bin);free(file);return 0;
    }
    if (!private_roster_bind(roster) || !working_palette_source_guards() || !working_palette_prepare(file,n,WORKING_RECORD_COUNT)) {
        free(bin);free(file);return 0;
    }
    if (!jump_audio_load(file,n)) {
        fprintf(stderr,"mmx6 co-op: counterpart audio resources refused\n");
        free(bin);free(file);return 0;
    }
    uint8_t *compressed=malloc(v.graphics.size);
    uint16_t *pixels=calloc(1024*512,sizeof *zero_ui_pixels);
    if (!compressed || !pixels) { free(compressed);free(pixels);free(bin);free(file);return 0; }
    zero_compressed=compressed;zero_ui_pixels=pixels;
    /* Plan all aligned spans/source and working palette bounds BEFORE copies. */
    memset(zero_overlay,0,sizeof zero_overlay);
    memcpy(zero_overlay,v.overlay.data,v.overlay.size);
    memcpy(zero_giga_backup,zero_overlay+ZERO_GIGA_BACKUP_OFFSET,sizeof zero_giga_backup);
    memcpy(zero_compressed,v.graphics.data,v.graphics.size);compressed_size=v.graphics.size;
    assembly=assets+v.layout.assembly;
    palette_source=assets+v.layout.palette_source;
    active_palette=assets+v.layout.active_palette;
    menu_assembly=assets+v.layout.menu_assembly;
    project(assets,v.graphics.data,v.graphics.size);
    project(assembly,v.assembly.data,v.assembly.size);
    project(palette_source,v.palette.data,v.palette.size);
    if (!working_palette_seed(1)) {
        free(zero_compressed);zero_compressed=NULL;compressed_size=0;
        free(zero_ui_pixels);zero_ui_pixels=NULL;free(bin);free(file);return 0;
    }
    project(menu_memory,v.menu_graphics.data,v.menu_graphics.size);
    project(menu_memory+0x8000,v.font.data,v.font.size);
    project(menu_memory+0x10000,v.menu_colors.data,v.menu_colors.size);
    project(menu_memory+MENU_PORTRAIT,v.portrait.data,v.portrait.size);
    project(menu_memory+MENU_PORTRAIT_COLORS,v.portrait_colors.data,v.portrait_colors.size);
    project(menu_assembly,v.menu_layout.data,v.menu_layout.size);
    if (!ui_upload(&v.common) || !ui_upload(&v.icons) || !ui_upload(&v.menu_graphics) || !ui_upload(&v.font)) {
        free(bin);free(file);return 0;
    }
#ifdef MMX6_COOP_MODERN_STATE
    const Mmx6AssetView sources[]={v.graphics,v.assembly,v.palette,v.menu_graphics,v.font,v.menu_colors,
        v.menu_layout,v.portrait,v.portrait_colors,v.common,v.icons,
        {working_palette_lengths,sizeof working_palette_lengths,5},
        {&native_working_palettes[0][0],sizeof native_working_palettes,5}};
    snapshot_assets_loaded(sources,sizeof sources/sizeof sources[0]);
#endif
    free(bin);free(file);
    fprintf(stdout,"mmx6 co-op: character%u resources loaded; status/input at %08X\n",private_actor.character,diagnostic);
    fflush(stdout);
    return 1;
}
static void subtank_seed(void) {
    if(!separate_subtanks || subtank_seeded)return;
    capture(PLAY+0x63,zero_subtanks,sizeof zero_subtanks);
    subtank_found=psx_mod_read_byte(PLAY+0x6B)&0x30u;
    subtank_seeded=1;
}
static void subtank_acquired(void) {
    if(!separate_subtanks)return;
    unsigned found=psx_mod_read_byte(PLAY+0x6B)&0x30u,added=found&~subtank_found;
    subtank_found=found;
    for(unsigned i=0;i<2;++i)if(added&(0x10u<<i)) {
        zero_subtanks[i]|=0x80;
        psx_mod_write_byte(PLAY+0x63+i,psx_mod_read_byte(PLAY+0x63+i)|0x80);
        if(zero_projected)saved_play[0x63+i]|=0x80;
    }
}
static void enter_zero(void) {
    subtank_seed();
    subtank_acquired();
    capture_player(&p1);
    capture(OVERLAY,saved_overlay,sizeof saved_overlay);
    capture(PLAY,saved_play,sizeof saved_play);
    if(separate_subtanks)project(PLAY+0x63,zero_subtanks,sizeof zero_subtanks);
    capture(0x800971F8,saved_camera,sizeof saved_camera);
    saved_resources[0]=psx_mod_read_word(SCRATCH+0x14);
    saved_resources[1]=psx_mod_read_word(SCRATCH+0x1C);
    saved_resources[2]=psx_mod_read_word(SCRATCH+0x24);
    saved_resources[3]=psx_mod_read_word(SCRATCH+0x28);
    saved_resources[4]=psx_mod_read_word(SCRATCH+0x38);
    saved_resources[5]=psx_mod_read_word(SCRATCH+0x3C);
    saved_resources[6]=psx_mod_read_word(SCRATCH+0xA8);
    saved_palette_dirty=psx_mod_read_byte(0x800C4560);
    project_player(&p2);
    code_bank(zero_overlay);
    if(private_actor.character==MMX6_COOP_CHARACTER_ZERO)
        project(OVERLAY+ZERO_GIGA_BACKUP_OFFSET,zero_giga_backup,sizeof zero_giga_backup);
    psx_mod_write_word(SCRATCH+0x14,assets);
    psx_mod_write_word(SCRATCH+0x1C,assembly);
    psx_mod_write_word(SCRATCH+0x24,palette_source);
    psx_mod_write_word(SCRATCH+0x28,active_palette);
    psx_mod_write_word(SCRATCH+0x38,menu_memory+0x10000);
    psx_mod_write_word(SCRATCH+0x3C,menu_assembly);
    if (zero_menu_loaded) psx_mod_write_word(SCRATCH+0xA8,menu_memory+MENU_PORTRAIT_COLORS);
    psx_mod_write_byte(PLAY+0x38,private_actor.character);
    psx_mod_write_byte(PLAY+0x5E,private_actor.form);
    zero_projected=1;
}
static void leave_zero_context(int shared_world) {
    if(separate_subtanks) {
        subtank_acquired();
        capture(PLAY+0x63,zero_subtanks,sizeof zero_subtanks);
        saved_play[0x6B]|=psx_mod_read_byte(PLAY+0x6B)&0x30u;
    }
    capture_player(&p2);
    if(private_actor.character==MMX6_COOP_CHARACTER_X)capture(OVERLAY,zero_overlay,sizeof zero_overlay);
    if(private_actor.character==MMX6_COOP_CHARACTER_ZERO)
        capture(OVERLAY+ZERO_GIGA_BACKUP_OFFSET,zero_giga_backup,sizeof zero_giga_backup);
    project_player(&p1);
    code_bank(saved_overlay);
    psx_mod_write_word(SCRATCH+0x14,saved_resources[0]);
    psx_mod_write_word(SCRATCH+0x1C,saved_resources[1]);
    psx_mod_write_word(SCRATCH+0x24,saved_resources[2]);
    psx_mod_write_word(SCRATCH+0x28,saved_resources[3]);
    psx_mod_write_word(SCRATCH+0x38,saved_resources[4]);
    psx_mod_write_word(SCRATCH+0x3C,saved_resources[5]);
    psx_mod_write_word(SCRATCH+0xA8,saved_resources[6]);
    psx_mod_write_byte(0x800C4560,saved_palette_dirty);
    if (shared_world) {
        /* A surviving Zero owns this entire native stage pass. Keep the one
         * world/camera/menu update; only character identity is a projection. */
        psx_mod_write_byte(PLAY+0x38,saved_play[0x38]);
        psx_mod_write_byte(PLAY+0x5E,saved_play[0x5E]);
        if(separate_subtanks)project(PLAY+0x63,saved_play+0x63,2);
    } else {
        project(PLAY,saved_play,sizeof saved_play);
        project(0x800971F8,saved_camera,sizeof saved_camera);
    }
    zero_projected=0;
}
static void leave_zero(void) { leave_zero_context(0); }

static void shared_palette_load(CPUState *cpu,uint32_t address) {
    if(address!=0x8002B3D4u || !ready || !enrolled || failed || !zero_projected ||
       psx_mod_read_word(SCRATCH+0x28)!=active_palette ||
       saved_resources[3]<0x80010000u || saved_resources[3]>0x801FC000u)return;
    /* Original52ED0 selects NPC53/55/63 and loads eight shared boss rows
     * through52F44. A guest-owned world still displays those rows from the
     * resident bank. Keep the original copy into the private bank, and
     * publish only this exact shared span for the native17C40 upload. */
    uint32_t route=psx_mod_read_byte(PLAY+0x43Bu);
    uint32_t boss_source=psx_mod_read_word(SCRATCH+0x30);
    uint32_t boss_offset=route?(route==1?0x100u:0x180u):0;
    if(cpu->gpr[31]==0x80052F4Cu && cpu->gpr[4]==0x58u && cpu->gpr[6]==8 &&
       boss_source>=0x80010000u && boss_source<=0x801FFF00u-boss_offset &&
       cpu->gpr[5]==boss_source+boss_offset) {
        uint8_t colors[256];
        capture(cpu->gpr[5],colors,sizeof colors);
        project(saved_resources[3]+0xB00u,colors,sizeof colors);
        saved_palette_dirty|=1u;
        return;
    }
    /* Original Turtloid weather fades interpolate this shared row in
     * ED69C/ED774/ED850 before the native resident palette upload. */
    if(psx_mod_read_byte(PLAY+12)==6 && !psx_mod_read_byte(PLAY+13) &&
       (cpu->gpr[31]==0x800ED728u || cpu->gpr[31]==0x800ED804u || cpu->gpr[31]==0x800ED8D8u) &&
       cpu->gpr[4]==0x63u && cpu->gpr[5]==0x800F6BC4u && cpu->gpr[6]==1) {
        uint8_t colors[32];
        capture(cpu->gpr[5],colors,sizeof colors);
        project(saved_resources[3]+0xC60u,colors,sizeof colors);
        saved_palette_dirty|=1u;
        return;
    }
    unsigned alternate=psx_mod_read_half(0x80090D6Au)!=0;
    uint32_t first=alternate?0x5Eu:0x15u,slot=cpu->gpr[4],source=cpu->gpr[5];
    uint32_t count=cpu->gpr[6],caller=cpu->gpr[31];
    int opening=slot==first && count==2 && source==0x8006E408u &&
        caller==(alternate?0x800219B0u:0x8002199Cu);
    int speaker=slot==first+1 && count==1 && source>=0x8006E484u &&
        source<0x8006E584u && !((source-0x8006E484u)&31u) &&
        (caller==(alternate?0x8002289Cu:0x80022884u) || caller==0x800225D8u);
    int closing=slot==first && count==2 && source==0x800E33D8u &&
        caller==(alternate?0x800221D4u:0x800221BCu);
    if(!opening && !speaker && !closing)return;
    uint8_t colors[64];
    if(opening) {
        /* Native21968 has backed up Zero's private rows. The shared font
         * actually displayed beforehand belongs to the resident upload.
         * Keep that baseline in the original, already serialized backup;
         * native221B4/221CC will restore it when the dialogue closes. */
        capture(saved_resources[3]+first*32u,colors,sizeof colors);
        project(0x800E33D8u,colors,sizeof colors);
    }
    /* Native223E0 text uses CLUT7845 and the first/name row adds one at
     *22564, consuming the shared GPU rows80/96,481. The original loader
     * still writes Zero's private working palette after this entry hook.
     * Publish only its exact dialogue span to the resident working bank
     * and retain the dirty bit through leave_zero_context, so the original
     *17C40 upload also presents these colors. Other private rows stay owned. */
    capture(source,colors,count*32u);
    project(saved_resources[3]+slot*32u,colors,count*32u);
    saved_palette_dirty|=1u;
}

#include "mmx6_coop_shared_effects.inc"

/* Pickup routines only need a body and character identity. Keep all native
 * shared changes (life count, tanks, collection flags and heal freeze) while
 * projecting the collector, including when Zero owns the world pass. */
static uint32_t pickup_as_seat(CPUState *cpu, uint32_t address, uint32_t actor, unsigned seat) {
    unsigned resident=zero_world?1:0;
    if (seat==resident) return guest(cpu,address,actor,0);
    uint8_t body[sizeof p2.body], character=psx_mod_read_byte(PLAY+0x38);
    uint8_t armor=psx_mod_read_byte(PLAY+0x5E);
    uint8_t identity[2]={character,armor};
    uint8_t tanks[3]={psx_mod_read_byte(PLAY+0x63),psx_mod_read_byte(PLAY+0x64),psx_mod_read_byte(PLAY+0x6B)};
    uint8_t *other=seat?p2.body:p1.body;
    capture(PLAYER,body,sizeof body);
    STATE_BYTES(restore_body,2,body,sizeof body);
    STATE_BYTES(restore_identity,3,identity,sizeof identity);
    uint32_t selection[3]={address,actor,seat};
    STATE_WORDS(restore_selection,27,selection,3);
    STATE_BYTES(restore_tanks,81,tanks,sizeof tanks);
    if(separate_subtanks) {
        subtank_seed();
        project(PLAY+0x63,seat?zero_subtanks:saved_play+0x63,2);
    }
    project(PLAYER,other,sizeof body);
    psx_mod_write_byte(PLAY+0x38,seat?private_actor.character:saved_play[0x38]);
    psx_mod_write_byte(PLAY+0x5E,seat?private_actor.form:saved_play[0x5E]);
    uint32_t result=guest(cpu,address,actor,0);
    if(separate_subtanks) {
        capture(PLAY+0x63,seat?zero_subtanks:saved_play+0x63,2);
        project(PLAY+0x63,tanks,2);
        subtank_acquired();
    }
    capture(PLAYER,other,sizeof body);
    project(PLAYER,body,sizeof body);
    psx_mod_write_byte(PLAY+0x38,character);
    psx_mod_write_byte(PLAY+0x5E,armor);
    STATE_POP(restore_tanks);STATE_POP(restore_selection);STATE_POP(restore_identity);STATE_POP(restore_body);
    return result;
}
static int pickup_collect(CPUState *cpu, uint32_t address) {
    if (pickup_call || !enrolled || failed) return 0;
    uint32_t actor=cpu->gpr[4], result=0;
    pickup_call=1;
    /* Preserve deterministic P1 priority only when both actually overlap.
     * Native overlap, item effects and capacity handling remain unchanged. */
    for (unsigned seat=0;seat<2;++seat) {
        if (life.status[seat]!=MMX6_COOP_ALIVE || scene_passenger(seat)) continue;
        uint32_t context[3]={address,actor,seat};
        STATE_WORDS(restore_collector,30,context,3);
        result=pickup_as_seat(cpu,address,actor,seat);
        STATE_POP(restore_collector);
        unsigned mode=psx_mod_read_byte(actor+4);
        if (mode==1) continue;
        if (mode==2) {
            unsigned i=0;
            while (i<128 && pickup_owners[i].actor && pickup_owners[i].actor!=actor) ++i;
            if (i==128) { failed=1; break; }
            pickup_owners[i]=(PickupOwner){actor,(uint8_t)seat};
        }
        psx_mod_write_word(diagnostic+0x60,actor);
        psx_mod_write_byte(diagnostic+0x64,(uint8_t)(seat+1));
        break;
    }
    cpu->gpr[2]=result;
    pickup_call=0;
    return 1;
}
static int pickup_tick(CPUState *cpu, uint32_t address) {
    if (pickup_call || !enrolled || failed) return 0;
    uint32_t actor=cpu->gpr[4];
    for (unsigned i=0;i<128;++i) if (pickup_owners[i].actor==actor) {
        if (psx_mod_read_byte(actor+4)!=2) { pickup_owners[i].actor=0; return 0; }
        pickup_call=1;
        uint32_t context[2]={actor,i};STATE_WORDS(restore_collector,31,context,2);
        cpu->gpr[2]=pickup_as_seat(cpu,address,actor,pickup_owners[i].seat);
        STATE_POP(restore_collector);
        pickup_call=0;
        if (psx_mod_read_byte(actor+4)!=2) pickup_owners[i].actor=0;
        return 1;
    }
    return 0;
}
static uint32_t pickup_overlap(CPUState *cpu, uint32_t actor, unsigned seat) {
    if (seat==(unsigned)(zero_world?1:0)) return guest(cpu,0x8002DCF4,actor,PLAYER);
    uint8_t body[sizeof p2.body];
    capture(PLAYER,body,sizeof body);
    STATE_BYTES(restore_body,4,body,sizeof body);
    project(PLAYER,seat?p2.body:p1.body,sizeof body);
    uint32_t result=guest(cpu,0x8002DCF4,actor,PLAYER);
    project(PLAYER,body,sizeof body);
    STATE_POP(restore_body);
    return result;
}
static int nightmare_soul(CPUState *cpu, uint32_t address) {
    uint32_t actor=cpu->gpr[4];
    if (pickup_call || !enrolled || failed || psx_mod_read_byte(actor+5)!=5 ||
        !psx_mod_read_byte(actor+0x8E)) return 0;
    pickup_call=1;
    unsigned seat=zero_world?1:0;
    uint32_t box=psx_mod_read_word(actor+0x68);
    uint32_t context[5]={address,actor,box,seat,0};STATE_WORDS(restore_soul,32,context,5);
    psx_mod_write_word(actor+0x68,0x80075EE0); /* Native collectible soul box. */
    for (unsigned candidate=0;candidate<2;++candidate) {
        context[4]=candidate;STATE_UPDATE(restore_soul,context);
        if (life.status[candidate]==MMX6_COOP_ALIVE && !scene_passenger(candidate) &&
            pickup_overlap(cpu,actor,candidate)) { seat=candidate; break; }
    }
    psx_mod_write_word(actor+0x68,box);
    context[3]=seat;context[4]=2;STATE_UPDATE(restore_soul,context);
    /* Run this entity once. The original routine selects PLAY+D2/D4 from
     * the collector's character, retaining native soul values and rank data. */
    cpu->gpr[2]=pickup_as_seat(cpu,address,actor,seat);
    STATE_POP(restore_soul);
    pickup_call=0;
    return 1;
}
static void begin_join(CPUState *cpu, uint32_t x, uint32_t y);
static void enroll(CPUState *cpu,const Mmx6CoopRoster *roster,int arrival) {
    if (mmx6_coop_resources_fixed_runtime_admit(roster)!=MMX6_COOP_RESOURCES_OK) { failed=1;return; }
    /* Native fresh-stage/checkpoint birth reapplies its own body rows next. */
    if (working_palette_assets_ready && !working_palette_seed(0)) { failed=1;return; }
    if (life.status[1]==MMX6_COOP_ABSENT) {
        /* The native primary may enter a new area after Zero has completed
         * a voluntary departure. Keep that absent body and saved personal
         * return context; resource admission does not authorize a new birth.
         * A later deliberate Select still owns the existing return path. */
        enrolled=1;previous_input=0;
        arrival_pair=join_phase=0;
        p2_hud_fade=0;
        refight_return_checkpoint=0;
        return;
    }
    uint32_t x=psx_mod_read_word(PLAYER+8), y=psx_mod_read_word(PLAYER+12);
    unsigned arrival_delay=psx_mod_read_byte(PLAYER+0xCE);
    uint32_t arrival_box=psx_mod_read_word(PLAYER+0x68);
    uint32_t origin[5]={x,y,arrival_delay,arrival_box,(unsigned)arrival};
    STATE_WORDS(restore_origin,33,origin,5);
    memset(&p2,0,sizeof p2);
    enter_zero();
    psx_mod_write_byte(PLAY+0x1E,0);
    guest(cpu,0x8003BD24,0,0); /* Native actor initialization, including animation table. */
    psx_mod_write_word(PLAYER+8,x+(24u<<16));
    psx_mod_write_word(PLAYER+12,y);
    psx_mod_write_word(PLAYER+0x18,x+(24u<<16));
    psx_mod_write_word(PLAYER+0x1C,y);
    psx_mod_write_byte(PLAYER+3,1);
    psx_mod_write_byte(PLAYER+4,1);
    guest(cpu,0x8003D718,PLAYER,0); /* Character's own unlocks/parts. */
    guest(cpu,0x8003D630,PLAYER,0);
    guest(cpu,0x8003AD18,PLAYER,0); /* Native idle transition. */
    leave_zero();
    if (refight_return_checkpoint && psx_mod_read_byte(PLAY+12)==12 &&
        !psx_mod_read_byte(PLAY+13) && psx_mod_read_byte(PLAY+0x1D)==refight_return_checkpoint) {
        /* Native owner initialization uses its saved current HP on this path.
         * Do the same for Zero, retaining personal weapon/energy but none of
         * the old room's pose, position, combat objects or solid history. */
        memcpy(p2.body+0x5C,returning_body+0x5C,3);
        p2.body[0x5C]&=0x7F;
        p2.body[0x93]=returning_body[0x93];
        memcpy(p2.body+0xA8,returning_body+0xA8,18);
        psx_mod_counter_add("mmx6.coop.refight-resources-restored",1);
    }
    refight_return_checkpoint=0;
    enrolled=1; previous_input=0;
    mmx6_coop_lifecycle_respawn(&life);
    /* Reuse the original incoming beam for an actual simultaneous arrival;
     * other handoffs retain the existing offscreen voluntary-return path. */
    p2_hud_fade=0;
    if (arrival) {
        /* Original action0 (80035144) owns descent, terrain contact and the
         * resolving pose. Do not interpolate to X's still-airborne Y or mark
         * a successful landing. The ordinary 24px enrollment offset remains. */
        enter_zero();
        /* 35168..35194 counts CE down before enabling standing contact.
         * Share the native arrival's remaining delay, not a fabricated floor
         * or completed pose; each character resolves its own standing box. */
        psx_mod_write_byte(PLAYER+0xCE,(uint8_t)arrival_delay);
        if (arrival_box) guest(cpu,0x8003CCBC,PLAYER,0);
        guest(cpu,0x8003D850,PLAYER,0);
        leave_zero();
        life.status[1]=MMX6_COOP_JOINING;
        join_phase=0;
        arrival_pair=1;
    } else {
        /* This fresh nonpaired birth uses begin_join too, before any Select
         * departure can have saved returning_body. Retain the actual native
         * init/parts/idle result for an immediately following shared scene. */
        memcpy(returning_body,p2.body,sizeof returning_body);
        begin_join(cpu,x+(24u<<16),y);
    }
    STATE_POP(restore_origin);
    fprintf(stdout,"mmx6 co-op: Zero enrolled at (%u,%u)\n",x>>16,y>>16);
    fflush(stdout);
}

/* Retail Ultimate Nova (8003E584..8003E600, 801EC4C0..801EC678) holds
 * PLAY+1C for X's action22, then clears it on native recovery. It does not
 * freeze the native cameras or ordinary Zero player/input updates. Admit
 * that live personal action only, without changing the canonical hold flag;
 * a concurrent scene, pause, death, vehicle or other world freeze still wins. */
static int primary_nova_active(void) {
    if (!ready || !enrolled || failed || scene_owner || clear_phase || pause_owner>=0 ||
        life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_ALIVE ||
        psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
        psx_mod_read_byte(PLAY+0x0F) || psx_mod_read_byte(PLAY+0x10) ||
        psx_mod_read_byte(PLAY+0x1C)!=1 || psx_mod_read_byte(0x8008EAFCu) ||
        !(psx_mod_read_byte(PLAYER)&1) || psx_mod_read_byte(PLAYER+2) ||
        psx_mod_read_byte(PLAYER+4)!=1 || psx_mod_read_byte(PLAYER+5)!=0x22 ||
        psx_mod_read_byte(PLAYER+6)>2 || psx_mod_read_byte(PLAYER+0xE7)!=4 ||
        psx_mod_read_byte(PLAYER+0xE0)!=1 || psx_mod_read_byte(PLAYER+0x7A)!=1 ||
        !psx_mod_read_byte(PLAYER+0x5C) || psx_mod_read_byte(PLAYER+0x5C)>=0x80 ||
        psx_mod_read_byte(PLAYER+0xCC) || psx_mod_read_byte(PLAYER+0xD0) ||
        psx_mod_read_byte(PLAYER+0xD3) || psx_mod_read_byte(PLAYER+0xD4) ||
        psx_mod_read_byte(PLAYER+0xD5)) return 0;
    return (p2.body[0]&1) && p2.body[2]==1 && p2.body[4]==1 &&
        p2.body[0x5C] && p2.body[0x5C]<0x80 && !p2.body[0xCC] &&
        !p2.body[0xD0] && !p2.body[0xD3] && !p2.body[0xD4] && !p2.body[0xD5];
}
static int coop_world_hold(void) {
    return psx_mod_read_byte(PLAY+0x1C) && !primary_nova_active();
}
static int shared_camera(void) {
    return enrolled && !scene_owner && !clear_phase && life.status[0]==MMX6_COOP_ALIVE && life.status[1]==MMX6_COOP_ALIVE &&
        psx_mod_read_byte(PLAYER+4)==1 && psx_mod_read_byte(PLAYER+5)>=2 &&
        !psx_mod_read_byte(PLAY+0x10) && !psx_mod_read_byte(PLAY+0x1C);
}
static int pickup_heal_camera(void) {
    /* Native 8004E0A8/8004DCB8 freeze ordinary health collection through
     * 8004E78C(1), which writes PLAY+10..17. Keep both living bodies' camera
     * during that shared freeze; movement/scene admission still uses the
     * original shared_camera predicate. Only an owned, live native health
     * pickup in its delayed phase qualifies, never an arbitrary scene hold. */
    if (!ready || !enrolled || scene_owner || life.status[0]!=MMX6_COOP_ALIVE ||
        life.status[1]!=MMX6_COOP_ALIVE || psx_mod_read_byte(PLAYER+4)!=1 ||
        psx_mod_read_byte(PLAYER+5)<2 || psx_mod_read_byte(PLAY)!=10 ||
        psx_mod_read_byte(PLAY+1) || psx_mod_read_byte(PLAY+0x1C)) return 0;
    for (unsigned i=0x10;i<0x18;++i) if (psx_mod_read_byte(PLAY+i)!=1) return 0;
    for (unsigned i=0;i<128;++i) {
        uint32_t actor=pickup_owners[i].actor;
        if (pickup_owners[i].seat>1 || actor<0x8008EF48u || actor>=0x80090C88u ||
            (actor-0x8008EF48u)%0x9Cu || !(psx_mod_read_byte(actor)&1) ||
            psx_mod_read_byte(actor+1)!=0x2F || psx_mod_read_byte(actor+4)!=2) continue;
        unsigned kind=psx_mod_read_byte(actor+2);
        if (kind==32 || kind==33) return 1;
    }
    return 0;
}
static void constrain_player(unsigned player) {
    if (independent_views || !shared_camera()) return;
    int32_t x=(int32_t)psx_mod_read_word(PLAYER+8), z=(int32_t)le32(p2.body+8);
    unsigned width=320u+2u*(unsigned)psx_mod_widescreen_x_margin();
    int32_t limited=mmx6_coop_limit_x(player?z:x,player?x:z,width);
    if (!player && limited!=x) {
        psx_mod_write_word(PLAYER+8,(uint32_t)limited);
        psx_mod_write_word(PLAYER+0x20,0);
    }
    if (player && limited!=z) { put32(p2.body+8,(uint32_t)limited); put32(p2.body+0x20,0); }
}
static int camera_target(CPUState *cpu, uint32_t address) {
    if (independent_views || inside || failed || (!shared_camera() && !pickup_heal_camera())) return 0;
    unsigned axis=address==0x80029598u?8:12;
    uint32_t original=psx_mod_read_word(PLAYER+axis);
    STATE_WORDS(restore_axis,5,&original,1);
    int64_t midpoint=((int64_t)(int32_t)original+(int32_t)le32(p2.body+axis))/2;
    inside=1;
    psx_mod_write_word(PLAYER+axis,(uint32_t)midpoint);
    uint32_t result=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    psx_mod_write_word(PLAYER+axis,original);
    STATE_POP(restore_axis);
    cpu->gpr[2]=result;
    inside=0;
    return 1;
}
static void pit_death(unsigned seat, int bottom) {
    int resident=!seat || zero_world;
    unsigned phase=resident?psx_mod_read_byte(PLAYER+4):p2.body[4];
    unsigned action=resident?psx_mod_read_byte(PLAYER+5):p2.body[5];
    unsigned hp=resident?psx_mod_read_byte(PLAYER+0x5C):p2.body[0x5C];
    int y=(int16_t)(resident?psx_mod_read_half(PLAYER+14):le32(p2.body+12)>>16);
    if (life.status[seat]!=MMX6_COOP_ALIVE || phase!=1 || action<2 ||
        !hp || hp==0x80 || y-8<bottom) return;
    /* 800282F0: retain the native fatal flag and damage bookkeeping. The
     * next native player update enters death; the existing co-op lifecycle
     * then keeps the survivor active and spends a life only on a team wipe. */
    if (resident) psx_mod_write_byte(PLAYER+0x5C,0x80);
    else p2.body[0x5C]=0x80;
    psx_mod_write_word(PLAY+0x98,psx_mod_read_word(PLAY+0x98)+(hp&0x7F));
}
static void camera_pits(CPUState *cpu, uint32_t address) {
    (void)address;
    if (private_draw || !enrolled || failed || (inside && !zero_world) || scene_owner ||
        cpu->gpr[4]!=0x800971F8u || psx_mod_read_byte(PLAY)!=0x0A ||
        psx_mod_read_byte(PLAY+0x10) || coop_world_hold()) return;
    /* Native 8002820C owns pit death as part of camera clamping, outside
     * the player update. Use the current room's authored bottom limit for
     * each player, independent of whether their shared camera reached it.
     * This is not the visible screen bottom: vertical rooms remain playable. */
    int bottom=(int16_t)(psx_mod_read_half(0x800971F8u+0x20)+256);
    if (!zero_world) pit_death(0,bottom);
    pit_death(1,bottom);
}
static void clear_p2_combat(void) {
    memset(p2.shots,0,sizeof p2.shots);
    /* These fixed actors are initialized by native8003BFBC..8003C0A8,
     * unlike dynamically allocated shots. Retire visibility/activity as
     * native80020EE4/EEEC and80020C18/C20 do; keep their indices, parents,
     * animation resources and palettes for the next accepted action. */
    for(unsigned i=0;i<3;++i) {
        p2.trails[i*0x60+3]=p2.trails[i*0x60+4]=0;
        p2.effects[i*0x50+3]=p2.effects[i*0x50+4]=0;
    }
}
static void start_leave(CPUState *cpu) {
    memcpy(returning_body,p2.body,sizeof returning_body);
    clear_p2_combat();
    enter_zero();
    guest(cpu,0x8003A980,PLAYER,0); /* Cancel dash, charge and combat state. */
    guest(cpu,0x8003BA04,PLAYER,3); /* Native teleport-out pose. */
    guest(cpu,0x8003B954,PLAYER,0); /* Native beam velocity/action and sound. */
    psx_mod_write_word(PLAYER+0x54,0);
    leave_zero();
}
static void begin_join(CPUState *cpu, uint32_t x, uint32_t y) {
    put32(p2.body+8,x);
    join_y=(int32_t)y;
    int32_t top=(int16_t)psx_mod_read_half(0x80097206)-40;
    put32(p2.body+12,(uint32_t)(top*65536));
    put32(p2.body+0x18,le32(p2.body+8));
    put32(p2.body+0x1C,le32(p2.body+12));
    p2.body[3]=p2.body[4]=1;
    p2.body[5]=p2.body[6]=0;
    enter_zero();
    guest(cpu,0x8003A980,PLAYER,0);
    guest(cpu,0x8003BA04,PLAYER,1); /* Native incoming beam. */
    psx_mod_write_word(PLAYER+0x68,0);
    psx_mod_write_word(PLAYER+0x54,0);
    leave_zero();
    life.status[1]=MMX6_COOP_JOINING;
    join_phase=1;
}
static void start_join(CPUState *cpu) {
    memcpy(p2.body,returning_body,sizeof returning_body);
    begin_join(cpu,psx_mod_read_word(PLAYER+8),psx_mod_read_word(PLAYER+12));
}
static void join_animation(CPUState *cpu) {
    enter_zero();
    guest(cpu,0x80017A04,PLAYER,0);
    if (join_phase==1) {
        int32_t y=(int32_t)psx_mod_read_word(PLAYER+12)+8*65536;
        if (y>=join_y) {
            y=join_y;
            STATE_WORDS(restore_y,34,&y,1);
            guest(cpu,0x8003BA04,PLAYER,2); /* Native beam resolves into Zero. */
            STATE_POP(restore_y);
            join_phase=2;
        }
        psx_mod_write_word(PLAYER+12,(uint32_t)y);
    } else if (!psx_mod_read_byte(PLAYER+0x46)) {
        guest(cpu,0x8003AD18,PLAYER,0);
        psx_mod_write_byte(PLAYER+0x61,60);
        join_phase=0;
        mmx6_coop_teleport_done(&life);
    }
    leave_zero();
}
static void retain_surviving_zero(CPUState *cpu) {
    if (life.status[1]!=MMX6_COOP_LEAVING && life.status[1]!=MMX6_COOP_JOINING) return;
    /* The departure request was legal while X lived. If X dies during the
     * beam, keep the remaining player at the departure/landing position with
     * their saved health. Never let native out-of-stage mode end this run. */
    if (life.status[1]==MMX6_COOP_LEAVING) memcpy(p2.body,returning_body,sizeof returning_body);
    else put32(p2.body+12,(uint32_t)join_y);
    p2.body[3]=p2.body[4]=1;
    enter_zero();
    guest(cpu,0x8003A980,PLAYER,0);
    guest(cpu,0x8003AD18,PLAYER,0);
    psx_mod_write_byte(PLAYER+0x61,60);
    leave_zero();
    life.status[1]=MMX6_COOP_ALIVE;
    life.select_frames=life.select_armed=0;
    join_phase=0;
}
/* Bounded host-context observation, not a framework/core state checksum.
 * Excludes host pointers, retained texture caches and transient projections.
 * All fields are sampled at the existing canonical diagnostic boundary. */
static uint32_t diagnostic_host_digest(void) {
    uint32_t hash=2166136261u;
#define HASH_BYTES(data, count) do { \
    const uint8_t *bytes_=(const uint8_t *)(data); \
    for (size_t i_=0;i_<(count);++i_) hash=(hash^bytes_[i_])*16777619u; \
} while (0)
    HASH_BYTES(&p2,sizeof p2);
    HASH_BYTES(returning_body,sizeof returning_body);
    HASH_BYTES(scene_body,sizeof scene_body);
    /* Serialize integer fields explicitly; never hash structure padding. */
    const uint32_t fields[]={
        (uint32_t)life.status[0],(uint32_t)life.status[1],life.select_frames,
        life.select_armed,life.select_previous,life.wipe,life.rejoin_pending,
        previous_input,p2_edges,join_phase,arrival_pair,(uint32_t)join_y,refight_return_checkpoint,
        private_actor.character,private_actor.form,private_actor.bin_member,private_actor.bin_type,
        private_actor.dat_member,private_actor.portrait_index,private_actor.portrait_graphics,private_actor.portrait_palette,
        (uint32_t)pause_owner,(uint32_t)p2_start_previous,
        scene_owner,scene_phase,(uint32_t)scene_y,both_door_actor,both_door_origin,both_door_members,
        (uint32_t)ready,(uint32_t)enrolled,(uint32_t)failed,
        checkpoint_fatal_option,checkpoint_fatal_state
    };
    for (size_t i=0;i<sizeof fields/sizeof fields[0];++i) {
        uint8_t bytes[4]; put32(bytes,fields[i]); HASH_BYTES(bytes,sizeof bytes);
    }
    for (size_t i=0;i<sizeof death_effect/sizeof death_effect[0];++i) {
        uint8_t bytes[15];
        unsigned valid=death_effect[i].valid;
        put32(bytes,valid?death_effect[i].x:0);put32(bytes+4,valid?death_effect[i].y:0);
        put32(bytes+8,valid?death_effect[i].assembly:0);
        bytes[12]=valid?death_effect[i].layer:0;bytes[13]=(uint8_t)valid;
        bytes[14]=death_effect[i].owner;
        HASH_BYTES(bytes,sizeof bytes);
    }
    for (size_t i=0;i<sizeof pickup_owners/sizeof pickup_owners[0];++i) {
        uint8_t bytes[5];put32(bytes,pickup_owners[i].actor);bytes[4]=pickup_owners[i].seat;
        HASH_BYTES(bytes,sizeof bytes);
    }
    HASH_BYTES(zero_solid_contacts,sizeof zero_solid_contacts);
#undef HASH_BYTES
    return hash;
}
static void diagnostic_p2_boxes(void) {
    static const unsigned offsets[3]={0x50,0x54,0x68};
    uint8_t wire[MMX6_BOX_DIAG_BYTES]={0};
    put32(wire,MMX6_BOX_DIAG_MAGIC);
    put32(wire+4,MMX6_BOX_DIAG_SCHEMA);
    put32(wire+8,MMX6_BOX_DIAG_BYTES);
    put32(wire+12,frame_count);
    for(unsigned i=0;i<3;++i) {
        uint8_t *record=wire+16+i*12;
        uint32_t pointer=le32(p2.body+offsets[i]);
        put32(record,pointer);
        if(!ready || failed)continue;
        /* P2 pointers into PL00 address the private code/data bank. Reading
         * restored singleton RAM here would publish X bytes for Zero. */
        if(pointer>=OVERLAY && pointer<=OVERLAY+OVERLAY_SIZE-4u) {
            put32(record+4,MMX6_BOX_PRIVATE_OVERLAY);
            memcpy(record+8,zero_overlay+(pointer-OVERLAY),4);
        } else if(pointer>=0x80010000u && pointer<=OVERLAY-4u) {
            put32(record+4,MMX6_BOX_NATIVE_RAM);
            capture(pointer,record+8,4);
        }
    }
    project(diagnostic+MMX6_BOX_DIAG_HEADER,wire,sizeof wire);
}
static unsigned checkpoint_contact_protection_status(void);
static unsigned checkpoint_starting_hp[2],checkpoint_starting_hp_applied;
static unsigned checkpoint_starting_hp_status(void);
static unsigned checkpoint_starting_hp_mask(void);
static void checkpoint_earned_weapons_diagnostics(void);
static void diagnostics(uint16_t input) {
    ++frame_count;
    /* Odd sequence denotes publication in progress; finish with an even one.
     * Read the entire block in one emulation-thread debug command. */
    psx_mod_write_word(diagnostic+0x88,frame_count*2u-1u);
    /* Read-only publication of the active energy policy and both supplies. */
    psx_mod_write_byte(diagnostic+0x1FF0,(uint8_t)separate_subtanks);
    psx_mod_write_byte(diagnostic+0x1FF1,(uint8_t)subtank_seeded);
    for(unsigned i=0;i<2;++i) {
        psx_mod_write_byte(diagnostic+0x1FF2+i,zero_projected?saved_play[0x63+i]:psx_mod_read_byte(PLAY+0x63+i));
        psx_mod_write_byte(diagnostic+0x1FF4+i,zero_subtanks[i]);
    }
    psx_mod_write_word(diagnostic,0x434F4F50);
    psx_mod_write_word(diagnostic+4,frame_count);
    project(diagnostic+8,p2.body+8,8);
    project(diagnostic+16,p2.body+2,6);
    psx_mod_write_byte(diagnostic+24,p2.body[0x5C]);
    psx_mod_write_half(diagnostic+26,input);
    psx_mod_write_word(diagnostic+36,psx_mod_read_word(PLAY+0x90));
    psx_mod_write_byte(diagnostic+0x38,(uint8_t)life.status[0]);
    psx_mod_write_byte(diagnostic+0x39,(uint8_t)life.status[1]);
    psx_mod_write_byte(diagnostic+0x3A,(uint8_t)life.select_frames);
    psx_mod_write_byte(diagnostic+0x3B,life.wipe);
    psx_mod_write_byte(diagnostic+0x3C,(uint8_t)(pause_owner+1));
    psx_mod_write_byte(diagnostic+0x3D,(uint8_t)p2_hud_fade);
    psx_mod_write_byte(diagnostic+0x3E,(uint8_t)scene_owner);
    psx_mod_write_byte(diagnostic+0x3F,(uint8_t)scene_phase);
    project(diagnostic+0x100,p2.body,sizeof p2.body);
    project(diagnostic+0x300,p2.shots,sizeof p2.shots);
    /* Stable P1 snapshot: a debugger may otherwise observe PLAYER while a
     * nested native Zero pass is projected into that same guest address. */
    uint8_t body[0x158];
    capture(PLAYER,body,sizeof body);
    project(diagnostic+0x1800,body,sizeof body);
    psx_mod_write_word(diagnostic+0x80,1); /* diagnostic schema */
    psx_mod_write_word(diagnostic+0x84,0x1958);
    psx_mod_write_byte(diagnostic+0x8C,(uint8_t)ready);
    psx_mod_write_byte(diagnostic+0x8D,(uint8_t)enrolled);
    psx_mod_write_byte(diagnostic+0x8E,(uint8_t)failed);
    psx_mod_write_byte(diagnostic+0x90,psx_mod_read_byte(PLAY));
    psx_mod_write_byte(diagnostic+0x91,psx_mod_read_byte(PLAY+1));
    psx_mod_write_byte(diagnostic+0xAF,(uint8_t)checkpoint_contact_protection_status());
    /* C0:0off/1selected-pending/2applied; C1/C2:requested actualHP (0off);
     * C3:once-applied seat mask. No death/heal/result bit is authored. */
    psx_mod_write_byte(diagnostic+0xC0,(uint8_t)checkpoint_starting_hp_status());
    psx_mod_write_byte(diagnostic+0xC1,(uint8_t)checkpoint_starting_hp[0]);
    psx_mod_write_byte(diagnostic+0xC2,(uint8_t)checkpoint_starting_hp[1]);
    psx_mod_write_byte(diagnostic+0xC3,(uint8_t)(checkpoint_starting_hp_applied?checkpoint_starting_hp_mask():0));
    checkpoint_earned_weapons_diagnostics();
    psx_mod_write_word(diagnostic+0x94,diagnostic_host_digest());
    psx_mod_write_word(diagnostic+0x98,1); /* bounded host FNV-1a, not core CRC */
#ifdef MMX6_COOP_MODERN_STATE
    psx_mod_write_byte(diagnostic+0x9C,(uint8_t)!!psx_mod_netplay_has_state_digest());
#endif
    /* Host-owned P2 pools, never a second read of the projected singleton.
     * Publish before completing the SAME base sequence: old base readers
     * keep their schema1/1958h contract; extension readers use one1C20h RPC. */
    psx_mod_write_word(diagnostic+MMX6_FX_DIAG_HEADER,MMX6_FX_DIAG_MAGIC);
    psx_mod_write_word(diagnostic+MMX6_FX_DIAG_HEADER+4,MMX6_FX_DIAG_SCHEMA);
    psx_mod_write_word(diagnostic+MMX6_FX_DIAG_HEADER+8,MMX6_FX_DIAG_BYTES);
    psx_mod_write_word(diagnostic+MMX6_FX_DIAG_HEADER+12,frame_count);
    project(diagnostic+MMX6_FX_DIAG_TRAILS,p2.trails,sizeof p2.trails);
    project(diagnostic+MMX6_FX_DIAG_ATTACHED,p2.effects,sizeof p2.effects);
    diagnostic_p2_boxes();
    psx_mod_write_word(diagnostic+0x88,frame_count*2u);
}
static int diagnostic_mutation_allowed(void) {
#ifdef PSX_NO_DEBUG_TOOLS
    return 0;
#else
    return !psx_mod_netplay_is_active();
#endif
}
static int checkpoint_mounted_fatal_ready(unsigned seat);
#include "mmx6_coop_checkpoint.inc"
static uint16_t p2_input(unsigned consumer) {
    uint16_t raw=(uint16_t)~sio_get_pad_buttons_slot(1);
    int contaminated=0;
    if (psx_mod_read_byte(diagnostic+0x30)) {
        if (diagnostic_mutation_allowed()) {
            raw=(uint16_t)~psx_mod_read_half(diagnostic+0x34);contaminated=1;
#ifdef MMX6_COOP_INPUT_TAINT_API
            psx_session_input_taint_add(PSX_INPUT_TAINT_GAME_MAILBOX);
#endif
        }
        else {
            psx_mod_write_byte(diagnostic+0x30,0);
            psx_mod_counter_add("mmx6.coop.debug-input-rejected",1);
        }
    }
    return mmx6_diagnostics_p2(consumer,raw,contaminated);
}
/* One original first-slot armor in each authenticated native stage, never a
 * second vehicle/world pass. Recycle EE924 and alternate EC6B4 both request
 * D5=1 for CD340 (2 denotes the secondary slot); 3A268 consumes it as -1.
 * Existing body bytes/shared RAM own the snapshot/digest; no owner cache. */
enum { RIDE_NONE=2, RIDE_INVALID=3, RIDE_RECYCLE=1, RIDE_ALTERNATE=2 };
static void ride_body(unsigned seat,uint8_t body[0x158]) {
    if(seat==(unsigned)!!zero_projected)capture(PLAYER,body,0x158);
    else memcpy(body,seat?p2.body:p1.body,0x158);
}
static unsigned ride_owner(void) {
    uint8_t body[0x158];unsigned claims=0,owner=RIDE_NONE;
    for(unsigned seat=0;seat<2;++seat) {
        ride_body(seat,body);
        if(body[0xD5]==1 || body[0xD5]==255){owner=seat;++claims;}
    }
    return claims>1?RIDE_INVALID:owner;
}
static int ride_source(void) {
    if(psx_mod_read_byte(PLAY+12)==4 && !psx_mod_read_byte(PLAY+13) &&
        psx_mod_read_byte(RIDE) && !psx_mod_read_byte(RIDE+1) &&
        psx_mod_read_word(RIDE+0x10)==0x800F2B1Cu &&
        psx_mod_read_word(0x80071380u)==0x800F2414u &&
        psx_mod_read_word(0x800F2414u)==0x27BDFFE8u &&
        psx_mod_read_word(0x800EE924u)==0x27BDFFD8u &&
        psx_mod_read_word(0x800EEA74u)==0x24050012u)return RIDE_RECYCLE;
    /* Original BIN28 7f49ac29...; only authored20/1 recordF2588 and the
     * first-slot type1 dispatcher/action/geometry. Preserve source flags0/1
     * and native-observed allocated81; other flags remain unsupported.
     * Secondary requests2/FE never claim this slot. */
    uint32_t record=psx_mod_read_word(0x800F2588u);
    return psx_mod_read_byte(PLAY+12)==20 && psx_mod_read_byte(PLAY+13)==1 &&
        psx_mod_read_byte(RIDE) && psx_mod_read_byte(RIDE+1)==1 &&
        psx_mod_read_word(RIDE+0x10)==0x800F2588u &&
        (record==0x03011E00u || record==0x03011E01u || record==0x03011E81u) &&
        psx_mod_read_word(0x800F258Cu)==0x01620020u &&
        psx_mod_read_word(0x80071384u)==0x800F01A4u &&
        psx_mod_read_word(0x800F01A4u)==0x27BDFFE8u &&
        psx_mod_read_word(0x800F2F34u)==0x800EBF64u &&
        psx_mod_read_word(0x800F2F38u)==0x800EFC54u &&
        psx_mod_read_word(0x800EFC54u)==0x27BDFFE0u &&
        psx_mod_read_word(0x800F2F58u)==0x800EC6B4u &&
        psx_mod_read_word(0x800EC6B4u)==0x27BDFFD8u &&
        psx_mod_read_word(0x800EC7B0u)==0x24422F2Cu &&
        psx_mod_read_word(0x800EC804u)==0x24050012u &&
        psx_mod_read_word(0x800EC830u)==0x24020002u &&
        psx_mod_read_word(0x800EC834u)==0x24020001u &&
        psx_mod_read_word(0x800EC838u)==0xA22200D5u &&
        psx_mod_read_word(0x800F2F28u)==0x1D0F0300u &&
        psx_mod_read_word(0x800F2F2Cu)==0x0A0F1600u?RIDE_ALTERNATE:0;
}
static int ride_grounded(unsigned kind) {
    return ((kind==RIDE_ALTERNATE?psx_mod_read_byte(RIDE+0xA8):
        (psx_mod_read_byte(RIDE+0x70)|psx_mod_read_byte(RIDE+0x71)))&8u)!=0;
}
/* Native boarding replaces the pilot foot box/contact with action18/D5.
 * A deliberate partner return may use that one grounded, intact owner as its
 * anchor; airborne/unclaimed/retired armor still defers the queued request. */
static int safe_join_landing(void) {
    if(!psx_mod_read_byte(PLAYER+0x67) && (psx_mod_read_byte(PLAYER+0x70)&8u))return 1;
    unsigned hp=psx_mod_read_byte(PLAYER+0x5C),armor_hp=psx_mod_read_byte(RIDE+0x5C);
    unsigned claim=psx_mod_read_byte(PLAYER+0xD5),kind=ride_source();
    return life.status[0]==MMX6_COOP_ALIVE && psx_mod_read_byte(PLAYER+4)==1 &&
        psx_mod_read_byte(PLAYER+5)==0x12 && (claim==1 || claim==255) && hp && hp<128 &&
        kind && ride_owner()==0 && psx_mod_read_byte(RIDE+4)==1 &&
        armor_hp && armor_hp<128 && (psx_mod_read_byte(RIDE+0x97)&0xC0u)==0x40u &&
        ride_grounded(kind);
}
static int ride_entry(CPUState *cpu,unsigned seat) {
    uint8_t body[0x158];ride_body(seat,body);
    unsigned kind=ride_source();
    /* Native EE924/EC6B4 eligibility plus the dispatcher's personal hit-pause
     * gate. The original callback still performs the actual boarding. */
    if(!kind || life.status[seat]!=MMX6_COOP_ALIVE || scene_passenger(seat) ||
       body[0xCC] || body[0xD0] || body[0xD5] || psx_mod_read_byte(PLAY+0x0F) ||
       (body[2] && body[0x8E]) || body[0x7A] || body[0xE0] ||
       (int8_t)body[0x5C]<=0 || body[0xA4] || body[0x79] ||
       (psx_mod_read_half(RIDE+0x96)&0x8200u) ||
       !ride_grounded(kind))return 0;
    uint8_t resident[0x158];capture(PLAYER,resident,sizeof resident);
    uint32_t box=psx_mod_read_word(RIDE+0x68);
    STATE_BYTES(restore_body,58,resident,sizeof resident);
    STATE_WORDS(restore_box,59,&box,1);
    project(PLAYER,body,sizeof body);
    psx_mod_write_word(RIDE+0x68,kind==RIDE_ALTERNATE?0x800F2F2Cu:0x800F3A48u);
    uint32_t overlap=guest(cpu,0x8002DCF4u,PLAYER,RIDE);
    psx_mod_write_word(RIDE+0x68,box);project(PLAYER,resident,sizeof resident);
    STATE_POP(restore_box);STATE_POP(restore_body);
    return overlap!=0;
}
static int ride_tick(CPUState *cpu,uint32_t address) {
    if(ride_call || !enrolled || failed || address!=0x80020A08u ||
       cpu->gpr[31]!=0x80020C60u || !ride_source())return 0;
    ride_call=1;
    unsigned owner=ride_owner();
    if(owner==RIDE_INVALID){failed=1;ride_call=0;return 0;}
    if(owner==RIDE_NONE && !(psx_mod_read_byte(RIDE+0x97)&0x40u) &&
       psx_mod_read_byte(RIDE+4)==1 && !psx_mod_read_byte(RIDE+5)) {
        /* Preserve native primary priority if both eligible boxes overlap. */
        if(ride_entry(cpu,0))owner=0;
        else if(ride_entry(cpu,1))owner=1;
    }
    unsigned resident=(unsigned)!!zero_projected;
    if(owner==RIDE_NONE)owner=resident;
    uint32_t context[3]={owner,(uint32_t)inside,resident};
    STATE_WORDS(restore_context,60,context,3);
    uint32_t result;
    if(owner==resident)result=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    else if(owner==1) {
        uint8_t input[6];capture(0x800C456C,input,sizeof input);
        STATE_BYTES(restore_input,61,input,sizeof input);
        inside=1;enter_zero();
        /* Armor runs before controller()'s private pass. Translate this
         * accepted sample now without consuming that pass's edge history. */
        uint16_t raw=p2_input(MMX6_INPUT_CONTROLLER_PLAYER);raw=(uint16_t)((raw<<8)|(raw>>8));
        psx_mod_write_half(0x800C456C,raw);
        psx_mod_write_half(0x800C456E,previous_input);
        psx_mod_write_half(0x800C4570,(uint16_t)(raw&~previous_input));
        guest(cpu,0x8003CD44u,0,0);
        result=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
        leave_zero_context(1);inside=(int)context[1];
        project(0x800C456C,input,sizeof input);STATE_POP(restore_input);
    } else result=shared_effect_as_primary(cpu,address,cpu->gpr[4]);
    STATE_POP(restore_context);ride_call=0;cpu->gpr[2]=result;return 1;
}
/* Existing agreed p1/p2 fatal choices only. The completed Recycle option7
 * receipt may precede the real portal; this exact original mounted20/1
 * context permits native EFCCC/EFCD0's HP-only rider/armor request. */
static int checkpoint_mounted_fatal_ready(unsigned seat) {
    if(seat>1 || checkpoint_fatal_option!=seat+1 || checkpoint_lab_option!=7 ||
       !checkpoint_lab_receipt_complete() || !checkpoint_safe_boundary() ||
       scene_call || clear_phase || life.wipe || join_phase || arrival_pair || both_door_actor ||
       psx_mod_read_byte(PLAY+12)!=20 || psx_mod_read_byte(PLAY+13)!=1 ||
       psx_mod_read_byte(diagnostic+0xAD)!=2 || ride_source()!=RIDE_ALTERNATE ||
       ride_owner()!=seat || !(psx_mod_read_byte(RIDE)&1u) || psx_mod_read_byte(RIDE+4)!=1 ||
       !psx_mod_read_byte(RIDE+0x5C) || psx_mod_read_byte(RIDE+0x5C)>=128 ||
       (psx_mod_read_byte(RIDE+0x97)&0xC0u)!=0x40u || !(psx_mod_read_byte(RIDE+0xA8)&8u) ||
       !checkpoint_fatal_idle(seat^1u) ||
       psx_mod_read_word(0x800EFCC8u)!=0x2402FF80u ||
       psx_mod_read_word(0x800EFCCCu)!=0xA102005Cu ||
       psx_mod_read_word(0x800EFCD0u)!=0xA202005Cu)return 0;
    uint8_t pilot[0x158],partner[0x158];ride_body(seat,pilot);ride_body(seat^1u,partner);
    return pilot[0] && pilot[3] && pilot[4]==1 && pilot[5]==0x12 && pilot[0xD5]==255 &&
        pilot[0x5C] && pilot[0x5C]<128 && !partner[0xD5];
}
static void ride_sync_rider(void) {
    if(!ride_source() || !(psx_mod_read_byte(RIDE+0x97)&0x40u))return;
    unsigned owner=ride_owner();
    if(owner>1 || owner==(unsigned)!!zero_projected)return;
    uint8_t *body=owner?p2.body:p1.body;
    /* Literal 31F04..31F28 copyout after shared vehicle collision. The
     * second body-only solid pass deliberately never resolves armor twice. */
    if(body[5]==0x12) {
        put32(body+8,psx_mod_read_word(RIDE+8));
        put32(body+12,psx_mod_read_word(RIDE+12));
    }
}
#include "mmx6_coop_victory.inc"
/* A scene's ordinary incoming constructor returns an on-foot action. A
 * passenger who still owns the intact native armor must consume the original
 * boarding request again; retaining D5=-1 alone leaves an on-foot pilot. */
static int ride_resume_passenger(CPUState *cpu,unsigned seat,const uint8_t *before) {
    unsigned hp=psx_mod_read_byte(PLAYER+0x5C),ride_hp=psx_mod_read_byte(RIDE+0x5C);
    if(before[4]!=1 || before[5]!=0x12 ||
       (before[0xD5]!=1 && before[0xD5]!=255) ||
       before[2]!=psx_mod_read_byte(PLAYER+2) || life.status[seat]!=MMX6_COOP_ALIVE ||
       psx_mod_read_byte(PLAYER+4)!=1 || !hp || hp>=128 ||
       !ride_source() || ride_owner()!=seat || psx_mod_read_byte(RIDE+4)!=1 ||
       !ride_hp || ride_hp>=128 || (psx_mod_read_byte(RIDE+0x97)&0xC0u)!=0x40u)
        return 0;
    /* Original31F14..31F28 anchors a mounted body to this one vehicle. New
     * boarding begins with matching history, not the outgoing beam's Y. */
    for(unsigned axis=8;axis<=12;axis+=4) {
        uint32_t value=psx_mod_read_word(RIDE+axis);
        psx_mod_write_word(PLAYER+axis,value);
        psx_mod_write_word(PLAYER+axis+0x10,value);
    }
    /* OriginalEEAA8 requests D5=1. Original3A268 initializes the actor's
     * mounted resources/action18/null foot box and consumes it as D5=-1. */
    psx_mod_write_byte(PLAYER+0xD5,1);
    guest(cpu,0x8003A268u,PLAYER,0);
    return 1;
}
static int arrival_source(void);
static int arrival_grounded(const uint8_t *body);
/* One projected incoming actor only. Callers own enter/leave_zero and retain
 * the canonical world clocks, scene flags and camera around these calls. */
static void arrival_body_tick(CPUState *cpu) {
    for (unsigned i=0;i<8;i+=2) psx_mod_write_half(PLAYER+0x7C+i,0);
    guest(cpu,0x80034DCC,0,0);
    guest(cpu,0x8002012C,0,0);
    guest(cpu,0x8002F288,PLAYER,0);
    guest(cpu,0x80020D74,0,0);
    guest(cpu,0x80020DC8,0,0);
}
static void scene_begin(unsigned seat, uint32_t source) {
    if (scene_owner || clear_phase || !enrolled || life.status[seat]!=MMX6_COOP_ALIVE) return;
    scene_owner=seat+1;
    scene_phase=0;
    life.select_frames=0;
    psx_mod_write_word(diagnostic+0x70,psx_mod_read_word(diagnostic+0x70)+1);
    psx_mod_write_word(diagnostic+0x74,source);
    /* Animation starts at the end of this world pass, after all projections
     * have unwound. A dead or voluntarily absent partner never joins it. */
    if (life.status[seat^1]==MMX6_COOP_ALIVE ||
        (seat==0 && life.status[1]==MMX6_COOP_JOINING)) scene_phase=1;
}
static int sigma_transition_in_place(const CPUState *cpu,uint32_t address) {
    /* BIN15 first-body death EDEC4 and later-body init EFC90 both request
     * native command20. They lock the one world; neither departs the room.
     * Keep the already-living pair in place through those original holds.
     * Initial type61 arrival and final type62 death retain their policies. */
    if(address!=0x8003D308u || cpu->gpr[4]!=20 || scene_owner ||
       !ready || !enrolled || failed || scene_call || zero_projected ||
       private_draw || world_render || pause_owner>=0 ||
       psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
       psx_mod_read_byte(PLAY+12)!=12 || psx_mod_read_byte(PLAY+13)!=1 ||
       !shared_clear_living(0) || !shared_clear_living(1) ||
       !psx_mod_read_byte(PLAYER) || !psx_mod_read_byte(PLAYER+3) ||
       !p2.body[0] || !p2.body[3])return 0;
    const unsigned later=cpu->gpr[31]==0x800EFDFCu;
    if(!later && cpu->gpr[31]!=0x800EDEFCu)return 0;
    /* The original death preserves its actor in s0; later init uses s1.
     * PLAY20 is cleared by the genuine transform, so cannot identify init. */
    const uint32_t actor=cpu->gpr[later?17:16];
    if(actor<0x8008EF48u || actor>=0x80090C88u ||
       (actor-0x8008EF48u)%0x9Cu || !(psx_mod_read_byte(actor)&1u) ||
       psx_mod_read_byte(actor+1)!=(later?62:61) || psx_mod_read_byte(actor+2) ||
       psx_mod_read_byte(actor+4)!=(later?1:2) ||
       psx_mod_read_byte(actor+5)!=(later?2:0) || psx_mod_read_byte(actor+0x5C) ||
       /* Original EE0F4/2CF0C clears the complete actor before type62 init. */
       psx_mod_read_word(actor+0x10)!=(later?0u:0x800F57ECu) ||
       (!later && psx_mod_read_word(PLAY+0x20)!=actor))return 0;
    static const uint32_t common[][2]={
        {0x800F5920u,0x800EDE18u},{0x800F5924u,0x800F2154u},
        {0x800F6674u,0x800EDE88u},{0x800F6E18u,0x800EFC90u}};
    for(unsigned i=0;i<sizeof common/sizeof common[0];++i)
        if(psx_mod_read_word(common[i][0])!=common[i][1])return 0;
    if(later)return psx_mod_read_word(0x800EFCA4u)==0x00808821u &&
        psx_mod_read_word(0x800EFDB4u)==0xA2220004u &&
        psx_mod_read_word(0x800EFDDCu)==0xA2320005u &&
        psx_mod_read_word(0x800EFDF0u)==0x92650015u &&
        psx_mod_read_word(0x800EFDF4u)==0x0C00F4C2u &&
        psx_mod_read_word(0x800EFDF8u)==0x24040014u;
    return psx_mod_read_word(0x800EDECCu)==0x00808021u &&
        psx_mod_read_word(0x800EDEECu)==0x90650015u &&
        psx_mod_read_word(0x800EDEF0u)==0x24040014u &&
        psx_mod_read_word(0x800EDEF4u)==0x0C00F4C2u &&
        psx_mod_read_word(0x800EDEF8u)==0xA06000CAu;
}
static void script_begin(CPUState *cpu, uint32_t address) {
    if(shared_clear_admit(cpu,address))return;
    if (!scene_call && !failed) {
        const int in_place=sigma_transition_in_place(cpu,address);
        scene_begin(zero_projected?1:0,address);
        if(in_place)scene_phase=0;
    }
}
#include "mmx6_coop_recycle_portal.inc"
#include "mmx6_coop_refight_portal.inc"
static int door_eligibility(CPUState *cpu, uint32_t address) {
    /* Original 80050250 calls its pure predicate at 80050360, after its
     * subtype prerequisites and once-only native collision/drawing. Veto
     * only this admission; never manufacture a successful native overlap.
     * The callback frame already owns/digests these future-restored words,
     * including across guest yields. No untracked gate or host pointer. */
    if (address!=0x80050C88u || cpu->gpr[31]!=0x80050368u ||
        failed || !enrolled) return 0;
    /* Zero's original menu preview draws a native world while already
     * projected. Its door AI bypasses door_begin's outer callback guard.
     * Drawing a personal menu must never claim a touching actor or set the
     * original stage lock, under Either or Both. The pure predicate remains
     * authoritative again after the owning menu actually releases. */
    if (pause_owner>=0) { cpu->gpr[2]=0;return 1; }
    if (!scene_call) return 0;
    for (unsigned i=state_track.count;i;--i) {
        const Mmx6StateFrame *f=&state_track.frame[i-1];
        if (f->tag!=35 || !f->words || f->bytes!=6*4u) continue;
        uint32_t context[6];memcpy(context,f->saved,sizeof context);
        if (context[0]==0x80050250u && context[1]==cpu->gpr[4] &&
            context[4] && context[5] && !context[3]) {
            cpu->gpr[2]=0;return 1;
        }
        return 0;
    }
    return 0;
}
static uint32_t door_probe(CPUState *cpu,uint32_t actor,unsigned both) {
    if (both) {
        /* Native 80050C88 dereferences four-byte authored boxes. A not-yet
         * present body/box cannot supply permission for Both. */
        uint32_t a=psx_mod_read_word(actor+0x68),p=psx_mod_read_word(PLAYER+0x68);
        if (!psx_mod_read_byte(PLAYER) || a<0x80010000u || a>0x801FFFFCu ||
            p<0x80010000u || p>0x801FFFFCu) return 0;
    }
    return guest(cpu,0x80050C88u,actor,0);
}
static uint8_t door_body_byte(unsigned seat,unsigned offset) {
    return seat?p2.body[offset]:psx_mod_read_byte(PLAYER+offset);
}
static uint32_t door_body_x(unsigned seat) {
    return seat?le32(p2.body+8):psx_mod_read_word(PLAYER+8);
}
static void door_capture_extents(void) {
    memset(both_door_extents,0,sizeof both_door_extents);
    for(unsigned seat=0;seat<2;++seat)if(both_door_members&(1u<<seat)) {
        uint8_t body[sizeof p2.body];
        if(seat==(unsigned)!!zero_projected)capture(PLAYER,body,sizeof body);
        else memcpy(body,seat?p2.body:p1.body,sizeof body);
        uint32_t box=le32(body+0x68);
        if(body[2]>1 || box<0x80010000u || box>0x801FFFFCu)continue;
        /* Native3CCBC's standing box bounds must survive the original ghost
         * interval. Include an already larger authored admission pose too. */
        uint32_t standing=0x80073D50u+body[2]*4u;
        int left=0,right=0;
        for(unsigned n=0;n<2;++n) {
            uint32_t shape=n?standing:box;
            int offset=(int8_t)psx_mod_read_byte(shape);
            unsigned radius=psx_mod_read_byte(shape+2),height=psx_mod_read_byte(shape+3);
            if(!radius || !height) {left=right=0;break;}
            int l=offset-(int)radius,h=offset+(int)radius;
            if(!n || l<left)left=l;
            if(!n || h>right)right=h;
        }
        both_door_extents[seat][0]=(int16_t)left;both_door_extents[seat][1]=(int16_t)right;
    }
}
static int door_all_living_clear(uint32_t actor,unsigned members,uint32_t velocity) {
    uint32_t box=psx_mod_read_word(actor+0x68);
    if(box<0x80010000u || box>0x801FFFFCu || !psx_mod_read_byte(box+2))return 0;
    int direction=(int32_t)velocity<0?-1:1;
    int edge=(int8_t)psx_mod_read_byte(box)+direction*(int)psx_mod_read_byte(box+2);
    int64_t plane=(int32_t)psx_mod_read_word(actor+8)+(int64_t)edge*65536;
    for(unsigned seat=0;seat<2;++seat)if(members&(1u<<seat)) {
        int left=both_door_extents[seat][0],right=both_door_extents[seat][1];
        if(left>=right)return 0; /* Missing box is never clearance permission. */
        int32_t next=(int32_t)(door_body_x(seat)+velocity); /* Native wrapping ADdu. */
        int64_t extent=(int64_t)next+(int64_t)(direction>0?left:right)*65536;
        if(direction>0?extent<=plane:extent>=plane)return 0;
    }
    return 1;
}
static int door_update(CPUState *cpu,uint32_t address) {
    uint32_t actor=cpu->gpr[4];
    if(address!=0x80050DFCu || inside || scene_call || zero_projected || failed ||
       !enrolled || !both_door_traversal_active() || actor!=both_door_actor) return 0;
    unsigned members=both_door_members;
    for(unsigned seat=0;seat<2;++seat)
        if(life.status[seat]!=MMX6_COOP_ALIVE)members&=~(1u<<seat);
    if(!members)return 0;
    unsigned phase=psx_mod_read_byte(actor+5),seat=(members&1)?0:1;
    uint32_t velocity=psx_mod_read_word(actor+0x84);
    if(members==3) {
        if(phase==1) {
            /* Each original player must acknowledge request1 itself. Native
             * 50540 waits for negative D4; project an unready actor rather
             * than copying the other body's FF acknowledgement. */
            if((int8_t)door_body_byte(1,0xD4)>=0)seat=1;
        } else if(phase==3) {
            /* 50EA0 moves its resident and commits the shared camera once.
             * Use the trailing actor for that original camera/close test. */
            int32_t x0=(int32_t)door_body_x(0),x1=(int32_t)door_body_x(1);
            if((int32_t)velocity<0?x1>x0:x1<x0)seat=1;
        } else if(phase==4 && (door_body_byte(1,0xD0) ||
                  door_body_byte(1,0xD4) || door_body_byte(1,0xE0)))seat=1;
    }
    uint32_t context[6]={address,actor,seat,phase,members,velocity};
    STATE_WORDS(restore_door_update,58,context,6);
    scene_call=1;
    if(phase==3 && !door_all_living_clear(actor,members,velocity)) {
        /* Literal native50DFC outer history and50EB4..50ECC wrapping carry.
         * 50EA0 has no other side effect before its close-only branch.
         * Defer that branch while any full living extent is inside; do not
         * forge camera equality, a phase, an animation or a close result.
         * Original2CB50 still draws once as the outer50E40 call does. */
        psx_mod_write_word(actor+0x18,psx_mod_read_word(actor+8));
        psx_mod_write_word(actor+0x1C,psx_mod_read_word(actor+12));
        for(unsigned member=0;member<2;++member)if(members&(1u<<member)) {
            uint32_t next=door_body_x(member)+velocity;
            if(member)put32(p2.body+8,next);else psx_mod_write_word(PLAYER+8,next);
        }
        if(seat) {inside=1;enter_zero();}
        uint32_t draw_a2=cpu->gpr[6];STATE_WORDS(restore_door_draw,68,&draw_a2,1);
        cpu->gpr[6]=PLAYER; /* Original50E8C's A2 survives into outer drawing. */
        uint32_t result=guest(cpu,0x8002CB50u,actor,PLAY);
        cpu->gpr[6]=draw_a2;STATE_POP(restore_door_draw);
        if(seat) {leave_zero_context(1);inside=0;}
        scene_call=0;STATE_POP(restore_door_update);cpu->gpr[2]=result;return 1;
    }
    if(seat) {inside=1;enter_zero();}
    uint32_t result=guest(cpu,address,actor,cpu->gpr[5]);
    if(members==3) {
        uint8_t *other=seat?p1.body:p2.body;
        if(phase==1 && psx_mod_read_byte(PLAYER+0xD4)==0xFE &&
           (int8_t)other[0xD4]<0) {
            /* Literal body-local commands of 50574/50580. Door animation,
             * sound, PLAY and camera commands already executed once. */
            other[0xD4]=0xFE;put32(other+0x68,0);
        } else if(phase==3) {
            /* Literal native 50EB4..50ECC per-body 16.16 addition. The
             * waiting action19 does not move a body on its own. */
            put32(other+8,le32(other+8)+velocity);
            if(!psx_mod_read_byte(PLAYER+0xD4)) {
                other[0xD4]=0;
                uint8_t resident[sizeof p2.body];capture(PLAYER,resident,sizeof resident);
                STATE_BYTES(restore_door_body,59,resident,sizeof resident);
                project(PLAYER,other,sizeof resident);
                guest(cpu,0x8003CCBCu,PLAYER,0); /* Other character's original standing box. */
                capture(PLAYER,other,sizeof resident);project(PLAYER,resident,sizeof resident);
                STATE_POP(restore_door_body);
            }
        }
    }
    if(seat) {leave_zero_context(1);inside=0;}
    scene_call=0;STATE_POP(restore_door_update);cpu->gpr[2]=result;
    return 1;
}
static int door_begin(CPUState *cpu, uint32_t address) {
    if (scene_call || inside || !enrolled || failed || scene_owner) return 0;
    uint32_t actor=cpu->gpr[4];
    scene_call=1;
    unsigned seat=0;
    uint32_t context[6]={address,actor,seat,0,both_doors,0};STATE_WORDS(restore_door,35,context,6);
    unsigned present=life.status[0]==MMX6_COOP_ALIVE;
    uint32_t hit=present?door_probe(cpu,actor,both_doors):0;
    unsigned all=hit;
    if ((both_doors || !hit) && life.status[1]==MMX6_COOP_ALIVE) {
        inside=1;
        enter_zero();
        uint32_t second=door_probe(cpu,actor,both_doors);
        leave_zero();
        inside=0;
        if (second && !hit) seat=1;
        all=(!present || all) && second;
        present=1;hit|=second;
    }
    if (both_doors) hit=present && all;
    /* Probe only the pure native overlap test. Door AI, effects and room
     * changes still execute once, under the touching player's context. */
    context[2]=seat;context[3]=hit;context[5]=1;STATE_UPDATE(restore_door,context);
    if (seat) { inside=1; enter_zero(); }
    uint32_t result=guest(cpu,address,actor,cpu->gpr[5]);
    if (hit && psx_mod_read_byte(PLAYER+0xD4)) {
        scene_begin(seat,address);
        /* Both bodies already passed the original native eligibility. Keep
         * the native scene lock, without withdrawing/rejoining a passenger.
         * Other doors, portals and scripted scenes retain their own policy. */
        if (both_doors) {
            scene_phase=0;
            both_door_actor=actor;
            both_door_origin=psx_mod_read_word(actor+0x10);
            both_door_members=(life.status[0]==MMX6_COOP_ALIVE?1u:0u)|
                (life.status[1]==MMX6_COOP_ALIVE?2u:0u);
            door_capture_extents();
            /* Native AI admitted every living original body box, but sets
         * D4 only on its resident player. Give the other admitted body
         * that same request1. Each original player earns its own FF ack;
         * door_update handles later body commands and native movement. */
            if (life.status[seat^1]==MMX6_COOP_ALIVE) {
                uint8_t request=psx_mod_read_byte(PLAYER+0xD4);
                if (seat) p1.body[0xD4]=request;
                else p2.body[0xD4]=request;
            }
        }
    }
    if (seat) { leave_zero_context(1); inside=0; }
    scene_call=0;
    STATE_POP(restore_door);
    cpu->gpr[2]=result;
    return 1;
}
static int interaction_inside(uint32_t address, uint32_t actor, unsigned seat) {
    int x=seat?(int32_t)le32(p2.body+8)>>16:(int16_t)psx_mod_read_half(PLAYER+10);
    int y=seat?(int32_t)le32(p2.body+12)>>16:(int16_t)psx_mod_read_half(PLAYER+14);
    if (address==0x80051924) {
        int dx=x-(int16_t)psx_mod_read_half(actor+10);
        int dy=y-(int16_t)psx_mod_read_half(actor+14);
        return dx>=-64 && dx<=64 && dy>=-104 && dy<=16;
    }
    unsigned stage=psx_mod_read_byte(PLAY+12), sub=psx_mod_read_byte(PLAY+13);
    unsigned row=psx_mod_read_byte(0x8007A124+stage*2+sub);
    uint32_t bounds=0x8007A154+row*128+(psx_mod_read_byte(actor+2)&15)*8;
    return x>(int16_t)psx_mod_read_half(bounds) && x<(int16_t)psx_mod_read_half(bounds+2) &&
        y>(int16_t)psx_mod_read_half(bounds+4) && y<(int16_t)psx_mod_read_half(bounds+6);
}
static int interaction_begin(CPUState *cpu, uint32_t address) {
    if (scene_call || inside || !enrolled || failed || scene_owner) return 0;
    uint32_t actor=cpu->gpr[4];
    int first=life.status[0]==MMX6_COOP_ALIVE && interaction_inside(address,actor,0);
    int second=life.status[1]==MMX6_COOP_ALIVE && interaction_inside(address,actor,1);
    int optional=address==0x80052F64 && (psx_mod_read_byte(actor+2)&0xF0);
    unsigned seat=second && (!first || (optional && (p2_edges&0x100) &&
        !(psx_mod_read_half(0x800C4570)&0x100)));
    uint32_t context[3]={address,actor,seat};STATE_WORDS(restore_context,36,context,3);
    scene_call=1;
    uint8_t input[6];
    unsigned restore_input=UINT32_MAX;
    if (seat) {
        inside=1;
        capture(0x800C456C,input,sizeof input);
        restore_input=mmx6_state_push(6,input,sizeof input,0);
        enter_zero();
        uint16_t raw=p2_input(MMX6_INPUT_INTERACTION); raw=(uint16_t)((raw<<8)|(raw>>8));
        psx_mod_write_half(0x800C456C,raw);
        psx_mod_write_half(0x800C4570,p2_edges);
    }
    uint32_t result=guest(cpu,address,actor,cpu->gpr[5]);
    if (psx_mod_read_byte(PLAYER+0xD0) || psx_mod_read_byte(PLAY+0x10)==2) {
        scene_begin(seat,address);
        /* Original Dr. Light action20 and optional Alia radio conversations
         * stay in this room. 530E4..53194 admits the latter only after its
         * authored bounds, live body and fresh Select check; the high nibble
         * distinguishes it from mandatory event/story zones on the same path.
         * Retain the selected owner and original locks, with the living
         * partner visible in place. Neither scene has a passenger destination.
         * Mandatory story zones, doors and authored transports retain their
         * own withdrawal/arrival policy; never bypass their prerequisites. */
        if (address==0x80051924u ||
            (address==0x80052F64u && (psx_mod_read_byte(actor+2)&0xF0u))) scene_phase=0;
    }
    if (seat) {
        leave_zero_context(1);
        project(0x800C456C,input,sizeof input);
        STATE_POP(restore_input);
        inside=0;
    }
    scene_call=0;
    STATE_POP(restore_context);
    cpu->gpr[2]=result;
    return 1;
}
static int scene_shared_locked(void) {
    return psx_mod_read_byte(PLAY+0x10) || psx_mod_read_byte(PLAY+0x1C) ||
        psx_mod_read_byte(0x8008EAFC);
}
static int scene_locked(const uint8_t *owner) {
    return owner[0xD0] || owner[0xD4] || owner[0x7A] || scene_shared_locked();
}
static int scene_owner_fatal(void) {
    if(!scene_owner || !scene_phase || life.wipe || clear_phase) return 0;
    unsigned owner=scene_owner-1;
    unsigned hp=owner?psx_mod_read_byte(PLAYER+0x5C):p2.body[0x5C];
    return (life.status[owner]==MMX6_COOP_DYING || life.status[owner]==MMX6_COOP_FALLEN) &&
        mmx6_coop_living(&life,owner^1u) && scene_body[4]==1 &&
        scene_body[0x5C] && scene_body[0x5C]<128 && hp && hp<128;
}
static void scene_tick(CPUState *cpu) {
    if (!scene_owner || !enrolled) return;
    if(both_door_actor && !both_door_source_valid()) {
        int pending=((both_door_members&1) && life.status[0]==MMX6_COOP_ALIVE &&
                     psx_mod_read_byte(PLAYER+0xD4)) ||
                    ((both_door_members&2) && life.status[1]==MMX6_COOP_ALIVE && p2.body[0xD4]);
        both_door_reset();
        /* An original completed door may retire normally. A missing or
         * reused actor cannot authorize more motion or invent a release. */
        if(pending) {failed=1;return;}
    }
    unsigned seat=scene_owner-1, passenger=seat^1;
    uint8_t owner[sizeof scene_body];
    if (seat) memcpy(owner,p2.body,sizeof owner);
    else capture(PLAYER,owner,sizeof owner);
    int owner_dead=owner[4]==2 || life.status[seat]==MMX6_COOP_DYING ||
        life.status[seat]==MMX6_COOP_FALLEN;
    /* A fatal body can retain personal control/door acknowledgements. Only
     * the original shared script/dialogue holds can delay its survivor. */
    int locked=owner_dead?scene_shared_locked():scene_locked(owner);
    if (!scene_phase) {
        /* A voluntary departure already in flight still finishes, even if
         * native gameplay is now frozen for the other player's dialogue. */
        if (!seat && life.status[1]==MMX6_COOP_LEAVING) {
            int prior_inside=inside;
            uint32_t context[2]={(uint32_t)prior_inside,(uint32_t)locked};
            STATE_WORDS(restore_short_scene,37,context,2);
            inside=1;
            enter_zero();
            guest(cpu,0x8003674C,PLAYER,0);
            leave_zero();
            inside=prior_inside;
            if (p2.body[4]==3) mmx6_coop_teleport_done(&life);
            STATE_POP(restore_short_scene);
        }
        if (both_door_actor) {
            if((both_door_members&2) && life.status[1]==MMX6_COOP_ALIVE &&
               scene_locked(p2.body))locked=1;
            if((both_door_members&1) && life.status[0]==MMX6_COOP_ALIVE &&
               (psx_mod_read_byte(PLAYER+0xD0) || psx_mod_read_byte(PLAYER+0xD4) ||
                psx_mod_read_byte(PLAYER+0x7A)))locked=1;
        }
        if (!locked) { scene_owner=0;both_door_reset(); }
        return;
    }
    if (locked && scene_phase>=4 && !owner_dead) scene_phase=1;
    /* Wait for an actual grounded, controllable destination. Native door
     * and script locks, including chained boss dialogue, must all release. */
    int landing=!locked && owner[4]==1 && owner[5]>=2 &&
        !owner[0x67] && (owner[0x70]&8) && owner[0x5C];
    /* Death cannot supply a new grounded destination. Once the original
     * script releases, return the still-living passenger to its own retained
     * grounded body. Keep an incoming beam already in flight intact. */
    if (owner_dead && !locked && mmx6_coop_living(&life,passenger) &&
        scene_body[4]==1 && scene_body[0x5C] && scene_body[0x5C]<128 &&
        !scene_body[0x67] && (scene_body[0x70]&8)) {
        memcpy(owner,scene_body,sizeof owner);
        landing=1;
    }
    if (scene_phase==3 && !landing) return;
    int prior_inside=inside;
    inside=scene_call=1;
    uint8_t play[sizeof saved_play], camera[sizeof saved_camera];
    capture(PLAY,play,sizeof play);
    capture(0x800971F8,camera,sizeof camera);
    STATE_BYTES(restore_play,7,play,sizeof play);
    STATE_BYTES(restore_camera,8,camera,sizeof camera);
    STATE_BYTES(restore_owner,9,owner,sizeof owner);
    uint32_t scene_context[5]={seat,passenger,(uint32_t)locked,(uint32_t)landing,(uint32_t)prior_inside};
    STATE_WORDS(restore_context,28,scene_context,5);
    if (passenger) enter_zero();
    if (scene_phase==1 && passenger && arrival_pair && life.status[1]==MMX6_COOP_JOINING) {
        /* A native boss can claim X immediately after his checkpoint beam,
         * while Zero's original action0 is still incoming. returning_body
         * belongs only to voluntary Select departure/return; it is neither
         * initialized nor authoritative for this fresh native birth. Finish
         * the existing body-only arrival pipeline before withdrawing it. */
        if (!arrival_source()) failed=1;
        else {
            arrival_body_tick(cpu);
            uint8_t incoming[sizeof scene_body];capture(PLAYER,incoming,sizeof incoming);
            if (arrival_grounded(incoming)) {
                arrival_pair=0;
                mmx6_coop_teleport_done(&life);
            } else if (incoming[4]==2) {
                arrival_pair=0;
                mmx6_coop_fatal(&life,1);
                scene_phase=0; /* A native fatal body is no living passenger. */
            }
        }
        /* Keep phase1 for this pass, even on genuine native completion.
         * The next world pass captures that completed body as passenger. */
    } else if (scene_phase==1) {
        if (passenger && life.status[1]==MMX6_COOP_JOINING && join_phase) {
            uint32_t x=psx_mod_read_word(PLAYER+8);
            project(PLAYER,returning_body,sizeof returning_body);
            psx_mod_write_word(PLAYER+8,x);
            psx_mod_write_word(PLAYER+12,(uint32_t)join_y);
            life.status[1]=MMX6_COOP_ALIVE;
            join_phase=0;
        }
        capture(PLAYER,scene_body,sizeof scene_body);
        if (passenger) clear_p2_combat();
        /* Clear dynamic shots, including a cancelled saber, in the resident
         * context too. Fixed effects keep their native constructor metadata;
         * wiping it leaves the next dash with zero parents and palettes. */
        for (unsigned i=0;i<sizeof p2.shots;i+=4) psx_mod_write_word(0x800950A0+i,0);
        for(unsigned i=0;i<3;++i) {
            psx_mod_write_byte(0x800972F8u+i*0x60+3,0);
            psx_mod_write_byte(0x800972F8u+i*0x60+4,0);
            psx_mod_write_byte(0x800911A8u+i*0x50+3,0);
            psx_mod_write_byte(0x800911A8u+i*0x50+4,0);
        }
        guest(cpu,0x8003A980,PLAYER,0);
        guest(cpu,0x8003BA04,PLAYER,3);
        guest(cpu,0x8003B954,PLAYER,0);
        psx_mod_write_word(PLAYER+0x54,0);
        scene_phase=2;
    } else if (scene_phase==2) {
        guest(cpu,0x8003674C,PLAYER,0); /* Original outgoing beam animation. */
        if (psx_mod_read_byte(PLAYER+4)==3) scene_phase=3;
    } else if (scene_phase==3) {
        project(PLAYER,scene_body,sizeof scene_body);
        psx_mod_write_word(PLAYER+8,le32(owner+8));
        scene_y=(int32_t)le32(owner+12);
        int32_t top=(int16_t)psx_mod_read_half(0x80097206)-40;
        psx_mod_write_word(PLAYER+12,(uint32_t)(top*65536));
        psx_mod_write_word(PLAYER+0x18,le32(owner+8));
        psx_mod_write_word(PLAYER+0x1C,(uint32_t)(top*65536));
        psx_mod_write_byte(PLAYER+3,1);
        psx_mod_write_byte(PLAYER+4,1);
        psx_mod_write_byte(PLAYER+0x14,owner[0x14]);
        psx_mod_write_byte(PLAYER+0x15,owner[0x15]);
        guest(cpu,0x8003A980,PLAYER,0);
        guest(cpu,0x8003BA04,PLAYER,1);
        psx_mod_write_word(PLAYER+0x68,0);
        psx_mod_write_word(PLAYER+0x54,0);
        scene_phase=4;
    } else {
        guest(cpu,0x80017A04,PLAYER,0);
        if (scene_phase==4) {
            int32_t y=(int32_t)psx_mod_read_word(PLAYER+12)+8*65536;
            if (y>=scene_y) {
                y=scene_y;
                STATE_WORDS(restore_y,38,&y,1);
                guest(cpu,0x8003BA04,PLAYER,2);
                STATE_POP(restore_y);
                scene_phase=5;
            }
            psx_mod_write_word(PLAYER+12,(uint32_t)y);
        } else if (!psx_mod_read_byte(PLAYER+0x46)) {
            guest(cpu,0x8003AD18,PLAYER,0);
            guest(cpu,0x8003CCBC,PLAYER,0);
            (void)ride_resume_passenger(cpu,passenger,scene_body);
            psx_mod_write_byte(PLAYER+0x61,60);
            scene_owner=scene_phase=0;
            life.select_frames=0;
        }
    }
    if (passenger) leave_zero();
    project(PLAY,play,sizeof play);
    project(0x800971F8,camera,sizeof camera);
    STATE_POP(restore_context);STATE_POP(restore_owner);STATE_POP(restore_camera);STATE_POP(restore_play);
    inside=prior_inside;
    scene_call=0;
}
static void diagnostic_setup(CPUState *cpu) {
    unsigned command=psx_mod_read_byte(diagnostic+0x50);
    if (!command) return;
    if (!diagnostic_mutation_allowed()) {
        psx_mod_write_byte(diagnostic+0x50,0);
        psx_mod_counter_add("mmx6.coop.debug-fixture-rejected",1);
        return;
    }
    /* Commands8/9 may only commit at the outer stage entry, never from the
     * controller's projected/nested post-player boundary. */
    if (command==8 || command==9) return;
    if (command==10) {
        /* Bounded offline audit protection, not a permanent gameplay option.
         * Native8002D654 checks defender+61; positive1..127 expires through
         * original80039494. Unlike C4568 this does not bypass player actions.
         * Commit both seats atomically while neither body is projected. */
        if(inside || stage_call || zero_projected)return;
        unsigned ticks=psx_mod_read_byte(diagnostic+0x51),mask=psx_mod_read_byte(diagnostic+0x52);
        int valid=ready && enrolled && !failed && ticks && ticks<=127 && mask && mask<=3 &&
            !scene_owner && pause_owner<0 && psx_mod_read_byte(PLAY)==10 && !psx_mod_read_byte(PLAY+1);
        if(mask&1)valid=valid && life.status[0]==MMX6_COOP_ALIVE &&
            psx_mod_read_byte(PLAYER+4)==1 && psx_mod_read_byte(PLAYER+0x5C)>0 && psx_mod_read_byte(PLAYER+0x5C)<128;
        if(mask&2)valid=valid && life.status[1]==MMX6_COOP_ALIVE && p2.body[4]==1 && p2.body[0x5C]>0 && p2.body[0x5C]<128;
        if(valid) {
#ifdef MMX6_COOP_INPUT_TAINT_API
            psx_session_input_taint_add(PSX_INPUT_TAINT_GAME_MAILBOX);
#endif
            if(mask&1)psx_mod_write_byte(PLAYER+0x61,(uint8_t)ticks);
            if(mask&2)p2.body[0x61]=(uint8_t)ticks;
        } else psx_mod_counter_add("mmx6.coop.debug-protection-rejected",1);
        psx_mod_write_byte(diagnostic+0x50,0);return;
    }
    /* Development-only fixture setup. The published host-body copy remains
     * read-only; a one-byte command commits the already-written payload. */
#ifdef MMX6_COOP_INPUT_TAINT_API
    if(command>=1 && command<=7)psx_session_input_taint_add(PSX_INPUT_TAINT_GAME_MAILBOX);
#endif
    if (command==1) p2.body[0x5C]=psx_mod_read_byte(diagnostic+0x51);
    if (command==2) {
        uint16_t ammo=psx_mod_read_half(diagnostic+0x52);
        for (unsigned i=0xA8;i<0xBA;i+=2) {
            p2.body[i]=(uint8_t)ammo; p2.body[i+1]=(uint8_t)(ammo>>8);
        }
    }
    if (command==3) {
        /* Native dropped-item allocation for private ownership fixtures. */
        uint32_t actor=guest(cpu,0x8002BBF4,0,0);
        if (actor) {
            unsigned seat=psx_mod_read_byte(diagnostic+0x52)&1;
            psx_mod_write_byte(actor,0x21);
            unsigned kind=psx_mod_read_byte(diagnostic+0x51);
            psx_mod_write_byte(actor+1,kind==0xF0?0x0F:0x2F);
            psx_mod_write_byte(actor+2,kind==0xF0?0x31:kind);
            psx_mod_write_word(actor+8,seat?le32(p2.body+8):psx_mod_read_word(PLAYER+8));
            psx_mod_write_word(actor+12,seat?le32(p2.body+12):psx_mod_read_word(PLAYER+12));
        }
        psx_mod_write_word(diagnostic+0x68,actor);
    }
    if (command==4) {
        /* Atomic private placement, avoiding debug writes during projection. */
        unsigned seat=psx_mod_read_byte(diagnostic+0x52);
        uint32_t x=psx_mod_read_word(diagnostic+0x54), y=psx_mod_read_word(diagnostic+0x58);
        if (seat) {
            put32(p2.body+8,x); put32(p2.body+12,y);
            put32(p2.body+0x18,x); put32(p2.body+0x1C,y);
        }
        if (seat!=1) {
            psx_mod_write_word(PLAYER+8,x); psx_mod_write_word(PLAYER+12,y);
            psx_mod_write_word(PLAYER+0x18,x); psx_mod_write_word(PLAYER+0x1C,y);
        }
    }
    if (command==5 || command==6) {
        unsigned seat=command==5?(psx_mod_read_byte(diagnostic+0x52)&1):scene_owner==2;
        if (seat) enter_zero();
        guest(cpu,command==5?0x8003D308:0x8003D330,0x14,0x40);
        if (seat) leave_zero_context(1);
    }
    if (command==7) {
        /* Select a weapon for private native-HUD fixtures at the same safe
         * boundary as player placement; never write a projected body. */
        uint8_t weapon=psx_mod_read_byte(diagnostic+0x51);
        if (psx_mod_read_byte(diagnostic+0x52)&1) p2.body[0x93]=weapon;
        else psx_mod_write_byte(PLAYER+0x93,weapon);
    }
    if (command) psx_mod_write_byte(diagnostic+0x50,0);
}
static void route_p2_input(uint16_t raw) {
    psx_mod_write_half(0x800C456C,raw);
    psx_mod_write_half(0x800C456E,previous_input);
    psx_mod_write_half(0x800C4570,(uint16_t)(raw & ~previous_input));
    previous_input=raw;
}
static void menu_vram(CPUState *cpu, int zero) {
    if (zero==zero_menu_loaded) return;
    STATE_WORDS(restore_owner,39,&zero,1);
    /* These are the original PL00 menu/font upload pages, from native loader
     * table 8006E2EC (types 7/1), plus its 8006D9D4 menu palette rectangle.
     * Only one pause menu is visible, so preserve the exact resident X pages
     * on the host and exchange them after native DrawSync. Body rendering
     * continues to use retained banks. Block DMA is limited to guest RAM, so
     * submit the retained pixels through GP0's normal upload command. */
    /* The native stage loader also installs four 8bpp portrait strips and
     * one 256-color CLUT. These must follow the pause owner with the menu. */
    static const unsigned x[8]={896,960,256,384,448,512,576,0};
    static const unsigned y[8]={256,256,496,0,0,0,0,510};
    static const unsigned width[8]={64,64,64,64,64,64,64,256};
    static const unsigned height[8]={256,256,16,16,16,16,16,1};
    static const unsigned offset[8]={0,0x8000,0x10000,MENU_PORTRAIT,
        MENU_PORTRAIT+0x800,MENU_PORTRAIT+0x1000,MENU_PORTRAIT+0x1800,MENU_PORTRAIT_COLORS};
    guest(cpu,0x80066150,0,0);
    uint32_t resident_colors=psx_mod_read_word(SCRATCH+0x28)+0x3C00;
    if (zero) {
        uint8_t colors[0x200];
        capture(resident_colors,saved_portrait_colors,sizeof saved_portrait_colors);
        capture(menu_memory+MENU_PORTRAIT_COLORS,colors,sizeof colors);
        /* Native end-of-frame palette uploads use the resident X context. */
        project(resident_colors,colors,sizeof colors);
    } else project(resident_colors,saved_portrait_colors,sizeof saved_portrait_colors);
    for (unsigned i=0;i<8;++i) {
        uint32_t backup=menu_memory+MENU_BYTES+offset[i];
        if (zero) {
            const uint16_t *vram=gpu_get_vram();
            for (unsigned row=0;row<height[i];++row) for (unsigned col=0;col<width[i];++col)
                psx_mod_write_half(backup+2*(row*width[i]+col),vram[(y[i]+row)*1024+x[i]+col]);
        }
        uint32_t source=zero?menu_memory+offset[i]:backup;
        gpu_set_gp0_source(0);
        gpu_write_gp0(0xA0000000);
        gpu_write_gp0(x[i]|(y[i]<<16));
        gpu_write_gp0(width[i]|(height[i]<<16));
        for (unsigned p=0;p<width[i]*height[i]*2;p+=4)
            gpu_write_gp0(psx_mod_read_word(source+p));
    }
    /* Zero's native menu stage also services its player upload queue. That
     * queue targets the singleton player sheet at320,0 even though both
     * bodies draw from retained banks during the borrowed world pass. X's
     * frozen animation cache still considers its original sheet resident.
     * Preserve it on entry and restore it before ordinary X rendering resumes;
     * otherwise the first resumed X frame samples Zero's tile arrangement. */
    if (zero) {
        const uint16_t *vram=gpu_get_vram();
        for (unsigned row=0;row<256;++row) for (unsigned col=0;col<64;++col)
            psx_mod_write_half(menu_memory+MENU_PLAYER_BACKUP+2*(row*64+col),vram[row*1024+320+col]);
    } else {
        gpu_set_gp0_source(0);
        gpu_write_gp0(0xA0000000);gpu_write_gp0(320);gpu_write_gp0(64|(256u<<16));
        for (unsigned p=0;p<0x8000;p+=4)
            gpu_write_gp0(psx_mod_read_word(menu_memory+MENU_PLAYER_BACKUP+p));
    }
    zero_menu_loaded=zero;
    STATE_POP(restore_owner);
}
static int arrival_source(void) {
    return psx_mod_read_word(0x80073ACCu)==0x80035144u &&
        psx_mod_read_word(0x8003D850u)==0x27BDFFE8u &&
        psx_mod_read_word(0x8003D860u)==0x0C00EE81u &&
        psx_mod_read_word(0x8003D880u)==0xAE020024u &&
        psx_mod_read_word(0x8003D730u)==0x90C4005Eu &&
        psx_mod_read_word(0x8003D73Cu)==0xA0A400E7u &&
        psx_mod_read_word(0x800351B4u)==0x0C00EE81u &&
        psx_mod_read_word(0x8003525Cu)==0x0C00EB46u;
}
static int arrival_grounded(const uint8_t *body) {
    return (body[0]&1) && body[3] && body[4]==1 && body[5]==2 &&
        body[0x5C] && body[0x5C]<128 &&
        !body[0x67] && (body[0x70]&8) && !(le32(body+12)&65535u) &&
        body[2]<=1 && le32(body+0x68)==(body[2]?0x80073D54u:0x80073D50u);
}
static int arrival_spaced(const uint8_t *a,const uint8_t *b) {
    uint32_t ab=le32(a+0x68),bb=le32(b+0x68);
    int ac=(int16_t)(le32(a+8)>>16)+(int8_t)psx_mod_read_byte(ab);
    int bc=(int16_t)(le32(b+8)>>16)+(int8_t)psx_mod_read_byte(bb);
    int distance=ac>bc?ac-bc:bc-ac;
    return distance>=(int)(psx_mod_read_byte(ab+2)+psx_mod_read_byte(bb+2));
}
static int paired_arrival(CPUState *cpu) {
    /* Action0 is the original incoming beam, not a door/script/voluntary
     * return. Native 3D718 assigns body E7 from PLAY5E only at landing;
     * while that field is uninitialized, resolve this exact native campaign
     * selection without pretending the completed-body guard has run. */
    if (psx_mod_read_byte(PLAY+1) || scene_owner || clear_phase || pause_owner>=0 || zero_menu_loaded ||
        psx_mod_read_byte(PLAY+0x0F) || psx_mod_read_byte(PLAY+0x10) ||
        psx_mod_read_byte(0x8008EAFCu) || psx_mod_read_byte(PLAYER+0xD0) ||
        psx_mod_read_byte(PLAYER+0xD4) || psx_mod_read_byte(PLAYER+0xD5) ||
        psx_mod_read_byte(PLAYER+0xE0)) return arrival_pair!=0;
    if (!arrival_pair) {
        /* Intro CP0 has automatic HELP0 at native144/976. Original 52F64
         * admits its volume before action2, queues script20 at5318C, then
         * publishes seen bit PLAY9E. Do not arm on the earlier beam frame
         * before D0 exists: the ensuing dialogue still needs native input.
         * The original post-idle enrollment remains responsible for it. */
        if (!psx_mod_read_byte(PLAY+12) && !psx_mod_read_byte(PLAY+13) &&
            !psx_mod_read_byte(PLAY+0x1D) && !(psx_mod_read_half(PLAY+0x9E)&1u)) return 0;
        if (enrolled || psx_mod_read_byte(PLAYER+2)>1 || psx_mod_read_byte(PLAYER+4)!=1 ||
            !psx_mod_read_byte(PLAYER+0x5C) || psx_mod_read_byte(PLAYER+0x5C)>=128 ||
            psx_mod_read_byte(PLAYER+5) || psx_mod_read_byte(PLAYER+6) ||
            psx_mod_read_byte(PLAYER+0x67)!=255 ||
            psx_mod_read_word(PLAYER+0x24)!=0xFFF80000u || !arrival_source()) return 0;
        Mmx6CoopRoster roster;
        Mmx6CoopRosterNative native={psx_mod_read_byte(PLAYER+2),psx_mod_read_byte(PLAY+0x5E),
            psx_mod_read_byte(PLAY+0x38),psx_mod_read_byte(PLAY+0x5E),psx_mod_read_byte(PLAY+0x5F)};
        if (mmx6_coop_roster_resolve_partner(&native,partner_x_armor,psx_mod_read_byte(PLAY+0x69),&roster)!=MMX6_COOP_ROSTER_OK ||
            mmx6_coop_resources_fixed_runtime_admit(&roster)!=MMX6_COOP_RESOURCES_OK) return 0;
        inside=1;
        ready=load_assets(&roster);
        if (!ready) failed=1;
        if (!failed) enroll(cpu,&roster,1);
        inside=0;
        if (failed) return 1;
    }
    if (psx_mod_read_byte(PLAYER+4)!=1 || p2.body[4]!=1) {
        arrival_pair=0;
        if (p2.body[4]==1) mmx6_coop_teleport_done(&life);
        else if (p2.body[4]==2) mmx6_coop_fatal(&life,1);
        return 0; /* Native body action0 still owns a living survivor's beam. */
    }
    inside=1;
    /* Only this owned actor runs again. enter/leave restores X, all world
     * flags/clocks and the canonical camera, including native PLAY1C clears. */
    enter_zero();
    arrival_body_tick(cpu);
    leave_zero();
    uint8_t primary[0x158];capture(PLAYER,primary,sizeof primary);
    if (arrival_grounded(primary) && arrival_grounded(p2.body) &&
        arrival_spaced(primary,p2.body)) {
        arrival_pair=0;
        mmx6_coop_teleport_done(&life);
    }
    if (p2.body[4]==2) { arrival_pair=0;mmx6_coop_fatal(&life,1); }
    if (!stage_call) diagnostics(0);
    inside=0;
    return 1;
}
static int player_tick(CPUState *cpu, uint32_t address) {
    if ((inside && !zero_world) || player_call || !enrolled || failed) return 0;
    unsigned seat=zero_world?1u:0u;
    /* A survivor's original beam belongs to scene_tick, even after its dead
     * owner stops hosting the native world. Do not run ordinary movement or
     * contact on that same body before the beam completes. */
    unsigned hp=psx_mod_read_byte(PLAYER+0x5C);
    if(scene_passenger(seat) && mmx6_coop_living(&life,seat) && hp && hp<128) {
        cpu->gpr[2]=0;
        return 1;
    }
    /* 8003CD44 has decoded this frame's pad before this native update.
     * Withhold its held/edge words until BOTH original arrivals finish. The
     * native body/terrain/animation pass still runs, including fatal paths. */
    if (arrival_pair) for (unsigned i=0;i<8;i+=2)
        psx_mod_write_half(PLAYER+0x7C+i,0);
    uint8_t freeze[11];
    capture(PLAY+0x12,freeze,sizeof freeze);
    STATE_BYTES(restore_freeze,10,freeze,sizeof freeze);
    player_call=1;
    uint32_t result=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    player_call=0;
    if (psx_mod_read_byte(PLAYER+4)==2 || life.status[seat]==MMX6_COOP_DYING) {
        mmx6_coop_fatal(&life,seat);
        if (mmx6_coop_living(&life,seat^1u)) project(PLAY+0x12,freeze,sizeof freeze);
        if (psx_mod_read_byte(PLAYER+4)==3) life.status[seat]=MMX6_COOP_FALLEN;
    }
    STATE_POP(restore_freeze);
    cpu->gpr[2]=result;
    return 1;
}
static void diagnostic_inventory_setup(CPUState *cpu) {
    if (psx_mod_read_byte(diagnostic+0x50)!=9) return;
    /* An offline prerequisite bypass for native resource tests. Neither
     * selection nor current HP/ammo is changed: subsequent native input must
     * spend energy, and actual state load/rewind must restore it. */
    unsigned mask=psx_mod_read_byte(diagnostic+0x51);
    if (!diagnostic_mutation_allowed() || !mask || scene_owner || zero_projected ||
        psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
        psx_mod_read_byte(PLAY+12) || psx_mod_read_byte(PLAY+13) ||
        psx_mod_read_byte(PLAY+0x38) || psx_mod_read_byte(PLAY+0x5E)!=1 ||
        life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_ALIVE ||
        psx_mod_read_byte(PLAYER+2) || p2.body[2]!=1 ||
        psx_mod_read_byte(PLAYER+0xE7)!=1 || p2.body[0xE7]!=5 ||
        psx_mod_read_byte(PLAYER+4)!=1 || p2.body[4]!=1 ||
        psx_mod_read_byte(PLAYER+5)!=2 || p2.body[5]!=2 ||
        !checkpoint_equipment_source()) {
        psx_mod_write_byte(diagnostic+0x50,0);
        psx_mod_counter_add("mmx6.coop.debug-inventory-rejected",1);
        return;
    }
#ifdef MMX6_COOP_INPUT_TAINT_API
    psx_session_input_taint_add(PSX_INPUT_TAINT_GAME_MAILBOX);
#endif
    checkpoint_equipment_native(cpu,mask);
    psx_mod_write_byte(diagnostic+0x50,0);
    psx_mod_counter_add("mmx6.coop.debug-inventory-grant",1);
}
static int stage_tick(CPUState *cpu, uint32_t address) {
    if (stage_call || inside) return 0;
    if (checkpoint_stage_boundary(cpu)) return 1;
    if (!enrolled || failed) return 0;
    diagnostic_inventory_setup(cpu);
    diagnostic_setup(cpu);
    uint16_t raw=p2_input(MMX6_INPUT_STAGE);
    if(checkpoint_lab_boundary(cpu,raw))return 1;
    /* Native 1EAE0 checks the resident body for phase3 before updating it.
     * Prime a withdrawn living survivor through the existing incoming path
     * first, after ALL safe-boundary script releases, in either seat. A
     * predeclared LAB call can release after diagnostic_setup; checking
     * before that call exposes withdrawn state3 to the original retry gate. */
    if(!psx_mod_read_byte(PLAY+1) && scene_owner_fatal() &&
       !scene_shared_locked() && scene_phase==3) scene_tick(cpu);
    int start=!!(raw&8), pressed=start&&!p2_start_previous;
    unsigned phase=psx_mod_read_byte(PLAY+1);
    p2_start_previous=start;
    uint32_t stage_context[4]={raw,phase,0,0};
    STATE_WORDS(restore_stage,29,stage_context,4);
    /* Menus can bypass controller entirely. Consume their Select samples so
     * a held UI press cannot become a new rejoin edge on gameplay resume. */
    if (phase || scene_owner || psx_mod_read_byte(PLAY+0x10) || psx_mod_read_byte(PLAY+0x1C))
        (void)mmx6_coop_join_input(&life,raw&1,0,0);
    if (!phase) {
        pause_owner=-1;
        /* Match the native pause gate. Simultaneous requests go to P1; an
         * absent/dead/departing actor cannot become the menu's owner. */
        if (!arrival_pair && !scene_owner && !clear_phase && !psx_mod_read_byte(PLAY+0x1C) && !psx_mod_read_byte(PLAY+0x10) &&
            !psx_mod_read_byte(PLAY+0x0F) && !psx_mod_read_byte(0x80097424)) {
            if (life.status[0]==MMX6_COOP_ALIVE && (psx_mod_read_half(0x800C4570)&0x0800))
                pause_owner=0;
            else if (life.status[1]==MMX6_COOP_ALIVE && pressed) pause_owner=1;
        }
    } else if (phase==2) {
        life.select_frames=0;
        if (pause_owner<0) pause_owner=mmx6_coop_living(&life,0)?0:1;
    }
    independent_menu_begin();
    int survivor=(!life.wipe || life.wipe==2) &&
        (life.status[0]==MMX6_COOP_DYING || life.status[0]==MMX6_COOP_FALLEN) &&
        life.status[1]!=MMX6_COOP_ABSENT && (life.wipe || life.status[1]!=MMX6_COOP_FALLEN);
    stage_context[3]=(uint32_t)survivor;STATE_UPDATE(restore_stage,stage_context);
    /* A dead Zero no longer hosts the world after the shared script releases.
     * Finish his original body-only death once; controller intentionally
     * withholds its ordinary private player update while a scene is active. */
    if(!phase && scene_owner==2 && scene_owner_fatal() && !scene_shared_locked() && p2.body[4]==2) {
        inside=1;enter_zero();guest(cpu,0x80034DCC,0,0);leave_zero();inside=0;
        if(p2.body[4]==3) life.status[1]=MMX6_COOP_FALLEN;
    }
    if (!survivor && pause_owner!=1 &&
        (scene_owner!=2 || (scene_owner_fatal() && !scene_shared_locked())) && !shared_clear_zero_world()) {
        uint8_t arrival_input[6];unsigned restore_arrival_input=UINT32_MAX;
        if (arrival_pair) {
            capture(0x800C456C,arrival_input,sizeof arrival_input);
            restore_arrival_input=mmx6_state_push(53,arrival_input,sizeof arrival_input,0);
            /* Pause/interaction also read native pads outside the decoder.
             * Neutralize this guest pass, retaining accepted SDK input and
             * restoring the original pad publication after the world pass. */
            for (unsigned i=0;i<6;i+=2) psx_mod_write_half(0x800C456C+i,0);
        }
        stage_call=1;
        uint32_t result=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
        if (restore_arrival_input!=UINT32_MAX) {
            project(0x800C456C,arrival_input,sizeof arrival_input);
            mmx6_state_pop(restore_arrival_input);
        }
        stage_context[2]=result;STATE_UPDATE(restore_stage,stage_context);
        if (!psx_mod_read_byte(PLAY+1)) scene_tick(cpu);
        shared_clear_tick(cpu,0);
        diagnostics((uint16_t)((raw<<8)|(raw>>8)));
        if (psx_mod_read_byte(PLAY)!=0x0A) enrolled=arrival_pair=0;
        cpu->gpr[2]=result;
        stage_call=0;
        STATE_POP(restore_stage);
        return 1;
    }
    stage_call=inside=1;
    if (pause_owner==1 && !zero_menu_loaded) menu_vram(cpu,1);
    if (survivor && !life.wipe) retain_surviving_zero(cpu);
    /* Finish X's native death pose/orbs without spending a life, freezing
     * enemies, or advancing the shared clock a second time. */
    if (!phase && psx_mod_read_byte(PLAYER+4)==2 && mmx6_coop_living(&life,1)) {
        uint8_t flags[11];
        uint32_t timer=psx_mod_read_word(PLAY+0x90), total=psx_mod_read_word(PLAY+0xCC);
        capture(PLAY+0x12,flags,sizeof flags);
        uint32_t clocks[2]={timer,total};
        STATE_BYTES(restore_flags,11,flags,sizeof flags);
        STATE_WORDS(restore_clocks,12,clocks,2);
        guest(cpu,0x80034DCC,0,0);
        project(PLAY+0x12,flags,sizeof flags);
        psx_mod_write_word(PLAY+0x90,timer);
        psx_mod_write_word(PLAY+0xCC,total);
        STATE_POP(restore_clocks);STATE_POP(restore_flags);
        if (psx_mod_read_byte(PLAYER+4)==3) life.status[0]=MMX6_COOP_FALLEN;
    }
    uint8_t input[6];
    capture(0x800C456C,input,sizeof input);
    STATE_BYTES(restore_input,13,input,sizeof input);
    /* Native Select enters campaign Quit, which belongs to P1. Consume the
     * actual UI sample in the join-history gate above, but withhold Select
     * from P2's owned pause. Gameplay departure/rejoin and P1 input retain
     * their native controls. Other personal-menu buttons still pass through. */
    if (pause_owner==1 && phase==2) raw=(uint16_t)(raw&~1u);
    raw=(uint16_t)((raw<<8)|(raw>>8));
    stage_context[0]=raw;STATE_UPDATE(restore_stage,stage_context);
    enter_zero();
    route_p2_input(raw);
    zero_world=1;
    uint32_t result=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    stage_context[2]=result;STATE_UPDATE(restore_stage,stage_context);
    if (psx_mod_read_byte(PLAYER+4)==2) mmx6_coop_fatal(&life,1);
    if (life.status[1]==MMX6_COOP_DYING && psx_mod_read_byte(PLAYER+4)==3)
        life.status[1]=MMX6_COOP_FALLEN;
    zero_world=0;
    leave_zero_context(1);
    project(0x800C456C,input,sizeof input);
    STATE_POP(restore_input);
    if (!psx_mod_read_byte(PLAY+1)) scene_tick(cpu);
    shared_clear_tick(cpu,1);
    diagnostics(raw);
    if (zero_menu_loaded && psx_mod_read_byte(PLAY+1)!=2) menu_vram(cpu,0);
    if (psx_mod_read_byte(PLAY)!=0x0A) enrolled=arrival_pair=0;
    cpu->gpr[2]=result;
    stage_call=inside=0;
    STATE_POP(restore_stage);
    return 1;
}
/* Original screen/task replacement closes its program thread and ChangeThread
 * abandons the stage_tick/guest C stack. The scheduler retires framework context, but
 * these title-owned guards/copies survive. Admit only the original root's
 * major9 caller after that escape; never replay old copies into the new game.
 * Source/caller proof: docs/COOP_NATIVE_PLAYER_INIT_CALLER_AUDIT.md. */
static uint32_t retired_host_word(const Mmx6StateFrame *frame,size_t index) {
    uint32_t value;
    /* STATE_WORDS retains native host words, unlike guest RAM byte copies. */
    memcpy(&value,frame->saved+index*sizeof value,sizeof value);
    return value;
}
static int retire_quit_stage(CPUState *cpu,uint32_t address) {
    if (!cpu || address!=0x8003BD24u || inside || player_call || zero_world || zero_projected ||
        world_render || hud_call || render_x_death || effect_call || shared_fx_call || shared_fx_allocate_call || pickup_call || solid_call ||
        solid_allocate_call || ride_call || view_call || private_draw || scene_call || unit_choices_call || target_projection_call ||
        stage_call!=1 || state_track.count!=2 || state_track.error ||
        psx_mod_read_byte(PLAY)!=9 || psx_mod_read_byte(PLAY+1) ||
        cpu->gpr[31]!=0x8001E26Cu || cpu->gpr[16]!=PLAY) return 0;
    uint32_t sp=cpu->gpr[29];
    if ((sp&3u) || sp<0x80010000u || sp>0x801FFFE8u ||
        psx_mod_read_word(sp+0x14u)!=0x8001E720u) return 0;
    const Mmx6StateFrame *stage=&state_track.frame[0],*call=&state_track.frame[1];
    if (stage->tag!=29 || stage->bytes!=16 || stage->words!=1 ||
        retired_host_word(stage,1)>2 || retired_host_word(stage,3)!=0 ||
        call->tag!=1 || call->bytes!=102u*4u || call->words!=1 ||
        retired_host_word(call,99)!=0x8001E9ECu ||
        retired_host_word(call,100)!=PLAY ||
        retired_host_word(call,31)!=0x8001E720u) return 0;
    stage_call=0;
    state_track.count=0;
    fprintf(stdout,"mmx6 co-op: retired stage callback at original fresh initialization\n");
    return 1;
}
static void native_player_init(CPUState *cpu, uint32_t address) {
    if (inside) return;
    intro_camera_valid=0;memset(intro_camera_requests,0,sizeof intro_camera_requests);
    int retired=retire_quit_stage(cpu,address);
    /* Frontend initialization (including a new native Load/New Game) retires
     * the runtime-only second bank. Ordinary major9 checkpoint births keep it.
     * Seeding is delayed until the loaded campaign actually enters co-op. */
    if(retired || (psx_mod_read_byte(PLAY)!=9 && psx_mod_read_byte(PLAY)!=10)) {
        subtank_seeded=subtank_found=0;memset(zero_subtanks,0,sizeof zero_subtanks);
    }
    /* This is the native fresh-stage/checkpoint-respawn initialization, never
     * an ordinary door. An ordinary native beam may enroll both arrivals. */
    enrolled=0;
    arrival_pair=0;
    scene_owner=scene_phase=0;
    both_door_reset();
    shared_clear_reset();
    memset(pickup_owners,0,sizeof pickup_owners);
    memset(zero_solid_contacts,0,sizeof zero_solid_contacts);
    memset(shared_effect_owners,0,sizeof shared_effect_owners);
    mmx6_coop_lifecycle_checkpoint(&life);
    pause_owner=-1; p2_start_previous=0;
    ride_call=0;
}
static void controller(CPUState *cpu, uint32_t address) {
    (void)address;
    if (inside || failed) return;
    /* Only the normal gameplay driver's post-player boundary. */
    if (cpu->gpr[31]!=0x80020C70u) return;
    if (scene_owner || clear_phase) {
        (void)mmx6_coop_join_input(&life,p2_input(MMX6_INPUT_CONTROLLER_SCENE)&1,0,0);
        if (!both_door_traversal_active()) return;
    }
    if (psx_mod_read_byte(PLAY)!=0x0A || !psx_mod_read_byte(PLAYER)) {
        (void)mmx6_coop_join_input(&life,p2_input(MMX6_INPUT_CONTROLLER_INACTIVE)&1,0,0);
        enrolled=0; arrival_pair=0; return;
    }
    if (paired_arrival(cpu)) return;
    if (psx_mod_read_byte(PLAY+1) || (psx_mod_read_byte(PLAYER+4)!=2 &&
         (psx_mod_read_byte(PLAYER+4)!=1 || psx_mod_read_byte(PLAYER+5)<2)) ||
        (psx_mod_read_byte(PLAY+0x10) && !both_door_traversal_active()) ||
        (coop_world_hold() && !both_door_traversal_active())) {
        (void)mmx6_coop_join_input(&life,p2_input(MMX6_INPUT_CONTROLLER_BLOCKED)&1,0,0);
        return;
    }
    /* The opening's scripted jump/dialogue also uses action >= 2. Wait for
     * the native idle handoff before first enrollment, including restarts. */
    if (!enrolled && (psx_mod_read_byte(PLAYER+4)!=1 || psx_mod_read_byte(PLAYER+5)!=2)) return;
    inside=1;
    if (!ready || !enrolled) {
        Mmx6CoopRoster roster;
        /* The original idle handoff has completed body/parts initialization.
         * Recheck even when immutable Zero assets survived a native respawn. */
        if (!fixed_roster(&roster)) { failed=1;inside=0;return; }
        {
            ready=load_assets(&roster);
            if (!ready) { failed=1; fprintf(stderr,"mmx6 co-op: resource validation failed\n"); }
        }
        if (ready && !enrolled) enroll(cpu,&roster,0);
    }
    if (ready && enrolled) {
        constrain_player(0);
        uint16_t raw=p2_input(MMX6_INPUT_CONTROLLER_PLAYER);
        uint32_t input_context=raw;STATE_WORDS(restore_raw,42,&input_context,1);
        uint8_t saved_input[6];
        if (!stage_call) diagnostic_setup(cpu);
        int safe=safe_join_landing();
        Mmx6CoopJoinAction action=scene_owner?MMX6_COOP_NO_ACTION:
            mmx6_coop_join_input(&life,raw&1,1,safe);
        if (action==MMX6_COOP_LEAVE) start_leave(cpu);
        else if (action==MMX6_COOP_JOIN) start_join(cpu);
        raw=(uint16_t)((raw<<8)|(raw>>8)); /* Native PadRead byte order. */
        input_context=raw;STATE_UPDATE(restore_raw,&input_context);
        if (life.status[1]==MMX6_COOP_JOINING) {
            join_animation(cpu);
            if (!stage_call) diagnostics(raw);
            STATE_POP(restore_raw);
            inside=0; return;
        }
        if (life.status[1]==MMX6_COOP_ABSENT || life.status[1]==MMX6_COOP_FALLEN) {
            if (!stage_call) diagnostics(raw);
            STATE_POP(restore_raw);
            inside=0; return;
        }
        capture(0x800C456C,saved_input,sizeof saved_input);
        STATE_BYTES(restore_input,14,saved_input,sizeof saved_input);
        enter_zero();
        psx_mod_write_half(0x800C456C,life.status[1]==MMX6_COOP_LEAVING?0:raw);
        psx_mod_write_half(0x800C456E,previous_input);
        psx_mod_write_half(0x800C4570,(uint16_t)(raw & ~previous_input));
        p2_edges=(uint16_t)(raw & ~previous_input);
        previous_input=raw;
        guest(cpu,0x8003CD44,0,0);
        guest(cpu,0x80034DCC,0,0);
        guest(cpu,0x8002012C,0,0); /* This player's attack pool, never enemies/world. */
        guest(cpu,0x8002F288,PLAYER,0); /* Native terrain/platform contact. */
        /* Original 80020C40 orders these fixed actor-owned pools after
         * contact. They read the resident PLAYER and trail parent links;
         * keep both calls inside the one private projection. The native
         * survivor/menu world pass already owns them when inside is set. */
        guest(cpu,0x80020D74,0,0);
        guest(cpu,0x80020DC8,0,0);
        leave_zero();
        if (life.status[1]==MMX6_COOP_LEAVING && p2.body[4]==3)
            mmx6_coop_teleport_done(&life);
        if (p2.body[4]==2) mmx6_coop_fatal(&life,1);
        if (life.status[1]==MMX6_COOP_DYING && p2.body[4]==3) life.status[1]=MMX6_COOP_FALLEN;
        constrain_player(1);
        project(0x800C456C,saved_input,sizeof saved_input);
        STATE_POP(restore_input);
        if (!stage_call) diagnostics(raw);
        STATE_POP(restore_raw);
    }
    inside=0;
}

static uint16_t retain_sprite_bank(uint32_t source,uint16_t tile,const uint8_t colors[32],
                                   const uint16_t *pixels) {
    uint32_t count=tile==UINT16_MAX?65536u:256u;
    uint32_t bytes=mmx6_pixels_size(pixels,count);
    uint8_t *encoded=bytes?malloc(bytes):NULL;
    if (!encoded || !mmx6_pixels_encode(encoded,bytes,pixels,count)) {free(encoded);return 0;}
    /* A guest compression address can be reused by another stage or form.
     * Compare actual decoded content, not source/palette keys or trailing RAM. */
    for (unsigned i=0;i<bank_count;++i) {
        SpriteBank *b=&banks[i];
        if ((b->tile==UINT16_MAX)==(tile==UINT16_MAX) && b->pixel_bytes==bytes &&
            b->pixels && !memcmp(b->pixels,encoded,bytes)) {
            b->source=source;b->tile=tile;b->character=(uint8_t)(render_x_death?2u:private_actor.character);
            memcpy(b->colors,colors,32);free(encoded);return b->id;}
    }
    if (bank_count==4096) {free(encoded);return 0;}
    uint16_t id=(uint16_t)(0x6000+bank_count);
    unsigned width=count==65536?256:16;
    if (!psx_mod_define_texture_bank(id,width,width,pixels)) {free(encoded);return 0;}
    SpriteBank *b=&banks[bank_count++];
    b->source=source;b->id=id;b->tile=tile;b->pixel_bytes=bytes;b->pixels=encoded;
    b->character=(uint8_t)(render_x_death?2u:private_actor.character);
    memcpy(b->colors,colors,32);
    return id;
}
/* Original Zero801EA254/EXE80043638 resolves graphics header+10h.
 * Its23 frames share one32-tile source;80043724's final untaken ordinary
 * BNE still executes delay80043728(a0=s1), then80043778 uploads it at
 * VRAM(0140h words,0040h). Page5 starts at0140h, so native UV origin is
 * (0,64), not the body/trail origin(0,0). Admit the immutable resource and
 * geometry, never actor position, current palette or screenshot contents. */
static uint32_t zero_yammar_upload_table(void) {
    if (!zero_compressed || compressed_size<0x14u) return 0;
    uint32_t relative=le32(zero_compressed+0x10);
    if (relative<0x14u || relative>=compressed_size ||
        compressed_size-relative<23u*4u+2u ||
        (uint64_t)assets+relative+0x5Cu>UINT32_MAX) return 0;
    for (unsigned i=0;i<23;++i)
        if (le32(zero_compressed+relative+i*4u)!=0x0200005Cu) return 0;
    return assets+relative;
}
/* Original X801F226C resolves graphics header+24h for Ray Arrow. Native
 *8004AF94's subtype0Ch uploads that same table at VRAM(0140h words,0020h)
 * through8004B1AC/80017B04. Page5 starts at0140h: atlas origin(0,32).
 * Its26 frames alias one32-tile stream; retain only this checked geometry. */
static uint32_t x_ray_upload_table(void) {
    if (private_actor.character!=MMX6_COOP_CHARACTER_X ||
        !zero_compressed || compressed_size<0x28u) return 0;
    uint32_t relative=le32(zero_compressed+0x24);
    if (relative<0x28u || relative>=compressed_size ||
        compressed_size-relative<26u*4u+2u ||
        (uint64_t)assets+relative+0x68u>UINT32_MAX) return 0;
    for (unsigned i=0;i<26;++i)
        if (le32(zero_compressed+relative+i*4u)!=0x02000068u) return 0;
    return assets+relative;
}
/* Original Shadow801ED524 resolves graphics header8 for native type45.
 * Deferred4AF94/subtype5 selects the same table at4B084..4B098, then
 *4B1AC/17B04 uploads it at VRAM(0140h words,0020h). DAT88's18 frames
 * alias one16-tile stream; native page0520 therefore samples UV row32. */
static uint32_t x_shadow_upload_table(void) {
    if(private_actor.character!=MMX6_COOP_CHARACTER_X ||
       private_actor.form!=MMX6_COOP_FORM_SHADOW ||
       !zero_compressed || compressed_size<0x0Cu)return 0;
    uint32_t relative=le32(zero_compressed+8);
    if(relative<0x0Cu || relative>=compressed_size ||
       compressed_size-relative<18u*4u+2u ||
       (uint64_t)assets+relative+0x48u>UINT32_MAX)return 0;
    for(unsigned i=0;i<18;++i)
        if(le32(zero_compressed+relative+i*4u)!=0x01000048u)return 0;
    return assets+relative;
}
static int working_palette_clut_offset(uint16_t clut,size_t *offset) {
    /* Native17C40 uploads rectangle8006E360=(0,480,256,32), not a full
     *1024-word VRAM row. CLUT7849 is144,481, hence working byte320;
     * subtracting7800 incorrectly reads byte920, three rows too far. */
    unsigned x=(clut&63u)*16u,y=clut>>6;
    if(y<480u || y>=512u || x+16u>256u)return 0;
    *offset=((size_t)(y-480u)*256u+x)*2u;
    return 1;
}
static uint16_t sprite_bank(uint32_t table, unsigned frame, uint16_t clut, uint16_t tile) {
    uint32_t offset, packed, source;
    uint8_t decoded[32768];
    uint16_t pixels[256*256];
    size_t written, palette_offset;
    unsigned tiles;
    uint8_t colors[32];
    const uint8_t *compressed;
    size_t available;
    uint8_t x_compressed[65536];
    if (!working_palette_clut_offset(clut,&palette_offset)) return 0;
    if (render_x_death) {
        if (table<0x80010000 || table+frame*4>=0x80200000) return 0;
        packed=psx_mod_read_word(table+frame*4);
        source=table+(packed&0xFFFFF);
        if (source>=0x80200000) return 0;
        available=0x80200000u-source;
        if (available>sizeof x_compressed) available=sizeof x_compressed;
        compressed=x_compressed;
    } else {
        if (table<assets || table-assets>=compressed_size ||
            (size_t)frame*4+4>compressed_size-(table-assets)) return 0;
        offset=table-assets;
        packed=le32(zero_compressed+offset+frame*4);
        source=table+(packed&0xFFFFF);
        if (source-assets>=compressed_size) return 0;
        compressed=zero_compressed+(source-assets);
        available=compressed_size-(source-assets);
    }
    tiles=packed>>20;
    if (!tiles || tiles>256 ||
        palette_offset+32>0x4000) return 0;
    uint32_t yammar=render_x_death || private_actor.character!=MMX6_COOP_CHARACTER_ZERO?
        0:zero_yammar_upload_table();
    uint32_t ray=render_x_death?0:x_ray_upload_table();
    uint32_t shadow=render_x_death?0:x_shadow_upload_table();
    unsigned upload_y=0;
    if (yammar && table==yammar) {
        if (frame>=23 || packed!=0x0200005Cu) return 0;
        upload_y=64;
    }
    if (ray && table==ray) {
        if (frame>=26 || packed!=0x02000068u) return 0;
        upload_y=32;
    }
    if(shadow && table==shadow) {
        if(frame>=18 || packed!=0x01000048u)return 0;
        upload_y=32;
    }
    unsigned upload_height=((tiles+15u)/16u)*16u;
    if (upload_y>256u-upload_height) return 0;
    capture((render_x_death?saved_resources[3]:active_palette)+(uint32_t)palette_offset,colors,sizeof colors);
    /* Zero's archive is immutable; native upload origins can differ by
     * table. Resident X death additionally uses replaceable native RAM. */
    /* Different tables can reference the same compressed source with
     * different native upload origins. For this source, decode and let the
     * existing exact-pixel cache distinguish both aliases without new keys. */
    if (!render_x_death && !(yammar && source==yammar+0x5Cu) &&
        !(ray && source==ray+0x68u) && !(shadow && source==shadow+0x48u))
        for (unsigned i=0;i<bank_count;++i)
        if (banks[i].character==private_actor.character && banks[i].source==source && banks[i].tile==tile &&
            !memcmp(banks[i].colors,colors,sizeof colors)) return banks[i].id;
    if (render_x_death) capture(source,x_compressed,available);
    if (!mmx6_coop_decode_sprite(compressed,
            available,decoded,sizeof decoded,&written) || written!=(size_t)tiles*128)
        return 0;
    memset(pixels,0,sizeof pixels);
    /* The native upload emits full 256-pixel rows, then a partial 16-high row. */
    unsigned remaining=tiles, row=upload_y, in=0;
    while (remaining) {
        unsigned chunk=remaining<16?remaining:16, width=chunk*16;
        for (unsigned y=0;y<16;++y) for (unsigned x=0;x<width;++x) {
            unsigned byte=decoded[in+(y*width+x)/2];
            unsigned index=(byte>>((x&1)*4))&15;
            const uint8_t *p=colors+index*2;
            pixels[(row+y)*256+x]=(uint16_t)(p[0]|p[1]<<8);
        }
        in+=chunk*128; row+=16; remaining-=chunk;
    }
    if (tile!=UINT16_MAX) {
        uint16_t tile_pixels[16*16];
        for (unsigned y=0;y<16;++y) for (unsigned x=0;x<16;++x)
            tile_pixels[y*16+x]=pixels[(((tile>>8)+y)&255)*256+(((tile&255)+x)&255)];
        return retain_sprite_bank(source,tile,colors,tile_pixels);
    }
    return retain_sprite_bank(source,tile,colors,pixels);
}
static int zero_ui_effect(uint32_t actor) {
    int slot=shared_effect_slot(actor);
    /* Native8004AE78..AEAC resolves the UI table's first relative offset;
     * actor+3C holds that assembly, not the table base at SCRATCH+3C. */
    uint32_t offset=menu_assembly?psx_mod_read_word(menu_assembly):ASSET_SPACE;
    return slot>=0 && shared_effect_owners[slot]==2 && psx_mod_read_byte(actor) &&
        psx_mod_read_byte(actor+1)==17 && offset<ASSET_SPACE &&
        psx_mod_read_word(actor+0x3C)==menu_assembly+offset;
}
static int zero_icon_effect(uint32_t actor) {
    int slot=shared_effect_slot(actor);
    /* Original Zero801EE2DC..E304 resolves decimal offset60 in its sprite
     * assembly table. Native packed shapes add their own page to actor+40:
     * page0 there still samples the character's different icon atlas.
     * 801EAA24 also allocates personal type44 shots through8002C32C. Their
     * ownership follows the projected PlayerContext, unlike shared type26.
     * Admit those only while drawing Zero, including her survivor world. */
    unsigned type=psx_mod_read_byte(actor+1);
    int owned=slot>=0?shared_effect_owners[slot]==2 && type==26:
        actor>=0x800950A0u && actor<0x800964A0u &&
        !((actor-0x800950A0u)%0xA0u) && type==44 && !render_x_death &&
        psx_mod_read_byte(PLAYER+2)==1;
    uint32_t offset=assembly?psx_mod_read_word(assembly+0x3C):ASSET_SPACE;
    return owned && psx_mod_read_byte(actor) && offset<ASSET_SPACE &&
        psx_mod_read_word(actor+0x3C)==assembly+offset;
}
static int zero_native_weapon_effect(uint32_t actor) {
    /* Original DAT85 assembly words34h/38h select native ceiling ice33 and
     * rising flame34. They have no compressed frame table: their original
     * page/UVs address Zero's uploaded atlas, which shares VRAM with X.
     * Admit only an actual private native shot and its exact source assembly. */
    if(render_x_death || !assembly || actor<0x800950A0u || actor>=0x800964A0u ||
       (actor-0x800950A0u)%0xA0u || psx_mod_read_byte(PLAYER+2)!=1 ||
       !(psx_mod_read_byte(actor)&1) || psx_mod_read_word(actor+0x38))return 0;
    unsigned kind=psx_mod_read_byte(actor+1);
    unsigned header=kind==33?0x34u:kind==34?0x38u:0;
    if(!header)return 0;
    uint32_t offset=psx_mod_read_word(assembly+header);
    return offset && offset<ASSET_SPACE &&
        psx_mod_read_word(actor+0x3C)==assembly+offset;
}
static int zero_dash_effect(uint32_t actor) {
    int slot=shared_effect_slot(actor);
    /* Original80049100 resolves assembly word4. Its Zero shapes and C3
     * palette differ from the shared X atlas even after owner projection. */
    uint32_t offset=assembly?psx_mod_read_word(assembly+4):ASSET_SPACE;
    return slot>=0 && shared_effect_owners[slot]==2 && psx_mod_read_byte(actor) &&
        psx_mod_read_byte(actor+1)==1 && offset<ASSET_SPACE &&
        psx_mod_read_word(actor+0x3C)==assembly+offset;
}
static int private_falcon_flight_effect(uint32_t actor) {
    /* Original3F310 allocates shared18 during Falcon action23. 4B3A0
     * resolves assembly header1C, sets page0500/CLUT7802 and uses the
     * current body frame minus42. DAT87 body frame42 has20 tiles; its
     * three jet shapes select tiles8/9/10 of that SAME compressed frame. */
    if(render_x_death || private_actor.character!=MMX6_COOP_CHARACTER_X ||
       private_actor.form!=MMX6_COOP_FORM_FALCON || !assembly)return 0;
    int slot=shared_effect_slot(actor);
    if(slot<0 || shared_effect_owners[slot]!=2 || !psx_mod_read_byte(actor) ||
       psx_mod_read_byte(actor+1)!=18 || psx_mod_read_word(actor+0x38) ||
       psx_mod_read_half(actor+0x40)!=0x0500)return 0;
    uint32_t offset=psx_mod_read_word(assembly+0x1C);
    return offset && offset<ASSET_SPACE && psx_mod_read_word(actor+0x3C)==assembly+offset;
}
static int zero_death_effect(uint32_t actor) {
    /* Native global FX11 resolves assembly word4 and remaps packed icon
     * tiles (flags21). Its original origin is already retained at birth;
     * its atlas/palette owner must also outlive the player callback. */
    if(actor<0x800CD410u || actor>=0x800CF810u ||
        (actor-0x800CD410u)%0x60u || !assembly)return 0;
    unsigned slot=(actor-0x800CD410u)/0x60u;
    uint32_t offset=psx_mod_read_word(assembly+4);
    return death_effect[slot].owner==2 && psx_mod_read_byte(actor) &&
        psx_mod_read_byte(actor+1)==0x11 && offset<ASSET_SPACE &&
        psx_mod_read_word(actor+0x3C)==assembly+offset;
}
static uint16_t zero_atlas_effect_bank(uint16_t page,uint16_t clut,uint16_t tile,int menu) {
    /* Original type1 dash, type17 UI, type26/44 icons and native33/34 weapons share VRAM with X's
     * different PL00 art. Decode the original private atlas and the native
     * menu/player palette, retaining actual page, UVs, tint and blending.
     * The virtual source key is outside the compressed player archive. */
    if(!zero_ui_pixels || (page&0x180u))return 0;
    unsigned cx=(clut&63)*16,cy=clut>>6;
    uint8_t colors[32];
    if(menu) {
        if(cy<496 || cy>=512 || cx<256 || cx+16>320)return 0;
        capture(menu_memory+0x10000+((cy-496)*64+cx-256)*2,colors,sizeof colors);
    } else {
        size_t offset;
        if(!working_palette_clut_offset(clut,&offset))return 0;
        capture(active_palette+(uint32_t)offset,colors,sizeof colors);
    }
    uint32_t source=menu_memory+MENU_BYTES+(page&31u)*4u;
    for(unsigned i=0;i<bank_count;++i)
        if(banks[i].character==private_actor.character && banks[i].source==source && banks[i].tile==tile && !memcmp(banks[i].colors,colors,32))
            return banks[i].id;
    uint16_t pixels[256*256];
    unsigned width=tile==UINT16_MAX?256:16,bx=(page&15)*64,by=(page&16)*16;
    for(unsigned y=0;y<width;++y)for(unsigned x=0;x<width;++x) {
        unsigned u=tile==UINT16_MAX?x:((tile&255)+x)&255;
        unsigned v=tile==UINT16_MAX?y:((tile>>8)+y)&255;
        unsigned word=zero_ui_pixels[(by+v)*1024+bx+u/4];
        unsigned color=(word>>((u&3)*4))&15;
        pixels[y*width+x]=(uint16_t)(colors[color*2]|colors[color*2+1]<<8);
    }
    return retain_sprite_bank(source,tile,colors,pixels);
}
static uint16_t zero_ui_effect_bank(uint16_t page,uint16_t clut,uint16_t tile) {
    return zero_atlas_effect_bank(page,clut,tile,1);
}
static void triangle(uint32_t dst, uint32_t next, const uint32_t *q,
                     unsigned a, unsigned b, unsigned c, uint16_t bank) {
    uint32_t color=q[1]&0xFFFFFF;
    unsigned v[3]={a,b,c};
    psx_mod_write_word(dst,0x09000000u|(next&0xFFFFFF));
    for (unsigned i=0;i<3;++i) {
        uint32_t tag=i==0 ? (0x34000000u|(q[1]&0x03000000u)) :
                     i==1 ? (uint32_t)(bank&255)<<24 : (uint32_t)(bank>>8)<<24;
        uint32_t uv=q[3+v[i]*2]&0xFFFF;
        if(i==1) uv|=(0x100u|((q[5]>>16)&0x60u))<<16; /* Host bank is 16-bit color. */
        psx_mod_write_word(dst+4+i*12,tag|color);
        psx_mod_write_word(dst+8+i*12,q[2+v[i]*2]);
        psx_mod_write_word(dst+12+i*12,uv);
    }
}
/* Process-local, read-only rendering diagnosis. No guest/native state writes. */
#ifndef PSX_NO_DEBUG_TOOLS
static uint32_t giga_trace_pointed_word(uint32_t pointer,int *valid) {
    uint32_t physical=pointer&0x1FFFFFFFu,packet_physical=packets&0x1FFFFFFFu;
    *valid=!(physical&3u) && ((physical>=0x10000u && physical<=0x1FFFFCu) ||
        (packets && physical>=packet_physical && physical-packet_physical<=FRAME_ARENA*2u-4u));
    if (*valid) return psx_mod_read_word(physical|0x80000000u);
    return UINT32_MAX;
}
static void giga_packet_trace(const char *phase,uint32_t actor) {
    const char *enabled=getenv("MMX6_GIGA_PACKET_TRACE");
    if (!enabled || strcmp(enabled,"1")) return;
    int slot=actor?shared_effect_slot(actor):-1;
    int personal=actor>=0x800950A0u && actor<0x800964A0u && (actor-0x800950A0u)%0xA0u==0;
    if (actor && slot<0 && !personal) return; /* Admit the pool before reading actor fields. */
    unsigned type=actor?psx_mod_read_byte(actor+1):0;
    if (actor) {
        int owned_shared=slot>=0 && shared_effect_owners[slot]==2 && (type==17 || type==26);
        int owned_shot=personal && type==44 &&
            psx_mod_read_byte(PLAYER+2)==1 && !render_x_death;
        if (!owned_shared && !owned_shot) return;
    } else if (p2.body[5]!=59) return;
    unsigned parity=psx_mod_read_word(SCRATCH)&1u;
    uint32_t head11=psx_mod_read_word(0x80090D70u+parity*128u+36u);
    uint32_t tail11=psx_mod_read_word(0x8008EB08u+parity*128u+36u);
    uint32_t head37=psx_mod_read_word(0x80090D70u+parity*128u+124u);
    uint32_t tail37=psx_mod_read_word(0x8008EB08u+parity*128u+124u);
    int head11_valid,tail11_valid,head37_valid,tail37_valid;
    uint32_t head11_word=giga_trace_pointed_word(head11,&head11_valid);
    uint32_t tail11_word=giga_trace_pointed_word(tail11,&tail11_valid);
    uint32_t head37_word=giga_trace_pointed_word(head37,&head37_valid);
    uint32_t tail37_word=giga_trace_pointed_word(tail37,&tail37_valid);
    static uint64_t host_trace_sequence;
    fprintf(stdout,"mmx6_giga_packet_trace sequence=%llu phase=%s actor=%08X type=%u subtype=%u state=%u action=%u assembly=%08X priority=%02X parity=%u native_timer=%u sprite_frame47=%u scratch0=%08X world_packets=%08X inside=%d world_render=%d zero_world=%d pause_owner=%d base=%08X mode=%08X budget=%u head11=%08X head11_valid=%d head11_word=%08X tail11=%08X tail11_valid=%d tail11_word=%08X head37=%08X head37_valid=%d head37_word=%08X tail37=%08X tail37_valid=%d tail37_word=%08X\n",
        (unsigned long long)++host_trace_sequence,phase,actor,type,
        actor?psx_mod_read_byte(actor+2):0,actor?psx_mod_read_byte(actor+4):0,
        actor?psx_mod_read_byte(actor+5):0,actor?psx_mod_read_word(actor+0x3C):0,
        actor?psx_mod_read_byte(actor+0x16):0,parity,
        psx_mod_read_word(PLAY+0x90),actor?psx_mod_read_byte(actor+0x47):0,
        psx_mod_read_word(SCRATCH),world_packets,inside,world_render,zero_world,pause_owner,
        psx_mod_read_word(SCRATCH+0x100),
        psx_mod_read_word(SCRATCH+0x104),psx_mod_read_word(SCRATCH+0x124),
        head11,head11_valid,head11_word,tail11,tail11_valid,tail11_word,
        head37,head37_valid,head37_word,tail37,tail37_valid,tail37_word);
}
#else
static void giga_packet_trace(const char *phase,uint32_t actor) { (void)phase;(void)actor; }
#endif

static void begin_world_draw(CPUState *cpu,uint32_t address) {
    /* Native80025FB0 precedes background and sprite/HUD emission, including
     * the first arrival draw before stage_tick. Both private bodies and
     * deferred shared effects append once in this original render order. */
    independent_world_begin();
    if(enrolled && !failed)world_packets=packets+(psx_mod_read_word(SCRATCH)&1u)*FRAME_ARENA;
    giga_packet_trace("world-begin",0);
    (void)cpu;(void)address;
}
static void render_actor_pass(CPUState *cpu, uint32_t actor, uint32_t arena,int armor) {
    uint32_t base=psx_mod_read_word(SCRATCH+0x100);
    uint32_t mode=psx_mod_read_word(SCRATCH+0x104);
    /* Preserve native's no-output return at budget>=1000. A negative budget
     * would evade its signed comparison and cannot protect our arena. */
    if (base<arena || base-arena>PLAYER_PACKET_BYTES || (base-arena)%40 ||
        mode!=arena+PLAYER_MODE_OFFSET+(base-arena)/5 ||
        (psx_mod_read_word(SCRATCH+0x124)&0x80000000u) ||
        psx_mod_read_word(SCRATCH+0x124)<(base-arena)/40) {
        failed=1; return;
    }
    uint32_t restore_words[4]={base,mode,actor,arena};
    STATE_WORDS(restore_packet,15,restore_words,4);
    giga_packet_trace("before-native",actor);
    /* Native22960 follows the ordinary X body with2619C. That pass
     * resolves actor+DC in the assembly HEADER, not actor+3C, and samples
     * the remaining tiles in that SAME compressed body frame, with fixed
     * armor CLUTs instead of actor+42. Project only the assembly pointer;
     * native owns form/pose gates,
     * shape geometry, camera, priority, CLUT selection and packet budget. */
    uint32_t original_assembly=psx_mod_read_word(SCRATCH+0x1C);
    STATE_WORDS(restore_assembly,15,&original_assembly,1);
    if(armor)psx_mod_write_word(SCRATCH+0x1C,assembly);
    guest(cpu,armor?0x8002619Cu:0x800232D4u,actor,0);
    if(armor)psx_mod_write_word(SCRATCH+0x1C,original_assembly);
    STATE_POP(restore_assembly);
    STATE_POP(restore_packet);
    giga_packet_trace("after-native",actor);
    uint32_t end=psx_mod_read_word(SCRATCH+0x100);
    if (end<base || end-arena>PLAYER_PACKET_BYTES || (end-base)%40 ||
        psx_mod_read_word(SCRATCH+0x104)!=mode+(end-base)/5 ||
        (psx_mod_read_word(SCRATCH+0x124)&0x80000000u) ||
        psx_mod_read_word(SCRATCH+0x124)<(end-arena)/40) {
        failed=1; return;
    }
    uint32_t table=psx_mod_read_word(actor+0x38);
    unsigned frame=psx_mod_read_byte(actor+0x47);
    /* Native saber actors share the player's uploaded frame, with their own
     * assembly and palette (801ED4F4); they have no decompression pointer. */
    const uint8_t *retained_body=render_x_death?p1.body:p2.body;
    if (!table && (private_falcon_flight_effect(actor) ||
        (psx_mod_read_word(actor+0x3C)==le32(retained_body+0x3C) &&
         psx_mod_read_half(actor+0x40)==(uint16_t)(retained_body[0x40]|retained_body[0x41]<<8)))) {
        table=zero_world&&!render_x_death?psx_mod_read_word(PLAYER+0x38):le32(retained_body+0x38);
        frame=zero_world&&!render_x_death?psx_mod_read_byte(PLAYER+0x47):retained_body[0x47];
    }
    /* Common effects use the stage's already resident textures. Only native
     * Zero frames need the retained host bank instead of X's texture slot. */
    int ui=zero_ui_effect(actor),icons=zero_icon_effect(actor)||zero_native_weapon_effect(actor)||zero_death_effect(actor)||zero_dash_effect(actor);
    if (!ui && !icons && !render_x_death && (table<assets || table-assets>=compressed_size)) {
        giga_packet_trace("native-only",actor);return;
    }
    if (render_x_death && (table<0x80010000u || table>=0x80200000u)) {
        giga_packet_trace("native-only",actor);return;
    }
    uint32_t expanded=arena+PLAYER_PACKET_BYTES+(base-arena)*2;
    for (uint32_t at=base;at<end;at+=40,expanded+=80,mode+=8) {
        uint32_t q[10];
        for (unsigned i=0;i<10;++i) q[i]=psx_mod_read_word(at+i*4);
        uint16_t tile;
        int supported=mmx6_coop_sprite_quad(q,&tile);
        if (tile!=UINT16_MAX)
            q[5]|=(psx_mod_read_word(mode+4)&0x60u)<<16;
        uint16_t bank=0;
        uint16_t page=tile==UINT16_MAX?(uint16_t)(q[5]>>16):(uint16_t)psx_mod_read_word(mode+4);
        if(supported)bank=ui?zero_ui_effect_bank(page,
            (uint16_t)(q[3]>>16),tile):icons?zero_atlas_effect_bank(page,
            (uint16_t)(q[3]>>16),tile,0):sprite_bank(table,frame,(uint16_t)(q[3]>>16),tile);
        /* Native OT links still address the original tag. Turn it into a
         * zero-command link to two tagged GT3 packets in our own DMA arena. */
        if (bank) {
            triangle(expanded,expanded+40,q,0,1,2,bank);
            triangle(expanded+40,q[0],q,2,1,3,bank);
            psx_mod_tag_world_primitive(expanded,1);
            psx_mod_tag_world_primitive(expanded+40,1);
            psx_mod_write_word(at,expanded&0xFFFFFF);
            /* Native actor lists append through a saved tail tag. Retarget
             * that tail too, or the next actor overwrites our link and drops
             * this actor's last tile (Zero's boot in the idle pose). */
            unsigned priority=psx_mod_read_byte(actor+0x16);
            if (priority!=0xFF) {
                uint32_t tail=0x8008EB08u+(psx_mod_read_word(SCRATCH)&1u)*128+
                              (priority>>4)*32+(priority&7)*4;
                if (psx_mod_read_word(tail)==at) psx_mod_write_word(tail,expanded+40);
            }
        } else {
            psx_mod_write_word(at,q[0]&0xFFFFFF);
        }
    }
    giga_packet_trace("after-conversion",actor);
}
static void render_actor(CPUState *cpu,uint32_t actor,uint32_t arena) {
    render_actor_pass(cpu,actor,arena,0);
}
static int native_x_armor_draw(void) {
    unsigned form=psx_mod_read_byte(PLAYER+0xE7);
    return !psx_mod_read_byte(PLAYER+2) && form>=1 && form<=4;
}
static void render_armor(CPUState *cpu,uint32_t arena) {
    if(native_x_armor_draw() && !failed)render_actor_pass(cpu,PLAYER,arena,1);
}
static int render_armor_survivor(CPUState *cpu,uint32_t address) {
    (void)address;
    /* When the guest owns the original world,22960 still invokes its own
     * armor pass. Replace that single call instead of appending it again
     * from the ordinary body replacement. */
    if(world_render || !zero_world || !enrolled || failed || cpu->gpr[4]!=PLAYER ||
       private_actor.character!=MMX6_COOP_CHARACTER_X ||
       psx_mod_read_byte(PLAY)!=0x0A || !psx_mod_texture_banks_supported())return 0;
    world_render=1;
    uint32_t original=psx_mod_read_word(SCRATCH+0x100);
    uint32_t original_mode=psx_mod_read_word(SCRATCH+0x104);
    uint32_t arena=packets+(psx_mod_read_word(SCRATCH)&1u)*FRAME_ARENA;
    uint32_t context[4]={original,original_mode,PLAYER,arena};
    STATE_WORDS(restore_packet,18,context,4);
    psx_mod_write_word(SCRATCH+0x100,world_packets);
    psx_mod_write_word(SCRATCH+0x104,arena+PLAYER_MODE_OFFSET+(world_packets-arena)/5);
    render_armor(cpu,arena);
    world_packets=psx_mod_read_word(SCRATCH+0x100);
    psx_mod_write_word(SCRATCH+0x100,original);
    psx_mod_write_word(SCRATCH+0x104,original_mode);
    STATE_POP(restore_packet);world_render=0;
    return 1;
}
static void render(CPUState *cpu, uint32_t address) {
    (void)address;
    if (inside || world_render || failed || !enrolled || cpu->gpr[4]!=PLAYER || !p2.body[3] ||
        life.status[1]==MMX6_COOP_ABSENT || life.status[1]==MMX6_COOP_FALLEN ||
        psx_mod_read_byte(PLAY)!=0x0A || !psx_mod_texture_banks_supported()) return;
    /* Nested guest dispatch still runs the survivor replacement. Keep that
     * replacement outside this entire private draw pass: a retained type44
     * shot otherwise restarts at world_packets before this pass appends its
     * body, and later shared curtain packets overwrite the shot's live tail. */
    inside=world_render=1;
    uint32_t original=psx_mod_read_word(SCRATCH+0x100);
    uint32_t original_mode=psx_mod_read_word(SCRATCH+0x104);
    uint32_t arena=packets+(psx_mod_read_word(SCRATCH)&1u)*FRAME_ARENA;
    uint32_t base=world_packets;
    capture_player(&p1);
    STATE_BYTES(restore_player,16,&p1,sizeof p1);
    uint32_t render_context[4]={original,original_mode,arena,base};STATE_WORDS(restore_packet,17,render_context,4);
    project_player(&p2);
    psx_mod_write_word(SCRATCH+0x100,base);
    psx_mod_write_word(SCRATCH+0x104,arena+PLAYER_MODE_OFFSET+(base-arena)/5);
    render_actor(cpu,PLAYER,arena);
    render_armor(cpu,arena);
    /* 80022960 draws X-only attached actors, then visible trails2/1/0.
     * Fixed P2 is Zero, so preserve the native no-charge-glow draw gate;
     * updating its attached pool does not authorize synthetic X artwork. */
    if (!psx_mod_read_byte(PLAYER+2)) for (unsigned i=0;i<3 && !failed;++i) {
        uint32_t actor=0x800911A8u+i*0x50;
        if (psx_mod_read_byte(actor+3)) render_actor(cpu,actor,arena);
    }
    for (unsigned i=3;i && !failed;--i) {
        uint32_t actor=0x800972F8u+(i-1)*0x60;
        if (psx_mod_read_byte(actor+3)) render_actor(cpu,actor,arena);
    }
    for (unsigned i=0;i<32 && !failed;++i) {
        uint32_t actor=0x800950A0u+i*0xA0;
        if (psx_mod_read_byte(actor+3)) render_actor(cpu,actor,arena);
    }
    uint32_t end=psx_mod_read_word(SCRATCH+0x100);
    world_packets=end;
    psx_mod_write_word(SCRATCH+0x100,original);
    psx_mod_write_word(SCRATCH+0x104,original_mode);
    project_player(&p1);
    STATE_POP(restore_packet);STATE_POP(restore_player);
    psx_mod_write_word(diagnostic+28,bank_count);
    psx_mod_write_word(diagnostic+32,(end-base)/40);
    inside=world_render=0;
}
static int living_primary_frozen_draw(void) {
    /* A guest-owned in-place dialogue and a guest-owned pause both keep
     * the living primary's own frozen body/personal pools in this world.
     * Transport scenes retain their separate passenger animation policy. */
    return life.status[0]==MMX6_COOP_ALIVE &&
        (pause_owner==1 || (scene_owner==2 && !scene_phase));
}
static int render_survivor(CPUState *cpu, uint32_t address) {
    uint32_t actor=cpu->gpr[4];
    if(world_render || !enrolled || failed || psx_mod_read_byte(PLAY)!=0x0A ||
        !psx_mod_texture_banks_supported())return 0;
    int retained=zero_ui_effect(actor)||zero_icon_effect(actor)||zero_native_weapon_effect(actor)||zero_death_effect(actor)||zero_dash_effect(actor)||private_falcon_flight_effect(actor);
    if (!zero_world && !retained) return 0;
    int shot=actor>=0x800950A0 && actor<0x800964A0 && !((actor-0x800950A0)%0xA0);
    int trail=actor>=0x800972F8 && actor<0x80097418 && !((actor-0x800972F8)%0x60);
    int attached=!psx_mod_read_byte(PLAYER+2) && actor>=0x800911A8 && actor<0x80091298 &&
        !((actor-0x800911A8)%0x50);
    if (actor!=PLAYER && !shot && !trail && !attached && !retained) return 0;
    world_render=1;
    uint32_t original=psx_mod_read_word(SCRATCH+0x100);
    uint32_t original_mode=psx_mod_read_word(SCRATCH+0x104);
    uint32_t arena=packets+(psx_mod_read_word(SCRATCH)&1u)*FRAME_ARENA;
    uint32_t render_context[4]={original,original_mode,actor,arena};STATE_WORDS(restore_packet,18,render_context,4);
    psx_mod_write_word(SCRATCH+0x100,world_packets);
    psx_mod_write_word(SCRATCH+0x104,arena+PLAYER_MODE_OFFSET+(world_packets-arena)/5);
    render_actor(cpu,actor,arena);
    /* A guest-owned pause or in-place dialogue draws the native world with
     * its owner projected at PLAYER. Retain the living primary in that same
     * draw instead of hiding it until gameplay resumes. Native menu-only
     * pages do not call this path. */
    if (actor==PLAYER && (life.status[0]==MMX6_COOP_DYING || scene_passenger(0) ||
        living_primary_frozen_draw()) && p1.body[3]) {
        PlayerContext zero_player;
        capture_player(&zero_player);
        STATE_BYTES(restore_player,19,&zero_player,sizeof zero_player);
        project_player(&p1);
        render_x_death=1;
        render_actor(cpu,PLAYER,arena);
        if (living_primary_frozen_draw()) {
            /* Original PLAYER world dispatch also owns X's frozen personal
             * pools. Native menu-only pages never invoke this branch. Common
             * charge art keeps its original stage texture; X-frame trails and
             * shots use retained banks rather than Zero's singleton sheet. */
            for (unsigned i=0;i<3 && !failed;++i) {
                uint32_t effect=0x800911A8u+i*0x50;
                if (psx_mod_read_byte(effect+3)) render_actor(cpu,effect,arena);
            }
            for (unsigned i=3;i && !failed;--i) {
                uint32_t trail_actor=0x800972F8u+(i-1)*0x60;
                if (psx_mod_read_byte(trail_actor+3)) render_actor(cpu,trail_actor,arena);
            }
            for (unsigned i=0;i<32 && !failed;++i) {
                uint32_t shot_actor=0x800950A0u+i*0xA0;
                if (psx_mod_read_byte(shot_actor+3)) render_actor(cpu,shot_actor,arena);
            }
        }
        render_x_death=0;
        project_player(&zero_player);
        STATE_POP(restore_player);
    }
    world_packets=psx_mod_read_word(SCRATCH+0x100);
    psx_mod_write_word(SCRATCH+0x100,original);
    psx_mod_write_word(SCRATCH+0x104,original_mode);
    STATE_POP(restore_packet);
    world_render=0;
    (void)address;
    return 1;
}
static int death_effect_allocate(CPUState *cpu, uint32_t address) {
    if (effect_call || !enrolled || failed) return 0;
    uint32_t caller=cpu->gpr[31];
    effect_call=1;
    uint32_t actor=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    effect_call=0;
    if (actor>=0x800CD410 && actor<0x800CF810 && (actor-0x800CD410)%0x60==0) {
        DeathEffectOrigin *o=&death_effect[(actor-0x800CD410)/0x60];
        /* Every allocation invalidates the preceding occupant's ownership,
         * including unrelated effects reusing a retired FX11 slot. */
        o->valid=0;o->owner=0;
        if (caller==0x8003DB0C || caller==0x8003DB8C) {
            o->x=psx_mod_read_word(PLAYER+8); o->y=psx_mod_read_word(PLAYER+12);
            o->layer=psx_mod_read_byte(PLAYER+0x14);
            o->assembly=psx_mod_read_word(SCRATCH+0x1C);
            o->valid=1;o->owner=(uint8_t)(psx_mod_read_byte(PLAYER+2)?2:1);
        }
    }
    cpu->gpr[2]=actor;
    return 1;
}
static int death_effect_init(CPUState *cpu, uint32_t address) {
    uint32_t actor=cpu->gpr[4];
    if (effect_call || !enrolled || failed || actor<0x800CD410 || actor>=0x800CF810 ||
        (actor-0x800CD410)%0x60) return 0;
    DeathEffectOrigin *o=&death_effect[(actor-0x800CD410)/0x60];
    if (!o->valid) return 0;
    o->valid=0;
    uint32_t x=psx_mod_read_word(PLAYER+8), y=psx_mod_read_word(PLAYER+12);
    uint32_t assembly_now=psx_mod_read_word(SCRATCH+0x1C);
    uint8_t layer=psx_mod_read_byte(PLAYER+0x14);
    uint32_t restore_values[4]={x,y,assembly_now,layer};
    STATE_WORDS(restore_origin,20,restore_values,4);
    psx_mod_write_word(PLAYER+8,o->x); psx_mod_write_word(PLAYER+12,o->y);
    psx_mod_write_byte(PLAYER+0x14,o->layer); psx_mod_write_word(SCRATCH+0x1C,o->assembly);
    effect_call=1;
    uint32_t result=guest(cpu,address,actor,cpu->gpr[5]);
    effect_call=0;
    psx_mod_write_word(PLAYER+8,x); psx_mod_write_word(PLAYER+12,y);
    psx_mod_write_byte(PLAYER+0x14,layer); psx_mod_write_word(SCRATCH+0x1C,assembly_now);
    STATE_POP(restore_origin);
    cpu->gpr[2]=result;
    return 1;
}
#include "mmx6_coop_boss_balance.inc"
static int enemy_hit(CPUState *cpu, uint32_t address) {
    if(private_draw || psx_mod_local_view_scope())return 0;
    if(inside || !enrolled || failed || scene_owner || psx_mod_read_byte(PLAY)!=10)return 0;
    uint32_t enemy=cpu->gpr[4];
    BossBalanceState *balance=boss_balance_actor(enemy);
    if(life.status[1]!=MMX6_COOP_ALIVE && !balance)return 0;
    boss_balance_pending_actor=0;inside=1;
    if(balance && boss_balance_independent) {
        for(unsigned seat=0;seat<2;++seat)if(balance->clocks[seat])--balance->clocks[seat];
        if(balance->timer_offset && (psx_mod_read_word(enemy+0x58)!=0x8007433Cu ||
           !boss_balance_native_clock(enemy,balance)))balance->timer_offset=balance->timer_half=0;
    }
    unsigned resident=(unsigned)!!zero_projected;
    uint32_t result=psx_mod_read_byte(PLAYER+0xCC)?0:
        boss_balance_scan(cpu,address,enemy,resident,balance);
    /* Rejected126/127 contacts are not accepted hits and must not consume a
     * ready partner's separate window. Keep the original P1-first reaction. */
    if(!resident && (!result || (balance && boss_balance_independent && (result==126 || result==127))) &&
       (!balance || boss_balance_pending_actor!=enemy) &&
       life.status[1]==MMX6_COOP_ALIVE && p2.body[0x5C] && !p2.body[0xCC]) {
        enter_zero();result=boss_balance_scan(cpu,address,enemy,1,balance);leave_zero();
        if(result)psx_mod_write_word(diagnostic+40,psx_mod_read_word(diagnostic+40)+1);
    }
    cpu->gpr[2]=result;inside=0;return 1;
}
static int player_contact(CPUState *cpu, uint32_t address) {
    /* A negotiated, tainted prerequisite may bypass enemy contact only.
     * Run before the ordinary co-op retry guard: P1 still needs protection
     * while P2 is absent, and a real projected P2 callback may be nested. */
    unsigned protected=checkpoint_contact_protection_mask();
    unsigned resident=psx_mod_read_byte(PLAYER+2);
    if(address==0x80030ECCu && resident<2 && (protected&(1u<<resident))) {
        cpu->gpr[2]=0;return 1; /* Exact native no-contact result; no body write. */
    }
    if (inside || !enrolled || failed || scene_owner || life.status[1]!=MMX6_COOP_ALIVE ||
        psx_mod_read_byte(PLAY)!=0x0A) return 0;
    inside=1;
    /* Native contact applies damage/knockback/iframes, then its caller handles
     * the enemy/projectile. Retry only a miss so a consumed projectile cannot
     * damage both actors and its AI still runs exactly once. */
    uint32_t actor=cpu->gpr[4], result=psx_mod_read_byte(PLAYER+0xCC)?0:
        guest(cpu,address,actor,cpu->gpr[5]);
    if (!result && (p2.body[0x5C]&0x7F) && !p2.body[0xCC]) {
        enter_zero();
        result=guest(cpu,address,actor,cpu->gpr[5]);
        leave_zero();
        if (result) psx_mod_write_word(diagnostic+0x44,psx_mod_read_word(diagnostic+0x44)+1);
    }
    cpu->gpr[2]=result;
    inside=0;
    return 1;
}
static SolidContact *solid_contact(uint32_t actor) {
    if (actor>=0x800C1220u && actor<0x800C4560u && !((actor-0x800C1220u)%0xA4))
        return &zero_solid_contacts[(actor-0x800C1220u)/0xA4];
    /* Personal pools share their guest addresses during projection. Only the
     * resident X pool owns these contacts; a projected Zero shot must neither
     * use nor clear an unrelated X block's saved partner history. */
    if (!zero_projected && actor>=0x800950A0u && actor<0x800964A0u &&
        !((actor-0x800950A0u)%0xA0))
        return &zero_solid_contacts[STAGE_SOLID_CONTACTS+(actor-0x800950A0u)/0xA0];
    return NULL;
}
static int solid_allocate(CPUState *cpu, uint32_t address) {
    if (solid_allocate_call || !enrolled || failed) return 0;
    solid_allocate_call=1;
    uint32_t actor=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    solid_allocate_call=0;
    SolidContact *contact=solid_contact(actor);
    if (contact) memset(contact,0,sizeof *contact);
    cpu->gpr[2]=actor;
    return 1;
}
static uint32_t solid_as_zero(CPUState *cpu, uint32_t address, uint32_t actor,
                              SolidContact *contact) {
    uint8_t sides=psx_mod_read_byte(actor+0x72), carried=psx_mod_read_byte(actor+0x76);
    uint8_t history[2]={sides,carried};
    STATE_BYTES(restore_contact,21,history,sizeof history);
    uint32_t context[3]={address,actor,(uint32_t)(contact-zero_solid_contacts)};
    STATE_WORDS(restore_target,43,context,3);
    psx_mod_write_byte(actor+0x72,contact->sides);
    psx_mod_write_byte(actor+0x76,contact->carried);
    uint32_t result=guest(cpu,address,actor,cpu->gpr[5]);
    contact->sides=psx_mod_read_byte(actor+0x72);
    contact->carried=psx_mod_read_byte(actor+0x76);
    psx_mod_write_byte(actor+0x72,sides);
    psx_mod_write_byte(actor+0x76,carried);
    STATE_POP(restore_target);STATE_POP(restore_contact);
    return result;
}
static int snail_support_mask(const CPUState *cpu,uint32_t actor) {
    /* Amazon's original outer callback brackets 31DA8 with a body-local
     * support mask. The extra player collision call must carry that same
     * bracket; it does not execute the enemy's outer callback a second time. */
    if(cpu->gpr[31]!=0x800EC0B8u || cpu->gpr[18]!=actor || cpu->gpr[19]!=PLAYER ||
       psx_mod_read_byte(PLAY+12)!=1 || psx_mod_read_byte(PLAY+13) ||
       psx_mod_read_byte(actor+1)!=1 || psx_mod_read_byte(actor+4)!=1 ||
       psx_mod_read_word(actor+0x30)!=0x800F73D4u ||
       psx_mod_read_word(actor+0x68)!=0x800F73ECu)return 0;
    uint32_t origin=psx_mod_read_word(actor+0x10);
    if(origin<0x800F6540u || origin>0x800F6588u || ((origin-0x800F6540u)&7u) ||
       psx_mod_read_byte(origin+1)!=7 || psx_mod_read_byte(origin+2))return 0;
    return psx_mod_read_word(0x800EC0A4u)==0x92710072u &&
        psx_mod_read_word(0x800EC0A8u)==0xA2620072u &&
        psx_mod_read_word(0x800EC0ACu)==0x92500072u &&
        psx_mod_read_word(0x800EC0B0u)==0x0C00C76Au &&
        psx_mod_read_word(0x800EC0D0u)==0xA2710072u &&
        psx_mod_read_word(0x800EC0E8u)==0xA2620072u;
}
/* Original51890 consumes last update's +72 in its phase, then computes the
 * next contact through31DA8. Keep that complete transaction in the actual X
 * owner's context: a phase-only projection leaves its producer outside it.
 * Animation, phase, effects and shared collisions still execute exactly once.
 * The other hero receives only the original body-contact pass, never the AI. */
static int capsule_owner_update(CPUState *cpu,uint32_t address) {
    uint32_t actor=cpu->gpr[4];
    if(address!=0x80051890u || scene_call || solid_call || private_draw || view_call ||
       !ready || !enrolled || failed || pause_owner>=0 || clear_phase ||
       psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
       !both_door_slot(actor) || !(psx_mod_read_byte(actor)&1u) ||
       psx_mod_read_byte(actor+1)!=26 || psx_mod_read_byte(actor+2)!=4 ||
       psx_mod_read_word(actor+0x10)!=0x800F2E24u || psx_mod_read_byte(actor+4)!=1 ||
       private_actor.character!=MMX6_COOP_CHARACTER_X || p2.body[2]!=0 ||
       life.status[1]!=MMX6_COOP_ALIVE || !p2.body[0] || p2.body[4]!=1 ||
       !p2.body[0x5C] || p2.body[0x5C]>=128 ||
       (scene_owner && scene_owner!=2))return 0;
    unsigned phase=psx_mod_read_byte(actor+5),projected=zero_world!=0;
    if(phase<6 || phase>10 || (projected?!zero_projected:(inside || zero_projected)) ||
       (projected?p1.body[2]:psx_mod_read_byte(PLAYER+2))!=1)return 0;
    SolidContact *contact=solid_contact(actor);
    if(!contact)return 0;
    uint32_t context[4]={actor,(uint32_t)inside,(uint32_t)scene_call,(uint32_t)solid_call};
    STATE_WORDS(restore_capsule,69,context,4);
    uint8_t ride=psx_mod_read_byte(0x800CD340u);
    STATE_BYTES(restore_capsule_ride,23,&ride,1);
    scene_call=solid_call=inside=1;
    if(!projected)enter_zero();
    /* The one primary contact below also owns the original ride contact. */
    psx_mod_write_byte(0x800CD340u,0);
    uint32_t result=solid_as_zero(cpu,address,actor,contact);
    STATE_WORDS(restore_capsule_result,44,&result,1);
    psx_mod_write_byte(0x800CD340u,ride);
    if(psx_mod_read_byte(PLAYER+0xE2) && psx_mod_read_byte(actor+5)>=7) {
        scene_begin(1,address);
        if(scene_owner==2)scene_phase=0; /* Original in-place boarding. */
    }
    if(life.status[0]==MMX6_COOP_ALIVE && p1.body[4]==1 &&
       p1.body[0x5C] && p1.body[0x5C]<128 && !p1.body[0xE5]) {
        uint8_t owner_body[sizeof p2.body];capture(PLAYER,owner_body,sizeof owner_body);
        STATE_BYTES(restore_capsule_owner,22,owner_body,sizeof owner_body);
        project(PLAYER,p1.body,sizeof p1.body);
        guest(cpu,0x80031DA8u,actor,0);
        capture(PLAYER,p1.body,sizeof p1.body);
        project(PLAYER,owner_body,sizeof owner_body);
        STATE_POP(restore_capsule_owner);
    }
    if(!projected)leave_zero_context(1);
    STATE_POP(restore_capsule_result);
    inside=(int)context[1];scene_call=(int)context[2];solid_call=(int)context[3];
    STATE_POP(restore_capsule_ride);STATE_POP(restore_capsule);
    cpu->gpr[2]=result;return 1;
}
static int solid_player_collision(CPUState *cpu, uint32_t address) {
    uint32_t actor=cpu->gpr[4];
    SolidContact *contact=solid_contact(actor);
    if (solid_call || !contact || !enrolled || failed || (inside && !zero_world) ||
        psx_mod_read_byte(PLAY)!=0x0A) return 0;
    solid_call=1;
    uint32_t result;
    if (zero_world) {
        /* The survivor/scene owner is already projected. Preserve X's stored
         * contact even while Zero owns the native world pass. */
        result=solid_as_zero(cpu,address,actor,contact);
    } else {
        result=guest(cpu,address,actor,cpu->gpr[5]);
        STATE_WORDS(restore_result,44,&result,1);
        if (life.status[1]==MMX6_COOP_ALIVE && !scene_passenger(1) && p2.body[4]==1) {
            inside=1;
            /* 31DA8 and its terrain/box helpers use the player body and the
             * common EXE hitbox tables. They never execute character overlay
             * code or touch the attack pools. Project only that body: swapping
             * the 44 KiB overlay for every solid made Recycle Lab CPU-bound. */
            uint8_t body[sizeof p2.body];
            capture(PLAYER,body,sizeof body);
            STATE_BYTES(restore_body,22,body,sizeof body);
            project(PLAYER,p2.body,sizeof p2.body);
            /* 31DA8 also resolves the shared ride armor. That part already
             * ran above; the extra call handles only the second player. */
            uint8_t ride=psx_mod_read_byte(0x800CD340);
            STATE_BYTES(restore_ride,23,&ride,1);
            psx_mod_write_byte(0x800CD340,0);
            uint32_t mask_context[3]={(unsigned)snail_support_mask(cpu,actor),
                psx_mod_read_byte(PLAYER+0x72),contact->sides};
            STATE_WORDS(restore_mask,82,mask_context,3);
            if(mask_context[0])psx_mod_write_byte(PLAYER+0x72,8);
            solid_as_zero(cpu,address,actor,contact);
            if(mask_context[0]) {
                /* Literal EC0B8..EC0E8: merge this player's own old/new
                 * support bits, including the one-frame lost-top marker.
                 * The native outer call still performs P1's bracket once. */
                unsigned mask=mask_context[1]|(contact->sides&8u);
                if((mask_context[2]&8u) && !(contact->sides&8u))mask|=8u;
                psx_mod_write_byte(PLAYER+0x72,(uint8_t)mask);
            }
            STATE_POP(restore_mask);
            psx_mod_write_byte(0x800CD340,ride);
            capture(PLAYER,p2.body,sizeof p2.body);
            project(PLAYER,body,sizeof body);
            STATE_POP(restore_ride);STATE_POP(restore_body);
            inside=0;
        } else memset(contact,0,sizeof *contact);
        STATE_POP(restore_result);
    }
    ride_sync_rider();
    cpu->gpr[2]=result;
    solid_call=0;
    return 1;
}
#include "mmx6_coop_northpole_ice.inc"

/* Retain each original 16x16 HUD tile with its original palette. Tile-local
 * UVs also avoid the 8-bit UV wrap at the edge of a native texture page. */
static uint16_t hud_tile_bank(uint16_t page, uint16_t clut, uint16_t uv) {
    if (page&0x180) return 0;
    uint16_t colors[16], pixels[16*16];
    unsigned cx=(clut&63)*16, cy=clut>>6;
    for (unsigned i=0;i<16;++i) {
        if (cy>=496 && cy<512 && cx>=256 && cx+16<=320)
            colors[i]=psx_mod_read_half(menu_memory+0x10000+((cy-496)*64+cx-256+i)*2);
        /* HUD frames use the game's shared UI palette, not the character's
         * raw palette archive. Use the same current CLUT as the native HUD,
         * including native fades; weapon icons use Zero's menu CLUT above. */
        else colors[i]=gpu_get_vram()[cy*1024+cx+i];
    }
    for (unsigned i=0;i<ui_bank_count;++i)
        if (ui_banks[i].page==page && ui_banks[i].clut==clut && ui_banks[i].uv==uv &&
            !memcmp(ui_banks[i].colors,colors,sizeof colors)) return ui_banks[i].id;
    if (ui_bank_count==4096) return 0;
    unsigned base_x=(page&15)*64, base_y=(page&16)*16;
    for (unsigned y=0;y<16;++y) for (unsigned x=0;x<16;++x) {
        unsigned u=((uv&255)+x)&255, v=((uv>>8)+y)&255;
        unsigned word=zero_ui_pixels[(base_y+v)*1024+base_x+u/4];
        pixels[y*16+x]=colors[(word>>((u&3)*4))&15];
    }
    uint16_t id=(uint16_t)(0x7000+ui_bank_count);
    if (!psx_mod_define_texture_bank(id,16,16,pixels)) return 0;
    UiBank *bank=&ui_banks[ui_bank_count++];
    bank->page=page; bank->clut=clut; bank->uv=uv; bank->id=id;
    memcpy(bank->colors,colors,sizeof colors);
    return id;
}
static int hud_icon(CPUState *cpu, uint32_t address) {
    (void)address;
    /* The life pool is shared. Keep its original P1 display, without a
     * duplicate beneath Zero's meters. All frames/icons remain native. */
    if (hud_seat!=1 || (cpu->gpr[4]!=3 && cpu->gpr[4]!=4)) return 0;
    cpu->gpr[2]=0;
    return 1;
}
static void hud_offsets(int *x, int *y) {
    char layout[32];
    *x=0; *y=private_draw?0:P2_HUD_Y;
    if(private_draw)return;
    /* Committed package options are immutable while the plugin runs. Read
     * the presentation preference directly: no new simulation/snapshot state.
     * Unknown/old configurations keep the original stacked default. */
    if (psx_mod_option_value("mmx6.local-coop","prototype","hud_layout",layout,sizeof layout) &&
        !strcmp(layout,"side_by_side")) { *x=56; *y=0; }
}
static void hud_zero_packets(uint32_t arena) {
    uint32_t sprites=psx_mod_read_word(SCRATCH+0x108);
    uint32_t modes=psx_mod_read_word(SCRATCH+0x10C);
    uint32_t bars=psx_mod_read_word(SCRATCH+0x110);
    if (sprites<arena || sprites>arena+0x1000 || (sprites-arena)%16 ||
        modes<arena+0x1000 || modes>arena+0x2000 ||
        (modes-arena-0x1000)!=(sprites-arena)/2 ||
        bars<arena+0x2000 || bars>arena+0x3000 || (bars-arena-0x2000)%36) {
        failed=1; return;
    }
    int offset_x,offset_y;hud_offsets(&offset_x,&offset_y);
    uint32_t expanded=arena+0x3000, mode=arena+0x1000;
    for (uint32_t at=arena;at<sprites;at+=16,mode+=8,expanded+=80) {
        uint32_t link=psx_mod_read_word(at), uv=psx_mod_read_word(at+12);
        uint16_t page=(uint16_t)psx_mod_read_word(mode+4);
        uint16_t bank=hud_tile_bank(page,(uint16_t)(uv>>16),(uint16_t)uv);
        if (!bank || expanded+80>arena+0x8000) { failed=1; return; }
        int x=(int16_t)psx_mod_read_half(at+8)+offset_x;
        int y=(int16_t)psx_mod_read_half(at+10)+offset_y;
        /* Native texture modulation fades the original art, without making
         * alternate HUD graphics or changing its normal colors. */
        uint32_t shade=p2_hud_fade*0x010101u;
        uint32_t q[10]={link,0x2C000000u|shade,0,0,0,0,0,0,0,0};
        for (unsigned i=0;i<4;++i) {
            q[2+i*2]=(uint16_t)(x+(i&1)*16)|((uint32_t)(uint16_t)(y+(i>>1)*16)<<16);
            q[3+i*2]=(i&1)*16|((i>>1)*16<<8);
        }
        triangle(expanded,expanded+40,q,0,1,2,bank);
        triangle(expanded+40,link,q,2,1,3,bank);
        psx_mod_tag_hud_primitive(expanded,-1);
        psx_mod_tag_hud_primitive(expanded+40,-1);
        psx_mod_write_word(at,expanded&0xFFFFFF);
    }
    for (uint32_t at=arena+0x2000;at<bars;at+=36) {
        for (unsigned xy=8;xy<=32;xy+=8) {
            psx_mod_write_half(at+xy,(uint16_t)(psx_mod_read_half(at+xy)+offset_x));
            psx_mod_write_half(at+xy+2,(uint16_t)(psx_mod_read_half(at+xy+2)+offset_y));
        }
        for (unsigned c=4;c<=28;c+=8) {
            uint32_t color=psx_mod_read_word(at+c), faded=color&0xFF000000u;
            for (unsigned channel=0;channel<24;channel+=8)
                faded|=(((color>>channel)&255)*p2_hud_fade/128)<<channel;
            psx_mod_write_word(at+c,faded);
        }
        psx_mod_tag_hud_primitive(at,-1);
    }
}
static int draw_coop_hud(CPUState *cpu, uint32_t address) {
    if (hud_call || !enrolled || failed || psx_mod_read_byte(PLAY)!=0x0A) return 0;
    /* A private pane contains its own native meters. P1 follows the original
     * path; P2 uses the same native HUD with its retained UI texture bank. */
    if(private_draw && !private_seat)return 0;
    hud_call=1;
    /* Arrival and voluntary departure fade this HUD. Dead players retain
     * their meters, making the shared-life/survivor state visible. */
    if (!private_draw && (life.status[1]==MMX6_COOP_LEAVING || life.status[1]==MMX6_COOP_ABSENT))
        p2_hud_fade=p2_hud_fade>8?p2_hud_fade-8:0;
    else if(!private_draw)p2_hud_fade=p2_hud_fade<120?p2_hud_fade+8:128;
    uint8_t current[sizeof p2.body];
    capture(PLAYER,current,sizeof current);
    uint32_t sprites_now=psx_mod_read_word(SCRATCH+0x1C);
    uint32_t menu_now=psx_mod_read_word(SCRATCH+0x3C);
    uint32_t saved_pointers[2]={sprites_now,menu_now};
    STATE_BYTES(restore_body,24,current,sizeof current);
    STATE_WORDS(restore_pointers,25,saved_pointers,2);
    if (zero_world) {
        project(PLAYER,p1.body,sizeof p1.body);
        psx_mod_write_word(SCRATCH+0x1C,saved_resources[1]);
        psx_mod_write_word(SCRATCH+0x3C,saved_resources[5]);
    }
    /* P1 and the boss HUD execute their original draw path exactly once. */
    uint32_t result=private_draw?0:guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    STATE_WORDS(restore_result,45,&result,1);
    if (zero_world) capture(PLAYER,p1.body,sizeof p1.body);
    else capture(PLAYER,current,sizeof current);
    STATE_UPDATE(restore_body,current);
    if (psx_mod_read_byte(PLAY+0x1F) && p2_hud_fade) {
        project(PLAYER,zero_world?current:p2.body,sizeof p2.body);
        psx_mod_write_word(SCRATCH+0x1C,assembly);
        psx_mod_write_word(SCRATCH+0x3C,menu_assembly);
        uint32_t pools[4];
        for (unsigned i=0;i<3;++i) pools[i]=psx_mod_read_word(SCRATCH+0x108+i*4);
        uint32_t arena=hud_packets+(psx_mod_read_word(SCRATCH)&1u)*0x8000;
        pools[3]=arena;STATE_WORDS(restore_pools,26,pools,4);
        for (unsigned i=0;i<3;++i) psx_mod_write_word(SCRATCH+0x108+i*4,arena+i*0x1000);
        hud_seat=1;
        if(private_draw)guest(cpu,address,0,0);
        else {
            guest(cpu,0x80024F90,PLAYER,0);
            guest(cpu,private_actor.character==MMX6_COOP_CHARACTER_ZERO?0x800249D4u:0x800246B4u,PLAYER,0);
        }
        hud_seat=0;
        hud_zero_packets(arena);
        for (unsigned i=0;i<3;++i) psx_mod_write_word(SCRATCH+0x108+i*4,pools[i]);
        STATE_POP(restore_pools);
        if (zero_world) capture(PLAYER,current,sizeof current);
        else capture(PLAYER,p2.body,sizeof p2.body);
    }
    project(PLAYER,current,sizeof current);
    psx_mod_write_word(SCRATCH+0x1C,sprites_now);
    psx_mod_write_word(SCRATCH+0x3C,menu_now);
    STATE_POP(restore_result);
    STATE_POP(restore_pointers);STATE_POP(restore_body);
    cpu->gpr[2]=result;
    hud_call=0;
    return 1;
}
#ifdef MMX6_COOP_MODERN_STATE
#include "mmx6_coop_snapshot.inc"
#endif
#include "mmx6_coop_views.inc"
#include "mmx6_coop_intro_placement.inc"
static void activate(void) {
    state_track.count=state_track.error=0;
    intro_camera_valid=0;memset(intro_camera_requests,0,sizeof intro_camera_requests);
#ifdef MMX6_COOP_MODERN_STATE
    snapshot_asset_valid=0;
    snapshot_discard_prepared();
#endif
    free(zero_compressed); zero_compressed=NULL; compressed_size=0;
    free(zero_ui_pixels); zero_ui_pixels=NULL;
    /* The SDK retires enhancement arenas, packet registrations and every
     * texture-bank ID before activation. No process-static address or cached
     * ID owns storage in the replacement session, even if its number recurs. */
    for (unsigned i=0;i<4096;++i) free(banks[i].pixels);
    memset(banks,0,sizeof banks);bank_count=0;
    memset(ui_banks,0,sizeof ui_banks);ui_bank_count=0;
    assets=assembly=palette_source=active_palette=packets=diagnostic=0;
    menu_memory=menu_assembly=hud_packets=world_packets=0;
    memset(&p1,0,sizeof p1);memset(&p2,0,sizeof p2);
    memset(saved_overlay,0,sizeof saved_overlay);memset(zero_overlay,0,sizeof zero_overlay);
    memset(saved_play,0,sizeof saved_play);memset(saved_camera,0,sizeof saved_camera);
    memset(saved_resources,0,sizeof saved_resources);saved_palette_dirty=0;
    memset(returning_body,0,sizeof returning_body);memset(scene_body,0,sizeof scene_body);
    refight_return_checkpoint=0;
    memset(saved_portrait_colors,0,sizeof saved_portrait_colors);
    subtank_seeded=subtank_found=0;memset(zero_subtanks,0,sizeof zero_subtanks);
    inside=ready=enrolled=failed=0;
    working_palette_assets_ready=0;
    memset(native_working_palettes,0,sizeof native_working_palettes);
    memset(working_palette_lengths,0,sizeof working_palette_lengths);
    frame_count=0; previous_input=p2_edges=0;
    mmx6_coop_lifecycle_init(&life); join_phase=arrival_pair=0;join_y=scene_y=0;
    player_call=stage_call=zero_world=world_render=0;
    pause_owner=-1; p2_start_previous=0;
    render_x_death=effect_call=shared_fx_call=shared_fx_allocate_call=0; memset(death_effect,0,sizeof death_effect);
    memset(shared_effect_owners,0,sizeof shared_effect_owners);
    hud_call=hud_seat=0;
    p2_hud_fade=128;
    pickup_call=0; memset(pickup_owners,0,sizeof pickup_owners);
    solid_call=solid_allocate_call=ride_call=0;
    memset(zero_solid_contacts,0,sizeof zero_solid_contacts);
    scene_owner=scene_phase=0; scene_call=zero_projected=0;
    both_door_reset();
    shared_clear_reset();
    memset(boss_balance,0,sizeof boss_balance);boss_balance_allocate_call=0;boss_balance_pending_actor=0;
    char balance[16];
    boss_balance_enabled=psx_mod_option_value("mmx6.local-coop","prototype","boss_balance",balance,sizeof balance) && !strcmp(balance,"on");
    char cooldowns[16];
    boss_balance_independent=boss_balance_enabled &&
        psx_mod_option_value("mmx6.local-coop","prototype","boss_cooldowns",cooldowns,sizeof cooldowns) &&
        !strcmp(cooldowns,"independent");
    char doors[16];
    both_doors=psx_mod_option_value("mmx6.local-coop","prototype","doors",doors,sizeof doors) &&
        !strcmp(doors,"both");
    char tanks[16];
    separate_subtanks=psx_mod_option_value("mmx6.local-coop","prototype","subtank_energy",tanks,sizeof tanks) &&
        !strcmp(tanks,"independent");
    char armor[16];partner_x_armor=MMX6_COOP_FORM_X;
    if(psx_mod_option_value("mmx6.local-coop","prototype","partner_x_armor",armor,sizeof armor)) {
        if(!strcmp(armor,"falcon"))partner_x_armor=MMX6_COOP_FORM_FALCON;
        else if(!strcmp(armor,"shadow"))partner_x_armor=MMX6_COOP_FORM_SHADOW;
        else if(!strcmp(armor,"blade"))partner_x_armor=MMX6_COOP_FORM_BLADE;
        else if(strcmp(armor,"base"))failed=1;
    }
    unit_choices_call=target_projection_call=0;
    zero_menu_loaded=0;
    private_actor=default_private_actor;
    memset(zero_giga_backup,0,sizeof zero_giga_backup);
    assets=psx_mod_alloc_guest_memory(ASSET_SPACE,16);
    diagnostic=psx_mod_alloc_guest_memory(0x2000,16);
    packets=psx_mod_alloc_texture_packet_memory(FRAME_ARENA*2,16);
    hud_packets=psx_mod_alloc_texture_packet_memory(0x10000,16);
    menu_memory=psx_mod_alloc_gpu_dma_memory(MENU_STORAGE_BYTES,16);
    int audio_allocated=jump_audio_activate();
    failed=!(assets && diagnostic && packets && hud_packets && menu_memory && audio_allocated);
    if (diagnostic) for (unsigned i=0;i<0x2000;i+=4) psx_mod_write_word(diagnostic+i,0);
    checkpoint_reset();
    if (!psx_mod_set_function_replacement(0x80016C48,jump_audio_sound) ||
        !psx_mod_set_function_replacement(0x8005A9D4,jump_audio_keyon) ||
        !psx_mod_set_function_replacement(0x80055B14,jump_audio_status) ||
        !psx_mod_set_function_replacement(0x8001750C,jump_audio_stop)) failed=1;
    if (!psx_mod_set_function_replacement(0x80031474,enemy_hit)) failed=1;
    if (!psx_mod_set_function_replacement(0x8002BCCC,boss_balance_allocate)) failed=1;
    if (!psx_mod_set_function_replacement(0x800E9898,unit_choices)) failed=1;
    if (!psx_mod_set_function_replacement(0x800EB14C,intro_near_target)) failed=1;
    if (!psx_mod_set_function_replacement(0x800ED150,northpole_ice_admission) ||
        !psx_mod_set_function_replacement(0x800EBF18,northpole_ice_live)) failed=1;
    if (!psx_mod_set_function_replacement(0x800EC780,recycle_portal_contact) ||
        !psx_mod_set_function_replacement(0x800EC8F8,recycle_portal_departure_wait) ||
        !psx_mod_set_function_replacement(0x800EC860,refight_portal_contact) ||
        !psx_mod_set_function_replacement(0x800EC8E8,refight_portal_both_admission)) failed=1;
    if (!psx_mod_set_function_replacement(0x80029598,camera_target) ||
        !psx_mod_set_function_replacement(0x80029658,camera_target)) failed=1;
    if (!psx_mod_set_function_replacement(0x8002CBFC,intro_guest_geometry_lifetime)) failed=1;
    if (!psx_mod_set_function_replacement(0x80034DCC,player_tick) ||
        !psx_mod_set_function_replacement(0x8001E9EC,stage_tick) ||
        !psx_mod_set_function_replacement(0x80020A08,ride_tick) ||
        !psx_mod_set_function_replacement(0x800232D4,render_survivor) ||
        !psx_mod_set_function_replacement(0x8002619C,render_armor_survivor)) failed=1;
    if (!psx_mod_set_function_replacement(0x80014F70,working_palette_native_load)) failed=1;
    if (!psx_mod_set_function_replacement(0x80030ECC,player_contact)) failed=1;
    if (!psx_mod_set_function_replacement(0x80031DA8,solid_player_collision) ||
        !psx_mod_set_function_replacement(0x8002BFD0,solid_allocate) ||
        !psx_mod_set_function_replacement(0x8002C4C4,solid_allocate) ||
        !psx_mod_set_function_replacement(0x8002C32C,solid_allocate)) failed=1;
    if (!psx_mod_set_function_replacement(0x8004E26C,pickup_collect) ||
        !psx_mod_set_function_replacement(0x8004DCB8,pickup_tick) ||
        /* Reploids have their own contact and delayed-healing routines.
         * Their native state machine uses the same waiting/healing phases;
         * keep the collector projected until that player's heal completes. */
        !psx_mod_set_function_replacement(0x8004EECC,pickup_collect) ||
        !psx_mod_set_function_replacement(0x8004EC30,pickup_tick)) failed=1;
    if (!psx_mod_set_function_replacement(0x80040800,nightmare_soul)) failed=1;
    if (!psx_mod_set_function_replacement(0x80050250,door_begin) ||
        !psx_mod_set_function_replacement(0x80050DFC,door_update) ||
        !psx_mod_set_function_replacement(0x80050C88,door_eligibility)) failed=1;
    if (!psx_mod_set_function_replacement(0x80051924,interaction_begin) ||
        !psx_mod_set_function_replacement(0x80052F64,interaction_begin) ||
        !psx_mod_set_function_replacement(0x80051890,capsule_owner_update)) failed=1;
    if (!psx_mod_set_function_replacement(0x800244C0,draw_coop_hud) ||
        !psx_mod_set_function_replacement(0x80024CC0,hud_icon)) failed=1;
    if (!psx_mod_set_function_replacement(0x8002C530,death_effect_allocate) ||
        !psx_mod_set_function_replacement(0x80047E34,death_effect_init)) failed=1;
    if (!psx_mod_set_function_replacement(0x8002C398,shared_effect_allocate) ||
        !psx_mod_set_function_replacement(0x80049100,shared_effect_callback) ||
        !psx_mod_set_function_replacement(0x80049478,shared_effect_callback) ||
        !psx_mod_set_function_replacement(0x8004AE1C,shared_effect_callback) ||
        !psx_mod_set_function_replacement(0x8004B3A0,shared_effect_callback) ||
        !psx_mod_set_function_replacement(0x801EE254,shared_effect_callback)) failed=1;
    independent_activate();
    fprintf(stdout,"mmx6 co-op: development prototype active (OpenGL rendering required)\n");
}
PSX_MOD_CONSTRUCTOR(mmx6_register_coop_plugin) {
    (void)psx_mod_register_session_reset_plugin("mmx6.local-coop.prototype",mmx6_adaptive_background_reset);
    static const PSXModNetplayProfile netplay_profile = {
        .plugin_id = "mmx6.local-coop.prototype",
        .compatibility_id = MMX6_HOST_LAB_TITLE_COMPATIBILITY,
        .rollback_supported = 0,
        .savestates_supported = 0,
        .skip_bios_intro = 1,
        .fixed_aspect_mask = 7,
        .widescreen_plugin_id = "mmx6.widescreen",
#if defined(PSX_MOD_NETPLAY_SETTINGS_LOADING_API) && PSX_MOD_NETPLAY_SETTINGS_LOADING_API >= 1
        .settings_package_id = "mmx6.local-coop",
        .settings_feature_id = "prototype",
#endif
#ifdef MMX6_COOP_MODERN_STATE
        .state_digest = state_digest,
        .requires_retained_texture_banks = 1,
#endif
        .loading_package_id = "mmx6.enhancement.seamless-loading",
        .loading_feature_id = "seamless-loading",
        .loading_plugin_id = "mmx6.seamless",
#if defined(PSX_MOD_NETPLAY_HOST_CATALOG_API) && PSX_MOD_NETPLAY_HOST_CATALOG_API >= 2
        .host_profiles = mmx6_coop_lab_host_profiles
#endif
    };
    psx_mod_register_netplay_profile(&netplay_profile);
#ifdef MMX6_COOP_MODERN_STATE
    /* Online selects only the forced profile; offline selects its package.
     * The runtime guarantees that exactly one of these identities is active. */
    psx_mod_register_snapshot_provider("mmx6.local-coop",&snapshot_provider);
    psx_mod_register_snapshot_provider("mmx6.local-coop.prototype",&snapshot_provider);
    psx_mod_register_savestate_plugin("mmx6.local-coop.prototype",snapshot_resources_restored);
#endif
    psx_mod_register_activation_plugin("mmx6.local-coop.prototype",activate);
    psx_mod_register_instruction_plugin("mmx6.local-coop.prototype",0x800318F4u,0x9102005Cu,boss_balance_damage);
    for(unsigned i=0;i<sizeof boss_cooldown_sites/sizeof boss_cooldown_sites[0];++i)
        psx_mod_register_instruction_plugin("mmx6.local-coop.prototype",boss_cooldown_sites[i].address,
            boss_cooldown_sites[i].words[6],boss_balance_shared_cooldown);
    psx_mod_register_instruction_plugin("mmx6.local-coop.prototype",0x800EB310u,0x84830000u,weather_window_target);
    psx_mod_register_instruction_plugin("mmx6.local-coop.prototype",0x800EF510u,0x0C0196DDu,sigma_special_target);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x8002012C,controller);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x800232D4,render);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x80025FB0,begin_world_draw);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x8002927C,independent_camera_begin);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x80029D18,intro_guest_placement_scan);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x800270D0,independent_background_begin);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x80026ECC,independent_background_end);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x8002B3D4,shared_palette_load);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x8003BD24,native_player_init);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x8001E1BC,checkpoint_native_entry);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x8003D308,script_begin);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x8002820C,camera_pits);
}
