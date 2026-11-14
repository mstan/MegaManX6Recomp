/* Amazon's first original seed7 support belongs to either living view. The
 * canonical camera can remain at the entrance while the guest approaches.
 * Reuse the native allocator and bounds helpers; never run its AI twice. */
#ifdef MMX6_COOP_MODERN_STATE
static int private_zero_saber_visibility(CPUState *cpu,uint32_t address) {
    uint32_t actor=cpu->gpr[4];
    /* Original BIN1 Zero801ED6F0 follows its owning PLAYER, then D910
     * tests visibility with authored128/128. The private player pass still
     * has the canonical camera; a distant native saber otherwise loses3
     * before the existing retained-body-frame draw can append its pixels. */
    if(address!=0x8002CCB0u || cpu->gpr[31]!=0x801ED918u || view_call ||
       !independent_views || !ready || !enrolled || failed || !zero_projected || private_draw ||
       private_actor.character!=MMX6_COOP_CHARACTER_ZERO || psx_mod_read_byte(PLAYER+2)!=1 ||
       life.status[1]!=MMX6_COOP_ALIVE || psx_mod_read_byte(PLAYER+4)!=1 ||
       psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
       actor<0x800950A0u || actor>=0x800964A0u || (actor-0x800950A0u)%0xA0u ||
       !(psx_mod_read_byte(actor)&1u) || psx_mod_read_byte(actor+1)<24 || psx_mod_read_byte(actor+1)>42 ||
       psx_mod_read_word(actor+0x38) ||
       psx_mod_read_word(actor+0x3C)!=psx_mod_read_word(PLAYER+0x3C) ||
       psx_mod_read_half(actor+0x40)!=psx_mod_read_half(PLAYER+0x40) ||
       psx_mod_read_word(0x801ED704u)!=0xACC20008u || psx_mod_read_word(0x801ED710u)!=0xACC3000Cu ||
       psx_mod_read_word(0x801ED90Cu)!=0x24050080u || psx_mod_read_word(0x801ED910u)!=0x0C00B32Cu ||
       psx_mod_read_word(0x801ED914u)!=0x24060080u)return 0;
    int limits[4];for(unsigned i=0;i<4;++i)limits[i]=(int16_t)psx_mod_read_half(VIEW_CAMERA+0x1C+i*2);
    if(limits[0]<limits[1] || limits[2]<limits[3])return 0;
    int x=(int16_t)psx_mod_read_half(PLAYER+10)-160,y=(int16_t)psx_mod_read_half(PLAYER+14)-96;
    if(x<limits[1])x=limits[1];if(x>limits[0])x=limits[0];
    if(y<limits[3])y=limits[3];if(y>limits[2])y=limits[2];
    uint32_t saved[4]={psx_mod_read_word(VIEW_CAMERA+8),psx_mod_read_word(VIEW_CAMERA+12),view_call,cpu->gpr[6]};
    STATE_WORDS(restore_saber_view,144,saved,4);
    view_call=1;psx_mod_write_word(VIEW_CAMERA+8,(uint32_t)x<<16);psx_mod_write_word(VIEW_CAMERA+12,(uint32_t)y<<16);
    /* The inner original entry applies any widescreen margin once. */
    cpu->gpr[6]=128;uint32_t result=guest(cpu,address,actor,128);
    psx_mod_write_word(VIEW_CAMERA+8,saved[0]);psx_mod_write_word(VIEW_CAMERA+12,saved[1]);
    view_call=saved[2];cpu->gpr[6]=saved[3];cpu->gpr[2]=result;STATE_POP(restore_saber_view);return 1;
}
static int amazon_support_source(void) {
    uint32_t placement=psx_mod_read_word(0x800F6540u);
    return (placement&0x00FFFFFEu)==0x00000700u &&
        !(placement&0x0F000000u) && (placement>>24)<=0x60u &&
        psx_mod_read_word(0x800F6544u)==0x017C0220u &&
        psx_mod_read_word(0x800734A4u)==0x800F6368u &&
        psx_mod_read_word(0x800EC268u)==0x0C00B131u &&
        psx_mod_read_word(0x800EC280u)==0xA0A20001u &&
        psx_mod_read_word(0x800EC030u)==0x0C00B2FFu &&
        psx_mod_read_word(0x800EC044u)==0x24050020u &&
        psx_mod_read_word(0x800EC048u)==0x0C00B32Cu &&
        psx_mod_read_word(0x800EC04Cu)==0x24060020u &&
        psx_mod_read_word(0x800EC060u)==0x24050020u &&
        psx_mod_read_word(0x800EC064u)==0x0C00B32Cu;
}
static int amazon_guest_view(int *x,int *y) {
    if(!independent_views || !ready || !enrolled || failed || private_draw || inside || zero_world ||
       scene_owner || clear_phase || pause_owner>=0 ||
       psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
       psx_mod_read_byte(PLAY+12)!=1 || psx_mod_read_byte(PLAY+13) ||
       psx_mod_read_byte(PLAY+0x10) || coop_world_hold() ||
       life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_ALIVE ||
       !(p2.body[0]&1u) || p2.body[4]!=1 || p2.body[5]<2 ||
       !p2.body[0x5C] || p2.body[0x5C]>=128 || p2.body[0xCC] || p2.body[0xE0] ||
       psx_mod_read_byte(VIEW_CAMERA+4)!=1 || !psx_mod_read_byte(VIEW_CAMERA+0x44) ||
       psx_mod_read_half(VIEW_CAMERA+0x30)!=160 || psx_mod_read_half(VIEW_CAMERA+0x32)!=160 ||
       psx_mod_read_half(VIEW_CAMERA+0x2C)!=96 || !amazon_support_source())return 0;
    /* Simulation-owned body and authored limits, never draw-cadence caches. */
    int limits[4];for(unsigned i=0;i<4;++i)limits[i]=(int16_t)psx_mod_read_half(VIEW_CAMERA+0x1C+i*2);
    if(limits[0]<limits[1] || limits[2]<limits[3])return 0;
    *x=(int16_t)(le32(p2.body+8)>>16)-160;*y=(int16_t)(le32(p2.body+12)>>16)-96;
    if(*x<limits[1])*x=limits[1];if(*x>limits[0])*x=limits[0];
    if(*y<limits[3])*y=limits[3];if(*y>limits[2])*y=limits[2];
    return 1;
}
static void amazon_guest_placement_scan(CPUState *cpu,uint32_t address) {
    (void)address;int x,y;
    if(!amazon_guest_view(&x,&y) || 544<=x-48 || 544>=x+368 || 380<=y-48 || 380>=y+288)return;
    /* Restrict the real list to this original record. Save the next record's
     * header, used only as a temporary native sentinel, and the real root. */
    uint32_t stack=cpu->gpr[29]+0x10u;
    uint32_t saved[7]={cpu->gpr[6],cpu->gpr[7],stack,psx_mod_read_word(stack),(uint32_t)inside,
        psx_mod_read_word(0x800734A4u),psx_mod_read_word(0x800F6548u)};
    STATE_WORDS(restore_amazon_scan,83,saved,7);
    inside=1;cpu->gpr[6]=(uint32_t)(y-48);cpu->gpr[7]=(uint32_t)(y+288);
    psx_mod_write_word(0x800734A4u,0x800F6540u);
    psx_mod_write_word(0x800F6548u,(saved[6]&0x00FFFFFFu)|0x0F000000u);
    psx_mod_write_word(stack,0);
    guest(cpu,0x80029F38u,(uint32_t)(x-48),(uint32_t)(x+368));
    cpu->gpr[6]=saved[0];cpu->gpr[7]=saved[1];psx_mod_write_word(stack,saved[3]);
    psx_mod_write_word(0x800734A4u,saved[5]);psx_mod_write_word(0x800F6548u,saved[6]);inside=(int)saved[4];
    STATE_POP(restore_amazon_scan);
}
static int amazon_guest_support(uint32_t actor,int *x,int *y) {
    return actor>=0x800C1220u && actor<0x800C4560u && !((actor-0x800C1220u)%0xA4u) &&
        (psx_mod_read_byte(actor)&1u) && psx_mod_read_byte(actor+1)==1 &&
        psx_mod_read_byte(actor+4)==1 && !psx_mod_read_byte(actor+0x14) &&
        psx_mod_read_word(actor+0x10)==0x800F6540u &&
        psx_mod_read_word(actor+0x30)==0x800F73D4u &&
        psx_mod_read_word(actor+0x68)==0x800F73ECu && amazon_guest_view(x,y);
}
static int guest_geometry_lifetime(CPUState *cpu,uint32_t address) {
    if(world_guest_bounds(cpu,0))return 1;
    if(shared_effect_view_bounds(cpu,address))return 1;
    if(intro_guest_streaming_lifetime(cpu))return 1;
    if(intro_guest_geometry_lifetime(cpu,address))return 1;
    int x,y;uint32_t actor=cpu->gpr[4];
    if(cpu->gpr[31]!=0x800EC038u || !amazon_guest_support(actor,&x,&y))return 0;
    /* Original2CBFC uint16 half-open rectangle, original radii64/64. */
    int dx=(int16_t)(psx_mod_read_half(actor+10)-(uint16_t)x);
    int dy=(int16_t)(psx_mod_read_half(actor+14)-(uint16_t)y);
    if((uint16_t)(dx+64)>=448u || (uint16_t)(dy+64)>=368u)return 0;
    cpu->gpr[2]=0;return 1;
}
static int amazon_guest_support_visibility(CPUState *cpu,uint32_t address) {
    if(world_guest_bounds(cpu,1))return 1;
    if(shared_effect_view_bounds(cpu,address))return 1;
    if(intro_guest_streaming_visibility(cpu))return 1;
    if(private_zero_saber_visibility(cpu,address))return 1;
    int x,y;uint32_t actor=cpu->gpr[4];
    if((cpu->gpr[31]!=0x800EC050u && cpu->gpr[31]!=0x800EC06Cu) ||
       !amazon_guest_support(actor,&x,&y))return 0;
    uint32_t saved[5]={psx_mod_read_word(VIEW_CAMERA+8),psx_mod_read_word(VIEW_CAMERA+12),
        (uint32_t)inside,cpu->gpr[5],cpu->gpr[6]};
    STATE_WORDS(restore_amazon_visible,84,saved,5);
    /* These pinned callers author32/32. Pass that original radius so the
     * widescreen entry hook applies its margin once to each native call. */
    inside=1;cpu->gpr[6]=32;uint32_t result=guest(cpu,address,actor,32);
    if(!psx_mod_read_byte(actor+3)) {
        psx_mod_write_word(VIEW_CAMERA+8,(uint32_t)x<<16);
        psx_mod_write_word(VIEW_CAMERA+12,(uint32_t)y<<16);
        cpu->gpr[6]=32;result=guest(cpu,address,actor,32);
        psx_mod_write_word(VIEW_CAMERA+8,saved[0]);psx_mod_write_word(VIEW_CAMERA+12,saved[1]);
    }
    cpu->gpr[6]=saved[4];inside=(int)saved[2];cpu->gpr[2]=result;STATE_POP(restore_amazon_visible);return 1;
}
#else
static void amazon_guest_placement_scan(CPUState *cpu,uint32_t address) {(void)cpu;(void)address;}
static int guest_geometry_lifetime(CPUState *cpu,uint32_t address) {return shared_effect_view_bounds(cpu,address) || intro_guest_geometry_lifetime(cpu,address);}
static int amazon_guest_support_visibility(CPUState *cpu,uint32_t address) {return shared_effect_view_bounds(cpu,address);}
#endif
static int guest_actor_visibility(CPUState *cpu,uint32_t address) {
    if(world_guest_bounds(cpu,2))return 1;
    return shared_effect_view_bounds(cpu,address);
}
