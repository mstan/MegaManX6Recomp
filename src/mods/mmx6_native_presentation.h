#ifndef MMX6_NATIVE_PRESENTATION_H
#define MMX6_NATIVE_PRESENTATION_H
/* Immutable native 2D drawing. The old scene receives the NEW frame's exact
 * animation/UV/color/primitive shape and only the authored previous rigid pose.
 * This is sprite/camera transport, never image or vertex correspondence. */
#include "gpu.h"
#include "presentation_scene.h"
#include "presentation_draw.h"
#include "presentation_gpu.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <map>
#include <memory>
#include <vector>

namespace mmx6_native {
constexpr unsigned MaxPackets=16384, MaxVertices=MaxPackets*6;
struct Motion {
    uint64_t key=0, identity=0;
    double x=0,y=0, camera_x=0,camera_y=0;
    bool world=false;
};
struct Primitive {
    uint64_t identity=0;
    Motion motion{};
    PsxPresentationMaterial material{};
    PsxPresentationVertex vertices[6]{};
    unsigned count=0;
};
struct SceneDelete { void operator()(PsxPresentationScene* p)const{psx_presentation_scene_destroy(p);} };
struct DrawDelete { void operator()(PsxPresentationDraw* p)const{psx_presentation_draw_destroy(p);} };
using Scene=std::unique_ptr<PsxPresentationScene,SceneDelete>;
using Draw=std::unique_ptr<PsxPresentationDraw,DrawDelete>;
struct Frame {
    uint64_t epoch=0, serial=0;
    uint32_t tick=0;
    GpuDrawingEnvironment environment{};
    GpuDrawArea target{};
    bool target_set=false,valid=true;
    const char* failure="";
    uint8_t filter=0;
    bool accurate=false;
    std::map<uint64_t,Motion> motions;
    std::vector<Primitive> primitives;
    unsigned moved=0;
    bool reject(const char* reason){valid=false;failure=reason;return false;}
    void anchor(const Motion& m){if(m.key)motions[m.key]=m;}
    static int signed11(uint32_t x){return (int(x&2047)^1024)-1024;}
    uint32_t color(uint32_t value,bool textured)const {
        uint32_t result=0xFF000000u;
        for(unsigned k=0;k<3;++k){
            unsigned c=(value>>(8*k))&255;
            if(!textured){c>>=3;c=accurate?c*8:unsigned(std::lround(c*255.0/31.0));}
            result|=c<<(8*k);
        }
        return result;
    }
    bool add(uint32_t source,const uint32_t* w,unsigned n,const Motion& motion,
             const int32_t* ui_x=nullptr,const int32_t* ui_y=nullptr) {
        if(!valid || !n)return valid;
        const unsigned op=w[0]>>24;
        auto& env=environment;
        if(op>=0xE1 && op<=0xE6){
            if(n!=1)return reject("invalid environment command");
            switch(op){
            case 0xE1:env.mode=(env.mode&~0x83FFu)|(w[0]&0x3FFu)|((w[0]&(1u<<11))<<4);break;
            case 0xE2:env.texture_window=w[0]&0xFFFFFu;break;
            case 0xE3:env.area.left=w[0]&1023;env.area.top=(w[0]>>10)&511;break;
            case 0xE4:env.area.right=w[0]&1023;env.area.bottom=(w[0]>>10)&511;break;
            case 0xE5:env.area.offset_x=signed11(w[0]);env.area.offset_y=signed11(w[0]>>11);break;
            case 0xE6:env.mode=(env.mode&~0x1800u)|((w[0]&3u)<<11);break;
            }return true;
        }
        if(op==0 || op==1)return n==1 || reject("invalid no-op");
        if(primitives.size()>=MaxPackets)return reject("primitive capacity");
        if(!target_set){target=env.area;target_set=true;}
        Primitive p{};p.identity=uint64_t(primitives.size())+1;p.motion=motion;
        auto& m=p.material;m.filter=filter;m.texture_window=env.texture_window;
        m.clip[0]=int16_t(env.area.left);m.clip[1]=int16_t(env.area.top);
        m.clip[2]=int16_t(env.area.right);m.clip[3]=int16_t(env.area.bottom);
        m.texpage=uint16_t(env.mode&511);m.semi=(op&2)?int16_t((env.mode>>5)&3):-1;
        if(env.mode&(1u<<11))m.flags|=PSX_PRESENTATION_MASK_SET;
        if(env.mode&(1u<<12))m.flags|=PSX_PRESENTATION_MASK_CHECK;
        PsxPresentationVertex v[4]{};unsigned points=0;
        const bool rectangle=(op&0xE0)==0x60, polygon=(op&0xE0)==0x20;
        const bool textured=(op&4)!=0,shaded=(op&16)!=0;
        if(rectangle){
            unsigned size=(op>>3)&3;const unsigned fixed[4]={0,1,8,16};
            const unsigned expected=size?(textured?3:2):(textured?4:3);
            if(n!=expected)return reject("rectangle word count");
            uint32_t wh=size?0:w[textured?3:2];
            unsigned width=size?fixed[size]:(textured?wh&1023:std::min(wh&65535u,1023u));
            unsigned height=size?fixed[size]:(textured?(wh>>16)&511:std::min(wh>>16,511u));
            if(!width || !height)return true;
            const int x=signed11(w[1])+env.area.offset_x,y=signed11(w[1]>>16)+env.area.offset_y;
            unsigned u=0,vv=0;
            if(textured){
                const unsigned clut=w[2]>>16;m.clut_x=uint16_t((clut&63)*16);m.clut_y=uint16_t((clut>>6)&511);
                u=w[2]&255;vv=(w[2]>>8)&255;
                m.uv_limits[0]=uint16_t(u+width<=256?u:0);m.uv_limits[2]=uint16_t(u+width<=256?u+width-1:255);
                m.uv_limits[1]=uint16_t(vv+height<=256?vv:0);m.uv_limits[3]=uint16_t(vv+height<=256?vv+height-1:255);
            }
            for(unsigned j=0;j<4;++j){
                v[j].position[0]=ui_x?ui_x[j]+env.area.offset_x:x+((j&1)?width:0);
                v[j].position[1]=ui_y?ui_y[j]+env.area.offset_y:y+((j&2)?height:0);
                v[j].position[2]=1;v[j].rgba=color(w[0],textured);
                v[j].uv[0]=float(u+((j&1)?width:0));v[j].uv[1]=float(vv+((j&2)?height:0));
            }points=4;
        }else if(polygon){
            points=(op&8)?4:3;const unsigned stride=1+unsigned(textured)+unsigned(shaded);
            if(n!=points*stride+unsigned(!shaded))return reject("polygon word count");
            if(textured){
                m.texpage=uint16_t(w[2+stride]>>16);env.mode=(env.mode&~511u)|(m.texpage&511u);
                const unsigned clut=w[2]>>16;m.clut_x=uint16_t((clut&63)*16);m.clut_y=uint16_t((clut>>6)&511);
                m.uv_limits[0]=m.uv_limits[1]=255;
            }
            m.semi=(op&2)?int16_t((env.mode>>5)&3):-1;
            for(unsigned j=0;j<points;++j){
                const uint32_t xy=w[1+j*stride];
                v[j].position[0]=(ui_x?ui_x[j]:signed11(xy))+env.area.offset_x;
                v[j].position[1]=(ui_y?ui_y[j]:signed11(xy>>16))+env.area.offset_y;
                v[j].position[2]=1;v[j].rgba=color(shaded?w[j*stride]:w[0],textured);
                if(textured){
                    const uint32_t uv=w[2+j*stride];v[j].uv[0]=float(uv&255);v[j].uv[1]=float((uv>>8)&255);
                    for(unsigned k=0;k<2;++k){m.uv_limits[k]=uint16_t(std::min(unsigned(m.uv_limits[k]),unsigned(v[j].uv[k])));
                        m.uv_limits[k+2]=uint16_t(std::max(unsigned(m.uv_limits[k+2]),unsigned(v[j].uv[k])));}
                }
            }
        }else if(op==2){
            if(n!=3)return reject("fill word count");
            m={};m.semi=-1;m.clip[2]=1023;m.clip[3]=511;
            const unsigned x=w[1]&0x3F0,y=(w[1]>>16)&511;
            const unsigned width=((w[2]&1023)+15)&~15u,height=(w[2]>>16)&511;
            if(!width || !height)return true;
            if(x+width>1024 || y+height>512)return reject("wrapped fill");
            for(unsigned j=0;j<4;++j){v[j].position[0]=x+((j&1)?width:0);v[j].position[1]=y+((j&2)?height:0);
                v[j].position[2]=1;v[j].rgba=color(w[0],false);}points=4;p.motion={};
        }else return reject("unsupported native command");
        if(textured && op!=2){m.flags|=PSX_PRESENTATION_TEXTURED;if(op&1)m.flags|=PSX_PRESENTATION_RAW_TEXTURE;}
        if((env.mode&(1u<<9)) && ((textured && !(op&1)) || shaded))m.flags|=PSX_PRESENTATION_DITHER;
        const unsigned indices[2][3]={{0,1,2},{1,2,3}};p.count=points==4?6:3;
        for(unsigned t=0;t<p.count/3;++t)for(unsigned k=0;k<3;++k){
            auto vertex=v[indices[t][k]];
            vertex.position[0]-=p.motion.x;vertex.position[1]-=p.motion.y;
            p.vertices[t*3+k]=vertex;
        }
        anchor(p.motion);primitives.push_back(p);return true;
    }
};
struct Prepared {
    Draw draw{nullptr};
    std::vector<PsxPresentationMaterial> materials;
    unsigned matched=0,cuts=0;
    const char* failure="";
    bool build(const Frame& old,const Frame& now,uint64_t texture,double alpha){
        matched=cuts=0;materials.clear();
        if(!old.valid || !now.valid || !old.target_set || !now.target_set ||
           old.epoch!=now.epoch || old.serial+1!=now.serial || now.tick-old.tick<1 || now.tick-old.tick>8){failure="nonadjacent scene";return false;}
        unsigned vertices=0;for(const auto& p:now.primitives)vertices+=p.count;
        const unsigned objects=unsigned(now.primitives.size());
        if(!objects || objects>MaxPackets || vertices>MaxVertices){failure="empty or oversized source";return false;}
        Scene a(psx_presentation_scene_create(objects,vertices,objects,objects*sizeof(PsxPresentationMaterial)));
        Scene b(psx_presentation_scene_create(objects,vertices,objects,objects*sizeof(PsxPresentationMaterial)));
        if(!a || !b){failure="scene allocation";return false;}
        PsxPresentationCamera camera{};camera.pose.rotation[0]=1;
        camera.pose.scale[0]=camera.pose.scale[1]=camera.pose.scale[2]=1;
        camera.focal_x=camera.focal_y=1;camera.near_z=.1;
        if(!psx_presentation_scene_begin(a.get(),now.epoch,old.tick,&camera) ||
           !psx_presentation_scene_begin(b.get(),now.epoch,now.tick,&camera)){failure="scene begin";return false;}
        const double limit=96.0*double(now.tick-old.tick);
        for(const auto& p:now.primitives){
            auto material=p.material;material.texture_version=texture;
            uint32_t ra=0,rb=0;
            if(!psx_presentation_scene_resource(a.get(),&material,sizeof material,&ra) ||
               !psx_presentation_scene_resource(b.get(),&material,sizeof material,&rb) || ra!=rb){failure="scene resource";return false;}
            materials.push_back(material);
            PsxPresentationObject object{};object.identity=p.identity;object.lifetime=now.epoch;object.topology=p.identity;
            object.pose.rotation[0]=1;object.pose.scale[0]=object.pose.scale[1]=object.pose.scale[2]=1;
            object.pose.position[0]=p.motion.x;object.pose.position[1]=p.motion.y;
            object.vertices=p.vertices;object.vertex_count=p.count;object.resource=rb;
            object.flags=PSX_PRESENTATION_AFFINE_UV;
            const auto previous=old.motions.find(p.motion.key);
            const bool same=p.motion.key && p.motion.world && previous!=old.motions.end() && previous->second.identity==p.motion.identity;
            bool move=false;
            if(same){
                const auto& q=previous->second;
                move=std::fabs((p.motion.x+p.motion.camera_x)-(q.x+q.camera_x))<=limit &&
                     std::fabs((p.motion.y+p.motion.camera_y)-(q.y+q.camera_y))<=limit &&
                     std::fabs(p.motion.camera_x-q.camera_x)<=limit && std::fabs(p.motion.camera_y-q.camera_y)<=limit;
                if(!move)++cuts;
            }
            if(!move)object.flags|=PSX_PRESENTATION_NATIVE;
            if(!psx_presentation_scene_append(b.get(),&object)){failure="current append";return false;}
            if(move){object.pose.position[0]=previous->second.x;object.pose.position[1]=previous->second.y;++matched;}
            if(!psx_presentation_scene_append(a.get(),&object)){failure="previous append";return false;}
        }
        if(!matched){failure="no authored motion pair";return false;}
        if(!psx_presentation_scene_seal(a.get()) || !psx_presentation_scene_seal(b.get())){failure="scene seal";return false;}
        if(!draw)draw.reset(psx_presentation_draw_create(MaxVertices,MaxPackets*12));
        const PsxPresentationViewport viewport{0,0,1024,512};
        if(!draw || !psx_presentation_draw_build(draw.get(),a.get(),b.get(),alpha,&viewport)){failure="draw build";return false;}
        failure="";return true;
    }
};
}
#endif
