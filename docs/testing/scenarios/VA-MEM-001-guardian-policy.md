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
13. **Pass/fail:** PASS means the decision logic holds on deterministic traces. It does not mean a live engine was protected or a real VoiceBox was unloaded.
14. **Metrics:** Stop count, relief times, and log lines per trace.
15. **Evidence:** pytest summary; the recorded stop reasons and relief timestamps per trace.
16. **Cleanup:** None; no files are written (the real `write_pressure` is stubbed).
17. **Known failure modes:** The trace replaces the sensors, so it cannot catch a miscalibration in `vm_memory_stats` itself. Post-stop iterations keep `running` true in the synthetic world, so traces end immediately after the expected action. The re-check shrinks the unload window but cannot make gate+unload atomic; VoiceBox would need to reject unload while a stream is active for a hard guarantee.
18. **Automation status:** LEVEL 1.
19. **Known limitations:** The live VoiceBox unload (port 17493) has never been measured: the service had no listener at verification time, so the ~2.4 GiB relief claim is unverified. Physical protection under a real burst is Level 4/5 and not run here.
20. **Last verified:** 2026-11-14 16:45 UTC, 12 passed; guardian `self-test` and `pressure` ran cleanly after the edit (no kill conditions on the real machine).

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-14 10:45 | tiered guardian + synthetic trace harness | PASS | Unit level. Steady state no longer kills; relief precedes the kill. |
| 2026-11-14 16:45 | unload race re-check + no phantom relief | PASS | `shed_voice` re-reads the playing flag before the POST; failed unloads log `VOICE_DEFER` and do not arm the relief grace. 12 tests. |