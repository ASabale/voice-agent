# VA-LOG-003 — Log rotation

1. **ID:** VA-LOG-003
2. **Name:** Logs keep one backup after 1 MiB
3. **Objective:** A long-running voice log does not grow without a bound, and one previous file is kept.
4. **Failure investigated:** On 2026-11-13 `controller.log` was 3.1 MiB and `speech.log` was 1.5 MiB. Nothing rotated them.
5. **Preconditions:** Repository checkout, the project virtualenv, and Node.
6. **Required application versions:** None.
7. **Required services:** None. Do not start or stop the controller.
8. **Hardware requirements:** None.
9. **Setup:** From the repository root. The tests use temporary files. Do not pass the live log paths.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_speech_tier.py -q
    node --experimental-strip-types --test tests/speech-queue.test.ts
    ```
11. **Fixtures:** Temporary files containing `old-line` and `next-line`. No recorded speech.
12. **Expected behavior:** A file larger than the limit is renamed to the same name plus `.1`. A second rotation replaces that backup. A file under the limit is left in place. A missing file returns false. The limit used by the programs is 1 MiB. The tests pass a smaller limit.
13. **Pass/fail:** PASS means those two tests. It does not mean the live files were rotated.
14. **Metrics:** File size against 1,048,576 bytes.
15. **Evidence:** The pytest and node summaries.
16. **Cleanup:** The tests delete their temporary directories.
17. **Known failure modes:** The running controller holds `controller.log` open, so renaming that path now would detach the process from the path. Rotation runs the next time a controller starts. The running extension rotates `speech.log` only after that session reloads.
18. **Automation status:** LEVEL 4.
19. **Known limitations:** Only one backup is kept. `controller.log` still quotes transcripts.
20. **Last verified:** 2026-11-13, working tree on `5540a03`. `pytest tests/ -q` — 97 passed. The three Node test files passed 54.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-13 | running processes | FAIL | Logs were 3.1 MiB and 1.5 MiB with no backup. |
| 2026-11-13 | working tree after `5540a03` | PASS | Unit tests on temporary files. Live logs were not renamed. |
