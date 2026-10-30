# SPDX-License-Identifier: Apache-2.0
# This application only sends USB audio. CDC OUT remains available.
if(NOT CONFIG_SOC_NRF52840 OR NOT CONFIG_UDC_NRF)
  message(FATAL_ERROR "The ISO-IN-only customization requires nRF52840 and CONFIG_UDC_NRF")
endif()

set(olf_udc_target drivers__usb__udc)
set(olf_udc_original "${ZEPHYR_BASE}/drivers/usb/udc/udc_nrf.c")
set(olf_udc_script "${CMAKE_CURRENT_LIST_DIR}/../scripts/prepare_nrf_iso_in.py")
set(olf_udc_generated "${PROJECT_BINARY_DIR}/generated/udc_nrf_iso_in.c")

set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
  "${olf_udc_original}" "${olf_udc_script}")
execute_process(
  COMMAND "${Python3_EXECUTABLE}" "${olf_udc_script}" "${olf_udc_original}" "${olf_udc_generated}"
  RESULT_VARIABLE olf_udc_result
  ERROR_VARIABLE olf_udc_error
)
if(NOT olf_udc_result EQUAL 0)
  message(FATAL_ERROR "Cannot prepare ISO-IN-only UDC driver: ${olf_udc_error}")
endif()

# Keep the driver in its original Zephyr library with the same compiler flags.
get_target_property(olf_udc_sources ${olf_udc_target} SOURCES)
set(olf_udc_new_sources)
set(olf_udc_replaced 0)
foreach(olf_source IN LISTS olf_udc_sources)
  if(olf_source MATCHES "(^|/)udc_nrf\\.c$")
    list(APPEND olf_udc_new_sources "${olf_udc_generated}")
    math(EXPR olf_udc_replaced "${olf_udc_replaced} + 1")
  else()
    list(APPEND olf_udc_new_sources "${olf_source}")
  endif()
endforeach()
if(NOT olf_udc_replaced EQUAL 1)
  message(FATAL_ERROR "Expected exactly one nRF UDC source in ${olf_udc_target}")
endif()
set_property(TARGET ${olf_udc_target} PROPERTY SOURCES "${olf_udc_new_sources}")
target_include_directories(${olf_udc_target} PRIVATE "${ZEPHYR_BASE}/drivers/usb/udc")
message(STATUS "nRF52840 ISO-IN-only driver: 1023-byte ISO IN; ISO OUT unavailable")
