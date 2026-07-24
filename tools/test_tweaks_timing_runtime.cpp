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

constexpr const char* kPackage = "mmx6.tweaks.timing";
constexpr const char* kGame = "SLUS-01395";
constexpr const char* kDisc =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";

int failures;

void check(bool condition, const std::string& message) {
    if (condition) return;
    std::cerr << "FAIL: " << message << "\n";
    ++failures;
}

size_t feature_writes(const ModResolution& plan, const std::string& feature) {
    return static_cast<size_t>(std::count_if(
        plan.writes.begin(), plan.writes.end(),
        [&](const ModResolution::Write& write) {
            return write.package_id == kPackage &&
                   write.feature_id == feature;
        }));
}

bool set_value(ModPackageManager& manager, const std::string& feature,
               const std::string& option, const std::string& value,
               std::string& error) {
    return manager.set_feature_option(
        kPackage, feature, option, value, &error);
}

} // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: test_tweaks_timing_runtime <package.psxmod>\n";
        return 2;
    }

    const fs::path root =
        fs::temp_directory_path() / "mmx6-timing-package-runtime-test";
    std::error_code ec;
    fs::remove_all(root, ec);
    ModPackageManager manager(root);
    std::string error;
    std::string installed_id;
    std::string installed_version;
    check(
        manager.install_archive(
            argv[1], &installed_id, &installed_version, &error),
        "package install: " + error);
    check(installed_id == kPackage && installed_version == "1.0.0",
          "installed package identity");
    check(manager.load_state(&error), "load state: " + error);

    ModResolution disabled = manager.resolve(kGame, {}, kDisc);
    check(disabled.ok && disabled.writes.empty(),
          "all features default disabled");

    const std::vector<std::string> features = {
        "x_saber_timing",
        "shadow_saber_timing",
        "zero_saber_cooldown_timing",
        "maximum_lives",
        "nightmare_dark_opacity",
    };
    for (const std::string& feature : features)
        check(manager.set_feature_enabled(kPackage, feature, true, &error),
              "enable " + feature + ": " + error);
    ModResolution stock_defaults = manager.resolve(kGame, {}, kDisc);
    check(stock_defaults.ok && stock_defaults.writes.empty(),
          "enabled stock defaults elide every sparse field");

    check(!set_value(
              manager, "x_saber_timing", "timing_1", "0", error),
          "animation zero must be outside the admitted domain");
    check(!set_value(
              manager, "maximum_lives", "maximum", "100", error),
          "maximum lives above 99 must be rejected");
    check(!set_value(
              manager, "nightmare_dark_opacity", "opacity", "0", error),
          "opacity below 1 must be rejected");

    for (const auto& [feature, count] :
         std::map<std::string, int>{
             {"x_saber_timing", 7},
             {"shadow_saber_timing", 7},
         })
        for (int index = 1; index <= count; ++index)
            check(
                set_value(
                    manager, feature, "timing_" + std::to_string(index),
                    "50", error),
                "set " + feature + " timing");
    for (int index = 2; index <= 7; ++index)
        check(
            set_value(
                manager, "zero_saber_cooldown_timing",
                "timing_" + std::to_string(index), "50", error),
            "set Zero cooldown timing");
    check(set_value(
              manager, "maximum_lives", "maximum", "10", error),
          "set Maximum Lives");
    check(set_value(
              manager, "nightmare_dark_opacity", "opacity", "28", error),
          "set Nightmare Dark opacity");

    ModResolution all = manager.resolve(kGame, {}, kDisc);
    check(all.ok, "all admitted controls resolve: " +
                      (all.errors.empty() ? std::string{} : all.errors[0]));
    check(all.writes.size() == 48, "complete selected plan has 48 writes");
    check(feature_writes(all, "x_saber_timing") == 10,
          "X Saber has ten semantic occurrences");
    check(feature_writes(all, "shadow_saber_timing") == 10,
          "Shadow Saber has ten semantic occurrences");
    check(feature_writes(all, "zero_saber_cooldown_timing") == 18,
          "Zero cooldown has eighteen semantic occurrences");
    check(feature_writes(all, "maximum_lives") == 5,
          "Maximum Lives includes four values and the >9 helper");
    check(feature_writes(all, "nightmare_dark_opacity") == 5,
          "Nightmare opacity includes the sector-split record");

    size_t owned_fields = 0;
    bool saw_animation = false;
    bool saw_cap = false;
    bool saw_cap_plus_one = false;
    bool saw_display_helper = false;
    bool saw_opacity = false;
    bool saw_opacity_minus_one = false;
    for (const ModResolution::Write& write : all.writes) {
        check(write.replacement.empty() && !write.fields.empty(),
              "format-4 write retains only sparse resolved fields");
        owned_fields += write.fields.size();
        for (const ModResolution::Write::Field& field : write.fields) {
            if (write.feature_id.find("saber") != std::string::npos &&
                field.replacement == std::vector<uint8_t>{50})
                saw_animation = true;
            if (write.feature_id == "maximum_lives") {
                saw_cap = saw_cap ||
                          field.replacement ==
                              std::vector<uint8_t>({10, 0});
                saw_cap_plus_one =
                    saw_cap_plus_one ||
                    field.replacement == std::vector<uint8_t>({11, 0});
                saw_display_helper =
                    saw_display_helper ||
                    field.replacement == std::vector<uint8_t>(4, 0);
            }
            if (write.feature_id == "nightmare_dark_opacity") {
                saw_opacity = saw_opacity ||
                              field.replacement ==
                                  std::vector<uint8_t>{28};
                saw_opacity_minus_one =
                    saw_opacity_minus_one ||
                    field.replacement == std::vector<uint8_t>{27};
            }
        }
    }
    check(owned_fields == 51, "48 writes resolve to 51 disjoint fields");
    check(saw_animation && saw_cap && saw_cap_plus_one &&
              saw_display_helper && saw_opacity && saw_opacity_minus_one,
          "resolved bytes reproduce direct, additive, and conditional values");
    check(manager.resolve(kGame, {}, kDisc).fingerprint == all.fingerprint,
          "selected plan fingerprint is deterministic");

    for (const std::string& feature : features)
        if (feature != "maximum_lives")
            check(manager.set_feature_enabled(kPackage, feature, false, &error),
                  "disable " + feature);
    check(set_value(
              manager, "maximum_lives", "maximum", "9", error),
          "restore stock maximum");
    ModResolution stock_lives = manager.resolve(kGame, {}, kDisc);
    check(stock_lives.ok && stock_lives.writes.empty(),
          "Maximum Lives 9 is a complete stock no-op");
    check(set_value(
              manager, "maximum_lives", "maximum", "10", error),
          "restore non-stock maximum");
    ModResolution double_digit_lives = manager.resolve(kGame, {}, kDisc);
    check(double_digit_lives.ok &&
              feature_writes(double_digit_lives, "maximum_lives") == 5,
          "Maximum Lives 10 activates the display helper boundary");

    fs::remove_all(root, ec);
    if (failures) {
        std::cerr << failures << " timing runtime test(s) failed\n";
        return 1;
    }
    std::cout << "timing runtime package tests passed\n";
    return 0;
}
