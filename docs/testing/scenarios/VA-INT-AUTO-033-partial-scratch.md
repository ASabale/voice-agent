# VA-INT-AUTO-033 — Partial scratch failed

1. **ID:** VA-INT-AUTO-033
2. **Checked:** 2026-11-13 20:42 UTC.
3. **Level:** `show_partial` and `retract_partial` when the bridge does not scratch. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `bridge_request` records posts to `http://127.0.0.1:9` and returns the scripted answer. `resolve_delivery` fails the test, so port 62283 is not looked up.
5. **Scratch missing:** The bridge returns nothing for `scratch that`. The old text `hello there` stays. `good night` is not posted.
6. **Scratch not accepted:** The bridge returns action `appended` for the scratch. That is not `scratched`. The old text stays. The replacement is not posted.
7. **Scratch accepted, write rejected:** The scratch returns `scratched` and the following post returns `sent`. The old shown text is cleared. `good night` was posted, but it is not stored as the partial because the action was not `appended`.
8. **No old partial:** The next `good night` is posted by itself and stored.
9. **Retract:** A retract whose answer is `appended` leaves `partial_shown` and `partial_base` in place.
10. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905. Nothing was posted to port 62283.
11. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `bridge_request`.
