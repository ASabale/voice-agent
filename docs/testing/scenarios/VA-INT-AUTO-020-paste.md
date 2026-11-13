# VA-INT-AUTO-020 — Paste delivery

1. **ID:** VA-INT-AUTO-020
2. **Checked:** 2026-11-13 20:29 UTC.
3. **Level:** `dispatch_transcript` when delivery mode is `paste`. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `resolve_delivery` returns mode `paste` and port 9, so the live session is not selected. `fallback_macos_inject` records the text and does not type. `bridge_request` does not open a socket. `subprocess.run` fails the test, so the v1 delete keystrokes cannot run.
5. **Plain text:** `hello there` is typed as `hello there ` with action `appended`. Nothing is posted. The result says `via` `focus`.
6. **Scratch:** `scratch that` returns action `scratched` and types nothing. The focused app is not given that command as characters.
7. **Send:** `ship all done` types `ship` and returns action `sent`. The words `all done` are the Enter, not more typed text. Nothing is posted.
8. **Pause:** `please stop` is posted as `please stop` to port 9 and is not typed. The bridge response is returned.
9. **Preserved line:** A stored pause line `remember this` is put in front of the next send, so `ship all done` types `remember this ship`. The bridge draft matches that stored line, so the next post is `clear draft`.
10. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905. Nothing was typed into the focused app. Nothing was posted to port 62283.
11. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `dispatch_transcript` or the real `fallback_macos_inject`.
