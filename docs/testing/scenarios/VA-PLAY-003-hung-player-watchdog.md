# VA-PLAY-003 — A watchdog-killed hung player is never counted as spoken

Status: implemented, LEVEL 1 (unit, fake `afplay` on PATH). No microphone, no real VoiceBox, no real audio output.

## The failure prevented

`play()` spawns `afplay` with a 45 s playback watchdog: if the player process
never exits, the watchdog SIGKILLs it and calls `finish(null, "SIGKILL")`.
`playbackHeard(null, "SIGKILL", false)` returns `true` — semantics written for
**barge-in** kills (a user interrupting a genuinely playing clip counts the
sentence as heard). The watchdog kill was indistinguishable from a barge kill,
so a player that hung and played **nothing** was `commitSpoken`: the sentence
was permanently consumed, never played, never retried. This violated the
Priority E contract ("a hung generation does not permanently consume a
sentence") on the player side: generation hangs defer and retry; player hangs
silently dropped.

## Reproduction

`tests/voicebox-refusal.test.ts`, test "a player hung until the watchdog kills
it is never counted as spoken": stub generator writes a real 4410-frame WAV;
the **real** `play()` runs; PATH is prepended with a temp dir holding a fake
`afplay` (`#!/bin/sh` + busy loop, chmod +x); `OMP_PLAY_WATCHDOG_MS=300` makes
the watchdog fire in 300 ms.

- Pre-fix: 305 ms elapsed (watchdog, not spawn error), `currentSpokenText()` =
  the sentence → FAIL. Raw: `.local/voice-agent/runs/VA-LOOP-012-hung-player.txt`.
- Discarded first attempt: enqueue with the default `generate` hit the dead
  VoiceBox (17493 refused), deferred the sentence, and `play` never ran — a
  vacuous pass that contaminated the repro; rewired to a stub generator.

## The fix

`extension/voicebox-speech.ts`:

- `playWatchdogMs()` reads `OMP_PLAY_WATCHDOG_MS` (default 45000) — test
  knob mirrors `ttsTimeoutMs()`; production threshold unchanged.
- The watchdog sets `watchdogFired = true` before killing.
- `if (playbackHeard(exitCode, exitSignal, spawnError) && !watchdogFired)
  commitSpoken(...)` else `releaseUnspoken(...)`.
- Barge-in kills (signal without watchdog) still count as heard; the existing
  contract vector `playbackHeard(null, "SIGKILL", false) === true`
  (`tests/speech-queue.test.ts:133`) is untouched.

## Tests

- `node --experimental-strip-types --test tests/voicebox-refusal.test.ts` — 26 passed.
- Full Node suite: 114 passed (was 110 before this scenario). Python suite: 308 passed, unaffected.
- Recovery proof (VA-LOOP-013, 2026-11-16 02:45 UTC): a second test re-enqueues
  the same sentence after the watchdog release with a stub player — it passes
  dedupe, plays, and commits. `releaseUnspoken`'s `forget=true` branch removes
  the chunk from `session.spoken`, so the sentence is genuinely re-speakable.
- Automatic retry chain (VA-LOOP-014, 2026-11-16 03:00 UTC): the watchdog-killed
  sentence is pushed onto `session.deferred` and re-spoken automatically by the
  5 s cadence, exactly like a hung generation. The deferral keeps the FIRST
  deferral timestamp (VA-TTS-019 clock rule), so a permanently broken player is
  bounded by the 120 s expiry. A re-enqueue of the same held sentence does not
  duplicate the deferral entry. Red repro first (`deferred.length 0 !== 1`);
  green after the fix.
- Generalized (VA-LOOP-015, 2026-11-16 03:15 UTC): `play()` returns `{ heard }`
  and `speakChunk` defers on ANY un-heard player outcome — hang, non-zero exit
  code, or spawn failure — not just watchdog kills (`logSpeech(..., reason
  "player-failure")`). Red repro with a fake `afplay` that `exit 1`
  (`deferred.length 0 !== 1`), green after the fix. Barge-in kills still count
  as heard and never defer.

## Limitations

- Level 1 only: the fake player never touches real audio hardware; a real
  `afplay` wedging is not reproduced.
- The retry-chain replay regenerates the clip; against a live-but-broken
  player it retries until expiry. A clip-duration-aware watchdog (WAV frames /
  sample rate + slack, pattern from the VA-PLAY-002 orphan lease) would avoid
  killing legitimately long (>45 s) sentences; deliberately not implemented.
- Live deployment note: running OMP sessions keep the old extension until
  they reload; the retry replay through real `afplay` is Level 3 evidence and
  needs VoiceBox back up (A1).
