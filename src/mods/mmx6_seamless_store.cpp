/* Native first-run preparation of ROCK_X6.DAT and ROCK_X6.BIN from the
 * player's mounted disc. The pack contains original (or mod-effective) disc
 * resources only, never initialized game state. X6 stores these resources
 * uncompressed, so preparation is a verified copy; no decoding is involved. */
#include "mmx6_seamless_store.h"
#include "mod_plugins.h"
#include "mod_runtime.h"
#include "psx_sha256.h"
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <system_error>
#include <vector>
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <unistd.h>
#endif

namespace {
using Bytes = std::vector<unsigned char>;
struct GuardRange { uint32_t lo, hi; };
struct ArchiveFile { const char *path; unsigned lba, size, count; const char *hash; };
struct ArchiveMember { unsigned archive, index, offset, size; const char *hash; };
#include "mmx6_seamless_catalog.inc"

constexpr char kMagic[8] = {'X', '6', 'R', 'E', 'S', '0', '0', '1'};
constexpr unsigned kKeepPacks = 4;
/* Largest file on an 80-minute CD; asset mods may grow ROCK_X6.DAT into the
 * padding file that follows it (e.g. the retranslation, ~66 MiB). */
constexpr uint32_t kMaxArchiveBytes = 360000u * 2048u;

struct Archive {
    Bytes data;          /* sector padded */
    uint32_t size = 0;   /* file bytes */
    std::vector<std::pair<uint32_t, uint32_t>> members;  /* {sector offset, bytes} */
};
std::vector<Archive> resident;
unsigned modified_members = 0;
unsigned archive_differs = 0;

std::string hex(const unsigned char *h) {
    char out[65];
    for (unsigned i = 0; i < 32; i++) std::snprintf(out + 2 * i, 3, "%02x", h[i]);
    return out;
}
std::string digest(const unsigned char *p, size_t n) {
    unsigned char h[32];
    psx_sha256_compute(p, n, h);
    return hex(h);
}
std::string digest(const Bytes &b) { return digest(b.data(), b.size()); }

std::filesystem::path cache_dir() {
    if (const char *p = std::getenv("MMX6_SEAMLESS_CACHE"))
        if (*p) return p;
    std::filesystem::path root;
#ifdef _WIN32
    if (const char *p = std::getenv("LOCALAPPDATA")) root = p;
#else
    if (const char *p = std::getenv("XDG_CACHE_HOME")) root = p;
    else if (const char *p = std::getenv("HOME")) root = std::filesystem::path(p) / ".cache";
#endif
    if (root.empty()) throw std::runtime_error("no cache directory");
    return root / "MegaManX6Recomp" / "seamless";
}

/* The plan fingerprint covers package order, selections, disc writes and
 * overlays, derived discs and the source disc hash. A changed asset plan can
 * never reuse another plan's pack; packs are also verified on every load. */
std::filesystem::path cache_path() {
    const auto &plan = PSXRecompV4::mod_runtime_fingerprint();
    const auto key = digest(reinterpret_cast<const unsigned char *>(plan.data()), plan.size());
    return cache_dir() / ("slus01395-resident-v1-" + key + ".pack");
}

/* Parse and bound the archive's own descriptor header, exactly as the game's
 * initializers will (count fixed by original code at 0x800147D0/0x80016780). */
void parse(Archive &a, unsigned count) {
    if (a.data.size() < 4096) throw std::runtime_error("archive header missing");
    a.members.clear();
    const uint32_t sectors = uint32_t(a.data.size() / 2048);
    for (unsigned i = 0; i < count; i++) {
        uint32_t offset, size;
        std::memcpy(&offset, a.data.data() + i * 8, 4);
        std::memcpy(&size, a.data.data() + i * 8 + 4, 4);
        if (offset < 2 || offset >= sectors || size > (sectors - offset) * 2048u)
            throw std::runtime_error("archive descriptor out of bounds");
        a.members.emplace_back(offset, size);
    }
}

/* Classify effective content against the original disc catalog. Differences
 * are permitted (asset mods); they are counted, never silently replaced. */
void classify() {
    modified_members = archive_differs = 0;
    std::vector<bool> stock(std::size(archives));
    for (size_t i = 0; i < std::size(archives); i++) {
        stock[i] = resident[i].size == archives[i].size && digest(resident[i].data) == archives[i].hash;
        if (!stock[i]) ++archive_differs;
    }
    for (const auto &m : members) {
        if (stock[m.archive]) continue;
        const auto &a = resident[m.archive];
        const auto &[offset, size] = a.members.at(m.index);
        const size_t n = size_t((size + 2047u) / 2048u) * 2048u;
        if (offset != m.offset || size != m.size ||
            digest(a.data.data() + size_t(offset) * 2048u, n) != m.hash)
            ++modified_members;
    }
}

bool load(const std::filesystem::path &path, std::vector<Archive> &out) {
    std::ifstream in(path, std::ios::binary);
    char magic[8];
    if (!in.read(magic, 8) || std::memcmp(magic, kMagic, 8)) return false;
    out.assign(std::size(archives), Archive{});
    for (size_t i = 0; i < out.size(); i++) {
        uint32_t size;
        unsigned char hash[32];
        if (!in.read(reinterpret_cast<char *>(&size), 4) || !size || size > kMaxArchiveBytes ||
            !in.read(reinterpret_cast<char *>(hash), 32)) return false;
        out[i].size = size;
        out[i].data.resize((size + 2047u) & ~2047u);
        if (!in.read(reinterpret_cast<char *>(out[i].data.data()), std::streamsize(out[i].data.size())) ||
            digest(out[i].data) != hex(hash)) return false;
    }
    if (in.peek() != std::char_traits<char>::eof()) return false;
    for (size_t i = 0; i < out.size(); i++) parse(out[i], archives[i].count);
    return true;
}

void publish(const std::filesystem::path &path, const std::vector<Archive> &data) {
    std::filesystem::create_directories(path.parent_path());
    auto tmp = path;
#ifdef _WIN32
    tmp += "." + std::to_string(GetCurrentProcessId()) + ".tmp";
#else
    tmp += "." + std::to_string(getpid()) + ".tmp";
#endif
    {
        std::ofstream out(tmp, std::ios::binary | std::ios::trunc);
        out.write(kMagic, 8);
        for (const auto &a : data) {
            unsigned char hash[32];
            psx_sha256_compute(a.data.data(), a.data.size(), hash);
            out.write(reinterpret_cast<const char *>(&a.size), 4);
            out.write(reinterpret_cast<const char *>(hash), 32);
            out.write(reinterpret_cast<const char *>(a.data.data()), std::streamsize(a.data.size()));
        }
        out.close();
        if (!out) {
            std::error_code ec;
            std::filesystem::remove(tmp, ec);
            throw std::runtime_error("cannot write prepared resource pack");
        }
    }
#ifdef _WIN32
    if (!MoveFileExW(tmp.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        std::error_code ec;
        std::filesystem::remove(tmp, ec);
        throw std::runtime_error("cannot publish prepared resource pack");
    }
#else
    std::filesystem::rename(tmp, path);
#endif
}

/* Each pack is ~52 MB. Keep the active plan's pack and a few recent others. */
void prune(const std::filesystem::path &keep) {
    std::error_code ec;
    std::vector<std::filesystem::directory_entry> packs;
    for (const auto &e : std::filesystem::directory_iterator(keep.parent_path(), ec)) {
        const auto name = e.path().filename().string();
        if (e.path() != keep && name.rfind("slus01395-resident-", 0) == 0) packs.push_back(e);
    }
    if (packs.size() < kKeepPacks) return;
    std::sort(packs.begin(), packs.end(), [](const auto &a, const auto &b) {
        std::error_code e1, e2;
        return a.last_write_time(e1) > b.last_write_time(e2);
    });
    for (size_t i = kKeepPacks - 1; i < packs.size(); i++) std::filesystem::remove(packs[i].path(), ec);
}

std::vector<Archive> prepare() {
    std::fprintf(stdout, "mmx6 seamless: preparing disc resources (one time)\n");
    std::fflush(stdout);
    std::vector<Archive> out(std::size(archives));
    for (size_t i = 0; i < out.size(); i++) {
        uint32_t size = 0;
        if (!psx_mod_read_disc_file(archives[i].path, nullptr, 0, &size) || !size ||
            size > kMaxArchiveBytes)
            throw std::runtime_error(std::string("cannot size ") + archives[i].path);
        out[i].size = size;
        out[i].data.assign((size + 2047u) & ~2047u, 0);
        uint32_t got = 0;
        if (!psx_mod_read_disc_file(archives[i].path, out[i].data.data(),
                                    uint32_t(out[i].data.size()), &got) || got != size)
            throw std::runtime_error(std::string("cannot read ") + archives[i].path);
        parse(out[i], archives[i].count);
    }
    return out;
}
}  // namespace

extern "C" int mmx6_seamless_prepare(void) {
    try {
        const auto path = cache_path();
        std::vector<Archive> data;
        const bool warm = load(path, data);
        if (!warm) {
            data = prepare();
            publish(path, data);
        } else {
            std::error_code ec;
            std::filesystem::last_write_time(path, std::filesystem::file_time_type::clock::now(), ec);
        }
        resident = std::move(data);
        classify();
        prune(path);
        size_t bytes = 0;
        for (const auto &a : resident) bytes += a.data.size();
        std::fprintf(stdout,
                     "mmx6 seamless: %s pack, %zu archives, %zu resident bytes, %u/%zu members differ "
                     "from the original disc; cache=%s\n",
                     warm ? "verified" : "prepared", resident.size(), bytes, modified_members,
                     std::size(members), path.string().c_str());
        std::fflush(stdout);
        return 1;
    } catch (const std::exception &e) {
        resident.clear();
        modified_members = archive_differs = 0;
        std::fprintf(stderr, "mmx6 seamless: preparation failed (%s); using original loading\n", e.what());
        return 0;
    }
}

extern "C" unsigned mmx6_seamless_archive_count(void) { return unsigned(resident.size()); }

extern "C" unsigned mmx6_seamless_member_count(unsigned archive) {
    return archive < resident.size() ? unsigned(resident[archive].members.size()) : 0;
}

extern "C" int mmx6_seamless_member(unsigned archive, unsigned index, uint32_t *offset, uint32_t *size) {
    if (archive >= resident.size() || index >= resident[archive].members.size()) return 0;
    *offset = resident[archive].members[index].first;
    *size = resident[archive].members[index].second;
    return 1;
}

extern "C" uint32_t mmx6_seamless_archive_sectors(unsigned archive) {
    return archive < resident.size() ? uint32_t(resident[archive].data.size() / 2048) : 0;
}

extern "C" const unsigned char *mmx6_seamless_sector(unsigned archive, uint32_t sector) {
    if (archive >= resident.size() || sector >= resident[archive].data.size() / 2048) return nullptr;
    return resident[archive].data.data() + size_t(sector) * 2048u;
}

extern "C" unsigned mmx6_seamless_modified_members(void) { return modified_members; }

extern "C" int mmx6_seamless_guard_ok(uint8_t (*read)(uint32_t)) {
    psx_sha256_ctx ctx;
    psx_sha256_init(&ctx);
    for (const auto &g : guard_ranges) {
        uint8_t chunk[256];
        for (uint32_t a = g.lo; a < g.hi;) {
            uint32_t n = std::min<uint32_t>(sizeof chunk, g.hi - a);
            for (uint32_t i = 0; i < n; i++) chunk[i] = read(a + i);
            psx_sha256_update(&ctx, chunk, n);
            a += n;
        }
    }
    unsigned char h[32];
    psx_sha256_final(&ctx, h);
    return hex(h) == guard_sha256;
}
