# VA-SOAK-005 — Four consecutive conversations in one controller life

**Level 5 — extended reliability.** One isolated `omp -p` session (pid 82233, bridge port 59535, discovered from the registry, not assumed) sends four prompts through the live VoiceBox (63081); four distinct real `afplay` processes play the replies through the speakers while the live controller (38298, never restarted, mic owned but never opened by the probe) tracks the render reference and suppresses wake on the echo. Nobody speaks.

## Acceptance (as coded in `scripts/run_soak_sessions_probe.py`)

1. All 4 turns play; 4 distinct afplay pids; ≥4 generated clips for the session.
2. Every turn: render reference connects during playback and disconnects after.
3. Zero wake lines in the controller log for the run window.
4. Zero `failed` speech events for the window.
5. Controller alive, final state IDLE, `render_connected: false`.
6. Mic counter **deltas** zero (baseline 34/0 captured before the run; lifetime counts are not the gate).
7. Post-drain controller RSS median within 100 MB of the pre-run median; per-turn peak within 300 MB of baseline.

## Result — PASS, 2026-11-15 18:02 UTC

- Turns played 4/4; playback latency 52.6 s (first turn, model queue) then 27.1/25.6/27.7 s — dominated by the single-slot local engine, not the voice path.
- Render connect→disconnect observed for all four turns; echo samples logged during each (`aec_echo_db` −0.1 to −5.3 dB, one window +0.5 dB — see limitations).
- Wake lines: 0. Failed speech: 0. Mic delta: 0/0. Final state IDLE, controller alive, registry entry present.
- RSS: baseline median 350.3 MB → post-drain median 353.0 MB (+2.7 MB); peak 179.6 MB — no growth beyond noise. Per-turn "after turn" RSS (83–247 MB) swings far below baseline mid-run: macOS page compression under the steady ~60 GiB system pressure, the documented noise this gate is built for.
- Raw evidence: `.local/voice-agent/runs/VA-SOAK-005-LIVE.json`.

## Probe defects fixed before the run (previously never executed)

- Gate required lifetime `mic_dropped == 0` / `mic_invalid == 0` — impossible on a 20-hour controller with 34 cumulative drops. Replaced with baseline-captured deltas.
- 20 MB growth band contradicted the measured ±180 MB ps-RSS noise (probe's own comment); set to the VA-SOAK-006 100 MB median band, five spaced samples for baseline and post-drain.

## Limitations

- Four turns in one session, one controller life; not six (B step 9) and not multiple sessions.
- Echo cancellation during soak stays at the weak live-path level (−0.1 to −5.3 dB, consistent with the echo-lag attribution from AEC-REAL-001); one window measured +0.5 dB (cleaned louder than mic) — unexplained, needs the Priority D physical-path investigation, not a soak gate.
- `session_still_alive: true` at the boundary: the probe terminates its session in `finally`, before the RSS post-sampling; cleanup verified for slots/registry only for the live pid.
- VoiceBox survived 4 replies (≈4 clip generations) with zero crashes; does not yet bound the ~24-generation crash threshold.

## Next action

B step 9: rerun with `TURNS = 6` after the owner-gated controller restart so the soak exercises the deployed (pid-locked, turn-latency-instrumented) controller.
