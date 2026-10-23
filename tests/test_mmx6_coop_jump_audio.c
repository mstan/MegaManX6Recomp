/* The actual plugin callbacks against isolated RAM and exact-typed SDK doubles.
 * The guest double models the bounded ordinary driver contract, not an original
 * MIPS execution or audio qualification. It deliberately touches every byte of
 * the native transaction to catch incomplete rollback, including voice+36. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mod_plugins.h"
static unsigned allocations,fail_allocation;
static void *audio_test_malloc(size_t bytes);
#define malloc audio_test_malloc
#undef PSX_MOD_CONSTRUCTOR
#define PSX_MOD_CONSTRUCTOR(name) static void name(void)
#include "../src/mods/mmx6_coop_plugin.c"
#undef malloc
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line%d: %s\n",__LINE__,#x);exit(1);}}while(0)
static void *audio_test_malloc(size_t bytes){return ++allocations==fail_allocation?NULL:malloc(bytes);}
static uint8_t test_ram[0x200000];
static unsigned guest_calls;
static unsigned memory_writes;
static uint32_t next_guest=0x9F1A0000;
uint32_t psx_mod_alloc_guest_memory(uint32_t bytes,uint32_t alignment) {
    CHECK(bytes==8192 && alignment==16);uint32_t address=next_guest;next_guest+=8192;return address;
}
static uint8_t *memory(uint32_t address){return test_ram+(address&0x1FFFFFu);}
uint8_t psx_mod_read_byte(uint32_t a){return *memory(a);}
uint16_t psx_mod_read_half(uint32_t a){return (uint16_t)(psx_mod_read_byte(a)|(uint16_t)psx_mod_read_byte(a+1)<<8);}
uint32_t psx_mod_read_word(uint32_t a){return psx_mod_read_half(a)|(uint32_t)psx_mod_read_half(a+2)<<16;}
void psx_mod_write_byte(uint32_t a,uint8_t v){++memory_writes;*memory(a)=v;}
void psx_mod_write_half(uint32_t a,uint16_t v){psx_mod_write_byte(a,(uint8_t)v);psx_mod_write_byte(a+1,(uint8_t)(v>>8));}
void psx_mod_write_word(uint32_t a,uint32_t v){for(unsigned i=0;i<4;++i)psx_mod_write_byte(a+i,(uint8_t)(v>>(i*8)));}
void psx_dispatch_call(CPUState *cpu,uint32_t target,uint32_t ret) {
    (void)ret;CHECK(target==0x8001750C && jump_audio_stop_call);++guest_calls;
    /* Deliberately retain the nonjump/global hardware stop. No double replaces
     * it with private behavior or treats unchanged nonjump ownership as fixed. */
    uint32_t mask=(cpu->gpr[4]&255u)==255?0xFFFFFFu:1u<<22;
    psx_mod_write_word(0x800E5568,psx_mod_read_word(0x800E5568)|mask);
    psx_mod_write_word(0x800E4E30,psx_mod_read_word(0x800E4E30)&~mask);
    cpu->gpr[2]=(cpu->gpr[4]&255u)==255?0:0xFF000000u;
}

static uint32_t epoch=1,active,stopped;
static uint32_t private_bank[24];
static unsigned plays,volumes,registrations,calculations,keyons,status_reads;
static unsigned slot_volumes[24];
static int bank_conflict,play_failure,wrong_keyon,charged_call,no_keyon,bad_output;
static uint32_t played_bank,played_slot,played_mode;
static uint16_t played[8];
int psx_mod_texture_banks_supported(void){return 1;}
int psx_mod_local_view_scope(void){return 0;}
static uint8_t expected_driver[JUMP_DRIVER_BYTES],expected_priority[24],expected_records[128],expected_outside[8];
static void same_native(void) {
    uint8_t bytes[JUMP_DRIVER_BYTES];capture(JUMP_DRIVER,bytes,sizeof bytes);
    CHECK(!memcmp(bytes,expected_driver,sizeof bytes));
    capture(0x800E25E0,bytes,24);CHECK(!memcmp(bytes,expected_priority,24));
    capture(0x80097738,bytes,128);CHECK(!memcmp(bytes,expected_records,128));
    capture(0x800E459C,bytes,4);capture(0x800E155C,bytes+4,4);CHECK(!memcmp(bytes,expected_outside,8));
}
uint32_t psx_mod_spu_sample_bank_epoch(void){return epoch;}
uint32_t psx_mod_spu_private_voice_active(void){return active;}
int spu_get_private_voice_state(unsigned slot,SpuVoiceState *out) {
    CHECK(slot<24 && out);memset(out,0,sizeof *out);out->active=!!(active&(1u<<slot));
    out->sample_bank=private_bank[slot];return 1;
}
int psx_mod_spu_sample_bank(uint32_t bank,const void *bytes,uint32_t size) {
    CHECK(bank==30 || bank==31);CHECK(bytes && size==jump_audio_banks[bank==31].layout.sample_bytes);
    ++registrations;return !bank_conflict;
}
int psx_mod_spu_private_voice_play(unsigned slot,uint32_t bank,const uint16_t regs[8],unsigned mode) {
    same_native();CHECK(!jump_audio_call && !jump_audio_keyon_call && !state_track.count);
    ++plays;played_slot=slot;played_bank=bank;played_mode=mode;memcpy(played,regs,sizeof played);
    active|=1u<<slot;private_bank[slot]=bank;return !play_failure;
}
int psx_mod_spu_private_voice_volume(unsigned slot,uint16_t left,uint16_t right) {
    CHECK(slot==20 || slot==22 || slot==23);CHECK(!left && !right);++volumes;++slot_volumes[slot];return 1;
}
void psx_mod_spu_private_voice_stop(uint32_t mask){
    CHECK(!(mask&~JUMP_STOP_MASK));stopped|=mask;
    /* The real DSP keeps active1 through release/END_STOP; it is not proof
     * that a sample is still audible, nor a private-slot allocation flag. */
}
uint32_t psx_mod_call_guest_uncharged(CPUState *cpu,uint32_t target,uint32_t ret,
    uint32_t a0,uint32_t a1,uint32_t a2,uint32_t a3,uint32_t budget,int *charged) {
    (void)ret;CHECK(!budget && jump_audio_call && state_track.count==4 && !snapshot_ready());
    *charged=charged_call;
    if(target==0x80016C48) {
        ++calculations;CHECK(a0==1 || a0==3);CHECK(a2==PLAYER);
        JumpAudioBank *b=&jump_audio_banks[a0==3];
        CHECK(psx_mod_read_word(0x80097738+a0*4)==b->guest+b->layout.vab);
        CHECK(psx_mod_read_word(0x80097778+a0*4)==b->guest+8);
        for(unsigned i=0;i<2;++i) {
            JumpAudioBank *v=&jump_audio_banks[i];unsigned id=v->layout.id;
            CHECK(psx_mod_read_byte(0x800E5690+id)==1);
            CHECK(psx_mod_read_word(0x800E56F0+id*4)==0);
            CHECK(psx_mod_read_word(0x800E55C8+id*4)==v->guest+v->layout.vab);
        }
        CPUState nested=*cpu;nested.gpr[4]=1u<<jump_audio_slot;
        CHECK(jump_audio_status(&nested,0x80055B14));++status_reads;
        CHECK(nested.gpr[2]==((active&(1u<<jump_audio_slot))?1u:0u));
        if(no_keyon)return 0;
        nested=*cpu;
        const uint8_t *record=b->parsed+8+a1*4;
        nested.gpr[4]=wrong_keyon?21:record[3]&31u;
        nested.gpr[5]=b->layout.id;nested.gpr[6]=record[2]&15u;nested.gpr[7]=record[2]>>4;
        nested.gpr[29]=0x801D0000;
        const uint8_t *tone=b->parsed+b->layout.tones+nested.gpr[7]*32;
        psx_mod_write_word(nested.gpr[29]+16,tone[6]);psx_mod_write_word(nested.gpr[29]+20,tone[5]);
        psx_mod_write_word(nested.gpr[29]+24,79);psx_mod_write_word(nested.gpr[29]+28,113);
        CHECK(jump_audio_keyon(&nested,0x8005A9D4));
        return nested.gpr[2];
    }
    CHECK(target==0x8005A9D4 && jump_audio_keyon_call);++keyons;
    CHECK(a0==jump_audio_slot && a1==(jump_audio_bank==30?14u:15u) && !a2 && a3==jump_audio_tone);
    /* Source closure: dirty+register+metadata(0x38 stride), all masks/history,
     * selected VAB globals and tables. Touch the entire owned span. */
    for(unsigned i=0;i<JUMP_DRIVER_BYTES;++i)psx_mod_write_byte(JUMP_DRIVER+i,(uint8_t)(i*13+9));
    memset(memory(0x800E25E0),0xA1,24);memset(memory(0x80097738),0xB2,128);
    psx_mod_write_word(0x800E459C,0x1234);psx_mod_write_word(0x800E155C,0x5678);
    uint32_t r=0x800E53A0+a0*16;
    const uint16_t actual[6]={1234,2345,0x478,8,0x80FF,0x1FC0};
    for(unsigned i=0;i<6;++i)psx_mod_write_half(r+i*2,actual[i]);
    psx_mod_write_half(0x800E4E40+a0*0x38+0x1E,0);
    psx_mod_write_half(0x800E4E40+a0*0x38+0x2A,0);
    if(bad_output==1)psx_mod_write_half(0x800E4E40+a0*0x38+0x1E,1);
    if(bad_output==2)psx_mod_write_half(0x800E4E40+a0*0x38+0x2A,1);
    if(bad_output==3)psx_mod_write_half(r+6,16); /* Outside this bank's128bytes. */
    psx_mod_write_word(0x800E4E38,1u<<a0);psx_mod_write_word(0x800E4E34,1u<<a0);
    return 0;
}
static void setup_audio(void) {
    memset(test_ram,0,sizeof test_ram);memset(&state_track,0,sizeof state_track);
    failed=jump_audio_faulted=jump_audio_call=jump_audio_keyon_call=jump_audio_stop_call=0;
    bank_conflict=play_failure=wrong_keyon=charged_call=no_keyon=bad_output=0;
    ready=enrolled=zero_projected=1;zero_world=0;active=stopped=0;
    private_bank[20]=31;private_bank[22]=private_bank[23]=30;
    jump_audio_loaded=1;jump_audio_bound_epoch=jump_audio_owned_epoch=epoch;
    plays=volumes=registrations=calculations=keyons=status_reads=guest_calls=0;
    memset(slot_volumes,0,sizeof slot_volumes);
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAYER+2,1);psx_mod_write_byte(PLAYER+4,1);
    psx_mod_write_byte(PLAYER+5,6);psx_mod_write_byte(PLAYER+0xE7,5);
    for(unsigned i=0;i<2;++i) {
        JumpAudioBank *b=&jump_audio_banks[i];
        if(!b->parsed)b->parsed=calloc(1,8192);
        if(!b->samples)b->samples=calloc(1,128);
        CHECK(b->parsed && b->samples);
        b->guest=0x9F1A0000+i*8192;
        b->layout=(Mmx6JumpAudioHeader){i?3:1,i?15:14,i?31:30,3184,128,80,112,2160,18,8};
        memset(b->parsed,0,8192);b->parsed[112]=10;
        for(unsigned t=0;t<10;++t){b->parsed[2160+t*32+6]=60;b->parsed[2160+t*32+5]=0;}
        for(unsigned r=1;r<=(i?7u:8u);++r) {
            b->parsed[8+r*4]=(uint8_t)(0x80u+b->layout.id);
            b->parsed[8+r*4+2]=(uint8_t)((!i && r>=2?r+1:r)<<4);
            b->parsed[8+r*4+3]=(uint8_t)(i?20:r>=7?23:22);
        }
    }
    /* P1 already has arbitrary queued data. Zero must not edit any of it. */
    for(unsigned i=0;i<JUMP_DRIVER_BYTES;++i)psx_mod_write_byte(JUMP_DRIVER+i,(uint8_t)(i*7+3));
    memset(memory(0x800E25E0),0x78,24);memset(memory(0x80097738),0x9A,128);
    const uint32_t tables[]={0x800E5588,0x800E55C8,0x800E5610,0x800E56A8,0x800E56F0};
    for(unsigned id=14;id<=15;++id) {
        psx_mod_write_byte(0x800E5690+id,0);
        for(unsigned t=0;t<5;++t)psx_mod_write_word(tables[t]+id*4,0);
    }
    psx_mod_write_half(0x800E5652,128);psx_mod_write_word(0x800E5520,0);psx_mod_write_word(0x800E5398,0);
    psx_mod_write_word(0x800E459C,0);psx_mod_write_byte(0x8006E356,0);
    psx_mod_write_word(0x800E5568,0);psx_mod_write_word(0x800E4E30,JUMP_STOP_MASK);
    capture(JUMP_DRIVER,expected_driver,sizeof expected_driver);capture(0x800E25E0,expected_priority,24);
    capture(0x80097738,expected_records,128);capture(0x800E459C,expected_outside,4);capture(0x800E155C,expected_outside+4,4);
}
static CPUState request(unsigned group,unsigned record) {
    CPUState cpu;memset(&cpu,0,sizeof cpu);cpu.gpr[4]=group;cpu.gpr[5]=record;cpu.gpr[6]=PLAYER;
    cpu.gpr[29]=0x801C0000;cpu.gpr[31]=group==3?0x8003D004:0x800356F4;
    psx_mod_write_word(cpu.gpr[29]+16,0x8003AFCC);return cpu;
}
static void transactions(void) {
    const unsigned groups[]={1,1,1,1,1,1,1,1,3,3,3},records[]={1,2,3,4,5,6,7,8,2,4,7};
    for(unsigned n=0;n<sizeof records/sizeof records[0];++n) {
        setup_audio();CPUState cpu=request(groups[n],records[n]);CPUState before=cpu;
        CHECK(jump_audio_sound(&cpu,0x80016C48)==1 && !failed && !cpu.gpr[2]);
        before.gpr[2]=cpu.gpr[2];CHECK(!memcmp(&before,&cpu,sizeof cpu));same_native();
        CHECK(plays==1 && keyons==1 && calculations==1 && status_reads==1);
        CHECK(played_slot==(groups[n]==3?20u:records[n]>=7?23u:22u) && played_bank==(groups[n]==3?31u:30u) && played_mode==3);
        CHECK(played[0]==1234 && played[1]==2345 && played[2]==0x478 && played[3]==8);
        CHECK(played[4]==0x80FF && played[5]==0x1FC0 && !played[6] && played[7]==8);
        CHECK(!jump_audio_call && !jump_audio_keyon_call && !jump_audio_calculated && !state_track.count);
        CHECK(jump_audio_sound(&cpu,0x80016C48)==1 && plays==2 && !failed);same_native(); /* Own active replacement. */
    }
    for(unsigned r=1;r<=8;++r) {
        setup_audio();CPUState cpu=request(1,r);cpu.gpr[6]=PLAYER+0x100;
        CHECK(!jump_audio_sound(&cpu,0x80016C48) && !plays && !calculations && !failed);same_native();
        setup_audio();cpu=request(1,r);psx_mod_write_byte(PLAYER+4,2);
        CHECK(!jump_audio_sound(&cpu,0x80016C48) && !plays && !calculations && !failed);same_native();
    }
    for(unsigned n=0;n<6;++n) {
        setup_audio();CPUState cpu=request(3,7);
        if(n==0)zero_projected=0;
        if(n==1)cpu.gpr[31]^=4;
        if(n==2)psx_mod_write_word(cpu.gpr[29]+16,0x8003B000);
        if(n==3)cpu.gpr[5]=3;
        if(n==4)psx_mod_write_byte(PLAY+0x5F,0x20);
        if(n==5)psx_mod_write_byte(0x80090D53,255);
        CHECK(!jump_audio_sound(&cpu,0x80016C48) && !plays && !calculations && !failed);same_native();
    }
    for(unsigned n=0;n<4;++n) {
        setup_audio();CPUState cpu=request(3,7);
        wrong_keyon=n==0;charged_call=n==1;no_keyon=n==2;play_failure=n==3;
        CHECK(jump_audio_sound(&cpu,0x80016C48) && cpu.gpr[2]==UINT32_MAX && failed);
        same_native();CHECK(!jump_audio_call && !jump_audio_keyon_call && !state_track.count);
        CHECK(plays==(n==3?1u:0u));
    }
    for(unsigned n=1;n<=3;++n) {
        setup_audio();CPUState cpu=request(3,7);bad_output=(int)n;
        CHECK(jump_audio_sound(&cpu,0x80016C48) && cpu.gpr[2]==UINT32_MAX && failed && !plays);
        same_native();CHECK(!jump_audio_call && !jump_audio_keyon_call && !state_track.count);
    }
    const uint32_t conflicts[]={0x800E569E,0x800E55C0,0x800E5520,0x800E5398,0x800E459C,0x8006E356};
    for(unsigned n=0;n<sizeof conflicts/sizeof conflicts[0];++n) {
        setup_audio();psx_mod_write_byte(conflicts[n],1);CPUState cpu=request(1,1);
        CHECK(jump_audio_sound(&cpu,0x80016C48) && failed && !plays && !calculations);
        CHECK(psx_mod_read_byte(conflicts[n])==1); /* Never clear a native conflict. */
    }
    setup_audio();jump_audio_bound_epoch=0;bank_conflict=1;CPUState cpu=request(3,7);
    CHECK(jump_audio_sound(&cpu,0x80016C48) && failed && !calculations && !plays);same_native();
    setup_audio();jump_audio_bound_epoch=jump_audio_owned_epoch=0;active=1u<<20;cpu=request(3,7);
    CHECK(jump_audio_sound(&cpu,0x80016C48) && failed && !registrations && !stopped);same_native();
    setup_audio();active=1u<<20;private_bank[20]=29;cpu=request(3,7);
    unsigned unchanged_writes=memory_writes;CHECK(!jump_audio_ready() && memory_writes==unchanged_writes);
    CHECK(jump_audio_sound(&cpu,0x80016C48) && failed && !calculations && !plays);
    CHECK((active&(1u<<20)) && !(stopped&(1u<<20)) && !slot_volumes[20]);same_native(); /* Foreign voice is retained. */
    setup_audio();jump_audio_bound_epoch=0;cpu=request(3,7);
    CHECK(jump_audio_sound(&cpu,0x80016C48) && !failed && registrations==2 && plays==1);same_native();
    setup_audio();state_track.count=MMX6_STATE_FRAMES;cpu=request(3,7);
    CHECK(jump_audio_sound(&cpu,0x80016C48) && failed && state_track.count==MMX6_STATE_FRAMES && !calculations);same_native();
}
static void stops(void) {
    setup_audio();CPUState cpu=request(3,7);active=1u<<20;
    CHECK(jump_audio_stop(&cpu,0x8001750C) && cpu.gpr[2]==0xFF000000u);
    CHECK(stopped==(1u<<20) && volumes==1 && !guest_calls);same_native();
    setup_audio();cpu=request(1,1);CHECK(jump_audio_stop(&cpu,0x8001750C) && stopped==(1u<<22));same_native();
    setup_audio();cpu=request(3,3);CHECK(!jump_audio_stop(&cpu,0x8001750C) && !stopped && !volumes);
    const uint32_t callers[]={0x80038604,0x800386F4,0x800387EC,0x80038900,0x8003B23C,
                              0x8003D8C4,0x8003D8D0,0x8003F49C,0x8003F614};
    for(unsigned i=0;i<sizeof callers/sizeof callers[0];++i) {
        unsigned r=i<6?5:7,slot=r==5?22:23;
        setup_audio();cpu=request(1,r);cpu.gpr[16]=PLAYER;cpu.gpr[31]=callers[i];
        psx_mod_write_byte(PLAYER+4,(uint8_t)(i==5 || i==6?2:1));
        CPUState before=cpu;
        CHECK(jump_audio_stop(&cpu,0x8001750C) && !guest_calls && stopped==(1u<<slot) && volumes==1);
        CHECK(cpu.gpr[2]==0xFF000000u);before.gpr[2]=cpu.gpr[2];CHECK(!memcmp(&before,&cpu,sizeof cpu));same_native();
        /* Preserve pending P1 KEYON, masks, registers, metadata, both complete
         * native tables and outside driver state; no native STOP runs. */
        for(unsigned invalid=0;invalid<10;++invalid) {
            setup_audio();cpu=request(1,r);cpu.gpr[16]=PLAYER;cpu.gpr[31]=callers[i];
            psx_mod_write_byte(PLAYER+4,(uint8_t)(i==5 || i==6?2:1));
            if(invalid==0)cpu.gpr[16]+=0x100;
            if(invalid==1)cpu.gpr[31]^=4;
            if(invalid==2)zero_projected=0;
            if(invalid==3)enrolled=0;
            if(invalid==4)ready=0;
            if(invalid==5)psx_mod_write_byte(PLAYER+2,0);
            if(invalid==6)psx_mod_write_byte(PLAYER+0xE7,1);
            if(invalid==7)psx_mod_write_byte(PLAY,9);
            if(invalid==8)psx_mod_write_byte(PLAYER+4,0);
            if(invalid==9)psx_mod_write_byte(PLAYER+4,(uint8_t)(i==5 || i==6?1:2));
            CHECK(!jump_audio_stop(&cpu,0x8001750C) && !stopped && !volumes && !guest_calls);same_native();
        }
    }
    setup_audio();cpu=request(3,7);zero_projected=0;CHECK(!jump_audio_stop(&cpu,0x8001750C) && !stopped);
    setup_audio();cpu=request(255,0);CHECK(jump_audio_stop(&cpu,0x8001750C) && guest_calls==1);
    CHECK(stopped==JUMP_STOP_MASK && volumes==3 && !jump_audio_stop_call);
    setup_audio();cpu=request(3,7);active=1u<<20;private_bank[20]=29;
    CHECK(jump_audio_stop(&cpu,0x8001750C) && failed && !guest_calls && !slot_volumes[20]);
    CHECK((active&(1u<<20)) && !(stopped&(1u<<20)));
    setup_audio();cpu=request(255,0);active=1u<<20;private_bank[20]=29;
    CHECK(jump_audio_stop(&cpu,0x8001750C) && failed && guest_calls==1 && !slot_volumes[20]);
    CHECK((active&(1u<<20)) && !(stopped&(1u<<20)));
    unsigned foreign_volumes=slot_volumes[20];CHECK(jump_audio_activate());
    CHECK((active&(1u<<20)) && !(stopped&(1u<<20)) && slot_volumes[20]==foreign_volumes);
    setup_audio();cpu=request(1,7);cpu.gpr[16]=PLAYER;cpu.gpr[31]=0x8003F49C;
    active=1u<<23;private_bank[23]=29;
    CHECK(jump_audio_stop(&cpu,0x8001750C) && failed && !guest_calls && !slot_volumes[23]);
    CHECK((active&(1u<<23)) && !(stopped&(1u<<23)));same_native();
    setup_audio();cpu=request(1,7);active=1u<<23;private_bank[23]=29;
    CHECK(!jump_audio_ready());
    CHECK(jump_audio_sound(&cpu,0x80016C48) && failed && !calculations && !plays && !slot_volumes[23]);
    CHECK((active&(1u<<23)) && !(stopped&(1u<<23)));same_native();
}
static void original_assets(const char *path) {
    FILE *f=fopen(path,"rb");CHECK(f);CHECK(!fseek(f,0,SEEK_END));long length=ftell(f);
    CHECK(length>0 && length<2*1024*1024 && !fseek(f,0,SEEK_SET));
    uint8_t *data=malloc((size_t)length);CHECK(data && fread(data,1,(size_t)length,f)==(size_t)length);fclose(f);
    setup_audio();CHECK(jump_audio_activate());
    /* Hash/type validation precedes allocations and guest header writes. */
    unsigned writes=memory_writes;CHECK(!jump_audio_load(data,2047) && !jump_audio_loaded && memory_writes==writes);
    for(unsigned nth=1;nth<=4;++nth) {
        fail_allocation=nth;allocations=0;
        CHECK(!jump_audio_load(data,(size_t)length) && !jump_audio_loaded && memory_writes==writes);
        for(unsigned i=0;i<2;++i)CHECK(!jump_audio_banks[i].parsed && !jump_audio_banks[i].samples);
    }
    fail_allocation=0;allocations=0;bank_conflict=0;registrations=0;
    CHECK(jump_audio_load(data,(size_t)length) && jump_audio_ready() && registrations==2);
    CHECK(jump_audio_banks[0].layout.sample_bytes==123408 && jump_audio_banks[1].layout.sample_bytes==52096);
    for(unsigned i=0;i<2;++i) {
        JumpAudioBank *b=&jump_audio_banks[i];Mmx6AssetView original;
        CHECK(mmx6_coop_dat_asset(data,(size_t)length,85,12+i*2,&original));
        CHECK(!memcmp(b->samples,original.data,original.size));
        uint8_t restored[8192];capture(b->guest,restored,b->layout.bytes);CHECK(!memcmp(restored,b->parsed,b->layout.bytes));
    }
    ++epoch;active=0;CHECK(!jump_audio_ready() && jump_audio_bind() && jump_audio_ready());
    CHECK(jump_audio_activate() && !jump_audio_loaded && !jump_audio_call);
    /* Corrupt actual source bytes, preserving structural extents: exact digest
     * rejection is before any published resource or registry mutation. */
    Mmx6AssetView sample;CHECK(mmx6_coop_dat_asset(data,(size_t)length,85,12,&sample));
    data[sample.data-data]^=1;writes=memory_writes;registrations=0;
    CHECK(!jump_audio_load(data,(size_t)length) && !jump_audio_loaded && memory_writes==writes && !registrations);
    free(data);puts("original Zero immutable header/body load, allocation rollback and epoch rebind PASS");
}
int main(int argc,char **argv) {
    transactions();stops();
    if(argc==2)original_assets(argv[1]);else CHECK(argc==1);
    puts("actual X6 private jump callbacks: exact native rollback, routing, refusal and stop PASS");return 0;
}
