/* Original SLUS_013.95 dd4bea: 1EC40 decodes3CD44 then menu34830.
 * MENU CF810 states0/1/2 dispatch34874/348B0/3499C. Both native menu
 * simulations share one fade/world clock; rendering is a separate sandbox. */
enum { PERSONAL_MENU=0x800CF810u,PERSONAL_PAD=0x800C456Cu,
       PERSONAL_WEAPON=0x800E4430u,PERSONAL_START=0x0800,PERSONAL_SELECT=0x0100 };
static void personal_reset(void) {
    memset(personal_menu,0,sizeof personal_menu);
    memset(personal_previous,0,sizeof personal_previous);
    personal_active=personal_initialized=personal_eligible=0;
    personal_pass=personal_seat=personal_rendering=0;
}
static void personal_read(unsigned seat) {
    capture(PERSONAL_MENU,personal_menu[seat].native,sizeof personal_menu[seat].native);
    personal_menu[seat].original_weapon=psx_mod_read_byte(PERSONAL_WEAPON);
}
static void personal_write(unsigned seat) {
    project(PERSONAL_MENU,personal_menu[seat].native,sizeof personal_menu[seat].native);
    psx_mod_write_byte(PERSONAL_WEAPON,personal_menu[seat].original_weapon);
}
static int personal_modal(void) {
    return personal_menu[0].native[4]==1 &&
        (personal_menu[0].native[5]==5 || personal_menu[0].native[5]==6);
}
static int personal_busy(unsigned seat) {
    const uint8_t *m=personal_menu[seat].native;
    return m[4]==1 && (m[5]==3 || m[5]==4);
}
static int personal_tank_request(unsigned seat,uint16_t edge) {
    const uint8_t *m=personal_menu[seat].native;
    return (personal_eligible&(1u<<seat)) && m[4]==1 && m[5]==1 &&
        m[0x14]>=10 && m[0x14]<=12 && (edge&~PERSONAL_START)==0x40;
}
static int personal_finish(CPUState *cpu) { cpu->gpr[2]=0;return 1; }
static int personal_shared_effect(CPUState *cpu,uint32_t address) {
    if(!personal_pass || personal_seat!=1)return 0;
    switch(address) {
    case 0x800139A0u:case 0x800139F4u:case 0x8001750Cu:
    case 0x80020C40u:case 0x80025FB0u:return personal_finish(cpu);
    default:return 0; /* In particular22928 is an actor-owned palette load. */
    }
}
static int personal_draw_filter(CPUState *cpu,uint32_t address) {
    (void)address;
    int modal=!personal_seat && psx_mod_read_byte(PERSONAL_MENU+4)==1 &&
        (psx_mod_read_byte(PERSONAL_MENU+5)==5 || psx_mod_read_byte(PERSONAL_MENU+5)==6);
    return personal_pass && !personal_rendering && !modal?personal_finish(cpu):0;
}
static int personal_dead_commit(CPUState *cpu,uint32_t address) {
    (void)address;
    if(!personal_pass || (personal_eligible&(1u<<personal_seat)))return 0;
    /* Original34CD0 animation/equipment installation is never a corpse tick. */
    if(!personal_seat) {
        guest(cpu,0x80020C40u,0,0);guest(cpu,0x800139A0u,0x20,0);
    }
    psx_mod_write_byte(PERSONAL_MENU+5,3);
    return personal_finish(cpu);
}
static uint32_t personal_step(CPUState *cpu,uint32_t address,unsigned seat,
                              uint16_t input,uint16_t old) {
    personal_write(seat);
    uint16_t edge=(uint16_t)(input&~old);
    if(seat) {
        input&=(uint16_t)~PERSONAL_SELECT;old&=(uint16_t)~PERSONAL_SELECT;
        edge&=(uint16_t)~PERSONAL_SELECT;
        /* X6 cursor15 is Parts, unlike X4. Native337EC cursor16 sets+38
         * for a campaign escape; cursor13/14 are Escape/Options. */
        unsigned cursor=personal_menu[seat].native[0x14];
        if(personal_menu[seat].native[5]==2 &&
           (cursor==13 || cursor==14 || cursor==16))edge&=(uint16_t)~0x40u;
    }
    uint8_t major=psx_mod_read_byte(PLAY),minor=psx_mod_read_byte(PLAY+1);
    if(seat) {
        enter_zero();
        psx_mod_write_word(SCRATCH+0xA8,menu_memory+MENU_PORTRAIT_COLORS);
    }
    psx_mod_write_half(PERSONAL_PAD,input);psx_mod_write_half(PERSONAL_PAD+2,old);
    psx_mod_write_half(PERSONAL_PAD+4,edge);
    personal_pass=1;personal_seat=seat;
    guest(cpu,0x8003CD44u,0,0);
    uint32_t result=guest(cpu,address,PERSONAL_MENU,0);
    personal_pass=0;
    if(seat) {
        uint8_t dirty=psx_mod_read_byte(0x800C4560u)&1u;
        leave_zero_context(1);
        /* P2's original346EC may finish before P1; it cannot independently
         * resume the one shared world or initiate a campaign transition. */
        psx_mod_write_byte(PLAY,major);psx_mod_write_byte(PLAY+1,minor);
        psx_mod_write_byte(0x800C4560u,(uint8_t)(psx_mod_read_byte(0x800C4560u)|dirty));
    }
    personal_read(seat);
    personal_seat=0;
    return result;
}
static void personal_begin(uint16_t raw) {
    personal_reset();personal_active=1;
    for(unsigned seat=0;seat<2;++seat)
        if(life.status[seat]==MMX6_COOP_ALIVE)personal_eligible|=1u<<seat;
    personal_read(0);
    personal_previous[0]=psx_mod_read_half(PERSONAL_PAD);
    personal_previous[1]=(uint16_t)((raw<<8)|(raw>>8));
    pause_owner=0; /* Canonical menu/fade authority, independently of opener. */
}
static uint32_t personal_tick(CPUState *cpu,uint16_t raw) {
    uint8_t pad[6];capture(PERSONAL_PAD,pad,sizeof pad);
    uint16_t input[2]={psx_mod_read_half(PERSONAL_PAD),(uint16_t)((raw<<8)|(raw>>8))};
    uint16_t old[2]={personal_previous[0],personal_previous[1]};
    uint16_t edge[2]={(uint16_t)(input[0]&~old[0]),(uint16_t)(input[1]&~old[1])};
    memcpy(personal_previous,input,sizeof input);previous_input=input[1];
    uint32_t result=0;
    if(!personal_initialized) {
        result=personal_step(cpu,0x80034830u,0,0,0);
        if(personal_menu[0].native[4]==0 && personal_menu[0].native[5]==2) {
            personal_menu_prepare_assets(cpu);
            memset(&personal_menu[1],0,sizeof personal_menu[1]);
            uint8_t fading=psx_mod_read_byte(0x80097424u);
            psx_mod_write_byte(0x80097424u,0);
            personal_step(cpu,0x80032DF0u,1,0,0);
            psx_mod_write_byte(0x80097424u,fading);
            personal_initialized=1;
        }
    } else {
        int busy=personal_busy(0)||personal_busy(1);
        int tank[2]={personal_tank_request(0,edge[0]),personal_tank_request(1,edge[1])};
        int interactive=personal_menu[0].native[4]==1 && personal_menu[1].native[4]==1;
        unsigned resume=0;
        for(unsigned seat=0;seat<2;++seat)
            resume|=(personal_eligible&(1u<<seat)) && (edge[seat]&PERSONAL_START);
        if(interactive && !busy && !tank[0] && !tank[1] && resume) {
            for(unsigned seat=0;seat<2;++seat) {
                personal_menu[seat].native[4]=2;personal_menu[seat].native[5]=0;
            }
        }
        unsigned first=personal_busy(1)||(tank[1]&&!tank[0])?1:0;
        for(unsigned turn=0;turn<2;++turn) {
            unsigned seat=first^turn;
            if(personal_modal() && seat && !personal_busy(seat))continue;
            uint16_t mask=PERSONAL_START;
            const uint8_t *m=personal_menu[seat].native;
            if(busy && (tank[seat] || (!seat && m[5]==2 && (m[0x14]==13 || m[0x14]==16))))mask|=0x40;
            int allowed=(personal_eligible&(1u<<seat)) && !personal_modal();
            result=personal_step(cpu,0x80034830u,seat,
                allowed?(uint16_t)(input[seat]&~mask):0,
                allowed?(uint16_t)(old[seat]&~mask):0);
            if(!seat && personal_menu[0].native[4]==2 && personal_menu[1].native[4]==1) {
                personal_menu[1].native[4]=2;personal_menu[1].native[5]=0;
            }
            busy|=personal_busy(seat);
        }
    }
    personal_write(0);project(PERSONAL_PAD,pad,sizeof pad);
    if(psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1)!=2)personal_reset();
    return result;
}
static void personal_modal_prepare(CPUState *cpu,uint16_t raw) {
    uint8_t pad[6];capture(PERSONAL_PAD,pad,sizeof pad);
    uint16_t second=(uint16_t)((raw<<8)|(raw>>8));
    if(personal_busy(1)) {
        inside=1;personal_step(cpu,0x80034830u,1,0,0);inside=0;
    }
    personal_previous[0]=psx_mod_read_half(PERSONAL_PAD);
    personal_previous[1]=previous_input=second;
    personal_write(0);project(PERSONAL_PAD,pad,sizeof pad);
}
static void personal_after_stage(CPUState *cpu,unsigned phase,uint16_t raw) {
    if(personal_active) {
        personal_read(0);
        if(psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1)!=2)personal_reset();
    } else if(phase!=2 && psx_mod_read_byte(PLAY)==10 &&
              psx_mod_read_byte(PLAY+1)==2 && pause_owner>=0) {
        if(zero_menu_loaded)menu_vram(cpu,0);
        personal_begin(raw);
    }
}
static int personal_resuming_world(void) {
    return personal_active && personal_initialized &&
        personal_menu[0].native[4]==2 && personal_menu[0].native[5]>=3;
}
static int personal_menus_active(void) {
    return personal_active && personal_initialized && !personal_modal() && !personal_resuming_world();
}
static unsigned personal_menu_fade(uint32_t buffer) {
    if(!personal_active || !personal_initialized)return 0;
    unsigned fading=psx_mod_read_byte(0x80097424u);
    if(!fading && personal_menu[0].native[4]==2 && personal_menu[0].native[5]<=2)return 255;
    if(!fading)return 0;
    /* Original13530 at135CC/135DC selects C4838[parity], then1362C..34
     * publishes the current shared shade. Replay that displayed TILE value,
     * not its next counter C8860, and never advance the fade task here. */
    unsigned index=buffer==0x800C4668u;
    return psx_mod_read_byte(0x800C483Cu+index*16u);
}
static int personal_menu_draw(CPUState *cpu,unsigned seat) {
    if(seat>1 || !personal_menus_active() || zero_projected)return 0;
    if(seat) {
        enter_zero();
        psx_mod_write_word(SCRATCH+0xA8,menu_memory+MENU_PORTRAIT_COLORS);
    }
    personal_write(seat);personal_menu_assets(cpu,seat);
    personal_pass=personal_rendering=1;personal_seat=seat;
    guest(cpu,0x80026028u,PERSONAL_MENU,0);
    personal_pass=personal_seat=personal_rendering=0;
    if(seat)leave_zero();
    personal_write(0);return 1;
}
