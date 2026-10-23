#pragma once
#include "mmx6_input_capture.hpp"
#include <istream>
#include <regex>
#include <vector>

namespace Mmx6Capture {
/* A bounded complete prefetch: no filesystem/parser/worker queue can block a
 * native N/C callback. Larger streams are explicitly unsupported in this slice.
 * Raw serial/publication replay and restored-state baselines are not implied. */
constexpr size_t MaxReplayEvents=262144;
constexpr uint64_t MaxReplayBytes=128u*1024u*1024u;
class ReplayReader {
    struct CompareSink:Sink {
        std::string pending;
        bool write(const std::string& canonical)override {
            if(canonical!=pending)throw std::runtime_error("replay identity/canonical/terminal mismatch");
            return true;
        }
    } sink;
    uint64_t bytes=0;
    psx_sha256_ctx source_hash{};
    std::string source_digest;
    std::string line(std::istream& source){
        std::string result;result.reserve(512);
        for(;;){const int c=source.get();
            if(c==std::char_traits<char>::eof())throw std::runtime_error("truncated replay record/terminal");
            if(++bytes>MaxReplayBytes||result.size()>=16384)throw std::runtime_error("replay file/line bound");
            result+=char(c);if(c=='\n'){
                psx_sha256_update(&source_hash,reinterpret_cast<const uint8_t*>(result.data()),result.size());return result;}
        }
    }
    static uint64_t number(const std::ssub_match& match,unsigned bits){
        const auto s=match.str();uint64_t out=0;
        for(char c:s){const unsigned digit=unsigned(c-'0');
            if(out>(UINT64_MAX-digit)/10)throw std::runtime_error("replay unsigned integer overflow");
            out=out*10+digit;}
        if(bits<64&&out>=(UINT64_C(1)<<bits))throw std::runtime_error("replay field range");
        return out;
    }
public:
    const std::string& file_sha256()const{return source_digest;}
    std::vector<Event> read(std::istream& source,const Identity& actual,size_t cap=MaxReplayEvents){
        if(actual.netplay)throw std::runtime_error("native-consumption replay is offline only");
        if(!cap||cap>MaxReplayEvents)throw std::runtime_error("invalid replay complete-prefetch cap");
        bytes=0;source_digest.clear();psx_sha256_init(&source_hash);sink.pending=line(source);
        /* The exact canonical header is independently built from the actual
         * current startup export/cards. This also rejects any non-null baseline,
         * online/profile trace, changed build, unknown or duplicate header key. */
        Encoder check(sink,actual);
        static const std::regex native(R"row(^\{"caller":([0-9]+),"cycles":([0-9]+),"frame":([0-9]+),"native":([0-9]+),"order":([0-9]+),"pads":\[\[([0-9]+),([0-9]+),([0-9]+)\],\[([0-9]+),([0-9]+),([0-9]+)\]\],"sim_tick":null,"type":"N"\}\n$)row");
        static const std::regex partner(R"row(^\{"buttons":([0-9]+),"consumer":"(stage|controller-scene|controller-inactive|controller-blocked|controller-player|interaction)","cycles":([0-9]+),"native":([0-9]+),"order":([0-9]+),"seat":1,"sim_tick":null,"type":"C"\}\n$)row");
        std::vector<Event> events;
        events.reserve(4096);
        for(;;){sink.pending=line(source);
            if(sink.pending.compare(0,10,"{\"events\":")==0){
                if(!check.native_count())throw std::runtime_error("replay contains no native calls");
                check.finish("");
                if(source.get()!=std::char_traits<char>::eof()||source.bad())
                    throw std::runtime_error("replay data after terminal/read failure");
                uint8_t hash[32];psx_sha256_final(&source_hash,hash);source_digest=hex(hash);return events;
            }
            if(events.size()>=cap)throw std::runtime_error("replay complete-prefetch event cap");
            Event e;std::smatch fields;
            if(std::regex_match(sink.pending,fields,native)){
                e.kind=0;e.caller=uint32_t(number(fields[1],32));e.cycles=number(fields[2],64);
                e.frame=uint32_t(number(fields[3],32));e.native=number(fields[4],64);e.order=number(fields[5],64);
                for(unsigned p=0;p<2;++p)for(unsigned w=0;w<3;++w)e.pads[p][w]=uint16_t(number(fields[6+3*p+w],16));
            }else if(std::regex_match(sink.pending,fields,partner)){
                e.kind=1;e.buttons=uint16_t(number(fields[1],16));const auto tag=fields[2].str();
                unsigned consumer=0;while(consumer<6&&tag!=Consumers[consumer])++consumer;e.consumer=uint8_t(consumer);
                e.cycles=number(fields[3],64);e.native=number(fields[4],64);e.order=number(fields[5],64);
            }else throw std::runtime_error("malformed/unknown replay native-consumption row");
            /* The actual writer validator rechecks order/caller/edge/cycle
             * invariants and reconstructs the exact canonical bytes/hash. */
            check.append(e);events.push_back(e);
        }
    }
};
class ReplayCursor {
    const std::vector<Event>& events;
    size_t next=0;
    const char *failure=nullptr;
    bool refuse(const char *reason){if(!failure)failure=reason;return false;}
public:
    explicit ReplayCursor(const std::vector<Event>& validated):events(validated){}
    /* Supply only after checking the actual ordered consumer/call boundary.
     * The caller applies the returned native triples/value solely in explicit
     * replay; normal recording never passes through this matcher. */
    bool consume(const Event& observed,Event& supplied){
        if(failure)return false;
        if(next==events.size())return refuse("native-consumption replay exhausted");
        const Event& expected=events[next];
        if(observed.kind!=expected.kind||observed.order!=expected.order||observed.native!=expected.native)
            return refuse("native/P2 consumption order diverged");
        if(observed.cycles!=expected.cycles||observed.tick!=expected.tick)
            return refuse("native/P2 consumption cycle/tick diverged");
        if(!expected.kind){
            if(observed.caller!=expected.caller||observed.frame!=expected.frame)
                return refuse("native decoder caller/frame diverged");
            /* Current/pressed are the replay supply. Previous must still be
             * what the original decoder consumed from the prior interval. */
            for(unsigned port=0;port<2;++port)if(observed.pads[port][1]!=expected.pads[port][1])
                return refuse("native previous decoded input diverged");
        }else if(observed.consumer!=expected.consumer)return refuse("P2 consumer tag diverged");
        supplied=expected;++next;return true;
    }
    bool exhausted()const{return next==events.size();}
    size_t consumed()const{return next;}
    const char *error()const{return failure?failure:"";}
};
}
