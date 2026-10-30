# SPDX-License-Identifier: Apache-2.0
set(olf_disk_image "${PROJECT_BINARY_DIR}/generated/olf_tools.img")
set(olf_disk_files)
foreach(name OLF-WIN.EXE OLF-WARM.EXE OLF-LX64 OLF-LARM OLF-MAC SHA256.TXT BUILD.TXT)
  list(APPEND olf_disk_files "${CMAKE_CURRENT_SOURCE_DIR}/host/dist/${name}")
endforeach()
add_custom_command(OUTPUT "${olf_disk_image}"
  COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/make_tools_disk.py"
    "${CMAKE_CURRENT_SOURCE_DIR}" "${olf_disk_image}"
  DEPENDS ${olf_disk_files} host/olfctl.c host/DRIVE_README.txt host/LICENSE.txt scripts/make_tools_disk.py
  VERBATIM)
set(olf_disk_assembly "${PROJECT_BINARY_DIR}/generated/olf_tools.S")
file(WRITE "${olf_disk_assembly}"
  ".section .rodata.olf_tools,\"a\",%progbits\n.balign 4\n.global olf_tools_disk_start\nolf_tools_disk_start:\n.incbin \"${olf_disk_image}\"\n.global olf_tools_disk_end\nolf_tools_disk_end:\n")
set_source_files_properties("${olf_disk_assembly}" PROPERTIES OBJECT_DEPENDS "${olf_disk_image}")
target_sources(app PRIVATE src/tools_disk.c "${olf_disk_assembly}")
zephyr_linker_sources(SECTIONS "${CMAKE_CURRENT_SOURCE_DIR}/src/bootloader_limit.ld")

set(olf_scsi_original "${ZEPHYR_BASE}/subsys/usb/device_next/class/usbd_msc_scsi.c")
set(olf_scsi_generated "${PROJECT_BINARY_DIR}/generated/usbd_msc_scsi_readonly.c")
set(olf_scsi_script "${CMAKE_CURRENT_SOURCE_DIR}/scripts/prepare_msc_readonly.py")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${olf_scsi_original}" "${olf_scsi_script}")
execute_process(COMMAND "${Python3_EXECUTABLE}" "${olf_scsi_script}" "${olf_scsi_original}" "${olf_scsi_generated}"
  RESULT_VARIABLE olf_scsi_result ERROR_VARIABLE olf_scsi_error)
if(NOT olf_scsi_result EQUAL 0)
  message(FATAL_ERROR "Cannot prepare read-only MSC SCSI: ${olf_scsi_error}")
endif()
get_target_property(olf_scsi_sources subsys__usb__device_next SOURCES)
set(olf_scsi_new_sources)
set(olf_scsi_replaced 0)
foreach(olf_source IN LISTS olf_scsi_sources)
  if(olf_source MATCHES "(^|/)usbd_msc_scsi\\.c$")
    list(APPEND olf_scsi_new_sources "${olf_scsi_generated}")
    math(EXPR olf_scsi_replaced "${olf_scsi_replaced} + 1")
  else()
    list(APPEND olf_scsi_new_sources "${olf_source}")
  endif()
endforeach()
if(NOT olf_scsi_replaced EQUAL 1)
  message(FATAL_ERROR "Expected one MSC SCSI source")
endif()
set_property(TARGET subsys__usb__device_next PROPERTY SOURCES "${olf_scsi_new_sources}")
target_include_directories(subsys__usb__device_next PRIVATE "${ZEPHYR_BASE}/subsys/usb/device_next/class")
