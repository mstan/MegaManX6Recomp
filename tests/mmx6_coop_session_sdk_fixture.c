/* Actual SDK arena ownership/reset and actual bank/packet registration code.
 * This follows the SDK's own test_mod_memory_snapshot.c inclusion pattern.
 * Strict typed peripheral callbacks close retained COFF links, without
 * relying on section GC/LTO to discard unrelated hardware routing. No
 * reset/allocator model is substituted. Private getters are fixture-only. */
#include "memory.c"
#include "mod_texture_banks.c"
#include "mod_function_replacements.c"
#include "mmx6_coop_session_sdk_fixture.h"
#include "mmx6_coop_session_peripherals.inc"
int g_psx_render_pass_active;
void gl_renderer_forget_texture_bank_range(uint16_t first,uint32_t count) {
    (void)first;(void)count; /* No renderer is created by this unit fixture. */
}
uint8_t *mmx6_test_session_pointer(uint32_t address) {
    uint32_t physical=address&0x1FFFFFFFu,offset;
    if(mod_memory_offset(physical,1,&offset))return mod_memory+offset;
    if(mod_gpu_dma_memory_offset(physical,1,&offset))return mod_gpu_dma_memory+offset;
    fprintf(stderr,"fixture: write/read outside actual allocated session arenas: %08X\n",address);
    abort();
}
Mmx6SessionResources mmx6_test_session_resources(void) {
    Mmx6SessionResources out={mod_memory_used,mod_gpu_dma_memory_used,arena_count,bank_bytes,0,replacement_count,
        psx_mod_memory_layout_cookie()};
    for(unsigned i=1;i<65536;++i)out.bank_count+=banks[i].pixels!=NULL;
    return out;
}
int mmx6_test_session_reset(void) {
    /* Exactly the SDK start_mod_session order after renderer teardown. */
    if(!mod_texture_banks_reset_session()||!psx_mod_memory_reset_session())return 0;
    /* mod_runtime_activate_plugins clears this actual table immediately
     * before invoking the newly committed activation callbacks. */
    psx_mod_clear_function_replacements();return 1;
}
