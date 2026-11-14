# VA-TTS-017 — A hung VoiceBox generation no longer silently drops the sentence

Status: implemented, LEVEL 1 (unit, mock HTTP). No microphone, no real VoiceBox.

## The failure prevented

`generate()` wraps `/generate/stream` in a 90 s watchdog (`AbortController`). If
VoiceBox is alive but wedged — headers sent, body never ends — the watchdog
aborted the fetch and the catch classified the `AbortError` as a plain failure:
`logSpeech("failed")` and `return undefined`. In `speakChunk` that path calls
`releaseUnspoken` with no deferral, so the reply sentence was released from the
queue, never played, and never retried. On screen: the reply exists; through the
speakers: nothing, forever. Distinct from the already-covered refusal (500,
short payload, connection refused) paths, which all defer.

## Reproduction

`probes/tts_timeout_drop_probe.mjs` (mock VoiceBox on a dedicated port; never
touches 17493): a `/generate/stream` handler sends 200 headers and never ends
the body.

- Pre-fix: `deferred=0`, `spoken=""` after the 90 s watchdog elapsed
  (`elapsed_ms=90003`) — silent drop.
- Post-fix (watchdog shortened via `OMP_VOICE_TTS_TIMEOUT_MS=3000`):
  `deferred=1` — the sentence enters the retry chain.

## The fix

`extension/voicebox-speech.ts`:

- `ttsTimeoutMs()` reads `OMP_VOICE_TTS_TIMEOUT_MS` (default 90000) so the
  watchdog is test-configurable; production default unchanged.
- The timer sets `watchdogFired` before calling `abort()`.
- In the catch, an `AbortError` is split by source: watchdog abort while the
  reply epoch is still current → `{ deferred: true }` with reason
  `generation-timeout`; abort caused by a real stop/barge-in (which bumps
  `speechEpoch` in `stopPlayback`) → explicit `dropped` with reason `abort`.
  Deferred sentences ride the existing retry chain (5 s retries, 120 s expiry,
  oldest-first, epoch discipline).

## Tests

`node --experimental-strip-types --test tests/voicebox-refusal.test.ts` — 9
passed:

1. Hung stream (800 ms watchdog) → sentence held, not counted spoken, nothing
   played; when the mock recovers, the retry chain replays it exactly once.
2. `stopPlayback()` during a hung stream → the sentence is dropped, never
   deferred and never resurrected after the stop.

Full suites on the current tree: Node 91 passed (was 89), Python 255 passed.
`py_compile` unaffected (no Python change).

## Limits

The watchdog is still a bound, not a proof VoiceBox recovers; the physical
hung-sidecar scenario is untested because the real VoiceBox sidecar (17493) is
down and reopening it is a human step. The retry chain is bounded by
`DEFER_EXPIRY_MS` (120 s), so a permanently wedged sidecar eventually gives up
on the sentence — that behavior is already unit-tested elsewhere. The running
OMP session keeps the old extension until it reloads.
