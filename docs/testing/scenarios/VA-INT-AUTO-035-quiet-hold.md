# VA-INT-AUTO-035 — Quiet barge hold while playback continues

1. **ID:** VA-INT-AUTO-035
2. **Checked:** 2026-11-13 20:44 UTC.
3. **Level:** The quiet release inside the `tts_active` branch. Playback is still marked active. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `resume_tts_clips` is counted. The real function sends `SIGCONT`. `sync_speech_tier` does nothing. `fn_held` and `is_voicebox_speaking` are false. `enter_dictating` fails the test. These also fail the test: `silence_speech`, `kill_tts_clips`, `pause_tts_clips`, `handy_start_recording`, `handy_cancel`, `dispatch_transcript`, `play_cue`, `write_status`, `stop_playback`.
5. **Skip is not quiet:** A hold with two skip frames left consumes two quiet frames as skip. The hold stays. Quiet stays 0. Resume is not called. The buffered frame stays.
6. **Two quiet frames:** With skip already 0, the first quiet frame leaves the hold up. The second clears the buffer, calls resume once, and does not queue Whisper. `tts_active` stays true. The state stays `IDLE`. The floor holdoff ends at 5 because this same frame sets it to 6 and then decrements it. The resume attack is ignored for 1.5 s. VA-INT-AUTO-034 leaves the holdoff at 6 because playback is already over and that decrement does not run.
7. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905.
8. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `resume_tts_clips`.
