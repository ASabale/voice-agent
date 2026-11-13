# VA-INT-AUTO-013 — Idle send and scratch

1. **ID:** VA-INT-AUTO-013
2. **Checked:** 2026-11-13 20:22 UTC.
3. **Level:** `MicState.apply_whisper` with kind `idle_verify`. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `dispatch_transcript` records the text and does not post. `play_cue` records the sound and does not start `afplay`. These fail the test if called: `silence_speech`, `stop_playback`, `handy_start_recording`, `pause_tts_clips`, `kill_tts_clips`. `enter_dictating` fails the test.
5. **Send:** `send prompt` and `all done` both post the fixed text `send prompt`. The heard synonym is not what gets posted. Each plays `SOUND_SEND`. State stays `IDLE`.
6. **Scratch:** `scratch that` posts that heard text and plays `SOUND_CANCEL`. State stays `IDLE`.
7. **Not a command here:** `stop` and `good morning` post nothing and play nothing. A lone `stop` stops playback only when the kind is `tts_barge`, which is VA-INT-AUTO-012.
8. **Live loop:** `controller.log` mtime stayed 1794598062. `status.json` stayed `IDLE` at `updated_at` 1794598062.972905. Nothing was posted to port 62283.
9. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `dispatch_transcript`.
