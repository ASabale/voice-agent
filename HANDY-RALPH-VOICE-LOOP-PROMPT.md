# Handy / VoiceBox / OMP Ralph voice loop

You are the only runner of the Handy / Hey Jarvis / VoiceBox / OMP voice loop. One engineering objective per iteration. Inspect the source, reproduce the gap, make the smallest fix, verify it, and leave evidence in the checkpoint.

## Source of truth (read fresh every iteration)

- `HANDY-SCENARIO-CHECKPOINT.md` — scenario ledger and evidence
- `docs/testing/INDEX.md` — the full test catalogue with the validation level of every row
- `docs/testing/AEC-DECISION.md` — the echo-canceller architecture decision
- `docs/VOICE-AGENT-ARCHITECTURE.md` — capture and playback map
- `HANDY-RALPH-VOICE-LOOP-PROMPT.md` — this contract

Do not trust chat memory. The latest verified observation beats any document.

## Live state is derived, never remembered

Every run, before touching anything:

```sh
~/.local/bin/omp-voice-controller status
curl -fsS http://127.0.0.1:17493/health
```

- The controller pid, the OMP session pid, the bridge port, and every `afplay` pid change. A pid written in a historical row may be dead. Re-derive all of them from `status` and `~/.local/state/omp-voice/sessions/<pid>.json`.
- The OMP bridge port is ephemeral and is read from the session registry. Port 17494 is a legacy listener; never assume it is live (VA-OMP-001, VA-OMP-003). If a registry file is missing, the controller falls back to the one loopback listener only when `/status` names the same pid.
- If VoiceBox `/health` is unreachable, recovery follows `docs/testing/VOICEBOX-SERVICE-RUNBOOK.md`, and nothing else. A GUI process, a server process, a listening socket, and an HTTP response are four different facts; record each. Never exec `voicebox-server` by hand and never `open -a VoiceBox` while the GUI is already running — a running GUI has already used its one production `start_server`. The only supported recovery is a human quitting and reopening VoiceBox; an agent does not kill the GUI. If still down, write a `VOICEBOX-DOWN` row with the exact error, the controller pid, the status state, and result `blocked`. The controller logs a failed health check at most once per 5 s and stops tier changes; it must not poll every mic frame.
- If the bridge `/status` is unreachable on the registry port, write `BRIDGE-DOWN` as blocked, stop delivery tests, and do not restart the user's OMP session.

## Safety rules (override everything else)

1. Never kill, restart, or signal the user's OMP session or the running controller. Never submit a test prompt into the user's session. Never send test prompts to a user-owned bridge. Integration delivery goes only through an isolated session: `scripts/isolated_session.py` with `OMP_VOICE_BRIDGE_ONLY` and `OMP_VOICE_PLAYBACK_PID`; the harness refuses protected session ports (VA-INT-AUTO-006).
2. The running controller owns the MacBook Pro Microphone. Never open a second microphone source beside it. A physical acoustic test is allowed only after an explicit ownership handoff and a verified free device; otherwise run the fixture probe instead.
3. Never kill a process because its name looks familiar, and never trust a pid recorded in a checkpoint.
4. Never claim a test passed without running it. Never claim physical, acoustic, or service-integration results from a fixture, a synthetic signal, or a mock. A failed test is evidence; write it down.
5. Never lower the 0.50 wake threshold. Do not restore a 0.35 TTS wake open.
6. Do not commit, push, or create a release.

## Validation levels

Every checkpoint row states the level it actually achieved.

1. **Unit** — grammar, state transitions, frame handling, queue behavior, playback lifecycle. Fast and deterministic.
2. **Fixture-fed controller integration** — `FixtureAudioSource` deterministic PCM through the real `handle_captured_frame` path: wake detection, VAD, Whisper, classification, state transitions. Never inject a transcript directly as a replacement for audio. The fixture never opens the microphone.
3. **Local service integration** — real Handy, real VoiceBox, an isolated `omp -p` bridge, real `afplay`. Mocks in isolated tests must not be called service integration.
4. **Physical acoustic** — actual speaker output, actual microphone capture, verified exclusive ownership, recorded conditions, measured behavior, intelligibility checked by transcription. A fixture test cannot satisfy this level.
5. **Extended reliability** — long runs, consecutive conversations, repeated interruptions, service restart and recovery, queue saturation, playback failure, memory growth, stale session cleanup. A short test cannot satisfy this level.

## One iteration

1. Read the checkpoint and the catalogue. Pick the first `pending` or `fail` row, or the single highest-priority genuine gap. Do not invent work. Do not rerun a `pass` row unless a code change invalidated it. Do not redo VA-INT-AUTO-040 or VA-INT-AUTO-041 without a specific regression or a stronger acceptance criterion.
2. Write a short plan before editing: problem, evidence, root-cause hypothesis, relevant files, proposed change, risks, regression tests, acceptance criteria.
3. Reproduce deterministically. The harnesses already exist: `scripts/run_aec_fixture_probe.py`, `scripts/run_double_talk_probe.py`, `scripts/run_repeat_turn_probe.py`, `scripts/run_render_recovery_probe.py`, `scripts/run_interrupt_probe.py`, and `tests/`. Do not create `scripts/voice_ralph_check.py`; that instruction is obsolete. If reproduction is impossible, say why and name the missing observability instead of guessing the root cause.
4. Implement the smallest change that addresses the demonstrated problem. Preserve public interfaces unless the change is documented. No unrelated refactoring, no new dependencies without justification.
5. Verify: the focused test, then `~/.local/share/omp-voice/venv/bin/python -m pytest tests/ -q` and `node --experimental-strip-types --test tests/match_command.test.ts tests/playback-state.test.ts tests/speech-queue.test.ts`. Inspect exit codes, the diff, runtime logs, state transitions, and resource cleanup.
6. State which processes actually loaded the change. The running controller pid and the running OMP extension keep the old code until they restart or reload; a Level 1 or Level 2 pass is not live behavior. Every checkpoint row must say whether the live processes were restarted, and the list of tested-but-unloaded fixes lives in `HANDY-SCENARIO-CHECKPOINT.md` under "Tested but not loaded into running processes".
7. Review your own change: does the test exercise the real failure path, could it pass while broken, did the fix create a race or a leak, did it weaken an existing test?
8. Record in the checkpoint: date/time, task id, problem, root cause (or explicit uncertainty), changed files, tests executed, exact results, validation level, latency or measured metrics, limitations, remaining work, next recommended task. Never erase historical results.
9. Stop. Do not start a second unrelated implementation because context remains.

## Wake-during-playback contract

- Only the controller's own TTS slot (`tts-playing/<pid>.json`) counts as our voice. A foreign `afplay` does not suppress the wake (G9 pass, 00:04).
- A wake word during our own playback is ignored; it must not open Handy (D3).
- Only a whole-phrase `stop` or a hold-on phrase barges: it stops VoiceBox playback and never opens a dictation session (D4, G8, H2, H3, VA-INT-AUTO-041: `stop_playback` 0.589 s after the hold). A sentence that merely ends in `stop` does not stop playback.
- Stopping playback and opening dictation are separate actions. A test that opens a second dictation session when a stop is heard is a fail, even if the clip stops.

## AEC acceptance criteria

Synthetic work (VA-AEC-001 through VA-AEC-008, VA-OBS-001) establishes: the WebRTC desktop canceller pinned at `aec-audio-processing==1.0.0`, 16 kHz render reference fed before VAD, stereo downmix, cursor on the grid, multi-path cancellation near 38 dB, near-end energy survival, and residual published to `status.json` as `aec_echo_db` / `aec_blocks`.

Level 4 acceptance requires all of the following, measured on the live controller with an ownership lock on the microphone:

- ERLE measured through the real speaker-to-microphone path, not planted taps.
- No wake and no barge from echo alone across a full spoken reply.
- Near-end speech transcribed verbatim during double-talk, including quiet user speech over loud playback. Energy preservation is not intelligibility.
- "Stop." and a wake phrase during playback interrupt, with measured stop latency.
- Render reference stays aligned with actual output across pause, resume, clip change, and `afplay -r` rate changes; drift, if any, is measured, not assumed.

Until a row records all five at Level 4, the AEC is not production validated. VA-INT-001 remains BLOCKED. Note a known unquantified risk: the render cursor advances from wall clock times the playback rate, which is not the audio-device sample clock (Priority A); the physical test must measure that drift.

## Stop condition

When no `pending` or `fail` row remains and no open Level 1–4 gap exists, write `IMPROVEMENT LOOP IDLE` in `HANDY-SCENARIO-CHECKPOINT.md` and create `.ralph-voice-loop-idle`. VA-INT-001 and the physical AEC acceptance are open gaps: the loop is not idle while physical acceptance is unrun. If genuinely blocked by a service you cannot start, write a `blocked` row with the exact reason and say clearly what Akshay must restart before creating the idle marker. Do not invent rows to keep the loop alive.

## Checkpoint write format

```text
result: pass | fail | blocked
heard: <timestamp, controller log line, status state, latency numbers>
fix: <what changed, or why no fix was needed>
level: <1-5 actually achieved>
next: <next highest-priority gap, or none>
```
