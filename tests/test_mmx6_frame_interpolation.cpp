#undef NDEBUG
#include "cpu_state.h"
#include "mod_plugins.h"
#include <cassert>
#include <cstring>
#include <cstdio>
static uint8_t test_ram[0x200000],test_scratch[1024];
static unsigned entries,instructions,ticks,activations,env_calls,draw_calls,wait_calls,finished,planned;
static bool fail_span;
extern "C" {
int g_psx_render_pass_active=0;
int psx_mod_register_activation_plugin(const char* id,PSXModActivationCallback){assert(!std::strcmp(id,"mmx6.frame-interpolation"));++activations;return 1;}
int psx_mod_register_vblank_plugin(const char*,PSXModVBlankCallback){++ticks;return 1;}
int psx_mod_register_function_entry_plugin(const char*,uint32_t,PSXModFunctionEntryCallback){++entries;return 1;}
int psx_mod_register_instruction_plugin(const char*,uint32_t,uint32_t,PSXModFunctionEntryCallback){++instructions;return 1;}
int psx_mod_activate_render_pass_rate(const char* p,const char* f,const char* o,uint32_t flip){assert(!std::strcmp(p,"mmx6.enhancement.frame-interpolation"));assert(!std::strcmp(f,"frame-interpolation"));assert(!std::strcmp(o,"rate"));assert(flip==PSX_MOD_RENDER_PASS_FLIP_PENDING);return 1;}
uint8_t* memory_get_ram_ptr(){return test_ram;}
uint8_t* memory_get_scratchpad_ptr(){return test_scratch;}
uint32_t memory_get_ram_bytes(){return sizeof test_ram;}
uint8_t psx_mod_read_byte(uint32_t a){return test_ram[a&0x1FFFFF];}
uint16_t psx_mod_read_half(uint32_t a){uint16_t v;std::memcpy(&v,test_ram+(a&0x1FFFFF),2);return v;}
uint32_t psx_mod_read_word(uint32_t a){uint32_t v;std::memcpy(&v,test_ram+(a&0x1FFFFF),4);return v;}
void psx_mod_write_byte(uint32_t a,uint8_t v){test_ram[a&0x1FFFFF]=v;}
void psx_mod_write_half(uint32_t a,uint16_t v){std::memcpy(test_ram+(a&0x1FFFFF),&v,2);}
void psx_mod_write_word(uint32_t a,uint32_t v){std::memcpy(test_ram+(a&0x1FFFFF),&v,4);}
void pgxp_invalidate_all(){}
void gpu_get_gp0_stats(uint64_t* n,uint64_t* f,uint64_t* d,uint64_t* e,uint64_t* c){*n=*f=*e=*c=0;*d=draw_calls;}
void psx_mod_counter_add(const char*,uint32_t){}
uint32_t psx_mod_render_pass_frame(CPUState*,const PSXModRenderPassFrame* f,PSXModRenderPassFn,void*){assert(wait_calls==1 && f->shown_after_vblanks==0);++planned;return 0;}
int psx_mod_finish_function(CPUState*){++finished;return 1;}
void psx_dispatch_call(CPUState*,uint32_t fn,uint32_t){
    if(fn==0x800667B4){++env_calls;psx_mod_write_word(0x800B91C4,0xE1000000);}
    else if(fn==0x80066744){++draw_calls;assert(psx_mod_read_word(0x800B91C4)==0x64000000);}
    else if(fn==0x80060964)++wait_calls;
    else assert(fn==0x80066150);
}
int psx_mod_run_guest_span(CPUState*,uint32_t,uint32_t);
}
#include "../src/mods/mmx6_frame_interpolation_plugin.cpp"
constexpr uint32_t Sprite=0x800970A0,HUD=0x800950A0;
extern "C" int psx_mod_run_guest_span(CPUState* cpu,uint32_t start,uint32_t stop){
    assert(start==Draw && stop==End && env_calls>draw_calls);
    assert(psx_mod_read_word(0x800CF908)==0x010C4578); // preserve the linked OT
    assert(psx_mod_read_word(0x800CF90C)==0xE5078000); // target offset y=240
    assert(psx_mod_read_word(0x800CF94C)==0xE303C000); // target clip top y=240
    assert(psx_mod_read_word(0x800CF950)==0xE4077D3F); // target clip bottom y=479
    if(fail_span)return 0;
    assert(psx_mod_read_word(0x80090000)==123); // restore the draw-entry RAM
    cameras(cpu,Camera);cpu->gpr[4]=Sprite;actor(cpu,Actor);
    assert(psx_mod_read_word(Sprite+8)==12*65536);
    assert(psx_mod_read_word(Sprite+12)==22*65536);
    assert(psx_mod_read_word(Layers+8)==101*65536);
    assert(psx_mod_read_byte(Sprite+0x47)==2); // retain current animation cell
    cpu->gpr[4]=HUD;actor(cpu,Actor);
    assert(psx_mod_read_word(HUD+8)==200*65536);
    psx_mod_write_word(0x800B91C4,0x64000000);return 1;
}
static void capture(CPUState& cpu,int x,int y,int cam){
    tick();psx_mod_write_word(Sprite+8,x*65536);psx_mod_write_word(Sprite+12,y*65536);
    psx_mod_write_word(Layers+8,cam*65536);
    psx_mod_write_word(0x80090000,123);
    begin(&cpu,Draw);cameras(&cpu,Camera);cpu.gpr[4]=Sprite;actor(&cpu,Actor);
    cpu.gpr[4]=HUD;actor(&cpu,Actor);end(&cpu,End);
}
int main(){
    assert(activations==1 && entries==3 && instructions==2 && ticks==1);activate();
    CPUState cpu{};cpu.gpr[29]=0x801FF000;
    psx_mod_write_word(0x8009B7A0,Base);
    psx_mod_write_word(0x800CF908,0x010C4578);
    psx_mod_write_word(0x800CF90C,0xE5000000);psx_mod_write_word(0x800CF918,0xE5078000);
    psx_mod_write_word(0x800CF94C,0xE3000000);psx_mod_write_word(0x800CF950,0xE403BD3F);
    psx_mod_write_word(0x800CF958,0xE303C000);psx_mod_write_word(0x800CF95C,0xE4077D3F);
    psx_mod_write_byte(Layers+3,1);psx_mod_write_byte(Layers+0x52,0xFF);
    psx_mod_write_byte(Sprite+0x14,0);psx_mod_write_word(Sprite+0x3C,0x80070000);
    psx_mod_write_byte(HUD+0x14,0xFF);psx_mod_write_word(HUD+8,200*65536);
    capture(cpu,10,20,100);assert(!ready);
    psx_mod_write_byte(Sprite+0x47,2);capture(cpu,14,24,102);
    assert(ready && stats.tracked==4 && stats.blended==4 && stats.ticks==1);
    psx_mod_write_word(0x80090000,456);g_psx_render_pass_active=1;
    assert(pass(&cpu,nullptr,32768));assert(draw_calls==1);
    fail_span=true;assert(!pass(&cpu,nullptr,32768));assert(draw_calls==1);
    fail_span=false;g_psx_render_pass_active=0;
    // A queued generation must follow the original wait, which executes once.
    // Completing the intercepted VSync prevents a second guest wait.
    psx_mod_write_word(Base,0);psx_mod_write_word(Base+4,0x00F00140);
    psx_mod_write_word(Base+Stride+0x14,0);psx_mod_write_word(Base+Stride+0x18,0x00F00140);
    cpu.gpr[31]=0x80012104;cpu.gpr[4]=0;finish(&cpu,VSync);
    assert(wait_calls==1 && finished==1 && planned==1 && !ready);
    // A late fade must stay above the rebuilt world's head in the same bucket.
    psx_mod_write_word(Base+0x70,0x000CF000);draw_heads[0]=0x000CF000;
    psx_mod_write_word(0x800CF020,0x010CF000);psx_mod_write_word(0x800CF024,0xE1000040);
    psx_mod_write_word(Base+0x70,0x000CF020);assert(capture_late_packets());
    assert(late[0].size()==1 && late[0][0].words[1]==0xE1000040);
    psx_mod_write_word(Base+0x70,0x000CF040);apply_late_packets();
    assert(psx_mod_read_word(Base+0x70)==0x000CF020);
    assert(psx_mod_read_word(0x800CF020)==0x010CF040);
    // A cycle or unrecognised tail declines replay instead of corrupting OT.
    psx_mod_write_word(0x800CF020,0x010CF020);assert(!capture_late_packets());
    psx_mod_write_word(Sprite+0x3C,0x80071000);capture(cpu,16,26,104);
    int32_t value=0;assert(psx_motion_blend_at(motion,PSX_MOTION_SCALAR,Sprite+8,.5,&value)==0 && value==16*65536);
    capture(cpu,500,26,106);assert(stats.placed==1);
    assert(psx_motion_blend_at(motion,PSX_MOTION_SCALAR,Sprite+8,.5,&value)==0 && value==500*65536);
    vblanks+=8;capture(cpu,502,26,108);assert(!ready);
    // Invalid frame-buffer pointers must clear history and suppress replay.
    psx_mod_write_word(0x8009B7A0,0x800C1234);begin(&cpu,Draw);assert(!capturing && !ready);
    puts("MMX6 native sprite/camera midpoint, HUD, animation, identity, cuts and draw-order guards: PASS");
}
