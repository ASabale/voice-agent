# VA-TTS-002 — A chunk that never played

1. **ID:** VA-TTS-002
2. **Name:** A failed VoiceBox request is not spoken
3. **Objective:** A sentence that never came back from VoiceBox can be spoken later, without replaying a sentence that was already queued after it.
4. **Failure investigated:** On 2026-11-13 VoiceBox was not listening. `enqueue` stored the chunk before the request, and a missing clip left the chunk in the spoken list.
5. **Preconditions:** Repository checkout. Node on `PATH`.
6. **Required application versions:** None.
7. **Required services:** None. Do not start VoiceBox.
8. **Hardware requirements:** None.
9. **Setup:** From the repository root.
10. **Execution:**
    ```sh
    node --experimental-strip-types --test tests/speech-queue.test.ts
    ```
11. **Fixtures:** The sentences `The file is ready.` and `Open it next.` are built in the test. They are not recordings.
12. **Expected behavior:** Dropping the first chunk leaves the second in the in-flight list and leaves the queue unchanged, because the failed chunk is not the end. The first sentence is not spoken-already. Dropping a queue that is only the failed chunk rewinds it to empty. A chunk that is already committed is not forgotten.
13. **Pass/fail:** PASS means `a chunk that never played is not treated as spoken`. It does not mean the sentence was heard.
14. **Metrics:** None.
15. **Evidence:** The node test summary.
16. **Cleanup:** None.
17. **Known failure modes:** The running extension still keeps the failed chunk until that OMP session reloads. A failed chunk in the middle of the queue is not retried, so the later sentence is not spoken twice.
18. **Automation status:** LEVEL 4.
19. **Known limitations:** The test does not call VoiceBox and does not play audio.
20. **Last verified:** 2026-11-13, working tree on `5540a03`. The three Node test files passed 53.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-13 | running extension | FAIL | A refused request left the chunk in the spoken list. |
| 2026-11-13 | working tree after `5540a03` | PASS | Unit test only. OMP was not restarted. |
