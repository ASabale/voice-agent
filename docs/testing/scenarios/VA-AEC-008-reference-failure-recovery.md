# VA-AEC-008 — The render reference breaks mid-playback; the loop recovers

Status: implemented, LEVEL 4 (fixture-fed production frame loop, ~40 s wall).
No microphone, no sound played.

## What it proves

`scripts/run_render_recovery_probe.py` runs one continuous conversation
through `handle_captured_frame` while the playback reference fails and is
replaced:

1. Connected baseline: 25 echo blocks of a valid clip cancel to −28.2 dB.
2. Writer crash: mid-playback the slot announces a clip whose file on disk is
   truncated (header claims more PCM than exists). The canceller refuses the
   reference — status shows `render_connected: false`, the log records
   "render reference unavailable" — and echo flows through uncancelled with
   no exception. The mic stays IDLE; raw echo never wakes it (no wake word),
   though the barge-hold gate briefly fires on it (rms 683) without acting.
3. Recovery: a fresh valid clip connects again (frames=44800), cancels 25
   blocks to −29.6 dB, and the conversation continues.
4. After the reconnect, wake fires (openWakeWord 0.95), the sentence flushes
   verbatim ('Confirm the recovery transcript.'), and the run ends IDLE.

## Design notes

- Deleting a loaded clip file does NOT disconnect the canceller: the PCM is
  already in memory and the reconnect only re-reads when the slot's
  (wav, frames, rate, channels) key changes. The first probe version assumed
  unlink = failure and was wrong; the crash modeled here is the real one — a
  new reference that fails to parse.
- A failed parse leaves the reference disconnected until a new clip key
  arrives. That matches VoiceBox behavior: every utterance writes a new file.
- Raw echo through a disconnected reference can trip the barge-hold gate
  (hot frames, rms above floor × 2.4). Only Whisper-confirmed commands act,
  so it held harmlessly here. On real hardware this is the case the physical
  test must examine: with the reference gone, echo could trigger barge logic.

## Reproduce

```bash
~/.local/share/omp-voice/venv/bin/python scripts/run_render_recovery_probe.py
```

Exits 0 on PASS. Isolated state dir (`fixture-008`), dead bridge port
(17999). Pid 64238 and 16590 untouched.

## Limits

Synthetic room and synthesized clips; the physical VoiceBox crash path (a
truncated write racing afplay) is not exercised. Not VA-INT-001.
