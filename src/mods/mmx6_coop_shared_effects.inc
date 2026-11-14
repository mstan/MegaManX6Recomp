/* Original shared pool80091298..80093C98, allocator8002C398 and deferred
 * dispatch80020430 (return80020438). Dash follow uses type1; X muzzle uses2;
 * Giga uses17/26. Original49854 waits for the muzzle's animation command,
 * allocates the real shot in the resident pool and increments PLAYER+98.
 * Its shared-pool lifetime must therefore retain the allocating player too.
 * Type26's selected801EE254 is a Zero entry but an unrelated X continuation.
 * Preserve the native selector, loop, order and shared palette/packet state;
 * run the selected callback in its allocating player's actual context. */
static int shared_effect_slot(uint32_t actor) {
    if(actor<0x80091298u || actor>=0x80093C98u || (actor-0x80091298u)%0x70u)return -1;
    return (int)((actor-0x80091298u)/0x70u);
}
/* Native terrain24 emits type3/sub8 steps and sub9 surface splashes through
 * 3C7D8/3CA70. 49A14 owns their animation, DF release and finite retirement.
 * Its 49C98/49D60 bounds calls must use the allocating hero's view too; a
 * distant guest otherwise loses the effect before its first visible sample.
 * Derive the standard native view from simulation body/limits, not draw caches. */
static int shared_common_native(void) {
    return psx_mod_read_word(0x80049C98u)==0x0C00B2FFu &&
        psx_mod_read_word(0x80049CD4u)==0xA24000DFu &&
        psx_mod_read_word(0x80049D60u)==0x0C00B32Cu;
}
static int shared_surface_source(uint32_t actor) {
    return psx_mod_read_byte(actor+1)==3 &&
        psx_mod_read_word(actor+0x30)==0x8007789Cu && shared_common_native();
}
static int shared_effect_view_bounds(CPUState *cpu,uint32_t address) {
    uint32_t actor=cpu->gpr[4];int slot=shared_effect_slot(actor);
    if(!enrolled || failed || shared_fx_call==2 || !independent_views || slot<0 ||
       !shared_effect_owners[slot] || !psx_mod_read_byte(actor) ||
       private_draw)return 0;
    /* Native type4 explosions use the void visibility writer2CB50, not the
     * type3 bounds pair. Their position/lifetime already belong to the stage;
     * only the visibility bit needs the union of living local views. */
    uint32_t table=psx_mod_read_word(SCRATCH+0x88);
    int explosion=address==0x8002CB50u && psx_mod_read_byte(actor+1)==4 &&
        psx_mod_read_word(actor+0x30)==0x80077D54u &&
        table>=0x80010000u && table<=0x801FFF00u && !(table&3u) &&
        psx_mod_read_word(table+16)==0x8004A154u &&
        ((cpu->gpr[31]==0x8004A240u && psx_mod_read_word(0x8004A238u)==0x0C00B2D4u) ||
         (cpu->gpr[31]==0x8004A2A4u && psx_mod_read_word(0x8004A29Cu)==0x0C00B2D4u));
    if(!explosion && (shared_fx_call!=1 || !shared_surface_source(actor) ||
       !((address==0x8002CBFCu && cpu->gpr[31]==0x80049CA0u) ||
         (address==0x8002CCB0u && cpu->gpr[31]==0x80049D68u))))return 0;
    unsigned primary=explosion || shared_effect_owners[slot]==1;
    if(primary && (zero_projected ||
       (life.status[1]!=MMX6_COOP_ALIVE && life.status[1]!=MMX6_COOP_JOINING)))return 0;
    if(!primary && !zero_projected)return 0;
    const uint32_t camera=0x800971F8u;
    if(psx_mod_read_byte(camera+4)!=1 || !psx_mod_read_byte(camera+0x44) ||
       psx_mod_read_half(camera+0x30)!=160 || psx_mod_read_half(camera+0x32)!=160 ||
       psx_mod_read_half(camera+0x2C)!=96)return 0;
    int limits[4];for(unsigned i=0;i<4;++i)limits[i]=(int16_t)psx_mod_read_half(camera+0x1C+i*2);
    if(limits[0]<limits[1] || limits[2]<limits[3])return 0;
    int x=(int16_t)(primary?(le32(p2.body+8)>>16):psx_mod_read_half(PLAYER+10))-160;
    int y=(int16_t)(primary?(le32(p2.body+12)>>16):psx_mod_read_half(PLAYER+14))-96;
    if(x<limits[1])x=limits[1];if(x>limits[0])x=limits[0];
    if(y<limits[3])y=limits[3];if(y>limits[2])y=limits[2];
    uint32_t saved[3]={psx_mod_read_word(camera+8),psx_mod_read_word(camera+12),(uint32_t)shared_fx_call};
    STATE_WORDS(restore_surface_view,143,saved,3);
    shared_fx_call=2; /* The inner replacement falls through to original once. */
    /* Enemy and scenery callbacks allocate their common explosions in the
     * primary world even when only the guest can see the source. Keep the
     * native result if visible there; otherwise try the living guest's view
     * before the original callback retires the effect. */
    uint32_t result=primary?guest(cpu,address,actor,cpu->gpr[5]):1;
    if(explosion?!psx_mod_read_byte(actor+3):result) {
        psx_mod_write_word(camera+8,(uint32_t)x<<16);psx_mod_write_word(camera+12,(uint32_t)y<<16);
        result=guest(cpu,address,actor,cpu->gpr[5]);
    }
    psx_mod_write_word(camera+8,saved[0]);psx_mod_write_word(camera+12,saved[1]);
    shared_fx_call=(int)saved[2];STATE_POP(restore_surface_view);cpu->gpr[2]=result;return 1;
}
static int shared_effect_allocate(CPUState *cpu,uint32_t address) {
    if(shared_fx_allocate_call || !enrolled || failed)return 0;
    shared_fx_allocate_call=1;
    uint32_t owner=zero_projected?2u:1u;
    STATE_WORDS(restore_owner,46,&owner,1);
    uint32_t actor=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    int slot=shared_effect_slot(actor);
    if(slot>=0)shared_effect_owners[slot]=(uint8_t)owner; /* Every reuse replaces stale ownership. */
    STATE_POP(restore_owner);
    shared_fx_allocate_call=0;cpu->gpr[2]=actor;return 1;
}
static uint32_t shared_effect_as_primary(CPUState *cpu,uint32_t address,uint32_t actor) {
    /* A Zero-owned world can still contain an older X effect. Preserve the
     * entire resident Zero overlay, including mutable data not yet captured
     * by the enclosing leave_zero_context. No alternate X callback is chosen. */
    static const unsigned offsets[7]={0x14,0x1C,0x24,0x28,0x38,0x3C,0xA8};
    PlayerContext resident;
    uint8_t overlay[OVERLAY_SIZE],identity[2];
    uint32_t resources[8],flags[3];
    capture_player(&resident);capture(OVERLAY,overlay,sizeof overlay);
    identity[0]=psx_mod_read_byte(PLAY+0x38);identity[1]=psx_mod_read_byte(PLAY+0x5E);
    for(unsigned i=0;i<7;++i)resources[i]=psx_mod_read_word(SCRATCH+offsets[i]);
    resources[7]=psx_mod_read_byte(0x800C4560);
    flags[0]=(uint32_t)inside;flags[1]=(uint32_t)zero_world;flags[2]=(uint32_t)zero_projected;
    STATE_BYTES(restore_body,47,&resident,sizeof resident);
    STATE_BYTES(restore_identity,48,identity,sizeof identity);
    STATE_WORDS(restore_resources,49,resources,8);
    STATE_WORDS(restore_flags,50,flags,3);
    unsigned frames[(OVERLAY_SIZE+MMX6_STATE_FRAME_BYTES-1)/MMX6_STATE_FRAME_BYTES];
    for(unsigned i=0;i<sizeof frames/sizeof frames[0];++i) {
        unsigned offset=i*MMX6_STATE_FRAME_BYTES,n=OVERLAY_SIZE-offset;
        if(n>MMX6_STATE_FRAME_BYTES)n=MMX6_STATE_FRAME_BYTES;
        frames[i]=mmx6_state_push(51u+i,overlay+offset,n,0);
    }
    inside=1;zero_world=zero_projected=0;
    project_player(&p1);code_bank(saved_overlay);
    for(unsigned i=0;i<7;++i)psx_mod_write_word(SCRATCH+offsets[i],saved_resources[i]);
    psx_mod_write_byte(0x800C4560,saved_palette_dirty);
    psx_mod_write_byte(PLAY+0x38,saved_play[0x38]);psx_mod_write_byte(PLAY+0x5E,saved_play[0x5E]);
    uint32_t result=guest(cpu,address,actor,cpu->gpr[5]);
    capture_player(&p1);capture(OVERLAY,saved_overlay,sizeof saved_overlay);
    for(unsigned i=0;i<7;++i)saved_resources[i]=psx_mod_read_word(SCRATCH+offsets[i]);
    saved_palette_dirty=psx_mod_read_byte(0x800C4560);
    project_player(&resident);code_bank(overlay);
    for(unsigned i=0;i<7;++i)psx_mod_write_word(SCRATCH+offsets[i],resources[i]);
    psx_mod_write_byte(0x800C4560,(uint8_t)resources[7]);
    psx_mod_write_byte(PLAY+0x38,identity[0]);psx_mod_write_byte(PLAY+0x5E,identity[1]);
    inside=(int)flags[0];zero_world=(int)flags[1];zero_projected=(int)flags[2];
    for(unsigned i=(unsigned)(sizeof frames/sizeof frames[0]);i;--i)mmx6_state_pop(frames[i-1]);
    STATE_POP(restore_flags);STATE_POP(restore_resources);STATE_POP(restore_identity);STATE_POP(restore_body);
    return result;
}
static int shared_effect_callback(CPUState *cpu,uint32_t address) {
    if(shared_fx_call || !enrolled || failed || cpu->gpr[31]!=0x80020438u)return 0;
    uint32_t actor=cpu->gpr[4];int slot=shared_effect_slot(actor);
    if(slot<0 || !psx_mod_read_byte(actor) || !shared_effect_owners[slot])return 0;
    unsigned type=psx_mod_read_byte(actor+1);
    /* Original80049100 reads canonical PLAYER for both birth and follow.
     * A Zero-owned dash must not initialize or chase the stationary primary.
     * Native4B3A0 Falcon flight18 likewise reads canonical PLAYER action23,
     * current body frame and SCRATCH+1C header1C before following the flyer. */
    if(!((address==0x80049410u && type==0) ||
         (address==0x80049100u && type==1) ||
         (address==0x80049478u && type==2) ||
         /* The first callback installs +30 and the owner's assembly/origin.
          * Waiting for an initialized surface subtype misses wall/contact
          * and impact effects, and can initialize them from the other hero. */
         (address==0x80049A14u && type==3 && shared_common_native()) ||
         (address==0x8004AE1Cu && type==17) || (address==0x801EE254u && type==26) ||
         (address==0x8004B3A0u && type==18)))return 0;
    uint32_t table=psx_mod_read_word(SCRATCH+0x88);
    if(table<0x80010000u || table>0x801FFF00u || (table&3u) ||
       psx_mod_read_word(table+type*4u)!=address)return 0;
    shared_fx_call=1;
    uint32_t context[4]={actor,(uint32_t)slot,shared_effect_owners[slot],(uint32_t)inside};
    STATE_WORDS(restore_context,57,context,4);
    uint32_t result;
    if(context[2]==(zero_projected?2u:1u))result=guest(cpu,address,actor,cpu->gpr[5]);
    else if(context[2]==2) {
        inside=1;enter_zero();
        result=guest(cpu,address,actor,cpu->gpr[5]);
        leave_zero_context(1);inside=(int)context[3];
    } else result=shared_effect_as_primary(cpu,address,actor);
    if(!psx_mod_read_byte(actor))shared_effect_owners[slot]=0;
    STATE_POP(restore_context);shared_fx_call=0;cpu->gpr[2]=result;return 1;
}
