#include "mod_packages.h"

#include <algorithm>
#include <charconv>
#include <cstdint>
#include <set>
#include <string>
#include <string_view>
#include <vector>

namespace {
using PSXRecompV4::ModFeature;
using PSXRecompV4::ModFeatureSelection;
using PSXRecompV4::ModPackage;
using PSXRecompV4::ModPatchTarget;
using PSXRecompV4::ModResolution;
using PSXRecompV4::ModSelection;
using PSXRecompV4::mod_register_builtin_resolver;

constexpr std::string_view kPackageId = "mmx6.tweaks.ingame-options";
constexpr std::string_view kPackageVersion = "1.0.0";
constexpr std::string_view kResolverId = "mmx6-ingame-options";
constexpr std::string_view kGameId = "SLUS-01395";
constexpr std::string_view kStockDisc =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";
constexpr std::string_view kNativePackageId = "mmx6.tweaks.native";
constexpr std::string_view kFeatureId = "settings_menu_options";

struct Site {
    ModPatchTarget target;
    uint64_t location;
    const char* expected;
    const char* replacement;
    bool fire_overlap_a;
    bool fire_overlap_b;
};

constexpr Site kSites[] = {
    {ModPatchTarget::MainExe, 0x8006D5F7ull, "18", "78", false, false},
    {ModPatchTarget::MainExe, 0x8002A608ull, "0780023C30365024", "0880023C42AB5024", false, false},
    {ModPatchTarget::MainExe, 0x8002A690ull, "0A001124", "0C001134", false, false},
    {ModPatchTarget::MainExe, 0x8002A7C8ull, "0B000224", "0D000234", false, false},
    {ModPatchTarget::MainExe, 0x8002A844ull, "0B000224", "0D000234", false, false},
    {ModPatchTarget::MainExe, 0x8002A878ull, "0B000224", "0D000234", false, false},
    {ModPatchTarget::MainExe, 0x8002A9FCull, "0B00622C", "0D00622C", false, false},
    {ModPatchTarget::MainExe, 0x8002AA2Cull, "0780023C0C364224", "0880023C3CAB4224", false, false},
    {ModPatchTarget::MainExe, 0x80046C18ull, "0780023C0C364224", "0880023C3CAB4224", false, false},
    {ModPatchTarget::MainExe, 0x80046908ull, "1900A214", "00000000", false, false},
    {ModPatchTarget::MainExe, 0x8007AB3Cull, "000000000000", "010204204010", false, false},
    {ModPatchTarget::MainExe, 0x8007AB42ull,
     "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
     "013000023D01034A02045703056404067105157E06078A0708960809A20933AE0A32BA0B34C60C0CD20DFF0000",
     false, false},
    {ModPatchTarget::MainExe, 0x80073658ull,
     "30003D014A025703640471057E068B079808A509B20ABF0BFF000000",
     "30003D014A025703640471057E068A079608A209AE0ABA0BC60CD20D",
     false, false},
    {ModPatchTarget::MainExe, 0x8001C010ull,
     "B403E2A1B503E3A1B603E4A1",
     "C9001B93A0EA010840007B33",
     false, false},
    {ModPatchTarget::MainExe, 0x8007AA80ull,
     "00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
     "0E00601700000000690100A36A0100A36B0100A36C0100A36D0100A36E0100A36F0100A3700100A33A0400A3650400A3660400A307700008670400A3B403E2A1B503E3A107700008B603E4A1",
     false, false},
    {ModPatchTarget::DiscUser, 0x19CB1660ull,
     "3A04638203000224", "91EA0108C9005392", true, false},
    {ModPatchTarget::MainExe, 0x8007AA44ull,
     "000000000000000000000000000000000000000000000000000000000000000000000000",
     "0000000040007332020060163A0443822FBC03080000533603000234B2BB030800000000",
     false, false},
    {ModPatchTarget::DiscUser, 0x19D9B3DCull,
     "3A04638203000224", "EDE90108C9005B92", false, true},
    {ModPatchTarget::MainExe, 0x8007A7B4ull,
     "000000000000000000000000000000000000000000000000000000000000000000000000",
     "0000000040007B330300601700000000A1B50308000000003A04638211B5030803000234",
     false, false},
    {ModPatchTarget::MainExe, 0x800530A8ull, "0200628400000000", "80EA010899CF6292", false, false},
    {ModPatchTarget::MainExe, 0x8007AA00ull,
     "0000000000000000000000000000000000000000000000000000000000000000",
     "000000002000423003004010020062842C4C010800000000844C010800000000",
     false, false},
    {ModPatchTarget::DiscUser, 0x19D173F8ull, "06004014FF000524", "88EA0108B900A490", false, false},
    {ModPatchTarget::MainExe, 0x8007AA20ull,
     "00000000000000000000000000000000000000000000000000000000000000000000000000000000",
     "000000002000843005008010FF000534030040140000000018C90308000000001DC9030800000000",
     false, false},
};

std::vector<uint8_t> hex_bytes(std::string_view text) {
    std::vector<uint8_t> out;
    if (text.size() % 2 != 0) return out;
    out.reserve(text.size() / 2);
    for (size_t at = 0; at < text.size(); at += 2) {
        uint8_t value = 0;
        const auto parsed = std::from_chars(
            text.data() + at, text.data() + at + 2, value, 16);
        if (parsed.ec != std::errc() || parsed.ptr != text.data() + at + 2)
            return {};
        out.push_back(value);
    }
    return out;
}

const ModFeatureSelection* selected(
    const ModSelection& selection, std::string_view feature_id
) {
    const auto found = selection.features.find(std::string(feature_id));
    return found == selection.features.end() ? nullptr : &found->second;
}

bool enabled(const ModSelection& selection, std::string_view feature_id) {
    const ModFeatureSelection* feature = selected(selection, feature_id);
    return feature && feature->has_enabled && feature->enabled;
}

bool active_feature_enabled(
    const PSXRecompV4::ModBuiltinResolverContext& context,
    std::string_view package_id, std::string_view feature_id
) {
    if (!context.active_packages || !context.selections)
        return false;
    const auto active_package =
        context.active_packages->find(std::string(package_id));
    if (active_package == context.active_packages->end())
        return false;
    const auto selection = context.selections->find(std::string(package_id));
    if (selection == context.selections->end())
        return false;
    return enabled(selection->second, feature_id);
}

void add_write(
    std::vector<ModResolution::Write>& writes, ModPatchTarget target,
    uint64_t location, std::string_view expected,
    std::string_view replacement
) {
    ModResolution::Write write;
    write.target = target;
    write.location = location;
    write.expected = hex_bytes(expected);
    write.replacement = hex_bytes(replacement);
    write.package_id = std::string(kPackageId);
    write.feature_id = std::string(kFeatureId);
    writes.push_back(std::move(write));
}

bool validate(const ModPackage& package, std::vector<std::string>& errors) {
    if (
        package.id != kPackageId || package.version != kPackageVersion ||
        package.resolver != "builtin:" + std::string(kResolverId) ||
        package.targets.size() != 1 ||
        package.targets[0].game_id != kGameId ||
        package.targets[0].disc_sha256 != kStockDisc ||
        !package.targets[0].exe_sha256.empty() ||
        !package.patches.empty() || !package.overlays.empty() ||
        !package.derived_discs.empty() || !package.conflicts.empty() ||
        !package.options.empty() || !package.constraints.empty()
    ) {
        errors.push_back(package.id + ": trusted manifest contract mismatch");
        return false;
    }
    if (
        package.dependencies.size() != 1 ||
        package.dependencies[0].id != kNativePackageId ||
        package.dependencies[0].version != ">=1.10.4"
    ) {
        errors.push_back(package.id + ": trusted dependency mismatch");
        return false;
    }
    if (
        package.features.size() != 1 ||
        package.features[0].id != kFeatureId ||
        package.features[0].default_enabled || package.features[0].legacy
    ) {
        errors.push_back(package.id + ": trusted feature inventory mismatch");
        return false;
    }
    return true;
}

bool resolve_ingame_options(
    const ModPackage& package, const ModSelection& selection,
    const PSXRecompV4::ModBuiltinResolverContext& context,
    std::vector<ModResolution::Write>& writes,
    std::vector<std::string>& errors
) {
    if (!validate(package, errors)) return false;
    if (!selection.values.empty() ||
        (!selection.version.empty() && selection.version != kPackageVersion)) {
        errors.push_back(package.id + ": invalid trusted package selection");
        return false;
    }
    for (const auto& [id, feature] : selection.features) {
        if (id != kFeatureId || !feature.values.empty()) {
            errors.push_back(package.id + ": unknown or configured feature");
            return false;
        }
    }
    if (!enabled(selection, kFeatureId))
        return true;

    if (!active_feature_enabled(context, kNativePackageId, "retranslation")) {
        errors.push_back(
            package.id + ": Settings Menu Options requires native Retranslation"
        );
        return false;
    }
    const bool disable_fire = active_feature_enabled(
        context, kNativePackageId, "disable_nightmare_fire");

    for (const Site& site : kSites) {
        if (disable_fire && site.fire_overlap_a)
            continue;
        if (disable_fire && site.fire_overlap_b) {
            add_write(
                writes, site.target, site.location, site.expected,
                "A1B50308C9005B92"
            );
            continue;
        }
        add_write(
            writes, site.target, site.location, site.expected,
            site.replacement);
    }
    return true;
}

const bool kRegistered = mod_register_builtin_resolver(
    std::string(kResolverId), resolve_ingame_options);

} // namespace
