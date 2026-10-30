/* Optional X4-style effective double HP, in X6's original native HP units.
 * Original 318F4 is after token/defense/part/difficulty admission and before
 * SUBU at318FC, HP store31908 and lethal result/feedback selection31920.
 * Changing only accepted A1 damage preserves native weakness/result identity
 * and avoids losing overkill strength by observing already-clipped HP.
 * Shared tenths retain alternating X(5/10) and Zero(4/10) fractional damage.
 */
enum { BOSS_BALANCE_SLOTS=48, BOSS_BALANCE_POOL=0x8008EF48u,
       BOSS_BALANCE_STRIDE=0x9Cu };
typedef struct {
    uint32_t origin;
    uint8_t kind,remainder,recognized;
} BossBalanceState;
static BossBalanceState boss_balance[BOSS_BALANCE_SLOTS];
static unsigned boss_balance_enabled,boss_balance_allocate_call;

static int boss_balance_slot(uint32_t actor) {
    if(actor<BOSS_BALANCE_POOL ||
       actor>=BOSS_BALANCE_POOL+BOSS_BALANCE_SLOTS*BOSS_BALANCE_STRIDE ||
       (actor-BOSS_BALANCE_POOL)%BOSS_BALANCE_STRIDE)return -1;
    return (int)((actor-BOSS_BALANCE_POOL)/BOSS_BALANCE_STRIDE);
}
static void boss_balance_damage(CPUState *cpu,uint32_t address) {
    (void)address;
    if(!boss_balance_enabled || !ready || !enrolled || failed || private_draw ||
       psx_mod_local_view_scope() || psx_mod_read_byte(PLAY)!=10)return;
    uint32_t actor=cpu->gpr[8]; /* Original T0, not A0/A3's attack context. */
    int slot=boss_balance_slot(actor);
    if(slot<0 || !psx_mod_read_byte(actor) ||
       psx_mod_read_byte(actor+4)!=1)return;
    unsigned hp=psx_mod_read_byte(actor+0x5C),amount=cpu->gpr[5];
    if(!hp || hp>127 || !amount || amount>127)return;
    BossBalanceState *state=&boss_balance[slot];
    unsigned kind=psx_mod_read_byte(actor+1);
    uint32_t origin=psx_mod_read_word(actor+0x10);
    if(state->kind!=kind || state->origin!=origin) {
        memset(state,0,sizeof *state);state->kind=(uint8_t)kind;state->origin=origin;
    }
    /* Admit the real native metered boss. Once identified, its hidden-meter
     * attack phases keep the same budget; unrelated enemies never acquire it. */
    if(psx_mod_read_word(PLAY+0x20)==actor && psx_mod_read_byte(PLAY+0x24))
        state->recognized=1;
    if(!state->recognized)return;
    unsigned zero=psx_mod_read_byte(PLAYER+2)==1;
    unsigned total=amount*(zero?4u:5u)+state->remainder;
    state->remainder=(uint8_t)(total%10u);
    cpu->gpr[5]=total/10u;
    psx_mod_counter_add("mmx6.coop.boss-damage-before-scaling",amount);
    psx_mod_counter_add("mmx6.coop.boss-damage-after-scaling",total/10u);
    if(zero)psx_mod_counter_add("mmx6.coop.zero-boss-damage-before-scaling",amount);
}
static int boss_balance_allocate(CPUState *cpu,uint32_t address) {
    if(!boss_balance_enabled || boss_balance_allocate_call || private_draw ||
       psx_mod_local_view_scope())return 0;
    boss_balance_allocate_call=1;
    uint32_t actor=guest(cpu,address,cpu->gpr[4],cpu->gpr[5]);
    boss_balance_allocate_call=0;
    int slot=boss_balance_slot(actor);
    if(slot>=0)memset(&boss_balance[slot],0,sizeof boss_balance[slot]);
    cpu->gpr[2]=actor;return 1;
}
