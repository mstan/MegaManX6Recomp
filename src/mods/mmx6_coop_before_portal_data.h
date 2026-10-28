/* Original EXE/BIN6/DAT98 guards for the declared portal approach.
 * Source identities and derivation: docs/COOP_HOST_LAB_CONTRACT.json. */
#ifndef MMX6_COOP_BEFORE_PORTAL_DATA_H
#define MMX6_COOP_BEFORE_PORTAL_DATA_H
enum { PORTAL_SETUP_LAYOUT=0x80097438u, PORTAL_SETUP_LAYOUT_BYTES=528,
    PORTAL_SETUP_WIDTH=22, PORTAL_SETUP_HEIGHT=8, PORTAL_SETUP_LAYER_STRIDE=176,
    PORTAL_SETUP_META_BYTES=87040, PORTAL_SETUP_DESC_BYTES=8000 };
#define PORTAL_SETUP_LAYOUT_FNV 0x2BB42374u
#define PORTAL_SETUP_METATILES_FNV 0xFE37745Eu
#define PORTAL_SETUP_DESCRIPTORS_FNV 0xFFE72AE8u
static const Mmx6CheckpointCode portal_setup_code[]={
    {0x800205A0u,0x800206C0u,0x68415FC8u}, /* solid_update */
    {0x8004F834u,0x8004F880u,0xBFA4A25Fu}, /* phase_dispatch */
    {0x80078C7Cu,0x80078CA0u,0xDE33DFBEu}, /* phase_table */
    {0x8004E800u,0x8004EA78u,0xEB920F5Au}, /* initialize */
    {0x8004EA78u,0x8004EC30u,0xFF84D348u}, /* idle */
    {0x8004EECCu,0x8004EFD0u,0xEABAA832u}, /* contact */
    {0x8002DCF4u,0x8002DE54u,0xAE99F9CDu}, /* body_contact_geometry */
    {0x8004FE8Cu,0x8004FEFCu,0x1332611Du}, /* facing_animation_selection */
    {0x800179A4u,0x80017A44u,0xFA84E5FDu}, /* animation */
    {0x8002CBFCu,0x8002CD6Cu,0x97A22C42u}, /* offscreen_visibility */
    {0x80078910u,0x80078914u,0x0B82089Du}, /* body_box */
    {0x80029E7Cu,0x8002A0F8u,0x5CF2D299u}, /* scanner_record_mutation */
    {0x8002C4C4u,0x8002C530u,0x012FD433u}, /* category4_allocator */
    {0x80051158u,0x80051490u,0x7FAE8260u}, /* capsule_initialize */
    {0x80051890u,0x80051924u,0xEF8DDF11u}, /* capsule_update */
    {0x80051924u,0x80051A44u,0x0CA9AFDCu}, /* capsule_trigger */
    {0x80078E18u,0x80078E2Cu,0x2CF77087u}, /* capsule_action_table */
    {0x80078DF8u,0x80078E04u,0x800B5361u}, /* capsule_boxes */
};
#endif
