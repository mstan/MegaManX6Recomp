#include "mmx6_coop_jump_audio.h"
#include <string.h>

static uint16_t h16(const uint8_t *p) {return (uint16_t)(p[0]|(uint16_t)p[1]<<8);}
static uint32_t h32(const uint8_t *p) {return h16(p)|(uint32_t)h16(p+2)<<16;}
static void p16(uint8_t *p,uint32_t v) {p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
static void p32(uint8_t *p,uint32_t v) {p16(p,v);p16(p+2,v>>16);}

Mmx6JumpAudioReason mmx6_jump_audio_prepare_header(const uint8_t *source,size_t size,
    size_t sample_bytes,unsigned group,uint8_t *parsed,size_t capacity,Mmx6JumpAudioHeader *out) {
    Mmx6JumpAudioHeader result;
    uint32_t offset,programs,tones,samples,populated=0,tone_total=0,total=0;
    uint16_t rank[128];
    if (!source || !parsed || !out || (group!=1 && group!=3) || size<8 ||
        size>MMX6_JUMP_AUDIO_HEADER_BYTES || capacity<size ||
        ((uintptr_t)source<=(uintptr_t)parsed ? (uintptr_t)parsed-(uintptr_t)source<size :
                                               (uintptr_t)source-(uintptr_t)parsed<size))
        return MMX6_JUMP_AUDIO_ARGUMENT;
    offset=h32(source)&0xFFFFFFu;
    if ((h32(source)>>24)!=group || offset<8 || (offset&3u) || offset>size ||
        size-offset<32 || memcmp(source+offset,"pBAV",4) || h32(source+offset+4)!=7 ||
        h32(source+4)!=sample_bytes || !sample_bytes || sample_bytes>=0x80000u || (sample_bytes&15u))
        return MMX6_JUMP_AUDIO_FORMAT;
    programs=h16(source+offset+18);tones=h16(source+offset+20);samples=h16(source+offset+22);
    if (!programs || programs>128 || !samples || samples>255 ||
        offset+32u+2048u+programs*512u+512u!=size ||
        h32(source+offset+12)!=size-offset+sample_bytes)
        return MMX6_JUMP_AUDIO_FORMAT;
    for (unsigned i=0;i<128;++i) {
        unsigned count=source[offset+32u+i*16u];
        if (count>16) return MMX6_JUMP_AUDIO_PROGRAMS;
        rank[i]=(uint16_t)populated;
        if(count) {++populated;tone_total+=count;}
    }
    if(populated!=programs || tone_total!=tones) return MMX6_JUMP_AUDIO_PROGRAMS;
    const uint8_t *lengths=source+size-512;
    if(h16(lengths))return MMX6_JUMP_AUDIO_SAMPLES;
    for(unsigned i=0;i<=samples;++i) {
        uint32_t bytes=(uint32_t)h16(lengths+i*2u)*8u;
        if(bytes>sample_bytes-total)return MMX6_JUMP_AUDIO_SAMPLES;
        total+=bytes;
        if((total&15u) || total/8u>65535u)return MMX6_JUMP_AUDIO_SAMPLES;
    }
    if(total!=sample_bytes)return MMX6_JUMP_AUDIO_SAMPLES;
    for(unsigned i=0;i<programs*16u;++i) {
        uint16_t sample=h16(source+offset+32u+2048u+i*32u+22u);
        /* Sample255 takes the native shared-noise/device-write path. */
        if(sample==255 || sample>samples)return MMX6_JUMP_AUDIO_SAMPLES;
    }
    for(unsigned at=8;at<offset;at+=4) {
        if(!h32(source+at))continue;
        const uint8_t *r=source+at;
        unsigned id=r[0]&63u,voice=r[3]&31u,count=1u+((r[3]>>5)&3u);
        if((id!=1 && id!=3) || (r[0]&0xC0u)!=0x80u || (r[3]&0x80u) ||
           voice>=24 || count>24u-voice)return MMX6_JUMP_AUDIO_RECORD;
        /* Cross-bank references are checked after both headers are ready. */
        if(id!=group)continue;
        for(unsigned n=0;n<count;++n) {
            unsigned program=(r[1]&127u)+((r[2]>>4)+n)/16u,tone=((r[2]>>4)+n)%16u;
            if(program>=128 || tone>=source[offset+32u+program*16u])return MMX6_JUMP_AUDIO_RECORD;
            const uint8_t *t=source+offset+32u+2048u+rank[program]*512u+tone*32u;
            if(!h16(t+22) || t[4]>127 || t[5]>127 || t[6]>127)return MMX6_JUMP_AUDIO_RECORD;
        }
    }
    memset(&result,0,sizeof result);
    result.group=group;result.id=group==1?MMX6_JUMP_AUDIO_SFX_ID:MMX6_JUMP_AUDIO_VOICE_ID;
    result.bank=group==1?MMX6_JUMP_AUDIO_SFX_BANK:MMX6_JUMP_AUDIO_VOICE_BANK;
    result.bytes=(uint32_t)size;result.sample_bytes=(uint32_t)sample_bytes;result.vab=offset;
    result.programs=offset+32u;result.tones=result.programs+2048u;
    result.records=(offset-8u)/4u;result.samples=samples;
    memcpy(parsed,source,size);
    /* Native80060408 gives every program row its populated-program index. */
    for(unsigned i=0;i<128;++i)p32(parsed+result.programs+i*16u+8u,rank[i]);
    /* Native8006054C accumulates table0..sample_count in 8-byte units, then
     * interleaves addresses through program-row+0C/+0E. */
    total=0;
    for(unsigned i=0;i<=samples;++i) {
        total+=(uint32_t)h16(lengths+i*2u)*8u;
        p16(parsed+result.programs+(i/2u)*16u+12u+(i&1u)*2u,total/8u);
    }
    for(unsigned at=8;at<offset;at+=4) if(h32(source+at))
        parsed[at]=(uint8_t)((source[at]&0xC0u)|
            ((source[at]&63u)==1?MMX6_JUMP_AUDIO_SFX_ID:MMX6_JUMP_AUDIO_VOICE_ID));
    *out=result;
    return MMX6_JUMP_AUDIO_OK;
}

static int private_bank_valid(const Mmx6PrivateAudioBank *b,unsigned index) {
    if(!b || !b->parsed || !b->layout)return 0;
    const Mmx6JumpAudioHeader *h=b->layout;
    if(h->group!=(index?3u:1u) || h->id!=(index?15u:14u) || (h->bank!=28u+index && h->bank!=30u+index) ||
       h->bytes>8192 || h->vab<8 || (h->vab&3u) || h->vab>h->bytes || h->bytes-h->vab<32 ||
       h->programs!=h->vab+32u || h->programs>h->bytes || h->bytes-h->programs<2048 ||
       h->tones!=h->programs+2048u || h->records!=(h->vab-8u)/4u ||
       !h->sample_bytes || h->sample_bytes>=0x80000u || (h->sample_bytes&15u) ||
       h32(b->parsed+4)!=h->sample_bytes)return 0;
    unsigned count=h16(b->parsed+h->vab+18u);
    return count && count<=128 && h->tones+count*512u+512u==h->bytes &&
        h->samples==h16(b->parsed+h->vab+22u) && h->samples && h->samples<=255;
}
Mmx6JumpAudioReason mmx6_private_audio_record(const Mmx6PrivateAudioBank banks[2],
    unsigned group,unsigned record,Mmx6PrivateAudioRecord *out) {
    if(!banks || !out || (group!=1 && group!=3) ||
       !private_bank_valid(&banks[0],0) || !private_bank_valid(&banks[1],1) ||
       banks[1].layout->bank!=banks[0].layout->bank+1u)return MMX6_JUMP_AUDIO_ARGUMENT;
    const Mmx6PrivateAudioBank *table=&banks[group==3];
    if(record>=table->layout->records)return MMX6_JUMP_AUDIO_RECORD;
    const uint8_t *r=table->parsed+8u+record*4u;unsigned id=r[0]&63u;
    if(!h32(r) || (id!=14 && id!=15) || (r[0]&0xC0u)!=0x80u || (r[3]&0x80u))return MMX6_JUMP_AUDIO_RECORD;
    const Mmx6PrivateAudioBank *b=&banks[id==15];const Mmx6JumpAudioHeader *h=b->layout;
    Mmx6PrivateAudioRecord result;memset(&result,0,sizeof result);
    result.group=group;result.record=record;result.first_voice=r[3]&31u;
    result.voice_count=1u+((r[3]>>5)&3u);result.priority=r[2]&15u;
    if(result.first_voice>=24 || result.voice_count>24u-result.first_voice)return MMX6_JUMP_AUDIO_RECORD;
    result.voice_mask=((1u<<result.voice_count)-1u)<<result.first_voice;
    for(unsigned n=0;n<result.voice_count;++n) {
        Mmx6PrivateAudioTone *v=&result.voices[n];unsigned t=(r[2]>>4)+n;
        v->slot=result.first_voice+n;v->bank=h->bank;v->id=h->id;
        v->program=(r[1]&127u)+t/16u;v->tone=t%16u;
        if(v->program>=128)return MMX6_JUMP_AUDIO_RECORD;
        const uint8_t *program=b->parsed+h->programs+v->program*16u;
        uint32_t rank=h32(program+8);
        if(!program[0] || program[0]>16 || v->tone>=program[0] || rank>=h16(b->parsed+h->vab+18u))
            return MMX6_JUMP_AUDIO_RECORD;
        const uint8_t *tone=b->parsed+h->tones+rank*512u+v->tone*32u;
        unsigned sample=h16(tone+22u);
        if(!sample || sample>h->samples)return MMX6_JUMP_AUDIO_RECORD;
        unsigned before=sample-1u;
        uint32_t start=(uint32_t)h16(b->parsed+h->programs+(before/2u)*16u+12u+(before&1u)*2u)*8u;
        uint32_t end=(uint32_t)h16(b->parsed+h->programs+(sample/2u)*16u+12u+(sample&1u)*2u)*8u;
        if(start>=end || end>h->sample_bytes || ((start|end)&15u) || tone[4]>127 || tone[5]>127 || tone[6]>127)
            return MMX6_JUMP_AUDIO_RECORD;
        v->sample_offset=start;v->sample_bytes=end-start;v->note=tone[6];v->shift=tone[5];
        v->adsr_lo=h16(tone+16);v->adsr_hi=h16(tone+18);
    }
    *out=result;return MMX6_JUMP_AUDIO_OK;
}
Mmx6JumpAudioReason mmx6_private_audio_validate(const Mmx6PrivateAudioBank banks[2],uint32_t *voice_mask) {
    if(!voice_mask || !banks || !private_bank_valid(&banks[0],0) || !private_bank_valid(&banks[1],1) ||
       banks[1].layout->bank!=banks[0].layout->bank+1u)
        return MMX6_JUMP_AUDIO_ARGUMENT;
    uint32_t result=0;
    for(unsigned i=0;i<2;++i)for(unsigned r=0;r<banks[i].layout->records;++r) {
        if(!h32(banks[i].parsed+8u+r*4u))continue;
        Mmx6PrivateAudioRecord record;
        Mmx6JumpAudioReason reason=mmx6_private_audio_record(banks,i?3:1,r,&record);
        if(reason!=MMX6_JUMP_AUDIO_OK)return reason;
        result|=record.voice_mask;
    }
    *voice_mask=result;return MMX6_JUMP_AUDIO_OK;
}
