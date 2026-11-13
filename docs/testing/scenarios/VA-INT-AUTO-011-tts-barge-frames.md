# VA-INT-AUTO-011 — TTS barge frames

1. **ID:** VA-INT-AUTO-011
2. **Checked:** 2026-11-13 20:20 UTC.
3. **Level:** The `tts_active` branch of `handle_idle_frame`. Not the microphone. Not LEVEL 4.
4. **Why a raw stop file does not queue:** `stop-say.wav` has four loud frames. The branch needs three hot frames to arm, skips the next two, then needs three more before it calls the clip a voice. The file ends first. Also, loud frames fed while the hold is down are stored as the speaker-bleed floor. The next frame must beat 2.4 times that floor, so the clip raises its own gate and never arms.
5. **What was fed:** 25 quiet frames at amplitude 150, then the four loud frames repeated to eight, then six silent frames. Nothing was played. `pause_tts_clips` and `resume_tts_clips` were recorded and not run. The real `pause_tts_clips` sends `SIGSTOP` to `afplay`. These were patched to fail the test: `silence_speech`, `kill_tts_clips`, `stop_playback`, `handy_start_recording`, `play_cue`, `dispatch_transcript`.
6. **Result:** State stayed `IDLE`. One job was queued with kind `tts_barge` and prompt `Hey Jarvis. stop.` Whisper on that job was a playback barge. `pause_tts_clips` was the stub, not the real function. No forbidden function ran.
7. **Live loop:** `controller.log` mtime stayed 1794598062. `status.json` stayed `IDLE` at `updated_at` 1794598062.972905.
8. **Still blocked:** Playing the clip would run the real pause and, if the words are "stop", `stop_playback`. LEVEL 4 still needs a second input.
