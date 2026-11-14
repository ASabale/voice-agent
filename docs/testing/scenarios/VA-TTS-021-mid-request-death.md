# VA-TTS-021 — a sidecar dying mid-request no longer drops the sentence

Status: implemented, LEVEL 1 (unit) + LEVEL 3 (real 5 s timer chain against a mock VoiceBox).

## The gap

`isConnectionRefusal` held sentences for `ECONNREFUSED`, `ECONNRESET`, `ETIMEDOUT`, `ENOTFOUND`, and "Unable to connect". But when VoiceBox **accepts the TCP connection and then dies before responding** — the shape the GUI crash produced on this machine — Node 26's `fetch` throws:

```
TypeError: fetch failed
  cause: SocketError: other side closed   (code UND_ERR_SOCKET)
```

None of the classic errno strings appear in that shape, so every sentence hit the `logSpeech("failed")` drop path: silently lost, no deferral, no retry. The probe's own `speech.log` rows at 20:41:47 UTC recorded exactly `event: failed, reason: TypeError: fetch failed` for all four reply sentences.

## Reproduction (pre-fix)

`.local/voice-agent/probes/defer_order_probe.mjs` against a mock that accepts the connection then `req.destroy()`s it:

- pre-fix: `deferred=0`, `spoken=""` — four sentences requested, four dropped.
- the two unit assertions on the real Node error shape failed (`isConnectionRefusal` returned false).

## Fix

`extension/voicebox-speech.ts` `isConnectionRefusal` now also matches `other side closed`, `UND_ERR_SOCKET`, and `socket hang up` (the Node http-client phrasing of the same event). The refusal-hold window still arms, so the retry chain stops hammering a dying service; `AbortError` from barge-in is still *not* a refusal.

## Verification

- Unit: `tests/voicebox-refusal.test.ts` "a socket closed mid-request by the sidecar is a refusal, not a loss" — the exact Node 26 error shape, plus `socket hang up`.
- End-to-end: "a sidecar dying mid-request holds the sentence and replays it on recovery" — mock accepts, destroys the socket, the sentence is held (not dropped, not counted as spoken), then replays on recovery.
- Level 3: `defer_order_probe.mjs` — real `generate()`, real `retryTimer`, real `afplay` on silent mock audio, four-sentence reply against a mock that is down (0–25 s), flaky (fails only sentence 2, 25–35 s), then up. Request log:

```
t=6ms      refused <profiles>      (hold window stops the other 3 from hammering)
t=5011..25022ms refused <profiles> (one probe per 5 s tick)
t=30030ms  200 First line
t=31116ms  500 Second line
t=36119ms  200 Second line          (retried before Third — no jump-ahead)
t=37187ms  200 Third line
t=38258ms  200 Fourth line
RESULT jumpAhead=false successesInOrder=true finalDeferred=0
finalSpoken="First line... Second line... Third line... Fourth line..."
```

Suites: Node 103 passed (refusal file 21), Python 255 unchanged.

## Limits

- Level 1 + Level 3 only: mock service, silent synthesized WAV, no microphone, no real VoiceBox.
- The mock's death is socket-close-after-headers; a process SIGKILL produces the same `UND_ERR_SOCKET` shape, but that was not separately exercised.
- Ordering of real TTS audio after recovery still needs a restarted controller and a live VoiceBox (VA-TTS-020's open item, unchanged).
