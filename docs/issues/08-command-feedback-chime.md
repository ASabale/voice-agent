# 08 — Command feedback sound + live verify

Status: done 2026-11-22. `MacActuator.chime()` fires `afplay` on `COMMAND_SOUND`
(`OMP_VOICE_COMMAND_SOUND`, empty disables) after every command the actuator runs.
Controller reloaded via launchctl bootout/bootstrap; pid 50647 running, status IDLE.

Depends on 06, 07.

## Goal
Eyes-free confirmation independent of VoiceBox: when an actuator command fires, play a short macOS system sound (`afplay /System/Library/Sounds/Tink.aiff`, configurable via env `OMP_VOICE_COMMAND_SOUND`, empty disables).

## Constraints
- Must NOT be matched by `_omp_vb_pids()` (needle `omp-vb-`), so barge-in/kill never touches it and it never counts as a render reference for AEC. Fire-and-forget, non-blocking.
- No change to TTS playback path.

## Acceptance
- Test via recording adapter that a fired command requests the sound; test that the sound command line does not contain `omp-vb-`.
- Restart the controller (launchctl bootout/bootstrap per repo runbook / skill restart-voice-controller), verify `pgrep -fl omp-voice-controller` and `omp-voice-controller status` healthy.
- `python -m pytest tests -q` green.
