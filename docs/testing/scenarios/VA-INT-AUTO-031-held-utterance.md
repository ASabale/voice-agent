# VA-INT-AUTO-031 — Held idle utterance

1. **ID:** VA-INT-AUTO-031
2. **Checked:** 2026-11-13 20:40 UTC.
3. **Level:** `release_idle_utterance`, which `handle_idle_frame` calls on every idle frame. Not the microphone. Not LEVEL 4.
4. **Stubbed:** The wake model returns 0. `sync_speech_tier` does nothing. `fn_held` and `is_voicebox_speaking` are false. `enter_dictating` fails the test. These also fail the test: `silence_speech`, `kill_tts_clips`, `handy_start_recording`, `handy_cancel`, `dispatch_transcript`, `play_cue`, `write_status`, `stop_playback`, `pause_tts_clips`.
5. **Free:** A held clip with prompt `held clip` is queued as `idle_verify`. The hold is cleared. The audio is the same array. The state stays `IDLE`.
6. **Dictating:** The same hold is dropped. Nothing is queued. Dictation does not verify an idle clip.
7. **Still busy:** If a Whisper job is already pending, the hold stays and the queue stays empty.
8. **Full queue:** If the queue cannot take the job, the hold is put back and `whisper_pending` stays empty.
9. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905.
10. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `enter_dictating`.
