# VA-INT-AUTO-016 — Dictation idle timeout

1. **ID:** VA-INT-AUTO-016
2. **Checked:** 2026-11-13 20:25 UTC.
3. **Level:** The no-speech branch of `handle_dictating_frame`. The timeout in this test is 15 s. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `handy_cancel`, `play_cue`, `write_status`, `fn_held`, and `latest_history_row`. These fail the test if called: `silence_speech`, `stop_playback`, `handy_stop_recording`, `handy_start_recording`, `dispatch_transcript`, `pause_tts_clips`, `kill_tts_clips`, `bridge_request`.
5. **Still waiting:** 14 s with no speech stays `DICTATING`. Handy is not cancelled. No cue.
6. **Speech resets the idea of idle:** 20 s after the chunk started, a speech frame sets `speech_seen_in_chunk` and does not cancel Handy. The state stays `DICTATING`.
7. **Timeout:** 15 s with no speech calls the `handy_cancel` stub once, records the pause cue, and sets the state to `IDLE`. The cooldown is in the future.
8. **Live files:** `status.json` mtime stayed 1794598062 and the state stayed `IDLE` at `updated_at` 1794598062.972905.
9. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `handy_cancel` or the real `write_status`.
