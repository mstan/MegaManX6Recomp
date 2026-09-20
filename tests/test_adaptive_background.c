#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../src/mods/mmx6_adaptive_background.c"

static uint8_t ram[0x200000], extra[ARENA_BYTES];
static WsViewAnchor test_view;
static uint8_t *memory(uint32_t p, unsigned n) {
    p &= 0x1fffffffu;
    if (p >= 0x800000u && p - 0x800000u <= sizeof extra - n) return extra + p - 0x800000u;
    assert(p <= sizeof ram - n);
    return ram + p;
}
uint8_t psx_mod_read_byte(uint32_t p) { return *memory(p, 1); }
uint16_t psx_mod_read_half(uint32_t p) {
    if ((p & 0x1fffffffu) == 0x1f800000u) return 0;
    uint16_t v; memcpy(&v,memory(p,2),2); return v;
}
uint32_t psx_mod_read_word(uint32_t p) {
    if (p == 0x1f800000u) return 0;
    if (p == 0x1f800004u) return 0x80100000u;
    if (p == 0x1f800008u) return 0x80110000u;
    if (p == 0x1f80000cu) return 0x80140000u;
    uint32_t v; memcpy(&v,memory(p,4),4); return v;
}
void psx_mod_write_word(uint32_t p, uint32_t v) { memcpy(memory(p,4),&v,4); }
uint32_t psx_mod_alloc_gpu_dma_memory(uint32_t n,uint32_t a) {
    assert(n==sizeof extra && a==32); return 0x80800000u;
}
void gpu_ws_bg2d_set_host_arena(uint32_t p,uint32_t n) { assert(p==0x80800000u && n==sizeof extra); }
int gpu_ws_bg2d_get_view(unsigned layer,WsViewAnchor *v) { assert(layer<3); *v=test_view; return 320; }
static void half(uint32_t p,uint16_t v) { memcpy(memory(p,2),&v,2); }
static void fixture(void) {
    memset(ram,0,sizeof ram); memset(extra,0,sizeof extra);
    ram[0x971fb]=1; ram[0x9724a]=255; ram[0x97246]=31; /* draw, parent, right screen */
    ram[0xcd338]=32; half(0x8008ec10u,32*4);
    memset(ram+0x100000,1,32*4*3);
    for(unsigned i=0;i<256;++i) half(0x80110200u+i*2,1);
    /* At x=1024 use different art from x=0: aliases in the old 64-col ring. */
    ram[0x100004]=2;
    for(unsigned i=0;i<256;++i) half(0x80110400u+i*2,2);
    psx_mod_write_word(0x80140004u,0x01123000u);
    psx_mod_write_word(0x80140008u,0x02564000u);
    psx_mod_write_word(0x800b91c4u,0x7d808080u);
    for(unsigned i=0;i<102;++i) {
        uint32_t head=0x80090e78u+i*4u;
        psx_mod_write_word(0x8008ec18u+i*4u,head);
    }
}
int main(void) {
    assert(mmx6_adaptive_background_activate()); fixture();
    Mmx6TileMap m={0x80100000u,0x80110000u,0x80140000u,32,128,0,0,31};
    assert(mmx6_map_tile(&m,0,0,psx_mod_read_byte,psx_mod_read_half)==1);
    assert(mmx6_map_tile(&m,1024,0,psx_mod_read_byte,psx_mod_read_half)==2);
    assert(!mmx6_map_tile(&m,-1,0,psx_mod_read_byte,psx_mod_read_half));
    assert(!mmx6_map_tile(&m,8192,0,psx_mod_read_byte,psx_mod_read_half));
    assert(!mmx6_map_tile(&m,0,1024,psx_mod_read_byte,psx_mod_read_half));
    int flip;
    assert(mmx6_mirror_tile_x(624,640,&flip)==624 && !flip);
    assert(mmx6_mirror_tile_x(640,640,&flip)==624 && flip);
    assert(mmx6_mirror_tile_x(1264,640,&flip)==0 && flip);
    assert(mmx6_mirror_tile_x(1280,640,&flip)==0 && !flip);
    assert(mmx6_mirror_tile_x(-16,640,&flip)==0 && flip);
    assert(mmx6_mirror_tile_x(-656,640,&flip)==624 && !flip);
    assert(!intro_panorama_width(2));
    ram[0x972a4]=3; ram[0x972f2]=255;
    half(0x800972e2u,640);
    assert(intro_panorama_width(2)==640 && intro_panorama_width(1)==1088);
    assert(!intro_panorama_width(0));
    ram[0xccedc]=1; assert(!intro_panorama_width(2)); ram[0xccedc]=0;
    half(0x800972e0u,1280); assert(!intro_panorama_width(2));
    half(0x800972e0u,0);
    test_view=(WsViewAnchor){0,1386,-693,0,0}; /* 64:9 anchored at left edge */
    uint8_t original_ring[3*4096]; memcpy(original_ring,ram+0xa21b8,sizeof original_ring);
    mmx6_adaptive_background_end(0,0x800b91c0u);
    assert(!memcmp(original_ring,ram+0xa21b8,sizeof original_ring));
    assert(psx_mod_read_word(0x800b91c4u)==0x7d808080u);
    unsigned count=0; int saw_far=0;
    for(unsigned bucket=1;bucket<=2;++bucket) {
        uint32_t p=psx_mod_read_word(0x80090e78u+bucket*4u)&0xffffffu;
        while(p) {
            assert(p>=0x800000u && p<0x900000u && !(p&31));
            uint32_t xy=psx_mod_read_word(p+8u);
            int x=(int16_t)xy;
            assert(x>=336 && x<1728);
            assert(psx_mod_read_word(p+12u)==mmx6_tile_uvclut(bucket==1?0x01123000u:0x02564000u));
            assert(psx_mod_read_word(p+16u)==(uint32_t)-693);
            assert(psx_mod_read_word(p+28u)==0x58364247u);
            if(x>=1024 && x<1280) { assert(bucket==2); saw_far=1; }
            p=psx_mod_read_word(p)&0xffffffu; assert(++count<=16*87);
        }
    }
    assert(saw_far && count==16*87);
    /* This backdrop's extra packets must reflect active-scene art, including
     * pixel orientation, instead of reading another scene beyond x=1088. */
    fixture();
    ram[0x972a3]=1; ram[0x972a4]=3; ram[0x972f2]=255; ram[0x972ee]=31;
    half(0x800972e2u,640);
    mmx6_adaptive_background_end(2,0x800b91c0u);
    uint32_t p=psx_mod_read_word(0x80090e78u+2*68+4)&0xffffffu;
    count=0;
    while(p) {
        int x=(int16_t)psx_mod_read_word(p+8u);
        int source=mmx6_mirror_tile_x(x,640,&flip);
        assert(source>=0 && source<640);
        assert(psx_mod_read_word(p+12u)==mmx6_tile_uvclut(0x01123000u));
        assert(psx_mod_read_word(p+28u)==(GPU_WS_BG2D_PACKET_MAGIC |
            (flip?GPU_WS_BG2D_MIRROR_X:0u)));
        p=psx_mod_read_word(p)&0xffffffu; assert(++count<=16*87);
    }
    assert(count==16*87);
    fixture(); test_view=(WsViewAnchor){0}; mmx6_adaptive_background_end(0,0x800b91c0u);
    for(unsigned i=0;i<sizeof extra;++i) assert(!extra[i]);
    puts("adaptive background: >64-ring columns, texture buckets, packet metadata, finite maps, native ring and 4:3 identity PASS");
}
