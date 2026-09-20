#include "mmx6_adaptive_background.h"
#include "mod_plugins.h"
#include "gpu.h"
#include <stdio.h>

/* Separate 1MiB per layer per guest display buffer. At 32 bytes per packet,
 * each slice holds 2048 columns x16 rows: the full 32768px signed-coordinate
 * viewport. Capacity is a checked storage invariant, never an aspect cap.
 * Metadata lives beside packets so a saved pending OT is self-contained. */
#define LAYER_BYTES (1024u * 1024u)
#define ARENA_BYTES (6u * LAYER_BYTES)
static uint32_t arena;

/* The intro map is also an atlas for later camera scenes. Its opening
 * panorama is 640px wide (+one streaming guard tile), and the nearer wreckage
 * ends at 1088px, where tiles requiring a different scene's palettes begin.
 * Repeat only these two backdrops while the game's opening parallax setup is
 * active. Terrain, native packets, other stages and later scenes stay direct.
 * Matching the live scroll setup makes this survive snapshots/transitions
 * without a host-side "current scene" cache. */
static int intro_panorama_width(unsigned layer) {
    if (layer == 0 || psx_mod_read_byte(0x800ccedcu) != 0 ||
        psx_mod_read_byte(0x800cceddu) != 0) return 0;
    const uint32_t far = 0x800972a0u;
    if (psx_mod_read_byte(far + 4u) != 3 ||
        psx_mod_read_half(far + 0x40u) != 0 ||
        psx_mod_read_half(far + 0x42u) != 640 ||
        (int8_t)psx_mod_read_byte(far + 0x52u) >= 0) return 0;
    return layer == 2 ? 640 : 1088;
}

int mmx6_adaptive_background_activate(void) {
    arena = psx_mod_alloc_gpu_dma_memory(ARENA_BYTES, 32u);
    if (!arena) {
        fprintf(stderr, "MMX6 Custom Renderer: background arena allocation failed\n");
        return 0;
    }
    gpu_ws_bg2d_set_host_arena(arena, ARENA_BYTES);
    return 1;
}

void mmx6_adaptive_background_end(unsigned layer, uint32_t native_packet) {
    WsViewAnchor view;
    if (!arena || layer >= 3 || !gpu_ws_bg2d_get_view(layer, &view)) return;
    if (view.left <= 0 && view.right <= 0) return;
    if (psx_mod_read_half(0x80090d6au)) return; /* Native 512px title mode. */
    uint32_t buffer = psx_mod_read_word(0x1f800000u);
    if (buffer > 1) return;
    uint32_t b = 0x800971f8u + layer * 0x54u;
    if (!psx_mod_read_byte(b + 3u)) return;
    int sx = (int16_t)psx_mod_read_half(b + 10u);
    int sy = (int16_t)psx_mod_read_half(b + 14u);
    int parent = (int8_t)psx_mod_read_byte(b + 0x52u);
    if (parent >= 0 && parent < 3) {
        uint32_t p = 0x800971f8u + (unsigned)parent * 0x54u;
        sx += (int16_t)psx_mod_read_half(p + 10u);
        sy += (int16_t)psx_mod_read_half(p + 14u);
    }
    Mmx6TileMap map = {
        psx_mod_read_word(0x1f800004u), psx_mod_read_word(0x1f800008u),
        psx_mod_read_word(0x1f80000cu), psx_mod_read_byte(0x800cd338u),
        psx_mod_read_half(0x8008ec10u), layer,
        psx_mod_read_byte(b + 0x4du), psx_mod_read_byte(b + 0x4eu)
    };
    if (!mmx6_ram_range(map.map, 1) || !mmx6_ram_range(map.metatiles, 512) ||
        !mmx6_ram_range(map.descriptors, 4)) return;
    int left = (view.left + 15) / 16, right = (view.right + 15) / 16;
    if (left + right > 2048 || left > 2048 || right > 2027) {
        fprintf(stderr, "MMX6 Custom Renderer: viewport exceeds signed packet coordinates\n");
        return;
    }
    uint32_t cursor = arena + (buffer * 3u + layer) * LAYER_BYTES;
    uint32_t limit = cursor + LAYER_BYTES;
    /* Native packets are initialized as raw SPRT_16; retain the template's
     * command/color bits, replacing only this tile's semi-transparency bit. */
    uint32_t color = psx_mod_read_word(native_packet + 4u);
    if ((color >> 24 & 0xfdu) != 0x7du) color = 0x7d808080u;
    int start_col = sx / 16, start_row = sy / 16;
    int screen_x = -(sx & 15), screen_y = -(sy & 15);
    int panorama_width = parent < 0 ? intro_panorama_width(layer) : 0;
    for (int row = 0; row < 16; ++row) {
        for (int col = -left; col < 21 + right; ++col) {
            if (col >= 0 && col < 21) continue; /* Native tiles already submitted. */
            int tile_x = (start_col + col) * 16, flipped = 0;
            if (panorama_width)
                tile_x = mmx6_mirror_tile_x(tile_x, panorama_width, &flipped);
            uint16_t tile = mmx6_map_tile(&map, tile_x,
                (start_row + row) * 16, psx_mod_read_byte, psx_mod_read_half);
            if (!tile) continue;
            uint32_t desc_addr = map.descriptors + (tile & 0x3fffu) * 4u;
            if (!mmx6_ram_range(desc_addr, 4)) continue;
            uint32_t desc = psx_mod_read_word(desc_addr);
            unsigned bucket = (desc >> 24) & 0x3fu;
            if ((desc >> 24) == 255u || bucket >= 17u) continue;
            if (cursor > limit - 32u) return; /* No guest-buffer overrun. */
            unsigned group = layer + ((tile & 0x8000u) ? 3u : 0u);
            uint32_t tail_slot = 0x8008ec18u + buffer * 408u + group * 68u + bucket * 4u;
            uint32_t tail = psx_mod_read_word(tail_slot);
            if (!mmx6_ram_range(tail, 4) && !(tail >= arena && tail < arena + ARENA_BYTES))
                continue;
            int x = screen_x + col * 16, y = screen_y + row * 16;
            psx_mod_write_word(cursor, 0x03000000u);
            psx_mod_write_word(cursor + 4u, (color & ~0x02000000u) |
                ((tile & 0x4000u) ? 0x02000000u : 0u));
            psx_mod_write_word(cursor + 8u, (uint16_t)x | ((uint32_t)(uint16_t)y << 16));
            psx_mod_write_word(cursor + 12u, mmx6_tile_uvclut(desc));
            psx_mod_write_word(cursor + 16u, (uint32_t)view.shift);
            psx_mod_write_word(cursor + 20u, (uint32_t)view.pad_left);
            psx_mod_write_word(cursor + 24u, (uint32_t)view.pad_right);
            psx_mod_write_word(cursor + 28u, GPU_WS_BG2D_PACKET_MAGIC |
                (flipped ? GPU_WS_BG2D_MIRROR_X : 0u));
            psx_mod_write_word(tail, (psx_mod_read_word(tail) & 0xff000000u) | (cursor & 0xffffffu));
            psx_mod_write_word(tail_slot, cursor);
            cursor += 32u;
        }
    }
}
