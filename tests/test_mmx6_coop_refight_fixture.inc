/* External native input contracts only. The C test does not execute or
 * qualify original gravity, portal code, loader, boss or active gameplay. */
static void setup_refight_option(CPUState *cpu,int online,unsigned option) {
    setup_agreed(cpu,online);test_lab_option=option==16?"refight_distant_cp1":"refight_portal_cp1";checkpoint_reset();
    CHECK(checkpoint_lab_option==option && checkpoint_lab_index()==60 &&
        checkpoint_lab_nonce()==(option==16?0x4C524644u:0x4C524650u));
    CHECK(checkpoint_lab_boundary(cpu,6));mode9(cpu);checkpoint_native_entry(cpu,0x8001E1BCu);
    CHECK(checkpoint_pending.phase==2 && psx_mod_read_word(diagnostic+0xB8)==0x80072978u);
    memcpy(test_ram,refight_source_ram,sizeof test_ram);
    psx_mod_write_byte(PLAY,10);psx_mod_write_byte(PLAY+12,12);psx_mod_write_byte(PLAY+13,0);
    psx_mod_write_byte(PLAY+0x1D,1);psx_mod_write_word(PLAY+0x90,10);
    psx_mod_write_byte(PLAY+0x5B,32);psx_mod_write_byte(PLAY+0x5C,32);
    const uint32_t pools[][3]={{0x8008EF48u,0x80090C88u,0x9C},
        {0x80093C98u,0x80095098u,0xA0},{0x800950A0u,0x800964A0u,0xA0},{0x800C1220u,0x800C4560u,0xA4}};
    for(unsigned pool=0;pool<4;++pool)for(uint32_t a=pools[pool][0];a<pools[pool][1];a+=pools[pool][2])
        psx_mod_write_byte(a,0); /* External input state; no runtime actor is cleared. */
    portal_test_body(0,1712,1147);portal_test_body(1,1736,1146);
    for(unsigned i=0x5D;i<=0x5E;++i){psx_mod_write_byte(PLAYER+i,32);p2.body[i]=32;}
    psx_mod_write_word(0x800971F8u+8,1552u<<16);psx_mod_write_word(0x800971F8u+12,1024u<<16);
    const uint16_t bounds[]={1632,1472,1744,1024,1632,1472,1744,1024};
    for(unsigned i=0;i<8;++i)psx_mod_write_half(0x800971F8u+0x1C+i*2,bounds[i]);
    uint32_t meta,desc;
    CHECK(checkpoint_refight_source() && checkpoint_refight_assets(&meta,&desc) &&
          checkpoint_refight_ground(meta,desc) && checkpoint_refight_original_arrival(meta,desc));
}
static void setup_refight_prerequisite(CPUState *cpu,int online) {
    setup_refight_option(cpu,online,15);
}
static void refight_external_standing(void) {
    psx_mod_write_word(PLAYER+12,1243u<<16);psx_mod_write_word(PLAYER+0x1C,1243u<<16);
    put32(p2.body+12,1242u<<16);put32(p2.body+0x1C,1242u<<16);
    psx_mod_write_word(PLAY+0x90,12);
}
static void agreed_refight_prerequisite(CPUState *cpu) {
    for(int online=0;online<=1;++online)for(unsigned velocities=0;velocities<4;++velocities) {
        setup_refight_prerequisite(cpu,online);
        gate_enemy_test_vy(0,velocities&1?-0x80000:0);gate_enemy_test_vy(1,velocities&2?-0x80000:0);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;CPUState registers=*cpu;
        Mmx6CoopLifecycle lifecycle=life;
        const unsigned offsets[]={8,12,0x18,0x1C};
        for(unsigned i=0;i<4;++i) {
            uint32_t v=(i==0 || i==2?1852u:1241u)<<16;
            for(unsigned n=0;n<4;++n)before_ram[(PLAYER+offsets[i]+n)&0x1FFFFF]=(uint8_t)(v>>(n*8));
            put32(partner.body+offsets[i],v);
        }
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner) &&
            !memcmp(&registers,cpu,sizeof registers) && !memcmp(&lifecycle,&life,sizeof life));
        psx_mod_write_word(PLAY+0x90,12);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        refight_external_standing();psx_mod_write_word(PLAY+0x90,11);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        psx_mod_write_word(PLAY+0x90,12);memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner) &&
            psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
    }
    const uint32_t corrupt[]={0x800EC430u,0x800ED7DCu,0x8003D850u,0x8003AD18u,
        0x80097438u,0x80100000u,0x80120000u,0x80073D50u,0x8006DA2Cu};
    for(unsigned i=0;i<sizeof corrupt/sizeof corrupt[0];++i) {
        setup_refight_prerequisite(cpu,0);psx_mod_write_byte(corrupt[i],psx_mod_read_byte(corrupt[i])^1u);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
    }
    /* Original2C9D4 marks this secondary placement retired with0x80 after
     * the original six-reference mapcopy. This is not portal allocator bit0. */
    setup_refight_prerequisite(cpu,0);psx_mod_write_byte(0x800ED088u,0x80);
    CHECK(checkpoint_refight_source());
    CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
    /* First native mode10 can precede body/map initialization. Waiting must
     * preserve all guest state; once typed standing exists, the same bad
     * resource must be rejected before placement. */
    setup_refight_prerequisite(cpu,0);psx_mod_write_byte(PLAYER+4,0);
    psx_mod_write_byte(0x80100000u,psx_mod_read_byte(0x80100000u)^1u);
    memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext initializing_partner=p2;
    CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 &&
        !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&initializing_partner,&p2,sizeof p2));
    psx_mod_write_byte(PLAYER+4,1);memcpy(before_ram,test_ram,sizeof test_ram);
    CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase &&
        psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE &&
        !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&initializing_partner,&p2,sizeof p2));
    const uint8_t wrong_secondary_flags[]={1,0x81,0x40};
    for(unsigned i=0;i<sizeof wrong_secondary_flags;++i) {
        setup_refight_prerequisite(cpu,0);psx_mod_write_byte(0x800ED088u,wrong_secondary_flags[i]);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
    }
    for(unsigned bad=0;bad<9;++bad) {
        setup_refight_prerequisite(cpu,0);
        if(bad==0)p2.body[4]=2;if(bad==1)p2.body[0x5C]=0x80;if(bad==2)p2.body[0x70]=0;
        if(bad==3)gate_enemy_test_vy(0,-0x80001);if(bad==4)gate_enemy_test_vy(1,1);
        if(bad==5)psx_mod_write_byte(PLAY+0x2E,1);
        if(bad==6)psx_mod_write_word(PLAYER+0x20,1);
        if(bad==7)psx_mod_write_half(0x800971F8u+0x1C,1633);
        if(bad==8){psx_mod_write_byte(0x80093C98u,1);psx_mod_write_word(0x80093C98u+8,1852u<<16);psx_mod_write_word(0x80093C98u+12,1241u<<16);}
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
    }
    setup_refight_prerequisite(cpu,0);uint32_t meta,desc;CHECK(checkpoint_refight_assets(&meta,&desc));
    unsigned cell=psx_mod_read_byte(0x80097438u+(1248u>>8)*12+(1852u>>8));
    unsigned air=cell*512u+((1248u>>4)&15)*32+((1852u>>4)&15)*2;
    unsigned floor=cell*512u+((1264u>>4)&15)*32+((1852u>>4)&15)*2;
    uint16_t empty=psx_mod_read_half(meta+air),solid=psx_mod_read_half(meta+floor);
    psx_mod_write_half(meta+air,solid);CHECK(!checkpoint_refight_ground(meta,desc));
    psx_mod_write_half(meta+air,empty);psx_mod_write_half(meta+floor,empty);CHECK(!checkpoint_refight_ground(meta,desc));
    for(unsigned combo=0;combo<3;++combo) {
        setup_agreed(cpu,1);test_lab_option="refight_portal_cp1";
        if(combo<2)test_lab_hp_option[combo]="1";else test_lab_earned_option="all";
        checkpoint_reset();CHECK(failed);
        test_lab_hp_option[0]=test_lab_hp_option[1]="off";test_lab_earned_option="off";
    }
    test_lab_option="off";checkpoint_reset();CHECK(!checkpoint_lab_option);
}
/* Model inputs only: original gravity/portal/scene completion are NOT run
 * or credited by this C fixture. Preserve the entire primary byte-for-byte. */
static void agreed_refight_distant_prerequisite(CPUState *cpu) {
    for(int online=0;online<=1;++online)for(unsigned velocities=0;velocities<4;++velocities) {
        setup_refight_option(cpu,online,16);
        gate_enemy_test_vy(0,velocities&1?-0x80000:0);gate_enemy_test_vy(1,velocities&2?-0x80000:0);
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;CPUState registers=*cpu;
        Mmx6CoopLifecycle lifecycle=life;
        const unsigned offsets[]={8,12,0x18,0x1C};
        for(unsigned i=0;i<4;++i)put32(partner.body+offsets[i],(i==0 || i==2?1852u:1241u)<<16);
        CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3 && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner) &&
            !memcmp(&registers,cpu,sizeof registers) && !memcmp(&lifecycle,&life,sizeof life));
        CHECK(psx_mod_read_word(PLAYER+8)==(1712u<<16) && psx_mod_read_word(PLAYER+12)==(1147u<<16));
        psx_mod_write_word(PLAY+0x90,12);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        put32(p2.body+12,1242u<<16);put32(p2.body+0x1C,1242u<<16);
        psx_mod_write_word(PLAY+0x90,11);CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==3);
        psx_mod_write_word(PLAY+0x90,12);memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase && !guest_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner) &&
            psx_mod_read_byte(diagnostic+0xA8)==CHECKPOINT_COMPLETE && checkpoint_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
    }
    /* A different original primary arrival cannot authorize this named pose. */
    setup_refight_option(cpu,0,16);psx_mod_write_word(PLAYER+8,1713u<<16);
    memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
    CHECK(!checkpoint_stage_boundary(cpu) && checkpoint_pending.phase==2 && !guest_calls &&
        !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
    /* Refuse corrupted producer/source, original upper floor/air and bodies. */
    const uint32_t corrupt[]={0x800EC430u,0x8003D850u,0x80097438u,0x80100000u,0x80120000u,0x80073D50u};
    for(unsigned i=0;i<sizeof corrupt/sizeof corrupt[0];++i) {
        setup_refight_option(cpu,0,16);psx_mod_write_byte(corrupt[i],psx_mod_read_byte(corrupt[i])^1u);
        memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;
        CHECK(!checkpoint_stage_boundary(cpu) && !checkpoint_pending.phase &&
            psx_mod_read_byte(diagnostic+0xA9)==CHECKPOINT_SOURCE &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
    }
    setup_refight_option(cpu,0,16);uint32_t meta,desc;CHECK(checkpoint_refight_assets(&meta,&desc));
    CHECK(checkpoint_refight_distant_ground(meta,desc));
    unsigned cell=psx_mod_read_byte(0x80097438u+(1168u>>8)*12+(1712u>>8));
    unsigned floor=cell*512u+((1168u>>4)&15)*32+((1712u>>4)&15)*2;
    unsigned air=cell*512u+((1152u>>4)&15)*32+((1712u>>4)&15)*2;
    uint16_t empty=psx_mod_read_half(meta+air),solid=psx_mod_read_half(meta+floor);
    psx_mod_write_half(meta+floor,empty);CHECK(!checkpoint_refight_distant_ground(meta,desc));
    psx_mod_write_half(meta+floor,solid);psx_mod_write_half(meta+air,solid);
    CHECK(!checkpoint_refight_distant_ground(meta,desc));
    for(unsigned combo=0;combo<3;++combo) {
        setup_agreed(cpu,1);test_lab_option="refight_distant_cp1";
        if(combo<2)test_lab_hp_option[combo]="1";else test_lab_earned_option="all";
        checkpoint_reset();CHECK(failed);
        test_lab_hp_option[0]=test_lab_hp_option[1]="off";test_lab_earned_option="off";
    }
    test_lab_option="off";checkpoint_reset();CHECK(!checkpoint_lab_option);
}
static void setup_refight_hook(CPUState *cpu) {
    setup_refight_prerequisite(cpu,0);checkpoint_pending.phase=0;stage_call=1;scene_call=0;
    portal_test_body(0,1852,1243);portal_test_body(1,1888,1242);
    const uint32_t actor=0x800C1220u;
    psx_mod_write_byte(actor,0x41);psx_mod_write_byte(actor+1,23);psx_mod_write_byte(actor+2,2);
    psx_mod_write_byte(actor+4,1);psx_mod_write_word(actor+0x10,0x800ED040u);
    psx_mod_write_word(actor+8,1888u<<16);psx_mod_write_word(actor+12,1256u<<16);
    psx_mod_write_word(actor+0x30,0x800ED7D0u);psx_mod_write_word(actor+0x68,0x800ED7DCu);
    psx_mod_write_byte(0x800ED040u,1);cpu->gpr[4]=actor;
    both_doors=0;refight_stub=1;refight_probe_calls=refight_action_calls=refight_refuse=0;
    refight_post_solid=refight_admission_fault=0;
}
static void refight_owner_projection(CPUState *cpu) {
    setup_refight_hook(cpu);uint8_t body[sizeof p2.body];capture(PLAYER,body,sizeof body);
    CHECK(refight_portal_contact(cpu,0x800EC860u));
    CHECK(refight_probe_calls==2 && refight_action_calls==1 && scene_owner==2 && scene_phase==1 &&
        p2.body[5]==2 && p2.body[0xD0]==1 && p2.body[0xD1]==20 && p2.body[0x7A]==1 &&
        psx_mod_read_byte(PLAY+0x1C)==1 && le32(p2.body+8)==1888u<<16 && le32(p2.body+12)==1237u<<16 &&
        psx_mod_read_byte(0x800C1220u+6)==1 && !memcmp(body,memory(PLAYER),sizeof body) &&
        !inside && !scene_call && !zero_projected && !state_track.count);
    CHECK(psx_mod_read_byte(PLAY+0x66)==0x5A); /* Single native shared write retained. */
    /* rf7l retained native admission followed by the original pedestal solid
     * pass: Y1226+fraction is valid after EC934's intermediate Y1237. The
     * queued command is still pending; the original owner update consumes it. */
    for(unsigned fraction=0;fraction<2;++fraction) {
        setup_refight_hook(cpu);refight_post_solid=1;
        put32(p2.body+8,(1883u<<16)|(fraction?0x8000u:0));
        put32(p2.body+12,(1226u<<16)|(fraction?0xF600u:0));p2.body[5]=3;
        capture(PLAYER,body,sizeof body);
        CHECK(refight_portal_contact(cpu,0x800EC860u));
        CHECK(refight_probe_calls==2 && refight_action_calls==1 && scene_owner==2 && scene_phase==1 &&
            p2.body[5]==3 && p2.body[0xD0]==1 && p2.body[0xD1]==20 && p2.body[0x7A]==1 &&
            le32(p2.body+8)==((1888u<<16)|(fraction?0x8000u:0)) &&
            le32(p2.body+12)==((1226u<<16)|(fraction?0xF600u:0)) &&
            psx_mod_read_byte(0x800C1220u+6)==1 && !memcmp(body,memory(PLAYER),sizeof body) &&
            psx_mod_read_byte(PLAY+0x66)==0x5A && !inside && !scene_call && !zero_projected && !state_track.count);
    }
    /* Dropping the intermediate Y assumption does not admit a bare overlap
     * or incomplete native queue, actor progression, lock or integer X snap. */
    for(unsigned fault=1;fault<=7;++fault) {
        setup_refight_hook(cpu);refight_post_solid=1;refight_admission_fault=fault;
        CHECK(refight_portal_contact(cpu,0x800EC860u) && refight_action_calls==1 && !scene_owner);
    }
    setup_refight_hook(cpu);psx_mod_write_word(PLAYER+8,1888u<<16);psx_mod_write_word(PLAYER+12,1243u<<16);
    CHECK(!refight_portal_contact(cpu,0x800EC860u) && refight_probe_calls==1 && !refight_action_calls && !scene_owner);
    setup_refight_hook(cpu);put32(p2.body+8,1882u<<16);
    CHECK(!refight_portal_contact(cpu,0x800EC860u) && refight_probe_calls==2 && !refight_action_calls && !scene_owner);
    setup_refight_hook(cpu);p2.body[5]=6;
    CHECK(!refight_portal_contact(cpu,0x800EC860u) && refight_probe_calls==2 && !refight_action_calls && !scene_owner);
    setup_refight_hook(cpu);refight_refuse=1;
    CHECK(refight_portal_contact(cpu,0x800EC860u) && refight_action_calls==1 && !scene_owner && p2.body[5]==2);
    setup_refight_hook(cpu);psx_mod_write_byte(0x800ED043u,0x14);
    CHECK(!refight_portal_contact(cpu,0x800EC860u) && !refight_probe_calls && !refight_action_calls);
    /* Original pure contact drives optional Both. Exactly one participant
     * waits; neither and both fall through to the original callback. No
     * private/native body, actor, lock, progress or owner is written. */
    for(unsigned contacts=0;contacts<4;++contacts) {
        setup_refight_hook(cpu);both_doors=1;cpu->gpr[31]=0x800ECAFCu;
        psx_mod_write_word(PLAYER+8,((contacts&1)?1888u:1852u)<<16);
        put32(p2.body+8,((contacts&2)?1888u:1852u)<<16);
        CHECK(!refight_portal_contact(cpu,0x800EC860u) && !refight_probe_calls && !refight_action_calls); /* Original outer support must run. */
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
        CHECK(refight_portal_both_admission(cpu,0x800EC8E8u)==(contacts==1 || contacts==2));
        CHECK(refight_probe_calls==2 && !refight_action_calls && !scene_owner &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner) &&
            !inside && !scene_call && !zero_projected && !state_track.count);
    }
    /* A living participant in a temporary native hold cannot silently turn
     * Both into Either. Actual absent/fallen lifecycle states do not block
     * the existing original primary or projected-survivor callback. */
    for(unsigned seat=0;seat<2;++seat) {
        setup_refight_hook(cpu);both_doors=1;cpu->gpr[31]=0x800ECAFCu;
        if(seat)p2.body[0x7A]=1;else psx_mod_write_byte(PLAYER+0x7A,1);
        CHECK(!refight_portal_contact(cpu,0x800EC860u) && !refight_probe_calls && !refight_action_calls); /* Original outer support must run. */
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
        CHECK(refight_portal_both_admission(cpu,0x800EC8E8u) && !refight_probe_calls && !refight_action_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
        for(unsigned state=MMX6_COOP_ABSENT;state<=MMX6_COOP_FALLEN;++state) {
            setup_refight_hook(cpu);both_doors=1;cpu->gpr[31]=0x800ECAFCu;life.status[seat]=state;
            memcpy(before_ram,test_ram,sizeof test_ram);partner=p2;
            CHECK(!refight_portal_both_admission(cpu,0x800EC8E8u) && !refight_probe_calls && !refight_action_calls &&
                !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
        }
    }
    setup_refight_hook(cpu);const uint32_t icon=0x800C12C4u;
    psx_mod_write_byte(icon,0x51);psx_mod_write_byte(icon+1,24);psx_mod_write_byte(icon+4,1);
    psx_mod_write_word(icon+0x30,0x800ED7D0u);psx_mod_write_word(icon+0x50,0x800C1220u);
    psx_mod_write_word(icon+8,1888u<<16);psx_mod_write_word(icon+12,1228u<<16);
    CHECK(checkpoint_refight_clear());
    psx_mod_write_word(icon+0x68,0x800ED7DCu);CHECK(!checkpoint_refight_clear());
    /* Every admitted subtype is tied to its exact original record/XY, not
     * just a matching mutable actor and placement supplied by a caller. */
    for(unsigned sub=2;sub<=9;++sub) {
        setup_refight_hook(cpu);uint32_t actor=0x800C1220u,record=0x800ED040u+(sub-2)*8u;
        psx_mod_write_byte(actor+2,(uint8_t)sub);psx_mod_write_word(actor+0x10,record);
        psx_mod_write_half(actor+10,psx_mod_read_half(record+4));psx_mod_write_half(actor+14,psx_mod_read_half(record+6));
        CHECK(refight_portal_actor(actor));
        psx_mod_write_half(record+4,psx_mod_read_half(record+4)+1);psx_mod_write_half(actor+10,psx_mod_read_half(record+4));
        CHECK(!refight_portal_actor(actor));
    }
    for(unsigned bad=0;bad<8;++bad) {
        setup_refight_hook(cpu);
        if(bad==0)scene_owner=1;if(bad==1)inside=1;if(bad==2)stage_call=0;
        if(bad==3)psx_mod_write_byte(PLAY+12,4);if(bad==4)pause_owner=0;
        if(bad==5)psx_mod_write_byte(0x800C1220u+6,1);
        if(bad==6)psx_mod_write_byte(0x800EC430u,0);
        if(bad==7)life.status[1]=MMX6_COOP_FALLEN;
        memcpy(before_ram,test_ram,sizeof test_ram);PlayerContext partner=p2;
        CHECK(!refight_portal_contact(cpu,0x800EC860u) && !refight_probe_calls && !refight_action_calls &&
            !memcmp(before_ram,test_ram,sizeof test_ram) && !memcmp(&partner,&p2,sizeof partner));
    }
    refight_stub=0;stage_call=inside=scene_owner=scene_phase=0;pause_owner=-1;
}
