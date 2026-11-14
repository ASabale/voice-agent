# VA-MEM-004 — The guardian's voice flag cannot outlive its afplay pid

**ID:** VA-MEM-004
**Checked:** 2026-11-14 19:20 UTC
**Level:** 1, unit, real guardian code with synthetic state files.

## Failure prevented

The voice-shed tier (VA-MEM-001) protects the engine by unloading VoiceBox before a kill. It is gated by `_voice_is_playing()`, which reads only the flat `tts-playing.json` projection. Pruning of dead playback slots is read-triggered (VA-PLAY-002), and the guardian never reads the slot directory. If a session is SIGKILLed mid-clip and no controller read happens afterwards, the projection stays frozen with `playing: true` forever. The guardian then defers every VoiceBox unload — the voice-shed tier is permanently disabled, and the engine reaches the sustained kill line instead of getting relief.

## Reproduction (before the fix)

```
guardian believes voice playing with dead pid: True
```

A projection `{"playing": true, "started_at": 1000.0, "pid": <pid of a reaped `true` process>}` returned True from the verbatim installed guardian. The live `~/.local/state/omp-voice/tts-playing.json` at check time was `{"playing": false}`, so the hazard was latent, not currently firing.

## Change

`_voice_is_playing()` in `~/.local/bin/strata-memory-ceiling` now treats the projection's `pid` field as a liveness witness: if a positive integer pid is present and `kill(pid, 0)` raises `ESRCH`, the voice is not playing. Missing or malformed pid stays conservative (defer the unload); a zombie afplay still counts as playing, which is correct until its parent reaps it. No thresholds, timings, or tiers changed.

## Tests

- `pytest tests/test_memory_guardian_contract.py tests/test_memory_guardian_policy.py tests/test_playback_state.py -q` → 40 passed. New test `test_the_voice_flag_does_not_outlive_its_afplay_pid` covers: dead pid → not playing; live pid → playing; no pid → conservative defer; malformed pid → conservative defer; `playing: false` with a live pid → not playing.
- Full suites: 251 Python, 88 Node.
- `py_compile` clean on the guardian script.

## Limitations

- The running guardian instance (pid 40203, started 06:08 UTC) predates this edit; the check is not live until the guardian is restarted — a human decision, since the watchdog is the safety net.
- Cross-uid processes can return EPERM for `kill(pid, 0)`; afplay is always uid-matched, so this is not a practical miss here.
- End-to-end unload relief in GiB is still unmeasured (VoiceBox 17493 refused).
