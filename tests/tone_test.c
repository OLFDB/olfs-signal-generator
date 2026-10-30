/* SPDX-License-Identifier: Apache-2.0 */
#include "tone.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define PACKET_FRAMES (sample_rate / 1000U)
#define PACKET_SAMPLES (PACKET_FRAMES * TONE_CHANNELS)
#define PACKET_BYTES (PACKET_SAMPLES * TONE_SAMPLE_BYTES)

static int32_t whole[TONE_MAX_SAMPLE_RATE];
static int32_t chunks[TONE_MAX_SAMPLE_RATE];

static void test_rate(uint32_t sample_rate)
{
    const double pi = acos(-1.0);
    struct tone_settings cfg = {
        .frequency = 1000, .amplitude = 100, .running = true,
    };

    for (int wave = TONE_SINE; wave <= TONE_SQUARE; ++wave) {
        cfg.wave = (enum tone_wave)wave;
        struct tone_state a = {0}, b = {0};

        tone_render(&a, &cfg, sample_rate, whole, sample_rate);
        for (size_t i = 0; i < sample_rate; i += PACKET_FRAMES) {
            tone_render(&b, &cfg, sample_rate, chunks + i, PACKET_FRAMES);
        }
        assert(memcmp(whole, chunks, sample_rate * sizeof(whole[0])) == 0);
        int crossings = 0;
        double sum = 0;
        for (size_t i = 0; i < sample_rate; ++i) {
            assert(whole[i] >= -8388607 && whole[i] <= 8388607);
            sum += whole[i];
            if (i && whole[i - 1] < 0 && whole[i] >= 0) {
                ++crossings;
            }
            if (wave == TONE_SINE) {
                uint32_t step = (uint32_t)(((uint64_t)cfg.frequency << 32) / sample_rate);
                uint32_t phase = (uint32_t)((uint64_t)step * i);
                double reference = 8388607 * sin(2 * pi * phase / 4294967296.0);
                assert(fabs(whole[i] - reference) < 48);
            }
            if (wave == TONE_SQUARE) {
                assert(whole[i] == 8388607 || whole[i] == -8388607);
            }
        }
        assert(crossings >= 999 && crossings <= 1000);
        assert(fabs(sum / sample_rate) < 768);

        cfg.amplitude = 25;
        a.phase = 0;
        tone_render(&a, &cfg, sample_rate, chunks, sample_rate);
        for (size_t i = 0; i < sample_rate; ++i) {
            assert(chunks[i] == whole[i] * 25 / 100);
        }
        cfg.amplitude = 100;
    }

    /* Stop and zero amplitude both produce PCM silence. */
    for (int mode = 0; mode < 2; ++mode) {
        struct tone_state state = {0};
        cfg.running = mode != 0;
        cfg.amplitude = mode ? 0 : 100;
        tone_render(&state, &cfg, sample_rate, whole, sample_rate);
        for (size_t i = 0; i < sample_rate; ++i) {
            assert(whole[i] == 0);
        }
    }

    /* DDS retains its phase across frequency changes, including limits. */
    struct tone_state state = { .phase = 123456789 };
    cfg.running = true;
    cfg.amplitude = 100;
    for (uint32_t freq = 1; freq <= 20000; freq += 19999) {
        cfg.frequency = freq;
        uint32_t before = state.phase;
        uint32_t step = (uint32_t)(((uint64_t)freq << 32) / sample_rate);
        tone_render(&state, &cfg, sample_rate, whole, PACKET_FRAMES);
        assert(state.phase == before + step * PACKET_FRAMES);
    }
    /* Wire format: extrema, sign extension, and low-order precision. */
    const int32_t pcm[] = {0, 1, -1, 8388607, -8388608, 0x123456, -256};
    const uint8_t expected[] = {
        0,0,0, 1,0,0, 255,255,255, 255,255,127,
        0,0,128, 0x56,0x34,0x12, 0,255,255
    };
    uint8_t packed[sizeof(expected)];
    tone_pack_pcm24(packed, pcm, sizeof(pcm) / sizeof(pcm[0]));
    assert(memcmp(packed, expected, sizeof(expected)) == 0);
    const uint8_t expected16[] = {
        0,0, 0,0, 255,255, 255,127, 0,128, 0x34,0x12, 255,255
    };
    uint8_t packed16[sizeof(expected16)];
    tone_pack_pcm16(packed16, pcm, sizeof(pcm) / sizeof(pcm[0]));
    assert(memcmp(packed16, expected16, sizeof(expected16)) == 0);
    /* Independent stereo: channel isolation and exact L/R sample order. */
    struct tone_stereo_settings stereo = {
        .channel = {
            { .wave = TONE_SINE, .frequency = 997, .amplitude = 25, .running = true },
            { .wave = TONE_TRIANGLE, .frequency = 2003, .amplitude = 60, .running = true },
        },
        .linked = false,
    };
    struct tone_state states[2] = {{1234}, {987654321}};
    struct tone_state refs[2] = {states[0], states[1]};
    int32_t interleaved[PACKET_SAMPLES], left[PACKET_FRAMES], right[PACKET_FRAMES];
    uint8_t stereo_pcm[PACKET_BYTES], mono_pcm[TONE_SAMPLE_BYTES];
    uint8_t stereo_pcm16[PACKET_SAMPLES * 2], mono_pcm16[2];
    assert(PACKET_BYTES == (sample_rate == 48000U ? 288U : 576U));
    for (size_t packet = 0; packet < 100; ++packet) {
        tone_render_stereo(states, &stereo, sample_rate, interleaved, PACKET_FRAMES);
        tone_render(&refs[0], &stereo.channel[0], sample_rate, left, PACKET_FRAMES);
        tone_render(&refs[1], &stereo.channel[1], sample_rate, right, PACKET_FRAMES);
        tone_pack_pcm24(stereo_pcm, interleaved, PACKET_SAMPLES);
        tone_pack_pcm16(stereo_pcm16, interleaved, PACKET_SAMPLES);
        for (size_t i = 0; i < PACKET_FRAMES; ++i) {
            assert(interleaved[2*i] == left[i]);
            assert(interleaved[2*i+1] == right[i]);
            tone_pack_pcm24(mono_pcm, &left[i], 1);
            assert(memcmp(stereo_pcm + 6*i, mono_pcm, 3) == 0);
            tone_pack_pcm24(mono_pcm, &right[i], 1);
            assert(memcmp(stereo_pcm + 6*i + 3, mono_pcm, 3) == 0);
            tone_pack_pcm16(mono_pcm16, &left[i], 1);
            assert(memcmp(stereo_pcm16 + 4*i, mono_pcm16, 2) == 0);
            tone_pack_pcm16(mono_pcm16, &right[i], 1);
            assert(memcmp(stereo_pcm16 + 4*i + 2, mono_pcm16, 2) == 0);
        }
    }
    /* Linking synchronizes both phase and samples despite different settings. */
    stereo.linked = true;
    tone_render_stereo(states, &stereo, sample_rate, interleaved, PACKET_FRAMES);
    assert(states[0].phase == states[1].phase);
    for (size_t i = 0; i < PACKET_FRAMES; ++i) {
        assert(interleaved[2*i] == interleaved[2*i+1]);
    }
    /* Unlinking preserves both phases; stop right without muting left. */
    stereo.channel[1] = stereo.channel[0];
    stereo.channel[1].running = false;
    stereo.linked = false;
    tone_render_stereo(states, &stereo, sample_rate, interleaved, PACKET_FRAMES);
    assert(states[0].phase == states[1].phase);
    bool left_nonzero = false;
    for (size_t i = 0; i < PACKET_FRAMES; ++i) {
        left_nonzero |= interleaved[2*i] != 0;
        assert(interleaved[2*i+1] == 0);
    }
    assert(left_nonzero);
    puts("tone: waveform accuracy, frequency, amplitude, silence, packet continuity, stereo isolation, coupling and PCM order passed");
    printf("Sample rate: %u Hz passed\n", sample_rate);
}

int main(void)
{
    test_rate(48000U);
    test_rate(96000U);
    /* Switching sample rate changes packet size and DDS step, not phase. */
    struct tone_state state = { .phase = 123456789U };
    struct tone_settings cfg = {
        .wave = TONE_SINE, .frequency = 1000, .amplitude = 100, .running = true,
    };
    const uint32_t rates[] = {48000U, 44100U, 96000U, 44100U, 48000U};
    for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
        uint32_t before = state.phase;
        uint32_t frames = rates[i] / 1000U;
        uint32_t step = (uint32_t)(((uint64_t)cfg.frequency << 32) / rates[i]);
        struct tone_state reference = state;
        int32_t first;
        tone_render(&reference, &cfg, rates[i], &first, 1);
        tone_render(&state, &cfg, rates[i], whole, frames);
        assert(whole[0] == first);
        assert(state.phase == before + step * frames);
    }
    /* At 44.1 kHz, 900 packets carry 44 frames and 100 carry 45. */
    struct tone_pacing pacing = {0};
    struct tone_state continuous = {0}, packetized = {0};
    tone_render(&continuous, &cfg, 44100U, whole, 44100);
    size_t offset = 0, long_packets = 0;
    for (size_t packet = 0; packet < 1000; ++packet) {
        size_t frames = tone_next_frames(&pacing, 44100U);
        assert(frames == 44 || frames == 45);
        long_packets += frames == 45;
        assert(offset + frames <= 44100U);
        tone_render(&packetized, &cfg, 44100U, chunks + offset, frames);
        offset += frames;
    }
    assert(offset == 44100U && long_packets == 100 && pacing.remainder == 0);
    assert(memcmp(whole, chunks, 44100 * sizeof(whole[0])) == 0);
    assert(continuous.phase == packetized.phase);
    int crossings = 0;
    for (size_t i = 1; i < 44100U; ++i) {
        if (chunks[i-1] < 0 && chunks[i] >= 0) ++crossings;
    }
    assert(crossings >= 999 && crossings <= 1000);
    tone_next_frames(&pacing, 44100U); /* fractional remainder = 100 */
    assert(tone_next_frames(&pacing, 48000U) == 48 && pacing.remainder == 0);
    assert(tone_next_frames(&pacing, 96000U) == 96 && pacing.remainder == 0);
    assert(tone_next_frames(&pacing, 44100U) == 44 && pacing.remainder == 100);
    puts("44.1-kHz packet pacing, tone frequency, sample continuity and rate changes passed");
    return 0;
}
