#ifndef MMX6_NATIVE_PAIR_H
#define MMX6_NATIVE_PAIR_H
#include "mmx6_native_presentation.h"
#include <array>
namespace mmx6_native {
/* One immutable GPU target holds both current native panes. Neither pane is
 * published unless BOTH complete scene pairs and retained material versions
 * are available. Source clipping/mask state remains independent per pane. */
struct PairPrepared {
    Prepared panes[2];
    std::vector<PsxPresentationTriangle> triangles;
    std::vector<PsxPresentationMaterial> materials;
    int crop[2][4]{};
    const char* failure="";
    bool build(const std::array<const Frame*,2>& old,const std::array<const Frame*,2>& now,
               const std::array<uint64_t,2>& textures,double alpha) {
        triangles.clear();materials.clear();
        if(!old[0] || !old[1] || !now[0] || !now[1] || !textures[0] || !textures[1] ||
           now[0]->serial!=now[1]->serial || now[0]->epoch!=now[1]->epoch ||
           old[0]->serial!=old[1]->serial || old[0]->epoch!=old[1]->epoch ||
           now[0]->tick!=now[1]->tick || old[0]->tick!=old[1]->tick ||
           now[0]->tick-old[0]->tick!=1){failure="incomplete native pair";return false;}
        /* Stack the two owned panes vertically: the fixed1024x512 target
         * then retains wide panes instead of limiting each to512 pixels. */
        unsigned y=0,width=0,height=0;
        for(unsigned eye=0;eye<2;++eye){
            const auto& area=now[eye]->target;
            if(area.right<area.left || area.bottom<area.top){failure="native pane bounds";return false;}
            const unsigned w=area.right-area.left+1,h=area.bottom-area.top+1;
            if(!w || w>1024 || h>512 || y>512-h || (eye && (width!=w || height!=h))){failure="native pair target bounds";return false;}
            if(!panes[eye].build(*old[eye],*now[eye],textures[eye],alpha)){
                failure=panes[eye].failure;triangles.clear();materials.clear();return false;
            }
            uint32_t count=0;const auto* source=psx_presentation_draw_triangles(panes[eye].draw.get(),&count);
            const unsigned material_base=unsigned(materials.size());
            for(auto material:panes[eye].materials){
                material.clip[0]=int16_t(std::max(int(material.clip[0]),int(area.left))-int(area.left));
                material.clip[1]=int16_t(std::max(int(material.clip[1]),int(area.top))-int(area.top)+int(y));
                material.clip[2]=int16_t(std::min(int(material.clip[2]),int(area.right))-int(area.left));
                material.clip[3]=int16_t(std::min(int(material.clip[3]),int(area.bottom))-int(area.top)+int(y));
                materials.push_back(material);
            }
            for(unsigned i=0;i<count;++i){
                auto triangle=source[i];triangle.resource+=material_base;
                triangle.identity|=uint64_t(eye)<<63;
                for(auto& vertex:triangle.vertices){vertex.x-=area.left;vertex.y+=double(y)-area.top;}
                triangles.push_back(triangle);
            }
            crop[eye][0]=0;crop[eye][1]=int(y);crop[eye][2]=int(w);crop[eye][3]=int(h);
            y+=h;width=w;height=h;
        }
        failure="";return true;
    }
};
}
#endif
