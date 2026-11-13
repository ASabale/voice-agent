# VA-INT-AUTO-018 — Dispatch on a v2 bridge

1. **ID:** VA-INT-AUTO-018
2. **Checked:** 2026-11-13 20:27 UTC.
3. **Level:** `dispatch_transcript` against a version 2 bridge. Not the microphone. Not LEVEL 4.
4. **Stubbed:** `resolve_delivery` returns port 9, not pid 16590. `bridge_request` records the call and does not open a socket. `paste_into_focus` and `fallback_macos_inject` fail the test. Those type into the focused app.
5. **Empty:** Whitespace returns `noop` and does not call the bridge.
6. **Send:** `all done` is posted as `send prompt`. The v2 body is that rewritten text.
7. **Not a send:** `scratch that` and `hello there` are posted unchanged.
8. **Pause:** `please stop` is posted as `please stop`. On v2 it is not rewritten to `pause listening`. That rewrite is the v1 branch. The pause prefix is kept in memory and the test clears it.
9. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905. Nothing was posted to port 62283.
10. **Still blocked:** LEVEL 4 still needs a second input. Do not call the real `dispatch_transcript`.
