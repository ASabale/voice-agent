# VA-LOG-003 — Log rotation

1. **ID:** VA-LOG-003
2. **Name:** Logs keep one backup after 1 MiB, including while the process is running
3. **Objective:** A long-running voice log does not grow without a bound, and one previous file is kept.
4. **Failure investigated:** On 2026-11-13 `controller.log` was 3.1 MiB and `speech.log` was 1.5 MiB with nothing rotating them. On 2026-11-14 the fix was still incomplete: `rotate_log` had exactly one call site, in the `start` command before spawning, so a daemon that never restarts rotated nothing — `controller.log` reached 29.6 MiB after one day of pid 64238.
5. **Preconditions:** Repository checkout, the project virtualenv, and Node.
6. **Required application versions:** None.
7. **Required services:** None. Do not start or stop the controller.
8. **Hardware requirements:** None.
9. **Setup:** From the repository root. The tests use temporary files. Do not pass the live log paths.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_speech_tier.py tests/test_log_rotation_runtime.py -q
    node --experimental-strip-types --test tests/speech-queue.test.ts
    ```
11. **Fixtures:** Temporary files. The runtime test duplicates fd 1 onto a temp log file, drives `_rotate_stdout_log` past the limit, and restores fd 1 afterwards. No recorded speech.
12. **Expected behavior:**
    - `rotate_log`: a file larger than the limit is renamed to name plus `.1`; a second rotation replaces the backup; a file under the limit is left in place; a missing file returns false.
    - `_rotate_stdout_log`: when fd 1 is a regular file that is the same inode as `LOG_FILE` and exceeds the limit, the log is moved to `.1`, fd 1 is re-pointed at a fresh empty `controller.log`, and subsequent writes land in the fresh file. When stdout is a terminal, a pipe, or a different file, nothing happens.
13. **Pass/fail:** PASS means these tests. It does not mean the live controller's log was rotated — the fix only applies after the running process loads it.
14. **Metrics:** File size against 1,048,576 bytes.
15. **Evidence:** pytest summaries: `test_log_rotation_runtime.py` 4 passed (rotate-and-repoint, backup replaced on second rotation, foreign stdout untouched, under-limit untouched); `test_speech_tier.py` rotation tests pass; node speech-log rotation test passes.
16. **Cleanup:** The tests delete their temporary directories and restore fd 1.
17. **Known failure modes:** The earlier design accepted that "rotation runs the next time a controller starts"; that is the bug this iteration fixes. The running daemon cannot be fixed by renaming the path it holds open — hence the `dup2` re-point. Only one backup is kept.
18. **Automation status:** LEVEL 1 (the daemon condition — fd 1 held open on the log path — is reproduced on a temp file inside the test process).
19. **Known limitations:** Running pid 64238 was started before this change, so its 29.6 MiB `controller.log` is not rotated until Akshay restarts the controller. `controller.log` still quotes transcripts.
20. **Last verified:** 2026-11-14 11:10 UTC. `pytest tests/ -q` — 236 passed.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-13 | running processes | FAIL | Logs were 3.1 MiB and 1.5 MiB with no backup. |
| 2026-11-13 | working tree after `5540a03` | PASS | Unit tests on temporary files. Live logs were not renamed. |
| 2026-11-14 11:10 | runtime rotation via fd 1 re-point + 4 regression tests | PASS | Level 1. Live pid 64238 still unrotated until restart. |