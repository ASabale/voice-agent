# VA-AEC-002 — Stereo render references are downmixed before cancellation

Status: PASS (synthetic, LEVEL 1). 2026-11-13.

## Problem

`refresh_render_reference` resampled mono clips to 16 kHz and marked them aligned. A stereo clip kept the interleaved samples, `aligned` stayed `False`, and `cancel_playback_echo` returned the microphone block unchanged. Any VoiceBox or afplay clip with two channels had no echo reference at all.

## Change

`downmix_to_mono` averages interleaved channels onto one, then `resample_to_mic_rate` maps it onto the 16 kHz grid. afplay plays stereo through both speakers and the microphone hears their sum, so the averaged pair is the reference. The reference is downmixed once at connect time, not per block; the 16 kHz render cursor and `render_block_at` stay unchanged.

## Verification

`~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_echo_control.py -q` — 15 passed:

- `test_downmix_averages_interleaved_channels` — averaging and the mono passthrough.
- `test_a_stereo_clip_downmixes_to_an_aligned_reference` — a 24 kHz stereo WAV built from `sentence-stop-say.wav` connects, reports `render_aligned` true, and the stored samples equal the averaged, resampled reference.
- `test_stereo_playback_echo_is_cancelled_on_the_production_path` — a microphone block containing the averaged clip 320 samples late at gain 0.6 goes through `refresh_render_reference` and `cancel_playback_echo` with the real WebRTC canceller and loses at least 12 dB of tail energy.

No microphone opened. No processes restarted. Pid 64238 still runs the previous controller until it is restarted.

## Not claimed

Not a speaker-to-microphone measurement. Not VA-INT-001. Stereo room response is not modeled by a channel average.
