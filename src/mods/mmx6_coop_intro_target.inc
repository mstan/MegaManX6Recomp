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
    if (intro_target_call || !ready || !enrolled || failed || inside || zero_world || zero_projected ||
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
    intro_target_call=1;
    psx_mod_write_half(PLAYER+10,(uint16_t)z);
    cpu->gpr[2]=guest(cpu,address,actor,cpu->gpr[5]);
    psx_mod_write_half(PLAYER+10,(uint16_t)original_x);
    STATE_POP(restore_target_x);
    intro_target_call=0;
    return 1;
}
