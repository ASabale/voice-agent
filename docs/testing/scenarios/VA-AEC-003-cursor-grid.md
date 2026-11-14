# VA-AEC-003 — the published cursor rides the AEC grid

**Level:** LEVEL 1. No microphone. **Date:** 2026-11-14 00:04 UTC. **Result:** PASS for the cursor units. NOT_RUN for speakers.

## Problem

`refresh_render_reference` published `render_cursor` counted in the **file's** sample rate and clamped to the file's frame count. Both cancellation paths — `render_block_at` (WebRTC) and `subtract_playback_at` (short fit) — read the reference after `downmix_to_mono` + `resample_to_mic_rate`, so they index the 16 kHz grid. For a 24 kHz clip the status cursor was 1.5x the position actually fed to the canceller, which corrupts any latency or residual-echo reading taken from `status.json`.

## Change

- `MIC_RENDER_RATE = 16000` is now the single constant used by `resample_to_mic_rate`, `render_block_at`, `subtract_playback_at`, and the WebRTC stream format.
- The cursor is computed on the 16 kHz grid at load time and every refresh, clamped to `processed_frames` (the grid length), not the file frames.
- `status.json` gains `render_processed_frames`. `render_rate` and `render_frames` stay file provenance.

## Tests (`tests/test_echo_control.py`)

1. `test_the_published_cursor_counts_on_the_aec_grid` — 24 kHz stereo, `afplay -r 1.18`: after 0.5 wall s the cursor is 9440 grid samples (not 12000 file samples); past the end it clamps to 64000, not 96000; the published cursor equals the end position `render_block_at` reads.
2. `test_the_grid_cursor_freezes_while_afplay_is_stopped` — SIGSTOP at 1.0 s holds the cursor at 18880 through 0.5 s stopped; resume advances to 28320.

## Verification

`pytest tests/test_echo_control.py tests/test_playback_state.py -q` → 35 passed. Full suite → 210 passed. The 16 kHz expectations in `test_playback_state.py` (8000/12000) are unchanged because file rate equals grid rate there.

## Limits

Unit level only. Pid 64238 was not restarted and still runs the old cursor code. Not a room measurement, not VA-INT-001.
