/* SPDX-License-Identifier: Apache-2.0 */
#ifndef OLF_TONE_H
#define OLF_TONE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define TONE_DEFAULT_SAMPLE_RATE 96000U
#define TONE_MAX_SAMPLE_RATE 96000U
#define TONE_SAMPLE_BYTES 3U
#define TONE_CHANNELS 2U
#define TONE_FULL_SCALE 8388607

enum tone_wave { TONE_SINE, TONE_TRIANGLE, TONE_SQUARE };

struct tone_settings {
    enum tone_wave wave;
    uint32_t frequency;
    uint32_t amplitude; /* Peak amplitude in percent of signed full scale. */
    bool running;
};

struct tone_state { uint32_t phase; };

/* Fractional samples/ms accumulator; reset automatically on rate changes. */
struct tone_pacing { uint32_t rate; uint32_t remainder; };
size_t tone_next_frames(struct tone_pacing *pacing, uint32_t sample_rate);

struct tone_stereo_settings {
    struct tone_settings channel[TONE_CHANNELS]; /* left, right */
    bool linked;
};

/* Interleaved L/R frames; linked mode uses left settings and phase for both. */
void tone_render_stereo(struct tone_state state[TONE_CHANNELS],
                        const struct tone_stereo_settings *settings, uint32_t sample_rate,
                        int32_t *samples, size_t frames);

/* Samples are signed 24-bit values stored in int32_t.
 * Phase is preserved across packet boundaries and settings changes. */
void tone_render(struct tone_state *state, const struct tone_settings *settings, uint32_t sample_rate,
                 int32_t *samples, size_t count);

/* Packed signed 24-bit little-endian USB PCM (three bytes per sample). */
void tone_pack_pcm24(uint8_t *destination, const int32_t *samples, size_t count);
/* Quantize signed 24-bit generator samples to packed signed 16-bit PCM. */
void tone_pack_pcm16(uint8_t *destination, const int32_t *samples, size_t count);

int tone_usb_init(void);

#endif
