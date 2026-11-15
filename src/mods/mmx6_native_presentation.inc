#include "mmx6_native_presentation.h"
#include "cpu_state.h"
#include "mod_plugins.h"
#include "mod_texture_banks.h"
#include "psx_cycle_freeze.h"
#include "gpu_gl_renderer.h"
#include "gpu_render.h"
#include "dma.h"
#include <atomic>
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
    uint64_t texture=0;
    ~Published(){if(texture)psx_presentation_gpu_release(texture);}
};
struct Output {
    uint64_t epoch=0,serial=0,version=0;
    GpuDrawArea front{},back{};
};
std::atomic<uint64_t> native_epoch{1},native_serial{0};
std::atomic<bool> native_enabled{false};
std::atomic<uint64_t> native_captured{0},native_ready{0},native_presented{0},native_fallbacks{0};
std::atomic<const char*> native_failure{"inactive"};
uint32_t native_ticks=0,native_buffer=0,native_head=0;
bool native_open=false,native_complete=false,native_armed=false;
std::unique_ptr<Frame> native_writing;
std::vector<Range> native_ranges;
Scope native_actor_scope,native_bg_scope;
std::mutex native_publication;
std::unique_ptr<Published> native_previous;
Prepared native_prepared;
Output native_output;

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
    if(end<begin || end-begin>4096u*0x28u || !native_ram(begin,end-begin)) {
        native_reject("producer packet range");return;
    }
    if(end>begin)native_ranges.push_back({begin,end,scope.motion});
    if(native_writing)native_writing->anchor(scope.motion);
    scope={};
}
void native_actor_begin(CPUState* cpu,uint32_t) {
    if(g_psx_render_pass_active || psx_mod_local_view_scope() || !native_open || !native_writing)return;
    if(native_actor_scope.active){native_reject("nested sprite producer");return;}
    const uint32_t actor=cpu->gpr[4];
    if(!native_ram(actor,0x50))return;
    const int layer=int8_t(psx_mod_read_byte(actor+0x14));
    Motion m{};
    if(layer>=0 && layer<3 && native_layer(unsigned(layer),m)) {
        m.key=0x100000000ull|(actor&0x1FFFFFFFu);m.world=true;
        m.identity=native_identity(psx_mod_read_word(actor),psx_mod_read_word(actor+0x38),
            psx_mod_read_word(actor+0x3C)^uint32_t(layer));
        m.x=double(int32_t(psx_mod_read_word(actor+8)))/65536.0-m.camera_x;
        m.y=double(int32_t(psx_mod_read_word(actor+12)))/65536.0-m.camera_y;
    }
    native_actor_scope={psx_mod_read_word(0x1F800100u),m,true};
}
void native_actor_end(CPUState*,uint32_t) {
    if(!g_psx_render_pass_active && !psx_mod_local_view_scope() && native_open)native_finish_scope(native_actor_scope,psx_mod_read_word(0x1F800100u));
}
void native_bg_begin(CPUState* cpu,uint32_t) {
    if(g_psx_render_pass_active || psx_mod_local_view_scope() || !native_open || !native_writing)return;
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
    if(!g_psx_render_pass_active && !psx_mod_local_view_scope() && native_open)native_finish_scope(native_bg_scope,psx_mod_read_word(0x1F800108u));
}
void native_begin(CPUState*,uint32_t) {
    if(g_psx_render_pass_active || psx_mod_local_view_scope())return;
    native_serial.fetch_add(1);
    native_open=native_complete=native_armed=false;
    native_actor_scope={};native_bg_scope={};native_ranges.clear();native_writing.reset();
    if(!native_enabled)return;
    if(psx_mod_widescreen_view_x_margin()!=0 || gpu_last_frame_vertical_split_screen()) {
        native_failure="wide or co-op view not yet bound";++native_fallbacks;return;
    }
    native_buffer=psx_mod_read_word(0x8009B7A0u);
    if(native_buffer!=FrameBase && native_buffer!=FrameBase+FrameStride){native_failure="framebuffer";return;}
    native_writing=std::make_unique<Frame>();
    native_writing->epoch=native_epoch;native_writing->serial=native_serial;
    native_writing->tick=native_ticks;native_open=true;
}
void native_end(CPUState*,uint32_t) {
    if(g_psx_render_pass_active || psx_mod_local_view_scope() || !native_open)return;
    if(native_actor_scope.active || native_bg_scope.active){native_reject("unclosed producer");return;}
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
void native_ot(CPUState* cpu,uint32_t) {
    if(!g_psx_render_pass_active && !psx_mod_local_view_scope() && native_open && native_complete && cpu->gpr[4]==native_buffer+0xECu) {
        native_head=cpu->gpr[4]&0x1FFFFFFFu;native_armed=true;
    }
}
void native_gpu_ready_impl(void* user,uint64_t version) {
    std::unique_ptr<Published> next(static_cast<Published*>(user));next->texture=version;
    if(!version || !native_enabled || next->frame.epoch!=native_epoch)return;
    std::lock_guard<std::mutex> lock(native_publication);
    native_output={};
    if(next->frame.epoch!=native_epoch)return;
    const bool banks=native_previous &&
        (native_previous->frame.target.left!=next->frame.target.left || native_previous->frame.target.top!=next->frame.target.top) &&
        native_previous->frame.target.right-native_previous->frame.target.left==next->frame.target.right-next->frame.target.left &&
        native_previous->frame.target.bottom-native_previous->frame.target.top==next->frame.target.bottom-next->frame.target.top;
    if(banks && next->frame.tick-native_previous->frame.tick==2 &&
       native_prepared.build(native_previous->frame,next->frame,version,.5)) {
        uint32_t count=0;const auto* triangles=psx_presentation_draw_triangles(native_prepared.draw.get(),&count);
        if(psx_presentation_gpu_render(triangles,count,native_prepared.materials.data(),uint32_t(native_prepared.materials.size()))) {
            native_output={next->frame.epoch,next->frame.serial,psx_presentation_gpu_output_version(),
                native_previous->frame.target,next->frame.target};
            native_failure="";++native_ready;
        }else{native_failure="private GPU target";++native_fallbacks;}
    }else{native_failure=!native_previous?"first scene":!banks?"source display binding":
        next->frame.tick-native_previous->frame.tick!=2?"native cadence not two ticks":native_prepared.failure;++native_fallbacks;}
    native_previous=std::move(next);
}
void native_gpu_ready(void* user,uint64_t version) noexcept {
    try {native_gpu_ready_impl(user,version);}
    catch(...) {std::lock_guard<std::mutex> lock(native_publication);native_output={};native_failure="native scene allocation";++native_fallbacks;}
}
void native_receipt_impl(void*,const DMANativeGpuNode* nodes,uint32_t count,
    const uint32_t* words,uint32_t total,int terminated) {
    if(!native_open || !native_complete || !native_armed || !native_writing)return;
    native_armed=false;
    if(!terminated || !count || count>MaxPackets || !words || nodes[0].address!=native_head) {
        native_reject("incomplete native list");return;
    }
    Frame& f=*native_writing;gpu_get_drawing_environment(&f.environment);
    f.filter=uint8_t(gr_texture_filter());f.accurate=gl_renderer_accurate_blending()!=0;
    for(uint32_t i=0;i<count && f.valid;++i) {
        const auto& node=nodes[i];const unsigned n=node.header>>24;
        if(node.offset>total || n>total-node.offset){f.reject("receipt bounds");break;}
        for(unsigned at=0;at<n && f.valid;) {
            const uint32_t* w=words+node.offset+at;const unsigned op=w[0]>>24;
            const int length=gpu_gp0_command_word_count(uint8_t(op));
            if(length<=0 || unsigned(length)>n-at){f.reject("stream command bounds");break;}
            const uint32_t source=node.address+4u+at*4u;
            if(mod_texture_packet_bank(source,w,unsigned(length))){f.reject("immutable bank not yet bound");break;}
            int32_t x[4]{},y[4]{};unsigned vertices=0;const int rectangle=(op&0xE0u)==0x60u;
            if(rectangle){
                if(unsigned(length)>=2){const unsigned size=(op>>3)&3,fixed[4]={0,1,8,16};
                    const uint32_t wh=size?0:w[(op&4)?3:2];
                    const unsigned width=size?fixed[size]:wh&1023,height=size?fixed[size]:(wh>>16)&511;
                    const int xx=Frame::signed11(w[1]),yy=Frame::signed11(w[1]>>16);
                    for(unsigned j=0;j<4;++j){x[j]=xx+((j&1)?width:0);y[j]=yy+((j&2)?height:0);}vertices=4;}
            }else if((op&0xE0u)==0x20u){
                vertices=(op&8)?4:3;const unsigned stride=1+unsigned((op&4)!=0)+unsigned((op&16)!=0);
                if(vertices*stride+unsigned(!(op&16))!=unsigned(length)){f.reject("polygon bounds");break;}
                for(unsigned j=0;j<vertices;++j){x[j]=Frame::signed11(w[1+j*stride]);y[j]=Frame::signed11(w[1+j*stride]>>16);}
            }
            const bool ui=vertices && gpu_ws_copy_presented_ui(source,w,unsigned(length),x,y,vertices,rectangle);
            const Motion m=ui?Motion{}:native_packet_motion(node.address+at*4u);
            f.add(source,w,unsigned(length),m,ui?x:nullptr,ui?y:nullptr);at+=unsigned(length);
        }
    }
    native_open=false;
    if(!f.valid){native_reject(f.failure);return;}
    auto next=std::make_unique<Published>();next->frame=std::move(f);native_writing.reset();
    ++native_captured;
    Published* transfer=next.release();
    if(!psx_presentation_gpu_snapshot_async(native_gpu_ready,transfer)){
        delete transfer;native_failure="native GPU snapshot unavailable";++native_fallbacks;
    }
}
void native_receipt(void* user,const DMANativeGpuNode* nodes,uint32_t count,
    const uint32_t* words,uint32_t total,int terminated) noexcept {
    try {native_receipt_impl(user,nodes,count,words,total,terminated);}
    catch(...) {native_reject("native capture allocation");}
}
int native_present(void*,int x,int y,int w,int h,int repeated,int crop[4]) {
    if(!native_enabled || !repeated || gpu_last_frame_vertical_split_screen())return 0;
    std::lock_guard<std::mutex> lock(native_publication);
    const auto& out=native_output;
    if(!out.version || out.epoch!=native_epoch || out.serial!=native_serial ||
       int(out.front.left)!=x || int(out.front.top)!=y ||
       int(out.front.right-out.front.left+1)!=w || int(out.front.bottom-out.front.top+1)!=h ||
       !psx_presentation_gpu_output_ready(out.version))return 0;
    crop[0]=int(out.back.left);crop[1]=int(out.back.top);crop[2]=w;crop[3]=h;
    native_output.version=0; /* This native 30Hz interval owns one midpoint. */
    ++native_presented;return 1;
}
void native_reset() {
    native_enabled=false;++native_epoch;
    (void)dma_set_native_gpu_receipt(nullptr,nullptr);
    psx_presentation_gpu_set_provider(nullptr,nullptr);
    std::unique_ptr<Published> release;
    {std::lock_guard<std::mutex> lock(native_publication);release=std::move(native_previous);native_output={};}
    native_open=native_complete=native_armed=false;native_writing.reset();native_ranges.clear();
    native_actor_scope={};native_bg_scope={};native_failure="inactive";
}
void native_restore() {native_epoch.fetch_add(1);native_open=native_complete=native_armed=false;native_writing.reset();}
void native_tick(){if(!g_psx_render_pass_active)++native_ticks;}
void native_activate() {
    native_reset();native_ticks=0;char rate[24]="display";
    (void)psx_mod_option_value("mmx6.enhancement.frame-interpolation","frame-interpolation","rate",rate,sizeof rate);
    if(std::strcmp(rate,"display") && std::strcmp(rate,"60")){native_failure="output cadence not yet bound";return;}
    if(!dma_set_native_gpu_receipt(native_receipt,nullptr)){native_failure="native immutable-list service unavailable";return;}
    native_enabled=true;psx_presentation_gpu_set_provider(native_present,nullptr);
}
}
PSX_MOD_CONSTRUCTOR(mmx6_register_frame_interpolation_plugin) {
    psx_mod_register_session_reset_plugin(NativePlugin,native_reset);
    psx_mod_register_savestate_plugin(NativePlugin,native_restore);
    psx_mod_register_activation_plugin(NativePlugin,native_activate);
    psx_mod_register_vblank_plugin(NativePlugin,native_tick);
    psx_mod_register_function_entry_plugin(NativePlugin,NativeDraw,native_begin);
    psx_mod_register_function_entry_plugin(NativePlugin,NativeActor,native_actor_begin);
    psx_mod_register_function_entry_plugin(NativePlugin,NativeBg,native_bg_begin);
    psx_mod_register_function_entry_plugin(NativePlugin,NativeBgEnd,native_bg_end);
    psx_mod_register_function_entry_plugin(NativePlugin,NativeOT,native_ot);
    psx_mod_register_instruction_plugin(NativePlugin,NativeActorEnd,0x03E00008u,native_actor_end);
    psx_mod_register_instruction_plugin(NativePlugin,NativeEnd,0x03E00008u,native_end);
}
