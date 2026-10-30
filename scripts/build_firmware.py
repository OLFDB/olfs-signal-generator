#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the Open-Bootloader application sysbuild using the selected Nordic toolchain environment."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, default=Path("/opt/nordic/ncs/v3.2.1"))
    parser.add_argument("--toolchain", type=Path, default=Path("/opt/nordic/ncs/toolchains/322ac893fe"))
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    parser.add_argument("--pristine", action="store_true")
    args = parser.parse_args()
    project = Path(__file__).resolve().parent.parent
    toolchain = args.toolchain.resolve()
    env = dict(os.environ)
    for entry in json.loads((toolchain / "environment.json").read_text())["env_vars"]:
        name = entry["key"]
        if entry["type"] == "relative_paths":
            value = os.pathsep.join(str(toolchain / value) for value in entry["values"])
        else:
            value = entry["value"]
        if entry.get("existing_value_treatment") == "prepend_to" and env.get(name):
            value += os.pathsep + env[name]
        env[name] = value
    build = args.build_dir if args.build_dir.is_absolute() else project / args.build_dir
    command = [str(toolchain / "bin/west"), "build", "--sysbuild", "--build-dir", str(build),
               "-b", "nrf52840dongle/nrf52840"]
    if args.pristine:
        command += ["--pristine", "always"]
    command += [str(project), "--", "-DPython3_EXECUTABLE=" + str(toolchain / "bin/python")]
    subprocess.run(command, cwd=args.sdk.resolve(), env=env, check=True)


if __name__ == "__main__":
    main()
