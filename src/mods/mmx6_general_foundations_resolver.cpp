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

constexpr std::string_view kPackageId = "mmx6.tweaks.general-foundations";
constexpr std::string_view kPackageVersion = "1.1.0";
constexpr std::string_view kResolverId = "mmx6-general-foundations";
constexpr std::string_view kGameId = "SLUS-01395";
constexpr std::string_view kStockDisc =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";
constexpr std::string_view kSharedOwner = "mission_report_rank_unlocks";
constexpr std::string_view kLowerDefenseOwner = "lower_defense";

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

void add_write(
    std::vector<ModResolution::Write>& writes, ModPatchTarget target,
    uint64_t location, std::string_view expected,
    std::vector<uint8_t> replacement, std::string_view feature_id
) {
    ModResolution::Write write;
    write.target = target;
    write.location = location;
    write.expected = hex_bytes(expected);
    write.replacement = std::move(replacement);
    write.package_id = std::string(kPackageId);
    write.feature_id = std::string(feature_id);
    writes.push_back(std::move(write));
}

void add_write(
    std::vector<ModResolution::Write>& writes, ModPatchTarget target,
    uint64_t location, std::string_view expected, std::string_view replacement
) {
    add_write(
        writes, target, location, expected, hex_bytes(replacement),
        kSharedOwner);
}

void add_write(
    std::vector<ModResolution::Write>& writes, ModPatchTarget target,
    uint64_t location, std::string_view expected,
    std::string_view replacement, std::string_view feature_id
) {
    add_write(
        writes, target, location, expected, hex_bytes(replacement),
        feature_id);
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
        !package.dependencies.empty() || !package.conflicts.empty() ||
        !package.constraints.empty() || !package.options.empty()
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
        "ultimate_armor_rank_unlock",
        "black_zero_rank_unlock",
        "normalize_unarmored_x_defense",
        "normalize_zero_defense",
    };
    if (features != expected_features) {
        errors.push_back(package.id + ": trusted feature inventory mismatch");
        return false;
    }
    return true;
}

bool resolve_general_foundations(
    const ModPackage& package, const ModSelection& selection,
    std::vector<ModResolution::Write>& writes,
    std::vector<std::string>& errors
) {
    if (!validate(package, errors)) return false;
    for (const auto& [id, feature] : selection.features) {
        if (
            id != "ultimate_armor_rank_unlock" &&
            id != "black_zero_rank_unlock" &&
            id != "normalize_unarmored_x_defense" &&
            id != "normalize_zero_defense"
        ) {
            errors.push_back(package.id + ": unknown selected feature " + id);
            return false;
        }
        if (!feature.values.empty()) {
            errors.push_back(package.id + ": selected feature has no options");
            return false;
        }
    }

    const bool ultimate = enabled(selection, "ultimate_armor_rank_unlock");
    const bool black = enabled(selection, "black_zero_rank_unlock");
    const bool normalize_x =
        enabled(selection, "normalize_unarmored_x_defense");
    const bool normalize_zero = enabled(selection, "normalize_zero_defense");
    if (!ultimate && !black && !normalize_x && !normalize_zero) return true;

    if (ultimate || black) {
        add_write(
        writes, ModPatchTarget::DiscUser, 0x19D4FB8C,
        "1000B0AF0F80103C1400B1AF0F80113CF948239244381026",
        "1400B1AF0F80113C1000B0AFD4E90108F948239244383026");
    add_write(
        writes, ModPatchTarget::DiscUser, 0x19D4FC58,
        "0D80043C6F000324",
        "E2E901080D80043C");
    add_write(
        writes, ModPatchTarget::DiscUser, 0x19D50E08,
        "0D80023CD0CE45246900A3900F0004240F0063300B00641421304000C800A290000000000F00423006004310010002245F00A39000000000040063340800E0035F00A3A0D0CEC5246900A290F0000324F00044300B00831400000000C800A29000000000F000423006004410020002245F00A39000000000020063340800E0035F00A3A00800E00321100000",
        "9CE9010800000000690083900F0005340F0063300B00651400004634C8008290000000000F00423006004310010002345F00839000000000040063340800E0035F0083A0D0CEC52469008290F0000334F00045300B00A31400000000C800829000000000F000423006004510020002345F00839000000000020063340800E0035F0083A0B9E9010800000000");
    add_write(
        writes, ModPatchTarget::DiscUser, 0x19D54666,
        "0015", "0018");

    std::vector<uint8_t> allocation = hex_bytes(
        "0000E737000000000000000000000000000000000000FF34690087909CC10308C80088908D00832421186500000063905F0082900D006014000000000200A014200043300800433008006014000000000200A0140200033401000334060082900000000025104300060082A00800E00300000000060082905F00859016004010000000000100433007006010000000000800A5345F0085A001004238060082A00800E00305000234020043300A006010000000002000A5345F0085A002004238060082A01000A5300300A010000000000800E003070002340800E003000002340200A2242A10620005004014000000000780103C57A7103601BD03080000000000BD030800000000046801056902066700075E030000000039CF0392D2CE029298CF03A26F0003340400401004000234F8CE83A00800E003D2CE02A230BD030800000000");
    if (allocation.size() != 324) {
        errors.push_back(package.id + ": invalid built-in allocation");
        return false;
    }
    if (ultimate) {
        const std::vector<uint8_t> hook =
            hex_bytes("A5E9010C00000534");
        std::copy(hook.begin(), hook.end(), allocation.begin() + 4);
    }
    if (black) {
        const std::vector<uint8_t> hook =
            hex_bytes("A5E9010C01000534");
        std::copy(hook.begin(), hook.end(), allocation.begin() + 12);
    }
    add_write(
        writes, ModPatchTarget::MainExe, 0x8007A670,
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
        std::move(allocation), kSharedOwner);
    }
    if (normalize_x || normalize_zero) {
        const std::string_view replacement =
            normalize_x && normalize_zero
                ? "FFFF62240400422CA8C30008"
                : normalize_x
                    ? "05000234000000000E006214"
                    : "FFFF62240400422C0E006014";
        add_write(
            writes, ModPatchTarget::MainExe, 0x80030E5C,
            "FFFF62240400422C0E004014",
            replacement, kLowerDefenseOwner);
    }
    return true;
}

const bool kRegistered = mod_register_builtin_resolver(
    std::string(kResolverId), resolve_general_foundations);

} // namespace
