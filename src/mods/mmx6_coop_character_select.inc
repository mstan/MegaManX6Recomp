/* Original BIN16 selector, twice: native campaign/P1, then opposite-family P2.
 * Availability stays in native progress. Menu-local IDs remain native0..5;
 * Black Zero is a second appearance of5, never an invented actor/form6. */
typedef struct {
    uint8_t roster[7],count,seat,active,valid,forms[2],black;
    uint16_t previous[2];
} CharacterSelection;
static CharacterSelection character_selection;
static int character_select_call;
static uint16_t p2_input(unsigned consumer);
enum { CHARACTER_LIST=0x800F1CB0u,CHARACTER_COUNT=0x800F1CEBu,
       CHARACTER_PAD=0x800C456Cu,CHARACTER_UPDATE=0x800ECE48u };

static unsigned selected_zero_black(void) {
    if(!(psx_mod_read_byte(PLAY+0x5F)&0x20u))return 0;
    if(character_selection.active) {
        unsigned cursor=psx_mod_read_byte(PLAY+0x30);
        if(cursor<character_selection.count &&
           psx_mod_read_byte(CHARACTER_LIST+cursor)==5)
            return cursor && psx_mod_read_byte(CHARACTER_LIST+cursor-1)==5;
    }
    return character_selection.valid?character_selection.black:1u;
}
static unsigned selected_partner_x(void) {
    return character_selection.valid && character_selection.forms[1]<5?
        character_selection.forms[1]:partner_x_armor;
}
static void character_native_roster(void) {
    unsigned count=psx_mod_read_byte(CHARACTER_COUNT);
    if(!count || count>6)return;
    memset(character_selection.roster,0,sizeof character_selection.roster);
    capture(CHARACTER_LIST,character_selection.roster,count);
    unsigned zero=0;
    for(unsigned i=0;i<count;++i)zero|=character_selection.roster[i]==5;
    if(!zero)character_selection.roster[count++]=5;
    if(psx_mod_read_byte(PLAY+0x5F)&0x20u) {
        unsigned at=0;while(at<count && character_selection.roster[at]!=5)++at;
        memmove(character_selection.roster+at+2,character_selection.roster+at+1,count-at-1);
        character_selection.roster[at+1]=5;++count;
    }
    character_selection.count=(uint8_t)count;
    project(CHARACTER_LIST,character_selection.roster,count);
    psx_mod_write_byte(CHARACTER_COUNT,(uint8_t)count);
}
static void character_filter_roster(unsigned reset_cursor) {
    uint8_t list[7]={0};unsigned count=0;
    for(unsigned i=0;i<character_selection.count;++i) {
        unsigned form=character_selection.roster[i];
        if(!character_selection.seat ||
           (form==5)!=(character_selection.forms[0]==5))list[count++]=(uint8_t)form;
    }
    if(!count)return;
    project(CHARACTER_LIST,list,sizeof list);
    psx_mod_write_byte(CHARACTER_COUNT,(uint8_t)count);
    unsigned cursor=psx_mod_read_byte(PLAY+0x30);
    if(reset_cursor || cursor>=count) {
        unsigned wanted=character_selection.forms[character_selection.seat];cursor=0;
        for(unsigned i=0;i<count;++i)if(list[i]==wanted) {cursor=i;break;}
        if(wanted==5 && character_selection.black && cursor+1<count && list[cursor+1]==5)++cursor;
    }
    psx_mod_write_byte(PLAY+0x30,(uint8_t)cursor);
    if(reset_cursor)psx_mod_write_byte(PLAY+0x28,list[cursor]);
}
static int character_select(CPUState *cpu,uint32_t address) {
    /* Other BINs reuse this address. Match this exact original dispatcher. */
    if(character_select_call || failed || cpu->gpr[4]!=PLAY ||
       psx_mod_local_view_scope() || psx_mod_read_word(address)!=0x27BDFFE8u ||
       psx_mod_read_word(address+0xC)!=0x80820002u ||
       psx_mod_read_word(address+0x10)!=0x24630F40u ||
       !character_selection.count)return 0;
    unsigned phase=psx_mod_read_byte(PLAY+2);
    uint16_t held[2]={psx_mod_read_half(CHARACTER_PAD),p2_input(MMX6_INPUT_STAGE)},edges[2];
    held[1]=(uint16_t)((held[1]<<8)|(held[1]>>8));
    for(unsigned seat=0;seat<2;++seat) {
        edges[seat]=(uint16_t)(held[seat]&~character_selection.previous[seat]);
        character_selection.previous[seat]=held[seat];
    }
    if(!character_selection.active && phase<=5) {
        character_selection.active=1;character_selection.seat=0;
        character_selection.forms[0]=psx_mod_read_byte(PLAY+0x5E);
        character_selection.forms[1]=character_selection.forms[0]==5?(uint8_t)partner_x_armor:5;
        if(!character_selection.valid)character_selection.black=(psx_mod_read_byte(PLAY+0x5F)&0x20u)!=0;
    }
    if(character_selection.active)character_filter_roster(0);
    uint16_t native_edges=psx_mod_read_half(CHARACTER_PAD+4);
    if(phase==5)psx_mod_write_half(CHARACTER_PAD+4,edges[character_selection.seat]);
    character_select_call=1;
    uint32_t result=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    character_select_call=0;
    psx_mod_write_half(CHARACTER_PAD+4,native_edges);
    unsigned next=psx_mod_read_byte(PLAY+2);
    if(phase==4)character_filter_roster(1);
    if(phase==5 && next==7) {
        unsigned form=psx_mod_read_byte(PLAY+0x5E);
        if(form==5)character_selection.black=(uint8_t)selected_zero_black();
        character_selection.forms[character_selection.seat]=(uint8_t)form;
        if(!character_selection.seat) {
            character_selection.seat=1;
            character_selection.forms[1]=form==5?(uint8_t)partner_x_armor:5;
            psx_mod_write_byte(PLAY+2,5);psx_mod_write_byte(PLAY+0x31,0);
            character_filter_roster(1);
        } else {
            character_selection.valid=1;character_selection.active=0;
            project(CHARACTER_LIST,character_selection.roster,sizeof character_selection.roster);
            psx_mod_write_byte(CHARACTER_COUNT,character_selection.count);
        }
        psx_mod_write_byte(PLAY+0x38,character_selection.forms[0]==5);
        psx_mod_write_byte(PLAY+0x5E,character_selection.forms[0]);
    } else if(phase==5 && next==9) {
        if(character_selection.seat) {
            character_selection.seat=0;psx_mod_write_byte(PLAY+2,5);
            psx_mod_write_byte(PLAY+0x31,0);psx_mod_write_byte(PLAY+0x32,0);
            character_filter_roster(1);
        } else {
            character_selection.active=0;
            project(CHARACTER_LIST,character_selection.roster,sizeof character_selection.roster);
            psx_mod_write_byte(CHARACTER_COUNT,character_selection.count);
        }
    }
    cpu->gpr[2]=result;return 1;
}
static void shared_portrait_character(CPUState *cpu,uint32_t address) {
    /* Native21AF0's -1 portrait-table entry selects the campaign hero.
     * A P2-owned shared dialogue runs inside the projected stage update,
     * but its resident portrait atlas still belongs to the original hero.
     * Keep its matching animation/face geometry. Personal menus select their
     * own actor normally. Change registers only, never shared PLAY fields. */
    if(failed || !enrolled || !zero_projected || !zero_world || personal_pass ||
       private_draw || saved_play[0x38]>1)return;
    if(address==0x80021B88u && psx_mod_read_word(address)==0x14400012u &&
       psx_mod_read_word(address-8)==0x80A20038u)
        cpu->gpr[2]=saved_play[0x38];
    else if(address==0x80021B98u && psx_mod_read_word(address)==0x14600003u &&
            psx_mod_read_word(address-8)==0x90A3005Eu)
        cpu->gpr[3]=saved_play[0x5E];
}
static void character_zero_variant(CPUState *cpu,uint32_t address) {
    /* Runs before the original ANDI. Change its register input only; the
     * persistent unlock byte and native capsule availability stay intact. */
    if(failed || psx_mod_read_word(address)!=0x30420020u)return;
    if(address>=OVERLAY && (psx_mod_read_word(OVERLAY)!=0x3Du ||
       psx_mod_read_word(address-8)!=0x9062005Fu))return;
    cpu->gpr[2]=(cpu->gpr[2]&~0x20u)|(selected_zero_black()?0x20u:0);
}
