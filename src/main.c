/* SPDX-License-Identifier: Apache-2.0 */
#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/usb/usbd.h>
#include <zephyr/usb/usb_ch9.h>
#include "tone.h"
#include "tools_disk.h"
#include <zephyr/sys/util.h>
#include <zephyr/logging/log.h>
#include <errno.h>

LOG_MODULE_REGISTER(multi_cdc, LOG_LEVEL_INF);

/* USB identity for OLFs Signal Generator. */
#define DEV_VID 0x16d0
#define DEV_PID 0x1471

USBD_DEVICE_DEFINE(multi_cdc_usbd, DEVICE_DT_GET(DT_NODELABEL(zephyr_udc0)),
                   DEV_VID, DEV_PID);
USBD_DESC_LANG_DEFINE(usb_lang);
USBD_DESC_MANUFACTURER_DEFINE(usb_manufacturer, "eisenzelt.de");
USBD_DESC_PRODUCT_DEFINE(usb_product, "OLFs Signal Generator");
USBD_DESC_SERIAL_NUMBER_DEFINE(usb_serial);
USBD_DESC_CONFIG_DEFINE(fs_cfg_desc, "Audio + Shell + Logs + Tools");
USBD_CONFIGURATION_DEFINE(fs_cfg, 0, 50, &fs_cfg_desc);

static int setup_usb(void)
{
    int err;
    err = usbd_add_descriptor(&multi_cdc_usbd, &usb_lang);
    if (err) return err;
    err = usbd_add_descriptor(&multi_cdc_usbd, &usb_manufacturer);
    if (err) return err;
    err = usbd_add_descriptor(&multi_cdc_usbd, &usb_product);
    if (err) return err;
    err = usbd_add_descriptor(&multi_cdc_usbd, &usb_serial);
    if (err) return err;
    err = usbd_add_configuration(&multi_cdc_usbd, USBD_SPEED_FS, &fs_cfg);
    if (err) return err;
    /* Register two CDC ports, UAC2 audio and the read-only tools disk. */
    err = usbd_register_all_classes(&multi_cdc_usbd, USBD_SPEED_FS, 1, NULL);
    if (err) return err;
    usbd_device_set_code_triple(&multi_cdc_usbd, USBD_SPEED_FS,
                                USB_BCC_MISCELLANEOUS, 0x02, 0x01);
    err = usbd_init(&multi_cdc_usbd);
    if (err) return err;
    return usbd_enable(&multi_cdc_usbd);
}

int main(void)
{
    int err;
    err = tools_disk_init();
    if (err) {
        return err;
    }
    err = tone_usb_init();
    if (err) {
        return err;
    }

    err = setup_usb();
    if (err) {
        /* CDC console may not be operational yet: inspect return code in debugger. */
        return err;
    }
    printk("USB initialized: audio / shell / logs / tools drive\n");
    LOG_INF("USB audio generator ready: 44100/48000/96000 Hz (default %u Hz), 16/24-bit stereo", TONE_DEFAULT_SAMPLE_RATE);
    while (true) {
        k_sleep(K_SECONDS(5));
    }
    return 0;
}
