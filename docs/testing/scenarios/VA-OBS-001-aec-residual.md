# VA-OBS-001 — Rolling AEC residual echo in status

Status: implemented, LEVEL 1. No microphone was opened.

## What it measures

`cancel_playback_echo` now accumulates the raw and cleaned energy of every block the
WebRTC canceller processes (blocks whose render reference is silent are skipped).
`aec_window_fields()` turns the accumulation into `aec_echo_db` — the residual echo as
20·log10(cleaned/mic), negative when the echo got smaller — plus `aec_blocks`, then
resets the window. `publish_capture_totals` merges both into `status.json` on its
1-second cadence, so the residual follows the same rolling pattern as
`mic_dropped` and `render_cursor`.

One implementation note that a test caught: squaring int16 samples in 16 bits wraps
(`np.dot` on int16 arrays overflows), so the energies are widened to int64 before
summing.

## Measured values

| Scenario | Window | Result |
|---|---|---|
| Four-path room response, 8 s | 101 blocks, whole window including adaptation | -33.1 dB |
| Silent reference, noise mic | 0 blocks | no fields published |
| Second read with no new blocks | — | empty window |

## Reproduce

```bash
~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_echo_control.py -s \
  -k "residual"
```

## Limits

The window spans whole seconds including the first blocks while the filter adapts; it
is not the tail-only ERLE the synthetic scenario doc quotes. The fallback short fit is
not metered — `aec_echo_db` appears only when the WebRTC path processes blocks. The
live controller (pid 64238) still runs the old path until it is restarted.
