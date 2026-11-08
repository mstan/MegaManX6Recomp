/* One original intro geometry placement, shared simulation only. Native
 * 29F38 still owns allocation/difficulty/latches; no actor or event is made
 * here. Its one native update must also survive the original lifetime test
 * while this additional living view owns the actor. */
#ifdef MMX6_COOP_MODERN_STATE
static int intro_geometry_source(void) {
    uint32_t placement=psx_mod_read_word(0x800FA394u);
    return (placement&0x00FFFFFEu)==0x00030000u &&
        !(placement&0x0F000000u) && (placement>>24)<=0x60u &&
        psx_mod_read_word(0x800FA398u)==0x02E01360u &&
        psx_mod_read_word(0x8007349Cu)==0x800FA214u &&
        checkpoint_hash(0x80029D18u,0x8002A338u)==0xA4F26DC8u &&
        checkpoint_hash(0x8002CBFCu,0x8002CCB0u)==0xF4DCD43Cu &&
        checkpoint_hash(0x800EA1D8u,0x800EA8E0u)==0x759777E7u;
}
static int intro_guest_view(int *x,int *y) {
    if(!independent_views || !enrolled || failed || private_draw || inside || zero_world ||
       scene_owner || clear_phase || pause_owner>=0 || !intro_camera_valid ||
       psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
       psx_mod_read_byte(PLAY+12) || psx_mod_read_byte(PLAY+13) ||
       psx_mod_read_byte(PLAY+0x10) || coop_world_hold() ||
       life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_ALIVE ||
       !(p2.body[0]&1u) || p2.body[4]!=1 || p2.body[5]<2 ||
       !p2.body[0x5C] || p2.body[0x5C]>=128 || p2.body[0xCC] || p2.body[0xE0] ||
       psx_mod_read_byte(VIEW_CAMERA+4)!=1 || !psx_mod_read_byte(VIEW_CAMERA+0x44) ||
       psx_mod_read_half(VIEW_CAMERA+0x30)!=160 || psx_mod_read_half(VIEW_CAMERA+0x32)!=160 ||
       psx_mod_read_half(VIEW_CAMERA+0x2C)!=96 || !intro_geometry_source())return 0;
    /* Deterministic original320x240 body-follow rectangle, clamped by this
     * hero's authored requests. Never consult render-cadence camera caches. */
    int limits[4];for(unsigned i=0;i<4;++i)
        limits[i]=(int16_t)(intro_camera_requests[i*2]|intro_camera_requests[i*2+1]<<8);
    if(limits[0]<limits[1] || limits[2]<limits[3])return 0;
    *x=(int16_t)(le32(p2.body+8)>>16)-160;*y=(int16_t)(le32(p2.body+12)>>16)-96;
    if(*x<limits[1])*x=limits[1];if(*x>limits[0])*x=limits[0];
    if(*y<limits[3])*y=limits[3];if(*y>limits[2])*y=limits[2];
    return 1;
}
static uint32_t intro_placement_end(void) {
    for(uint32_t at=0x800FA214u;at<0x800FA424u;at+=8u)
        if(psx_mod_read_byte(at+3)==15)return at;
    return 0;
}
static void intro_guest_streaming_scan(CPUState *cpu) {
    int x,y;if(!intro_guest_view(&x,&y))return;
    uint32_t end=intro_placement_end();if(!end)return;
    /* Admit original records individually. A second whole-list scan would
     * also reset inactive placements outside its rectangle, including ones
     * belonging to the primary view. Native allocation and latches stay in
     * 29F38; the special geometry record retains its existing path below. */
    for(uint32_t at=0x800FA214u;at<end;at+=8u) {
        if(at==0x800FA394u || (psx_mod_read_byte(at)&0x81u) ||
           (psx_mod_read_byte(at+3)&15u)>=3u)continue;
        int px=(int16_t)psx_mod_read_half(at+4),py=(int16_t)psx_mod_read_half(at+6);
        if(px<=x-48 || px>=x+368 || py<=y-48 || py>=y+288)continue;
        uint32_t stack=cpu->gpr[29]+0x10u;
        uint32_t saved[12]={cpu->gpr[6],cpu->gpr[7],stack,psx_mod_read_word(stack),
            (uint32_t)inside,psx_mod_read_word(0x8007349Cu),
            psx_mod_read_word(at+8),at+8,at,end,(uint32_t)x,(uint32_t)y};
        STATE_WORDS(restore_intro_stream,147,saved,12);
        inside=1;cpu->gpr[6]=(uint32_t)(y-48);cpu->gpr[7]=(uint32_t)(y+288);
        psx_mod_write_word(0x8007349Cu,at);
        psx_mod_write_word(at+8,(saved[6]&0x00FFFFFFu)|0x0F000000u);
        psx_mod_write_word(stack,0);
        guest(cpu,0x80029F38u,(uint32_t)(x-48),(uint32_t)(x+368));
        cpu->gpr[6]=saved[0];cpu->gpr[7]=saved[1];psx_mod_write_word(stack,saved[3]);
        psx_mod_write_word(0x8007349Cu,saved[5]);psx_mod_write_word(at+8,saved[6]);
        inside=(int)saved[4];STATE_POP(restore_intro_stream);
    }
}
static int intro_guest_streaming_actor(uint32_t actor,int *x,int *y) {
    if(actor<0x8008EF48u || actor>=0x80090C88u || (actor-0x8008EF48u)%0x9Cu ||
       !(psx_mod_read_byte(actor)&1u) || psx_mod_read_byte(actor+0x14) ||
       !intro_guest_view(x,y))return 0;
    uint32_t record=psx_mod_read_word(actor+0x10),end=intro_placement_end();
    if(!end || record<0x800FA214u || record>=end || (record-0x800FA214u)%8u ||
       record==0x800FA394u || (psx_mod_read_byte(record+3)&15u)>=3u ||
       psx_mod_read_byte(record+1)!=psx_mod_read_byte(actor+1))return 0;
    return 1;
}
static int intro_guest_streaming_lifetime(CPUState *cpu) {
    int x,y;uint32_t actor=cpu->gpr[4];
    if(!intro_guest_streaming_actor(actor,&x,&y))return 0;
    /* Preserve the native unsigned half-open test and this caller's radii.
     * Only veto retirement while a living second view still owns the actor. */
    unsigned rx=cpu->gpr[5],ry=cpu->gpr[6];
    int dx=(int16_t)(psx_mod_read_half(actor+10)-(uint16_t)x);
    int dy=(int16_t)(psx_mod_read_half(actor+14)-(uint16_t)y);
    if((uint16_t)(dx+rx)>=(uint16_t)(rx*2u+320u) ||
       (uint16_t)(dy+ry)>=(uint16_t)(ry*2u+240u))return 0;
    cpu->gpr[2]=0;return 1;
}
static int intro_guest_streaming_visibility(CPUState *cpu) {
    int x,y;uint32_t actor=cpu->gpr[4];
    if(!intro_guest_streaming_actor(actor,&x,&y))return 0;
    unsigned rx=cpu->gpr[5],ry=cpu->gpr[6];
    int dx=(int16_t)(psx_mod_read_half(actor+10)-(uint16_t)x);
    int dy=(int16_t)(psx_mod_read_half(actor+14)-(uint16_t)y);
    if((uint16_t)(dx+rx)>=(uint16_t)(rx*2u+psx_mod_read_word(0x8009B79Cu)) ||
       (uint16_t)(dy+ry)>=(uint16_t)(ry*2u+240u))return 0;
    /* Native2CCB0's shared visibility bit must include either living view.
     * Each pane's original packet projection still clips the actual sprite. */
    psx_mod_write_byte(actor+3,1);return 1;
}
static void intro_guest_placement_scan(CPUState *cpu,uint32_t address) {
    (void)address;int x,y;
    if(!intro_guest_view(&x,&y))return;
    int px=(int16_t)psx_mod_read_half(0x800FA398u),py=(int16_t)psx_mod_read_half(0x800FA39Au);
    if(px<=x-48 || px>=x+368 || py<=y-48 || py>=y+288)return;
    /* Restrict the original list to this same authored record, not a copied
     * placement with another origin. Native29F38 would otherwise reset other
     * inactive placements outside the extra rectangle. Both temporary list
     * words are future-restored state; native FA394 admitted writes remain. */
    uint32_t stack=cpu->gpr[29]+0x10u;
    uint32_t saved[7]={cpu->gpr[6],cpu->gpr[7],stack,psx_mod_read_word(stack),(uint32_t)inside,
        psx_mod_read_word(0x8007349Cu),psx_mod_read_word(0x800FA39Cu)};
    STATE_WORDS(restore_intro_scan,65,saved,7);
    inside=1;cpu->gpr[6]=(uint32_t)(y-48);cpu->gpr[7]=(uint32_t)(y+288);
    psx_mod_write_word(0x8007349Cu,0x800FA394u);
    psx_mod_write_word(0x800FA39Cu,(saved[6]&0x00FFFFFFu)|0x0F000000u);
    psx_mod_write_word(stack,0);
    guest(cpu,0x80029F38u,(uint32_t)(x-48),(uint32_t)(x+368));
    cpu->gpr[6]=saved[0];cpu->gpr[7]=saved[1];psx_mod_write_word(stack,saved[3]);
    psx_mod_write_word(0x8007349Cu,saved[5]);psx_mod_write_word(0x800FA39Cu,saved[6]);inside=(int)saved[4];
    STATE_POP(restore_intro_scan);
}
static int intro_guest_geometry_lifetime(CPUState *cpu,uint32_t address) {
    (void)address;int x,y;uint32_t actor=cpu->gpr[4];
    if(cpu->gpr[31]!=0x800EA3D8u || actor<0x8008EF48u || actor>=0x80090C88u ||
       (actor-0x8008EF48u)%0x9Cu || !(psx_mod_read_byte(actor)&1u) ||
       psx_mod_read_byte(actor+1) || psx_mod_read_byte(actor+2)!=3 ||
       psx_mod_read_byte(actor+4)!=1 || psx_mod_read_byte(actor+0x14) ||
       psx_mod_read_word(actor+0x10)!=0x800FA394u || !intro_guest_view(&x,&y))return 0;
    /* Literal original2CBFC uint16 rectangle semantics, with EA3D0's original
     * radii80/160. Existing widescreen entry changes cannot accumulate here.
     * Only veto false outside-view retirement; never run the actor twice. */
    int dx=(int16_t)(psx_mod_read_half(actor+10)-(uint16_t)x);
    int dy=(int16_t)(psx_mod_read_half(actor+14)-(uint16_t)y);
    if((uint16_t)(dx+80)>=480u || (uint16_t)(dy+160)>=560u)return 0;
    cpu->gpr[2]=0;return 1;
}
#else
static void intro_guest_streaming_scan(CPUState *cpu) {(void)cpu;}
static int intro_guest_streaming_lifetime(CPUState *cpu) {(void)cpu;return 0;}
static int intro_guest_streaming_visibility(CPUState *cpu) {(void)cpu;return 0;}
static void intro_guest_placement_scan(CPUState *cpu,uint32_t address) {(void)cpu;(void)address;}
static int intro_guest_geometry_lifetime(CPUState *cpu,uint32_t address) {(void)cpu;(void)address;return 0;}
#endif
