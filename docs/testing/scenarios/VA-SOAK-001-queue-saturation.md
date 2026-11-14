# VA-SOAK-001 — A reply of hundreds of sentences held during an outage recovers exactly once

Status: implemented, LEVEL 1 (unit, mock HTTP). This is a deterministic stand-in
for the Level 5 "queue saturation" row; it is not live behavior and does not
close Level 5.

## The failure prevented

During a VoiceBox outage, every sentence of a reply is deferred. If the retry
chain mishandles scale — arming timers per sentence, losing order, double
playing, or silently dropping — the user gets a garbled, partial, or doubled
reply after the service returns. Before this pass, saturation was only tested
with 1–2 sentences.

## Exact reproduction

`node --experimental-strip-types --test tests/voicebox-refusal.test.ts`
(test "a whole reply held during an outage replays exactly once, in order, on
recovery"):

1. 300 distinct sentences enqueued while nothing listens on port 17991.
2. After the queue settles: `played.length == 0`,
   `currentDeferred().length == 300` — all held; the refusal hold keeps 299 of
   the attempts from hammering the dead port (one fetch, then held).
3. Wait out the real 5 s refusal window (wall-clock, not injected), start a
   mock that answers `/generate/stream` with a valid WAV.
4. `retryDeferredSpeech(undefined, stubPlayer)`: returns 300; the stub player
   records exactly the 300 sentences in the original order; the deferred queue
   is empty; `currentSpokenText()` equals the full reply.

Each generated clip is written to `os.tmpdir()` by the real `generate()` and
unlinked by the stub player; the temp directory was verified empty after the
run (0 `omp-vb-*` files).

## Result

PASS 2026-11-14 20:05 UTC: 12/12 in the refusal file; full Node suite 94
passed; Python suite 255 passed.

## Limits

- Level 1 only: no microphone, no real VoiceBox, stub player instead of
  `afplay`. Live saturation (Level 5) still requires a running controller and
  service.
- The retry chain's 120 s expiry is not exercised at saturation scale; the
  expiry path itself is unit-tested (VA-TTS-014).
- Ordering is oldest-first within one reply epoch; a barge-in during the
  outage window drops all held sentences (tested, VA-TTS-014).
