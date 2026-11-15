#undef NDEBUG
#include "../src/mods/mmx6_native_pair.h"
#include <cassert>
#include <cstdio>
using namespace mmx6_native;
static Frame frame(uint64_t serial,uint32_t tick,int x,int y,int bank,unsigned seat){
    Frame f;f.epoch=9;f.serial=serial;f.tick=tick;
    f.environment.mode=0x20;f.environment.area={0,uint32_t(bank*240),319,uint32_t(bank*240+239),0,bank*240};
    const uint32_t clear[]={0x02000040,uint32_t(bank*240)<<16,320|(240u<<16)};
    assert(f.add(0,clear,3,{}));
    Motion motion;motion.key=1;motion.identity=100+seat;motion.world=true;motion.x=x;motion.y=y;
    const uint32_t sprite[]={0x7C808080,uint16_t(x)|(uint32_t(uint16_t(y))<<16),0x79000000};
    assert(f.add(0xB0004,sprite,3,motion));
    const uint32_t fade[]={0x2A000020,0,319,240u<<16,(240u<<16)|319};
    assert(f.add(0xB1004,fade,5,{}));
    return f;
}
int main(){
    auto a0=frame(1,10,10,20,0,0),a1=frame(1,10,100,30,0,1);
    auto b0=frame(2,12,14,24,1,0),b1=frame(2,12,108,34,1,1);
    PairPrepared pair;
    assert(pair.build({&a0,&a1},{&b0,&b1},{41,42},.5));
    assert(pair.triangles.size()==12 && pair.materials.size()==6);
    assert(pair.crop[0][0]==0 && pair.crop[1][0]==320 && pair.crop[1][2]==320 && pair.crop[1][3]==240);
    assert(std::fabs(pair.triangles[2].vertices[0].x-12)<.0001);
    assert(std::fabs(pair.triangles[8].vertices[0].x-424)<.0001);
    assert(pair.materials[1].texture_version==41 && pair.materials[4].texture_version==42);
    assert(pair.materials[0].clip[0]==0 && pair.materials[0].clip[2]==319);
    assert(pair.materials[4].clip[0]==320 && pair.materials[4].clip[2]==639);
    assert(pair.materials[2].semi==1 && pair.materials[5].semi==1); // exact current overlay order and blend
    assert(pair.triangles[6].identity>>63); // per-view identities never cross-pair
    assert(!pair.build({&a0,nullptr},{&b0,&b1},{41,42},.5) && pair.triangles.empty());
    assert(!pair.build({&a0,&a1},{&b0,&b1},{41,0},.5) && pair.triangles.empty());
    b1.serial=3;
    assert(!pair.build({&a0,&a1},{&b0,&b1},{41,42},.5));
    b1.serial=2;b1.valid=false;
    assert(!pair.build({&a0,&a1},{&b0,&b1},{41,42},.5) && pair.triangles.empty());
    puts("PASS immutable pair: independent sprite motion/materials, clear/fade order, pane clips and whole-pair fallback");
}
