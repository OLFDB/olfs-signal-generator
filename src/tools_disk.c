/* SPDX-License-Identifier: Apache-2.0 */
#include "tools_disk.h"
#include <zephyr/storage/disk_access.h>
#include <zephyr/usb/class/usbd_msc.h>
#include <errno.h>
#include <string.h>

#define DISK_NAME "OLFTOOLS"
#define SECTOR_SIZE 512U
#define SECTORS 1024U

extern const uint8_t olf_tools_disk_start[];
extern const uint8_t olf_tools_disk_end[];

USBD_DEFINE_MSC_LUN(olf_tools, DISK_NAME, "OLF", "Console Tools", "1.00");

static int disk_init(struct disk_info *disk) { ARG_UNUSED(disk); return 0; }
static int disk_status(struct disk_info *disk)
{
    ARG_UNUSED(disk);
    return DISK_STATUS_WR_PROTECT;
}

static int disk_read(struct disk_info *disk, uint8_t *buffer, uint32_t start, uint32_t count)
{
    ARG_UNUSED(disk);
    if (start > SECTORS || count > SECTORS - start) return -EINVAL;
    memcpy(buffer, olf_tools_disk_start + start * SECTOR_SIZE, count * SECTOR_SIZE);
    return 0;
}

static int disk_write(struct disk_info *disk, const uint8_t *buffer, uint32_t start, uint32_t count)
{
    ARG_UNUSED(disk); ARG_UNUSED(buffer); ARG_UNUSED(start); ARG_UNUSED(count);
    return -EROFS;
}

static int disk_ioctl(struct disk_info *disk, uint8_t command, void *buffer)
{
    ARG_UNUSED(disk);
    switch (command) {
    case DISK_IOCTL_GET_SECTOR_COUNT: *(uint32_t *)buffer = SECTORS; return 0;
    case DISK_IOCTL_GET_SECTOR_SIZE: *(uint32_t *)buffer = SECTOR_SIZE; return 0;
    case DISK_IOCTL_GET_ERASE_BLOCK_SZ: *(uint32_t *)buffer = 1; return 0;
    case DISK_IOCTL_CTRL_SYNC:
    case DISK_IOCTL_CTRL_INIT:
    case DISK_IOCTL_CTRL_DEINIT: return 0;
    default: return -EINVAL;
    }
}

static const struct disk_operations disk_ops = {
    .init = disk_init, .status = disk_status, .read = disk_read,
    .write = disk_write, .ioctl = disk_ioctl,
};
static struct disk_info tools_disk = { .name = DISK_NAME, .ops = &disk_ops };

int tools_disk_init(void)
{
    if ((size_t)(olf_tools_disk_end - olf_tools_disk_start) != SECTOR_SIZE * SECTORS) return -EINVAL;
    int err = disk_access_register(&tools_disk);
    return err ? err : disk_access_init(DISK_NAME);
}
