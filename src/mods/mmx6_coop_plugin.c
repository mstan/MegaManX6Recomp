/* Local co-op development plugin. Not part of the preloaded release catalog.
 * The native world still runs once. A second player pass projects a host-owned
 * context into the game's singleton player addresses, then restores P1.
 * Resource evidence: SLUS-01395 USA v1.1, Tweaks workbook IngameTable and
 * FilesIndex; instruction boundaries verified against the original executable.
 */
#include "mod_plugins.h"
#include "cpu_state.h"
#include "sio.h"
#include "gpu.h"
#include "mmx6_coop_assets.h"
#include "mmx6_coop_lifecycle.h"
#include "mmx6_coop_sprite_packet.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PLAYER 0x800970A0u
#define PLAY 0x800CCED0u
#define OVERLAY 0x801EA000u
#define OVERLAY_SIZE 0xB000u
#define SCRATCH 0x1F800000u
#define ASSET_SPACE 0x80000u
#define FRAME_ARENA 0x20000u

typedef struct {
    uint8_t body[0x158];
    uint8_t shots[0x1400];
    uint8_t trails[0x120];
    uint8_t effects[0xF0];
} PlayerContext;
typedef struct { uint32_t source; uint16_t id, tile; uint8_t colors[32]; } SpriteBank;
static PlayerContext p2, p1;
static uint8_t saved_overlay[OVERLAY_SIZE], zero_overlay[OVERLAY_SIZE];
static uint8_t saved_play[0xE0], saved_camera[0x100];
static uint8_t *zero_compressed;
static size_t compressed_size;
static uint32_t assets, assembly, palette_source, active_palette, packets, diagnostic;
static uint32_t saved_resources[7], frame_count;
static uint32_t menu_memory, menu_assembly;
enum { MENU_PORTRAIT=0x10800, MENU_PORTRAIT_COLORS=0x12800, MENU_BYTES=0x12A00 };
static uint8_t saved_portrait_colors[0x200];
static int zero_menu_loaded;
static uint8_t saved_palette_dirty;
static uint16_t previous_input, p2_edges;
static SpriteBank banks[4096];
static unsigned bank_count;
static int inside, ready, enrolled, failed;
static Mmx6CoopLifecycle life;
static uint8_t returning_body[0x158];
static unsigned join_phase;
static int32_t join_y;
static int player_call, stage_call, zero_world, world_render;
static int pause_owner = -1, p2_start_previous;
static uint32_t world_packets;
static uint32_t hud_packets;
static int hud_call, hud_seat;
enum { P2_HUD_X=26 };
static unsigned p2_hud_fade=128;
static uint16_t *zero_ui_pixels;
typedef struct { uint16_t page, clut, uv, id, colors[16]; } UiBank;
static UiBank ui_banks[4096];
static unsigned ui_bank_count;
static int render_x_death, effect_call;
typedef struct { uint32_t x,y,assembly; uint8_t layer,valid; } DeathEffectOrigin;
static DeathEffectOrigin death_effect[96];
typedef struct { uint32_t actor; uint8_t seat; } PickupOwner;
static PickupOwner pickup_owners[128];
static int pickup_call;
/* Native stage solids keep one player's previous contact at +72/+76.
 * Keep Zero's copy on the host; +73/+77 still belong to the ride armor. */
typedef struct { uint8_t sides, carried; } SolidContact;
static SolidContact zero_solid_contacts[80];
static int solid_call, solid_allocate_call;
/* Scene transport is independent of voluntary absence and death. The owner
 * occupies the native singleton for the one world pass until control returns. */
static unsigned scene_owner, scene_phase;
static uint8_t scene_body[0x158];
static int32_t scene_y;
static int scene_call, zero_projected;

static int scene_passenger(unsigned seat) { return scene_phase && scene_owner!=seat+1; }

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
    uint32_t regs[32], data[32], ctrl[32];
    uint32_t pc=cpu->pc, hi=cpu->hi, lo=cpu->lo;
    memcpy(regs,cpu->gpr,sizeof regs);
    memcpy(data,cpu->gte_data,sizeof data);
    memcpy(ctrl,cpu->gte_ctrl,sizeof ctrl);
    cpu->pc=0; cpu->gpr[4]=a0; cpu->gpr[5]=a1;
    psx_dispatch_call(cpu,address,regs[31]);
    uint32_t result=cpu->gpr[2];
    memcpy(cpu->gpr,regs,sizeof regs);
    memcpy(cpu->gte_data,data,sizeof data);
    memcpy(cpu->gte_ctrl,ctrl,sizeof ctrl);
    cpu->pc=pc; cpu->hi=hi; cpu->lo=lo;
    return result;
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
static int load_assets(void) {
    uint32_t n;
    uint8_t *file=disc_file("ROCK_X6.BIN",&n);
    Mmx6AssetView v, graphics, sprites, palette;
    if (!file) return 0;
    if (!mmx6_coop_overlay(file,n,1,&v) || v.size>sizeof zero_overlay || v.type!=0x3D) {
        free(file); return 0;
    }
    memcpy(zero_overlay,v.data,v.size);
    free(file);
    file=disc_file("ROCK_X6.DAT",&n);
    if (!file) return 0;
    if (!mmx6_coop_dat_asset(file,n,85,3,&graphics) || graphics.type!=2 ||
        !mmx6_coop_dat_asset(file,n,85,10,&sprites) || sprites.type!=3 ||
        !mmx6_coop_dat_asset(file,n,85,0,&palette) || palette.type!=9 ||
        graphics.size+sprites.size+palette.size+0x4040>ASSET_SPACE) { free(file); return 0; }
    zero_compressed=malloc(graphics.size);
    if (!zero_compressed) { free(file); return 0; }
    memcpy(zero_compressed,graphics.data,graphics.size); compressed_size=graphics.size;
    assembly=assets+(((uint32_t)graphics.size+15u) & ~15u);
    palette_source=assembly+(((uint32_t)sprites.size+15u) & ~15u);
    active_palette=palette_source+(((uint32_t)palette.size+15u) & ~15u);
    project(assets,graphics.data,graphics.size);
    project(assembly,sprites.data,sprites.size);
    project(palette_source,palette.data,palette.size);
    project(active_palette,palette.data,palette.size);
    Mmx6AssetView menu_gfx, menu_font, menu_colors, menu_layout, portrait, portrait_colors;
    if (!mmx6_coop_dat_asset(file,n,85,6,&menu_gfx) || menu_gfx.size!=0x8000 ||
        !mmx6_coop_dat_asset(file,n,85,7,&menu_font) || menu_font.size!=0x8000 ||
        !mmx6_coop_dat_asset(file,n,85,8,&menu_colors) || menu_colors.size!=0x800 ||
        !mmx6_coop_dat_asset(file,n,85,9,&menu_layout) ||
        !mmx6_coop_dat_record(file,n,165,&portrait) || portrait.size!=0x2000 ||
        !mmx6_coop_dat_record(file,n,166,&portrait_colors) || portrait_colors.size!=0x200) {
        free(file); return 0;
    }
    menu_assembly=active_palette+0x4000;
    if (menu_assembly-assets+menu_layout.size>ASSET_SPACE) { free(file); return 0; }
    project(menu_memory,menu_gfx.data,menu_gfx.size);
    project(menu_memory+0x8000,menu_font.data,menu_font.size);
    project(menu_memory+0x10000,menu_colors.data,menu_colors.size);
    project(menu_memory+MENU_PORTRAIT,portrait.data,portrait.size);
    project(menu_memory+MENU_PORTRAIT_COLORS,portrait_colors.data,portrait_colors.size);
    project(menu_assembly,menu_layout.data,menu_layout.size);
    zero_ui_pixels=calloc(1024*512,sizeof *zero_ui_pixels);
    Mmx6AssetView common, icons;
    if (!zero_ui_pixels || !mmx6_coop_dat_asset(file,n,85,1,&common) ||
        !mmx6_coop_dat_asset(file,n,85,2,&icons) || !ui_upload(&common) ||
        !ui_upload(&icons) || !ui_upload(&menu_gfx) || !ui_upload(&menu_font)) {
        free(file); return 0;
    }
    free(file);
    fprintf(stdout,"mmx6 co-op: Zero resources loaded; status/input at %08X\n",diagnostic);
    fflush(stdout);
    return 1;
}
static void enter_zero(void) {
    capture_player(&p1);
    capture(OVERLAY,saved_overlay,sizeof saved_overlay);
    capture(PLAY,saved_play,sizeof saved_play);
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
    psx_mod_write_word(SCRATCH+0x14,assets);
    psx_mod_write_word(SCRATCH+0x1C,assembly);
    psx_mod_write_word(SCRATCH+0x24,palette_source);
    psx_mod_write_word(SCRATCH+0x28,active_palette);
    psx_mod_write_word(SCRATCH+0x38,menu_memory+0x10000);
    psx_mod_write_word(SCRATCH+0x3C,menu_assembly);
    if (zero_menu_loaded) psx_mod_write_word(SCRATCH+0xA8,menu_memory+MENU_PORTRAIT_COLORS);
    psx_mod_write_byte(PLAY+0x38,1);
    psx_mod_write_byte(PLAY+0x5E,5);
    zero_projected=1;
}
static void leave_zero_context(int shared_world) {
    capture_player(&p2);
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
    } else {
        project(PLAY,saved_play,sizeof saved_play);
        project(0x800971F8,saved_camera,sizeof saved_camera);
    }
    zero_projected=0;
}
static void leave_zero(void) { leave_zero_context(0); }

/* Pickup routines only need a body and character identity. Keep all native
 * shared changes (life count, tanks, collection flags and heal freeze) while
 * projecting the collector, including when Zero owns the world pass. */
static uint32_t pickup_as_seat(CPUState *cpu, uint32_t address, uint32_t actor, unsigned seat) {
    unsigned resident=zero_world?1:0;
    if (seat==resident) return guest(cpu,address,actor,0);
    uint8_t body[sizeof p2.body], character=psx_mod_read_byte(PLAY+0x38);
    uint8_t armor=psx_mod_read_byte(PLAY+0x5E);
    uint8_t *other=seat?p2.body:p1.body;
    capture(PLAYER,body,sizeof body);
    project(PLAYER,other,sizeof body);
    psx_mod_write_byte(PLAY+0x38,seat?1:saved_play[0x38]);
    psx_mod_write_byte(PLAY+0x5E,seat?5:saved_play[0x5E]);
    uint32_t result=guest(cpu,address,actor,0);
    capture(PLAYER,other,sizeof body);
    project(PLAYER,body,sizeof body);
    psx_mod_write_byte(PLAY+0x38,character);
    psx_mod_write_byte(PLAY+0x5E,armor);
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
        result=pickup_as_seat(cpu,address,actor,seat);
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
        cpu->gpr[2]=pickup_as_seat(cpu,address,actor,pickup_owners[i].seat);
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
    project(PLAYER,seat?p2.body:p1.body,sizeof body);
    uint32_t result=guest(cpu,0x8002DCF4,actor,PLAYER);
    project(PLAYER,body,sizeof body);
    return result;
}
static int nightmare_soul(CPUState *cpu, uint32_t address) {
    uint32_t actor=cpu->gpr[4];
    if (pickup_call || !enrolled || failed || psx_mod_read_byte(actor+5)!=5 ||
        !psx_mod_read_byte(actor+0x8E)) return 0;
    pickup_call=1;
    unsigned seat=zero_world?1:0;
    uint32_t box=psx_mod_read_word(actor+0x68);
    psx_mod_write_word(actor+0x68,0x80075EE0); /* Native collectible soul box. */
    for (unsigned candidate=0;candidate<2;++candidate) {
        if (life.status[candidate]==MMX6_COOP_ALIVE && !scene_passenger(candidate) &&
            pickup_overlap(cpu,actor,candidate)) { seat=candidate; break; }
    }
    psx_mod_write_word(actor+0x68,box);
    /* Run this entity once. The original routine selects PLAY+D2/D4 from
     * the collector's character, retaining native soul values and rank data. */
    cpu->gpr[2]=pickup_as_seat(cpu,address,actor,seat);
    pickup_call=0;
    return 1;
}
static void enroll(CPUState *cpu) {
    uint32_t x=psx_mod_read_word(PLAYER+8), y=psx_mod_read_word(PLAYER+12);
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
    enrolled=1; previous_input=0;
    mmx6_coop_lifecycle_respawn(&life);
    join_phase=0;
    fprintf(stdout,"mmx6 co-op: Zero enrolled at (%u,%u)\n",x>>16,y>>16);
    fflush(stdout);
}

static int shared_camera(void) {
    return enrolled && !scene_owner && life.status[0]==MMX6_COOP_ALIVE && life.status[1]==MMX6_COOP_ALIVE &&
        psx_mod_read_byte(PLAYER+4)==1 && psx_mod_read_byte(PLAYER+5)>=2 &&
        !psx_mod_read_byte(PLAY+0x10) && !psx_mod_read_byte(PLAY+0x1C);
}
static void constrain_player(unsigned player) {
    if (!shared_camera()) return;
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
    if (inside || failed || !shared_camera()) return 0;
    unsigned axis=address==0x80029598u?8:12;
    uint32_t original=psx_mod_read_word(PLAYER+axis);
    int64_t midpoint=((int64_t)(int32_t)original+(int32_t)le32(p2.body+axis))/2;
    inside=1;
    psx_mod_write_word(PLAYER+axis,(uint32_t)midpoint);
    uint32_t result=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    psx_mod_write_word(PLAYER+axis,original);
    cpu->gpr[2]=result;
    inside=0;
    return 1;
}
static void clear_p2_combat(void) {
    memset(p2.shots,0,sizeof p2.shots);
    memset(p2.trails,0,sizeof p2.trails);
    memset(p2.effects,0,sizeof p2.effects);
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
static void start_join(CPUState *cpu) {
    memcpy(p2.body,returning_body,sizeof returning_body);
    put32(p2.body+8,psx_mod_read_word(PLAYER+8));
    join_y=(int32_t)psx_mod_read_word(PLAYER+12);
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
    join_phase=1;
}
static void join_animation(CPUState *cpu) {
    enter_zero();
    guest(cpu,0x80017A04,PLAYER,0);
    if (join_phase==1) {
        int32_t y=(int32_t)psx_mod_read_word(PLAYER+12)+8*65536;
        if (y>=join_y) {
            y=join_y;
            guest(cpu,0x8003BA04,PLAYER,2); /* Native beam resolves into Zero. */
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
static void diagnostics(uint16_t input) {
    ++frame_count;
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
}
static uint16_t p2_input(void) {
    uint16_t raw=(uint16_t)~sio_get_pad_buttons_slot(1);
    if (psx_mod_read_byte(diagnostic+0x30)) raw=(uint16_t)~psx_mod_read_half(diagnostic+0x34);
    return raw;
}
static void scene_begin(unsigned seat, uint32_t source) {
    if (scene_owner || !enrolled || life.status[seat]!=MMX6_COOP_ALIVE) return;
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
static void script_begin(CPUState *cpu, uint32_t address) {
    (void)cpu;
    if (!scene_call && !failed) scene_begin(zero_projected?1:0,address);
}
static int door_begin(CPUState *cpu, uint32_t address) {
    if (scene_call || inside || !enrolled || failed || scene_owner) return 0;
    uint32_t actor=cpu->gpr[4];
    scene_call=1;
    unsigned seat=0;
    uint32_t hit=life.status[0]==MMX6_COOP_ALIVE?guest(cpu,0x80050C88,actor,0):0;
    if (!hit && life.status[1]==MMX6_COOP_ALIVE) {
        inside=1;
        enter_zero();
        hit=guest(cpu,0x80050C88,actor,0);
        leave_zero();
        inside=0;
        if (hit) seat=1;
    }
    /* Probe only the pure native overlap test. Door AI, effects and room
     * changes still execute once, under the touching player's context. */
    if (seat) { inside=1; enter_zero(); }
    uint32_t result=guest(cpu,address,actor,cpu->gpr[5]);
    if (hit && psx_mod_read_byte(PLAYER+0xD4)) scene_begin(seat,address);
    if (seat) { leave_zero_context(1); inside=0; }
    scene_call=0;
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
    scene_call=1;
    uint8_t input[6];
    if (seat) {
        inside=1;
        capture(0x800C456C,input,sizeof input);
        enter_zero();
        uint16_t raw=p2_input(); raw=(uint16_t)((raw<<8)|(raw>>8));
        psx_mod_write_half(0x800C456C,raw);
        psx_mod_write_half(0x800C4570,p2_edges);
    }
    uint32_t result=guest(cpu,address,actor,cpu->gpr[5]);
    if (psx_mod_read_byte(PLAYER+0xD0) || psx_mod_read_byte(PLAY+0x10)==2)
        scene_begin(seat,address);
    if (seat) {
        leave_zero_context(1);
        project(0x800C456C,input,sizeof input);
        inside=0;
    }
    scene_call=0;
    cpu->gpr[2]=result;
    return 1;
}
static int scene_locked(const uint8_t *owner) {
    return owner[0xD0] || owner[0xD4] || owner[0x7A] ||
        psx_mod_read_byte(PLAY+0x10) || psx_mod_read_byte(PLAY+0x1C) ||
        psx_mod_read_byte(0x8008EAFC);
}
static void scene_tick(CPUState *cpu) {
    if (!scene_owner || !enrolled) return;
    unsigned seat=scene_owner-1, passenger=seat^1;
    uint8_t owner[sizeof scene_body];
    if (seat) memcpy(owner,p2.body,sizeof owner);
    else capture(PLAYER,owner,sizeof owner);
    int locked=scene_locked(owner);
    if (!scene_phase) {
        /* A voluntary departure already in flight still finishes, even if
         * native gameplay is now frozen for the other player's dialogue. */
        if (!seat && life.status[1]==MMX6_COOP_LEAVING) {
            int prior_inside=inside;
            inside=1;
            enter_zero();
            guest(cpu,0x8003674C,PLAYER,0);
            leave_zero();
            inside=prior_inside;
            if (p2.body[4]==3) mmx6_coop_teleport_done(&life);
        }
        if (!locked) scene_owner=0;
        return;
    }
    if (locked && scene_phase>=4) scene_phase=1;
    /* Wait for an actual grounded, controllable destination. Native door
     * and script locks, including chained boss dialogue, must all release. */
    int landing=!locked && owner[4]==1 && owner[5]>=2 &&
        !owner[0x67] && (owner[0x70]&8) && owner[0x5C];
    if (scene_phase==3 && !landing) return;
    int prior_inside=inside;
    inside=scene_call=1;
    uint8_t play[sizeof saved_play], camera[sizeof saved_camera];
    capture(PLAY,play,sizeof play);
    capture(0x800971F8,camera,sizeof camera);
    if (passenger) enter_zero();
    if (scene_phase==1) {
        if (passenger && life.status[1]==MMX6_COOP_JOINING) {
            uint32_t x=psx_mod_read_word(PLAYER+8);
            project(PLAYER,returning_body,sizeof returning_body);
            psx_mod_write_word(PLAYER+8,x);
            psx_mod_write_word(PLAYER+12,(uint32_t)join_y);
            life.status[1]=MMX6_COOP_ALIVE;
            join_phase=0;
        }
        capture(PLAYER,scene_body,sizeof scene_body);
        if (passenger) clear_p2_combat();
        /* Clear the resident pools too; they will be captured on projection
         * exit. Otherwise a cancelled saber can survive the teleport. */
        for (unsigned i=0;i<sizeof p2.shots;i+=4) psx_mod_write_word(0x800950A0+i,0);
        for (unsigned i=0;i<sizeof p2.trails;i+=4) psx_mod_write_word(0x800972F8+i,0);
        for (unsigned i=0;i<sizeof p2.effects;i+=4) psx_mod_write_word(0x800911A8+i,0);
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
                guest(cpu,0x8003BA04,PLAYER,2);
                scene_phase=5;
            }
            psx_mod_write_word(PLAYER+12,(uint32_t)y);
        } else if (!psx_mod_read_byte(PLAYER+0x46)) {
            guest(cpu,0x8003AD18,PLAYER,0);
            guest(cpu,0x8003CCBC,PLAYER,0);
            psx_mod_write_byte(PLAYER+0x61,60);
            scene_owner=scene_phase=0;
            life.select_frames=0;
        }
    }
    if (passenger) leave_zero();
    project(PLAY,play,sizeof play);
    project(0x800971F8,camera,sizeof camera);
    inside=prior_inside;
    scene_call=0;
}
static void diagnostic_setup(CPUState *cpu) {
    unsigned command=psx_mod_read_byte(diagnostic+0x50);
    /* Development-only fixture setup. The published host-body copy remains
     * read-only; a one-byte command commits the already-written payload. */
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
    zero_menu_loaded=zero;
}
static int player_tick(CPUState *cpu, uint32_t address) {
    if (inside || player_call || !enrolled || failed) return 0;
    uint8_t freeze[11];
    capture(PLAY+0x12,freeze,sizeof freeze);
    player_call=1;
    uint32_t result=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    player_call=0;
    if (psx_mod_read_byte(PLAYER+4)==2 || life.status[0]==MMX6_COOP_DYING) {
        mmx6_coop_fatal(&life,0);
        if (mmx6_coop_living(&life,1)) project(PLAY+0x12,freeze,sizeof freeze);
        if (psx_mod_read_byte(PLAYER+4)==3) life.status[0]=MMX6_COOP_FALLEN;
        psx_mod_write_byte(diagnostic+0x38,(uint8_t)life.status[0]);
        psx_mod_write_byte(diagnostic+0x3B,life.wipe);
    }
    cpu->gpr[2]=result;
    return 1;
}
static int stage_tick(CPUState *cpu, uint32_t address) {
    if (stage_call || inside || !enrolled || failed) return 0;
    diagnostic_setup(cpu);
    uint16_t raw=p2_input();
    int start=!!(raw&8), pressed=start&&!p2_start_previous;
    unsigned phase=psx_mod_read_byte(PLAY+1);
    p2_start_previous=start;
    if (!phase) {
        pause_owner=-1;
        /* Match the native pause gate. Simultaneous requests go to P1; an
         * absent/dead/departing actor cannot become the menu's owner. */
        if (!scene_owner && !psx_mod_read_byte(PLAY+0x1C) && !psx_mod_read_byte(PLAY+0x10) &&
            !psx_mod_read_byte(PLAY+0x0F) && !psx_mod_read_byte(0x80097424)) {
            if (life.status[0]==MMX6_COOP_ALIVE && (psx_mod_read_half(0x800C4570)&0x0800))
                pause_owner=0;
            else if (life.status[1]==MMX6_COOP_ALIVE && pressed) pause_owner=1;
        }
    } else if (phase==2) {
        life.select_frames=0;
        if (pause_owner<0) pause_owner=mmx6_coop_living(&life,0)?0:1;
    }
    psx_mod_write_byte(diagnostic+0x3C,(uint8_t)(pause_owner+1));
    int survivor=(!life.wipe || life.wipe==2) &&
        (life.status[0]==MMX6_COOP_DYING || life.status[0]==MMX6_COOP_FALLEN) &&
        life.status[1]!=MMX6_COOP_ABSENT && (life.wipe || life.status[1]!=MMX6_COOP_FALLEN);
    if (!survivor && pause_owner!=1 && scene_owner!=2) {
        stage_call=1;
        uint32_t result=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
        if (!psx_mod_read_byte(PLAY+1)) scene_tick(cpu);
        diagnostics((uint16_t)((raw<<8)|(raw>>8)));
        if (psx_mod_read_byte(PLAY)!=0x0A) enrolled=0;
        cpu->gpr[2]=result;
        stage_call=0;
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
        guest(cpu,0x80034DCC,0,0);
        project(PLAY+0x12,flags,sizeof flags);
        psx_mod_write_word(PLAY+0x90,timer);
        psx_mod_write_word(PLAY+0xCC,total);
        if (psx_mod_read_byte(PLAYER+4)==3) life.status[0]=MMX6_COOP_FALLEN;
    }
    uint8_t input[6];
    capture(0x800C456C,input,sizeof input);
    raw=(uint16_t)((raw<<8)|(raw>>8));
    enter_zero();
    route_p2_input(raw);
    zero_world=1;
    world_packets=packets+(psx_mod_read_word(SCRATCH)&1u)*FRAME_ARENA;
    uint32_t result=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    if (psx_mod_read_byte(PLAYER+4)==2) mmx6_coop_fatal(&life,1);
    if (life.status[1]==MMX6_COOP_DYING && psx_mod_read_byte(PLAYER+4)==3)
        life.status[1]=MMX6_COOP_FALLEN;
    zero_world=0;
    leave_zero_context(1);
    project(0x800C456C,input,sizeof input);
    if (!psx_mod_read_byte(PLAY+1)) scene_tick(cpu);
    diagnostics(raw);
    if (zero_menu_loaded && psx_mod_read_byte(PLAY+1)!=2) menu_vram(cpu,0);
    if (psx_mod_read_byte(PLAY)!=0x0A) enrolled=0;
    cpu->gpr[2]=result;
    stage_call=inside=0;
    return 1;
}
static void native_player_init(CPUState *cpu, uint32_t address) {
    (void)cpu; (void)address;
    if (inside) return;
    /* This is the native fresh-stage/checkpoint-respawn initialization, never
     * an ordinary door. The host body is enrolled after the new X body lands. */
    enrolled=0;
    scene_owner=scene_phase=0;
    memset(pickup_owners,0,sizeof pickup_owners);
    memset(zero_solid_contacts,0,sizeof zero_solid_contacts);
    mmx6_coop_lifecycle_respawn(&life);
    pause_owner=-1; p2_start_previous=0;
}
static void controller(CPUState *cpu, uint32_t address) {
    (void)address;
    if (inside || failed) return;
    /* Only the normal gameplay driver's post-player boundary. */
    if (cpu->gpr[31]!=0x80020C70u) return;
    if (scene_owner) { life.select_frames=0; return; }
    if (psx_mod_read_byte(PLAY)!=0x0A || !psx_mod_read_byte(PLAYER)) {
        enrolled=0; return;
    }
    if ((psx_mod_read_byte(PLAYER+4)!=2 &&
         (psx_mod_read_byte(PLAYER+4)!=1 || psx_mod_read_byte(PLAYER+5)<2)) ||
        psx_mod_read_byte(PLAY+0x10) || psx_mod_read_byte(PLAY+0x1C)) {
        life.select_frames=0; return;
    }
    /* The opening's scripted jump/dialogue also uses action >= 2. Wait for
     * the native idle handoff before first enrollment, including restarts. */
    if (!enrolled && (psx_mod_read_byte(PLAYER+4)!=1 || psx_mod_read_byte(PLAYER+5)!=2)) return;
    inside=1;
    if (!ready) {
        ready=load_assets();
        if (!ready) { failed=1; fprintf(stderr,"mmx6 co-op: resource validation failed\n"); }
    }
    if (ready && !enrolled) enroll(cpu);
    if (ready && enrolled) {
        constrain_player(0);
        uint16_t raw=p2_input();
        uint8_t saved_input[6];
        if (!stage_call) diagnostic_setup(cpu);
        int safe=!psx_mod_read_byte(PLAYER+0x67) && (psx_mod_read_byte(PLAYER+0x70)&8);
        Mmx6CoopJoinAction action=mmx6_coop_join_input(&life,raw&1,1,safe);
        if (action==MMX6_COOP_LEAVE) start_leave(cpu);
        else if (action==MMX6_COOP_JOIN) start_join(cpu);
        raw=(uint16_t)((raw<<8)|(raw>>8)); /* Native PadRead byte order. */
        if (life.status[1]==MMX6_COOP_JOINING) {
            join_animation(cpu);
            if (!stage_call) diagnostics(raw);
            inside=0; return;
        }
        if (life.status[1]==MMX6_COOP_ABSENT || life.status[1]==MMX6_COOP_FALLEN) {
            if (!stage_call) diagnostics(raw);
            inside=0; return;
        }
        capture(0x800C456C,saved_input,sizeof saved_input);
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
        leave_zero();
        if (life.status[1]==MMX6_COOP_LEAVING && p2.body[4]==3)
            mmx6_coop_teleport_done(&life);
        if (p2.body[4]==2) mmx6_coop_fatal(&life,1);
        if (life.status[1]==MMX6_COOP_DYING && p2.body[4]==3) life.status[1]=MMX6_COOP_FALLEN;
        constrain_player(1);
        project(0x800C456C,saved_input,sizeof saved_input);
        if (!stage_call) diagnostics(raw);
    }
    inside=0;
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
    if (clut<0x7800) return 0;
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
    palette_offset=(size_t)(clut-0x7800)*32;
    if (!tiles || tiles>256 ||
        palette_offset+32>0x4000) return 0;
    capture((render_x_death?saved_resources[3]:active_palette)+(uint32_t)palette_offset,colors,sizeof colors);
    for (unsigned i=0;i<bank_count;++i)
        if (banks[i].source==source && banks[i].tile==tile &&
            !memcmp(banks[i].colors,colors,sizeof colors)) return banks[i].id;
    if (render_x_death) capture(source,x_compressed,available);
    if (bank_count==4096 || !mmx6_coop_decode_sprite(compressed,
            available,decoded,sizeof decoded,&written) || written!=(size_t)tiles*128)
        return 0;
    memset(pixels,0,sizeof pixels);
    /* The native upload emits full 256-pixel rows, then a partial 16-high row. */
    unsigned remaining=tiles, row=0, in=0;
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
    uint16_t id=(uint16_t)(0x6000+bank_count);
    if (tile!=UINT16_MAX) {
        uint16_t tile_pixels[16*16];
        for (unsigned y=0;y<16;++y) for (unsigned x=0;x<16;++x)
            tile_pixels[y*16+x]=pixels[(((tile>>8)+y)&255)*256+(((tile&255)+x)&255)];
        if (!psx_mod_define_texture_bank(id,16,16,tile_pixels)) return 0;
    } else if (!psx_mod_define_texture_bank(id,256,256,pixels)) return 0;
    banks[bank_count].source=source; banks[bank_count].id=id;
    banks[bank_count].tile=tile;
    memcpy(banks[bank_count++].colors,colors,sizeof colors);
    return id;
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
static void render_actor(CPUState *cpu, uint32_t actor, uint32_t arena) {
    uint32_t base=psx_mod_read_word(SCRATCH+0x100);
    uint32_t mode=psx_mod_read_word(SCRATCH+0x104);
    guest(cpu,0x800232D4,actor,0);
    uint32_t end=psx_mod_read_word(SCRATCH+0x100);
    if (end<base || end-arena>40000 || (end-base)%40) {
        failed=1; return;
    }
    uint32_t table=psx_mod_read_word(actor+0x38);
    unsigned frame=psx_mod_read_byte(actor+0x47);
    /* Native saber actors share the player's uploaded frame, with their own
     * assembly and palette (801ED4F4); they have no decompression pointer. */
    if (!table && psx_mod_read_word(actor+0x3C)==le32(p2.body+0x3C) &&
        psx_mod_read_half(actor+0x40)==(uint16_t)(p2.body[0x40]|p2.body[0x41]<<8)) {
        table=zero_world?psx_mod_read_word(PLAYER+0x38):le32(p2.body+0x38);
        frame=zero_world?psx_mod_read_byte(PLAYER+0x47):p2.body[0x47];
    }
    /* Common effects use the stage's already resident textures. Only native
     * Zero frames need the retained host bank instead of X's texture slot. */
    if (!render_x_death && (table<assets || table-assets>=compressed_size)) return;
    uint32_t expanded=arena+40000+(base-arena)*2;
    for (uint32_t at=base;at<end;at+=40,expanded+=80,mode+=8) {
        uint32_t q[10];
        for (unsigned i=0;i<10;++i) q[i]=psx_mod_read_word(at+i*4);
        uint16_t tile;
        int supported=mmx6_coop_sprite_quad(q,&tile);
        if (tile!=UINT16_MAX)
            q[5]|=(psx_mod_read_word(mode+4)&0x60u)<<16;
        uint16_t bank=supported?sprite_bank(table,frame,(uint16_t)(q[3]>>16),tile):0;
        /* Native OT links still address the original tag. Turn it into a
         * zero-command link to two tagged GT3 packets in our own DMA arena. */
        if (bank) {
            triangle(expanded,expanded+40,q,0,1,2,bank);
            triangle(expanded+40,q[0],q,2,1,3,bank);
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
}
static void render(CPUState *cpu, uint32_t address) {
    (void)address;
    if (inside || failed || !enrolled || cpu->gpr[4]!=PLAYER || !p2.body[3] ||
        life.status[1]==MMX6_COOP_ABSENT || life.status[1]==MMX6_COOP_FALLEN ||
        psx_mod_read_byte(PLAY)!=0x0A || !psx_mod_texture_banks_supported()) return;
    inside=1;
    uint32_t original=psx_mod_read_word(SCRATCH+0x100);
    uint32_t base=packets+(psx_mod_read_word(SCRATCH)&1u)*FRAME_ARENA;
    capture_player(&p1);
    project_player(&p2);
    psx_mod_write_word(SCRATCH+0x100,base);
    render_actor(cpu,PLAYER,base);
    for (unsigned i=0;i<32 && !failed;++i) {
        uint32_t actor=0x800950A0u+i*0xA0;
        if (psx_mod_read_byte(actor+3)) render_actor(cpu,actor,base);
    }
    uint32_t end=psx_mod_read_word(SCRATCH+0x100);
    psx_mod_write_word(SCRATCH+0x100,original);
    project_player(&p1);
    psx_mod_write_word(diagnostic+28,bank_count);
    psx_mod_write_word(diagnostic+32,(end-base)/40);
    inside=0;
}
static int render_survivor(CPUState *cpu, uint32_t address) {
    if (!zero_world || world_render) return 0;
    uint32_t actor=cpu->gpr[4];
    if (actor!=PLAYER && !(actor>=0x800950A0 && actor<0x800964A0)) return 0;
    world_render=1;
    uint32_t original=psx_mod_read_word(SCRATCH+0x100);
    uint32_t arena=packets+(psx_mod_read_word(SCRATCH)&1u)*FRAME_ARENA;
    psx_mod_write_word(SCRATCH+0x100,world_packets);
    render_actor(cpu,actor,arena);
    if (actor==PLAYER && (life.status[0]==MMX6_COOP_DYING || scene_passenger(0)) && p1.body[3]) {
        uint8_t zero_body[sizeof p2.body];
        capture(PLAYER,zero_body,sizeof zero_body);
        project(PLAYER,p1.body,sizeof p1.body);
        render_x_death=1;
        render_actor(cpu,PLAYER,arena);
        render_x_death=0;
        project(PLAYER,zero_body,sizeof zero_body);
    }
    world_packets=psx_mod_read_word(SCRATCH+0x100);
    psx_mod_write_word(SCRATCH+0x100,original);
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
        o->valid=0;
        if (caller==0x8003DB0C || caller==0x8003DB8C) {
            o->x=psx_mod_read_word(PLAYER+8); o->y=psx_mod_read_word(PLAYER+12);
            o->layer=psx_mod_read_byte(PLAYER+0x14);
            o->assembly=psx_mod_read_word(SCRATCH+0x1C);
            o->valid=1;
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
    psx_mod_write_word(PLAYER+8,o->x); psx_mod_write_word(PLAYER+12,o->y);
    psx_mod_write_byte(PLAYER+0x14,o->layer); psx_mod_write_word(SCRATCH+0x1C,o->assembly);
    effect_call=1;
    uint32_t result=guest(cpu,address,actor,cpu->gpr[5]);
    effect_call=0;
    psx_mod_write_word(PLAYER+8,x); psx_mod_write_word(PLAYER+12,y);
    psx_mod_write_byte(PLAYER+0x14,layer); psx_mod_write_word(SCRATCH+0x1C,assembly_now);
    cpu->gpr[2]=result;
    return 1;
}
static int enemy_hit(CPUState *cpu, uint32_t address) {
    if (inside || !enrolled || failed || scene_owner || life.status[1]!=MMX6_COOP_ALIVE ||
        psx_mod_read_byte(PLAY)!=0x0A) return 0;
    inside=1;
    /* The caller owns enemy AI, invulnerability and applying this result.
     * Check P1 first; only a miss tries P2 with Zero's native hitbox tables.
     * Nested dispatch declines this replacement and executes the stock body. */
    uint32_t enemy=cpu->gpr[4], result=guest(cpu,address,enemy,cpu->gpr[5]);
    if (!result && p2.body[0x5C]) {
        enter_zero();
        result=guest(cpu,address,enemy,cpu->gpr[5]);
        leave_zero();
        if (result) psx_mod_write_word(diagnostic+40,psx_mod_read_word(diagnostic+40)+1);
    }
    cpu->gpr[2]=result;
    inside=0;
    return 1;
}
static int player_contact(CPUState *cpu, uint32_t address) {
    if (inside || !enrolled || failed || scene_owner || life.status[1]!=MMX6_COOP_ALIVE ||
        psx_mod_read_byte(PLAY)!=0x0A) return 0;
    inside=1;
    /* Native contact applies damage/knockback/iframes, then its caller handles
     * the enemy/projectile. Retry only a miss so a consumed projectile cannot
     * damage both actors and its AI still runs exactly once. */
    uint32_t actor=cpu->gpr[4], result=guest(cpu,address,actor,cpu->gpr[5]);
    if (!result && (p2.body[0x5C]&0x7F)) {
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
    if (actor<0x800C1220u || actor>=0x800C4560u || (actor-0x800C1220u)%0xA4) return NULL;
    return &zero_solid_contacts[(actor-0x800C1220u)/0xA4];
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
    psx_mod_write_byte(actor+0x72,contact->sides);
    psx_mod_write_byte(actor+0x76,contact->carried);
    uint32_t result=guest(cpu,address,actor,cpu->gpr[5]);
    contact->sides=psx_mod_read_byte(actor+0x72);
    contact->carried=psx_mod_read_byte(actor+0x76);
    psx_mod_write_byte(actor+0x72,sides);
    psx_mod_write_byte(actor+0x76,carried);
    return result;
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
        if (life.status[1]==MMX6_COOP_ALIVE && !scene_passenger(1) && p2.body[4]==1) {
            inside=1;
            enter_zero();
            /* 31DA8 also resolves the shared ride armor. That part already
             * ran above; the extra call handles only the second player. */
            uint8_t ride=psx_mod_read_byte(0x800CD340);
            psx_mod_write_byte(0x800CD340,0);
            solid_as_zero(cpu,address,actor,contact);
            psx_mod_write_byte(0x800CD340,ride);
            leave_zero();
            inside=0;
        } else memset(contact,0,sizeof *contact);
    }
    cpu->gpr[2]=result;
    solid_call=0;
    return 1;
}
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
    uint32_t expanded=arena+0x3000, mode=arena+0x1000;
    for (uint32_t at=arena;at<sprites;at+=16,mode+=8,expanded+=80) {
        uint32_t link=psx_mod_read_word(at), uv=psx_mod_read_word(at+12);
        uint16_t page=(uint16_t)psx_mod_read_word(mode+4);
        uint16_t bank=hud_tile_bank(page,(uint16_t)(uv>>16),(uint16_t)uv);
        if (!bank || expanded+80>arena+0x8000) { failed=1; return; }
        int x=(int16_t)psx_mod_read_half(at+8)+P2_HUD_X;
        int y=(int16_t)psx_mod_read_half(at+10);
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
        for (unsigned xy=8;xy<=32;xy+=8)
            psx_mod_write_half(at+xy,(uint16_t)(psx_mod_read_half(at+xy)+P2_HUD_X));
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
    hud_call=1;
    /* Only voluntary presence changes fade this HUD. Dead players retain
     * their meters, making the shared-life/survivor state visible. */
    if (life.status[1]==MMX6_COOP_LEAVING || life.status[1]==MMX6_COOP_ABSENT)
        p2_hud_fade=p2_hud_fade>8?p2_hud_fade-8:0;
    else p2_hud_fade=p2_hud_fade<120?p2_hud_fade+8:128;
    uint8_t current[sizeof p2.body];
    capture(PLAYER,current,sizeof current);
    uint32_t sprites_now=psx_mod_read_word(SCRATCH+0x1C);
    uint32_t menu_now=psx_mod_read_word(SCRATCH+0x3C);
    if (zero_world) {
        project(PLAYER,p1.body,sizeof p1.body);
        psx_mod_write_word(SCRATCH+0x1C,saved_resources[1]);
        psx_mod_write_word(SCRATCH+0x3C,saved_resources[5]);
    }
    /* P1 and the boss HUD execute their original draw path exactly once. */
    uint32_t result=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    if (zero_world) capture(PLAYER,p1.body,sizeof p1.body);
    else capture(PLAYER,current,sizeof current);
    if (psx_mod_read_byte(PLAY+0x1F) && p2_hud_fade) {
        project(PLAYER,zero_world?current:p2.body,sizeof p2.body);
        psx_mod_write_word(SCRATCH+0x1C,assembly);
        psx_mod_write_word(SCRATCH+0x3C,menu_assembly);
        uint32_t pools[3];
        for (unsigned i=0;i<3;++i) pools[i]=psx_mod_read_word(SCRATCH+0x108+i*4);
        uint32_t arena=hud_packets+(psx_mod_read_word(SCRATCH)&1u)*0x8000;
        for (unsigned i=0;i<3;++i) psx_mod_write_word(SCRATCH+0x108+i*4,arena+i*0x1000);
        hud_seat=1;
        guest(cpu,0x80024F90,PLAYER,0);
        guest(cpu,0x800249D4,PLAYER,0);
        hud_seat=0;
        hud_zero_packets(arena);
        for (unsigned i=0;i<3;++i) psx_mod_write_word(SCRATCH+0x108+i*4,pools[i]);
        if (zero_world) capture(PLAYER,current,sizeof current);
        else capture(PLAYER,p2.body,sizeof p2.body);
    }
    project(PLAYER,current,sizeof current);
    psx_mod_write_word(SCRATCH+0x1C,sprites_now);
    psx_mod_write_word(SCRATCH+0x3C,menu_now);
    cpu->gpr[2]=result;
    hud_call=0;
    return 1;
}
static void activate(void) {
    free(zero_compressed); zero_compressed=NULL; compressed_size=0;
    free(zero_ui_pixels); zero_ui_pixels=NULL; ui_bank_count=0;
    inside=ready=enrolled=failed=0;
    bank_count=frame_count=0; previous_input=p2_edges=0;
    mmx6_coop_lifecycle_init(&life); join_phase=0;
    player_call=stage_call=zero_world=world_render=0;
    pause_owner=-1; p2_start_previous=0;
    render_x_death=effect_call=0; memset(death_effect,0,sizeof death_effect);
    hud_call=hud_seat=0;
    p2_hud_fade=128;
    pickup_call=0; memset(pickup_owners,0,sizeof pickup_owners);
    solid_call=solid_allocate_call=0;
    memset(zero_solid_contacts,0,sizeof zero_solid_contacts);
    scene_owner=scene_phase=0; scene_call=zero_projected=0;
    zero_menu_loaded=0;
    assets=psx_mod_alloc_guest_memory(ASSET_SPACE,16);
    diagnostic=psx_mod_alloc_guest_memory(0x2000,16);
    packets=psx_mod_alloc_texture_packet_memory(FRAME_ARENA*2,16);
    hud_packets=psx_mod_alloc_texture_packet_memory(0x10000,16);
    menu_memory=psx_mod_alloc_gpu_dma_memory(MENU_BYTES*2,16);
    failed=!(assets && diagnostic && packets && hud_packets && menu_memory);
    if (!psx_mod_set_function_replacement(0x80031474,enemy_hit)) failed=1;
    if (!psx_mod_set_function_replacement(0x80029598,camera_target) ||
        !psx_mod_set_function_replacement(0x80029658,camera_target)) failed=1;
    if (!psx_mod_set_function_replacement(0x80034DCC,player_tick) ||
        !psx_mod_set_function_replacement(0x8001E9EC,stage_tick) ||
        !psx_mod_set_function_replacement(0x800232D4,render_survivor)) failed=1;
    if (!psx_mod_set_function_replacement(0x80030ECC,player_contact)) failed=1;
    if (!psx_mod_set_function_replacement(0x80031DA8,solid_player_collision) ||
        !psx_mod_set_function_replacement(0x8002C4C4,solid_allocate)) failed=1;
    if (!psx_mod_set_function_replacement(0x8004E26C,pickup_collect) ||
        !psx_mod_set_function_replacement(0x8004DCB8,pickup_tick)) failed=1;
    if (!psx_mod_set_function_replacement(0x80040800,nightmare_soul)) failed=1;
    if (!psx_mod_set_function_replacement(0x80050250,door_begin)) failed=1;
    if (!psx_mod_set_function_replacement(0x80051924,interaction_begin) ||
        !psx_mod_set_function_replacement(0x80052F64,interaction_begin)) failed=1;
    if (!psx_mod_set_function_replacement(0x800244C0,draw_coop_hud) ||
        !psx_mod_set_function_replacement(0x80024CC0,hud_icon)) failed=1;
    if (!psx_mod_set_function_replacement(0x8002C530,death_effect_allocate) ||
        !psx_mod_set_function_replacement(0x80047E34,death_effect_init)) failed=1;
    fprintf(stdout,"mmx6 co-op: development prototype active (OpenGL rendering required)\n");
}
PSX_MOD_CONSTRUCTOR(mmx6_register_coop_plugin) {
    psx_mod_register_activation_plugin("mmx6.local-coop.prototype",activate);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x8002012C,controller);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x800232D4,render);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x8003BD24,native_player_init);
    psx_mod_register_function_entry_plugin("mmx6.local-coop.prototype",0x8003D308,script_begin);
}
