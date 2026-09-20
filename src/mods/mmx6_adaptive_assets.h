#ifndef MMX6_ADAPTIVE_ASSETS_H
#define MMX6_ADAPTIVE_ASSETS_H
#include <stdint.h>
#include <stddef.h>

static inline uint32_t mmx6_asset_u32(const uint8_t *p) {
    return p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
/* ROCK_X6.DAT directory sectors and subasset padding are 2048 bytes.
 * Validate every range before dereferencing; never depend on reused CD RAM. */
static inline const uint8_t *mmx6_intro_asset(const uint8_t *data, uint32_t size,
                                             uint32_t type) {
    if (!data || size < 2048u) return NULL;
    uint32_t sector = mmx6_asset_u32(data + 94u * 8u);
    uint32_t length = mmx6_asset_u32(data + 94u * 8u + 4u);
    if (sector > size / 2048u || length < 2048u || length > size - sector * 2048u) return NULL;
    const uint8_t *record = data + sector * 2048u;
    uint32_t count = mmx6_asset_u32(record), offset = 2048u;
    if (count > 255u || mmx6_asset_u32(record + 4u) != length) return NULL;
    for (uint32_t i = 0; i < count; ++i) {
        uint32_t n = mmx6_asset_u32(record + 12u + i * 8u);
        if (offset > length || n > length - offset) return NULL;
        if (mmx6_asset_u32(record + 8u + i * 8u) == type)
            return n == 0x40000u ? record + offset : NULL;
        offset += n;
        if (offset > UINT32_MAX - 2047u) return NULL;
        offset = (offset + 2047u) & ~2047u;
    }
    return NULL;
}

/* The opening upload is eight page-major 64x256 strips. The factory upload
 * is a single row-major 512x256 rectangle. Both replace VRAM (320,256).
 * CLUTs are deliberately absent: retained indices use live guest palettes. */
static inline void mmx6_unpack_intro_bank(uint16_t *out, const uint8_t *src, int factory) {
    for (unsigned y = 0; y < 256u; ++y) for (unsigned x = 0; x < 512u; ++x) {
        unsigned p = factory ? y * 512u + x : (x / 64u) * 16384u + y * 64u + x % 64u;
        out[(y + 256u) * 1024u + x + 320u] = src[p * 2u] | (uint16_t)src[p * 2u + 1u] << 8;
    }
}
#endif
