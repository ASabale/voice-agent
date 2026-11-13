# VA-INT-AUTO-019 — Dispatch on a v1 bridge

1. **ID:** VA-INT-AUTO-019
2. **Checked:** 2026-11-13 20:28 UTC.
3. **Level:** The version 1 branch of `dispatch_transcript`. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `resolve_delivery` returns port 9. `bridge_request` does not open a socket. `subprocess.run` records the `osascript` argv and does not run it. `time.sleep` is a no-op. `paste_into_focus` and `fallback_macos_inject` fail the test.
5. **Already pasted:** The draft is `hello there` and the transcript is the same. The result is `appended` with that draft. Nothing is posted. No keystrokes are recorded.
6. **Send:** The draft is empty. `all done` is posted as `send prompt`. No keystrokes.
7. **Pause:** The draft already ends in `please stop`. Version 1 records one `osascript` that would press delete 11 times, then posts `please pause listening`. Version 2 posted the words as heard (VA-INT-AUTO-018). The pause prefix is cleared after the test.
8. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905. Nothing was posted to port 62283. No real keystrokes were sent.
9. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `dispatch_transcript`.
