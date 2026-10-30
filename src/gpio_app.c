/* SPDX-License-Identifier: Apache-2.0 */
#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>
#include <zephyr/shell/shell.h>
#include <errno.h>
#include <string.h>

LOG_MODULE_REGISTER(gpio_app, LOG_LEVEL_DBG);

static const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(DT_ALIAS(led0), gpios);

static int cmd_gpio_app_led(const struct shell *sh, size_t argc, char **argv)
{
    int err;
    int active;

    ARG_UNUSED(argc);
    if (strcmp(argv[1], "on") == 0) {
        active = 1;
    } else if (strcmp(argv[1], "off") == 0) {
        active = 0;
    } else {
        shell_error(sh, "Use: gpio_app led on|off");
        return -EINVAL;
    }

    if (!gpio_is_ready_dt(&led)) {
        LOG_ERR("LED GPIO device is not ready");
        shell_error(sh, "LED GPIO device is not ready");
        return -ENODEV;
    }

    /* Configure directly to the requested logical state, respecting active-low. */
    err = gpio_pin_configure_dt(&led, active ? GPIO_OUTPUT_ACTIVE : GPIO_OUTPUT_INACTIVE);
    if (err < 0) {
        LOG_ERR("LED configuration failed: %d", err);
        shell_error(sh, "LED configuration failed: %d", err);
        return err;
    }

    LOG_DBG("%s pin %u: LED %s (logical %d)",
            led.port->name, led.pin, active ? "on" : "off", active);
    shell_print(sh, "LED %s", active ? "on" : "off");
    return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(gpio_app_commands,
    SHELL_CMD_ARG(led, NULL, "Set green LED: on|off", cmd_gpio_app_led, 2, 0),
    SHELL_SUBCMD_SET_END
);

SHELL_CMD_REGISTER(gpio_app, &gpio_app_commands, "Application GPIO controls", NULL);
