# VA-INT-AUTO-022 — Handy closed, or fn released

1. **ID:** VA-INT-AUTO-022
2. **Checked:** 2026-11-13 20:31 UTC.
3. **Level:** `handle_dictating_frame` when Handy disappears or fn is released. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `handy_process_running`, `handy_window_open`, `handy_stop_recording`, `handy_cancel`, `wait_for_new_history_row`, `dispatch_transcript`, `play_cue`, and `write_status`. These fail the test if called: `handy_start_recording`, `silence_speech`, `stop_playback`, `bridge_request`, `pause_tts_clips`, `kill_tts_clips`.
5. **Still starting:** The process is up and the window has not been seen. Two seconds into the chunk the state stays `DICTATING`. That is the hidden start, not a close.
6. **Process gone:** The state becomes `IDLE`. The pause cue is recorded. New wakes are blocked for 45 seconds. Nothing is posted. Handy is not stopped, cancelled, or started.
7. **Window closed:** A frame that sees the window, then a later frame that does not, also goes `IDLE` with the pause cue.
8. **Fn release:** A history row `ship all done` is posted as those words. Dispatch reports `sent`, but the transition still uses the pause cue, not the send cue. The state is `IDLE`. Handy is not stopped or cancelled, because the row was already there.
9. **Live files:** `status.json` mtime stayed 1794598062 and the state stayed `IDLE` at `updated_at` 1794598062.972905.
10. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real Handy controls or the real `write_status`.
