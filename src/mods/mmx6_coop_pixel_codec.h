#ifndef MMX6_COOP_PIXEL_CODEC_H
#define MMX6_COOP_PIXEL_CODEC_H
#include <stdint.h>
#include <stddef.h>

/* Canonical little-endian retained pixels: byte0 is raw(0) or runs(1).
 * Runs are nonzero LE16 length, LE16 color; zero is never a hidden 65536. */
static uint32_t mmx6_pixels_size(const uint16_t *pixels,uint32_t count) {
    if (!pixels || !count || count>65536) return 0;
    uint32_t runs=0;
    for (uint32_t i=0;i<count;) {
        uint32_t n=1;
        while (n<65535 && n<count-i && pixels[i+n]==pixels[i]) ++n;
        i+=n;++runs;
    }
    return 1+(runs*4<count*2?runs*4:count*2);
}
static int mmx6_pixels_encode(uint8_t *out,uint32_t len,const uint16_t *pixels,uint32_t count) {
    uint32_t expected=mmx6_pixels_size(pixels,count),at=1;
    if (!out || !expected || len!=expected) return 0;
    out[0]=(uint8_t)(len!=1+count*2);
    for (uint32_t i=0;i<count;) {
        uint32_t n=1;
        if (out[0]) {
            while (n<65535 && n<count-i && pixels[i+n]==pixels[i]) ++n;
            out[at++]=(uint8_t)n;out[at++]=(uint8_t)(n>>8);
        }
        out[at++]=(uint8_t)pixels[i];out[at++]=(uint8_t)(pixels[i]>>8);i+=n;
    }
    return at==len;
}
static int mmx6_pixels_decode(const uint8_t *in,uint32_t len,uint32_t count,uint16_t *out) {
    if (!in || !len || !count || count>65536 || in[0]>1 || len>1+count*2) return 0;
    uint32_t at=1,used=0;
    if (!in[0] && len!=1+count*2) return 0;
    while (at<len) {
        uint32_t n=1;
        if (in[0]) {
            if (len-at<4) return 0;
            n=(uint32_t)in[at]|((uint32_t)in[at+1]<<8);at+=2;
        } else if (len-at<2) return 0;
        uint16_t color=(uint16_t)(in[at]|((uint16_t)in[at+1]<<8));at+=2;
        if (!n || n>count-used) return 0;
        if (out) for (uint32_t i=0;i<n;++i) out[used+i]=color;
        used+=n;
    }
    return at==len && used==count;
}
#endif
