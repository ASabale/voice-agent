# VA-AEC-011 — A failed reference read recovers on the same clip key

Status: implemented, LEVEL 1 (unit, synthetic). No microphone, no sound.

## The bug

`refresh_render_reference` pinned `_render_file_key` to the announced
`(wav, frames, rate, channels)` key **before** checking whether the read
succeeded. One transient read failure (file momentarily unreadable, e.g.
during a writer race or a tmp cleanup) set the key, cleared the parsed
reference, and every later frame with the same key fell into the
`elif _render_parsed is None` branch: `render_connected: false` forever for
that clip, even after the file became fully readable again. AEC stayed dead
for the whole utterance — the exact silent-loss pattern the loop targets —
until some *new* clip key arrived.

Reproduced before fixing: delete the WAV while a slot announces it →
`render_connected: false`; rewrite the identical file → still `false` at
t=100.1, 100.2, 100.5. Reference never reconnected.

## The fix

`bin/omp-voice-controller`: `_render_file_key = key` is now assigned only
after `connect_render_reference` succeeds. A failed read leaves the key
unpinned, so the next frame retries the same key. The retry is bounded by
the frame cadence (~12.5/s) and an `OSError` on a missing file is trivial.
No thresholds, gates, or fallback behavior changed.

## Test

`tests/test_echo_control.py::test_a_failed_reference_read_recovers_when_the_file_returns`

1. Slot announces a 4 s mono clip whose file does not exist:
   `refresh_render_reference` reports `render_connected: false`; a mic block
   carrying echo passes through byte-identical (no ghost subtraction, no
   crash).
2. The same file is written (same key). The next refresh reconnects
   (`render_connected: true`, aligned), and cancellation resumes on the same
   clip: synthetic echo (320-sample delay, 0.6 gain) is cancelled to
   ERLE >= 12 dB.

```bash
~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_echo_control.py -q   # 27 passed
```

Full suite on the current tree: 255 passed. `py_compile` clean on
`bin/omp-voice-controller` and `bin/playback_state.py`. Verified with the
real production `cancel_playback_echo` path, not a stub.

## Limits

The physical trigger (VoiceBox writing the WAV while afplay starts) is not
exercised; this pins the state-machine contract only. The running controller
(pid 64238) keeps the old behavior until it is restarted.
