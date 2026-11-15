# VA-TTS-014 — Deferred sentences retry in order and expire with the pressure

1. **ID:** VA-TTS-014
2. **Name:** Headroom-deferred speech is retried, ordered, epoch-guarded, and expiry-bounded
3. **Objective:** When `waitForHeadroom` gives up, the sentence is held in `session.deferred` and replayed when headroom returns — never lost, never duplicated, never spoken after a newer reply has started.
4. **Failure investigated:** The first deferral implementation (VA-TTS-013) dropped the sentence entirely. Silent loss of content the user expected to hear is a reliability failure of the same class as the repeat bugs in TTS-002/009/012.
5. **Preconditions:** Node 22+ with `--experimental-strip-types`.
6. **Required application versions:** `extension/voicebox-speech.ts` with `enqueue`, `retryDeferredSpeech`, `DeferredSpeech`, `DEFER_RETRY_MS`, `DEFER_EXPIRY_MS`.
7. **Required services:** None. Generator and player are injected stubs; no VoiceBox, no `afplay`.
8. **Hardware requirements:** None.
9. **Setup:** None.
10. **Execution:**
    ```sh
    node --experimental-strip-types --test tests/memory-pressure.test.ts
    ```
11. **Fixtures:** A headroom sequence passed to `waitForHeadroom`; a stub generator that returns `{deferred: true}` while the sequence says pressure persists and `{clip: "…n"}` otherwise; a stub player that records clips as spoken.
12. **Expected behavior:**
    - Two sentences deferred while pressure holds: `currentSpokenText()` stays `""`; once headroom returns, both replay oldest-first.
    - A retry attempt while pressure still holds re-defers silently and plays nothing.
    - `stopPlayback()` (a new reply) before recovery empties the queue: no clip from the old reply ever plays.
    - With a frozen clock past `DEFER_EXPIRY_MS`, retry drops the stale items with a `defer-expired` log instead of retrying forever.
    - A retried sentence whose text was already committed as spoken is skipped by the `speechAfterSpoken` dedupe.
    - A deferred item retried after recovery plays exactly once: it is removed from the queue before generation and is never counted twice.
13. **Pass/fail:** PASS means the queue discipline holds at unit level. Whether VoiceBox actually recovers headroom on a real machine is a separate Level 4 question.
14. **Metrics:** Deferred queue length, spoken clip order, expiry logs.
15. **Evidence:** 13 node test names including "deferred sentences retry in order once headroom returns", "a new reply before recovery drops the stale deferrals", "deferrals expire after the pressure window instead of retrying forever".
16. **Cleanup:** None.
17. **Known failure modes:** The retry timer is a single `setTimeout`; tests call `stopDeferredRetry()` to keep the process from lingering. Real TTS after a 5 s deferral may arrive after the user has moved on; the epoch guard drops it then.
18. **Automation status:** LEVEL 1.
19. **Known limitations:** No real `/generate/stream` call and no real playback are exercised. Live unload relief was measured once at 11 MB of 5,656 MB (2026-11-14 21:30 UTC, see VA-MEM-001); the sidecar has been down since the 21:37 SIGABRT.
20. **Last verified:** 2026-11-14 10:42 UTC, 13 passed.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-14 10:42 | deferred queue + retry timer + epoch/expiry guards | PASS | Unit level. Order, expiry, and dedupe verified. |