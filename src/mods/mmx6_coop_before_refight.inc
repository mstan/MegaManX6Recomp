/* F122/F124 development prerequisite only. Original0C/0 CP1 initializes
 * normally before one disclosed position/history bypass. All portal, room,
 * boss, progress, gravity, camera and native collision outcomes stay native. */
static int checkpoint_refight_source(void) {
    static const struct { uint32_t first,end,hash; } code[]={
        {0x800EC430u,0x800ECCACu,0xDFDC6516u},
        {0x800ED7D0u,0x800ED818u,0xB02A84CAu},
        {0x80014084u,0x800140A8u,0xE387433Fu},
        {0x800154D0u,0x8001551Cu,0xE8DB401Du},
        {0x8002798Cu,0x80027A50u,0x18C6AC34u},
        {0x80028078u,0x800280F4u,0xB274C2DAu},
        {0x80029D18u,0x8002A338u,0xA4F26DC8u},
        {0x80030304u,0x8003040Cu,0xEF191854u},
        {0x800304D8u,0x8003056Cu,0x630190CCu},
        {0x8002F840u,0x8002FBECu,0xA2CFC9E6u},
        {0x8003D850u,0x8003D8A8u,0x26065317u},
        {0x8003AD18u,0x8003ADB4u,0x24EE2986u},
        {0x8003D308u,0x8003D34Cu,0x8B958C0Au},
        {0x800E9A34u,0x800E9B68u,0x289D0633u},
        {0x800ED098u,0x800ED0B4u,0x328FB140u},
        {0x800262ECu,0x8002649Cu,0x2C53650Fu},
        {0x80027BA0u,0x80027C98u,0xD5E21EAAu},
        {0x8002A3E8u,0x8002A5BCu,0x8985783Fu},
        {0x8006DEF4u,0x8006DEF8u,0xB1924E8Au},
        {0x800ED374u,0x800ED378u,0xABB67F19u},
        {0x800735B4u,0x800735B8u,0x204776ABu}
    };
    for(unsigned i=0;i<sizeof code/sizeof code[0];++i)
        if(checkpoint_hash(code[i].first,code[i].end)!=code[i].hash)return 0;
    return psx_mod_read_word(0x80073D50u)==0x130B0200u &&
        psx_mod_read_word(0x80073D54u)==0x130B0300u &&
        psx_mod_read_half(0x8006DA2Cu)==104 && psx_mod_read_half(0x800763C8u)==0x0E0Cu &&
        psx_mod_read_word(0x80076340u)==0x800ECD90u &&
        psx_mod_read_word(0x8006DFACu)==0x800ED424u &&
        psx_mod_read_word(SCRATCH+0x94)==0x800ED424u &&
        psx_mod_read_word(0x800ED480u)==0x800EC860u &&
        /* The secondary mapcopy retires through original2C9D4, which ORs
         * record flag0x80; accept only pristine or that exact retired state. */
        (psx_mod_read_word(0x800ED088u)&0xFFFFFF7Fu)==0x03000100u &&
        psx_mod_read_word(0x800ED08Cu)==0x04380208u &&
        /* 29E84..29E8C category4 takes29EFC before the category0..2
         * lifetime writes. Only allocator bit0 changes on this placement. */
        (psx_mod_read_word(0x800ED040u)&0xFFFFFFFEu)==0x04021700u &&
        psx_mod_read_word(0x800ED044u)==0x04E80760u;
}
static int checkpoint_refight_assets(uint32_t *meta,uint32_t *desc) {
    *meta=psx_mod_read_word(SCRATCH+8);*desc=psx_mod_read_word(SCRATCH+12);
    return psx_mod_read_word(SCRATCH+4)==0x80097438u &&
        psx_mod_read_half(0x800CD338u)==0x0E0Cu && psx_mod_read_half(0x8008EC10u)==168 &&
        *meta>=0x80010000u && *meta<=0x80200000u-82944u &&
        *desc>=0x80010000u && *desc<=0x80200000u-4036u &&
        checkpoint_hash(0x80097438u,0x80097438u+504u)==0x2B74F1CDu &&
        /* Original CP1 cat3/type1 E9A34 copies six references via27BA0;
         * authenticate that complete loaded bank, not pristine DAT104. */
        checkpoint_hash(*meta,*meta+82944u)==0xAF40A509u &&
        checkpoint_hash(*desc,*desc+4036u)==0xE5AD1AB2u;
}
static int checkpoint_refight_tile(uint32_t meta,uint32_t desc,unsigned x,unsigned y) {
    if(x>=12u*256u || y>=14u*256u)return -1;
    unsigned cell=psx_mod_read_byte(0x80097438u+(y>>8)*12u+(x>>8));
    if(!cell)return 0;
    unsigned at=cell*512u+((y>>4)&15u)*32u+((x>>4)&15u)*2u;
    if(at+2u>82944u)return -1;
    unsigned tile=psx_mod_read_half(meta+at)&0x3FFFu;
    if(tile*4u+4u>4036u)return -1;
    unsigned code=psx_mod_read_byte(desc+tile*4u);return code==0x3B?0x38:(int)code;
}
static int checkpoint_refight_ground(uint32_t meta,uint32_t desc) {
    for(unsigned x=1841;x<=1904;++x) {
        if(checkpoint_refight_tile(meta,desc,x,1264)!=0x38)return 0;
        for(unsigned y=1216;y<1264;++y)if(checkpoint_refight_tile(meta,desc,x,y))return 0;
    }
    return 1;
}
/* Refusal-only LAB reads at the failing world boundary. An asynchronous TCP
 * snapshot can observe resources after the original world changes them. */
static void checkpoint_refight_refusal(const Mmx6Checkpoint *entry) {
#ifdef MMX6_COOP_AGREED_CHECKPOINT
    uint32_t meta=0,desc=0;
    unsigned common=checkpoint_source(entry),source=checkpoint_refight_source();
    unsigned assets=checkpoint_refight_assets(&meta,&desc);
    unsigned ground=assets && checkpoint_refight_ground(meta,desc);
    checkpoint_source_refusal(entry);
    checkpoint_refusal_value("refight-atomic-common-source-assets-ground",0,entry->record,
        common|(source<<1)|(assets<<2)|(ground<<3),15);
    const uint32_t addresses[]={0x80073D50u,0x80073D54u,0x8006DA2Cu,0x800763C8u,
        0x80076340u,0x8006DFACu,SCRATCH+0x94,0x800ED480u,0x800ED088u,0x800ED08Cu,
        0x800ED040u,0x800ED044u,SCRATCH+4,0x800CD338u,0x8008EC10u};
    const uint32_t expected[]={0x130B0200u,0x130B0300u,104u,0x0E0Cu,
        0x800ECD90u,0x800ED424u,0x800ED424u,0x800EC860u,0x03000100u,0x04380208u,
        0x04021700u,0x04E80760u,0x80097438u,0x0E0Cu,168u};
    for(unsigned i=0;i<sizeof addresses/sizeof addresses[0];++i)
        checkpoint_refusal_value("refight-atomic-word",i,addresses[i],psx_mod_read_word(addresses[i]),expected[i]);
    checkpoint_refusal_value("refight-atomic-layout-hash",0,0x80097438u,
        checkpoint_hash(0x80097438u,0x80097438u+504u),0x2B74F1CDu);
    checkpoint_refusal_value("refight-atomic-meta-pointer",0,SCRATCH+8,meta,0);
    checkpoint_refusal_value("refight-atomic-desc-pointer",0,SCRATCH+12,desc,0);
    if(meta>=0x80010000u && meta<=0x80200000u-82944u)
        checkpoint_refusal_value("refight-atomic-meta-hash",0,meta,
            checkpoint_hash(meta,meta+82944u),0xAF40A509u);
    if(desc>=0x80010000u && desc<=0x80200000u-4036u)
        checkpoint_refusal_value("refight-atomic-desc-hash",0,desc,
            checkpoint_hash(desc,desc+4036u),0xE5AD1AB2u);
    if(assets && !ground)for(unsigned x=1841;x<=1904;++x)for(unsigned y=1216;y<=1264;++y) {
        int actual=checkpoint_refight_tile(meta,desc,x,y),wanted=y==1264?0x38:0;
        if(actual!=wanted) {
            checkpoint_refusal_value("refight-atomic-tile-XY",0,(y<<16)|x,(uint32_t)actual,(uint32_t)wanted);return;
        }
    }
#else
    (void)entry;
#endif
}
static int checkpoint_refight_camera(void) {
    const uint32_t cam=0x800971F8u;
    /* CP1 original current and target bounds: maxX,minX,maxY,minY. */
    const uint16_t bounds[]={1632,1472,1744,1024,1632,1472,1744,1024};
    for(unsigned i=0;i<8;++i)if(psx_mod_read_half(cam+0x1C+i*2)!=bounds[i])return 0;
    int x=(int16_t)psx_mod_read_half(cam+10),y=(int16_t)psx_mod_read_half(cam+14);
    return x>=1472 && x<=1632 && y>=1024 && y<=1744;
}
static int checkpoint_refight_clear(void) {
    const uint32_t pools[][3]={{0x8008EF48u,0x80090C88u,0x9C},
        {0x80093C98u,0x80095098u,0xA0},{0x800950A0u,0x800964A0u,0xA0},
        {0x800C1220u,0x800C4560u,0xA4}};
    for(unsigned p=0;p<4;++p)for(uint32_t a=pools[p][0];a<pools[p][1];a+=pools[p][2]) {
        if(!(psx_mod_read_byte(a)&1u))continue;
        /* The native target portal is intentionally nearby, but must still
         * be unused and not departing. No authored actor is removed. */
        if(p==3 && psx_mod_read_word(a+0x10)==0x800ED040u) {
            if(psx_mod_read_byte(a+1)!=23 || psx_mod_read_byte(a+2)!=2 ||
               psx_mod_read_byte(a+4)>1 || psx_mod_read_byte(a+5) || psx_mod_read_byte(a+6))return 0;
            continue;
        }
        /* EC764..7E8 creates a draw-only24/sub0 icon, with parent+50 and
         * no collision boxes. ECC60 updates only animation/draw; retaining
         * this exact native cosmetic must not make the prerequisite wait. */
        if(p==3 && psx_mod_read_byte(a)==0x51 && psx_mod_read_byte(a+1)==24 &&
           !psx_mod_read_byte(a+2) && psx_mod_read_byte(a+4)<=1 &&
           psx_mod_read_word(a+0x30)==0x800ED7D0u &&
           !psx_mod_read_word(a+0x68) && !psx_mod_read_word(a+0x54)) {
            uint32_t parent=psx_mod_read_word(a+0x50);
            if(parent>=0x800C1220u && parent<0x800C4560u && !((parent-0x800C1220u)%0xA4u) &&
               (psx_mod_read_byte(parent)&1u) && psx_mod_read_byte(parent+1)==23 &&
               psx_mod_read_byte(parent+2)==2 && psx_mod_read_word(parent+0x10)==0x800ED040u &&
               psx_mod_read_word(a+0x3C)==psx_mod_read_word(parent+0x3C) &&
               psx_mod_read_half(a+10)==1888 && psx_mod_read_half(a+14)==1228)continue;
        }
        int x=(int16_t)psx_mod_read_half(a+10),y=(int16_t)psx_mod_read_half(a+14);
        if(x>1792 && x<1904 && y>1184 && y<1296)return 0;
    }
    return !psx_mod_read_byte(PLAY+0x2E);
}
static int checkpoint_refight_standing(void) {
    if(!checkpoint_safe_boundary() || !checkpoint_before_doors_idle(0) ||
       !checkpoint_before_doors_idle(1))return 0;
    uint8_t primary[sizeof p2.body];capture(PLAYER,primary,sizeof primary);
    for(unsigned seat=0;seat<2;++seat) {
        const uint8_t *body=seat?p2.body:primary;int32_t vy=(int32_t)le32(body+0x24);
        /* Source3D850/idle3AD18 authenticate only this original beam-handoff
         * envelope. Neither velocity is changed by position placement. */
        if(le32(body+0x20) || vy< -0x80000 || vy>0 ||
           body[0x5C]!=32 || body[0x5D]!=32 || body[0x5E]!=32)return 0;
    }
    return psx_mod_read_byte(PLAY+0x5B)==32 && psx_mod_read_byte(PLAY+0x5C)==32;
}
static int checkpoint_refight_original_arrival(uint32_t meta,uint32_t desc) {
    if(!checkpoint_refight_standing() || !checkpoint_refight_camera() || !checkpoint_refight_clear())return 0;
    for(unsigned seat=0;seat<2;++seat) {
        uint32_t x=seat?le32(p2.body+8):psx_mod_read_word(PLAYER+8);
        uint32_t y=seat?le32(p2.body+12):psx_mod_read_word(PLAYER+12);
        if((x&0xFFFFu) || x<(1643u<<16) || x>(1781u<<16) || y!=((seat?1146u:1147u)<<16))return 0;
        for(unsigned px=(x>>16)-11;px<(x>>16)+11;++px) {
            if(checkpoint_refight_tile(meta,desc,px,1168)!=0x38)return 0;
            for(unsigned py=1120;py<1168;++py)if(checkpoint_refight_tile(meta,desc,px,py))return 0;
        }
    }
    return 1;
}
static void checkpoint_refight_place(void) {
    psx_mod_write_word(PLAYER+8,1852u<<16);psx_mod_write_word(PLAYER+0x18,1852u<<16);
    psx_mod_write_word(PLAYER+12,1241u<<16);psx_mod_write_word(PLAYER+0x1C,1241u<<16);
    put32(p2.body+8,1852u<<16);put32(p2.body+0x18,1852u<<16);
    put32(p2.body+12,1241u<<16);put32(p2.body+0x1C,1241u<<16);
#ifdef MMX6_COOP_MODERN_STATE
    independent_invalidate();
#endif
    checkpoint_pending.phase=3;checkpoint_pending.placed_world=psx_mod_read_word(PLAY+0x90);
    psx_mod_write_byte(diagnostic+0xAD,1);
}
static int checkpoint_refight_ready(void) {
    uint32_t elapsed=psx_mod_read_word(PLAY+0x90)-checkpoint_pending.placed_world;
    return elapsed>=2u && elapsed<0x80000000u && checkpoint_refight_standing() &&
        checkpoint_refight_camera() && checkpoint_refight_clear() &&
        psx_mod_read_word(PLAYER+8)==(1852u<<16) && le32(p2.body+8)==(1852u<<16) &&
        psx_mod_read_word(PLAYER+12)==(1243u<<16) && le32(p2.body+12)==(1242u<<16);
}
