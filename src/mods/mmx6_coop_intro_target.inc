/* SLUS-01395 v1.1 ROCK_X6.BIN member2, SHA256
 * d8bcf3aea6caf1dd4098b681ad912692835d726dfe16fddca779e82d894de607.
 * Only this action1 leaf reads PLAYER+0A; no hit/contact callbacks occur here.
 * Other facing/range decisions in this actor remain independent obligations. */
static const uint32_t intro_near_words[]={
    0x80820002u,0x00000000u,0x10400009u,0x3C028009u,0x8485000Au,
    0x844370AAu,0x00000000u,0x00A31023u,0x04400005u,0x28420070u,
    0x14400007u,0x24020002u,0x03E00008u,0x00000000u,0x00651023u,
    0x28420070u,0x1040FFFBu,0x24020002u,0xA0820005u,0x03E00008u,0x00000000u
};
static int intro_target_eligible(unsigned seat) {
    unsigned active=seat?p2.body[3]:psx_mod_read_byte(PLAYER+3);
    unsigned phase=seat?p2.body[4]:psx_mod_read_byte(PLAYER+4);
    unsigned action=seat?p2.body[5]:psx_mod_read_byte(PLAYER+5);
    unsigned hp=seat?p2.body[0x5C]:psx_mod_read_byte(PLAYER+0x5C);
    unsigned lock=seat?(p2.body[0x7A]|p2.body[0xD0]|p2.body[0xD4]):
        (psx_mod_read_byte(PLAYER+0x7A)|psx_mod_read_byte(PLAYER+0xD0)|psx_mod_read_byte(PLAYER+0xD4));
    return life.status[seat]==MMX6_COOP_ALIVE && active && phase==1 && action>=2 &&
        hp && !(hp&0x80) && !lock && !scene_passenger(seat);
}
static int intro_near_target(CPUState *cpu,uint32_t address) {
    /* Survivor Zero already occupies the native singleton. Never overlay that
     * world, a player/render projection, pause, vehicle or scene transport. */
    if (target_projection_call || !ready || !enrolled || failed || inside || zero_world || zero_projected ||
        address!=0x800EB14Cu || scene_owner || scene_phase || psx_mod_read_byte(PLAY)!=0x0A ||
        psx_mod_read_byte(PLAY+1) || psx_mod_read_byte(PLAY+12) || psx_mod_read_byte(PLAY+13) ||
        psx_mod_read_byte(PLAY+0x10) || psx_mod_read_byte(PLAY+0x1C)) return 0;
    uint32_t actor=cpu->gpr[4];
    if (actor<0x8008EF48u || actor>=0x80090C88u || (actor-0x8008EF48u)%0x9Cu ||
        !psx_mod_read_byte(actor) || psx_mod_read_byte(actor+1)!=1 ||
        psx_mod_read_byte(actor+2)!=1 || psx_mod_read_byte(actor+4)!=1 ||
        psx_mod_read_byte(actor+5)!=1 || psx_mod_read_word(0x8006DC6C)!=0x800FA424u ||
        psx_mod_read_word(0x800FA428)!=0x800EAFB0u ||
        psx_mod_read_word(0x800FAB4C)!=0x800EAC8Cu ||
        psx_mod_read_word(0x800FAB5C)!=0x800EB14Cu) return 0;
    for(unsigned i=0;i<sizeof intro_near_words/sizeof intro_near_words[0];++i)
        if(psx_mod_read_word(address+i*4)!=intro_near_words[i])return 0;
    if(!intro_target_eligible(1))return 0;
    int enemy=(int16_t)psx_mod_read_half(actor+10);
    int x=(int16_t)psx_mod_read_half(PLAYER+10),z=(int16_t)(le32(p2.body+8)>>16);
    int dx=enemy-x,dz=enemy-z;if(dx<0)dx=-dx;if(dz<0)dz=-dz;
    if(intro_target_eligible(0) && dx<=dz)return 0; /* Deterministic tie: P1. */
    uint32_t original_x=psx_mod_read_half(PLAYER+10);
    STATE_WORDS(restore_target_x,46,&original_x,1);
    target_projection_call=1;
    psx_mod_write_half(PLAYER+10,(uint16_t)z);
    cpu->gpr[2]=guest(cpu,address,actor,cpu->gpr[5]);
    psx_mod_write_half(PLAYER+10,(uint16_t)original_x);
    STATE_POP(restore_target_x);
    target_projection_call=0;
    return 1;
}

/* Original BIN15 (3a6fd0aa690e053909e5f5864d73450aee9449ec82ba81bdf057b0be7adaaed1)
 * EF0B0 allocates a type1F child from the native 93C98/A0 pool and stores its
 * parent at +7C. Its phase0 EF48C reads PLAYER.Y/X at EF504/508. At EF510 both
 * loads have completed: A0 is child.Y-player.Y, A1 is child.X, and A2 is
 * player.X. Supply only the selected target operands before the original
 * angle call and its X-delta delay instruction. Facing EF2E8 is independent;
 * native allocation, velocity, lifetime, damage and contact remain original. */
static const uint32_t sigma_special_target_words[]={
    0x3C028009u,0x9624000Eu,0x8625000Au,0x244270A0u,
    0xAE230068u,0x2484FFF1u,0xA624000Eu,0x00042400u,
    0x00042403u,0x8443000Eu,0x8446000Au,0x00832023u,
    0x0C0196DDu,0x00C52823u
};
static void sigma_special_target(CPUState *cpu,uint32_t address) {
    if(address!=0x800EF510u || !ready || !enrolled || failed || inside ||
       zero_world || zero_projected || private_draw || scene_owner || scene_phase ||
       pause_owner>=0 || psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
       psx_mod_read_byte(PLAY+12)!=12 || psx_mod_read_byte(PLAY+13)!=1 ||
       !intro_target_eligible(1) || cpu->gpr[2]!=PLAYER)return;
    uint32_t child=cpu->gpr[17];
    if(child<0x80093C98u || child>=0x80095098u || (child-0x80093C98u)%0xA0u ||
       !(psx_mod_read_byte(child)&1u) || psx_mod_read_byte(child+1)!=0x1Fu ||
       psx_mod_read_byte(child+6) || psx_mod_read_word(0x800F6768u)!=0x800EF48Cu)return;
    uint32_t parent=psx_mod_read_word(child+0x7Cu);
    if(parent<0x8008EF48u || parent>=0x80090C88u || (parent-0x8008EF48u)%0x9Cu ||
       !(psx_mod_read_byte(parent)&1u) || psx_mod_read_byte(parent+1)!=61 ||
       psx_mod_read_byte(parent+4)!=1 || !psx_mod_read_byte(parent+0x5Cu) ||
       (psx_mod_read_byte(parent+0x5Cu)&0x80u))return;
    for(unsigned i=0;i<sizeof sigma_special_target_words/sizeof sigma_special_target_words[0];++i)
        if(psx_mod_read_word(0x800EF4E0u+i*4)!=sigma_special_target_words[i])return;
    int x=(int16_t)psx_mod_read_half(child+10),y=(int16_t)psx_mod_read_half(child+14);
    int gx=(int16_t)(le32(p2.body+8)>>16),gy=(int16_t)(le32(p2.body+12)>>16);
    if(intro_target_eligible(0)) {
        int px=(int16_t)psx_mod_read_half(PLAYER+10),py=(int16_t)psx_mod_read_half(PLAYER+14);
        int64_t px_delta=px-x,py_delta=py-y,gx_delta=gx-x,gy_delta=gy-y;
        if(px_delta*px_delta+py_delta*py_delta<=gx_delta*gx_delta+gy_delta*gy_delta)return;
    }
    cpu->gpr[4]=(uint32_t)(int32_t)(y-gy);
    cpu->gpr[6]=(uint32_t)(int32_t)gx;
    psx_mod_counter_add("mmx6.coop.sigma-special-guest-target",1);
}
