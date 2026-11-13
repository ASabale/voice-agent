# VA-INT-AUTO-009 — Barge decision on a file

1. **ID:** VA-INT-AUTO-009
2. **Checked:** 2026-11-13 20:16 UTC.
3. **Level:** The TTS barge classifier, not the microphone. This is not LEVEL 4.
4. **How:** `say -o` wrote three clips. `ffmpeg` made 16 kHz mono WAVs. Nothing was played. Whisper used the barge prompt `Hey Jarvis. stop.` and `clip_for_whisper` cap 6.
5. **Heard:** `stop-say.wav` → `stop.` → tokens `["stop"]` → barge. `hold-on-say.wav` → `Hold on a second.` → barge. `sentence-stop-say.wav` was spoken as "this sentence ends with stop" and heard as `The sentence ends with stop.` → not a barge. A sentence that ends in stop is not a stop command.
6. **Not called:** `stop_playback`. That function calls `silence_speech(True)` and stops every VoiceBox clip, including pid 16590.
7. **Live loop:** `controller.log` mtime stayed 1794598062. `status.json` stayed `IDLE` at `updated_at` 1794598062.972905.
8. **Fixtures:** `tests/fixtures/stop-say.wav`, `hold-on-say.wav`, `sentence-stop-say.wav`.
9. **Still blocked:** Playing any of these would be a real utterance on the MacBook mic. LEVEL 4 still needs a second input.
