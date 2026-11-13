# VA-INT-AUTO-012 — apply_whisper decisions

1. **ID:** VA-INT-AUTO-012
2. **Checked:** 2026-11-13 20:21 UTC.
3. **Level:** `MicState.apply_whisper`. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `stop_playback` records its reason and does not run. The real function calls `silence_speech`. These fail the test if called: `silence_speech`, `kill_tts_clips`, `pause_tts_clips`, `resume_tts_clips`, `handy_start_recording`, `handy_cancel`, `play_cue`, `dispatch_transcript`. `enter_dictating` on the TTS cases fails the test. The idle-verify case replaces it and does not start Handy.
5. **Barge:** `stop.` and `Hold on a second.` each call `stop_playback` with `Heard '<text>' over TTS -> stopping speech, not opening Handy`. State stays `IDLE`. `tts_active` and `tts_barge_held` become false.
6. **Not a barge:** `The sentence ends with stop.` does not call `stop_playback`. `tts_active` stays true.
7. **Wake over TTS:** `Hey Jarvis.` with kind `tts_barge` returns true, stays `IDLE`, and does not enter dictation. The same words with kind `idle_verify` call the stub with `whisper heard 'Hey Jarvis.'` and set the state to `DICTATING`.
8. **Live loop:** `controller.log` mtime stayed 1794598062. `status.json` stayed `IDLE` at `updated_at` 1794598062.972905.
9. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `stop_playback` or `enter_dictating`.
