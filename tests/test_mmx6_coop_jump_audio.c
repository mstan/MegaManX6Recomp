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
static uint64_t private_owner[24];
static unsigned plays,volumes,registrations,calculations,keyons,status_reads;
static unsigned slot_volumes[24];
static int bank_conflict,play_failure,wrong_keyon,charged_call,no_keyon,bad_output;
static int local_scope;
static uint32_t suppressed_result,skip_voices;
static uint32_t played_bank,played_slot,played_mode;
static uint16_t played[8];
int psx_mod_texture_banks_supported(void){return 1;}
int psx_mod_local_view_scope(void){return local_scope;}
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
    CHECK(bank>=28 && bank<=31);CHECK(bytes && size==jump_audio_banks[bank&1u].layout.sample_bytes);
    ++registrations;return !bank_conflict;
}
uint64_t psx_mod_spu_private_voice_owner(unsigned slot){CHECK(slot<24);return private_owner[slot];}
int psx_mod_spu_private_voice_claim(uint64_t owner,uint32_t mask) {
    CHECK(owner==JUMP_AUDIO_OWNER && mask==JUMP_STOP_MASK);
    for(unsigned s=0;s<24;++s)if(mask&(1u<<s))
        if((private_owner[s] && private_owner[s]!=owner) || (!private_owner[s] && (active&(1u<<s))))return 0;
    for(unsigned s=0;s<24;++s)if(mask&(1u<<s))private_owner[s]=owner;
    return 1;
}
int psx_mod_spu_private_voice_play_owned(uint64_t owner,unsigned slot,uint32_t bank,const uint16_t regs[8],unsigned mode) {
    same_native();CHECK(!jump_audio_call && !jump_audio_keyon_call && !state_track.count);
    CHECK(owner==JUMP_AUDIO_OWNER && private_owner[slot]==owner);
    ++plays;played_slot=slot;played_bank=bank;played_mode=mode;memcpy(played,regs,sizeof played);
    if(play_failure)return 0;
    active|=1u<<slot;private_bank[slot]=bank;return 1;
}
int psx_mod_spu_private_voice_volume_owned(uint64_t owner,unsigned slot,uint16_t left,uint16_t right) {
    CHECK(slot<24 && (JUMP_STOP_MASK&(1u<<slot)) && private_owner[slot]==owner && owner==JUMP_AUDIO_OWNER);
    CHECK(!left && !right);++volumes;++slot_volumes[slot];return 1;
}
int psx_mod_spu_private_voice_stop_owned(uint64_t owner,uint32_t mask){
    CHECK(!(mask&~JUMP_STOP_MASK));stopped|=mask;
    for(unsigned s=0;s<24;++s)if(mask&(1u<<s))CHECK(owner==JUMP_AUDIO_OWNER && private_owner[s]==owner);
    /* The real DSP keeps active1 through release/END_STOP; it is not proof
     * that a sample is still audible, nor a private-slot allocation flag. */
    return 1;
}
uint32_t psx_mod_call_guest_uncharged(CPUState *cpu,uint32_t target,uint32_t ret,
    uint32_t a0,uint32_t a1,uint32_t a2,uint32_t a3,uint32_t budget,int *charged) {
    (void)ret;CHECK(!budget && jump_audio_call && state_track.count==4 && !snapshot_ready());
    *charged=charged_call;
    if(target==0x80016C48) {
        ++calculations;unsigned group=a0&127u;CHECK(group==1 || group==3);CHECK(a2==PLAYER);
        JumpAudioBank *b=&jump_audio_banks[group==3];
        CHECK(psx_mod_read_word(0x80097738+group*4)==b->guest+b->layout.vab);
        CHECK(psx_mod_read_word(0x80097778+group*4)==b->guest+8);
        CHECK(!memcmp(memory(0x800E25E0),jump_audio_priorities,24));
        for(unsigned i=0;i<2;++i) {
            JumpAudioBank *v=&jump_audio_banks[i];unsigned id=v->layout.id;
            CHECK(psx_mod_read_byte(0x800E5690+id)==1);
            CHECK(psx_mod_read_word(0x800E56F0+id*4)==0);
            CHECK(psx_mod_read_word(0x800E55C8+id*4)==v->guest+v->layout.vab);
        }
        const uint8_t *record=b->parsed+8+(a1&255u)*4;
        unsigned count=1+((record[3]>>5)&3u),first=record[3]&31u;
        for(unsigned v=0;v<count;++v) {
            CPUState nested=*cpu;nested.gpr[4]=1u<<(first+v);
            CHECK(jump_audio_status(&nested,0x80055B14));++status_reads;
            CHECK(nested.gpr[2]==((active&(1u<<(first+v)))?1u:0u));
            if(no_keyon || (skip_voices&(1u<<(first+v))))continue;
            JumpAudioBank *effective=&jump_audio_banks[(record[0]&63u)==15];
            unsigned t=(record[2]>>4)+v,program=(record[1]&127u)+t/16u;
            const uint8_t *p=effective->parsed+effective->layout.programs+program*16u;
            unsigned rank=(unsigned)p[8]|(unsigned)p[9]<<8;
            const uint8_t *tone=effective->parsed+effective->layout.tones+rank*512u+(t%16u)*32u;
            nested=*cpu;nested.gpr[4]=wrong_keyon?24:first+v;
            nested.gpr[5]=effective->layout.id;nested.gpr[6]=program;nested.gpr[7]=t%16u;
            nested.gpr[29]=0x801D0000;
            psx_mod_write_word(nested.gpr[29]+16,tone[6]);psx_mod_write_word(nested.gpr[29]+20,tone[5]);
            psx_mod_write_word(nested.gpr[29]+24,79);psx_mod_write_word(nested.gpr[29]+28,113);
            CHECK(jump_audio_keyon(&nested,0x8005A9D4));
            if(nested.gpr[2]==UINT32_MAX)return nested.gpr[2];
        }
        return no_keyon?suppressed_result:0;
    }
    CHECK(target==0x8005A9D4 && jump_audio_keyon_call);++keyons;
    CHECK(a0==jump_audio_slot && a1==((jump_audio_bank&1u)?15u:14u) && a3==jump_audio_tone);
    const JumpAudioBank *b=&jump_audio_banks[a1==15];
    const uint8_t *p=b->parsed+b->layout.programs+a2*16u;
    unsigned rank=(unsigned)p[8]|(unsigned)p[9]<<8;
    const uint8_t *tone=b->parsed+b->layout.tones+rank*512u+a3*32u;
    unsigned sample=(unsigned)tone[22]|(unsigned)tone[23]<<8,before=sample-1u;
    const uint8_t *start=b->parsed+b->layout.programs+(before/2u)*16u+12u+(before&1u)*2u;
    /* Source closure: dirty+register+metadata(0x38 stride), all masks/history,
     * selected VAB globals and tables. Touch the entire owned span. */
    for(unsigned i=0;i<JUMP_DRIVER_BYTES;++i)psx_mod_write_byte(JUMP_DRIVER+i,(uint8_t)(i*13+9));
    memset(memory(0x800E25E0),0xA1,24);memset(memory(0x80097738),0xB2,128);
    psx_mod_write_word(0x800E459C,0x1234);psx_mod_write_word(0x800E155C,0x5678);
    uint32_t r=0x800E53A0+a0*16;
    const uint16_t actual[6]={1234,2345,0x478,(uint16_t)(start[0]|(unsigned)start[1]<<8),
        (uint16_t)(tone[16]|(unsigned)tone[17]<<8),(uint16_t)(tone[18]|(unsigned)tone[19]<<8)};
    for(unsigned i=0;i<6;++i)psx_mod_write_half(r+i*2,actual[i]);
    psx_mod_write_half(0x800E4E40+a0*0x38+0x1E,0);
    psx_mod_write_half(0x800E4E40+a0*0x38+0x2A,0);
    if(bad_output==1)psx_mod_write_half(0x800E4E40+a0*0x38+0x1E,1);
    if(bad_output==2)psx_mod_write_half(0x800E4E40+a0*0x38+0x2A,1);
    if(bad_output==3)psx_mod_write_half(r+6,16); /* Outside this bank's128bytes. */
    if(bad_output==4)psx_mod_write_half(r+8,actual[4]^1u);
    psx_mod_write_word(0x800E4E38,1u<<a0);psx_mod_write_word(0x800E4E34,1u<<a0);
    return 0;
}
static void test16(uint8_t *p,unsigned v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
static void test_record(JumpAudioBank *b,unsigned record,unsigned id,unsigned program,unsigned tone,unsigned slot,unsigned count) {
    uint8_t *r=b->parsed+8u+record*4u;
    r[0]=(uint8_t)(0x80u|id);r[1]=(uint8_t)program;r[2]=(uint8_t)(tone<<4);
    r[3]=(uint8_t)(slot|((count-1u)<<5));
}
static void setup_audio(void) {
    private_actor=default_private_actor;jump_audio_character=MMX6_COOP_CHARACTER_ZERO;
    memset(test_ram,0,sizeof test_ram);memset(&state_track,0,sizeof state_track);
    failed=jump_audio_faulted=jump_audio_call=jump_audio_keyon_call=jump_audio_stop_call=0;
    bank_conflict=play_failure=wrong_keyon=charged_call=no_keyon=bad_output=0;
    local_scope=0;suppressed_result=skip_voices=0;
    jump_audio_clear_calculation();memset(jump_audio_priorities,0,sizeof jump_audio_priorities);
    ready=enrolled=zero_projected=1;zero_world=0;active=stopped=0;
    for(unsigned s=0;s<24;++s) {
        private_bank[s]=s==20?31:30;
        private_owner[s]=(JUMP_STOP_MASK&(1u<<s))?JUMP_AUDIO_OWNER:0;
    }
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
        unsigned records=i?18:32,vab=8+records*4,programs=vab+32,tones=programs+2048;
        b->layout=(Mmx6JumpAudioHeader){i?3:1,i?15:14,i?31:30,tones+3*512+512,128,vab,programs,tones,records,8};
        memset(b->parsed,0,8192);put32(b->parsed,((i?3u:1u)<<24)|vab);put32(b->parsed+4,128);
        test16(b->parsed+vab+18,3);test16(b->parsed+vab+22,8);
        for(unsigned p=0;p<3;++p) {
            b->parsed[programs+p*16]=16;put32(b->parsed+programs+p*16+8,p);
            for(unsigned t=0;t<16;++t) {
                uint8_t *tone=b->parsed+tones+p*512+t*32;
                tone[6]=(uint8_t)(60+p);tone[5]=(uint8_t)(p*2);
                test16(tone+16,0x80FF+p);test16(tone+18,0x1FC0+p);
                test16(tone+22,(t+p)%8+1);
            }
        }
        for(unsigned s=0;s<=8;++s)test16(b->parsed+programs+(s/2u)*16u+12u+(s&1u)*2u,s*2u);
        for(unsigned r=1;r<=(i?7u:8u);++r) {
            test_record(b,r,b->layout.id,0,!i && r>=2?r+1:r,i?20:r>=7?23:22,1);
        }
        test_record(b,0,b->layout.id,0,0,i?20:21,1);
    }
    test_record(&jump_audio_banks[0],11,14,0,14,20,4); /* Program rollover, four calculations. */
    test_record(&jump_audio_banks[0],12,14,0x81,7,3,1); /* Native program high flag. */
    test_record(&jump_audio_banks[1],17,14,1,7,3,1); /* Effective effects-bank alias. */
    test_record(&jump_audio_banks[1],14,15,1,0,23,1);
    const unsigned extra_slots[]={0,8,9,11};
    for(unsigned n=0;n<4;++n)test_record(&jump_audio_banks[0],19+n,14,2,n,extra_slots[n],1);
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
        unsigned t=groups[n]==1 && records[n]>=2?records[n]+1:records[n],start=(t%8u)*2u;
        CHECK(played[0]==1234 && played[1]==2345 && played[2]==0x478 && played[3]==start);
        CHECK(played[4]==0x80FF && played[5]==0x1FC0 && !played[6] && played[7]==start);
        CHECK(!jump_audio_call && !jump_audio_keyon_call && !jump_audio_calculated && !state_track.count);
        CHECK(jump_audio_extra_idle());for(unsigned s=0;s<24;++s)CHECK(jump_audio_priorities[s]==0xA1);
        CHECK(jump_audio_sound(&cpu,0x80016C48)==1 && plays==2 && !failed);same_native(); /* Own active replacement. */
    }
    for(unsigned r=1;r<=8;++r) {
        setup_audio();CPUState cpu=request(1,r);cpu.gpr[6]=PLAYER+0x100;
        CHECK(!jump_audio_sound(&cpu,0x80016C48) && !plays && !calculations && !failed);same_native();
        setup_audio();cpu=request(1,r);psx_mod_write_byte(PLAYER+4,4);
        CHECK(!jump_audio_sound(&cpu,0x80016C48) && !plays && !calculations && !failed);same_native();
    }
    for(unsigned n=0;n<3;++n) {
        setup_audio();CPUState cpu=request(3,7);
        if(n==0)zero_projected=0;
        if(n==1)local_scope=1;
        if(n==2)psx_mod_write_byte(0x80090D53,255);
        CHECK(!jump_audio_sound(&cpu,0x80016C48) && !plays && !calculations && !failed);same_native();
    }
    /* Body ownership is independent of one vocal wrapper, shared defense
     * parts, and the living phase. Raw flag/record arguments stay intact. */
    for(unsigned phase=0;phase<=3;++phase) {
        setup_audio();CPUState cpu=request(0x83,0x103);cpu.gpr[31]=0x801EBE90;
        psx_mod_write_byte(PLAYER+4,(uint8_t)phase);psx_mod_write_byte(PLAY+0x5F,0x20);
        CHECK(jump_audio_sound(&cpu,0x80016C48) && !failed && plays==1 && played_bank==31);same_native();
    }
    for(unsigned n=0;n<3;++n) {
        setup_audio();CPUState cpu=request(3,7);
        wrong_keyon=n==0;charged_call=n==1;play_failure=n==2;
        CHECK(jump_audio_sound(&cpu,0x80016C48) && cpu.gpr[2]==UINT32_MAX && failed);
        same_native();CHECK(!jump_audio_call && !jump_audio_keyon_call && !state_track.count);
        CHECK(plays==(n==2?1u:0u) && jump_audio_extra_idle());
    }
    for(unsigned n=0;n<2;++n) {
        setup_audio();CPUState cpu=request(3,7);no_keyon=1;suppressed_result=n?UINT32_MAX:0;
        jump_audio_priorities[20]=9;
        CHECK(jump_audio_sound(&cpu,0x80016C48) && cpu.gpr[2]==suppressed_result && !failed && !plays);
        CHECK(jump_audio_priorities[20]==9 && jump_audio_extra_idle());same_native();
    }
    for(unsigned n=1;n<=4;++n) {
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
    setup_audio();jump_audio_bound_epoch=jump_audio_owned_epoch=0;active=1u<<20;private_owner[20]=0;cpu=request(3,7);
    CHECK(jump_audio_sound(&cpu,0x80016C48) && failed && !registrations && !(stopped&(1u<<20)));same_native();
    setup_audio();active=1u<<20;private_owner[20]=JUMP_AUDIO_OWNER+1;cpu=request(3,7);
    unsigned unchanged_writes=memory_writes;CHECK(!jump_audio_ready() && memory_writes==unchanged_writes);
    CHECK(jump_audio_sound(&cpu,0x80016C48) && failed && !calculations && !plays);
    CHECK((active&(1u<<20)) && !(stopped&(1u<<20)) && !slot_volumes[20]);same_native(); /* Foreign voice is retained. */
    setup_audio();jump_audio_bound_epoch=0;cpu=request(3,7);
    CHECK(jump_audio_sound(&cpu,0x80016C48) && !failed && registrations==2 && plays==1);same_native();
    setup_audio();state_track.count=MMX6_STATE_FRAMES;cpu=request(3,7);
    CHECK(jump_audio_sound(&cpu,0x80016C48) && failed && state_track.count==MMX6_STATE_FRAMES && !calculations);same_native();

    /* Effective-bank aliases and nonzero programs retain their identities. */
    const unsigned gs[]={3,3,1,1,1,1,1},rs[]={17,14,12,19,20,21,22},slots[]={3,23,3,0,8,9,11};
    for(unsigned n=0;n<7;++n) {
        setup_audio();cpu=request(gs[n],rs[n]);CHECK(jump_audio_sound(&cpu,0x80016C48) && !failed && plays==1);
        CHECK(played_slot==slots[n] && played_bank==(n==1?31u:30u) && jump_audio_extra_idle());same_native();
    }
    setup_audio();cpu=request(1,11);CHECK(jump_audio_sound(&cpu,0x80016C48) && !failed && plays==4 && keyons==4);
    CHECK(played_slot==23 && played[4]==0x8100 && played[5]==0x1FC1 && jump_audio_extra_idle());same_native();
    setup_audio();skip_voices=(1u<<22)|(1u<<23);cpu=request(1,11);
    CHECK(jump_audio_sound(&cpu,0x80016C48) && !failed && plays==2 && keyons==2 && status_reads==4);same_native();
    setup_audio();cpu=request(1,7);CHECK(jump_audio_sound(&cpu,0x80016C48) && played_bank==30);
    cpu=request(3,14);CHECK(jump_audio_sound(&cpu,0x80016C48) && !failed && played_slot==23 && played_bank==31);same_native();
    for(unsigned n=0;n<2;++n) {
        setup_audio();cpu=request(3,n?18:13);
        CHECK(jump_audio_sound(&cpu,0x80016C48) && !failed && !calculations && !plays);
        CHECK(cpu.gpr[2]==(n?0xFFFFFFFEu:0xFFFFFFFBu));same_native();
    }
    /* Foreign reservations are forbidden even inactive, on the SAME bank. */
    for(unsigned slot=0;slot<24;++slot)if(JUMP_STOP_MASK&(1u<<slot)) {
        setup_audio();private_owner[slot]=JUMP_AUDIO_OWNER+1;cpu=request(1,1);
        CHECK(!jump_audio_ready() && jump_audio_sound(&cpu,0x80016C48) && failed && !plays && !calculations);
        CHECK(!slot_volumes[slot] && !(stopped&(1u<<slot)) && private_owner[slot]==JUMP_AUDIO_OWNER+1);same_native();
    }
}
static void stops(void) {
    setup_audio();CPUState cpu=request(3,7);active=1u<<20;
    CHECK(!jump_audio_stop(&cpu,0x8001750C) && !stopped && !volumes && !guest_calls);same_native();
    setup_audio();cpu=request(1,1);CHECK(!jump_audio_stop(&cpu,0x8001750C) && !stopped);same_native();
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
            if(invalid==7)local_scope=1;
            if(invalid==8)psx_mod_write_byte(PLAYER+4,0);
            if(invalid==9)psx_mod_write_byte(PLAYER+4,(uint8_t)(i==5 || i==6?1:2));
            CHECK(!jump_audio_stop(&cpu,0x8001750C) && !stopped && !volumes && !guest_calls);same_native();
        }
    }
    setup_audio();cpu=request(3,7);zero_projected=0;CHECK(!jump_audio_stop(&cpu,0x8001750C) && !stopped);
    setup_audio();cpu=request(255,0);CHECK(jump_audio_stop(&cpu,0x8001750C) && guest_calls==1);
    CHECK(stopped==JUMP_STOP_MASK && volumes==9 && !jump_audio_stop_call);
    setup_audio();cpu=request(255,0);active=1u<<20;private_owner[20]=JUMP_AUDIO_OWNER+1;
    CHECK(jump_audio_stop(&cpu,0x8001750C) && failed && guest_calls==1 && !slot_volumes[20]);
    CHECK((active&(1u<<20)) && !(stopped&(1u<<20)));
    unsigned foreign_volumes=slot_volumes[20];CHECK(jump_audio_activate());
    CHECK((active&(1u<<20)) && !(stopped&(1u<<20)) && slot_volumes[20]==foreign_volumes);
    setup_audio();cpu=request(1,7);cpu.gpr[16]=PLAYER;cpu.gpr[31]=0x8003F49C;
    active=1u<<23;private_owner[23]=JUMP_AUDIO_OWNER+1;
    CHECK(jump_audio_stop(&cpu,0x8001750C) && failed && !guest_calls && !slot_volumes[23]);
    CHECK((active&(1u<<23)) && !(stopped&(1u<<23)));same_native();
    setup_audio();cpu=request(1,7);active=1u<<23;private_owner[23]=JUMP_AUDIO_OWNER+1;
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
    /* Actual original record data through the actual adapter. The native
     * calculation is still an explicit guest double, never gameplay evidence. */
    unsigned routed=0;plays=0;
    for(unsigned i=0;i<2;++i)for(unsigned r=0;r<jump_audio_banks[i].layout.records;++r) {
        const uint8_t *entry=jump_audio_banks[i].parsed+8u+r*4u;
        if(!(entry[0]|entry[1]|entry[2]|entry[3]))continue;
        CPUState cpu=request(i?3:1,r);
        CHECK(jump_audio_sound(&cpu,0x80016C48) && !failed && !cpu.gpr[2] && jump_audio_extra_idle());
        same_native();++routed;
    }
    CHECK(routed==45 && plays==47);
    ++epoch;active=0;memset(private_owner,0,sizeof private_owner);
    CHECK(!jump_audio_ready() && jump_audio_bind() && jump_audio_ready());
    CHECK(jump_audio_activate() && !jump_audio_loaded && !jump_audio_call);
    /* Corrupt actual source bytes, preserving structural extents: exact digest
     * rejection is before any published resource or registry mutation. */
    Mmx6AssetView sample;CHECK(mmx6_coop_dat_asset(data,(size_t)length,85,12,&sample));
    data[sample.data-data]^=1;writes=memory_writes;registrations=0;
    CHECK(!jump_audio_load(data,(size_t)length) && !jump_audio_loaded && memory_writes==writes && !registrations);
    free(data);puts("original Zero load, 45 records/47 mocked calculations, allocation rollback and epoch rebind PASS");
}
static void character_bank_pairs(void) {
    setup_audio();
    Mmx6PrivateAudioBank views[2]={{jump_audio_banks[0].parsed,&jump_audio_banks[0].layout},
        {jump_audio_banks[1].parsed,&jump_audio_banks[1].layout}};
    for(unsigned base=28;base<=30;base+=2) {
        jump_audio_banks[0].layout.bank=base;jump_audio_banks[1].layout.bank=base+1;
        Mmx6PrivateAudioRecord meta;uint32_t mask=0;
        CHECK(mmx6_private_audio_validate(views,&mask)==MMX6_JUMP_AUDIO_OK && mask==JUMP_STOP_MASK);
        CHECK(mmx6_private_audio_record(views,1,1,&meta)==MMX6_JUMP_AUDIO_OK && meta.voices[0].bank==base);
        CHECK(mmx6_private_audio_record(views,3,1,&meta)==MMX6_JUMP_AUDIO_OK && meta.voices[0].bank==base+1);
        /* Original voice records may alias the effects VAB. The alias must
         * stay inside the same character's pair for either roster. */
        CHECK(mmx6_private_audio_record(views,3,17,&meta)==MMX6_JUMP_AUDIO_OK && meta.voices[0].bank==base);
    }
    const unsigned mixed[2][2]={{28,31},{30,29}};
    for(unsigned i=0;i<2;++i) {
        jump_audio_banks[0].layout.bank=mixed[i][0];jump_audio_banks[1].layout.bank=mixed[i][1];
        Mmx6PrivateAudioRecord meta;uint32_t mask=0;
        CHECK(mmx6_private_audio_validate(views,&mask)==MMX6_JUMP_AUDIO_ARGUMENT);
        CHECK(mmx6_private_audio_record(views,3,17,&meta)==MMX6_JUMP_AUDIO_ARGUMENT);
    }
    setup_audio();
}
static void opposite_character_audio_transaction(void) {
    setup_audio();
    Mmx6CoopRosterNative native={1,5,1,5,0};Mmx6CoopRoster roster;
    CHECK(mmx6_coop_roster_resolve(&native,&roster)==MMX6_COOP_ROSTER_OK && private_roster_bind(&roster));
    jump_audio_character=MMX6_COOP_CHARACTER_X;
    jump_audio_banks[0].layout.bank=28;jump_audio_banks[1].layout.bank=29;
    psx_mod_write_byte(PLAYER+2,0);psx_mod_write_byte(PLAYER+0xE7,0);
    CPUState cpu=request(1,1);
    CHECK(jump_audio_sound(&cpu,0x80016C48) && !failed && calculations==1 && plays==1 && played_bank==28);
    same_native();CHECK(!state_track.count && jump_audio_extra_idle());
    /* A matching seat is insufficient: reject another character/form before
     * either the native calculation or private DSP sees the request. */
    const unsigned wrong[3][2]={{1,5},{0,5},{1,0}};
    for(unsigned i=0;i<3;++i) {
        psx_mod_write_byte(PLAYER+2,(uint8_t)wrong[i][0]);psx_mod_write_byte(PLAYER+0xE7,(uint8_t)wrong[i][1]);
        cpu=request(1,1);CHECK(!jump_audio_sound(&cpu,0x80016C48) && !failed && calculations==1 && plays==1);
        same_native();
    }
    psx_mod_write_byte(PLAYER+2,0);psx_mod_write_byte(PLAYER+0xE7,0);
    zero_projected=0;cpu=request(1,1);
    CHECK(!jump_audio_sound(&cpu,0x80016C48) && calculations==1 && plays==1);
    zero_projected=1;
    jump_audio_character=MMX6_COOP_CHARACTER_ZERO;cpu=request(1,1);
    CHECK(!jump_audio_sound(&cpu,0x80016C48) && calculations==1 && plays==1);
    jump_audio_bound_epoch=0;unsigned registered=registrations;
    CHECK(!jump_audio_bind() && registrations==registered && !jump_audio_ready());
    setup_audio();
}
static void opposite_original_audio_assets(const char *path) {
    FILE *stream=fopen(path,"rb");CHECK(stream && !fseek(stream,0,SEEK_END));
    long length=ftell(stream);CHECK(length>0 && !fseek(stream,0,SEEK_SET));
    uint8_t *data=malloc((size_t)length);CHECK(data && fread(data,1,(size_t)length,stream)==(size_t)length);
    fclose(stream);setup_audio();
    Mmx6CoopRosterNative native={1,5,1,5,0};Mmx6CoopRoster roster;
    CHECK(mmx6_coop_roster_resolve(&native,&roster)==MMX6_COOP_ROSTER_OK && private_roster_bind(&roster));
    psx_mod_write_byte(PLAYER+2,0);psx_mod_write_byte(PLAYER+0xE7,0);
    CHECK(jump_audio_activate());registrations=0;
    CHECK(jump_audio_load(data,(size_t)length) && jump_audio_ready() && registrations==2);
    CHECK(jump_audio_character==0 && jump_audio_banks[0].layout.sample_bytes==172768 &&
        jump_audio_banks[1].layout.sample_bytes==52608);
    for(unsigned i=0;i<2;++i) {
        Mmx6AssetView original;CHECK(mmx6_coop_dat_asset(data,(size_t)length,86,12+i*2,&original));
        CHECK(!memcmp(jump_audio_banks[i].samples,original.data,original.size));
    }
    unsigned routed=0;plays=0;
    for(unsigned i=0;i<2;++i)for(unsigned r=0;r<jump_audio_banks[i].layout.records;++r) {
        const uint8_t *entry=jump_audio_banks[i].parsed+8u+r*4u;
        if(!(entry[0]|entry[1]|entry[2]|entry[3]))continue;
        CPUState cpu=request(i?3:1,r);
        CHECK(jump_audio_sound(&cpu,0x80016C48) && !failed && !cpu.gpr[2] && jump_audio_extra_idle());
        same_native();++routed;
    }
    CHECK(routed==54 && plays==56);
    uint32_t handles[2]={jump_audio_banks[0].guest,jump_audio_banks[1].guest};
    unsigned hashed=0;for(unsigned i=0;i<sizeof jump_audio_asset_sha;++i)hashed|=jump_audio_asset_sha[i];
    CHECK(hashed);
    jump_audio_release_character();private_actor=default_private_actor;
    CHECK(!jump_audio_loaded && !jump_audio_bound_epoch && !jump_audio_owned_epoch && jump_audio_extra_idle());
    for(unsigned i=0;i<sizeof jump_audio_asset_sha;++i)CHECK(!jump_audio_asset_sha[i]);
    for(unsigned i=0;i<2;++i)CHECK(!jump_audio_banks[i].parsed && !jump_audio_banks[i].samples && !jump_audio_banks[i].layout.bytes);
    CHECK(jump_audio_load(data,(size_t)length) && jump_audio_ready());
    CHECK(jump_audio_banks[0].layout.bank==30 && jump_audio_banks[1].layout.bank==31);
    CHECK(jump_audio_banks[0].guest==handles[0] && jump_audio_banks[1].guest==handles[1]);
    jump_audio_release_character();CHECK(private_roster_bind(&roster));
    CHECK(jump_audio_load(data,(size_t)length) && jump_audio_ready());
    CHECK(jump_audio_banks[0].layout.bank==28 && jump_audio_banks[1].layout.bank==29);
    CHECK(jump_audio_banks[0].guest==handles[0] && jump_audio_banks[1].guest==handles[1]);
    CHECK(jump_audio_activate());
    Mmx6AssetView sample;CHECK(mmx6_coop_dat_asset(data,(size_t)length,86,12,&sample));
    data[sample.data-data]^=1;unsigned writes=memory_writes;registrations=0;
    CHECK(!jump_audio_load(data,(size_t)length) && !jump_audio_loaded && memory_writes==writes && !registrations);
    jump_audio_release_character();free(data);setup_audio();puts("original base-X load, 54 records/56 mocked calculations, digest refusal and roster switch PASS");
}
int main(int argc,char **argv) {
    transactions();stops();character_bank_pairs();opposite_character_audio_transaction();
    if(argc>=2)original_assets(argv[1]);else CHECK(argc==1);
    if(argc==3)opposite_original_audio_assets(argv[2]);else CHECK(argc<=2);
    puts("actual X6 private character callbacks: exact native rollback, routing, refusal and stop PASS");return 0;
}
