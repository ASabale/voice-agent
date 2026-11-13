# VA-INT-AUTO-028 — Fn during playback

1. **ID:** VA-INT-AUTO-028
2. **Checked:** 2026-11-13 20:37 UTC.
3. **Level:** The fn edge inside `handle_idle_frame` while VoiceBox is marked active. Not the microphone. Not LEVEL 4.
4. **Stubbed:** The cut thread runs inline. `silence_speech`, `kill_tts_clips`, `handy_cancel`, and `handy_start_recording` are recorded. `time.sleep` only moves a fake clock. `is_voicebox_speaking` is false, so the 1.5 s wait does not spin. These fail the test if called: `dispatch_transcript`, `play_cue`, `write_status`, `stop_playback`, `pause_tts_clips`. `enter_dictating` fails the test. The frame is silence, and the wake model stub returns 0.
5. **No playback:** Fn down while VoiceBox is not active records nothing. `fn_was_down` becomes true. The state stays `IDLE`.
6. **Already down:** A second frame while fn is still down does not cut again. `tts_active` stays true.
7. **Released:** The first edge calls `kill_tts_clips`, `silence_speech(True)`, and `handy_cancel(allow_launch=False)`. Fn is up by the time the cut finishes, so Handy is not started. `tts_active` is false. `fn_cut_busy` is false. History id 11 is ignored. The state stays `IDLE`.
8. **Still held:** The same cut also calls `handy_start_recording(allow_launch=False)`. It does not launch Handy. The state stays `IDLE`.
9. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905.
10. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `silence_speech` or the real Handy controls.
