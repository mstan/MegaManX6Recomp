/* ROCK_X6.DAT and ROCK_X6.BIN held resident through the framework's resident
 * disc packs (mod_resident.h): read once from the effective (mod-patched)
 * disc, SHA-256 verified, cached per mod plan. X6 stores these archives
 * uncompressed, so nothing is derived; this file only parses and classifies
 * each archive's own descriptor table. */
#include "mmx6_seamless_store.h"
#include "mod_plugins.h"
#include "mod_resident.h"
#include "psx_sha256.h"
#include <cstdio>
#include <cstring>
#include <iterator>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {
struct GuardRange { uint32_t lo, hi; };
struct ArchiveFile { const char *path; unsigned lba, size, count; const char *hash; };
struct ArchiveMember { unsigned archive, index, offset, size; const char *hash; };
#include "mmx6_seamless_catalog.inc"

/* Largest file on an 80-minute CD; asset mods may grow ROCK_X6.DAT into the
 * padding file that follows it (e.g. the retranslation, ~66 MiB). */
constexpr uint32_t kMaxArchiveBytes = 360000u * 2048u;

const PSXResidentPack *pack;
std::vector<std::vector<std::pair<uint32_t, uint32_t>>> descriptors; /* {sector, bytes} */
unsigned modified_members;

std::string digest(const uint8_t *p, size_t n) {
    uint8_t h[32];
    char out[65];
    psx_sha256_compute(p, n, h);
    for (unsigned i = 0; i < 32; i++) std::snprintf(out + 2 * i, 3, "%02x", h[i]);
    return out;
}

/* Parse and bound the archive's descriptor header exactly as the game's
 * initializers will (count fixed by original code at 0x800147D0/0x80016780). */
std::vector<std::pair<uint32_t, uint32_t>> parse(const uint8_t *data, uint32_t padded, unsigned count) {
    if (padded < 4096) throw std::runtime_error("archive header missing");
    std::vector<std::pair<uint32_t, uint32_t>> out;
    const uint32_t sectors = padded / 2048;
    for (unsigned i = 0; i < count; i++) {
        uint32_t offset, size;
        std::memcpy(&offset, data + i * 8, 4);
        std::memcpy(&size, data + i * 8 + 4, 4);
        if (offset < 2 || offset >= sectors || size > (sectors - offset) * 2048u)
            throw std::runtime_error("archive descriptor out of bounds");
        out.emplace_back(offset, size);
    }
    return out;
}

/* Members of a modified archive that differ from the original disc. */
unsigned classify() {
    unsigned modified = 0;
    for (const auto &m : members) {
        if (psx_resident_file_stock(pack, m.archive)) continue;
        uint32_t padded = 0;
        const uint8_t *data = psx_resident_file(pack, m.archive, nullptr, &padded);
        const auto &[offset, size] = descriptors.at(m.archive).at(m.index);
        const size_t n = size_t((size + 2047u) / 2048u) * 2048u;
        if (offset != m.offset || size != m.size || digest(data + size_t(offset) * 2048u, n) != m.hash)
            ++modified;
    }
    return modified;
}
}  // namespace

extern "C" int mmx6_seamless_prepare(void) {
    static PSXResidentFile files[std::size(archives)];
    for (size_t i = 0; i < std::size(archives); i++)
        files[i] = {archives[i].path, archives[i].size, archives[i].hash};
    PSXResidentSpec spec{};
    spec.struct_size = sizeof spec;
    spec.title = "MegaManX6Recomp";
    spec.format = "slus01395-archives-v2";
    spec.files = files;
    spec.file_count = uint32_t(std::size(files));
    spec.policy = PSX_RESIDENT_ALLOW_MODIFIED;
    spec.max_file_bytes = kMaxArchiveBytes;
    descriptors.clear();
    modified_members = 0;
    pack = psx_resident_prepare(&spec);
    if (!pack) return 0;
    try {
        for (size_t i = 0; i < std::size(archives); i++) {
            uint32_t padded = 0;
            const uint8_t *data = psx_resident_file(pack, uint32_t(i), nullptr, &padded);
            descriptors.push_back(parse(data, padded, archives[i].count));
        }
        modified_members = classify();
    } catch (const std::exception &) {
        pack = nullptr;
        descriptors.clear();
        psx_mod_counter_add("mmx6.seamless.archive_rejected", 1);
        return 0;
    }
    psx_mod_counter_add("mmx6.seamless.modified_members", modified_members);
    return 1;
}

extern "C" unsigned mmx6_seamless_archive_count(void) { return pack ? unsigned(descriptors.size()) : 0; }

extern "C" unsigned mmx6_seamless_member_count(unsigned archive) {
    return pack && archive < descriptors.size() ? unsigned(descriptors[archive].size()) : 0;
}

extern "C" int mmx6_seamless_member(unsigned archive, unsigned index, uint32_t *offset, uint32_t *size) {
    if (!pack || archive >= descriptors.size() || index >= descriptors[archive].size()) return 0;
    *offset = descriptors[archive][index].first;
    *size = descriptors[archive][index].second;
    return 1;
}

extern "C" uint32_t mmx6_seamless_archive_sectors(unsigned archive) {
    uint32_t padded = 0;
    return pack && psx_resident_file(pack, archive, nullptr, &padded) ? padded / 2048u : 0;
}

extern "C" const unsigned char *mmx6_seamless_sector(unsigned archive, uint32_t sector) {
    uint32_t padded = 0;
    const uint8_t *data = pack ? psx_resident_file(pack, archive, nullptr, &padded) : nullptr;
    return data && sector < padded / 2048u ? data + size_t(sector) * 2048u : nullptr;
}

extern "C" unsigned mmx6_seamless_modified_members(void) { return modified_members; }

extern "C" int mmx6_seamless_guard_ok(void) {
    static PSXResidentRange ranges[std::size(guard_ranges)];
    for (size_t i = 0; i < std::size(guard_ranges); i++) ranges[i] = {guard_ranges[i].lo, guard_ranges[i].hi};
    return psx_resident_guest_ranges_match(ranges, uint32_t(std::size(ranges)), guard_sha256);
}
