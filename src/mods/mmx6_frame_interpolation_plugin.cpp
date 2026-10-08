#include "cpu_state.h"
#include "mod_plugins.h"
#include "render_pass_motion.h"
#include "psx_cycle_freeze.h"
#include "pgxp.h"
#include "gpu.h"
#include <cstring>
#include <vector>

extern "C" uint8_t* memory_get_ram_ptr(void);
extern "C" uint8_t* memory_get_scratchpad_ptr(void);
extern "C" uint32_t memory_get_ram_bytes(void);

// SLUS-01395: the world draw wrapper calls background + actor renderers only.
// Capture after gameplay has updated their positions; replay never runs input,
// movement, collision, animation advancement or the audio update.
namespace {
constexpr uint32_t Draw=0x80025FB0, End=0x80025FD0, Camera=0x80026DA4;
constexpr uint32_t Actor=0x800232D4, VSync=0x80060964;
constexpr uint32_t Base=0x800C4578, Stride=0xF0, Layers=0x800971F8;
constexpr uint32_t PutDrawEnv=0x800667B4, DrawOTag=0x80066744, DrawSync=0x80066150;
CPUState entry{};
std::vector<uint8_t> ram;
uint8_t scratch[1024]{};
PSXMotionSet* motion=nullptr;
PSXMotionStats stats{};
uint32_t vblanks=0, buffer=0, alpha=0;
bool capturing=false, ready=false, waiting=false;
uint32_t draw_heads[32]{};
struct LatePacket { uint32_t address;std::vector<uint32_t> words; };
std::vector<LatePacket> late[32];

bool capture_late_packets() {
    // Other scene tasks can prepend a fade or overlay after the world wrapper
    // returns. Preserve those exact current-frame packets in their OT buckets.
    // Only a bounded prefix ending at the captured world head is accepted.
    uint32_t total=0;
    for(uint32_t i=0;i<32;++i) {
        late[i].clear();
        uint32_t node=psx_mod_read_word(buffer+0x70+4*i)&0xFFFFFF;
        const uint32_t stop=draw_heads[i]&0xFFFFFF;
        while(node!=stop) {
            if(node<0x90000 || (node&3) || node>memory_get_ram_bytes()-4 || ++total>4096)return false;
            const uint32_t tag=psx_mod_read_word(node),words=1+(tag>>24);
            if(words*4>memory_get_ram_bytes()-node)return false;
            LatePacket packet{node,{}};packet.words.reserve(words);
            for(uint32_t j=0;j<words;++j)packet.words.push_back(psx_mod_read_word(node+4*j));
            late[i].push_back(std::move(packet));node=tag&0xFFFFFF;
        }
    }
    return true;
}
void apply_late_packets() {
    for(uint32_t i=0;i<32;++i) {
        if(late[i].empty())continue;
        const uint32_t slot=buffer+0x70+4*i, head=psx_mod_read_word(slot);
        for(const auto& p:late[i])for(uint32_t j=0;j<p.words.size();++j)
            psx_mod_write_word(p.address+4*j,p.words[j]);
        const auto& tail=late[i].back();
        psx_mod_write_word(tail.address,(tail.words[0]&0xFF000000)|(head&0xFFFFFF));
        psx_mod_write_word(slot,(head&0xFF000000)|late[i][0].address);
    }
}

bool retarget_packets() {
    const uint32_t index=(buffer-Base)/Stride;
    // Main-loop OT prefixes carry their own draw offset and draw area. Those
    // override PutDrawEnv, so replay must select the pending display bank's
    // payload while retaining this OT's links and current authored shake/crop.
    const uint32_t offset=0x800CF908+12*index, clip=0x800CF948+12*index;
    const uint32_t offset_other=0x800CF908+12*(1-index), clip_other=0x800CF948+12*(1-index);
    if((psx_mod_read_word(offset+4)>>24)!=0xE5 ||
       (psx_mod_read_word(offset_other+4)>>24)!=0xE5 ||
       (psx_mod_read_word(clip_other+4)>>24)!=0xE3 ||
       (psx_mod_read_word(clip_other+8)>>24)!=0xE4)return false;
    psx_mod_write_word(offset+4,psx_mod_read_word(offset_other+4));
    psx_mod_write_word(clip+4,psx_mod_read_word(clip_other+4));
    psx_mod_write_word(clip+8,psx_mod_read_word(clip_other+8));
    return true;
}

uint32_t call(CPUState* cpu,uint32_t fn,uint32_t a0) {
    const CPUState saved=*cpu;
    cpu->pc=0;cpu->gpr[4]=a0;
    psx_dispatch_call(cpu,fn,saved.gpr[31]);
    const uint32_t result=cpu->gpr[2];*cpu=saved;return result;
}
void reset() { capturing=ready=false;psx_motion_invalidate(motion); }
void tick(){if(!g_psx_render_pass_active)++vblanks;}
void begin(CPUState* cpu,uint32_t) {
    if(g_psx_render_pass_active)return;
    const uint32_t next=psx_mod_read_word(0x8009B7A0);
    if(next!=Base && next!=Base+Stride){reset();return;}
    if(!motion)motion=psx_motion_set_create(4096);
    if(!motion)return;
    if(capturing)reset();
    buffer=next;entry=*cpu;
    ram.resize(memory_get_ram_bytes());
    std::memcpy(ram.data(),memory_get_ram_ptr(),ram.size());
    std::memcpy(scratch,memory_get_scratchpad_ptr(),sizeof scratch);
    psx_motion_begin(motion,vblanks);capturing=true;ready=false;
}
void position(uint32_t addr,uint32_t identity) {
    if(g_psx_render_pass_active) {
        int32_t value;
        if(psx_motion_blend_at(motion,PSX_MOTION_SCALAR,addr,
                              double(alpha)/65536.0,&value)==1)
            psx_mod_write_word(addr,uint32_t(value));
    } else if(capturing) {
        if(!psx_motion_track(motion,PSX_MOTION_SCALAR,addr,identity))reset();
    }
}
void cameras(CPUState*,uint32_t) {
    if(!capturing && !g_psx_render_pass_active)return;
    // After the layer initializer, before streaming and tile construction.
    // Parent layers are captured separately; their authored offsets stay intact.
    for(uint32_t i=0;i<3;++i) {
        const uint32_t b=Layers+i*0x54;
        if(!psx_mod_read_byte(b+3))continue;
        const uint32_t id=psx_motion_identity(psx_mod_read_word(b+0x18),
            psx_mod_read_word(b+0x1C),psx_mod_read_byte(b+0x52));
        position(b+8,id);position(b+12,id);
    }
}
void actor(CPUState* cpu,uint32_t) {
    if(!capturing && !g_psx_render_pass_active)return;
    const uint32_t b=cpu->gpr[4], phys=b&0x1FFFFFFF;
    if(phys>memory_get_ram_bytes()-0x50 || (b&3))return;
    // Negative camera indices are absolute screen coordinates (HUD/menus).
    const int8_t layer=int8_t(psx_mod_read_byte(b+0x14));
    if(layer<0 || layer>=3)return;
    const uint32_t id=psx_motion_identity(psx_mod_read_word(b+0x38),
        psx_mod_read_word(b+0x3C),uint32_t(layer));
    position(b+8,id);position(b+12,id);
}
void end(CPUState*,uint32_t) {
    if(g_psx_render_pass_active || !capturing)return;
    capturing=false;
    for(uint32_t i=0;i<32;++i)draw_heads[i]=psx_mod_read_word(buffer+0x70+4*i);
    const PSXMotionLimits limits{96.0*65536.0,0.0};
    ready=psx_motion_prepare(motion,&limits,&stats)!=0;
    psx_mod_counter_add("mmx6.fr.frames",1);
    psx_mod_counter_add("mmx6.fr.values",stats.tracked);
    psx_mod_counter_add("mmx6.fr.matched",stats.blended);
    psx_mod_counter_add("mmx6.fr.cuts",stats.placed);
}
int pass(CPUState* cpu,void*,uint32_t phase) {
    if(!ready || !g_psx_render_pass_active || ram.size()!=memory_get_ram_bytes())return 0;
    std::memcpy(memory_get_ram_ptr(),ram.data(),ram.size());
    std::memcpy(memory_get_scratchpad_ptr(),scratch,sizeof scratch);
    pgxp_invalidate_all();*cpu=entry;alpha=phase;
    if(!retarget_packets()){psx_mod_counter_add("mmx6.fr.environment_rejected",1);return 0;}
    const uint32_t other=buffer==Base?Base+Stride:Base;
    // The pending DISPENV names the other bank's draw area. Configure it before
    // world packets are rebuilt, since PutDrawEnv writes its command storage.
    for(uint32_t i=0;i<0x5C;i+=4)
        psx_mod_write_word(buffer+0x14+i,psx_mod_read_word(other+0x14+i));
    call(cpu,PutDrawEnv,buffer+0x14);
    uint64_t nop=0,fill=0,before_draw=0,env=0,copy=0;
    gpu_get_gp0_stats(&nop,&fill,&before_draw,&env,&copy);
    if(!psx_mod_run_guest_span(cpu,Draw,End)) {
        psx_mod_counter_add("mmx6.fr.draw_failed",1);return 0;
    }
    apply_late_packets();
    call(cpu,DrawOTag,buffer+0xEC);call(cpu,DrawSync,0);
    uint64_t after_draw=0;gpu_get_gp0_stats(&nop,&fill,&after_draw,&env,&copy);
    psx_mod_counter_add("mmx6.fr.primitives",uint32_t(after_draw-before_draw));
    return after_draw!=before_draw;
}
void finish(CPUState* cpu,uint32_t) {
    if(g_psx_render_pass_active || waiting || cpu->gpr[31]!=0x80012104 || cpu->gpr[4]!=0)return;
    if(!ready)return;
    ready=false;
    const uint32_t other=buffer==Base?Base+Stride:Base;
    if(psx_mod_read_word(0x8009B7A0)!=buffer ||
       psx_mod_read_word(buffer)!=psx_mod_read_word(other+0x14) ||
       psx_mod_read_word(buffer+4)!=psx_mod_read_word(other+0x18))return;
    if(!capture_late_packets()){psx_mod_counter_add("mmx6.fr.overlay_rejected",1);return;}
    // Let the preceding display flip be captured before opening this frame's
    // generation. VSync(1) is only a query, so a plan before VSync(0)'s wait
    // otherwise overwrites its predecessor before that predecessor is shown.
    // Execute the original wait once and finish the intercepted function;
    // running its body again would add a guest VBlank and slow gameplay.
    waiting=true;
    psx_dispatch_call(cpu,VSync,cpu->gpr[31]);
    waiting=false;
    ready=true;
    PSXModRenderPassFrame frame{};frame.struct_size=sizeof frame;
    frame.period_vblanks=stats.ticks;
    frame.x=psx_mod_read_half(buffer);frame.y=psx_mod_read_half(buffer+2);
    frame.w=psx_mod_read_half(buffer+4);frame.h=psx_mod_read_half(buffer+6);
    psx_mod_counter_add("mmx6.fr.passes",psx_mod_render_pass_frame(cpu,&frame,pass,nullptr));
    ready=false;
    psx_mod_finish_function(cpu);
}
void activate() {
    reset();vblanks=0;
    psx_mod_activate_render_pass_rate("mmx6.enhancement.frame-interpolation",
        "frame-interpolation","rate",PSX_MOD_RENDER_PASS_FLIP_PENDING);
}
}
PSX_MOD_CONSTRUCTOR(mmx6_register_frame_interpolation_plugin) {
    // The rate is the feature's "rate" option; one plugin id serves every rate.
    const char* id="mmx6.frame-interpolation";
    psx_mod_register_activation_plugin(id,activate);
    psx_mod_register_vblank_plugin(id,tick);
    psx_mod_register_function_entry_plugin(id,Draw,begin);
    psx_mod_register_function_entry_plugin(id,Actor,actor);
    psx_mod_register_function_entry_plugin(id,VSync,finish);
    psx_mod_register_instruction_plugin(id,Camera,0x0C009CF9,cameras);
    psx_mod_register_instruction_plugin(id,End,0x03E00008,end);
}
