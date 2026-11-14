# VA-TTS-016 — VoiceBox outage holds speech instead of dropping it

1. **ID:** VA-TTS-016
2. **Name:** Sentences held when VoiceBox is unreachable or unhealthy, retried when it returns
3. **Objective:** A reply rendered on screen must not be silently lost from speech because VoiceBox is down, returning 500, answering 200 with a truncated payload, or having its connection die mid-request. Before this fix, an outage dropped the sentence permanently: memory-deferred sentences had a retry chain, but refusal/HTTP/transport failures returned "no clip" and the retry chain never saw them.
4. **Failure investigated:** Reproduced in `tests/voicebox-refusal.test.ts` against mock VoiceBoxes on ports 17999/17998/17997 (never the real 17493): (a) a mock answering 500 on `/generate/stream` — sentence dropped, `currentDeferred()` empty, never spoken; (b) nothing listening on the port — sentence dropped; (c) VoiceBox alive but the model unloaded, answering 200 with a 4-byte payload — logged `failed` with reason `short-audio` and dropped. Second-order root cause found during repro: after a listener closes, Node's fetch reuses the dead keep-alive socket and throws `ECONNRESET` (not `ECONNREFUSED`), which the old `isConnectionRefusal` matcher did not recognize, so even the 5 s refusal hold rarely armed on real transient failures.
5. **Preconditions:** Node 22. No VoiceBox, no microphone, no controller.
6. **Required application versions:** extension/voicebox-speech.ts with the deferral contract.
7. **Required services:** A mock HTTP server; the real VoiceBox is never contacted (the test sets `OMP_VOICEBOX_API` before importing the module).
8. **Hardware requirements:** None.
9. **Setup:** None beyond the repo.
10. **Execution:**
    ```sh
    node --experimental-strip-types --test tests/voicebox-refusal.test.ts
    ```
11. **Fixtures:** Mock `/generate/stream` (500 or connection refused), stub player, stub generator.
12. **Expected behavior:** 500 → `{deferred: true}` → sentence in `currentDeferred()`, never counted as spoken (`currentSpokenText() === ""`), retried every 5 s (timer) while the reply is current, dropped only when a barge-in takes over the epoch or after `DEFER_EXPIRY_MS` (120 s) of continuous unavailability. Within the 5 s refusal window after a refused connection, further sentences are held without opening new connections. Recovery replays held sentences oldest-first, exactly once, with dedupe against already-committed text.
13. **Pass/fail:** PASS = all seven tests.
14. **Metrics:** Deferred count, HTTP attempt count (no hammering), played order, duplicate count (0), spoken-text accounting.
15. **Evidence:** 2026-11-14 17:35 UTC: 87 passed, 0 failed (7 refusal tests + 80 existing). Before the fix the same tests failed exactly where predicted (deferred length 0 for 500, refused, and short-audio cases). Standalone probes captured the real Node error shapes: `TypeError: fetch failed` with cause `connect ECONNREFUSED 127.0.0.1:17999`, and after a close, cause `read ECONNRESET` — the keep-alive pool keys by origin, so mock servers get their own ports per test to avoid dead-socket leakage. Live-log evidence of the old behavior: `speech.log` lines with `"event":"failed","reason":"short-audio","bytes":4` (mock) and `"reason":"TypeError: fetch failed"` (live session, 17:12 UTC).
16. **Cleanup:** Mock servers closed; no processes left running.
17. **Known failure modes:** An outage longer than 120 s expires held sentences by design (logged `defer-expired`, not silent). Non-transport errors (e.g. malformed profile lookup that returns 200 with junk) are still dropped as `failed` — they are not transient.
18. **Automation status:** LEVEL 1, in CI (added to the node job).
19. **Known limitations:** Mock HTTP, not the real VoiceBox sidecar: a real 500 (unloaded TTS model) will follow the same code path, but actual recovery latency and audio validity after recovery are unverified until VoiceBox is reopened (VA-LAT-001 prerequisite). Timer-driven retry against the real service is exercised only in live sessions.
20. **Last verified:** 2026-11-14 17:25 UTC.

## History

| When | Revision | Result | Notes |
|---|---|---|---|
| 2026-11-14 17:25 | `generate()` returns `{deferred: true}` on refusal-hold, HTTP non-2xx, and transport failures; `isConnectionRefusal` broadened to ECONNRESET/ETIMEDOUT/ENOTFOUND; `OMP_VOICEBOX_API` env override added for testability; `resetSpeechSession()` clears the refusal clock | PASS | No assertion weakened; expiry, epoch-drop, and dedupe semantics unchanged. |
| 2026-11-14 17:35 | HTTP 200 with a payload under 100 bytes also defers (reason `short-audio`); `apiBase()` resolved per call so each mock scenario runs on its own port; abort errors excluded | PASS | Short-audio deferral does not arm the connection-refusal hold — the service is reachable, the retry timer already paces attempts. No thresholds changed. |
