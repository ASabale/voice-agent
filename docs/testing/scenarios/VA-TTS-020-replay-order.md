# VA-TTS-020 — Held sentences keep replay order

Status: implemented, LEVEL 1 (unit, deterministic stubs).

## The failure prevented

When a reply was held during an outage and recovery was partial (the service
answers some sentences but one still fails), the retry pass handed *every* held
sentence to the pipeline at once. The sentence behind the still-failing one
played before it, and the failing sentence was appended at the end. Users hear
"First. Third. Fourth. … Second." A new sentence arriving while earlier
sentences of the same reply are still held played immediately, jumping the
queue. Both are ordering violations in a hands-free conversation: the reply is
spoken out of order.

## Reproduction (pre-fix)

`node --experimental-strip-types --test --test-name-pattern="jump ahead|waits behind" tests/voicebox-refusal.test.ts`:
- test 1: 4 sentences held, partial recovery → `retryDeferredSpeech` retried 4;
  played `["First", "Third", "Fourth"]`, "Second" deferred and replayed last.
- test 2: "Held line." deferred, then "Later line." enqueued → played
  `["Later line."]` while "Held line." was still queued.

Both tests failed with the pre-fix pipeline and pass after the fix.

## The fix

- `speakChunk` now returns `Promise<boolean>`: true when the sentence was
  pushed to the deferred queue.
- `retryDeferredSpeech` awaits each sentence and stops at the first one that
  re-defers; the remainder is re-pushed behind it, so the reply replays oldest
  first on the next 5 s tick.
- `enqueue` holds a new sentence behind an already-held one (deduped by text +
  epoch) instead of sending it straight to TTS.

## Tests

- "a sentence still held during replay does not let later sentences jump ahead
  of it" — partial retry plays only First, keeps Second/Third/Fourth queued in
  order; full recovery plays all four in order.
- "a new sentence arriving while earlier ones are held waits behind them" —
  the later sentence waits, then replays in order.
- Existing "retried sentence already spoken" test: the contract note updated —
  a re-arriving chunk is deduped against the held queue and spoken once by the
  retry pass (retried count is now 1, played exactly once; the anti-duplication
  assertion is unchanged).
Refusal file 15 passed; full Node suite 97 passed; Python 255 unchanged.

## Limits

- Level 1 only: stub generators/players, no real VoiceBox, no afplay, no
  microphone. Ordering of real clip playback after recovery still needs a
  restarted controller and a live VoiceBox.
- Ordering is guaranteed within one reply (epoch). Cross-reply ordering is by
  design: a new reply drops the old reply's held sentences (`defer-stale`).
