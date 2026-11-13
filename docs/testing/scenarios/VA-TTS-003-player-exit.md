# VA-TTS-003 — Player exit

1. **ID:** VA-TTS-003
2. **Name:** A player error is not spoken
3. **Objective:** A chunk is marked spoken only when afplay actually started.
4. **Failure investigated:** `play` called `commitSpoken` after every close, including a non-zero exit and a spawn error.
5. **Preconditions:** Repository checkout. Node on `PATH`.
6. **Required application versions:** None.
7. **Required services:** None. Do not start VoiceBox or afplay.
8. **Hardware requirements:** None.
9. **Setup:** From the repository root.
10. **Execution:**
    ```sh
    node --experimental-strip-types --test tests/speech-queue.test.ts
    ```
11. **Fixtures:** None. The test calls `playbackHeard` with exit codes and a signal name.
12. **Expected behavior:** Exit code 0 with no signal is heard. Exit code 1 with no signal is not. `SIGKILL` is heard, because the process had started. A spawn error is not, even if the code is empty.
13. **Pass/fail:** PASS means `a player error is not heard and a kill signal is`. It does not mean afplay ran.
14. **Metrics:** None.
15. **Evidence:** The node test summary.
16. **Cleanup:** None.
17. **Known failure modes:** The running extension still commits every close until that OMP session reloads. A 45 s watchdog kill is counted as started so the chunk is not spoken again.
18. **Automation status:** LEVEL 4.
19. **Known limitations:** The test does not spawn afplay. Today's log had no afplay failure. VoiceBox was down, so playback was not reached.
20. **Last verified:** 2026-11-13, working tree on `5540a03`. The three Node test files passed 55.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-13 | running extension | FAIL | Every afplay close committed the chunk. |
| 2026-11-13 | working tree after `5540a03` | PASS | Unit test only. OMP was not restarted. |
