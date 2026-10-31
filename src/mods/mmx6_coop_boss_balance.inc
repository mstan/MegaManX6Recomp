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
    uint32_t origin,vulnerable_table;
    uint8_t kind,remainder,recognized;
    uint8_t clocks[2],cookies[2],timer_offset,timer_half,hit_owner,hit_melee;
} BossBalanceState;
static BossBalanceState boss_balance[BOSS_BALANCE_SLOTS];
static unsigned boss_balance_enabled,boss_balance_independent,boss_balance_allocate_call;
static uint32_t boss_balance_pending_actor;

static int boss_balance_slot(uint32_t actor) {
    if(actor<BOSS_BALANCE_POOL ||
       actor>=BOSS_BALANCE_POOL+BOSS_BALANCE_SLOTS*BOSS_BALANCE_STRIDE ||
       (actor-BOSS_BALANCE_POOL)%BOSS_BALANCE_STRIDE)return -1;
    return (int)((actor-BOSS_BALANCE_POOL)/BOSS_BALANCE_STRIDE);
}
/* The existing31474 replacement runs once per native boss AI update. */
static BossBalanceState *boss_balance_actor(uint32_t actor) {
    int slot=boss_balance_slot(actor);
    if(!boss_balance_enabled || slot<0 || !psx_mod_read_byte(actor) ||
       psx_mod_read_byte(actor+4)!=1 || !(psx_mod_read_byte(actor+0x5C)&127))return NULL;
    BossBalanceState *s=&boss_balance[slot];
    unsigned kind=psx_mod_read_byte(actor+1);uint32_t origin=psx_mod_read_word(actor+0x10);
    if(s->kind!=kind || s->origin!=origin) {
        memset(s,0,sizeof *s);s->kind=(uint8_t)kind;s->origin=origin;
    }
    if(psx_mod_read_word(PLAY+0x20)==actor && psx_mod_read_byte(PLAY+0x24))s->recognized=1;
    return s->recognized?s:NULL;
}
static unsigned boss_balance_native_clock(uint32_t actor,const BossBalanceState *s) {
    if(!s->timer_offset)return 0;
    return s->timer_half?psx_mod_read_half(actor+s->timer_offset):psx_mod_read_byte(actor+s->timer_offset);
}
static void boss_balance_write_clock(uint32_t actor,const BossBalanceState *s,unsigned ticks) {
    if(s->timer_half)psx_mod_write_half(actor+s->timer_offset,(uint16_t)ticks);
    else psx_mod_write_byte(actor+s->timer_offset,(uint8_t)ticks);
}
static uint32_t boss_balance_scan(CPUState *cpu,uint32_t address,uint32_t actor,
                                  unsigned seat,BossBalanceState *s) {
    if(!s || !boss_balance_independent)return guest(cpu,address,actor,cpu->gpr[5]);
    if(s->clocks[seat]) {
        psx_mod_counter_add("mmx6.coop.boss-own-cooldown-rejected",1);return 0;
    }
    uint8_t token=psx_mod_read_byte(actor+0x65);
    uint32_t table=psx_mod_read_word(actor+0x58);
    unsigned ticks=boss_balance_native_clock(actor,s);
    /* Only our one-tick ordinary expiry window may expose the ready seat.
     * Native scripted/weakness protection (10000 and its40-tick tail) stays
     * native. The original AI still owns its one expiry/CLUT cleanup pass. */
    unsigned projected=s->timer_offset && s->vulnerable_table &&
        table==0x8007433Cu && ticks==1;
    if(projected) {
        psx_mod_write_word(actor+0x58,s->vulnerable_table);
        boss_balance_write_clock(actor,s,0);
    }
    psx_mod_write_byte(actor+0x65,s->cookies[seat]);
    uint32_t result=guest(cpu,address,actor,cpu->gpr[5]);
    s->cookies[seat]=psx_mod_read_byte(actor+0x65);
    psx_mod_write_byte(actor+0x65,token);
    if(projected && boss_balance_pending_actor!=actor) {
        psx_mod_write_word(actor+0x58,table);boss_balance_write_clock(actor,s,ticks);
    } else if(projected)psx_mod_counter_add("mmx6.coop.boss-ready-partner-table",1);
    return result;
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
    BossBalanceState *state=boss_balance_actor(actor);if(!state)return;
    unsigned zero=psx_mod_read_byte(PLAYER+2)==1;
    unsigned total=amount*(zero?4u:5u)+state->remainder;
    state->remainder=(uint8_t)(total%10u);
    cpu->gpr[5]=total/10u;
    if(boss_balance_independent) {
        unsigned seat=(unsigned)!!zero_projected;state->hit_owner=(uint8_t)seat;
        uint32_t table=psx_mod_read_word(actor+0x58),shot=cpu->gpr[7];
        if(table>=0x80010000u && table<0x80200000u && !(table&1u) && table!=0x8007433Cu)
            state->vulnerable_table=table;
        unsigned type=(shot>=0x800950A0u && shot<0x800964A0u && !((shot-0x800950A0u)%0xA0u))?psx_mod_read_byte(shot+1):255;
        state->hit_melee=(uint8_t)(zero && type>=24 && type<=28);
        if(state->clocks[seat^1u])psx_mod_counter_add("mmx6.coop.boss-hit-during-partner-cooldown",1);
        psx_mod_counter_add(seat?"mmx6.coop.boss-private-seat2-accepted":"mmx6.coop.boss-private-seat1-accepted",1);
    }
    boss_balance_pending_actor=actor;
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
    if(actor==boss_balance_pending_actor)boss_balance_pending_actor=0;
    if(slot>=0)memset(&boss_balance[slot],0,sizeof boss_balance[slot]);
    cpu->gpr[2]=actor;return 1;
}

/* Original post-hit stores only. The same physical overlay address may hold
 * unrelated code in another area; require the exact preceding six words too.
 * Pending accepted damage and the native rejection table exclude ordinary AI
 * counters. Large native scripted/weakness clocks retain their original value.
 */
typedef struct { uint32_t address,words[7]; } BossCooldownSite;
static const BossCooldownSite boss_cooldown_sites[]={
    {0x800F1A6Cu,{0x10400006u,0xA6030042u,0x3C031F80u,0x8C63004Cu,0x24020002u,0x0803C767u,0xA062008Bu}}, /* original member2 */
    {0x800F1A80u,{0x0803C767u,0xA062008Bu,0x3C031F80u,0x8C63004Cu,0x2402003Cu,0x0803C767u,0xA062008Bu}}, /* original member2 */
    {0x800F1A84u,{0xA062008Bu,0x3C031F80u,0x8C63004Cu,0x2402003Cu,0x0803C767u,0xA062008Bu,0xA062008Bu}}, /* original member2 */
    {0x800F1B84u,{0xA2110005u,0xA2020006u,0x3C031F80u,0x8C63004Cu,0x2402001Eu,0x0803C767u,0xA062008Bu}}, /* original member2 */
    {0x800EFE24u,{0x0044102Au,0x10400005u,0x2CA20008u,0x14400006u,0x24020002u,0x0803BFAAu,0xA2020086u}}, /* original member3 */
    {0x800F1808u,{0x2C420002u,0x10400003u,0xAE030058u,0x0803C602u,0x24020002u,0x2402001Eu,0xA6020088u}}, /* original member4 */
    {0x800EEEE8u,{0x0803BC31u,0xA0510086u,0x3C031F80u,0x8C63004Cu,0x2402001Eu,0x0803BC31u,0xA0620086u}}, /* original member5 */
    {0x800EF05Cu,{0x34638000u,0xA6030042u,0x3C041F80u,0x8C84004Cu,0x2402001Eu,0x0803BC31u,0xA0820086u}}, /* original member5 */
    {0x800EF060u,{0xA6030042u,0x3C041F80u,0x8C84004Cu,0x2402001Eu,0x0803BC31u,0xA0820086u,0xA0620086u}}, /* original member5 */
    {0x800EA7E0u,{0xAE020058u,0x2483FFE7u,0x2C630002u,0x10600002u,0x2402001Eu,0x24020002u,0xA6020084u}}, /* original member7 */
    {0x800F2208u,{0x2C420002u,0x10400003u,0xAE030058u,0x0803C882u,0x24020002u,0x2402001Eu,0xA6020088u}}, /* original member7 */
    {0x800F2F9Cu,{0xAE020058u,0x2463FFE7u,0x2C630002u,0x10600002u,0x2402001Eu,0x24020002u,0xA6020084u}}, /* original member7 */
    {0x800F0510u,{0x34638000u,0x10400003u,0xA6030042u,0x0803C144u,0x24020002u,0x2402001Eu,0xA6020080u}}, /* original member8 */
    {0x800F057Cu,{0x2402000Au,0xA6030080u,0xA2020005u,0x0803C175u,0xA2000006u,0x0803C175u,0xA6020080u}}, /* original member8 */
    {0x800F0A40u,{0xAE020054u,0x02002021u,0x0C00C51Du,0x00000000u,0x0803C291u,0x00408821u,0xA2020084u}}, /* original member9 */
    {0x800F0B20u,{0x12220009u,0x2622FFE7u,0x2C420002u,0x14400002u,0x24020002u,0x2402001Eu,0xA2020084u}}, /* original member9 */
    {0x800F498Cu,{0x2C420002u,0x10400003u,0xAE030058u,0x0803D263u,0x24020002u,0x2402001Eu,0xA6020088u}}, /* original member10 */
    {0x800F5ED4u,{0x18800076u,0x2402007Fu,0x10820074u,0x3C028007u,0x2442433Cu,0x2403001Eu,0xA6030084u}}, /* original member11 */
    {0x800ED020u,{0x2C420002u,0x10400003u,0x00808821u,0x0803B408u,0x24020002u,0x2402001Eu,0xA6020086u}}, /* original member15 */
    {0x800F0058u,{0x2C420002u,0x10400003u,0xAE230058u,0x0803C016u,0x2402000Au,0x2402001Eu,0xA6220084u}}, /* original member15 */
};
static void boss_balance_shared_cooldown(CPUState *cpu,uint32_t address) {
    if(!boss_balance_enabled || !boss_balance_pending_actor || !ready ||
       !enrolled || failed || private_draw || psx_mod_local_view_scope() ||
       psx_mod_read_byte(PLAY)!=10)return;
    for(unsigned i=0;i<sizeof boss_cooldown_sites/sizeof boss_cooldown_sites[0];++i) {
        const BossCooldownSite *site=&boss_cooldown_sites[i];
        if(site->address!=address)continue;
        unsigned matched=1;
        for(unsigned j=0;j<7;++j)
            if(psx_mod_read_word(address-24u+j*4u)!=site->words[j])matched=0;
        if(!matched)continue;
        uint32_t instruction=site->words[6];
        uint32_t actor=cpu->gpr[(instruction>>21)&31u];
        int slot=boss_balance_slot(actor);
        if(actor!=boss_balance_pending_actor || slot<0 ||
           !boss_balance[slot].recognized || psx_mod_read_byte(actor+4)!=1 ||
           psx_mod_read_word(actor+0x58)!=0x8007433Cu)return;
        unsigned source=(instruction>>16)&31u,ticks=cpu->gpr[source];
        boss_balance_pending_actor=0;
        if(ticks<2 || ticks>=255)return;
        unsigned effective=(ticks+1u)/2u;
        if(boss_balance_independent) {
            BossBalanceState *s=&boss_balance[slot];
            if(s->hit_melee && effective>4)effective=4;
            s->clocks[s->hit_owner]=(uint8_t)effective;
            s->timer_offset=(uint8_t)(instruction&0xFFFFu);
            s->timer_half=(uint8_t)((instruction>>26)==0x29u);
            unsigned next=s->clocks[0]<s->clocks[1]?s->clocks[0]:s->clocks[1];
            cpu->gpr[source]=next?next:1u;
            psx_mod_counter_add("mmx6.coop.boss-private-cooldown-installed",1);
            psx_mod_counter_add("mmx6.coop.boss-private-cooldown-effective",effective);
            psx_mod_counter_add(s->hit_owner?"mmx6.coop.boss-private-seat2-installed-ticks":"mmx6.coop.boss-private-seat1-installed-ticks",effective);
            return;
        }
        cpu->gpr[source]=effective;
        psx_mod_counter_add("mmx6.coop.shorter-shared-boss-cooldown",1);
        psx_mod_counter_add("mmx6.coop.boss-shared-cooldown-before",ticks);
        psx_mod_counter_add("mmx6.coop.boss-shared-cooldown-after",(ticks+1u)/2u);
        return;
    }
}
