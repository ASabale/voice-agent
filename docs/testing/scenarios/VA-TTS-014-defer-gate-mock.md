# VA-TTS-014 — The guardian's voice-shed gate holds the real generation path without touching VoiceBox, and relief replays held sentences in order exactly once

1. **ID:** VA-TTS-014
2. **User-facing failure prevented:** Under memory pressure the extension defers speech — but until now only the *queue bookkeeping* was tested with stub generators. Nothing proved the real `generate()` actually skips the HTTP call when the guardian reports shed, nothing proved a mid-wait recovery speaks instead of timing out, and nothing proved a deferred reply is later spoken exactly once in its original order (no lost speech, no duplicate speech).
3. **Preconditions:** Node 22+. No VoiceBox, no microphone, no guardian. Each test points `OMP_VOICE_PRESSURE_FILE` at its own temp file and `OMP_VOICEBOX_API` at a mock server on its own port (17988/17987/17986, distinct from `voicebox-refusal.test.ts`'s 17991–17999).
4. **Exact reproduction command:** `node --experimental-strip-types --test tests/memory-defer.test.ts` (real 1 s polls inside `waitForHeadroom`; only the pressure file and the HTTP endpoint are synthetic).
5. **Expected behavior:** with `shedVoice: true` or headroom < 3 GiB, `generate()` never issues `/generate/stream` and the sentence lands in the deferred queue with `deferredOldestAgeMs` ≥ the 8 s bound; later sentences of the same reply queue behind it without each burning their own wait; when the guardian reports relief, `retryDeferredSpeech` regenerates each held sentence exactly once, oldest first; if headroom returns mid-wait the sentence is spoken within the wait, not after the full bound; a stale (>30 s) or corrupt pressure file is treated as "no pressure" and never silences speech.
6. **Actual behavior:** all three tests pass with the real gate, exact counters: 0 mock requests during pressure, 3 requests and 3 plays after relief, no duplicates, mid-wait recovery at 2.0 s.
7. **Evidence:** `tests/memory-defer.test.ts` — test 1 asserts `streamHits() === 0` while deferred, `currentSpokenText() === ""`, `status.deferred === 1`, `deferredOldestAgeMs >= MEMORY_WAIT_MS`; after relief asserts `retried === 3`, `streamHits() === 3`, `played === ["Deploy is green.", "Second sentence.", "Third sentence."]`, `currentDeferred().length === 0`. Test 2 asserts elapsed ≥ 2000 ms and < 6000 ms with exactly one play. Test 3 asserts a 60 s-old shed file and a garbage file both produce immediate speech (2 hits, 2 plays, queue empty).
8. **Level:** LEVEL 1 (unit, mock HTTP; the deferral *gate* is exercised end-to-end through the exported `generate()`, not a stub).
9. **What was reproduced first:** reading `generate()` (extension/voicebox-speech.ts:770-791): `waitForHeadroom()` runs before the fetch and returns `{deferred: true}` on timeout; `speakChunk` releases the unspoken text and pushes it to `session.deferred` with the original timestamp. The gap was coverage, not behavior: no existing test called the real `generate()` with a pressure file.
10. **Root causes found:** none — the gate was implemented but untested against the HTTP boundary. `generate` was not exported, so the tests substituted stub generators, leaving the fetch-skip claim unproven.
11. **Fix:** exported `generate()` (documented as testability-only), added `tests/memory-defer-env.ts` (sets `OMP_VOICEBOX_PROFILE`/`OMP_VOICE_PRESSURE_FILE` before the module is evaluated) and three integration tests; wired `tests/memory-defer.test.ts` into the Node CI job.
12. **Tests run:** `node --experimental-strip-types --test tests/memory-defer.test.ts` → 3 passed (8.03 s, 2.01 s, 7.8 ms). Full Node CI invocation (6 files) → 110 passed, 0 failed. Full Python suite → 266 passed. Note: running the new file in isolation first exposed a port clash with `voicebox-refusal.test.ts` (both listened on 17998 when suites share a process); mocks were moved to 17986–17988 and the shared run passes cleanly.
13. **Result:** PASS.
14. **Latencies measured:** deferral fires after the full 8000 ms wait when pressure persists; mid-wait recovery spoke at ~2.0 s; no additional delay when pressure is absent (mock path < 10 ms).
15. **Boundary behavior:** headroom exactly 3.0 GiB does not defer (`< MEMORY_DEFER_HEADROOM_GIB` is strict — pinned by VA-TTS-013 tests); a file with no `at` field is treated as fresh; renamed keys parse as no-pressure rather than a deferral.
16. **Cleanup:** temp pressure dirs removed per test; mock servers closed; env restored to the nonexistent guardian path so later tests never read a stale deferral file.
17. **Automation status:** CI-level, rerunnable; no hardware.
18. **Known limitations:**
   - The mock validates the *gate*, not the guardian's real write cadence; the cross-system field contract is pinned separately by `tests/test_memory_guardian_contract.py` + `tests/fixtures/guardian-pressure.json`.
   - The guardian's live unload was measured once (2026-11-14 21:30 UTC): **11 MB of 5,656 MB freed** — do not claim reclaimed GiB; deferral is the real lever. Port 17493 has no listener since the 21:37 SIGABRT until the owner reopens VoiceBox.
   - Real `afplay` of the generated clip is stubbed here; clip play completion is covered by VA-TTS-003/VA-PLAY rows.
   - A barge-in mid-deferral drops held sentences with the reply (tested in `voicebox-refusal.test.ts`); that is intended behavior, not recovery.
19. **Last verified:** 2026-11-15 02:57 UTC, working tree on `4aa6a54` plus uncommitted changes.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-14 06:15 UTC | VA-TTS-013 stub-level deferral tests | PASS | synthetic readings only; queue semantics, not the HTTP gate |
| 2026-11-15 02:57 UTC | real-`generate()` gate tests (VA-TTS-014) | PASS | 3 new tests, 110/110 Node; port clash with refusal suite found and fixed (mocks moved to 17986–17988) |

next: live unload measurement still needs the owner to reopen VoiceBox (guardian POST to 17493); then close VA-SOAK-006's clean PASS and instrument VoiceBox footprint growth per generation.
