#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Create a project-local ISO-IN-only variant of NCS 3.2.1's nRF UDC driver.

Never modifies the SDK. Exact anchors deliberately fail on incompatible SDK
changes instead of silently compiling a partially applied customization.
"""
import argparse
from pathlib import Path


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"Unsupported nRF UDC source: expected exactly one {old!r}")
    return source.replace(old, new, 1)


def prepare(source):
    source = replace_once(
        source,
        "NRF_USBD->ISOSPLIT = USBD_ISOSPLIT_SPLIT_HalfIN << USBD_ISOSPLIT_SPLIT_Pos;",
        "/* Project mode: ISO IN owns the complete buffer; ISO OUT is unavailable. */\n"
        "\tNRF_USBD->ISOSPLIT = USBD_ISOSPLIT_SPLIT_OneDir << USBD_ISOSPLIT_SPLIT_Pos;",
    )
    source = replace_once(
        source,
        "for (int i = 0; i < ARRAY_SIZE(ep_cfg_out); i++) {\n",
        "for (int i = 0; i < ARRAY_SIZE(ep_cfg_out); i++) {\n"
        "\t\t/* Do not advertise or register the ISO OUT endpoint in IN-only mode. */\n"
        "\t\tif (i > CFG_EPOUT_CNT) {\n\t\t\tcontinue;\n\t\t}\n",
    )
    source = replace_once(
        source,
        "ep_cfg_in[i].caps.mps = NRF_USBD_COMMON_ISOSIZE / 2;",
        "ep_cfg_in[i].caps.mps = NRF_USBD_COMMON_ISOSIZE;",
    )
    # A second guard prevents ISO OUT from accidentally reaching the hardware,
    # even if a future change bypasses endpoint registration/capability checks.
    source = replace_once(
        source,
        "\t__ASSERT_NO_MSG(cfg);\n\tmps = (udc_mps_ep_size(cfg) == 0) ? cfg->caps.mps : udc_mps_ep_size(cfg);",
        "\t__ASSERT_NO_MSG(cfg);\n"
        "\tif (NRF_USBD_EPISO_CHECK(cfg->addr) && USB_EP_DIR_IS_OUT(cfg->addr)) {\n"
        "\t\treturn -ENOTSUP;\n\t}\n"
        "\tmps = (udc_mps_ep_size(cfg) == 0) ? cfg->caps.mps : udc_mps_ep_size(cfg);",
    )
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = prepare(args.source.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.output.exists() or args.output.read_text() != result:
        args.output.write_text(result)


if __name__ == "__main__":
    main()
