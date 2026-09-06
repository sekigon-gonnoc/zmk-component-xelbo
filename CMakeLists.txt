# SPDX-License-Identifier: MIT

# This repository contributes custom boards/shields for ZMK builds.

cmake_minimum_required(VERSION 3.20)

set(PINMAP_PROFILE "" CACHE STRING "Pin conversion profile (xiao_to_xelbo)")
set(PINMAP_SOURCE_ROOT "" CACHE PATH "Source shield directory to convert (optional)")
set(PINMAP_OUTPUT_ROOT "" CACHE PATH "Output directory for converted files (optional)")
set(PINMAP_PERSIST_SOURCE_BASE "" CACHE STRING "Original shield base name to rewrite in persist mode")
set(PINMAP_PERSIST_TARGET_BASE "" CACHE STRING "Generated shield base name in persist mode")
set(PINMAP_PERSIST_REQUIRES_BOARD "" CACHE STRING "Board name for generated shield metadata in persist mode")

if(PINMAP_PROFILE STREQUAL "xiao_to_xelbo")
	if(NOT PINMAP_PROFILE STREQUAL "xiao_to_xelbo")
		message(FATAL_ERROR "Unsupported PINMAP_PROFILE='${PINMAP_PROFILE}'. Supported: xiao_to_xelbo")
	endif()

	if(PINMAP_SOURCE_ROOT STREQUAL "")
		if(DEFINED SHIELD)
			set(_shield_dir_var "SHIELD_DIR_${SHIELD}")
			if(DEFINED ${_shield_dir_var})
				set(PINMAP_SOURCE_ROOT "${${_shield_dir_var}}")
			endif()
		endif()
	endif()

	if(PINMAP_SOURCE_ROOT STREQUAL "")
		message(FATAL_ERROR "PINMAP_PROFILE=xiao_to_xelbo requires PINMAP_SOURCE_ROOT to be set or discoverable from SHIELD")
	endif()

	find_package(Python3 COMPONENTS Interpreter REQUIRED)

	set(_pinmap_output_root "${PINMAP_OUTPUT_ROOT}")
	if(_pinmap_output_root STREQUAL "")
		set(_pinmap_output_root "${PINMAP_SOURCE_ROOT}")
	endif()

	if(_pinmap_output_root STREQUAL PINMAP_SOURCE_ROOT)
		message(STATUS "PINMAP profile '${PINMAP_PROFILE}' in-place conversion is handled in pre_dt_board.cmake")
	else()
		set(_pinmap_script "${CMAKE_CURRENT_LIST_DIR}/scripts/convert_pins.py")
		set(_pinmap_extra_args "")
		if(NOT PINMAP_PERSIST_SOURCE_BASE STREQUAL "")
			list(APPEND _pinmap_extra_args --persist-source-base "${PINMAP_PERSIST_SOURCE_BASE}")
		endif()
		if(NOT PINMAP_PERSIST_TARGET_BASE STREQUAL "")
			list(APPEND _pinmap_extra_args --persist-target-base "${PINMAP_PERSIST_TARGET_BASE}")
		endif()
		if(NOT PINMAP_PERSIST_REQUIRES_BOARD STREQUAL "")
			list(APPEND _pinmap_extra_args --persist-requires-board "${PINMAP_PERSIST_REQUIRES_BOARD}")
		endif()

		execute_process(
			COMMAND "${Python3_EXECUTABLE}" "${_pinmap_script}"
						"${PINMAP_SOURCE_ROOT}"
						"${_pinmap_output_root}"
						${_pinmap_extra_args}
			RESULT_VARIABLE _pinmap_result
			OUTPUT_VARIABLE _pinmap_stdout
			ERROR_VARIABLE _pinmap_stderr
		)

		if(NOT _pinmap_result EQUAL 0)
			message(FATAL_ERROR
				"Pin conversion failed (code=${_pinmap_result})\n"
				"stdout:\n${_pinmap_stdout}\n"
				"stderr:\n${_pinmap_stderr}\n")
		endif()

		if(NOT _pinmap_stdout STREQUAL "")
			message(STATUS "${_pinmap_stdout}")
		endif()

		message(STATUS "PINMAP profile '${PINMAP_PROFILE}' persist output written to: ${_pinmap_output_root}")
	endif()
endif()


zephyr_library()
zephyr_library_sources(src/gpio_ws2812.c)
