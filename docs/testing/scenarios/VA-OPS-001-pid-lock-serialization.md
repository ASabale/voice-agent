# VA-OPS-001 — the PID-file flock serializes controller starts, and an unclean death releases it

1. **ID:** VA-OPS-001
2. **Name:** `_open_pid_lock` refuses a second start while the daemon holds the lock, and the kernel releases the flock when the daemon dies — cleanly or by SIGKILL
3. **Objective:** The controller has no supervisor. Any future crash-recovery unit (launchd KeepAlive, or a user typing `omp-voice-controller start` twice) is only safe if a second process can never get past the PID-file lock while a daemon is alive, and can get past it the instant the daemon is gone. This is the precondition for every Level 5 restart row.
4. **Failure investigated:** The guard exists in `bin/omp-voice-controller` (`_open_pid_lock`, `cmd_start_bg`, `cmd_stop`) but had zero test coverage — no row in the catalogue had ever exercised it. Live state shows the controller pid 38298 has run 19 h without a crash (no `omp-voice-controller` report in `~/Library/Logs/DiagnosticReports`; the four `Python-*.ips` reports are children of `omp`, not the controller), so the guard has never been exercised in production either.
5. **Preconditions:** macOS. Venv.
6. **Required application versions:** Python 3.12+ (the controller is imported as a module).
7. **Required services:** None. The microphone is never opened; spawns are recorded by a stub `Popen`.
8. **Hardware requirements:** None.
9. **Setup:** None. Lock holders are synthetic subprocesses in a temp state dir.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_pid_lock.py -q
    ```
11. **Fixtures:** a subprocess holding `fcntl.LOCK_EX` on the temp PID file; a child spawned with `pass_fds` (the exact `cmd_start_bg` inheritance path) holding the inherited fd.
12. **Expected behavior:**
    - Lock held → `cmd_start_bg` prints "already running", returns 0, and `Popen` is never called — no second mic owner is ever spawned.
    - Holder SIGKILLed → the kernel releases the flock, the stale pid in the file is ignored (`os.kill(dead_pid, 0)` raises `OSError`), and `cmd_start_bg` spawns the `run` command.
    - A daemon that inherits the locked fd keeps it serialized while alive; the probe succeeds immediately after it dies.
    - `cmd_stop` against a dead pid file prints "not running" and unlinks the stale file.
13. **Pass/fail:** PASS means restart-after-crash is mechanically safe. It does not mean the live installation auto-recovers — no supervisor exists yet (VA-OPS-002, blocked on owner approval).
14. **Metrics:** none needed; correctness is the assertion.
15. **Evidence:** pytest summary: 4 passed in 0.74 s. Full Python suite: **294 passed** (was 290). Node suite unchanged (110 passed; no extension code touched).
16. **Cleanup:** temp dirs; holder/child processes killed and waited in `finally`.
17. **Known failure modes:** flock is advisory — a process that never calls `_open_pid_lock` (a raw `run` invocation, which `main` routes through the lock) is not prevented. The kernel-release timing is polled up to 3 s; a holder that dies but leaves the fd inherited by a third process keeps the lock — which is correct behavior, not a leak.
18. **Automation status:** LEVEL 1.
19. **Known limitations:** The real daemon's lifetime hold goes through `OMP_VOICE_PID_LOCK_FD`; the test exercises the same fd-inheritance mechanism, not the full 19-hour process. Level 5 proof still requires a real crash or a human kill.
20. **Last verified:** 2026-11-15 06:05 UTC, 4 tests in `tests/test_pid_lock.py`; full suite 294 passed.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-15 06:05 | first `test_pid_lock.py` | PASS | Guard existed since the daemon-lock commit but was never tested. The stale-pid path (`os.kill` probe raising `OSError`) and the kernel flock release on SIGKILL are now pinned. |
