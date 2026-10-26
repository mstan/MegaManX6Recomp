/* Actual plugin activation across real SDK arena/bank/packet resets.
 * Authored host pixels/audio metadata are unit fixtures, never game evidence. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mod_memory.h"
#include "mod_texture_banks.h"
#include "mmx6_coop_session_sdk_fixture.h"
static void *session_malloc(size_t size);
static void *session_calloc(size_t count,size_t size);
static void session_free(void *pointer);
#define malloc session_malloc
#define calloc session_calloc
#define free session_free
#define MMX6_TEST_SESSION_RESOURCES 1
#define main unused_private_effects_fixture_main
#include "test_mmx6_coop_private_effects.c"
#undef main
#undef malloc
#undef calloc
#undef free

static void *live_buffers[16384];
static unsigned host_buffers,guest_allocations,fail_guest_allocation;
static uint64_t owners[24];
static uint32_t stopped_owned;
static void *session_malloc(size_t size) {
    void *p=malloc(size);if(!p)return NULL;
    for(unsigned i=0;i<16384;++i)if(!live_buffers[i]){live_buffers[i]=p;++host_buffers;return p;}
    CHECK(0);return NULL;
}
static void *session_calloc(size_t count,size_t size) {
    CHECK(!count||size<=SIZE_MAX/count);void *p=session_malloc(count*size);
    if(p)memset(p,0,count*size);return p;
}
static void session_free(void *p) {
    if(!p)return;
    for(unsigned i=0;i<16384;++i)if(live_buffers[i]==p){live_buffers[i]=NULL;--host_buffers;free(p);return;}
    CHECK(0); /* Detect a duplicate free or a borrowed/static buffer. */
}
uint32_t psx_mod_alloc_guest_memory(uint32_t size,uint32_t alignment) {
    if(++guest_allocations==fail_guest_allocation)return 0;
    return psx_mod_memory_alloc(size,alignment);
}
uint32_t psx_mod_alloc_gpu_dma_memory(uint32_t size,uint32_t alignment) {
    return psx_mod_gpu_dma_memory_alloc(size,alignment);
}
void psx_mod_tag_hud_primitive(uint32_t address,int hud){(void)address;(void)hud;}
uint32_t psx_mod_spu_sample_bank_epoch(void){return 1;}
uint64_t psx_mod_spu_private_voice_owner(unsigned slot){CHECK(slot<24);return owners[slot];}
uint32_t psx_mod_spu_private_voice_active(void){return 0;}
int spu_get_private_voice_state(unsigned slot,SpuVoiceState *out){CHECK(slot<24&&out);memset(out,0,sizeof *out);return 1;}
int psx_mod_spu_sample_bank(uint32_t bank,const void *data,uint32_t bytes){CHECK((bank==30||bank==31)&&data&&bytes);return 1;}
int psx_mod_spu_private_voice_claim(uint64_t owner,uint32_t mask){
    for(unsigned i=0;i<24;++i)if(mask&(1u<<i)){if(owners[i]&&owners[i]!=owner)return 0;owners[i]=owner;}return 1;
}
int psx_mod_spu_private_voice_stop_owned(uint64_t owner,uint32_t mask){
    for(unsigned i=0;i<24;++i)if(mask&(1u<<i))CHECK(owners[i]==owner);stopped_owned|=mask;return 1;
}
int psx_mod_spu_private_voice_volume_owned(uint64_t owner,unsigned slot,uint16_t left,uint16_t right){
    CHECK(slot<24&&owners[slot]==owner&&!left&&!right);return 1;
}
int psx_mod_spu_private_voice_play_owned(uint64_t owner,unsigned slot,uint32_t bank,const uint16_t regs[8],unsigned mode){
    (void)owner;(void)slot;(void)bank;(void)regs;(void)mode;CHECK(0);return 0;
}
uint32_t psx_mod_call_guest_uncharged(CPUState *cpu,uint32_t target,uint32_t ret,uint32_t a0,uint32_t a1,
    uint32_t a2,uint32_t a3,uint32_t budget,int *charged){
    (void)cpu;(void)target;(void)ret;(void)a0;(void)a1;(void)a2;(void)a3;(void)budget;(void)charged;CHECK(0);return 0;
}
static void allocated(void) {
    Mmx6SessionResources r=mmx6_test_session_resources();
    CHECK(!failed&&!ready&&!enrolled&&r.guest_used==ASSET_SPACE+0x2000+2*MMX6_JUMP_AUDIO_HEADER_BYTES);
    CHECK(r.dma_used==FRAME_ARENA*2+0x10000+MENU_STORAGE_BYTES&&r.packet_arenas==2);
    CHECK(r.function_replacements>20&&r.function_replacements<=64);
    CHECK(guest_allocations==4&&assets&&diagnostic&&packets&&hud_packets&&menu_memory);
    CHECK(!assembly&&!palette_source&&!active_palette&&!menu_assembly&&!world_packets);
    CHECK(!bank_count&&!ui_bank_count&&!host_buffers&&!zero_compressed&&!zero_ui_pixels);
    CHECK(!jump_audio_loaded&&!jump_audio_bound_epoch&&!jump_audio_owned_epoch);
    CHECK(jump_audio_banks[0].guest&&jump_audio_banks[1].guest);
    uint32_t packet[9]={0x34000000,0,0,0x34000000,0,0,0x12000000,0,0};
    CHECK(mod_texture_packet_bank(packets+4,packet,9)==0x1234);
    CHECK(mod_texture_packet_bank(hud_packets+4,packet,9)==0x1234);
    CHECK(!mod_texture_packet_bank(menu_memory+4,packet,9));
    for(unsigned i=0;i<0x2000;++i){
        /* activate() clears the block, then checkpoint_reset() publishes its
         * exact existing capability word in both fixture variants. */
        const uint8_t expected=i>=0xA0&&i<0xA4?
            (uint8_t)(CHECKPOINT_CAPABILITY>>((i-0xA0)*8u)):0;
        CHECK(psx_mod_read_byte(diagnostic+i)==expected);
    }
}
static void seed_resources(void) {
    zero_compressed=session_calloc(1,64);compressed_size=64;
    zero_ui_pixels=session_calloc(1024*512,sizeof *zero_ui_pixels);
    CHECK(zero_compressed&&zero_ui_pixels);
    assembly=assets+0x100;palette_source=assets+0x200;active_palette=assets+0x300;menu_assembly=assets+0x400;
    uint16_t pixels[256];uint8_t colors[32]={0};for(unsigned i=0;i<256;++i)pixels[i]=0x1234;
    CHECK(retain_sprite_bank(assets,0,colors,pixels)==0x6000);
    CHECK(retain_sprite_bank(assets+16,0,colors,pixels)==0x6000&&bank_count==1);
    /* Exercise the actual menu-atlas path and real immutable bank registry. */
    for(unsigned i=0;i<1024*512;++i)zero_ui_pixels[i]=0x1111;
    psx_mod_write_half(menu_memory+0x10000+2,0x4567);
    CHECK(zero_ui_effect_bank(0,0x7C10,0)==0x6001&&bank_count==2);
    ui_bank_count=1;ui_banks[0].id=0x7000; /* Legacy metadata must retire too. */
    for(unsigned i=0;i<2;++i){
        JumpAudioBank *b=&jump_audio_banks[i];b->parsed=session_calloc(1,8192);b->samples=session_calloc(1,128);
        CHECK(b->parsed&&b->samples);b->layout.bytes=8192;b->layout.sample_bytes=128;b->layout.bank=30+i;
        project(b->guest,b->parsed,b->layout.bytes);
    }
    CHECK(psx_mod_spu_private_voice_claim(JUMP_AUDIO_OWNER,JUMP_STOP_MASK));
    jump_audio_loaded=1;jump_audio_bound_epoch=jump_audio_owned_epoch=1;
#ifdef MMX6_COOP_MODERN_STATE
    memset(snapshot_asset_sha,0x6B,sizeof snapshot_asset_sha);snapshot_asset_valid=1;
#endif
    ready=enrolled=1;p2.body[0]=p2.body[3]=p2.body[4]=1;p2.body[2]=1;p2.body[0xE7]=5;
    p2.body[0x5C]=32;world_packets=packets+40;
    CHECK(mmx6_test_session_resources().bank_count==2);
}
static void current_state_roundtrip(void) {
#ifdef MMX6_COOP_MODERN_STATE
    CHECK(snapshot_ready());uint32_t n=snapshot_bytes(),m=psx_mod_memory_snapshot_bytes();
    uint8_t *state=malloc(n),*arena=malloc(m);CHECK(n&&state&&m&&arena&&snapshot_write(state,n));
    psx_mod_memory_snapshot_write(arena);uint32_t cookie=psx_mod_memory_layout_cookie();
    p2.body[8]^=0x25;psx_mod_write_byte(assets,0xAA);
    CHECK(snapshot_validate(state,n));
    CHECK(psx_mod_memory_snapshot_read(arena,m));snapshot_read(state,n);snapshot_resources_restored();
    CHECK(snapshot_ready()&&p2.body[8]==0&&psx_mod_read_byte(assets)==0&&psx_mod_memory_layout_cookie()==cookie);
    uint32_t w,h;const uint16_t *pixels=mod_texture_bank_pixels(0x6000,&w,&h);
    CHECK(pixels&&w==16&&h==16&&pixels[0]==0x1234);
    pixels=mod_texture_bank_pixels(0x6001,&w,&h);CHECK(pixels&&pixels[0]==0x4567);
    free(state);free(arena);
#endif
}
int main(int argc,char **argv) {
    if(argc==3&&!strcmp(argv[1],"--peripheral-probe"))mmx6_test_session_peripheral_probe(argv[2]);
    CHECK(argc==1); /* Unknown probe arguments may never run the success case. */
    CHECK(mmx6_test_session_reset());Mmx6SessionResources expected={0};
    for(unsigned session=0;session<24;++session){
        guest_allocations=0;activate();allocated();
        if(session){
            CHECK(owners[0]==JUMP_AUDIO_OWNER+1&&!(stopped_owned&1));
            /* The authored foreign voice has now proved its lifetime. End
             * that test lease before this session's private-audio seeding. */
            owners[0]=0;
        }
        Mmx6SessionResources r=mmx6_test_session_resources();
        if(!session)expected=r;
        CHECK(r.guest_used==expected.guest_used&&r.dma_used==expected.dma_used&&r.layout_cookie==expected.layout_cookie&&
            r.function_replacements==expected.function_replacements);
        CHECK(psx_mod_memory_alloc(16,16)==assets+r.guest_used); /* No cached unreserved span. */
        seed_resources();current_state_roundtrip();
        uint32_t old_packets=packets;CHECK(mmx6_test_session_reset());
        r=mmx6_test_session_resources();CHECK(!r.guest_used&&!r.dma_used&&!r.packet_arenas&&!r.bank_count&&!r.bank_bytes&&!r.function_replacements);
        uint32_t words[9]={0x34000000,0,0,0x34000000,0,0,0x12000000,0,0};
        CHECK(!mod_texture_packet_bank(old_packets+4,words,9));
        uint32_t w,h;CHECK(!mod_texture_bank_pixels(0x6000,&w,&h));
        /* Both owned and unrelated DSP metadata can survive until SPU init;
         * activation must never touch another owner's voice. */
        owners[0]=JUMP_AUDIO_OWNER+1;stopped_owned=0;
    }
    /* Incomplete allocation fails closed, then a real reset recovers without
     * stale handles. Snapshot admission must stay unavailable. */
    guest_allocations=0;fail_guest_allocation=1;activate();CHECK(failed&&!ready&&!enrolled&&!assets);
#ifdef MMX6_COOP_MODERN_STATE
    CHECK(!snapshot_ready());
#endif
    CHECK(mmx6_test_session_reset());fail_guest_allocation=0;guest_allocations=0;activate();allocated();
    CHECK(owners[0]==JUMP_AUDIO_OWNER+1&&!(stopped_owned&1));
    CHECK(!host_buffers);CHECK(mmx6_test_session_reset());
    puts("actual plugin + SDK same-process session allocation/registration/reset and current-state roundtrip PASS");return 0;
}
