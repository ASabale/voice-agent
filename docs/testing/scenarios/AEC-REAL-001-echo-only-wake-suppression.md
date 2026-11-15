# AEC-REAL-001 — Echo alone never wakes the controller, and the live −2 dB window is explained

1. **ID:** AEC-REAL-001
2. **Name:** Echo-only wake suppression plus attribution of the live residual window
3. **Objective:** With the production controller (the one that owns the microphone) running against real speaker output and *no human speech at all*, prove (a) zero wake events across a full reply and (b) what the live `aec_echo_db ≈ −2 dB` actually consists of — the canceller failing, the guard returning raw blocks, or the metric being diluted.
4. **Failure investigated:** The synthetic four-path fixture reports −33 dB while every live playback window reports −1.8 to −2.7 dB. A single number cannot distinguish "the filter is bad" from "the window is polluted". `_aec_observe` (controller ~719) counted every block the canceller touched, including blocks the `echo_over_cancels` guard (~800) returned *raw* (ratio 1.0). Without a guard count, a window where most blocks were guard-passed looks identical to a window where the filter cancelled nothing.
5. **Preconditions:** VoiceBox listener answering on :17493, the live controller running and owning the microphone, `aec-audio-processing==1.0.0`. The probe opens no microphone and signals no protected process.
6. **Required application versions:** `aec-audio-processing==1.0.0`, openwakeword, the controller's own dependencies.
7. **Required services:** VoiceBox (:17493), the live controller, the OMP bridge of the probe's own isolated session.
8. **Hardware requirements:** MacBook speakers and microphone in the real room (live leg only).
9. **Setup:** Two probes. `scripts/run_aec_residual_probe.py` fetches a real 6.88 s VoiceBox clip through :17493, loads the controller module with state isolated to `.local/voice-agent/fixture-001-lag/state`, and feeds the *production* `cancel_playback_echo` path echo taps (gain 0.7 at lag, 0.25 at lag+150 ms) for lag = 0…600 ms, plus a +60 rms noise variant. `scripts/run_echo_only_status_probe.py` starts an isolated `omp -p` session, asks it for a four-sentence reply, and polls the live controller's `status.json` every 250 ms while afplay is alive.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python scripts/run_aec_residual_probe.py
    ~/.local/share/omp-voice/venv/bin/python scripts/run_echo_only_status_probe.py
    ```
11. **Fixtures:** the clip is a genuine VoiceBox generation; no planted sound is ever played.
12. **Expected behavior:** across the whole reply, zero "Wake triggered" lines; every status window during playback reports a negative residual; the sweep shows where cancellation collapses as echo lag grows.
13. **Pass/fail:** PASS (wake leg) = playback started, ≥4 status windows with `aec_blocks > 0`, `echo_db_max < 0`, zero wake lines, controller alive. The ERLE leg additionally requires a decomposition of the window (cancelled vs guard-raw blocks) — that needs `aec_guard_blocks` on the live controller, which requires a human restart.
14. **Metrics:** echo_db min/max/median per window, guard-block count per window, raw vs cleaned rms, collapse lag (ms), wake count, barge holds.
15. **Evidence:** `.local/voice-agent/runs/AEC-REAL-001-LAGSWEEP.json`, `.local/voice-agent/runs/AEC-REAL-001-LIVE.json`; prior live echo observations in VA-LAT-001 and AEC-REAL-006 evidence files.
16. **Cleanup:** probe sessions are terminated; the fixture slot's fake afplay pid (`sleep 120`) is killed by the probe; the fetched clip stays under `.local/voice-agent/fixture-001-lag/`.
17. **Known failure modes:** the status window is only published on the 1 s capture cadence, so short replies yield few windows; dedupe on `(echo_db, blocks)` collapses repeated polls, not repeated publishes.
18. **Automation status:** LEVEL 4 for the wake leg (real speaker output, real microphone via the live controller, no human voice); LEVEL 2 for the lag sweep (production path, synthetic echo, microphone never opened).
19. **Known limitations:** the live controller (pid 38298) predates the `aec_guard_blocks` field, so the physical decomposition of the −2 dB window cannot be measured until Akshay restarts it — the loop rules forbid the probe restarting the process that owns the microphone. The lag sweep is fixture evidence, not physical ERLE. One barge hold on echo is accepted behavior (Whisper-gated), matching VA-AEC-008 and AEC-REAL-006.
20. **Last verified:** 2026-11-14.

## Design notes

- The sweep pins the collapse between 300 and 400 ms of echo lag: at 100–300 ms the WebRTC path cancels −21 to −24 dB with 0–3 guard blocks; at 400–600 ms it reports −3.3/−3.1/−1.5 dB with 31/31/22 of 86 blocks guard-returned raw and cleaned rms *maxima* above raw (5996 against raw mean 1884) — a failed fit injecting energy, then the guard dumping the block. The guard window is `AEC_GUARD_LAG_SAMPLES = 4800` (300 ms): an echo that trails the render cursor by more than the guard window is indistinguishable from near-end speech by construction, so every crushed block of it is returned raw and the window ratio is pinned near 0 dB.
- Room-noise dilution is real but small: adding 60 rms noise to a well-lagged echo moved the window only from −23.5/−21.6/−21.1 to −19.8/−18.5/−19.0 dB. Noise cannot explain a −2 dB window.
- Delta-0 (echo exactly aligned with the cursor) cancels only −13.1 dB, consistent with VA-AEC-009's delta-0 ceiling (−16 dB): physical echo *always* trails (afplay startup + output buffering + flight time), so the live value is governed by the lag regime, not by this edge.
- The live median of −6.5 dB with a −14.6 dB best window (and −1.8 during the first second while the filter adapts) sits between the fixture cancellation level and the ≥400 ms collapse value. [INFERENCE] the live path is spending a substantial fraction of blocks in the guard-raw regime; the exact fraction is the one number the restart will settle.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-14 | lag sweep 0–600 ms, production path, real VoiceBox clip | see evidence | −13.1/−23.5/−21.6/−21.1 dB at 0/100/200/300 ms; −3.3/−3.1/−1.5 dB at 400/500/600 ms with 31/31/22 guard blocks of 86. Collapse is between 300 and 400 ms. Noise variant: −19.8/−18.5/−19.0 dB. |
| 2026-11-14 | echo-only live status capture, isolated session pid 86020, controller 38298 | PASS (wake leg) | 8.0 s clip, 9 windows: echo_db −1.8 → −14.6 → −2.7 (median −6.5, max −1.8); zero wake lines; one barge hold (rms 666, vad 0.77, floor 90) gated by Whisper; mic IDLE; controller alive. |
| 2026-11-14 | guard counter added to `_aec_observe`/`aec_window_fields` | implemented | `aec_guard_blocks` published alongside `aec_echo_db`; unit test feeds unrelated blocks through a crushed fit and asserts every counted block is guard-returned and the window reads 0.0 dB. Not yet observable on the pre-existing controller. |
