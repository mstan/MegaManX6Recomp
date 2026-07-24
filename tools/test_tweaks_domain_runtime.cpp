#include "mod_packages.h"

#include <algorithm>
#include <filesystem>
#include <iostream>
#include <map>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using namespace PSXRecompV4;

namespace {

constexpr const char* kGame = "SLUS-01395";
constexpr const char* kDisc =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";

int failures;

void check(bool condition, const std::string& message) {
    if (condition) return;
    std::cerr << "FAIL: " << message << "\n";
    ++failures;
}

size_t package_writes(const ModResolution& plan, const std::string& id) {
    return static_cast<size_t>(std::count_if(
        plan.writes.begin(), plan.writes.end(),
        [&](const ModResolution::Write& write) {
            return write.package_id == id;
        }));
}

bool install(ModPackageManager& manager, const fs::path& archive,
             const std::string& expected_id, std::string& error) {
    std::string id;
    std::string version;
    if (!manager.install_archive(
            archive, &id, &version, &error))
        return false;
    return id == expected_id && version == "1.0.0";
}

} // namespace

int main(int argc, char** argv) {
    if (argc != 5 && argc != 7) {
        std::cerr <<
            "usage: test_tweaks_domain_runtime "
            "<general> <stages> <boss> <damage> [native assets]\n";
        return 2;
    }

    const fs::path root =
        fs::temp_directory_path() / "mmx6-domain-package-runtime-test";
    std::error_code ec;
    fs::remove_all(root, ec);
    ModPackageManager manager(root);
    std::string error;

    const std::vector<std::pair<std::string, fs::path>> packages = {
        {"mmx6.tweaks.general", argv[1]},
        {"mmx6.tweaks.stage-modes", argv[2]},
        {"mmx6.tweaks.boss-attacks", argv[3]},
        {"mmx6.tweaks.damage-rules", argv[4]},
    };
    for (const auto& [id, archive] : packages)
        check(install(manager, archive, id, error),
              "install " + id + ": " + error);

    check(manager.load_state(&error), "load state: " + error);
    ModResolution disabled = manager.resolve(kGame, {}, kDisc);
    check(disabled.ok && disabled.writes.empty(),
          "all domain features default disabled");

    const std::vector<std::string> general_features = {
        "continue_from_stage_start",
        "skip_navigator_dialogues",
        "skip_stage_dialogues",
        "skip_nightmare_souls_explanation",
        "skip_stage_select_briefings",
        "share_life_energy_upgrades",
        "share_souls_rank",
        "code_one_unlocks_secret_armors",
        "code_two_starts_with_zero",
        "combine_secret_codes",
        "black_zero_unlock_effect",
        "continuous_cutscene_voice",
        "remember_character_armor",
    };
    for (const std::string& feature : general_features)
        check(manager.set_feature_enabled(
                  "mmx6.tweaks.general", feature, true, &error),
              "enable general/" + feature + ": " + error);
    check(manager.set_feature_enabled(
              "mmx6.tweaks.stage-modes",
              "falling_ceiling_behavior", true, &error),
          "enable falling ceiling behavior: " + error);
    check(manager.set_feature_option(
              "mmx6.tweaks.stage-modes",
              "falling_ceiling_behavior", "mode", "manual", &error),
          "select manual ceiling behavior: " + error);
    check(manager.set_feature_enabled(
              "mmx6.tweaks.boss-attacks",
              "yammark_reduce_idle_time", true, &error),
          "enable Yammark idle reduction: " + error);
    check(manager.set_feature_enabled(
              "mmx6.tweaks.damage-rules",
              "gate_vulnerable_to_normal_attacks", true, &error),
          "enable Gate vulnerability: " + error);

    ModResolution combined = manager.resolve(kGame, {}, kDisc);
    check(combined.ok, "all new domain packages compose: " +
          (combined.errors.empty() ? std::string() : combined.errors.front()));
    for (const auto& [id, _archive] : packages)
        check(package_writes(combined, id) > 0,
              id + " contributes owned writes");
    check(combined.diagnostics.empty(),
          "new domain packages have no collision diagnostics");

    check(!manager.set_feature_option(
              "mmx6.tweaks.stage-modes",
              "falling_ceiling_behavior", "mode", "unchanged", &error),
          "right pane must not expose redundant unchanged mode");

    if (argc == 7) {
        std::string id;
        std::string version;
        check(manager.install_archive(
                  argv[5], &id, &version, &error) &&
                  id == "mmx6.tweaks.native",
              "install native package: " + error);
        check(manager.install_archive(
                  argv[6], &id, &version, &error) &&
                  id == "mmx6.tweaks.assets",
              "install assets package: " + error);
        check(manager.scan(&error),
              "rescan installed ecosystem packages: " + error);
        check(manager.set_feature_enabled(
                  "mmx6.tweaks.native", "retranslation", true, &error),
              "enable native retranslation: " + error);
        check(manager.set_feature_enabled(
                  "mmx6.tweaks.assets", "mugshot_alia", true, &error),
              "enable typed Alia asset: " + error);
        ModResolution ecosystem = manager.resolve(kGame, {}, kDisc);
        check(ecosystem.ok,
              "general + stage + boss + damage + retranslation + assets "
              "must compose: " +
              (ecosystem.errors.empty()
                   ? std::string()
                   : ecosystem.errors.front()));
        check(package_writes(ecosystem, "mmx6.tweaks.native") > 0 ||
                  !ecosystem.overlays.empty(),
              "native retranslation contributes operations");
        check(std::any_of(
                  ecosystem.overlays.begin(), ecosystem.overlays.end(),
                  [](const ModResolution::Overlay& overlay) {
                      return overlay.package_id == "mmx6.tweaks.assets";
                  }),
              "typed asset package contributes an overlay");
    }

    fs::remove_all(root, ec);
    if (failures)
        std::cerr << failures << " domain runtime test(s) failed\n";
    return failures ? 1 : 0;
}
