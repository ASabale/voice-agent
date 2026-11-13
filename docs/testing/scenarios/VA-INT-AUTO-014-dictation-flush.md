# VA-INT-AUTO-014 — Dictation flush

1. **ID:** VA-INT-AUTO-014
2. **Checked:** 2026-11-13 20:23 UTC.
3. **Level:** `MicState.handle_dictating_frame` once the pause has already elapsed. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `handy_stop_recording`, `handy_start_recording`, `wait_for_new_history_row`, `latest_history_row`, `dispatch_transcript`, `play_cue`, and `write_status`. The real `write_status` replaces `status.json`. The real Handy calls toggle the live app. `time.sleep` was a no-op. These fail the test if called: `silence_speech`, `stop_playback`, `handy_cancel`, `pause_tts_clips`, `kill_tts_clips`, `bridge_request`.
5. **Sent:** Handy transcript `all done` is posted as `all done`, not rewritten to `send prompt`. That rewrite happens only on the idle-verify path (VA-INT-AUTO-013). The state becomes `IDLE` and the send cue is recorded. Handy is not started again.
6. **Scratch:** `scratch that` is posted as heard. The state stays `DICTATING`, the cancel cue is recorded, and the stub records one Handy start.
7. **Handy down:** `handy_stop_recording` returns false. Nothing is posted. The state becomes `IDLE` and the pause cue is recorded. Handy is not started.
8. **Live files:** `status.json` mtime stayed 1794598062 and the state stayed `IDLE` at `updated_at` 1794598062.972905.
9. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real Handy toggle or the real `write_status`.
