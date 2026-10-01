#ifndef MMX6_COOP_ASSETS_H
#define MMX6_COOP_ASSETS_H

#include <stddef.h>
#include <stdint.h>

/* Views into a caller-owned, mounted-disc file. No copyrighted assets are
 * included with the mod. Addresses are the USA v1.1 native format. */
typedef struct {
    const uint8_t *data;
    size_t size;
    uint32_t type;
} Mmx6AssetView;

int mmx6_coop_dat_asset(const uint8_t *dat, size_t size, unsigned record,
                        unsigned asset, Mmx6AssetView *out);
int mmx6_coop_overlay(const uint8_t *bin, size_t size, unsigned index,
                      Mmx6AssetView *out);
/* Native word LZ decoder at 0x80018BE0. Returns success only at the explicit
 * terminator; malformed input never reads/writes outside its supplied spans. */
int mmx6_coop_decode_sprite(const uint8_t *src, size_t size,
                            uint8_t *dst, size_t capacity, size_t *written);

#endif
