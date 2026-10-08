/* Seamless Loading compatibility matrix for the bundled mod catalog.
 *
 * Resolves every feature of every bundled package on its own (plus the
 * all-features plan when it resolves) and classifies what the plan changes:
 *   - disc writes/overlays inside ROCK_X6.DAT / ROCK_X6.BIN members: the
 *     resident pack is prepared from the effective disc, so these are served
 *     modified ("served-modified");
 *   - main-EXE writes overlapping the adapter's guarded loader code/data or a
 *     trusted blocking call site: the adapter must fall back to the original
 *     loader ("original-loader");
 *   - anything else does not interact with resident loading.
 * The printed matrix is the documented support table; assertions pin it. */
#include "mod_packages.h"
#include "mmx6_seamless_callers.h"

#include <algorithm>
#include <cstdio>
#include <filesystem>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace {
struct GuardRange { uint32_t lo, hi; };
struct ArchiveFile { const char *path; unsigned lba, size, count; const char *hash; };
struct ArchiveMember { unsigned archive, index, offset, size; const char *hash; };
#include "../src/mods/mmx6_seamless_catalog.inc"

constexpr const char *kGameId = "SLUS-01395";
constexpr const char *kStockDiscSha256 =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";
constexpr uint32_t kExeLba = 210930, kExeSectors = 255;  /* SLUS_013.95 on disc */
constexpr uint32_t kRootDirLba = 22;                     /* ISO root directory */
/* ZNULL.DAT pads the disc directly after ROCK_X6.DAT. Mods relocate grown
 * DAT records there and extend ROCK_X6.DAT's directory size to cover them. */
constexpr uint32_t kZnullLba = 236858, kZnullSectors = 18088;

int fail(const std::string &m) { std::cerr << "FAIL: " << m << "\n"; return 1; }
void no_op_plugin() {}

struct Row {
    std::string name, error;
    std::set<std::string> members;   /* "DAT[12]" / "BIN[3]" touched */
    unsigned disc_exe = 0, disc_other = 0, main_writes = 0, dir_writes = 0, growth = 0;
    uint32_t other_lo = ~0u, other_hi = 0;
    std::set<uint32_t> guard_hits, site_hits;
    bool derived = false;
    std::string verdict() const {
        if (!error.empty()) return "unresolved";
        if (!guard_hits.empty() || !site_hits.empty()) return "original-loader";
        if (derived) return "served-modified (derived disc)";
        if (!members.empty()) return "served-modified";
        return "unaffected";
    }
};

std::string member_of(uint32_t lba) {
    for (size_t a = 0; a < std::size(archives); a++) {
        const uint32_t sectors = (archives[a].size + 2047u) / 2048u;
        if (lba < archives[a].lba || lba >= archives[a].lba + sectors) continue;
        const uint32_t rel = lba - archives[a].lba;
        for (const auto &m : members)
            if (m.archive == a && rel >= m.offset && rel < m.offset + (m.size + 2047u) / 2048u)
                return std::string(a ? "BIN[" : "DAT[") + std::to_string(m.index) + "]";
        return std::string(a ? "BIN" : "DAT") + "-header";
    }
    return {};
}

void classify_disc(Row &row, PSXRecompV4::ModPatchTarget target, uint64_t location, uint64_t size) {
    const uint64_t unit = target == PSXRecompV4::ModPatchTarget::DiscRaw ? 2352u : 2048u;
    for (uint64_t lba = location / unit; lba <= (location + std::max<uint64_t>(size, 1) - 1) / unit; lba++) {
        const std::string m = member_of(uint32_t(lba));
        if (!m.empty()) row.members.insert(m);
        else if (lba >= kExeLba && lba < kExeLba + kExeSectors) row.disc_exe++;
        else if (lba == kRootDirLba) row.dir_writes++;
        else if (lba >= kZnullLba && lba < kZnullLba + kZnullSectors) row.growth++;
        else { row.disc_other++; row.other_lo = std::min(row.other_lo, uint32_t(lba)); row.other_hi = std::max(row.other_hi, uint32_t(lba)); }
    }
}

void classify_main(Row &row, uint64_t address, uint64_t size) {
    const uint32_t lo = uint32_t(address) | 0x80000000u, hi = lo + uint32_t(size);
    for (const auto &g : guard_ranges)
        if (lo < g.hi && hi > g.lo) row.guard_hits.insert(lo);
    auto sites = [&](const uint32_t *list, size_t n) {
        for (size_t i = 0; i < n; i++) {
            const uint32_t jal = list[i] - 8u;  /* jal and its delay slot */
            if (lo < jal + 8u && hi > jal) row.site_hits.insert(lo);
        }
    };
    sites(mmx6_seamless_pack_callers, std::size(mmx6_seamless_pack_callers));
    sites(mmx6_seamless_bin_callers, std::size(mmx6_seamless_bin_callers));
    sites(mmx6_seamless_raw_callers, std::size(mmx6_seamless_raw_callers));
}

Row analyse(const std::string &name, const PSXRecompV4::ModResolution &plan) {
    Row row;
    row.name = name;
    if (!plan.ok) {
        for (const auto &e : plan.errors) row.error += (row.error.empty() ? "" : "; ") + e;
        return row;
    }
    using T = PSXRecompV4::ModPatchTarget;
    for (const auto &w : plan.writes) {
        uint64_t size = w.expected.size();
        if (w.target == T::MainExe) { row.main_writes++; classify_main(row, w.location, size); }
        else classify_disc(row, w.target, w.location, size);
    }
    for (const auto &o : plan.overlays) {
        if (o.target == T::MainExe) { row.main_writes++; classify_main(row, o.location, o.payload.size()); }
        else classify_disc(row, o.target, o.location, o.payload.size());
    }
    row.derived = !plan.derived_discs.empty();
    return row;
}
}  // namespace

int main(int argc, char **argv) {
    if (argc != 2) return fail("expected the preloaded mods root");
    const std::filesystem::path root =
        std::filesystem::temp_directory_path() / "mmx6-seamless-matrix-test";
    std::error_code ec;
    std::filesystem::remove_all(root, ec);
    std::filesystem::copy(argv[1], root, std::filesystem::copy_options::recursive, ec);
    if (ec) return fail("could not stage catalog copy: " + ec.message());

    PSXRecompV4::ModPackageManager manager{root};
    std::string error;
    if (!manager.scan(&error) || !manager.load_state(&error)) return fail(error);
    std::set<std::string> plugin_ids;
    for (const auto &[id, versions] : manager.packages())
        for (const auto &[v, package] : versions)
            for (const auto &p : package.plugins) plugin_ids.insert(p.id);
    PSXRecompV4::mod_clear_plugins_for_tests();
    for (const auto &id : plugin_ids)
        if (!PSXRecompV4::mod_register_activation_plugin(id, no_op_plugin))
            return fail("could not register plugin " + id);

    /* Every feature alone, with Seamless Loading in its default-on state. */
    std::vector<std::pair<std::string, std::string>> features;
    for (const auto &[id, versions] : manager.packages()) {
        const auto *package = manager.selected_package(id);
        if (!package || id == "mmx6.enhancement.seamless-loading") continue;
        for (const auto &f : package->features) features.emplace_back(id, f.id);
    }
    std::vector<Row> rows;
    for (const auto &[package, feature] : features) {
        if (!manager.set_feature_enabled(package, feature, true, &error)) return fail(error);
        Row row = analyse(package + "/" + feature, manager.resolve(kGameId, "", kStockDiscSha256));
        /* A feature that requires another package is checked with it enabled. */
        const std::string needs = "requires enabled package ";
        const size_t at = row.error.find(needs);
        std::vector<std::pair<std::string, std::string>> extra;
        if (at != std::string::npos) {
            const std::string dependency = row.error.substr(at + needs.size());
            if (const auto *p = manager.selected_package(dependency))
                for (const auto &f : p->features) extra.emplace_back(dependency, f.id);
            for (const auto &[p, f] : extra) manager.set_feature_enabled(p, f, true, &error);
            row = analyse(package + "/" + feature + " (+" + dependency + ")",
                          manager.resolve(kGameId, "", kStockDiscSha256));
            for (const auto &[p, f] : extra) manager.set_feature_enabled(p, f, false, &error);
        }
        rows.push_back(row);
        if (!manager.set_feature_enabled(package, feature, false, &error)) return fail(error);
    }
    /* Every feature at once, when the catalog allows that combination. */
    for (const auto &[package, feature] : features) manager.set_feature_enabled(package, feature, true, &error);
    Row all = analyse("ALL FEATURES", manager.resolve(kGameId, "", kStockDiscSha256));

    std::map<std::string, unsigned> totals;
    for (const auto &r : rows) {
        totals[r.verdict()]++;
        if (r.verdict() == "unaffected") continue;
        std::printf("%-58s %-16s", r.name.c_str(), r.verdict().c_str());
        if (!r.members.empty()) {
            std::printf(" members=");
            for (const auto &m : r.members) std::printf("%s ", m.c_str());
        }
        if (r.disc_exe) std::printf(" disc-exe-sectors=%u", r.disc_exe);
        if (r.dir_writes) std::printf(" iso-directory");
        if (r.growth) std::printf(" dat-growth-sectors=%u", r.growth);
        if (r.disc_other) std::printf(" other-sectors=%u (lba %u..%u)", r.disc_other, r.other_lo, r.other_hi);
        for (uint32_t a : r.guard_hits) std::printf(" guard@%08X", a);
        for (uint32_t a : r.site_hits) std::printf(" callsite@%08X", a);
        if (!r.error.empty()) std::printf(" error=%s", r.error.c_str());
        std::printf("\n");
    }
    std::printf("%s: %s, %zu members modified, %zu guard hits, %zu call-site hits%s%s\n",
                all.name.c_str(), all.verdict().c_str(), all.members.size(), all.guard_hits.size(),
                all.site_hits.size(), all.error.empty() ? "" : " error=", all.error.c_str());
    for (const auto &[verdict, n] : totals) std::printf("  %-32s %u features\n", verdict.c_str(), n);

    /* Pinned support facts. A catalog change that alters them must update
     * docs/SEAMLESS_LOADING.md and this test together. */
    for (const auto &r : rows) {
        if (!r.error.empty()) return fail(r.name + " does not resolve alone: " + r.error);
        if (r.disc_other) return fail(r.name + " patches unclassified disc sectors");
        if (r.growth && !r.dir_writes)
            return fail(r.name + " writes the DAT growth area without growing ROCK_X6.DAT");
        if (!r.guard_hits.empty() || !r.site_hits.empty())
            return fail(r.name + " changes the seamless loader contract; document its fallback");
    }
    std::printf("PASS: %zu features classified; none alter the loader contract\n", rows.size());
    return 0;
}
