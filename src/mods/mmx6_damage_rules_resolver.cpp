#include "mod_packages.h"

#include <algorithm>
#include <charconv>
#include <cstdint>
#include <iterator>
#include <set>
#include <string>
#include <string_view>
#include <vector>

namespace {
using PSXRecompV4::ModFeature;
using PSXRecompV4::ModFeatureSelection;
using PSXRecompV4::ModOption;
using PSXRecompV4::ModPackage;
using PSXRecompV4::ModPatchTarget;
using PSXRecompV4::ModResolution;
using PSXRecompV4::ModSelection;
using PSXRecompV4::mod_register_builtin_resolver;

constexpr std::string_view kPackageId = "mmx6.tweaks.damage-rules";
constexpr std::string_view kPackageVersion = "1.1.0";
constexpr std::string_view kResolverId = "mmx6-damage-rules";
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
        if (parsed.ec != std::errc() || parsed.ptr != text.data() + at + 2) {
            return {};
        }
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

const ModOption* option(
    const ModPackage& package, std::string_view feature_id,
    std::string_view option_id
) {
    const auto found = std::find_if(
        package.options.begin(), package.options.end(),
        [&](const ModOption& item) {
            return item.feature_id == feature_id && item.id == option_id;
        });
    return found == package.options.end() ? nullptr : &*found;
}

bool integer(
    const ModPackage& package, const ModSelection& selection,
    std::string_view feature_id, std::string_view option_id, int64_t minimum,
    int64_t maximum, int64_t& value, std::vector<std::string>& errors
) {
    const ModOption* declared = option(package, feature_id, option_id);
    const ModFeatureSelection* feature = selected(selection, feature_id);
    if (!declared) {
        errors.push_back(
            package.id + "/" + std::string(feature_id) +
            ": missing trusted integer option " + std::string(option_id));
        return false;
    }
    std::string text = declared->default_value;
    if (feature) {
        const auto found = feature->values.find(std::string(option_id));
        if (found != feature->values.end()) text = found->second;
    }
    const auto parsed = std::from_chars(
        text.data(), text.data() + text.size(), value);
    if (
        parsed.ec != std::errc() || parsed.ptr != text.data() + text.size() ||
        value < minimum || value > maximum
    ) {
        errors.push_back(
            package.id + "/" + std::string(feature_id) +
            ": integer option outside trusted source range");
        return false;
    }
    return true;
}

void add_write(
    std::vector<ModResolution::Write>& writes, ModPatchTarget target,
    uint64_t location, std::string_view expected, std::string_view replacement,
    std::string_view feature_id
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
        !package.dependencies.empty() || !package.conflicts.empty() ||
        !package.constraints.empty()
    ) {
        errors.push_back(package.id + ": trusted manifest contract mismatch");
        return false;
    }

    std::set<std::string> features;
    for (const ModFeature& feature : package.features) {
        if (feature.default_enabled || feature.legacy) {
            errors.push_back(
                package.id + ": features must be independently disabled");
            return false;
        }
        features.insert(feature.id);
    }
    const std::set<std::string> expected_features = {
        "gate_vulnerable_to_normal_attacks",
        "gate_orb_explosion_damage",
    };
    if (features != expected_features || package.options.size() != 1) {
        errors.push_back(package.id + ": trusted feature inventory mismatch");
        return false;
    }
    const ModOption* damage =
        option(package, "gate_orb_explosion_damage", "damage");
    if (
        !damage || damage->default_value != "4" || damage->min_value != 1 ||
        damage->max_value != 127 || damage->step != 1
    ) {
        errors.push_back(package.id + ": trusted option inventory mismatch");
        return false;
    }
    return true;
}

bool resolve_damage_rules(
    const ModPackage& package, const ModSelection& selection,
    std::vector<ModResolution::Write>& writes,
    std::vector<std::string>& errors
) {
    if (!validate(package, errors)) return false;
    for (const auto& [id, feature] : selection.features) {
        if (id != "gate_vulnerable_to_normal_attacks" &&
            id != "gate_orb_explosion_damage") {
            errors.push_back(package.id + ": unknown selected feature " + id);
            return false;
        }
        for (const auto& [key, ignored] : feature.values) {
            (void)ignored;
            if (id != "gate_orb_explosion_damage" || key != "damage") {
                errors.push_back(package.id + ": unknown trusted option " + key);
                return false;
            }
        }
    }

    if (enabled(selection, "gate_vulnerable_to_normal_attacks")) {
        add_write(
            writes, ModPatchTarget::DiscUser, 433622372,
            "5C0022920000000023100202067862A05C0030A20F80023CDC77438C00000000",
            "840024928DE801085C002292067862A0840024A203004004DC77638C0F80023C",
            "gate_vulnerable_to_normal_attacks");
        add_write(
            writes, ModPatchTarget::MainExe, 2147686660, "06008214",
            "48C60008", "gate_vulnerable_to_normal_attacks");
        add_write(
            writes, ModPatchTarget::MainExe, 2147983924,
            "00000000000000000000000000000000000000000000000000000000000000000000000000000000",
            "0500801423100202050040040000000074BD03084000043476BD03085C0030A27ABD030800000000",
            "gate_vulnerable_to_normal_attacks");
    }

    if (enabled(selection, "gate_orb_explosion_damage")) {
        int64_t damage = 4;
        if (!integer(
                package, selection, "gate_orb_explosion_damage", "damage",
                1, 127, damage, errors))
            return false;
        if (damage != 4) {
            const uint16_t encoded =
                static_cast<uint16_t>(0x10000 - damage);
            const std::vector<uint8_t> replacement = {
                static_cast<uint8_t>(encoded & 0xFF),
                static_cast<uint8_t>((encoded >> 8) & 0xFF),
            };
            ModResolution::Write write;
            write.target = ModPatchTarget::DiscUser;
            write.location = 433622436;
            write.expected = {0xFC, 0xFF};
            write.replacement = replacement;
            write.package_id = std::string(kPackageId);
            write.feature_id = "gate_orb_explosion_damage";
            writes.push_back(std::move(write));
        }
    }
    return true;
}

const bool kRegistered = mod_register_builtin_resolver(
    std::string(kResolverId), resolve_damage_rules);

} // namespace
