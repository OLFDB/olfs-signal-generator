#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Merge the current application, secure bootloader and signed settings, preserving MBR."""
from pathlib import Path
from intelhex import IntelHex

root = Path(__file__).resolve().parent.parent
out = root / "build/secure_bootloader"
combined = IntelHex()
for path in (root / "build/multi_cdc_vscode_ready/zephyr/zephyr.hex",
             out / "olfs_secure_bootloader.hex", out / "olfs_bootloader_settings.hex"):
    image = IntelHex(str(path))
    # Different ELF entry metadata is irrelevant: boot starts through the MBR.
    image.start_addr = None
    combined.merge(image, overlap="error")
if any(address < 0x1000 for address in combined.addresses()):
    raise ValueError("Refusing an installation image that overwrites the MBR")
target = out / "olfs_secure_install_preserve_mbr.hex"
combined.write_hex_file(str(target))
print(target)
