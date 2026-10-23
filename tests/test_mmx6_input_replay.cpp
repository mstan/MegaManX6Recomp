#include "../src/mods/mmx6_input_replay.hpp"
#include <cassert>
#include <iostream>
#include <sstream>
using namespace Mmx6Capture;
struct Memory:Sink{std::string bytes;bool write(const std::string& row)override{bytes+=row;return true;}};
template<class F>static void rejects(F f){bool rejected=false;try{f();}catch(const std::exception&){rejected=true;}assert(rejected);}
static Identity identity(){Identity id;id.image=std::string(64,'a');id.manifest=std::string(64,'b');
    id.settings=std::string(64,'c');id.content=std::string(64,'d');id.simulation=std::string(64,'e');id.execution="fixture";
    id.cards[0]=std::string(64,'f');return id;}
static std::vector<Event> events(){
    Event n;n.kind=0;n.caller=0x80012220;n.frame=20;n.cycles=10;n.pads[0][0]=n.pads[0][2]=0x800;
    Event c;c.kind=1;c.order=1;c.native=0;c.cycles=11;c.consumer=0;c.buttons=8;
    Event c2=c;c2.order=2;c2.cycles=12;c2.consumer=4;
    Event n2=n;n2.order=3;n2.native=1;n2.cycles=30;n2.caller=0x8001A834;n2.pads[0][1]=0x800;n2.pads[0][2]=0;
    Event c3=c;c3.order=4;c3.native=1;c3.cycles=31;c3.buttons=0;
    return {n,c,c2,n2,c3};
}
static std::string encoded(const Identity& id,const std::string& failure=""){
    Memory sink;Encoder encoder(sink,id);for(const auto& e:events())encoder.append(e);encoder.finish(failure);return sink.bytes;
}
static std::vector<Event> decode(const std::string& bytes,const Identity& id){
    std::istringstream source(bytes);ReplayReader reader;return reader.read(source,id);
}
int main(){
    const auto id=identity();const auto bytes=encoded(id);const auto expected=events();const auto owned=decode(bytes,id);
    assert(owned.size()==expected.size());ReplayCursor replay(owned);
    for(auto observed:expected){
        if(!observed.kind){observed.pads[0][0]=observed.pads[0][2]=0;}else observed.buttons=0;
        Event supplied;assert(replay.consume(observed,supplied));
        assert(supplied.buttons==expected[observed.order].buttons&&supplied.pads[0][0]==expected[observed.order].pads[0][0]);
    }
    assert(replay.exhausted()&&replay.consumed()==5);Event out;assert(!replay.consume(expected.back(),out));
    assert(std::string(replay.error()).find("exhausted")!=std::string::npos);
    // Every truncated byte, terminal/hash/failed prefix and identity perturbation
    // is rejected by the actual C++ runtime reader before exposing any events.
    for(size_t end=0;end<bytes.size();++end)rejects([&]{decode(bytes.substr(0,end),id);});
    rejects([&]{decode(bytes+"x",id);});rejects([&]{decode(encoded(id,"fixture contaminated"),id);});
    {ReplayReader reader;std::istringstream source(bytes);assert(reader.read(source,id).size()==5);
        assert(reader.file_sha256()==sha(bytes.data(),bytes.size()));
        std::istringstream capped(bytes);rejects([&]{reader.read(capped,id,2);});assert(reader.file_sha256().empty());}
    for(auto field:{&Identity::image,&Identity::manifest,&Identity::execution,&Identity::settings,
                    &Identity::content,&Identity::simulation}){
        auto changed=id;changed.*field="different";rejects([&]{decode(bytes,changed);});}
    auto card=id;card.cards[0]=std::string(64,'1');rejects([&]{decode(bytes,card);});
    card=id;card.cards[1]=std::string(64,'1');rejects([&]{decode(bytes,card);});
    auto online=id;online.netplay=true;online.profile="fixture";online.selected=std::string(64,'1');
    rejects([&]{decode(encoded(online),id);});rejects([&]{decode(bytes,online);});
    auto altered=bytes;altered[altered.find("\"baseline\":null")+11]='0';rejects([&]{decode(altered,id);});
    for(const auto& row:{std::string("{\"unknown\":0}\n"),std::string(16385,'0')+"\n"}){
        const auto end=bytes.find('\n')+1;rejects([&]{decode(bytes.substr(0,end)+row+bytes.substr(end),id);});}
    const auto end=bytes.find('\n')+1;const auto next=bytes.find('\n',end)+1;
    rejects([&]{decode(bytes.substr(0,end)+bytes.substr(end,next-end)+bytes.substr(end),id);});
    altered=bytes;altered.replace(altered.find("\"caller\":"),9,"\"caller\":0");rejects([&]{decode(altered,id);});
    altered=bytes;altered.replace(altered.find("\"cycles\":10"),11,"\"cycles\":18446744073709551616");rejects([&]{decode(altered,id);});
    for(unsigned change=0;change<7;++change){ReplayCursor cursor(owned);auto bad=expected[0];
        if(change==0)++bad.order;
        if(change==1)++bad.native;
        if(change==2)++bad.cycles;
        if(change==3)++bad.tick;
        if(change==4)++bad.frame;
        if(change==5)bad.caller=0x8001AB18;
        if(change==6)++bad.pads[0][1];
        assert(!cursor.consume(bad,out));assert(!cursor.consume(expected[0],out));assert(cursor.consumed()==0);
    }
    ReplayCursor tag(owned);assert(tag.consume(expected[0],out));auto wrong=expected[1];wrong.consumer=1;
    assert(!tag.consume(wrong,out));assert(!tag.consume(expected[1],out));
    std::cout<<"strict offline reader/prefetch/identity/truncation/ordered N+C matcher PASS\n";
}
