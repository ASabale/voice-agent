# VA-PHYS-002 — wake word through the speakers: suppressed during reply playback, honored the instant playback drains

**Scenario class:** Live LEVEL 4 physical probe (real microphone, real speakers, running controller).
**Spec requirement:** §4 wake/AEC — a genuine wake word must not be eaten by the echo canceller, and reply echo must never open dictation.

## Design contract being tested
`bin/omp-voice-controller` `handle_idle_frame` (line ~3471): while `tts_active` is true the controller `oww.reset()`s the wake spotter and routes through the barge gate — a reply that sounds like "Hey Jarvis" must not open Handy. So "wake while TTS plays" is *by design* impossible; the physical risk is the **AEC tail**: the frames right after playback ends are still guard-processed against the render reference, and a genuine wake there could be crushed. This probe tests both sides.

## Probe
`scripts/run_wake_over_echo_probe.py`
1. Starts an isolated omp session (no microphone opened by the probe), submits a four-sentence prompt; reply plays through VoiceBox (8.8–11.6 s clips observed).
2. **Phase A:** plays `tests/fixtures/hey-jarvis-say.wav` through the speakers *while the reply is still playing*. Assert: zero wake lines.
3. Waits for the reply's afplay to exit.
4. **Phase B:** plays the same fixture immediately after playback drains. Assert: a wake line appears (`openWakeWord score=...` or `Wake triggered (whisper heard ...)`) and the controller enters DICTATING.
5. Cleanup: the probe terminates its session; the controller's own 15 s dictation idle timeout returns it to IDLE. Assert: same controller pid alive, final state IDLE.

## Result — PASS, 2026-11-16 05:12 UTC (controller pid 251, VoiceBox 0.6B sidecar)
- Phase A: wake fixture played 1.59 s into the reply window — **zero wake lines**. Speaker bleed of a real "hey jarvis" recording during playback does not open dictation (design suppression holds; no false wake).
- Phase B: fixture played the moment afplay exited — controller entered DICTATING within the 10 s window; log line: `[2026-11-16 00:03:40] Wake triggered (whisper heard 'Jarvis.') -> entering DICTATING` (local clock, matches the run). The wake was confirmed by the Whisper verifier, not merely the raw spotter.
- Controller survived; returned to IDLE via the 15 s idle timeout; pid unchanged.
- Evidence: `.local/voice-agent/runs/VA-PHYS-002-WAKE-OVER-ECHO.json`.

## First run note (FAIL, then root cause)
The first probe version asserted a wake *during* playback and FAILed with zero wake lines. Root cause: not an AEC defect — `tts_active` deliberately disables the wake spotter (controller line 3471, comment "While VoiceBox is playing, ignore the wake word"). The probe was rewritten to the two-phase contract above. No controller behavior changed.

## Known limitations
- Phase B wake came through the Whisper path; the raw openWakeWord score of the fixture in the AEC tail is not individually published. The acceptance is the state transition, which is the product-relevant signal.
- Probe plays the wake fixture once per phase; a miss would need a rerun, not a gate change.

**Last verified:** 2026-11-16 05:12 UTC, controller pid 251, revision `f954713` + probe rewrite.
