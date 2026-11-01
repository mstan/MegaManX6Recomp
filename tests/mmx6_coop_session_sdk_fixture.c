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
/* As in SDK test_mod_texture_banks.c, the fixture's output-only scope is
 * explicit. Normal activation runs outside it; packet allocation must refuse
 * inside it. This fixture does not instantiate the runtime callback scheduler. */
int psx_mod_host_output_scope(void) { return g_psx_render_pass_active; }
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
    /* Legacy callers retain their resources; title opt-in retires them. */
    uint32_t guest=mod_memory_used,dma=mod_gpu_dma_memory_used;
    uint32_t packets=arena_count,pixels=bank_bytes;
    if(!mod_texture_banks_begin_session(0)||!psx_mod_memory_begin_session(0) ||
       mod_memory_used!=guest || mod_gpu_dma_memory_used!=dma ||
       arena_count!=packets || bank_bytes!=pixels) abort();
    g_psx_render_pass_active=1;
    int banks_reset=mod_texture_banks_begin_session(1);
    int memory_reset=psx_mod_memory_begin_session(1);
    g_psx_render_pass_active=0;
    if(banks_reset || memory_reset || mod_memory_used!=guest ||
       mod_gpu_dma_memory_used!=dma || arena_count!=packets || bank_bytes!=pixels) abort();
    /* Exactly the SDK start_mod_session order after renderer teardown. */
    if(!mod_texture_banks_begin_session(1)||!psx_mod_memory_begin_session(1))return 0;
    /* mod_runtime_activate_plugins clears this actual table immediately
     * before invoking the newly committed activation callbacks. */
    psx_mod_clear_function_replacements();
    /* Exercise the linked scope contract against the actual SDK allocator.
     * A denied output-only call must not reserve DMA space or an arena. */
    uint32_t used=mod_gpu_dma_memory_used,count=arena_count;
    g_psx_render_pass_active=1;
    uint32_t address=psx_mod_alloc_texture_packet_memory(80,16);
    g_psx_render_pass_active=0;
    if(address || mod_gpu_dma_memory_used!=used || arena_count!=count) {
        fprintf(stderr,"fixture: output-only packet allocation mutated session resources\n");
        abort();
    }
    return 1;
}
