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

psxrecomp_v4_add_runtime_target(psx-runtime
    GAME_GENERATED_FULL_C "${GAME_GENERATED_FULL}"
    GAME_GENERATED_DISPATCH_C "${GAME_GENERATED_DISPATCH}"
    DEBUG_PORT 4490
    WINDOW_TITLE "MegaManX6Recomp"
    DEFAULT_BIOS_PATH "${PSXRECOMP_V4_ROOT}/bios/SCPH1001.BIN"
    DEFAULT_GAME_CONFIG_PATH "game.toml"
    EXE_NAME "mmx6-runtime"
    EXTRAS_SOURCES ${GAME_GENERATED_EXTRAS}
)

# Shared recomp-ui Dear ImGui launcher. Wires in the PSX-themed launcher UI
# (see main.cpp RECOMP_LAUNCHER gate) instead of the framework's default RmlUi
# launcher. recomp-ui is a real git submodule (github.com/mstan/recomp-ui,
# pinned via the recomp-ui gitlink); locally it is a directory junction to the
# working checkout so builds stay offline and reproducible like everything else.
include("${CMAKE_SOURCE_DIR}/recomp-ui/recomp_ui.cmake")
recomp_target_launcher_ui(psx-runtime
    BOXART "${CMAKE_SOURCE_DIR}/recomp/launcher/boxart.tga"
    PAD    "${CMAKE_SOURCE_DIR}/recomp/launcher/pad.tga"
    BRAND  "${CMAKE_SOURCE_DIR}/recomp/launcher/brand.tga"
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
        DEFAULT_BIOS_PATH "${PSXRECOMP_V4_ROOT}/bios/SCPH1001.BIN"
        DEFAULT_GAME_CONFIG_PATH "game.toml"
        EXTRAS_SOURCES ${GAME_GENERATED_EXTRAS}
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
