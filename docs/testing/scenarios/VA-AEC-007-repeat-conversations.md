# VA-AEC-007 — Two full conversations in one controller instance with echo

Status: implemented, LEVEL 4 (fixture-fed production frame loop, ~73 s wall).
No microphone, no sound played.

## What it proves

`scripts/run_repeat_turn_probe.py` runs two complete turns — echo of an
assistant clip, close the slot, wake, dictation, pause flush — through one
`MicState` and one controller import, with no restart between turns:

1. Echo of each assistant clip (40 and 30 blocks) triggers no wake: the mic
   stays IDLE while the "assistant" is playing.
2. Each real wake fires (openWakeWord 0.97) after the slot closes and the
   0.6 s reverb-tail guard clears.
3. Both chunks flush via the 5 s pause and Handy transcribes each verbatim:
   'Check the first transcript, please.' and 'Confirm the second transcript
   now.' Nothing from the assistant clips leaks into either transcript.
4. The flush dispatch is held (dead bridge), then the 15 s DICTATING idle
   timeout returns the mic to IDLE — the second conversation starts clean
   in the same process.
5. Wake-to-flush latency measured: 7.2 s and 8.4 s (dictation speech plus
   the fixed 5 s pause). First baseline for the observability metric.

## Design notes

- The wake gap after closing a slot is not a probe quirk: `slot_is_speaking`
  keeps the tail guard (0.60 s) open after `ended_at`, so feeding the wake
  immediately gets swallowed. Real users experience the same 0.6 s window.
- A "held" dispatch keeps the controller in DICTATING ("Continuing DICTATING
  for next chunk"). Only the idle timeout closes the turn. This is why the
  silence loop runs past 5 + 15 s: without it, echo playing in the DICTATING
  window would be appended to the next chunk. That is a live risk for the
  physical test, not a fixture artifact.
- `aec_blocks` resets each time the render reference is re-linked to a new
  clip; the published -25.8 dB describes the newest clip's window.

## Reproduce

```bash
~/.local/share/omp-voice/venv/bin/python scripts/run_repeat_turn_probe.py
```

Exits 0 on PASS. Isolated state dir, dead bridge port (17999). Pid 64238 and
16590 untouched.

## Limits

Synthetic room, synthesized `say` clips, one process — not the physical
speaker-to-mic path, and not two real agent turns. Not VA-INT-001.
