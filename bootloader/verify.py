#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify application-only Open Bootloader layout and Nordic DFU package."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile
from intelhex import IntelHex
import yaml

# Reuse the strict Nordic init-packet decoder; no private key is required.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from verify_signed_dfu import fields


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    root = Path(__file__).resolve().parent.parent
    build = root / "build"
    app = build / "multi_cdc_vscode_ready/zephyr"
    config = (app / ".config").read_text()
    require("# CONFIG_BOOTLOADER_MCUBOOT is not set" in config, "MCUboot still enabled")
    require('CONFIG_BOARD_TARGET="nrf52840dongle/nrf52840"' in config, "Incorrect board variant")
    require("CONFIG_BOARD_HAS_NRF5_BOOTLOADER=y" in config, "Factory bootloader mode missing")
    require("CONFIG_FLASH_LOAD_OFFSET=0x1000" in config, "Wrong application offset")
    domains = yaml.safe_load((build / "domains.yaml").read_text())
    require(len(domains["domains"]) == 1 and domains["domains"][0]["name"] == "multi_cdc_vscode_ready",
            "Unexpected bootloader build domain")
    layout = yaml.safe_load((build / "partitions.yml").read_text())
    require(layout["app"]["address"] == 0x1000 and layout["app"]["end_address"] == 0xE0000,
            "Wrong application partition")
    require("mcuboot" not in layout and "mcuboot_primary" not in layout, "MCUboot partitions remain")
    application = IntelHex(str(app / "zephyr.hex"))
    merged = IntelHex(str(build / "merged.hex"))
    for image in (application, merged):
        require(image.minaddr() == 0x1000 and all(0x1000 <= a < 0xE0000 for a in image.addresses()),
                "Image modifies MBR, factory bootloader, settings or UICR")
    require(application.addresses() == merged.addresses() and
            all(application[a] == merged[a] for a in application.addresses()), "Unexpected merged data")
    with zipfile.ZipFile(build / "multi_cdc_dfu.zip") as archive:
        manifest = json.loads(archive.read("manifest.json"))["manifest"]
        require(set(manifest) == {"application"}, "DFU package contains a bootloader/SoftDevice")
        entry = manifest["application"]
        binary = archive.read(entry["bin_file"])
        packet = fields(archive.read(entry["dat_file"]))
    require(set(packet) == {1}, "Expected unsigned init packet for Open Bootloader")
    command = fields(packet[1])
    require(command[1] == 1, "Expected INIT command")
    init = fields(command[2])
    digest = fields(init[8])
    require(init[2] == 52 and init[4] == 0 and init[7] == len(binary), "Wrong DFU metadata")
    require(digest[1] == 3 and digest[2] == hashlib.sha256(binary).digest()[::-1], "Wrong DFU hash")
    require(bytes(application.tobinarray(start=0x1000, size=len(binary))) == binary, "DFU/HEX differ")
    stack, reset = struct.unpack_from("<II", binary)
    require(0x20000000 < stack <= 0x20040000 and reset & 1 and 0x1000 <= reset-1 < 0xE0000,
            "Invalid application vectors")
    report = {
        "verified": True, "bootloader": "Original Nordic USB Open Bootloader (not replaced)",
        "board": "nrf52840dongle/nrf52840", "application_start": "0x1000",
        "application_limit": "0xe0000", "application_bytes": len(binary),
        "factory_bootloader_mbr_settings_uicr_preserved": True, "mcuboot": False,
        "dfu_unsigned": True, "dfu_hash_verified": True,
        "application_sha256": hashlib.sha256(binary).hexdigest(),
        "dfu_zip_sha256": hashlib.sha256((build / "multi_cdc_dfu.zip").read_bytes()).hexdigest(),
        "hardware_flashed": False,
    }
    (build / "openbootloader-verification.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
