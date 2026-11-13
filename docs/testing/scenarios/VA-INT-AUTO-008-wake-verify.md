# VA-INT-AUTO-008 — Whisper verifier on the same files

1. **ID:** VA-INT-AUTO-008
2. **Checked:** 2026-11-13 20:15 UTC.
3. **Level:** The idle verifier, not the microphone. This is not LEVEL 4.
4. **Path 1:** `handle_idle_frame` multiplies a frame by 3 when its RMS is under 1200, then reads `hey_jarvis`. On `tests/fixtures/hey-jarvis-say.wav` that peak was 0.9225, with 3 boosted frames. `good-morning-say.wav` stayed 0.0. Both are against the 0.5 threshold. A score at or above 0.5 calls `enter_dictating` immediately. That function was not called.
5. **Path 2:** `faster-whisper` `tiny.en`, `beam_size=1`, `clip_for_whisper` cap 6, and the idle prompt. The wake file transcribed as `Hey Jarvis.`, which `is_wake_phrase` accepts. The other file transcribed as `Good morning.`, which it rejects.
6. **Not called:** `enter_dictating`, `silence_speech`, `play_cue`, `handy_start_recording`. Those start a recording and stop every VoiceBox clip.
7. **Live loop:** `controller.log` mtime stayed 1794598062. `status.json` stayed `IDLE` at `updated_at` 1794598062.972905.
8. **Still blocked:** Playing the file would take the live path into `enter_dictating`. LEVEL 4 still needs a second input.
