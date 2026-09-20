#ifndef MMX6_ADAPTIVE_BACKGROUND_H
#define MMX6_ADAPTIVE_BACKGROUND_H
#include <stdint.h>
#include "ws_view_anchor.h"

/* Retail SLUS-01395: a 256px screen is a 16x16 array of tile IDs.
 * Resolve world coordinates directly, never through the wrapping 64-column
 * guest ring. Layer stride also bounds the authored map's row count. */
typedef struct {
    uint32_t map, metatiles, descriptors;
    unsigned map_width, layer_stride, layer, left_screen, right_screen;
} Mmx6TileMap;
typedef uint8_t (*Mmx6Read8)(uint32_t);
typedef uint16_t (*Mmx6Read16)(uint32_t);
typedef uint32_t (*Mmx6Read32)(uint32_t);

static inline int mmx6_ram_range(uint32_t p, uint32_t n) {
    p &= 0x1fffffffu;
    return p >= 0x10000u && p < 0x200000u && n <= 0x200000u - p;
}
static inline uint16_t mmx6_map_tile(const Mmx6TileMap *m, int x, int y,
                                     Mmx6Read8 read8, Mmx6Read16 read16) {
    if (x < 0 || y < 0 || !m->map_width || !m->layer_stride) return 0;
    unsigned col = (unsigned)x / 256u, row = (unsigned)y / 256u;
    if (col < m->left_screen || col > m->right_screen || col >= m->map_width ||
        row >= m->layer_stride / m->map_width) return 0;
    uint32_t cell = m->map + m->layer * m->layer_stride + row * m->map_width + col;
    if (!mmx6_ram_range(cell, 1)) return 0;
    uint32_t tile = m->metatiles + read8(cell) * 512u +
        (((unsigned)y / 16u) & 15u) * 32u + (((unsigned)x / 16u) & 15u) * 2u;
    return mmx6_ram_range(tile, 2) ? read16(tile) : 0;
}
static inline uint32_t mmx6_tile_uvclut(uint32_t descriptor) {
    unsigned page = descriptor >> 24;
    unsigned clut = 0x7980u + ((descriptor & 0xf000u) >> 6) + ((page & 0x40u) << 4);
    clut |= (descriptor >> 8) & 15u;
    return (clut << 16) | ((descriptor >> 12) & 0xf0u) |
        (((descriptor >> 16) & 0xf0u) << 8);
}

/* Reflect whole tiles, with a separate flag for their internal pixel order.
 * Euclidean modulo also handles a reveal to the left of the panorama. */
static inline int mmx6_mirror_tile_x(int x, int width, int *flipped) {
    int phase = x % (width * 2);
    if (phase < 0) phase += width * 2;
    *flipped = phase >= width;
    return *flipped ? width * 2 - 16 - phase : phase;
}

int mmx6_adaptive_background_activate(void);
void mmx6_adaptive_background_end(unsigned layer, uint32_t native_packet);
#endif
