#include "mmx6_coop_assets.h"

static uint16_t u16(const uint8_t *p) {
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}
static uint32_t u32(const uint8_t *p) {
    return (uint32_t)u16(p) | ((uint32_t)u16(p + 2) << 16);
}

int mmx6_coop_dat_record(const uint8_t *dat, size_t size, unsigned record,
                        Mmx6AssetView *out) {
    size_t begin, bytes;
    if (!dat || !out || record >= 256 || size < 2048) return 0;
    begin = (size_t)u32(dat + record * 8) * 2048;
    bytes = u32(dat + record * 8 + 4);
    if (begin < 2048 || begin > size || !bytes || bytes > size - begin)
        return 0;
    out->data=dat+begin; out->size=bytes; out->type=0;
    return 1;
}

int mmx6_coop_dat_asset(const uint8_t *dat, size_t size, unsigned record,
                        unsigned asset, Mmx6AssetView *out) {
    Mmx6AssetView entry;
    size_t bytes, cursor, i;
    uint32_t count;
    if (!out || !mmx6_coop_dat_record(dat,size,record,&entry) || entry.size<2048) return 0;
    dat=entry.data; bytes=entry.size;
    count = u32(dat);
    if (count > 255 || asset >= count || u32(dat + 4) != bytes) return 0;
    cursor = 2048;
    for (i = 0; i < count; ++i) {
        size_t n = u32(dat + 12 + i * 8);
        if (cursor > bytes || n > bytes - cursor) return 0;
        if (i == asset) {
            out->data = dat + cursor;
            out->size = n;
            out->type = u32(dat + 8 + i * 8);
        }
        cursor += (n + 2047) & ~(size_t)2047;
    }
    return cursor == bytes;
}

int mmx6_coop_overlay(const uint8_t *bin, size_t size, unsigned index,
                      Mmx6AssetView *out) {
    size_t begin, bytes;
    /* ROCK_X6.BIN uses sector extents, not opaque IDs followed by payloads.
     * The first payload starts at sector 2; index 0/1 are X/Zero. */
    if (!bin || !out || size < 4096 || index >= 59) return 0;
    begin = (size_t)u32(bin + index * 8) * 2048;
    bytes = u32(bin + index * 8 + 4);
    if (begin < 4096 || begin > size || bytes < 4 || bytes > size - begin)
        return 0;
    out->data = bin + begin;
    out->size = bytes;
    out->type = u32(out->data);
    return 1;
}

int mmx6_coop_decode_sprite(const uint8_t *src, size_t size,
                            uint8_t *dst, size_t capacity, size_t *written) {
    size_t in = 0, out = 0;
    if (written) *written = 0;
    if (!src || !dst || !written) return 0;
    while (size - in >= 2) {
        unsigned flags = u16(src + in), bit;
        in += 2;
        for (bit = 0x8000; bit; bit >>= 1) {
            unsigned code, count, distance;
            if (size - in < 2) return 0;
            code = u16(src + in);
            in += 2;
            if (!(flags & bit)) {
                if (capacity - out < 2) return 0;
                dst[out++] = (uint8_t)code;
                dst[out++] = (uint8_t)(code >> 8);
                continue;
            }
            count = code >> 11;
            distance = code & 0x7ff;
            if (!count) {
                if (size - in < 2) return 0;
                count = u16(src + in);
                in += 2;
            }
            if (!count && !distance) {
                *written = out;
                return 1;
            }
            if ((size_t)count * 2 > capacity - out || (size_t)distance * 2 > out)
                return 0;
            while (count--) {
                const uint8_t lo = distance ? dst[out - distance * 2] : 0;
                const uint8_t hi = distance ? dst[out - distance * 2 + 1] : 0;
                dst[out++] = lo;
                dst[out++] = hi;
            }
        }
    }
    return 0;
}
