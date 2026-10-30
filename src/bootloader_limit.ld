/* Preserve Nordic MBR, original Open Bootloader and settings. */
/* __rom_region_end includes MPU rounding; _flash_used measures stored bytes. */
ASSERT(__rom_region_start == 0x1000, "Open Bootloader application must start at 0x1000")
ASSERT(__rom_region_start + _flash_used <= 0xe0000, "Application overlaps factory bootloader")
