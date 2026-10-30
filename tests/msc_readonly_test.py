#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compile the real generated SCSI code on the host with mocked disk I/O."""
import argparse
from pathlib import Path
import subprocess
import tempfile

HEADERS = {
    "kernel.h": """
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#define __packed __attribute__((packed))
#define __ASSERT_NO_MSG(x) assert(x)
""",
    "sys/util.h": """
#define MIN(a,b) ((a)<(b)?(a):(b))
#define BIT(n) (1U<<(n))
#define BIT_MASK(n) (BIT(n)-1U)
#define BUILD_ASSERT(x) _Static_assert(x, #x)
""",
    "sys/byteorder.h": """
#define sys_cpu_to_be16(x) __builtin_bswap16(x)
#define sys_cpu_to_be32(x) __builtin_bswap32(x)
#define sys_be16_to_cpu(x) __builtin_bswap16(x)
#define sys_be32_to_cpu(x) __builtin_bswap32(x)
static inline void sys_put_be16(uint16_t v, uint8_t *b) {b[0]=v>>8; b[1]=v;}
""",
    "logging/log.h": """
#define LOG_MODULE_DECLARE(...)
#define LOG_DBG(...)
#define LOG_WRN(...)
#define LOG_ERR(...)
""",
    "usb/usbd.h": "#define USBD_MAX_BULK_MPS 64\n",
    "storage/disk_access.h": """
#define DISK_STATUS_OK 0
#define DISK_STATUS_WR_PROTECT 4
#define DISK_IOCTL_GET_SECTOR_COUNT 1
#define DISK_IOCTL_GET_SECTOR_SIZE 2
#define DISK_IOCTL_CTRL_SYNC 5
int disk_access_status(const char *name);
int disk_access_ioctl(const char *name, uint8_t cmd, void *buf);
int disk_access_read(const char *name, uint8_t *buf, uint32_t sector, uint32_t count);
int disk_access_write(const char *name, const uint8_t *buf, uint32_t sector, uint32_t count);
""",
}

HARNESS = r'''
#include <zephyr/kernel.h>
#include <zephyr/storage/disk_access.h>
#include "usbd_msc_scsi.h"
#include <stdio.h>
static int writes;
int disk_access_status(const char *n) {(void)n; return DISK_STATUS_WR_PROTECT;}
int disk_access_ioctl(const char *n,uint8_t cmd,void *b) {
    (void)n; if (!b) return 0; *(uint32_t *)b = cmd==DISK_IOCTL_GET_SECTOR_COUNT?1024:512; return 0;
}
int disk_access_read(const char *n,uint8_t *b,uint32_t s,uint32_t c) {
    (void)n; (void)s; memset(b,0xa5,c*512); return 0;
}
int disk_access_write(const char *n,const uint8_t *b,uint32_t s,uint32_t c) {
    (void)n;(void)b;(void)s;(void)c; ++writes; return -EROFS;
}
int main(void) {
    struct scsi_ctx ctx; uint8_t out[512];
    scsi_init(&ctx,"OLFTOOLS","OLF","Tools","1.00");
    const uint8_t ready[6]={0};
    scsi_cmd(&ctx,ready,6,out); assert(ctx.status==GOOD);
    const uint8_t mode6[6]={0x1a,0,0x3f,0,255,0};
    assert(scsi_cmd(&ctx,mode6,6,out)==4 && ctx.status==GOOD && out[2]==0x80);
    const uint8_t mode10[10]={0x5a,0,0x3f,0,0,0,0,0,255,0};
    assert(scsi_cmd(&ctx,mode10,10,out)==8 && ctx.status==GOOD && out[3]==0x80);
    const uint8_t cap[10]={0x25};
    assert(scsi_cmd(&ctx,cap,10,out)==8 && ctx.status==GOOD);
    assert(out[2]==3 && out[3]==255 && out[6]==2 && out[7]==0);
    const uint8_t read[10]={0x28,0,0,0,0,0,0,0,1,0};
    scsi_cmd(&ctx,read,10,out); assert(ctx.status==GOOD);
    assert(scsi_read_data(&ctx,out,512)==512 && out[0]==0xa5 && out[511]==0xa5);
    const uint8_t write[10]={0x2a,0,0,0,0,0,0,0,1,0};
    assert(scsi_cmd(&ctx,write,10,out)==0 && ctx.status==CHECK_CONDITION);
    assert(ctx.sense_key==DATA_PROTECT && ctx.asc==0x2700 && writes==0);
    puts("Real SCSI code: ready/read/capacity, both write-protect headers and write rejection passed");
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("generated", type=Path)
    parser.add_argument("sdk_class", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="olf-scsi-") as directory:
        root = Path(directory)
        for name, content in HEADERS.items():
            path = root / "zephyr" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        harness = root / "test.c"
        harness.write_text(HARNESS)
        binary = root / "test"
        subprocess.run(["cc", "-std=c11", "-Wno-pointer-sign", "-fsanitize=address,undefined",
                        "-DCONFIG_USBD_MSC_SCSI_BUFFER_SIZE=512", "-I"+str(root),
                        "-I"+str(args.sdk_class), str(harness), str(args.generated), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
