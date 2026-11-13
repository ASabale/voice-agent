# VA-TTS-004 — VoiceBox hold

1. **ID:** VA-TTS-004
2. **Name:** A refused VoiceBox is not called again for 5 seconds
3. **Objective:** A closed VoiceBox port does not get a new connection for every sentence.
4. **Failure investigated:** At 19:22 on 2026-11-13 `speech.log` recorded 14 `failed` lines with `ECONNREFUSED`. Four of them fell between 19:22:06 and 19:22:07.
5. **Preconditions:** Repository checkout. Node on `PATH`.
6. **Required application versions:** None.
7. **Required services:** None. Do not start VoiceBox.
8. **Hardware requirements:** None.
9. **Setup:** From the repository root.
10. **Execution:**
    ```sh
    node --experimental-strip-types --test tests/speech-queue.test.ts
    ```
11. **Fixtures:** None. The test calls `refusalHold` and `isConnectionRefusal`.
12. **Expected behavior:** A time before the retry instant is held. A time equal to the retry instant is not. `ECONNREFUSED` is a refusal, including when it is the error cause. `http 500` is not a refusal. The hold used by `generate` is 5 seconds.
13. **Pass/fail:** PASS means `a refused VoiceBox holds the next request until the retry time`. It does not mean a socket was opened.
14. **Metrics:** None.
15. **Evidence:** The node test summary and the 19:22 lines in `speech.log`.
16. **Cleanup:** None.
17. **Known failure modes:** The running extension still connects for every sentence until that OMP session reloads. A held sentence is not marked spoken. A later sentence after the hold can be requested again.
18. **Automation status:** LEVEL 4.
19. **Known limitations:** The test does not call port 17493. Sentences that arrive during the hold are not saved for a later replay.
20. **Last verified:** 2026-11-13, working tree on `96cee6e`. The three Node test files passed 56.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-13 19:22 | running extension | FAIL | Fourteen refusals in one minute, four in one second. |
| 2026-11-13 | working tree after `96cee6e` | PASS | Unit test only. OMP was not restarted. |
