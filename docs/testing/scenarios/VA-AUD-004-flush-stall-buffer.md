# VA-AUD-004 — The flush path cannot stall the mic consumer past the queue buffer, so dictation frames are not dropped mid-turn

1. **ID:** VA-AUD-004
2. **User-facing failure prevented:** During a flush (the moment a dictated sentence is submitted), the frame consumer blocks on synchronous Whisper waits. The callback thread keeps offering 12.5 blocks/second into a 32-block (2.56 s) queue; every block beyond the buffer is discarded — the beginning of whatever the user says next is silently lost. Observed in VA-SOAK-006 run 3: `mic_dropped` +5 while the owner was dictating.
3. **Preconditions:** Node-free; venv Python 3.12. No microphone opened (`SoundDeviceAudioSource` is constructed but never entered).
4. **Exact reproduction command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_mic_flush_stall.py -q`
5. **Expected behavior:** `show_closing_partial` returns immediately when a Whisper job is already in flight (matching `maybe_emit_partial`'s guard) and never waits longer than its bound when the worker is free; `transcribe_local_fallback` likewise; the production queue absorbs a full flush stall (≥ 8 s of callback blocks) with zero drops and preserves oldest-first order.
6. **Actual behavior (before fix):** four falsifiable tests failed against the working tree: closing partial blocked the frame loop **4.85 s** with a partial in flight; no wait bound existed; local fallback queued behind a busy worker and returned its transcript only after ~2 s; 100 blocks (8 s) into the 32-block queue dropped **68**.
7. **Evidence:** pre-fix run: `4 failed, 2 passed in 9.94s` (`tests/test_mic_flush_stall.py`). Magnitude check pinned to the live soak: a 3 s stall at callback cadence = 37 offers into 32 blocks = exactly **5 drops** — the same delta the soak probe measured on pid 38298. The blocking calls are at `bin/omp-voice-controller` `show_closing_partial` (blocking `jobs.put(timeout=8)` + `slot.get(timeout=8)`, no busy guard) and `transcribe_local_fallback` (unbounded `jobs.put`, `slot.get(timeout=30)`), both called from the frame-consumer loop right at flush.
8. **Level:** LEVEL 1 (unit; real controller code, emulated Whisper worker, no microphone).
9. **What was reproduced first:** the 5-drop magnitude and the 4.85 s stall, both before touching code.
10. **Root cause found:** the flush block runs `show_closing_partial` even when `whisper_pending` is set; `jobs` is `maxsize=1`, so `put(timeout=8)` waits for the in-flight partial, then the new job's own round trip waits again. With the subsequent Handy ASR wait (≤ 2.2 s), the 0.26 s paste settle, and dispatch, the consumer stalls ~3 s — longer than the 2.56 s buffer. The 32-block size was designed for catch-up speed, not for the flush stall.
11. **Fix:** `MIC_QUEUE_BLOCKS = 128` (10.24 s of audio, ~328 KB) sized to cover the documented flush stall; busy guard + `put_nowait` + bounded waits (`CLOSING_PARTIAL_WAIT_SECONDS = 6.0`, `LOCAL_FALLBACK_WAIT_SECONDS = 12.0`) in both flush-path functions. No gate weakened: drops during stalls are asserted to be zero, order asserted, and the old contract test updated to the new interface rather than deleted.
12. **Tests run:** `pytest tests/test_mic_flush_stall.py tests/test_mic_capture.py -q` → 12 passed. Full suite `pytest tests/ -q` → **272 passed** (266 previous + 6 new). Node CI invocation (6 files) → **110 passed**.
13. **Result:** PASS.
14. **Latencies measured:** closing partial with a busy worker: < 0.2 s (was 4.85 s in the reproduction with a 2 s worker delay). Free-worker bound: returns within `CLOSING_PARTIAL_WAIT_SECONDS`.
15. **Boundary behavior:** stalls longer than 10.24 s still drop the oldest blocks (bounded-loss design preserved); the busy guard means a closing partial is *skipped* (UI prefix stays stale) rather than delaying the flush — no speech is lost from the transcript.
16. **Cleanup:** none needed; no files, no processes, mic never opened.
17. **Automation status:** CI-level, rerunnable. Add `tests/test_mic_flush_stall.py` to the pytest run (the CI job runs `pytest tests/`, so it is covered).
18. **Known limitations:**
   - The Whisper worker is emulated; real tiny.en latency under the ~46 GiB model residency is not measured here. The queue covers 10 s, which exceeds any observed worker delay; an extreme stall beyond 10 s would still drop blocks.
   - **The live controller (pid 38298) still runs the old code** until the owner restarts it; a restart requires handing over the microphone. Until then this fix is proven at unit level only, not in the running installation.
   - Physical confirmation (dictate during a flush and see zero loss) needs the live controller on the new code — BLOCKED on owner handover, same as the AEC-REAL rows.
19. **Last verified:** 2026-11-15 03:10 UTC, working tree on `4aa6a54` plus uncommitted changes.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-14 ~21:20 local | VA-SOAK-006 run 3 | observation | `mic_dropped` +5 during owner dictation; flagged as unroot-caused |
| 2026-11-15 03:10 UTC | busy guard + bounded waits + 128-block queue | PASS | reproduction pinned the exact 5-drop magnitude; 272/272 Python |

next: owner restarts controller 38298 → rerun the soak (or any dictation turn) and verify `mic_dropped` delta 0 on the running installation; root-cause the VoiceBox SIGABRT once the app is reopened.
