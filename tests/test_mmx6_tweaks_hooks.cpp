#include "mmx6_tweaks_hooks_resolver.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

using namespace PSXRecompV4;

namespace {

namespace fs = std::filesystem;

int failures;

void check(bool value, const char* message) {
    if (!value) {
        std::cerr << "FAIL: " << message << "\n";
        ++failures;
    }
}

ModPackage valid_package(bool reverse_features = false) {
    ModPackage package;
    package.format_version = 4;
    package.id = MMX6Mods::kTweaksHooksPackageId;
    package.version = MMX6Mods::kTweaksHooksPackageVersion;
    package.name = "Mega Man X6 Voice Hooks";
    package.resolver = "builtin:mmx6.tweaks.hooks";
    package.save_compatibility = "shared";
    ModTarget target;
    target.game_id = "SLUS-01395";
    target.disc_sha256 =
        "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";
    package.targets.push_back(target);
    const std::array<const char*, 4> ids = {
        "voice_boss_intros",
        "voice_boss_warning",
        "voice_low_health",
        "voice_title",
    };
    for (const char* id : ids) {
        ModFeature feature;
        feature.id = id;
        feature.name = id;
        feature.default_enabled = false;
        package.features.push_back(feature);
    }
    if (reverse_features)
        std::reverse(package.features.begin(), package.features.end());
    struct Asset {
        uint64_t location;
        uint64_t size;
        const char* backing;
        const char* voice;
        const char* retranslation;
    };
    const Asset assets[] = {
        {0x1DC01000, 0xCD800,
         "faa6bea73bd03cdcf2d58dcf7e02488b7c1146ebb1031083aa8106cc82533717",
         "4a29d770fd4d335b6faa1e161395d4fa55fc08904e26e82294148ff35dc91400",
         "c81aa441f53fd1b8cc9f4edca76e82d9210a5ea10bca71c0847210cb3d460bc8"},
        {0x1DCCE800, 0xDF000,
         "a6e10f1f48c9b0bb4eb3374fb6a7c8ff74cc07d21155ed1a7a32611dde0f57ea",
         "929b02d80e2342830b202eea10cc9a9ad39cb45fbb47e976cdf799c74a9d883a",
         "6b3f4ba36faf8a833ced63fc055300bca9d90b14cb2e0ba129f9af08b7c93325"},
        {0x1DDAD800, 0xE6000,
         "10d8ce3cfcdff65c514699ea99b8c3a2543fef67f7485b25c58f426229b9c589",
         "3d64c9f78bfa79a3d19570909c831d37a3e380301233d9cbcceb888d1a2ccb19",
         "2a0094bac3a650e04cef98c514ab7f35c469a5eb04c01fb40391695728f24666"},
        {0x1DE93800, 0xC7800,
         "207fdcc5799cf911bd20210f9e6273e369cbc9570669fd7d5b0929b2bdfb372e",
         "c7021afb77529023d93d000f1baf2700f17313478c6e4fdff3a83b242cbb3e57",
         "c21fd0d59971f34cef78ad3304ff8fc23a97901d3d1d84e73cd241870a6fc970"},
        {0x1DF5B000, 0xE3800,
         "32bac2734c9376ba35b3663544947fb98fad53931d0721e24bbb0aefabfabd43",
         "a7a4476b6449a013683e86facca7139ae4dc871013ec141fdda33ab9bfa3399b",
         "20f3c92498858b315643b737d410f241ca1c9ff4d5df4a334ccf2ac4b73dddf8"},
    };
    for (const Asset& asset : assets) {
        for (bool retranslation : {false, true}) {
            ModOverlay overlay;
            overlay.feature_id = "voice_boss_warning";
            overlay.target = ModPatchTarget::DiscUser;
            overlay.location = asset.location;
            overlay.size = asset.size;
            overlay.sha256 = retranslation
                ? asset.retranslation : asset.voice;
            overlay.expected_sha256 = asset.backing;
            overlay.when_feature.present = true;
            overlay.when_feature.package_id = "mmx6.tweaks.native";
            overlay.when_feature.feature_id = "retranslation";
            overlay.when_feature.enabled = retranslation;
            package.overlays.push_back(std::move(overlay));
        }
    }
    return package;
}

ModSelection selection(std::initializer_list<const char*> ids) {
    ModSelection selected;
    selected.version = MMX6Mods::kTweaksHooksPackageVersion;
    for (const char* id : ids) {
        ModFeatureSelection feature;
        feature.enabled = true;
        feature.has_enabled = true;
        selected.features[id] = feature;
    }
    return selected;
}

bool resolve(const ModPackage& package, const ModSelection& selected,
             std::vector<ModResolution::Write>& writes,
             std::vector<std::string>& errors) {
    ModBuiltinResolverContext context;
    return MMX6Mods::resolve_tweaks_hooks(
        package, selected, context, writes, errors);
}

const ModResolution::Write* find_write(
    const std::vector<ModResolution::Write>& writes,
    ModPatchTarget target, uint64_t location) {
    const auto found = std::find_if(
        writes.begin(), writes.end(), [&](const ModResolution::Write& write) {
            return write.target == target && write.location == location;
        });
    return found == writes.end() ? nullptr : &*found;
}

bool all_zero(const std::vector<uint8_t>& bytes, size_t begin, size_t size) {
    return begin + size <= bytes.size() &&
        std::all_of(
            bytes.begin() + begin, bytes.begin() + begin + size,
            [](uint8_t value) { return value == 0; });
}

void test_disabled_is_empty() {
    std::vector<ModResolution::Write> writes;
    std::vector<std::string> errors;
    check(resolve(valid_package(), {}, writes, errors),
          "disabled package must resolve");
    check(errors.empty(), "disabled package must have no errors");
    check(writes.empty(), "disabled features must emit zero operations");
}

void test_independent_composition() {
    std::vector<ModResolution::Write> writes;
    std::vector<std::string> errors;
    check(resolve(
              valid_package(),
              selection({"voice_title", "voice_boss_warning"}),
              writes, errors),
          "disjoint voice features must resolve together");
    check(errors.empty(), "disjoint voice features must have no errors");
    check(writes.size() == 10,
          "title and warning must emit hooks plus six DAT redirects");

    const ModResolution::Write* code =
        find_write(writes, ModPatchTarget::MainExe, 0x80076440ull);
    check(code != nullptr, "voice foundation must own the named code region");
    if (code) {
        check(code->expected.size() == 0x74 &&
                  all_zero(code->expected, 0, code->expected.size()),
              "voice foundation must guard the full zero stock range");
        check(code->replacement.size() == 0x74,
              "voice foundation replacement must claim the full range");
        check(all_zero(code->replacement, 0x00, 0x3C),
              "disabled low-health and boss-intro slices must stay stock");
        check(!all_zero(code->replacement, 0x3C, 0x18),
              "enabled title slice must be populated");
        check(!all_zero(code->replacement, 0x54, 0x20),
              "enabled warning slice must be populated");
    }
    check(find_write(
              writes, ModPatchTarget::MainExe, 0x8001DEC4ull) != nullptr,
          "title hook must include its first full callsite");
    check(find_write(
              writes, ModPatchTarget::MainExe, 0x8001DF54ull) != nullptr,
          "title hook must include its second full callsite");
    check(find_write(
              writes, ModPatchTarget::MainExe, 0x80053874ull) != nullptr,
          "warning hook must include its full callsite");
    check(find_write(
              writes, ModPatchTarget::DiscUser, 0x19E0F2A8ull) != nullptr &&
              find_write(writes, ModPatchTarget::DiscUser, 0xB0A6ull) != nullptr,
          "warning must redirect its sound records and expose the DAT tail");
    check(find_write(
              writes, ModPatchTarget::DiscUser, 0x19D3FE18ull) == nullptr,
          "disabled boss-intro member must emit no operation");
}

void test_all_stock_guards_and_order() {
    std::vector<ModResolution::Write> writes;
    std::vector<std::string> errors;
    const ModSelection all = selection({
        "voice_title",
        "voice_boss_intros",
        "voice_low_health",
        "voice_boss_warning",
    });
    check(resolve(valid_package(), all, writes, errors),
          "all voices must compose");
    check(writes.size() == 12,
          "all voices must emit one foundation, five sites, and six redirects");
    const ModResolution::Write* intro =
        find_write(writes, ModPatchTarget::DiscUser, 0x19D3FE18ull);
    check(intro && intro->expected.size() == 12 &&
              intro->replacement.size() == 12,
          "boss-intro member write must carry its full 12-byte guard");
    const ModResolution::Write* low =
        find_write(writes, ModPatchTarget::MainExe, 0x8003D050ull);
    check(low && low->expected.size() == 44 &&
              low->replacement.size() == 44,
          "low-health hook must carry its full 44-byte guard");
    const ModResolution::Write* code =
        find_write(writes, ModPatchTarget::MainExe, 0x80076440ull);
    check(code && !all_zero(code->replacement, 0, 0x74),
          "all enabled slices must compose into one allocation");

    std::vector<ModResolution::Write> reversed;
    std::vector<std::string> reversed_errors;
    check(resolve(valid_package(true), all, reversed, reversed_errors),
          "feature declaration order must not affect resolution");
    check(writes.size() == reversed.size(),
          "deterministic plans must have the same operation count");
    bool identical = writes.size() == reversed.size();
    for (size_t i = 0; identical && i < writes.size(); ++i) {
        identical =
            writes[i].target == reversed[i].target &&
            writes[i].location == reversed[i].location &&
            writes[i].expected == reversed[i].expected &&
            writes[i].replacement == reversed[i].replacement &&
            writes[i].feature_id == reversed[i].feature_id;
    }
    check(identical,
          "feature declaration order must produce byte-identical plans");
}

void test_invalid_manifest_and_selection() {
    {
        ModPackage package = valid_package();
        package.id = "wrong.package";
        std::vector<ModResolution::Write> writes;
        std::vector<std::string> errors;
        check(!resolve(package, {}, writes, errors),
              "wrong package id must fail closed");
        check(writes.empty(), "failed package must roll back all operations");
    }
    {
        ModPackage package = valid_package();
        package.version = "1.0.1";
        std::vector<ModResolution::Write> writes;
        std::vector<std::string> errors;
        check(!resolve(package, {}, writes, errors),
              "unknown package version must fail closed");
    }
    {
        ModPackage package = valid_package();
        package.targets[0].disc_sha256.clear();
        std::vector<ModResolution::Write> writes;
        std::vector<std::string> errors;
        check(!resolve(package, {}, writes, errors),
              "unbound stock target must fail closed");
    }
    {
        ModPackage package = valid_package();
        ModFeature extra;
        extra.id = "untrusted";
        package.features.push_back(extra);
        std::vector<ModResolution::Write> writes;
        std::vector<std::string> errors;
        check(!resolve(package, {}, writes, errors),
              "unexpected manifest feature must fail closed");
    }
    {
        ModPackage package = valid_package();
        ModOption untrusted;
        untrusted.feature_id = "voice_title";
        untrusted.id = "payload";
        package.options.push_back(untrusted);
        std::vector<ModResolution::Write> writes;
        std::vector<std::string> errors;
        check(!resolve(package, {}, writes, errors),
              "resolver package option payload must fail closed");
    }
    {
        ModSelection selected = selection({"voice_title"});
        selected.features["voice_title"].values["payload"] = "untrusted";
        std::vector<ModResolution::Write> writes;
        std::vector<std::string> errors;
        check(!resolve(valid_package(), selected, writes, errors),
              "unexpected feature config must fail closed");
        check(writes.empty(), "invalid config must roll back the plan");
    }
    {
        ModSelection selected = selection({"voice_title"});
        ModFeatureSelection unknown;
        unknown.enabled = true;
        unknown.has_enabled = true;
        selected.features["unknown"] = unknown;
        std::vector<ModResolution::Write> writes;
        std::vector<std::string> errors;
        check(!resolve(valid_package(), selected, writes, errors),
              "unknown selected feature must fail closed");
    }
}

void test_manager_integration() {
    const fs::path root =
        fs::temp_directory_path() / "mmx6-tweaks-hooks-resolver-test";
    std::error_code ec;
    fs::remove_all(root, ec);
    const fs::path source = fs::path(__FILE__).parent_path().parent_path() /
        "mods" / "preloaded" / "packages" / "mmx6.tweaks.hooks" / "1.1.0";
    const fs::path destination = root / "packages" /
        "mmx6.tweaks.hooks" / "1.1.0";
    fs::create_directories(destination.parent_path(), ec);
    fs::copy(source, destination, fs::copy_options::recursive, ec);
    check(!ec, "preloaded trusted hook package must copy into test root");
    const fs::path native_source =
        fs::path(__FILE__).parent_path().parent_path() / "mods" /
        "preloaded" / "packages" / "mmx6.tweaks.native" / "1.10.5";
    const fs::path native_destination = root / "packages" /
        "mmx6.tweaks.native" / "1.10.5";
    fs::create_directories(native_destination.parent_path(), ec);
    fs::copy(
        native_source, native_destination, fs::copy_options::recursive, ec);
    check(!ec, "native retranslation package must copy into test root");

    ModPackageManager manager(root);
    std::string error;
    check(manager.scan(&error), "generated manifest shape must scan");
    check(manager.set_feature_enabled(
              "mmx6.tweaks.hooks", "voice_boss_intros", true, &error),
          "manager must enable one flat hook feature");
    check(manager.set_feature_enabled(
              "mmx6.tweaks.hooks", "voice_title", true, &error),
          "manager must independently enable a second hook feature");
    check(manager.set_feature_enabled(
              "mmx6.tweaks.hooks", "voice_boss_warning", true, &error),
          "manager must enable warning assets");
    const ModResolution resolved = manager.resolve(
        "SLUS-01395", "",
        "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318");
    check(resolved.ok,
          "package manager must invoke the registered trusted resolver");
    check(resolved.writes.size() == 11 && resolved.overlays.size() == 5,
          "manager plan must contain hooks, redirects, and five warning banks");
    check(find_write(
              resolved.writes, ModPatchTarget::DiscUser,
              0x19D3FE18ull) != nullptr,
          "manager plan must retain boss-intro member lifecycle write");
    check(!resolved.overlays.empty() &&
              resolved.overlays[0].payload_sha256 ==
                  "4a29d770fd4d335b6faa1e161395d4fa55fc08904e26e82294148ff35dc91400",
          "disabled retranslation must select stock-script warning banks");
    check(manager.set_feature_enabled(
              "mmx6.tweaks.native", "retranslation", true, &error),
          "manager must enable the external retranslation feature");
    const ModResolution translated = manager.resolve(
        "SLUS-01395", "",
        "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318");
    const bool found_composed = std::any_of(
        translated.overlays.begin(), translated.overlays.end(),
        [](const ModResolution::Overlay& overlay) {
            return overlay.payload_sha256 ==
                "c81aa441f53fd1b8cc9f4edca76e82d9210a5ea10bca71c0847210cb3d460bc8";
        });
    check(translated.ok && found_composed,
          "enabled retranslation must select composed warning banks");
    fs::remove_all(root, ec);
}

void test_local_archive_when_supplied() {
    const char* archive = std::getenv("MMX6_HOOKS_TEST_ARCHIVE");
    if (!archive || !archive[0]) return;
    const fs::path root =
        fs::temp_directory_path() / "mmx6-tweaks-hooks-archive-test";
    std::error_code ec;
    fs::remove_all(root, ec);
    ModPackageManager manager(root);
    std::string installed_id;
    std::string installed_version;
    std::string error;
    check(manager.install_archive(
              archive, &installed_id, &installed_version, &error),
          "locally generated hook archive must install");
    check(installed_id == "mmx6.tweaks.hooks" &&
              installed_version == "1.1.0",
          "local archive must retain its trusted identity");
    check(manager.set_feature_enabled(
              installed_id, "voice_title", true, &error),
          "installed local archive must expose flat features");
    const ModResolution resolved = manager.resolve(
        "SLUS-01395", "",
        "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318");
    check(resolved.ok && resolved.writes.size() == 3,
          "installed local archive must resolve through game-owned hooks");
    fs::remove_all(root, ec);
}

} // namespace

int main() {
    test_disabled_is_empty();
    test_independent_composition();
    test_all_stock_guards_and_order();
    test_invalid_manifest_and_selection();
    test_manager_integration();
    test_local_archive_when_supplied();
    if (failures)
        std::cerr << failures << " MMX6 hook resolver test(s) failed\n";
    return failures ? 1 : 0;
}
