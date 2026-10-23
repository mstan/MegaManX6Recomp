/* Additive read-only publication, protected by the base odd/even sequence. */
#ifndef MMX6_COOP_BOX_DIAGNOSTIC_H
#define MMX6_COOP_BOX_DIAGNOSTIC_H
enum {
    MMX6_BOX_DIAG_HEADER=0x1C20,
    MMX6_BOX_DIAG_MAGIC=0x58423658, /* little-endian "X6BX" */
    MMX6_BOX_DIAG_SCHEMA=1,
    MMX6_BOX_DIAG_BYTES=0x40,
    MMX6_BOX_DIAG_RECORDS=0x1C30,
    MMX6_BOX_DIAG_END=0x1C60,
    MMX6_BOX_UNAVAILABLE=0,
    MMX6_BOX_NATIVE_RAM=1,
    MMX6_BOX_PRIVATE_OVERLAY=2
};
typedef char Mmx6BoxDiagnosticFitsAllocation[(MMX6_BOX_DIAG_END<=0x2000)?1:-1];
#endif
