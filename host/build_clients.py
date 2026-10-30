#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build compact native clients on macOS/Xcode using Zig 0.14.1 for cross targets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zig", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    out = root / "dist"
    out.mkdir(exist_ok=True)
    env = dict(os.environ, ZIG_GLOBAL_CACHE_DIR=str(root / ".zig-cache"),
               ZIG_LOCAL_CACHE_DIR=str(root / ".zig-cache-local"))
    common = ["-std=c11", "-Os", "-Wall", "-Wextra", "-Werror"]
    src = str(root / "olfctl.c")
    for arch in ("x86_64", "arm64"):
        subprocess.run(["clang", *common, "-arch", arch, "-mmacosx-version-min=11.0",
                        src, "-o", str(out / ("mac-" + arch))], check=True)
    subprocess.run(["lipo", "-create", str(out / "mac-x86_64"), str(out / "mac-arm64"),
                    "-output", str(out / "OLF-MAC")], check=True)
    subprocess.run(["strip", "-x", str(out / "OLF-MAC")], check=True)
    # Apple Silicon requires a valid signature; ad-hoc signing needs no account.
    subprocess.run(["codesign", "--force", "--sign", "-", "--timestamp=none",
                    str(out / "OLF-MAC")], check=True)
    for target, name in (("x86_64-windows-gnu", "OLF-WIN.EXE"),
                         ("aarch64-windows-gnu", "OLF-WARM.EXE"),
                         ("x86_64-linux-musl", "OLF-LX64"),
                         ("aarch64-linux-musl", "OLF-LARM")):
        command = [str(args.zig.resolve()), "cc", "-target", target, *common, "-s", src,
                   "-o", str(out / name)]
        if "linux" in target:
            command.append("-static")
        print("Building", name, flush=True)
        subprocess.run(command, check=True, env=env)
    names = ("OLF-WIN.EXE", "OLF-WARM.EXE", "OLF-LX64", "OLF-LARM", "OLF-MAC")
    checksums = "".join(hashlib.sha256((out / n).read_bytes()).hexdigest() + "  " + n + "\n" for n in names)
    (out / "SHA256.TXT").write_text(checksums)
    provenance = {
        "source_sha256": hashlib.sha256((root / "olfctl.c").read_bytes()).hexdigest(),
        "zig_version": subprocess.check_output([str(args.zig.resolve()), "version"], text=True).strip(),
        "binaries": {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in names},
    }
    (out / "BUILD.TXT").write_text(json.dumps(provenance, indent=2) + "\n")
    for name in names:
        print(name, (out / name).stat().st_size, "bytes")


if __name__ == "__main__":
    main()
