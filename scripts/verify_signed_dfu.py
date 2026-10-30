#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify Nordic DFU ECDSA-P256/SHA256 init signature and firmware payload hash.

Uses the ecdsa package included in the Nordic toolchain Python. Verification
requires only the public key, never the private signing key.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from ecdsa import NIST256p, VerifyingKey


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(data):
    offset = 0

    def varint():
        nonlocal offset
        value = 0
        for shift in range(0, 70, 7):
            require(offset < len(data), "Truncated protobuf integer")
            byte = data[offset]
            offset += 1
            value |= (byte & 127) << shift
            if not byte & 128:
                return value
        raise ValueError("Oversized protobuf integer")

    result = {}
    while offset < len(data):
        tag = varint()
        number, wire = tag >> 3, tag & 7
        require(number > 0 and number not in result, "Unexpected duplicate/zero field")
        if wire == 0:
            value = varint()
        elif wire == 2:
            length = varint()
            require(offset + length <= len(data), "Truncated protobuf field")
            value = data[offset:offset + length]
            offset += length
        else:
            raise ValueError("Unexpected protobuf wire type")
        result[number] = value
    return result


def verify(package, public_key, require_boot_signature=False):
    key = VerifyingKey.from_pem(Path(public_key).read_text())
    require(key.curve == NIST256p, "Expected ECDSA P-256 key")
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read("manifest.json"))["manifest"]
        require(set(manifest) == {"application"}, "Expected application-only DFU")
        application = manifest["application"]
        firmware = archive.read(application["bin_file"])
        packet = fields(archive.read(application["dat_file"]))
    require(set(packet) == {2}, "Expected signed DFU packet")
    signed = fields(packet[2])
    require(signed[2] == 0 and len(signed[3]) == 64, "Expected ECDSA-P256-SHA256 signature")
    command = fields(signed[1])
    require(command[1] == 1, "Expected INIT command")
    init_bytes = command[2]
    init = fields(init_bytes)
    signature = signed[3][:32][::-1] + signed[3][32:][::-1]
    require(key.verify(signature, init_bytes, hashfunc=hashlib.sha256), "Invalid signature")
    digest = fields(init[8])
    require(digest[1] == 3, "Expected SHA-256 payload hash")
    require(digest[2] == hashlib.sha256(firmware).digest()[::-1], "Firmware hash mismatch")
    require(init[4] == 0 and init[7] == len(firmware), "Application type/size mismatch")
    boot_verified = False
    if 10 in init:
        boot = fields(init[10])
        if boot[1] == 3:
            require(len(boot[2]) == 64, "Expected ECDSA boot validation signature")
            boot_signature = boot[2][:32][::-1] + boot[2][32:][::-1]
            require(key.verify(boot_signature, firmware, hashfunc=hashlib.sha256),
                    "Invalid firmware boot signature")
            boot_verified = True
    require(not require_boot_signature or boot_verified, "Bootloader requires ECDSA boot validation")
    return {
        "signature": "ECDSA-P256-SHA256",
        "verified": True,
        "boot_validation_signature_verified": boot_verified,
        "public_key_der_sha256": hashlib.sha256(key.to_der()).hexdigest(),
        "firmware_bin_sha256": hashlib.sha256(firmware).hexdigest(),
        "package_sha256": hashlib.sha256(Path(package).read_bytes()).hexdigest(),
        "application_bytes": len(firmware),
        "application_version": init[1],
        "hardware_version": init[2],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("public_key", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--require-boot-signature", action="store_true")
    args = parser.parse_args()
    text = json.dumps(verify(args.package, args.public_key, args.require_boot_signature), indent=2) + "\n"
    if args.report:
        args.report.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
