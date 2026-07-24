#include "mod_packages.h"

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

constexpr std::string_view kPackageId = "mmx6.tweaks.player-standalone";
constexpr std::string_view kPackageVersion = "1.1.0";
constexpr std::string_view kResolverId = "mmx6-player-standalone";
constexpr std::string_view kGameId = "SLUS-01395";
constexpr std::string_view kStockDisc =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";

std::vector<uint8_t> hex_bytes(std::string_view text) {
    std::vector<uint8_t> out;
    out.reserve(text.size() / 2);
    for (size_t at = 0; at + 1 < text.size(); at += 2) {
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
    std::string_view replacement, std::string_view feature_id
) {
    ModResolution::Write write;
    write.target = target;
    write.location = location;
    write.expected = hex_bytes(expected);
    write.replacement = hex_bytes(replacement);
    write.package_id = std::string(kPackageId);
    write.feature_id = std::string(feature_id);
    writes.push_back(std::move(write));
}

bool validate(const ModPackage& package, std::vector<std::string>& errors) {
    if (
        package.id != kPackageId || package.version != kPackageVersion ||
        package.resolver != "builtin:" + std::string(kResolverId) ||
        package.targets.size() != 1 ||
        package.targets[0].game_id != kGameId ||
        package.targets[0].disc_sha256 != kStockDisc ||
        !package.targets[0].exe_sha256.empty() || !package.patches.empty() ||
        !package.overlays.empty() || !package.derived_discs.empty() ||
        !package.options.empty() || !package.dependencies.empty() ||
        !package.conflicts.empty() || !package.constraints.empty()
    ) {
        errors.push_back(package.id + ": trusted manifest contract mismatch");
        return false;
    }
    std::set<std::string> features;
    for (const ModFeature& feature : package.features) {
        if (feature.default_enabled || feature.legacy) {
            errors.push_back(package.id + ": feature defaults must be stock");
            return false;
        }
        features.insert(feature.id);
    }
    const std::set<std::string> expected_features = {
        "unlock_x_air_dash",
        "guard_shell_bug_fix",
        "disable_zero_weapon_autoselect",
    };
    if (features != expected_features) {
        errors.push_back(package.id + ": trusted feature inventory mismatch");
        return false;
    }
    return true;
}

bool resolve_player_standalone(
    const ModPackage& package, const ModSelection& selection,
    const PSXRecompV4::ModBuiltinResolverContext& context,
    std::vector<ModResolution::Write>& writes,
    std::vector<std::string>& errors
) {
    if (!validate(package, errors)) return false;
    for (const auto& [id, feature] : selection.features) {
        if (
            id != "unlock_x_air_dash" &&
            id != "guard_shell_bug_fix" &&
            id != "disable_zero_weapon_autoselect"
        ) {
            errors.push_back(package.id + ": unknown selected feature " + id);
            return false;
        }
        if (!feature.values.empty()) {
            errors.push_back(package.id + ": selected feature has no options");
            return false;
        }
    }

    const bool armor_by_part = active_feature_enabled(
        context, "mmx6.tweaks.general-foundations",
        "incomplete_armors_by_part");
    if (enabled(selection, "unlock_x_air_dash") && !armor_by_part) {
        add_write(
            writes, ModPatchTarget::MainExe, 0x80039120,
            "090040140000000092000292000000003900401421100000E7000392040002243500621421100000D3000282000000002C00401421100000",
            "060040140000033492000292000000003900401421100000E7000392D3000482010063303400601400000234000000002C00801400000234",
            "unlock_x_air_dash");
    }
    if (enabled(selection, "guard_shell_bug_fix")) {
        add_write(
            writes, ModPatchTarget::MainExe, 0x800314E4,
            "00000000290040100780023C5800238E9C42522405007214212000029C0002820000000021004010000000002128200280000626",
            "01000592290040100780023C5800238E9C42522405007214212000029C00028200000000210040100000000028EB010807000234",
            "guard_shell_bug_fix");
        add_write(
            writes, ModPatchTarget::MainExe, 0x8007ACA0,
            "00000000000000000000000000000000000000000000000000000000000000000000000000000000",
            "0E00679005004514FBFF4224030047140000000047C50008000002342128200246C5000880000626",
            "guard_shell_bug_fix");
    }
    if (enabled(selection, "disable_zero_weapon_autoselect")) {
        add_write(writes, ModPatchTarget::MainExe, 0x8003F78C, "93000382A8000526401803002128A3000000A49400000000232082000000A4A4", "D6010382A800052602006014D60100A29300038200000000C9D8010C40180300", "disable_zero_weapon_autoselect");
        add_write(writes, ModPatchTarget::MainExe, 0x80076324, "000000000000000000000000000000000000000000000000", "2128A3000000A49400000000232082000800E0030000A4A4", "disable_zero_weapon_autoselect");
        add_write(writes, ModPatchTarget::DiscUser, 0x19C84B1C, "930002A2", "D60102A2", "disable_zero_weapon_autoselect");
        add_write(writes, ModPatchTarget::MainExe, 0x8004399C, "930022A2", "D60122A2", "disable_zero_weapon_autoselect");
        add_write(writes, ModPatchTarget::MainExe, 0x80043A1C, "93002582", "D6012582", "disable_zero_weapon_autoselect");
        add_write(writes, ModPatchTarget::MainExe, 0x800436D0, "93008282000000002128400040100200", "02008392FFD801089300858240100500", "disable_zero_weapon_autoselect");
        add_write(writes, ModPatchTarget::MainExe, 0x800763FC, "00000000000000000000000000000000000000000000000000000000", "030007340300601000000000D60187A20000E534B70D010800000000", "disable_zero_weapon_autoselect");
        add_write(writes, ModPatchTarget::MainExe, 0x8003A938, "930011A2", "D60111A2", "disable_zero_weapon_autoselect");
        add_write(writes, ModPatchTarget::DiscUser, 0x19C872BC, "930002A2", "D60102A2", "disable_zero_weapon_autoselect");
        add_write(writes, ModPatchTarget::DiscUser, 0x19C84C30, "930002A2", "D60102A2", "disable_zero_weapon_autoselect");
        add_write(writes, ModPatchTarget::DiscUser, 0x19C8636C, "930002A2", "D60102A2", "disable_zero_weapon_autoselect");
        add_write(writes, ModPatchTarget::DiscUser, 0x19C84F00, "930022A2", "D60122A2", "disable_zero_weapon_autoselect");
        add_write(writes, ModPatchTarget::DiscUser, 0x19C84F60, "93002582", "D6012582", "disable_zero_weapon_autoselect");
        add_write(writes, ModPatchTarget::DiscUser, 0x19C874A4, "930002A2", "D60102A2", "disable_zero_weapon_autoselect");
        add_write(writes, ModPatchTarget::MainExe, 0x80045518, "930042A2", "D60142A2", "disable_zero_weapon_autoselect");
    }
    return true;
}

const bool kRegistered = mod_register_builtin_resolver(
    std::string(kResolverId), resolve_player_standalone);

} // namespace
