/* Commander Yammark's real defeat script is a shared clear, not a temporary
 * door passenger trip. Original member3 800F553C calls 8003D308(20), after
 * 800EFBBC..800EFBF8 has committed the main boss's native lethal state.
 * Reward8004299C, never this plugin, publishes PLAY+0F bit10. */
enum { CLEAR_ADMITTED=1, CLEAR_PRELUDE=2, CLEAR_VICTORY=3 };

static void shared_clear_reset(void) {
    clear_phase=clear_members=clear_started=0;
}
static int shared_clear_living(unsigned seat) {
    const uint8_t *body=seat?p2.body:(zero_projected?p1.body:NULL);
    unsigned state=body?body[4]:psx_mod_read_byte(PLAYER+4);
    unsigned hp=body?body[0x5C]:psx_mod_read_byte(PLAYER+0x5C);
    return life.status[seat]==MMX6_COOP_ALIVE && state==1 && (hp&0x7Fu);
}
static int shared_clear_admit(CPUState *cpu,uint32_t address) {
    if(clear_phase)return 1;
    if(!ready || !enrolled || failed || scene_call || scene_owner ||
        address!=0x8003D308u || cpu->gpr[31]!=0x800F5544u || cpu->gpr[4]!=20 ||
        psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
        psx_mod_read_byte(PLAY+12)!=1 || psx_mod_read_byte(PLAY+13) ||
        !shared_clear_living(0) || !shared_clear_living(1))return 0;
    uint32_t boss=psx_mod_read_word(PLAY+0x20);
    if(boss<0x80010000u || boss>0x801FFF00u || (boss&3u) ||
        !psx_mod_read_byte(boss) || psx_mod_read_byte(boss+1)!=49 ||
        psx_mod_read_byte(boss+2) || psx_mod_read_byte(boss+4)!=2 ||
        psx_mod_read_byte(boss+0x5C) || psx_mod_read_word(boss+0x10)!=0x800F66C0u)return 0;
    clear_phase=CLEAR_ADMITTED;clear_members=3;clear_started=0;
    life.select_frames=0;
    independent_invalidate();
    return 1;
}
/* Original8001EA28 advances the fade only after its resident body is state3.
 * Let the last still-departing native body own that ONE world pass, then
 * return campaign/exit ownership to X. No body state or result flag is held
 * back or manufactured, and original8001E32C remains untouched. */
static int shared_clear_zero_world(void) {
    return clear_phase==CLEAR_VICTORY && (clear_members&2u) &&
        psx_mod_read_byte(PLAYER+4)==3 && p2.body[4]!=3;
}
static void shared_clear_tick(CPUState *cpu,unsigned resident) {
    if(!clear_phase)return;
    if(psx_mod_read_byte(PLAY)!=10) {shared_clear_reset();return;}
    /* The lethal world already ran both ordinary player passes before the
     * boss callback admitted this clear. Do not run the companion twice. */
    if(clear_phase==CLEAR_ADMITTED) {clear_phase=CLEAR_PRELUDE;return;}
    if(psx_mod_read_byte(PLAY+1))return;
    int prior_inside=inside;
    uint32_t context[2]={(uint32_t)prior_inside,resident};
    STATE_WORDS(restore_clear,43,context,2);
    inside=1;
    if(clear_phase==CLEAR_PRELUDE && (psx_mod_read_byte(PLAY+0x0F)&0x10u))
        clear_phase=CLEAR_VICTORY;
    if((clear_members&2u) && !resident && p2.body[4]!=3) {
        uint8_t input[6];capture(0x800C456C,input,sizeof input);
        STATE_BYTES(restore_clear_input,14,input,sizeof input);
        enter_zero();
        for(unsigned i=0;i<sizeof input;i+=2)psx_mod_write_half(0x800C456C+i,0);
        guest(cpu,0x8003CD44u,0,0);
        guest(cpu,0x80034DCCu,0,0);
        guest(cpu,0x8002012Cu,0,0);
        guest(cpu,0x8002F288u,PLAYER,0);
        guest(cpu,0x80020D74u,0,0);
        guest(cpu,0x80020DC8u,0,0);
        leave_zero();
        project(0x800C456C,input,sizeof input);STATE_POP(restore_clear_input);
    }
    /* Original body actions choose WHEN clear admission is safe: an airborne
     * finisher must first recover/land, then8003A628 calls8003B870 once. Do not
     * force the constructor early or assign victory/outgoing/visibility. */
    if(clear_phase==CLEAR_VICTORY) {
        if(psx_mod_read_byte(PLAYER+4)==1 && psx_mod_read_byte(PLAYER+5)==25)clear_started|=1;
        if(p2.body[4]==1 && p2.body[5]==25)clear_started|=2;
    }
    inside=prior_inside;STATE_POP(restore_clear);
}
