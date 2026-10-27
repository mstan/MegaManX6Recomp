/* Actual trusted plugin/codec against isolated guest memory, not game logic.
 * No ROM, runner, original card, transport or inherited gameplay evidence. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "psx_host_escape.h"
#include "mod_plugins.h"
static void *test_malloc(size_t bytes);
#define malloc test_malloc
#undef PSX_MOD_CONSTRUCTOR
#define PSX_MOD_CONSTRUCTOR(name) static void name(void)
#include "../src/mods/mmx6_coop_plugin.c"
#undef malloc
#define CHECK(x) do {if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
static int allocation_fail,allocation_calls,local_scope,texture_support=1;
static unsigned guest_calls,guest_writes,forgotten;
static int abandon_guest;
static int solid_dispatch,allocator_dispatch;
static int camera_dispatch;
static uint32_t expected_camera_axis;
static uint32_t audio_epoch=1;
static int foreign_audio23;
uint32_t psx_mod_spu_sample_bank_epoch(void){return audio_epoch;}
uint64_t psx_mod_spu_private_voice_owner(unsigned slot){
    CHECK(slot<24);
    return (JUMP_STOP_MASK&(1u<<slot))?JUMP_AUDIO_OWNER+(slot==23 && foreign_audio23):0;
}
int spu_get_private_voice_state(unsigned slot,SpuVoiceState *out){
    CHECK((slot==20 || slot==22 || slot==23) && out);memset(out,0,sizeof *out);
    if(slot==23 && foreign_audio23){out->active=1;out->sample_bank=29;}
    return 1;
}
static jmp_buf abandon_target;
static uint8_t ram[0x200000],extra[0x200000];
static uint16_t vram[1024*512];
static uint32_t texture_hash[8192],texture_width[8192];
static PSXModTextureBankResolver installed_resolver;
static void *test_malloc(size_t bytes) {++allocation_calls;return allocation_fail?NULL:malloc(bytes);}
static uint8_t *memory(uint32_t address) {
    if(address>=0x9F000000u && address<0x9F200000u)return extra+address-0x9F000000u;
    return ram+(address&0x1FFFFFu);
}
uint8_t psx_mod_read_byte(uint32_t a){return *memory(a);}
uint16_t psx_mod_read_half(uint32_t a){return (uint16_t)(*memory(a)|((uint16_t)*memory(a+1)<<8));}
uint32_t psx_mod_read_word(uint32_t a){return (uint32_t)psx_mod_read_half(a)|((uint32_t)psx_mod_read_half(a+2)<<16);}
void psx_mod_write_byte(uint32_t a,uint8_t v){++guest_writes;*memory(a)=v;}
void psx_mod_write_half(uint32_t a,uint16_t v){psx_mod_write_byte(a,(uint8_t)v);psx_mod_write_byte(a+1,(uint8_t)(v>>8));}
void psx_mod_write_word(uint32_t a,uint32_t v){for(unsigned i=0;i<4;++i)psx_mod_write_byte(a+i,(uint8_t)(v>>(i*8)));}
void psx_mod_write_code_word(uint32_t a,uint32_t v){psx_mod_write_word(a,v);}
int psx_mod_local_view_scope(void){return local_scope;}
int psx_mod_texture_banks_supported(void){return texture_support;}
const uint16_t *gpu_get_vram(void){return vram;}
int psx_mod_define_texture_bank(uint16_t id,uint32_t width,uint32_t height,const uint16_t *pixels){
    CHECK(id>=0x6000 && id<0x8000 && width==height && (width==16 || width==256));
    uint32_t h=2166136261u;for(uint32_t i=0;i<width*height;++i){h=(h^(pixels[i]&255))*16777619u;h=(h^(pixels[i]>>8))*16777619u;}
    texture_hash[id-0x6000]=h;texture_width[id-0x6000]=width;return 1;
}
void psx_mod_set_texture_bank_resolver(PSXModTextureBankResolver resolver){installed_resolver=resolver;}
int psx_mod_forget_texture_bank_range(uint16_t first,uint32_t count){
    CHECK(first==0x6000 && count==8192);memset(texture_hash,0,sizeof texture_hash);++forgotten;return 1;
}
void psx_dispatch_call(CPUState *cpu,uint32_t target,uint32_t ret){
    (void)target;(void)ret;++guest_calls;CHECK(state_track.count && !snapshot_ready());
    if(abandon_guest)longjmp(abandon_target,1);
    uint32_t h=state_digest();state_track.frame[state_track.count-1].saved[0]^=1;
    CHECK(state_digest()!=h);state_track.frame[state_track.count-1].saved[0]^=1;
    if(allocator_dispatch){cpu->gpr[2]=0x800950A0u+31*0xA0u;return;}
    if(camera_dispatch){
        unsigned axis=target==0x80029598u?8:12;
        CHECK((target==0x80029598u || target==0x80029658u) &&
              psx_mod_read_word(PLAYER+axis)==expected_camera_axis);
        cpu->gpr[2]=77;return;
    }
    if(solid_dispatch){
        uint32_t actor=cpu->gpr[4];CHECK(target==0x80031DA8u && actor==0x800950A0u);
        unsigned zero=psx_mod_read_byte(PLAYER+2);
        CHECK(psx_mod_read_byte(actor+0x72)==(zero?5:3));
        CHECK(psx_mod_read_byte(actor+0x76)==(zero?6:4));
        psx_mod_write_byte(actor+0x72,(uint8_t)(zero?11:9));
        psx_mod_write_byte(actor+0x76,(uint8_t)(zero?255:10));
        psx_mod_write_word(PLAYER+8,zero?222:111);
        cpu->gpr[2]=zero?17:42;return;
    }
    cpu->gpr[2]=42;cpu->gpr[3]^=123;cpu->pc=0x80012340;
}

static void setup(void){
    memset(&p2,0,sizeof p2);mmx6_coop_lifecycle_init(&life);
    ready=enrolled=1;failed=0;pause_owner=1;zero_menu_loaded=1;
    assets=0x9F000000;assembly=assets+0x100;palette_source=assets+0x200;active_palette=assets+0x300;
    packets=0x9F100000;diagnostic=0x9F080000;hud_packets=0x9F140000;menu_memory=0x9F180000;menu_assembly=assets+0x10000;
    compressed_size=64;zero_compressed=malloc(compressed_size);CHECK(zero_compressed);memset(zero_compressed,0x53,compressed_size);
    zero_ui_pixels=calloc(1024*512,sizeof *zero_ui_pixels);CHECK(zero_ui_pixels);memset(zero_overlay,0x44,sizeof zero_overlay);
    p2.body[0]=p2.body[3]=p2.body[4]=1;p2.body[5]=2;p2.body[0x5C]=23;
    p2.body[0x93]=3;p2.shots[6]=0xA3;p2.trails[8]=0xB4;p2.effects[9]=0xC5;
    memset(returning_body,0x17,sizeof returning_body);memset(scene_body,0x29,sizeof scene_body);
    memset(saved_portrait_colors,0x3B,sizeof saved_portrait_colors);
    pickup_owners[0]=(PickupOwner){0x800C5000,1};zero_solid_contacts[3]=(SolidContact){3,255};
    death_effect[2]=(DeathEffectOrigin){123,456,0x80030000,2,1,2};
    /* An initialized native effect retains its owner after origin restore. */
    death_effect[3]=(DeathEffectOrigin){123,456,0x80030000,2,0,2};
    jump_audio_loaded=1;jump_audio_bound_epoch=jump_audio_owned_epoch=audio_epoch;
    for(unsigned s=0;s<24;++s)jump_audio_priorities[s]=(uint8_t)(s*9u);
    for(unsigned i=0;i<2;++i) {
        JumpAudioBank *b=&jump_audio_banks[i];
        b->guest=0x9F1B0000+i*8192;b->layout.bytes=32;b->layout.sample_bytes=128;
        b->parsed=malloc(32);CHECK(b->parsed);memset(b->parsed,(int)(0x62+i),32);
        b->samples=malloc(128);CHECK(b->samples);memset(b->samples,(int)(0x73+i),128);
    }
    Mmx6AssetView source={zero_compressed,compressed_size,2};snapshot_assets_loaded(&source,1);CHECK(snapshot_ready());
}
static void pixel_edges(void){
    uint16_t *pixels=malloc(65536*2u);CHECK(pixels);for(unsigned i=0;i<65536;++i)pixels[i]=0x1234;
    uint8_t encoded[513];CHECK(mmx6_pixels_size(pixels,65536)==9);
    CHECK(mmx6_pixels_encode(encoded,9,pixels,65536));CHECK(encoded[0]==1 && encoded[1]==255 && encoded[2]==255 && encoded[5]==1 && !encoded[6]);
    CHECK(mmx6_pixels_decode(encoded,9,65536,pixels));
    for(unsigned i=0;i<65536;++i)CHECK(pixels[i]==0x1234);
    for(unsigned i=0;i<256;++i)pixels[i]=(uint16_t)(0x1234+i);
    CHECK(mmx6_pixels_size(pixels,256)==513 && mmx6_pixels_encode(encoded,513,pixels,256));
    CHECK(!encoded[0] && encoded[1]==0x34 && encoded[2]==0x12);
    CHECK(!mmx6_pixels_decode(encoded,512,256,NULL));CHECK(!mmx6_pixels_size(pixels,65537));
    const uint8_t zero_run[]={1,0,0,0x34,0x12},overflow[]={1,1,1,0x34,0x12};
    CHECK(!mmx6_pixels_decode(zero_run,sizeof zero_run,256,NULL));CHECK(!mmx6_pixels_decode(overflow,sizeof overflow,256,NULL));
    CHECK(!mmx6_pixels_decode(encoded,513,255,NULL));free(pixels);
}
static void retain_native_x_pixels(void){
    const uint32_t table=0x80020000,source=table+0x20;render_x_death=1;saved_resources[3]=0x80030000;
    for(unsigned i=0;i<16;++i)psx_mod_write_half(saved_resources[3]+i*2,(uint16_t)(i*0x3D));
    psx_mod_write_word(table,0x100020); /* One original 16x16 packed tile. */
    const uint16_t stream[]={0x6000,0x1111,0x0001,63,0,0};
    for(unsigned i=0;i<6;++i)psx_mod_write_half(source+i*2,stream[i]);
    uint16_t first=sprite_bank(table,0,0x7800,UINT16_MAX);CHECK(first);
    uint32_t old=texture_hash[first-0x6000];
    psx_mod_write_half(source+2,0x2222); /* Same address/tile/palette, new actual art. */
    uint16_t second=sprite_bank(table,0,0x7800,UINT16_MAX);CHECK(second && second!=first);
    CHECK(texture_hash[second-0x6000]!=old);unsigned count=bank_count;
    psx_mod_write_byte(source+12,0xE7); /* Unrelated trailing RAM is not identity. */
    CHECK(sprite_bank(table,0,0x7800,UINT16_MAX)==second && bank_count==count);
    bank_count=4096; /* A full cache must still reuse its existing pixels. */
    CHECK(sprite_bank(table,0,0x7800,UINT16_MAX)==second && bank_count==4096);bank_count=count;
    render_x_death=0;
    uint8_t colors[32]={0};uint16_t tile[256];for(unsigned i=0;i<256;++i)tile[i]=(uint16_t)(i+4);
    CHECK(retain_sprite_bank(0x80040000,0,colors,tile));
    for(unsigned i=0;i<16;++i)vram[480*1024+i]=(uint16_t)(i+1);
    CHECK(hud_tile_bank(0,(uint16_t)(480*64),0));
    /* Deferred Giga UI pixels must survive cold texture reconstruction even
     * when resident VRAM belongs to the other player. */
    memset(vram,0xBB,sizeof vram);
    for(unsigned y=0;y<16;++y)for(unsigned x=0;x<4;++x)
        zero_ui_pixels[(256+80+y)*1024+896+16+x]=0x1111;
    psx_mod_write_half(menu_memory+0x10000+((505-496)*64+1)*2,0x1234);
    CHECK(zero_ui_effect_bank(0x3E,0x7E50,0x5040));
    CHECK(zero_ui_effect_bank(0x3E,0x7E50,UINT16_MAX));
    for(unsigned y=176;y<256;++y)for(unsigned x=768;x<832;++x)
        zero_ui_pixels[y*1024+x]=0x1111;
    psx_mod_write_half(active_palette+2*32+2,0x4321);
    CHECK(zero_atlas_effect_bank(0x2C,0x7802,UINT16_MAX,0));
}

static uint16_t saved_yammar_tile,saved_yammar_page;
static void retain_yammar_native_upload_pixels(void) {
    /* Actual sprite_bank -> existing wire5 encoded cache -> cold resolver.
     * Authored source/palette geometry; no ROM fixture or new engine field. */
    free(zero_compressed);compressed_size=0x200;zero_compressed=malloc(compressed_size);CHECK(zero_compressed);
    memset(zero_compressed,0,compressed_size);put32(zero_compressed+0x10,0x100);
    for(unsigned i=0;i<23;++i)put32(zero_compressed+0x100+i*4,0x0200005Cu);
    const uint16_t words[]={0x5800,0x1111,0x0001,1023,0x2222,0x0001,1023,0,0};
    for(unsigned i=0;i<sizeof words/sizeof *words;++i){
        zero_compressed[0x15C+i*2]=(uint8_t)words[i];zero_compressed[0x15D+i*2]=(uint8_t)(words[i]>>8);
    }
    Mmx6AssetView source={zero_compressed,compressed_size,2};snapshot_assets_loaded(&source,1);
    for(unsigned c=0;c<16;++c)psx_mod_write_half(active_palette+0x49*32+c*2,0);
    psx_mod_write_half(active_palette+0x49*32+2,0x1234);psx_mod_write_half(active_palette+0x49*32+4,0x4321);
    uint32_t core=state_digest();
    saved_yammar_tile=sprite_bank(assets+0x100,0,0x7849,0x4000);
    saved_yammar_page=sprite_bank(assets+0x100,22,0x7849,UINT16_MAX);
    CHECK(saved_yammar_tile && saved_yammar_page && state_digest()==core);
    uint16_t tile[256];CHECK(mmx6_pixels_decode(banks[saved_yammar_tile-0x6000].pixels,
        banks[saved_yammar_tile-0x6000].pixel_bytes,256,tile));
    for(unsigned i=0;i<256;++i)CHECK(tile[i]==0x1234);
    static uint16_t page[65536];CHECK(mmx6_pixels_decode(banks[saved_yammar_page-0x6000].pixels,
        banks[saved_yammar_page-0x6000].pixel_bytes,65536,page));
    CHECK(!page[0] && page[64*256]==0x1234 && page[80*256]==0x4321 && !page[96*256]);
}
static void digest_and_readiness(void){
    uint32_t h=state_digest();++frame_count;p2_hud_fade=17;CHECK(state_digest()==h);
    psx_mod_write_byte(diagnostic+0x50,8);CHECK(!snapshot_ready() && !snapshot_bytes());
    psx_mod_write_byte(diagnostic+0x50,0);CHECK(snapshot_ready());
    for(unsigned phase=1;phase<=2;++phase){
        checkpoint_pending=(Mmx6CheckpointPending){phase,1,1234};
        CHECK(!snapshot_ready() && !snapshot_bytes() && state_digest()!=h);
        memset(&checkpoint_pending,0,sizeof checkpoint_pending);
        CHECK(snapshot_ready() && state_digest()==h);
    }
#define PERTURB(value) do{(value)^=1;CHECK(state_digest()!=h);(value)^=1;CHECK(state_digest()==h);}while(0)
    PERTURB(p2.shots[6]);PERTURB(previous_input);PERTURB(p2_start_previous);
    PERTURB(zero_giga_backup[7]);
    PERTURB(shared_effect_owners[7]);
    PERTURB(checkpoint_lab_option);PERTURB(checkpoint_lab_state);PERTURB(checkpoint_lab_previous);
    PERTURB(checkpoint_pending.authority);
    PERTURB(saved_portrait_colors[7]);PERTURB(pickup_owners[0].seat);PERTURB(zero_solid_contacts[3].carried);
    PERTURB(death_effect[2].x);
    PERTURB(death_effect[3].owner);
    PERTURB(jump_audio_banks[0].guest);PERTURB(jump_audio_registers[4]);
    PERTURB(jump_audio_priorities[0]);PERTURB(jump_audio_priorities[20]);PERTURB(jump_audio_priorities[23]);
#undef PERTURB
    life.status[1]=MMX6_COOP_ABSENT;h=state_digest();life.rejoin_pending=1;CHECK(state_digest()!=h);life.rejoin_pending=0;life.status[1]=MMX6_COOP_ALIVE;
    zero_projected=1;h=state_digest();saved_play[3]^=1;CHECK(state_digest()!=h);saved_play[3]^=1;zero_projected=0;
    int *guards[]={&inside,&player_call,&stage_call,&zero_world,&world_render,&hud_call,&render_x_death,
        &effect_call,&pickup_call,&solid_call,&solid_allocate_call,&scene_call,&zero_projected,&unit_choices_call,&intro_target_call,&shared_fx_call,&shared_fx_allocate_call};
    for(unsigned i=0;i<sizeof guards/sizeof guards[0];++i){h=state_digest();*guards[i]=1;CHECK(!snapshot_ready());CHECK(state_digest()!=h);*guards[i]=0;CHECK(snapshot_ready());CHECK(state_digest()==h);}
    local_scope=1;CHECK(!snapshot_ready());local_scope=0;
    texture_support=0;CHECK(!snapshot_ready());texture_support=1;
    unsigned *audio_guards[]={&jump_audio_call,&jump_audio_keyon_call,&jump_audio_stop_call,&jump_audio_faulted,
        &jump_audio_slot,&jump_audio_bank,&jump_audio_tone,&jump_audio_mode,&jump_audio_calculated};
    for(unsigned i=0;i<sizeof audio_guards/sizeof audio_guards[0];++i) {
        h=state_digest();*audio_guards[i]=1;CHECK(!snapshot_ready() && state_digest()!=h);
        *audio_guards[i]=0;CHECK(snapshot_ready() && state_digest()==h);
    }
    h=state_digest();jump_audio_stop_mask=1;CHECK(!snapshot_ready() && state_digest()!=h);jump_audio_stop_mask=0;
    jump_audio_registers[4]=1;CHECK(!snapshot_ready() && state_digest()!=h);jump_audio_registers[4]=0;
    jump_audio_meta.voice_count=1;CHECK(!snapshot_ready() && state_digest()!=h);jump_audio_meta.voice_count=0;
    jump_audio_voices[3].bank=31;CHECK(!snapshot_ready() && state_digest()!=h);jump_audio_voices[3].bank=0;
    h=state_digest();++audio_epoch;CHECK(!snapshot_ready() && state_digest()==h);--audio_epoch;
    h=state_digest();foreign_audio23=1;CHECK(!snapshot_ready() && !snapshot_bytes() && state_digest()==h);
    foreign_audio23=0;CHECK(snapshot_ready() && state_digest()==h);
    CHECK(snapshot_ready() && pause_owner==1 && zero_menu_loaded); /* Stable paused UI remains admissible. */
    uint32_t words[2]={0x11223344,0x55667788},same[2]={0x11223344,0x55667788};
    STATE_WORDS(a,42,words,2);CHECK(!snapshot_ready());h=state_digest();STATE_POP(a);
    STATE_WORDS(b,42,same,2);CHECK(state_digest()==h);same[1]^=1;STATE_UPDATE(b,same);CHECK(state_digest()!=h);STATE_POP(b);
    CPUState cpu;memset(&cpu,0,sizeof cpu);cpu.pc=0x80010000;cpu.gpr[31]=0x80020000;cpu.gpr[3]=9;
    CHECK(guest(&cpu,0x80030000,1,2)==42 && cpu.pc==0x80010000 && cpu.gpr[3]==9 && cpu.gpr[31]==0x80020000);
    CHECK(guest_calls==1 && !state_track.count && snapshot_ready());
}
static void reject_unchanged(const uint8_t *wire,uint32_t len){
    uint32_t h=state_digest();PlayerContext before=p2;SpriteBank first=banks[0];unsigned writes=guest_writes;
    CHECK(!snapshot_validate(wire,len));CHECK(state_digest()==h && !memcmp(&before,&p2,sizeof p2));
    CHECK(banks[0].pixels==first.pixels && bank_count && guest_writes==writes);
}
static void actual_projection_backups(void){
    CPUState cpu;memset(&cpu,0,sizeof cpu);cpu.gpr[31]=0x80020000;
    uint8_t before[sizeof p2.body];for(unsigned i=0;i<sizeof before;++i)before[i]=(uint8_t)(i*3);
    project(PLAYER,before,sizeof before);psx_mod_write_byte(PLAY+0x38,7);psx_mod_write_byte(PLAY+0x5E,9);
    CHECK(pickup_as_seat(&cpu,0x8004E26C,0x800C5000,1)==42);
    uint8_t after[sizeof before];capture(PLAYER,after,sizeof after);CHECK(!memcmp(before,after,sizeof before));
    CHECK(psx_mod_read_byte(PLAY+0x38)==7 && psx_mod_read_byte(PLAY+0x5E)==9 && !state_track.count);
    CHECK(pickup_overlap(&cpu,0x800C5000,1)==42);capture(PLAYER,after,sizeof after);
    CHECK(!memcmp(before,after,sizeof before) && !state_track.count);
    psx_mod_write_byte(0x800C1220+0x72,1);psx_mod_write_byte(0x800C1220+0x76,2);
    CHECK(solid_as_zero(&cpu,0x80031DA8,0x800C1220,&zero_solid_contacts[3])==42);
    CHECK(psx_mod_read_byte(0x800C1220+0x72)==1 && psx_mod_read_byte(0x800C1220+0x76)==2);
    CHECK(zero_solid_contacts[3].carried==255 && !state_track.count && snapshot_ready());
}
static void weapon_support_projection_and_reuse(void){
    CHECK(solid_contact(0x800950A0u)==&zero_solid_contacts[80]);
    CHECK(solid_contact(0x80096400u)==&zero_solid_contacts[111]);
    CHECK(!solid_contact(0x8009509Fu) && !solid_contact(0x800950A1u) && !solid_contact(0x800964A0u));
    CPUState cpu;memset(&cpu,0,sizeof cpu);cpu.gpr[4]=0x800950A0u;
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAYER+2,0);
    psx_mod_write_byte(PLAYER+0xCC,0);p2.body[2]=1;
    psx_mod_write_byte(cpu.gpr[4]+0x72,3);psx_mod_write_byte(cpu.gpr[4]+0x76,4);
    psx_mod_write_byte(cpu.gpr[4]+0x73,23);psx_mod_write_byte(cpu.gpr[4]+0x77,27);
    zero_solid_contacts[80]=(SolidContact){5,6};
    solid_dispatch=1;CHECK(solid_player_collision(&cpu,0x80031DA8u)==1);solid_dispatch=0;
    CHECK(cpu.gpr[2]==42 && psx_mod_read_word(PLAYER+8)==111 && p2.body[8]==222 && !p2.body[9] && !p2.body[10] && !p2.body[11]);
    CHECK(psx_mod_read_byte(cpu.gpr[4]+0x72)==9 && psx_mod_read_byte(cpu.gpr[4]+0x76)==10);
    CHECK(psx_mod_read_byte(cpu.gpr[4]+0x73)==23 && psx_mod_read_byte(cpu.gpr[4]+0x77)==27);
    CHECK(zero_solid_contacts[80].sides==11 && zero_solid_contacts[80].carried==255 && !state_track.count);
    /* Reallocation clears only the resident X slot, including the last slot.
     * A projected Zero allocation aliases that address but owns another pool. */
    allocator_dispatch=1;zero_solid_contacts[111]=(SolidContact){7,255};
    CHECK(solid_allocate(&cpu,0x8002C32Cu)==1 && cpu.gpr[2]==0x80096400u);
    CHECK(!zero_solid_contacts[111].sides && !zero_solid_contacts[111].carried);
    zero_solid_contacts[111]=(SolidContact){7,255};zero_projected=1;
    CHECK(!solid_contact(0x80096400u));CHECK(solid_contact(0x800C1220u)==&zero_solid_contacts[0]);
    CHECK(solid_allocate(&cpu,0x8002C32Cu)==1);
    CHECK(zero_solid_contacts[111].sides==7 && zero_solid_contacts[111].carried==255);
    zero_projected=0;allocator_dispatch=0;CHECK(snapshot_ready());
}
static void native_health_freeze_camera(void){
    uint8_t old_body[sizeof p2.body],old_play[0x20];
    PlayerContext old_partner=p2;PickupOwner old_owners[128];
    capture(PLAYER,old_body,sizeof old_body);capture(PLAY,old_play,sizeof old_play);
    memcpy(old_owners,pickup_owners,sizeof old_owners);
    unsigned old_scene=scene_owner;Mmx6CoopLifecycle old_life=life;
    memset(pickup_owners,0,sizeof pickup_owners);
    for(unsigned i=0;i<0x20;++i)psx_mod_write_byte(PLAY+i,0);
    psx_mod_write_byte(PLAY,10);scene_owner=0;
    life.status[0]=life.status[1]=MMX6_COOP_ALIVE;
    psx_mod_write_byte(PLAYER+4,1);psx_mod_write_byte(PLAYER+5,2);
    psx_mod_write_word(PLAYER+8,144u<<16);psx_mod_write_word(PLAYER+12,1115u<<16);
    put32(p2.body+8,392u<<16);put32(p2.body+12,1082u<<16);
    CPUState cpu;memset(&cpu,0,sizeof cpu);camera_dispatch=1;
    expected_camera_axis=268u<<16;
    CHECK(camera_target(&cpu,0x80029598u)==1 && cpu.gpr[2]==77);
    CHECK(psx_mod_read_word(PLAYER+8)==144u<<16 && !state_track.count);
    for(unsigned i=0x10;i<0x18;++i)psx_mod_write_byte(PLAY+i,1);
    unsigned calls=guest_calls;CHECK(!shared_camera() && !camera_target(&cpu,0x80029598u));
    CHECK(guest_calls==calls); /* An unrelated freeze must keep native handling. */
    uint32_t actor=0x8008EF48u;uint8_t old_actor[0x9C];capture(actor,old_actor,sizeof old_actor);
    psx_mod_write_byte(actor,0x21);psx_mod_write_byte(actor+1,47);
    psx_mod_write_byte(actor+2,33);psx_mod_write_byte(actor+4,2);
    for(unsigned owner=0;owner<2;++owner){
        pickup_owners[0]=(PickupOwner){actor,(uint8_t)owner};
        expected_camera_axis=268u<<16;
        CHECK(camera_target(&cpu,0x80029598u)==1 && cpu.gpr[2]==77);
        expected_camera_axis=(1115u+1082u)<<15;
        CHECK(camera_target(&cpu,0x80029658u)==1 && cpu.gpr[2]==77);
        CHECK(psx_mod_read_word(PLAYER+8)==144u<<16 && psx_mod_read_word(PLAYER+12)==1115u<<16);
    }
    expected_camera_axis=268u<<16;
    psx_mod_write_byte(actor+2,32);CHECK(camera_target(&cpu,0x80029598u)==1);
    psx_mod_write_byte(actor+2,36);CHECK(!camera_target(&cpu,0x80029598u));
    psx_mod_write_byte(actor+2,33);psx_mod_write_byte(actor+4,1);CHECK(!camera_target(&cpu,0x80029598u));
    psx_mod_write_byte(actor+4,2);psx_mod_write_byte(actor,0);CHECK(!camera_target(&cpu,0x80029598u));
    psx_mod_write_byte(actor,0x21);pickup_owners[0].actor=actor+1;CHECK(!camera_target(&cpu,0x80029598u));
    pickup_owners[0].actor=0x800C5000u;CHECK(!camera_target(&cpu,0x80029598u));
    pickup_owners[0].actor=actor;scene_owner=2;CHECK(!camera_target(&cpu,0x80029598u));scene_owner=0;
    life.status[0]=MMX6_COOP_FALLEN;CHECK(!camera_target(&cpu,0x80029598u));life.status[0]=MMX6_COOP_ALIVE;
    psx_mod_write_byte(PLAY+0x1C,1);CHECK(!camera_target(&cpu,0x80029598u));psx_mod_write_byte(PLAY+0x1C,0);
    psx_mod_write_byte(PLAY+0x17,0);CHECK(!camera_target(&cpu,0x80029598u));
    camera_dispatch=0;scene_owner=old_scene;life=old_life;p2=old_partner;
    project(PLAYER,old_body,sizeof old_body);project(PLAY,old_play,sizeof old_play);
    project(actor,old_actor,sizeof old_actor);memcpy(pickup_owners,old_owners,sizeof old_owners);
    CHECK(!state_track.count && snapshot_ready());
}
static void roundtrip_and_malformed(void){
    zero_solid_contacts[111]=(SolidContact){13,255};
    uint8_t expected_giga[ZERO_GIGA_BACKUP_BYTES];
    uint8_t expected_owners[96];
    for(unsigned i=0;i<sizeof expected_giga;++i)zero_giga_backup[i]=expected_giga[i]=(uint8_t)(i*11u+3u);
    for(unsigned i=0;i<96;++i)shared_effect_owners[i]=expected_owners[i]=(uint8_t)(i%3);
    uint32_t len=snapshot_bytes();CHECK(len && len<STATE_MAX_BYTES);
    uint8_t *wire=malloc(len+1),*bad=malloc(len+1);CHECK(wire && bad && snapshot_write(wire,len));
    /* Locate the unique typed pending origin, then reject foreign owners
     * and a pending origin with no owner before committing any host state. */
    const uint8_t origin[]={1,2,123,0,0,0,200,1,0,0,0,0,3,128,2};
    unsigned origin_at=0,matches=0;
    for(unsigned at=0;at+sizeof origin<=len;++at)if(!memcmp(wire+at,origin,sizeof origin)){origin_at=at;++matches;}
    CHECK(matches==1);
    memcpy(bad,wire,len);bad[origin_at+1]=3;reject_unchanged(bad,len);
    memcpy(bad,wire,len);bad[origin_at+1]=0;reject_unchanged(bad,len);
    CHECK(!snapshot_write(wire,len-1));CHECK(!snapshot_write(wire,len+1));
    reject_unchanged(wire,0);reject_unchanged(wire,1);reject_unchanged(wire,len-1);
    memcpy(bad,wire,len);bad[len]=0;reject_unchanged(bad,len+1);
    memcpy(bad,wire,len);put32(bad+4,2);reject_unchanged(bad,len); /* Disposable older wire schema. */
    memcpy(bad,wire,len);bad[16]^=1;reject_unchanged(bad,len); /* Fixed guest allocation identity. */
    memcpy(bad,wire,len);bad[16+9*4]^=1;reject_unchanged(bad,len); /* Retained audio header allocation. */
    StateIO resources={STATE_COUNT,1,NULL,NULL,0,0,0};snapshot_resources(&resources);
    memcpy(bad,wire,len);bad[resources.pos-32]^=1;reject_unchanged(bad,len); /* Immutable asset SHA256. */
    memcpy(bad,wire,len);bad[resources.pos+sizeof p2]=255;reject_unchanged(bad,len); /* Lifecycle enum. */
    HostState core;state_capture(&core);StateIO count={STATE_COUNT,1,NULL,NULL,0,0,0};snapshot_resources(&count);state_core(&count,&core);
    uint32_t cache=count.pos;memcpy(bad,wire,len);put32(bad+cache,4097);reject_unchanged(bad,len);
    memcpy(bad,wire,len);bad[cache-10-96]=3;reject_unchanged(bad,len); /* Invalid shared effect owner. */
    memcpy(bad,wire,len);bad[cache+4+44]=2;reject_unchanged(bad,len); /* Invalid retained-pixel encoding. */
    allocation_fail=1;reject_unchanged(wire,len);allocation_fail=0;
    uint32_t untouched=state_digest();
    for(unsigned i=0;i<200;++i){
        memcpy(bad,wire,len);bad[(i*7919u)%len]^=(uint8_t)(1u<<(i%8));
        (void)snapshot_validate(bad,len);CHECK(state_digest()==untouched);
    }
    uint32_t original=state_digest(),original_diagnostic=diagnostic_host_digest(),saved_hash[8192];memcpy(saved_hash,texture_hash,sizeof saved_hash);
    CHECK(snapshot_validate(wire,len));p2.body[0x5C]=1;previous_input^=0x101;zero_solid_contacts[3].carried=0;
    zero_solid_contacts[111]=(SolidContact){0,0};
    memset(jump_audio_priorities,0,sizeof jump_audio_priorities);
    memset(zero_giga_backup,0,sizeof zero_giga_backup);
    memset(shared_effect_owners,0,sizeof shared_effect_owners);
    memset(death_effect,0,sizeof death_effect);
    int allocations=allocation_calls;allocation_fail=1;snapshot_read(wire,len);allocation_fail=0;
    CHECK(allocation_calls==allocations && state_digest()==original && p2.body[0x5C]==23);
    CHECK(zero_solid_contacts[111].sides==13 && zero_solid_contacts[111].carried==255);
    CHECK(diagnostic_host_digest()==original_diagnostic);
    CHECK(!memcmp(zero_giga_backup,expected_giga,sizeof expected_giga));
    CHECK(!memcmp(shared_effect_owners,expected_owners,sizeof expected_owners));
    CHECK(death_effect[2].owner==2 && death_effect[2].valid && death_effect[3].owner==2 && !death_effect[3].valid);
    for(unsigned s=0;s<24;++s)CHECK(jump_audio_priorities[s]==(uint8_t)(s*9u));
    /* Cold cache: retain immutable disc/build resources, destroy every current
     * pixel bank and metadata, then validate saved length independently of live. */
    for(unsigned i=0;i<4096;++i){free(banks[i].pixels);memset(&banks[i],0,sizeof banks[i]);}
    bank_count=ui_bank_count=0;memset(ui_banks,0,sizeof ui_banks);memset(&p2,0,sizeof p2);
    memset(zero_giga_backup,0,sizeof zero_giga_backup);
    memset(shared_effect_owners,0,sizeof shared_effect_owners);
    memset(death_effect,0,sizeof death_effect);
    CHECK(snapshot_validate(wire,len));allocation_fail=1;allocations=allocation_calls;snapshot_read(wire,len);
    snapshot_resources_restored();CHECK(forgotten==1 && installed_resolver && state_digest()==original);
    CHECK(!memcmp(shared_effect_owners,expected_owners,sizeof expected_owners));
    CHECK(death_effect[2].owner==2 && death_effect[2].valid && death_effect[3].owner==2 && !death_effect[3].valid);
    CHECK(allocation_calls==allocations);allocation_fail=0;
    for(unsigned i=0;i<2;++i) {
        uint8_t restored[32];capture(jump_audio_banks[i].guest,restored,sizeof restored);
        CHECK(!memcmp(restored,jump_audio_banks[i].parsed,sizeof restored));
    }
    for(unsigned i=0;i<bank_count;++i){CHECK(installed_resolver((uint16_t)(0x6000+i)));CHECK(texture_hash[i]==saved_hash[i]);}
    for(unsigned i=0;i<ui_bank_count;++i){CHECK(installed_resolver((uint16_t)(0x7000+i)));CHECK(texture_hash[4096+i]==saved_hash[4096+i]);}
    CHECK(!installed_resolver(0x5FFF));CHECK(!installed_resolver(0x8000));
    free(wire);free(bad);
}
static void agreed_latch_snapshot(void) {
    for(unsigned option=1;option<=2;++option) {
        checkpoint_lab_option=option;
        for(unsigned state=CHECKPOINT_LAB_ARMED;state<=CHECKPOINT_LAB_CONSUMED;++state) {
            checkpoint_lab_state=state;checkpoint_lab_previous=1;
            uint32_t length=snapshot_bytes(),digest=state_digest();uint8_t *wire=malloc(length);CHECK(wire);
            CHECK(snapshot_write(wire,length));
            checkpoint_lab_option=0;CHECK(!snapshot_validate(wire,length));
            checkpoint_lab_option=3-option;CHECK(!snapshot_validate(wire,length));checkpoint_lab_option=option;
            checkpoint_lab_state=checkpoint_lab_previous=0;
            CHECK(snapshot_validate(wire,length));snapshot_read(wire,length);
            CHECK(checkpoint_lab_state==state && checkpoint_lab_previous==1 && state_digest()==digest);
            free(wire);
        }
    }
    checkpoint_lab_option=checkpoint_lab_state=checkpoint_lab_previous=0;
}
static void abandoned_guest(void){
    /* Exercise the SDK's actual supported landing, including MinGW GNU's
     * large-frame case. The target function has not returned when dispatched
     * guest execution abandons its nested C frames. */
    volatile uint8_t landing[32768];landing[0]=17;landing[sizeof landing-1]=29;
    CPUState cpu;memset(&cpu,0,sizeof cpu);
    if(!psx_host_setjmp(abandon_target)){abandon_guest=1;(void)guest(&cpu,0x80030000,0,0);CHECK(0);}
    CHECK(landing[0]==17 && landing[sizeof landing-1]==29);
    CHECK(state_track.count && !snapshot_ready());(void)state_digest();
}
int main(void){
    pixel_edges();setup();retain_native_x_pixels();retain_yammar_native_upload_pixels();digest_and_readiness();actual_projection_backups();
    weapon_support_projection_and_reuse();native_health_freeze_camera();roundtrip_and_malformed();agreed_latch_snapshot();
    CHECK(sprite_bank(assets+0x100,22,0x7849,0x4000)==saved_yammar_tile);
    CHECK(sprite_bank(assets+0x100,0,0x7849,UINT16_MAX)==saved_yammar_page);
    /* Abandoned/overflowed call records are safe owned bytes, and explicitly
     * cannot be captured/restored as a resumable C stack. Reactivation required. */
    uint32_t v=1;for(unsigned i=0;i<MMX6_STATE_FRAMES;++i)CHECK(mmx6_state_push(i,&v,4,1)!=UINT32_MAX);
    CHECK(mmx6_state_push(999,&v,4,1)==UINT32_MAX && !snapshot_ready());(void)state_digest();
    state_track.count=state_track.error=0; /* Synthetic full-reactivation boundary. */
    abandoned_guest();
    puts("co-op canonical host state, checked snapshot and cold retained resources PASS");return 0;
}
