/* Read-only actual native126 breadcrumbs. Never simulation/snapshot state.
 * Counts saturate; use a fresh baseline and the existing uninterrupted actor
 * lifetime evidence, including after any execution-state load. No generation
 * or allocation lifetime is inferred from a slot counter alone.
 * Two additive spans fit the existing2000h diagnostic allocation, outside
 * base1958h, FX, box and energy publications; the base sequence protects both.
 * Record: count:u16, boss-slot:u8, HP:u8, native-frame:u32,
 * shot-header:3bytes, token:u8, parent:u32 (all integers little-endian).
 */
#ifndef MMX6_COOP_HIT_DIAGNOSTIC_H
#define MMX6_COOP_HIT_DIAGNOSTIC_H
#include <stdint.h>
enum {
    MMX6_HIT_DIAG_HEADER=0x1958,
    MMX6_HIT_DIAG_MAGIC=0x52483658u, /* "X6HR" */
    MMX6_HIT_DIAG_SCHEMA=1,
    MMX6_HIT_DIAG_RECORDS=0x1968,
    MMX6_HIT_DIAG_FIRST_COUNT=8,
    MMX6_HIT_DIAG_FIRST_END=0x19E8,
    MMX6_HIT_DIAG_REST=0x1C60,
    MMX6_HIT_DIAG_END=0x1FE0,
    MMX6_HIT_DIAG_SLOTS=32,
    MMX6_HIT_DIAG_STRIDE=16
};
typedef struct {
    uint16_t count;
    uint8_t boss_slot,hp;
    uint32_t frame;
    uint8_t header[3],token;
    uint32_t parent;
} Mmx6HitDiagnostic;
typedef char Mmx6HitDiagnosticRecordSize[(sizeof(Mmx6HitDiagnostic)==16)?1:-1];
typedef char Mmx6HitDiagnosticFirstFits[(MMX6_HIT_DIAG_FIRST_END<=0x1A00)?1:-1];
typedef char Mmx6HitDiagnosticRestFits[(MMX6_HIT_DIAG_END<=0x1FF0)?1:-1];
#endif
