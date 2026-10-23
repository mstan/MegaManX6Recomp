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
static unsigned rejected,guest_calls;
static uint8_t *memory(uint32_t address) {
    if (address>=0x9F080000u && address<0x9F082000u) return test_diagnostic+address-0x9F080000u;
    return test_ram+(address&0x1FFFFFu);
}
uint8_t psx_mod_read_byte(uint32_t address) { return *memory(address); }
uint16_t psx_mod_read_half(uint32_t address) { return (uint16_t)(psx_mod_read_byte(address)|(psx_mod_read_byte(address+1)<<8)); }
uint32_t psx_mod_read_word(uint32_t address) { return (uint32_t)psx_mod_read_half(address)|((uint32_t)psx_mod_read_half(address+2)<<16); }
void psx_mod_write_byte(uint32_t address,uint8_t value) { *memory(address)=value; }
void psx_mod_write_half(uint32_t address,uint16_t value) { psx_mod_write_byte(address,(uint8_t)value);psx_mod_write_byte(address+1,(uint8_t)(value>>8)); }
void psx_mod_write_word(uint32_t address,uint32_t value) { for(unsigned i=0;i<4;++i)psx_mod_write_byte(address+i,(uint8_t)(value>>(i*8))); }
void psx_mod_write_code_word(uint32_t address,uint32_t value) { psx_mod_write_word(address,value); }
int psx_mod_netplay_is_active(void) { return test_online; }
void psx_mod_counter_add(const char *name,uint32_t count) { CHECK(strstr(name,"rejected"));rejected+=count; }
uint16_t sio_get_pad_buttons_slot(int slot) { CHECK(slot==1);return 0xFFDF; }
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
    psx_mod_write_byte(diagnostic+0x30,1);
    psx_mod_write_half(diagnostic+0x34,0xBFFF);
    CHECK(p2_input()==0x20); /* Native P2 Right, never the queued Jump. */
    CHECK(!psx_mod_read_byte(diagnostic+0x30));CHECK(rejected==8);
    test_online=0;
    queue(1);diagnostic_setup(&cpu);
    psx_mod_write_byte(diagnostic+0x30,1);
#ifdef PSX_NO_DEBUG_TOOLS
    CHECK(p2.body[0x5C]==before.body[0x5C]);
    CHECK(p2_input()==0x20);CHECK(rejected==10);
#else
    CHECK(p2.body[0x5C]==17);
    CHECK(p2_input()==0x4000);CHECK(rejected==8);
#endif
    /* Padding and purely presentational cache growth must not change the
     * observation; owned combat/lifecycle mutations must change it. */
    uint32_t original=diagnostic_host_digest();
    ++bank_count;CHECK(diagnostic_host_digest()==original);
    ++p2.shots[5];CHECK(diagnostic_host_digest()!=original);--p2.shots[5];
    ++life.select_frames;CHECK(diagnostic_host_digest()!=original);--life.select_frames;
    ++life.rejoin_pending;CHECK(diagnostic_host_digest()!=original);--life.rejoin_pending;
    CHECK(diagnostic_host_digest()==original);
    ready=enrolled=1;psx_mod_write_byte(PLAY,10);
    diagnostics(0xFFFF);
    CHECK(psx_mod_read_word(diagnostic+0x80)==1);
    CHECK(psx_mod_read_word(diagnostic+0x84)==0x1958);
    CHECK(psx_mod_read_word(diagnostic+0x88)==frame_count*2 && !(frame_count*2&1));
    CHECK(psx_mod_read_byte(diagnostic+0x8C)==1 && psx_mod_read_byte(diagnostic+0x8D)==1);
    CHECK(psx_mod_read_byte(diagnostic+0x90)==10);
    CHECK(psx_mod_read_word(diagnostic+0x94)==diagnostic_host_digest());
    CHECK(psx_mod_read_word(diagnostic+0x98)==1);
    puts("co-op debug isolation and diagnostic publication PASS");return 0;
}
