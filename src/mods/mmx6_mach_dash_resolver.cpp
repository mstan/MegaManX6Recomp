#include "mod_packages.h"

#include <algorithm>
#include <array>
#include <charconv>
#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace {

using namespace PSXRecompV4;

constexpr std::string_view kPackageId = "mmx6.tweaks.mach-dash";
constexpr std::string_view kVersion = "1.1.0";
constexpr std::string_view kResolverId = "mmx6-mach-dash";
constexpr std::string_view kFeatureId = "blade_mach_dash_behavior";
constexpr std::string_view kGameId = "SLUS-01395";
constexpr std::string_view kStockDisc =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";

struct Operation {
    ModPatchTarget target;
    uint64_t location;
    std::string_view expected;
    std::string_view replacement;
};

constexpr Operation kMachBase[] = {
    {ModPatchTarget::DiscUser, 0x19C7A6DC,
     "7C00029600000000020042300200401000000000150000A27C00029600000000010042300200401040000224150002A2",
     "7C0002960800053C0040A53402005B3002006013D80105AE150000A20000000001005B300200601340000234150002A2"},
    {ModPatchTarget::MainExe, 0x8007A800,
     "000000000000000000000000000000000000000000000000",
     "06001C3C00309C3714000534D8011CAED4AB0708850005A2"},
    {ModPatchTarget::DiscUser, 0x19C7A778,
     "0801028EE9AB0708200000AE08006230090040100000000081EE000CBF0005240801028E200000AE2310020040100200FCAB0708240002AE2120000281EE000CC0000524150002920000000004004010000000000801028EFAAB0708401002000801028E000000002310020040100200200002AE240000AE",
     "D801028EE9AB0708200000AE08006230090040100000000081EE000CBF000524D801028E200000AE23100200F9AB0708240002AE0000043681EE000CC000053415000292000000000300401000000000D801028EF7AB0708D801028E0000000023100200200002AE240000AE000000000000000000000000"},
};

constexpr Operation kInputDisabled[] = {
    {ModPatchTarget::MainExe, 0x8003F33C, "80000296", "00000234"},
};
constexpr Operation kInputHybrid[] = {
    {ModPatchTarget::DiscUser, 0x19C7A6DC,
     "7C00029600000000020042300200401000000000150000A27C00029600000000010042300200401040000224150002A2460002820000000041004014000000007C0002960000000080014230",
     "7C0002960800053C0040A53402005C300200801301005C30150000A2020080133F009C2715001CA200015B3004006013D80105AE20EA01080100043400EA010880007B27D4011BA280004230"},
    {ModPatchTarget::MainExe, 0x8007A880,
     "000000000000000000000000000000000000000000000000000000000000000000000000",
     "D4011C920000000080009C330300801300000000C9AB07080000000000EA010800000000"},
};
constexpr Operation kWaitUnlimited[] = {
    {ModPatchTarget::DiscUser, 0x19C7A738, "01004224", "00000000"},
};
constexpr Operation kWaitMinimum[] = {
    {ModPatchTarget::DiscUser, 0x19C7A728, "09004010", "D4AB0708"},
};
constexpr Operation kWaitNoStop[] = {
    {ModPatchTarget::DiscUser, 0x19C7A6DC,
     "7C00029600000000", "00EA010801000434"},
};
constexpr Operation kPressBack[] = {
    {ModPatchTarget::MainExe, 0x8007A840,
     "000000000000000000000000000000000000000000000000000000000000000000000000",
     "15001B927C00059640007C3303006017000000000800E0030100A5300800E0030200A530"},
};
constexpr Operation kCancelShared[] = {
    {ModPatchTarget::MainExe, 0x8003F340, "00000000", "D40100A6"},
    {ModPatchTarget::MainExe, 0x8007A8DC,
     "0000000000000000000000000000000000000000",
     "D5010492FFFF6324850003A20800E00309008328"},
};
constexpr Operation kCancelPressBack[] = {
    {ModPatchTarget::DiscUser, 0x19C7BF68,
     "8500039200000000FFFF6324850003A2001E0300031E03000800632802006010000000007A0000A2",
     "37EA010C8500039202006014010084247A0000A210EA010C000000000200A010D50104A2850000A2"},
};
constexpr Operation kCancelHold[] = {
    {ModPatchTarget::DiscUser, 0x19C7BF68,
     "8500039200000000FFFF6324850003A2001E0300031E03000800632802006010000000007A0000A2",
     "37EA010C8500039202006014010084247A0000A20AEA010C7C00029602004014D50104A2850000A2"},
    {ModPatchTarget::MainExe, 0x8007A828,
     "000000000000000000000000000000000000000000000000",
     "80010534D3011B92000000002128BB000800E00324104500"},
    {ModPatchTarget::DiscUser, 0x19C7A75C,
     "7C00039600000000", "3DDA010CEC00028E"},
    {ModPatchTarget::MainExe, 0x800768F4,
     "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
     "000000001000423006004010D801028E0100033C008063340000000021104300D80102AE7C000396000000000F0062300800E003D30102A2"},
};
constexpr Operation kCancelInfinite[] = {
    {ModPatchTarget::DiscUser, 0x19C7BF68,
     "8500039200000000FFFF6324850003A2001E0300031E03000800632802006010000000007A0000A2",
     "85000392000000000000000006006010850003A20AEA010C7C0002960200401400000000850000A2"},
};
constexpr Operation kHybridCancel[] = {
    {ModPatchTarget::DiscUser, 0x19C7A750,
     "05000524125B000C21300002", "29EA01080100033400000000"},
    {ModPatchTarget::MainExe, 0x8007A8A4,
     "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
     "D4011C927C001B9680009C33020080130F007B330400601305000534125B000C00000636D6AB0708D40100A201000234E4B10708060002A2"},
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

const ModOption* option(
    const ModPackage& package, std::string_view id
) {
    const auto found = std::find_if(
        package.options.begin(), package.options.end(),
        [&](const ModOption& value) {
            return value.feature_id == kFeatureId && value.id == id;
        });
    return found == package.options.end() ? nullptr : &*found;
}

const ModFeatureSelection* selected(const ModSelection& selection) {
    const auto found = selection.features.find(std::string(kFeatureId));
    return found == selection.features.end() ? nullptr : &found->second;
}

std::string value(
    const ModPackage& package, const ModSelection& selection,
    std::string_view id
) {
    const ModFeatureSelection* feature = selected(selection);
    const ModOption* declaration = option(package, id);
    if (!feature || !declaration) return {};
    const auto found = feature->values.find(std::string(id));
    return found == feature->values.end()
        ? declaration->default_value : found->second;
}

bool integer(
    const ModPackage& package, const ModSelection& selection,
    std::string_view id, int minimum, int maximum, int& result,
    std::vector<std::string>& errors
) {
    const std::string text = value(package, selection, id);
    const auto conversion = std::from_chars(
        text.data(), text.data() + text.size(), result);
    if (conversion.ec != std::errc() ||
        conversion.ptr != text.data() + text.size() ||
        result < minimum || result > maximum) {
        errors.push_back(
            package.id + "/" + std::string(id) +
            ": value outside trusted source range");
        return false;
    }
    return true;
}

struct Cell {
    uint8_t expected = 0;
    uint8_t replacement = 0;
};
using CellKey = std::pair<int, uint64_t>;
using Cells = std::map<CellKey, Cell>;

bool apply_bytes(
    Cells& cells, ModPatchTarget target, uint64_t location,
    const std::vector<uint8_t>& expected,
    const std::vector<uint8_t>& replacement,
    std::vector<std::string>& errors
) {
    if (expected.empty() || expected.size() != replacement.size()) {
        errors.push_back(
            std::string(kPackageId) + ": malformed trusted operation");
        return false;
    }
    for (size_t index = 0; index < expected.size(); ++index) {
        CellKey key{static_cast<int>(target), location + index};
        const auto found = cells.find(key);
        if (found != cells.end() && found->second.expected != expected[index]) {
            errors.push_back(
                std::string(kPackageId) +
                ": overlapping trusted stock guards disagree");
            return false;
        }
        cells[key] = {expected[index], replacement[index]};
    }
    return true;
}

template <size_t Size>
bool apply(
    Cells& cells, const Operation (&operations)[Size],
    std::vector<std::string>& errors
) {
    for (const Operation& operation : operations)
        if (!apply_bytes(
                cells, operation.target, operation.location,
                hex_bytes(operation.expected),
                hex_bytes(operation.replacement), errors))
            return false;
    return true;
}

bool apply_u8(
    Cells& cells, uint64_t address, uint8_t expected, uint8_t replacement,
    std::vector<std::string>& errors
) {
    return apply_bytes(
        cells, ModPatchTarget::MainExe, address,
        {expected}, {replacement}, errors);
}

bool apply_speed(
    Cells& cells, int speed, std::vector<std::string>& errors
) {
    const uint32_t value = static_cast<uint32_t>(speed);
    const std::vector<uint8_t> high = {
        static_cast<uint8_t>((value >> 16) & 0xFF),
        static_cast<uint8_t>((value >> 24) & 0xFF),
    };
    const std::vector<uint8_t> low = {
        static_cast<uint8_t>(value & 0xFF),
        static_cast<uint8_t>((value >> 8) & 0xFF),
    };
    return apply_bytes(
               cells, ModPatchTarget::DiscUser, 0x19C7A6E0,
               {0x00, 0x00}, high, errors) &&
           apply_bytes(
               cells, ModPatchTarget::DiscUser, 0x19C7A6E4,
               {0x02, 0x00}, low, errors);
}

void emit(
    const Cells& cells, std::vector<ModResolution::Write>& writes
) {
    auto cursor = cells.begin();
    while (cursor != cells.end()) {
        const int target = cursor->first.first;
        uint64_t next_location = cursor->first.second;
        ModResolution::Write write;
        write.target = static_cast<ModPatchTarget>(target);
        write.location = next_location;
        write.package_id = std::string(kPackageId);
        write.feature_id = std::string(kFeatureId);
        while (cursor != cells.end() &&
               cursor->first.first == target &&
               cursor->first.second == next_location) {
            write.expected.push_back(cursor->second.expected);
            write.replacement.push_back(cursor->second.replacement);
            ++next_location;
            ++cursor;
        }
        writes.push_back(std::move(write));
    }
}

bool validate(
    const ModPackage& package, std::vector<std::string>& errors
) {
    if (package.id != kPackageId || package.version != kVersion ||
        package.resolver != "builtin:" + std::string(kResolverId) ||
        package.targets.size() != 1 ||
        package.targets[0].game_id != kGameId ||
        package.targets[0].disc_sha256 != kStockDisc ||
        !package.targets[0].exe_sha256.empty() ||
        package.features.size() != 1 ||
        package.features[0].id != kFeatureId ||
        package.features[0].default_enabled ||
        package.options.size() != 6 ||
        !package.patches.empty() || !package.overlays.empty() ||
        !package.derived_discs.empty()) {
        errors.push_back(package.id + ": trusted manifest contract mismatch");
        return false;
    }
    const std::set<std::string> expected = {
        "input", "wait", "cancel", "duration", "speed", "immunity"
    };
    std::set<std::string> actual;
    for (const ModOption& item : package.options)
        if (item.feature_id == kFeatureId) actual.insert(item.id);
    if (actual != expected) {
        errors.push_back(package.id + ": trusted option inventory mismatch");
        return false;
    }
    return true;
}

bool resolve_mach_dash(
    const ModPackage& package, const ModSelection& selection,
    std::vector<ModResolution::Write>& writes,
    std::vector<std::string>& errors
) {
    if (!validate(package, errors)) return false;
    for (const auto& [id, feature] : selection.features) {
        if (id != kFeatureId) {
            errors.push_back(package.id + ": unknown selected feature " + id);
            return false;
        }
        for (const auto& [key, ignored] : feature.values) {
            (void)ignored;
            if (!option(package, key)) {
                errors.push_back(package.id + ": unknown trusted option " + key);
                return false;
            }
        }
    }
    const ModFeatureSelection* feature = selected(selection);
    if (!feature || !feature->has_enabled || !feature->enabled) return true;

    std::string input = value(package, selection, "input");
    const std::string wait = value(package, selection, "wait");
    const std::string cancel = value(package, selection, "cancel");
    int duration = 0;
    int speed = 0;
    int immunity = 0;
    if (!integer(package, selection, "duration", 10, 50, duration, errors) ||
        !integer(package, selection, "speed", 200000, 600000, speed, errors) ||
        !integer(package, selection, "immunity", 4, 50, immunity, errors))
        return false;
    const std::set<std::string> inputs = {"normal", "disabled", "hybrid"};
    const std::set<std::string> waits = {
        "normal", "unlimited", "minimum", "no_stop"
    };
    const std::set<std::string> cancels = {
        "no_cancel", "press_back", "hold_release", "infinite"
    };
    if (!inputs.count(input) || !waits.count(wait) || !cancels.count(cancel)) {
        errors.push_back(package.id + ": choice outside trusted source domain");
        return false;
    }

    // Exact upstream GuiControl normalization.
    if (wait == "no_stop") {
        duration = 15;
        speed = 540672;
        if (input == "hybrid") input = "normal";
    }
    if (cancel == "no_cancel") immunity = 9;

    const bool need_base =
        input != "normal" || wait != "normal" ||
        duration != 15 || speed != 540672;
    Cells cells;
    if (need_base && !apply(cells, kMachBase, errors)) return false;
    if (wait == "unlimited" && !apply(cells, kWaitUnlimited, errors)) return false;
    if (wait == "minimum" && !apply(cells, kWaitMinimum, errors)) return false;
    if (wait == "no_stop" && !apply(cells, kWaitNoStop, errors)) return false;
    if (input == "disabled" && !apply(cells, kInputDisabled, errors)) return false;
    if (input == "hybrid" && !apply(cells, kInputHybrid, errors)) return false;
    if (duration != 15 &&
        !apply_u8(cells, 0x8003F37C, 0x0F,
                  static_cast<uint8_t>(duration), errors))
        return false;
    if (speed != 540672 && !apply_speed(cells, speed, errors)) return false;

    if (input == "hybrid" &&
        (cancel == "hold_release" || cancel == "infinite") &&
        !apply(cells, kHybridCancel, errors))
        return false;
    if (cancel != "no_cancel") {
        if (cancel == "press_back" && !apply(cells, kPressBack, errors))
            return false;
        if (!apply(cells, kCancelShared, errors)) return false;
        if ((cancel == "hold_release" || cancel == "infinite") &&
            !apply(cells, kCancelHold, errors))
            return false;
        if (cancel == "press_back" &&
            !apply(cells, kCancelPressBack, errors))
            return false;
        if (cancel == "infinite" &&
            !apply(cells, kCancelInfinite, errors))
            return false;
        if (immunity != 9 &&
            !apply_u8(cells, 0x8007A8EC, 0x00,
                      static_cast<uint8_t>(immunity), errors))
            return false;
    }
    emit(cells, writes);
    return true;
}

const bool kRegistered = mod_register_builtin_resolver(
    std::string(kResolverId), resolve_mach_dash);

} // namespace
