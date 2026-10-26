#ifndef MMX6_COOP_SESSION_SDK_FIXTURE_H
#define MMX6_COOP_SESSION_SDK_FIXTURE_H
#include <stdint.h>
typedef struct {
    uint32_t guest_used,dma_used,packet_arenas,bank_bytes,bank_count,function_replacements,layout_cookie;
} Mmx6SessionResources;
uint8_t *mmx6_test_session_pointer(uint32_t address);
Mmx6SessionResources mmx6_test_session_resources(void);
int mmx6_test_session_reset(void);
void mmx6_test_session_peripheral_probe(const char *name);
#endif
