#include "mmx6_coop_assets.h"
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
    put32(archive,2); put32(archive+4,4);
    check(mmx6_coop_overlay(archive,sizeof archive,0,&view) && view.data==archive+4096,"overlay sector origin");
    put32(archive,0xffffffff);
    check(!mmx6_coop_overlay(archive,sizeof archive,0,&view),"overlay extent bound");
    puts("MMX6 co-op asset checks passed");
    return 0;
}
