#include "mmx6_coop_resources.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1); } } while (0)
enum { BIN_SIZE=0x18000,DAT_SIZE=0x400000,ARENA=0x80000 };
static uint8_t *bin,*dat;
static size_t bundle[5],end;
static void put32(uint8_t *p,uint32_t v) {
    unsigned i;for(i=0;i<4;++i)p[i]=(uint8_t)(v>>(8*i));
}
static size_t rounded(size_t n) { return (n+2047)&~(size_t)2047; }
static void descriptor(unsigned record,size_t start,size_t bytes) {
    CHECK(start%2048==0 && start+bytes<=DAT_SIZE);
    put32(dat+record*8,(uint32_t)(start/2048));put32(dat+record*8+4,(uint32_t)bytes);
}
static void add_bundle(unsigned member,size_t palette) {
    /* Original measured view sizes, synthetic bytes and no audio assets. */
    const uint32_t types[11]={9,0x1000B,0x10206,2,0,0,0x10007,0x10001,0x11,0x12,3};
    size_t sizes[11]={0,0x8000,0x1B800,0,0,0,0x8000,0x8000,0x800,0,0};
    size_t begin=end,cursor=begin+2048;unsigned i;
    sizes[0]=palette;sizes[3]=member==85?229672:245288;
    sizes[9]=member==85?9036:9252;sizes[10]=member==85?34084:41400;
    bundle[member-85]=begin;put32(dat+begin,11);
    for(i=0;i<11;++i) {
        CHECK(cursor+rounded(sizes[i])<=DAT_SIZE);
        put32(dat+begin+8+i*8,types[i]);put32(dat+begin+12+i*8,(uint32_t)sizes[i]);
        memset(dat+cursor,(int)(member+i),sizes[i]);cursor+=rounded(sizes[i]);
    }
    put32(dat+begin+4,(uint32_t)(cursor-begin));descriptor(member,begin,cursor-begin);end=cursor;
}
static void archives(size_t zero_palette) {
    unsigned record;
    memset(bin,0,BIN_SIZE);memset(dat,0,DAT_SIZE);end=2048;
    put32(bin,2);put32(bin+4,44588);put32(bin+4096,0x3C);
    put32(bin+8,24);put32(bin+12,22964);put32(bin+24*2048,0x3D);
    add_bundle(85,zero_palette);for(record=86;record<=89;++record)add_bundle(record,2688);
    for(record=163;record<=174;++record) {
        size_t size=(record&1)?8192:512;
        descriptor(record,end,size);memset(dat+end,(int)record,size);end+=rounded(size);
    }
}
static Mmx6CoopRoster roster(unsigned form) {
    Mmx6CoopRoster r;
    Mmx6CoopRosterNative n={(uint8_t)(form==5),(uint8_t)form,
                           (uint8_t)(form==5),(uint8_t)form,0};
    CHECK(mmx6_coop_roster_resolve(&n,&r)==MMX6_COOP_ROSTER_OK);return r;
}
static uint32_t digest(const uint8_t *p,size_t n) {
    uint32_t h=2166136261u;size_t i;for(i=0;i<n;++i)h=(h^p[i])*16777619u;return h;
}
static void plan_failure(const Mmx6CoopRoster *r,unsigned seat,size_t bs,size_t ds,
                         uint32_t capacity,Mmx6CoopResourcesReason expected) {
    Mmx6CoopResourceViews v,empty;uint32_t bh=digest(bin,BIN_SIZE),dh=digest(dat,DAT_SIZE);
    memset(&v,0xA5,sizeof v);memset(&empty,0,sizeof empty);
    CHECK(mmx6_coop_resource_prepare(r,seat,bin,bs,dat,ds,capacity,&v)==expected);
    CHECK(!memcmp(&v,&empty,sizeof v));
    CHECK(bh==digest(bin,BIN_SIZE) && dh==digest(dat,DAT_SIZE));
}
static void layout_failure(size_t g,size_t a,size_t p,size_t m,uint32_t cap,
                           Mmx6CoopResourcesReason expected) {
    Mmx6CoopResourceLayout v,empty;
    memset(&v,0xA5,sizeof v);memset(&empty,0,sizeof empty);
    CHECK(mmx6_coop_resource_layout(g,a,p,m,cap,&v)==expected);
    CHECK(!memcmp(&v,&empty,sizeof v));
}
static void layouts(void) {
    Mmx6CoopResourceLayout v;
    /* Measured source sizes + independent expected aligned offsets. */
    CHECK(mmx6_coop_resource_layout(229672,34084,2656,9036,ARENA,&v)==MMX6_COOP_RESOURCES_OK);
    CHECK(v.assembly==229680 && v.palette_source==263776 && v.active_palette==266432);
    CHECK(v.menu_assembly==282816 && v.used==291852);
    CHECK(mmx6_coop_resource_layout(245288,41400,2688,9252,315028,&v)==MMX6_COOP_RESOURCES_OK);
    CHECK(v.assembly==245296 && v.palette_source==286704 && v.active_palette==289392);
    CHECK(v.menu_assembly==305776 && v.used==315028);
    layout_failure(245288,41400,2688,9252,315027,MMX6_COOP_RESOURCES_ALLOCATION_BOUND);
    /* All three alignment gaps matter, even for one-byte source views. */
    CHECK(mmx6_coop_resource_layout(1,1,1,1,16433,&v)==MMX6_COOP_RESOURCES_OK);
    CHECK(v.assembly==16 && v.palette_source==32 && v.active_palette==48 && v.used==16433);
    layout_failure(1,1,1,1,16432,MMX6_COOP_RESOURCES_ALLOCATION_BOUND);
    layout_failure(SIZE_MAX,1,1,1,UINT32_MAX,MMX6_COOP_RESOURCES_ALLOCATION_BOUND);
    layout_failure(1,SIZE_MAX,1,1,UINT32_MAX,MMX6_COOP_RESOURCES_ALLOCATION_BOUND);
    layout_failure(1,1,1,SIZE_MAX,UINT32_MAX,MMX6_COOP_RESOURCES_ALLOCATION_BOUND);
    layout_failure(UINT32_MAX-15u,16,1,1,UINT32_MAX,MMX6_COOP_RESOURCES_ALLOCATION_BOUND);
    layout_failure(1,1,0x4001,1,UINT32_MAX,MMX6_COOP_RESOURCES_PALETTE_BOUND);
    /* Old sum+4040 and menu-end checks both fit this arena, but copying the
     * source palette again at active_palette would extend past its end. */
    layout_failure(16,16,0x30000,16,0x40000,MMX6_COOP_RESOURCES_PALETTE_BOUND);
    layout_failure(0,1,1,1,ARENA,MMX6_COOP_RESOURCES_INVALID_ARGUMENT);
    layout_failure(1,0,1,1,ARENA,MMX6_COOP_RESOURCES_INVALID_ARGUMENT);
    layout_failure(1,1,0,1,ARENA,MMX6_COOP_RESOURCES_INVALID_ARGUMENT);
    layout_failure(1,1,1,0,ARENA,MMX6_COOP_RESOURCES_INVALID_ARGUMENT);
    layout_failure(1,1,1,1,0,MMX6_COOP_RESOURCES_ALLOCATION_BOUND);
    CHECK(mmx6_coop_resource_layout(1,1,1,1,ARENA,NULL)==MMX6_COOP_RESOURCES_INVALID_ARGUMENT);
    CHECK(mmx6_coop_resource_layout(1,1,0x4000,1,ARENA,&v)==MMX6_COOP_RESOURCES_OK);
    CHECK(v.menu_assembly-v.active_palette==0x4000 && v.active_palette-v.palette_source==0x4000);
}
static void preparation(void) {
    Mmx6CoopRoster x=roster(0),zero=roster(5),bad;
    Mmx6CoopResourceViews v;unsigned form;uint32_t bh,dh;
    archives(2656);bh=digest(bin,BIN_SIZE);dh=digest(dat,DAT_SIZE);
    for(form=0;form<5;++form) {
        Mmx6CoopRoster primary=roster(form);
        CHECK(mmx6_coop_resources_fixed_runtime_admit(&primary)==MMX6_COOP_RESOURCES_OK);
        CHECK(mmx6_coop_resource_prepare(&primary,1,bin,BIN_SIZE,dat,DAT_SIZE,ARENA,&v)==MMX6_COOP_RESOURCES_OK);
        CHECK(v.overlay.data==bin+24*2048 && v.overlay.type==0x3D);
        CHECK(v.graphics.size==229672 && v.graphics.data[0]==88 && v.layout.used==291852);
        CHECK(v.portrait.data[0]==165 && v.portrait_colors.data[0]==166);
    }
    /* Native Zero/P1 uses the original base X overlay and UI for P2. */
    CHECK(mmx6_coop_resources_fixed_runtime_admit(&zero)==MMX6_COOP_RESOURCES_OK);
    CHECK(mmx6_coop_resource_prepare(&zero,1,bin,BIN_SIZE,dat,DAT_SIZE,ARENA,&v)==MMX6_COOP_RESOURCES_OK);
    CHECK(v.overlay.data==bin+4096 && v.overlay.type==0x3C && v.graphics.size==245288);
    CHECK(v.graphics.data[0]==89 && v.portrait.data[0]==163 && v.portrait_colors.data[0]==164);
    CHECK(v.layout.used==315028);
    CHECK(mmx6_coop_resource_prepare(&x,0,bin,BIN_SIZE,dat,DAT_SIZE,ARENA,&v)==MMX6_COOP_RESOURCES_OK);
    CHECK(v.portrait.data[0]==163);
    CHECK(bh==digest(bin,BIN_SIZE) && dh==digest(dat,DAT_SIZE));
    bad=x;bad.seat[1].dat_member=86;
    CHECK(mmx6_coop_resources_fixed_runtime_admit(&bad)==MMX6_COOP_RESOURCES_INVALID_ROSTER);
    plan_failure(&bad,1,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_ROSTER);
    plan_failure(NULL,1,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_ROSTER);
    plan_failure(&x,2,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_SEAT);
    plan_failure(&x,1,BIN_SIZE,DAT_SIZE,291851,MMX6_COOP_RESOURCES_ALLOCATION_BOUND);
    plan_failure(&x,1,4095,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_OVERLAY);
    plan_failure(&x,1,BIN_SIZE,2047,ARENA,MMX6_COOP_RESOURCES_INVALID_ASSET);
    put32(bin+24*2048,0x3C);
    plan_failure(&x,1,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_OVERLAY);
    put32(bin+24*2048,0x3D);put32(bin+12,0xB001);
    plan_failure(&x,1,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_OVERLAY);
    put32(bin+12,22964);put32(dat+bundle[0]+8+3*8,3);
    plan_failure(&x,1,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_ASSET);
    put32(dat+bundle[0]+8+3*8,2);put32(dat+bundle[0]+8+8*8,9);
    plan_failure(&x,1,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_UI);
    put32(dat+bundle[0]+8+8*8,0x11);put32(dat+bundle[0]+12+6*8,0x7FFF);
    plan_failure(&x,1,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_UI);
    put32(dat+bundle[0]+12+6*8,0x8000);put32(dat+166*8+4,511);
    plan_failure(&x,1,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_UI);
    archives(0x4001);
    plan_failure(&x,1,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_PALETTE_BOUND);
    CHECK(mmx6_coop_resource_prepare(&x,1,NULL,0,dat,DAT_SIZE,ARENA,&v)==MMX6_COOP_RESOURCES_INVALID_ARGUMENT);
    CHECK(mmx6_coop_resource_prepare(&x,1,bin,BIN_SIZE,NULL,0,ARENA,&v)==MMX6_COOP_RESOURCES_INVALID_ARGUMENT);
    CHECK(mmx6_coop_resource_prepare(&x,1,bin,BIN_SIZE,dat,DAT_SIZE,ARENA,NULL)==MMX6_COOP_RESOURCES_INVALID_ARGUMENT);
}
static void inverse_failures(void) {
    Mmx6CoopRoster zero=roster(5),bad;
    Mmx6CoopResourceViews v;
    archives(2656);
    /* The inverse primary still prepares the original ordinary Zero assets. */
    CHECK(mmx6_coop_resource_prepare(&zero,0,bin,BIN_SIZE,dat,DAT_SIZE,ARENA,&v)==MMX6_COOP_RESOURCES_OK);
    CHECK(v.overlay.data==bin+24*2048 && v.graphics.size==229672);
    CHECK(v.portrait.data[0]==165 && v.portrait_colors.data[0]==166);
    /* Every supported partner form keeps its own source DAT and portrait. */
    for(unsigned form=1;form<=3;++form) {
        Mmx6CoopRosterNative n={1,5,1,5,7};Mmx6CoopRoster selected;
        CHECK(mmx6_coop_roster_resolve_partner(&n,form,255,&selected)==MMX6_COOP_ROSTER_OK);
        CHECK(mmx6_coop_resources_fixed_runtime_admit(&selected)==MMX6_COOP_RESOURCES_OK);
        CHECK(mmx6_coop_resource_prepare(&selected,1,bin,BIN_SIZE,dat,DAT_SIZE,ARENA,&v)==MMX6_COOP_RESOURCES_OK);
        CHECK(v.overlay.data==bin+4096 && v.graphics.data[0]==89+form);
        CHECK(v.portrait.data[0]==167+form*2 && v.portrait_colors.data[0]==168+form*2);
    }
    bad=zero;bad.seat[1]=roster(4).seat[0];
    CHECK(mmx6_coop_resources_fixed_runtime_admit(&bad)==MMX6_COOP_RESOURCES_INVALID_ROSTER);
    bad=zero;bad.seat[1].portrait_palette=166;
    CHECK(mmx6_coop_resources_fixed_runtime_admit(&bad)==MMX6_COOP_RESOURCES_INVALID_ROSTER);
    plan_failure(&zero,1,BIN_SIZE,DAT_SIZE,315027,MMX6_COOP_RESOURCES_ALLOCATION_BOUND);
    plan_failure(&zero,1,4096+44588-1,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_OVERLAY);
    put32(bin+4096,0x3D);
    plan_failure(&zero,1,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_OVERLAY);
    put32(bin+4096,0x3C);put32(bin+4,0xB001);
    plan_failure(&zero,1,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_OVERLAY);
    archives(2656);put32(dat+bundle[1]+8+3*8,3);
    plan_failure(&zero,1,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_ASSET);
    archives(2656);put32(dat+bundle[1]+12+7*8,0x7FFF);
    plan_failure(&zero,1,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_UI);
    archives(2656);put32(dat+163*8+4,0x1FFF);
    plan_failure(&zero,1,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_UI);
    archives(2656);put32(dat+164*8+4,0x1FF);
    plan_failure(&zero,1,BIN_SIZE,DAT_SIZE,ARENA,MMX6_COOP_RESOURCES_INVALID_UI);
}
int main(void) {
    bin=malloc(BIN_SIZE);dat=malloc(DAT_SIZE);CHECK(bin && dat);
    layouts();preparation();inverse_failures();free(bin);free(dat);
    CHECK(!strcmp(mmx6_coop_resources_reason(MMX6_COOP_RESOURCES_UNSUPPORTED_RUNTIME_ROSTER),"unsupported_runtime_roster"));
    puts("X6 bounded typed resource plans/aligned allocations/fixed runtime admission PASS");return 0;
}
