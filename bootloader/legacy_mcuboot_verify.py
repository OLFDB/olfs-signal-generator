#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify active MCUboot sysbuild layout, compiled public key and image signature."""
import hashlib
import csv
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from ecdsa import NIST256p, SigningKey, VerifyingKey
from elftools.elf.elffile import ELFFile
from intelhex import IntelHex
import yaml


def require(ok, message):
    if not ok:
        raise ValueError(message)


def configuration(path):
    result = {}
    for line in path.read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def main():
    root = Path(__file__).resolve().parent.parent
    build = root / "build"
    app = build / "multi_cdc_vscode_ready/zephyr"
    boot = build / "mcuboot/zephyr"
    signed = app / "zephyr.signed.bin"
    image = signed.read_bytes()
    header = struct.unpack_from("<IIHHIIBBHII", image)
    require(header[0] == 0x96F3B83D and header[2] == 512, "Invalid MCUboot header")
    require(header[6:10] == (1, 0, 0, 0), "Unexpected application version")
    require(len(image) <= 0xE0000, "Signed image exceeds primary slot")
    layout = yaml.safe_load((build / "partitions.yml").read_text())
    for name, address, size in (("mcuboot", 0, 0x20000), ("mcuboot_primary", 0x20000, 0xE0000),
                                ("app", 0x20200, 0xDFE00)):
        require(layout[name]["address"] == address and layout[name]["size"] == size,
                "Unexpected partition: " + name)
    require("mcuboot_secondary" not in layout and "nrf5_mbr" not in layout, "Unexpected legacy/secondary slot")
    config = configuration(boot / ".config")
    for name in ("SINGLE_APPLICATION_SLOT", "BOOT_VALIDATE_SLOT0", "MCUBOOT_SERIAL",
                 "BOOT_SERIAL_CDC_ACM", "BOOT_SERIAL_NO_APPLICATION", "BOOT_SERIAL_ENTRANCE_GPIO",
                 "BOOT_SERIAL_PIN_RESET", "FPROTECT", "BOOT_SIGNATURE_TYPE_ECDSA_P256"):
        require(config.get("CONFIG_"+name) == "y", "Missing boot policy: " + name)
    require(config.get("CONFIG_FLASH_LOAD_OFFSET") == "0x0", "Bootloader is not first-stage")
    require(config.get("CONFIG_BOARD_HAS_NRF5_BOOTLOADER") != "y", "Legacy boot chain enabled")
    require(config.get("CONFIG_NRF_APPROTECT_LOCK") != "y", "Unexpected SWD lock")
    require(config.get("CONFIG_USB_DEVICE_VID") == "0x1209" and
            config.get("CONFIG_USB_DEVICE_PID") == "0x0002", "Wrong recovery USB identity")
    key = VerifyingKey.from_pem((root / "signing/dfu_public.pem").read_text())
    with (boot / "zephyr.elf").open("rb") as stream:
        elf = ELFFile(stream)
        symbol = elf.get_section_by_name(".symtab").get_symbol_by_name("ecdsa_pub_key")[0]
        section = elf.get_section(symbol["st_shndx"])
        offset = symbol["st_value"] - section["sh_addr"]
        require(section.data()[offset:offset+symbol["st_size"]] == key.to_der(), "Wrong compiled boot key")
    # Use the actual module selected by CMake, rather than an unrelated imgtool.
    modules = (build / "mcuboot/zephyr_modules.txt").read_text().splitlines()
    module = next(row[1] for row in csv.reader(modules, delimiter=":") if row[0] == "mcuboot")
    imgtool = str(Path(module) / "scripts/imgtool.py")
    command = [sys.executable, imgtool, "verify", "-k", str(root / "signing/dfu_public.pem")]
    good = subprocess.run(command+[str(signed)], capture_output=True, text=True)
    require(good.returncode == 0 and "correctly validated" in good.stdout, good.stdout+good.stderr)
    with tempfile.TemporaryDirectory(prefix="olf-mcuboot-") as directory:
        altered = bytearray(image)
        altered[header[2]] ^= 1
        bad = Path(directory) / "tampered.bin"
        bad.write_bytes(altered)
        invalid = subprocess.run(command+[str(bad)], capture_output=True)
        require(invalid.returncode != 0, "Tampered image accepted")
    with tempfile.TemporaryDirectory(prefix="olf-mcuboot-key-") as directory:
        wrong_public = Path(directory) / "wrong.pem"
        wrong_public.write_bytes(SigningKey.generate(curve=NIST256p).get_verifying_key().to_pem())
        wrong = subprocess.run([sys.executable, imgtool, "verify", "-k", str(wrong_public), str(signed)],
                               capture_output=True)
        require(wrong.returncode != 0, "Image accepted with the wrong public key")
    boot_hex = IntelHex(str(boot / "zephyr.hex"))
    app_hex = IntelHex(str(app / "zephyr.signed.hex"))
    merged = IntelHex(str(build / "merged.hex"))
    require(all(0 <= a < 0x20000 for a in boot_hex.addresses()), "Bootloader exceeds partition/writes UICR")
    require(all(0x20000 <= a < 0x100000 for a in app_hex.addresses()), "Application exceeds partition")
    # NCS signs BIN and HEX separately; randomized ECDSA signatures may differ.
    authenticated_size = header[2] + header[4] + header[3]
    require(bytes(app_hex.tobinarray(start=0x20000, size=authenticated_size)) == image[:authenticated_size],
            "BIN/HEX authenticated payload mismatch")
    hex_check = subprocess.run(command+[str(app / "zephyr.signed.hex")], capture_output=True, text=True)
    require(hex_check.returncode == 0 and "correctly validated" in hex_check.stdout,
            hex_check.stdout+hex_check.stderr)
    require(len(merged.addresses()) == len(boot_hex.addresses())+len(app_hex.addresses()), "Unexpected merged data")
    for source in (boot_hex, app_hex):
        require(all(merged[a] == source[a] for a in source.addresses()), "Merged image differs")
    vectors = bytes(boot_hex.tobinarray(start=0, size=8))
    stack, reset = struct.unpack("<II", vectors)
    require(0x20000000 < stack <= 0x20040000 and reset & 1 and reset-1 < 0x20000,
            "Invalid first-stage vectors")
    report = {
        "verified": True, "bootloader": "MCUboot", "first_stage_address": "0x0",
        "primary_slot": "0x20000..0x100000", "secondary_slot": False,
        "signature": "ECDSA-P256-SHA256", "version": "1.0.0+0",
        "validate_primary_each_boot": True, "usb_serial_recovery": True,
        "boot_flash_protection": True, "swd_locked": False,
        "public_key_der_sha256": hashlib.sha256(key.to_der()).hexdigest(),
        "signed_image_sha256": hashlib.sha256(image).hexdigest(),
        "signed_image_bytes": len(image), "bootloader_bytes": len(boot_hex.addresses()),
        "tampered_image_rejected": True, "wrong_public_key_rejected": True, "hardware_tested": False,
    }
    (build / "mcuboot-verification.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
