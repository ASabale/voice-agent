# VA-AEC-004 — Multi-Path Room Response Scenarios

Status: implemented and measured, LEVEL 1. The room is synthetic; no microphone was touched.

## What the tests do

`tests/test_echo_control.py` builds a mic signal that hears the played clip through four
delayed paths — 15, 30, 60 and 90 ms with gains 0.45, 0.18, 0.07, 0.03 — then feeds it
through the production `cancel_playback_echo` in 1280-sample blocks with the same
wall-clock placement the live loop uses (`refresh_render_reference` plus
`render_block_at` per frame).

## Measured results

| Scenario | Measurement | Result |
|---|---|---|
| Four-path room response, 8 s | echo return loss | 37.7 dB cancelled |
| Near-end speech on top of the echo | near-end retained after cancellation | 0.54 of the original level |
| Same echo, 20 s continuous | tail return loss | 38.7 dB |

The short-fit subtractor cannot handle this: it removes exactly one delay (the AEC-DECISION
measurements show 9–11 dB left with two arrivals). AEC3 tracks all four paths and keeps
converging; the residual at the tail is under 2% of the echo energy.

## What this proves and what it does not

- Proves the canceller's filter length and adaptation handle multiple reflections and
  long utterances, which is the risk for the real laptop-speaker room.
- Proves near-end speech survives while the echo is cancelled — the double-talk
  requirement (iteration goal 5) is met in the synthetic channel.
- Does not measure the real speaker-to-microphone delay, real reflection gains, laptop
  volume, or Handy's behaviour on cancelled audio. Those need a physical test, which
  stays blocked while pid 64238 owns the microphone (INTEGRATION-BLOCKERS item 4).

## Reproduce

```bash
~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_echo_control.py -s \
  -k "multi_path or near_end_survives or twenty_seconds"
```
