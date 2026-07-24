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

constexpr std::string_view kPackageId = "mmx6.tweaks.zero-techniques";
constexpr std::string_view kPackageVersion = "1.0.0";
constexpr std::string_view kResolverId = "mmx6-zero-techniques";
constexpr std::string_view kGameId = "SLUS-01395";
constexpr std::string_view kStockDisc =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";
constexpr std::string_view kZeroOwner = "zero_techniques";

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

void patch_hex(std::vector<uint8_t>& bytes, size_t offset, std::string_view text) {
    const std::vector<uint8_t> replacement = hex_bytes(text);
    if (offset + replacement.size() <= bytes.size())
        std::copy(replacement.begin(), replacement.end(), bytes.begin() + offset);
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
    uint64_t location, std::string_view expected,
    std::string_view replacement, std::string_view feature_id
) {
    add_write(writes, target, location, expected, hex_bytes(replacement), feature_id);
}

#include "mmx6_zero_techniques_generated.inc"

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

bool choice_option(
    const ModPackage& package, const ModSelection& selection,
    std::string_view option_id, std::string& value,
    std::vector<std::string>& errors
) {
    const ModFeatureSelection* feature = selected(selection, kZeroOwner);
    const ModOption* trusted_option = option(package, kZeroOwner, option_id);
    if (!feature || !trusted_option || trusted_option->type != ModOptionType::Choice) {
        errors.push_back(package.id + ": missing trusted choice option");
        return false;
    }
    const auto selected_value = feature->values.find(std::string(option_id));
    value = selected_value == feature->values.end()
        ? trusted_option->default_value
        : selected_value->second;
    const auto found = std::find_if(
        trusted_option->choices.begin(), trusted_option->choices.end(),
        [&](const PSXRecompV4::ModChoice& choice) { return choice.value == value; });
    if (found == trusted_option->choices.end()) {
        errors.push_back(package.id + ": choice option is outside the trusted domain");
        return false;
    }
    return true;
}

bool boolean_option(
    const ModPackage& package, const ModSelection& selection,
    std::string_view option_id, bool& value,
    std::vector<std::string>& errors
) {
    const ModFeatureSelection* feature = selected(selection, kZeroOwner);
    const ModOption* trusted_option = option(package, kZeroOwner, option_id);
    if (!feature || !trusted_option || trusted_option->type != ModOptionType::Boolean) {
        errors.push_back(package.id + ": missing trusted boolean option");
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
    errors.push_back(package.id + ": boolean option is outside the trusted domain");
    return false;
}

bool integer_option(
    const ModPackage& package, const ModSelection& selection,
    std::string_view option_id, int& value,
    std::vector<std::string>& errors
) {
    const ModFeatureSelection* feature = selected(selection, kZeroOwner);
    const ModOption* trusted_option = option(package, kZeroOwner, option_id);
    if (!feature || !trusted_option || trusted_option->type != ModOptionType::Integer) {
        errors.push_back(package.id + ": missing trusted integer option");
        return false;
    }
    const auto selected_value = feature->values.find(std::string(option_id));
    const std::string& text = selected_value == feature->values.end()
        ? trusted_option->default_value
        : selected_value->second;
    int parsed = 0;
    const auto result = std::from_chars(text.data(), text.data() + text.size(), parsed);
    if (
        result.ec != std::errc() || result.ptr != text.data() + text.size() ||
        parsed < trusted_option->min_value || parsed > trusted_option->max_value
    ) {
        errors.push_back(package.id + ": integer option is outside the trusted domain");
        return false;
    }
    value = parsed;
    return true;
}

struct ZeroState {
    int sentsuizan_input = 1;
    int sentsuizan_mode = 1;
    int ensuizan_input = 1;
    bool ensuizan_air_mode = false;
    int ensuizan_reps = 3;
    int guard_shell = 1;
    bool yammar_like_x = false;
};

void force_sentsuizan_input(ZeroState& state, int value) {
    state.sentsuizan_input = value;
}

void force_ensuizan_input(ZeroState& state, int value) {
    state.ensuizan_input = value;
}

void force_guard_shell(ZeroState& state, int value) {
    state.guard_shell = value;
}

void zero_guard_shell(ZeroState& state) {
    if (state.guard_shell == 0)
        force_guard_shell(state, 1);
    if (!state.ensuizan_air_mode && state.ensuizan_input == 1) {
        if (state.guard_shell == 4)
            force_guard_shell(state, 1);
    }
}

ZeroState normalized(ZeroState state) {
    if (!state.ensuizan_air_mode) {
        if (state.sentsuizan_input == 2)
            force_ensuizan_input(state, 2);
        else
            force_ensuizan_input(state, 1);
        state.ensuizan_reps = 3;
    }
    zero_guard_shell(state);
    if (state.sentsuizan_input == 1) {
        if (state.ensuizan_input == 3)
            force_ensuizan_input(state, 1);
    } else if (state.sentsuizan_input == 2) {
        if (state.ensuizan_input == 1)
            force_ensuizan_input(state, 2);
    } else if (state.sentsuizan_input == 3) {
        if (state.ensuizan_input == 2)
            force_ensuizan_input(state, 1);
    }
    if (state.ensuizan_input == 1) {
        if (state.sentsuizan_input == 2)
            force_sentsuizan_input(state, 1);
    } else if (state.ensuizan_input == 2) {
        if (state.sentsuizan_input == 3)
            force_sentsuizan_input(state, 1);
        state.yammar_like_x = true;
    } else if (state.ensuizan_input == 3) {
        if (state.sentsuizan_input == 1)
            force_sentsuizan_input(state, 2);
    }
    if (state.ensuizan_input == 2 || state.sentsuizan_input == 3)
        state.yammar_like_x = true;
    zero_guard_shell(state);
    return state;
}

bool same_state(const ZeroState& left, const ZeroState& right) {
    return left.sentsuizan_input == right.sentsuizan_input &&
        left.sentsuizan_mode == right.sentsuizan_mode &&
        left.ensuizan_input == right.ensuizan_input &&
        left.ensuizan_air_mode == right.ensuizan_air_mode &&
        left.ensuizan_reps == right.ensuizan_reps &&
        left.guard_shell == right.guard_shell &&
        left.yammar_like_x == right.yammar_like_x;
}

std::string state_text(const ZeroState& state) {
    return "sentsuizan_input=" + std::to_string(state.sentsuizan_input) +
        ", sentsuizan_mode=" + std::to_string(state.sentsuizan_mode) +
        ", ensuizan_input=" + std::to_string(state.ensuizan_input) +
        ", ensuizan_air_mode=" + (state.ensuizan_air_mode ? "true" : "false") +
        ", ensuizan_reps=" + std::to_string(state.ensuizan_reps) +
        ", guard_shell=" + std::to_string(state.guard_shell) +
        ", yammar_like_x=" + (state.yammar_like_x ? "true" : "false");
}

void emit_sentsuizan_mode03(
    std::vector<ModResolution::Write>& writes, int sentsuizan_input
) {
    std::vector<uint8_t> first = hex_bytes(
        "890002920000000006004014000000007C00029200000000200042302E00401400000000D30003820000000002006014000000007A0000A28900029200000000080042301E0040100D80023CDCCE4494");
    const char* and2 = sentsuizan_input == 2 ? "28" :
        sentsuizan_input == 3 ? "24" : "14";
    patch_hex(first, 0x18, and2);
    add_write(
        writes, ModPatchTarget::DiscUser, 0x19C877B0,
        "1500029200000000020040100A000324090003248900029200000000241043002D004010010004241A000524125B000C21300002D30003820000000002006014000000007A0000A28900029200000000",
        std::move(first), kZeroOwner);
    add_write(
        writes, ModPatchTarget::DiscUser, 0x19C87800,
        "080042301A0040100D80023CDCCE449404010324060083141E000424020005241EA5000C0100062410B4070821200002",
        "040103340600831401000434020005341EA5000C0100063410B40708212000021A000534125B000C000006361E000434",
        kZeroOwner);
}

void emit_ensuizan_mode01(
    std::vector<ModResolution::Write>& writes, const ZeroState& state
) {
    std::vector<uint8_t> block = hex_bytes(
        "8600228208001234C9002392370052108900269220006330340060100800C62C1400C010D00122927C002696020040140800C330800026962C0060142000C6302A00C010010042240300462C0300C0140000000000000234860032A201001034D00122A2DD0030A28E0030A27DA90708CB0020A299A90708D00120A20300501400002436F8F3000C050005340100043418000534125B000C0000263600000000000024368C0020A281EE000C6700053464B3070C2A00053400002436610020A23BF1000CA40020A2000024363A0002347A0030A2050022A2060020A241B1070C00000000");
    const bool add_req = state.ensuizan_input != 4;
    const char* dir = state.ensuizan_input == 1 ? "08" : "04";
    const char* button = state.ensuizan_input == 3 ? "10" :
        state.ensuizan_input == 4 ? "" : "20";
    patch_hex(block, 0x30, dir);
    patch_hex(block, 0x38, add_req ? "2C006010" : "2C006014");
    if (button[0] != '\0')
        patch_hex(block, 0x3C, button);
    patch_hex(
        block, 0x48,
        std::string(1, "0123456789ABCDEF"[(state.ensuizan_reps >> 4) & 0xF]) +
        std::string(1, "0123456789ABCDEF"[state.ensuizan_reps & 0xF]) + "00");
    add_write(
        writes, ModPatchTarget::DiscUser, 0x19C84D78,
        "D300228200000000390040142110000086002282080012243500521021100000C9002292000000002000423030004010211000007C00229600000000080042302B0040102110000080002296000000002000423026004010211000008E00228200000000210040142120200201001024DD0030A28E0030A2CB0020A267F3000C8C0020A22120200281EE000C670005242120200264B3070C2A00052421202002F8F3000C050005240100042418000524125B000C2130200221202002610020A23BF1000CA40020A2212020023A0002247A0030A2050022A2060020A241B1070C860032A2",
        std::move(block), kZeroOwner);
    add_write(writes, ModPatchTarget::MainExe, 0x8003B3C0, "21808000", "D00100A2", kZeroOwner);
    add_write(writes, ModPatchTarget::MainExe, 0x8003CDB8, "00000000", "D00180A0", kZeroOwner);
}

std::string input_hint_sequence(std::initializer_list<std::string_view> parts) {
    std::string out;
    for (std::string_view part : parts)
        out += part;
    return out;
}

void emit_retranslation_hints(
    std::vector<ModResolution::Write>& writes, const ZeroState& state
) {
    constexpr std::string_view up = "00F9F0F2";
    constexpr std::string_view down = "00F8F0F2";
    constexpr std::string_view air = "00E8E9F3";
    constexpr std::string_view plus = "00FAFBF2";
    constexpr std::string_view attack = "00FB05F2";
    constexpr std::string_view special = "00FD05F2";
    constexpr std::string_view giga = "00FC05F2";
    if (state.sentsuizan_input != 1) {
        const std::string replacement = state.sentsuizan_input == 2
            ? input_hint_sequence({down, plus, special})
            : input_hint_sequence({up, plus, special});
        add_write(
            writes, ModPatchTarget::DiscUser, 0x1A21FC58,
            "00F9F0F200FAFBF200FB05F2", replacement, kZeroOwner);
    }
    if (state.ensuizan_air_mode || state.ensuizan_input != 1) {
        const std::string replacement = state.ensuizan_input == 1
            ? input_hint_sequence({down, plus, special})
            : state.ensuizan_input == 2
                ? input_hint_sequence({up, plus, special})
                : state.ensuizan_input == 3
                    ? input_hint_sequence({up, plus, attack})
                    : input_hint_sequence({air, plus, special});
        add_write(
            writes, ModPatchTarget::DiscUser, 0x1A21FCA0,
            "00F8F0F200FAFBF200FD05F2", replacement, kZeroOwner);
    }
    if (state.guard_shell == 4 || state.guard_shell == 5) {
        const std::string replacement = state.guard_shell == 4
            ? input_hint_sequence({down, plus, special})
            : input_hint_sequence({up, plus, giga});
        add_write(
            writes, ModPatchTarget::DiscUser, 0x1A21FA7C,
            "000F0000000F0000000F0000", replacement, kZeroOwner);
    }
    if (state.yammar_like_x) {
        add_write(
            writes, ModPatchTarget::DiscUser, 0x1A21F794,
            "000380F5003486F500208CF5002692F5003198F500309EF50025A4F5002CA9F50028ACF50024AFF50035B5F50025BEF5002CC3F5002080010034860100318C01003792010030980100239E01003CA7010031AD010037B301002FB90100F9F0F200FAFBF200FD05F2",
            "000380F5003486F500208CF5002692F5003198F500309EF50025A4F5002CA9F50028ACF50024AFF50035B5F50025BEF5002CC3F5003CC6F50020CFF50034D5F50031DBF50037E1F50030E7F50023EDF5003CF6F50031FCF5003702F5002F08F5000F80F5000F80F5000F80F5",
            kZeroOwner);
    }
}

bool validate(const ModPackage& package, std::vector<std::string>& errors) {
    if (
        package.id != kPackageId || package.version != kPackageVersion ||
        package.resolver != "builtin:" + std::string(kResolverId) ||
        package.targets.size() != 1 || package.targets[0].game_id != kGameId ||
        package.targets[0].disc_sha256 != kStockDisc ||
        !package.targets[0].exe_sha256.empty() || !package.patches.empty() ||
        !package.overlays.empty() || !package.derived_discs.empty() ||
        !package.dependencies.empty() || !package.conflicts.empty() ||
        !package.constraints.empty()
    ) {
        errors.push_back(package.id + ": trusted manifest contract mismatch");
        return false;
    }
    if (package.features.size() != 1 || package.features[0].id != kZeroOwner ||
        package.features[0].default_enabled || package.features[0].legacy ||
        package.options.size() != 7) {
        errors.push_back(package.id + ": trusted feature inventory mismatch");
        return false;
    }
    return true;
}

bool read_state(
    const ModPackage& package, const ModSelection& selection,
    ZeroState& state, std::vector<std::string>& errors
) {
    std::string value;
    if (!choice_option(package, selection, "sentsuizan_input", value, errors))
        return false;
    state.sentsuizan_input = value == "down_special" ? 2 :
        value == "up_special" ? 3 : 1;
    if (!choice_option(package, selection, "sentsuizan_mode", value, errors))
        return false;
    state.sentsuizan_mode = value == "press_back" ? 2 :
        value == "hold_release" ? 3 : 1;
    if (!choice_option(package, selection, "ensuizan_input", value, errors))
        return false;
    state.ensuizan_input = value == "up_special" ? 2 :
        value == "up_attack" ? 3 : value == "air_special" ? 4 : 1;
    if (!boolean_option(package, selection, "ensuizan_air_mode", state.ensuizan_air_mode, errors))
        return false;
    if (!integer_option(package, selection, "ensuizan_reps", state.ensuizan_reps, errors))
        return false;
    if (!choice_option(package, selection, "guard_shell_activation", value, errors))
        return false;
    state.guard_shell = value == "like_x" ? 2 :
        value == "down_special" ? 4 : value == "up_giga" ? 5 : 1;
    if (!boolean_option(package, selection, "yammar_like_x", state.yammar_like_x, errors))
        return false;
    return true;
}

bool resolve_zero_techniques(
    const ModPackage& package, const ModSelection& selection,
    const PSXRecompV4::ModBuiltinResolverContext& context,
    std::vector<ModResolution::Write>& writes,
    std::vector<std::string>& errors
) {
    if (!validate(package, errors)) return false;
    for (const auto& [id, feature] : selection.features) {
        if (id != kZeroOwner) {
            errors.push_back(package.id + ": unknown selected feature " + id);
            return false;
        }
        for (const auto& [option_id, _value] : feature.values) {
            if (
                option_id != "sentsuizan_input" &&
                option_id != "sentsuizan_mode" &&
                option_id != "ensuizan_input" &&
                option_id != "ensuizan_air_mode" &&
                option_id != "ensuizan_reps" &&
                option_id != "guard_shell_activation" &&
                option_id != "yammar_like_x"
            ) {
                errors.push_back(package.id + ": unknown selected option " + option_id);
                return false;
            }
        }
    }
    if (!enabled(selection, kZeroOwner))
        return true;

    ZeroState state;
    if (!read_state(package, selection, state, errors))
        return false;
    const ZeroState normalized_state = normalized(state);
    if (!same_state(state, normalized_state)) {
        errors.push_back(
            package.id + ": Zero Techniques option combination would be "
            "silently rewritten by MMX6 Tweaks; requested {" +
            state_text(state) + "} normalized to {" +
            state_text(normalized_state) + "}");
        return false;
    }

    if (state.sentsuizan_input == 2)
        emit_ZeroSentsuizanInput02(writes);
    else if (state.sentsuizan_input == 3)
        emit_ZeroSentsuizanInput03(writes);
    if (state.sentsuizan_mode == 2) {
        emit_PressBack01(writes);
        emit_ZeroSentsuizanMode02(writes);
    } else if (state.sentsuizan_mode == 3) {
        emit_sentsuizan_mode03(writes, state.sentsuizan_input);
    }
    if (state.ensuizan_air_mode) {
        emit_ensuizan_mode01(writes, state);
    } else if (state.ensuizan_input == 2) {
        emit_ZeroEnsuizanInput02(writes);
    }
    if (state.guard_shell != 1) {
        emit_ZeroAutoselect_Common(writes);
        if (state.guard_shell == 2) {
            emit_ZeroGuardShellInput03(writes);
            emit_ZeroGuardShellInput02(writes);
        } else if (state.guard_shell == 4) {
            emit_ZeroGuardShellInput04(writes);
        } else if (state.guard_shell == 5) {
            emit_ZeroGuardShellInput05(writes);
        }
    }
    if (state.yammar_like_x)
        emit_ZeroYammarInput01(writes);
    if (
        active_feature_enabled(
            context, "mmx6.tweaks.native", "retranslation")
    ) {
        emit_retranslation_hints(writes, state);
    }
    return true;
}

const bool kRegistered = mod_register_builtin_resolver(
    std::string(kResolverId), resolve_zero_techniques);

} // namespace
