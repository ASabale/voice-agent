# VA-TTS-015 — Guardian staleness

1. **ID:** VA-TTS-015
2. **Name:** A dead guardian's last pressure file must not silence the voice path forever
3. **Objective:** `readMemoryPressure` treats `pressure.json` as no-pressure when its `at` timestamp is older than 30 s, so a guardian that exits mid-shed cannot freeze speech deferral.
4. **Failure investigated:** The guardian writes `at` on every poll (≤ 2 s cadence while alive; worst observed gap ~5 s on the sleep branches). The extension ignored `at` entirely. If the watcher process exits while `shedVoice: true` is written, the extension would defer every sentence: each deferral waits 8 s, retries every 5 s, and expires after 120 s — the voice path goes silent on a machine nobody is monitoring, and deferred sentences are eventually dropped.
5. **Preconditions:** Repository checkout. Node on `PATH`.
6. **Required application versions:** None.
7. **Required services:** None. VoiceBox and the guardian are not started.
8. **Hardware requirements:** None.
9. **Setup:** From the repository root. Tests point `OMP_VOICE_PRESSURE_FILE` at temporary files with crafted `at` values.
10. **Execution:**
    ```sh
    node --experimental-strip-types --test tests/memory-pressure.test.ts
    ```
11. **Fixtures:** Temporary JSON files: `at` 60 s ago with `shedVoice: true`; `at` 10 s ago with `shedVoice: true`; no `at` field.
12. **Expected behavior:** A file older than `PRESSURE_STALE_MS` (30000 ms) returns `undefined` from `readMemoryPressure`, and `waitForHeadroom` returns `ok: true` with `waitedMs: 0`. A file inside the window still defers. A file without a timestamp is treated as fresh.
13. **Pass/fail:** PASS means the staleness rule behaves on synthetic files. It does not mean a real guardian crash was observed and survived.
14. **Metrics:** None.
15. **Evidence:** Node test summary; three named tests: "a stale pressure file left by a dead guardian never defers speech", "pressure inside the staleness window is still respected", "a pressure file with no timestamp is treated as fresh, not stale".
16. **Cleanup:** Tests remove their temp directories.
17. **Known failure modes:** Clock skew between the guardian (UTC `strftime`) and the extension (`Date.now`) is unmeasured; a 30 s window is far larger than any plausible skew. If the guardian is alive but wedged between long sleeps, the file can legitimately be ~5 s old — still inside the window.
18. **Automation status:** LEVEL 1.
19. **Known limitations:** No test kills a live guardian and observes the extension recovering; the contract is verified only against synthetic files. Live end-to-end deferral behavior remains blocked on VoiceBox.
20. **Last verified:** 2026-11-14 16:57 UTC. `node --experimental-strip-types --test tests/memory-pressure.test.ts` plus the other three suites: 80 passed, 0 failed.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-14 16:57 | `readMemoryPressure` parses `at`; stale file returns `undefined` | PASS | Unit level. The pre-existing guardian-file test had hard-coded an old timestamp and was updated to a fresh one; staleness itself is pinned by its own tests. |
