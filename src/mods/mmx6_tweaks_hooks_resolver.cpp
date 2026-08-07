#include "mmx6_tweaks_hooks_resolver.h"

#include <algorithm>
#include <array>
#include <set>
#include <string>
#include <utility>
#include <vector>

namespace MMX6Mods {
namespace {

using PSXRecompV4::ModFeature;
using PSXRecompV4::ModFeatureSelection;
using PSXRecompV4::ModPackage;
using PSXRecompV4::ModPatchTarget;
using PSXRecompV4::ModResolution;
using PSXRecompV4::ModSelection;

constexpr const char* kResolverName = "builtin:mmx6.tweaks.hooks";
constexpr const char* kGameId = "SLUS-01395";
constexpr const char* kStockDiscSha256 =
    "91ef53c12c3a3eb3362d51d524d3f83cd4ff8e68bf2d2ad6c5c8ea4e0310d318";
constexpr const char* kFoundationFeature = "voice_code_foundation";
constexpr uint64_t kVoiceCodeAddress = 0x80076440ull;
constexpr size_t kVoiceCodeSize = 0x74;

constexpr std::array<const char*, 4> kFeatureIds = {
    "voice_boss_intros",
    "voice_boss_warning",
    "voice_low_health",
    "voice_title",
};

struct Site {
    ModPatchTarget target;
    uint64_t location;
    const char* expected;
    const char* replacement;
};

struct VoiceFeature {
    const char* id;
    size_t code_offset;
    const char* code;
    const Site* sites;
    size_t site_count;
};

struct WarningRecord {
    uint32_t id;
    uint64_t table_location;
    const char* table_expected;
    const char* table_replacement;
    uint64_t payload_location;
    uint64_t payload_size;
    const char* backing_sha256;
    const char* voice_sha256;
    const char* retranslation_sha256;
};

constexpr WarningRecord kWarningRecords[] = {
    {85, 0x19E0F2A8ull, "F606000000B00C00", "E47B000000D80C00",
     0x1DC01000ull, 0xCD800ull,
     "faa6bea73bd03cdcf2d58dcf7e02488b7c1146ebb1031083aa8106cc82533717",
     "4a29d770fd4d335b6faa1e161395d4fa55fc08904e26e82294148ff35dc91400",
     "c81aa441f53fd1b8cc9f4edca76e82d9210a5ea10bca71c0847210cb3d460bc8"},
    {86, 0x19E0F2B0ull, "8C08000000C80D00", "7F7D000000F00D00",
     0x1DCCE800ull, 0xDF000ull,
     "a6e10f1f48c9b0bb4eb3374fb6a7c8ff74cc07d21155ed1a7a32611dde0f57ea",
     "929b02d80e2342830b202eea10cc9a9ad39cb45fbb47e976cdf799c74a9d883a",
     "6b3f4ba36faf8a833ced63fc055300bca9d90b14cb2e0ba129f9af08b7c93325"},
    {87, 0x19E0F2B8ull, "450A000000380E00", "3D7F000000600E00",
     0x1DDAD800ull, 0xE6000ull,
     "10d8ce3cfcdff65c514699ea99b8c3a2543fef67f7485b25c58f426229b9c589",
     "3d64c9f78bfa79a3d19570909c831d37a3e380301233d9cbcceb888d1a2ccb19",
     "2a0094bac3a650e04cef98c514ab7f35c469a5eb04c01fb40391695728f24666"},
    {88, 0x19E0F2C0ull, "0C0C000000500C00", "0981000000780C00",
     0x1DE93800ull, 0xC7800ull,
     "207fdcc5799cf911bd20210f9e6273e369cbc9570669fd7d5b0929b2bdfb372e",
     "c7021afb77529023d93d000f1baf2700f17313478c6e4fdff3a83b242cbb3e57",
     "c21fd0d59971f34cef78ad3304ff8fc23a97901d3d1d84e73cd241870a6fc970"},
    {89, 0x19E0F2C8ull, "960D000000100E00", "9882000000380E00",
     0x1DF5B000ull, 0xE3800ull,
     "32bac2734c9376ba35b3663544947fb98fad53931d0721e24bbb0aefabfabd43",
     "a7a4476b6449a013683e86facca7139ae4dc871013ec141fdda33ab9bfa3399b",
     "20f3c92498858b315643b737d410f241ca1c9ff4d5df4a334ccf2ac4b73dddf8"},
};

constexpr Site kTitleSites[] = {
    {
        ModPatchTarget::MainExe,
        0x8001DEC4ull,
        "1000B0AF21800000",
        "1FD901081000B0AF",
    },
    {
        ModPatchTarget::MainExe,
        0x8001DF54ull,
        "0800E003",
        "14780008",
    },
};

constexpr Site kBossIntroSites[] = {
    {
        ModPatchTarget::DiscUser,
        0x19D3FE18ull,
        "01004224010082A00800E003",
        "16D9010801004224B3A60308",
    },
};

constexpr Site kLowHealthSites[] = {
    {
        ModPatchTarget::MainExe,
        0x8003D050ull,
        "1010000023104300001602005C00C380031602002A1862000200601078"
        "0002248D00C2A00800E00300000000",
        "10D901081010000006006010030004340F000534125B000C0000063478"
        "0002248D0002A242DE000800000000",
    },
};

constexpr Site kBossWarningSites[] = {
    {
        ModPatchTarget::MainExe,
        0x80053874ull,
        "125B000C",
        "25D90108",
    },
};

constexpr VoiceFeature kVoices[] = {
    {
        "voice_title",
        0x3C,
        "0500043400000534125B000C00000634B377000800001034",
        kTitleSites,
        std::size(kTitleSites),
    },
    {
        "voice_boss_intros",
        0x18,
        "010082A0260082800000063421104800FFFF4590125B000C00000434"
        "A0A7030800000000",
        kBossIntroSites,
        std::size(kBossIntroSites),
    },
    {
        "voice_low_health",
        0x00,
        "23104300001602005C00C3800316020016F400082A186200",
        kLowHealthSites,
        std::size(kLowHealthSites),
    },
    {
        "voice_boss_warning",
        0x54,
        "125B000C00000634000004342C000534125B000C000006341F4E0108"
        "3C000334",
        kBossWarningSites,
        std::size(kBossWarningSites),
    },
};

int hex_nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

bool decode_hex(const char* text, std::vector<uint8_t>& out) {
    const std::string value(text ? text : "");
    if (value.empty() || value.size() % 2 != 0) return false;
    out.clear();
    out.reserve(value.size() / 2);
    for (size_t i = 0; i < value.size(); i += 2) {
        const int high = hex_nibble(value[i]);
        const int low = hex_nibble(value[i + 1]);
        if (high < 0 || low < 0) return false;
        out.push_back(static_cast<uint8_t>((high << 4) | low));
    }
    return true;
}

void fail(const ModPackage& package, std::vector<std::string>& errors,
          const std::string& message) {
    errors.push_back(package.id + ": " + message);
}

bool validate_package(const ModPackage& package,
                      std::vector<std::string>& errors) {
    if (package.id != kTweaksHooksPackageId) {
        fail(package, errors, "trusted resolver package id mismatch");
        return false;
    }
    if (package.version != kTweaksHooksPackageVersion) {
        fail(package, errors, "unsupported trusted resolver package version");
        return false;
    }
    if (package.format_version != 4 || package.resolver != kResolverName) {
        fail(package, errors, "trusted resolver manifest contract mismatch");
        return false;
    }
    if (package.save_compatibility != "shared" ||
        package.targets.size() != 1 ||
        package.targets[0].game_id != kGameId ||
        !package.targets[0].exe_sha256.empty() ||
        package.targets[0].disc_sha256 != kStockDiscSha256 ||
        !package.dependencies.empty() || !package.conflicts.empty() ||
        !package.options.empty() || !package.constraints.empty() ||
        !package.patches.empty() ||
        !package.derived_discs.empty()) {
        fail(package, errors, "trusted resolver target or payload mismatch");
        return false;
    }

    std::set<std::string> actual;
    for (const ModFeature& feature : package.features) {
        if (feature.legacy || feature.default_enabled ||
            !actual.emplace(feature.id).second) {
            fail(package, errors, "invalid or duplicate trusted feature");
            return false;
        }
    }
    const std::set<std::string> expected(
        kFeatureIds.begin(), kFeatureIds.end());
    if (actual != expected) {
        fail(package, errors, "trusted feature inventory mismatch");
        return false;
    }
    if (package.overlays.size() != std::size(kWarningRecords) * 2) {
        fail(package, errors, "trusted warning asset inventory mismatch");
        return false;
    }
    for (const WarningRecord& record : kWarningRecords) {
        for (bool retranslation : {false, true}) {
            const auto found = std::find_if(
                package.overlays.begin(), package.overlays.end(),
                [&](const PSXRecompV4::ModOverlay& overlay) {
                    return overlay.location == record.payload_location &&
                        overlay.when_feature.present &&
                        overlay.when_feature.enabled == retranslation;
                });
            const char* payload_sha256 = retranslation
                ? record.retranslation_sha256 : record.voice_sha256;
            if (found == package.overlays.end() ||
                found->feature_id != "voice_boss_warning" ||
                found->target != ModPatchTarget::DiscUser ||
                found->location != record.payload_location ||
                found->size != record.payload_size ||
                found->sha256 != payload_sha256 ||
                found->expected_sha256 != record.backing_sha256 ||
                !found->when.empty() ||
                !found->when_feature.present ||
                found->when_feature.package_id != "mmx6.tweaks.native" ||
                found->when_feature.feature_id != "retranslation" ||
                found->when_feature.enabled != retranslation) {
                fail(package, errors,
                     "trusted warning asset declaration mismatch");
                return false;
            }
        }
    }
    return true;
}

bool feature_enabled(const ModPackage& package, const ModSelection& selection,
                     const char* id, std::vector<std::string>& errors) {
    const auto found = selection.features.find(id);
    if (found == selection.features.end()) return false;
    const ModFeatureSelection& selected = found->second;
    if (!selected.values.empty()) {
        fail(package, errors, std::string(id) +
            " does not accept configuration values");
        return false;
    }
    return selected.has_enabled && selected.enabled;
}

void append_write(std::vector<ModResolution::Write>& writes,
                  ModPatchTarget target, uint64_t location,
                  std::vector<uint8_t> expected,
                  std::vector<uint8_t> replacement,
                  const std::string& feature_id) {
    ModResolution::Write write;
    write.target = target;
    write.location = location;
    write.expected = std::move(expected);
    write.replacement = std::move(replacement);
    write.package_id = kTweaksHooksPackageId;
    write.feature_id = feature_id;
    writes.push_back(std::move(write));
}

bool resolve_impl(const ModPackage& package, const ModSelection& selection,
                  const PSXRecompV4::ModBuiltinResolverContext& context,
                  std::vector<ModResolution::Write>& writes,
                  std::vector<std::string>& errors) {
    (void)context;
    if (!validate_package(package, errors)) return false;
    if (!selection.values.empty() ||
        (!selection.version.empty() &&
         selection.version != kTweaksHooksPackageVersion)) {
        fail(package, errors, "invalid trusted package selection");
        return false;
    }
    for (const auto& [id, selected] : selection.features) {
        if (!std::binary_search(
                kFeatureIds.begin(), kFeatureIds.end(), id)) {
            fail(package, errors, "unknown selected feature: " + id);
            return false;
        }
        if (!selected.values.empty()) {
            fail(package, errors, id + " does not accept configuration values");
            return false;
        }
    }

    std::array<bool, std::size(kVoices)> enabled{};
    bool any_enabled = false;
    for (size_t i = 0; i < std::size(kVoices); ++i) {
        enabled[i] =
            feature_enabled(package, selection, kVoices[i].id, errors);
        any_enabled = any_enabled || enabled[i];
    }
    if (!errors.empty()) return false;
    if (!any_enabled) return true;

    std::vector<uint8_t> code_expected(kVoiceCodeSize, 0);
    std::vector<uint8_t> code_replacement(kVoiceCodeSize, 0);
    for (size_t i = 0; i < std::size(kVoices); ++i) {
        if (!enabled[i]) continue;
        std::vector<uint8_t> code;
        if (!decode_hex(kVoices[i].code, code) ||
            kVoices[i].code_offset + code.size() > code_replacement.size()) {
            fail(package, errors, std::string(kVoices[i].id) +
                " has an invalid trusted code allocation");
            return false;
        }
        std::copy(code.begin(), code.end(),
                  code_replacement.begin() + kVoices[i].code_offset);
    }
    append_write(
        writes, ModPatchTarget::MainExe, kVoiceCodeAddress,
        std::move(code_expected), std::move(code_replacement),
        kFoundationFeature);

    for (size_t i = 0; i < std::size(kVoices); ++i) {
        if (!enabled[i]) continue;
        for (size_t site_index = 0;
             site_index < kVoices[i].site_count; ++site_index) {
            const Site& site = kVoices[i].sites[site_index];
            std::vector<uint8_t> expected;
            std::vector<uint8_t> replacement;
            if (!decode_hex(site.expected, expected) ||
                !decode_hex(site.replacement, replacement) ||
                expected.size() != replacement.size()) {
                fail(package, errors, std::string(kVoices[i].id) +
                    " has an invalid trusted hook site");
                return false;
            }
            append_write(
                writes, site.target, site.location, std::move(expected),
                std::move(replacement), kVoices[i].id);
        }
    }
    if (enabled[3]) {
        for (const WarningRecord& record : kWarningRecords) {
            std::vector<uint8_t> expected;
            std::vector<uint8_t> replacement;
            if (!decode_hex(record.table_expected, expected) ||
                !decode_hex(record.table_replacement, replacement)) {
                fail(package, errors,
                     "trusted warning record table bytes are invalid");
                return false;
            }
            append_write(
                writes, ModPatchTarget::DiscUser, record.table_location,
                std::move(expected), std::move(replacement),
                "voice_boss_warning");
        }
        std::vector<uint8_t> expected;
        std::vector<uint8_t> replacement;
        if (!decode_hex("00E008030308E000", expected) ||
            !decode_hex("00F822040422F800", replacement)) {
            fail(package, errors, "trusted warning DAT extent is invalid");
            return false;
        }
        append_write(
            writes, ModPatchTarget::DiscUser, 0xB0A6ull,
            std::move(expected), std::move(replacement),
            "voice_boss_warning");
    }
    return true;
}

} // namespace

bool resolve_tweaks_hooks(
    const ModPackage& package, const ModSelection& selection,
    const PSXRecompV4::ModBuiltinResolverContext& context,
    std::vector<ModResolution::Write>& writes,
    std::vector<std::string>& errors) {
    const size_t write_begin = writes.size();
    const size_t error_begin = errors.size();
    if (resolve_impl(package, selection, context, writes, errors)) return true;
    writes.resize(write_begin);
    if (errors.size() == error_begin)
        fail(package, errors, "trusted resolver failed");
    return false;
}

bool register_tweaks_hooks_resolver() {
    return PSXRecompV4::mod_register_builtin_resolver(
        kTweaksHooksResolverId, resolve_tweaks_hooks);
}

namespace {
const bool kRegistered = register_tweaks_hooks_resolver();
}

} // namespace MMX6Mods
