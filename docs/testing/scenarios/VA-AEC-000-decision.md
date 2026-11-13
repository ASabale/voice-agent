# VA-AEC-000 — Canceller choice, not a room test

1. **ID:** VA-AEC-000
2. **Checked:** 2026-11-13 21:45 UTC.
3. **Level:** Decision, plus one local measurement of the current filter. Not LEVEL 5. Not acoustic echo cancellation.
4. **Choice.** WebRTC desktop echo cancellation through `aec-audio-processing==1.0.0` (`macosx_15_0_arm64`, CPython 3.12), AEC only, in front of VAD, using the existing WAV render cursor. `afplay` stays. Recorded in `docs/testing/AEC-DECISION.md`.
5. **Current filter.** White noise, `remove_render_from_block`, search 150 ms, correlation 0.75. One delay at 0, 20 ms, or 120 ms was removed to rounding. A second path at 40 ms beside a 20 ms path left ERLE 5.0 dB (RMS 2865.3 to 1616.8). A 200 ms delay was unchanged. The fit is 48 taps, 3 ms.
6. **Not done.** The wheel is not installed. The live controller was not restarted. The microphone was not opened.
