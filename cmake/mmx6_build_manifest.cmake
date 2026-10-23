include("${PSXRECOMP_V4_ROOT}/cmake/psx_build_manifest.cmake")

function(mmx6_register_build_manifests)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    set(_roots "game=${CMAKE_SOURCE_DIR}" "build=${CMAKE_BINARY_DIR}"
        "sdk=${PSXRECOMP_V4_ROOT}"
        # Generated game sources may be a junction onto the scratch drive.
        # Give that exact declared tree its own logical root after resolution.
        "game-generated=${CMAKE_SOURCE_DIR}/${GAME_GENERATED_DIR}")
    set(_repositories game "${CMAKE_SOURCE_DIR}" sdk "${PSXRECOMP_V4_ROOT}")
    set(_headers "${CMAKE_SOURCE_DIR}/src" "${CMAKE_SOURCE_DIR}/${GAME_GENERATED_DIR}"
        "${PSXRECOMP_V4_ROOT}/runtime/include")
    set(_inputs "${CMAKE_SOURCE_DIR}/CMakeLists.txt" "${CMAKE_CURRENT_FUNCTION_LIST_FILE}"
        "${CMAKE_SOURCE_DIR}/tools/mmx6_build_provenance.py"
        "${PSXRECOMP_V4_ROOT}/third_party/deps.manifest")
    foreach(_dependency ui net rb)
        if(_dependency STREQUAL "ui")
            set(_path "${RECOMP_UI_ROOT}")
        elseif(_dependency STREQUAL "net")
            set(_path "${RECOMP_NET_ROOT}")
        else()
            set(_path "${RECOMP_RBENGINE_ROOT}")
        endif()
        if(_path)
            list(APPEND _roots "${_dependency}=${_path}")
            list(APPEND _repositories ${_dependency} "${_path}")
            list(APPEND _headers "${_path}/src")
            if(IS_DIRECTORY "${_path}/include")
                list(APPEND _headers "${_path}/include")
            endif()
            list(APPEND _inputs "${_path}/CMakeLists.txt")
        endif()
    endforeach()
    # Recipes affect dependency configuration and generated runtime bodies.
    file(GLOB _sdk_recipes CONFIGURE_DEPENDS "${PSXRECOMP_V4_ROOT}/cmake/*.cmake"
        "${PSXRECOMP_V4_ROOT}/runtime/*.cmake")
    list(APPEND _inputs ${_sdk_recipes})
    get_filename_component(_compiler_bin "${CMAKE_C_COMPILER}" DIRECTORY)
    get_filename_component(_toolchain "${_compiler_bin}/.." ABSOLUTE)
    list(APPEND _roots "toolchain=${_toolchain}")
    foreach(_source_dir psx_libchdr_SOURCE_DIR psx_libwebp_SOURCE_DIR libjuice_SOURCE_DIR)
        if(DEFINED ${_source_dir} AND IS_DIRECTORY "${${_source_dir}}")
            list(APPEND _roots "dep-${_source_dir}=${${_source_dir}}")
        endif()
    endforeach()
    foreach(_target psx-runtime psx-runtime-pgxp psx-cosim psx-cosim-pgxp)
        if(NOT TARGET ${_target})
            continue()
        endif()
        set(_dir "${CMAKE_BINARY_DIR}/mmx6-build-provenance/${_target}")
        set(_provenance "${_dir}/provenance.json")
        set(_arguments "")
        foreach(_pair IN LISTS _roots)
            list(APPEND _arguments --root "${_pair}")
        endforeach()
        list(LENGTH _repositories _count)
        math(EXPR _last "${_count}-1")
        foreach(_index RANGE 0 ${_last} 2)
            math(EXPR _next "${_index}+1")
            list(GET _repositories ${_index} _label)
            list(GET _repositories ${_next} _path)
            list(APPEND _arguments --repository "${_label}=${_path}")
        endforeach()
        add_custom_target(${_target}-build-provenance
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/tools/mmx6_build_provenance.py"
                --output "${_provenance}" --cache "${CMAKE_BINARY_DIR}/CMakeCache.txt" ${_arguments}
            BYPRODUCTS "${_provenance}" VERBATIM)
        psxrecomp_build_manifest(${_target} PYTHON "${Python3_EXECUTABLE}"
            ROOTS ${_roots} INPUTS ${_inputs} "${_provenance}"
            HEADER_DIRECTORIES ${_headers})
        # The SDK creates its manifest target at the directory's deferred edge.
        cmake_language(EVAL CODE "cmake_language(DEFER CALL add_dependencies ${_target}-build-manifest ${_target}-build-provenance)")
        if(TARGET ${_target}_app_icon)
            cmake_language(EVAL CODE "cmake_language(DEFER CALL add_dependencies ${_target}-build-manifest ${_target}_app_icon)")
        endif()
        target_sources(${_target} PRIVATE "${CMAKE_SOURCE_DIR}/src/mmx6_build_manifest.c")
    endforeach()
endfunction()
