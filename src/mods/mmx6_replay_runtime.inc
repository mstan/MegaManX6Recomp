/* Included inside the diagnostics TU's private namespace. Filesystem and
 * parser work happens only on the startup/status workers, never N/C hot paths. */
enum class ReplayControl { Continue,Failure,Complete };
struct ReplayResult { ReplayControl control=ReplayControl::Continue;uint16_t buttons=0;const char *reason=nullptr; };
std::filesystem::path owned_replay_path(const std::filesystem::path& path){
    if(!path.is_absolute())throw std::runtime_error("replay profile/path must be absolute");
    return std::filesystem::weakly_canonical(path);
}
bool within(const std::filesystem::path& child,const std::filesystem::path& parent){
    auto a=child.begin(),b=parent.begin();
    for(;b!=parent.end();++a,++b){if(a==child.end())return false;
        auto left=a->string(),right=b->string();
#ifdef _WIN32
        for(char& c:left)if(c>='A'&&c<='Z')c=char(c-'A'+'a');
        for(char& c:right)if(c>='A'&&c<='Z')c=char(c-'A'+'a');
#endif
        if(left!=right)return false;}
    return a!=child.end(); // Owned descendants, never the profile/root itself.
}
std::string bounded_file(const std::filesystem::path& path,size_t maximum){
    std::ifstream source(path,std::ios::binary|std::ios::ate);
    const auto size=source.tellg();
    if(!source||size<0||uint64_t(size)>maximum)throw std::runtime_error("replay artifact missing/oversized");
    std::string bytes(size_t(size),'\0');source.seekg(0);
    if(size&&!source.read(&bytes[0],size))throw std::runtime_error("replay artifact short read");
    if(source.get()!=std::char_traits<char>::eof()||source.bad())throw std::runtime_error("replay artifact changed/read failure");
    return bytes;
}
struct ReplayLoaded { std::filesystem::path profile;std::vector<Event> events;std::string trace_sha; };
ReplayLoaded load_replay(const Startup& startup,const std::string& input,const std::string& private_profile){
    ReplayLoaded loaded;loaded.profile=owned_replay_path(private_profile);
    const auto file=owned_replay_path(input),recording=loaded.profile/"replay";
#ifdef _WIN32
    const auto drive=loaded.profile.root_name().string();
    if(drive=="C:"||drive=="c:")throw std::runtime_error("replay private profile on C: refused");
#endif
    if(!std::filesystem::is_directory(loaded.profile)||file.filename()!="inputs.jsonl"||!within(file,recording))
        throw std::runtime_error("replay requires prepared private trace location");
    if(!within(owned_replay_path(startup.root),loaded.profile))throw std::runtime_error("runtime output root escaped replay profile");
    for(unsigned slot=0;slot<2;++slot){
        if(!startup.card_paths[slot].empty()&&!within(owned_replay_path(startup.card_paths[slot]),loaded.profile/"saves"))
            throw std::runtime_error("live memory card is outside the private replay saves");
        if(!startup.cards[slot].empty()&&startup.card_paths[slot].empty())
            throw std::runtime_error("present replay card has no owned live binding");
    }
    std::ifstream source(file,std::ios::binary);if(!source)throw std::runtime_error("replay input trace unavailable");
    ReplayReader reader;loaded.events=reader.read(source,startup.identity);loaded.trace_sha=reader.file_sha256();
    const std::string marker="mmx6-native-replay-private-v1\n"+startup.identity.image+"\n"+loaded.trace_sha+"\n";
    if(bounded_file(loaded.profile/"replay-profile.txt",512)!=marker)
        throw std::runtime_error("private replay preparation marker/trace changed");
    auto same=[&](const char *name,const std::string& expected){
        const auto artifact_path=owned_replay_path(recording/name);
        if(!within(artifact_path,recording)||bounded_file(artifact_path,PSX_SESSION_DIAGNOSTICS_MAX_BUNDLE)!=expected)
            throw std::runtime_error("retained replay startup bundle differs from actual startup");};
    same("settings.json",startup.settings);same("content.json",startup.content);same("simulation-contract.json",startup.implementation);
    for(unsigned slot=0;slot<2;++slot){const auto path=recording/("card"+std::to_string(slot+1)+".initial.mcd");
        if(startup.cards[slot].empty()){
            if(std::filesystem::exists(path))throw std::runtime_error("absent replay card has an artifact");
        }else{
            const auto owned=owned_replay_path(path);
            if(!within(owned,recording)||bounded_file(owned,MEMCARD_SIZE)!=
                std::string(reinterpret_cast<const char*>(startup.cards[slot].data()),startup.cards[slot].size()))
                throw std::runtime_error("retained initial replay card differs from actual private card");}}
    const std::string status=bounded_file(recording/"status.json",4096);
    static const std::regex finalized(R"row(^\{"contract":"mmx6\.native-consumption\.v1","epoch":([1-9][0-9]*),"failure":"","schema":1,"scope":"native-consumption diagnostics; replay unimplemented","status":"finalized"\}\n$)row");
    std::smatch fields;
    if(!std::regex_match(status,fields,finalized))throw std::runtime_error("recording status is missing/failed/not finalized");
    (void)std::stoull(fields[1].str()); // Overflow must reject, never wrap source epoch.
    JsonObject running;running.number("schema",1);running.text("status","running");
    running.text("trace_sha256",loaded.trace_sha);artifact(loaded.profile/"replay-result.json",running.bytes()+"\n");
    return loaded;
}
class Replay {
    enum Outcome { Running,Consumed,Failed };
    Startup startup;
    ReplayLoaded loaded;
    std::unique_ptr<ReplayCursor> cursor;
    std::atomic<unsigned> outcome{Running};
    std::atomic<const char*> first_failure{nullptr};
    std::atomic<uint64_t> count{0};
    std::condition_variable wake;
    std::mutex wait_mutex;
    std::thread writer;
    uint64_t natives=0;
    void failure(const char *reason)noexcept{
        const char *empty=nullptr;first_failure.compare_exchange_strong(empty,reason);
        outcome.store(Failed,std::memory_order_release);wake.notify_one();
    }
    ReplayResult refused(const char *reason)noexcept{failure(reason);return {ReplayControl::Failure,0,reason};}
    ReplayResult complete()noexcept{return {ReplayControl::Complete,0,nullptr};}
    void result_writer()noexcept{
        try{
            /* Producer/error flags are atomic and deliberately do not take the
             * worker mutex. A bounded timed wait also covers notification in
             * the predicate-to-sleep gap; shutdown cannot miss a final wake. */
            {std::unique_lock<std::mutex> lock(wait_mutex);
                while(outcome.load(std::memory_order_acquire)==Running)wake.wait_for(lock,std::chrono::milliseconds(50));}
            const bool failed=outcome.load(std::memory_order_acquire)==Failed;
            JsonObject result;result.number("schema",1);result.number("epoch",startup.epoch);
            result.text("contract",Contract);result.text("trace_sha256",loaded.trace_sha);
            result.number("events",loaded.events.size());result.number("consumed",count.load());
            result.text("status",failed?"failed":"consumed");
            const char *why=first_failure.load();result.text("failure",why?why:"");
            result.text("scope","ordered native/P2 consumption only; no full SIO or outcome qualification");
            artifact(loaded.profile/"replay-result.json",result.bytes()+"\n");
        }catch(...){failure("replay result worker I/O failed");}
    }
    ReplayResult consume(Event& observed)noexcept{
        if(outcome.load(std::memory_order_acquire)==Failed){const char *why=first_failure.load();
            return refused(why?why:"replay failed");}
        if(psx_session_input_taint_get()&PSX_INPUT_TAINT_UNILATERAL_MASK)
            return refused("fixture or unilateral input interrupted replay");
        if(cursor->exhausted())return complete();
        observed.order=cursor->consumed();observed.native=observed.kind?natives-1:natives;
        observed.cycles=psx_get_cycle_count();observed.tick=0;Event supplied;
        if(!cursor->consume(observed,supplied))return refused(cursor->error());
        count.store(cursor->consumed(),std::memory_order_release);
        if(!observed.kind){
            const uint32_t bases[]={0x800C456Cu,0x800C4758u};
            for(unsigned port=0;port<2;++port)for(unsigned word=0;word<3;++word)
                psx_mod_write_half(bases[port]+2*word,supplied.pads[port][word]);
            ++natives;
        }
        return {ReplayControl::Continue,supplied.buttons,nullptr};
    }
public:
    Replay(Startup owned,const std::string& input,const std::string& profile):startup(std::move(owned)){
        std::string error;
        std::thread loader([&]{try{loaded=load_replay(startup,input,profile);}
            catch(const std::exception& e){error=e.what();}catch(...){error="replay prefetch failed";}});
        loader.join();if(!error.empty())throw std::runtime_error(error);
        cursor=std::make_unique<ReplayCursor>(loaded.events);
        writer=std::thread([this]{result_writer();});
    }
    ~Replay(){(void)stop(PSX_SESSION_DIAGNOSTICS_END_PROCESS_EXIT);}
    bool stop(int reason)noexcept{
        if(outcome.load()==Running){
            if(reason==PSX_SESSION_DIAGNOSTICS_END_STATE_REPLACED)failure("state replacement interrupted replay");
            else if(reason==PSX_SESSION_DIAGNOSTICS_END_START_FAILED||!cursor->exhausted())failure("replay ended before the complete consumption stream");
            else{outcome.store(Consumed,std::memory_order_release);wake.notify_one();}}
        if(writer.joinable())writer.join();
        return outcome.load()!=Failed;
    }
    ReplayResult native(CPUState *cpu,uint32_t address)noexcept{
        Event observed;observed.kind=0;
        if(!sample_native(cpu,address,observed))return refused("invalid native replay decoder stack/site");
        return consume(observed);
    }
    ReplayResult p2(unsigned consumer,uint16_t,int contaminated)noexcept{
        if(contaminated)return refused("title input mailbox interrupted replay");
        if(!natives||consumer>=6)return refused("P2 replay consumer before native input or unknown tag");
        Event observed;observed.kind=1;observed.consumer=uint8_t(consumer);return consume(observed);
    }
};
