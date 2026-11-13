# VA-INT-AUTO-024 — Headphone speech gate

1. **ID:** VA-INT-AUTO-024
2. **Checked:** 2026-11-13 20:33 UTC.
3. **Level:** `handle_dictating_frame` with `on_headphones` set. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `handy_stop_recording` returns false and does not toggle the live app. `play_cue` and `write_status` are recorded. `fn_held` is false. `latest_history_row` returns no new row. These fail the test if called: `handy_start_recording`, `handy_cancel`, `dispatch_transcript`, `silence_speech`, `stop_playback`, `bridge_request`.
5. **Room mic:** A frame with VAD 0.2 and RMS 40 is not speech when `is_speech` is false. No frames are kept. The state stays `DICTATING`.
6. **Headphones:** The same frame is speech. `speech_seen_in_chunk` becomes true and the frame is kept. VAD 0 and RMS 10 are still not speech. The gate is VAD 0.15 or RMS 30.
7. **Explicit speech:** `is_speech` true counts on the room mic even when VAD and RMS are 0.
8. **Flush:** The room pause in this test is 5 s. Six seconds of silence flushes the room mic: Handy stop is called once, the pause cue is recorded, and the state is `IDLE`. The same six seconds on headphones do not flush. Eight seconds do. The headphone wait is 8 s.
9. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905.
10. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real Handy toggle or the real `write_status`.
