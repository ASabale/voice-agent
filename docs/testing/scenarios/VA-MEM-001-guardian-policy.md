# VA-MEM-001 — Guardian tier policy on synthetic traces

1. **ID:** VA-MEM-001
2. **Name:** The memory guardian tiers voice relief before engine stop and never kills on its normal steady state
3. **Objective:** The `watch()` loop in `~/.local/bin/strata-memory-ceiling` applies its tiering rules exactly as documented: shed voice first, require sustained evidence for a kill, never unload TTS mid-utterance, rate-limit unloads, and only idle-unload near the kill line.
4. **Failure investigated:** On 2026-11-13 the guardian killed Flash-Next at 62.0–62.4 GiB (`reason=kernel_vm_critical`), which is the machine's normal operating point with a 46 GiB model resident. Kernel CRITICAL alone is not exhaustion.
5. **Preconditions:** macOS with the guardian installed at `~/.local/bin/strata-memory-ceiling`. Venv.
6. **Required application versions:** Python 3.12 (the guardian runs on the system python; the test only imports its source).
7. **Required services:** None. No engine, no VoiceBox, no watcher process is touched.
8. **Hardware requirements:** None. The real Mach/libproc sensors are replaced by a deterministic trace.
9. **Setup:** None beyond the installed guardian script.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_memory_guardian_policy.py -q
    ```
11. **Fixtures:** Synthetic samples built from GiB-level facts with the guardian's own constants (`CEILING_BYTES`, `SYSTEM_USED_KILL_BYTES`, `MIN_HEADROOM_BYTES`, `EMERGENCY_HEADROOM_BYTES`, `VOICE_SHED_BYTES`). `sample()`, `stop_engine`, `shed_voice`, `write_pressure`, `_voice_is_playing`, `_idle_seconds`, and `time` are replaced; `watch()` is the real loop.
12. **Expected behavior:**
    - 62 GiB used, kernel CRITICAL, 46 GiB footprint: twenty samples produce no stop and no unload; the pressure file carries `shedVoice: true` so the extension defers speech.
    - Three samples over 63 GiB then recovery: no kill (one spike is not sustained evidence).
    - Sustained 63.2 GiB (headroom 0.8 GiB): exactly one VoiceBox unload first, then `RELIEF_PENDING` logged, then the stop only after the 10 s relief grace; reason `system_memory`.
    - Headroom 0.6 GiB: immediate `memory_exhausted` stop on the first sample; no waiting for voice relief.
    - Voice playing: no unload is issued mid-utterance; the engine kill still proceeds after sustained strikes.
    - Sustained footprint over the 55 GiB ceiling with system headroom: unloads are separated by at least 60 s, never once per sample.
    - Recovery to 57 GiB clears `shedVoice`.
    - Idle unload arms only at 62 GiB or above; a 300 s idle at 61 GiB keeps the model resident.
    - `shed_voice` against a refused connection reports `freedBytes: 0` and "voice relief unavailable", never a success.
    - The playing flag is re-checked inside `shed_voice` immediately before the unload POST: if an utterance starts between the gate in `watch()` and the POST, the unload is deferred (`detail: "deferred: utterance in progress"`) and no HTTP call is made at all.
    - A failed or deferred unload does not set the relief grace clock and logs `VOICE_DEFER`, not `RELIEF`; the sustained-evidence kill then proceeds without a phantom 10 s wait.
    - A second engine sampled alongside Strata is stopped immediately with target `mtplx` (Rule 0), before the emergency rule, the voice shed, or any pressure-file write; the conflict is resolved before generic memory tiers apply.
    - The idle unload at the arm line is blocked by the watchdog's `keep` policy, by a request already in flight, or by a busy prompt slot; it fires on the first sample where all three guards clear.
    - Swap growth (≥128 MiB since engine start with ≥32 pages swapped out per check) is **not** an independent kill trigger: `swapping` requires headroom < 1 GiB, the same floor as `overSystem`. At 61.5 GiB used with 512 MiB of swap growth nothing is tight — no unload, no stop, only the shed flag. When swap growth accompanies a sustained headroom breach, the kill reason is labeled `swap` rather than `system_memory`, and voice relief still precedes it.
13. **Pass/fail:** PASS means the decision logic holds on deterministic traces. It does not mean a live engine was protected or a real VoiceBox was unloaded.
14. **Metrics:** Stop count, relief times, and log lines per trace.
15. **Evidence:** pytest summary; the recorded stop reasons and relief timestamps per trace.
16. **Cleanup:** None; no files are written (the real `write_pressure` is stubbed).
17. **Known failure modes:** The trace replaces the sensors, so it cannot catch a miscalibration in `vm_memory_stats` itself. The harness models engine death after a recorded stop (target-aware: a Rule 0 stop removes only MTPLX, an `all` stop removes every engine), so traces run past a kill and assert the rules do not re-fire and the shed flag clears on the not-running branch — it does not model a restart or a relaunch. The re-check shrinks the unload window but cannot make gate+unload atomic; VoiceBox would need to reject unload while a stream is active for a hard guarantee.
18. **Automation status:** LEVEL 1.
19. **Known limitations:** The live VoiceBox unload was measured on 2026-11-14 21:30 UTC (listener pid 38531): `POST /models/unload` freed **11 MB of a 5,656 MB footprint** — the MLX Metal arena stays allocated, so voice shedding is a bounded courtesy and the extension-side deferral via `pressure.json` is the real memory lever. That listener died in the 21:37 SIGABRT, so the measurement is a single data point, not a repeated result, and per-generation footprint growth is still uninstrumented. Physical protection under a real burst is Level 4/5 and not run here.
20. **Last verified:** 2026-11-15 04:40 UTC, 22 passed in this file; live guardian confirmed running (pids 38389/38402, `pressure.json` rewritten within one poll at 59.94 GiB used / 4.06 GiB headroom, `shedVoice: false`).

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-14 10:45 | tiered guardian + synthetic trace harness | PASS | Unit level. Steady state no longer kills; relief precedes the kill. |
| 2026-11-14 16:45 | unload race re-check + no phantom relief | PASS | `shed_voice` re-reads the playing flag before the POST; failed unloads log `VOICE_DEFER` and do not arm the relief grace. 12 tests. |
| 2026-11-15 03:55 | dual-engine Rule 0 coverage | PASS | Three new tests: conflict stop targets `mtplx` before any memory rule; Rule 0 precedes the emergency kill (order asserted); no pressure file or voice shed is written while engines conflict. 15 tests in the file. |
| 2026-11-15 04:05 | Rule 4 idle-guard branches | PASS | `keep` policy, in-flight request, and busy slot each block the idle unload; a drained slot fires `proactive_idle_pressure` on the first free sample. 19 tests. First genuine failure this session: the drain trace kept the synthetic engine "running" after a stop and re-fired the rule four times — trace now ends at the expected action (the harness's documented known failure mode), assertion unchanged. |
| 2026-11-15 04:25 | Swap-reason kill coverage | PASS | Two new tests (21 in file): 512 MiB swap growth at 61.5 GiB used stays quiet (no unload, no stop); sustained 63.2 GiB with 128 MiB swap growth + 32-page swapout delta kills with reason `swap` after voice relief. Structural finding pinned by assertion: `swapping` needs headroom < 1 GiB, the same floor as `overSystem`, so swap growth can label a kill but never trigger one alone. First run failed on a 60-sample trace because the post-stop synthetic engine re-fired the rule four more times — trace truncated to 42 samples, assertion unchanged. |
| 2026-11-15 04:40 | Harness models engine death after a stop | PASS | `fake_stop` now marks the killed engine(s) absent from later samples, target-aware (Rule 0 kills only MTPLX). This removed the documented "traces end at the expected action" limitation: the drain test uses a real busy→free slot sequence ([True]×4 + [False]×4) instead of a truncated trace; the swap test runs 60 samples and asserts exactly one kill; a new test asserts a kill clears the shed flag and never re-fires. Two dual-engine tests failed first — the naive model had every stop kill both engines, contradicting Rule 0's targeted MTPLX stop — fixed by target-aware death, not by weakening assertions. 22 tests in the file. |