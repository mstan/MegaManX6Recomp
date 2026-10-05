/* Integration test for Seamless Loading preparation using an owner-supplied
 * disc image. No disc data is distributed; the catalog holds metadata only. */
#include "mmx6_seamless_store.h"
#include "psx_sha256.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace {
struct GuardRange { uint32_t lo, hi; };
struct ArchiveFile { const char *path; unsigned lba, size, count; const char *hash; };
struct ArchiveMember { unsigned archive, index, offset, size; const char *hash; };
#include "../src/mods/mmx6_seamless_catalog.inc"

std::ifstream disc;
unsigned reads;
bool available = true;
/* Simulated asset mod: replace bytes inside one DAT member's sectors. */
int patch_member = -1;
std::string fingerprint = "stock-test-plan";
std::vector<unsigned char> exe_text;

void require(bool ok, const char *what) {
    if (!ok) { std::fprintf(stderr, "FAIL: %s\n", what); std::exit(1); }
}
std::string hash(const unsigned char *p, size_t n) {
    unsigned char h[32]; char hex[65];
    psx_sha256_compute(p, n, h);
    for (unsigned i = 0; i < 32; i++) std::snprintf(hex + 2 * i, 3, "%02x", h[i]);
    return hex;
}
bool read_user(unsigned lba, unsigned char *out) {
    unsigned char raw[2352];
    disc.clear();
    disc.seekg(std::streamoff(lba) * 2352);
    if (!disc.read(reinterpret_cast<char *>(raw), sizeof raw) || raw[15] != 2 || (raw[18] & 0x20)) return false;
    std::memcpy(out, raw + 24, 2048);
    return true;
}
uint8_t exe_byte(uint32_t address) { return exe_text.at(address - 0x80010000u); }
uint8_t modified_exe_byte(uint32_t address) {
    return address == 0x80015230u ? uint8_t(exe_byte(address) ^ 1u) : exe_byte(address);
}
}  // namespace

namespace PSXRecompV4 {
const std::string &mod_runtime_fingerprint() { return fingerprint; }
}

extern "C" int psx_mod_read_disc_file(const char *path, void *buffer, uint32_t capacity, uint32_t *size) {
    ++reads;
    if (size) *size = 0;
    if (!available) return 0;
    for (const auto &a : archives) {
        if (std::strcmp(a.path, path)) continue;
        if (!buffer) { *size = a.size; return 1; }
        if (capacity < a.size) return 0;
        unsigned char sector[2048];
        for (uint32_t offset = 0; offset < a.size; offset += 2048) {
            if (!read_user(a.lba + offset / 2048, sector)) return 0;
            std::memcpy(static_cast<unsigned char *>(buffer) + offset, sector,
                        std::min<uint32_t>(2048u, a.size - offset));
        }
        if (patch_member >= 0 && !std::strcmp(path, "ROCK_X6.DAT")) {
            const auto &m = members[patch_member];
            static_cast<unsigned char *>(buffer)[m.offset * 2048u + 16u] ^= 0x5A;
        }
        *size = a.size;
        return 1;
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        std::fprintf(stderr, "usage: mmx6_seamless_store_test disc.bin scratch-directory\n");
        return 2;
    }
    /* A fresh, test-owned cache directory beneath the scratch directory. */
    const auto cache = std::filesystem::absolute(argv[2]) /
        ("run-" + std::to_string(std::filesystem::file_time_type::clock::now().time_since_epoch().count()));
    require(!std::filesystem::exists(cache), "test requires a fresh cache directory");
#ifdef _WIN32
    _putenv_s("MMX6_SEAMLESS_CACHE", cache.string().c_str());
#else
    setenv("MMX6_SEAMLESS_CACHE", cache.string().c_str(), 1);
#endif
    disc.open(argv[1], std::ios::binary);
    require(bool(disc), "disc open");

    /* Original executable from the disc, for the loader-code guard. */
    {
        unsigned char sector[2048], pvd[2048];
        require(read_user(16, pvd), "volume descriptor");
        uint32_t root, root_size;
        std::memcpy(&root, pvd + 158, 4); std::memcpy(&root_size, pvd + 166, 4);
        std::vector<unsigned char> dir;
        for (uint32_t i = 0; i < (root_size + 2047) / 2048; i++) {
            require(read_user(root + i, sector), "root directory");
            dir.insert(dir.end(), sector, sector + 2048);
        }
        uint32_t lba = 0, size = 0;
        for (size_t p = 0; p < dir.size();) {
            if (!dir[p]) { p = (p / 2048 + 1) * 2048; continue; }
            if (std::string(reinterpret_cast<char *>(&dir[p + 33]), dir[p + 32]).rfind("SLUS_013.95", 0) == 0) {
                std::memcpy(&lba, &dir[p + 2], 4); std::memcpy(&size, &dir[p + 10], 4);
            }
            p += dir[p];
        }
        require(lba && size > 0x800, "boot executable");
        std::vector<unsigned char> exe;
        for (uint32_t i = 0; i < (size + 2047) / 2048; i++) {
            require(read_user(lba + i, sector), "boot executable read");
            exe.insert(exe.end(), sector, sector + 2048);
        }
        exe_text.assign(exe.begin() + 0x800, exe.begin() + size);
    }
    require(mmx6_seamless_guard_ok(exe_byte), "original loader guard matches the executable");
    require(!mmx6_seamless_guard_ok(modified_exe_byte), "modified loader code rejected");

    require(mmx6_seamless_prepare() == 1 && reads == 4, "cold native preparation");
    require(mmx6_seamless_modified_members() == 0, "stock disc classified as original");
    for (const auto &m : members) {
        uint32_t offset = 0, size = 0;
        require(mmx6_seamless_member(m.archive, m.index, &offset, &size) &&
                offset == m.offset && size == m.size, "resident descriptor table");
        std::vector<unsigned char> bytes;
        for (uint32_t s = 0; s < (size + 2047) / 2048; s++) {
            const unsigned char *p = mmx6_seamless_sector(m.archive, offset + s);
            require(p != nullptr, "resident member sector");
            bytes.insert(bytes.end(), p, p + 2048);
        }
        require(hash(bytes.data(), bytes.size()) == m.hash, "resident member hash");
    }
    require(!mmx6_seamless_sector(MMX6_SEAMLESS_DAT, mmx6_seamless_archive_sectors(MMX6_SEAMLESS_DAT)),
            "sector past archive end rejected");
    require(!mmx6_seamless_sector(7, 0), "unknown archive rejected");

    reads = 0; available = false;
    require(mmx6_seamless_prepare() == 1 && reads == 0, "warm launch uses the verified pack");

    std::filesystem::path stock_pack;
    for (const auto &e : std::filesystem::directory_iterator(cache)) stock_pack = e.path();

    /* An asset mod changes the plan fingerprint and the effective disc. The
     * stock pack must not be reused; the modified bytes are what is served. */
    fingerprint = "asset-mod-plan"; patch_member = 5;
    require(mmx6_seamless_prepare() == 0 && !mmx6_seamless_sector(0, 2),
            "changed plan cannot reuse the stock pack");
    available = true; reads = 0;
    require(mmx6_seamless_prepare() == 1 && reads == 4, "asset-mod plan prepared from the effective disc");
    require(mmx6_seamless_modified_members() == 1, "modified member classified");
    {
        const auto &m = members[patch_member];
        unsigned char original[2048];
        require(read_user(archives[0].lba + m.offset, original), "original member sector");
        const unsigned char *p = mmx6_seamless_sector(0, m.offset);
        require(p && p[16] == uint8_t(original[16] ^ 0x5A), "effective modified bytes are served");
    }
    fingerprint = "stock-test-plan"; patch_member = -1; available = false;
    require(mmx6_seamless_prepare() == 1 && mmx6_seamless_modified_members() == 0,
            "returning to the stock plan reuses its own pack");

    { std::fstream out(stock_pack, std::ios::in | std::ios::out | std::ios::binary);
      out.seekp(4096 + 44); out.put(char(0xAA)); }
    available = true; reads = 0;
    require(mmx6_seamless_prepare() == 1 && reads == 4, "corrupt pack rebuilt from the disc");
    { std::ofstream out(stock_pack, std::ios::binary | std::ios::trunc); out.write("X6RES001", 8); }
    available = false;
    require(mmx6_seamless_prepare() == 0 && !mmx6_seamless_sector(0, 2),
            "failed repair leaves no resident state (original loading)");
    std::error_code ec;
    std::filesystem::remove_all(cache, ec);
    std::printf("PASS: cold/warm preparation, %zu member hashes, loader guard, asset-mod plan "
                "isolation and classification, corruption repair, fail-closed fallback\n",
                std::size(members));
    return 0;
}
