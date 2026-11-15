# VA-SOAK-005 — The controller's memory does not drift across repeated conversations

1. **ID:** VA-SOAK-005
2. **User-facing failure prevented:** A controller that slowly accumulates memory across turns eventually triggers the guardian's kill rules or exhausts the machine mid-conversation, killing hands-free use at an arbitrary point in a long session.
3. **Preconditions:** Live controller owning the microphone (pid 38298 at run time); VoiceBox healthy on 17493; no user speech; probe owns its own isolated omp session.
4. **Exact reproduction command:** `~/.local/share/omp-voice/venv/bin/python scripts/run_soak_sessions_probe.py` (four prompts, controller RSS sampled at every turn boundary plus a 5-sample median 30 s after the session exits).
5. **Expected behavior:** across four consecutive conversations in one controller lifetime, controller RSS returns to within 20 MB of its entry value once the session exits and playback drains; no per-turn peak exceeds the baseline by 300 MB; all other soak invariants hold (4 plays, 4 distinct afplay pids, render connect/disconnect each turn, zero wake lines, zero failed speech, IDLE, slot count stable, registry entry present).
6. **Actual behavior:** PASS. Baseline 157.1 MB; per-turn peaks 254.2 / 76.6 / 137.3 / 283.1 MB; post-exit median 173.8 MB (+16.7 MB over baseline). Four turns played, four distinct afplay pids, nine clips generated, zero wake lines, zero failed speech, final IDLE, render false, mic_dropped 0, mic_invalid 0, slot dir stable at 2 entries, controller alive.
7. **Evidence:** `.local/voice-agent/runs/VA-SOAK-005-LIVE.json`.
8. **Level:** LEVEL 3 (live services, real playback, real controller; no microphone input exercised).
9. **What was reproduced first:** the hypothesized leak did not exist. The first probe version used a naive `final_rss - baseline` gate and reported FAIL at 92.6 MB "growth"; the 1 s-resolution trace probe (`.local/voice-agent/probes/rss_trace_probe.py`, run output in `.local/voice-agent/runs/rss-trace.json`) showed RSS swinging between ~142 and ~356 MB *within a single turn* while the controller is otherwise idle. That is macOS page residency churn under the resident ~46 GiB model, not controller accumulation.
10. **Root cause of the false alarm:** `ps` RSS is not a stable leak metric on a machine under the guardian's steady-state pressure; per-frame numpy churn in the wake/VAD path plus system page compression moves resident pages in and out. The stable signals are (a) the median RSS after all sessions exit and playback drains, and (b) a peak ceiling.
11. **Fix:** acceptance criteria in the probe changed from "final minus baseline < 20" to "post-exit median within 20 MB of baseline AND every turn peak within 300 MB of baseline", with the per-turn boundary samples and the 1 s trace recorded as raw evidence.
12. **Tests run:** the probe itself (four live runs: first two FAIL due to the metric bug, then PASS after the gate fix). `pytest tests/test_playback_state.py -q` unaffected (27 passed in the previous iteration); no unit code changed in this iteration.
13. **Result:** PASS.
14. **Latencies measured:** playback latencies 7.91 / 11.87 / 8.54 / 25.58 s (model contention inflates the tail); clip lengths 1.84–14.48 s.
15. **Boundary behavior:** the 300 MB peak ceiling is a guard, not an observed limit — peaks never exceeded baseline + 126 MB.
16. **Cleanup:** probe terminates its omp session and closes its pty master; evidence JSON stays in `.local/voice-agent/runs/`.
17. **Automation status:** LEVEL 3 live probe, rerunnable any time; no microphone opened.
18. **Known limitations:** `ps` RSS undercounts/overcounts residency under heavy system pressure; a true long-run leak study needs several soak cycles over hours (Level 5 proper). The controller itself was never restarted, so this measures the pid that has already run two soak cycles plus this one.
19. **Last verified:** 2026-11-15 00:40 UTC, controller pid 38298, working tree on `4aa6a54` plus uncommitted fixes.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-14 23:55 | first RSS probe version | FAIL (metric bug) | 92.6 MB "growth" vs 258 MB baseline; 1 s trace showed ±200 MB intra-turn swings with render idle — residency churn, not accumulation |
| 2026-11-15 00:40 | post-exit median + peak ceiling gates | PASS (Level 3) | post-exit median 173.8 MB vs baseline 157.1 MB; max turn peak 283.1 MB, within the 300 MB ceiling |
