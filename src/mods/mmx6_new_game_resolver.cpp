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

constexpr std::string_view kPackageId = "mmx6.tweaks.new-game";
constexpr std::string_view kResolverId = "mmx6-new-game";
constexpr std::string_view kSharedOwner = "new_game_foundation";

constexpr std::array<std::string_view, 18> kFeatureIds = {
    "x_life_upgrades",
    "zero_life_upgrades",
    "x_energy_upgrades",
    "zero_energy_upgrades",
    "x_starting_rank",
    "zero_starting_rank",
    "heart_tank_1",
    "heart_tank_2",
    "heart_tank_3",
    "heart_tank_4",
    "heart_tank_5",
    "heart_tank_6",
    "heart_tank_7",
    "heart_tank_8",
    "sub_tank_1",
    "sub_tank_2",
    "sub_tank_3",
    "sub_tank_4",
};

constexpr std::string_view kHookExpected = "0800E0031D00A0A0";
constexpr std::string_view kHookReplace = "78DA010810000E34";
constexpr std::string_view kTemplateExpected =
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000";
constexpr std::string_view kTemplateReplace =
    "74582C26D800AD2400008B8D04008C250000ABAD0400AD25FBFFC01DFFFFCE255F"
    "00AE9020000B3420000C345B00ABA05C00ACA00000CE355F00AEA030000B34300"
    "00C346100ABA06200ACA000000B3400000C346900ABA06B00ACA007000B340700"
    "0C348D00ABA08E00ACA000000B3400000C34D200ABA4D400ACA400000C3C0000"
    "8C357000ACAC00000B346C00ABA000000C345C01AB8C6D00ACA0030060110000"
    "0C3472E80108F5FF6B250800E0036F00ACA0";
constexpr std::string_view kTailExpected = "00000000000000000000000000000000";
constexpr std::string_view kTailReplace =
    "5E00ABA0FCFF6B25A3DA01083800ABA0";

std::vector<uint8_t> hex_bytes(std::string_view text) {
    auto digit = [](char value) -> int {
        if (value >= '0' && value <= '9') return value - '0';
        if (value >= 'A' && value <= 'F') return value - 'A' + 10;
        if (value >= 'a' && value <= 'f') return value - 'a' + 10;
        return -1;
    };
    if (text.size() % 2) return {};
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

const ModFeatureSelection* selected_feature(
    const ModSelection& selection, std::string_view feature_id
) {
    const auto found = selection.features.find(std::string(feature_id));
    return found == selection.features.end() ? nullptr : &found->second;
}

bool enabled(
    const ModSelection& selection, std::string_view feature_id
) {
    const ModFeatureSelection* feature =
        selected_feature(selection, feature_id);
    return feature && feature->has_enabled && feature->enabled;
}

const ModOption* find_option(
    const ModPackage& package,
    std::string_view feature_id,
    std::string_view option_id
) {
    for (const ModOption& option : package.options) {
        if (option.feature_id == feature_id && option.id == option_id)
            return &option;
    }
    return nullptr;
}

bool integer_value(
    const ModPackage& package,
    const ModSelection& selection,
    std::string_view feature_id,
    int minimum,
    int maximum,
    int& value,
    std::vector<std::string>& errors
) {
    const ModFeatureSelection* feature =
        selected_feature(selection, feature_id);
    const ModOption* option = find_option(package, feature_id, "count");
    if (!feature || !option) {
        errors.push_back(
            package.id + "/" + std::string(feature_id) +
            ": missing trusted integer option"
        );
        return false;
    }
    auto selected = feature->values.find("count");
    const std::string& text =
        selected == feature->values.end()
            ? option->default_value
            : selected->second;
    int parsed = 0;
    const auto conversion = std::from_chars(
        text.data(), text.data() + text.size(), parsed
    );
    if (
        conversion.ec != std::errc() ||
        conversion.ptr != text.data() + text.size() ||
        parsed < minimum ||
        parsed > maximum
    ) {
        errors.push_back(
            package.id + "/" + std::string(feature_id) +
            ": count is outside the trusted domain"
        );
        return false;
    }
    value = parsed;
    return true;
}

std::string option_value(
    const ModPackage& package,
    const ModSelection& selection,
    std::string_view feature_id,
    std::string_view option_id
) {
    const ModFeatureSelection* feature =
        selected_feature(selection, feature_id);
    const ModOption* option = find_option(package, feature_id, option_id);
    if (!feature || !option) return {};
    const auto selected = feature->values.find(std::string(option_id));
    return selected == feature->values.end()
        ? option->default_value
        : selected->second;
}

ModResolution::Write make_write(
    uint64_t address,
    std::vector<uint8_t> expected,
    std::vector<uint8_t> replacement
) {
    ModResolution::Write write;
    write.target = ModPatchTarget::MainExe;
    write.location = address;
    write.expected = std::move(expected);
    write.replacement = std::move(replacement);
    write.package_id = std::string(kPackageId);
    write.feature_id = std::string(kSharedOwner);
    return write;
}

bool resolve_new_game(
    const ModPackage& package,
    const ModSelection& selection,
    std::vector<ModResolution::Write>& writes,
    std::vector<std::string>& errors
) {
    if (
        package.id != kPackageId ||
        package.resolver != "builtin:" + std::string(kResolverId)
    ) {
        errors.push_back("MMX6 New Game resolver package identity mismatch");
        return false;
    }
    std::set<std::string> declared;
    for (const ModFeature& feature : package.features)
        declared.insert(feature.id);
    if (
        declared.size() != kFeatureIds.size() ||
        !std::all_of(
            kFeatureIds.begin(),
            kFeatureIds.end(),
            [&](std::string_view id) {
                return declared.count(std::string(id)) != 0;
            }
        )
    ) {
        errors.push_back(package.id + ": trusted feature catalog mismatch");
        return false;
    }

    bool any = false;
    for (std::string_view feature_id : kFeatureIds)
        any = any || enabled(selection, feature_id);
    if (!any) return true;

    std::vector<uint8_t> composed = hex_bytes(kTemplateReplace);
    if (composed.size() != 180) {
        errors.push_back(package.id + ": invalid built-in foundation");
        return false;
    }

    struct IntegerField {
        std::string_view feature;
        size_t offset;
        int maximum;
        int addend;
    };
    constexpr std::array<IntegerField, 4> integers = {{
        {"x_life_upgrades", 0x24, 16, 0x20},
        {"zero_life_upgrades", 0x28, 16, 0x20},
        {"x_energy_upgrades", 0x3C, 8, 0x30},
        {"zero_energy_upgrades", 0x40, 8, 0x30},
    }};
    for (const IntegerField& field : integers) {
        if (!enabled(selection, field.feature)) continue;
        int value = 0;
        if (!integer_value(
                package, selection, field.feature, 1, field.maximum,
                value, errors
            ))
            return false;
        composed[field.offset] =
            static_cast<uint8_t>(field.addend + 2 * value);
    }

    struct RankValue {
        std::string_view name;
        uint8_t rank;
        uint16_t souls;
    };
    constexpr std::array<RankValue, 7> ranks = {{
        {"C", 6, 200},
        {"B", 5, 300},
        {"A", 4, 500},
        {"SA", 3, 800},
        {"GA", 2, 1200},
        {"PA", 1, 5000},
        {"UH", 0, 9999},
    }};
    const auto apply_rank = [&](
        std::string_view feature_id, size_t rank_offset, size_t souls_offset
    ) -> bool {
        if (!enabled(selection, feature_id)) return true;
        const std::string value = option_value(
            package, selection, feature_id, "rank"
        );
        const auto found = std::find_if(
            ranks.begin(), ranks.end(),
            [&](const RankValue& rank) { return rank.name == value; }
        );
        if (found == ranks.end()) {
            errors.push_back(
                package.id + "/" + std::string(feature_id) +
                ": rank is outside the trusted domain"
            );
            return false;
        }
        composed[rank_offset] = found->rank;
        composed[souls_offset] =
            static_cast<uint8_t>(found->souls & 0xFF);
        composed[souls_offset + 1] =
            static_cast<uint8_t>(found->souls >> 8);
        return true;
    };
    if (
        !apply_rank("x_starting_rank", 0x5C, 0x6C) ||
        !apply_rank("zero_starting_rank", 0x60, 0x70)
    )
        return false;

    uint8_t heart_tanks = 0;
    for (int index = 1; index <= 8; ++index) {
        if (enabled(selection, "heart_tank_" + std::to_string(index)))
            heart_tanks |= static_cast<uint8_t>(1u << (index - 1));
    }
    composed[0x88] = heart_tanks;

    uint8_t sub_tanks = 0;
    for (int index = 1; index <= 4; ++index) {
        if (enabled(selection, "sub_tank_" + std::to_string(index)))
            sub_tanks |= static_cast<uint8_t>(1u << (index + 3));
    }
    composed[0x50] = sub_tanks;

    writes.push_back(make_write(
        0x8001E1B4, hex_bytes(kHookExpected), hex_bytes(kHookReplace)
    ));
    writes.push_back(make_write(
        0x800769E0, hex_bytes(kTemplateExpected), std::move(composed)
    ));
    writes.push_back(make_write(
        0x8007A1C8, hex_bytes(kTailExpected), hex_bytes(kTailReplace)
    ));
    return true;
}

const bool kRegistered = mod_register_builtin_resolver(
    std::string(kResolverId), resolve_new_game
);

} // namespace
