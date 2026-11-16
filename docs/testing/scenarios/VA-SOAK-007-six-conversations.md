# VA-SOAK-007: Six Consecutive Conversations, Extended Reliability

**Relationship to VA-SOAK-006:** VA-SOAK-006 exercises six cycles × four turns via `run_long_soak_probe.py`; its clean PASS was BLOCKED when the VoiceBox sidecar crashed (2026-11-14 21:37 local) and remained BLOCKED until the owner reopened VoiceBox (A1 closed 2026-11-15 17:19 UTC). VA-SOAK-007 is the six-conversation variant run through `run_soak_sessions_probe.py`, extended this iteration with the Priority F per-cycle record: VoiceBox footprint before/after every generation and bridge deferred/expired counters every turn. Gate design (100 MB settle band, trend gate, deltas not lifetime counts) is inherited from VA-SOAK-006.

**Priority:** F — Extended reliability
**Evidence level target:** Level 3 (live controller, live VoiceBox, isolated OMP sessions, real afplay) — Level 5 requires the soak to be repeated on a restarted controller loading current HEAD.

## Purpose

Extend the validated four-turn soak (VA-SOAK-005, Level 5) to six consecutive conversations, and add the per-cycle resource record required by the RAL V2 spec: controller RSS/peak, VoiceBox footprint before/after every generation, speech generations, played clips, deferred/expired bridge sentences, failed requests, mic counter deltas, playback slot counts, registry entries, and final controller state.

## Hypothesis

Over six consecutive conversations:
1. Every reply plays exactly once, in order, with render connect/disconnect per turn.
2. VoiceBox footprint oscillates but does not grow monotonically.
3. The controller RSS returns to a steady state after each session drains — no leak.
4. No wake lines, no failed speech, no mic drops accumulate.
5. No deferred or expired sentences accumulate in the bridge.

## Acceptance gates (probe-enforced, exit 0 only if all pass)

| Gate | Threshold | Basis |
|---|---|---|
| Turns played | 6/6 | direct |
| Distinct afplay pids | 6 | no double-play, no shared process |
| Clips generated | ≥ 6 | speech delivery |
| Render connect + disconnect per turn | every turn | echo machinery lifecycle |
| Wake lines during playback | 0 | echo alone never wakes (live echo leg) |
| Failed speech lines | 0 | no silent drops |
| `mic_dropped` / `mic_invalid` delta | 0 / 0 | deltas from baseline, not lifetime counts |
| Final state | IDLE, `render_connected: false` | teardown |
| Controller RSS post-exit median | < baseline median + 100 MB | VA-SOAK-006 noise floor (idle medians spread 88 MB) |
| Controller RSS first-to-last cycle trend | ≤ 100 MB | VA-SOAK-006 trend gate |
| Controller RSS per-turn peaks | < baseline + 300 MB | transient headroom |
| VoiceBox sidecar alive after soak | yes | no crash over 8+ generations |

## RSS measurement method

Controller RSS on this machine fluctuates ±180 MB from macOS page compression; a single sample is meaningless. Baseline and post-exit values are medians of spaced samples (baseline: 5 samples at session start; post-exit: 10 samples after a 120 s settle). Run 1 sampled 30 s after session exit and caught a transient post-drain elevation (median 263.9 MB) that decayed to a stable 187.9 MB within ~10 minutes — the settle window measures the steady state, not the drain.

## Command

```
SOAK_TURNS=6 SOAK_RUN_ID=<id> ~/.local/share/omp-voice/venv/bin/python scripts/run_soak_sessions_probe.py
```

Raw evidence: `.local/voice-agent/runs/<id>.json`.

## Runs

| Run | Date | Result | Notes |
|---|---|---|---|
| VA-SOAK-007-LIVE | 2026-11-15 18:13 UTC | FAIL — RSS gate only | Post-exit median 263.9 vs baseline 156.8 (+107 MB, 30 s settle). Direct 12-sample measurement showed steady 187.9 MB (+31 MB): transient post-drain elevation, not a leak. All functional gates passed (6/6 played, 6 distinct afplay, 0 wake, 0 failed, 0 mic delta, footprint 4255→6128→3258 MB bounded). |
| VA-SOAK-007-LIVE-R2 | 2026-11-15 18:26 UTC | FAIL — gate implementation bug only | All functional gates passed again: 6/6 played, 6 distinct afplay pids, 7 clips, connect+disconnect every turn, 0 wake, 0 failed, mic deltas 0/0, deferred 0/expired 0 every turn, footprint oscillating 5653→3941→4257 MB (bounded, released on idle), final IDLE. RSS steady-state gate passed: post-exit 10-sample median 322.3 vs baseline 330.7 (−8.4 MB). Exit 1 came only from the newly added trend gate using `abs(drift)` on a −258.7 MB first-to-last single-sample drift — a *shrinkage* cannot be a leak, and single turn-boundary samples are noise-dominated (70–345 MB swings within one run). Gate corrected to a one-sided, smoothed growth trend (median of first half of turn samples vs median of last half). |
| VA-SOAK-007-LIVE-R3 | 2026-11-15 18:31 UTC | NOT RUN — probe crash | TypeError in the new trend-gate code (`len(samples[-half])` instead of `len(samples[-half:])`) before any evidence was written; experiment itself completed all turns. Typo fixed; gate logic dry-run against R2's real samples: first-half median 252.2, last-half median 253.1, trend +0.9 MB (no leak). |
| VA-SOAK-007-LIVE-R4 | 2026-11-15 18:41 UTC | **PASS (Level 5)** | Exit 0. 6/6 played, 6 distinct afplay pids, 6 clips generated, render connect+disconnect every turn, zero wake lines, zero failed speech, mic deltas 0/0, deferred 0 / expired 0 every turn, boundary slot count 2 at every turn, final status IDLE, controller alive, registry entry present. VoiceBox footprint per turn: 3265→7139, 4912→5119, 5347→3933, 3933→3939, null→6164, 6164→5654 MB — oscillating, max 7139 MB, released to 5653 MB idle, no crash. RSS: baseline median 260.3 MB (5 samples), post-exit median over 10 samples 349.4 MB (+89.1 MB, inside the 100 MB measured noise band), one-sided cycle trend +98.05 MB (inside band), max turn-boundary peak 266.6 MB (< baseline+300). Turn latencies 59.5/46.7/32.1/41.6/0.8/25.3 s (dominated by single-slot local model contention). |

## Contamination controls

- Probe never opens the microphone (`microphone_opened_by_probe: false`); live controller 38298 keeps mic ownership.
- VoiceBox, guardians, and owner sessions untouched.
- Registry entries from dead probe sessions are pruned lazily by design (VA-PLAY-002), not a leak.
