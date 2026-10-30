/* SPDX-License-Identifier: Apache-2.0 */
#include "tone.h"

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/shell/shell.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/usb/usbd.h>
#include <zephyr/usb/class/usbd_uac2.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

LOG_MODULE_REGISTER(generator, LOG_LEVEL_INF);

#define MAX_FRAME_SAMPLES DIV_ROUND_UP(TONE_MAX_SAMPLE_RATE, 1000U)
#define FRAME_BYTES (MAX_FRAME_SAMPLES * TONE_CHANNELS * TONE_SAMPLE_BYTES)
#define OUTPUT_TERMINAL UAC2_ENTITY_ID(DT_NODELABEL(tone_usb_out))

BUILD_ASSERT(TONE_MAX_SAMPLE_RATE == DT_PROP_BY_IDX(DT_NODELABEL(tone_clock), sampling_frequencies, 2),
             "Generator rate must match USB clock descriptor");
BUILD_ASSERT(FRAME_BYTES <= 1023U, "Stereo PCM packet exceeds full-speed ISO maximum");

K_MEM_SLAB_DEFINE_STATIC(audio_slab, ROUND_UP(FRAME_BYTES, UDC_BUF_GRANULARITY),
                         4, UDC_BUF_ALIGN);

static struct k_spinlock settings_lock;
static struct tone_stereo_settings settings = {
    .channel = {
        { .wave = TONE_SINE, .frequency = 1000, .amplitude = 25, .running = false },
        { .wave = TONE_SINE, .frequency = 1000, .amplitude = 25, .running = false },
    },
    .linked = true,
};
/* Only the serialized USB SOF callback touches oscillator phase. */
static struct tone_state oscillator[TONE_CHANNELS];
static struct tone_pacing pacing;
static atomic_t sample_rate = ATOMIC_INIT(TONE_DEFAULT_SAMPLE_RATE);
static atomic_t sample_bytes = ATOMIC_INIT(2);
static atomic_t streaming;
static atomic_t packets;
static atomic_t dropped;

static const char *const wave_names[] = { "sine", "triangle", "square" };

/* Called by the project-local UAC2 class before the terminal state callback. */
void olf_audio_format_update(uint8_t alternate)
{
    if (alternate == 1 || alternate == 2) {
        unsigned int bytes = alternate == 1 ? 2U : 3U;
        atomic_set(&sample_bytes, bytes);
        LOG_INF("USB format selected by host: %u-bit", bytes * 8U);
    }
}

static struct tone_stereo_settings get_settings(void)
{
    k_spinlock_key_t key = k_spin_lock(&settings_lock);
    struct tone_stereo_settings copy = settings;

    k_spin_unlock(&settings_lock, key);
    return copy;
}

static void audio_release(const struct device *dev, uint8_t terminal,
                          void *buf, void *user_data)
{
    ARG_UNUSED(dev);
    ARG_UNUSED(terminal);
    ARG_UNUSED(user_data);
    k_mem_slab_free(&audio_slab, buf);
}

static void audio_terminal(const struct device *dev, uint8_t terminal,
                           bool enabled, bool microframes, void *user_data)
{
    ARG_UNUSED(dev);
    ARG_UNUSED(user_data);
    if (terminal == OUTPUT_TERMINAL) {
        atomic_set(&streaming, enabled && !microframes);
        LOG_INF("Host audio capture %s", enabled ? "enabled" : "disabled");
    }
}

static void audio_sof(const struct device *dev, void *user_data)
{
    ARG_UNUSED(user_data);
    if (!atomic_get(&streaming)) {
        return;
    }

    uint32_t rate = (uint32_t)atomic_get(&sample_rate);
    unsigned int bytes = (unsigned int)atomic_get(&sample_bytes);
    size_t frames = tone_next_frames(&pacing, rate);
    struct tone_stereo_settings current = get_settings();
    int32_t samples[MAX_FRAME_SAMPLES * TONE_CHANNELS];
    void *buffer;

    /* Advance phase even if this frame cannot be queued. */
    tone_render_stereo(oscillator, &current, rate, samples, frames);
    if (k_mem_slab_alloc(&audio_slab, &buffer, K_NO_WAIT)) {
        atomic_inc(&dropped);
        return;
    }
    if (bytes == 2U) {
        tone_pack_pcm16(buffer, samples, frames * TONE_CHANNELS);
    } else {
        tone_pack_pcm24(buffer, samples, frames * TONE_CHANNELS);
    }
    if (usbd_uac2_send(dev, OUTPUT_TERMINAL, buffer, frames * TONE_CHANNELS * bytes) < 0) {
        k_mem_slab_free(&audio_slab, buffer);
        atomic_inc(&dropped);
    } else {
        atomic_inc(&packets);
    }
}

static uint32_t audio_get_rate(const struct device *dev, uint8_t clock_id, void *user_data)
{
    ARG_UNUSED(dev);
    ARG_UNUSED(clock_id);
    ARG_UNUSED(user_data);
    return (uint32_t)atomic_get(&sample_rate);
}

static int audio_set_rate(const struct device *dev, uint8_t clock_id,
                          uint32_t rate, void *user_data)
{
    ARG_UNUSED(dev);
    ARG_UNUSED(user_data);
    if (clock_id != UAC2_ENTITY_ID(DT_NODELABEL(tone_clock)) ||
        (rate != 44100U && rate != 48000U && rate != 96000U)) {
        return -EINVAL;
    }
    atomic_set(&sample_rate, rate);
    LOG_INF("USB sample rate selected by host: %u Hz", rate);
    return 0;
}

static const struct uac2_ops audio_ops = {
    .sof_cb = audio_sof,
    .terminal_update_cb = audio_terminal,
    .buf_release_cb = audio_release,
    .get_sample_rate = audio_get_rate,
    .set_sample_rate = audio_set_rate,
};

int tone_usb_init(void)
{
    const struct device *dev = DEVICE_DT_GET(DT_NODELABEL(tone_audio));

    if (!device_is_ready(dev)) {
        return -ENODEV;
    }
    usbd_uac2_set_ops(dev, &audio_ops, NULL);
    return 0;
}

static int cmd_status(const struct shell *sh, size_t argc, char **argv)
{
    ARG_UNUSED(argc);
    ARG_UNUSED(argv);
    struct tone_stereo_settings current = get_settings();

    shell_print(sh, "Channels: %s", current.linked ? "linked (left master)" : "independent");
    for (size_t i = 0; i < TONE_CHANNELS; ++i) {
        const struct tone_settings *ch = &current.channel[i];
        shell_print(sh, "%s: %s, %s, %u Hz, %u%% peak amplitude",
                    i ? "right" : "left", ch->running ? "running" : "stopped",
                    wave_names[ch->wave], ch->frequency, ch->amplitude);
    }
    shell_print(sh, "USB: %u Hz / %u-bit / stereo, host capture %s",
                (unsigned int)atomic_get(&sample_rate), (unsigned int)atomic_get(&sample_bytes) * 8U,
                atomic_get(&streaming) ? "active" : "inactive");
    shell_print(sh, "Packets queued: %u, dropped: %u",
                (unsigned int)atomic_get(&packets), (unsigned int)atomic_get(&dropped));
    return 0;
}

/* Optional final argument selects a channel; omitted means both. */
static int channel_mask(const struct shell *sh, const char *name)
{
    if (!name || strcmp(name, "both") == 0) return 3;
    if (strcmp(name, "left") == 0) return 1;
    if (strcmp(name, "right") == 0) return 2;
    shell_error(sh, "Channel must be left, right or both");
    return -EINVAL;
}

static int cmd_run(const struct shell *sh, size_t argc, char **argv)
{
    int mask = channel_mask(sh, argc == 2 ? argv[1] : NULL);
    if (mask < 0) return mask;
    bool run = strcmp(argv[0], "start") == 0;
    k_spinlock_key_t key = k_spin_lock(&settings_lock);
    if (settings.linked) mask = 3;
    for (size_t i = 0; i < TONE_CHANNELS; ++i) {
        if (mask & BIT(i)) settings.channel[i].running = run;
    }
    k_spin_unlock(&settings_lock, key);
    LOG_INF("Generator %s, channel mask %d", run ? "started" : "stopped", mask);
    return cmd_status(sh, 0, NULL);
}

static int cmd_wave(const struct shell *sh, size_t argc, char **argv)
{
    int mask = channel_mask(sh, argc == 3 ? argv[2] : NULL);
    if (mask < 0) return mask;
    for (size_t wave = 0; wave < ARRAY_SIZE(wave_names); ++wave) {
        if (strcmp(argv[1], wave_names[wave]) == 0) {
            k_spinlock_key_t key = k_spin_lock(&settings_lock);
            if (settings.linked) mask = 3;
            for (size_t i = 0; i < TONE_CHANNELS; ++i) {
                if (mask & BIT(i)) settings.channel[i].wave = (enum tone_wave)wave;
            }
            k_spin_unlock(&settings_lock, key);
            LOG_INF("Waveform: %s, channel mask %d", wave_names[wave], mask);
            return cmd_status(sh, 0, NULL);
        }
    }
    shell_error(sh, "Use: gen wave sine|triangle|square [left|right|both]");
    return -EINVAL;
}

static int cmd_number(const struct shell *sh, size_t argc, char **argv)
{
    int mask = channel_mask(sh, argc == 3 ? argv[2] : NULL);
    if (mask < 0) return mask;
    bool frequency = strcmp(argv[0], "freq") == 0;
    unsigned long min = frequency ? 1 : 0;
    unsigned long max = frequency ? 20000 : 100;
    char *end;

    errno = 0;
    unsigned long value = strtoul(argv[1], &end, 10);
    if (argv[1][0] < '0' || argv[1][0] > '9' || *end || errno == ERANGE ||
        value < min || value > max) {
        shell_error(sh, "%s requires an integer from %lu to %lu", argv[0], min, max);
        return -EINVAL;
    }
    k_spinlock_key_t key = k_spin_lock(&settings_lock);
    if (settings.linked) mask = 3;
    for (size_t i = 0; i < TONE_CHANNELS; ++i) {
        if (!(mask & BIT(i))) continue;
        if (frequency) settings.channel[i].frequency = (uint32_t)value;
        else settings.channel[i].amplitude = (uint32_t)value;
    }
    k_spin_unlock(&settings_lock, key);
    LOG_INF("%s: %lu, channel mask %d", frequency ? "Frequency (Hz)" : "Amplitude (%)", value, mask);
    return cmd_status(sh, 0, NULL);
}

static int cmd_link(const struct shell *sh, size_t argc, char **argv)
{
    ARG_UNUSED(argc);
    bool link;
    if (strcmp(argv[1], "on") == 0) link = true;
    else if (strcmp(argv[1], "off") == 0) link = false;
    else {
        shell_error(sh, "Use: gen link on|off");
        return -EINVAL;
    }
    k_spinlock_key_t key = k_spin_lock(&settings_lock);
    settings.linked = link;
    if (link) settings.channel[1] = settings.channel[0];
    k_spin_unlock(&settings_lock, key);
    LOG_INF("Channels %s", link ? "linked (left master)" : "independent");
    return cmd_status(sh, 0, NULL);
}

SHELL_STATIC_SUBCMD_SET_CREATE(generator_commands,
    SHELL_CMD_ARG(status, NULL, "Show generator and USB stream status", cmd_status, 1, 0),
    SHELL_CMD_ARG(start, NULL, "Start [left|right|both]", cmd_run, 1, 1),
    SHELL_CMD_ARG(stop, NULL, "Stop [left|right|both]", cmd_run, 1, 1),
    SHELL_CMD_ARG(wave, NULL, "sine|triangle|square [left|right|both]", cmd_wave, 2, 1),
    SHELL_CMD_ARG(freq, NULL, "1..20000 Hz [left|right|both]", cmd_number, 2, 1),
    SHELL_CMD_ARG(amp, NULL, "0..100 percent [left|right|both]", cmd_number, 2, 1),
    SHELL_CMD_ARG(link, NULL, "Couple channels: on|off (left master)", cmd_link, 2, 0),
    SHELL_SUBCMD_SET_END
);

SHELL_CMD_REGISTER(gen, &generator_commands, "USB audio signal generator", NULL);
