# VA-INT-AUTO-021 — Bridge status failed

1. **ID:** VA-INT-AUTO-021
2. **Checked:** 2026-11-13 20:30 UTC.
3. **Level:** `dispatch_transcript` when `bridge_request` returns nothing. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `resolve_delivery` returns port 9. `bridge_request` returns `None`. `fallback_macos_inject` records the text and does not type. `subprocess.run` fails the test.
5. **Plain text:** `hello there` is typed as `hello there ` and the result is `appended`.
6. **Send:** `ship all done` is canonicalized before the fallback. The typed text is `ship` and the action is `sent`.
7. **Pause:** `please stop` types `please ` and returns `paused`. The pause word is not typed.
8. **Cancel:** `cancel` returns `cancelled` and types nothing.
9. **Scratch, no text focus:** `scratch that` is typed as `scratch that ` and the result is `appended`. It is not treated as a scratch command.
10. **Scratch, text focus:** The same words return action `scratched` with `via` `focus` and type nothing more.
11. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905. Nothing was typed. Nothing was posted to port 62283.
12. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `dispatch_transcript` or the real `fallback_macos_inject`.
