#pragma once
#include "psx_sha256.h"
#include "session_diagnostics_json.hpp"
#include <array>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>

namespace Mmx6Capture {
using psx_session_diagnostics_detail::JsonObject;
using psx_session_diagnostics_detail::array;
constexpr const char *Contract="mmx6.native-consumption.v1";
constexpr uint64_t MaxEvents=1000000;
constexpr const char *Consumers[]={"stage","controller-scene","controller-inactive",
    "controller-blocked","controller-player","interaction"};
inline std::string hex(const uint8_t hash[32]) {
    char out[65];for(unsigned i=0;i<32;++i)std::snprintf(out+2*i,3,"%02x",hash[i]);return out;
}
inline std::string sha(const void *data,size_t size) {
    uint8_t hash[32];psx_sha256_compute(static_cast<const uint8_t*>(data),size,hash);return hex(hash);
}
inline bool digest(const std::string& s) {
    return s.size()==64&&s.find_first_not_of("0123456789abcdef")==std::string::npos;
}
inline bool text(const std::string& s) {
    if(s.empty()||s.size()>256)return false;
    for(unsigned char c:s)if(c<32||c>=127)return false;
    return true;
}
struct Identity {
    std::string image,manifest,execution,settings,content,simulation,profile,selected;
    uint32_t revision=0;
    bool netplay=false;
    std::array<std::string,2> cards;
    std::string json()const {
        if(!digest(image)||!digest(manifest)||!digest(settings)||!digest(content)||
           !digest(simulation)||!text(execution)||(netplay&&(!text(profile)||!digest(selected))))
            throw std::invalid_argument("incomplete capture identity");
        JsonObject id;id.raw("baseline","null");std::vector<std::string> card_json;
        for(const auto& c:cards){if(c.empty())card_json.push_back("null");else{
            if(!digest(c))throw std::invalid_argument("invalid card identity");
            JsonObject b;b.number("bytes",131072);b.text("sha256",c);card_json.push_back(b.bytes());}}
        id.raw("cards",array(card_json));id.text("content_sha256",content);id.text("execution_id",execution);
        id.text("image_sha256",image);id.text("manifest_sha256",manifest);id.text("mode",netplay?"netplay":"offline");
        if(netplay){JsonObject p;p.text("id",profile);p.number("revision",revision);
            p.text("selected_sha256",selected);id.raw("profile",p.bytes());}else id.raw("profile","null");
        id.text("settings_sha256",settings);id.text("simulation_contract_sha256",simulation);return id.bytes();
    }
};
/* Owned POD only. No addresses to live RAM, borrowed strings or host padding
 * are serialized. The worker encodes every field explicitly. */
struct Event {
    uint64_t order=0,native=0,cycles=0;
    uint32_t tick=0,frame=0,caller=0;
    uint16_t pads[2][3]{};
    uint16_t buttons=0;
    uint8_t kind=0,consumer=0;
};
template<size_t Capacity>class Queue {
    static_assert(Capacity>0,"bounded queue needs capacity");
    std::array<Event,Capacity> slots{};
    std::atomic<uint64_t> head{0},tail{0};
public:
    bool push(const Event& e)noexcept {
        const uint64_t h=head.load(std::memory_order_relaxed);
        if(h-tail.load(std::memory_order_acquire)>=Capacity)return false;
        slots[h%Capacity]=e;head.store(h+1,std::memory_order_release);return true;
    }
    bool pop(Event& e)noexcept {
        const uint64_t t=tail.load(std::memory_order_relaxed);
        if(t==head.load(std::memory_order_acquire))return false;
        e=slots[t%Capacity];tail.store(t+1,std::memory_order_release);return true;
    }
};
enum class Take { Empty,Ready,Terminal };
template<size_t Capacity,class Terminal>
Take take_before_terminal(Queue<Capacity>& queue,Event& event,Terminal terminal){
    if(queue.pop(event))return Take::Ready;
    if(!terminal())return Take::Empty;
    /* Terminal is published only after producers disarm/drain. A producer may
     * have accepted its last event between the first pop and this observation.
     * Re-read after that acquire before declaring the accepted prefix drained. */
    return queue.pop(event)?Take::Ready:Take::Terminal;
}
struct Sink { virtual bool write(const std::string&)=0;virtual ~Sink()=default; };
/* Same strict event/terminal contract as tools/mmx6_input_recording.py. A sink
 * or validation error poisons this encoder; it can never finalize success. */
class Encoder {
    Sink& sink;
    psx_sha256_ctx hash{};
    uint64_t events=0,natives=0,reads=0,cycles=0;
    bool netplay,poisoned=false,finished=false;
    void line(const JsonObject& object,bool hashed=true){
        const std::string bytes=object.bytes()+"\n";
        if(bytes.size()>16384||!sink.write(bytes)){poisoned=true;throw std::runtime_error("recording short write/line bound");}
        if(hashed)psx_sha256_update(&hash,reinterpret_cast<const uint8_t*>(bytes.data()),bytes.size());
    }
public:
    Encoder(Sink& out,const Identity& identity):sink(out),netplay(identity.netplay){
        psx_sha256_init(&hash);JsonObject h;h.text("contract",Contract);h.raw("identity",identity.json());
        h.number("schema",1);h.text("type","header");line(h);
    }
    void append(const Event& e){
        if(poisoned||finished)throw std::runtime_error("recording encoder closed/poisoned");
        try{
            if(e.order!=events||e.cycles<cycles||events>=MaxEvents)
                throw std::runtime_error("native-consumption order/cycle/event bound");
            JsonObject row;row.number("cycles",e.cycles);row.number("native",e.native);
            row.number("order",e.order);if(netplay)row.number("sim_tick",e.tick);else row.raw("sim_tick","null");
            if(e.kind==0){
                if(e.native!=natives||(e.caller!=0x80012220&&e.caller!=0x8001A834&&e.caller!=0x8001AB18))
                    throw std::runtime_error("unmapped native input ordinal/caller");
                std::vector<std::string> pads;
                for(const auto& p:e.pads){if(p[2]!=((p[0]^p[1])&p[0]))
                        throw std::runtime_error("native pressed-edge invariant");
                    pads.push_back(array({std::to_string(p[0]),std::to_string(p[1]),std::to_string(p[2])}));}
                row.number("caller",e.caller);row.number("frame",e.frame);row.raw("pads",array(pads));row.text("type","N");
                line(row);++natives;
            }else if(e.kind==1){
                if(!natives||e.native!=natives-1||e.consumer>=6)
                    throw std::runtime_error("P2 consumer outside native interval/tag");
                row.number("buttons",e.buttons);row.text("consumer",Consumers[e.consumer]);
                row.number("seat",1);row.text("type","C");line(row);++reads;
            }else throw std::runtime_error("unknown native-consumption event");
            cycles=e.cycles;++events;
        }catch(...){poisoned=true;throw;}
    }
    void finish(const std::string& failure){
        if(poisoned||finished)throw std::runtime_error("recording encoder closed/poisoned");
        try{
            if(!failure.empty()&&!text(failure))throw std::invalid_argument("invalid capture failure reason");
            JsonObject end;end.number("events",events);end.number("natives",natives);end.number("p2_reads",reads);
            end.raw("failure",failure.empty()?"null":psx_session_diagnostics_detail::quote(failure));
            uint8_t digest[32];psx_sha256_final(&hash,digest);end.text("stream_sha256",hex(digest));end.text("type","end");
            line(end,false);finished=true;
        }catch(...){poisoned=true;throw;}
    }
    uint64_t native_count()const{return natives;}
};
}
