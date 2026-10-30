/* Original member14 cat4/type23 refight portals2..9. The shared actor's
 * action runs once in its native admitted owner's context; no successful
 * predicate, scene result, checkpoint or boss activation is synthesized. */
static int refight_portal_actor(uint32_t actor) {
    if(actor<0x800C1220u || actor>=0x800C4560u || (actor-0x800C1220u)%0xA4u ||
       !(psx_mod_read_byte(actor)&1u) || psx_mod_read_byte(actor+1)!=23 ||
       psx_mod_read_byte(actor+4)!=1 || psx_mod_read_byte(actor+5) || psx_mod_read_byte(actor+6) ||
       psx_mod_read_word(actor+0x30)!=0x800ED7D0u ||
       psx_mod_read_word(actor+0x68)!=0x800ED7DCu)return 0;
    unsigned sub=psx_mod_read_byte(actor+2);if(sub<2 || sub>9)return 0;
    static const uint32_t coordinates[]={0x04E80760u,0x053806B0u,0x05880600u,0x05D806B0u,
        0x06280760u,0x067806B0u,0x06C80600u,0x071806B0u};
    uint32_t record=0x800ED040u+(sub-2u)*8u;
    unsigned flags=psx_mod_read_byte(record),category=psx_mod_read_byte(record+3);
    return psx_mod_read_word(actor+0x10)==record && flags<=1 && category==4 &&
        psx_mod_read_byte(record+1)==23 && psx_mod_read_byte(record+2)==sub &&
        psx_mod_read_word(record+4)==coordinates[sub-2] &&
        psx_mod_read_half(actor+10)==psx_mod_read_half(record+4) &&
        psx_mod_read_half(actor+14)==psx_mod_read_half(record+6) &&
        !psx_mod_read_byte(PLAY+0x2C+sub);
}
static int refight_portal_boundary(uint32_t actor) {
    return !scene_call && !inside && !zero_world && !zero_projected && !private_draw &&
        stage_call && ready && enrolled && !failed && !scene_owner && !scene_phase && pause_owner<0 &&
        psx_mod_read_byte(PLAY)==10 && !psx_mod_read_byte(PLAY+1) &&
        psx_mod_read_byte(PLAY+12)==12 && !psx_mod_read_byte(PLAY+13) &&
        !psx_mod_read_byte(PLAY+0x0F) && !psx_mod_read_byte(PLAY+0x10) && !psx_mod_read_byte(PLAY+0x1C) &&
        !psx_mod_read_byte(0x80097424u) && !psx_mod_read_byte(PLAYER+2) && p2.body[2]==1 &&
        refight_portal_actor(actor) && checkpoint_refight_source();
}
static int refight_portal_both_admission(CPUState *cpu,uint32_t address) {
    /* EC860 -> ECB9C -> ECAC8 -> EC8E8, then original2CB50 animation
     * and31DA8 body support. Gate only this phase0 admission leaf: skipping
     * EC860 also skips those required original outer passes. */
    if(address!=0x800EC8E8u || cpu->gpr[31]!=0x800ECAFCu || !both_doors ||
       life.status[0]!=MMX6_COOP_ALIVE || life.status[1]!=MMX6_COOP_ALIVE ||
       !refight_portal_boundary(cpu->gpr[4]))return 0;
    /* A living actor in a native hold still participates. Absent/fallen
     * actors retain their original primary/projected-survivor path. */
    if(!recycle_portal_eligible(0) || !recycle_portal_eligible(1)) {
        cpu->gpr[2]=0;return 1;
    }
    uint32_t actor=cpu->gpr[4],context[4]={address,actor,0,0};
    STATE_WORDS(restore_refight_both,77,context,4);scene_call=1;
    uint32_t primary=guest(cpu,0x800EC430u,actor,PLAYER);
    inside=1;enter_zero();
    uint32_t partner=guest(cpu,0x800EC430u,actor,PLAYER);
    leave_zero();inside=0;scene_call=0;STATE_POP(restore_refight_both);
    if(!!primary!=!!partner) {cpu->gpr[2]=0;return 1;}
    return 0; /* Neither keeps original idle; both keep primary precedence. */
}
static int refight_portal_contact(CPUState *cpu,uint32_t address) {
    if(address!=0x800EC860u || both_doors || !refight_portal_boundary(cpu->gpr[4]) ||
       !recycle_portal_eligible(0) || !recycle_portal_eligible(1))return 0;
    uint32_t actor=cpu->gpr[4],context[4]={address,actor,0,0};
    STATE_WORDS(restore_refight,77,context,4);scene_call=1;
    /* Either retains the established guest-owned native full callback. */
    if(guest(cpu,0x800EC430u,actor,PLAYER)) {
        scene_call=0;STATE_POP(restore_refight);return 0;
    }
    inside=1;enter_zero();
    uint32_t hit=guest(cpu,0x800EC430u,actor,PLAYER),result=0;
    context[2]=hit;STATE_UPDATE(restore_refight,context);
    if(hit) {
        result=guest(cpu,address,actor,cpu->gpr[5]);
        context[3]=result;STATE_UPDATE(restore_refight,context);
        /* EC914..934 snaps XY and calls3D308, which queues D0/D1/7A and
         * PLAY1C; it does NOT immediately change body action+5. EC95C waits
         * for the next original owning player update to earn action20.
         * ECB9C then calls31DA8 after the admission action: the pedestal
         * can resolve Y again. Retain that native result instead of requiring
         * EC934's intermediate Y after the complete callback has returned.
         * A pure overlap without these native admission writes owns nothing. */
        if(psx_mod_read_byte(actor+4)==1 && !psx_mod_read_byte(actor+5) &&
           psx_mod_read_byte(actor+6)==1 && psx_mod_read_byte(PLAYER+4)==1 &&
           psx_mod_read_byte(PLAYER+0xD0)==1 && psx_mod_read_byte(PLAYER+0xD1)==20 &&
           psx_mod_read_byte(PLAYER+0xD2)==psx_mod_read_byte(PLAYER+0x15) &&
           psx_mod_read_byte(PLAYER+0x7A)==1 && psx_mod_read_byte(PLAY+0x1C)==1 &&
           psx_mod_read_half(PLAYER+10)==psx_mod_read_half(actor+10))scene_begin(1,address);
        leave_zero_context(1);
    } else leave_zero();
    inside=0;scene_call=0;STATE_POP(restore_refight);
    if(!hit)return 0;
    cpu->gpr[2]=result;return 1;
}
