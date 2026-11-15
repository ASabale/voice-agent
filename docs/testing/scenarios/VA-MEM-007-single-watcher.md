# VA-MEM-007 — exactly one watcher may own the kill loop

1. **ID:** VA-MEM-007
2. **Name:** The guardian's `watch` loop claims a single-instance lock; a duplicate instance exits instead of running a second kill loop
3. **Objective:** `watch()` in `~/.local/bin/strata-memory-ceiling` must be owned by exactly one process. Kill decisions, voice-shed rate limits, and the last-stop record all assume a single strike counter.
4. **Failure investigated:** The live field state (verified 2026-11-15 05:20 UTC) had two watchers running the identical loop: pid 38389 started manually (parent 96779, Homebrew Python 3.14) and pid 38402 started by launchd (`com.akshay.strata-memory-ceiling.plist`, KeepAlive, system Python 3.9), both up 16 h 23 m at the time of the check. Two watchers mean two independent 6-sample strike counters (each counts its own samples), two independent 60 s voice-shed timers (up to two `/models/unload` POSTs per minute), and duplicate STOP records in `memory-ceiling-last.json` — last-writer-wins, so the forensic record shows whichever watcher fired last, not the one that made the decision. No crash risk: `stop_engine` swallows `OSError` on already-dead pids, so the second stop attempt is a no-op.
5. **Preconditions:** macOS with the guardian installed. Venv for pytest.
6. **Required application versions:** Python 3.9+ (the file uses `from __future__ import annotations`; launchd runs the system 3.9).
7. **Required services:** None. Lock files are written to a temp directory in the tests; the live probe writes only under the temp dir.
8. **Hardware requirements:** None.
9. **Setup:** None.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_memory_guardian_contract.py -q
    ```
11. **Fixtures:** Temp lock file; a short-lived `sleep 30` child as the "live other watcher"; pid `999999999` as the dead owner.
12. **Expected behavior:**
    - First claim creates `watcher.lock` with the claimant's pid and returns `None` (proceed).
    - A second instance with a live pid in the lock returns that pid and `watch()` logs `duplicate watcher pid=...` and returns 0 before entering the sampling loop.
    - A lock held by a dead pid is replaced; the same pid re-claiming its own lock is fine (restart of the same process).
13. **Pass/fail:** PASS means the lock semantics are correct. It does NOT mean the live duplicate (38389/38402) is gone — the running instances predate the guard and hold no lock.
14. **Metrics:** Return values of `_claim_watcher_slot()`, lock file contents, log lines from `watch()`.
15. **Evidence:** pytest summary (10 passed in the contract file); dry-run probe output: claim1 None, claim2 None (same pid), claim3 None with lock rewritten after dead owner, claim4 returns 38389.
16. **Cleanup:** Temp directories only; the `sleep` children are killed in the tests.
17. **Known failure modes:** If the lock file is unreadable (empty/corrupt), the claimant overwrites it and proceeds — a corrupt lock cannot permanently disable the guardian. `O_EXCL` makes simultaneous starters mutually exclusive; only the pathological same-instant race could confuse ownership, and it is harmless (two watchers with identical decisions).
18. **Automation status:** LEVEL 1.
19. **Known limitations:** The guard applies only at process start. The two 16-hour-old instances must be consolidated by the owner: retire the manual watcher (`kill 38389`) and let launchd's KeepAlive unit own the loop. Until then, launchd restarts of 38402 (after a crash) will exit immediately and retry every ThrottleInterval (10 s) while 38389 lives — bounded churn, logged as `duplicate watcher`.
20. **Last verified:** 2026-11-15 05:25 UTC, 10 passed in `tests/test_memory_guardian_contract.py` (2 new tests); full suite 287 passed.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-15 05:25 | `_claim_watcher_slot()` + early exit in `watch()` | PASS | Discovered by inspecting live processes: manual 38389 + launchd 38402, same start time 16:23:38 local. Duplicate watchers were flagged in VA-MEM-004's limitations but never root-caused; the plist confirms launchd owns one instance and KeepAlive guarantees it returns after a crash. |
