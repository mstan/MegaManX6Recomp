#include "mmx6_coop_jump_audio.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#define CHECK(x) do {if(!(x)){fprintf(stderr,"line%d: %s\n",__LINE__,#x);exit(1);}}while(0)
static uint8_t source[4096],parsed[8192],before[8192];
static const unsigned pre=80,program=112,tone=2160,bytes=3184;
static void p16(uint8_t *p,unsigned v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
static void p32(uint8_t *p,uint32_t v){p16(p,v);p16(p+2,v>>16);}
static unsigned u16(const uint8_t *p){return p[0]|(unsigned)p[1]<<8;}
static unsigned u32(const uint8_t *p){return u16(p)|u16(p+2)<<16;}
static void fixture(void) {
    memset(source,0,sizeof source);p32(source,(3u<<24)|pre);p32(source+4,128);
    memcpy(source+pre,"pBAV",4);p32(source+pre+4,7);p32(source+pre+12,bytes-pre+128);
    p16(source+pre+18,1);p16(source+pre+20,8);p16(source+pre+22,8);
    source[program]=8;source[program+1]=127;
    for(unsigned i=0;i<8;++i) {
        uint8_t *t=source+tone+i*32u;t[2]=127;t[4]=60;t[6]=t[7]=60;p16(t+22,i+1);
        p16(source+bytes-512+(i+1)*2u,2);
    }
    const unsigned records[3]={2,4,7};
    for(unsigned n=0;n<3;++n){unsigned at=8+records[n]*4u;source[at]=0x83;source[at+2]=(uint8_t)(records[n]<<4);source[at+3]=20;}
    source[8+17*4]=0x81;source[8+17*4+3]=3; /* Native record17 effects-bank alias. */
}
static void rejected(size_t size,size_t body,unsigned group,size_t capacity) {
    Mmx6JumpAudioHeader out,saved;memset(&out,0xCD,sizeof out);saved=out;
    memset(parsed,0xA5,sizeof parsed);memcpy(before,parsed,sizeof before);
    CHECK(mmx6_jump_audio_prepare_header(source,size,body,group,parsed,capacity,&out)!=MMX6_JUMP_AUDIO_OK);
    CHECK(!memcmp(parsed,before,sizeof parsed));CHECK(!memcmp(&out,&saved,sizeof out));
}
static void sfx_fixture(void) {
    fixture();memset(source+8,0,pre-8);p32(source,(1u<<24)|pre);p32(source+4,160);
    p32(source+pre+12,bytes-pre+160);p16(source+pre+20,10);p16(source+pre+22,10);source[program]=10;
    for(unsigned i=0;i<10;++i) {
        uint8_t *t=source+tone+i*32u;t[2]=127;t[4]=60;t[6]=t[7]=60;p16(t+22,i+1);
        p16(source+bytes-512+(i+1)*2u,2);
    }
    for(unsigned r=1;r<=8;++r) {
        unsigned at=8+r*4;source[at]=0x81;source[at+2]=(uint8_t)((r>=2?r+1:r)<<4);
        source[at+3]=(uint8_t)(r>=7?23:22);
    }
}
int main(int argc,char **argv) {
    if(argc==4) {
        uint8_t input[8193],output[8192];Mmx6JumpAudioHeader h;
        FILE *file=fopen(argv[1],"rb");CHECK(file);size_t size=fread(input,1,sizeof input,file);CHECK(!ferror(file));fclose(file);
        unsigned body=(unsigned)strtoul(argv[2],NULL,10),group=(unsigned)strtoul(argv[3],NULL,10);
        CHECK(mmx6_jump_audio_prepare_header(input,size,body,group,output,sizeof output,&h)==MMX6_JUMP_AUDIO_OK);
        printf("original group%u header%u body%u samples%u parsed\n",h.group,h.bytes,h.sample_bytes,h.samples);return 0;
    }
    fixture();Mmx6JumpAudioHeader h;uint8_t original[4096];memcpy(original,source,sizeof source);
    CHECK(mmx6_jump_audio_prepare_header(source,bytes,128,3,parsed,sizeof parsed,&h)==MMX6_JUMP_AUDIO_OK);
    CHECK(!memcmp(source,original,sizeof source));CHECK(h.vab==pre && h.programs==program && h.tones==tone);
    CHECK(h.id==15 && h.bank==31 && h.records==18 && h.samples==8 && h.sample_bytes==128);
    CHECK(parsed[8+2*4]==0x8F && parsed[8+17*4]==0x8E);CHECK(parsed[8+17*4+3]==3);
    CHECK(u32(parsed+program+8)==0 && u32(parsed+program+16+8)==1);
    CHECK(u16(parsed+program+12)==0 && u16(parsed+program+14)==2);
    CHECK(u16(parsed+program+3*16+14)==14 && u16(parsed+program+4*16+12)==16);
    rejected(7,128,3,sizeof parsed);rejected(SIZE_MAX,128,3,sizeof parsed);rejected(bytes,128,0,sizeof parsed);
    rejected(bytes,0,3,sizeof parsed);rejected(bytes,0x80000,3,sizeof parsed);rejected(bytes,128,3,bytes-1);
    fixture();p32(source,0x03FFFFFF);rejected(bytes,128,3,sizeof parsed);
    fixture();source[pre]='x';rejected(bytes,128,3,sizeof parsed);
    fixture();p32(source+pre+4,8);rejected(bytes,128,3,sizeof parsed);
    fixture();p32(source+pre+12,0);rejected(bytes,128,3,sizeof parsed);
    fixture();p16(source+pre+18,129);rejected(bytes,128,3,sizeof parsed);
    fixture();p16(source+pre+20,7);rejected(bytes,128,3,sizeof parsed);
    fixture();source[program]=17;rejected(bytes,128,3,sizeof parsed);
    fixture();p16(source+bytes-512,1);rejected(bytes,128,3,sizeof parsed);
    fixture();p16(source+bytes-510,3);rejected(bytes,128,3,sizeof parsed);
    fixture();p16(source+tone+22,255);rejected(bytes,128,3,sizeof parsed);
    fixture();p16(source+tone+7*32+22,0);rejected(bytes,128,3,sizeof parsed);
    fixture();source[tone+7*32+7]=61;rejected(bytes,128,3,sizeof parsed);
    fixture();source[8+4*4+2]|=1;rejected(bytes,128,3,sizeof parsed);
    fixture();source[8+4*4+3]=21;rejected(bytes,128,3,sizeof parsed);
    fixture();source[8+4*4]=0xC3;rejected(bytes,128,3,sizeof parsed);
    fixture();source[8+17*4]=0x82;rejected(bytes,128,3,sizeof parsed);
    fixture();CHECK(mmx6_jump_audio_prepare_header(source,bytes,128,3,source,sizeof source,&h)==MMX6_JUMP_AUDIO_ARGUMENT);
    CHECK(mmx6_jump_audio_prepare_header(source,bytes,128,3,source+16,sizeof source-16,&h)==MMX6_JUMP_AUDIO_ARGUMENT);
    sfx_fixture();CHECK(mmx6_jump_audio_prepare_header(source,bytes,160,1,parsed,sizeof parsed,&h)==MMX6_JUMP_AUDIO_OK);
    CHECK(h.id==14 && h.bank==30 && parsed[8+5*4+2]==0x60 && parsed[8+7*4+3]==23);
    for(unsigned r=1;r<=8;++r)for(unsigned field=0;field<4;++field) {
        sfx_fixture();source[8+r*4+field]^=1;rejected(bytes,160,1,sizeof parsed);
    }
    puts("X6 private jump parsed-header bounds and alias tests passed");return 0;
}
