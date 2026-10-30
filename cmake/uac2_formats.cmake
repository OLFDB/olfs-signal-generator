# SPDX-License-Identifier: Apache-2.0
set(olf_uac_dir "${ZEPHYR_BASE}/subsys/usb/device_next/class")
set(olf_uac_script "${CMAKE_CURRENT_LIST_DIR}/../scripts/prepare_uac2_formats.py")
set(olf_uac_header "${CMAKE_CURRENT_LIST_DIR}/../src/uac2_formats.h")
set(olf_uac_output "${PROJECT_BINARY_DIR}/generated")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
  "${olf_uac_dir}/usbd_uac2.c" "${olf_uac_dir}/usbd_uac2_macros.h"
  "${olf_uac_script}" "${olf_uac_header}")
execute_process(COMMAND "${Python3_EXECUTABLE}" "${olf_uac_script}"
  "${olf_uac_dir}/usbd_uac2.c" "${olf_uac_dir}/usbd_uac2_macros.h"
  "${olf_uac_header}" "${olf_uac_output}"
  RESULT_VARIABLE olf_uac_result ERROR_VARIABLE olf_uac_error)
if(NOT olf_uac_result EQUAL 0)
  message(FATAL_ERROR "Cannot prepare 16/24-bit UAC2 class: ${olf_uac_error}")
endif()
set(olf_uac_target subsys__usb__device_next)
get_target_property(olf_uac_sources ${olf_uac_target} SOURCES)
set(olf_uac_new_sources)
set(olf_uac_replaced 0)
foreach(olf_source IN LISTS olf_uac_sources)
  if(olf_source MATCHES "(^|/)usbd_uac2\\.c$")
    list(APPEND olf_uac_new_sources "${olf_uac_output}/usbd_uac2_formats.c")
    math(EXPR olf_uac_replaced "${olf_uac_replaced} + 1")
  else()
    list(APPEND olf_uac_new_sources "${olf_source}")
  endif()
endforeach()
if(NOT olf_uac_replaced EQUAL 1)
  message(FATAL_ERROR "Expected one UAC2 class source in ${olf_uac_target}")
endif()
set_property(TARGET ${olf_uac_target} PROPERTY SOURCES "${olf_uac_new_sources}")
message(STATUS "UAC2 formats: alternate 1 = 16-bit; alternate 2 = 24-bit")
