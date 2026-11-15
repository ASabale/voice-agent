# VA-SOAK-003 — Four consecutive conversations in one controller lifetime

1. **ID:** VA-SOAK-003
2. **Name:** Repeated sessions under one long-running controller
3. **Objective:** Four consecutive `omp` sessions' replies play through the real speakers in a single controller lifetime without wake false-positives, slot accumulation, registry leaks, mic frame loss, or speech-generation failures.
4. **Failure investigated:** Level 5 reliability: an installation that runs for hours accumulates session slots, registry entries, and status churn. VA-AEC-007 proved two fixture-fed turns in one controller; nothing proved repeated *real* VoiceBox replies across sessions against the live controller.
5. **Preconditions:** Repository checkout, project virtualenv, VoiceBox listener healthy on 17493, the live controller already running and owning the microphone.
6. **Required application versions:** None beyond the pinned requirements.
7. **Required services:** VoiceBox GUI listener; the live controller. The probe never starts or stops either.
8. **Hardware requirements:** Speakers only. The probe opens no microphone.
9. **Setup:** From the repository root.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python scripts/run_soak_sessions_probe.py
    ```
11. **Fixtures:** None. Each turn submits a two-sentence prompt through the probe session's ephemeral bridge port; VoiceBox generates real speech; `afplay` plays it through the real speakers while the live controller tracks the render reference. No protected pid is signaled; the probe terminates only the session it started.
12. **Expected behavior:** Every prompt produces exactly one generated clip and one `afplay` process. The controller's `status.json` shows `render_connected: true` while each clip plays and false after it ends. No "Wake triggered" line appears in the controller log during the run. No `failed` event appears in `speech.log` after the run start. At the end, after the last clip drains, the controller is IDLE with `mic_dropped: 0` and `mic_invalid: 0`, the session's registry entry is present, and the slot directory holds only live sessions.
13. **Pass/fail:** Four turns played, four clips generated for the session, four distinct afplay pids, render connect+disconnect each turn, zero wake lines, zero failed speech events, final status render false / IDLE / clean mic counters, controller alive, registry entry present.
14. **Metrics:** Per-turn submit-to-playback latency (includes model generation), clip length, echo dB samples during playback, slot-directory count at each turn boundary, wake/failed line counts.
15. **Evidence:** Live run 2026-11-14 23:59 UTC against controller 38298 (never restarted), isolated session pid 418, probe opened no microphone: 4/4 turns played, 4 clips generated for the session, 4 distinct afplay pids, render connected during every clip and disconnected after every clip, 0 "Wake triggered" lines, 0 failed speech events, final status `render_connected: false`, state IDLE, `mic_dropped: 0`, `mic_invalid: 0`, controller alive, registry entry present, slot directory held exactly 2 entries (probe session + main session 2734) at every boundary — no accumulation. Submit-to-playback latencies 14.6 / 14.9 / 20.7 / 35.0 s (single-slot local model shared with the owner's live session). Echo residual sampled per turn: turn 1 −5.7…−7.8 dB, turn 2 −3.3…−11.7, turn 3 −2.4…−13.9 (four 0.0 dB samples — guard-passed blocks, no wake), turn 4 −4.5…−22.8. Evidence JSON: `.local/voice-agent/runs/VA-SOAK-003-LIVE.json`. Earlier run 23:49 UTC (pid 94918) FAILed on two harness bugs: turn 1's reply exceeded the 240 s wait while the owner's session queued on the shared model (all 4 replies generated; nothing lost), and a `timezone` NameError aborted the fixed probe before it wrote evidence. Both fixed; the acceptance criteria were tightened to require 4 generated clips and 4 distinct afplay pids.
16. **Known failure modes:** (a) The single-slot local model is shared with the owner's live session; probe replies can queue behind owner replies, inflating submit-to-playback latency (observed first run: turn 1 exceeded a 240 s wait while owner session 2734 was mid-conversation — a harness window problem, not lost speech: all four replies eventually generated). (b) Turn attribution: if a turn's wait expires, its late reply is attributed to the next turn; the current probe tracks distinct afplay pids to prevent double-counting. (c) `render_connected` is a global projection — if another live session plays concurrently, the final "render false" check can be violated legitimately; the probe drains its own afplay pids before the final read.
17. **Cleanup:** The probe terminates its own omp session on exit. The controller prunes that session's slot on the next read.
18. **Automation status:** LEVEL 3 live probe (real session, real speaker output, real controller; no microphone opened by the probe).
19. **Known limitations:** Not a physical acoustic test — nobody speaks into the microphone, so wake *suppression* is observed but user wake/dictation is not exercised (AEC-REAL-002–005 remain blocked on the owner's voice). Latency figures are contaminated by contention on the single-slot local model whenever the owner's session is active.
20. **Last verified:** 2026-11-14 23:59 UTC, working tree on top of `4aa6a54`.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-14 23:49 | probe v1, live run | FAIL (harness) | Turn 1 timed out at 240 s under model contention; turn attribution shifted; `timezone` NameError aborted run 2 before evidence was written. No product defect observed: all replies generated and played. |
| 2026-11-14 23:59 | probe v2 (420 s windows, afplay-pid attribution, drain-and-settle, JSON speech-log scan) | PASS (Level 3) | 4/4 turns, 4 clips, 4 afplays, zero wake, zero failed speech, clean final status, controller 38298 alive and never restarted. |
