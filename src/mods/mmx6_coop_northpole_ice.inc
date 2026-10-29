/* SLUS-01395 ROCK_X6.BIN member4. The original ice-shaft controller and
 * child AI still run once; only their primary-only hero predicates expand.
 * Source: docs/COOP_PRIVATE_CHECKPOINT_SETUP.md. */
#define NORTHPOLE_GATE_FNV 0x4B3B5134u
#define NORTHPOLE_LIVE_FNV 0x3BC9F4C6u
static int northpole_ice_slot(uint32_t actor) {
    return actor>=0x800C1220u && actor<0x800C4560u &&
        !((actor-0x800C1220u)%0xA4u);
}
static int northpole_ice_source(void) {
    return psx_mod_read_word(SCRATCH+0x94)==0x800F6554u &&
        psx_mod_read_word(0x800F6570u)==0x800ECDE8u &&
        psx_mod_read_word(0x800F6BA0u)==0x800EBF18u &&
        psx_mod_read_word(0x800F6BF8u)==0x800ED150u &&
        checkpoint_hash(0x800ED150u,0x800ED1ECu)==NORTHPOLE_GATE_FNV &&
        checkpoint_hash(0x800EBF18u,0x800EC1DCu)==NORTHPOLE_LIVE_FNV;
}
static int northpole_ice_context(void) {
    /* Survivor/scene worlds already place their owner in PLAYER. */
    return !target_projection_call && ready && enrolled && !failed && !inside &&
        !zero_world && !zero_projected && !private_draw && !scene_owner && !scene_phase &&
        psx_mod_read_byte(PLAY)==10 && !psx_mod_read_byte(PLAY+1) &&
        psx_mod_read_byte(PLAY+12)==2 && !psx_mod_read_byte(PLAY+13) &&
        !psx_mod_read_byte(PLAY+0x10) && !psx_mod_read_byte(PLAY+0x1C) &&
        northpole_ice_source();
}
static int northpole_ice_parent(uint32_t actor) {
    if(!northpole_ice_slot(actor) || !psx_mod_read_byte(actor) ||
       psx_mod_read_byte(actor+1)!=7 || psx_mod_read_byte(actor+2) ||
       psx_mod_read_byte(actor+4)!=1)return 0;
    unsigned x=psx_mod_read_half(actor+10),y=psx_mod_read_half(actor+14);
    return (x==4992 || x==5344) && y==1376;
}
static int northpole_ice_admits(uint32_t actor,int x,int y) {
    return psx_mod_read_half(actor+10)<5312 ? x>=5137 && y>=1473 :
        x>=5345 && y>=1489;
}
static int northpole_ice_admission(CPUState *cpu,uint32_t address) {
    uint32_t actor=cpu->gpr[4];
    if(address!=0x800ED150u || !northpole_ice_context() ||
       !northpole_ice_parent(actor) || psx_mod_read_byte(actor+6)!=8 ||
       !intro_target_eligible(1))return 0;
    int x=(int16_t)psx_mod_read_half(PLAYER+10),y=(int16_t)psx_mod_read_half(PLAYER+14);
    int other_x=(int16_t)(le32(p2.body+8)>>16),other_y=(int16_t)(le32(p2.body+12)>>16);
    if(northpole_ice_admits(actor,x,y) || !northpole_ice_admits(actor,other_x,other_y))return 0;
    uint32_t original[2]={(uint16_t)x,(uint16_t)y};
    STATE_WORDS(restore_target,71,original,2);
    target_projection_call=1;
    psx_mod_write_half(PLAYER+10,(uint16_t)other_x);
    psx_mod_write_half(PLAYER+14,(uint16_t)other_y);
    uint32_t result=guest(cpu,address,actor,cpu->gpr[5]);
    psx_mod_write_half(PLAYER+10,(uint16_t)original[0]);
    psx_mod_write_half(PLAYER+14,(uint16_t)original[1]);
    target_projection_call=0;STATE_POP(restore_target);
    cpu->gpr[2]=result;return 1;
}
static int northpole_ice_child(uint32_t actor) {
    if(!northpole_ice_slot(actor) || !psx_mod_read_byte(actor) ||
       psx_mod_read_byte(actor+1)!=7 || psx_mod_read_byte(actor+2)!=12 ||
       psx_mod_read_byte(actor+4)!=1 || psx_mod_read_byte(actor+7)>=6 ||
       psx_mod_read_word(actor+0x68)!=actor+0x80u ||
       psx_mod_read_word(actor+0x80)!=0x18180000u)return 0;
    uint32_t parent=psx_mod_read_word(actor+0x7C);
    unsigned phase=psx_mod_read_byte(actor+6);
    return northpole_ice_parent(parent) && psx_mod_read_byte(parent+6)==9 &&
        phase<8 && phase!=4 && phase!=5;
}
static int northpole_ice_contact_gate(uint32_t actor,unsigned seat) {
    unsigned e5=seat?p2.body[0xE5]:psx_mod_read_byte(PLAYER+0xE5);
    int x=seat?(int16_t)(le32(p2.body+8)>>16):(int16_t)psx_mod_read_half(PLAYER+10);
    int distance=x-(int16_t)psx_mod_read_half(actor+10);
    return !e5 && distance>-48 && distance<48;
}
static void northpole_ice_private_tail(CPUState *cpu,uint32_t actor,SolidContact *contact) {
    /* Source EC100..EC1C0. Top/side support alone never retires the block.
     * A native underside contact during falling phase6 also requires the
     * copied contacting body's actual terrain ground bit. */
    if(!(contact->sides&4u) || psx_mod_read_byte(actor+6)!=6)return;
    uint8_t copy[0x154];capture(PLAYER,copy,sizeof copy);project(0x800F76ECu,copy,sizeof copy);
    guest(cpu,0x8002F288u,0x800F76ECu,0);
    if(!(psx_mod_read_byte(0x800F775Cu)&8u))return;
    uint32_t a2=cpu->gpr[6];STATE_WORDS(restore_a2,72,&a2,1);
    cpu->gpr[6]=actor;guest(cpu,0x800477E4u,3,0x800F6B8Cu);cpu->gpr[6]=a2;
    STATE_POP(restore_a2);
    uint32_t parent=psx_mod_read_word(actor+0x7C),column=psx_mod_read_byte(actor+7);
    psx_mod_write_byte(parent+7,(uint8_t)(psx_mod_read_byte(parent+7)-1u));
    psx_mod_write_byte(parent+0x86u+column,(uint8_t)(psx_mod_read_byte(parent+0x86u+column)-1u));
    psx_mod_write_byte(actor+4,4);
}
static int northpole_ice_live(CPUState *cpu,uint32_t address) {
    uint32_t actor=cpu->gpr[4];
    if(address!=0x800EBF18u || !northpole_ice_context() ||
       !northpole_ice_child(actor) || !intro_target_eligible(1))return 0;
    unsigned primary_contact=northpole_ice_contact_gate(actor,0);
    uint32_t context[2]={actor,primary_contact};STATE_WORDS(restore_context,73,context,2);
    target_projection_call=1;
    /* Keep original animation, motion, attacks, shared collisions and AI in
     * their canonical context. Replaying them as the guest would change the
     * resident attack-pool owner and advance this shared actor twice. */
    uint32_t result=guest(cpu,address,actor,cpu->gpr[5]);
    STATE_WORDS(restore_result,74,&result,1);
    if(!primary_contact && intro_target_eligible(1) && northpole_ice_child(actor) &&
       !northpole_ice_contact_gate(actor,0) && northpole_ice_contact_gate(actor,1)) {
        uint8_t body[sizeof p2.body],ride=psx_mod_read_byte(0x800CD340u);
        capture(PLAYER,body,sizeof body);STATE_BYTES(restore_body,75,body,sizeof body);
        STATE_BYTES(restore_ride,76,&ride,1);
        project(PLAYER,p2.body,sizeof p2.body);psx_mod_write_byte(0x800CD340u,0);
        inside=1;
        SolidContact *contact=solid_contact(actor);
        solid_as_zero(cpu,0x80031DA8u,actor,contact);
        northpole_ice_private_tail(cpu,actor,contact);
        capture(PLAYER,p2.body,sizeof p2.body);
        project(PLAYER,body,sizeof body);psx_mod_write_byte(0x800CD340u,ride);
        inside=0;STATE_POP(restore_ride);STATE_POP(restore_body);
    }
    STATE_POP(restore_result);STATE_POP(restore_context);target_projection_call=0;
    cpu->gpr[2]=result;return 1;
}
