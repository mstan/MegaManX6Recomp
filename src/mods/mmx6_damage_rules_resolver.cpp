#include "mod_packages.h"

#include <algorithm>
#include <array>
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
constexpr std::string_view kPackageVersion = "1.2.0";
constexpr std::string_view kResolverId = "mmx6-damage-rules";
constexpr std::string_view kGameId = "SLUS-01395";
constexpr std::string_view kStockDisc =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";

struct BossOption {
    uint8_t boss;
    uint8_t level;
    const char* id;
    int64_t default_value;
};

enum class SiteKind {
    DirectByte,
    BaseByte,
    DeltaByte,
    DeltaHalfword,
    MotherBase,
    MotherZero4,
    SnakeHealth,
    SnakeInverse,
    SnakeQuarter,
};

struct BossSite {
    uint8_t boss;
    uint8_t level;
    SiteKind kind;
    uint64_t location;
    const char* expected;
};

constexpr std::array<BossOption, 61> kBossOptions = {{
    {1, 1, "d1000_level_1", 32},
    {2, 1, "nightmare_snake_level_1", 127},
    {3, 1, "nightmare_pressure_level_1", 48},
    {4, 1, "illumina_level_1", 64},
    {5, 1, "commander_yammark_level_1", 32},
    {5, 2, "commander_yammark_level_2", 38},
    {5, 3, "commander_yammark_level_3", 44},
    {5, 4, "commander_yammark_level_4", 48},
    {6, 1, "blizzard_wolfang_level_1", 48},
    {6, 2, "blizzard_wolfang_level_2", 50},
    {6, 3, "blizzard_wolfang_level_3", 52},
    {6, 4, "blizzard_wolfang_level_4", 54},
    {7, 1, "blaze_heatnix_level_1", 48},
    {7, 3, "blaze_heatnix_level_3", 52},
    {7, 4, "blaze_heatnix_level_4", 56},
    {8, 1, "metal_shark_player_level_1", 48},
    {8, 2, "metal_shark_player_level_2", 48},
    {8, 3, "metal_shark_player_level_3", 52},
    {8, 4, "metal_shark_player_level_4", 56},
    {9, 1, "ground_scaravich_level_1", 40},
    {10, 1, "rainy_turtloid_level_1", 56},
    {10, 2, "rainy_turtloid_level_2", 56},
    {10, 3, "rainy_turtloid_level_3", 60},
    {10, 4, "rainy_turtloid_level_4", 64},
    {11, 1, "shield_sheldon_level_1", 32},
    {11, 2, "shield_sheldon_level_2", 36},
    {11, 3, "shield_sheldon_level_3", 40},
    {11, 4, "shield_sheldon_level_4", 48},
    {12, 1, "infinity_mijinion_level_1", 48},
    {12, 2, "infinity_mijinion_level_2", 52},
    {12, 3, "infinity_mijinion_level_3", 54},
    {12, 4, "infinity_mijinion_level_4", 56},
    {13, 1, "nightmare_zero_level_1", 48},
    {13, 2, "nightmare_zero_level_2", 50},
    {13, 3, "nightmare_zero_level_3", 52},
    {13, 4, "nightmare_zero_level_4", 56},
    {14, 1, "high_max_hidden_area_level_1", 48},
    {14, 2, "high_max_hidden_area_level_2", 52},
    {14, 3, "high_max_hidden_area_level_3", 56},
    {14, 4, "high_max_hidden_area_level_4", 64},
    {15, 1, "dynamo_level_1", 50},
    {15, 2, "dynamo_level_2", 58},
    {15, 3, "dynamo_level_3", 62},
    {15, 4, "dynamo_level_4", 66},
    {16, 1, "nightmare_mother_level_1", 120},
    {16, 2, "nightmare_mother_level_2", 122},
    {16, 3, "nightmare_mother_level_3", 124},
    {16, 4, "nightmare_mother_level_4", 125},
    {17, 1, "high_max_secret_lab_level_1", 48},
    {17, 2, "high_max_secret_lab_level_2", 52},
    {17, 3, "high_max_secret_lab_level_3", 56},
    {17, 4, "high_max_secret_lab_level_4", 64},
    {18, 1, "gate_level_1", 52},
    {18, 2, "gate_level_2", 54},
    {18, 3, "gate_level_3", 56},
    {18, 4, "gate_level_4", 58},
    {19, 1, "sigma_level_1", 48},
    {19, 2, "sigma_level_2", 50},
    {19, 3, "sigma_level_3", 52},
    {19, 4, "sigma_level_4", 54},
    {20, 1, "sigma_second_form_level_1", 127},
}};

constexpr std::array<BossSite, 115> kBossSites = {{
    {1, 1, SiteKind::DirectByte, 0x19C90F68ull, "20"},
    {3, 1, SiteKind::DirectByte, 0x19CD17E0ull, "30"},
    {3, 1, SiteKind::DirectByte, 0x19CD19E8ull, "30"},
    {4, 1, SiteKind::DirectByte, 0x19D1734Cull, "40"},
    {9, 1, SiteKind::DirectByte, 0x19CE9374ull, "28"},
    {9, 1, SiteKind::DirectByte, 0x19DDE43Cull, "28"},
    {20, 1, SiteKind::DirectByte, 0x19D30030ull, "7F"},
    {2, 1, SiteKind::SnakeHealth, 0x19CBDE28ull, "7F00"},
    {2, 1, SiteKind::SnakeHealth, 0x19CBDE44ull, "7F00"},
    {2, 1, SiteKind::SnakeHealth, 0x19CBDEE0ull, "7F00"},
    {2, 1, SiteKind::SnakeHealth, 0x19CBE0B8ull, "7F00"},
    {2, 1, SiteKind::SnakeHealth, 0x19CBE160ull, "7F00"},
    {2, 1, SiteKind::SnakeHealth, 0x19CBBC3Cull, "7F00"},
    {2, 1, SiteKind::SnakeInverse, 0x19CBBC34ull, "80FF"},
    {2, 1, SiteKind::SnakeQuarter, 0x19CBB318ull, "2000"},
    {2, 1, SiteKind::SnakeQuarter, 0x19CBB32Cull, "2000"},
    {7, 1, SiteKind::DirectByte, 0x19CBFEE8ull, "30"},
    {7, 1, SiteKind::DirectByte, 0x19DD0E94ull, "30"},
    {7, 3, SiteKind::DirectByte, 0x19CBFF00ull, "34"},
    {7, 3, SiteKind::DirectByte, 0x19DD0EACull, "34"},
    {7, 4, SiteKind::DirectByte, 0x19CBFF10ull, "38"},
    {7, 4, SiteKind::DirectByte, 0x19DD0EBCull, "38"},
    {14, 1, SiteKind::DirectByte, 0x19DF7B9Cull, "30"},
    {14, 2, SiteKind::DirectByte, 0x19DF7BD0ull, "40"},
    {14, 3, SiteKind::DirectByte, 0x19DF7BDCull, "F6"},
    {14, 4, SiteKind::DirectByte, 0x19DF7BD8ull, "8C"},
    {17, 1, SiteKind::DirectByte, 0x19D79F1Cull, "30"},
    {17, 2, SiteKind::DirectByte, 0x19D79F50ull, "40"},
    {17, 3, SiteKind::DirectByte, 0x19D79F5Cull, "F6"},
    {17, 4, SiteKind::DirectByte, 0x19D79F58ull, "8C"},
    {5, 1, SiteKind::BaseByte, 0x19CA31BCull, "20"},
    {5, 1, SiteKind::BaseByte, 0x19DC3ADCull, "20"},
    {5, 1, SiteKind::DeltaByte, 0x19C9D0ACull, "00"},
    {5, 2, SiteKind::DeltaByte, 0x19C9D0ADull, "06"},
    {5, 3, SiteKind::DeltaByte, 0x19C9D0AEull, "0C"},
    {5, 4, SiteKind::DeltaByte, 0x19C9D0AFull, "10"},
    {5, 1, SiteKind::DeltaByte, 0x19DC3808ull, "00"},
    {5, 2, SiteKind::DeltaByte, 0x19DC3809ull, "06"},
    {5, 3, SiteKind::DeltaByte, 0x19DC380Aull, "0C"},
    {5, 4, SiteKind::DeltaByte, 0x19DC380Bull, "10"},
    {6, 1, SiteKind::BaseByte, 0x19CB4B6Cull, "30"},
    {6, 1, SiteKind::BaseByte, 0x19DCBF24ull, "30"},
    {6, 1, SiteKind::DeltaByte, 0x19CAC2CCull, "00"},
    {6, 2, SiteKind::DeltaByte, 0x19CAC2CDull, "02"},
    {6, 3, SiteKind::DeltaByte, 0x19CAC2CEull, "04"},
    {6, 4, SiteKind::DeltaByte, 0x19CAC2CFull, "06"},
    {6, 1, SiteKind::DeltaByte, 0x19DCB004ull, "00"},
    {6, 2, SiteKind::DeltaByte, 0x19DCB005ull, "02"},
    {6, 3, SiteKind::DeltaByte, 0x19DCB006ull, "04"},
    {6, 4, SiteKind::DeltaByte, 0x19DCB007ull, "06"},
    {8, 1, SiteKind::BaseByte, 0x19CDA5DCull, "30"},
    {8, 1, SiteKind::BaseByte, 0x19DD78ECull, "30"},
    {8, 1, SiteKind::DeltaByte, 0x19CCFA0Cull, "00"},
    {8, 2, SiteKind::DeltaByte, 0x19CCFA0Dull, "00"},
    {8, 3, SiteKind::DeltaByte, 0x19CCFA0Eull, "04"},
    {8, 4, SiteKind::DeltaByte, 0x19CCFA0Full, "08"},
    {8, 1, SiteKind::DeltaByte, 0x19DD5004ull, "00"},
    {8, 2, SiteKind::DeltaByte, 0x19DD5005ull, "00"},
    {8, 3, SiteKind::DeltaByte, 0x19DD5006ull, "04"},
    {8, 4, SiteKind::DeltaByte, 0x19DD5007ull, "08"},
    {10, 1, SiteKind::BaseByte, 0x19CF47ACull, "38"},
    {10, 1, SiteKind::BaseByte, 0x19DDFC48ull, "38"},
    {10, 1, SiteKind::DeltaByte, 0x19CED860ull, "00"},
    {10, 2, SiteKind::DeltaByte, 0x19CED861ull, "00"},
    {10, 3, SiteKind::DeltaByte, 0x19CED862ull, "04"},
    {10, 4, SiteKind::DeltaByte, 0x19CED863ull, "08"},
    {10, 1, SiteKind::DeltaByte, 0x19DDF804ull, "00"},
    {10, 2, SiteKind::DeltaByte, 0x19DDF805ull, "00"},
    {10, 3, SiteKind::DeltaByte, 0x19DDF806ull, "04"},
    {10, 4, SiteKind::DeltaByte, 0x19DDF807ull, "08"},
    {11, 1, SiteKind::BaseByte, 0x19D070C8ull, "20"},
    {11, 1, SiteKind::BaseByte, 0x19DE5CD0ull, "20"},
    {11, 1, SiteKind::DeltaByte, 0x19CFB5C8ull, "00"},
    {11, 2, SiteKind::DeltaByte, 0x19CFB5C9ull, "04"},
    {11, 3, SiteKind::DeltaByte, 0x19CFB5CAull, "08"},
    {11, 4, SiteKind::DeltaByte, 0x19CFB5CBull, "10"},
    {11, 1, SiteKind::DeltaByte, 0x19DE4824ull, "00"},
    {11, 2, SiteKind::DeltaByte, 0x19DE4825ull, "04"},
    {11, 3, SiteKind::DeltaByte, 0x19DE4826ull, "08"},
    {11, 4, SiteKind::DeltaByte, 0x19DE4827ull, "10"},
    {12, 1, SiteKind::BaseByte, 0x19D1B728ull, "30"},
    {12, 1, SiteKind::BaseByte, 0x19DEC4B4ull, "30"},
    {12, 1, SiteKind::DeltaByte, 0x19D0EB30ull, "00"},
    {12, 2, SiteKind::DeltaByte, 0x19D0EB31ull, "04"},
    {12, 3, SiteKind::DeltaByte, 0x19D0EB32ull, "06"},
    {12, 4, SiteKind::DeltaByte, 0x19D0EB33ull, "08"},
    {12, 1, SiteKind::DeltaByte, 0x19DEB95Cull, "00"},
    {12, 2, SiteKind::DeltaByte, 0x19DEB95Dull, "04"},
    {12, 3, SiteKind::DeltaByte, 0x19DEB95Eull, "06"},
    {12, 4, SiteKind::DeltaByte, 0x19DEB95Full, "08"},
    {13, 1, SiteKind::BaseByte, 0x19DF29D4ull, "30"},
    {13, 1, SiteKind::DeltaByte, 0x19DF2804ull, "00"},
    {13, 2, SiteKind::DeltaByte, 0x19DF2805ull, "02"},
    {13, 3, SiteKind::DeltaByte, 0x19DF2806ull, "04"},
    {13, 4, SiteKind::DeltaByte, 0x19DF2807ull, "08"},
    {18, 1, SiteKind::BaseByte, 0x19D88C30ull, "30"},
    {18, 1, SiteKind::DeltaByte, 0x19D83058ull, "04"},
    {18, 2, SiteKind::DeltaByte, 0x19D83059ull, "06"},
    {18, 3, SiteKind::DeltaByte, 0x19D8305Aull, "08"},
    {18, 4, SiteKind::DeltaByte, 0x19D8305Bull, "0A"},
    {19, 1, SiteKind::BaseByte, 0x19D2C948ull, "30"},
    {19, 1, SiteKind::DeltaByte, 0x19D29004ull, "00"},
    {19, 2, SiteKind::DeltaByte, 0x19D29005ull, "02"},
    {19, 3, SiteKind::DeltaByte, 0x19D29006ull, "04"},
    {19, 4, SiteKind::DeltaByte, 0x19D29007ull, "06"},
    {15, 1, SiteKind::BaseByte, 0x19DFF984ull, "3A"},
    {15, 1, SiteKind::DeltaHalfword, 0x19DFF804ull, "F8FF"},
    {15, 2, SiteKind::DeltaHalfword, 0x19DFF806ull, "0000"},
    {15, 3, SiteKind::DeltaHalfword, 0x19DFF808ull, "0400"},
    {15, 4, SiteKind::DeltaHalfword, 0x19DFF80Aull, "0800"},
    {16, 1, SiteKind::MotherBase, 0x19D6B260ull, "74"},
    {16, 1, SiteKind::MotherZero4, 0x19D6B284ull, "04004224"},
    {16, 2, SiteKind::DeltaByte, 0x19D6B29Cull, "06"},
    {16, 3, SiteKind::DeltaByte, 0x19D6B2B4ull, "08"},
    {16, 4, SiteKind::DeltaByte, 0x19D6B2C0ull, "09"},
}};

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

void add_dynamic_write(
    std::vector<ModResolution::Write>& writes, uint64_t location,
    std::string_view expected, std::vector<uint8_t> replacement,
    std::string_view feature_id
) {
    ModResolution::Write write;
    write.target = ModPatchTarget::DiscUser;
    write.location = location;
    write.expected = hex_bytes(expected);
    write.replacement = std::move(replacement);
    write.package_id = std::string(kPackageId);
    write.feature_id = std::string(feature_id);
    writes.push_back(std::move(write));
}

std::vector<uint8_t> byte_value(int64_t value) {
    return {static_cast<uint8_t>(value & 0xFF)};
}

std::vector<uint8_t> little_u16(int64_t value) {
    return {
        static_cast<uint8_t>(value & 0xFF),
        static_cast<uint8_t>((value >> 8) & 0xFF),
    };
}

bool known_boss_option(std::string_view id) {
    return std::any_of(
        kBossOptions.begin(), kBossOptions.end(),
        [&](const BossOption& option) { return option.id == id; });
}

bool read_boss_table(
    const ModPackage& package, const ModSelection& selection,
    std::array<std::array<int64_t, 5>, 21>& health,
    std::vector<std::string>& errors
) {
    for (const BossOption& spec : kBossOptions) {
        const ModOption* declared =
            option(package, "boss_health_by_level", spec.id);
        if (
            !declared || declared->default_value !=
                std::to_string(spec.default_value) ||
            declared->min_value != 32 || declared->max_value != 127 ||
            declared->step != 1
        ) {
            errors.push_back(package.id +
                ": trusted boss-health option inventory mismatch");
            return false;
        }
        int64_t value = spec.default_value;
        if (!integer(
                package, selection, "boss_health_by_level", spec.id, 32, 127,
                value, errors)) {
            return false;
        }
        health[spec.boss][spec.level] = value;
    }

    for (uint8_t boss = 1; boss < health.size(); ++boss) {
        if (!health[boss][2]) {
            if (
                health[boss][3] &&
                (health[boss][1] > health[boss][3] ||
                 health[boss][3] > health[boss][4])
            ) {
                errors.push_back(
                    package.id +
                    "/boss_health_by_level: boss health values must ascend");
                return false;
            }
            continue;
        }
        if (
            health[boss][1] > health[boss][2] ||
            health[boss][2] > health[boss][3] ||
            health[boss][3] > health[boss][4]
        ) {
            errors.push_back(
                package.id +
                "/boss_health_by_level: boss health values must ascend");
            return false;
        }
    }
    return true;
}

bool resolve_boss_health(
    const ModPackage& package, const ModSelection& selection,
    std::vector<ModResolution::Write>& writes,
    std::vector<std::string>& errors
) {
    if (!enabled(selection, "boss_health_by_level")) return true;
    std::array<std::array<int64_t, 5>, 21> health{};
    if (!read_boss_table(package, selection, health, errors)) return false;
    for (const BossSite& site : kBossSites) {
        std::vector<uint8_t> replacement;
        const int64_t level_value = health[site.boss][site.level];
        const int64_t base_value = health[site.boss][1];
        switch (site.kind) {
            case SiteKind::DirectByte:
            case SiteKind::BaseByte:
            case SiteKind::MotherBase:
                replacement = byte_value(level_value);
                break;
            case SiteKind::DeltaByte:
                replacement = byte_value(level_value - base_value);
                break;
            case SiteKind::DeltaHalfword:
                replacement = little_u16(level_value - base_value);
                break;
            case SiteKind::MotherZero4:
                replacement = {0, 0, 0, 0};
                break;
            case SiteKind::SnakeHealth:
                replacement = little_u16(base_value);
                break;
            case SiteKind::SnakeInverse:
                replacement = little_u16(0xFFFF - base_value);
                break;
            case SiteKind::SnakeQuarter:
                replacement = little_u16((base_value + 3) / 4);
                break;
        }
        add_dynamic_write(
            writes, site.location, site.expected, std::move(replacement),
            "boss_health_by_level");
    }
    return true;
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
        "boss_health_by_level",
    };
    if (
        features != expected_features ||
        package.options.size() != 1 + kBossOptions.size()
    ) {
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
    for (const BossOption& spec : kBossOptions) {
        const ModOption* boss =
            option(package, "boss_health_by_level", spec.id);
        if (
            !boss || boss->default_value !=
                std::to_string(spec.default_value) ||
            boss->min_value != 32 || boss->max_value != 127 ||
            boss->step != 1
        ) {
            errors.push_back(
                package.id + ": trusted boss-health option mismatch");
            return false;
        }
    }
    return true;
}

bool resolve_damage_rules(
    const ModPackage& package, const ModSelection& selection,
    const PSXRecompV4::ModBuiltinResolverContext& context,
    std::vector<ModResolution::Write>& writes,
    std::vector<std::string>& errors
) {
    (void)context;
    if (!validate(package, errors)) return false;
    for (const auto& [id, feature] : selection.features) {
        if (id != "gate_vulnerable_to_normal_attacks" &&
            id != "gate_orb_explosion_damage" &&
            id != "boss_health_by_level") {
            errors.push_back(package.id + ": unknown selected feature " + id);
            return false;
        }
        for (const auto& [key, ignored] : feature.values) {
            (void)ignored;
            const bool known_gate_damage =
                id == "gate_orb_explosion_damage" && key == "damage";
            const bool known_boss_health =
                id == "boss_health_by_level" && known_boss_option(key);
            if (!known_gate_damage && !known_boss_health) {
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
    if (!resolve_boss_health(package, selection, writes, errors)) {
        return false;
    }
    return true;
}

const bool kRegistered = mod_register_builtin_resolver(
    std::string(kResolverId), resolve_damage_rules);

} // namespace
