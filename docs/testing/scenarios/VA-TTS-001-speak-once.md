# VA-TTS-001 — Speak each chunk once

1. **ID:** VA-TTS-001
2. **Name:** Speak each chunk once
3. **Objective:** A streaming reply does not play the same chunk twice, a short sentence inside an older chunk is not dropped, a prefix rewrite does not replay the reply, and a new assistant message can say a sentence that the previous message already said.
4. **Failure investigated:** `enqueue` skipped any sentence found with `spokenText.includes`. A prefix that no longer matched cleared `spoken`, `committed`, and `inflight`, then the same push enqueued the reply again.
5. **Preconditions:** Repository checkout. Node on `PATH` (this machine: v26.11.0). No services.
6. **Required application versions:** None.
7. **Required services:** None. Do not start VoiceBox or OMP.
8. **Hardware requirements:** None.
9. **Setup:** From the repository root.
10. **Execution:**
    ```sh
    node --experimental-strip-types --test tests/speech-queue.test.ts
    ```
11. **Fixtures:** None. The cases are in the test file.
12. **Expected behavior:**
    - `isSpokenChunk(["The cat sat. Then he left."], "sat.")` is false.
    - The same text, and the join of consecutive chunks, is true.
    - `queuedAfterRewrite` returns `""` when the spoken head is gone, and the old chunk stays spoken.
    - `isNewReply` is true only when both message ids are non-empty and different. The first id does not count as a new reply.
13. **Pass/fail:** PASS when the command exits 0. There is no speaker result.
14. **Metrics:** None.
15. **Evidence:** The node test summary.
16. **Cleanup:** None.
17. **Known failure modes:** A tool round that copies the parent text under a new message id is treated as a new reply and can speak it again. A tool round that keeps the message id does not. Messages with no `id` never take the new-reply path.
18. **Automation status:** LEVEL 4. The workflow runs this file with the other Node tests.
19. **Known limitations:** Does not generate or play audio. The loaded OMP extension does not change until that session reloads.
20. **Last verified:** 2026-11-13, working tree on `5540a03`. `node --experimental-strip-types --test tests/speech-queue.test.ts tests/match_command.test.ts` — 36 passed.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-13 before the fix | `5540a03` | FAIL | Substring skip, and a prefix miss cleared spoken state. |
| 2026-11-13 | working tree after `5540a03` | PASS | Unit tests only. No audio. |
