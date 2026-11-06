/* Actual diagnostics TU, external SDK boundary doubles and real private files.
 * No game binary or original execution is modeled. Native qualification is
 * separate; this exercises admission, supply, refusal and terminal ownership. */
#include "mod_plugins.h"
#undef PSX_MOD_CONSTRUCTOR
#define PSX_MOD_CONSTRUCTOR(name) static void name(void)
#include "../src/mods/mmx6_diagnostics.cpp"
#include <cassert>
#include <iostream>

static PSXSessionDiagnosticsStartFn start_fn;
static PSXSessionDiagnosticsEndFn stop_fn;
static PSXModFunctionEntryCallback native_fn;
static PSXModFunctionEntryCallback standalone_native_fn;
static unsigned sequence_calls;
static uint16_t sequence_buttons;
static std::thread::id owner;
static uint8_t ram[0x200000];
static uint64_t cycle=10;
static uint32_t taint;
static unsigned writes,ends;
static bool present=true,selected=true;
static std::string card_path,refusal,scenario;
static uint8_t card[MEMCARD_SIZE];
static void owned(){assert(std::this_thread::get_id()==owner);}
static void env(const char *key,const std::string& value){
#ifdef _WIN32
    assert(_putenv_s(key,value.c_str())==0);
#else
    assert(setenv(key,value.c_str(),1)==0);
#endif
}
extern "C" int psx_game_register_session_diagnostics(PSXSessionDiagnosticsStartFn,PSXSessionDiagnosticsEndFn){assert(false);return 0;}
extern "C" int psx_game_register_guarded_session_diagnostics(PSXSessionDiagnosticsStartFn a,PSXSessionDiagnosticsEndFn b){
    assert(!start_fn&&!stop_fn);start_fn=a;stop_fn=b;return 1;}
extern "C" int psx_session_diagnostics_refuse_replay(const char *why){owned();if(refusal.empty())refusal=why?why:"missing reason";return 1;}
extern "C" void psx_session_diagnostics_end(int reason){owned();assert(!callbacks.load()&&!active_replay.load());
    ++ends;stop_fn(current_epoch,reason);}
extern "C" void psx_fatal_halt(const char *why){owned();assert(why&&*why&&!callbacks.load()&&!active_replay.load()&&!current_replay);
    assert(writes==(scenario=="taint"||scenario=="tag"||scenario=="mailbox"?6u:0u));
    assert(ends==1);std::fprintf(stderr,"expected terminal replay failure: %s\n",why);std::exit(42);}
extern "C" void psx_crash_trace_set_exit_origin(const char *why){owned();assert(!std::strcmp(why,"mmx6_native_consumption_replay_end"));
    assert(ends==1&&!callbacks.load()&&!active_replay.load()&&!current_replay);}
extern "C" int psx_mod_register_instruction_plugin(const char *id,uint32_t address,uint32_t instruction,PSXModFunctionEntryCallback callback){
    assert(address==0x80012C44&&instruction==0x8FBF0010);
    auto& slot=!std::strcmp(id,"mmx6.local-coop.prototype")?native_fn:standalone_native_fn;
    assert(!std::strcmp(id,"mmx6.local-coop.prototype")||!std::strcmp(id,"mmx6.diagnostics"));
    if(slot)return 0; // Actual SDK refuses a second hook for this plugin/address.
    slot=callback;return 1;}
extern "C" int mod_runtime_diagnostics_plugin_active(const char*){owned();return selected;}
extern "C" uint64_t psx_get_cycle_count(){owned();return cycle;}
extern "C" uint32_t psx_netplay_sim_tick(){owned();assert(false);return 0;}
extern "C" uint32_t psx_session_input_taint_get(){owned();return taint;}
extern "C" void psx_session_input_taint_add(uint32_t bits){owned();taint|=bits;}
extern "C" int memcard_is_present(int slot){owned();return !slot&&present;}
extern "C" int memcard_export_raw(int slot,uint8_t *out){owned();assert(!slot&&present);std::memcpy(out,card,sizeof card);return 0;}
extern "C" int memcard_debug_info(int slot,const char **path,uint8_t*,int*,int*){owned();if(path)*path=slot?"":card_path.c_str();return 0;}
extern "C" uint16_t psx_mod_read_half(uint32_t address){owned();const auto p=address&0x1FFFFFu;assert(p<sizeof ram-1);
    return uint16_t(ram[p]|uint16_t(ram[p+1])<<8);}
extern "C" uint32_t psx_mod_read_word(uint32_t address){return psx_mod_read_half(address)|uint32_t(psx_mod_read_half(address+2))<<16;}
extern "C" void mmx6_coop_checkpoint_native_input(CPUState*,uint32_t address){
    owned();assert(address==0x80012C44);++sequence_calls;
    sequence_buttons=psx_mod_read_half(0x800C456C);}
static void half(uint32_t address,uint16_t value){ram[address&0x1FFFFFu]=uint8_t(value);ram[(address+1)&0x1FFFFFu]=uint8_t(value>>8);}
static void word(uint32_t address,uint32_t value){for(unsigned i=0;i<4;++i)ram[(address+i)&0x1FFFFFu]=uint8_t(value>>(8*i));}
extern "C" void psx_mod_write_half(uint32_t address,uint16_t value){owned();assert(address==0x800C456C||address==0x800C456E||
    address==0x800C4570||address==0x800C4758||address==0x800C475A||address==0x800C475C);++writes;half(address,value);}
struct Memory:Mmx6Capture::Sink{std::string bytes;bool write(const std::string& row)override{bytes+=row;return true;}};
static void write_native(const Mmx6Capture::Event& event,CPUState& cpu){
    cpu.gpr[29]=0x801FFF00;cpu.gpr[31]=0x80012C44;word(cpu.gpr[29]+16,event.caller);word(0x80097420,event.frame);
    const uint32_t bases[]={0x800C456C,0x800C4758};
    for(unsigned p=0;p<2;++p){half(bases[p],0xFFFF);half(bases[p]+2,event.pads[p][1]);half(bases[p]+4,0);}}
int main(int argc,char **argv){
    assert(argc==3);owner=std::this_thread::get_id();scenario=argv[2];
    const auto profile=std::filesystem::absolute(argv[1]);assert(!std::filesystem::exists(profile));
    std::filesystem::create_directories(profile/"replay");std::filesystem::create_directories(profile/"saves");
    for(unsigned i=0;i<sizeof card;++i)card[i]=uint8_t(i);
    std::string settings="{\"resolved\":\"settings\"}\n",content="{\"resolved\":\"content\"}\n",implementation="{\"resolved\":\"implementation\"}\n";
    PSXSessionDiagnosticsStart s{};s.schema=1;s.session_epoch=1;s.envelope_complete=1;s.manifest_schema=1;
    const auto root=(profile/"state").string();s.output_root=root.c_str();s.unavailable_reason="unsupported fixture scope";
    std::strcpy(s.image_sha256,std::string(64,'1').c_str());std::strcpy(s.manifest_sha256,std::string(64,'2').c_str());
    std::strcpy(s.execution_id,"fixture-execution");s.settings={settings.data(),settings.size()};s.content={content.data(),content.size()};
    s.implementation={implementation.data(),implementation.size()};card_path=(profile/"saves/card1.mcd").string();
    Mmx6Capture::Identity id;id.image=s.image_sha256;id.manifest=s.manifest_sha256;id.execution=s.execution_id;
    id.settings=Mmx6Capture::sha(settings.data(),settings.size());id.content=Mmx6Capture::sha(content.data(),content.size());
    id.simulation=Mmx6Capture::sha(implementation.data(),implementation.size());id.cards[0]=Mmx6Capture::sha(card,sizeof card);
    artifact(profile/"replay/settings.json",settings);artifact(profile/"replay/content.json",content);
    artifact(profile/"replay/simulation-contract.json",implementation);artifact(profile/"replay/card1.initial.mcd",card,sizeof card);
    artifact(profile/"saves/card1.mcd",card,sizeof card);
    Mmx6Capture::Event n;n.caller=0x80012220;n.frame=20;n.cycles=10;n.pads[0][0]=n.pads[0][2]=0x800;
    n.pads[1][0]=n.pads[1][2]=0x400;
    std::vector<Mmx6Capture::Event> events{n};
    for(unsigned i=0;i<6;++i){Mmx6Capture::Event c;c.kind=1;c.consumer=uint8_t(i);c.order=i+1;c.cycles=11+i;c.buttons=uint16_t(1u<<i);events.push_back(c);}
    n.order=7;n.native=1;n.cycles=30;n.caller=0x8001A834;n.pads[0][1]=0x800;n.pads[0][2]=0;
    n.pads[1][0]=n.pads[1][2]=0;n.pads[1][1]=0x400;events.push_back(n);
    Memory sink;Mmx6Capture::Encoder encoder(sink,id);for(const auto& event:events)encoder.append(event);
    encoder.finish(scenario=="failed-trace"?"fixture input":"");
    if(scenario=="truncated")sink.bytes.pop_back();
    artifact(profile/"replay/inputs.jsonl",sink.bytes);
    artifact(profile/"replay/status.json","{\"contract\":\"mmx6.native-consumption.v1\",\"epoch\":1,\"failure\":\"\",\"schema\":1,\"scope\":\"native-consumption diagnostics; replay unimplemented\",\"status\":\"finalized\"}\n");
    artifact(profile/"replay-profile.txt","mmx6-native-replay-private-v1\n"+id.image+"\n"+Mmx6Capture::sha(sink.bytes.data(),sink.bytes.size())+"\n");
    if(scenario=="settings")settings[2]='X';
    if(scenario=="card")card[0]^=1;
    if(scenario=="outside-card")card_path=(profile.parent_path()/"user-card.mcd").string();
    if(scenario=="bundle")artifact(profile/"replay/content.json","changed");
    if(scenario=="marker")artifact(profile/"replay-profile.txt","changed");
    if(scenario=="status")artifact(profile/"replay/status.json","{}");
    if(scenario=="incomplete")s.envelope_complete=0;
    if(scenario=="inactive")selected=false;
    if(scenario=="image")s.image_sha256[0]='3';
    if(scenario=="online")s.netplay=1;
    env("MMX6_INPUT_REPLAY",(profile/"replay/inputs.jsonl").string());env("MMX6_INPUT_REPLAY_PROFILE",profile.string());
    mmx6_register_diagnostics();assert(start_fn&&stop_fn&&native_fn&&standalone_native_fn&&native_fn!=standalone_native_fn);
    CPUState probe{};standalone_native_fn(&probe,0x80012C44);assert(!sequence_calls);
    native_fn(&probe,0x80012C44);assert(sequence_calls==1);sequence_calls=0;
    start_fn(&s);
    if(!refusal.empty()){
        assert(!current_replay&&!active_replay.load()&&!writes&&!callbacks.load());
        artifact(profile/"refused.txt",refusal);std::cout<<"startup refused: "<<refusal<<"\n";return 17;}
    assert(current_replay&&active_replay.load()&&!active.load()&&!writes);
    if(scenario=="early-end"||scenario=="state-replaced"){
        stop_fn(1,scenario=="early-end"?PSX_SESSION_DIAGNOSTICS_END_PROCESS_EXIT:PSX_SESSION_DIAGNOSTICS_END_STATE_REPLACED);
        assert(!current_replay&&!active_replay.load());return 0;}
    CPUState cpu{};const auto before=cpu;
    for(const auto& event:events){cycle=event.cycles;
        if(!event.kind){write_native(event,cpu);const auto snapshot=cpu;const unsigned original_writes=writes;
            if(!event.native){
                if(scenario=="cycle")++cycle;
                if(scenario=="caller")word(cpu.gpr[29]+16,0x8001AB18);
                if(scenario=="frame")word(0x80097420,event.frame+1);
                if(scenario=="previous")half(0x800C456E,1);}
            const unsigned before_sequence=sequence_calls;
            native_fn(&cpu,0x80012C44);assert(!std::memcmp(&cpu,&snapshot,sizeof cpu));assert(writes==original_writes+6);
            assert(sequence_calls==before_sequence+1&&sequence_buttons==0xFFFF); // Observer precedes replay supply.
            assert(psx_mod_read_half(0x800C456C)==0x800&&psx_mod_read_half(0x800C456E)==event.pads[0][1]);
            assert(psx_mod_read_half(0x800C4758)==event.pads[1][0]&&psx_mod_read_half(0x800C475A)==event.pads[1][1]);
        }else{
            if(scenario=="taint")taint=PSX_INPUT_TAINT_DIRECT_SIO;
            const unsigned tag=scenario=="tag"?event.consumer+1:event.consumer;
            const auto supplied=mmx6_diagnostics_p2(tag,0xFFFF,scenario=="mailbox");assert(supplied==event.buttons);}
    }
    (void)before;assert(writes==12);
    // Completion is terminal on the next real consumption boundary. The last
    // returned C value has already reached its caller; no live fallback runs.
    mmx6_diagnostics_p2(0,0xFFFF,0);assert(false);
}
