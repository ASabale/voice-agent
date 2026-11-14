# VA-TTS-019 — Re-deferral does not reset the expiry clock

Status: implemented, LEVEL 1 (unit) + LEVEL 3 (real timer chain against a dead
mock port; no microphone, no real VoiceBox).

## The failure prevented

`retryDeferredSpeech` is armed by a 5 s timer after every deferral. Before the
fix, each failed retry re-pushed the sentence with `at: Date.now()`, so
`now - at` never exceeded `DEFER_EXPIRY_MS` (120 s) and the `defer-expired`
branch could never fire. Against a permanently unreachable VoiceBox a sentence
retried forever: every 5 s a `deferred` line was appended to `speech.log` and
the retry chain never terminated. The checkpoint claimed the chain was
"bounded (5 s cadence, 120 s expiry)"; it was not.

## Reproduction (pre-fix)

`.local/voice-agent/probes/defer_expiry_probe.mjs`: real timer chain against a
port with nothing listening (17990). Sentence deferred at t=5 ms; the timer
retried every 5 s; at t=135 s (> 120 s expiry) the sentence was still in the
deferred queue — never expired.

## The fix

`speakChunk` takes the deferral timestamp as a parameter (`at`, defaulting to
`Date.now()`); `retryDeferredSpeech` passes the item's original `at`, so the
clock measures from the first deferral, not the latest failed attempt.

## Tests

`node --experimental-strip-types --test tests/voicebox-refusal.test.ts`:
"a repeatedly deferred sentence keeps its original deferral time and eventually
expires" — a sentence retried inside the window stays deferred with an
unchanged `at`; once the window passes it is logged `dropped` with reason
`defer-expired` and leaves the queue. Refusal file 13 passed; full Node suite
95 passed; Python 255 unchanged.

Post-fix probe: same dead-port chain; the sentence is dropped at t=125,036 ms
(the first 5 s timer tick past the 120 s window) with `dropped` reason
`defer-expired` in `speech.log`, and the chain terminates (`deferred=0`).

## Limits

- The probe exercised `generate()` against a mock-dead port, not the real
  VoiceBox (down). The refusal-hold short-circuit means the unbounded chain
  costs no network traffic — the fix is about termination and log growth, not
  load.
- Expiry dropping a sentence after 120 s of continuous unavailability is the
  documented design; whether the user should be told on screen is out of scope
  for this fix.
