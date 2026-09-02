cmake_minimum_required(VERSION 3.20)
project(MegaManX6Recomp C CXX)
include(CTest)

set(CMAKE_C_STANDARD 99)
set(CMAKE_CXX_STANDARD 17)

set(PSXRECOMP_V4_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/psxrecomp-v4" CACHE PATH
    "Path to psxrecomp-v4")

include("${PSXRECOMP_V4_ROOT}/runtime/runtime.cmake")

# Generated-C directory. Defaults to "generated" (the vanilla recompile). A
# variant build (e.g. a "MMX6 Tweaks" patched-input recompile) sets
# -DGAME_GENERATED_DIR=generated-tweaks to consume a parallel regen without
# disturbing the vanilla generated/ or its build dir. See mmx6-tweaks/ + the
# game.tweaks.toml variant config.
set(GAME_GENERATED_DIR "generated" CACHE STRING
    "Directory (relative to source) holding the recompiled game C")

# The current recompiler emits the game as split translation units. Keep the
# monolithic fallback for older generated/ directories used by variant builds.
file(GLOB GAME_GENERATED_FULL_SHARDS CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/${GAME_GENERATED_DIR}/SLUS_013.95_full_*.c")
if(GAME_GENERATED_FULL_SHARDS)
    set(GAME_GENERATED_FULL ${GAME_GENERATED_FULL_SHARDS})
    list(POP_FRONT GAME_GENERATED_FULL GAME_GENERATED_PRIMARY)
    set(GAME_GENERATED_EXTRAS ${GAME_GENERATED_FULL})
    set(GAME_GENERATED_FULL ${GAME_GENERATED_PRIMARY})
else()
    set(GAME_GENERATED_FULL
        "${CMAKE_CURRENT_SOURCE_DIR}/${GAME_GENERATED_DIR}/SLUS_013.95_full.c")
endif()
set(GAME_GENERATED_DISPATCH
    "${CMAKE_CURRENT_SOURCE_DIR}/${GAME_GENERATED_DIR}/SLUS_013.95_dispatch.c")

# Trusted, statically linked mod plugin implementations. A package manifest in
# mods/preloaded selects one by its stable plugin id; archives never carry or
# load native code.
file(GLOB MMX6_MOD_PLUGIN_SOURCES CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/src/mods/*.c")

# Game-owned trusted mod resolvers live in independent source files so feature
# domains can be developed and reviewed without editing one central registry.
file(GLOB GAME_MOD_RESOLVER_SOURCES CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/src/mods/*.cpp")

# The game-owned mod catalog (the two presentation enhancements plus the
# acediez Tweaks set). Every feature stays disabled until selected on the
# launcher's Mods page.
#
# The FRAMEWORK stages it: PRELOADED_MODS_DIR below hands the directory to
# psxrecomp_add_runtime_target(), which wipes <exe-dir>/mods/bundled and copies
# both its own mods/builtin/packages and these packages into it, plus
# mods/preloaded/README.md -> mods/README.md. This repo must NOT copy the tree
# itself. It used to, with a hand-written POST_BUILD copy_directory into
# <exe-dir>/mods, and because that named the destination as a STRING, framework
# commit 4cc04be3's rename of the staged catalog from mods/packages to
# mods/bundled broke it silently -- nothing a configure, compile or link step
# can see. The 15 mmx6.* packages went on landing in mods/packages, which
# neither the launcher nor the release packager's Add-ModCatalog reads.
# Bead beads-eio.3.101.
set(MMX6_PRELOADED_MODS "${CMAKE_CURRENT_SOURCE_DIR}/mods/preloaded")

psxrecomp_v4_add_runtime_target(psx-runtime
    GAME_GENERATED_FULL_C "${GAME_GENERATED_FULL}"
    GAME_GENERATED_DISPATCH_C "${GAME_GENERATED_DISPATCH}"
    DEBUG_PORT 4490
    WINDOW_TITLE "MegaManX6Recomp"
    DEFAULT_GAME_CONFIG_PATH "game.toml"
    EXE_NAME "mmx6-runtime"
    LAUNCHER_BOXART "${CMAKE_SOURCE_DIR}/recomp/launcher/boxart.tga"
    PRELOADED_MODS_DIR "${MMX6_PRELOADED_MODS}"
    EXTRAS_SOURCES
        ${GAME_GENERATED_EXTRAS}
        ${MMX6_MOD_PLUGIN_SOURCES}
        ${GAME_MOD_RESOLVER_SOURCES}
)

# First-divergence co-sim oracle build (COSIM_ORACLE.md): clean, deterministic,
# PSX_NO_DEBUG_TOOLS + PSX_COSIM. Two of these (one normal, one PSX_FORCE_INTERP=1)
# are cycle-lockstepped by tools/cosim.py to find the exact first compiled-vs-interp
# divergence. Only built on explicit request (-DPSX_BUILD_COSIM=ON) to keep normal
# game builds lean.
if(PSX_BUILD_COSIM)
    psxrecomp_v4_add_runtime_target(psx-cosim
        GAME_GENERATED_FULL_C "${GAME_GENERATED_FULL}"
        GAME_GENERATED_DISPATCH_C "${GAME_GENERATED_DISPATCH}"
        WINDOW_TITLE "MMX6-cosim"
        DEFAULT_GAME_CONFIG_PATH "game.toml"
        EXTRAS_SOURCES ${GAME_GENERATED_EXTRAS} ${GAME_MOD_RESOLVER_SOURCES}
        COSIM
    )
endif()

# Per-game launcher art override. The framework copies its shared launcher assets
# (img/disc.png etc. — the default is Tomba's disc) next to the exe; this copies
# this repo's launcher_art/ on top AFTERWARD so the launcher shows MMX6's disc.
# POST_BUILD commands run in add order, and the framework's copy is added inside
# psxrecomp_v4_add_runtime_target above, so this override wins. Drop official art
# into launcher_art/img/ to replace the generated placeholder.
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/launcher_art")
    add_custom_command(TARGET psx-runtime POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_directory
            "${CMAKE_CURRENT_SOURCE_DIR}/launcher_art"
            "$<TARGET_FILE_DIR:psx-runtime>"
        COMMENT "Overriding launcher art with MegaManX6Recomp/launcher_art")
endif()

# Framework sources these tests compile in are addressed through
# ${PSXRECOMP_V4_ROOT}, not the bare relative path "psxrecomp-v4/...". The
# relative spelling only resolved when the submodule/junction was populated
# in-tree, so `-DPSXRECOMP_V4_ROOT=<worktree>` -- the way a title is validated
# against a framework branch without moving its submodule pin -- failed to
# generate at all ("No SOURCES given to target: mmx6_preloaded_mods_test").
# A title that cannot be built against framework master cannot be checked
# against it either.
if(BUILD_TESTING)
    add_executable(mmx6_tweaks_hooks_test
        tests/test_mmx6_tweaks_hooks.cpp
        src/mods/mmx6_tweaks_hooks_resolver.cpp
        "${PSXRECOMP_V4_ROOT}/runtime/src/mod_packages.cpp"
        "${PSXRECOMP_V4_ROOT}/runtime/src/crc32.c"
        "${PSXRECOMP_V4_ROOT}/runtime/src/psx_sha256.c"
    )
    target_include_directories(mmx6_tweaks_hooks_test PRIVATE
        src/mods
        "${PSXRECOMP_V4_ROOT}/runtime/include"
        "${PSXRECOMP_V4_ROOT}/recompiler/lib/toml11"
    )
    add_test(
        NAME mmx6_tweaks_hooks_test
        COMMAND "./$<TARGET_FILE_NAME:mmx6_tweaks_hooks_test>"
    )
    set_tests_properties(
        mmx6_tweaks_hooks_test
        PROPERTIES WORKING_DIRECTORY "$<TARGET_FILE_DIR:mmx6_tweaks_hooks_test>"
    )

    add_executable(mmx6_preloaded_mods_test
        tests/test_preloaded_mods.cpp
        ${GAME_MOD_RESOLVER_SOURCES}
        "${PSXRECOMP_V4_ROOT}/runtime/src/mod_packages.cpp"
        "${PSXRECOMP_V4_ROOT}/runtime/src/crc32.c"
        "${PSXRECOMP_V4_ROOT}/runtime/src/psx_sha256.c"
    )
    target_include_directories(mmx6_preloaded_mods_test PRIVATE
        src/mods
        "${PSXRECOMP_V4_ROOT}/runtime/include"
        "${PSXRECOMP_V4_ROOT}/recompiler/lib/toml11"
    )
    add_test(
        NAME mmx6_preloaded_mods_test
        COMMAND "$<TARGET_FILE:mmx6_preloaded_mods_test>"
                "${MMX6_PRELOADED_MODS}"
    )

    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    set(MMX6_TIMING_PACKAGE_DIR
        "${MMX6_PRELOADED_MODS}/packages/mmx6.tweaks.timing/1.1.0")
    set(MMX6_TIMING_TEST_ARCHIVE
        "${CMAKE_CURRENT_BINARY_DIR}/test-packages/MMX6-Tweaks-Timing.psxmod")
    file(GLOB_RECURSE MMX6_TIMING_PACKAGE_FILES CONFIGURE_DEPENDS
        "${MMX6_TIMING_PACKAGE_DIR}/*")
    add_custom_command(
        OUTPUT "${MMX6_TIMING_TEST_ARCHIVE}"
        COMMAND "${Python3_EXECUTABLE}"
                "${PSXRECOMP_V4_ROOT}/tools/psxmod_pack.py"
                "${MMX6_TIMING_PACKAGE_DIR}"
                "${MMX6_TIMING_TEST_ARCHIVE}"
        DEPENDS
            ${MMX6_TIMING_PACKAGE_FILES}
            "${PSXRECOMP_V4_ROOT}/tools/psxmod_pack.py"
        COMMENT "Packing the preloaded MMX6 timing test package"
        VERBATIM
    )
    add_custom_target(mmx6_timing_test_package
        DEPENDS "${MMX6_TIMING_TEST_ARCHIVE}")

    add_executable(mmx6_tweaks_timing_runtime_test
        tools/test_tweaks_timing_runtime.cpp
        "${PSXRECOMP_V4_ROOT}/runtime/src/mod_packages.cpp"
        "${PSXRECOMP_V4_ROOT}/runtime/src/crc32.c"
        "${PSXRECOMP_V4_ROOT}/runtime/src/psx_sha256.c"
    )
    add_dependencies(mmx6_tweaks_timing_runtime_test
        mmx6_timing_test_package)
    target_include_directories(mmx6_tweaks_timing_runtime_test PRIVATE
        "${PSXRECOMP_V4_ROOT}/runtime/include"
        "${PSXRECOMP_V4_ROOT}/recompiler/lib/toml11"
    )
    add_test(
        NAME mmx6_tweaks_timing_runtime_test
        COMMAND "$<TARGET_FILE:mmx6_tweaks_timing_runtime_test>"
                "${MMX6_TIMING_TEST_ARCHIVE}"
    )
endif()
