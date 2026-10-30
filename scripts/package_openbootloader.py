#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Package the application for the factory Nordic USB Open Bootloader (no signing key)."""
import argparse
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--nrfutil", default="nrfutil")
parser.add_argument("--version", type=int, default=1)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
subprocess.run([args.nrfutil, "nrf5sdk-tools", "pkg", "generate",
                "--hw-version", "52", "--sd-req", "0x00",
                "--application", str(root / "build/multi_cdc_vscode_ready/zephyr/zephyr.hex"),
                "--application-version", str(args.version),
                str(root / "build/multi_cdc_dfu.zip")], check=True)
