# VA-INT-AUTO-015 — Fast command during dictation

1. **ID:** VA-INT-AUTO-015
2. **Checked:** 2026-11-13 20:24 UTC.
3. **Level:** The 1.5 s fast-command gate inside `handle_dictating_frame`. The normal pause in this test is 5 s. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `handy_stop_recording`, `wait_for_new_history_row`, `handy_start_recording`, `dispatch_transcript`, `play_cue`, `write_status`, and `latest_history_row`. `time.sleep` was a no-op. These fail the test if called: `silence_speech`, `stop_playback`, `handy_cancel`, `pause_tts_clips`, `kill_tts_clips`, `bridge_request`.
5. **Flag:** Kind `fast_cmd` with the text `stop` sets `pending_fast_flush` and stays `DICTATING`. Nothing is posted. `good morning` leaves the flag false.
6. **Early flush:** After 1.6 s of silence the flag flushes before the 5 s pause. Handy returns `stop`. That posts `stop`, plays the pause cue, and the state becomes `IDLE`. Handy is not started again. `handy_stop_recording` ran once, as the stub.
7. **No flag:** The same 1.6 s silence with seven tail frames does not stop Handy. The silence frame makes eight, which queues one `fast_cmd` job. The prompt contains `send prompt`. The state stays `DICTATING`. Nothing new is posted.
8. **Live files:** `status.json` mtime stayed 1794598062 and the state stayed `IDLE` at `updated_at` 1794598062.972905.
9. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real Handy toggle or the real `write_status`.
