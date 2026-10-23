/* Actual capture TU, fake external read-only engine boundary, real worker and
 * private files. Python independently validates every successful native stream.
 * No game bytes, windows, SIO mutation, memory-card import or guest calls. */
#include "mod_plugins.h"
#undef PSX_MOD_CONSTRUCTOR
#define PSX_MOD_CONSTRUCTOR(name) static void name(void)
#include "../src/mods/mmx6_diagnostics.cpp"
#include <cassert>
#include <cstring>
#include <iostream>

static PSXSessionDiagnosticsStartFn start_fn;
static PSXSessionDiagnosticsEndFn stop_fn;
static PSXModFunctionEntryCallback native_fn;
static unsigned registrations,card_exports,runtime_reads,card_presence_reads;
static bool plugin_selected=true;
static uint64_t test_cycles=10;
static uint32_t test_tick=3,taint;
static std::thread::id owner;
static uint8_t test_ram[0x200000];
static void owned(){assert(std::this_thread::get_id()==owner);}
extern "C" int psx_game_register_session_diagnostics(PSXSessionDiagnosticsStartFn a,PSXSessionDiagnosticsEndFn b){
    assert(!start_fn&&!stop_fn);start_fn=a;stop_fn=b;return 1;}
extern "C" int psx_mod_register_instruction_plugin(const char *id,uint32_t address,uint32_t word,PSXModFunctionEntryCallback f){
    assert(!std::strcmp(id,registrations?"mmx6.local-coop.prototype":"mmx6.diagnostics"));
    assert(address==0x80012C44&&word==0x8FBF0010);native_fn=f;++registrations;return 1;}
extern "C" int mod_runtime_diagnostics_plugin_active(const char *id){owned();assert(id&&*id);return plugin_selected;}
extern "C" uint64_t psx_get_cycle_count(){owned();return test_cycles;}
extern "C" uint32_t psx_netplay_sim_tick(){owned();return test_tick;}
extern "C" uint32_t psx_session_input_taint_get(){owned();return taint;}
extern "C" void psx_session_input_taint_add(uint32_t flags){owned();taint|=flags;}
extern "C" int memcard_is_present(int slot){owned();++card_presence_reads;return slot==0;}
extern "C" int memcard_export_raw(int slot,uint8_t *out){owned();assert(slot==0);++card_exports;
    for(unsigned i=0;i<MEMCARD_SIZE;++i)out[i]=static_cast<uint8_t>(i);
    return 0;}
extern "C" uint16_t psx_mod_read_half(uint32_t address){owned();++runtime_reads;const auto p=address&0x1FFFFFu;
    assert(p<sizeof test_ram-1);return uint16_t(test_ram[p]|unsigned(test_ram[p+1])<<8);}
extern "C" uint32_t psx_mod_read_word(uint32_t address){return psx_mod_read_half(address)|uint32_t(psx_mod_read_half(address+2))<<16;}
static void word(uint32_t address,uint32_t value){for(unsigned i=0;i<4;++i)test_ram[(address+i)&0x1FFFFFu]=uint8_t(value>>(8*i));}
static void half(uint32_t address,uint16_t value){test_ram[address&0x1FFFFFu]=uint8_t(value);test_ram[(address+1)&0x1FFFFFu]=uint8_t(value>>8);}
struct MemorySink:Mmx6Capture::Sink{
    std::string bytes;bool short_write=false;
    bool write(const std::string& row)override{if(short_write){bytes+=row.substr(0,row.size()/2);return false;}bytes+=row;return true;}
};
template<class F>static void rejects(F f){bool caught=false;try{f();}catch(const std::exception&){caught=true;}assert(caught);}
static Mmx6Capture::Identity identity(){Mmx6Capture::Identity id;id.image=std::string(64,'1');id.manifest=std::string(64,'2');
    id.settings=std::string(64,'3');id.content=std::string(64,'4');id.simulation=std::string(64,'5');id.execution="fixture-execution";return id;}
static void codec_negatives(){
    using namespace Mmx6Capture;
    Queue<2> queue;Event a;a.order=7;assert(queue.push(a));a.order=8;assert(queue.push(a));
    a.order=9;assert(!queue.push(a));Event out;assert(queue.pop(out)&&out.order==7);
    assert(queue.push(a));assert(queue.pop(out)&&out.order==8);assert(queue.pop(out)&&out.order==9);assert(!queue.pop(out));
    /* Deterministically publish the last accepted event after the first empty
     * pop but before normal/failure terminal observation. The exact production
     * drain helper must re-read, retain that event and only then finish. */
    for(bool failure_terminal:{false,true}){
        Queue<2> tail;Event last;last.order=failure_terminal?22:21;
        unsigned observed=0;
        const Take first=take_before_terminal(tail,out,[&]{++observed;assert(tail.push(last));return true;});
        assert(first==Take::Ready&&out.order==last.order&&observed==1);
        assert(take_before_terminal(tail,out,[]{return true;})==Take::Terminal);
    }
    auto id=identity();MemorySink sink;Encoder encoder(sink,id);Event n;n.caller=0x80012220;n.cycles=10;
    encoder.append(n);auto c=n;c.kind=1;c.native=0;c.order=1;c.consumer=4;c.buttons=8;encoder.append(c);encoder.finish("");
    rejects([&]{encoder.append(c);});rejects([&]{encoder.finish("");});
    for(unsigned variant=0;variant<7;++variant){MemorySink bad;Encoder e(bad,id);auto event=n;
        if(variant==0)event.order=1;
        if(variant==1)event.native=1;
        if(variant==2)event.caller=0x80012224;
        if(variant==3)event.pads[0][2]=1;
        if(variant==4)event.kind=2;
        if(variant==5){event.kind=1;event.consumer=0;}if(variant==6)bad.short_write=true;
        rejects([&]{e.append(event);});rejects([&]{e.finish("");});}
    MemorySink bad;Encoder e(bad,id);e.append(n);n.order=1;n.native=1;n.cycles=9;
    rejects([&]{e.append(n);});rejects([&]{e.finish("");});
    MemorySink invalid;id.image="unknown";rejects([&]{Encoder e(invalid,id);});assert(invalid.bytes.empty());
    Queue<128> concurrent;constexpr unsigned count=20000;
    std::thread consumer([&]{for(unsigned i=0;i<count;){Event read;if(concurrent.pop(read)){assert(read.order==i);++i;}}});
    for(unsigned i=0;i<count;){Event event;event.order=i;if(concurrent.push(event))++i;}
    consumer.join();
}
int main(int argc,char **argv){
    assert(argc>=2);owner=std::this_thread::get_id();codec_negatives();mmx6_register_diagnostics();
    assert(start_fn&&stop_fn&&native_fn&&registrations==2);
    std::string settings="{\"actual\":\"settings\"}\n",content="{\"actual\":\"content\"}\n",implementation="{\"actual\":\"implementation\"}\n";
    PSXSessionDiagnosticsStart s{};s.schema=1;s.session_epoch=1;s.envelope_complete=1;s.output_root=argv[1];
    std::strcpy(s.image_sha256,std::string(64,'1').c_str());std::strcpy(s.manifest_sha256,std::string(64,'2').c_str());
    std::strcpy(s.execution_id,"fixture-execution");s.settings={settings.data(),settings.size()};s.content={content.data(),content.size()};
    s.implementation={implementation.data(),implementation.size()};s.manifest_schema=1;
    // Disabled and unsupported starts may not export cards or create a worker.
    plugin_selected=false;start_fn(&s);assert(!active.load()&&!card_exports);plugin_selected=true;
    s.envelope_complete=0;s.unavailable_reason="fixture unsupported startup";start_fn(&s);assert(!active.load()&&!card_exports);
    s.envelope_complete=1;s.unavailable_reason="";start_fn(&s);assert(active.load());
    assert(card_exports==1&&card_presence_reads==2);
    // Mutating borrowed startup bytes after callback cannot change artifacts.
    settings[2]='X';content[2]='Y';implementation[2]='Z';
    CPUState cpu{};cpu.gpr[29]=0x801FFF00;cpu.gpr[31]=0x80012C44;word(cpu.gpr[29]+16,0x80012220);
    word(0x80097420,20);const CPUState before=cpu;
    native_fn(&cpu,0x80012C44);assert(!std::memcmp(&cpu,&before,sizeof cpu));
    for(unsigned tag=0;tag<6;++tag){++test_cycles;mmx6_diagnostics_p2(tag,8,0);}
    ++test_cycles;word(cpu.gpr[29]+16,0x8001A834);half(0x800C456C,0x800);half(0x800C4570,0x800);
    native_fn(&cpu,0x80012C44);++test_cycles;mmx6_diagnostics_p2(0,8,0);
    if(argc>2&&!std::strcmp(argv[2],"--atexit")){
        std::atexit([]{stop_fn(1,PSX_SESSION_DIAGNOSTICS_END_PROCESS_EXIT);});std::exit(0);}
    stop_fn(99,0);assert(active.load());stop_fn(1,0);assert(!active.load());stop_fn(1,0);
    // Rematch gets a fresh native ordinal; online data is annotated, not replay.
    s.session_epoch=2;s.netplay=1;std::strcpy(s.profile_id,"fixture-profile");s.profile_revision=2;
    std::strcpy(s.selected_sha256,std::string(64,'6').c_str());start_fn(&s);native_fn(&cpu,0x80012C44);stop_fn(2,0);
    // Fixture contamination keeps an explicit failed prefix, never a success.
    s.session_epoch=3;start_fn(&s);native_fn(&cpu,0x80012C44);mmx6_diagnostics_p2(0,4,1);stop_fn(3,0);
    assert(taint&PSX_INPUT_TAINT_GAME_MAILBOX);taint=0;
    s.session_epoch=4;start_fn(&s);mmx6_diagnostics_p2(0,0,0);stop_fn(4,0);
    s.session_epoch=5;start_fn(&s);cpu.gpr[29]=0x1F801000;native_fn(&cpu,0x80012C44);stop_fn(5,0);
    // End can race bounded owner publication without freeing live storage.
    s.session_epoch=6;start_fn(&s);cpu.gpr[29]=0x801FFF00;native_fn(&cpu,0x80012C44);
    std::thread finish([]{stop_fn(6,0);});for(unsigned i=0;i<2000;++i)mmx6_diagnostics_p2(0,8,0);finish.join();
    assert(!active.load());
    // A real non-directory destination fails without touching the sentinel or
    // throwing into the simulation owner. Its raw error is retained by Python.
    const auto sentinel=std::filesystem::path(argv[1])/"not-a-directory";
    artifact(sentinel,"preserve existing output\n");const std::string bad_root=sentinel.string();
    s.session_epoch=7;s.output_root=bad_root.c_str();start_fn(&s);native_fn(&cpu,0x80012C44);stop_fn(7,0);
    s.session_epoch=8;s.output_root=argv[1];start_fn(&s);native_fn(&cpu,0x80012C44);
    stop_fn(8,PSX_SESSION_DIAGNOSTICS_END_STATE_REPLACED);assert(!active.load());
    std::cout<<"actual MMX6 capture worker/codec/ownership/failure fixture PASS\n";
}
