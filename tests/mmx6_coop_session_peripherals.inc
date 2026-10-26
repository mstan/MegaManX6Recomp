/* Link boundary for the actual memory.c included by this fixture TU.
 * The game fixture never executes device routing, scheduler, trace, overlay
 * or draw-pass policy. MinGW/COFF can retain those public memory.c readers
 * despite function sections/LTO. Every such callback fails visibly if reached;
 * none substitutes RAM, an allocator, a bank, a replacement table or reset.
 * SDK headers already included by memory.c provide the actual prototypes.
 * Signatures for memory.c-local extern hooks are identical to that source.
 */
#include "overlay_loader.h"
#include "interrupts.h"

CPUState *debug_cpu_ptr;
uint32_t g_debug_current_func_addr,g_debug_last_store_pc;
volatile int g_ds_recording;
int g_ls_mode,g_ls_replay_active,g_ls_suppress_record,g_ram_read_watch_active;
int g_event_step_conservative,g_psx_cyc_bb_defer,g_psx_guest_time_frozen;
int g_dma_exec_depth,g_dma_cur_ch;
uint32_t g_dma_initiator_pc,g_dma_cur_madr,g_dma_cur_bcr;
uint32_t g_overlay_region_floor;
uint32_t g_text_image_lo;
/* No linked BIOS is activated or executed by this resource unit fixture. */
PsxBiosImageInfo psx_bios_image;
const PsxKernelBody *psx_bios_kernel_bodies;
uint32_t psx_bios_kernel_body_count;
const PsxKernelPatchRange *psx_bios_kernel_patch_ranges;
uint32_t psx_bios_kernel_patch_range_count;
void (*g_overlay_flush_pending_cycles)(void);
uint64_t psx_cycle_count,s_frame_count,psx_next_service_cycle,g_psx_cycle_fast_limit;
int psx_in_device_service;
uint32_t g_psx_cyc_batch,g_psx_cyc_batch_limit;
uint32_t *g_psx_cyc_local_acc;
uint32_t g_psx_gcs_recip_q16=65536u,g_psx_gcs_frac;
uint32_t g_psx_icache_tv[1024];
uint32_t g_dirty_ram_dispatch_pc_bitmap[DIRTY_RAM_EXEC_BITMAP_WORDS];
uint32_t g_dirty_ram_dispatch_seg_bitmap[PSX_CODE_SEGMENT_COUNT][DIRTY_RAM_EXEC_BITMAP_WORDS];
uint32_t g_dirty_ram_exec_pc_bitmap[DIRTY_RAM_EXEC_BITMAP_WORDS];
uint32_t g_dirty_ram_exec_page_bitmap[DIRTY_RAM_EXEC_PAGE_BITMAP_WORDS];

static void mmx6_session_forbidden(const char *name) {
    fprintf(stderr,"F39 fixture forbidden peripheral: %s\n",name);
    fflush(stderr);
    exit(86); /* Portable, deterministic failure; no OS crash dialog. */
}
#define F39_VOID0(name) void name(void){mmx6_session_forbidden(#name);}
#define F39_VOID1(name,T,a) void name(T a){(void)a;mmx6_session_forbidden(#name);}
#define F39_VOID2(name,T,a,U,b) void name(T a,U b){(void)a;(void)b;mmx6_session_forbidden(#name);}
#define F39_VOID3(name,T,a,U,b,V,c) void name(T a,U b,V c){(void)a;(void)b;(void)c;mmx6_session_forbidden(#name);}
#define F39_VOID4(name,T,a,U,b,V,c,W,d) void name(T a,U b,V c,W d){(void)a;(void)b;(void)c;(void)d;mmx6_session_forbidden(#name);}
#define F39_READ0(name) uint32_t name(void){mmx6_session_forbidden(#name);return 0;}
#define F39_READ1(name) uint32_t name(uint32_t a){(void)a;mmx6_session_forbidden(#name);return 0;}

F39_VOID1(psx_advance_cycles_slow,uint32_t,cycles)
F39_VOID0(psx_devices_mmio_sync)
F39_VOID0(psx_irq_refresh_cause_ip2)
F39_VOID1(psx_fatal_halt,const char *,reason)
int psx_get_in_exception(void){mmx6_session_forbidden("psx_get_in_exception");return 0;}
int fntrace_is_game_started(void){mmx6_session_forbidden("fntrace_is_game_started");return 0;}
F39_VOID2(sio_card_handoff_on_imask,uint32_t,old_mask,uint32_t,new_mask)
F39_VOID1(sio_tick,int,cycles)
F39_VOID3(psx_icache_isc_store,uint32_t,biu,uint32_t,address,uint32_t,value)
F39_VOID1(pgxp_invalidate_word,uint32_t,address)

F39_READ1(cdrom_read)
F39_READ1(dma_read)
F39_READ1(mdec_read)
F39_READ1(sio_read)
F39_READ1(spu_read)
F39_READ1(timers_read)
F39_READ0(gpu_read_gpuread)
F39_READ0(gpu_read_gpustat)
F39_VOID2(cdrom_write,uint32_t,address,uint32_t,value)
F39_VOID2(dma_write,uint32_t,address,uint32_t,value)
F39_VOID3(dma_write_masked,uint32_t,address,uint32_t,value,uint32_t,mask)
F39_VOID2(mdec_write,uint32_t,address,uint32_t,value)
F39_VOID2(sio_write,uint32_t,address,uint32_t,value)
F39_VOID2(spu_write,uint32_t,address,uint32_t,value)
F39_VOID2(timers_write,uint32_t,address,uint32_t,value)
F39_VOID1(gpu_write_gp1,uint32_t,value)
/* gpu_write_gp0/gpu_set_gp0_source are the pre-existing strict menu-upload
 * fixture providers in test_mmx6_coop_private_effects.c, never duplicated. */

F39_VOID0(overlay_loader_note_code_write)
F39_VOID0(overlay_loader_resync_validation_after_restore)
F39_VOID2(overlay_loader_active_write_check,uint32_t,address,uint32_t,bytes)
F39_VOID0(ds_note_dma_write)
F39_VOID2(ds_note_read,uint32_t,address,uint32_t,bytes)
F39_VOID2(ds_note_write,uint32_t,address,uint32_t,bytes)
F39_VOID0(ls_shadow_record_unreplayable)
uint32_t ls_read_hook(uint32_t address,int size,uint32_t value){
    (void)address;(void)size;(void)value;mmx6_session_forbidden("ls_read_hook");return 0;
}
F39_VOID3(ls_write_hook,uint32_t,address,int,size,uint32_t,value)
F39_VOID2(debug_server_trace_ram_read_watch,uint32_t,address,uint32_t,value)
F39_VOID3(debug_server_trace_mmio_read,uint32_t,address,uint32_t,value,uint8_t,width)
F39_VOID3(debug_server_trace_mmio_write,uint32_t,address,uint32_t,value,uint8_t,width)
F39_VOID4(debug_server_trace_write_check,uint32_t,address,uint32_t,old_value,uint32_t,new_value,uint8_t,width)
F39_VOID4(debug_server_trace_entryint_write,uint32_t,address,uint32_t,old_value,uint32_t,new_value,uint8_t,width)
F39_VOID3(parity_trace_note_write,uint32_t,address,uint32_t,width,uint32_t,pc)
int card_data_writes_check(uint32_t address,uint32_t value,uint8_t width){
    (void)address;(void)value;(void)width;mmx6_session_forbidden("card_data_writes_check");return 0;
}
int render_pass_mmio_read_allowed(uint32_t address,uint32_t width){
    (void)address;(void)width;mmx6_session_forbidden("render_pass_mmio_read_allowed");return 0;
}
int render_pass_store_to(const RenderPassStoreTarget *target,uint32_t address,uint32_t value,uint32_t width){
    (void)target;(void)address;(void)value;(void)width;mmx6_session_forbidden("render_pass_store_to");return 0;
}

#undef F39_VOID0
#undef F39_VOID1
#undef F39_VOID2
#undef F39_VOID3
#undef F39_VOID4
#undef F39_READ0
#undef F39_READ1

void mmx6_test_session_peripheral_probe(const char *name) {
    /* Probe actual memory.c device/render routing, plus a direct device
     * callback. Successful session-resource tests never enter these paths. */
    if(!strcmp(name,"mmio-route")){(void)mmio_read8(0x1F801800u);}
    else if(!strcmp(name,"render-route")){render_pass_store(0x80010000u,0,4);}
    else if(!strcmp(name,"device")){(void)cdrom_read(0x1F801800u);}
    else {fprintf(stderr,"unknown fixture peripheral probe\n");exit(87);}
    fprintf(stderr,"fixture peripheral probe unexpectedly returned\n");exit(88);
}
