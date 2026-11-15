cmake_minimum_required(VERSION 3.20)
project(MegaManX6Recomp C CXX)
include(CTest)
find_package(Python3 QUIET COMPONENTS Interpreter)

set(CMAKE_C_STANDARD 99)
set(CMAKE_CXX_STANDARD 17)
option(PSX_NETPLAY "Build the shared two-player netplay stack" ON)
option(MMX6_ENABLE_LOOPBACK_HOST_LAB
    "Enable unqualified same-machine Clang22 ENHANCED loopback candidate for explicit lab validation" OFF)
option(MMX6_ENABLE_PORTABLE_CPU_HOST_LAB
    "Add unqualified Windows x64 portable-CPU ENHANCED loopback cell for explicit validation" OFF)
if(MMX6_ENABLE_PORTABLE_CPU_HOST_LAB AND NOT MMX6_ENABLE_LOOPBACK_HOST_LAB)
    message(FATAL_ERROR "Portable CPU candidate requires the existing explicit loopback host lab")
endif()
if(MMX6_ENABLE_PORTABLE_CPU_HOST_LAB)
    foreach(_portable_language C CXX)
        foreach(_portable_config "" _DEBUG _RELEASE _RELWITHDEBINFO _MINSIZEREL)
            if("${CMAKE_${_portable_language}_FLAGS${_portable_config}}" MATCHES "(-march=|-mcpu=|-mavx|-msse3|-mssse3|-msse4|-mfma|/arch:|/fp:fast|-ffast-math|-Ofast)")
                message(FATAL_ERROR "Portable CPU candidate requires generic ISA/canonical FP flags")
            endif()
        endforeach()
    endforeach()
endif()

set(PSXRECOMP_V4_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/psxrecomp-v4" CACHE PATH
    "Path to psxrecomp-v4")

include("${PSXRECOMP_V4_ROOT}/runtime/runtime.cmake")
option(MMX6_NATIVE_IDLE_WAIT "Select the audited native PsyQ frame wait" ON)
set(MMX6_NATIVE_IDLE_WAIT_SITES "")
if(MMX6_NATIVE_IDLE_WAIT)
    if(NOT COMMAND psxrecomp_native_idle_wait)
        message(FATAL_ERROR "MMX6_NATIVE_IDLE_WAIT needs native wait-policy support")
    endif()
    # SLUS-01395 v1.1 v_wait at80060ADC: timeout word atsp+16,
    # frame counter8007C8E4, no MMIO or other counter-dependent exit.
    set(MMX6_NATIVE_IDLE_WAIT_SITES 0x80060B04 0x80060B4C)
endif()

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
# Runtime draw hooks and the Seamless Loading resident store are separate from
# declarative catalog resolvers.
list(FILTER GAME_MOD_RESOLVER_SOURCES EXCLUDE REGEX "mmx6_frame_interpolation_plugin[.]cpp$")
list(FILTER GAME_MOD_RESOLVER_SOURCES EXCLUDE REGEX "mmx6_seamless_store[.]cpp$")

set_property(SOURCE src/mods/mmx6_startup_log.cpp APPEND PROPERTY COMPILE_DEFINITIONS
    "MMX6_STARTUP_BUILD_ID=\"mmx6-x-zero-delay-v67\"")

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
if(MMX6_ENABLE_LOOPBACK_HOST_LAB)
    # These named checkpoint/position/contact prerequisites exist only in the explicit
    # lab catalog. The normal catalog never gains a teleport control.
    # Normal source/release catalogs never acquire it. The framework still
    # owns final staging and catalog validation of this generated input tree.
    set(_mmx6_coop_manifest "packages/mmx6.local-coop/0.0.1/manifest.toml")
    set(_mmx6_checkpoint_option "${CMAKE_CURRENT_SOURCE_DIR}/packaging/lab/coop-checkpoint-option.toml")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
        "${MMX6_PRELOADED_MODS}/${_mmx6_coop_manifest}" "${_mmx6_checkpoint_option}")
    file(READ "${MMX6_PRELOADED_MODS}/${_mmx6_coop_manifest}" _mmx6_coop_catalog)
    file(READ "${_mmx6_checkpoint_option}" _mmx6_checkpoint_catalog)
    set(_mmx6_lab_catalog "${CMAKE_CURRENT_BINARY_DIR}/mmx6-lab-catalog")
    file(COPY "${MMX6_PRELOADED_MODS}/" DESTINATION "${_mmx6_lab_catalog}")
    file(WRITE "${_mmx6_lab_catalog}/${_mmx6_coop_manifest}" "${_mmx6_coop_catalog}\n${_mmx6_checkpoint_catalog}")
    set(MMX6_PRELOADED_MODS "${_mmx6_lab_catalog}")
endif()

# Seamless Loading replaces the generic CD-speed and host-turbo builtins:
# neither may change guest CD or audio pacing in this catalog. Restore the
# caller's selection afterward for any other target.
set(_mmx6_previous_builtin_allowlist "${PSX_BUILTIN_MOD_ALLOWLIST}")
set(PSX_BUILTIN_MOD_ALLOWLIST
    psx.enhancement.8mb-ram
    psx.enhancement.pgxp
    psx.presentation.bezel)
psxrecomp_v4_add_runtime_target(psx-runtime
    NATIVE_IDLE_WAIT_SITES ${MMX6_NATIVE_IDLE_WAIT_SITES}
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
        "${CMAKE_CURRENT_SOURCE_DIR}/src/mods/mmx6_frame_interpolation_plugin.cpp"
        "${CMAKE_CURRENT_SOURCE_DIR}/src/mods/mmx6_seamless_store.cpp"
        ${GAME_MOD_RESOLVER_SOURCES}
)
set(PSX_BUILTIN_MOD_ALLOWLIST "${_mmx6_previous_builtin_allowlist}")
unset(_mmx6_previous_builtin_allowlist)
if(MMX6_ENABLE_LOOPBACK_HOST_LAB)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_custom_target(mmx6_host_lab_contract_check
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/mmx6_host_lab_contract.py"
            --execution-profile "${CMAKE_CURRENT_BINARY_DIR}/psx_execution/psx-runtime/profile.h"
        VERBATIM)
endif()
foreach(_mmx6_host_target psx-runtime psx-runtime-pgxp)
    if(TARGET ${_mmx6_host_target})
        # Every activation reacquires title-owned arenas and retained banks.
        set_property(TARGET ${_mmx6_host_target} PROPERTY PSX_MOD_SESSION_RESOURCES ON)
        target_compile_definitions(${_mmx6_host_target} PRIVATE
            MMX6_ENABLE_LOOPBACK_HOST_LAB=$<BOOL:${MMX6_ENABLE_LOOPBACK_HOST_LAB}>
            MMX6_ENABLE_PORTABLE_CPU_HOST_LAB=$<BOOL:${MMX6_ENABLE_PORTABLE_CPU_HOST_LAB}>)
        if(TARGET mmx6_host_lab_contract_check)
            add_dependencies(${_mmx6_host_target} mmx6_host_lab_contract_check)
        endif()
    endif()
endforeach()

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

# Separate declared build identity; title/execution/content checks stay active.
include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/mmx6_build_manifest.cmake")
mmx6_register_build_manifests()

# Per-game launcher art override. The framework copies its shared launcher assets
# (img/disc.png etc. â€” the default is Tomba's disc) next to the exe; this copies
# this repo's launcher_art/ on top AFTERWARD so the launcher shows MMX6's disc.
# POST_BUILD commands run in add order, and the framework's copy is added inside
# psxrecomp_v4_add_runtime_target above, so this override wins. Drop official art
# into launcher_art/img/ to replace the generated placeholder.
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/launcher_art")
    foreach(MMX6_RUNTIME_TARGET psx-runtime psx-runtime-pgxp)
        if(TARGET ${MMX6_RUNTIME_TARGET})
            add_custom_command(TARGET ${MMX6_RUNTIME_TARGET} POST_BUILD
                COMMAND ${CMAKE_COMMAND} -E copy_directory
                    "${CMAKE_CURRENT_SOURCE_DIR}/launcher_art"
                    "$<TARGET_FILE_DIR:${MMX6_RUNTIME_TARGET}>"
                COMMENT "Overriding launcher art with MegaManX6Recomp/launcher_art")
        endif()
    endforeach()
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
    set(_lab_sdk_sources "")
    if(EXISTS "${PSXRECOMP_V4_ROOT}/runtime/src/netplay_host_profile.c")
        list(APPEND _lab_sdk_sources "${PSXRECOMP_V4_ROOT}/runtime/src/netplay_host_profile.c"
            "${PSXRECOMP_V4_ROOT}/runtime/src/psx_sha256.c")
    endif()
    foreach(_lab_variant enabled disabled wrong-contract pgxp legacy-settings-api)
        set(_lab_test mmx6_host_lab_${_lab_variant}_test)
        add_executable(${_lab_test} tests/test_mmx6_coop_host_lab.c ${_lab_sdk_sources})
        target_include_directories(${_lab_test} PRIVATE tests src/mods "${PSXRECOMP_V4_ROOT}/runtime/include")
        set(_lab_expected 0)
        if(_lab_variant STREQUAL "disabled")
            target_compile_definitions(${_lab_test} PRIVATE MMX6_ENABLE_LOOPBACK_HOST_LAB=0)
        else()
            target_compile_definitions(${_lab_test} PRIVATE MMX6_ENABLE_LOOPBACK_HOST_LAB=1)
            if((_lab_variant STREQUAL "enabled" OR _lab_variant STREQUAL "legacy-settings-api")
                AND WIN32 AND MINGW AND CMAKE_SIZEOF_VOID_P EQUAL 8
                AND CMAKE_SYSTEM_PROCESSOR MATCHES "^(AMD64|amd64|x86_64|X86_64)$"
                AND CMAKE_C_COMPILER_ID STREQUAL "Clang" AND CMAKE_C_COMPILER_VERSION VERSION_EQUAL "22.1.8")
                set(_lab_expected 1)
            endif()
        endif()
        if(_lab_variant STREQUAL "wrong-contract")
            target_compile_definitions(${_lab_test} PRIVATE MMX6_HOST_LAB_TEST_BAD_EXECUTION=1)
        endif()
        if(_lab_variant STREQUAL "pgxp")
            target_compile_definitions(${_lab_test} PRIVATE PSX_PGXP=1)
        endif()
        if(_lab_variant STREQUAL "legacy-settings-api")
            target_compile_definitions(${_lab_test} PRIVATE MMX6_HOST_LAB_TEST_LEGACY_SETTINGS_API=1)
        endif()
        target_compile_definitions(${_lab_test} PRIVATE MMX6_HOST_LAB_EXPECT_OFFER=${_lab_expected})
        add_test(NAME ${_lab_test} COMMAND ${_lab_test})
    endforeach()
    foreach(_portable_variant enabled disabled wrong-contract pgxp)
        set(_portable_test mmx6_portable_cpu_host_lab_${_portable_variant}_test)
        add_executable(${_portable_test} tests/test_mmx6_coop_portable_cpu_host_lab.c ${_lab_sdk_sources})
        target_include_directories(${_portable_test} PRIVATE tests src/mods "${PSXRECOMP_V4_ROOT}/runtime/include")
        set(_portable_expected 0)
        if(_portable_variant STREQUAL "enabled" AND WIN32 AND MINGW AND CMAKE_SIZEOF_VOID_P EQUAL 8
            AND CMAKE_SYSTEM_PROCESSOR MATCHES "^(AMD64|amd64|x86_64|X86_64)$"
            AND CMAKE_C_COMPILER_ID STREQUAL "Clang" AND CMAKE_C_COMPILER_VERSION VERSION_EQUAL "22.1.8")
            set(_portable_expected 1)
        endif()
        target_compile_definitions(${_portable_test} PRIVATE MMX6_ENABLE_LOOPBACK_HOST_LAB=1
            MMX6_ENABLE_PORTABLE_CPU_HOST_LAB=$<NOT:$<STREQUAL:${_portable_variant},disabled>>
            MMX6_HOST_LAB_EXPECT_OFFER=0
            MMX6_PORTABLE_CPU_HOST_LAB_EXPECT_OFFER=${_portable_expected})
        if(_portable_variant STREQUAL "wrong-contract")
            target_compile_definitions(${_portable_test} PRIVATE MMX6_HOST_LAB_TEST_BAD_EXECUTION=1)
        endif()
        if(_portable_variant STREQUAL "pgxp")
            target_compile_definitions(${_portable_test} PRIVATE PSX_PGXP=1)
        endif()
        add_test(NAME ${_portable_test} COMMAND ${_portable_test})
    endforeach()
    foreach(_release_variant enabled debug lab wrong-contract pgxp)
        set(_release_test mmx6_release_host_profile_${_release_variant}_test)
        add_executable(${_release_test} tests/test_mmx6_coop_release_host_profile.c ${_lab_sdk_sources})
        target_include_directories(${_release_test} PRIVATE tests src/mods "${PSXRECOMP_V4_ROOT}/runtime/include")
        set(_release_expected 0)
        if(_release_variant STREQUAL "enabled" AND WIN32 AND MINGW AND CMAKE_SIZEOF_VOID_P EQUAL 8
            AND CMAKE_SYSTEM_PROCESSOR MATCHES "^(AMD64|amd64|x86_64|X86_64)$"
            AND CMAKE_C_COMPILER_ID STREQUAL "Clang" AND CMAKE_C_COMPILER_VERSION VERSION_EQUAL "22.1.8")
            set(_release_expected 1)
        endif()
        target_compile_definitions(${_release_test} PRIVATE MMX6_HOST_LAB_EXPECT_OFFER=0
            MMX6_RELEASE_HOST_EXPECT_OFFER=${_release_expected}
            MMX6_ENABLE_LOOPBACK_HOST_LAB=$<STREQUAL:${_release_variant},lab>
            MMX6_ENABLE_PORTABLE_CPU_HOST_LAB=$<STREQUAL:${_release_variant},lab>)
        if(NOT _release_variant STREQUAL "debug")
            target_compile_definitions(${_release_test} PRIVATE PSX_NO_DEBUG_TOOLS)
        endif()
        if(_release_variant STREQUAL "wrong-contract")
            target_compile_definitions(${_release_test} PRIVATE MMX6_HOST_LAB_TEST_BAD_EXECUTION=1)
        endif()
        if(_release_variant STREQUAL "pgxp")
            target_compile_definitions(${_release_test} PRIVATE PSX_PGXP=1)
        endif()
        add_test(NAME ${_release_test} COMMAND ${_release_test})
    endforeach()
    if(Python3_Interpreter_FOUND)
        set(_mmx6_host_lab_contract_profile_args)
        if(MMX6_ENABLE_LOOPBACK_HOST_LAB)
            set(_mmx6_host_lab_contract_profile_args --execution-profile
                "${CMAKE_CURRENT_BINARY_DIR}/psx_execution/psx-runtime/profile.h")
        endif()
        add_test(NAME mmx6_host_lab_contract_test
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/mmx6_host_lab_contract.py"
                ${_mmx6_host_lab_contract_profile_args})
        unset(_mmx6_host_lab_contract_profile_args)
    endif()
    if(Python3_Interpreter_FOUND AND Python3_VERSION VERSION_GREATER_EQUAL 3.11)
        foreach(_mmx6_python_test test_coop_debug_protocol test_mmx6_coop_reference
                test_mmx6_coop_content test_mmx6_coop_audio_audit test_mmx6_audio_driver_audit
                test_prepare_mmx6_coop_playtest test_mmx6_coop_enemy_admission
                test_mmx6_coop_pair_options test_mmx6_build_provenance test_mmx6_world_trace
                test_coop_host_profile test_mmx6_coop_personal_menu
                test_mmx6_coop_personal_menu_runner test_mmx6_coop_contact
                test_mmx6_input_recording test_mmx6_content_coverage
                test_mmx6_coop_contact_runner test_mmx6_coop_owned_cleanup
                test_mmx6_coop_checkpoint test_mmx6_lab_earned_weapons test_mmx6_coop_intro_fixture test_mmx6_coop_private_effects
                test_mmx6_coop_private_pause test_mmx6_coop_published_input
                test_mmx6_native_zero_reference
                test_prepare_mmx6_input_replay test_qualify_mmx6_input_replay
                test_mmx6_coop_native_quit test_mmx6_coop_native_quit_runner
                test_mmx6_coop_hud_audit
                test_mmx6_reploid_rescue_audit test_mmx6_death_particle_audit
                test_mmx6_alternate_route_audit test_mmx6_coop_recycle_portal
                test_mmx6_recycle_terrain_audit test_mmx6_coop_native_reentry
                test_mmx6_coop_jump_audio
                test_mmx6_coop_native_reentry_runner test_qualify_mmx6_coop_jump_audio
                test_mmx6_coop_jump_audio_private
                test_mmx6_coop_jump_audio_pair
                test_mmx6_coop_body_audio
                test_mmx6_private_action_audio_audit
                test_mmx6_recycle_return_audit
                test_mmx6_body_audio_routes
                test_mmx6_coop_recycle_setup test_mmx6_coop_collision_boxes
                test_qualify_mmx6_coop_recycle_portal
                test_mmx6_coop_reploid059
                test_mmx6_native_player_init_audit
                test_mmx6_input_capture_hook)
            add_test(NAME mmx6_${_mmx6_python_test}
                COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/${_mmx6_python_test}.py")
        endforeach()
        add_test(NAME mmx6_coop_present_capture_test
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_coop_present_capture.py")
        add_test(NAME mmx6_coop_state_protocol_test
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_coop_state_protocol.py")
        add_test(NAME mmx6_coop_private_state_protocol_test
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_coop_private_state_protocol.py")
        add_test(NAME mmx6_coop_shared_hook_profile
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_mmx6_coop_shared_hook_profile.py")
        set(MMX6_X5_REFERENCE_REPO "" CACHE PATH "Optional local X5 Git repository for frozen-reference provenance checks")
        if(MMX6_X5_REFERENCE_REPO)
            add_test(NAME mmx6_coop_reference_provenance
                COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/build_mmx6_coop_reference.py"
                    --check --source-repo "${MMX6_X5_REFERENCE_REPO}" --root "${CMAKE_CURRENT_SOURCE_DIR}")
        endif()
    endif()
    add_executable(mmx6_startup_log_test tests/test_mmx6_startup_log.cpp
        src/mods/mmx6_startup_log.cpp)
    target_include_directories(mmx6_startup_log_test PRIVATE src/mods
        "${PSXRECOMP_V4_ROOT}/runtime/include")
    target_compile_definitions(mmx6_startup_log_test PRIVATE MMX6_STARTUP_LOG_TEST=1)
    target_link_libraries(mmx6_startup_log_test PRIVATE Threads::Threads)
    set(_startup_cases normal closed unavailable pointer-unavailable)
    if(WIN32)
        list(APPEND _startup_cases detached null invalid tee detached-pointer-unavailable)
    endif()
    foreach(_startup_case IN LISTS _startup_cases)
        add_test(NAME mmx6_startup_log_${_startup_case}_test
            COMMAND mmx6_startup_log_test "${CMAKE_CURRENT_BINARY_DIR}/startup-${_startup_case}-qa" "${_startup_case}")
        set_tests_properties(mmx6_startup_log_${_startup_case}_test PROPERTIES TIMEOUT 15)
    endforeach()


    find_package(Python3 QUIET COMPONENTS Interpreter)
    if(Python3_FOUND)
        add_test(NAME mmx6_vwait_contract
            COMMAND "${Python3_EXECUTABLE}"
                "${PSXRECOMP_V4_ROOT}/runtime/tests/native_wait_caller.py"
                --framework "${PSXRECOMP_V4_ROOT}" --cc "${CMAKE_C_COMPILER}"
                --generated "${CMAKE_CURRENT_SOURCE_DIR}/${GAME_GENERATED_DIR}"
                --contract "${CMAKE_CURRENT_SOURCE_DIR}/tests/vwait_contract.json")
        set_tests_properties(mmx6_vwait_contract PROPERTIES SKIP_RETURN_CODE 77 RUN_SERIAL TRUE)
    endif()
    add_executable(mmx6_frame_interpolation_test
        tests/test_mmx6_frame_interpolation.cpp
        "${PSXRECOMP_V4_ROOT}/runtime/src/render_pass_motion.c")
    # Keep the released replay implementation's semantic fixture; production
    # uses the no-replay producer and its independent scene tests below.
    target_compile_definitions(mmx6_frame_interpolation_test PRIVATE MMX6_LEGACY_FRAME_INTERPOLATION_FIXTURE=1)
    target_include_directories(mmx6_frame_interpolation_test PRIVATE
        "${PSXRECOMP_V4_ROOT}/runtime/include")
    add_test(NAME mmx6_frame_interpolation_test
        COMMAND "$<TARGET_FILE:mmx6_frame_interpolation_test>")

    add_executable(mmx6_native_presentation_test
        tests/test_mmx6_native_presentation.cpp
        "${PSXRECOMP_V4_ROOT}/runtime/src/presentation_scene.c"
        "${PSXRECOMP_V4_ROOT}/runtime/src/presentation_draw.c")
    target_include_directories(mmx6_native_presentation_test PRIVATE
        "${PSXRECOMP_V4_ROOT}/runtime/include")
    if(NOT MSVC)
        target_link_libraries(mmx6_native_presentation_test PRIVATE m)
    endif()
    add_test(NAME mmx6_native_presentation_test COMMAND mmx6_native_presentation_test)
    add_executable(mmx6_native_pair_test tests/test_mmx6_native_pair.cpp
        "${PSXRECOMP_V4_ROOT}/runtime/src/presentation_scene.c"
        "${PSXRECOMP_V4_ROOT}/runtime/src/presentation_draw.c")
    target_include_directories(mmx6_native_pair_test PRIVATE "${PSXRECOMP_V4_ROOT}/runtime/include")
    if(NOT MSVC)
        target_link_libraries(mmx6_native_pair_test PRIVATE m)
    endif()
    add_test(NAME mmx6_native_pair_test COMMAND mmx6_native_pair_test)


    # Seamless Loading preparation against an owner-supplied disc image:
    # -DMMX6_TEST_DISC=<path to "Mega Man X6 (USA) (v1.1).bin">.
    add_executable(mmx6_seamless_store_test
        tests/test_seamless_store.cpp
        src/mods/mmx6_seamless_store.cpp
        "${PSXRECOMP_V4_ROOT}/runtime/src/mod_resident.cpp"
        "${PSXRECOMP_V4_ROOT}/runtime/src/iso_reader.cpp"
        "${PSXRECOMP_V4_ROOT}/runtime/src/cue_sheet.cpp"
        "${PSXRECOMP_V4_ROOT}/runtime/src/psx_sha256.c")
    target_include_directories(mmx6_seamless_store_test PRIVATE
        src/mods
        "${PSXRECOMP_V4_ROOT}/runtime/include"
        "${PSXRECOMP_V4_ROOT}/recompiler/include")
    target_link_libraries(mmx6_seamless_store_test PRIVATE chdr-static)
    set(MMX6_TEST_DISC "" CACHE FILEPATH "Original SLUS-01395 v1.1 .bin for disc tests")
    if(MMX6_TEST_DISC)
        add_test(NAME mmx6_seamless_store_test
            COMMAND "$<TARGET_FILE:mmx6_seamless_store_test>" "${MMX6_TEST_DISC}"
                    "${CMAKE_CURRENT_BINARY_DIR}/seamless-test-cache")
    endif()

    add_executable(mmx6_adaptive_background_test tests/test_adaptive_background.c)
    target_include_directories(mmx6_adaptive_background_test PRIVATE "${PSXRECOMP_V4_ROOT}/runtime/include")
    add_test(NAME mmx6_adaptive_background_test COMMAND mmx6_adaptive_background_test)
    add_executable(mmx6_widescreen_view_test tests/test_widescreen_view.c)
    target_include_directories(mmx6_widescreen_view_test PRIVATE "${PSXRECOMP_V4_ROOT}/runtime/include")
    add_test(NAME mmx6_widescreen_view_test COMMAND mmx6_widescreen_view_test)

    add_executable(mmx6_coop_lifecycle_test
        tests/test_mmx6_coop_lifecycle.c src/mods/mmx6_coop_lifecycle.c)
    target_include_directories(mmx6_coop_lifecycle_test PRIVATE src/mods)
    add_test(NAME mmx6_coop_lifecycle_test COMMAND "$<TARGET_FILE:mmx6_coop_lifecycle_test>")

    add_executable(mmx6_coop_assets_test
        tests/test_mmx6_coop_assets.c src/mods/mmx6_coop_assets.c)
    target_include_directories(mmx6_coop_assets_test PRIVATE src/mods)
    add_test(NAME mmx6_coop_assets_test COMMAND "$<TARGET_FILE:mmx6_coop_assets_test>")

    add_executable(mmx6_coop_intro_target_test tests/test_mmx6_coop_intro_target.c
        src/mods/mmx6_coop_lifecycle.c "${PSXRECOMP_V4_ROOT}/runtime/src/mod_function_replacements.c")
    target_include_directories(mmx6_coop_intro_target_test PRIVATE src/mods
        "${PSXRECOMP_V4_ROOT}/runtime/include")
    if(MSVC)
        target_compile_options(mmx6_coop_intro_target_test PRIVATE /O2 /Gy /Gw)
        target_link_options(mmx6_coop_intro_target_test PRIVATE /OPT:REF)
    else()
        target_compile_options(mmx6_coop_intro_target_test PRIVATE -O2 -ffunction-sections -fdata-sections)
        if(APPLE)
            target_link_options(mmx6_coop_intro_target_test PRIVATE -Wl,-dead_strip)
        else()
            target_link_options(mmx6_coop_intro_target_test PRIVATE -Wl,--gc-sections)
        endif()
    endif()
    add_test(NAME mmx6_coop_intro_target_test COMMAND "$<TARGET_FILE:mmx6_coop_intro_target_test>")

    add_executable(mmx6_coop_northpole_ice_test tests/test_mmx6_coop_northpole_ice.c
        src/mods/mmx6_coop_lifecycle.c "${PSXRECOMP_V4_ROOT}/runtime/src/mod_function_replacements.c")
    target_include_directories(mmx6_coop_northpole_ice_test PRIVATE src/mods
        "${PSXRECOMP_V4_ROOT}/runtime/include")
    if(MSVC)
        target_compile_options(mmx6_coop_northpole_ice_test PRIVATE /O2 /Gy /Gw)
        target_link_options(mmx6_coop_northpole_ice_test PRIVATE /OPT:REF)
    else()
        target_compile_options(mmx6_coop_northpole_ice_test PRIVATE -O2 -ffunction-sections -fdata-sections)
        if(APPLE)
            target_link_options(mmx6_coop_northpole_ice_test PRIVATE -Wl,-dead_strip)
        else()
            target_link_options(mmx6_coop_northpole_ice_test PRIVATE -Wl,--gc-sections)
        endif()
    endif()
    add_test(NAME mmx6_coop_northpole_ice_test COMMAND "$<TARGET_FILE:mmx6_coop_northpole_ice_test>")
    set_tests_properties(mmx6_coop_northpole_ice_test PROPERTIES SKIP_RETURN_CODE 77)

    # Compile the actual trusted plugin into an isolated guest-memory fixture.
    # Dead gameplay entry points are discarded; both developer and production
    # builds must reject the one-sided debug channel during netplay.
    foreach(_mmx6_diag_variant debug production)
        set(_mmx6_diag_target mmx6_coop_diagnostics_${_mmx6_diag_variant}_test)
        add_executable(${_mmx6_diag_target} tests/test_mmx6_coop_diagnostics.c)
        target_include_directories(${_mmx6_diag_target} PRIVATE src/mods
            "${PSXRECOMP_V4_ROOT}/runtime/include")
        if(_mmx6_diag_variant STREQUAL "production")
            target_compile_definitions(${_mmx6_diag_target} PRIVATE PSX_NO_DEBUG_TOOLS)
        endif()
        if(MSVC)
            target_compile_options(${_mmx6_diag_target} PRIVATE /Gy /Gw)
            target_link_options(${_mmx6_diag_target} PRIVATE /OPT:REF)
        else()
            target_compile_options(${_mmx6_diag_target} PRIVATE -ffunction-sections -fdata-sections)
            if(APPLE)
                target_link_options(${_mmx6_diag_target} PRIVATE -Wl,-dead_strip)
            else()
                target_link_options(${_mmx6_diag_target} PRIVATE -Wl,--gc-sections)
            endif()
        endif()
        add_test(NAME ${_mmx6_diag_target} COMMAND "$<TARGET_FILE:${_mmx6_diag_target}>")
    endforeach()

    foreach(_mmx6_visual_kind private_effects private_views hud resource_admission recycle_portal reentry_retirement jump_audio session_resources)
      foreach(_mmx6_effects_variant debug production)
        set(_mmx6_effects_target mmx6_coop_${_mmx6_visual_kind}_${_mmx6_effects_variant}_test)
        add_executable(${_mmx6_effects_target} tests/test_mmx6_coop_${_mmx6_visual_kind}.c
            src/mods/mmx6_coop_lifecycle.c src/mods/mmx6_coop_assets.c
            "${PSXRECOMP_V4_ROOT}/runtime/src/psx_sha256.c")
        target_include_directories(${_mmx6_effects_target} PRIVATE src/mods
            "${PSXRECOMP_V4_ROOT}/runtime/include")
        if(_mmx6_visual_kind STREQUAL "session_resources")
            target_sources(${_mmx6_effects_target} PRIVATE tests/mmx6_coop_session_sdk_fixture.c
                "${PSXRECOMP_V4_ROOT}/runtime/src/kernel_patch_ranges.c"
                "${PSXRECOMP_V4_ROOT}/runtime/src/psx_ram_geometry.c")
            target_include_directories(${_mmx6_effects_target} PRIVATE
                "${PSXRECOMP_V4_ROOT}/runtime/src")
        endif()
        if(_mmx6_visual_kind STREQUAL "recycle_portal" OR _mmx6_visual_kind STREQUAL "private_views")
            target_sources(${_mmx6_effects_target} PRIVATE
                "${PSXRECOMP_V4_ROOT}/runtime/src/mod_function_replacements.c")
        endif()
        if(_mmx6_effects_variant STREQUAL "production")
            target_compile_definitions(${_mmx6_effects_target} PRIVATE PSX_NO_DEBUG_TOOLS)
        endif()
        if(MSVC)
            target_compile_options(${_mmx6_effects_target} PRIVATE /O2 /Gy /Gw)
            target_link_options(${_mmx6_effects_target} PRIVATE /OPT:REF)
        else()
            target_compile_options(${_mmx6_effects_target} PRIVATE -O2 -ffunction-sections -fdata-sections)
            if(MINGW AND (_mmx6_visual_kind STREQUAL "hud" OR _mmx6_visual_kind STREQUAL "private_views"))
                # These C fixtures embed the plugin but own only the exercised
                # call graph. Win64 unwind roots must not retain unrelated
                # bootstrap functions when a diagnostic is compiled atO0.
                target_compile_options(${_mmx6_effects_target} PRIVATE
                    -fno-asynchronous-unwind-tables -fno-unwind-tables)
            endif()
            if(APPLE)
                target_link_options(${_mmx6_effects_target} PRIVATE -Wl,-dead_strip)
            else()
                target_link_options(${_mmx6_effects_target} PRIVATE -Wl,--gc-sections)
            endif()
        endif()
        add_test(NAME ${_mmx6_effects_target} COMMAND "$<TARGET_FILE:${_mmx6_effects_target}>")
        if(_mmx6_visual_kind STREQUAL "recycle_portal")
            set_tests_properties(${_mmx6_effects_target} PROPERTIES SKIP_RETURN_CODE 77)
        endif()
      endforeach()
    endforeach()

    if(Python3_Interpreter_FOUND AND Python3_VERSION VERSION_GREATER_EQUAL 3.11)
        add_test(NAME mmx6_coop_session_resources_source_test
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/test_mmx6_coop_session_resources.py"
                --sdk-root "${PSXRECOMP_V4_ROOT}")
        add_test(NAME mmx6_coop_session_peripheral_rejection_test
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/test_mmx6_coop_session_peripheral_rejection.py"
                --debug "$<TARGET_FILE:mmx6_coop_session_resources_debug_test>"
                --production "$<TARGET_FILE:mmx6_coop_session_resources_production_test>")
        set_tests_properties(mmx6_coop_session_peripheral_rejection_test PROPERTIES TIMEOUT 90)
    endif()

    foreach(_mmx6_header_variant debug production)
        set(_mmx6_header_target mmx6_coop_jump_audio_header_${_mmx6_header_variant}_test)
        add_executable(${_mmx6_header_target} tests/test_mmx6_coop_jump_audio_header.c
            src/mods/mmx6_coop_jump_audio.c)
        target_include_directories(${_mmx6_header_target} PRIVATE src/mods)
        if(_mmx6_header_variant STREQUAL "production")
            target_compile_definitions(${_mmx6_header_target} PRIVATE PSX_NO_DEBUG_TOOLS)
        endif()
        add_test(NAME ${_mmx6_header_target} COMMAND "$<TARGET_FILE:${_mmx6_header_target}>")
        if(Python3_Interpreter_FOUND AND Python3_VERSION VERSION_GREATER_EQUAL 3.11)
            set(_mmx6_records_test mmx6_coop_private_audio_records_${_mmx6_header_variant}_test)
            add_test(NAME ${_mmx6_records_test}
                COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/test_mmx6_coop_private_audio_records.py"
                    "$<TARGET_FILE:${_mmx6_header_target}>" --scratch-root "${CMAKE_BINARY_DIR}/private-audio-records")
            set_tests_properties(${_mmx6_records_test} PROPERTIES SKIP_RETURN_CODE 77 TIMEOUT 90)
        endif()
    endforeach()

    add_executable(mmx6_coop_roster_test tests/test_mmx6_coop_roster.c
        src/mods/mmx6_coop_roster.c)
    target_include_directories(mmx6_coop_roster_test PRIVATE src/mods)
    add_test(NAME mmx6_coop_roster_test COMMAND "$<TARGET_FILE:mmx6_coop_roster_test>")
    add_executable(mmx6_coop_resources_test tests/test_mmx6_coop_resources.c
        src/mods/mmx6_coop_resources.c src/mods/mmx6_coop_roster.c
        src/mods/mmx6_coop_assets.c)
    target_include_directories(mmx6_coop_resources_test PRIVATE src/mods)
    add_test(NAME mmx6_coop_resources_test COMMAND "$<TARGET_FILE:mmx6_coop_resources_test>")

    foreach(_mmx6_checkpoint_variant debug production agreed_lab)
        set(_mmx6_checkpoint_target mmx6_coop_checkpoint_${_mmx6_checkpoint_variant}_test)
        add_executable(${_mmx6_checkpoint_target} tests/test_mmx6_coop_checkpoint.c
            src/mods/mmx6_coop_lifecycle.c src/mods/mmx6_coop_assets.c
            "${PSXRECOMP_V4_ROOT}/runtime/src/psx_sha256.c")
        target_include_directories(${_mmx6_checkpoint_target} PRIVATE src/mods
            "${PSXRECOMP_V4_ROOT}/runtime/include")
        if(_mmx6_checkpoint_variant STREQUAL "production")
            target_compile_definitions(${_mmx6_checkpoint_target} PRIVATE PSX_NO_DEBUG_TOOLS)
        endif()
        if(_mmx6_checkpoint_variant STREQUAL "agreed_lab")
            # Source-backed pre-door coverage additionally reads the external
            # MMX6_BEFORE_DOORS_RAM and MMX6_PORTAL_SETUP_RAM fixtures;
            # no original disc data is bundled.
            target_compile_definitions(${_mmx6_checkpoint_target} PRIVATE MMX6_ENABLE_LOOPBACK_HOST_LAB=1)
        endif()
        if(MSVC)
            target_compile_options(${_mmx6_checkpoint_target} PRIVATE /O2 /Gy /Gw)
            target_link_options(${_mmx6_checkpoint_target} PRIVATE /OPT:REF)
        else()
            target_compile_options(${_mmx6_checkpoint_target} PRIVATE -O2 -ffunction-sections -fdata-sections)
            if(APPLE)
                target_link_options(${_mmx6_checkpoint_target} PRIVATE -Wl,-dead_strip)
            else()
                target_link_options(${_mmx6_checkpoint_target} PRIVATE -Wl,--gc-sections)
            endif()
        endif()
        add_test(NAME ${_mmx6_checkpoint_target} COMMAND "$<TARGET_FILE:${_mmx6_checkpoint_target}>")
        set_tests_properties(${_mmx6_checkpoint_target} PROPERTIES SKIP_RETURN_CODE 77)
    endforeach()

    if(EXISTS "${PSXRECOMP_V4_ROOT}/runtime/include/session_diagnostics.h" AND
            Python3_Interpreter_FOUND AND Python3_VERSION VERSION_GREATER_EQUAL 3.11)
        find_package(Threads REQUIRED)
        foreach(_mmx6_capture_variant debug production)
            set(_mmx6_capture_target mmx6_input_capture_${_mmx6_capture_variant}_test)
            add_executable(${_mmx6_capture_target} tests/test_mmx6_input_capture.cpp
                "${PSXRECOMP_V4_ROOT}/runtime/src/psx_sha256.c")
            target_include_directories(${_mmx6_capture_target} PRIVATE src/mods
                "${PSXRECOMP_V4_ROOT}/runtime/include")
            target_link_libraries(${_mmx6_capture_target} PRIVATE Threads::Threads)
            if(_mmx6_capture_variant STREQUAL "production")
                target_compile_definitions(${_mmx6_capture_target} PRIVATE PSX_NO_DEBUG_TOOLS)
            endif()
            if(MSVC)
                target_compile_options(${_mmx6_capture_target} PRIVATE /O2 /UNDEBUG /fp:strict)
            else()
                target_compile_options(${_mmx6_capture_target} PRIVATE -O3 -UNDEBUG -ffp-contract=off)
            endif()
            add_test(NAME ${_mmx6_capture_target}
                COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/test_mmx6_input_capture.py"
                    --fixture "$<TARGET_FILE:${_mmx6_capture_target}>"
                    --output "${CMAKE_CURRENT_BINARY_DIR}/input-capture-fixtures/${_mmx6_capture_variant}")
        endforeach()
        foreach(_mmx6_replay_variant debug production)
            foreach(_mmx6_replay_kind input native)
                set(_mmx6_replay_target mmx6_${_mmx6_replay_kind}_replay_${_mmx6_replay_variant}_test)
                add_executable(${_mmx6_replay_target}
                    tests/test_mmx6_${_mmx6_replay_kind}_replay.cpp
                    "${PSXRECOMP_V4_ROOT}/runtime/src/psx_sha256.c")
                target_include_directories(${_mmx6_replay_target} PRIVATE src/mods
                    "${PSXRECOMP_V4_ROOT}/runtime/include")
                target_link_libraries(${_mmx6_replay_target} PRIVATE Threads::Threads)
                if(_mmx6_replay_variant STREQUAL "production")
                    target_compile_definitions(${_mmx6_replay_target} PRIVATE PSX_NO_DEBUG_TOOLS)
                endif()
                if(MSVC)
                    target_compile_options(${_mmx6_replay_target} PRIVATE /O2 /UNDEBUG /fp:strict)
                else()
                    target_compile_options(${_mmx6_replay_target} PRIVATE -O3 -UNDEBUG -ffp-contract=off)
                endif()
                if(_mmx6_replay_kind STREQUAL "native")
                    add_test(NAME ${_mmx6_replay_target}
                        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/test_mmx6_native_replay.py"
                            --fixture "$<TARGET_FILE:${_mmx6_replay_target}>"
                            --output "${CMAKE_CURRENT_BINARY_DIR}/native-replay-fixtures/${_mmx6_replay_variant}")
                else()
                    add_test(NAME ${_mmx6_replay_target} COMMAND "$<TARGET_FILE:${_mmx6_replay_target}>")
                endif()
            endforeach()
        endforeach()
        add_test(NAME mmx6_native_input_hook_emission_test
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_mmx6_input_capture_hook.py"
                --unit "${CMAKE_CURRENT_SOURCE_DIR}/${GAME_GENERATED_DIR}/SLUS_013.95_full_00.c")
        add_test(NAME mmx6_native_dialogue_palette_hook_emission_test
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_mmx6_dialogue_palette_hook.py"
                --unit "${CMAKE_CURRENT_SOURCE_DIR}/${GAME_GENERATED_DIR}/SLUS_013.95_full_08.c")
    endif()

    # These tests require the modern host-state API. Legacy SDK builds retain
    # the disabled snapshot/network-state capability and remain buildable.
    if(EXISTS "${PSXRECOMP_V4_ROOT}/runtime/include/mod_snapshot.h")
        foreach(_mmx6_state_variant debug production)
            set(_mmx6_state_target mmx6_coop_snapshot_${_mmx6_state_variant}_test)
            add_executable(${_mmx6_state_target} tests/test_mmx6_coop_snapshot.c
                src/mods/mmx6_coop_lifecycle.c src/mods/mmx6_coop_assets.c
                "${PSXRECOMP_V4_ROOT}/runtime/src/psx_sha256.c")
            target_include_directories(${_mmx6_state_target} PRIVATE src/mods
                "${PSXRECOMP_V4_ROOT}/runtime/include")
            if(_mmx6_state_variant STREQUAL "production")
                target_compile_definitions(${_mmx6_state_target} PRIVATE PSX_NO_DEBUG_TOOLS)
            endif()
            if(MSVC)
                target_compile_options(${_mmx6_state_target} PRIVATE /O2 /Gy /Gw)
                target_link_options(${_mmx6_state_target} PRIVATE /OPT:REF)
            else()
                target_compile_options(${_mmx6_state_target} PRIVATE -O2 -ffunction-sections -fdata-sections)
                if(APPLE)
                    target_link_options(${_mmx6_state_target} PRIVATE -Wl,-dead_strip)
                else()
                    target_link_options(${_mmx6_state_target} PRIVATE -Wl,--gc-sections)
                endif()
            endif()
            add_test(NAME ${_mmx6_state_target} COMMAND "$<TARGET_FILE:${_mmx6_state_target}>")
        endforeach()
    endif()

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

    # This fixture resolves catalog patches. The diagnostics observer is a
    # runtime service, exercised by its own actual-module fixtures and the game;
    # its constructors/consumers require the engine's session and memory APIs.
    set(MMX6_CATALOG_RESOLVER_SOURCES ${GAME_MOD_RESOLVER_SOURCES})
    list(REMOVE_ITEM MMX6_CATALOG_RESOLVER_SOURCES
        "${CMAKE_CURRENT_SOURCE_DIR}/src/mods/mmx6_diagnostics.cpp")
    add_executable(mmx6_preloaded_mods_test
        tests/test_preloaded_mods.cpp
        ${MMX6_CATALOG_RESOLVER_SOURCES}
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

    # Seamless Loading compatibility matrix over every bundled mod feature.
    add_executable(mmx6_seamless_mod_matrix_test
        tests/test_seamless_mod_matrix.cpp
        ${MMX6_CATALOG_RESOLVER_SOURCES}
        "${PSXRECOMP_V4_ROOT}/runtime/src/mod_packages.cpp"
        "${PSXRECOMP_V4_ROOT}/runtime/src/crc32.c"
        "${PSXRECOMP_V4_ROOT}/runtime/src/psx_sha256.c"
    )
    target_include_directories(mmx6_seamless_mod_matrix_test PRIVATE
        src/mods
        "${PSXRECOMP_V4_ROOT}/runtime/include"
        "${PSXRECOMP_V4_ROOT}/recompiler/lib/toml11"
    )
    add_test(
        NAME mmx6_seamless_mod_matrix_test
        COMMAND "$<TARGET_FILE:mmx6_seamless_mod_matrix_test>"
                "${MMX6_PRELOADED_MODS}"
    )

    find_package(Python3 REQUIRED COMPONENTS Interpreter)

    add_test(
        NAME mmx6_release_config_test
        COMMAND "${Python3_EXECUTABLE}"
                "${CMAKE_CURRENT_SOURCE_DIR}/tools/test_release_config.py"
    )

    # Clean-room CD-ROM EDC/ECC recompute (tools/edc_ecc.py) â€” the Tweaks apply
    # path's replacement for the former GPLv3 error_recalc.exe. Pure Python, no
    # disc image needed: the suite checks the Reed-Solomon syndromes directly.
    add_test(
        NAME mmx6_edc_ecc_test
        COMMAND "${Python3_EXECUTABLE}"
                "${CMAKE_CURRENT_SOURCE_DIR}/tools/test_edc_ecc.py"
    )

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
    set_tests_properties(mmx6_preloaded_mods_test mmx6_seamless_mod_matrix_test
        mmx6_tweaks_hooks_test mmx6_tweaks_timing_runtime_test
        PROPERTIES TIMEOUT 120)
    get_property(_mmx6_test_targets DIRECTORY PROPERTY BUILDSYSTEM_TARGETS)
    foreach(_target IN LISTS _mmx6_test_targets)
        if(_target MATCHES "^mmx6_.*test$")
            get_target_property(_sources ${_target} SOURCES)
            if("${_sources}" MATCHES "tests/test_mmx6_coop_(intro_target|diagnostics|private_effects|private_views|hud|checkpoint|snapshot|resource_admission|recycle_portal|reentry_retirement|jump_audio|session_resources)[.]c")
                target_sources(${_target} PRIVATE src/mods/mmx6_coop_roster.c
                    src/mods/mmx6_coop_resources.c src/mods/mmx6_coop_jump_audio.c
                    tests/mmx6_coop_private_view_sdk_fixture.c)
                if(NOT "${_sources}" MATCHES "src/mods/mmx6_coop_assets[.]c")
                    target_sources(${_target} PRIVATE src/mods/mmx6_coop_assets.c)
                endif()
            endif()
            if("${_sources}" MATCHES "mod_packages[.]cpp")
                target_sources(${_target} PRIVATE tests/mod_media_stub.cpp)
            endif()
        endif()
    endforeach()
endif()
