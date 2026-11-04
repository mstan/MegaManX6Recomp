#include "mmx6_coop_private_view_sdk_fixture.h"
#include "psx_netplay.h"
#include <string.h>
Mmx6ViewSdkFixture mmx6_view_sdk;
void mmx6_view_sdk_reset(void) { memset(&mmx6_view_sdk,0,sizeof mmx6_view_sdk); }
int psx_mod_current_option_value(const char *id,char *out,uint32_t size) {
    const char *value=NULL;
    if(!id || !out || !size)return 0;
    out[0]=0;
    if(!strcmp(id,"local_cameras"))value=mmx6_view_sdk.local_cameras;
    else if(!strcmp(id,"cameras"))value=mmx6_view_sdk.cameras;
    else return 0;
    if(!value)value="unified";
    if(strlen(value)>=size)return 0;
    memcpy(out,value,strlen(value)+1);return 1;
}
int psx_netplay_local_port(void) { return mmx6_view_sdk.local_port; }
int psx_mod_set_fixed_display_aspect(uint32_t n,uint32_t d) {
    ++mmx6_view_sdk.aspect_calls;return n==4 && d==3;
}
int psx_mod_set_local_pair_presentation(int enabled) {
    if(enabled!=0 && enabled!=1)return 0;
    if(enabled && mmx6_view_sdk.online && !mmx6_view_sdk.netplay_allowed)return 0;
    mmx6_view_sdk.pair_enabled=enabled;return 1;
}
int psx_mod_set_render_pass_netplay(int enabled) {
    mmx6_view_sdk.netplay_allowed=!!enabled;return 1;
}
int psx_mod_render_local_view(CPUState *cpu,const PSXModRenderPass *r,PSXModRenderPassFn fn,void *user) {
    ++mmx6_view_sdk.view_calls;
    if(!mmx6_view_sdk.online || !cpu || !r || r->struct_size!=sizeof *r ||
       !r->w || !r->h || !fn || mmx6_view_sdk.busy || !mmx6_view_sdk.transaction)return 0;
    mmx6_view_sdk.busy=1;
    int ok=mmx6_view_sdk.transaction(cpu,fn,user,r->alpha_q16);
    mmx6_view_sdk.busy=0;return ok;
}
int psx_mod_render_local_pair(CPUState *cpu,const PSXModStereoFrame *f,PSXModStereoFn fn,void *user) {
    ++mmx6_view_sdk.pair_calls;
    if((mmx6_view_sdk.online && !mmx6_view_sdk.netplay_allowed) || !cpu || !f || f->struct_size!=sizeof *f ||
       !f->w || !f->h || f->period_vblanks<1 || f->period_vblanks>8 ||
       !fn || mmx6_view_sdk.busy || !mmx6_view_sdk.transaction)return 0;
    mmx6_view_sdk.busy=1;
    int ok=mmx6_view_sdk.transaction(cpu,fn,user,0);
    if(ok)ok=mmx6_view_sdk.transaction(cpu,fn,user,1);
    mmx6_view_sdk.busy=0;return ok;
}
/* The focused co-op fixture does not execute the independent background
 * emitter; its packet/region contract is exercised by adaptive_background. */
int mmx6_adaptive_background_activate(void) { return 1; }
void mmx6_adaptive_background_reset(void) {}
void mmx6_adaptive_background_begin(unsigned layer) { (void)layer; }
void mmx6_private_background_end(unsigned layer,uint32_t packet) { (void)layer;(void)packet; }
int mmx6_adaptive_background_resolve_bank(uint16_t id) { return id==0x5001u || id==0x5002u; }
void gpu_ws_bg2d_begin_view_layer(unsigned layer,uint32_t packet,unsigned mask) { (void)layer;(void)packet;(void)mask; }
