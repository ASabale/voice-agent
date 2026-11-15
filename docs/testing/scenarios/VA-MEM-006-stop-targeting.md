# VA-MEM-006 — stop_engine targets the right processes and escalates only survivors

1. **ID:** VA-MEM-006
2. **Name:** The guardian's engine stop signals only the targeted engine, survives a hanging supervisor, and SIGKILLs only processes that outlived SIGTERM
3. **Objective:** `stop_engine` in `~/.local/bin/strata-memory-ceiling` is the actuator behind every kill rule. Its three side effects — SIGTERM targeting, supervisor cleanup that must never raise, and the 1.5 s rescans-then-SIGKILL escalation — are exercised with every process touch stubbed.
4. **Failure investigated:** Two recorded field incidents shaped this code: a `subprocess.TimeoutExpired` from the supervisor stop escaped `watch()` and launchd restarted the guardian with the engine half-dead; and Rule 0's `target="mtplx"` stop must never signal Strata, since killing the resident 46 GiB model mid-request is exactly what the tiering protects against. Neither behavior had any test before 2026-11-15: the policy harness stubs `stop_engine` itself, and the contract file only covered `write_pressure` and `_voice_is_playing`.
5. **Preconditions:** macOS with the guardian installed. Venv.
6. **Required application versions:** Python 3.12 (imports the guardian source as a module).
7. **Required services:** None. `os.kill`, `subprocess.run`, `scan_processes`, and `time.sleep` are stubbed; no real process is signalled, and the record file is written to a temp directory.
8. **Hardware requirements:** None.
9. **Setup:** None beyond the installed guardian script.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_memory_guardian_contract.py -q
    ```
11. **Fixtures:** Synthetic snapshot with strata pids [101, 102] and mtplx pids [201]; `survivors` controls what the post-SIGTERM rescan finds.
12. **Expected behavior:**
    - `target="mtplx"` SIGTERMs only the mtplx pid and never invokes the strata runtime-stop supervisor; the `memory-ceiling-last.json` record documents the strata pids that stayed up.
    - `target="all"` SIGTERMs every engine pid.
    - Supervisor `TimeoutExpired` and `OSError` are logged (`supervisor stop timed out` / `supervisor stop failed`) and never propagate; the SIGTERM phase still completed.
    - Survivors of SIGTERM are escalated to SIGKILL in the rescans; pids that exited are not re-signalled; a targeted mtplx stop never escalates a strata survivor.
13. **Pass/fail:** PASS means the actuator logic is correct on synthetic pids. It does not mean a live engine was cleanly stopped.
14. **Metrics:** Recorded (pid, signal) pairs, supervisor argvs, log lines, and the last-stop record.
15. **Evidence:** pytest summary; recorded kill lists per case.
16. **Cleanup:** None; temp directories only. The stubs are restored in `finally`.
17. **Known failure modes:** The probe replaces `os.kill` on the guardian module, so an unstubbed code path inside `stop_engine` that touches real processes would be caught by an `AttributeError` (first runs failed exactly this way on `subprocess.DEVNULL` and `os.path`) rather than by a stray signal. The rescan stub cannot verify that the supervisor actually releases the Metal arena.
18. **Automation status:** LEVEL 1.
19. **Known limitations:** SIGTERM→SIGKILL timing (1.5 s) is stubbed; the real drain behaviour of the strata runtime supervisor is untested. Live clean-stop observation is Level 3 and not run here.
20. **Last verified:** 2026-11-15 04:55 UTC, 8 passed in this file (4 existed before). The live engine (pid 53687, running 4 h 43 m) was confirmed still running after the run — the probe's fake `os.kill` intercepted every signal.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-15 04:55 | stop_engine targeting + escalation + supervisor resilience | PASS | Four new tests. First run SIGKILL-logged the live engine pid because the post-SIGTERM rescan was real — fixed by stubbing `scan_processes` and `sleep`, not by removing the assertion. Escalation semantics (SIGTERM survivors only, never dead pids, never a strata survivor under a mtplx-targeted stop) now pinned. |
