# VA-INT-AUTO-025 — Wake blocked after Handy closes

1. **ID:** VA-INT-AUTO-025
2. **Checked:** 2026-11-13 20:34 UTC.
3. **Level:** `handle_idle_frame` while `score_wake_blocked_until` is set. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `enter_dictating` records the reason and does not run. These fail the test if called: `silence_speech`, `kill_tts_clips`, `handy_start_recording`, `handy_cancel`, `play_cue`, `dispatch_transcript`, `pause_tts_clips`, `resume_tts_clips`, `stop_playback`, `write_status`. `sync_speech_tier` does nothing, so VoiceBox is not queried. `fn_held` is false.
5. **Blocked:** The wake fixture is fed as 1280-sample frames with the block set far in the future. The simulated clock starts at 10 s. The state stays `IDLE`. The stub is not called.
6. **Open:** The same file with the block at 0 sets the state to `DICTATING`. One reason is recorded, `openWakeWord score=` at or above 0.5. VA-INT-AUTO-022 is what sets this block for 45 s when Handy closes. This test checks that the idle loop honors it.
7. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905. The fixture was not played.
8. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `enter_dictating` or play the fixture.
