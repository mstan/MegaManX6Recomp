#include "mod_packages.h"

#include <algorithm>
#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using namespace PSXRecompV4;

namespace {
constexpr const char* kPackage = "mmx6.tweaks.player-standalone";
constexpr const char* kGame = "SLUS-01395";
constexpr const char* kDisc =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";
int failures;

void check(bool condition, const std::string& message) {
    if (condition) return;
    std::cerr << "FAIL: " << message << "\n";
    ++failures;
}

size_t count_feature(const ModResolution& plan, const std::string& feature) {
    return static_cast<size_t>(std::count_if(
        plan.writes.begin(), plan.writes.end(),
        [&](const ModResolution::Write& write) {
            return write.package_id == kPackage &&
                   write.feature_id == feature;
        }));
}
} // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: test_tweaks_player_standalone_runtime "
                     "<package.psxmod>\n";
        return 2;
    }
    const fs::path root =
        fs::temp_directory_path() / "mmx6-player-standalone-runtime-test";
    std::error_code ec;
    fs::remove_all(root, ec);

    ModPackageManager manager(root);
    std::string error;
    std::string id;
    std::string version;
    check(
        manager.install_archive(argv[1], &id, &version, &error),
        "install archive: " + error);
    check(id == kPackage && version == "1.0.0", "installed identity");
    check(manager.load_state(&error), "load state: " + error);

    ModResolution disabled = manager.resolve(kGame, {}, kDisc);
    check(disabled.ok && disabled.writes.empty(), "default-disabled no-op");

    const std::vector<std::string> features = {
        "unlock_x_air_dash",
        "guard_shell_bug_fix",
        "zero_weapon_autoselect",
    };
    for (const std::string& feature : features)
        check(
            manager.set_feature_enabled(kPackage, feature, true, &error),
            "enable " + feature + ": " + error);

    ModResolution forward = manager.resolve(kGame, {}, kDisc);
    check(
        forward.ok,
        "resolve all features: " +
            (forward.errors.empty() ? std::string{} : forward.errors.front()));
    check(forward.writes.size() == 18, "all features emit 18 owned writes");
    check(count_feature(forward, "unlock_x_air_dash") == 1,
          "air dash exact closure");
    check(count_feature(forward, "guard_shell_bug_fix") == 2,
          "Guard Shell exact closure");
    check(count_feature(forward, "zero_weapon_autoselect") == 15,
          "Zero autoselect includes two common writes");
    for (const ModResolution::Write& write : forward.writes) {
        check(!write.expected.empty(), "every write has a complete stock guard");
        check(write.expected.size() == write.replacement.size(),
              "fixed replacement owns exactly its guard");
    }
    check(manager.resolve(kGame, {}, kDisc).fingerprint == forward.fingerprint,
          "resolution fingerprint deterministic");

    for (auto it = features.rbegin(); it != features.rend(); ++it)
        check(manager.set_feature_enabled(kPackage, *it, false, &error),
              "disable " + *it + ": " + error);
    ModResolution reverse_disabled = manager.resolve(kGame, {}, kDisc);
    check(reverse_disabled.ok && reverse_disabled.writes.empty(),
          "reverse disable restores no-op");

    fs::remove_all(root, ec);
    if (failures) return 1;
    std::cout << "standalone player runtime package tests passed\n";
    return 0;
}
