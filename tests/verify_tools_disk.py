#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independently read FAT12 files and verify their bytes in the firmware ELF."""
import hashlib
from pathlib import Path
import struct
import sys
from elftools.elf.elffile import ELFFile


def main(image_path, elf_path):
    image = Path(image_path).read_bytes()
    root = Path(__file__).resolve().parent.parent
    sector_size = struct.unpack_from("<H", image, 11)[0]
    reserved = struct.unpack_from("<H", image, 14)[0]
    entries = struct.unpack_from("<H", image, 17)[0]
    sectors = struct.unpack_from("<H", image, 19)[0]
    fat_sectors = struct.unpack_from("<H", image, 22)[0]
    assert sector_size == 512 and sectors == 1024 and len(image) == sector_size * sectors
    assert image[13] == 1 and image[16] == 2 and image[510:512] == b"\x55\xaa"
    fat = image[reserved*sector_size:(reserved+fat_sectors)*sector_size]
    assert fat == image[(reserved+fat_sectors)*sector_size:(reserved+2*fat_sectors)*sector_size]
    directory = (reserved + 2 * fat_sectors) * sector_size
    data_start = directory + entries * 32
    files = {}
    occupied = set()
    for i in range(entries):
        entry = image[directory+32*i:directory+32*(i+1)]
        if not entry[0]:
            break
        if entry[11] & 8:
            continue
        assert entry[11] & 1  # read-only file
        name = entry[:8].decode("ascii").rstrip()
        suffix = entry[8:11].decode("ascii").rstrip()
        if suffix:
            name += "." + suffix
        cluster, length = struct.unpack_from("<HI", entry, 26)
        content = bytearray()
        while cluster < 0xFF8:
            assert cluster >= 2 and cluster not in occupied
            occupied.add(cluster)
            offset = data_start + (cluster-2)*sector_size
            assert offset+sector_size <= len(image)
            content.extend(image[offset:offset+sector_size])
            offset = cluster + cluster//2
            word = int.from_bytes(fat[offset:offset+2], "little")
            cluster = word >> 4 if cluster & 1 else word & 0xFFF
        assert len(content) >= length
        files[name] = bytes(content[:length])
    expected = {name: (root/"host/dist"/name).read_bytes() for name in
                ("OLF-WIN.EXE", "OLF-WARM.EXE", "OLF-LX64", "OLF-LARM", "OLF-MAC", "SHA256.TXT", "BUILD.TXT")}
    expected["LICENSE.TXT"] = (root/"host/LICENSE.txt").read_bytes()
    expected["OLFCTL.C"] = (root/"host/olfctl.c").read_bytes()
    expected["README.TXT"] = (root/"host/DRIVE_README.txt").read_bytes().replace(b"\n", b"\r\n")
    assert files == expected
    for line in files["SHA256.TXT"].decode().splitlines():
        digest, name = line.split()
        assert hashlib.sha256(files[name]).hexdigest() == digest
    with open(elf_path, "rb") as stream:
        elf = ELFFile(stream)
        symbols = elf.get_section_by_name(".symtab")
        start = symbols.get_symbol_by_name("olf_tools_disk_start")[0]["st_value"]
        end = symbols.get_symbol_by_name("olf_tools_disk_end")[0]["st_value"]
        assert 0x1000 <= start < end <= 0xE0000 and end-start == len(image)
        matched = False
        for segment in elf.iter_segments():
            if segment["p_type"] != "PT_LOAD" or not segment["p_filesz"]:
                continue
            physical = segment["p_paddr"]
            if physical < 0x100000:
                assert 0x1000 <= physical and physical+segment["p_filesz"] <= 0xE0000
            virtual = segment["p_vaddr"]
            if virtual <= start and end <= virtual+segment["p_filesz"]:
                assert segment.data()[start-virtual:end-virtual] == image
                matched = True
        assert matched
    print("Tools disk: FAT12, all file bytes/hashes, embedded image and factory bootloader boundaries verified")


if __name__ == "__main__":
    main(*sys.argv[1:])
