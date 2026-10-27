#include "mmx6_diagnostics.h"
#if defined(__has_include)
#if __has_include("session_diagnostics.h")
#define MMX6_SESSION_DIAGNOSTICS 1
#endif
#endif
#ifdef MMX6_SESSION_DIAGNOSTICS
#include "session_diagnostics.h"
#include "session_input_taint.h"
#include "mod_runtime.h"
#include "mod_plugins.h"
#include "cpu_state.h"
#include "psx_cycles.h"
#include "psx_netplay.h"
#include "memcard.h"
#include "crash_trace.h"
#include "mmx6_input_capture.hpp"
#include "mmx6_input_replay.hpp"
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <memory>
#include <mutex>
#include <thread>

namespace {
using namespace Mmx6Capture;
enum Failure { None,QueueFull,EventLimit,InvalidNative,BeforeNative,Unilateral,StartFailed,WorkerFailed,StateReplaced };
const char *failure_text(unsigned reason){switch(reason){
    case QueueFull:return "bounded native-consumption queue full";
    case EventLimit:return "bounded native-consumption event limit reached";
    case InvalidNative:return "unmapped native input stack/caller/edge";
    case BeforeNative:return "P2 consumer observed before first native decode";
    case Unilateral:return "unilateral debug or fixture input contaminated capture";
    case StartFailed:return "runtime startup observer failed";
    case WorkerFailed:return "recording worker I/O or validation failed";
    case StateReplaced:return "guest execution state replaced; capture segment ended";
    default:return "";}}
struct Startup {
    uint64_t epoch=0;
    Identity identity;
    std::string root,settings,content,implementation;
    std::array<std::vector<uint8_t>,2> cards;
    std::array<std::string,2> card_paths;
};
struct FileSink:Sink {
    FILE *file=nullptr;
    explicit FileSink(const std::filesystem::path& p){
#ifdef _WIN32
        file=_wfopen(p.c_str(),L"wb");
#else
        file=std::fopen(p.c_str(),"wb");
#endif
        if(!file)throw std::runtime_error("cannot create recording file");
    }
    bool write(const std::string& s)override{return std::fwrite(s.data(),1,s.size(),file)==s.size();}
    void flush(){if(std::fflush(file)!=0)throw std::runtime_error("recording flush failed");}
    void close(){FILE *f=file;file=nullptr;if(f&&std::fclose(f)!=0)throw std::runtime_error("recording close failed");}
    ~FileSink(){if(file)std::fclose(file);}
};
void artifact(const std::filesystem::path& path,const void *data,size_t size){
    FileSink file(path);if(size&&std::fwrite(data,1,size,file.file)!=size)
        throw std::runtime_error("startup artifact short write");
    file.close();
}
void artifact(const std::filesystem::path& path,const std::string& bytes){artifact(path,bytes.data(),bytes.size());}
std::filesystem::path private_directory(const Startup& s){
    std::filesystem::path root(s.root);
    if(!root.is_absolute())throw std::runtime_error("capture output root is not absolute");
#ifdef _WIN32
    /* Agent runs must never silently spill bulk output onto the system drive.
     * A caller can select its owned F:/G: root with MMX6_INPUT_RECORDING_DIR. */
    const auto drive=root.root_name().string();
    if(drive=="C:"||drive=="c:")throw std::runtime_error("capture output on C: refused; choose owned F:/G: root");
#endif
    std::filesystem::create_directories(root);
    const auto stamp=std::chrono::system_clock::now().time_since_epoch().count();
    for(unsigned attempt=0;attempt<32;++attempt){
        auto path=root/("session-"+std::to_string(stamp)+"-"+std::to_string(s.epoch)+"-"+std::to_string(attempt));
        if(std::filesystem::create_directory(path)){
#ifndef _WIN32
            std::filesystem::permissions(path,std::filesystem::perms::owner_all,
                std::filesystem::perm_options::replace);
#endif
            return path;}}
    throw std::runtime_error("cannot reserve unique capture output directory");
}
bool sample_native(CPUState *cpu,uint32_t address,Event& e)noexcept{
    const uint32_t sp=cpu?cpu->gpr[29]:0,physical=sp&0x1FFFFFFFu;
    if(!cpu||address!=0x80012C44u||(sp&3)||physical>0x1FFFECu||
       !((sp>=0x80000000u&&sp<0x80200000u)||(sp>=0xA0000000u&&sp<0xA0200000u)))return false;
    e.caller=psx_mod_read_word(sp+16);e.frame=psx_mod_read_word(0x80097420u);
    const uint32_t bases[]={0x800C456Cu,0x800C4758u};
    for(unsigned port=0;port<2;++port)for(unsigned word=0;word<3;++word)
        e.pads[port][word]=psx_mod_read_half(bases[port]+2*word);
    return true;
}
#include "mmx6_replay_runtime.inc"
class Capture {
    Queue<8192> queue;
    std::atomic<bool> accepting{false},closing{false};
    std::atomic<unsigned> in_flight{0},failure{None};
    std::condition_variable wake;
    std::mutex wait_mutex;
    std::thread worker;
    Startup startup;
    uint64_t order=0,natives=0; // simulation-owner producer only
    bool netplay=false;
    void fail(unsigned reason)noexcept{
        unsigned first=None;failure.compare_exchange_strong(first,reason);
        accepting.store(false,std::memory_order_release);wake.notify_one();
    }
    void write()noexcept{
        std::filesystem::path directory;
        try{
            directory=private_directory(startup);
            artifact(directory/"settings.json",startup.settings);artifact(directory/"content.json",startup.content);
            artifact(directory/"simulation-contract.json",startup.implementation);
            for(unsigned slot=0;slot<2;++slot)if(!startup.cards[slot].empty())
                artifact(directory/("card"+std::to_string(slot+1)+".initial.mcd"),startup.cards[slot].data(),startup.cards[slot].size());
            FileSink file(directory/"inputs.jsonl");Encoder encoder(file,startup.identity);
            // Only this worker touches stdio. A sparse last accepted event
            // must become visible without another input or session shutdown.
            // Check the same steady-clock deadline while busy and while idle.
            const auto flush_interval=std::chrono::milliseconds(100);
            auto flush_at=std::chrono::steady_clock::now()+flush_interval;
            bool dirty=true; // The encoder has already written its header.
            for(;;){Event event;
                const auto now=std::chrono::steady_clock::now();
                if(dirty&&now>=flush_at){file.flush();dirty=false;flush_at=now+flush_interval;}
                const Take take=take_before_terminal(queue,event,[this]{
                    return closing.load(std::memory_order_acquire)||
                        (failure.load(std::memory_order_acquire)&&!in_flight.load(std::memory_order_acquire));});
                if(take==Take::Ready){encoder.append(event);dirty=true;continue;}
                if(take==Take::Terminal)break;
                std::unique_lock<std::mutex> lock(wait_mutex);
                if(dirty)wake.wait_until(lock,flush_at);
                else wake.wait_for(lock,std::chrono::milliseconds(50));
            }
            std::string reason=failure_text(failure.load(std::memory_order_acquire));
            if(!encoder.native_count()&&reason.empty())reason="no native input calls observed";
            encoder.finish(reason);file.close();
            JsonObject status;status.number("schema",1);status.number("epoch",startup.epoch);
            status.text("contract",Contract);status.text("status",reason.empty()?"finalized":"failed");
            status.text("failure",reason);status.text("scope","native-consumption diagnostics; replay unimplemented");
            artifact(directory/"status.json",status.bytes()+"\n");
            std::fprintf(stderr,"mmx6 diagnostics: %s capture %s\n",reason.empty()?"finalized":"failed",directory.string().c_str());
        }catch(const std::exception& e){
            fail(WorkerFailed);
            std::fprintf(stderr,"mmx6 diagnostics: capture unavailable/failed: %s\n",e.what());
            if(!directory.empty())try{JsonObject status;status.number("schema",1);status.number("epoch",startup.epoch);
                status.text("status","failed");status.text("failure",failure_text(failure.load()));
                status.text("worker_error",e.what());artifact(directory/"status.json",status.bytes()+"\n");}catch(...){}
        }catch(...){fail(WorkerFailed);std::fprintf(stderr,"mmx6 diagnostics: capture worker failed\n");}
    }
    bool enter()noexcept{
        if(!accepting.load(std::memory_order_acquire))return false;
        in_flight.fetch_add(1,std::memory_order_acq_rel);
        if(!accepting.load(std::memory_order_acquire)){in_flight.fetch_sub(1,std::memory_order_release);return false;}
        return true;
    }
    void publish(Event& event)noexcept{
        if(psx_session_input_taint_get()&PSX_INPUT_TAINT_UNILATERAL_MASK)fail(Unilateral);
        else if(order>=MaxEvents)fail(EventLimit);
        else{
            event.order=order;event.cycles=psx_get_cycle_count();
            event.tick=netplay?psx_netplay_sim_tick():0;
            if(!queue.push(event))fail(QueueFull);else{++order;if(!event.kind)++natives;wake.notify_one();}
        }
        in_flight.fetch_sub(1,std::memory_order_release);
    }
public:
    explicit Capture(Startup s):startup(std::move(s)),netplay(startup.identity.netplay){
        accepting.store(true,std::memory_order_release);worker=std::thread([this]{write();});
    }
    ~Capture(){stop(PSX_SESSION_DIAGNOSTICS_END_PROCESS_EXIT);}
    void stop(int reason)noexcept{
        accepting.store(false,std::memory_order_release);
        if(reason==PSX_SESSION_DIAGNOSTICS_END_START_FAILED)fail(StartFailed);
        if(reason==PSX_SESSION_DIAGNOSTICS_END_STATE_REPLACED)fail(StateReplaced);
        /* A process-exit callback may be on another thread. The producer's
         * bounded no-I/O publication must leave before its storage is freed. */
        while(in_flight.load(std::memory_order_acquire))std::this_thread::yield();
        closing.store(true,std::memory_order_release);wake.notify_one();
        if(worker.joinable())worker.join();
    }
    void native(CPUState *cpu,uint32_t address)noexcept{
        if(!enter())return;
        Event e;e.kind=0;e.native=natives;
        if(!sample_native(cpu,address,e)){
            fail(InvalidNative);in_flight.fetch_sub(1,std::memory_order_release);return;}
        publish(e);
    }
    void p2(unsigned consumer,uint16_t buttons,int contaminated)noexcept{
        if(!enter())return;
        if(contaminated){psx_session_input_taint_add(PSX_INPUT_TAINT_GAME_MAILBOX);fail(Unilateral);}
        if(!natives||consumer>=6){fail(BeforeNative);in_flight.fetch_sub(1,std::memory_order_release);return;}
        Event e;e.kind=1;e.native=natives-1;e.consumer=static_cast<uint8_t>(consumer);e.buttons=buttons;publish(e);
    }
};
/* Router start/end are serialized. End disarms the raw pointer, waits for all
 * outer Callback guards, drains the worker and only then resets the object. */
std::unique_ptr<Capture> current;
std::unique_ptr<Replay> current_replay;
std::atomic<Capture*> active{nullptr};
std::atomic<Replay*> active_replay{nullptr};
std::atomic<unsigned> callbacks{0};
std::atomic<bool> replay_end_failed{false};
uint64_t current_epoch=0;
struct Callback {
    Capture *capture=nullptr;
    Replay *replay=nullptr;
    Callback(){callbacks.fetch_add(1);capture=active.load();replay=active_replay.load();}
    ~Callback(){callbacks.fetch_sub(1);}
};
void end(uint64_t epoch,int reason){
    if(epoch!=current_epoch)return;
    /* Sequential ordering across these two atomics prevents the exiting thread
     * from freeing a pointer that a producer has just acquired. */
    active.store(nullptr);
    active_replay.store(nullptr);
    while(callbacks.load())std::this_thread::yield();
    if(current){current->stop(reason);current.reset();}
    if(current_replay){replay_end_failed.store(!current_replay->stop(reason));current_replay.reset();}
    current_epoch=0;
}
void begin(const PSXSessionDiagnosticsStart *s){
    if(!s)return;
    const char *replay_path=std::getenv("MMX6_INPUT_REPLAY");
    const bool replay_requested=replay_path!=nullptr;
    /* Offline feature selection is actual committed plugin ownership. Online
     * the executable's forced profile owns the same native instruction hook. */
    if(!mod_runtime_diagnostics_plugin_active(s->netplay?"mmx6.local-coop.prototype":"mmx6.diagnostics")){
        if(replay_requested)psx_session_diagnostics_refuse_replay("required diagnostics native hook is not active");return;}
    const char *enabled=std::getenv("MMX6_INPUT_RECORDING");
    if(!replay_requested&&enabled&&!std::strcmp(enabled,"0"))return;
    if(!s->envelope_complete){
        if(replay_requested)psx_session_diagnostics_refuse_replay(s->unavailable_reason);
        else std::fprintf(stderr,"mmx6 diagnostics: capture unavailable: %s\n",s->unavailable_reason);
        return;}
    if(replay_requested&&s->netplay){psx_session_diagnostics_refuse_replay("native-consumption replay is offline only");return;}
    if(s->guest_cycles||s->sim_tick||current||current_replay)throw std::runtime_error("diagnostics requires fresh resolved startup boundary");
    Startup owned;owned.epoch=s->session_epoch;
    owned.root=(std::filesystem::path(s->output_root)/"input-recordings").string();
    if(const char *root=std::getenv("MMX6_INPUT_RECORDING_DIR"))owned.root=root;
    owned.settings.assign(s->settings.data,s->settings.size);owned.content.assign(s->content.data,s->content.size);
    owned.implementation.assign(s->implementation.data,s->implementation.size);
    auto& id=owned.identity;id.image=s->image_sha256;id.manifest=s->manifest_sha256;id.execution=s->execution_id;
    id.settings=sha(owned.settings.data(),owned.settings.size());id.content=sha(owned.content.data(),owned.content.size());
    id.simulation=sha(owned.implementation.data(),owned.implementation.size());
    id.netplay=s->netplay!=0;id.profile=s->profile_id;id.revision=s->profile_revision;id.selected=s->selected_sha256;
    for(unsigned slot=0;slot<2;++slot){
        if(replay_requested){const char *path=nullptr;
            if(memcard_debug_info(slot,&path,nullptr,nullptr,nullptr)!=0)throw std::runtime_error("live replay card path unavailable");
            owned.card_paths[slot]=path?path:"";}
        if(memcard_is_present(slot)){
        owned.cards[slot].resize(MEMCARD_SIZE);
        if(memcard_export_raw(slot,owned.cards[slot].data())!=0)throw std::runtime_error("initial memory card export failed");
        id.cards[slot]=sha(owned.cards[slot].data(),owned.cards[slot].size());}}
    (void)id.json(); // Validate before worker/producer activation.
    if(replay_requested){
        try{
            if(!*replay_path)throw std::runtime_error("explicit replay path is empty");
            const char *profile=std::getenv("MMX6_INPUT_REPLAY_PROFILE");
            if(!profile||!*profile)throw std::runtime_error("explicit replay requires a prepared private profile");
            current_replay=std::make_unique<Replay>(std::move(owned),replay_path,profile);
            current_epoch=s->session_epoch;replay_end_failed.store(false);active_replay.store(current_replay.get());
        }catch(const std::exception& error){psx_session_diagnostics_refuse_replay(error.what());}
        return;
    }
    current_epoch=s->session_epoch;current=std::make_unique<Capture>(std::move(owned));
    active.store(current.get());
}
[[noreturn]]void finish_replay(ReplayResult result){
    /* ERROR/completion control only. Every Callback guard is already released;
     * atomically disarm, drain the status worker, then use existing terminal
     * runtime boundaries. Never longjmp or return a live input fallback. */
    active_replay.store(nullptr);
    psx_session_diagnostics_end(result.control==ReplayControl::Complete?
        PSX_SESSION_DIAGNOSTICS_END_NORMAL:PSX_SESSION_DIAGNOSTICS_END_START_FAILED);
    if(result.control==ReplayControl::Complete&&!replay_end_failed.load()){
        psx_crash_trace_set_exit_origin("mmx6_native_consumption_replay_end");std::exit(0);
    }
    psx_fatal_halt(result.reason?result.reason:"native-consumption replay result failed");
    std::abort(); // Boundary is documented nonreturning, even on legacy headers.
}
void native(CPUState *cpu,uint32_t address){
    ReplayResult result;{Callback scope;
        if(scope.replay)result=scope.replay->native(cpu,address);
        else if(scope.capture)scope.capture->native(cpu,address);}
    if(result.control!=ReplayControl::Continue)finish_replay(result);
}
}
extern "C" uint16_t mmx6_diagnostics_p2(unsigned consumer,uint16_t buttons,int contaminated){
    ReplayResult result;result.buttons=buttons;{Callback scope;
        if(scope.replay)result=scope.replay->p2(consumer,buttons,contaminated);
        else if(scope.capture)scope.capture->p2(consumer,buttons,contaminated);}
    if(result.control!=ReplayControl::Continue)finish_replay(result);
    return result.buttons;
}
PSX_MOD_CONSTRUCTOR(mmx6_register_diagnostics){
    if(std::getenv("MMX6_INPUT_REPLAY"))psx_game_register_guarded_session_diagnostics(begin,end);
    else psx_game_register_session_diagnostics(begin,end);
    for(const char *id:{"mmx6.diagnostics","mmx6.local-coop.prototype"})
        psx_mod_register_instruction_plugin(id,0x80012C44u,0x8FBF0010u,native);
}
#else
/* Legacy SDK helper fixtures remain linkable; no capture is advertised. */
#include "mod_plugins.h"
#include <cstdio>
#include <cstdlib>
extern "C" uint16_t mmx6_diagnostics_p2(unsigned,uint16_t buttons,int){return buttons;}
static void unavailable(){std::fprintf(stderr,"mmx6 diagnostics: capture unavailable: SDK session diagnostics service required\n");}
PSX_MOD_CONSTRUCTOR(mmx6_register_diagnostics_unavailable){
    if(std::getenv("MMX6_INPUT_REPLAY")){
        std::fprintf(stderr,"mmx6 diagnostics: explicit replay refused: SDK guarded session diagnostics service required\n");
        std::exit(EXIT_FAILURE);
    }
    psx_mod_register_activation_plugin("mmx6.diagnostics",unavailable);
}
#endif
