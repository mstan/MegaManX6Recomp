/* Source-contract inputs only; no original code or native gameplay runs here. */
static void setup_recycle_departure_wait(CPUState *cpu) {
    setup_agreed(cpu,0);memcpy(test_ram,portal_source_ram,sizeof test_ram);
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+12,4);psx_mod_write_byte(PLAY+13,0);
    psx_mod_write_byte(PLAY+0x0F,0);psx_mod_write_byte(PLAY+0x10,2);psx_mod_write_byte(PLAY+0x1C,1);
    portal_test_body(0,1526,1595);portal_test_body(1,1506,1594);
    life.status[1]=MMX6_COOP_LEAVING;p2.body[5]=1;p2.body[6]=0;p2.body[0x67]=1;
    put32(p2.body+0x68,0);put32(p2.body+0x24,8u<<16);
    const uint32_t actor=0x8008EF48u;
    psx_mod_write_byte(actor,0x49);psx_mod_write_byte(actor+1,0x1C);psx_mod_write_byte(actor+2,1);
    psx_mod_write_byte(actor+4,1);psx_mod_write_byte(actor+5,2);psx_mod_write_byte(actor+6,1);
    psx_mod_write_word(actor+0x10,0x800F2B0Cu);
    psx_mod_write_word(actor+8,1552u<<16);psx_mod_write_word(actor+12,1584u<<16);
    psx_mod_write_word(actor+0x50,0x800F38BCu);psx_mod_write_word(actor+0x54,0x800F38C0u);
    psx_mod_write_word(actor+0x68,0x800F38B8u);psx_mod_write_half(actor+0x7C,28);
    psx_mod_write_half(actor+0x80,1526);psx_mod_write_half(actor+0x82,1526);
    stage_call=1;scene_owner=1;scene_phase=scene_call=inside=zero_world=zero_projected=private_draw=view_call=0;
    cpu->gpr[4]=actor;cpu->gpr[31]=0x800EC8ACu;
    CHECK(recycle_portal_source());
}
static void recycle_departure_native_exit_contract(uint32_t actor) {
    /* EC8F8..EC98C external contract: original counter/jitter prefix and
     * the final requested exit. This model does NOT emulate fade139F4. */
    uint16_t count=(uint16_t)(psx_mod_read_half(actor+0x7C)+1u);
    uint16_t right=(uint16_t)(psx_mod_read_half(actor+0x80)+1u);
    uint16_t left=(uint16_t)(psx_mod_read_half(actor+0x82)-1u);
    psx_mod_write_half(actor+0x7C,count);psx_mod_write_half(actor+0x80,right);psx_mod_write_half(actor+0x82,left);
    psx_mod_write_half(PLAYER+10,(psx_mod_read_word(0x80097420u)&1u)?left:right);
    if((int16_t)count>=29) {
        psx_mod_write_byte(PLAY+0x0F,psx_mod_read_byte(actor+2)|0x40u);
        psx_mod_write_byte(actor+6,psx_mod_read_byte(actor+6)+1u);
    }
}
static void recycle_departure_final_order(CPUState *cpu) {
    const uint32_t actor=0x8008EF48u;
    /* Baseline source contract commits while the voluntary beam is unfinished. */
    setup_recycle_departure_wait(cpu);recycle_departure_native_exit_contract(actor);
    CHECK(psx_mod_read_byte(PLAY+0x0F)==0x41 && psx_mod_read_byte(actor+6)==2 &&
        life.status[1]==MMX6_COOP_LEAVING && p2.body[4]==1 && le32(p2.body+12)==(1594u<<16));
    /* Earlier ordinary timer progress remains native; only its final call waits. */
    setup_recycle_departure_wait(cpu);psx_mod_write_half(actor+0x7C,27);
    CHECK(!recycle_portal_departure_wait(cpu,0x800EC8F8u));recycle_departure_native_exit_contract(actor);
    CHECK(psx_mod_read_half(actor+0x7C)==28 && !psx_mod_read_byte(PLAY+0x0F));
    memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;CPUState registers=*cpu;Mmx6CoopLifecycle lifecycle=life;
    for(unsigned i=0;i<5;++i)CHECK(recycle_portal_departure_wait(cpu,0x800EC8F8u) &&
        !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner) &&
        !memcmp(&registers,cpu,sizeof registers) && !memcmp(&lifecycle,&life,sizeof life) && !guest_calls);
    /* Inputs representing the existing original3674C animation phases are
     * supplied externally; the replacement never manufactures this progress. */
    p2.body[6]=1;CHECK(recycle_portal_departure_wait(cpu,0x800EC8F8u));
    p2.body[3]=0;p2.body[4]=3;mmx6_coop_teleport_done(&life);
    CHECK(life.status[1]==MMX6_COOP_ABSENT && !recycle_portal_departure_wait(cpu,0x800EC8F8u));
    partner=p2;recycle_departure_native_exit_contract(actor);
    CHECK(psx_mod_read_half(actor+0x7C)==29 && psx_mod_read_byte(PLAY+0x0F)==0x41 &&
        psx_mod_read_byte(actor+6)==2 && life.status[1]==MMX6_COOP_ABSENT && !memcmp(&partner,&p2,sizeof partner));
    for(unsigned bad=0;bad<25;++bad) {
        setup_recycle_departure_wait(cpu);uint32_t target=0x800EC8F8u;
        if(bad==0)target+=4;if(bad==1)cpu->gpr[31]+=4;if(bad==2)scene_owner=2;
        if(bad==3)scene_phase=1;if(bad==4)life.status[1]=MMX6_COOP_ALIVE;
        if(bad==5)life.status[1]=MMX6_COOP_ABSENT;if(bad==6)life.status[1]=MMX6_COOP_FALLEN;
        if(bad==7)life.status[0]=MMX6_COOP_DYING;if(bad==8)inside=1;if(bad==9)private_draw=1;
        if(bad==10)stage_call=0;if(bad==11)psx_mod_write_byte(PLAY+12,12);
        if(bad==12)psx_mod_write_byte(PLAY+0x0F,0x41);if(bad==13)psx_mod_write_byte(PLAY+0x10,0);
        if(bad==14)psx_mod_write_byte(actor+2,2);if(bad==15)psx_mod_write_byte(actor+6,2);
        if(bad==16)psx_mod_write_word(actor+0x10,0x800F2B14u);
        if(bad==17)psx_mod_write_half(actor+0x7C,29);if(bad==18)psx_mod_write_half(actor+10,1553);
        if(bad==19)psx_mod_write_word(actor+0x68,0);if(bad==20)psx_mod_write_byte(0x800EC8F8u,0);
        if(bad==21)p2.body[0x5C]=0x80;if(bad==22)p2.body[4]=2;
        if(bad==23)psx_mod_write_byte(PLAYER+0x5C,0);if(bad==24)cpu->gpr[4]=actor+4;
        memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;registers=*cpu;lifecycle=life;
        CHECK(!recycle_portal_departure_wait(cpu,target) && !memcmp(before_ram,test_ram,sizeof test_ram) &&
            !memcmp(&partner,&p2,sizeof partner) && !memcmp(&registers,cpu,sizeof registers) &&
            !memcmp(&lifecycle,&life,sizeof life) && !guest_calls);
    }
    stage_call=inside=private_draw=scene_owner=scene_phase=0;
}
