/* Named development prerequisite only: original CP2 entry and native landing
 * precede one disclosed position/previous-position bypass. All camera,
 * scanner, actor, portal admission, loading and destination results stay native. */
#include "mmx6_coop_before_portal_data.h"
static int recycle_portal_source(void);
static int checkpoint_portal_source(void) {
    for(unsigned i=0;i<sizeof portal_setup_code/sizeof portal_setup_code[0];++i)
        if(checkpoint_hash(portal_setup_code[i].first,portal_setup_code[i].end)!=portal_setup_code[i].hash)return 0;
    return recycle_portal_source() && psx_mod_read_word(0x80078910u)==0x10080000u &&
        psx_mod_read_word(0x800F338Cu)==0x80054820u &&
        (psx_mod_read_word(0x800F2B7Cu)&0xFFFFFFFEu)==0x043B0400u &&
        psx_mod_read_word(0x800F2B80u)==0x06400550u;
}
static int checkpoint_portal_assets(uint32_t *meta,uint32_t *desc) {
    *meta=psx_mod_read_word(0x1F800008u);*desc=psx_mod_read_word(0x1F80000Cu);
    return psx_mod_read_word(0x1F800004u)==PORTAL_SETUP_LAYOUT &&
        psx_mod_read_half(0x800CD338u)==0x0816u && psx_mod_read_half(0x8008EC10u)==176 &&
        *meta>=0x80010000u && *meta<=0x80200000u-PORTAL_SETUP_META_BYTES &&
        *desc>=0x80010000u && *desc<=0x80200000u-PORTAL_SETUP_DESC_BYTES &&
        checkpoint_hash(PORTAL_SETUP_LAYOUT,PORTAL_SETUP_LAYOUT+PORTAL_SETUP_LAYOUT_BYTES)==PORTAL_SETUP_LAYOUT_FNV &&
        checkpoint_hash(*meta,*meta+PORTAL_SETUP_META_BYTES)==PORTAL_SETUP_METATILES_FNV &&
        checkpoint_hash(*desc,*desc+PORTAL_SETUP_DESC_BYTES)==PORTAL_SETUP_DESCRIPTORS_FNV;
}
static int checkpoint_portal_tile(uint32_t meta,uint32_t desc,unsigned x,unsigned y) {
    unsigned cell=psx_mod_read_byte(PORTAL_SETUP_LAYOUT+(y>>8)*PORTAL_SETUP_WIDTH+(x>>8));
    if(!cell)return 0;
    unsigned at=cell*512u+((y>>4)&15u)*32u+((x>>4)&15u)*2u;
    if(at+2u>PORTAL_SETUP_META_BYTES)return -1;
    unsigned tile=psx_mod_read_half(meta+at)&0x3FFFu;
    if(tile*4u+4u>PORTAL_SETUP_DESC_BYTES)return -1;
    unsigned code=psx_mod_read_byte(desc+tile*4u);return code==0x3B?0x38:(int)code;
}
static unsigned checkpoint_portal_x(unsigned seat) {
    return checkpoint_lab_option==10 && !seat?1490u:1506u;
}
static unsigned checkpoint_portal_floor(unsigned seat) {
    return checkpoint_lab_option==10 && !seat?896u:1616u;
}
static int checkpoint_portal_ground(uint32_t meta,uint32_t desc) {
    for(unsigned seat=0;seat<2;++seat) {
        unsigned center=checkpoint_portal_x(seat);
        unsigned floor=checkpoint_portal_floor(seat);
        for(unsigned x=center-11;x<center+11;++x) {
            if(checkpoint_portal_tile(meta,desc,x,floor)!=0x38)return 0;
            for(unsigned y=floor-48;y<floor;++y)if(checkpoint_portal_tile(meta,desc,x,y))return 0;
        }
    }
    return 1;
}
static int checkpoint_portal_camera(void) {
    const uint32_t cam=0x800971F8u;
    const unsigned offsets[]={0x1C,0x1E,0x20,0x22,0x24,0x26,0x28,0x2A};
    const uint16_t expected[]={1264,320,1424,1424,1264,320,1424,1424};
    for(unsigned i=0;i<8;++i)if(psx_mod_read_half(cam+offsets[i])!=expected[i])return 0;
    return psx_mod_read_half(cam+14)==1424 && psx_mod_read_half(cam+10)>=320 && psx_mod_read_half(cam+10)<=1264;
}
static int checkpoint_portal_original_arrival(void) {
    return checkpoint_safe_boundary() && checkpoint_before_doors_idle(0) && checkpoint_before_doors_idle(1) &&
        psx_mod_read_word(PLAYER+8)==(480u<<16) && le32(p2.body+8)==(504u<<16) &&
        psx_mod_read_word(PLAYER+12)==(1595u<<16) && le32(p2.body+12)==(1594u<<16) &&
        checkpoint_portal_camera();
}
static void checkpoint_portal_place(void) {
    const uint32_t x=checkpoint_portal_x(0)<<16,y=(checkpoint_portal_floor(0)-23u)<<16;
    psx_mod_write_word(PLAYER+8,x);psx_mod_write_word(PLAYER+0x18,x);
    psx_mod_write_word(PLAYER+12,y);psx_mod_write_word(PLAYER+0x1C,y);
    put32(p2.body+8,checkpoint_portal_x(1)<<16);put32(p2.body+0x18,checkpoint_portal_x(1)<<16);
    put32(p2.body+12,1593u<<16);put32(p2.body+0x1C,1593u<<16);
#ifdef MMX6_COOP_MODERN_STATE
    independent_invalidate();
#endif
    checkpoint_pending.phase=3;checkpoint_pending.placed_world=psx_mod_read_word(PLAY+0x90);
    psx_mod_write_byte(diagnostic+0xAD,1); /* Position applied; no scanner call. */
}
static int checkpoint_portal_ready(void) {
    if((uint32_t)(psx_mod_read_word(PLAY+0x90)-checkpoint_pending.placed_world)<2u ||
       !checkpoint_safe_boundary() || !checkpoint_before_doors_idle(0) || !checkpoint_before_doors_idle(1) ||
       psx_mod_read_word(PLAYER+8)!=(checkpoint_portal_x(0)<<16) || le32(p2.body+8)!=(checkpoint_portal_x(1)<<16) ||
       psx_mod_read_word(PLAYER+12)!=((checkpoint_portal_floor(0)-21u)<<16) || le32(p2.body+12)!=(1594u<<16) ||
       !checkpoint_portal_camera() || psx_mod_read_half(0x80097202u)!=1264)return 0;
    unsigned portal=0,capsule=0,reploid=0;
    for(uint32_t a=0x8008EF48u;a<0x80090C88u;a+=0x9Cu)
        if((psx_mod_read_byte(a)&1u) && psx_mod_read_byte(a+1)==0x1C && psx_mod_read_byte(a+2)==1 &&
           psx_mod_read_word(a+0x10)==0x800F2B0Cu && psx_mod_read_byte(a+4)==1 &&
           psx_mod_read_byte(a+5)==1 && !psx_mod_read_byte(a+6) &&
           psx_mod_read_word(a+8)==(1552u<<16) && psx_mod_read_word(a+12)==(1584u<<16) &&
           psx_mod_read_word(a+0x68)==0x800F38B8u)++portal;
    for(uint32_t a=0x800C1220u;a<0x800C4560u;a+=0xA4u) {
        if(!(psx_mod_read_byte(a)&1u) || psx_mod_read_byte(a+4)!=1 || psx_mod_read_byte(a+5) || psx_mod_read_byte(a+6))continue;
        if(psx_mod_read_byte(a+1)==26 && psx_mod_read_byte(a+2)==4 &&
           psx_mod_read_word(a+0x10)==0x800F2E24u && psx_mod_read_word(a+8)==(1424u<<16) &&
           psx_mod_read_word(a+12)==(1604u<<16))++capsule;
        if(psx_mod_read_word(a)==0x013B0441u && psx_mod_read_byte(a+7)==1 &&
           psx_mod_read_word(a+0x10)==0x800F2B7Cu && psx_mod_read_word(a+8)==(1360u<<16) &&
           psx_mod_read_word(a+12)==(1600u<<16) && psx_mod_read_word(a+0x68)==0x80078910u &&
           (psx_mod_read_byte(a+0x70)&8u))++reploid;
    }
    return portal==1 && capsule==1 && reploid==1;
}

/* F106 prerequisite only. A genuine healthy CP2 arrival precedes a single
 * position/history placement above an original pit. Native fall, fatal flag,
 * FALLEN lifecycle, portal admission and recovery are all later observations. */
static unsigned checkpoint_fallen_portal_seat(void) {
    return checkpoint_lab_option==13?1u:0u;
}
static int checkpoint_fallen_portal_live_portal(void);
static int checkpoint_fallen_portal_source(void) {
    return checkpoint_portal_source() &&
        psx_mod_read_word(0x80073D50u)==0x130B0200u &&
        psx_mod_read_word(0x80073D54u)==0x130B0300u &&
        checkpoint_hash(0x8002820Cu,0x80028338u)==0x1D131C3Cu &&
        checkpoint_hash(0x8002953Cu,0x80029598u)==0xA6AAD062u &&
        checkpoint_hash(0x80029658u,0x800296A8u)==0x1D9D0B4Bu &&
        checkpoint_hash(0x8002D2B0u,0x8002D2D4u)==0xEB31C56Au &&
        checkpoint_hash(0x8003D850u,0x8003D8A8u)==0x26065317u &&
        checkpoint_hash(0x8003AD18u,0x8003ADB4u)==0x24EE2986u &&
        (psx_mod_read_word(0x800F2E24u)&0xFFFFFFFEu)==0x04041A00u &&
        psx_mod_read_word(0x800F2E28u)==0x06380590u;
}
static int checkpoint_fallen_portal_ground(uint32_t meta,uint32_t desc) {
    /* Both source standing boxes have radius11 and height19. Include both
     * offsets (X2/Zero3), from initial1593 through native fatalY1688.
     * Native282F0 owns the fatal flag once camera.maxY1424 +256+8 is crossed. */
    for(unsigned x=1301;x<=1322;++x)
        for(unsigned y=1576;y<=1710;++y)
            if(checkpoint_portal_tile(meta,desc,x,y))return 0;
    for(unsigned x=1495;x<=1516;++x) {
        if(checkpoint_portal_tile(meta,desc,x,1616)!=0x38)return 0;
        for(unsigned y=1568;y<1616;++y)
            if(checkpoint_portal_tile(meta,desc,x,y))return 0;
    }
    /* Exact source admission misses for either seat assignment: capsule
     * radius65 at1424, Reploid radii8+11 at1360, both strictly overlapping.
     * Neither input routing nor future native interaction is manufactured. */
    const int centers[]={1312,1506};
    for(unsigned seat=0;seat<2;++seat) {
        int capsule=centers[seat]-1424,reploid=centers[seat]-1360;
        if((capsule>-65 && capsule<65) || (reploid>-19 && reploid<19))return 0;
    }
    return 1;
}
static int checkpoint_fallen_portal_standing_vy(uint32_t value) {
    /* Original beam handoff 8003D850..8003D8A8 writes VY=-0x80000 at
     * 3D87C/880 (FNV26065317, SHA256
     * 75c2be1b842225635daeed3106a879e7d51c3ae197f95aa31187dd3f23b85068).
     * Arrival35144 reaches idle3AD18..3ADB4 (FNV24EE2986), which sets
     * action2 without clearing VY. Permit this retained standing envelope;
     * it is not a universal gravity clamp, and placement never changes VY. */
    int32_t vy=(int32_t)value;
    return vy>=-0x80000 && vy<=0;
}
static int checkpoint_fallen_portal_original_arrival(void) {
    if(!checkpoint_portal_original_arrival() || !checkpoint_fallen_portal_live_portal())return 0;
    return !psx_mod_read_word(PLAYER+0x20) &&
        checkpoint_fallen_portal_standing_vy(psx_mod_read_word(PLAYER+0x24)) &&
        !le32(p2.body+0x20) && checkpoint_fallen_portal_standing_vy(le32(p2.body+0x24));
}
static void checkpoint_fallen_portal_place(void) {
    unsigned fallen=checkpoint_fallen_portal_seat();
    for(unsigned seat=0;seat<2;++seat) {
        uint32_t x=(seat==fallen?1312u:1506u)<<16,y=1593u<<16;
        if(seat) {
            put32(p2.body+8,x);put32(p2.body+0x18,x);
            put32(p2.body+12,y);put32(p2.body+0x1C,y);
        } else {
            psx_mod_write_word(PLAYER+8,x);psx_mod_write_word(PLAYER+0x18,x);
            psx_mod_write_word(PLAYER+12,y);psx_mod_write_word(PLAYER+0x1C,y);
        }
    }
#ifdef MMX6_COOP_MODERN_STATE
    independent_invalidate();
#endif
    checkpoint_pending.phase=3;checkpoint_pending.placed_world=psx_mod_read_word(PLAY+0x90);
    psx_mod_write_byte(diagnostic+0xAD,1);
}
static int checkpoint_fallen_portal_live_portal(void) {
    unsigned count=0;
    for(uint32_t a=0x8008EF48u;a<0x80090C88u;a+=0x9Cu) {
        if(!(psx_mod_read_byte(a)&1u) || psx_mod_read_word(a+0x10)!=0x800F2B0Cu)continue;
        if(psx_mod_read_byte(a+1)!=0x1C || psx_mod_read_byte(a+2)!=1 ||
           psx_mod_read_byte(a+4)!=1 || psx_mod_read_byte(a+5)!=1 || psx_mod_read_byte(a+6) ||
           psx_mod_read_word(a+8)!=(1552u<<16) || psx_mod_read_word(a+12)!=(1584u<<16) ||
           psx_mod_read_word(a+0x68)!=0x800F38B8u)return 0;
        ++count;
    }
    /* The ordinary scanner may not reach the portal before this early fall
     * witness. Authenticate its authored source; require every resident copy
     * to remain the exact idle portal, without demanding an allocation. */
    return count<=1;
}
static int checkpoint_fallen_portal_ready(void) {
    if((uint32_t)(psx_mod_read_word(PLAY+0x90)-checkpoint_pending.placed_world)<2u ||
       !checkpoint_safe_boundary() || !checkpoint_portal_camera() ||
       !checkpoint_fallen_portal_live_portal())return 0;
    unsigned fallen=checkpoint_fallen_portal_seat(),safe=fallen^1u;
    if(!checkpoint_before_doors_idle(safe))return 0;
    uint8_t primary[sizeof p2.body];capture(PLAYER,primary,sizeof primary);
    const uint8_t *fall=fallen?p2.body:primary,*standing=safe?p2.body:primary;
    int32_t y=(int32_t)le32(fall+12);
    return (fall[0]&1u) && fall[4]==1 && fall[0x5C]>0 && fall[0x5C]<128 &&
        le32(fall+8)==(1312u<<16) && fall[2]==fallen &&
        le32(fall+0x68)==0x80073D50u+fallen*4u &&
        fall[0x67] && !(fall[0x70]&8u) && !le32(fall+0x20) &&
        (int32_t)le32(fall+0x24)<0 && y>(1593<<16) && y<(1688<<16) &&
        le32(standing+8)==(1506u<<16) && le32(standing+12)==((1595u-safe)<<16) &&
        !le32(standing+0x20) && checkpoint_fallen_portal_standing_vy(le32(standing+0x24));
}
