#ifndef MMX6_COOP_RESOURCES_H
#define MMX6_COOP_RESOURCES_H
#include "mmx6_coop_assets.h"
#include "mmx6_coop_roster.h"

enum { MMX6_COOP_OVERLAY_BYTES=0xB000, MMX6_COOP_WORKING_PALETTE_BYTES=0x4000 };
typedef enum {
    MMX6_COOP_RESOURCES_OK,
    MMX6_COOP_RESOURCES_INVALID_ARGUMENT,
    MMX6_COOP_RESOURCES_INVALID_ROSTER,
    MMX6_COOP_RESOURCES_UNSUPPORTED_RUNTIME_ROSTER,
    MMX6_COOP_RESOURCES_INVALID_SEAT,
    MMX6_COOP_RESOURCES_INVALID_OVERLAY,
    MMX6_COOP_RESOURCES_INVALID_ASSET,
    MMX6_COOP_RESOURCES_INVALID_UI,
    MMX6_COOP_RESOURCES_PALETTE_BOUND,
    MMX6_COOP_RESOURCES_ALLOCATION_BOUND
} Mmx6CoopResourcesReason;

typedef struct {
    uint32_t assembly, palette_source, active_palette, menu_assembly, used;
} Mmx6CoopResourceLayout;
typedef struct {
    Mmx6AssetView overlay,graphics,assembly,palette;
    Mmx6AssetView menu_graphics,font,menu_colors,menu_layout;
    Mmx6AssetView portrait,portrait_colors,common,icons;
    Mmx6CoopResourceLayout layout;
} Mmx6CoopResourceViews;

/* Validate the native primary and its opposite base counterpart. Black Zero
 * remains a distinct unsupported native variant; never clear persistent bits. */
Mmx6CoopResourcesReason mmx6_coop_resources_fixed_runtime_admit(const Mmx6CoopRoster *roster);

/* Checked 32-bit guest offsets, including every 16-byte alignment gap, the
 * complete source palette and 4000h working window, then the native menu.
 * No pointers/allocations/writes. A failure clears a non-null output. */
Mmx6CoopResourcesReason mmx6_coop_resource_layout(size_t graphics,size_t assembly,
    size_t palette,size_t menu,uint32_t capacity,Mmx6CoopResourceLayout *out);

/* Bounded typed views into CALLER-OWNED archive buffers, valid until those
 * buffers are released. No file I/O, allocation, guest call, or publication.
 * This checks descriptors/types/extents, not a cryptographic content identity
 * or native readiness. The caller binds its mounted-disc/content identity.
 * Supports either canonical seat; runtime must
 * ALSO use fixed_runtime_admit. On failure a non-null output is cleared. */
Mmx6CoopResourcesReason mmx6_coop_resource_prepare(const Mmx6CoopRoster *roster,
    unsigned seat,const uint8_t *bin,size_t bin_size,const uint8_t *dat,size_t dat_size,
    uint32_t capacity,Mmx6CoopResourceViews *out);
const char *mmx6_coop_resources_reason(Mmx6CoopResourcesReason reason);
#endif
