cmake_minimum_required(VERSION 3.20)
project(MegaManX6Recomp C CXX)

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

psxrecomp_v4_add_runtime_target(psx-runtime
    GAME_GENERATED_FULL_C "${GAME_GENERATED_FULL}"
    GAME_GENERATED_DISPATCH_C "${GAME_GENERATED_DISPATCH}"
    DEBUG_PORT 4490
    WINDOW_TITLE "MegaManX6Recomp"
    DEFAULT_GAME_CONFIG_PATH "game.toml"
    EXE_NAME "mmx6-runtime"
    LAUNCHER_BOXART "${CMAKE_SOURCE_DIR}/recomp/launcher/boxart.tga"
    EXTRAS_SOURCES ${GAME_GENERATED_EXTRAS} ${MMX6_MOD_PLUGIN_SOURCES}
)

# Ship the game-owned mod catalog beside the executable. Every feature stays
# disabled until selected on the launcher's Mods page.
set(MMX6_PRELOADED_MODS "${CMAKE_CURRENT_SOURCE_DIR}/mods/preloaded")
if(EXISTS "${MMX6_PRELOADED_MODS}/packages")
    add_custom_command(TARGET psx-runtime POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_directory
            "${MMX6_PRELOADED_MODS}"
            "$<TARGET_FILE_DIR:psx-runtime>/mods"
        COMMENT "Preloading the Mega Man X6 mod catalog")
endif()

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
        EXTRAS_SOURCES ${GAME_GENERATED_EXTRAS}
        COSIM
    )
endif()
