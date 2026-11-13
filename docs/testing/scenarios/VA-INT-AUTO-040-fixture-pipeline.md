# VA-INT-AUTO-040 — Fixture audio through the controller

1. **ID:** VA-INT-AUTO-040
2. **Checked:** 2026-11-13 21:17 UTC.
3. **Level:** Fixture-fed controller integration. Not the physical microphone. Not acoustic echo cancellation. Not VA-INT-001.
4. **Source:** `FixtureAudioSource` yields 16 kHz mono frames of 1280 samples (80 ms), in order, with the silence that follows each clip. `SoundDeviceAudioSource` is the production path and is the only class that opens `sounddevice.InputStream`. Both call `handle_captured_frame`. The run log said `Audio source fixture (149 frames, microphone not opened)`.
5. **Isolation:** State dir `.local/voice-agent/fixture-040/state`. `OMP_VOICE_BRIDGE_ONLY` was the test bridge. `OMP_VOICE_PLAYBACK_PID` limited clip kills to that pid. `OMP_VOICE_HANDY=transcribe-file` so the run did not toggle, cancel, or relaunch the shared Handy app. Handy history max id stayed 771. The log line `chunk #771` is that existing id, not a new row.
6. **Turn 1:** OMP pid 47508, bridge 49919. Wake handler ran: `openWakeWord score=0.95`, state `DICTATING`. Handy `--transcribe-file` returned `Respond with exactly voice integration test successful. Send prompt.` Delivery was bridge 49919, action `sent`, draft `respond with exactly voice integration test successful`. Playback started. `afplay` pid 47643.
7. **Stop:** The stop fixture was fed while that slot was still open. No `TTS barge` line and no call that cut the clip. The slot later wrote `ended_at` 1794604643.5, `reason` `end`, 3.1 s after the stop feed began. `reason: end` is also what a finished clip writes. This run does not show that the stop fixture stopped playback. An earlier pass with one copy and a gap logged `TTS barge hold` then `TTS barge release` and also left the clip running.
8. **Turn 2:** Same process, no controller restart. Wake `openWakeWord score=0.94`. Handy returned `Reply with exactly second voice check complete. Send prompt.` Action `sent`. Second playback started.
9. **Left alone:** Controller pid 64238 and OMP pid 16590. `status.json` stayed `IDLE` at `updated_at` 1794598062.972905. `controller.log` mtime did not change. No second VoiceBox server.
10. **Not proved:** Acoustic echo cancellation. The frames never came from a microphone that was hearing the speakers.
11. **Runner:** `~/.local/share/omp-voice/venv/bin/python scripts/run_fixture_pipeline.py`
12. **Frame check:** `pytest tests/test_audio_source.py -q`

## Fixture format

16 kHz, mono, 16-bit PCM. Each segment is `(samples, seconds of silence after it)`. The source pads to a whole frame and sleeps 80 ms per frame when pace is on. Wake and stop clips are `tests/fixtures/hey-jarvis-say.wav` and `tests/fixtures/stop-say.wav`. The two dictation lines were made with `say -o <file> --data-format=LEI16@16000` and were not played.

## Cleanup

The runner terminates only the `omp` pid it started, and only if that pid is not 16590 or 64238. Closing its pty is what ends that session. It does not signal pid 64238.
