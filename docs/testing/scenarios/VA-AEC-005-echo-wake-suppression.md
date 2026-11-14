# VA-AEC-005 — Echo-only playback never wakes; real speech still does

Status: implemented, LEVEL 4 (fixture-fed production frame loop). No microphone
was opened and no sound was played.

## What it proves

`scripts/run_aec_fixture_probe.py` connects a render slot for a 4.5 s
"Hey Jarvis. Hey Jarvis. Hey Jarvis. Hey Jarvis." clip, then feeds the echo of
that clip — four taps at 15/30/60/90 ms — through the production
`handle_captured_frame` with the real openwakeword model, real VAD, and real
`handy --transcribe-file` on the cleaned frames.

1. Echo-only playback produces no wake and no dictation: the mic stays IDLE
   and no transcript is produced from echo.
2. The canceller reports its own residual: `aec_echo_db = -34.8 dB` over the
   57 echo blocks in the status window.
3. After the slot closes, the real wake fixture scores 0.98 and the near-end
   sentence transcribes verbatim: "The echo probe recorded clearly." The
   flush is held (dead bridge port), never typed anywhere.

## Design note that the first run exposed

The echo must be generated on the exact 16 kHz grid: block `k` is captured at
`started_at + (k+1) * 1280 / (16000 * 1.18)`. A wall-clock loop (`while time < deadline`)
drifts ~0.1 s per frame once VAD/wake models run, which skips render content
between blocks and AEC3 never converges — the first attempt measured only -2.7 dB
with that bug. Contiguous blocks converge to -34 dB inside one second.

## Reproduce

```bash
~/.local/share/omp-voice/venv/bin/python scripts/run_aec_fixture_probe.py
```

Exits 0 on PASS. Isolated state dir, dead bridge port (17999), a `sleep` pid
stands in for afplay so nothing plays.

## Limits

Still a synthetic room; the true speaker-to-mic path is untested until the
live controller (pid 64238, pre-AEC code) is restarted. Not VA-INT-001.
