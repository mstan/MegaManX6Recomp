/* F80 prerequisite only. Original SecretLab2B18/0 CP0 arrival precedes one
 * position/history bypass. Enemy admission, AI, attacks and HP stay native. */
static int checkpoint_gate_enemy_source(void) {
    static const struct { uint32_t first,end,hash; } code[]={
        {0x80014084u,0x800140A8u,0xE387433Fu},
        {0x800154D0u,0x8001551Cu,0xE8DB401Du},
        {0x8002798Cu,0x80027A50u,0x18C6AC34u},
        {0x80028078u,0x800280F4u,0xB274C2DAu},
        {0x80029D18u,0x8002A338u,0xA4F26DC8u},
        {0x8002BBF4u,0x8002BCB0u,0x00AD7F28u},
        {0x80030304u,0x8003040Cu,0xEF191854u},
        {0x800304D8u,0x8003056Cu,0x630190CCu},
        {0x8002F840u,0x8002FBECu,0xA2CFC9E6u},
        {0x8003D850u,0x8003D8A8u,0x26065317u},
        {0x8003AD18u,0x8003ADB4u,0x24EE2986u},
        {0x800EA3B0u,0x800EA424u,0x847D841Eu},
        {0x800E9BDCu,0x800E9D70u,0x1228E3D2u},
        {0x800E9D70u,0x800E9F18u,0x38ADBFD0u},
        {0x800F64C4u,0x800F64D0u,0xEBAA0A87u},
        {0x800F664Cu,0x800F665Cu,0xC80BDD63u}
    };
    for(unsigned i=0;i<sizeof code/sizeof code[0];++i)
        if(checkpoint_hash(code[i].first,code[i].end)!=code[i].hash)return 0;
    return psx_mod_read_word(0x80073D50u)==0x130B0200u &&
        psx_mod_read_word(0x80073D54u)==0x130B0300u &&
        psx_mod_read_half(0x8006DA44u)==114 &&
        psx_mod_read_half(0x800763E0u)==0x0A19u &&
        psx_mod_read_word(0x80076370u)==0x800F5998u &&
        psx_mod_read_word(0x8006DCFCu)==0x800F5F88u &&
        psx_mod_read_word(SCRATCH+0x80)==0x800F5F88u &&
        psx_mod_read_word(0x800F5F90u)==0x800EA3B0u &&
        psx_mod_read_word(0x8007347Cu)==0x8002BBF4u &&
        psx_mod_read_word(0x800F5CE4u)==0x00700320u &&
        (psx_mod_read_word(0x800F5CE0u)&0x00FFFFFEu)==0x00010200u;
}
static int checkpoint_gate_enemy_assets(uint32_t *meta,uint32_t *desc) {
    *meta=psx_mod_read_word(SCRATCH+8);*desc=psx_mod_read_word(SCRATCH+12);
    return psx_mod_read_word(SCRATCH+4)==0x80097438u &&
        psx_mod_read_half(0x800CD338u)==0x0A19u && psx_mod_read_half(0x8008EC10u)==250 &&
        *meta>=0x80010000u && *meta<=0x80200000u-92160u &&
        *desc>=0x80010000u && *desc<=0x80200000u-7436u &&
        checkpoint_hash(0x80097438u,0x80097438u+750u)==0x91D0BA11u &&
        checkpoint_hash(*meta,*meta+92160u)==0x2C46D0EAu &&
        checkpoint_hash(*desc,*desc+7436u)==0x429ACAC2u;
}
static int checkpoint_gate_enemy_tile(uint32_t meta,uint32_t desc,unsigned x,unsigned y) {
    if(x>=25u*256u || y>=10u*256u)return -1;
    unsigned cell=psx_mod_read_byte(0x80097438u+(y>>8)*25u+(x>>8));
    if(!cell)return 0;
    unsigned at=cell*512u+((y>>4)&15u)*32u+((x>>4)&15u)*2u;
    if(at+2u>92160u)return -1;
    unsigned tile=psx_mod_read_half(meta+at)&0x3FFFu;
    if(tile*4u+4u>7436u)return -1;
    unsigned code=psx_mod_read_byte(desc+tile*4u);return code==0x3B?0x38:(int)code;
}
static int checkpoint_gate_enemy_ground(uint32_t meta,uint32_t desc) {
    const unsigned centers[]={152,176,560,576};
    for(unsigned seat=0;seat<4;++seat)for(unsigned x=centers[seat]-11;x<centers[seat]+11;++x) {
        if(checkpoint_gate_enemy_tile(meta,desc,x,144)!=0x38)return 0;
        for(unsigned y=80;y<144;++y)if(checkpoint_gate_enemy_tile(meta,desc,x,y))return 0;
    }
    /* Admit just beyond592 on this continuous floor. The later approach to
     * the native800/112 actor has an original64px recess, floor176 instead
     * of144. Native walking/drop/jump, never this fixture, must cross it. */
    for(unsigned x=549;x<=821;++x) {
        unsigned floor=x>=704 && x<768?176u:144u;
        if(checkpoint_gate_enemy_tile(meta,desc,x,floor)!=0x38)return 0;
        for(unsigned y=80;y<floor;++y)if(checkpoint_gate_enemy_tile(meta,desc,x,y))return 0;
    }
    return 1;
}
static int checkpoint_gate_enemy_inactive(void) {
    if(psx_mod_read_word(0x800F5CE0u)!=0x00010200u)return 0;
    for(uint32_t a=0x8008EF48u;a<0x80090C88u;a+=0x9Cu)
        if((psx_mod_read_byte(a)&1u) && psx_mod_read_word(a+0x10)==0x800F5CE0u)return 0;
    return 1;
}
static int checkpoint_gate_enemy_camera(unsigned placed) {
    const uint32_t cam=0x800971F8u;
    const uint16_t bounds[]={1600,0,0,0,1600,0,0,0};
    for(unsigned i=0;i<8;++i)if(psx_mod_read_half(cam+0x1C+i*2)!=bounds[i])return 0;
    int x=(int16_t)psx_mod_read_half(cam+10),old_x=(int16_t)psx_mod_read_half(cam+0x16);
    /* Original right-strip edge C+368 must still exclude authored800.
     * This reads the actual canonical camera; inactivity separately covers
     * supplemental guest-view scans. It never installs a camera or scanner. */
    return x>=0 && x<=(placed?431:32) && old_x>=0 && old_x<=431 &&
        !psx_mod_read_half(cam+14) && !psx_mod_read_half(cam+0x1A);
}
static int checkpoint_gate_enemy_clear(void) {
    const uint32_t pools[][3]={{0x8008EF48u,0x80090C88u,0x9C},
        {0x80093C98u,0x80095098u,0xA0},{0x800950A0u,0x800964A0u,0xA0},{0x800C1220u,0x800C4560u,0xA4}};
    for(unsigned pool=0;pool<4;++pool)for(uint32_t a=pools[pool][0];a<pools[pool][1];a+=pools[pool][2]) {
        if(!(psx_mod_read_byte(a)&1u))continue;
        int x=(int16_t)psx_mod_read_half(a+10),y=(int16_t)psx_mod_read_half(a+14);
        if(x>496 && x<640 && y>16 && y<208)return 0;
    }
    return 1;
}
static int checkpoint_gate_enemy_standing(void) {
    if(!checkpoint_safe_boundary() || !checkpoint_before_doors_idle(0) || !checkpoint_before_doors_idle(1))return 0;
    uint8_t primary[sizeof p2.body];capture(PLAYER,primary,sizeof primary);
    for(unsigned seat=0;seat<2;++seat) {
        const uint8_t *body=seat?p2.body:primary;
        int32_t vy=(int32_t)le32(body+0x24);
        /* Exact original beam/idle spans above qualify only this retained
         * standing handoff envelope. Placement preserves VX and VY. */
        if(le32(body+0x20) || vy< -0x80000 || vy>0 ||
           body[0x5C]!=32 || body[0x5D]!=32 || body[0x5E]!=32)return 0;
    }
    return psx_mod_read_byte(PLAY+0x5B)==32 && psx_mod_read_byte(PLAY+0x5C)==32;
}
static int checkpoint_gate_enemy_original_arrival(void) {
    return checkpoint_gate_enemy_standing() && checkpoint_gate_enemy_camera(0) &&
        checkpoint_gate_enemy_clear() && checkpoint_gate_enemy_inactive() &&
        psx_mod_read_word(PLAYER+8)==(152u<<16) && le32(p2.body+8)==(176u<<16) &&
        psx_mod_read_word(PLAYER+12)==(123u<<16) && le32(p2.body+12)==(122u<<16);
}
static void checkpoint_gate_enemy_place(void) {
    psx_mod_write_word(PLAYER+8,560u<<16);psx_mod_write_word(PLAYER+0x18,560u<<16);
    psx_mod_write_word(PLAYER+12,121u<<16);psx_mod_write_word(PLAYER+0x1C,121u<<16);
    put32(p2.body+8,576u<<16);put32(p2.body+0x18,576u<<16);
    put32(p2.body+12,121u<<16);put32(p2.body+0x1C,121u<<16);
#ifdef MMX6_COOP_MODERN_STATE
    independent_invalidate();
#endif
    checkpoint_pending.phase=3;checkpoint_pending.placed_world=psx_mod_read_word(PLAY+0x90);
    psx_mod_write_byte(diagnostic+0xAD,1);
}
static int checkpoint_gate_enemy_ready(void) {
    uint32_t elapsed=psx_mod_read_word(PLAY+0x90)-checkpoint_pending.placed_world;
    return elapsed>=2u && elapsed<0x80000000u && checkpoint_gate_enemy_standing() &&
        checkpoint_gate_enemy_camera(1) && checkpoint_gate_enemy_clear() && checkpoint_gate_enemy_inactive() &&
        psx_mod_read_word(PLAYER+8)==(560u<<16) && le32(p2.body+8)==(576u<<16) &&
        psx_mod_read_word(PLAYER+12)==(123u<<16) && le32(p2.body+12)==(122u<<16);
}
