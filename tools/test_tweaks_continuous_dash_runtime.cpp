#include "mod_packages.h"

#include <filesystem>
#include <iostream>
#include <string>

namespace fs = std::filesystem;
using namespace PSXRecompV4;

namespace {
constexpr const char* kPackage = "mmx6.tweaks.continuous-dash";
constexpr const char* kGame = "SLUS-01395";
constexpr const char* kDisc =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";
int failures;

void check(bool condition, const std::string& message) {
    if (condition) return;
    std::cerr << "FAIL: " << message << "\n";
    ++failures;
}
} // namespace

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const fs::path root =
        fs::temp_directory_path() / "mmx6-continuous-dash-runtime-test";
    std::error_code ec;
    fs::remove_all(root, ec);
    ModPackageManager manager(root);
    std::string error;
    std::string id;
    std::string version;
    check(
        manager.install_archive(argv[1], &id, &version, &error),
        "install: " + error);
    check(id == kPackage && version == "1.0.0", "installed identity");
    check(manager.load_state(&error), "load state: " + error);
    check(manager.resolve(kGame, {}, kDisc).writes.empty(),
          "default-disabled no-op");

    check(manager.set_feature_enabled(
              kPackage, "continuous_dash_speed_normal", true, &error),
          "enable normal: " + error);
    check(manager.set_feature_option(
              kPackage, "continuous_dash_speed_normal", "speed",
              "333333", &error),
          "set normal speed: " + error);
    ModResolution normal = manager.resolve(kGame, {}, kDisc);
    if (!normal.ok || normal.writes.size() != 3) {
        std::cerr << "normal writes=" << normal.writes.size() << " errors=";
        for (const std::string& value : normal.errors)
            std::cerr << value << "; ";
        std::cerr << "\n";
    }
    check(normal.ok && normal.writes.size() == 3,
          "normal emits one foundation plus two guarded hot-path sites");
    if (normal.writes.size() == 3) {
        check(normal.writes[0].replacement.size() == 24,
              "foundation is one fixed composed write");
        check(normal.writes[1].fields.size() == 2 &&
                  normal.writes[2].fields.size() == 2,
              "normal sites own only two immediate fields each");
    }

    check(manager.set_feature_enabled(
              kPackage, "continuous_dash_speed_hyper", true, &error),
          "enable Hyper: " + error);
    check(manager.set_feature_option(
              kPackage, "continuous_dash_speed_hyper", "speed",
              "123456", &error),
          "set Hyper speed: " + error);
    ModResolution both = manager.resolve(kGame, {}, kDisc);
    check(both.ok && both.writes.size() == 3,
          "both rows compose without a duplicate foundation");
    check(both.diagnostics.empty(), "all-feature plan has no collisions");
    check(manager.resolve(kGame, {}, kDisc).fingerprint == both.fingerprint,
          "all-feature plan deterministic");
    check(!manager.set_feature_option(
              kPackage, "continuous_dash_speed_normal", "speed",
              "199999", &error),
          "normal source lower bound enforced");
    check(!manager.set_feature_option(
              kPackage, "continuous_dash_speed_hyper", "speed",
              "160001", &error),
          "Hyper source upper bound enforced");

    check(manager.set_feature_enabled(
              kPackage, "continuous_dash_speed_normal", false, &error),
          "disable normal");
    ModResolution hyper = manager.resolve(kGame, {}, kDisc);
    check(hyper.ok && hyper.writes.size() == 1,
          "Hyper-only owns one complete foundation");
    check(manager.set_feature_enabled(
              kPackage, "continuous_dash_speed_hyper", false, &error),
          "disable Hyper");
    check(manager.resolve(kGame, {}, kDisc).writes.empty(),
          "disable all restores no-op");

    fs::remove_all(root, ec);
    if (failures) return 1;
    std::cout << "continuous dash runtime package tests passed\n";
    return 0;
}
