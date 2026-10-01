#ifndef MMX6_COOP_SPRITE_PACKET_H
#define MMX6_COOP_SPRITE_PACKET_H

#include <stdint.h>

/* Native 800232D4 reserves ten words for either an FT4 or a SPRT_16.
 * Unflipped tiles use SPRT_16; flipped tiles use FT4. Preserve FT4 geometry
 * exactly, and express SPRT_16 with tile-local UVs into a retained 16x16 bank.
 * This also avoids wrapping an endpoint of 256 into the next texture row. */
static inline int mmx6_coop_sprite_quad(uint32_t q[10], uint16_t *tile) {
    unsigned command=q[1]>>24;
    *tile=UINT16_MAX;
    if ((command&0xFC)==0x2C) return 1;
    if ((command&0xFC)!=0x7C) return 0;
    int x=(int16_t)q[2], y=(int16_t)(q[2]>>16);
    uint32_t clut=q[3]&0xFFFF0000u;
    *tile=(uint16_t)q[3];
    q[1]=(q[1]&0x03FFFFFFu)|0x2C000000u;
    for (unsigned i=0;i<4;++i) {
        q[2+i*2]=(uint16_t)(x+(i&1)*16)|((uint32_t)(uint16_t)(y+(i>>1)*16)<<16);
        q[3+i*2]=(i&1)*16|((i>>1)*16<<8);
    }
    q[3]|=clut;
    return 1;
}

#endif
