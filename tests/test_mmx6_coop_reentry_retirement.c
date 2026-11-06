/* Actual stage_tick/guest callbacks with a source-bound scheduler escape.
 * The guest double models CloseThread/ChangeThread by longjmp; this is a
 * callback/state regression, never a native game qualification. */
#include <setjmp.h>
#include <stdint.h>
struct CPUState;
static jmp_buf retired_stack;
static int escape_stage,open_guest_menu;
static int reentry_dispatch(struct CPUState *,uint32_t,uint32_t);
#define MMX6_TEST_DISPATCH_CALL reentry_dispatch
#define main private_effects_fixture_main
#include "test_mmx6_coop_private_effects.c"
#undef main

static int reentry_dispatch(CPUState *cpu,uint32_t address,uint32_t ret) {
    (void)cpu;(void)ret;
    if(address==0x8001E9ECu && escape_stage)longjmp(retired_stack,1);
    if(address==0x80066150u && open_guest_menu) {
        CHECK(stage_call && inside && !zero_projected && !personal_pass);
        return 1; /* Native DrawSync before restoring the canonical menu bank. */
    }
    if(address==0x8001E9ECu && open_guest_menu)psx_mod_write_byte(PLAY+1,2);
    return 0;
}
static void abandoned_stage(CPUState *cpu) {
    setup(cpu);stage_call=0;state_track.count=state_track.error=0;
    pause_owner=0;scene_owner=scene_phase=0;menu_probe=2;
    cpu->gpr[31]=0x8001E720u;cpu->gpr[16]=PLAY;cpu->gpr[29]=0x801FF000u;cpu->gpr[4]=PLAY;
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+1,2);
    escape_stage=1;
    if(!setjmp(retired_stack)) {
        (void)stage_tick(cpu,0x8001E9ECu);CHECK(0);
    }
    escape_stage=0;
    CHECK(stage_call==1 && state_track.count==2 && !state_track.error);
    CHECK(state_track.frame[0].tag==29 && state_track.frame[1].tag==1);
    CHECK(!inside && !zero_world && !zero_projected && !player_call);
    /* New original root has entered major9. Its initializer has not yet
     * rewritten the resident body/resources, which must not be assumed. */
    cpu->gpr[31]=0x8001E26Cu;cpu->gpr[16]=PLAY;cpu->gpr[29]=0x801FF000u;
    psx_mod_write_word(cpu->gpr[29]+0x14,0x8001E720u);
    psx_mod_write_byte(PLAY,9);psx_mod_write_byte(PLAY+1,0);
}
static void refused(CPUState *cpu,uint32_t address) {
    uint32_t count=state_track.count,error=state_track.error;
    int guard=stage_call;uint8_t old_player[sizeof p2.body],old_play[0xE0];
    capture(PLAYER,old_player,sizeof old_player);capture(PLAY,old_play,sizeof old_play);
    CHECK(!retire_quit_stage(cpu,address));
    CHECK(stage_call==guard && state_track.count==count && state_track.error==error);
    CHECK(!memcmp(memory(PLAYER),old_player,sizeof old_player));
    CHECK(!memcmp(memory(PLAY),old_play,sizeof old_play));
}
static void saved_host_word(Mmx6StateFrame *frame,size_t index,uint32_t value) {
    memcpy(frame->saved+index*sizeof value,&value,sizeof value);
}
int main(void) {
    CPUState cpu;abandoned_stage(&cpu);
    uint32_t tick=frame_count;uint8_t resident[sizeof p2.body],campaign[0xE0];
    capture(PLAYER,resident,sizeof resident);capture(PLAY,campaign,sizeof campaign);
    native_player_init(&cpu,0x8003BD24u);
    CHECK(!stage_call && !state_track.count && !state_track.error && !enrolled);
    CHECK(frame_count==tick && pause_owner==-1);
    CHECK(!memcmp(resident,memory(PLAYER),sizeof resident));
    CHECK(!memcmp(campaign,memory(PLAY),sizeof campaign));
    CHECK(!retire_quit_stage(&cpu,0x8003BD24u)); /* Idempotent boundary. */
    enrolled=1;psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+1,0);
    cpu.gpr[31]=0x8001E720u;menu_probe=2;
    CHECK(stage_tick(&cpu,0x8001E9ECu));
    CHECK(frame_count>tick && !stage_call && !state_track.count && !state_track.error);
    /* The original P2 Start reaches its native callback and opens both menus. The
     * fixture supplies native phase2, with existing VRAM ownership modeled. */
    menu_probe=1;open_guest_menu=1;zero_menu_loaded=1;pad_buttons=(uint16_t)~8u;
    unsigned syncs=occurrences(0x80066150u);menu_vram_probe=1;
    psx_mod_write_half(menu_memory+MENU_BYTES,0x3821);
    psx_mod_write_half(menu_memory+MENU_PLAYER_BACKUP,0x5142);
    psx_mod_write_half(0x800C4570u,0);
    CHECK(stage_tick(&cpu,0x8001E9ECu));
    CHECK(pause_owner==0 && personal_active && personal_eligible==3 && !zero_menu_loaded);
    CHECK(psx_mod_read_byte(PLAY+1)==2 && !stage_call && !inside);
    CHECK(!state_track.count && !state_track.error && psx_mod_read_byte(diagnostic+0x3C)==2);
    CHECK(occurrences(0x80066150u)==syncs+1 && !gp0_upload_stage && !gp0_upload_left);
    CHECK(test_vram[256*1024+896]==0x3821 && test_vram[320]==0x5142);
    menu_vram_probe=0;open_guest_menu=0;

    /* Native task replacement can retire an ordinary gameplay or scene pass,
     * as well as the primary menu. Keep the same exact fresh root signature. */
    for(unsigned phase=0;phase<3;++phase) {
        abandoned_stage(&cpu);saved_host_word(&state_track.frame[0],1,phase);
        CHECK(retire_quit_stage(&cpu,0x8003BD24u));
        CHECK(!stage_call && !state_track.count && !state_track.error);
    }
    for(unsigned variant=0;variant<25;++variant) {
        abandoned_stage(&cpu);uint32_t address=0x8003BD24u;
        switch(variant) {
        case 0:address+=4;break;
        case 1:cpu.gpr[31]=0x8001D584u;break; /* Different original initializer. */
        case 2:cpu.gpr[16]=PLAYER;break;
        case 3:cpu.gpr[29]|=1;break;
        case 4:cpu.gpr[29]=0x7FFFFFFCu;break;
        case 5:cpu.gpr[29]=0x801FFFF0u;break;
        case 6:psx_mod_write_word(cpu.gpr[29]+0x14,0x8001E724u);break;
        case 7:psx_mod_write_byte(PLAY,10);break;
        case 8:psx_mod_write_byte(PLAY+1,2);break;
        case 9:inside=1;break;
        case 10:zero_projected=1;break;
        case 11:player_call=1;break;
        case 12:state_track.error=1;break;
        case 13:state_track.count=3;break;
        case 14:state_track.frame[0].tag=10;break;
        case 15:state_track.frame[0].words=0;break;
        case 16:state_track.frame[0].bytes=12;break;
        case 17:state_track.frame[1].tag=42;break;
        case 18:saved_host_word(&state_track.frame[1],99,0x8003BD24u);break;
        case 19:saved_host_word(&state_track.frame[1],31,0x80020C70u);break;
        case 20:saved_host_word(&state_track.frame[0],1,3);break;
        case 21:saved_host_word(&state_track.frame[0],3,1);break;
        case 22:saved_host_word(&state_track.frame[1],100,PLAYER);break;
        case 23:state_track.frame[1].bytes=100*4;break;
        case 24:state_track.frame[1].words=0;break;
        }
        refused(&cpu,address);
    }
    puts("Actual native reentry callback retirement checks passed");return 0;
}
