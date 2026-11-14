# VA-SOAK-002 — Repeated crash/recovery cycles speak every sentence exactly once

**Status:** PASS (Level 1 unit + Level 3 real-timer probe against a mock
restart cycle). No code change; behavior verified. Level 5 (real VoiceBox
crash/relaunch) remains BLOCKED — VoiceBox GUI recovery is human-only.

## Gap

The realistic outage shape on this machine is not one clean downtime but a
sequence: VoiceBox dies, a human relaunches it, it dies again. Level 1 had
unit coverage for a single deferral, replay-on-recovery, and ordering during
partial recovery (VA-TTS-020), but nothing ever chained *multiple*
crash→recover→crash cycles through the same session. Unbounded growth of
`committed`/`spoken`/`deferred`, a replay of an already-spoken sentence after
a recovery, or a retry timer that never terminates were all untested.

## What was verified

1. **Session state is bounded by design.** `committed` and `spoken` are
   cleared whenever a new reply begins (`beginReplyStopsPlayback` → the
   new-reply reset in `speak`); `deferred` is bounded by the 120 s expiry
   (VA-TTS-019). No unbounded structure exists at session level.
2. **Unit test (Level 1).** New test in `tests/voicebox-refusal.test.ts`:
   reply A deferred during outage → replays in order on recovery; reply B
   deferred during the second outage → partial recovery plays `beta one`,
   `beta two` fails again, and `beta three` waits behind it (VA-TTS-020
   ordering holds across cycles); final recovery plays all five sentences
   exactly once, `deferred=0`, `expiredSpeech=0`.
3. **Level-3 probe.** `.local/voice-agent/probes/recovery_cycle_probe.mjs`
   (mock on 17990, real `generate()`, real 5 s wall-clock retry timer, real
   silent `afplay`):
   - Mock service cycles down(0–20 s) → up(20–40 s) → down(40–62 s) → up(62 s+).
     Each phase change closes and re-creates the HTTP server on the same port,
     modelling a crash + relaunch; "down" destroys the socket mid-request, the
     exact Node 26 `SocketError: other side closed` shape pinned by VA-TTS-021.
   - Four replies (11 sentences) enqueue across the phases.
   - After the second recovery, `C two.` returns 500 on its first attempt
     (half-healthy service) and succeeds on the next retry, with `C three.`
     waiting behind it.
   - The probe deliberately never calls `stopDeferredRetry()` and never
     `process.exit(0)`: natural process exit is the timer-leak assertion. If
     the retry chain or any handle leaked, Node would hang.
   - Asserts: committed spoken text equals the 11 sentences in exact order;
     `deferred=0`; `expiredSpeech=0`; zero stray `omp-vb-<pid>-*.wav` files in
     tmp; RSS delta < 10 MB; watchdog fails the probe if the queue never drains.

## Probe evidence

SEE_EVIDENCE

## Limits

- Mock service, not real VoiceBox: this proves the client-side retry chain
  survives repeated restarts, not that VoiceBox itself recovers.
- `afplay` plays silent 100 ms clips; no microphone or wake word involved.
- The probe process is the only speech client; no concurrent controller.
