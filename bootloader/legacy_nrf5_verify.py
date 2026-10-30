#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify the built dongle bootloader, key, signed settings and install image."""
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib
from ecdsa import VerifyingKey
from elftools.elf.elffile import ELFFile
from intelhex import IntelHex


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    root = Path(__file__).resolve().parent.parent
    out = root / "build/secure_bootloader"
    key = VerifyingKey.from_pem((root / "signing/dfu_public.pem").read_text())
    point = key.to_string()
    expected = point[:32][::-1] + point[32:][::-1]
    with (out / "olfs_secure_bootloader.out").open("rb") as stream:
        elf = ELFFile(stream)
        symbol = elf.get_section_by_name(".symtab").get_symbol_by_name("pk")[0]
        section = elf.get_section(symbol["st_shndx"])
        offset = symbol["st_value"] - section["sh_addr"]
        require(section.data()[offset:offset+64] == expected, "Wrong public key in bootloader")
        require(0xE0000 <= symbol["st_value"] < 0xFE000, "Key outside protected bootloader")
        # The modern-GCC section declaration fix must preserve actual instances.
        symbols = elf.get_section_by_name(".symtab")
        for name in ("crypto_data", "fs_data"):
            start = symbols.get_symbol_by_name("__start_"+name)[0]["st_value"]
            end = symbols.get_symbol_by_name("__stop_"+name)[0]["st_value"]
            require(end > start, "Empty SDK linker section: " + name)
    loader = IntelHex(str(out / "olfs_secure_bootloader.hex"))
    for address in loader.addresses():
        require(0xE0000 <= address < 0xFE000 or 0x10001014 <= address < 0x1000101C,
                "Unexpected bootloader write address")
    vectors = bytes(loader.tobinarray(start=0xE0000, size=8))
    stack, reset = struct.unpack("<II", vectors)
    require(0x20000008 < stack <= 0x20040000 and not stack % 8, "Invalid stack pointer")
    require(reset & 1 and 0xE0000 <= reset-1 < 0xFE000, "Invalid bootloader reset vector")
    uicr = bytes(loader.tobinarray(start=0x10001014, size=8))
    require(struct.unpack("<II", uicr) == (0xE0000, 0xFE000), "Wrong UICR boot/MBR addresses")
    with zipfile.ZipFile(root / "build/multi_cdc_dfu_signed.zip") as package:
        manifest = json.loads(package.read("manifest.json"))["manifest"]["application"]
        firmware = package.read(manifest["bin_file"])
    application = IntelHex(str(root / "build/multi_cdc_vscode_ready/zephyr/zephyr.hex"))
    require(bytes(application.tobinarray(start=0x1000, size=len(firmware))) == firmware,
            "Signed application differs from installation application")
    settings = IntelHex(str(out / "olfs_bootloader_settings.hex"))
    record = bytes(settings.tobinarray(start=0xFF000, size=0x324))
    require(record == bytes(settings.tobinarray(start=0xFE000, size=0x324)), "Settings backup mismatch")
    word = lambda offset: struct.unpack_from("<I", record, offset)[0]
    require(word(4) == 2 and word(8) == 1 and word(12) == 1, "Unexpected settings versions")
    require(word(0) == zlib.crc32(record[4:92]), "Settings CRC mismatch")
    require(word(0x25C) == zlib.crc32(record[0x260:0x323]), "Boot validation CRC mismatch")
    require(word(24) == len(firmware) and word(28) == zlib.crc32(firmware) and word(32) == 1,
            "Invalid application bank information")
    require(record[0x2A1] == 3, "ECDSA boot validation missing")
    signature = record[0x2A2:0x2E2]
    signature = signature[:32][::-1] + signature[32:][::-1]
    require(key.verify(signature, firmware, hashfunc=hashlib.sha256), "Invalid settings boot signature")
    combined = IntelHex(str(out / "olfs_secure_install_preserve_mbr.hex"))
    require(not any(a < 0x1000 for a in combined.addresses()), "Install image overwrites MBR")
    require(len(combined.addresses()) == sum(len(i.addresses()) for i in (loader, application, settings)),
            "Overlapping/extra installation data")
    for image in (loader, application, settings):
        require(all(image[a] == combined[a] for a in image.addresses()), "Incorrect merged data")
    config = (out / "config/sdk_config.h").read_text()
    for name, value in {
        "NRF_DFU_REQUIRE_SIGNED_APP_UPDATE": 1, "NRF_BL_APP_SIGNATURE_CHECK_REQUIRED": 1,
        "NRF_BL_DEBUG_PORT_DISABLE": 0, "NRF_BL_DFU_ENTER_METHOD_PINRESET": 1,
        "NRF_BL_DFU_ENTER_METHOD_BUTTON_PIN": 38,
    }.items():
        require(f"#define {name} {value}\n" in config, "Incorrect policy: " + name)
    require("-DNRF_DFU_DEBUG_VERSION" not in (out / "armgcc/Makefile").read_text(), "Debug DFU build")
    report = {
        "verified": True, "board": "PCA10059 nRF52840 Dongle",
        "bootloader_start": "0xe0000", "bootloader_flash_bytes":
            len([a for a in loader.addresses() if a < 0x100000]),
        "application_bytes": len(firmware), "signed_updates_required": True,
        "application_signature_required_at_boot": True, "swd_recovery_enabled": True,
        "public_key_der_sha256": hashlib.sha256(key.to_der()).hexdigest(),
        "settings_and_backup_verified": True, "mbr_preserved": True,
        "hardware_tested": False,
    }
    (out / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
