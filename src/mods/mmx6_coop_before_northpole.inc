/* Declared F111 approach only. Original CP3 init/arrival and all authored
 * camera/scanner/producer updates precede readiness. Position is the only bypass. */
static int checkpoint_northpole_source(void) {
    return psx_mod_read_word(0x80073D50u)==0x130B0200u &&
        psx_mod_read_word(0x80073D54u)==0x130B0300u &&
        psx_mod_read_word(SCRATCH+0x94)==0x800F6554u &&
        psx_mod_read_word(0x800F6570u)==0x800ECDE8u &&
        psx_mod_read_word(0x800F6BF8u)==0x800ED150u &&
        checkpoint_hash(0x800ED150u,0x800ED1ECu)==0x4B3B5134u &&
        checkpoint_hash(0x800EBF18u,0x800EC1DCu)==0x3BC9F4C6u &&
        psx_mod_read_word(0x800F64D0u)==0x800F049Cu &&
        checkpoint_hash(0x800F049Cu,0x800F050Cu)==0x18CFB99Du &&
        checkpoint_hash(0x80027BA0u,0x80027C98u)==0xD5E21EAAu &&
        checkpoint_hash(0x800F6DF4u,0x800F6DFCu)==0xCB9E2AB8u;
}
static int checkpoint_northpole_assets(uint32_t *meta,uint32_t *desc) {
    *meta=psx_mod_read_word(SCRATCH+8);*desc=psx_mod_read_word(SCRATCH+12);
    uint32_t hash=0;
    if(*meta>=0x80010000u && *meta<=0x80200000u-103424u)hash=checkpoint_hash(*meta,*meta+103424u);
    /* Original F04B0..F04FC closes three tiles behind the CP3 approach when
     * canonical X>=4833,Y>=1217. The full bank must be exactly original or
     * exactly that source-table copy; partial/other collision edits fail. */
    unsigned native_closure=(checkpoint_pending.phase==3 ||
        (checkpoint_lab_option==28 && checkpoint_pending.phase>=4)) &&
        (int16_t)psx_mod_read_half(PLAYER+10)>=4833 &&
        (int16_t)psx_mod_read_half(PLAYER+14)>=1217 && hash==0x65F367C2u;
    return psx_mod_read_word(SCRATCH+4)==0x80097438u &&
        psx_mod_read_half(0x800CD338u)==0x071Bu && psx_mod_read_half(0x8008EC10u)==189 &&
        *meta>=0x80010000u && *meta<=0x80200000u-103424u &&
        *desc>=0x80010000u && *desc<=0x80200000u-13412u &&
        checkpoint_hash(0x80097438u,0x80097438u+567u)==0x63300EA4u &&
        (hash==0x142A1278u || native_closure) &&
        checkpoint_hash(*desc,*desc+13412u)==0x9A9D6BF9u;
}
static int checkpoint_northpole_tile(uint32_t meta,uint32_t desc,unsigned x,unsigned y) {
    if(x>=27u*256u || y>=7u*256u)return -1;
    unsigned cell=psx_mod_read_byte(0x80097438u+(y>>8)*27u+(x>>8));
    if(!cell)return 0;
    unsigned at=cell*512u+((y>>4)&15u)*32u+((x>>4)&15u)*2u;
    if(at+2u>103424u)return -1;
    unsigned tile=psx_mod_read_half(meta+at)&0x3FFFu;
    return tile*4u+4u<=13412u?psx_mod_read_byte(desc+tile*4u):-1;
}
static int checkpoint_northpole_ground(uint32_t meta,uint32_t desc) {
    const unsigned centers[]={5016,5120};
    for(unsigned seat=0;seat<2;++seat)for(unsigned x=centers[seat]-11;x<centers[seat]+11;++x) {
        if(checkpoint_northpole_tile(meta,desc,x,1616)!=0x3C)return 0;
        for(unsigned y=1568;y<1616;++y)if(checkpoint_northpole_tile(meta,desc,x,y))return 0;
    }
    return 1;
}
static int checkpoint_northpole_camera(void) {
    const uint32_t cam=0x800971F8u;
    const unsigned offsets[]={0x1C,0x1E,0x20,0x22,0x24,0x26,0x28,0x2A};
    const uint16_t expected[]={4976,4640,1456,1264,4976,4640,1456,1264};
    for(unsigned i=0;i<8;++i)if(psx_mod_read_half(cam+offsets[i])!=expected[i])return 0;
    int x=(int16_t)psx_mod_read_half(cam+10),y=(int16_t)psx_mod_read_half(cam+14);
    return x>=4640 && x<=4976 && y>=1264 && y<=1456;
}
static int checkpoint_northpole_reploid_miss(uint32_t a) {
    /* Only the original subtype22 idle Reploid. Native contact2DCF4 rejects
     * both standing heroes horizontally: source radii8+11, strict overlap<19.
     * This says nothing about future Left input, which can rescue it. */
    if(psx_mod_read_word(a)!=0x01160441u || psx_mod_read_word(a+4)!=0x01000001u ||
       psx_mod_read_word(a+0x10)!=0x800F608Cu || psx_mod_read_word(a+8)!=(5096u<<16) ||
       psx_mod_read_word(a+12)!=(1600u<<16) || psx_mod_read_byte(a+0x14) ||
       psx_mod_read_word(a+0x68)!=0x8007891Cu || psx_mod_read_byte(a+0x70)!=8 ||
       psx_mod_read_byte(a+0x84)!=1 || psx_mod_read_byte(a+0x7E) ||
       psx_mod_read_word(0x8007891Cu)!=0x10080000u ||
       psx_mod_read_word(0x800F6564u)!=0x8004F834u ||
       (psx_mod_read_word(0x800F608Cu)&0xFFFFFFFEu)!=0x04160400u ||
       psx_mod_read_word(0x800F6090u)!=0x064813E8u)return 0;
    for(unsigned n=0x20;n<0x30;n+=4)if(psx_mod_read_word(a+n))return 0;
    for(unsigned i=0;i<9;++i)
        if(checkpoint_hash(portal_setup_code[i].first,portal_setup_code[i].end)!=portal_setup_code[i].hash)return 0;
    int x0=(int16_t)psx_mod_read_half(PLAYER+10)-5096;
    int x1=(int16_t)(le32(p2.body+8)>>16)-5096;
    return (x0<=-19 || x0>=19) && (x1<=-19 || x1>=19);
}
static int checkpoint_northpole_clear(void) {
    /* Refuse a bypass into any nearby active enemy, projectile or shared solid.
     * Original producers atY1376 are outside these conservative rectangles. */
    const uint32_t pools[][3]={{0x8008EF48u,0x80090C88u,0x9C},
        {0x80093C98u,0x80095098u,0xA0},{0x800950A0u,0x800964A0u,0xA0},{0x800C1220u,0x800C4560u,0xA4}};
    for(unsigned pool=0;pool<4;++pool)for(uint32_t a=pools[pool][0];a<pools[pool][1];a+=pools[pool][2]) {
        if(!(psx_mod_read_byte(a)&1u))continue;
        int x=(int16_t)psx_mod_read_half(a+10),y=(int16_t)psx_mod_read_half(a+14);
        if(y>1514 && y<1675 && ((x>4952 && x<5080)||(x>5056 && x<5184)) &&
           !(pool==3 && checkpoint_northpole_reploid_miss(a)))return 0;
    }
    return 1;
}
static int checkpoint_northpole_original_arrival(void) {
    return checkpoint_safe_boundary() && checkpoint_before_doors_idle(0) && checkpoint_before_doors_idle(1) &&
        psx_mod_read_word(PLAYER+8)==(4800u<<16) && le32(p2.body+8)==(4824u<<16) &&
        checkpoint_northpole_camera() && checkpoint_northpole_clear();
}
static void checkpoint_northpole_place(void) {
    psx_mod_write_word(PLAYER+8,5016u<<16);psx_mod_write_word(PLAYER+0x18,5016u<<16);
    psx_mod_write_word(PLAYER+12,1594u<<16);psx_mod_write_word(PLAYER+0x1C,1594u<<16);
    put32(p2.body+8,5120u<<16);put32(p2.body+0x18,5120u<<16);
    put32(p2.body+12,1593u<<16);put32(p2.body+0x1C,1593u<<16);
#ifdef MMX6_COOP_MODERN_STATE
    independent_invalidate();
#endif
    checkpoint_pending.phase=3;checkpoint_pending.placed_world=psx_mod_read_word(PLAY+0x90);
    psx_mod_write_byte(diagnostic+0xAD,1);
}
static int checkpoint_northpole_ready(void) {
    if((uint32_t)(psx_mod_read_word(PLAY+0x90)-checkpoint_pending.placed_world)<2u ||
       !checkpoint_safe_boundary() || !checkpoint_before_doors_idle(0) || !checkpoint_before_doors_idle(1) ||
       psx_mod_read_word(PLAYER+8)!=(5016u<<16) || le32(p2.body+8)!=(5120u<<16) ||
       psx_mod_read_word(PLAYER+12)!=(1595u<<16) || le32(p2.body+12)!=(1594u<<16) ||
       !checkpoint_northpole_camera() || !checkpoint_northpole_clear())return 0;
    unsigned producers=0;
    for(uint32_t a=0x800C1220u;a<0x800C4560u;a+=0xA4u)
        if((psx_mod_read_byte(a)&1u) && psx_mod_read_byte(a+1)==7 && !psx_mod_read_byte(a+2) &&
           psx_mod_read_byte(a+4)==1 && psx_mod_read_byte(a+6)==8 &&
           psx_mod_read_word(a+0x10)==0x800F60D4u &&
           psx_mod_read_word(a+8)==(4992u<<16) && psx_mod_read_word(a+12)==(1376u<<16))++producers;
    return producers==1;
}

/* F36 prerequisite only: ordinary P2 admission creates the real falling child.
 * First contact and later carry are exclusively native observations, not setup
 * conditions. No allocator/constructor or physics is reproduced here. */
static int checkpoint_northpole_pickup_source(void) {
    uint32_t table=psx_mod_read_word(SCRATCH+0x80u);
    return table==0x800F6654u &&
        psx_mod_read_word(table+47u*4u)==0x8004D77Cu &&
        (psx_mod_read_word(0x800F6104u)&0xFFFFFFFEu)==0x00012F00u &&
        psx_mod_read_word(0x800F6108u)==0x02A01430u &&
        checkpoint_hash(0x80029F38u,0x8002A258u)==0xE979ACE4u &&
        checkpoint_hash(0x8002BBF4u,0x8002BCCCu)==0x30908E4Eu &&
        checkpoint_hash(0x8004D77Cu,0x8004DA7Cu)==0x1523A40Du &&
        psx_mod_read_word(0x800F6BD8u+6u*4u)==0x800EC628u &&
        psx_mod_read_word(0x800EC63Cu)==0x0C00B4ACu;
}
static int checkpoint_northpole_pickup_child(uint32_t a) {
    if(a<0x800C1220u || a>=0x800C4560u || (a-0x800C1220u)%0xA4u ||
       !(psx_mod_read_byte(a)&1u) || psx_mod_read_byte(a+1)!=7 || psx_mod_read_byte(a+2)!=12 ||
       psx_mod_read_byte(a+4)!=1 || psx_mod_read_byte(a+6)!=6 ||
       psx_mod_read_word(a+0x68)!=a+0x80u || psx_mod_read_word(a+0x80u)!=0x18180000u)return 0;
    uint32_t parent=psx_mod_read_word(a+0x7Cu);
    int x=(int16_t)psx_mod_read_half(a+10),y=(int16_t)psx_mod_read_half(a+14);
    return parent>=0x800C1220u && parent<0x800C4560u && !((parent-0x800C1220u)%0xA4u) &&
        (psx_mod_read_byte(parent)&1u) && psx_mod_read_byte(parent+1)==7 && !psx_mod_read_byte(parent+2) &&
        psx_mod_read_byte(parent+4)==1 && psx_mod_read_byte(parent+6)==9 &&
        psx_mod_read_word(parent+0x10)==0x800F60D4u &&
        psx_mod_read_word(parent+8)==(4992u<<16) && psx_mod_read_word(parent+12)==(1376u<<16) &&
        x>=5064 && x<=5208 && y>=1408 && y<=1504;
}
static uint32_t checkpoint_northpole_pickup_actor(void) {
    uint32_t found=0;
    for(uint32_t a=0x8008EF48u;a<0x80090C88u;a+=0x9Cu)
        if((psx_mod_read_byte(a)&1u) && psx_mod_read_word(a+0x10)==0x800F6104u) {
            if(found)return UINT32_MAX;found=a;
        }
    return found;
}
static void checkpoint_northpole_pickup(CPUState *cpu,const Mmx6Checkpoint *entry) {
    uint32_t meta,desc;
    if(!checkpoint_safe_boundary() || !checkpoint_before_doors_idle(0) || !checkpoint_before_doors_idle(1))return;
    if(!checkpoint_source(entry) || !checkpoint_northpole_source() ||
       !checkpoint_northpole_assets(&meta,&desc) || !checkpoint_northpole_pickup_source()) {
        checkpoint_cancel(CHECKPOINT_SOURCE);return;
    }
    uint32_t item=checkpoint_northpole_pickup_actor(),child=checkpoint_pending.placed_world;
    if(checkpoint_pending.phase==4) {
        if(item==UINT32_MAX) {checkpoint_cancel(CHECKPOINT_UNSAFE);return;}
        child=0;
        for(uint32_t a=0x800C1220u;a<0x800C4560u;a+=0xA4u)
            if(checkpoint_northpole_pickup_child(a)) {child=a;break;}
        if(!child)return;
        /* Exact original scanner ABI, including fifth argument0. Its native
         * allocator creates2F/1 from sourceF6104; next ordinary world update
         * invokes4D77C/4D7B8 under the original assembly context. */
        if(item) {checkpoint_pending.placed_world=child;checkpoint_pending.phase=5;return;}
        uint32_t stack=cpu->gpr[29];
        if((stack&3u) || stack<0x80010000u || stack>0x801FFFECu) {checkpoint_cancel(CHECKPOINT_UNSAFE);return;}
        uint32_t old=psx_mod_read_word(stack+0x10u),a2=cpu->gpr[6],a3=cpu->gpr[7];
        psx_mod_write_word(stack+0x10u,0);cpu->gpr[6]=671;cpu->gpr[7]=674;
        guest(cpu,0x80029F38u,5167,5170);
        psx_mod_write_word(stack+0x10u,old);cpu->gpr[6]=a2;cpu->gpr[7]=a3;
        checkpoint_pending.placed_world=child;checkpoint_pending.phase=5;
        return;
    }
    if(!checkpoint_northpole_pickup_child(child) || item==UINT32_MAX) {checkpoint_cancel(CHECKPOINT_UNSAFE);return;}
    if(!item || psx_mod_read_byte(item+4)!=1)return; /* Actual native constructor first. */
    if(psx_mod_read_byte(item+1)!=47 || psx_mod_read_byte(item+2)!=1 ||
       psx_mod_read_word(item+0x30)!=0x800787C0u || psx_mod_read_word(item+0x68)!=0x800787F0u) {
        checkpoint_cancel(CHECKPOINT_SOURCE);return;
    }
    int x=(int16_t)psx_mod_read_half(child+10),top=(int16_t)psx_mod_read_half(child+14)-24;
    for(int px=x-29;px<=x+27;++px)for(int py=top-48;py<top;++py)
        if(checkpoint_northpole_tile(meta,desc,(unsigned)px,(unsigned)py)) {checkpoint_cancel(CHECKPOINT_UNSAFE);return;}
    /* Native +68 boxes use signed center offsets and half extents:
     * 73D50=00/02/0B/13 ->X bottomY+21; 73D54=00/03/0B/13 ->Zero+22;
     * 787F0=00/00/0A/0A ->item+10; child00/00/18/18 ->topY-24.
     * These poses have zero foot gap. 32208/323D4 must still perform native
     * overlap/snap before2E1A0/2E664 can establish top8. Phase6 falls at2px
     * per update; ordinary accelerating fall may catch it, never setupVY.
     * Keep nativeHP/air/ground/velocity, supportbits98/9C and every phase. */
    for(unsigned offset=8;offset<=0x18;offset+=0x10) {
        psx_mod_write_word(PLAYER+offset,(uint32_t)(x-17)<<16);
        psx_mod_write_word(PLAYER+offset+4,(uint32_t)(top-21)<<16);
        put32(p2.body+offset,(uint32_t)(x-9)<<16);put32(p2.body+offset+4,(uint32_t)(top-22)<<16);
        psx_mod_write_word(item+offset,(uint32_t)(x+17)<<16);
        psx_mod_write_word(item+offset+4,(uint32_t)(top-10)<<16);
    }
#ifdef MMX6_COOP_MODERN_STATE
    independent_invalidate();
#endif
    psx_mod_write_byte(diagnostic+0xAD,3);checkpoint_complete(cpu);
}
