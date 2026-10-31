#include "mmx6_coop_resources.h"
#include <string.h>

Mmx6CoopResourcesReason mmx6_coop_resources_fixed_runtime_admit(const Mmx6CoopRoster *r) {
    if (mmx6_coop_roster_validate(r)!=MMX6_COOP_ROSTER_OK)
        return MMX6_COOP_RESOURCES_INVALID_ROSTER;
    return MMX6_COOP_RESOURCES_OK;
}

static int aligned_span(size_t bytes,uint32_t cap,uint32_t *cursor) {
    uint32_t aligned;
    if (bytes>UINT32_MAX-15u) return 0;
    aligned=((uint32_t)bytes+15u)&~15u;
    if (aligned>cap-*cursor) return 0;
    *cursor+=aligned;
    return 1;
}
Mmx6CoopResourcesReason mmx6_coop_resource_layout(size_t graphics,size_t assembly,
    size_t palette,size_t menu,uint32_t capacity,Mmx6CoopResourceLayout *out) {
    Mmx6CoopResourceLayout r;
    uint32_t cursor=0;
    if (out) memset(out,0,sizeof *out);
    if (!out || !graphics || !assembly || !palette || !menu)
        return MMX6_COOP_RESOURCES_INVALID_ARGUMENT;
    if (palette>MMX6_COOP_WORKING_PALETTE_BYTES)
        return MMX6_COOP_RESOURCES_PALETTE_BOUND;
    if (!aligned_span(graphics,capacity,&cursor))
        return MMX6_COOP_RESOURCES_ALLOCATION_BOUND;
    r.assembly=cursor;
    if (!aligned_span(assembly,capacity,&cursor))
        return MMX6_COOP_RESOURCES_ALLOCATION_BOUND;
    r.palette_source=cursor;
    if (!aligned_span(palette,capacity,&cursor))
        return MMX6_COOP_RESOURCES_ALLOCATION_BOUND;
    r.active_palette=cursor;
    if (MMX6_COOP_WORKING_PALETTE_BYTES>capacity-cursor)
        return MMX6_COOP_RESOURCES_ALLOCATION_BOUND;
    cursor+=MMX6_COOP_WORKING_PALETTE_BYTES;r.menu_assembly=cursor;
    if (menu>capacity-cursor) return MMX6_COOP_RESOURCES_ALLOCATION_BOUND;
    r.used=cursor+(uint32_t)menu;
    *out=r;
    return MMX6_COOP_RESOURCES_OK;
}

static int asset(const uint8_t *dat,size_t size,unsigned member,unsigned index,
                 uint32_t type,Mmx6AssetView *view) {
    return mmx6_coop_dat_asset(dat,size,member,index,view) &&
        view->size && view->type==type;
}
Mmx6CoopResourcesReason mmx6_coop_resource_prepare(const Mmx6CoopRoster *roster,
    unsigned seat,const uint8_t *bin,size_t bin_size,const uint8_t *dat,size_t dat_size,
    uint32_t capacity,Mmx6CoopResourceViews *out) {
    Mmx6CoopResourceViews v;
    const Mmx6CoopRosterActor *actor;
    Mmx6CoopResourcesReason reason;
    if (out) memset(out,0,sizeof *out);
    if (!out || !bin || !dat) return MMX6_COOP_RESOURCES_INVALID_ARGUMENT;
    if (mmx6_coop_roster_validate(roster)!=MMX6_COOP_ROSTER_OK)
        return MMX6_COOP_RESOURCES_INVALID_ROSTER;
    if (seat>1) return MMX6_COOP_RESOURCES_INVALID_SEAT;
    actor=&roster->seat[seat];
    if (!mmx6_coop_overlay(bin,bin_size,actor->bin_member,&v.overlay) ||
        v.overlay.size>MMX6_COOP_OVERLAY_BYTES || v.overlay.type!=actor->bin_type)
        return MMX6_COOP_RESOURCES_INVALID_OVERLAY;
    if (!asset(dat,dat_size,actor->dat_member,3,2,&v.graphics) ||
        !asset(dat,dat_size,actor->dat_member,10,3,&v.assembly) ||
        !asset(dat,dat_size,actor->dat_member,0,9,&v.palette))
        return MMX6_COOP_RESOURCES_INVALID_ASSET;
    if (!asset(dat,dat_size,actor->dat_member,6,0x00010007,&v.menu_graphics) ||
        v.menu_graphics.size!=0x8000 ||
        !asset(dat,dat_size,actor->dat_member,7,0x00010001,&v.font) || v.font.size!=0x8000 ||
        !asset(dat,dat_size,actor->dat_member,8,0x11,&v.menu_colors) || v.menu_colors.size!=0x800 ||
        !asset(dat,dat_size,actor->dat_member,9,0x12,&v.menu_layout) ||
        !asset(dat,dat_size,actor->dat_member,1,0x0001000B,&v.common) || v.common.size!=0x8000 ||
        !asset(dat,dat_size,actor->dat_member,2,0x00010206,&v.icons) || v.icons.size!=0x1B800 ||
        !mmx6_coop_dat_record(dat,dat_size,actor->portrait_graphics,&v.portrait) ||
        v.portrait.size!=0x2000 ||
        !mmx6_coop_dat_record(dat,dat_size,actor->portrait_palette,&v.portrait_colors) ||
        v.portrait_colors.size!=0x200)
        return MMX6_COOP_RESOURCES_INVALID_UI;
    reason=mmx6_coop_resource_layout(v.graphics.size,v.assembly.size,v.palette.size,
                                    v.menu_layout.size,capacity,&v.layout);
    if (reason!=MMX6_COOP_RESOURCES_OK) return reason;
    *out=v;
    return MMX6_COOP_RESOURCES_OK;
}

const char *mmx6_coop_resources_reason(Mmx6CoopResourcesReason reason) {
    switch (reason) {
    case MMX6_COOP_RESOURCES_OK:return "ok";
    case MMX6_COOP_RESOURCES_INVALID_ARGUMENT:return "invalid_argument";
    case MMX6_COOP_RESOURCES_INVALID_ROSTER:return "invalid_roster";
    case MMX6_COOP_RESOURCES_UNSUPPORTED_RUNTIME_ROSTER:return "unsupported_runtime_roster";
    case MMX6_COOP_RESOURCES_INVALID_SEAT:return "invalid_seat";
    case MMX6_COOP_RESOURCES_INVALID_OVERLAY:return "invalid_overlay";
    case MMX6_COOP_RESOURCES_INVALID_ASSET:return "invalid_asset";
    case MMX6_COOP_RESOURCES_INVALID_UI:return "invalid_ui";
    case MMX6_COOP_RESOURCES_PALETTE_BOUND:return "palette_bound";
    case MMX6_COOP_RESOURCES_ALLOCATION_BOUND:return "allocation_bound";
    default:return "unknown_resources_reason";
    }
}
