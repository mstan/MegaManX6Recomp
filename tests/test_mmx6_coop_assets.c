#include "mmx6_coop_assets.h"
#include "mmx6_coop_sprite_packet.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void check(int ok, const char *what) {
    if (!ok) { fprintf(stderr, "FAIL: %s\n", what); exit(1); }
}
static void put32(uint8_t *p, unsigned v) {
    for (unsigned i = 0; i < 4; ++i) p[i] = (uint8_t)(v >> (8 * i));
}
int main(void) {
    /* Native unflipped SPRT_16 and flipped FT4 must both survive projection.
     * Exercise signed XY, palette/blend flags and the last tile of a page. */
    uint32_t sprite[10]={0x03123456,0x7F808080,0x0064FFFD,0x7800F0F0};
    uint16_t tile;
    check(mmx6_coop_sprite_quad(sprite,&tile),"unflipped sprite accepted");
    check(tile==0xF0F0 && sprite[0]==0x03123456 && sprite[1]==0x2F808080,"sprite identity");
    check(sprite[2]==0x0064FFFD && sprite[4]==0x0064000D &&
          sprite[6]==0x0074FFFD && sprite[8]==0x0074000D,"full sixteen-pixel coverage");
    check(sprite[3]==0x78000000 && sprite[5]==0x10 &&
          sprite[7]==0x1000 && sprite[9]==0x1010,"tile-local UVs do not wrap");
    uint32_t flipped[10]={0x09123456,0x2D808080,0x00640010,0x7800000F,
                         0x00640020,0x00200000,0x00740010,0x0000100F,0x00740020,0x1000};
    uint32_t original[10]; memcpy(original,flipped,sizeof original);
    check(mmx6_coop_sprite_quad(flipped,&tile) && tile==UINT16_MAX &&
          !memcmp(original,flipped,sizeof original),"native flipped geometry preserved");
    sprite[1]=0x60000000;
    check(!mmx6_coop_sprite_quad(sprite,&tile),"unsupported primitive rejected");
    uint8_t out[32], archive[8192] = {0};
    size_t written;
    Mmx6AssetView view;
    /* Literal 1234, overlapping distance-one repeat, zero fill, terminator. */
    const uint8_t stream[] = {0x00,0x70, 0x34,0x12, 0x01,0x18,
                             0x00,0x10, 0x00,0x00, 0x00,0x00};
    check(mmx6_coop_decode_sprite(stream,sizeof stream,out,sizeof out,&written),"decode");
    check(written == 12,"decoded length");
    for (unsigned i=0;i<8;i+=2) check(out[i]==0x34 && out[i+1]==0x12,"overlapping copy");
    for (unsigned i=8;i<12;++i) check(!out[i],"zero fill");
    for (size_t n=0;n<sizeof stream;++n)
        check(!mmx6_coop_decode_sprite(stream,n,out,sizeof out,&written),"truncation rejected");
    check(!mmx6_coop_decode_sprite(stream,sizeof stream,out,10,&written),"output bound");
    const uint8_t bad[] = {0,0x80,1,8};
    check(!mmx6_coop_decode_sprite(bad,sizeof bad,out,sizeof out,&written),"backreference bound");
    const uint8_t extended[] = {0,0xc0,0,0,3,0,0,0,0,0};
    check(mmx6_coop_decode_sprite(extended,sizeof extended,out,sizeof out,&written) && written==6,"extended zero run");
    put32(archive+85*8,2); put32(archive+85*8+4,4096);
    put32(archive+4096,1); put32(archive+4100,4096);
    put32(archive+4104,3); put32(archive+4108,4);
    archive[6144]=0xAB;
    check(mmx6_coop_dat_asset(archive,sizeof archive,85,0,&view) &&
          view.data==archive+6144 && view.size==4 && view.type==3,"DAT ownership");
    check(!mmx6_coop_dat_asset(archive,6145,85,0,&view),"DAT truncation");
    check(!mmx6_coop_dat_asset(archive,sizeof archive,85,1,&view),"DAT asset index");
    put32(archive+166*8,3); put32(archive+166*8+4,512);
    check(mmx6_coop_dat_record(archive,sizeof archive,166,&view) &&
          view.data==archive+6144 && view.size==512,"raw portrait palette record");
    check(!mmx6_coop_dat_record(archive,6655,166,&view),"raw record truncation");
    check(!mmx6_coop_dat_record(archive,sizeof archive,256,&view),"raw record index bound");
    put32(archive,2); put32(archive+4,4);
    check(mmx6_coop_overlay(archive,sizeof archive,0,&view) && view.data==archive+4096,"overlay sector origin");
    put32(archive,0xffffffff);
    check(!mmx6_coop_overlay(archive,sizeof archive,0,&view),"overlay extent bound");
    puts("MMX6 co-op asset checks passed");
    return 0;
}
