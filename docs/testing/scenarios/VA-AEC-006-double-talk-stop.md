# VA-AEC-006 — A spoken "stop" barges through live echo

Status: implemented, LEVEL 4 (fixture-fed production frame loop). No
microphone, no sound played.

## What it proves

`scripts/run_double_talk_probe.py` plays a ~6.7 s assistant clip through the
render slot with the four-tap room response (15/30/60/90 ms), then feeds the
user's "Stop. Stop. Stop." mixed with the continuing echo through
`handle_captured_frame`:

1. Echo alone (blocks 0-39) triggers no wake and no barge hold: the mic stays
   IDLE and the canceller measures -27.4 dB residual over 40 blocks.
2. Mixed echo + speech trips the barge gate exactly as production:
   `TTS barge hold rms=6257 vad=0.96 floor=8 hot=3` — the floor from the
   cancelled echo is 8, so the user's voice sits far above the bleed floor.
3. Whisper hears "stop." -> `stop_playback` -> `kill_tts_clips` kills the
   stand-in clip pid -> the slot stops counting as playing ->
   "render reference unavailable". The mic never entered DICTATING.

## Design notes

- The barge gate requires three consecutive hot frames (vad >= 0.55,
  rms >= max(320, floor*2.4)). A single `say "Stop."` clip voiced only 2
  frames per tile, so the near-end is a dense "Stop. Stop. Stop." tile — the
  same shape a real barge-in has.
- The stand-in clip process is named `afplay-omp-vb-<owner>-clip` so the real
  `kill_tts_clips` ps matcher finds and kills it. The probe must reap it
  each block: an unreaped zombie child still answers `os.kill(pid, 0)`, which
  would fake a playing slot.
- `double_talk_aec_db` (-4.4 dB) mixes user speech into the window energy and
  is reported, not asserted. The echo assertion uses the echo-only window.

## Reproduce

```bash
~/.local/share/omp-voice/venv/bin/python scripts/run_double_talk_probe.py
```

Exits 0 on PASS. Isolated state dir, dead bridge port (17999), the bridge
`/barge-in` POST fails harmlessly. Pid 64238 untouched.

## Limits

Whisper heard "stop." from a synthesized clip, not a real voice; the physical
speaker-to-mic path is still untested until the live controller restarts.
Not VA-INT-001.
