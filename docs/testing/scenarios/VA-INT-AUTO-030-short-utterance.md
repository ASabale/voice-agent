# VA-INT-AUTO-030 — Short utterance under the wake score

1. **ID:** VA-INT-AUTO-030
2. **Checked:** 2026-11-13 20:39 UTC.
3. **Level:** Path 2 of `handle_idle_frame`. The wake stub returns 0, so this is not the keyword path. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `sync_speech_tier` does nothing. `fn_held` and `is_voicebox_speaking` are false. `enter_dictating` fails the test. These also fail the test: `silence_speech`, `kill_tts_clips`, `handy_start_recording`, `handy_cancel`, `dispatch_transcript`, `play_cue`, `write_status`, `stop_playback`, `pause_tts_clips`.
5. **Not yet:** One frame at amplitude 500 plus six silence frames does not queue. Six frames are 480 ms.
6. **Queued:** The seventh silence frame queues one `idle_verify` job. The prompt starts with `Hey Jarvis`. The speech buffer is cleared. The state stays `IDLE`. Seven frames are 560 ms. The peak gate is 450.
7. **Too quiet:** Amplitude 100 with the same silence does not queue.
8. **Too long:** 43 speech frames clear the buffer. The cap is 42. The following silence does not queue.
9. **Busy:** If a Whisper job is already pending, the utterance is held on `idle_verify_next` and the queue stays empty. The pending kind stays `busy`.
10. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905.
11. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `enter_dictating`.
