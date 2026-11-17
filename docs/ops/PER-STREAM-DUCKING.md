# Per-stream ducking: why we stopped touching the master volume

## Problem
The barge-in duck (VA-DUCK / spec §3) implemented attenuation through macOS
master output volume via osascript. Ducking the VoiceBox reply therefore also
silenced YouTube, music, and everything else on the machine while the assistant
was speaking. macOS exposes no public per-application output volume, and
CoreAudio process taps are capture-only (they read a process's output for
analysis, they cannot inject gain), so in-process attenuation of the VoiceBox
stream is the only architecture that leaves other apps untouched.

## Design
- `bin/voice-play` is a sounddevice player that replaces `afplay` for VoiceBox
  clips when `OMP_VOICE_STREAM_PLAYER=1`. It re-reads
  `~/.local/state/omp-voice/stream-gain.json` every 40 ms chunk and ramps gain
  over ~50 ms, so attenuation changes take effect mid-sentence without
  restarting playback. It supports `--speed` (mirrors `afplay -r`, clamped
  0.25–2.0) because the production playback rate is 1.18.
- The controller's `duck_output_volume` / `restore_output_volume` gain a
  stream branch when `stream_player_enabled()`: the duck writes
  `gain = target_pct / current` to the file instead of calling osascript.
  Adaptive depth (echo vs ambient), minimum attenuation, retry backoff,
  transaction persistence (`duck-state.json` gains `stream_gain`), the stuck
  duck watchdog, and the rms-floor holdoff all operate identically on the
  gain value.
- The AEC is unaffected: normalized cross-correlation is scale-invariant, and
  `_duck_ratio` (used to scale the reverse reference in
  `cancel_playback_echo`) carries the same semantics for gain as for volume.
- The pid probe (`_omp_vb_pids`) matches both `afplay` and `voice-play` so
  pause/resume and termination work for either player.

## Cutover
- Production: add `OMP_VOICE_STREAM_PLAYER=1` to the launchd plist
  (`docs/ops/com.akshay.omp-voice-controller.plist`) and reload. The extension
  reads the same env in the omp process; the controller reads it in the
  daemon. If the env is absent the old master-volume path still works — the
  flag is opt-in, not a hard requirement.
- The master-volume path remains for machines where the stream player cannot
  open the output device; it is not deleted so the regression suite still
  covers it.

## Verification
- `tests/test_stream_duck.py`: gain written not master volume; restore to 1.0
  including `_duck_ratio`; ambient-dominance halves the duck; sub-minimum
  attenuation skipped; crash transaction reconciles to 1.0; pid probe matches
  voice-play and afplay, rejects unrelated players.
- `tests/test_stream_player.py`: WAV parsing, gain-file response, clean exit
  on SIGTERM.
- `scripts/run_stream_gain_probe.py` (VD-DUCK-001) measures the echo level at
  the microphone while the gain file flips mid-playback, and asserts the
  master volume is unchanged. Run with the controller stopped (mic
  contention); reload launchd afterwards.
