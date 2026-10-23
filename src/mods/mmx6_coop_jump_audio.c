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
        unsigned id=source[at]&63u;
        if(id!=1 && id!=3)return MMX6_JUMP_AUDIO_RECORD;
    }
    const unsigned record_list[3]={2,4,7};
    for(unsigned n=0;n<(group==1?1u:3u);++n) {
        unsigned record=group==1?1u:record_list[n];
        if(record>=(offset-8u)/4u)return MMX6_JUMP_AUDIO_RECORD;
        const uint8_t *r=source+8u+record*4u;
        if(r[0]!=(uint8_t)(0x80u|group) || r[1] || r[2]!=(uint8_t)(record<<4) ||
            r[3]!=(group==1?22u:20u))return MMX6_JUMP_AUDIO_RECORD;
        if(!source[offset+32] || record>=source[offset+32])return MMX6_JUMP_AUDIO_RECORD;
        const uint8_t *t=source+offset+32u+2048u+rank[0]*512u+record*32u;
        if(!h16(t+22) || !source[offset+33] || !t[2] || t[4]>127 || t[5]>127 ||
            t[6]>127 || t[6]!=t[7])return MMX6_JUMP_AUDIO_RECORD;
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
