# VA-MEM-008 — voice shedding survives a dead or hung VoiceBox

1. **ID:** VA-MEM-008
2. **Name:** `shed_voice` returns a no-op when VoiceBox refuses or hangs, and short-circuits before any HTTP while an utterance is playing
3. **Objective:** The relief tier in `~/.local/bin/strata-memory-ceiling` POSTs `/models/unload` to VoiceBox before the guardian touches the engine. The shed must never raise (that would kill the watcher mid-kill-decision) and never stall longer than the HTTP timeout (that would delay the sustained kill).
4. **Failure investigated:** VoiceBox has had no listener on 17493 since the 2026-11-14 21:37 SIGABRT, yet the guardians keep attempting sheds whenever system used crosses 61 GiB — the machine's steady state. VA-LAT-001 documented the half-dead variant: `/health` returns 200 while every `/generate/stream` 500s. A server that accepts sockets but never answers is a plausible state nobody had tested.
5. **Preconditions:** macOS with the guardian installed. Venv.
6. **Required application versions:** Python 3.9+ (the guardian is exec'd as a module; `from __future__ import annotations` is present).
7. **Required services:** None. The "VoiceBox" is a synthetic socket server on an ephemeral port; the refused case targets 17990, which nothing listens on (distinct from the Node mock ranges 17986–17999).
8. **Hardware requirements:** None.
9. **Setup:** None.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_memory_guardian_shed.py -q
    ```
11. **Fixtures:** `VOICE_PLAYING_PATH` pointed at a temp file (`playing: false`, or `playing: true` with the test process's own pid as the liveness witness); a socket server that accepts and never responds.
12. **Expected behavior:**
    - Connection refused → `{"freedBytes": 0, "detail": "voice relief unavailable: ..."}`, immediately, no exception.
    - Hung server → same shape, bounded: the shed returns in under 8 s (the 5 s `urlopen` timeout, plus margin).
    - Playing utterance → `{"freedBytes": 0, "detail": "deferred: utterance in progress"}` and the HTTP helper is never called — the mid-generation unload guard fires before any connection.
13. **Pass/fail:** PASS means the shed actuator is safe against both service states. It does not mean a real unload freed anything — the live VoiceBox is down, and the measured unload of 11 MB (VA-MEM-001) stands as the only real-relief evidence.
14. **Metrics:** Wall-clock elapsed of the shed against the hung server; recorded `_http_json` calls.
15. **Evidence:** pytest summary: 3 passed in 5.65 s (the hung case lands at ~5 s, exactly the timeout).
16. **Cleanup:** Temp dirs; the hung server thread is daemon and the listening socket is closed in `finally`.
17. **Known failure modes:** If someone raises the `urlopen` timeout above ~10 s the elapsed assertion fails — deliberately, because the kill loop's cadence assumes shed latency is bounded. The synthetic server holds connections 20 s; a real server that responds slowly-but-correctly is not modeled.
18. **Automation status:** LEVEL 1.
19. **Known limitations:** Tests the actuator, not end-to-end relief (no real footprint delta). The `time.sleep(1.0)` between unload and re-measure is real and untested for necessity.
20. **Last verified:** 2026-11-15 05:40 UTC, 3 tests in `tests/test_memory_guardian_shed.py`; full suite 290 passed.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-15 05:40 | refused / hung / playing-short-circuit shed tests | PASS | First time the shed path itself was exercised end-to-end; the policy harness stubs `shed_result` and never ran the real `_http_json` timeout. The bound is 5 s per request (two requests worst case: status then unload, plus 1 s re-measure sleep). |
