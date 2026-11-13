# VA-INT-AUTO-027 — Partial written at flush time

1. **ID:** VA-INT-AUTO-027
2. **Checked:** 2026-11-13 20:36 UTC.
3. **Level:** `show_closing_partial` and `apply_whisper` kind `partial`. Not the microphone. Not LEVEL 4.
4. **Stubbed:** The worker slot is filled inside `put`, so the 8 s wait does not run. `bridge_request` records posts to `http://127.0.0.1:9`. `resolve_delivery` fails the test, so port 62283 is not looked up.
5. **Not written:** Five loud frames do not ask the worker. Six frames at amplitude 100 do not either. The peak gate is 350. Six loud frames whose `partial_sent_frames` is already 3 do not ask, because fewer than four frames are new.
6. **Written:** Six frames at amplitude 400 ask with the prompt `A person dictating a sentence.` The answer `hello there` is posted once. `partial_sent_frames` becomes 6.
7. **Empty or down:** A blank answer posts nothing and leaves `partial_sent_frames` at 0. A worker that raises posts nothing.
8. **Kind partial:** The same words in `IDLE` do not post. In `DICTATING` they scratch the previous partial and post `good night`.
9. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905. Nothing was posted to port 62283.
10. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `bridge_request`.
