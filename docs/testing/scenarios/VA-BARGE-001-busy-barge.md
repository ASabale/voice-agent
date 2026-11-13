# VA-BARGE-001 — Busy Whisper keeps one barge clip

1. **ID:** VA-BARGE-001
2. **Name:** A full Whisper queue keeps the interruption
3. **Objective:** A barge clip that cannot enter the one-slot Whisper queue is kept, and playback is not resumed just because the queue was full.
4. **Failure investigated:** `controller.log` records `whisper busy; skipped TTS barge clip`, including 2026-11-13 00:15:09 and a run on 2026-11-11 from 22:35 through 22:40.
5. **Preconditions:** Repository checkout and the project virtualenv.
6. **Required application versions:** None.
7. **Required services:** None. Do not start Whisper, Handy, VoiceBox, or afplay.
8. **Hardware requirements:** None.
9. **Setup:** From the repository root.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_idle_whisper.py -q
    ```
11. **Fixtures:** Four-sample float arrays built in the test. No recorded speech.
12. **Expected behavior:** With the one-slot queue already full and no job pending, the first barge clip is held and a second replaces it. Releasing before the worker takes the queued job leaves the held clip in place. After that job is taken, release queues the newer clip. Its prompt is `two`. The test does not send a signal.
13. **Pass/fail:** PASS means `test_a_full_whisper_queue_holds_the_newest_barge_clip`. It does not mean a spoken interruption was heard on the laptop.
14. **Metrics:** None.
15. **Evidence:** The pytest summary. The log lines stay in `controller.log`.
16. **Cleanup:** None.
17. **Known failure modes:** The running controller still drops the clip and resumes playback until that process restarts. Two barge clips during one full queue keep only the newer one.
18. **Automation status:** LEVEL 4.
19. **Known limitations:** The test does not load Whisper, open the microphone, or pause `afplay`.
20. **Last verified:** 2026-11-13, working tree on `5540a03`. `pytest tests/ -q` — 96 passed.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-11 22:35 and 2026-11-13 00:15 | running controller | FAIL | Barge clips were skipped while the Whisper queue was full. |
| 2026-11-13 | working tree after `5540a03` | PASS | Unit test only. The controller was not restarted. |
