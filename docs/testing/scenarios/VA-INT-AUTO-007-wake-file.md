# VA-INT-AUTO-007 — Wake model on a file

1. **ID:** VA-INT-AUTO-007
2. **Checked:** 2026-11-13 20:13 UTC.
3. **Level:** The openWakeWord model, not the microphone. This is not LEVEL 4.
4. **How:** `say -o` wrote two AIFF files. `ffmpeg` made 16 kHz mono 16-bit WAVs. Nothing was played. `openwakeword.model.Model` scored 1280-sample frames, the same size `run_daemon` uses.
5. **Scores:** `hey jarvis` peaked at 0.9647. `good morning` peaked at 0.0. One second of silence peaked at 0.0001. The controller threshold is 0.5.
6. **Live loop:** `controller.log` mtime stayed 1794598062. Last line is still the 14:27:42 IDLE return. Pid 64238 was not restarted. The clips were not sent to the speakers.
7. **Fixtures:** `tests/fixtures/hey-jarvis-say.wav` and `tests/fixtures/good-morning-say.wav`.
8. **Still blocked:** Playing either file would be a real wake on the MacBook mic. LEVEL 4 still needs a second input.
