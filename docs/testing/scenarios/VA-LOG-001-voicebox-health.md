# VA-LOG-001 — VoiceBox health retry

1. **ID:** VA-LOG-001
2. **Name:** VoiceBox health is not a per-frame retry
3. **Objective:** A refused VoiceBox health check waits 5 seconds and does not change the Handy model flag.
4. **Failure investigated:** On 2026-11-13 from 12:32:16 to 12:32:22, `controller.log` repeated `VoiceBox health unread; speech tier not changed` on idle microphone frames.
5. **Preconditions:** Repository checkout and the project virtualenv. VoiceBox must not be required.
6. **Required application versions:** None.
7. **Required services:** None. Do not start VoiceBox or Handy.
8. **Hardware requirements:** None.
9. **Setup:** From the repository root. The test replaces the health and Handy functions, so it does not read the user's Handy settings.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_speech_tier.py -q
    ```
11. **Fixtures:** None. The health function returns failure, then success, inside the test.
12. **Expected behavior:** With Strata marked loaded, one failure calls health once. Calls at 80 ms and at 4.9 s do not call it again. The call at 5.0 s does. The Handy flag stays true. After a success, the next frame does not call health. Changing the Strata flag calls health once.
13. **Pass/fail:** PASS means those call counts. It does not mean VoiceBox loaded a model.
14. **Metrics:** Health calls and Handy calls.
15. **Evidence:** The pytest summary. The original storm is in `controller.log` at 12:32, and that file is not copied here.
16. **Cleanup:** None. The test clears its own flags.
17. **Known failure modes:** The running controller still has the per-frame check until that process restarts. A 2 s health timeout can stall one frame on a dead route that does not refuse immediately.
18. **Automation status:** LEVEL 4.
19. **Known limitations:** The test does not open port 17493 and does not check which TTS model is loaded.
20. **Last verified:** 2026-11-13, working tree on `5540a03`. `pytest tests/test_speech_tier.py -q` passed as part of `pytest tests/ -q` — 93 passed.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-13 12:32 | running controller | FAIL | Health line repeated on idle frames for about 6 s. |
| 2026-11-13 | working tree after `5540a03` | PASS | Unit test only. Controllers were not restarted. |
