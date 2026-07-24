#include "mod_packages.h"

#include <algorithm>
#include <array>
#include <charconv>
#include <cstdint>
#include <set>
#include <string>
#include <string_view>
#include <vector>

namespace {

using namespace PSXRecompV4;

constexpr std::string_view kPackageId = "mmx6.tweaks.continuous-dash";
constexpr std::string_view kPackageVersion = "1.0.0";
constexpr std::string_view kResolverId = "mmx6-continuous-dash";
constexpr std::string_view kGameId = "SLUS-01395";
constexpr std::string_view kStockDisc =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";
constexpr std::array<std::string_view, 2> kFeatures = {
    "continuous_dash_speed_normal",
    "continuous_dash_speed_hyper",
};

std::vector<uint8_t> hex_bytes(std::string_view text) {
    const auto digit = [](char value) -> int {
        if (value >= '0' && value <= '9') return value - '0';
        if (value >= 'a' && value <= 'f') return value - 'a' + 10;
        if (value >= 'A' && value <= 'F') return value - 'A' + 10;
        return -1;
    };
    if (text.empty() || text.size() % 2) return {};
    std::vector<uint8_t> result;
    result.reserve(text.size() / 2);
    for (size_t index = 0; index < text.size(); index += 2) {
        const int high = digit(text[index]);
        const int low = digit(text[index + 1]);
        if (high < 0 || low < 0) return {};
        result.push_back(static_cast<uint8_t>((high << 4) | low));
    }
    return result;
}

const ModFeatureSelection* selected(
    const ModSelection& selection, std::string_view id
) {
    const auto found = selection.features.find(std::string(id));
    return found == selection.features.end() ? nullptr : &found->second;
}

bool enabled(const ModSelection& selection, std::string_view id) {
    const ModFeatureSelection* value = selected(selection, id);
    return value && value->has_enabled && value->enabled;
}

const ModOption* option(
    const ModPackage& package, std::string_view feature
) {
    const auto found = std::find_if(
        package.options.begin(), package.options.end(),
        [&](const ModOption& value) {
            return value.feature_id == feature && value.id == "speed";
        });
    return found == package.options.end() ? nullptr : &*found;
}

bool speed_value(
    const ModPackage& package, const ModSelection& selection,
    std::string_view feature, int minimum, int maximum, uint32_t& result,
    std::vector<std::string>& errors
) {
    const ModFeatureSelection* chosen = selected(selection, feature);
    const ModOption* declaration = option(package, feature);
    if (!chosen || !declaration) {
        errors.push_back(
            package.id + "/" + std::string(feature) +
            ": missing trusted speed option");
        return false;
    }
    const auto explicit_value = chosen->values.find("speed");
    const std::string& text =
        explicit_value == chosen->values.end()
            ? declaration->default_value
            : explicit_value->second;
    int parsed = 0;
    const auto conversion = std::from_chars(
        text.data(), text.data() + text.size(), parsed);
    if (conversion.ec != std::errc() ||
        conversion.ptr != text.data() + text.size() ||
        parsed < minimum || parsed > maximum) {
        errors.push_back(
            package.id + "/" + std::string(feature) +
            ": speed is outside the trusted source range");
        return false;
    }
    result = static_cast<uint32_t>(parsed);
    return true;
}

std::array<uint8_t, 2> upper_half(uint32_t value) {
    return {
        static_cast<uint8_t>((value >> 16) & 0xFF),
        static_cast<uint8_t>((value >> 24) & 0xFF),
    };
}

std::array<uint8_t, 2> lower_half(uint32_t value) {
    return {
        static_cast<uint8_t>(value & 0xFF),
        static_cast<uint8_t>((value >> 8) & 0xFF),
    };
}

void add_full(
    std::vector<ModResolution::Write>& writes, uint64_t address,
    std::string_view expected, std::vector<uint8_t> replacement,
    std::string_view owner
) {
    ModResolution::Write write;
    write.target = ModPatchTarget::MainExe;
    write.location = address;
    write.expected = hex_bytes(expected);
    write.replacement = std::move(replacement);
    write.package_id = std::string(kPackageId);
    write.feature_id = std::string(owner);
    writes.push_back(std::move(write));
}

bool add_speed_fields(
    std::vector<ModResolution::Write>& writes, uint64_t address,
    std::string_view expected, uint32_t speed, std::vector<std::string>& errors
) {
    ModResolution::Write write;
    write.target = ModPatchTarget::MainExe;
    write.location = address;
    write.expected = hex_bytes(expected);
    write.replacement = write.expected;
    const auto high = upper_half(speed);
    const auto low = lower_half(speed);
    if (write.replacement.size() != 8) {
        errors.push_back("continuous dash speed write has invalid guard size");
        return false;
    }
    std::copy(high.begin(), high.end(), write.replacement.begin());
    std::copy(low.begin(), low.end(), write.replacement.begin() + 4);
    write.package_id = std::string(kPackageId);
    write.feature_id = "continuous_dash_speed_normal";
    writes.push_back(std::move(write));
    return true;
}

bool validate_package(
    const ModPackage& package, std::vector<std::string>& errors
) {
    if (package.id != kPackageId ||
        package.version != kPackageVersion ||
        package.resolver != "builtin:" + std::string(kResolverId) ||
        package.targets.size() != 1 ||
        package.targets[0].game_id != kGameId ||
        package.targets[0].disc_sha256 != kStockDisc ||
        !package.targets[0].exe_sha256.empty() ||
        !package.patches.empty() || !package.overlays.empty() ||
        !package.derived_discs.empty() || !package.dependencies.empty() ||
        !package.conflicts.empty() || !package.constraints.empty()) {
        errors.push_back(package.id + ": trusted manifest contract mismatch");
        return false;
    }
    std::set<std::string> actual;
    for (const ModFeature& feature : package.features) {
        if (feature.default_enabled || feature.legacy)
            return errors.push_back(
                package.id + ": features must be independently disabled"), false;
        actual.insert(feature.id);
    }
    const std::set<std::string> wanted(kFeatures.begin(), kFeatures.end());
    if (actual != wanted || package.options.size() != 2) {
        errors.push_back(package.id + ": trusted feature inventory mismatch");
        return false;
    }
    return true;
}

bool resolve_continuous_dash(
    const ModPackage& package, const ModSelection& selection,
    const PSXRecompV4::ModBuiltinResolverContext& context,
    std::vector<ModResolution::Write>& writes,
    std::vector<std::string>& errors
) {
    (void)context;
    if (!validate_package(package, errors)) return false;
    for (const auto& [id, value] : selection.features) {
        if (std::find(kFeatures.begin(), kFeatures.end(), id) ==
            kFeatures.end()) {
            errors.push_back(package.id + ": unknown selected feature " + id);
            return false;
        }
        for (const auto& [key, ignored] : value.values) {
            (void)ignored;
            if (key != "speed") {
                errors.push_back(
                    package.id + "/" + id +
                    ": unknown trusted option " + key);
                return false;
            }
        }
    }
    const bool normal_enabled =
        enabled(selection, "continuous_dash_speed_normal");
    const bool hyper_enabled =
        enabled(selection, "continuous_dash_speed_hyper");
    if (!normal_enabled && !hyper_enabled) return true;

    uint32_t normal = 270336;
    uint32_t hyper = 67584;
    if (normal_enabled &&
        !speed_value(
            package, selection, "continuous_dash_speed_normal",
            200000, 600000, normal, errors))
        return false;
    if (hyper_enabled &&
        !speed_value(
            package, selection, "continuous_dash_speed_hyper",
            60000, 160000, hyper, errors))
        return false;

    std::vector<uint8_t> foundation = hex_bytes(
        "0100053C0008A5340401028E0C01048E211043000801038E");
    if (foundation.size() != 24) {
        errors.push_back(package.id + ": invalid trusted hook foundation");
        return false;
    }
    const auto hyper_high = upper_half(hyper);
    const auto hyper_low = lower_half(hyper);
    std::copy(hyper_high.begin(), hyper_high.end(), foundation.begin());
    std::copy(hyper_low.begin(), hyper_low.end(), foundation.begin() + 4);
    add_full(
        writes, 0x8003D694,
        "0100053C0401028E0C01048E211043000801038E0008A534",
        std::move(foundation), "continuous_dash_foundation");

    if (normal_enabled) {
        if (!add_speed_fields(
                writes, 0x8003D5A8, "0600093C00802935", normal, errors))
            return false;
        if (!add_speed_fields(
                writes, 0x8003D5B0, "04000B3C00206B35", normal, errors))
            return false;
    }
    return true;
}

const bool kRegistered = mod_register_builtin_resolver(
    std::string(kResolverId), resolve_continuous_dash);

} // namespace
