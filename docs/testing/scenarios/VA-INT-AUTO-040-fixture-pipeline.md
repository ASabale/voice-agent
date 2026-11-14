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

The runner terminates only the `omp` pid it started, and only if that pid is not 16590 or 64238. Closing its pty is that ends that session. It does not signal pid 64238.

## Stop fixture cut root cause and fix — 2026-11-14 13:35 UTC

Reproduced with a stubbed `afplay` (no VoiceBox, microphone never opened): a twenty-second reference clip plays through the render seam while two copies of `stop-say.wav` are fed as microphone frames. Per-frame trace from the throwaway probe `stop_cut_probe5.py` (deleted with its scratch dirs after the iteration, alongside `/tmp/stop-cut-7.txt` … `/tmp/stop-cut-11.txt`; the numbers below are the preserved evidence):

- **Before the fix, with a render reference:** stop frames entered WebRTC at raw rms 4130 and left at rms 3 — the unconverged warm-up fit was squashing the interruption before the barge gate ever scored it. No `TTS barge hold` line, the clip kept playing. Without a reference the identical feed fired holds on intact audio, so the gate itself was never the problem.
- **The gate is unchanged:** `hot = vad_score >= 0.55 and rms >= gate` with `gate = max(320.0, floor * 2.4)`, three consecutive hot frames. The probe fires it on intact stop frames.

Fix in `bin/omp-voice-controller`:

1. `echo_over_cancels(mic, cleaned, reference)` — the guard fires only when the filter removed more than 75% of the block energy **and** the microphone block shares no sample-lagged window of the render reference. Measured separation on this machine: genuine echo paths (single delay 0–300 ms, four-tap room response) correlate with a lagged render window at 0.62–1.0; unrelated speech of the same voice peaks at 0.46. Threshold 0.55 sits between with margin. The correlation is a sample-resolution FFT cross-correlation over ±300 ms (`AEC_GUARD_LAG_SAMPLES = 4800`), matching the measured flight lags (VA-AEC-009). A frame the guard flags is returned raw and the filter still sees it in `_aec_observe` as mic-vs-mic.
2. `tts_pre_roll` (gate-burst pre-roll) seeds the barge clip: every frame above the gate appends to an 8-frame burst, any frame below clears it, and the hold takes `list(self.tts_pre_roll) or [frame]` so the clip holds the word onset, not just the tail.

A warm-up skip (pass the first 3 s of a clip unfiltered) was tried and reverted: it starved the filter, broke the ERLE tests, and the correlation guard alone covers the fixture case.

After the fix, probe5 reference arm: stop frames survive (4130→4130, 5318→5318; the few moderately attenuated frames stay above the gate), holds fire (`TTS barge hold rms=2605 hot=3 frames=4`), the whisper clip peaks 25244, and `Heard 'stop.' over TTS -> stopping speech` fires with latency 0.636 s. Unit coverage: `tests/test_echo_control.py` guard tests (bogus fit flagged, real delayed echo trusted) and `tests/test_barge_fixture.py::test_a_squashing_canceller_cannot_erase_the_stop`. Full suites: 247 pytest passed, 87 node passed.

Still not proved here: acoustic echo cancellation through a real microphone; the guard is Level 1/2 evidence.

## Zombie semantics note — 2026-11-14

`stop_playback` (controller line 2782) polls `pid_alive` (`os.kill(pid, 0)`) on the afplay pids until they disappear, up to 2 s. Verified behavior: an exited process that its parent has not reaped is a zombie and `os.kill(pid, 0)` succeeds — confirmed directly in a fresh venv (`Popen(['true'])` unreaped: kill succeeds; after `wait()`: `ProcessLookupError`). The afplay clips are children of the VoiceBox sidecar, not of the controller, so if VoiceBox exits or is slow to reap, `stop_playback` can burn the full 2 s window and return `None` even though the sound stopped. The probe runs reported a real latency (0.636 s), so this edge is not currently firing; it stays a hazard to confirm the moment VoiceBox is back.
