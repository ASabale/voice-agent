# VA-INT-AUTO-017 — Live partial text

1. **ID:** VA-INT-AUTO-017
2. **Checked:** 2026-11-13 20:26 UTC.
3. **Level:** `MicState.show_partial` and `retract_partial`. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `bridge_request` records the post and does not open a socket. `resolve_delivery` fails the test if called, so the live session on port 62283 is not looked up. The base in the test is `http://127.0.0.1:9`.
5. **Plain text:** `hello there` is posted once. The same text again does not post.
6. **Bare command:** `send that` becomes an empty prefix. Nothing is posted and the previous partial stays.
7. **Command with words before it:** `hello send that` scratches the old partial, then posts `hello`. The command itself is not posted.
8. **One-word command:** `please pause` is not stripped. The last word is posted as `pause` plus a word joiner, so the bridge will not treat it as the pause command.
9. **Retract:** One `scratch that` post clears `partial_shown` and `partial_base`.
10. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905. Nothing was posted to port 62283.
11. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `bridge_request`.
