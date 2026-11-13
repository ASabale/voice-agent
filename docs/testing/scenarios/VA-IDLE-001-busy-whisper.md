# VA-IDLE-001 — Busy Whisper keeps one idle clip

1. **ID:** VA-IDLE-001
2. **Name:** Busy Whisper keeps the newest idle clip
3. **Objective:** An idle utterance that finishes while Whisper is busy is queued later, not discarded.
4. **Failure investigated:** `controller.log` recorded `whisper busy; skipped idle utterance` at 12:43:37, 12:52:42, 13:09:13, 13:09:15, and 13:09:23 on 2026-11-13.
5. **Preconditions:** Repository checkout and the project virtualenv.
6. **Required application versions:** None.
7. **Required services:** None. Do not start Whisper, Handy, or VoiceBox.
8. **Hardware requirements:** None.
9. **Setup:** From the repository root.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_idle_whisper.py -q
    ```
11. **Fixtures:** Eight-sample float arrays built in the test. No recorded speech.
12. **Expected behavior:** While a partial job is still in the one-slot queue, the first idle clip is held and a second idle clip replaces it. Releasing before the worker takes the partial job leaves the held clip in place. After that job is taken and its result is collected, release queues the newer clip. The prompt on that job is `two`. Setting state to `DICTATING` and releasing drops the held clip and leaves the queue empty.
13. **Pass/fail:** PASS means those two tests. It does not mean a spoken wake was recovered on the laptop.
14. **Metrics:** None.
15. **Evidence:** The pytest summary. The five log lines stay in `controller.log`.
16. **Cleanup:** None.
17. **Known failure modes:** The running controller still drops the clip until that process restarts. Two idle clips during one busy job keep only the newer one.
18. **Automation status:** LEVEL 4.
19. **Known limitations:** The test does not load the Whisper model and does not open the microphone.
20. **Last verified:** 2026-11-13, working tree on `5540a03`. `pytest tests/ -q` — 95 passed.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-13 12:43 to 13:09 | running controller | FAIL | Five idle clips were skipped while Whisper was busy. |
| 2026-11-13 | working tree after `5540a03` | PASS | Unit test only. The controller was not restarted. |
