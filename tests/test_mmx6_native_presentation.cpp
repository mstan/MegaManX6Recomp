#undef NDEBUG
#include "cpu_state.h"
#include "mod_plugins.h"
#include "dma.h"
#include "presentation_gpu.h"
#include "gpu.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>
static uint8_t test_ram[0x200000],test_scratch[1024];
static PSXModActivationCallback activation,reset_session,restore_state;
static PSXModVBlankCallback tick_callback;
struct Instruction {uint32_t pc,word;PSXModFunctionEntryCallback callback;};
static Instruction instructions[8];static unsigned instruction_count;
static DMANativeGpuReceipt receipt;static void* receipt_user;
static PsxPresentationProvider provider;static void* provider_user;
static bool receipt_available=true,output_ready=true,split=false,banked=false;
static int wide_margin,local_scope;
static char selected_rate[24]="60";
static uint64_t texture_serial,output_serial,releases,render_calls;
static GpuDrawingEnvironment environment;
static std::vector<PsxPresentationTriangle> rendered;
static std::vector<PsxPresentationMaterial> rendered_materials;
extern "C" {
int g_psx_render_pass_active=0;
int psx_mod_register_activation_plugin(const char*,PSXModActivationCallback f){activation=f;return 1;}
int psx_mod_register_session_reset_plugin(const char*,PSXModActivationCallback f){reset_session=f;return 1;}
int psx_mod_register_savestate_plugin(const char*,PSXModActivationCallback f){restore_state=f;return 1;}
int psx_mod_register_vblank_plugin(const char*,PSXModVBlankCallback f){tick_callback=f;return 1;}
int psx_mod_register_function_entry_plugin(const char*,uint32_t,PSXModFunctionEntryCallback){return 1;}
int psx_mod_register_instruction_plugin(const char*,uint32_t pc,uint32_t word,PSXModFunctionEntryCallback f){
    instructions[instruction_count++]={pc,word,f};return 1;
}
int psx_mod_option_value(const char*,const char*,const char*,char* out,uint32_t n){std::snprintf(out,n,"%s",selected_rate);return 1;}
static uint8_t* address(uint32_t a){return (a&0x1FFFFC00u)==0x1F800000u?test_scratch+(a&1023):test_ram+(a&0x1FFFFF);}
uint8_t psx_mod_read_byte(uint32_t a){return *address(a);}
uint16_t psx_mod_read_half(uint32_t a){uint16_t v;std::memcpy(&v,address(a),2);return v;}
uint32_t psx_mod_read_word(uint32_t a){uint32_t v;std::memcpy(&v,address(a),4);return v;}
int32_t psx_mod_widescreen_view_x_margin(void){return wide_margin;}
int psx_mod_local_view_scope(void){return local_scope;}
int gpu_last_frame_vertical_split_screen(void){return split;}
void gpu_get_drawing_environment(GpuDrawingEnvironment* out){*out=environment;}
int gr_texture_filter(void){return 0;}
int gl_renderer_accurate_blending(void){return 0;}
int gpu_gp0_command_word_count(uint8_t op){
    if(op==0 || op==1 || op>=0xE1)return 1;
    if(op==2)return 3;
    if((op&0xE0)==0x60){unsigned size=(op>>3)&3;return size?((op&4)?3:2):((op&4)?4:3);}
    if((op&0xE0)==0x20){unsigned n=(op&8)?4:3;return int(n*(1+unsigned((op&4)!=0)+unsigned((op&16)!=0))+unsigned(!(op&16)));}
    return 4;
}
int gpu_ws_copy_presented_ui(uint32_t,const uint32_t*,uint32_t,int32_t[4],int32_t[4],unsigned,int){return 0;}
uint16_t mod_texture_packet_bank(uint32_t,const uint32_t*,uint32_t){return banked?1:0;}
int dma_set_native_gpu_receipt(DMANativeGpuReceipt f,void* user){if(!receipt_available)return 0;receipt=f;receipt_user=user;return 1;}
int psx_presentation_gpu_snapshot_async(PsxPresentationSnapshotReady ready,void* user){ready(user,++texture_serial);return 1;}
void psx_presentation_gpu_release(uint64_t v){assert(v);++releases;}
void psx_presentation_gpu_set_provider(PsxPresentationProvider f,void* user){provider=f;provider_user=user;}
int psx_presentation_gpu_render(const PsxPresentationTriangle* t,uint32_t n,const PsxPresentationMaterial* m,uint32_t count){
    rendered.assign(t,t+n);rendered_materials.assign(m,m+count);++render_calls;++output_serial;return 1;
}
uint64_t psx_presentation_gpu_output_version(void){return output_serial;}
int psx_presentation_gpu_output_ready(uint64_t v){return output_ready && v==output_serial;}
}
#include "../src/mods/mmx6_frame_interpolation_plugin.cpp"
static void put(uint32_t a,uint32_t v){std::memcpy(address(a),&v,4);}
static uint32_t xy(int x,int y){return uint16_t(x)|(uint32_t(uint16_t(y))<<16);}
constexpr uint32_t ActorRecord=0x800970A0,ActorPacket=0x000B0000,HUDPacket=0x000B1000,BackgroundPacket=0x000B2000;
static void close_instruction(CPUState& cpu,uint32_t pc){
    for(unsigned i=0;i<instruction_count;++i)if(instructions[i].pc==pc){assert(instructions[i].word==0x03E00008u);instructions[i].callback(&cpu,pc);return;}
    assert(false);
}
static void capture(CPUState& cpu,int bank,int actor_x,int actor_y,int camera_x,unsigned uv=0,uint32_t identity=0x80070000){
    environment={};environment.area={0,uint32_t(bank*240),319,uint32_t(bank*240+239),0,bank*240};
    put(0x8009B7A0,FrameBase+bank*FrameStride);
    put(LayerBase+8,uint32_t(camera_x*65536));put(LayerBase+12,0);
    *address(LayerBase+3)=1;
    put(ActorRecord,1);*address(ActorRecord+0x14)=0;
    put(ActorRecord+8,uint32_t(actor_x*65536));put(ActorRecord+12,uint32_t(actor_y*65536));
    put(ActorRecord+0x38,0x80060000);put(ActorRecord+0x3C,identity);
    native_begin(&cpu,NativeDraw);assert(native_open);
    put(0x1F800108,BackgroundPacket);cpu.gpr[4]=0;native_bg_begin(&cpu,NativeBg);
    put(0x1F800108,BackgroundPacket+16);native_bg_end(&cpu,NativeBgEnd);
    put(0x1F800100,ActorPacket);cpu.gpr[4]=ActorRecord;native_actor_begin(&cpu,NativeActor);
    put(0x1F800100,ActorPacket+0x28);close_instruction(cpu,NativeActorEnd);
    close_instruction(cpu,NativeEnd);assert(native_complete);
    cpu.gpr[4]=native_buffer+0xEC;native_ot(&cpu,NativeOT);assert(native_armed);
    uint32_t words[]={0x7C808080,xy(150-camera_x,40),0x79000000,
                      0x7C808080,xy(actor_x-camera_x,actor_y),0x79000000|uv,
                      0x7C808080,xy(200,20),0x79000010};
    DMANativeGpuNode nodes[]={{native_head,0,0},{BackgroundPacket,0x03000000u,0},
                            {ActorPacket,0x03000000u,3},{HUDPacket,0x03FFFFFFu,6}};
    const CPUState before=cpu;std::vector<uint8_t> ram_before(test_ram,test_ram+sizeof test_ram);
    uint8_t scratch_before[1024];std::memcpy(scratch_before,test_scratch,sizeof test_scratch);
    assert(receipt);receipt(receipt_user,nodes,4,words,9,1);
    assert(!std::memcmp(&before,&cpu,sizeof cpu));
    assert(!std::memcmp(ram_before.data(),test_ram,sizeof test_ram));
    assert(!std::memcmp(scratch_before,test_scratch,sizeof test_scratch));
    std::memset(words,0,sizeof words); // every published byte has independent ownership
}
static void near(double a,double b){assert(std::fabs(a-b)<.00001);}
int main(){
    assert(activation && reset_session && restore_state && tick_callback && instruction_count==2);
    CPUState cpu{};activation();assert(native_enabled && receipt && provider);
    capture(cpu,0,110,20,100);
    assert(render_calls==0);
    tick_callback();tick_callback();capture(cpu,1,114,22,102,32);
    assert(render_calls==1 && rendered.size()==6 && rendered_materials.size()==3);
    near(rendered[0].vertices[0].x,49); // world tile follows the authored layer camera
    near(rendered[2].vertices[0].x,11);near(rendered[2].vertices[0].y,261);
    near(rendered[2].vertices[0].uv[0],32); // newer animation tile remains exact
    near(rendered[4].vertices[0].x,200);near(rendered[4].vertices[0].y,260); // current HUD
    for(const auto& m:rendered_materials)assert(m.texture_version==2);
    int crop[4]{};output_ready=false;assert(!provider(provider_user,0,0,320,240,1,crop));
    output_ready=true;assert(!provider(provider_user,0,0,320,240,0,crop));
    split=true;assert(!provider(provider_user,0,0,320,240,1,crop));split=false;
    assert(provider(provider_user,0,0,320,240,1,crop));
    assert(crop[0]==0 && crop[1]==240 && crop[2]==320 && crop[3]==240);
    assert(!provider(provider_user,0,0,320,240,1,crop)); // at most one midpoint per native interval

    tick_callback();tick_callback();capture(cpu,0,116,24,104,48,0x80071000);
    assert(render_calls==2);near(rendered[2].vertices[0].x,12); // changed actor identity snaps
    tick_callback();tick_callback();capture(cpu,1,500,26,106,64,0x80071000);
    near(rendered[2].vertices[0].x,394); // teleport/cut never travels through the scene
    restore_state();assert(!provider(provider_user,0,0,320,240,1,crop));

    // Unsupported scene state neither substitutes a partial image nor touches sound/guest state.
    const auto rendered_before=render_calls;
    tick_callback();tick_callback();banked=true;capture(cpu,0,502,26,108);banked=false;
    assert(render_calls==rendered_before && !provider(provider_user,0,240,320,240,1,crop));
    wide_margin=100;native_begin(&cpu,NativeDraw);assert(!native_open);wide_margin=0;
    local_scope=1;const auto serial=native_serial.load();native_begin(&cpu,NativeDraw);assert(native_serial==serial);local_scope=0;
    reset_session();assert(!receipt && !provider && !native_enabled);
    assert(releases==texture_serial);
    std::strcpy(selected_rate,"120");activation();assert(!native_enabled && !provider);
    std::strcpy(selected_rate,"60");receipt_available=false;activation();assert(!native_enabled && !provider);
    puts("PASS X6 native producer: real immutable scene/draw midpoint, current animation/HUD/order, resource ownership, cuts/identity, one native-timeline midpoint, readiness/restore/unload and honest unsupported/reference fallback; no guest replay or writes");
}
