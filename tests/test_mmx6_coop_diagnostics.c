/* Exercise the real plugin's debug boundary against isolated guest memory.
 * No original game logic is simulated by this test. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mod_plugins.h"
#undef PSX_MOD_CONSTRUCTOR
#define PSX_MOD_CONSTRUCTOR(name) static void name(void)
#include "../src/mods/mmx6_coop_plugin.c"
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x); exit(1); } } while (0)
static uint8_t test_diagnostic[0x2000],test_ram[0x200000];
static int test_online;
#ifdef MMX6_COOP_MODERN_STATE
static int test_digest_registered;
int psx_mod_netplay_has_state_digest(void) { return test_digest_registered; }
#endif
static unsigned rejected,guest_calls,effect_writes;
static unsigned observed_reads,observed_consumer,sio_reads;
static int test_replay_supply;
static uint16_t observed_buttons;
static int observed_contaminated;
#ifdef MMX6_COOP_INPUT_TAINT_API
static uint32_t diagnostic_test_taint;
void psx_session_input_taint_add(uint32_t flags){diagnostic_test_taint|=flags;}
#endif
uint16_t mmx6_diagnostics_p2(unsigned consumer,uint16_t buttons,int contaminated) {
    ++observed_reads;observed_consumer=consumer;observed_buttons=buttons;observed_contaminated=contaminated;
    return test_replay_supply?0x1234:buttons;
}
static uint8_t *memory(uint32_t address) {
    if (address>=0x9F080000u && address<0x9F082000u) return test_diagnostic+address-0x9F080000u;
    return test_ram+(address&0x1FFFFFu);
}
uint8_t psx_mod_read_byte(uint32_t address) { return *memory(address); }
uint16_t psx_mod_read_half(uint32_t address) { return (uint16_t)(psx_mod_read_byte(address)|(psx_mod_read_byte(address+1)<<8)); }
uint32_t psx_mod_read_word(uint32_t address) { return (uint32_t)psx_mod_read_half(address)|((uint32_t)psx_mod_read_half(address+2)<<16); }
void psx_mod_write_byte(uint32_t address,uint8_t value) {
    if(address>=diagnostic+MMX6_FX_DIAG_HEADER && address<diagnostic+MMX6_FX_DIAG_END) {
        CHECK(psx_mod_read_word(diagnostic+0x88)&1);++effect_writes;
    }
    *memory(address)=value;
}
void psx_mod_write_half(uint32_t address,uint16_t value) { psx_mod_write_byte(address,(uint8_t)value);psx_mod_write_byte(address+1,(uint8_t)(value>>8)); }
void psx_mod_write_word(uint32_t address,uint32_t value) { for(unsigned i=0;i<4;++i)psx_mod_write_byte(address+i,(uint8_t)(value>>(i*8))); }
void psx_mod_write_code_word(uint32_t address,uint32_t value) { psx_mod_write_word(address,value); }
int psx_mod_netplay_is_active(void) { return test_online; }
void psx_mod_counter_add(const char *name,uint32_t count) { CHECK(strstr(name,"rejected"));rejected+=count; }
uint16_t sio_get_pad_buttons_slot(int slot) { CHECK(slot==1);++sio_reads;return 0xFFDF; }
void psx_dispatch_call(CPUState *cpu,uint32_t target,uint32_t ret) { (void)cpu;(void)target;(void)ret;++guest_calls; }

static void queue(unsigned command) {
    psx_mod_write_byte(diagnostic+0x50,(uint8_t)command);
    psx_mod_write_byte(diagnostic+0x51,17);
    psx_mod_write_half(diagnostic+0x52,0x90);
}
int main(void) {
    CPUState cpu; memset(&cpu,0,sizeof cpu);diagnostic=0x9F080000u;
    memset(&p2,0x32,sizeof p2);
    PlayerContext before=p2;
    test_online=1;
    for(unsigned command=1;command<=7;++command) {
        queue(command);diagnostic_setup(&cpu);
        CHECK(!memcmp(&before,&p2,sizeof p2));
        CHECK(!psx_mod_read_byte(diagnostic+0x50));
        CHECK(!guest_calls);
    }
#ifdef MMX6_COOP_INPUT_TAINT_API
    CHECK(!diagnostic_test_taint); /* Rejected online operations do not taint. */
#endif
    psx_mod_write_byte(diagnostic+0x30,1);
    psx_mod_write_half(diagnostic+0x34,0xBFFF);
    CHECK(p2_input(MMX6_INPUT_CONTROLLER_PLAYER)==0x20); /* Native P2 Right, never the queued Jump. */
    CHECK(observed_reads==1 && observed_consumer==MMX6_INPUT_CONTROLLER_PLAYER &&
          observed_buttons==0x20 && !observed_contaminated);
    CHECK(!psx_mod_read_byte(diagnostic+0x30));CHECK(rejected==8);
    test_online=0;
    queue(1);diagnostic_setup(&cpu);
    psx_mod_write_byte(diagnostic+0x30,1);
#ifdef PSX_NO_DEBUG_TOOLS
    CHECK(p2.body[0x5C]==before.body[0x5C]);
    CHECK(p2_input(MMX6_INPUT_CONTROLLER_BLOCKED)==0x20);CHECK(rejected==10);
    CHECK(!observed_contaminated && observed_buttons==0x20);
#else
    CHECK(p2.body[0x5C]==17);
    CHECK(p2_input(MMX6_INPUT_CONTROLLER_BLOCKED)==0x4000);CHECK(rejected==8);
    CHECK(observed_contaminated && observed_buttons==0x4000);
#endif
    CHECK(observed_reads==2 && observed_consumer==MMX6_INPUT_CONTROLLER_BLOCKED);
    /* The accepted debug override is intentionally persistent. Clear it before
     * separately checking the ordinary sampler/explicit-return wiring. */
    psx_mod_write_byte(diagnostic+0x30,0);
    CHECK(sio_reads==2);test_replay_supply=1;
    CHECK(p2_input(MMX6_INPUT_INTERACTION)==0x1234);
    CHECK(sio_reads==3 && observed_reads==3 && observed_buttons==0x20 && !observed_contaminated);
    test_replay_supply=0;
    /* Padding and purely presentational cache growth must not change the
     * observation; owned combat/lifecycle mutations must change it. */
    uint32_t original=diagnostic_host_digest();
    ++bank_count;CHECK(diagnostic_host_digest()==original);
    ++p2.shots[5];CHECK(diagnostic_host_digest()!=original);--p2.shots[5];
    ++life.select_frames;CHECK(diagnostic_host_digest()!=original);--life.select_frames;
    ++life.rejoin_pending;CHECK(diagnostic_host_digest()!=original);--life.rejoin_pending;
    CHECK(diagnostic_host_digest()==original);
    ready=enrolled=1;psx_mod_write_byte(PLAY,10);
    /* Resident/native pools deliberately differ: publication owns P2 host
     * bytes even while PLAYER belongs to P1. Canaries bound its new writes. */
    memset(test_diagnostic+0x1958,0xA5,0x2000-0x1958);
    for(unsigned i=0;i<sizeof p2.trails;++i)p2.trails[i]=(uint8_t)(i*7+3);
    for(unsigned i=0;i<sizeof p2.effects;++i)p2.effects[i]=(uint8_t)(i*11+9);
    memset(memory(0x800972F8),0xE1,sizeof p2.trails);
    memset(memory(0x800911A8),0xE2,sizeof p2.effects);
    PlayerContext published=p2;
    diagnostics(0xFFFF);
    CHECK(psx_mod_read_word(diagnostic+0x80)==1);
    CHECK(psx_mod_read_word(diagnostic+0x84)==0x1958);
    CHECK(psx_mod_read_word(diagnostic+0x88)==frame_count*2 && !(frame_count*2&1));
    CHECK(psx_mod_read_byte(diagnostic+0x8C)==1 && psx_mod_read_byte(diagnostic+0x8D)==1);
    CHECK(psx_mod_read_byte(diagnostic+0x90)==10);
    CHECK(psx_mod_read_word(diagnostic+0x94)==diagnostic_host_digest());
    CHECK(psx_mod_read_word(diagnostic+0x98)==1);
    CHECK(effect_writes==MMX6_FX_DIAG_BYTES);
    CHECK(psx_mod_read_word(diagnostic+MMX6_FX_DIAG_HEADER)==MMX6_FX_DIAG_MAGIC);
    CHECK(psx_mod_read_word(diagnostic+MMX6_FX_DIAG_HEADER+4)==1);
    CHECK(psx_mod_read_word(diagnostic+MMX6_FX_DIAG_HEADER+8)==0x220);
    CHECK(psx_mod_read_word(diagnostic+MMX6_FX_DIAG_HEADER+12)==frame_count);
    CHECK(!memcmp(test_diagnostic+MMX6_FX_DIAG_TRAILS,p2.trails,sizeof p2.trails));
    CHECK(!memcmp(test_diagnostic+MMX6_FX_DIAG_ATTACHED,p2.effects,sizeof p2.effects));
    CHECK(!memcmp(&published,&p2,sizeof p2)); /* Observation is read-only. */
    for(unsigned i=0x1958;i<MMX6_FX_DIAG_HEADER;++i)CHECK(test_diagnostic[i]==0xA5);
    for(unsigned i=MMX6_FX_DIAG_END;i<0x2000;++i)CHECK(test_diagnostic[i]==0xA5);
    /* All bytes, including hidden/unallocated stale native fields, are copied;
     * the observer decides whether they are eligible source-bound evidence. */
    p2.trails[0x50]^=0x80;p2.effects[0x42]^=0x40;
    diagnostics(0xFFFF);
    CHECK(test_diagnostic[MMX6_FX_DIAG_TRAILS+0x50]==p2.trails[0x50]);
    CHECK(test_diagnostic[MMX6_FX_DIAG_ATTACHED+0x42]==p2.effects[0x42]);
    CHECK(psx_mod_read_word(diagnostic+MMX6_FX_DIAG_HEADER+12)==frame_count);
#ifdef MMX6_COOP_MODERN_STATE
    CHECK(psx_mod_read_byte(diagnostic+0x9C)==0);
    test_digest_registered=1;diagnostics(0xFFFF);
    CHECK(psx_mod_read_byte(diagnostic+0x9C)==1);
#endif
    /* Every known accepted fixture command marks provenance before mutation;
     * unknown commands do not invent a fixture acceptance. */
#ifdef MMX6_COOP_INPUT_TAINT_API
    for(unsigned command=1;command<=7;++command){
        diagnostic_test_taint=0;queue(command);diagnostic_setup(&cpu);
#ifdef PSX_NO_DEBUG_TOOLS
        CHECK(!diagnostic_test_taint);
#else
        CHECK(diagnostic_test_taint==PSX_INPUT_TAINT_GAME_MAILBOX);
#endif
    }
    diagnostic_test_taint=0;queue(9);diagnostic_setup(&cpu);CHECK(!diagnostic_test_taint);
#endif
    puts("co-op debug isolation and diagnostic publication PASS");return 0;
}
