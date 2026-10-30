/* Original Turtloid BIN9 EB2D4 rain-window predicate. EB304 loads the
 * resident hero's integer X; EB308/EB30C consume its load delay before this
 * guarded EB310 instruction loads the authored window's lower bound.
 * Supply a living guest's X only when it adds a contact with that window.
 * The original comparisons, rain flag, controller, clocks and exit still run
 * once. This is a register input change, never a second producer/world pass. */
static void weather_window_target(CPUState *cpu,uint32_t address) {
    if(address!=0x800EB310u || !ready || !enrolled || failed || inside || zero_world ||
       zero_projected || private_draw || scene_owner || scene_phase || pause_owner>=0 ||
       psx_mod_read_byte(PLAY)!=10 || psx_mod_read_byte(PLAY+1) ||
       psx_mod_read_byte(PLAY+12)!=6 || psx_mod_read_byte(PLAY+13) ||
       !intro_target_eligible(1))return;
    uint32_t actor=cpu->gpr[17],window=cpu->gpr[4];
    unsigned index=psx_mod_read_byte(0x800F6BA0u);
    if(actor<0x8008EF48u || actor>=0x80090C88u || (actor-0x8008EF48u)%0x9Cu ||
       !psx_mod_read_byte(actor) || psx_mod_read_byte(actor+1)!=14 ||
       index>6 || window!=0x800F5E90u+index*4 ||
       psx_mod_read_word(0x800EB304u)!=0x84C670AAu ||
       psx_mod_read_word(address)!=0x84830000u)return;
    int low=(int16_t)psx_mod_read_half(window),high=(int16_t)psx_mod_read_half(window+2);
    int primary=(int32_t)cpu->gpr[6],guest_x=(int16_t)(le32(p2.body+8)>>16);
    if(low>high || (primary>=low && primary<=high) || guest_x<low || guest_x>high)return;
    cpu->gpr[6]=(uint32_t)(int32_t)guest_x;
    psx_mod_counter_add("mmx6.coop.rain-guest-window",1);
}
