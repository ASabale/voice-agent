# VA-INT-AUTO-034 — Playback ends during a barge hold

1. **ID:** VA-INT-AUTO-034
2. **Checked:** 2026-11-13 20:43 UTC.
3. **Level:** `handle_idle_frame` when `tts_active` is false and a barge hold is still open. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `resume_tts_clips` is counted. The real function sends `SIGCONT`. The wake stub returns 0. `sync_speech_tier` does nothing. `fn_held` and `is_voicebox_speaking` are false. `enter_dictating` fails the test. These also fail the test: `silence_speech`, `kill_tts_clips`, `pause_tts_clips`, `handy_start_recording`, `handy_cancel`, `dispatch_transcript`, `play_cue`, `write_status`, `stop_playback`.
5. **Hold open:** `tts_barge_held` is true and one loud frame is buffered. Resume runs once. The hold, the voice flag, and the buffered frames are cleared. Nothing is queued. The state stays `IDLE`. The floor holdoff is 6 frames. The resume attack is ignored for 1.5 s.
6. **No hold:** Buffered frames with the hold already false are discarded. Resume is not called again. The cooldown stays 0.
7. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905.
8. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `resume_tts_clips`.
