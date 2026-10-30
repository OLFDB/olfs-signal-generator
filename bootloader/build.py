#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the application for the existing Nordic Open Bootloader."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parent.parent / "scripts/build_firmware.py"),
               run_name="__main__")
