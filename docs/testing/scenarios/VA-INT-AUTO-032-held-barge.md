# VA-INT-AUTO-032 — Held barge clip

1. **ID:** VA-INT-AUTO-032
2. **Checked:** 2026-11-13 20:41 UTC.
3. **Level:** `release_barge_clip`. The mic loop calls it after `take_whisper`. Not the microphone. Not LEVEL 4.
4. **Not called:** `silence_speech`, `pause_tts_clips`, `stop_playback`, Handy, and `dispatch_transcript`. The method only queues.
5. **Empty:** No hold returns false.
6. **Busy:** A pending Whisper job keeps the hold. The pending kind stays `busy`. Nothing new is queued.
7. **Dictating:** Unlike an idle hold, a barge hold is still queued while the state is `DICTATING`. The kind is `tts_barge`. The prompt is `Hey Jarvis. stop.` The hold is cleared. The state stays `DICTATING`.
8. **Full queue:** The queue cannot take the job. The hold is put back. `whisper_pending` stays empty. The placeholder already in the queue stays there.
9. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905.
10. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `pause_tts_clips` or `stop_playback`.
