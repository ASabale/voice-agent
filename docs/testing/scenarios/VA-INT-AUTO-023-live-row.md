# VA-INT-AUTO-023 — Handy row during dictation

1. **ID:** VA-INT-AUTO-023
2. **Checked:** 2026-11-13 20:32 UTC.
3. **Level:** A new Handy history row while `handle_dictating_frame` is dictating. The 5 s pause has not elapsed. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `latest_history_row`, `dispatch_transcript`, `play_cue`, `write_status`, and `handy_start_recording`. `time.sleep` is a no-op. These fail the test if called: `handy_stop_recording`, `handy_cancel`, `silence_speech`, `stop_playback`, `bridge_request`, `pause_tts_clips`, `kill_tts_clips`.
5. **No new row:** History id 3 is already consumed. The state stays `DICTATING`. Nothing is posted. Handy is not started.
6. **Send:** Row `all done` is posted as those words. The state becomes `IDLE` and the send cue is recorded. Handy is not started. This is not the fn-release path: fn release uses the pause cue even when dispatch says `sent`.
7. **Scratch:** `scratch that` stays `DICTATING`. The cue is the chunk tick, not the cancel cue. The silence-flush path plays the cancel cue for a scratch. This path starts Handy once. The buffered speech frames are cleared.
8. **Pause:** `stop` is posted as `stop`. The state becomes `IDLE` and the pause cue is recorded. Handy is not started.
9. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905.
10. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real Handy controls or the real `write_status`.
