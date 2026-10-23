#pragma once

#include <chrono>
#include <filesystem>
#include <string>
#include <system_error>

// Reserve a directory atomically: concurrent configurations/worktrees may share
// TEMP. Never remove another run's workspace, including retained failure data.
inline std::filesystem::path reserve_test_workspace(
    const char* prefix, std::error_code& error,
    const std::filesystem::path& base = {}) {
    error.clear();
    const auto parent = base.empty() ? std::filesystem::temp_directory_path(error) : base;
    if (error) return {};
    const auto stamp = std::chrono::steady_clock::now().time_since_epoch().count();
    for (unsigned attempt = 0; attempt < 100; ++attempt) {
        error.clear();
        const auto candidate = parent /
            (std::string(prefix) + "-" + std::to_string(stamp) + "-" +
             std::to_string(attempt));
        if (std::filesystem::create_directory(candidate, error)) return candidate;
        if (error && error != std::errc::file_exists) return {};
    }
    error = std::make_error_code(std::errc::file_exists);
    return {};
}
