#include "mmx6_native_presentation.h"
#include "cpu_state.h"
#include "mod_plugins.h"
#include "mod_texture_banks.h"
#include "mod_memory.h"
#include "psx_cycle_freeze.h"
#include "gpu_gl_renderer.h"
#include "gpu_render.h"
#include "dma.h"
#include "mmx6_native_view_observer.h"
#include "mmx6_native_pair.h"
#include "gpu_view_receipt.h"
#include "presentation_view.h"
#include "psx_cycles.h"
#include "psx_video_timing.h"
#include "render_thread.h"
#include <atomic>
#include <cstdio>
#include <cstring>
#include <mutex>

/* SLUS-01395 v1.1. Observe ordinary drawing, never rerun it. U1 hands us its
 * already frozen packet bytes after UI classification and before native GP0.
 * The current native packet shape/animation is transported by authored rigid
 * sprite/layer poses; unowned HUD and overlays stay at their current positions.
 * The initial eligibility cell is a single native 4:3 30Hz view at 60Hz output.
 * Every unavailable contract keeps ordinary native presentation and audio. */
namespace {
using namespace mmx6_native;
constexpr uint32_t NativeDraw=0x80025FB0u, NativeEnd=0x80025FD0u;
constexpr uint32_t NativeActor=0x800232D4u, NativeActorEnd=0x800239C4u;
constexpr uint32_t NativeBg=0x800270D0u, NativeBgEnd=0x80026ECCu;
constexpr uint32_t NativeOT=0x80066744u, FrameBase=0x800C4578u, FrameStride=0xF0u;
constexpr uint32_t LayerBase=0x800971F8u;
constexpr const char* NativePlugin="mmx6.frame-interpolation";
struct Range {uint32_t lo,hi;Motion motion;};
struct Scope {uint32_t begin=0;Motion motion{};bool active=false;};
struct Published {
    Frame frame;
    uint64_t texture=0,ready_cycle=0,ready_ns=0,period_ns=0;
    ~Published(){if(texture)psx_presentation_gpu_release(texture);}
};
struct Output {
    uint64_t epoch=0,serial=0,version=0;
    GpuDrawArea front{},back{};
    uint64_t deadline=0;
};
std::atomic<uint64_t> native_epoch{1},native_serial{0};
std::atomic<bool> native_enabled{false};
std::atomic<bool> native_rate{false};
std::atomic<uint64_t> native_captured{0},native_ready{0},native_presented{0},native_fallbacks{0};
std::atomic<const char*> native_failure{"inactive"};
uint32_t native_ticks=0,native_buffer=0,native_head=0;
bool native_open=false,native_complete=false,native_armed=false;
std::unique_ptr<Frame> native_writing;
std::vector<Range> native_ranges;
Scope native_actor_scope,native_bg_scope;
std::vector<Scope> native_actor_stack;
unsigned native_view=0;
void native_coop_observe(void*,CPUState*,unsigned,unsigned,int);
void native_coop_clear();
std::mutex native_publication;
std::shared_ptr<Published> native_previous,native_pending;
std::shared_ptr<Published> native_older;
bool native_list_scope=false;
Prepared native_prepared;
Output native_output;
void native_rate_coop_prepare(const PsxPresentationRateRequest& request);
void native_rate_prepare(void*,const PsxPresentationRateRequest* request) noexcept {
    try {
        if(!request || !native_enabled || !native_rate)return;
        if(request->pair_id){native_rate_coop_prepare(*request);return;}
        std::lock_guard<std::mutex> lock(native_publication);
        native_output={};
        const auto& old=native_older;const auto& next=native_previous;
        if(!old || !next || next->frame.epoch!=native_epoch || next->frame.serial!=native_serial ||
           old->frame.binding().left!=unsigned(request->x) || old->frame.binding().top!=unsigned(request->y) ||
           request->display_start_cycle<old->ready_cycle)return;
        const uint64_t period=next->period_ns;
        if(!period || old->period_ns!=period || request->deadline_ns<=request->display_start_ns ||
           request->deadline_ns>=request->display_start_ns+period)return;
        double alpha=0;
        if(!psx_presentation_phase(request->display_start_ns,request->display_start_ns+period,
            next->ready_ns,request->deadline_ns,&alpha) ||
           !native_prepared.build(old->frame,next->frame,next->texture,alpha))return;
        uint32_t count=0;const auto* triangles=psx_presentation_draw_triangles(native_prepared.draw.get(),&count);
        if(!psx_presentation_gpu_render(triangles,count,native_prepared.materials.data(),uint32_t(native_prepared.materials.size())))return;
        native_output={next->frame.epoch,next->frame.serial,psx_presentation_gpu_output_version(),
            old->frame.binding(),next->frame.target,request->deadline_ns};
        native_output.front.right=native_output.front.left+next->frame.target.right-next->frame.target.left;
        ++native_ready;
    }catch(...) {std::lock_guard<std::mutex> lock(native_publication);native_output={};native_failure="native rate allocation";++native_fallbacks;}
}

bool native_ram(uint32_t p,uint32_t size) {
    p&=0x1FFFFFFFu;
    return p>=0x10000u && p<0x200000u && size<=0x200000u-p;
}
uint64_t native_identity(uint32_t a,uint32_t b,uint32_t c) {
    uint64_t h=1469598103934665603ull;
    for(uint32_t v:{a,b,c})for(unsigned i=0;i<4;++i)h=(h^((v>>(8*i))&255))*1099511628211ull;
    return h;
}
void native_reject(const char* why) {
    native_failure=why;++native_fallbacks;
    native_open=native_complete=native_armed=false;
    native_actor_scope={};native_bg_scope={};native_writing.reset();
}
bool native_layer(unsigned layer,Motion& m) {
    if(layer>=3)return false;
    const uint32_t b=LayerBase+layer*0x54;
    if(!psx_mod_read_byte(b+3))return false;
    m.camera_x=double(int32_t(psx_mod_read_word(b+8)))/65536.0;
    m.camera_y=double(int32_t(psx_mod_read_word(b+12)))/65536.0;
    return true;
}
void native_finish_scope(Scope& scope,uint32_t end) {
    if(!scope.active)return;
    const uint32_t begin=scope.begin&0x1FFFFFFFu;end&=0x1FFFFFFFu;
    if(end<begin || end-begin>4096u*0x28u ||
       (!native_ram(begin,end-begin) && !(native_view && psx_mod_gpu_dma_memory_contains(begin,end-begin)))) {
        native_reject("producer packet range");return;
    }
    if(end>begin)native_ranges.push_back({begin,end,scope.motion});
    if(native_writing)native_writing->anchor(scope.motion);
    scope={};
}
void native_actor_begin(CPUState* cpu,uint32_t) {
    if((!native_view && (g_psx_render_pass_active || psx_mod_local_view_scope())) || !native_open || !native_writing)return;
    if(native_actor_scope.active) {
        if(native_actor_stack.size()>=32){native_reject("sprite nesting capacity");return;}
        native_actor_stack.push_back(native_actor_scope);
    }
    const uint32_t actor=cpu->gpr[4];
    if(!native_ram(actor,0x50))return;
    const int layer=int8_t(psx_mod_read_byte(actor+0x14));
    Motion m{};
    if(layer>=0 && layer<3 && native_layer(unsigned(layer),m)) {
        m.key=0x100000000ull|(actor&0x1FFFFFFFu);m.world=true;
        // The projected partner's existing host arena is a distinct authored
        // producer even when both bodies use the same guest singleton slot.
        if(native_view && psx_mod_gpu_dma_memory_contains(psx_mod_read_word(0x1F800100u),1))m.key|=1ull<<40;
        m.identity=native_identity(psx_mod_read_word(actor),psx_mod_read_word(actor+0x38),
            psx_mod_read_word(actor+0x3C)^uint32_t(layer));
        m.x=double(int32_t(psx_mod_read_word(actor+8)))/65536.0-m.camera_x;
        m.y=double(int32_t(psx_mod_read_word(actor+12)))/65536.0-m.camera_y;
    }
    native_actor_scope={psx_mod_read_word(0x1F800100u),m,true};
}
void native_actor_end(CPUState*,uint32_t) {
    if((native_view || (!g_psx_render_pass_active && !psx_mod_local_view_scope())) && native_open){
        native_finish_scope(native_actor_scope,psx_mod_read_word(0x1F800100u));
        if(!native_actor_stack.empty()){native_actor_scope=native_actor_stack.back();native_actor_stack.pop_back();}
    }
}
void native_bg_begin(CPUState* cpu,uint32_t) {
    if((!native_view && (g_psx_render_pass_active || psx_mod_local_view_scope())) || !native_open || !native_writing)return;
    if(native_bg_scope.active){native_reject("nested background producer");return;}
    const unsigned layer=cpu->gpr[4];Motion m{};
    if(!native_layer(layer,m))return;
    const uint32_t b=LayerBase+layer*0x54;
    m.key=0x200000000ull|layer;m.world=true;
    m.identity=native_identity(psx_mod_read_word(b+0x18),psx_mod_read_word(b+0x1C),psx_mod_read_byte(b+0x52));
    m.x=-m.camera_x;m.y=-m.camera_y;
    native_bg_scope={psx_mod_read_word(0x1F800108u),m,true};
}
void native_bg_end(CPUState*,uint32_t) {
    if((native_view || (!g_psx_render_pass_active && !psx_mod_local_view_scope())) && native_open)native_finish_scope(native_bg_scope,psx_mod_read_word(0x1F800108u));
}
void native_begin(CPUState*,uint32_t) {
    if(native_view)return; // scope already owns its clear and environment
    if(g_psx_render_pass_active || psx_mod_local_view_scope())return;
    native_serial.fetch_add(1);
    native_open=native_complete=native_armed=false;
    native_actor_scope={};native_actor_stack.clear();native_bg_scope={};native_ranges.clear();native_writing.reset();
    if(!native_enabled)return;
    if(gpu_last_frame_vertical_split_screen()) {
        native_failure="co-op native view owned separately";++native_fallbacks;return;
    }
    native_buffer=psx_mod_read_word(0x8009B7A0u);
    if(native_buffer!=FrameBase && native_buffer!=FrameBase+FrameStride){native_failure="framebuffer";return;}
    native_writing=std::make_unique<Frame>();
    native_writing->epoch=native_epoch;native_writing->serial=native_serial;
    native_writing->tick=native_ticks;
    native_writing->native_target={psx_mod_read_half(native_buffer+0x14),psx_mod_read_half(native_buffer+0x16),0,0,0,0};
    native_writing->native_target.right=native_writing->native_target.left+psx_mod_read_half(native_buffer+0x18)-1;
    native_writing->native_target.bottom=native_writing->native_target.top+psx_mod_read_half(native_buffer+0x1A)-1;
    native_writing->native_target_set=true;native_open=true;
}
void native_end(CPUState*,uint32_t) {
    if((!native_view && (g_psx_render_pass_active || psx_mod_local_view_scope())) || !native_open)return;
    if(native_actor_scope.active || !native_actor_stack.empty() || native_bg_scope.active){native_reject("unclosed producer");return;}
    std::sort(native_ranges.begin(),native_ranges.end(),[](const Range& a,const Range& b){return a.lo<b.lo;});
    for(size_t i=1;i<native_ranges.size();++i)
        if(native_ranges[i-1].hi>native_ranges[i].lo){native_reject("overlapping producers");return;}
    native_complete=true;
}
Motion native_packet_motion(uint32_t source) {
    source&=0x1FFFFFFFu;
    const auto end=std::upper_bound(native_ranges.begin(),native_ranges.end(),source,
        [](uint32_t p,const Range& range){return p<range.lo;});
    if(end==native_ranges.begin())return {};
    const auto& range=*(end-1);return source<range.hi?range.motion:Motion{};
}
void native_coop_ot(CPUState* cpu);
void native_ot(CPUState* cpu,uint32_t) {
    if(native_view){native_coop_ot(cpu);return;}
    if(!g_psx_render_pass_active && !psx_mod_local_view_scope() && native_open && native_complete && cpu->gpr[4]==native_buffer+0xECu) {
        native_head=cpu->gpr[4]&0x1FFFFFFFu;native_armed=true;
    }
}
void native_gpu_ready_impl(std::shared_ptr<Published> next) {
    const uint64_t version=next->texture;
    if(!version || !native_enabled || next->frame.epoch!=native_epoch)return;
    native_rate=psx_presentation_gpu_rate_active()!=0;
    std::lock_guard<std::mutex> lock(native_publication);
    native_output={};
    if(next->frame.epoch!=native_epoch)return;
    const bool banks=native_previous &&
        (native_previous->frame.binding().left!=next->frame.binding().left || native_previous->frame.binding().top!=next->frame.binding().top) &&
        native_previous->frame.target.right-native_previous->frame.target.left==next->frame.target.right-next->frame.target.left &&
        native_previous->frame.target.bottom-native_previous->frame.target.top==next->frame.target.bottom-next->frame.target.top;
    next->ready_ns=rt_now_ns();
    if(native_rate) {
        native_older=banks && next->frame.tick-native_previous->frame.tick==2?native_previous:nullptr;
        native_previous=std::move(next);return;
    }
    if(banks && next->frame.tick-native_previous->frame.tick==2 &&
       native_prepared.build(native_previous->frame,next->frame,version,.5)) {
        uint32_t count=0;const auto* triangles=psx_presentation_draw_triangles(native_prepared.draw.get(),&count);
        if(psx_presentation_gpu_render(triangles,count,native_prepared.materials.data(),uint32_t(native_prepared.materials.size()))) {
            native_output={next->frame.epoch,next->frame.serial,psx_presentation_gpu_output_version(),
                native_previous->frame.binding(),next->frame.target};
            native_output.front.right=native_output.front.left+next->frame.target.right-next->frame.target.left;
            native_failure="";++native_ready;
        }else{native_failure="private GPU target";++native_fallbacks;}
    }else{native_failure=!native_previous?"first scene":!banks?"source display binding":
        next->frame.tick-native_previous->frame.tick!=2?"native cadence not two ticks":native_prepared.failure;++native_fallbacks;}
    native_previous=std::move(next);
}
void native_gpu_ready(void* user) noexcept {
    std::unique_ptr<std::shared_ptr<Published>> transfer(static_cast<std::shared_ptr<Published>*>(user));
    try {native_gpu_ready_impl(*transfer);if(native_rate)psx_presentation_gpu_rate_source_ready();}
    catch(...) {std::lock_guard<std::mutex> lock(native_publication);native_output={};native_failure="native scene allocation";++native_fallbacks;}
}
void native_material_ready(void* user,uint64_t version) noexcept {
    std::unique_ptr<std::shared_ptr<Published>> transfer(static_cast<std::shared_ptr<Published>*>(user));
    (*transfer)->texture=version;
}
void native_receipt_impl(void*,const DMANativeGpuNode* nodes,uint32_t count,
    const uint32_t* words,uint32_t total,int terminated) {
    if(native_view || !native_open || !native_complete || !native_armed || !native_writing)return;
    native_armed=false;
    if(!terminated || !count || count>MaxPackets || !words || nodes[0].address!=native_head) {
        native_reject("incomplete native list");return;
    }
    (void)total;
    if(!gpu_view_command_receipt_begin(0)){native_reject("native command scope unavailable");return;}
    native_list_scope=true;gpu_get_drawing_environment(&native_writing->environment);
    native_writing->filter=uint8_t(gr_texture_filter());native_writing->accurate=gl_renderer_accurate_blending()!=0;
    native_pending=std::make_shared<Published>();
    auto transfer=std::make_unique<std::shared_ptr<Published>>(native_pending);
    if(psx_presentation_gpu_snapshot_async(native_material_ready,transfer.get()))transfer.release();
    else native_writing->reject("native GPU material snapshot unavailable");
}
void native_receipt_end(void*,int terminated) noexcept {
    if(!native_list_scope)return;
    native_list_scope=false;
    const bool complete=gpu_view_command_receipt_end()!=0;
    if(!terminated || !complete || !native_writing || !native_writing->valid || !native_pending) {
        native_pending.reset();native_reject("incomplete native command scene");return;
    }
    try {
        native_pending->frame=std::move(*native_writing);native_pending->ready_cycle=psx_get_cycle_count();
        native_pending->period_ns=uint64_t(g_psx_vblank_cycles)*2ull*1000000000ull/33868800ull;
        native_writing.reset();native_open=false;++native_captured;
        auto transfer=std::make_unique<std::shared_ptr<Published>>(std::move(native_pending));
        if(psx_presentation_gpu_prepare_async(native_gpu_ready,transfer.get()))transfer.release();
        else{native_failure="native scene preparation unavailable";++native_fallbacks;}
    }catch(...){native_pending.reset();native_reject("native completion allocation");}
}
void native_receipt(void* user,const DMANativeGpuNode* nodes,uint32_t count,
    const uint32_t* words,uint32_t total,int terminated) noexcept {
    try {native_receipt_impl(user,nodes,count,words,total,terminated);}
    catch(...) {native_reject("native capture allocation");}
}
int native_present(void*,int x,int y,int w,int h,int repeated,int crop[4]) {
    if(!native_enabled || (!native_rate && !repeated) || gpu_last_frame_vertical_split_screen())return 0;
    PsxPresentationRateRequest request{};
    if(native_rate && !psx_presentation_gpu_rate_request(&request))return 0;
    std::lock_guard<std::mutex> lock(native_publication);
    const auto& out=native_output;
    if(!out.version || (native_rate && (!request.deadline_ns || out.deadline!=request.deadline_ns)) ||
       out.epoch!=native_epoch || out.serial!=native_serial ||
       int(out.front.left)!=x || int(out.front.top)!=y ||
       int(out.front.right-out.front.left+1)!=w || int(out.front.bottom-out.front.top+1)!=h ||
       !psx_presentation_gpu_output_ready(out.version))return 0;
    crop[0]=int(out.back.left);crop[1]=int(out.back.top);crop[2]=w;crop[3]=h;
    native_output.version=0; /* This native 30Hz interval owns one midpoint. */
    ++native_presented;return 1;
}
void native_reset() {
    native_enabled=false;native_rate=false;++native_epoch;
    psx_presentation_gpu_set_rate(0,nullptr,nullptr);
    (void)dma_set_native_gpu_receipt(nullptr,nullptr);
    psx_presentation_gpu_set_provider(nullptr,nullptr);
    psx_presentation_gpu_set_pair_provider(nullptr,nullptr);
    gpu_set_view_command_receipt(nullptr,nullptr);
    mmx6_native_coop_set_observer(nullptr,nullptr);
    native_coop_clear();
    native_pending.reset();native_list_scope=false;
    std::shared_ptr<Published> release;
    {std::lock_guard<std::mutex> lock(native_publication);release=std::move(native_previous);native_older.reset();native_output={};}
    native_open=native_complete=native_armed=false;native_writing.reset();native_ranges.clear();
    native_actor_scope={};native_bg_scope={};native_failure="inactive";
}
void native_restore() {native_epoch.fetch_add(1);psx_presentation_gpu_rate_reset();native_open=native_complete=native_armed=false;native_writing.reset();native_coop_clear();native_pending.reset();native_list_scope=false;}
void native_tick(){
    if(g_psx_render_pass_active)return;
    ++native_ticks;
    /* Publish the existing GPU-owner totals on the CPU's existing counter
     * service. A selected native provider is distinct from a native pair swap. */
    static uint64_t seen[4]{};
    const uint64_t totals[]={native_captured.load(),native_ready.load(),native_presented.load(),native_fallbacks.load()};
    static const char* const names[]={"mmx6.interpolation.captured","mmx6.interpolation.ready",
        "mmx6.interpolation.selected","mmx6.interpolation.fallback"};
    for(unsigned i=0;i<4;++i){
        const uint64_t delta=totals[i]-seen[i];
        if(delta)psx_mod_counter_add(names[i],uint32_t(std::min(delta,uint64_t(UINT32_MAX))));
        seen[i]=totals[i];
    }
}
void native_coop_activate();
void native_activate() {
    native_reset();native_ticks=0;char rate[24]="display";
    (void)psx_mod_option_value("mmx6.enhancement.frame-interpolation","frame-interpolation","rate",rate,sizeof rate);
    constexpr struct {const char* id;double hz;} choices[]={
        {"display",0},{"uncapped",0},{"60",60},{"90",90},
        {"120",120},{"144",144},{"165",165},{"240",240}};
    double output_hz=-1;
    for(const auto& choice:choices)if(!std::strcmp(rate,choice.id)){output_hz=choice.hz;break;}
    if(output_hz<0){native_failure="unsupported output cadence";return;}
    if(!dma_set_native_gpu_receipt_scope(native_receipt,native_receipt_end,nullptr)){native_failure="native immutable-list service unavailable";return;}
    native_enabled=true;psx_presentation_gpu_set_provider(native_present,nullptr);
    native_coop_activate();
    const int cadence=psx_presentation_gpu_set_rate(output_hz,native_rate_prepare,nullptr);
    native_rate=cadence==2;
    if(!cadence){native_failure="native output cadence unavailable";++native_fallbacks;}
}
#include "mmx6_native_coop.inc"
}
PSX_MOD_CONSTRUCTOR(mmx6_register_frame_interpolation_plugin) {
    psx_mod_register_session_reset_plugin(NativePlugin,native_reset);
    psx_mod_register_savestate_plugin(NativePlugin,native_restore);
    psx_mod_register_activation_plugin(NativePlugin,native_activate);
    psx_mod_register_vblank_plugin(NativePlugin,native_tick);
    psx_mod_register_function_entry_plugin(NativePlugin,NativeDraw,native_begin);
    /* Entry hooks run before another plugin can replace the function. Observe
     * the first REAL instruction instead: a replaced outer call has no native
     * return, while its nested native draw owns one balanced producer scope. */
    psx_mod_register_instruction_plugin(NativePlugin,NativeActor,0x27BDFFD0u,native_actor_begin);
    psx_mod_register_function_entry_plugin(NativePlugin,NativeBg,native_bg_begin);
    psx_mod_register_function_entry_plugin(NativePlugin,NativeBgEnd,native_bg_end);
    psx_mod_register_function_entry_plugin(NativePlugin,NativeOT,native_ot);
    psx_mod_register_instruction_plugin(NativePlugin,NativeActorEnd,0x03E00008u,native_actor_end);
    psx_mod_register_instruction_plugin(NativePlugin,NativeEnd,0x03E00008u,native_end);
}
