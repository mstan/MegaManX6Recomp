/* Resident ROCK_X6.DAT / ROCK_X6.BIN store for Seamless Loading. */
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum { MMX6_SEAMLESS_DAT = 0, MMX6_SEAMLESS_BIN = 1 };

/* Load the verified pack for the active mod plan, or prepare it from the
 * mounted disc. Returns 1 when resident data is available. */
int mmx6_seamless_prepare(void);
unsigned mmx6_seamless_archive_count(void);
uint32_t mmx6_seamless_archive_sectors(unsigned archive);
/* Effective descriptor table parsed from the resident archive header. */
unsigned mmx6_seamless_member_count(unsigned archive);
int mmx6_seamless_member(unsigned archive, unsigned index, uint32_t *offset, uint32_t *size);
/* 2048 user-data bytes of an archive-relative sector, or NULL. */
const unsigned char *mmx6_seamless_sector(unsigned archive, uint32_t sector);
/* Members whose bytes differ from the original disc (asset mods). */
unsigned mmx6_seamless_modified_members(void);
/* Live loader code/data matches the original executable. */
int mmx6_seamless_guard_ok(void);

#ifdef __cplusplus
}
#endif
