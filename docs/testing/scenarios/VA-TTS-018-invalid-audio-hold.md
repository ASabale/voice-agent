# VA-TTS-018 — A 200 whose body is not playable PCM no longer counts as speech

Status: implemented, LEVEL 1 (unit, mock HTTP). No microphone, no real VoiceBox.

## The failure prevented

`generate()` accepted any 200 response with a body of 100 bytes or more as
audio: it wrote the bytes to a WAV file and handed it to `afplay`. A wedged
service can answer 200 with an error page, a truncated header, or a valid
header with no real audio. Two losses followed:

- `afplay` fails on the garbage (non-zero exit): `playbackHeard` returns false,
  `releaseUnspoken` runs, but nothing defers the sentence. It is neither spoken
  nor retried — silently lost.
- A valid header with ~silence plays "successfully": the sentence is committed
  as spoken while the user heard nothing.

Reproduced pre-fix with `.local/voice-agent/probes/garbage_payload_probe.mjs`
(mock on 17994, 200 with a 149-byte JSON error body): `speech.log` recorded
`event:"generated", bytes:149, reference:null`, then `deferred=0`,
`spokenText=""`. The sentence was gone with no retry.

## The fix

`extension/voicebox-speech.ts` — before writing the clip, `wavReference`
(which already parses RIFF/WAVE, fmt, and data chunks in
`extension/playback-state.ts`) is checked:

```ts
if (!reference || reference.frames < Math.floor(reference.sample_rate * 0.1)) {
  logSpeech("deferred", text, { reason: "invalid-audio", bytes: wavBytes.byteLength });
  return { deferred: true };
}
```

Non-PCM bodies, truncated headers, and headers with less than 100 ms of audio
now join the same bounded retry chain as 500s and refusals (5 s retries,
120 s expiry, epoch discipline). Real sentences are far longer than 100 ms,
so the floor cannot reject genuine speech.

## Tests

`node --experimental-strip-types --test tests/voicebox-refusal.test.ts` — 11
passed:

1. 200 with a 150-byte JSON error body → held, not spoken, nothing played;
   when the mock recovers with a real WAV, the retry replays it exactly once.
2. Valid WAV header with 20 ms of PCM → held, not counted as spoken.
3. The two existing "usable payload" mocks previously used `"RIFF" + zeros`
   (never a real WAV); they now use a `validWav()` helper, so the truncated-
   payload and watchdog-timeout recovery tests assert against genuine audio.

Full suites on the current tree: Node 93 passed, Python 255 passed.

## Limits

The guard validates the WAV container and a duration floor; it cannot detect
garbage PCM inside a structurally valid header (white noise, for example). The
actual VoiceBox never returned such a payload in any observed run; the class is
defensive. Running OMP session keeps the old extension until reload.
