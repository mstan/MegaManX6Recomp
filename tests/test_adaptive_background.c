#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../src/mods/mmx6_adaptive_background.c"

static uint8_t ram[0x200000], extra[ARENA_BYTES];
static WsViewAnchor test_view;
static int support_banks;
static uint16_t test_vram[1024u*512u];
const uint16_t *gpu_get_vram(void) { return test_vram; }
int psx_mod_texture_banks_supported(void) { return support_banks; }
int psx_mod_read_disc_file(const char *p,void *b,uint32_t c,uint32_t *n) { (void)p;(void)b;(void)c;(void)n;return 0; }
int psx_mod_define_texture_bank(uint16_t id,uint32_t w,uint32_t h,const uint16_t *p) {
    if(id!=WEATHER_BANK) return 0;
    assert(w==1024 && h==512 && p==test_vram); return 1;
}
void psx_mod_set_texture_bank_resolver(PSXModTextureBankResolver r) { assert(r); }
void psx_mod_set_texture_bank_batching(int e) { assert(e); }
void gpu_ws_set_view_bounds_override(int e,int lo,int hi) { (void)e; assert(lo==0 && hi==7872); }
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
    mmx6_adaptive_background_begin(0);
    for (int extra=85;extra<=2048;extra+=157) {
        for (unsigned layer=1;layer<=2;++layer) {
            int divisor=layer==1?2:4;
            /* At the left edge original artwork stays at its original X. */
            WsViewAnchor fg=ws_view_anchor(extra,0,0,6336);
            WsViewAnchor bg=intro_parallax_view(fg,layer,0);
            assert(bg.shift==-extra && bg.left==0 && bg.right==extra*2);
            /* A stationary host camera at the right edge cannot make slower
             * layers crawl or jitter while the native camera keeps moving. */
            for (int camera=6336-extra;camera<=6336;++camera) {
                fg=ws_view_anchor(extra,camera,0,6336);
                bg=intro_parallax_view(fg,layer,camera);
                assert(camera/divisor-bg.left==(6336-extra*2)/divisor);
                assert(bg.left+bg.right==extra*2);
            }
        }
    }
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
    assert(intro_panorama_width(2)==640 && intro_panorama_width(1)==0);
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
            assert(x>=0 && x<1728);
            assert(psx_mod_read_word(p+12u)==mmx6_tile_uvclut(bucket==1?0x01123000u:0x02564000u));
            assert(psx_mod_read_word(p+16u)==(uint32_t)-693);
            assert(psx_mod_read_word(p+28u)==0x58364247u);
            if(x>=1024 && x<1280) { assert(bucket==2); saw_far=1; }
            p=psx_mod_read_word(p)&0xffffffu; assert(++count<=16*108);
        }
    }
    assert(saw_far && count==16*108);
    /* Scene textures coexist across the transition, including a restored
     * packet's signed view shift. Ordinary upper VRAM pages stay unbanked. */
    fixture(); support_banks=1; intro_banks=1;
    half(0x80097202u, 1536);
    mmx6_adaptive_background_end(0,0x800b91c0u);
    uint32_t bankp=psx_mod_read_word(0x80090e7cu)&0xffffffu;
    int saw_opening=0,saw_factory=0;
    while(bankp) {
        int x=(int16_t)psx_mod_read_word(bankp+8u);
        uint32_t meta=psx_mod_read_word(bankp+16u);
        assert((int16_t)meta==-693);
        assert((meta>>16)==(x+1536>=2048?FACTORY_BANK:INTRO_BANK));
        assert(psx_mod_read_word(bankp+28u)==GPU_WS_BG2D_BANK_PACKET_MAGIC);
        if(x+1536>=2048)saw_factory=1;else saw_opening=1;
        bankp=psx_mod_read_word(bankp)&0xffffffu;
    }
    assert(saw_opening && saw_factory);support_banks=0;
    /* Both native-center columns and the extension reflect the same panorama,
     * including its internal pixel orientation. */
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
        p=psx_mod_read_word(p)&0xffffffu; assert(++count<=16*108);
    }
    assert(count==16*108);
    /* A stale native packet at the reflection edge must not survive alongside
     * the new full-width list, or it reintroduces the moving black seam. */
    fixture(); half(0x80097202u,339);
    psx_mod_write_word(0x80090e7cu,0x000b91c0u);
    psx_mod_write_word(0x8008ec1cu,0x800b91c0u);
    psx_mod_write_word(0x800b91c0u,0x03000000u);
    mmx6_adaptive_background_end(0,0x800b91c0u);
    assert((psx_mod_read_word(0x80090e7cu)&0xffffffu)>=0x800000u);
    assert(psx_mod_read_word(0x800b91c0u)==0x03000000u);
    fixture(); test_view=(WsViewAnchor){0}; mmx6_adaptive_background_end(0,0x800b91c0u);
    for(unsigned i=0;i<sizeof extra;++i) assert(!extra[i]);
    /* Weather is a frame atlas: inactive neighboring art must never leak,
     * while an active frame repeats without gaps at extreme aspects. */
    for (unsigned banked=0;banked<2;++banked) for (unsigned active=0;active<2;++active) {
        fixture(); test_view=(WsViewAnchor){694,694,0,0,0};
        support_banks=(int)banked;
        ram[0xccedc]=6; ram[0x9724f]=1; ram[0x97250]=5;
        ram[0x9729e]=255; ram[0x9729a]=31;
        half(0x80097256u,active?0:320);
        memset(ram+0x100000+128,0,128);
        ram[0x100000+128]=3; ram[0x100000+129]=4;
        for(unsigned row=0;row<16;++row) for(unsigned col=0;col<16;++col) {
            half(0x80110600u+row*32+col*2,1);
            half(0x80110800u+row*32+col*2,col<4?1:0);
        }
        mmx6_adaptive_background_end(1,0x800b91c0u);
        unsigned count=0;
        for(unsigned p=LAYER_BYTES;p<2*LAYER_BYTES && extra[p+7];p+=32) {
            assert(psx_mod_read_word(0x80800000u+p+12)==mmx6_tile_uvclut(0x01123000u));
            assert(psx_mod_read_word(0x80800000u+p+16)==(banked?WEATHER_BANK<<16:0));
            ++count;
        }
        assert(count==(active?(21+44+44)*16:0));
    }
    /* Original-disc parser and the two different native upload layouts. */
    static uint8_t dat[2048u*2u+0x40000u];
    static uint16_t pixels[1024u*512u];
    uint32_t sector=1,length=2048u+0x40000u,type=0x10000u,n=0x40000u,one=1;
    memcpy(dat+94*8,&sector,4);memcpy(dat+94*8+4,&length,4);
    memcpy(dat+2048,&one,4);memcpy(dat+2052,&length,4);
    memcpy(dat+2056,&type,4);memcpy(dat+2060,&n,4);
    const uint8_t *asset=mmx6_intro_asset(dat,sizeof dat,type);
    assert(asset==dat+4096);
    assert(!mmx6_intro_asset(dat,sizeof dat-1,type));
    assert(!mmx6_intro_asset(dat,sizeof dat,0x16u));
    dat[4096+32768]=0xad;dat[4096+32769]=0xba;
    mmx6_unpack_intro_bank(pixels,asset,0);
    assert(pixels[256u*1024u+384u]==0xbaad);
    memset(pixels,0,sizeof pixels);mmx6_unpack_intro_bank(pixels,asset,1);
    assert(pixels[288u*1024u+320u]==0xbaad);
    assert(pixels[256u*1024u+384u]==0);
    puts("adaptive background: >64-ring columns, texture buckets, packet metadata, finite maps, native ring and 4:3 identity PASS");
}
