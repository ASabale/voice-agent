# VA-INT-AUTO-029 — Idle history row

1. **ID:** VA-INT-AUTO-029
2. **Checked:** 2026-11-13 20:38 UTC.
3. **Level:** The manual Handy row at the start of `handle_idle_frame`. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `latest_history_row`, `dispatch_transcript`, and `play_cue`. `sync_speech_tier` does nothing. `fn_held` is false. `is_voicebox_speaking` is false. The wake stub returns 0. These fail the test if called: `silence_speech`, `kill_tts_clips`, `handy_start_recording`, `handy_cancel`, `write_status`, `stop_playback`, `pause_tts_clips`. `enter_dictating` fails the test.
5. **Dropped:** History id 7 is above the last id 5 and at or below `fn_ignore_through` 8. Nothing is posted and no cue plays. The last id becomes 7, so the same row is not posted on the next frame. This is the row recorded over playback.
6. **Blank:** Id 9 with only spaces does not post and does not advance the last id.
7. **Send:** `all done` is posted as those words. The send cue plays. The state stays `IDLE`.
8. **Scratch:** `scratch that` plays the cancel cue.
9. **Pause and cancel:** `stop` and `cancel` both play the pause cue, not the cancel cue.
10. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905. Nothing was posted to port 62283.
11. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `dispatch_transcript`.
