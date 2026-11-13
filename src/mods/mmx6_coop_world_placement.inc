/* Original stage placements and their native offscreen tests belong to both
 * living views. Allocation, difficulty, latches, AI and terminal cleanup stay
 * in the original guest code; presentation never advances world actors. */
#ifdef MMX6_COOP_MODERN_STATE
/* PLAYER+CC suspends native body/attack updates, not ownership of its view.
 * In particular Zero's air-saber landing freezes for four ticks. Shared
 * actors and inactive placement latches must survive that interval. */
static int world_guest_view(int *x,int *y) {
    if(!independent_views || !ready || !enrolled || failed || private_draw || inside || zero_world ||
       scene_owner || clear_phase || pause_owner>=0 || coop_world_hold() ||
       psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
       psx_mod_read_byte(PLAY+12)>1 || psx_mod_read_byte(PLAY+13)>1 ||
       psx_mod_read_byte(PLAY+0x10) ||
       life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_ALIVE ||
       !(p2.body[0]&1u) || p2.body[4]!=1 || p2.body[5]<2 ||
       !p2.body[0x5C] || p2.body[0x5C]>=128 || p2.body[0xE0] ||
       psx_mod_read_byte(VIEW_CAMERA+4)!=1 || !psx_mod_read_byte(VIEW_CAMERA+0x44) ||
       psx_mod_read_half(VIEW_CAMERA+0x30)!=160 || psx_mod_read_half(VIEW_CAMERA+0x32)!=160 ||
       psx_mod_read_half(VIEW_CAMERA+0x2C)!=96)return 0;
    int limits[4];
    for(unsigned i=0;i<4;++i) {
        if(!psx_mod_read_byte(PLAY+12) && !psx_mod_read_byte(PLAY+13) && intro_camera_valid)
            limits[i]=(int16_t)(intro_camera_requests[i*2]|intro_camera_requests[i*2+1]<<8);
        else limits[i]=(int16_t)psx_mod_read_half(VIEW_CAMERA+0x1C+i*2);
    }
    if(limits[0]<limits[1] || limits[2]<limits[3])return 0;
    *x=(int16_t)(le32(p2.body+8)>>16)-160;*y=(int16_t)(le32(p2.body+12)>>16)-96;
    if(*x<limits[1])*x=limits[1];if(*x>limits[0])*x=limits[0];
    if(*y<limits[3])*y=limits[3];if(*y>limits[2])*y=limits[2];
    return 1;
}
static uint32_t world_placement_root_slot(void) {
    return 0x8007349Cu+psx_mod_read_byte(PLAY+12)*8u+psx_mod_read_byte(PLAY+13)*4u;
}
static uint32_t world_placement_end(uint32_t root) {
    if(root<0x800E9000u || root>=0x801FC000u || (root&3u))return 0;
    for(uint32_t at=root;at<root+0x4000u && at<0x801FFFF0u;at+=8u) {
        unsigned category=psx_mod_read_byte(at+3);
        if(category==15u)return at;
        if((category&15u)>5u)return 0;
    }
    return 0;
}
static void world_guest_placement_scan(CPUState *cpu) {
    int x,y;if(!world_guest_view(&x,&y))return;
    if(checkpoint_hash(0x80029F38u,0x8002A33Cu)!=0x72A44816u ||
       checkpoint_hash(0x8002CBFCu,0x8002CCB0u)!=0xF4DCD43Cu)return;
    uint32_t slot=world_placement_root_slot(),root=psx_mod_read_word(slot);
    uint32_t end=world_placement_end(root);if(!end)return;
    for(uint32_t at=root;at<end;at+=8u) {
        if(psx_mod_read_byte(at)&0x81u)continue;
        if(!psx_mod_read_byte(PLAY+12) && !psx_mod_read_byte(PLAY+13) &&
           (psx_mod_read_byte(at+3)&15u)==5u && psx_mod_read_byte(at+1)==10u &&
           !intro_foreground_source())continue;
        int px=(int16_t)psx_mod_read_half(at+4),py=(int16_t)psx_mod_read_half(at+6);
        if(px<=x-48 || px>=x+368 || py<=y-48 || py>=y+288)continue;
        uint32_t stack=cpu->gpr[29]+0x10u;
        uint32_t saved[]={cpu->gpr[6],cpu->gpr[7],stack,psx_mod_read_word(stack),
            (uint32_t)inside,root,psx_mod_read_word(at+8),at+8,slot};
        STATE_WORDS(restore_world_scan,148,saved,9);
        inside=1;cpu->gpr[6]=(uint32_t)(y-48);cpu->gpr[7]=(uint32_t)(y+288);
        psx_mod_write_word(slot,at);
        psx_mod_write_word(at+8,(saved[6]&0x00FFFFFFu)|0x0F000000u);
        psx_mod_write_word(stack,0);
        guest(cpu,0x80029F38u,(uint32_t)(x-48),(uint32_t)(x+368));
        cpu->gpr[6]=saved[0];cpu->gpr[7]=saved[1];psx_mod_write_word(stack,saved[3]);
        psx_mod_write_word(slot,saved[5]);psx_mod_write_word(at+8,saved[6]);
        inside=(int)saved[4];STATE_POP(restore_world_scan);
    }
}
static int world_guest_actor(uint32_t actor,int *x,int *y) {
    if(!((actor>=0x8008EF48u && actor<0x80090C88u && !((actor-0x8008EF48u)%0x9Cu)) ||
         (actor>=0x8009B7B0u && actor<0x8009C9B0u && !((actor-0x8009B7B0u)%0x30u)) ||
         (actor>=0x800C1220u && actor<0x800C4560u && !((actor-0x800C1220u)%0xA4u)) ||
         (actor>=0x800CD410u && actor<0x800CF810u && !((actor-0x800CD410u)%0x60u))) ||
       !world_guest_view(x,y) || !(psx_mod_read_byte(actor)&1u) ||
       psx_mod_read_byte(actor+0x14))return 0;
    uint32_t root=psx_mod_read_word(world_placement_root_slot()),end=world_placement_end(root);
    uint32_t record=psx_mod_read_word(actor+0x10);
    if(!end || record<root || record>=end || (record-root)%8u ||
       psx_mod_read_byte(actor+1)!=psx_mod_read_byte(record+1) ||
       psx_mod_read_byte(actor+2)!=psx_mod_read_byte(record+2))return 0;
    unsigned category=psx_mod_read_byte(record+3)&15u;
    if(category<3u)return actor>=0x8008EF48u && actor<0x80090C88u && !((actor-0x8008EF48u)%0x9Cu);
    if(category==3u)return actor>=0x8009B7B0u && actor<0x8009C9B0u && !((actor-0x8009B7B0u)%0x30u);
    if(category==4u)return actor>=0x800C1220u && actor<0x800C4560u && !((actor-0x800C1220u)%0xA4u);
    if(category==5u)return actor>=0x800CD410u && actor<0x800CF810u && !((actor-0x800CD410u)%0x60u);
    return 0;
}
static int world_guest_bounds(CPUState *cpu,int visibility) {
    int x,y;uint32_t actor=cpu->gpr[4];
    uint32_t caller=cpu->gpr[31];
    if(caller<0x80010008u || caller>=0x80200000u || (caller&3u) ||
       psx_mod_read_word(caller-8)!=(visibility?0x0C00B32Cu:0x0C00B2FFu))return 0;
    if(!world_guest_actor(actor,&x,&y))return 0;
    if(!psx_mod_read_byte(PLAY+12) && !psx_mod_read_byte(PLAY+13) &&
       actor>=0x800CD410u && actor<0x800CF810u && psx_mod_read_byte(actor+1)==10u &&
       (!visibility || caller!=0x800F96C8u || !intro_foreground_source()))return 0;
    unsigned rx=cpu->gpr[5],ry=cpu->gpr[6];
    int dx=(int16_t)(psx_mod_read_half(actor+10)-(uint16_t)x);
    int dy=(int16_t)(psx_mod_read_half(actor+14)-(uint16_t)y);
    unsigned width=visibility?psx_mod_read_word(0x8009B79Cu):320u;
    if((uint16_t)(dx+rx)>=(uint16_t)(rx*2u+width) ||
       (uint16_t)(dy+ry)>=(uint16_t)(ry*2u+240u))return 0;
    if(visibility)psx_mod_write_byte(actor+3,1);else cpu->gpr[2]=0;
    return 1;
}
#else
static void world_guest_placement_scan(CPUState *cpu) {(void)cpu;}
static int world_guest_bounds(CPUState *cpu,int visibility) {(void)cpu;(void)visibility;return 0;}
#endif
