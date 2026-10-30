#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build nRF5 SDK 17.1.0 Secure USB DFU for the PCA10059 dongle.

Only generated build files are changed; the external SDK is read-only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--gcc-bin", type=Path, default=Path("/usr/local/bin"))
    parser.add_argument("--make", default="make")
    parser.add_argument("--library-path", type=Path, help="Optional macOS compiler dylib search path")
    parser.add_argument("--zstd-library", type=Path, help="Optional libzstd dylib for the local Arm GCC")
    args = parser.parse_args()
    project = Path(__file__).resolve().parent.parent
    sdk = args.sdk.resolve()
    example = sdk / "examples/dfu/secure_bootloader/pca10056_usb"
    out = project / "build/secure_bootloader"
    armgcc = out / "armgcc"
    config_dir = out / "config"
    armgcc.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(exist_ok=True)
    config = (example / "config/sdk_config.h").read_text()
    settings = {
        "NRF_DFU_REQUIRE_SIGNED_APP_UPDATE": "1",
        "NRF_BL_APP_SIGNATURE_CHECK_REQUIRED": "1",
        "NRF_BL_APP_CRC_CHECK_SKIPPED_ON_GPREGRET2": "0",
        "NRF_BL_APP_CRC_CHECK_SKIPPED_ON_SYSTEMOFF_RESET": "0",
        "NRF_BL_DFU_ENTER_METHOD_BUTTON": "1",
        "NRF_BL_DFU_ENTER_METHOD_BUTTON_PIN": "38",  # SW1: P1.06
        "NRF_BL_DFU_ENTER_METHOD_PINRESET": "1",
        "NRF_BL_DFU_ENTER_METHOD_GPREGRET": "1",
        "NRF_BL_DFU_INACTIVITY_TIMEOUT_MS": "0",
        "NRF_BL_DEBUG_PORT_DISABLE": "0",  # retain SWD recovery
        "NRF_DFU_HW_VERSION": "52",
        "NRF_DFU_APP_DOWNGRADE_PREVENTION": "1",
        "NRF_DFU_APP_ACCEPT_SAME_VERSION": "1",  # development releases currently use v1
        "NRF_DFU_SINGLE_BANK_APP_UPDATES": "1",  # app + tools disk exceeds half flash
        "NRF_DFU_FORCE_DUAL_BANK_APP_UPDATES": "0",
        "NRF_DFU_APP_DATA_AREA_SIZE": "0",
        "NRF_DFU_SETTINGS_COMPATIBILITY_MODE": "0",
        "APP_USBD_STRINGS_MANUFACTURER": 'APP_USBD_STRING_DESC("OLF Development")',
        "APP_USBD_STRINGS_PRODUCT": 'APP_USBD_STRING_DESC("OLFs Secure DFU Bootloader")',
    }
    for name, value in settings.items():
        config, count = re.subn(r"^#define " + name + r" .*$", "#define " + name + " " + value,
                                config, flags=re.MULTILINE)
        if count != 1:
            raise ValueError("SDK configuration changed: " + name)
    (config_dir / "sdk_config.h").write_text(config)
    linker = (example / "armgcc/secure_bootloader_gcc_nrf52.ld").read_text()
    linker = linker.replace("ORIGIN = 0xf4000, LENGTH = 0xa000", "ORIGIN = 0xe0000, LENGTH = 0x1e000")
    if "ORIGIN = 0xe0000, LENGTH = 0x1e000" not in linker:
        raise ValueError("Unexpected bootloader memory layout")
    (armgcc / "secure_bootloader_gcc_nrf52.ld").write_text(linker)
    makefile = (example / "armgcc/Makefile").read_text()
    makefile = makefile.replace("SDK_ROOT := ../../../../..", "SDK_ROOT := " + str(sdk))
    makefile = makefile.replace("PROJ_DIR := ../..", "PROJ_DIR := " + str(example.parent))
    makefile = makefile.replace("$(PROJ_DIR)/../dfu_public_key.c", str(project / "signing/dfu_public_key.c"))
    makefile = makefile.replace("BOARD_PCA10056", "BOARD_PCA10059")
    # SDK linker markers are storage boundaries, not pointer-sized objects.
    # Unknown-bound arrays express this correctly to modern GCC without
    # suppressing array-bound diagnostics in crypto/flash code.
    section = (sdk / "components/libraries/experimental_section_vars/nrf_section.h").read_text()
    section = section.replace("extern data_type * CONCAT_2(__start_, section_name);",
                              "extern data_type CONCAT_2(__start_, section_name)[];")
    section = section.replace("extern void      * CONCAT_2(__stop_,  section_name)",
                              "extern uint8_t CONCAT_2(__stop_, section_name)[]")
    if "extern data_type CONCAT_2(__start_, section_name)[];" not in section:
        raise ValueError("SDK linker-section declaration changed")
    section_header = config_dir / "nrf_section_gcc_compat.h"
    section_header.write_text(section)
    makefile += "\nCFLAGS += -include " + str(section_header) + " --param=min-pagesize=0\n"
    (armgcc / "Makefile").write_text(makefile)
    version = subprocess.check_output([str(args.gcc_bin / "arm-none-eabi-gcc"), "-dumpfullversion"], text=True).strip()
    env = dict(os.environ)
    if args.zstd_library:
        libraries = out / "compiler-libs"
        libraries.mkdir(exist_ok=True)
        link = libraries / "libzstd.1.dylib"
        if not link.exists():
            link.symlink_to(args.zstd_library.resolve())
        args.library_path = libraries
    if args.library_path:
        env["DYLD_LIBRARY_PATH"] = str(args.library_path.resolve())
    subprocess.run([args.make, "-j4", "GNU_INSTALL_ROOT=" + str(args.gcc_bin.resolve()) + "/",
                    "GNU_VERSION=" + version, "GNU_PREFIX=arm-none-eabi"], cwd=armgcc, check=True, env=env)
    for extension in ("hex", "out", "map"):
        source = armgcc / "_build" / ("nrf52840_xxaa." + extension)
        if source.exists():
            shutil.copyfile(source, out / ("olfs_secure_bootloader." + extension))
    provenance = {
        "sdk": str(sdk), "gcc_version": version, "board": "PCA10059 / nRF52840",
        "bootloader_start": "0xe0000", "mbr_params": "0xfe000", "settings": "0xff000",
        "public_key_source_sha256": hashlib.sha256((project / "signing/dfu_public_key.c").read_bytes()).hexdigest(),
        "configuration": settings,
    }
    (out / "build-info.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print("Secure USB bootloader:", out / "olfs_secure_bootloader.hex")


if __name__ == "__main__":
    main()
