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
constexpr std::string_view kPackageVersion = "1.2.0";
constexpr std::string_view kResolverId = "mmx6-new-game";
constexpr std::string_view kSharedOwner = "new_game_foundation";

constexpr std::array<std::string_view, 18> kCoreFeatureIds = {
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
constexpr std::array<std::string_view, 5> kCharacterFeatureIds = {
    "available_shadow_armor",
    "available_blade_armor",
    "available_ultimate_armor",
    "available_zero",
    "available_black_zero",
};
constexpr std::array<std::string_view, 24> kPartFeatureIds = {
    "part_hyper_dash", "part_energy_saver", "part_super_recover",
    "part_buster_plus", "part_speedster", "part_jumper",
    "part_hyperdrive", "part_power_drive", "part_weapon_driver",
    "part_life_recover", "part_speed_shot", "part_shock_buffer",
    "part_d_barrier", "part_d_converter", "part_quick_charge",
    "part_weapon_plus", "part_saber_plus", "part_saber_extend",
    "part_weapon_recover", "part_over_drive", "part_rapid_5",
    "part_ultimate_buster", "part_shot_eraser", "part_master_saber",
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
constexpr std::string_view kFoundTableExpected =
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000";
constexpr std::string_view kIntroArmorExpected =
    "09000724010002245F00A2A05E00A2A03031428D040003240300431430314425"
    "5F00A7A05E00A3A0";
constexpr std::string_view kIntroArmorReplace =
    "01000224000000005E00A2A03031478D040003340400E3143031442508004224"
    "5F00A2A05E00A3A0";

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

std::set<std::string> expected_feature_ids() {
    std::set<std::string> result;
    for (std::string_view id : kCoreFeatureIds)
        result.insert(std::string(id));
    for (std::string_view id : kCharacterFeatureIds)
        result.insert(std::string(id));
    result.insert("intro_stage_armor");
    for (std::string_view id : kPartFeatureIds)
        result.insert(std::string(id));
    result.insert("mark_no_item_reploids");
    for (int index = 1; index <= 8; ++index) {
        result.insert("parts_life_up_" + std::to_string(index));
        result.insert("parts_energy_up_" + std::to_string(index));
    }
    return result;
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
        package.version != kPackageVersion ||
        package.resolver != "builtin:" + std::string(kResolverId)
    ) {
        errors.push_back("MMX6 New Game resolver package identity mismatch");
        return false;
    }
    std::set<std::string> declared;
    for (const ModFeature& feature : package.features)
        declared.insert(feature.id);
    const std::set<std::string> expected = expected_feature_ids();
    if (declared != expected || package.features.size() != expected.size()) {
        errors.push_back(package.id + ": trusted feature catalog mismatch");
        return false;
    }

    bool any = false;
    for (const std::string& feature_id : expected)
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

    for (size_t index = 0; index < kCharacterFeatureIds.size(); ++index) {
        if (enabled(selection, kCharacterFeatureIds[index])) {
            composed[0x34] |= static_cast<uint8_t>(
                0x01u | (1u << (index + 1))
            );
        }
    }
    std::vector<uint8_t> intro_armor_replacement;
    if (enabled(selection, "intro_stage_armor")) {
        const std::string armor = option_value(
            package, selection, "intro_stage_armor", "armor"
        );
        uint8_t intro_character = 0;
        if (armor == "none") {
            intro_character = 0x00;
            composed[0x34] |= 0x01;
        } else if (armor == "blade") {
            intro_character = 0x03;
            composed[0x34] |= 0x05;
            composed[0x4C] |= 0x0F;
        } else if (armor == "shadow") {
            intro_character = 0x02;
            composed[0x34] |= 0x03;
            composed[0x4C] |= 0xF0;
        } else if (armor == "ultimate") {
            intro_character = 0x04;
            composed[0x34] |= 0x09;
        } else {
            errors.push_back(package.id + "/intro_stage_armor: "
                             "armor is outside the trusted domain");
            return false;
        }
        if (enabled(selection, "available_shadow_armor"))
            composed[0x4C] |= 0xF0;
        if (enabled(selection, "available_blade_armor"))
            composed[0x4C] |= 0x0F;
        intro_armor_replacement = hex_bytes(kIntroArmorReplace);
        if (intro_armor_replacement.size() != 40) {
            errors.push_back(package.id + ": invalid intro armor hook");
            return false;
        }
        intro_armor_replacement[0] = intro_character;
    }

    std::vector<uint8_t> found_table(64, 0);
    bool found_table_active = false;
    if (enabled(selection, "mark_no_item_reploids")) {
        constexpr std::string_view no_item_table =
            "2020202202222220222000222220022202222222022200202222022222000220"
            "2222202020222002222222200202022020222220222002202202222002202022";
        found_table = hex_bytes(no_item_table);
        if (found_table.size() != 64) {
            errors.push_back(package.id + ": invalid no-item table");
            return false;
        }
        found_table_active = true;
    }
    const auto apply_part = [&](
        std::string_view feature_id,
        size_t template_offset,
        uint8_t template_mask,
        size_t table_offset,
        uint8_t table_mask
    ) {
        if (!enabled(selection, feature_id)) return;
        composed[template_offset] |= template_mask;
        found_table[table_offset] |= table_mask;
        found_table_active = true;
    };
    constexpr std::array<size_t, 8> life_table_offsets = {
        0x00, 0x0D, 0x14, 0x1E, 0x22, 0x2C, 0x30, 0x3C,
    };
    constexpr std::array<uint8_t, 8> life_table_masks = {
        0x02, 0x02, 0x20, 0x20, 0x02, 0x20, 0x02, 0x20,
    };
    constexpr std::array<size_t, 8> energy_table_offsets = {
        0x01, 0x0A, 0x16, 0x1A, 0x26, 0x2B, 0x33, 0x3E,
    };
    constexpr std::array<uint8_t, 8> energy_table_masks = {
        0x02, 0x02, 0x02, 0x20, 0x02, 0x02, 0x02, 0x02,
    };
    for (int index = 1; index <= 8; ++index) {
        const size_t field_index = static_cast<size_t>(index - 1);
        const uint8_t field_mask =
            static_cast<uint8_t>(1u << field_index);
        apply_part(
            "parts_life_up_" + std::to_string(index),
            0x90, field_mask,
            life_table_offsets[field_index], life_table_masks[field_index]
        );
        apply_part(
            "parts_energy_up_" + std::to_string(index),
            0xA0, field_mask,
            energy_table_offsets[field_index], energy_table_masks[field_index]
        );
    }

    struct PartField {
        std::string_view feature;
        size_t template_offset;
        uint8_t template_mask;
        size_t table_offset;
        uint8_t table_mask;
    };
    constexpr std::array<PartField, 24> part_fields = {{
        {"part_hyper_dash", 0x80, 0x10, 0x2E, 0x20},
        {"part_energy_saver", 0x80, 0x20, 0x35, 0x02},
        {"part_super_recover", 0x80, 0x40, 0x04, 0x20},
        {"part_buster_plus", 0x80, 0x80, 0x10, 0x20},
        {"part_speedster", 0x80, 0x04, 0x23, 0x02},
        {"part_jumper", 0x80, 0x08, 0x0E, 0x20},
        {"part_hyperdrive", 0x81, 0x10, 0x1D, 0x20},
        {"part_power_drive", 0x81, 0x20, 0x16, 0x20},
        {"part_weapon_driver", 0x81, 0x40, 0x0A, 0x20},
        {"part_life_recover", 0x81, 0x80, 0x02, 0x02},
        {"part_speed_shot", 0x81, 0x01, 0x3B, 0x02},
        {"part_shock_buffer", 0x81, 0x02, 0x1D, 0x02},
        {"part_d_barrier", 0x81, 0x04, 0x36, 0x20},
        {"part_d_converter", 0x81, 0x08, 0x39, 0x20},
        {"part_quick_charge", 0x7C, 0x10, 0x24, 0x02},
        {"part_weapon_plus", 0x7C, 0x20, 0x37, 0x02},
        {"part_saber_plus", 0x7C, 0x40, 0x2F, 0x02},
        {"part_saber_extend", 0x7C, 0x80, 0x1F, 0x02},
        {"part_weapon_recover", 0x7C, 0x01, 0x2D, 0x20},
        {"part_over_drive", 0x7C, 0x02, 0x27, 0x20},
        {"part_rapid_5", 0x7C, 0x04, 0x07, 0x02},
        {"part_ultimate_buster", 0x7C, 0x08, 0x17, 0x02},
        {"part_shot_eraser", 0x7D, 0x01, 0x09, 0x02},
        {"part_master_saber", 0x7D, 0x02, 0x3D, 0x02},
    }};
    for (const PartField& field : part_fields) {
        apply_part(
            field.feature, field.template_offset, field.template_mask,
            field.table_offset, field.table_mask
        );
    }

    writes.push_back(make_write(
        0x8001E1B4, hex_bytes(kHookExpected), hex_bytes(kHookReplace)
    ));
    writes.push_back(make_write(
        0x800769E0, hex_bytes(kTemplateExpected), std::move(composed)
    ));
    writes.push_back(make_write(
        0x8007A1C8, hex_bytes(kTailExpected), hex_bytes(kTailReplace)
    ));
    if (!intro_armor_replacement.empty()) {
        writes.push_back(make_write(
            0x8001E164, hex_bytes(kIntroArmorExpected),
            std::move(intro_armor_replacement)
        ));
    }
    if (found_table_active) {
        writes.push_back(make_write(
            0x800769A0, hex_bytes(kFoundTableExpected),
            std::move(found_table)
        ));
    }
    return true;
}

const bool kRegistered = mod_register_builtin_resolver(
    std::string(kResolverId), resolve_new_game
);

} // namespace
