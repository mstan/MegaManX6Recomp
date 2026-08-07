#pragma once

#include "mod_packages.h"

namespace MMX6Mods {

inline constexpr const char* kTweaksHooksPackageId = "mmx6.tweaks.hooks";
inline constexpr const char* kTweaksHooksPackageVersion = "1.1.0";
inline constexpr const char* kTweaksHooksResolverId = "mmx6.tweaks.hooks";

bool resolve_tweaks_hooks(
    const PSXRecompV4::ModPackage& package,
    const PSXRecompV4::ModSelection& selection,
    const PSXRecompV4::ModBuiltinResolverContext& context,
    std::vector<PSXRecompV4::ModResolution::Write>& writes,
    std::vector<std::string>& errors);

bool register_tweaks_hooks_resolver();

} // namespace MMX6Mods
