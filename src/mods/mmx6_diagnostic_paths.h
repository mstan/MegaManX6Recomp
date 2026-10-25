#pragma once
#include <array>
#include <cstdlib>
#include <filesystem>
#include <stdexcept>
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

inline std::filesystem::path mmx6_diagnostic_application_directory() {
#ifdef _WIN32
    std::array<wchar_t,32768> path{};
    DWORD n=GetModuleFileNameW(nullptr,path.data(),(DWORD)path.size());
    if(!n || n>=path.size())throw std::runtime_error("cannot locate executable");
    return std::filesystem::path(path.data()).parent_path();
#else
    /* AppRun preserves APPIMAGE under RECOMP_APPIMAGE_PATH before unsetting
     * APPIMAGE. The real executable lives inside the read-only temporary mount. */
    const char *appimage=std::getenv("RECOMP_APPIMAGE_PATH");
    if(!appimage || !appimage[0])appimage=std::getenv("APPIMAGE");
    if(appimage && appimage[0]) {
        auto path=std::filesystem::u8path(appimage);
        if(path.is_absolute())return path.parent_path();
    }
    return std::filesystem::read_symlink("/proc/self/exe").parent_path();
#endif
}
