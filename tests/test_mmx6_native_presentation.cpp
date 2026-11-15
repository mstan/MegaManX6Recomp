#undef NDEBUG
#include "cpu_state.h"
#include "mod_plugins.h"
#include "dma.h"
#include "presentation_gpu.h"
#include "gpu.h"
#include "gpu_view_receipt.h"
#include "presentation_view.h"
#include "gpu_gl_renderer.h"
#include "../src/mods/mmx6_native_view_observer.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>
static uint8_t test_ram[0x200000],test_scratch[1024];
static PSXModActivationCallback activation,reset_session,restore_state;
static PSXModVBlankCallback tick_callback;
struct Instruction {uint32_t pc,word;PSXModFunctionEntryCallback callback;};
static Instruction instructions[8];static unsigned instruction_count;
static DMANativeGpuReceipt receipt;static DMANativeGpuReceiptEnd receipt_end;static void* receipt_user;
static PsxPresentationProvider provider;static void* provider_user;
static GpuViewCommandReceipt command_receipt;static void* command_user;
static Mmx6NativeViewObserver view_observer;static void* view_user;
static PsxPresentationPairProvider pair_provider;static void* pair_user;
static int receipt_view=-1;static int placement_shift;static uint64_t test_bank_identity;
static GLRenderStereoDiag pair_diag;
static bool receipt_available=true,output_ready=true,split=false,banked=false;
static int wide_margin,local_scope;
static char selected_rate[24]="60";
static uint64_t texture_serial,output_serial,releases,render_calls;
static uint64_t fake_ns=900000000,fake_cycle;
static PsxPresentationRatePrepare rate_prepare;
static void* rate_user;
static bool rate_configured,rate_dispatch;
static PsxPresentationRateRequest rate_request;
static double selected_hz;
static GpuDrawingEnvironment environment;
static std::vector<PsxPresentationTriangle> rendered;
static std::vector<PsxPresentationMaterial> rendered_materials;
extern "C" {
int g_psx_render_pass_active=0;
uint32_t g_psx_vblank_cycles=564480;
uint64_t psx_get_cycle_count(void){return fake_cycle;}
uint64_t rt_now_ns(void){return fake_ns;}
int psx_presentation_gpu_set_rate(double hz,PsxPresentationRatePrepare f,void* user){
    if(f)selected_hz=hz;
    rate_configured=f && (hz==0 || hz>60);rate_prepare=rate_configured?f:nullptr;rate_user=user;
    return rate_configured?2:1;
}
int psx_presentation_gpu_rate_active(void){return rate_configured;}
void psx_presentation_gpu_rate_source_ready(void){if(rate_prepare && rate_request.deadline_ns)rate_prepare(rate_user,&rate_request);}
void psx_presentation_gpu_rate_reset(void){rate_request={};rate_dispatch=false;}
int psx_presentation_gpu_rate_request(PsxPresentationRateRequest* out){if(!rate_dispatch)return 0;*out=rate_request;return 1;}
int psx_mod_gpu_dma_memory_contains(uint32_t,uint32_t){return 0;}
uint64_t mod_texture_bank_identity(uint16_t id){return id?test_bank_identity:0;}
static uint64_t selected_receipts;
void psx_mod_counter_add(const char* name,uint32_t delta){if(!std::strcmp(name,"mmx6.interpolation.selected"))selected_receipts+=delta;}
void psx_presentation_gpu_acquire(void){}
uint64_t psx_presentation_gpu_snapshot_local_view(void){assert(g_psx_render_pass_active && local_scope);return ++texture_serial;}
void gpu_set_view_command_receipt(GpuViewCommandReceipt f,void* user){command_receipt=f;command_user=user;receipt_view=-1;}
int gpu_view_command_receipt_begin(uint32_t view){if(receipt_view>=0 || !command_receipt)return 0;receipt_view=int(view);return 1;}
int gpu_view_command_receipt_end(void){const int ok=receipt_view>=0;receipt_view=-1;return ok;}
void mmx6_native_coop_set_observer(Mmx6NativeViewObserver f,void* user){view_observer=f;view_user=user;}
void psx_presentation_gpu_set_pair_provider(PsxPresentationPairProvider f,void* user){pair_provider=f;pair_user=user;}
int psx_presentation_gpu_prepare_async(PsxPresentationPrepareReady f,void* user){f(user);return 1;}
void gl_renderer_stereo_diag(GLRenderStereoDiag* out){*out=pair_diag;}

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
int dma_set_native_gpu_receipt_scope(DMANativeGpuReceipt f,DMANativeGpuReceiptEnd end,void* user){if(!receipt_available)return 0;receipt=f;receipt_end=f?end:nullptr;receipt_user=user;return 1;}
int dma_set_native_gpu_receipt(DMANativeGpuReceipt f,void* user){return dma_set_native_gpu_receipt_scope(f,nullptr,user);}
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
static void command(uint32_t,const uint32_t*,unsigned,const GpuViewCommandMetadata&);
static void capture(CPUState& cpu,int bank,int actor_x,int actor_y,int camera_x,unsigned uv=0,uint32_t identity=0x80070000,int view_shift=0){
    placement_shift=view_shift;
    environment={};environment.area={0,uint32_t(bank*240),319,uint32_t(bank*240+239),0,bank*240};
    put(0x8009B7A0,FrameBase+bank*FrameStride);
    put(FrameBase+bank*FrameStride+0x14,uint32_t(bank*240)<<16);
    put(FrameBase+bank*FrameStride+0x18,320|(240u<<16));
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
    assert(receipt && receipt_end);receipt(receipt_user,nodes,4,words,9,1);
    for(unsigned i=1;i<4;++i)command(nodes[i].address+4,words+nodes[i].offset,3,{});
    receipt_end(receipt_user,1);
    assert(!std::memcmp(&before,&cpu,sizeof cpu));
    assert(!std::memcmp(ram_before.data(),test_ram,sizeof test_ram));
    assert(!std::memcmp(scratch_before,test_scratch,sizeof test_scratch));
    std::memset(words,0,sizeof words); // every published byte has independent ownership
}
/* Explicit backend seam for this producer test. The actual native placement
 * implementation is exercised independently by the production GPU fixture. */
static void command(uint32_t source,const uint32_t* words,unsigned n,const GpuViewCommandMetadata& input={}) {
    assert(command_receipt && receipt_view>=0);auto metadata=input;
    if(!metadata.bank)metadata.bank=mod_texture_packet_bank(source,words,n);
    const unsigned op=words[0]>>24;
    auto& d=metadata.pieces[0];d.vertices=4;d.semi=(op&2)&&op!=2?int16_t((environment.mode>>5)&3):-1;
    d.wide=wide_margin>0;d.wide_width=320+2*wide_margin;
    d.view_shift=d.wide && source!=HUDPacket+4?placement_shift:0;
    d.clip[0]=d.wide?0:int(environment.area.left);d.clip[2]=d.wide?d.wide_width-1:int(environment.area.right);
    d.clip[1]=int(environment.area.top);d.clip[3]=int(environment.area.bottom);
    int x=Frame::signed11(words[1]),y=Frame::signed11(words[1]>>16),w=16,h=16;
    if(op==2){x=int(words[1]&0x3F0);y=int((words[1]>>16)&511);w=int(words[2]&1023);h=int(words[2]>>16&511);}
    else if((op&0xE0)==0x20){w=int16_t(words[2])-x;h=int16_t(words[3]>>16)-y;}
    d.textured=(op&4)!=0 && op!=2;d.raw=(op&1)!=0;d.texpage=uint16_t(environment.mode&511);
    d.clut_x=uint16_t((words[2]>>16&63)*16);d.clut_y=uint16_t(words[2]>>22&511);
    d.color555=!d.textured;
    const uint32_t c=words[0]&0xFFFFFFu;
    for(unsigned j=0;j<4;++j){
        d.x[j]=x+((j&1)?w:0)+(op==2?0:environment.area.offset_x)+(d.wide?wide_margin+d.view_shift:0);
        d.y[j]=y+((j&2)?h:0)+(op==2?0:environment.area.offset_y);
        d.u[j]=int(words[2]&255)+((j&1)?w:0);d.v[j]=int(words[2]>>8&255)+((j&2)?h:0);
        d.color[j]=d.color555?((c>>3)&31)|((c>>11&31)<<5)|((c>>19&31)<<10):c;
    }
    metadata.piece_count=1;
    command_receipt(command_user,uint32_t(receipt_view),source,words,n,&environment,&metadata);
}
static void capture_pair(CPUState& cpu,unsigned bank,int x0,int x1,bool hud=false,bool commit=true) {
    split=true;native_begin(&cpu,NativeDraw);assert(!native_open);
    put(0x8009B7A0,FrameBase+bank*FrameStride);const uint32_t buffer=FrameBase+bank*FrameStride;
    put(buffer+0x14,0|(bank*240u<<16));put(buffer+0x18,320|(240u<<16));
    for(unsigned seat=0;seat<2;++seat) {
        environment={};environment.mode=0x20;environment.area={0,bank*240u,319,bank*240u+239,0,int(bank*240u)};
        g_psx_render_pass_active=local_scope=1;view_observer(view_user,&cpu,MMX6_NATIVE_VIEW_BEGIN,seat,1);
        assert(native_view==seat+1);
        const uint32_t clear[]={0x02000040,bank*240u<<16,320|(240u<<16)};command(0,clear,3);
        put(LayerBase+8,0);put(LayerBase+12,0);*address(LayerBase+3)=1;
        put(ActorRecord,1);*address(ActorRecord+0x14)=0;put(ActorRecord+8,uint32_t((seat?x1:x0)*65536));
        put(ActorRecord+12,20u*65536);put(ActorRecord+0x38,0x80060000);put(ActorRecord+0x3C,0x80070000);
        put(0x1F800100,ActorPacket);cpu.gpr[4]=ActorRecord;native_actor_begin(&cpu,NativeActor);
        put(0x1F800100,ActorPacket+40);native_actor_end(&cpu,NativeActorEnd);native_end(&cpu,NativeEnd);
        cpu.gpr[4]=buffer+0xEC;native_ot(&cpu,NativeOT);
        const uint32_t sprite[]={0x7C808080,xy(seat?x1:x0,20),0x79000000};
        GpuViewCommandMetadata metadata{};metadata.bank=7;metadata.live_clut=uint8_t(seat);
        command(ActorPacket+4,sprite,3,metadata);
        if(hud){
            const uint32_t meter[]={0x2800FF00,xy(20,16),xy(26,16),xy(20,bank?76:56),xy(26,bank?76:56)};
            command(HUDPacket+4,meter,5);
        }
        const uint32_t fade[]={0x2A000020,0,319,240u<<16,(240u<<16)|319};command(0,fade,5);
        view_observer(view_user,&cpu,MMX6_NATIVE_VIEW_END,seat,1);assert(!native_view);
        g_psx_render_pass_active=local_scope=0;
    }
    if(commit)view_observer(view_user,&cpu,MMX6_NATIVE_PAIR_COMMITTED,0,1);
}
static void near(double a,double b){assert(std::fabs(a-b)<.00001);}
static void activation_choices(){
    constexpr struct {const char* id;double hz;} choices[]={
        {"60",60},{"90",90},{"120",120},{"144",144},{"165",165},{"240",240},
        {"display",0},{"uncapped",0}};
    for(const auto& choice:choices){
        std::strcpy(selected_rate,choice.id);selected_hz=-1;activation();
        assert(native_enabled && receipt && provider && selected_hz==choice.hz);
        assert(native_rate==(choice.hz==0 || choice.hz>60));
        reset_session();assert(!receipt && !provider && !native_enabled && !rate_configured);
    }
    for(const char* unsupported:{"75","120junk"}){
        std::strcpy(selected_rate,unsupported);activation();
        assert(!native_enabled && !receipt && !provider && !rate_configured);
    }
    std::strcpy(selected_rate,"60");receipt_available=false;activation();
    assert(!native_enabled && !provider);receipt_available=true;
}
static void postwait_rate_publication(){
    const uint64_t period=uint64_t(g_psx_vblank_cycles)*2ull*1000000000ull/33868800ull;
    for(const char* rate:{"120","display"}){
        CPUState cpu{};std::strcpy(selected_rate,rate);activation();test_bank_identity=77;
        fake_ns=900000000;pair_diag={};pair_diag.valid=1;pair_diag.mode=2;
        pair_diag.pair_id=90;pair_diag.guest_cycle=1000000;capture_pair(cpu,0,10,100);
        tick_callback();tick_callback();
        rate_request={};rate_request.display_start_ns=1000000000;
        rate_request.display_start_cycle=pair_diag.guest_cycle;rate_request.native_cycle=pair_diag.guest_cycle;
        rate_request.pair_id=90;rate_request.pair_cycle=pair_diag.guest_cycle;
        rate_request.deadline_ns=rate_request.display_start_ns+period/4;
        pair_diag.pair_id=91;pair_diag.guest_cycle+=2ull*g_psx_vblank_cycles;
        fake_ns=1000000000+period/8;capture_pair(cpu,1,14,108,false,false);
        assert(coop_previous && coop_rate_pair==90 && !coop_output.version); // views alone cannot publish
        const auto queued=rate_request;
        view_observer(view_user,nullptr,MMX6_NATIVE_PAIR_COMMITTED,0,1);
        assert(coop_rate_pair==91 && coop_rate_ready==fake_ns && !coop_output.version); // stale request never rebound
        assert(!std::memcmp(&queued,&rate_request,sizeof queued));
        rate_request.pair_id=91;rate_request.pair_cycle=pair_diag.guest_cycle;
        rate_request.native_cycle=rate_request.display_start_cycle=pair_diag.guest_cycle;
        rate_request.deadline_ns=coop_rate_ready-1;
        psx_presentation_gpu_rate_source_ready();assert(!coop_output.version); // late source skips its missed slot
        rate_request.deadline_ns=rate_request.display_start_ns+period/4;
        const auto original=rate_request;fake_ns+=1000000000; // GPU queue delay must not create a new origin
        psx_presentation_gpu_rate_source_ready();assert(coop_output.version);
        assert(!std::memcmp(&original,&rate_request,sizeof original));
        near(rendered[2].vertices[0].x,11);near(rendered[8].vertices[0].x,102);
        uint64_t version=0;int crop[2][4]{};rate_dispatch=true;output_ready=false;
        assert(!pair_provider(pair_user,91,pair_diag.guest_cycle,0,320,240,0,&version,crop));
        output_ready=true;assert(pair_provider(pair_user,91,pair_diag.guest_cycle,0,320,240,0,&version,crop));
        assert(version==output_serial && crop[1][1]==240);rate_dispatch=false;
        rate_request.deadline_ns=rate_request.display_start_ns+period;
        psx_presentation_gpu_rate_source_ready();assert(!coop_output.version); // never extrapolate beyond native endpoint
        reset_session();assert(!coop_previous && !coop_older && !rate_configured);
    }
    std::strcpy(selected_rate,"60");fake_ns=900000000;
}
static void committed_pair_serial(){
    const uint64_t period=uint64_t(g_psx_vblank_cycles)*2ull*1000000000ull/33868800ull;
    for(const char* rate:{"120","display","60"}){
        CPUState cpu{};std::strcpy(selected_rate,rate);activation();test_bank_identity=77;
        fake_ns=900000000;pair_diag={};pair_diag.valid=1;pair_diag.mode=2;
        pair_diag.pair_id=100;pair_diag.guest_cycle=1000000;capture_pair(cpu,0,10,100);
        tick_callback();tick_callback();pair_diag.pair_id=101;pair_diag.guest_cycle+=2ull*g_psx_vblank_cycles;
        fake_ns=1000000000+period/8;capture_pair(cpu,1,14,108);
        rate_request={};rate_request.display_start_ns=1000000000;
        rate_request.native_cycle=rate_request.display_start_cycle=pair_diag.guest_cycle;
        rate_request.deadline_ns=rate_request.display_start_ns+period/4;
        rate_request.pair_id=101;rate_request.pair_cycle=pair_diag.guest_cycle;
        if(native_rate)psx_presentation_gpu_rate_source_ready();
        assert(coop_output.version && coop_previous);
        const auto committed=coop_previous->view[0]->frame.serial;
        const auto queued=rate_request;
        // Actual canonical entry begins the NEXT world. It cannot revoke an
        // owned pair whose original present/deadline still selects that pair.
        native_begin(&cpu,NativeDraw);
        assert(native_serial>committed && coop_previous->view[0]->frame.serial==committed);
        if(native_rate)psx_presentation_gpu_rate_source_ready();
        assert(coop_output.version && "committed pair survives next CPU producer");
        assert(!std::memcmp(&queued,&rate_request,sizeof queued));
        rate_dispatch=native_rate;uint64_t output=0;int crop[2][4]{};
        const uint64_t present=pair_diag.guest_cycle+g_psx_vblank_cycles;
        assert(!pair_provider(pair_user,100,pair_diag.guest_cycle,present,320,240,1,&output,crop));
        const uint64_t serial=coop_output.serial;coop_output.serial=serial+1;
        assert(!pair_provider(pair_user,101,pair_diag.guest_cycle,present,320,240,1,&output,crop));coop_output.serial=serial;
        const uint64_t epoch=coop_output.epoch;coop_output.epoch=epoch+1;
        assert(!pair_provider(pair_user,101,pair_diag.guest_cycle,present,320,240,1,&output,crop));coop_output.epoch=epoch;
        if(native_rate){
            --rate_request.deadline_ns;
            assert(!pair_provider(pair_user,101,pair_diag.guest_cycle,present,320,240,1,&output,crop));++rate_request.deadline_ns;
        }else assert(!pair_provider(pair_user,101,pair_diag.guest_cycle,coop_output.expires+1,320,240,1,&output,crop));
        output_ready=false;assert(!pair_provider(pair_user,101,pair_diag.guest_cycle,present,320,240,1,&output,crop));
        output_ready=true;
        assert(pair_provider(pair_user,101,pair_diag.guest_cycle,present,320,240,1,&output,crop) && "eligible committed pair selected after next CPU producer");
        assert(output==output_serial && crop[1][1]==240);
        assert(!pair_provider(pair_user,101,pair_diag.guest_cycle,present,320,240,1,&output,crop));
        rate_dispatch=false;reset_session();
    }
    std::strcpy(selected_rate,"60");fake_ns=900000000;
}
static void wide_coop_hud(){
    CPUState cpu{};wide_margin=53;test_bank_identity=77;std::strcpy(selected_rate,"60");activation();
    pair_diag={};pair_diag.valid=1;pair_diag.mode=2;pair_diag.pair_id=70;pair_diag.guest_cycle=1000000;
    capture_pair(cpu,0,10,100,true);tick_callback();tick_callback();
    pair_diag.pair_id=71;pair_diag.guest_cycle+=2ull*g_psx_vblank_cycles;
    capture_pair(cpu,1,14,108,true);
    assert(coop_output.version && rendered.size()==16 && rendered_materials.size()==8);
    near(rendered[2].vertices[0].x,65);near(rendered[10].vertices[0].x,157);
    near(rendered[4].vertices[0].x,73);near(rendered[4].vertices[0].y,16);
    near(rendered[12].vertices[0].x,73);near(rendered[12].vertices[0].y,256);
    near(rendered[4].vertices[2].y,76);near(rendered[12].vertices[2].y,316); // current HP, never interpolated
    assert(rendered_materials[2].clip[0]==0 && rendered_materials[2].clip[2]==425);
    assert(rendered_materials[6].clip[1]==240 && rendered_materials[6].clip[3]==479);
    assert(rendered_materials[3].semi==1 && rendered_materials[7].semi==1); // clear/world/HUD/fade painter order
    uint64_t version=0;int crop[2][4]{};
    assert(!pair_provider(pair_user,71,pair_diag.guest_cycle,pair_diag.guest_cycle+g_psx_vblank_cycles,320,240,1,&version,crop));
    assert(pair_provider(pair_user,71,pair_diag.guest_cycle,pair_diag.guest_cycle+g_psx_vblank_cycles,426,240,1,&version,crop));
    assert(version==output_serial && crop[0][0]==0 && crop[0][1]==0 && crop[0][2]==426 && crop[1][1]==240 && crop[1][2]==426);
    const uint64_t selections=selected_receipts;tick_callback();assert(selected_receipts==selections+1);
    reset_session();wide_margin=0;split=false;
}
int main(int argc,char** argv){
    assert(activation && reset_session && restore_state && tick_callback && instruction_count==2);
    if(argc==2 && !std::strcmp(argv[1],"committed-serial-only")){committed_pair_serial();puts("PASS latest committed pair survives in-flight CPU producer at120/display/60; epoch/pair/deadline/readiness and original timestamp gates retained");return 0;}
    if(argc==2 && !std::strcmp(argv[1],"wide-coop-hud-only")){wide_coop_hud();postwait_rate_publication();puts("PASS original postwait publication,120/display queued timestamp/readiness, real expanded per-view producer, independent motion, two current HUDs, painter order and owned426x480 pair");return 0;}
    if(argc==2 && !std::strcmp(argv[1],"activation-only")){
        activation_choices();puts("PASS every released rate selector, legacy display alias, unsupported values and unavailable native service");return 0;
    }
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
    // Adaptive aspect uses the exact current native placements, including the
    // authored edge-origin change, with centered current UI.
    reset_session();activation();wide_margin=53;
    capture(cpu,0,110,20,100);tick_callback();tick_callback();
    capture(cpu,1,114,22,102,32,0x80070000,7);
    assert(native_output.version && native_previous->frame.wide);
    near(rendered[2].vertices[0].x,67.5);near(rendered[4].vertices[0].x,253);
    assert(provider(provider_user,0,0,426,240,1,crop) && crop[0]==0 && crop[1]==240 && crop[2]==426);
    reset_session();activation();wide_margin=0;
    local_scope=1;const auto serial=native_serial.load();native_begin(&cpu,NativeDraw);assert(native_serial==serial);local_scope=0;
    reset_session();assert(!receipt && !provider && !native_enabled);
    assert(releases==texture_serial);
    activation();test_bank_identity=77;
    pair_diag.valid=1;pair_diag.mode=2;pair_diag.pair_id=10;pair_diag.guest_cycle=1000000;
    capture_pair(cpu,0,10,100);assert(!coop_output.version);
    pair_diag.pair_id=11;pair_diag.guest_cycle+=2ull*g_psx_vblank_cycles;
    tick_callback();tick_callback();capture_pair(cpu,1,14,108);
    assert(coop_output.version && rendered.size()==12 && rendered_materials.size()==6);
    near(rendered[2].vertices[0].x,12);near(rendered[8].vertices[0].x,104);near(rendered[8].vertices[0].y,260);
    assert(rendered_materials[1].texture_bank==7 && rendered_materials[1].bank_identity==77);
    assert(!(rendered_materials[1].flags&PSX_PRESENTATION_BANK_LIVE_CLUT));
    assert(rendered_materials[4].flags&PSX_PRESENTATION_BANK_LIVE_CLUT);
    assert(rendered_materials[2].semi==1 && rendered_materials[5].semi==1);
    uint64_t output=0;int pair_crop[2][4]{};
    const uint64_t midpoint=pair_diag.guest_cycle+g_psx_vblank_cycles;
    assert(!pair_provider(pair_user,10,pair_diag.guest_cycle,midpoint,320,240,1,&output,pair_crop));
    assert(!pair_provider(pair_user,11,pair_diag.guest_cycle,midpoint,320,240,0,&output,pair_crop));
    output_ready=false;assert(!pair_provider(pair_user,11,pair_diag.guest_cycle,midpoint,320,240,1,&output,pair_crop));
    output_ready=true;assert(pair_provider(pair_user,11,pair_diag.guest_cycle,midpoint,320,240,1,&output,pair_crop));
    assert(pair_crop[1][0]==0 && pair_crop[1][1]==240 && output==output_serial);
    assert(!pair_provider(pair_user,11,pair_diag.guest_cycle,midpoint,320,240,1,&output,pair_crop));
    view_observer(view_user,nullptr,MMX6_NATIVE_PAIR_CANCEL,0,0);assert(!coop_output.version && !coop_previous);
    reset_session();assert(!command_receipt && !view_observer && !pair_provider && releases==texture_serial);
    split=false;
    std::strcpy(selected_rate,"120");activation();assert(native_enabled && provider && native_rate);
    rate_request={};capture(cpu,0,110,20,100);tick_callback();tick_callback();
    capture(cpu,1,114,22,102,32);
    const uint64_t period=uint64_t(g_psx_vblank_cycles)*2ull*1000000000ull/33868800ull;
    rate_request.display_start_ns=1000000000;rate_request.display_start_cycle=1;
    rate_request.x=rate_request.y=0;rate_request.width=320;rate_request.height=240;
    for(unsigned quarter:{1u,3u}) {
        rate_request.deadline_ns=rate_request.display_start_ns+period*quarter/4;
        psx_presentation_gpu_rate_source_ready();assert(native_output.version);
        near(rendered[2].vertices[0].x,10+double(quarter)/2);
        near(rendered[2].vertices[0].uv[0],32); // current animation at every output phase
        rate_dispatch=true;output_ready=false;assert(!provider(provider_user,0,0,320,240,0,crop));
        output_ready=true;assert(provider(provider_user,0,0,320,240,0,crop));rate_dispatch=false;
    }
    rate_request.deadline_ns=rate_request.display_start_ns+period;
    psx_presentation_gpu_rate_source_ready();assert(!native_output.version); // native endpoint, never extrapolate
    rate_request.deadline_ns=rate_request.display_start_ns+period/2;
    native_previous->ready_ns=rate_request.deadline_ns+1;
    psx_presentation_gpu_rate_source_ready();assert(!native_output.version); // late source never shifts timeline
    reset_session();assert(releases==texture_serial && !rate_configured);
    activation();rate_request={};pair_diag.pair_id=30;pair_diag.guest_cycle=1000000;
    capture_pair(cpu,0,10,100);tick_callback();tick_callback();
    pair_diag.pair_id=31;pair_diag.guest_cycle+=2ull*g_psx_vblank_cycles;
    capture_pair(cpu,1,14,108);
    rate_request.display_start_ns=1000000000;rate_request.deadline_ns=1000000000+period/4;
    rate_request.pair_id=31;rate_request.pair_cycle=pair_diag.guest_cycle;
    psx_presentation_gpu_rate_source_ready();assert(coop_output.version);
    near(rendered[2].vertices[0].x,11);near(rendered[8].vertices[0].x,102);near(rendered[8].vertices[0].y,260);
    rate_dispatch=true;
    assert(!pair_provider(pair_user,30,pair_diag.guest_cycle,0,320,240,0,&output,pair_crop));
    assert(pair_provider(pair_user,31,pair_diag.guest_cycle,0,320,240,0,&output,pair_crop));
    rate_dispatch=false;restore_state();assert(!coop_output.version && !coop_older && !rate_request.deadline_ns);
    reset_session();assert(releases==texture_serial);
    activation_choices();
    puts("PASS X6 native producer: real immutable scene/draw midpoint, current animation/HUD/order, resource ownership, cuts/identity, one native-timeline midpoint, readiness/restore/unload and honest unsupported/reference fallback; no guest replay or writes");
}
