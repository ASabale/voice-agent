# VA-AUD-002 — Dropped microphone frames

1. **ID:** VA-AUD-002
2. **Name:** Dropped microphone frames
3. **Objective:** When the capture queue is full, the oldest block is dropped, the newest is kept, and the loss is counted. An input overflow is counted separately. Samples are not logged.
4. **Failure investigated:** `on_mic` dropped the oldest block on `queue.Full` and did not count it, so a capture overrun looked like a speech-to-text miss.
5. **Preconditions:** Repository checkout. Python 3.12 venv at `~/.local/share/omp-voice/venv`.
6. **Required application versions:** None.
7. **Required services:** None. Do not start the controller, Handy, or VoiceBox.
8. **Hardware requirements:** None. This test does not open a microphone.
9. **Setup:** From the repository root.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_mic_capture.py -q
    ```
11. **Fixtures:** A `queue.Queue` of max size 1, and a status object with `input_overflow`.
12. **Expected behavior:** The second offer of a full queue returns `(1, 0)` and the queue holds the new block. An overflow status returns `(0, 1)` when the block still fits. `publish_capture_totals` sets `mic_dropped` and `mic_invalid` on the status JSON and leaves `last_action` in place. The file does not contain the block contents.
13. **Pass/fail:** PASS when the command exits 0. There is no hardware result.
14. **Metrics:** `mic_dropped` and `mic_invalid` on `status.json` once the controller that contains this code is the running process.
15. **Evidence:** The pytest summary.
16. **Cleanup:** The test uses `tmp_path`. Do not delete the user's `status.json`.
17. **Known failure modes:** The process that is already running still has the old callback. Its status file will not gain these keys until that process starts again.
18. **Automation status:** LEVEL 4.
19. **Known limitations:** Does not prove a real PortAudio overrun. A dropped frame and a Whisper miss are distinguishable only after the new controller is the one writing `status.json`.
20. **Last verified:** 2026-11-13, working tree on `5540a03`. `pytest tests/ -q` — 73 passed. `pytest tests/test_mic_capture.py -q` is included.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-13 before the fix | `5540a03` | FAIL | Full queue dropped a block and nothing counted it. |
| 2026-11-13 | working tree after `5540a03` | PASS | Unit test. No microphone. |
