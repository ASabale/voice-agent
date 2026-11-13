# VA-INT-AUTO-010 — Idle frame on the wake file

1. **ID:** VA-INT-AUTO-010
2. **Checked:** 2026-11-13 20:17 UTC.
3. **Level:** `MicState.handle_idle_frame`, not the microphone. This is not LEVEL 4.
4. **How:** The wake fixture and the good-morning fixture were fed as 1280-sample frames. `enter_dictating` was replaced on that instance. These were patched to fail the test if called: `silence_speech`, `kill_tts_clips`, `handy_start_recording`, `handy_cancel`, `play_cue`, `dispatch_transcript`, `pause_tts_clips`, `resume_tts_clips`, `apply_handy_model`, `apply_voicebox_model`, `stop_playback`. `fn_held` returned false. `sync_speech_tier` did nothing, so VoiceBox health was not called.
5. **Result:** The wake file set the state to `DICTATING` and the stub recorded one reason, `openWakeWord score=` at or above 0.5. The other file left the state `IDLE`. No forbidden function ran.
6. **Live loop:** `controller.log` mtime stayed 1794598062. `status.json` stayed `IDLE` at `updated_at` 1794598062.972905. The real `enter_dictating` was not used, so Handy did not start and no clip was stopped.
7. **Still blocked:** Playing the file would run the real `enter_dictating`. LEVEL 4 still needs a second input.
