# VA-INT-AUTO-036 — Handy file transcription

1. **ID:** VA-INT-AUTO-036
2. **Checked:** 2026-11-13 20:51 UTC.
3. **Level:** LEVEL 3. Handy `--transcribe-file` runs the app's batch path and exits. It does not open the microphone, so this is not LEVEL 4.
4. **Command:** `/Applications/Handy.app/Contents/MacOS/handy --transcribe-file <wav> --json`. No `--toggle-transcription` and no `--cancel`. The files were not played.
5. **Model:** The selected model loaded as `handy-computer/Qwen3-ASR-0.6B-gguf/Qwen3-ASR-0.6B-Q8_0.gguf` on `MTL0`. Requested device was the saved setting. The 1.7B model is installed and was not loaded.
6. **Fixtures:** Both files are 16 kHz mono. `tests/fixtures/good-morning-say.wav` is 0.90 s and came back as `Good morning.` in 109 ms. `tests/fixtures/stop-say.wav` is 0.63 s and came back as `Stop.` in 126 ms.
7. **Records:** `.local/voice-agent/runs/VA-INT-AUTO-036-good-morning.json` and `.local/voice-agent/runs/VA-INT-AUTO-036-stop.json`.
8. **Not this test:** The controller did not see the audio. Handy did not start a recording. Nothing was posted to a bridge. `status.json` stayed `IDLE` at `updated_at` 1794598062.972905. `controller.log` mtime stayed 1794598062.9733093.
9. **Still blocked:** LEVEL 4 still needs a second input. A file transcript is not a wake, and it is not a Handy history row.
