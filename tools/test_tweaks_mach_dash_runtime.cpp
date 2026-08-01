#include "mod_packages.h"

#include <filesystem>
#include <iostream>
#include <string>

namespace fs = std::filesystem;
using namespace PSXRecompV4;

namespace {
constexpr const char* kPackage = "mmx6.tweaks.mach-dash";
constexpr const char* kFeature = "blade_mach_dash_behavior";
constexpr const char* kGame = "SLUS-01395";
constexpr const char* kDisc =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";
int failures;

void check(bool condition, const std::string& message) {
    if (condition) return;
    std::cerr << "FAIL: " << message << "\n";
    ++failures;
}

bool set(
    ModPackageManager& manager, const std::string& option,
    const std::string& value, std::string& error
) {
    return manager.set_feature_option(
        kPackage, kFeature, option, value, &error);
}

bool same_writes(const ModResolution& left, const ModResolution& right) {
    if (left.writes.size() != right.writes.size()) return false;
    for (size_t index = 0; index < left.writes.size(); ++index) {
        const auto& a = left.writes[index];
        const auto& b = right.writes[index];
        if (a.target != b.target || a.location != b.location ||
            a.expected != b.expected || a.replacement != b.replacement ||
            a.fields.size() != b.fields.size())
            return false;
    }
    return true;
}

int resolved_byte(
    const ModResolution& plan, ModPatchTarget target, uint64_t location
) {
    for (const auto& write : plan.writes) {
        if (write.target != target || location < write.location ||
            location >= write.location + write.replacement.size())
            continue;
        return write.replacement[
            static_cast<size_t>(location - write.location)];
    }
    return -1;
}
} // namespace

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    const fs::path root =
        fs::temp_directory_path() / "mmx6-mach-dash-runtime-test";
    std::error_code ec;
    fs::remove_all(root, ec);
    ModPackageManager manager(root);
    std::string error;
    std::string id;
    std::string version;
    check(manager.install_archive(argv[1], &id, &version, &error),
          "install: " + error);
    check(id == kPackage && version == "1.0.0", "installed identity");
    check(manager.load_state(&error), "load state: " + error);
    check(manager.resolve(kGame, {}, kDisc).writes.empty(),
          "default-disabled no-op");
    check(manager.set_feature_enabled(kPackage, kFeature, true, &error),
          "enable behavior: " + error);
    ModResolution defaults = manager.resolve(kGame, {}, kDisc);
    check(defaults.ok && defaults.writes.empty(),
          "enabled stock options are a complete no-op");

    check(set(manager, "input", "hybrid", error), "set hybrid");
    check(set(manager, "wait", "minimum", error), "set minimum");
    check(set(manager, "cancel", "hold_release", error), "set hold");
    check(set(manager, "duration", "20", error), "set duration");
    check(set(manager, "speed", "600000", error), "set speed");
    check(set(manager, "immunity", "12", error), "set immunity");
    ModResolution all = manager.resolve(kGame, {}, kDisc);
    if (!all.ok) {
        for (const std::string& value : all.errors)
            std::cerr << value << "\n";
    }
    check(all.ok && !all.writes.empty(),
          "full state machine resolves");
    check(all.diagnostics.empty(), "composed plan has no collisions");
    for (const ModResolution::Write& write : all.writes) {
        check(!write.expected.empty(), "complete stock guard");
        check(write.expected.size() == write.replacement.size(),
              "complete owned replacement");
        check(write.package_id == kPackage &&
                  write.feature_id == kFeature,
              "single coherent package/feature owner");
    }
    check(manager.resolve(kGame, {}, kDisc).fingerprint == all.fingerprint,
          "repeated full resolution deterministic");
    check(resolved_byte(all, ModPatchTarget::MainExe, 0x8003F37C) == 20,
          "duration byte matches upstream");
    check(resolved_byte(all, ModPatchTarget::DiscUser, 0x19C7A6E0) == 0x09 &&
              resolved_byte(all, ModPatchTarget::DiscUser, 0x19C7A6E1) == 0x00 &&
              resolved_byte(all, ModPatchTarget::DiscUser, 0x19C7A6E4) == 0xC0 &&
              resolved_byte(all, ModPatchTarget::DiscUser, 0x19C7A6E5) == 0x27,
          "speed immediates match upstream NumWord encoding");
    check(resolved_byte(all, ModPatchTarget::MainExe, 0x8007A8EC) == 12,
          "immunity byte composes into cancellation foundation");
    check(resolved_byte(all, ModPatchTarget::DiscUser, 0x19C7A728) == 0xD4,
          "minimum wait hook survives full composition");

    // Upstream GuiControl makes Hybrid + No Stop resolve to Normal and restores
    // duration/speed defaults. Prove the resolver does not depend on set order.
    check(set(manager, "wait", "no_stop", error), "set no stop");
    ModResolution normalized_hybrid = manager.resolve(kGame, {}, kDisc);
    check(set(manager, "input", "normal", error), "set normal");
    check(set(manager, "duration", "15", error), "restore duration");
    check(set(manager, "speed", "540672", error), "restore speed");
    ModResolution explicit_normal = manager.resolve(kGame, {}, kDisc);
    check(normalized_hybrid.ok && explicit_normal.ok &&
              same_writes(normalized_hybrid, explicit_normal),
          "Hybrid + No Stop normalization is order independent");

    check(!set(manager, "duration", "9", error),
          "duration lower bound enforced");
    check(!set(manager, "speed", "600001", error),
          "speed upper bound enforced");
    check(!set(manager, "immunity", "3", error),
          "immunity lower bound enforced");
    check(manager.set_feature_enabled(kPackage, kFeature, false, &error),
          "disable behavior");
    check(manager.resolve(kGame, {}, kDisc).writes.empty(),
          "disable restores no-op");

    fs::remove_all(root, ec);
    if (failures) return 1;
    std::cout << "Mach Dash runtime package tests passed\n";
    return 0;
}
