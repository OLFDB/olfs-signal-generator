#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify the actual UAC2 descriptors and clock table in the built ELF.

Run with the Nordic toolchain Python (includes pyelftools), passing zephyr.elf.
This checks the compiled image, not device enumeration or audio on hardware.
"""
import sys
from elftools.elf.elffile import ELFFile


def main(path):
    with open(path, "rb") as stream:
        elf = ELFFile(stream)
        symbols = elf.get_section_by_name(".symtab")

        def at(address, size):
            for section in elf.iter_sections():
                start = section["sh_addr"]
                if section["sh_type"] != "SHT_NOBITS" and start <= address and address + size <= start + section["sh_size"]:
                    return section.data()[address-start:address-start+size]
            raise AssertionError(f"Unmapped descriptor: {address:#x}")

        def data(name):
            matches = symbols.get_symbol_by_name(name)
            assert matches and len(matches) == 1, f"Missing or ambiguous symbol: {name}"
            symbol = matches[0]
            section = elf.get_section(symbol["st_shndx"])
            offset = symbol["st_value"] - section["sh_addr"]
            return section.data()[offset:offset + symbol["st_size"]]

        suffix = "DT_N_S_usb_audio2_S_stream"
        endpoint = data("uac2_fs_std_data_ep_" + suffix)
        audio_format = data("uac2_as_format_desc_" + suffix)
        general = data("uac2_as_general_desc_" + suffix)
        alternate = data("uac2_fs_as_if_alt1_" + suffix)
        frequency = data("frequencies_0_1")

        assert endpoint[0:2] == bytes([7, 5])  # standard endpoint descriptor
        assert endpoint[2] & 0x80  # USB IN, device to host
        assert endpoint[3] & 0x0F == 0x0D  # synchronous isochronous
        assert int.from_bytes(endpoint[4:6], "little") == 384
        assert endpoint[6] == 1  # once per 1-ms full-speed frame
        assert audio_format == bytes([6, 0x24, 2, 1, 2, 16])
        assert general[10] == 2  # bNrChannels
        assert int.from_bytes(general[11:15], "little") == 3  # left + right
        assert alternate[4] == 1  # one endpoint, no explicit feedback
        assert len(frequency) == 12
        assert [int.from_bytes(frequency[i:i+4], "little") for i in (0, 4, 8)] == [44100, 48000, 96000]
        # Walk the actual class descriptor pointer array advertised to the host.
        pointers = data("uac2_fs_desc_0")
        addresses = [int.from_bytes(pointers[i:i+4], "little") for i in range(0, len(pointers), 4)]
        descriptors = []
        for address in addresses:
            if not address:
                break
            length = at(address, 1)[0]
            descriptors.append(at(address, length))
        alternates = {}
        active = None
        for desc in descriptors:
            if desc[1] == 4 and desc[5:7] == bytes([1, 2]):
                active = desc[3]
                alternates[active] = {"endpoints": desc[4], "interface": desc[2]}
            elif active and desc[1:3] == bytes([0x24, 2]):
                alternates[active]["format"] = (desc[4], desc[5])
            elif active and desc[1] == 5:
                alternates[active]["mps"] = int.from_bytes(desc[4:6], "little")
                alternates[active]["address"] = desc[2]
        assert set(alternates) == {0, 1, 2}
        assert alternates[0]["endpoints"] == 0
        assert alternates[1]["format"] == (2, 16) and alternates[1]["mps"] == 384
        assert alternates[2]["format"] == (3, 24) and alternates[2]["mps"] == 576
        assert alternates[1]["interface"] == alternates[2]["interface"]
        assert alternates[1]["address"] == alternates[2]["address"]
        # The patched class must still look up the original 16-bit endpoint.
        index = int.from_bytes(data("ep_indexes_0"), "little")
        assert descriptors[index] == endpoint
        clock = data("uac2_ac_entity_DT_N_S_usb_audio2_S_clock")
        assert clock[5] & 3 == 3  # host-programmable clock frequency control
    print("ELF: selectable 44.1/48/96 kHz, stereo, 16/24-bit alternate settings, shared ISO IN, 384/576-byte maxima verified")


if __name__ == "__main__":
    main(sys.argv[1])
