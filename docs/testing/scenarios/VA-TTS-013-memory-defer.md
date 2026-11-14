# VA-TTS-013 — Memory defer

1. **ID:** VA-TTS-013
2. **Name:** Speech waits for memory headroom instead of pushing the machine over the kill line
3. **Objective:** A VoiceBox generation is not started while the Strata memory guardian reports tight headroom.
4. **Failure investigated:** On 2026-11-13 the guardian killed the Flash-Next engine roughly every five minutes with `reason=kernel_vm_critical` at 62.0–62.4 GiB of System Memory Used, while VoiceBox TTS raised its own footprint from 3.03 GiB to 11.81 GiB during a burst. Speaking is the cheaper thing to shed, but the voice path had no idea the machine was tight.
5. **Preconditions:** Repository checkout. Node on `PATH`.
6. **Required application versions:** None.
7. **Required services:** None. Do not start VoiceBox; the guardian's watcher is not required either.
8. **Hardware requirements:** None.
9. **Setup:** From the repository root. The guardian writes `~/.local/state/strata/pressure.json`; the test points `OMP_VOICE_PRESSURE_FILE` at a temporary file.
10. **Execution:**
    ```sh
    node --experimental-strip-types --test tests/memory-pressure.test.ts
    ```
11. **Fixtures:** None. The test calls `readMemoryPressure`, `isMemoryTight` and `waitForHeadroom`.
12. **Expected behavior:** A guardian file with `shedVoice: true` or `headroomGiB < 3` is tight. A missing or corrupt file is not tight. `waitForHeadroom` re-reads once a second up to 8000 ms and reports `ok: true` as soon as headroom returns, `ok: false` with `waitedMs` equal to the budget when it does not.
13. **Pass/fail:** PASS means the predicate and the wait loop behave on synthetic readings. It does not mean a TTS request was refused on a live machine.
14. **Metrics:** None.
15. **Evidence:** The node test summary; the guardian log line `RELIEF reason=voice_unloaded` in `~/.local/state/strata/memory-ceiling.log` when the watcher is running.
16. **Cleanup:** None. The temp directory is removed by the test.
17. **Known failure modes:** When headroom does not return within the 8 s wait, `generate` returns `{deferred: true}` and the sentence is held in `session.deferred` for a retry every 5 s while the reply is open; it is dropped only when a new reply bumps the speech epoch or the 120 s expiry passes (see VA-TTS-014). The deferral adds up to 8 s of delay before the first held utterance.
18. **Automation status:** LEVEL 1.
19. **Known limitations:** No live VoiceBox unload was observed: port 17493 had no listener at verification time, so `shed_voice` returns `voice relief unavailable` and the unload itself is unmeasured.
20. **Last verified:** 2026-11-14 06:15 UTC. `node --test tests/` passed 68.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-13 23:50–05:29 | running guardian | FAIL | Engine killed at 62 GiB with VoiceBox resident; steady state, not a spike. |
| 2026-11-14 06:15 | guardian + extension after the defer gate | PASS | Unit level only. VoiceBox was down; the unload path was not exercised live. |
| 2026-11-14 10:42 | deferred sentences retried instead of dropped (VA-TTS-014) | PASS | Unit level. Retry order, expiry, and epoch drop verified against stubs. |
