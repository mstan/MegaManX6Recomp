/* Included after guest()/capture()/project(). Character records retain their
 * own VAB/program/tone/voice identities; private slots are leased by title. */
#include "mmx6_coop_jump_audio.h"
#include "psx_sha256.h"
#include "spu.h"
typedef struct {
    Mmx6JumpAudioHeader layout;
    uint8_t *parsed,*samples;
    uint32_t guest;
} JumpAudioBank;
static JumpAudioBank jump_audio_banks[2];
static uint8_t jump_audio_asset_sha[32];
static unsigned jump_audio_loaded,jump_audio_call,jump_audio_keyon_call,jump_audio_stop_call;
static uint32_t jump_audio_bound_epoch,jump_audio_owned_epoch;
static unsigned jump_audio_slot,jump_audio_bank,jump_audio_tone,jump_audio_mode,jump_audio_calculated,jump_audio_faulted;
static uint32_t jump_audio_stop_mask;
static uint16_t jump_audio_registers[8];
typedef struct { uint32_t slot,bank,mode;uint16_t regs[8]; } JumpAudioVoice;
static JumpAudioVoice jump_audio_voices[4];
static Mmx6PrivateAudioRecord jump_audio_meta;
static uint8_t jump_audio_priorities[24];
#define JUMP_AUDIO_OWNER UINT64_C(0x4D4D583650320001)
enum { JUMP_DRIVER=0x800E4E30u,JUMP_DRIVER_BYTES=0x900,
       JUMP_STOP_MASK=0x00F00B09u };

static uint32_t jump_audio_owned_mask(void) {
    uint32_t mask=0;
    for(unsigned slot=0;slot<24;++slot)
        if(psx_mod_spu_private_voice_owner(slot)==JUMP_AUDIO_OWNER)mask|=1u<<slot;
    return mask;
}
static int jump_audio_extra_idle(void) {
    const uint8_t *parts[]={(const uint8_t*)&jump_audio_meta,(const uint8_t*)jump_audio_voices};
    const size_t sizes[]={sizeof jump_audio_meta,sizeof jump_audio_voices};
    for(unsigned p=0;p<2;++p)for(size_t i=0;i<sizes[p];++i)if(parts[p][i])return 0;
    return 1;
}
static void jump_audio_clear_calculation(void) {
    jump_audio_slot=jump_audio_bank=jump_audio_tone=jump_audio_mode=jump_audio_calculated=0;
    memset(jump_audio_registers,0,sizeof jump_audio_registers);
    memset(&jump_audio_meta,0,sizeof jump_audio_meta);memset(jump_audio_voices,0,sizeof jump_audio_voices);
}

static int jump_audio_slot_available(unsigned slot,uint32_t bank,uint32_t epoch) {
    (void)bank;(void)epoch;SpuVoiceState voice;
    if(!spu_get_private_voice_state(slot,&voice))return 0;
    uint64_t owner=psx_mod_spu_private_voice_owner(slot);
    return owner==JUMP_AUDIO_OWNER || (!owner && !voice.active);
}
static int jump_audio_stop_owned(uint32_t mask) {
    uint32_t owned=jump_audio_owned_mask()&mask;
    int ok=owned==mask;
    for(unsigned slot=0;slot<24;++slot)if(owned&(1u<<slot))
        if(!psx_mod_spu_private_voice_volume_owned(JUMP_AUDIO_OWNER,slot,0,0))ok=0;
    if(owned && !psx_mod_spu_private_voice_stop_owned(JUMP_AUDIO_OWNER,owned))ok=0;
    return ok;
}
static void jump_audio_stop_private(void) {jump_audio_stop_owned(JUMP_STOP_MASK);}
static int jump_audio_fault(const char *reason) {
    jump_audio_faulted=1;failed=1;
    fprintf(stderr,"mmx6 co-op: private jump audio refused (%s)\n",reason);
    jump_audio_stop_private();return 0;
}
static int jump_audio_bind(void) {
    uint32_t epoch=psx_mod_spu_sample_bank_epoch();
    if(!jump_audio_loaded || !epoch)return 0;
    for(unsigned slot=0;slot<24;++slot)
        if((JUMP_STOP_MASK&(1u<<slot)) && !jump_audio_slot_available(slot,0,epoch))return 0;
    if(epoch==jump_audio_bound_epoch && (jump_audio_owned_mask()&JUMP_STOP_MASK)==JUMP_STOP_MASK)return 1;
    for(unsigned i=0;i<2;++i) {
        JumpAudioBank *b=&jump_audio_banks[i];
        if(!b->parsed || !b->samples || !b->guest ||
            !psx_mod_spu_sample_bank(b->layout.bank,b->samples,b->layout.sample_bytes))return 0;
    }
    if(!psx_mod_spu_private_voice_claim(JUMP_AUDIO_OWNER,JUMP_STOP_MASK))return 0;
    jump_audio_bound_epoch=jump_audio_owned_epoch=epoch;return 1;
}
static int jump_audio_ready(void) {
    if(!jump_audio_loaded || !jump_audio_bound_epoch ||
        jump_audio_bound_epoch!=psx_mod_spu_sample_bank_epoch())return 0;
    for(unsigned i=0;i<2;++i) {
        const JumpAudioBank *b=&jump_audio_banks[i];
        if(!b->guest || !b->parsed || !b->samples || !b->layout.bytes ||
            b->layout.bytes>MMX6_JUMP_AUDIO_HEADER_BYTES || !b->layout.sample_bytes ||
            b->layout.sample_bytes>=0x80000u)return 0;
    }
    return (jump_audio_owned_mask()&JUMP_STOP_MASK)==JUMP_STOP_MASK;
}
static int jump_audio_activate(void) {
    jump_audio_stop_private();
    for(unsigned i=0;i<2;++i) {
        JumpAudioBank *b=&jump_audio_banks[i];uint32_t address=b->guest;
        free(b->parsed);free(b->samples);memset(b,0,sizeof *b);b->guest=address;
        if(!b->guest)b->guest=psx_mod_alloc_guest_memory(MMX6_JUMP_AUDIO_HEADER_BYTES,16);
    }
    jump_audio_loaded=jump_audio_call=jump_audio_keyon_call=jump_audio_stop_call=0;
    jump_audio_calculated=jump_audio_faulted=0;jump_audio_bound_epoch=0;
    jump_audio_clear_calculation();memset(jump_audio_priorities,0,sizeof jump_audio_priorities);
    jump_audio_stop_mask=0;
    memset(jump_audio_registers,0,sizeof jump_audio_registers);memset(jump_audio_asset_sha,0,32);
    return jump_audio_banks[0].guest && jump_audio_banks[1].guest;
}
static int jump_audio_hash_is(const uint8_t *data,size_t size,const char *expected) {
    uint8_t digest[32];psx_sha256_ctx sha;psx_sha256_init(&sha);psx_sha256_update(&sha,data,size);psx_sha256_final(&sha,digest);
    static const char hex[]="0123456789abcdef";
    for(unsigned i=0;i<32;++i)if(expected[i*2]!=hex[digest[i]>>4] || expected[i*2+1]!=hex[digest[i]&15])return 0;
    return 1;
}
static int jump_audio_load(const uint8_t *dat,size_t size) {
    static const char *const hashes[2][2]={
        {"abf6451ffee33fa526e91be07e9c4f854c38ef0840ffa19c50a89c896536c857","425516420dc6ff1d973edae265717a6ca237454631cdb4b7c829c96f6f7057a8"},
        {"7c9fedd98a3d4740a2baddcc77323984e8b0a1ae139e24f36043cdfd0fa757ce","203c8e0e58ea4e55797445b7af76e7563528c21536ae8fd57e38566a89b38bdd"}};
    Mmx6AssetView headers[2],samples[2];Mmx6JumpAudioHeader layouts[2];uint8_t parsed[2][8192];
    if(jump_audio_loaded)return jump_audio_bind();
    for(unsigned i=0;i<2;++i) {
        unsigned group=i?3:1;
        if(!mmx6_coop_dat_asset(dat,size,85,11+i*2,&headers[i]) || headers[i].type!=6 ||
            !mmx6_coop_dat_asset(dat,size,85,12+i*2,&samples[i]) || samples[i].type!=(i?0x20303u:0x20101u) ||
            !jump_audio_hash_is(headers[i].data,headers[i].size,hashes[i][0]) ||
            !jump_audio_hash_is(samples[i].data,samples[i].size,hashes[i][1]) ||
            mmx6_jump_audio_prepare_header(headers[i].data,headers[i].size,samples[i].size,group,
                parsed[i],sizeof parsed[i],&layouts[i])!=MMX6_JUMP_AUDIO_OK)return 0;
    }
    Mmx6PrivateAudioBank views[2]={{parsed[0],&layouts[0]},{parsed[1],&layouts[1]}};
    uint32_t mask=0;
    if(mmx6_private_audio_validate(views,&mask)!=MMX6_JUMP_AUDIO_OK || mask!=JUMP_STOP_MASK)return 0;
    uint8_t *owned_headers[2]={NULL,NULL},*owned_samples[2]={NULL,NULL};
    for(unsigned i=0;i<2;++i) {
        owned_headers[i]=malloc(layouts[i].bytes);owned_samples[i]=malloc(layouts[i].sample_bytes);
        if(!jump_audio_banks[i].guest || !owned_headers[i] || !owned_samples[i]) {
            for(unsigned j=0;j<2;++j){free(owned_headers[j]);free(owned_samples[j]);}return 0;
        }
    }
    for(unsigned i=0;i<2;++i) {
        JumpAudioBank *b=&jump_audio_banks[i];
        b->parsed=owned_headers[i];b->samples=owned_samples[i];
        b->layout=layouts[i];memcpy(b->parsed,parsed[i],b->layout.bytes);
        memcpy(b->samples,samples[i].data,b->layout.sample_bytes);
        project(b->guest,b->parsed,b->layout.bytes);
    }
    psx_sha256_ctx sha;psx_sha256_init(&sha);
    for(unsigned i=0;i<2;++i) {
        psx_sha256_update(&sha,headers[i].data,headers[i].size);psx_sha256_update(&sha,samples[i].data,samples[i].size);
    }
    psx_sha256_final(&sha,jump_audio_asset_sha);jump_audio_loaded=1;
    return jump_audio_bind();
}
static int jump_audio_projected(void) {
    return ready && enrolled && !failed && (zero_projected || zero_world) &&
        !psx_mod_local_view_scope() && psx_mod_read_byte(PLAYER+4)<=3 &&
        psx_mod_read_byte(PLAYER+2)==1 && psx_mod_read_byte(PLAYER+0xE7)==5;
}
static Mmx6JumpAudioReason jump_audio_record(unsigned group,unsigned record,Mmx6PrivateAudioRecord *out) {
    Mmx6PrivateAudioBank views[2]={{jump_audio_banks[0].parsed,&jump_audio_banks[0].layout},
        {jump_audio_banks[1].parsed,&jump_audio_banks[1].layout}};
    return mmx6_private_audio_record(views,group,record,out);
}
static int jump_audio_body_stop(CPUState *cpu,unsigned record) {
    /* STOP has no actor argument. Only these original callers retain the
     * affected player in s0. Phase2 admits only its exact two entry stops. */
    if(cpu->gpr[16]!=PLAYER)return 0;
    unsigned phase=psx_mod_read_byte(PLAYER+4);uint32_t ra=cpu->gpr[31];
    if(phase==2)return (record==5 && ra==0x8003D8C4u) || (record==7 && ra==0x8003D8D0u);
    if(phase!=1)return 0;
    if(record==5)return ra==0x80038604u || ra==0x800386F4u || ra==0x800387ECu ||
        ra==0x80038900u || ra==0x8003B23Cu;
    return record==7 && (ra==0x8003F49Cu || ra==0x8003F614u);
}
static int jump_audio_free_native_slots(void) {
    const uint32_t tables[]={0x800E5588u,0x800E55C8u,0x800E5610u,0x800E56A8u,0x800E56F0u};
    for(unsigned id=14;id<=15;++id) {
        if(psx_mod_read_byte(0x800E5690u+id))return 0;
        for(unsigned t=0;t<sizeof tables/sizeof tables[0];++t)if(psx_mod_read_word(tables[t]+id*4u))return 0;
    }
    return 1;
}
static void jump_audio_install_tables(void) {
    for(unsigned i=0;i<2;++i) {
        const JumpAudioBank *b=&jump_audio_banks[i];unsigned id=b->layout.id;
        psx_mod_write_word(0x800E55C8u+id*4,b->guest+b->layout.vab);
        psx_mod_write_word(0x800E5588u+id*4,b->guest+b->layout.programs);
        psx_mod_write_word(0x800E5610u+id*4,b->guest+b->layout.tones);
        psx_mod_write_word(0x800E56A8u+id*4,b->layout.sample_bytes);
        psx_mod_write_word(0x800E56F0u+id*4,0);psx_mod_write_byte(0x800E5690u+id,1);
    }
}
static int jump_audio_keyon(CPUState *cpu,uint32_t address) {
    if(!jump_audio_call || jump_audio_keyon_call)return 0;
    const Mmx6PrivateAudioTone *tone=NULL;
    for(unsigned n=0;n<jump_audio_meta.voice_count;++n)
        if(jump_audio_meta.voices[n].slot==cpu->gpr[4])tone=&jump_audio_meta.voices[n];
    unsigned duplicate=0;
    for(unsigned n=0;n<jump_audio_calculated;++n)if(jump_audio_voices[n].slot==cpu->gpr[4])duplicate=1;
    uint32_t sp=cpu->gpr[29];
    if(!tone || duplicate || jump_audio_calculated>=4 || cpu->gpr[5]!=tone->id ||
        cpu->gpr[6]!=tone->program || cpu->gpr[7]!=tone->tone ||
        psx_mod_read_word(sp+16)!=tone->note || psx_mod_read_word(sp+20)!=tone->shift ||
        psx_mod_read_word(sp+24)>127 || psx_mod_read_word(sp+28)>127) {
        jump_audio_faulted=1;cpu->gpr[2]=UINT32_MAX;return 1;
    }
    jump_audio_slot=tone->slot;jump_audio_bank=tone->bank;jump_audio_tone=tone->tone;
    jump_audio_keyon_call=1;int charged=0;
    uint32_t result=psx_mod_call_guest_uncharged(cpu,address,cpu->gpr[31],cpu->gpr[4],cpu->gpr[5],
                                               cpu->gpr[6],cpu->gpr[7],0,&charged);
    if(result!=UINT32_MAX && !charged) {
        uint32_t regs=0x800E53A0u+jump_audio_slot*16u;
        for(unsigned r=0;r<6;++r)jump_audio_registers[r]=psx_mod_read_half(regs+r*2u);
        jump_audio_registers[6]=0;jump_audio_registers[7]=jump_audio_registers[3];
        jump_audio_mode=((psx_mod_read_word(0x800E4E38u)>>jump_audio_slot)&1u)|
                        (((psx_mod_read_word(0x800E4E34u)>>jump_audio_slot)&1u)<<1);
        uint32_t meta=0x800E4E40u+jump_audio_slot*0x38u;
        if(psx_mod_read_half(meta+0x1E) || psx_mod_read_half(meta+0x2A) ||
            (uint32_t)jump_audio_registers[3]*8u!=tone->sample_offset ||
            jump_audio_registers[4]!=tone->adsr_lo || jump_audio_registers[5]!=tone->adsr_hi)jump_audio_faulted=1;
        else {
            JumpAudioVoice *voice=&jump_audio_voices[jump_audio_calculated++];
            voice->slot=tone->slot;voice->bank=tone->bank;voice->mode=jump_audio_mode;
            memcpy(voice->regs,jump_audio_registers,sizeof voice->regs);
        }
    } else jump_audio_faulted=1;
    cpu->gpr[2]=result;jump_audio_keyon_call=0;return 1;
}
static int jump_audio_status(CPUState *cpu,uint32_t address) {
    (void)address;if(!jump_audio_call)return 0;
    if(!cpu->gpr[4] || (cpu->gpr[4]&~jump_audio_meta.voice_mask)) {
        jump_audio_faulted=1;cpu->gpr[2]=UINT32_MAX;return 1;
    }
    /* Selection only. active1 after END_STOP is never qualification evidence. */
    cpu->gpr[2]=(psx_mod_spu_private_voice_active()&cpu->gpr[4])?1u:0u;return 1;
}
static int jump_audio_sound(CPUState *cpu,uint32_t address) {
    unsigned group=cpu->gpr[4]&127u,record=cpu->gpr[5]&255u;
    if(jump_audio_call || !jump_audio_projected() || (group!=1 && group!=3) || cpu->gpr[6]!=PLAYER)return 0;
    /* The spatial actor proves body ownership without a jump-only caller
     * whitelist. Preserve the raw group: bit7 selects a native gain path. */
    /* Native channel-disabled semantics are unchanged and issue no KEYON. */
    if(psx_mod_read_byte(0x80090D50u+group)==255)return 0;
    Mmx6PrivateAudioRecord meta;JumpAudioBank *table=&jump_audio_banks[group==3];
    if(!jump_audio_loaded || !table->parsed) {
        jump_audio_fault("character records unavailable");cpu->gpr[2]=UINT32_MAX;return 1;
    }
    /* Original16CC8/16CE4 reject these before entering the native driver. */
    if(record>=table->layout.records){cpu->gpr[2]=0xFFFFFFFEu;return 1;}
    const uint8_t *entry=table->parsed+8u+record*4u;
    if(!(entry[0]|entry[1]|entry[2]|entry[3])){cpu->gpr[2]=0xFFFFFFFBu;return 1;}
    if(jump_audio_record(group,record,&meta)!=MMX6_JUMP_AUDIO_OK) {
        jump_audio_fault("character record invalid");cpu->gpr[2]=UINT32_MAX;return 1;
    }
    if(!jump_audio_bind() || !jump_audio_free_native_slots() || psx_mod_read_half(0x800E5652u)!=128 ||
        psx_mod_read_word(0x800E5520u) || psx_mod_read_word(0x800E5398u) ||
        psx_mod_read_word(0x800E459Cu) || psx_mod_read_byte(0x8006E356u)) {
        jump_audio_fault("bank/slot/native closure");cpu->gpr[2]=UINT32_MAX;return 1;
    }
    uint8_t driver[JUMP_DRIVER_BYTES],priority[24],records[128],outside[8];
    capture(JUMP_DRIVER,driver,sizeof driver);capture(0x800E25E0u,priority,sizeof priority);
    capture(0x80097738u,records,sizeof records);capture(0x800E459Cu,outside,4);capture(0x800E155Cu,outside+4,4);
    unsigned prior=state_track.count;
    STATE_BYTES(d,60,driver,sizeof driver);STATE_BYTES(p,61,priority,sizeof priority);
    STATE_BYTES(r,62,records,sizeof records);STATE_BYTES(o,63,outside,sizeof outside);
    if(!mmx6_state_can_call()) {
        state_track.count=prior;jump_audio_fault("host transaction capacity");cpu->gpr[2]=UINT32_MAX;return 1;
    }
    jump_audio_clear_calculation();jump_audio_meta=meta;jump_audio_call=1;jump_audio_faulted=0;
    jump_audio_install_tables();
    for(unsigned i=0;i<2;++i) {
        JumpAudioBank *b=&jump_audio_banks[i];unsigned g=i?3:1;
        psx_mod_write_word(0x80097738u+g*4u,b->guest+b->layout.vab);
        psx_mod_write_word(0x80097778u+g*4u,b->guest+8u);
    }
    project(0x800E25E0u,jump_audio_priorities,sizeof jump_audio_priorities);
    int charged=0;
    uint32_t result=psx_mod_call_guest_uncharged(cpu,address,cpu->gpr[31],cpu->gpr[4],cpu->gpr[5],
                                               cpu->gpr[6],cpu->gpr[7],0,&charged);
    uint8_t next_priority[24];capture(0x800E25E0u,next_priority,sizeof next_priority);
    /* Restore ALL native state before any private DSP call. The span is X6's
     * masks through final VAB sample-base table, not X4's queue extents. */
    project(JUMP_DRIVER,driver,sizeof driver);project(0x800E25E0u,priority,sizeof priority);
    project(0x80097738u,records,sizeof records);project(0x800E459Cu,outside,4);project(0x800E155Cu,outside+4,4);
    STATE_POP(o);STATE_POP(r);STATE_POP(p);STATE_POP(d);jump_audio_call=0;
    if(charged || jump_audio_faulted) {
        jump_audio_fault("native calculation/private DSP");result=UINT32_MAX;
    } else {
        /* Zero KEYONs is a valid native priority/status decision. Preserve its
         * opaque return value, including -1, rather than inventing a failure. */
        memcpy(jump_audio_priorities,next_priority,sizeof jump_audio_priorities);
        for(unsigned n=0;n<jump_audio_calculated;++n) {
            const JumpAudioVoice *voice=&jump_audio_voices[n];
            if(!psx_mod_spu_private_voice_play_owned(JUMP_AUDIO_OWNER,voice->slot,voice->bank,voice->regs,voice->mode)) {
                jump_audio_fault("private DSP ownership");result=UINT32_MAX;break;
            }
        }
    }
    jump_audio_clear_calculation();cpu->gpr[2]=result;return 1;
}
static int jump_audio_stop(CPUState *cpu,uint32_t address) {
    unsigned group=cpu->gpr[4]&255u,record=cpu->gpr[5]&255u;
    if(jump_audio_stop_call || !jump_audio_loaded)return 0;
    if(group==255) {
        jump_audio_stop_call=1;jump_audio_stop_mask=JUMP_STOP_MASK;
        uint32_t result=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
        if(!jump_audio_stop_owned(JUMP_STOP_MASK))jump_audio_fault("private global stop ownership");
        jump_audio_stop_call=0;jump_audio_stop_mask=0;cpu->gpr[2]=result;return 1;
    }
    if(group==1 && (record==5 || record==7)) {
        /* STOP supplies no spatial actor. These source-pinned callers prove
         * ownership via s0; death entry remains valid in phase2. */
        if(!jump_audio_projected() || !jump_audio_body_stop(cpu,record))return 0;
        Mmx6PrivateAudioRecord meta;
        if(jump_audio_record(group,record,&meta)!=MMX6_JUMP_AUDIO_OK ||
           !jump_audio_stop_owned(meta.voice_mask))jump_audio_fault("private body stop ownership");
        cpu->gpr[2]=0xFF000000u;return 1;
    }
    return 0;
}
