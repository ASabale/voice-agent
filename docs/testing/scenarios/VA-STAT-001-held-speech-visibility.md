# VA-STAT-001 — Held and expired speech is visible in status

Status: implemented, LEVEL 1 (unit). Live `/status` fetch against a running
OMP session not yet observed (needs a session reloaded with the extension).

## The failure prevented

During a VoiceBox outage or a guardian voice-shed, the voice path goes silent
while reply text sits on screen unspoken. `GET /status` reported only
`speaking: false` and the `voice status` command printed no hint of queued
speech. The owner could not tell the difference between "nothing to say",
"speech held awaiting recovery", and "speech lost after the 120 s expiry" —
the exact situation the loop prompt calls out: text on screen that was never
spoken must not be silently treated as a completed voice response.

## Reproduction (pre-fix)

There was no exported surface exposing `session.deferred` outside the test
helpers, and the `/status` handler payload contained no deferral fields. The
first status test fails against the pre-fix module with an import error for
`currentSpeechStatus`.

## The fix

- `VoiceSession` gains `expiredSpeech`, incremented in `retryDeferredSpeech`
  when a held sentence hits `defer-expired` (stale drops from a replaced
  reply are not counted — the user replaced the reply intentionally).
- Exported `currentSpeechStatus()` returns
  `{ speaking, deferred, deferredOldestAgeMs, expiredSpeech }`.
- `GET /status` merges it into the payload (additive; the controller's
  `cmd_status` dumps the whole bridge JSON, so `omp-voice-controller status`
  shows it with no controller change).
- The `voice status` fallback text now includes
  `held=N (Xs oldest)` and `expired=N` when nonzero.

## Tests

Four new tests in `tests/voicebox-refusal.test.ts`:
- held sentences during an outage report `deferred: 2`, `speaking: false`;
- injected-clock expiry reports `expiredSpeech: 1`, queue empty;
- an epoch-replaced reply drop does not count as expired;
- full replay clears both counters.
Refusal file 19 passed; full Node suite 101 passed; Python 255 unchanged.

## Limits

- Level 1: the status payload is exercised through the exported function, not
  a live HTTP `/status` request (the bridge handler needs an OMP ctx; it
  spreads the same function verbatim).
- `expiredSpeech` counts per session process, resets on
  `resetSpeechSession`; not persisted to disk.
- Controller status display of the new fields is inferred from the existing
  dump of the bridge payload, not observed on a restarted controller.
