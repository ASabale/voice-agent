# VA-LOG-002 — Speech log omits the sentence

1. **ID:** VA-LOG-002
2. **Name:** Speech log stores length, not the sentence
3. **Objective:** A TTS log line can be debugged without storing the words.
4. **Failure investigated:** On 2026-11-13, with VoiceBox not listening, `speech.log` appended `event: failed` records that included the sentence.
5. **Preconditions:** Repository checkout. Node on `PATH`.
6. **Required application versions:** None.
7. **Required services:** None. Do not start VoiceBox.
8. **Hardware requirements:** None.
9. **Setup:** From the repository root. Do not set `OMP_VOICE_LOG_TEXT` unless the include path is what you are checking.
10. **Execution:**
    ```sh
    node --experimental-strip-types --test tests/speech-queue.test.ts
    ```
11. **Fixtures:** The sentence `The weather is fine today.` is built in the test. It is not a recording.
12. **Expected behavior:** `speechLogRecord(event, sentence, extra, false)` has `chars` equal to the sentence length, `event`, and `reason`, and no `text` field. The same call with `true` sets `text` to the sentence. The default follows `OMP_VOICE_LOG_TEXT=1`.
13. **Pass/fail:** PASS means that test. It does not mean the running extension has reloaded.
14. **Metrics:** `chars`.
15. **Evidence:** The node test summary.
16. **Cleanup:** None. The test does not append to `speech.log`.
17. **Known failure modes:** The running extension still writes the sentence until that OMP session reloads. `controller.log` still quotes transcripts because the spoken checkpoint reads those lines.
18. **Automation status:** LEVEL 4.
19. **Known limitations:** This does not rotate logs and does not redact `controller.log`.
20. **Last verified:** 2026-11-13, working tree on `5540a03`. The three Node test files passed 52.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-13 | running extension | FAIL | Failed TTS records included the sentence. |
| 2026-11-13 | working tree after `5540a03` | PASS | Unit test only. OMP was not restarted. |
