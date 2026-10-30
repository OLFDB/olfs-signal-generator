#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Create a project-local UAC2 variant with 16/24-bit alternate settings."""
import argparse
from pathlib import Path
from prepare_nrf_iso_in import replace_once


def write_changed(path, text):
    if not path.exists() or path.read_text() != text:
        path.write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("class_source", type=Path)
    parser.add_argument("macro_header", type=Path)
    parser.add_argument("extension", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    source = replace_once(args.class_source.read_text(),
                          '#include "usbd_uac2_macros.h"',
                          '#include "usbd_uac2_macros_formats.h"\n#include "uac2_formats.h"')
    source = replace_once(source, "\t/* Notify application about terminal state change */",
                          "\tolf_audio_format_update(alternate);\n\n"
                          "\t/* Notify application about terminal state change */")
    header = args.macro_header.read_text()
    for macro in ("AS_DESCRIPTORS_ARRAYS", "AS_FS_DESCRIPTORS_PTRS"):
        header = replace_once(header, f"#define {macro}(node)",
                              f"#define OLF_BASE_{macro}(node)")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_changed(args.output_dir / "usbd_uac2_formats.c", source)
    write_changed(args.output_dir / "usbd_uac2_macros_formats.h", header)
    write_changed(args.output_dir / "uac2_formats.h", args.extension.read_text())


if __name__ == "__main__":
    main()
