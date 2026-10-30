#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Make NCS 3.2.1 MSC SCSI correctly expose a read-only disk."""
import sys
from pathlib import Path
from prepare_nrf_iso_in import replace_once

source = Path(sys.argv[1]).read_text()
source = replace_once(source, "\treturn status;\n}",
    "\t/* Write protection is a property, not a medium-not-ready error. */\n"
    "\treturn status < 0 ? status : status & ~DISK_STATUS_WR_PROTECT;\n}")
old = "\tr.device_specific_parameter = 0x00;"
if source.count(old) != 2:
    raise ValueError("Expected MODE SENSE(6) and MODE SENSE(10) headers")
source = source.replace(old,
    "\tr.device_specific_parameter = (disk_access_status(ctx->disk) & DISK_STATUS_WR_PROTECT) ? 0x80 : 0;")
old = "\tctx->write_cb = store_write_10;"
source = replace_once(source, old,
    "\tif (disk_access_status(ctx->disk) & DISK_STATUS_WR_PROTECT) {\n"
    "\t\tctx->status = CHECK_CONDITION;\n\t\tctx->sense_key = DATA_PROTECT;\n"
    "\t\tctx->asc = (enum scsi_additional_sense_code)0x2700; /* WRITE PROTECTED */\n"
    "\t\treturn 0;\n\t}\n\n" + old)
output = Path(sys.argv[2])
output.parent.mkdir(parents=True, exist_ok=True)
if not output.exists() or output.read_text() != source:
    output.write_text(source)
