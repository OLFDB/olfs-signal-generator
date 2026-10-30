#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build a deterministic 512-KiB FAT12 superfloppy containing native clients."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

SECTOR_SIZE = 512
SECTORS = 1024
FAT_SECTORS = 3
ROOT_ENTRIES = 64
ROOT_SECTORS = ROOT_ENTRIES * 32 // SECTOR_SIZE
ROOT_START = 1 + 2 * FAT_SECTORS
DATA_START = ROOT_START + ROOT_SECTORS


def make_image(files):
    image = bytearray(SECTOR_SIZE * SECTORS)
    image[:11] = b"\xeb\x3c\x90MSDOS5.0"
    struct.pack_into("<HBHBHHBHHHII", image, 11, SECTOR_SIZE, 1, 1, 2,
                     ROOT_ENTRIES, SECTORS, 0xF8, FAT_SECTORS, 32, 2, 0, 0)
    image[36:39] = bytes([0x80, 0, 0x29])
    struct.pack_into("<I", image, 39, 0x4F4C4631)
    image[43:54] = b"OLFS TOOLS "
    image[54:62] = b"FAT12   "
    image[510:512] = b"\x55\xaa"
    fat = bytearray(SECTOR_SIZE * FAT_SECTORS)
    fat[:3] = b"\xf8\xff\xff"

    def set_fat(cluster, value):
        offset = cluster + cluster // 2
        word = int.from_bytes(fat[offset:offset+2], "little")
        word = (word & 0x000F) | (value << 4) if cluster & 1 else (word & 0xF000) | value
        fat[offset:offset+2] = word.to_bytes(2, "little")

    root = ROOT_START * SECTOR_SIZE
    image[root:root+11] = b"OLFS TOOLS "
    image[root+11] = 8  # volume label
    cluster = 2
    if len(files) + 1 > ROOT_ENTRIES:
        raise ValueError("Too many root directory entries")
    used_names = set()
    for index, (name, content) in enumerate(files, 1):
        parts = name.upper().split(".")
        if len(parts) > 2 or not 1 <= len(parts[0]) <= 8 or len(parts[-1] if len(parts) == 2 else "") > 3:
            raise ValueError("Use FAT 8.3 names: " + name)
        short = (parts[0].ljust(8) + (parts[1] if len(parts) == 2 else "").ljust(3)).encode("ascii")
        if short in used_names:
            raise ValueError("Duplicate FAT name")
        used_names.add(short)
        count = (len(content) + SECTOR_SIZE - 1) // SECTOR_SIZE
        if cluster - 2 + count > SECTORS - DATA_START:
            raise ValueError("Native clients exceed the tools disk capacity")
        start = (DATA_START + cluster - 2) * SECTOR_SIZE
        image[start:start+len(content)] = content
        for n in range(count):
            set_fat(cluster + n, 0xFFF if n == count - 1 else cluster + n + 1)
        entry = root + index * 32
        image[entry:entry+11] = short
        image[entry+11] = 0x21  # read-only + archive
        struct.pack_into("<H", image, entry+16, 0x5821)  # 2024-01-01, deterministic
        struct.pack_into("<H", image, entry+24, 0x5821)
        struct.pack_into("<HI", image, entry+26, cluster if count else 0, len(content))
        cluster += count
    for copy in range(2):
        offset = (1 + copy * FAT_SECTORS) * SECTOR_SIZE
        image[offset:offset+len(fat)] = fat
    return bytes(image)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    provenance = json.loads((args.root / "host/dist/BUILD.TXT").read_text())
    if provenance["source_sha256"] != hashlib.sha256((args.root / "host/olfctl.c").read_bytes()).hexdigest():
        raise ValueError("Client source changed: rebuild native clients with host/build_clients.py first")
    for name, digest in provenance["binaries"].items():
        if hashlib.sha256((args.root / "host/dist" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Client binary hash mismatch: " + name)
    names = ("OLF-WIN.EXE", "OLF-WARM.EXE", "OLF-LX64", "OLF-LARM", "OLF-MAC", "SHA256.TXT", "BUILD.TXT")
    files = [(name, (args.root / "host" / "dist" / name).read_bytes()) for name in names]
    files.extend([
        ("README.TXT", (args.root / "host/DRIVE_README.txt").read_bytes().replace(b"\n", b"\r\n")),
        ("OLFCTL.C", (args.root / "host/olfctl.c").read_bytes()),
        ("LICENSE.TXT", (args.root / "host/LICENSE.txt").read_bytes()),
    ])
    result = make_image(files)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.output.exists() or args.output.read_bytes() != result:
        args.output.write_bytes(result)
    print(f"Tools disk: {len(result)} bytes, {sum(len(data) for _, data in files)} bytes of files")


if __name__ == "__main__":
    main()
