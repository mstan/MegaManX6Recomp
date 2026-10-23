/* Optional read-only publication; base schema1/1958h remains unchanged.
 * The base odd/even sequence protects this extension in the same RPC. */
#ifndef MMX6_COOP_EFFECT_DIAGNOSTIC_H
#define MMX6_COOP_EFFECT_DIAGNOSTIC_H
enum {
    MMX6_FX_DIAG_HEADER=0x1A00,
    MMX6_FX_DIAG_MAGIC=0x58463658, /* little-endian "X6FX" */
    MMX6_FX_DIAG_SCHEMA=1,
    MMX6_FX_DIAG_TRAILS=0x1A10,
    MMX6_FX_DIAG_ATTACHED=0x1B30,
    MMX6_FX_DIAG_END=0x1C20,
    MMX6_FX_DIAG_BYTES=MMX6_FX_DIAG_END-MMX6_FX_DIAG_HEADER
};
typedef char Mmx6EffectsDiagnosticFitsAllocation[(MMX6_FX_DIAG_END<=0x2000)?1:-1];
#endif
