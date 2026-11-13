# VA-INT-AUTO-026 — Partial transcript while speech continues

1. **ID:** VA-INT-AUTO-026
2. **Checked:** 2026-11-13 20:35 UTC.
3. **Level:** `maybe_emit_partial` inside `handle_dictating_frame`. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `fn_held` is false. `latest_history_row` returns no new row. `write_status` does nothing. These fail the test if called: `handy_stop_recording`, `handy_start_recording`, `handy_cancel`, `dispatch_transcript`, `silence_speech`, `stop_playback`, `bridge_request`, `play_cue`.
5. **Too short:** 17 frames at amplitude 400 do not queue a job. The state stays `DICTATING`.
6. **Too quiet:** 18 frames at amplitude 100 do not queue a job. The peak gate is 350.
7. **Ready:** 18 frames at amplitude 400 queue one job. The kind is `partial`. The prompt is `A person dictating a sentence.` `partial_sent_frames` becomes 18. The state stays `DICTATING`. Handy is not stopped.
8. **Not again yet:** One more loud frame does not queue a second job while the first is still pending. `partial_sent_frames` stays 18.
9. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905.
10. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real Handy toggle or the real `bridge_request`.
