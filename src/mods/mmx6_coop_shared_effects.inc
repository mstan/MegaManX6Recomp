/* Original shared pool80091298..80093C98, allocator8002C398 and deferred
 * dispatch80020430 (return80020438). Giga creates decimal types17/26.
 * Type26's selected801EE254 is a Zero entry but an unrelated X continuation.
 * Preserve the native selector, loop, order and shared palette/packet state;
 * run the selected callback in its allocating player's actual context. */
static int shared_effect_slot(uint32_t actor) {
    if(actor<0x80091298u || actor>=0x80093C98u || (actor-0x80091298u)%0x70u)return -1;
    return (int)((actor-0x80091298u)/0x70u);
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
    if(!((address==0x8004AE1Cu && type==17) || (address==0x801EE254u && type==26)))return 0;
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
