# Regression dependency map

Shared components and the scenarios that must be revalidated when each changes.
A passing targeted test does not declare the system healthy; run the rows tied to
the component you touched. Level 1 (unit) is always required; live levels are
required for behavior that only exists in the running environment.

## Component → required regressions

| Component changed | Must revalidate |
|---|---|
| Handy endpointing / capture (`handle_captured_frame`, flush logic) | Native Handy button operation; live transcript preview (partial rows); automatic endpointing (pause flush); turn submission (`Delivery` line + outcome); cancellation path; consecutive captures (second chunk without re-wake) |
| Ducking (`duck_output_volume`, `restore_output_volume`, `_duck_ratio`, stream-gain player `bin/voice-play`) | Ambient noise estimation (`ambient_rms`/`ambient_long_rms` move sensibly); speaker echo estimation (`echo_rms_full_gain`, `aec_echo_db`); human speech recognition over echo (wake-over-echo); volume/gain restoration (transaction reconcile); unrelated application volume unchanged (master volume probe); barge-in (hold + stop) |
| Playback player (`afplay` spawn, `voice-play`, watchdog) | Playback slot lifecycle (`tts-playing/<pid>.json` begin/end); render reference connection/disconnection for AEC; acoustic verification of audible output; hung-player watchdog kill; kill-detection in `_omp_vb_pids` |
| State management (`status.json`, sessions registry, duck-state, tts-playing) | Capture lifecycle; transcript ownership (protected pids); assistant streaming; playback lifecycle; UI state; cancellation and recovery |
| Bridge / session registry (`load_session_registry`, `OMP_VOICE_BRIDGE_ONLY`) | Delivery to the intended session only; ephemeral port discovery; multi-session isolation; delivery outcome semantics |
| VoiceBox generation path (payload shape, retries, deferral) | Real `/generate/stream` produces valid WAV (frames/rate/rms, not just 200); latency measurement; refusal classification; deferral expiry clock |
| Controller supervision (launchd plist, pid lock, restart) | Single-controller lock serialization; restart carries the current code; crash-loop guard; log rotation |

## Suites

- Level 1: `python -m pytest tests/` (344 tests) and `node --test tests/*.test.ts` (114 tests). Run both after any shared-component change.
- Level 3/4 live: `voice doctor` (diagnosis), `voice verify handy|voicebox`, `voice loop` (full physical loop with three-way comparison). Evidence lands in `.local/voice-agent/doctor/`.

## Live loop gating

`voice loop` is the only test that exercises wake → dictating → Handy ASR →
dispatch → assistant turn → VoiceBox generation → playback → acoustic
correlation in one physical run. It temporarily takes over the controller
(unload launchd, dedicated bridge-only controller) and restores launchd in
`finally`. Treat a loop run as the acceptance gate before declaring any
capture/ducking/playback change safe.
