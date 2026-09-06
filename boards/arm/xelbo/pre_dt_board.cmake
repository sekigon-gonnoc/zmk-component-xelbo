#
# Copyright (c) 2025 The ZMK Contributors
# SPDX-License-Identifier: MIT
#

# Suppresses duplicate unit-address warning at build time for power, clock, acl and flash-controller
# https://docs.zephyrproject.org/latest/build/dts/intro-input-output.html
list(APPEND EXTRA_DTC_FLAGS "-Wno-unique_unit_address_if_enabled")

if(DEFINED PINMAP_PROFILE AND PINMAP_PROFILE STREQUAL "xiao_to_xelbo")
	if(NOT PINMAP_PROFILE STREQUAL "xiao_to_xelbo")
		message(FATAL_ERROR "Unsupported PINMAP_PROFILE='${PINMAP_PROFILE}'. Supported: xiao_to_xelbo")
	endif()

	set(_pinmap_source_root "${PINMAP_SOURCE_ROOT}")
	if(_pinmap_source_root STREQUAL "" AND DEFINED SHIELD)
		set(_shield_dir_var "SHIELD_DIR_${SHIELD}")
		if(DEFINED ${_shield_dir_var})
			set(_pinmap_source_root "${${_shield_dir_var}}")
		endif()
	endif()

	if(_pinmap_source_root STREQUAL "")
		message(FATAL_ERROR "PINMAP_PROFILE=xiao_to_xelbo could not determine source shield directory. Set PINMAP_SOURCE_ROOT explicitly.")
	endif()

	set(_pinmap_output_root "${PINMAP_OUTPUT_ROOT}")
	if(_pinmap_output_root STREQUAL "")
		# Persist in place by default for one-shot west build workflows.
		set(_pinmap_output_root "${_pinmap_source_root}")
	endif()

	find_package(Python3 COMPONENTS Interpreter REQUIRED)
	set(_pinmap_script "${CMAKE_CURRENT_LIST_DIR}/../../../scripts/convert_pins.py")
	set(_pinmap_extra_args "")
	if(DEFINED PINMAP_PERSIST_SOURCE_BASE AND NOT PINMAP_PERSIST_SOURCE_BASE STREQUAL "")
		list(APPEND _pinmap_extra_args --persist-source-base "${PINMAP_PERSIST_SOURCE_BASE}")
	endif()
	if(DEFINED PINMAP_PERSIST_TARGET_BASE AND NOT PINMAP_PERSIST_TARGET_BASE STREQUAL "")
		list(APPEND _pinmap_extra_args --persist-target-base "${PINMAP_PERSIST_TARGET_BASE}")
	endif()
	if(DEFINED PINMAP_PERSIST_REQUIRES_BOARD AND NOT PINMAP_PERSIST_REQUIRES_BOARD STREQUAL "")
		list(APPEND _pinmap_extra_args --persist-requires-board "${PINMAP_PERSIST_REQUIRES_BOARD}")
	endif()

	execute_process(
		COMMAND "${Python3_EXECUTABLE}" "${_pinmap_script}"
						"${_pinmap_source_root}"
						"${_pinmap_output_root}"
						${_pinmap_extra_args}
		RESULT_VARIABLE _pinmap_result
		OUTPUT_VARIABLE _pinmap_stdout
		ERROR_VARIABLE _pinmap_stderr
	)

	if(NOT _pinmap_result EQUAL 0)
		message(FATAL_ERROR
			"PINMAP_CONVERT failed (code=${_pinmap_result})\n"
			"stdout:\n${_pinmap_stdout}\n"
			"stderr:\n${_pinmap_stderr}\n")
	endif()

	if(NOT _pinmap_stdout STREQUAL "")
		message(STATUS "${_pinmap_stdout}")
	endif()
	message(STATUS "PINMAP profile '${PINMAP_PROFILE}' persist applied before DTS: source=${_pinmap_source_root} output=${_pinmap_output_root}")
endif()