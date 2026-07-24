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
using PSXRecompV4::ModOption;
using PSXRecompV4::ModOptionType;
using PSXRecompV4::ModPackage;
using PSXRecompV4::ModPatchTarget;
using PSXRecompV4::ModResolution;
using PSXRecompV4::ModSelection;
using PSXRecompV4::mod_register_builtin_resolver;

constexpr std::string_view kPackageId = "mmx6.tweaks.general-foundations";
constexpr std::string_view kPackageVersion = "1.3.0";
constexpr std::string_view kResolverId = "mmx6-general-foundations";
constexpr std::string_view kGameId = "SLUS-01395";
constexpr std::string_view kStockDisc =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";
constexpr std::string_view kSharedOwner = "mission_report_rank_unlocks";
constexpr std::string_view kLowerDefenseOwner = "lower_defense";
constexpr std::string_view kCutsceneSoulsOwner = "cutscene_souls";
constexpr std::string_view kArmorByPartOwner = "incomplete_armors_by_part";

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

const ModOption* option(
    const ModPackage& package, std::string_view feature_id,
    std::string_view option_id
) {
    for (const ModOption& option : package.options) {
        if (option.feature_id == feature_id && option.id == option_id)
            return &option;
    }
    return nullptr;
}

bool integer_option(
    const ModPackage& package, const ModSelection& selection,
    std::string_view feature_id, std::string_view option_id, int minimum,
    int maximum, int& value, std::vector<std::string>& errors
) {
    const ModFeatureSelection* feature = selected(selection, feature_id);
    const ModOption* trusted_option = option(package, feature_id, option_id);
    if (!feature || !trusted_option) {
        errors.push_back(
            package.id + "/" + std::string(feature_id) +
            ": missing trusted integer option"
        );
        return false;
    }
    const auto selected_value = feature->values.find(std::string(option_id));
    const std::string& text = selected_value == feature->values.end()
        ? trusted_option->default_value
        : selected_value->second;
    int parsed = 0;
    const auto parsed_result = std::from_chars(
        text.data(), text.data() + text.size(), parsed);
    if (
        parsed_result.ec != std::errc() ||
        parsed_result.ptr != text.data() + text.size() ||
        parsed < minimum || parsed > maximum
    ) {
        errors.push_back(
            package.id + "/" + std::string(feature_id) +
            ": integer option is outside the trusted domain"
        );
        return false;
    }
    value = parsed;
    return true;
}

bool choice_option(
    const ModPackage& package, const ModSelection& selection,
    std::string_view feature_id, std::string_view option_id,
    std::string& value, std::vector<std::string>& errors
) {
    const ModFeatureSelection* feature = selected(selection, feature_id);
    const ModOption* trusted_option = option(package, feature_id, option_id);
    if (!feature || !trusted_option || trusted_option->type != ModOptionType::Choice) {
        errors.push_back(
            package.id + "/" + std::string(feature_id) +
            ": missing trusted choice option"
        );
        return false;
    }
    const auto selected_value = feature->values.find(std::string(option_id));
    value = selected_value == feature->values.end()
        ? trusted_option->default_value
        : selected_value->second;
    const auto found = std::find_if(
        trusted_option->choices.begin(), trusted_option->choices.end(),
        [&](const PSXRecompV4::ModChoice& choice) {
            return choice.value == value;
        });
    if (found == trusted_option->choices.end()) {
        errors.push_back(
            package.id + "/" + std::string(feature_id) +
            ": choice option is outside the trusted domain"
        );
        return false;
    }
    return true;
}

bool boolean_option(
    const ModPackage& package, const ModSelection& selection,
    std::string_view feature_id, std::string_view option_id,
    bool& value, std::vector<std::string>& errors
) {
    const ModFeatureSelection* feature = selected(selection, feature_id);
    const ModOption* trusted_option = option(package, feature_id, option_id);
    if (!feature || !trusted_option || trusted_option->type != ModOptionType::Boolean) {
        errors.push_back(
            package.id + "/" + std::string(feature_id) +
            ": missing trusted boolean option"
        );
        return false;
    }
    const auto selected_value = feature->values.find(std::string(option_id));
    const std::string& text = selected_value == feature->values.end()
        ? trusted_option->default_value
        : selected_value->second;
    if (text == "true") {
        value = true;
        return true;
    }
    if (text == "false") {
        value = false;
        return true;
    }
    errors.push_back(
        package.id + "/" + std::string(feature_id) +
        ": boolean option is outside the trusted domain"
    );
    return false;
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

std::vector<uint8_t> halfword_le(int value) {
    return {
        static_cast<uint8_t>(value & 0xFF),
        static_cast<uint8_t>((value >> 8) & 0xFF),
    };
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

#include "mmx6_general_foundations_armor.inc"

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
        "incomplete_armors_by_part",
        "gate_revealed_souls",
        "gate_revealed_refight_souls",
    };
    if (features != expected_features) {
        errors.push_back(package.id + ": trusted feature inventory mismatch");
        return false;
    }
    const ModOption* gate_souls = option(
        package, "gate_revealed_souls", "souls");
    const ModOption* refight_souls = option(
        package, "gate_revealed_refight_souls", "souls");
    const ModOption* armor_appearance = option(
        package, "incomplete_armors_by_part", "appearance");
    const ModOption* shadow_saber_palette = option(
        package, "incomplete_armors_by_part", "shadow_saber_palette");
    if (
        package.options.size() != 4 || !gate_souls || !refight_souls ||
        !armor_appearance || !shadow_saber_palette ||
        gate_souls->type != ModOptionType::Integer ||
        refight_souls->type != ModOptionType::Integer ||
        armor_appearance->type != ModOptionType::Choice ||
        shadow_saber_palette->type != ModOptionType::Boolean ||
        gate_souls->default_value != "256" ||
        refight_souls->default_value != "256" ||
        gate_souls->min_value != 256 || refight_souls->min_value != 256 ||
        gate_souls->max_value != 9999 || refight_souls->max_value != 9999 ||
        armor_appearance->default_value != "complete_armor" ||
        shadow_saber_palette->default_value != "false" ||
        armor_appearance->choices.size() != 2 ||
        armor_appearance->choices[0].value != "complete_armor" ||
        armor_appearance->choices[0].label != "Complete Armor" ||
        armor_appearance->choices[1].value != "unarmored_x" ||
        armor_appearance->choices[1].label != "Unarmored X"
    ) {
        errors.push_back(package.id + ": trusted option inventory mismatch");
        return false;
    }
    return true;
}

bool resolve_general_foundations(
    const ModPackage& package, const ModSelection& selection,
    const PSXRecompV4::ModBuiltinResolverContext& context,
    std::vector<ModResolution::Write>& writes,
    std::vector<std::string>& errors
) {
    if (!validate(package, errors)) return false;
    for (const auto& [id, feature] : selection.features) {
        if (
            id != "ultimate_armor_rank_unlock" &&
            id != "black_zero_rank_unlock" &&
            id != "normalize_unarmored_x_defense" &&
            id != "normalize_zero_defense" &&
            id != "incomplete_armors_by_part" &&
            id != "gate_revealed_souls" &&
            id != "gate_revealed_refight_souls"
        ) {
            errors.push_back(package.id + ": unknown selected feature " + id);
            return false;
        }
        const bool soul_feature =
            id == "gate_revealed_souls" ||
            id == "gate_revealed_refight_souls";
        const bool armor_feature = id == "incomplete_armors_by_part";
        if (
            !soul_feature && !armor_feature && !feature.values.empty()
        ) {
            errors.push_back(package.id + ": selected feature has no options");
            return false;
        }
        if (soul_feature) {
            for (const auto& [option_id, _value] : feature.values) {
                if (option_id != "souls") {
                    errors.push_back(
                        package.id + ": selected soul feature has unknown option"
                    );
                    return false;
                }
            }
        }
        if (armor_feature) {
            for (const auto& [option_id, _value] : feature.values) {
                if (
                    option_id != "appearance" &&
                    option_id != "shadow_saber_palette"
                ) {
                    errors.push_back(
                        package.id + ": selected armor feature has unknown option"
                    );
                    return false;
                }
            }
        }
    }

    const bool ultimate = enabled(selection, "ultimate_armor_rank_unlock");
    const bool black = enabled(selection, "black_zero_rank_unlock");
    const bool normalize_x =
        enabled(selection, "normalize_unarmored_x_defense");
    const bool normalize_zero = enabled(selection, "normalize_zero_defense");
    const bool armor_by_part =
        enabled(selection, "incomplete_armors_by_part");
    const bool gate_souls_enabled =
        enabled(selection, "gate_revealed_souls");
    const bool refight_souls_enabled =
        enabled(selection, "gate_revealed_refight_souls");
    if (
        !ultimate && !black && !normalize_x && !normalize_zero &&
        !armor_by_part && !gate_souls_enabled && !refight_souls_enabled
    )
        return true;

    if (ultimate || black || armor_by_part) {
        add_write(
        writes, ModPatchTarget::DiscUser, 0x19D4FB8C,
        "1000B0AF0F80103C1400B1AF0F80113CF948239244381026",
        "1400B1AF0F80113C1000B0AFD4E90108F948239244383026");
    add_write(
        writes, ModPatchTarget::DiscUser, 0x19D4FC58,
        "0D80043C6F000324",
        "E2E901080D80043C");
    if (!armor_by_part) {
        add_write(
            writes, ModPatchTarget::DiscUser, 0x19D50E08,
            "0D80023CD0CE45246900A3900F0004240F0063300B00641421304000C800A290000000000F00423006004310010002245F00A39000000000040063340800E0035F00A3A0D0CEC5246900A290F0000324F00044300B00831400000000C800A29000000000F000423006004410020002245F00A39000000000020063340800E0035F00A3A00800E00321100000",
            "9CE9010800000000690083900F0005340F0063300B00651400004634C8008290000000000F00423006004310010002345F00839000000000040063340800E0035F0083A0D0CEC52469008290F0000334F00045300B00A31400000000C800829000000000F000423006004510020002345F00839000000000020063340800E0035F0083A0B9E9010800000000");
    }
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
    if (armor_by_part) {
        std::string armor_appearance;
        bool shadow_saber_palette = false;
        if (
            !choice_option(
                package, selection, "incomplete_armors_by_part",
                "appearance", armor_appearance, errors
            ) ||
            !boolean_option(
                package, selection, "incomplete_armors_by_part",
                "shadow_saber_palette", shadow_saber_palette, errors
            )
        )
            return false;
        emit_ShadowBase01(writes);
        emit_ArmorByPart01(writes);
        if (armor_appearance == "unarmored_x")
            emit_ArmorByPart03(writes);
        if (shadow_saber_palette)
            emit_ArmorByPart04(writes);
        if (
            active_feature_enabled(
                context, "mmx6.tweaks.player-standalone",
                "unlock_x_air_dash"
            )
        ) {
            emit_DashGlobal01_ArmorByPart(writes);
        }
    }
    if (normalize_x || normalize_zero) {
        if (armor_by_part) {
            if (normalize_x && normalize_zero)
                emit_LowerDef_All_B(writes);
            else if (normalize_x)
                emit_LowerDef_X_B(writes);
            else
                emit_LowerDef_Zero_B(writes);
        } else {
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
    }
    int gate_souls = 3000;
    int refight_souls = 3000;
    if (
        gate_souls_enabled &&
        !integer_option(
            package, selection, "gate_revealed_souls", "souls",
            256, 9999, gate_souls, errors
        )
    )
        return false;
    if (
        refight_souls_enabled &&
        !integer_option(
            package, selection, "gate_revealed_refight_souls", "souls",
            256, 9999, refight_souls, errors
        )
    )
        return false;
    const bool gate_souls_active =
        gate_souls_enabled && gate_souls != 3000;
    const bool refight_souls_active =
        refight_souls_enabled && refight_souls != 3000;
    if (gate_souls_active || refight_souls_active) {
        add_write(
            writes, ModPatchTarget::MainExe, 0x8001E41C,
            "66008290000000000300422C",
            "5A0182900000000001004228",
            kCutsceneSoulsOwner);
        add_write(
            writes, ModPatchTarget::MainExe, 0x8001E45C,
            "1D790008", "B0DA0108", kCutsceneSoulsOwner);
        add_write(
            writes, ModPatchTarget::MainExe, 0x80076AC0,
            "000000000000000000000000",
            "FCFF63241D7900085A0183A0",
            kCutsceneSoulsOwner);
        add_write(
            writes, ModPatchTarget::MainExe, 0x8001F168,
            "6600A290000000000300422C",
            "5A01A2900000000001004228",
            kCutsceneSoulsOwner);
        add_write(
            writes, ModPatchTarget::MainExe, 0x8001F1B4,
            "0800E003", "707C0008", kCutsceneSoulsOwner);
        add_write(
            writes, ModPatchTarget::MainExe, 0x80076ACC,
            "000000000000000000000000",
            "FCFF63240800E0035A01A3A0",
            kCutsceneSoulsOwner);
        add_write(
            writes, ModPatchTarget::MainExe, 0x800347A4,
            "660023920B000224D0CE62A2010020A20300632C10006010020020A238002282000000004010020021102202D200438400000000B80B6328070060141300022405000324D0CE62A21D0023A2010020A2020020A2030020A2",
            "5A0123920B000224D0CE62A2010020A20100053410006014020020A238002282000000004010020021102202D200438400000000B80B6328070060141300022405000324D0CE62A21D0023A2010020A2020020A65A0125A2",
            kCutsceneSoulsOwner);
        add_write(
            writes, ModPatchTarget::DiscUser, 0x19E06D78,
            "66000292010000A2020000A20300422C",
            "5A010292010000A2020000A20100422C",
            kCutsceneSoulsOwner);
        add_write(
            writes, ModPatchTarget::DiscUser, 0x19E06DC0,
            "79E90308", "B6DA0108", kCutsceneSoulsOwner);
        add_write(
            writes, ModPatchTarget::MainExe, 0x80076AD8,
            "000000000000000000000000",
            "FCFF632479E903085A01A3A0",
            kCutsceneSoulsOwner);
        if (gate_souls_active) {
            const std::vector<uint8_t> replacement =
                halfword_le(gate_souls);
            add_write(
                writes, ModPatchTarget::MainExe, 0x8001E448,
                "B80B", replacement, kCutsceneSoulsOwner);
            add_write(
                writes, ModPatchTarget::MainExe, 0x8001F194,
                "B80B", replacement, kCutsceneSoulsOwner);
            add_write(
                writes, ModPatchTarget::MainExe, 0x800347D8,
                "B80B", replacement, kCutsceneSoulsOwner);
            add_write(
                writes, ModPatchTarget::DiscUser, 0x19E06D98,
                "B80B", replacement, kCutsceneSoulsOwner);
            add_write(
                writes, ModPatchTarget::DiscUser, 0x19E06DAC,
                "B80B", replacement, kCutsceneSoulsOwner);
        }
        if (refight_souls_active) {
            const std::vector<uint8_t> replacement =
                halfword_le(refight_souls);
            add_write(
                writes, ModPatchTarget::DiscUser, 0x19D4EF28,
                "B80B", replacement, kCutsceneSoulsOwner);
            add_write(
                writes, ModPatchTarget::DiscUser, 0x19D4EF3C,
                "B80B", replacement, kCutsceneSoulsOwner);
        }
    }
    return true;
}

const bool kRegistered = mod_register_builtin_resolver(
    std::string(kResolverId), resolve_general_foundations);

} // namespace
