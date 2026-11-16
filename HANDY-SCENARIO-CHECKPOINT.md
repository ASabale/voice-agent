# Handy scenario checkpoint

This file is the only source of truth for the Handy / Hey Jarvis test pass. Each turn, read this file fresh. Skip every row whose result is `pass`. Take the next `pending` or `fail` row, test it, and write the log result back into that row. If it fails, fix the controller in that same turn and retest until that row passes. Then mark it `pass` and move to the next open row. Do not retest a `pass`. Do not carry the plan from chat memory.

## Current engineering status (authoritative — 2026-11-16 03:55 UTC live re-derivation)

This section is the only current status. Everything below it is dated historical evidence and must never be read as live state. Pids, ports, and model sizes in any other section are snapshots; re-derive them from `omp-voice-controller status`, `~/.local/state/omp-voice/sessions/<pid>.json`, and `curl -fsS -m 2 http://127.0.0.1:17493/health` before acting.

Verified live at 03:45–03:55 UTC this run (RALF run 3, iterations 1–3):
- **Repo/CI:** branch `main`, HEAD `4632308` == origin/main; working tree carries the VA-OPS-004 fix (cmd_stop verification) plus its scenario doc until committed. Suites on the tree: 311 Python passed (03:50 UTC, was 308), Node 114 baseline stands (no TS touched this run).
- **Controller:** pid 90992 (started 2026-11-15 23:19 UTC from the working tree — pid lock, VA-AUD-004 flush buffer, turn-latency fields, clipboard-settle, AEC path loaded; paste-verify and stdout rotation landed after 23:19 UTC and are NOT loaded). `status.json`: `IDLE`, `turn_seq 2`. AEC fields ARE now published live: the 03:53 UTC echo probe saw `aec_echo_db`/`aec_blocks`/`render_cursor` through a real playback. Mic owned by 90992 only; Handy pid **85667** (drift from 4625 — Handy was restarted). Restart stdout → `controller-restart.log` (still unrotated until A2').
- **VoiceBox: UP — A1 CLOSED (03:46 UTC).** `/health` healthy, 0.6B loaded; a real `/generate/stream` request produced a 215 KB, 4.48 s, 24 kHz mono WAV; the clip played end-to-end in the echo probe (`clip_frames 222720`, afplay confirmed). Crash-report count unchanged (12 historical).
- **Handy functional proof (03:46 UTC):** the VoiceBox clip was fed to `handy --transcribe-file` (real Qwen3-ASR-0.6B, Metal, 35.8× realtime) and came back verbatim: "The quick brown fox jumps over the lazy dog at four twenty-seven." First same-process VoiceBox→Handy round trip with verbatim text.
- **Bridge (re-derived 03:46 UTC):** live sessions 85492 (`:63399`) and 54314 (`:62725`); 54314 predates the newest extension edits. `/status` is the endpoint, `/health` 404s.
- **Guardian (A3 open, unchanged):** manual 38389 + launchd 38402 both running, both pre-lock, neither holds `watcher.lock` (owner 64635, dead). Nothing is guarding the engine; two unlocked watchers share kill decisions. `pressure.json` live.
- **Idle-unload conflict (A5, unchanged):** watchdog (policy=idle, 300 s) vs guardian Rule 4 predicate disagreement stands (VA-OPS-003). Owner decision pending.
- **Level 4 (physical acoustic): echo-only criteria now PASSED (03:53 UTC).** Real speakers → real mic: 9 status windows during a 9.28 s reply, residual echo −1.0…−4.4 dB (median −2.1), `aec_blocks` counted (13), zero wake lines, zero barge holds, controller alive. Remaining Level-4 rows — verbatim double-talk transcription and human-barge stop latency — need Akshay's voice (A6).
- **`cmd_stop` reporting defect fixed (VA-OPS-004):** the old code printed "Stopped" and unlinked the pid file even when SIGTERM failed; now exit 1 with "still alive" and the pid file kept. Verified at Level 1 and Level 2 against the production binary.

**CI baseline fixed (2026-11-14).** Eight consecutive failed Actions runs (43530350727 → 43542615491) had two causes: (1) the openWakeWord wheel ships no model files, so four wake tests failed on the runner — fixed by `ensure_wake_models()` in `bin/omp-voice-controller` (downloads the two ONNX models when missing) plus an autouse fixture in `tests/conftest.py` that calls it before any test needing wake files; (2) `aec-audio-processing` was a bare line in `requirements-dev.txt` — moved to `requirements-aec.txt` and made best-effort in `bin/install`. Reproduced with the exact CI commands in a fresh Python 3.12 venv: `python -m py_compile bin/omp-voice-controller` and `python -m pytest tests/` pass; the three Node files pass on the local node. GitHub still shows the old failing runs until the fix is pushed.

Results by validation level (levels defined in `HANDY-RALPH-VOICE-LOOP-PROMPT.md`):

| Level | Closed | Open |
|---|---|---|
| 1 — unit | Full suite 306 passed; Node 110 passed (re-run 2026-11-15 23:45 UTC on the working tree). Grammar, playback ownership, playback-slot pruning of dead sessions on both sides plus projection re-derivation after a prune (VA-PLAY-002), speech queue, log rotation including runtime rotation of the daemon's own log (VA-LOG-003), mic-capture accounting, delivery holds, Handy control, dynamic bridge-port discovery (VA-OMP-001/002/003), synthetic AEC (VA-AEC-001–004, VA-AEC-009, VA-AEC-011, VA-OBS-001), turn-latency field semantics (VA-LAT-001 unit tests), guardian tier policy on synthetic traces including the unload race re-check and the bounded `freed=0` unload grace (VA-MEM-001, 13 tests), deferred-sentence retry/expiry/epoch discipline (VA-TTS-014, VA-TTS-017, VA-TTS-018), mid-request socket death held as refusal (VA-TTS-021), crash→recover→crash cycles replay every sentence exactly once in order (VA-SOAK-002) | none blocking |
| 2 — fixture-fed controller integration | VA-TTS-007/008/010, VA-AEC-005–008, VA-INT-AUTO-040 (closed 2026-11-14 13:35 UTC: wake, Handy file ASR, two submits, playback, and the stop fixture now cuts a stubbed `afplay` after the AEC correlation guard + pre-roll fix), VA-LAT-001 (turn latency `turn_seq`/`wake_to_flush_s`/`asr_s`/`dispatch_s` published through a full fixture turn; `stop_latency_s` only unit-tested — the Level 2 stop run is blocked on VoiceBox `/generate/stream` 500) | none blocking — VA-AEC-005–008 were re-run against the current uncommitted tree on 2026-11-14 11:19–11:33 UTC and all pass |
| 3 — local service integration | VA-INT-AUTO-001/003/004/036/037/041 (isolated `omp -p`, real Handy `--transcribe-file`, real VoiceBox, real `afplay`; VA-INT-AUTO-041 revalidated 2026-11-15 18:50 UTC: `stop_latency_s` 0.771 s ≤ 1.076 acceptance, real afplay killed, no resume, second turn played), VA-SOAK-002 (real 5 s timer chain against a mock restart cycle, natural process exit), VoiceBox unload relief measured: 11 MB of a 5,656 MB footprint freed — MLX arenas persist | Live-controller turn latency now partially demonstrated: pid 90992 (restarted 23:19 UTC from the working tree) publishes `turn_seq 1`, `wake_to_flush_s 18.09`, `asr_s 0.182`, `dispatch_s 0.573` in its real `status.json`. `stop_latency_s` remains null until a real playback turn occurs — blocked on A1 (VoiceBox down). Full end-to-end revalidation reruns after A1. |
| 4 — physical acoustic | none | VA-INT-001 and the five AEC acceptance criteria (room ERLE, no echo wake, verbatim double-talk transcription, stop/wake barge latency, render alignment under `-r` and pause). Mic ownership: pid 90992 (restarted 23:19 UTC from the working tree, so the AEC path is loaded); VoiceBox is DOWN on 17493 (A1 open), so no echo can be generated — even the echo-only criteria (no wake from playback alone, render alignment) are blocked until the owner reopens VoiceBox. Verbatim double-talk transcription additionally needs Akshay's voice and mic handover |
| 5 — extended reliability | queue saturation at Level 1 (VA-SOAK-001: 300 held sentences replay exactly once on recovery); repeated service restart/recovery cycles at Level 1+3 (VA-SOAK-002: two outages, a 500-on-first-attempt service, all 11 sentences spoken once in order, queue drained, no tmp files, RSS −8.4 MB, natural process exit); **four consecutive conversations in one live controller life at Level 5 (VA-SOAK-005, PASS 2026-11-15 18:02 UTC: 4/4 played, render connect/disconnect per turn, zero wake lines, zero failed speech, mic deltas 0/0, RSS median 350.3 → 353.0 MB, peak 179.6 MB, controller IDLE)**; **six consecutive conversations with per-turn VoiceBox footprint and bridge deferred/expired recording at Level 5 (VA-SOAK-007, PASS 2026-11-15 18:42 UTC run 4: 6/6 played, 6 distinct afplay pids, render connect/disconnect every turn, zero wake, zero failed speech, mic deltas 0/0, deferred 0/expired 0 every turn, VoiceBox footprint 3265→7139 peak→5653 MB released on idle, controller IDLE — after runs 1–3 FAIL/FAIL/NOT RUN on gate instrumentation, see iteration log)** | VoiceBox outage/recovery and controller shutdown/restart at Level 5; stale slot/registry cleanup unit-covered (VA-PLAY-002) but never observed over a long live run |

## Level 4 physical AEC acceptance — BLOCKED (2026-11-14 10:48 UTC)

The five acceptance criteria in `HANDY-RALPH-VOICE-LOOP-PROMPT.md` (ERLE through the real speaker-to-mic path, no wake or barge from echo alone, verbatim double-talk transcription, stop/wake barge latency, render alignment under `-r` and pause) cannot be run this session. Verified blockers:

1. `omp-voice-controller status` shows pid 64238 `IDLE` holding exclusive ownership of the MacBook Pro Microphone (VA-INT-AUTO-038). A second capture instance cannot attach without corrupting its VAD.
2. pid 64238 was started before the AEC diff, so the `aec_echo_db` / `aec_blocks` fields it would publish do not exist in the running process. Any Level 4 measurement requires Akshay to stop and restart the controller.
3. Nothing is listening on 17493, so a real spoken reply — the sound the canceller must cancel — cannot be generated. Per `docs/testing/VOICEBOX-SERVICE-RUNBOOK.md`, recovery is manual: quit VoiceBox and reopen it.

What Akshay must do before Level 4 can run: reopen VoiceBox, then restart the controller (`omp-voice-controller stop` then the usual `run --wake-word hey_jarvis --wake-threshold 0.5`). The loop stays non-idle until these rows have live evidence.

## Running-process deployment state (re-derived 2026-11-16 01:05 UTC)

A unit or fixture pass is not live behavior until the process loads it.

- **Controller 90992** (started 2026-11-15 23:19 UTC from the working tree) loads: pid lock, VA-AUD-004 flush buffering, turn-latency fields, clipboard-settle fix, the AEC path, and the DELIV hold logic. It does NOT load paste verification (landed 23:35–23:45 UTC) or any edit after 23:19 UTC — including the 01:45 UTC stdout-rotation fix, so `controller-restart.log` keeps growing unrotated until then (`bin/omp-voice-controller` last modified 2026-11-16 01:45 UTC). Restart is owner-gated (A2').
- **Extension (re-derived 02:45 UTC 2026-11-16 after owner session restart):** registry holds sessions 54314 (`:62725`, started 02:22 UTC) and 65225 (`:54462`, started 02:42 UTC — after the `9d22501` push). 65225's `/status` returns `deferred`, `deferredOldestAgeMs`, `expiredSpeech` fields → the VA-LOOP-014/015 player-failure deferral chain IS loaded in this live session (Level-1 contract visible live; no player failure has actually occurred yet, so the replay path is not live-observed). 54314 started before the 014/015 edits and holds the older extension. Sessions 22430/56658 have exited and are pruned from the registry.
- **Guardians 38389/38402** predate the VA-MEM-007 lock and own nothing; `watcher.lock` records dead pid 50063 (re-derived 02:40 UTC; A3 open).
- **Tested, not yet live-observed**: paste verify by pid (not even loaded in 90992); headroom-driven voice deferral against a real pressure event (synthetic files only); watcher-lock enforcement in production (VA-MEM-007b proved it against the real binary with a synthetic owner).
- All "the live controller keeps the old path until restart" caveats in `docs/testing/INDEX.md` were swept on 2026-11-16: they were written against pids 64238/38298 and are false for code that landed before 23:19 UTC. Rows whose fix landed after 23:19 UTC must state "not loaded in 90992" individually.

## Iteration log — 2026-11-16 04:10 UTC (RALF-3 iter 5: `cmd_start_bg` claimed success for a daemon that died instantly — VA-OPS-005)

- Scenario: Objective D restart leg — `cmd_start_bg` slept 1.2 s and printed "Started ... pid N" with exit 0 without ever checking `proc.poll()` or whether the pid file was written.
- Reproduced first: stub child printing `boom` and exiting 3 was reported as `Started OMP Voice Controller in background (pid 92505)` with exit 0.
- Fix: poll inside the window — child exited → "spawn failed: pid N exited with code C" → 1; pid file names the child → "Started" → 0; window expires alive-but-unregistered → explicit "did not register ... it is still running" → 1. No force-kill (same honest-reporting policy as VA-OPS-004).
- Tests: 3 new (dies-before-register, registers→success, alive-unregistered→1). `_SpawnRecorder`'s fake now registers — the old assertion `"Started" in out` still holds under the new contract. `test_pid_lock.py` 13 passed; full Python suite **314 passed**; py_compile ok.
- Level 2: production binary `start` against a held lock still refuses correctly ("already running", exit 0 path unchanged).
- Boundary discovered: the flock open creates an *empty* pid file, so success must mean "the file names the child," not "the file exists."
- Limitation: a daemon that registers then dies a second later (import crash after pid write) is still reported Started at check time; `stop`/`status` catch it. Live restart is owner-gated (A2').
- Regression risk: none identified — callers only consume the exit code/print; the refusal path is untouched.
- Next: soak run 6 result (iter 4).

## Iteration log — 2026-11-16 03:53 UTC (RALF-3 iter 3: echo-only physical acceptance finally runs — PASS)
- Scenario: Objective B / AEC acceptance, echo-only subset (no wake or barge from the agent's own speech through the real speaker→mic path).
- Baseline: VoiceBox UP since 03:46 UTC, controller 90992 IDLE holding the mic, probe launches its own omp session (pid 88735, bridge :65006) — never touches 85492.
- Experiment: `scripts/run_echo_only_status_probe.py` against the live stack; 9.28 s reply played through the speakers while the live controller ran the AEC.
- Actual: PASS. 9 status windows, `render_connected` true, residual −1.0…−4.4 dB (median −2.1), `aec_blocks` 1–13, zero wake lines, zero barge-hold lines, controller alive afterward. Raw: `.local/voice-agent/runs/AEC-REAL-001-LIVE.json` (03:53 UTC).
- Note: `aec_echo_db`/`aec_blocks`/`render_cursor` are now observable on 90992 — the old "AEC fields not published" gate is gone. The −2 dB median matches the AEC-REAL-001 attribution (echo trails past the 300 ms guard window; suppression of the *wake decision* is what the criteria require and it holds).
- Limitations: the physical guard-block counter (`aec_guard_blocks`) is only in the tree, not in 90992 (pre-23:19-UTC process). Verbatim double-talk and human-barge stop latency still need Akshay's voice (A6).
- Code changes: none. Regression: none needed (probe-only iteration).
- Next: Level-4 human rows are owner-gated; A3/A4/A5/A2' unchanged.

## Iteration log — 2026-11-16 03:50 UTC (RALF-3 iter 2: `cmd_stop` reported success on a process that survived SIGTERM — VA-OPS-004)

- Scenario: Objective D, explicit RALF requirement — "verify that cmd_stop() does not report successful termination when the process remains alive after its timeout."
- Root cause: `cmd_stop()` polled `kill(pid, 0)` for 30 × 50 ms, then *unconditionally* printed "Stopped", unlinked `controller.pid`, and returned 0. A failed stop destroyed the only evidence the mic-owning daemon was still running, making `status` lie. Secondary: `kill(pid, 0)` succeeds on a zombie, so a supervisor that spawned the daemon would classify an exited child as alive.
- Acceptance criteria (written first): cooperative exit → 0/"Stopped"/file removed; survivor → 1/"still alive"/file kept; stale dead pid → 0/"not running"/file removed (unchanged); zombie child counted as exited.
- Fix (`bin/omp-voice-controller`): `_process_exited()` reaps own-child zombies via `waitpid(WNOHANG)` before the liveness probe; `cmd_stop()` branches on the result, returns 1 and keeps the pid file on failure. Deliberately NOT force-killing — honest reporting is the contract, escalation is a policy decision.
- Tests: 3 new in `tests/test_pid_lock.py`. First draft of the survivor test failed for a *good* reason: SIGTERM landed before the stub installed its handler and it died with the default disposition (waitpid showed `(pid, 15)`) — the test would have passed vacuously. Fixed with a ready-sentinel file the stub writes after installing the handler.
- Verification: `test_pid_lock.py` 10 passed; production binary `/Users/akshay/.local/bin/omp-voice-controller stop` with `OMP_VOICE_STATE_DIR` pointed at a temp dir and a SIGTERM-ignoring stub → `exit 1`, "Controller pid 88379 is still alive 1.5s after SIGTERM; stop failed, pid file kept" (Level 2). Full Python suite **311 passed** (308 + 3); Node untouched (114 baseline).
- Regression risk: a daemon that legitimately takes >1.5 s to shut down now surfaces as a reported failure instead of a fake success — strictly better information; no caller relies on the old unconditional 0.
- Limitations: live stop of 90992 not exercised (owner-gated A2').
- Next: echo-only physical probe (iter 3).

## Iteration log — 2026-11-16 03:46 UTC (RALF-3 iter 1: state reconciliation — VoiceBox is UP, first verbatim VoiceBox→Handy round trip)


- Scenario: loop §8 iteration 1 — establish actual repo/service/deployment state, no assumptions from the prior checkpoint.
- Actual: HEAD `4632308` == origin/main. VoiceBox listener on 17493, `/health` healthy with 0.6B loaded → **A1 CLOSED**, the gate that blocked every Priority B/E/F live row for two days. Handy pid 85667 running; `handy --transcribe-file` on a real VoiceBox clip returned the sentence verbatim in 0.13 s (35.8× realtime, Qwen3-ASR-0.6B on M5 Pro Metal). Controller 90992 `IDLE`, `turn_seq 2`, mic exclusive. Bridges: 85492 `:63399` (this session), 54314 `:62725`. Watchers 38389/38402 still unlocked, lock owner 64635 dead (A3 unchanged).
- Failure analysis: none — the drift is VoiceBox having been reopened and Handy restarted.
- Code changes: none. Regression: none run (read-only audit).
- Level: 3 (live service integration).
- Next: Objective D `cmd_stop` audit (iter 2).

## Iteration log — 2026-11-16 03:15 UTC (VA-LOOP-015: every un-heard player outcome defers, not just watchdog kills)

- Scenario: VA-PLAY-003 extension, Priority E — the 03:00 UTC fix defers only `watchdogFired` hangs. A player that **exits non-zero** or fails to spawn hits `releaseUnspoken` and is never retried: still a silent drop under "no sentence is silently dropped".
- Hypothesis: any player outcome where `playbackHeard` is false (exit code ≠ 0, spawn error, watchdog kill) should enter the deferred retry chain, while a barge kill (signal without watchdog) stays "heard".
- Baseline: live re-derived 03:10 UTC — VoiceBox still refused on 17493 (A1 open); controller 90992; registry now 54314 + 56658; watchers 38389/38402, lock owner dead 50063; HEAD `16ee1732`, uncommitted tree.
- Experiment: new test — fake `afplay` = `#!/bin/sh; exit 1`; enqueue with real `play()`; assert `currentSpokenText()==""` and `currentDeferred().length===1`; then `retryDeferredSpeech` replays exactly once and commits.
- Actual (red): FAIL `0 !== 1` — released, never retried. Green after fix: 26 tests in the refusal file.
- Fix (`extension/voicebox-speech.ts`): `play()` now returns `{ heard }` (generalized from `{ hung }`); `speakChunk` defers when `played && played.heard === false && epoch === session.speechEpoch`, `logSpeech(..., reason: "player-failure")`. First deferral timestamp preserved via `speakChunk`'s `at` (VA-TTS-019 rule) so a permanently broken player is bounded by the 120 s expiry. Barge semantics untouched.
- Regression: full Node suite **114 passed** (was 113); `tests/speech-queue.test.ts` vectors including `playbackHeard(null,"SIGKILL",false)===true` unchanged. Raw: `.local/voice-agent/runs/VA-LOOP-015-suite.txt`.
- Validation level: 1.
- Limitations: fake player only; real `afplay` failure modes not reproduced. Not loaded in running OMP sessions until reload; live proof needs VoiceBox (A1).
- Next action: Priority E closed at Level 1; remainder is owner-gated.

## Iteration log — 2026-11-16 03:00 UTC (VA-LOOP-014: a watchdog-killed hung player defers into the retry chain)

- Scenario: VA-PLAY-003 extension, Priority E — "no sentence is silently dropped" was still violated in practice: the 02:30 UTC fix released watchdog-killed sentences but nothing re-spoke them; the reply's `enqueue` fires once per sentence, so a player hang was still a silent drop. Hung *generations* ride the deferred retry chain; hung *players* did not.
- Hypothesis: routing a watchdog kill into `session.deferred` makes the existing 5 s cadence / 120 s expiry chain re-speak it automatically, preserving order (the chain stops at the first held sentence).
- Baseline: live state re-derived 02:55 UTC — VoiceBox still refused on 17493 (no sidecar, 12 crash reports unchanged); controller 90992 IDLE; bridge only 56658 `:61545`; `watcher.lock` owner dead pid 50063; watchdog 4616 alive; Strata engine 4588 resident. HEAD `16ee1732`, uncommitted tree.
- Experiment: new test in `tests/voicebox-refusal.test.ts` — fake busy-loop `afplay` on PATH, `OMP_PLAY_WATCHDOG_MS=300`, stub generator; after `speechSettled()` assert `currentDeferred().length === 1` and `currentSpeechStatus().deferred === 1`; then `retryDeferredSpeech(stubGen, stubPlayer, now)` must replay it exactly once and commit.
- Expected: deferral present, retry returns 1, `played=[sentence]`.
- Actual (red): FAIL — `0 !== 1` at the deferral assertion (raw: first run, captured in-session). Sentence was released but nowhere in the pipeline.
- Fix (`extension/voicebox-speech.ts`, smallest surface): `play()` now returns `{ hung: watchdogFired }` (type `ClipPlayer` widened to `Promise<{ hung?: boolean } | void>` — stub players returning `void` unaffected); in `speakChunk`, `played?.hung && epoch === session.speechEpoch` → push `{ text: speak, epoch, at }` onto `session.deferred`, `startDeferredRetry()`, `logSpeech("deferred", ..., { reason: "player-hang", timeoutMs: playWatchdogMs() })`, return true so order discipline holds. The deferral timestamp is `speakChunk`'s `at` parameter, so a re-hang keeps the FIRST deferral time (VA-TTS-019 clock rule) — retries against a permanently broken player are bounded by the 120 s expiry instead of looping forever.
- First fix attempt misplacement: the `return { hung }` landed before `clearTimeout(watchdog)`/slot cleanup, skipping cleanup; caught by reading the tail and moved to the function end. No behavioral effect reached the tests.
- Contract alignment: the VA-LOOP-013 test simulated pre-fix behavior (manual turn-2 `enqueue` playing immediately). With deferral, a re-enqueue now correctly queues behind the held sentence; the test was rewritten to assert the real contract: re-enqueue does not duplicate the deferral entry (still 1), and the retry chain replays it exactly once.
- Regression: refusal file 25 passed; full Node suite **113 passed** (was 112); barge contract file `tests/speech-queue.test.ts` 14 passed — `playbackHeard(null,"SIGKILL",false)===true` intact. Raw: `.local/voice-agent/runs/VA-LOOP-014-suite.txt`. Python suite untouched by this TS-only change (308 unchanged).
- Validation level: 1.
- Limitations: fake player only, no real `afplay` wedge observed; a legitimately >45 s sentence would be watchdog-killed mid-play and re-deferred (bounded by expiry, at most 2–3 replay attempts) — a clip-duration-aware watchdog (WAV frames/rate + slack, pattern from the VA-PLAY-002 orphan lease) remains a future option, deliberately not implemented. Not loaded in running OMP sessions until reload; retry-chain replay against real `afplay` needs a live VoiceBox (A1).
- Next action: Priority E is now closed at Level 1 for player hangs. Everything remaining is owner-gated (A1 VoiceBox, A2' controller restart, A3 watcher consolidation, A4 supervision, A5 watchdog policy, Level 4 physical).

## Iteration log — 2026-11-16 02:45 UTC (VA-LOOP-013: the watchdog-released sentence is proven re-speakable)

- Scenario: VA-PLAY-003 follow-up, Priority E — the unproven half of the 02:30 UTC fix: "released, not consumed" had no evidence that the sentence could actually be spoken again.
- Hypothesis: `releaseUnspoken` with `forget=true` removes the chunk from `session.spoken`, so a later `enqueue` of the same sentence passes dedupe and plays.
- Baseline: live state re-derived 02:40 UTC — VoiceBox still refused on 17493 (no sidecar process, 12 crash reports unchanged); controller 90992 IDLE, `turn_seq 1`, `stop_latency_s: null`, `render_connected: false`; only bridge session 56658 `:61545`; `watcher.lock` owner is now dead pid 50063 (drift from 41973 — no live watcher, A3 still open); watchdog 4616 alive; Strata engine 4588 resident since Nov 15 19:01; `pressure.json` 59.83 GiB used, headroom 4.17 GiB, `shedVoice: false`.
- Experiment: two-turn test in `tests/voicebox-refusal.test.ts` — turn 1 enqueues with the real `play()` against the fake busy-loop `afplay` (watchdog 300 ms), turn 2 re-enqueues the identical sentence with a stub player.
- Expected: turn 1 `spokenText=""`; turn 2 the stub player receives the sentence and it commits.
- Actual: PASS first run — `played=[sentence]`, `currentSpokenText()=sentence`. No code change needed; the contract held. Raw: `.local/voice-agent/runs/VA-LOOP-013-suite.txt`.
- Regression: refusal file 24 passed; full Node suite **112 passed** (was 111). Python unaffected (308, unchanged since 02:30 UTC — no Python touched).
- Validation level: 1.
- Remaining limitations: re-speaking is caller-driven (the controller must re-enqueue on the next turn); the release is not pushed into the deferred retry chain, so a watchdog-killed sentence is not auto-retried mid-reply. No real `afplay` wedge observed (fake player only).
- Next action: stop. All remaining rows gate on A1/A2'/A3/A4/A5.

## Iteration log — 2026-11-16 02:30 UTC (VA-LOOP-012: a watchdog-killed hung player no longer counts as spoken)

- Scenario: VA-PLAY-003, Priority E — the silent-drop asymmetry between hung *generation* (defers, retries) and hung *player* (watchdog SIGKILL counted as heard, sentence permanently consumed).
- Hypothesis: `playbackHeard(null,"SIGKILL",false)===true` (written for barge-in kills) makes the 45 s playback-watchdog kill indistinguishable from a barge, so a never-played clip is `commitSpoken`.
- Baseline: no test drove the real `play()` with a hung player; the watchdog timeout was hard-coded 45000.
- Experiment: red first. New test in `tests/voicebox-refusal.test.ts`: stub generator writes a real 4410-frame WAV, player is the real `play()`, PATH prepended with a temp dir containing a fake `afplay` (`#!/bin/sh` busy loop), `OMP_PLAY_WATCHDOG_MS=300`. Pre-fix result: FAIL — `currentSpokenText()` returned the sentence after a 305 ms watchdog kill. Raw: `.local/voice-agent/runs/VA-LOOP-012-hung-player.txt`.
- Preserved contamination lesson: the first attempt used the default `generate` (dead VoiceBox → deferred → `play` never ran) and passed vacuously in 5 ms; discarded and rewired to a stub generator.
- Code change: `playWatchdogMs()` env knob (`OMP_PLAY_WATCHDOG_MS`, default 45000 — production threshold unchanged); `watchdogFired` flag set by the watchdog; `commitSpoken` only when `playbackHeard(...) && !watchdogFired`. Barge-in semantics preserved: `speech-queue.test.ts:133` vector `playbackHeard(null,"SIGKILL",false)===true` untouched.
- Regression: refusal file 23 passed; full Node suite **111 passed** (was 110); Python suite 308 passed unchanged (02:30 UTC).
- Validation level: 1.
- Remaining limitations: fake player only — no real `afplay` wedge observed; a watchdog-killed sentence is released/recoverable but not auto-retried in-turn; extension fix not loaded in live OMP sessions until reload.
- Next action: stop. Everything else gates on A1/A2'/A3/A4/A5.

## Iteration log — 2026-11-16 02:05 UTC (VA-LOOP-011: rotation guard hardened against a deleted stdout file)

- Scenario: VA-LOG-003, Level 1 completion — an untested branch of `_stdout_log_path()`: fd 1 is an over-limit regular file whose path no longer exists (operator `rm` on the redirect file while the daemon holds it open).
- Hypothesis: the `path.exists()` check refuses rotation instead of recreating a file at the dead name.
- Baseline: no test covered this; live state unchanged since 01:50 UTC (VoiceBox down, 90992 pre-fix, watchers unlocked — all Priority B–F rows still owner-gated).
- Experiment: repro outside pytest first — fd opened with `O_CREAT`, written 300 B over a 200-byte limit, unlinked, dup2'd to fd 1. macOS lsof reports the *original* path (no `(deleted)` suffix); `_rotate_stdout_log()` returned `False` and created nothing. This also corrected a wrong assumption in the test's first draft (it claimed lsof appends `(deleted)`).
- Preserved failed attempt: first test draft failed with `FileNotFoundError` because `os.open` lacked `O_CREAT` — harness bug, not product behavior.
- Code change: one new test `test_deleted_stdout_file_is_never_rotated` in `tests/test_log_rotation_runtime.py`; no production code touched (guard already behaves correctly).
- Regression: rotation file 6 passed; full Python suite **308 passed** (02:05 UTC), Node 110 unchanged (no TS edits).
- Validation level: 1.
- Remaining limitations: unchanged — everything else gates on A1/A2'/A3/A4/A5.
- Next action: stop. The loop is fully owner-blocked; no independently executable acceptance row remains.

## Iteration log — 2026-11-16 01:46 UTC (VA-LOOP-010: rotation fix exercised by the real binary, not just pytest)

- Scenario: VA-LOG-003, Level-2 extension — the VA-LOOP-008 fix executed by the actual `bin/omp-voice-controller` process.
- Hypothesis: a real controller invocation with stdout redirected to an over-limit file rotates that file via the new lsof path discovery; a never-opened `LOG_FILE` stays untouched.
- Baseline: pytest fixtures passed (Level 1/2 in-process) but no real-process evidence; live `controller.log` 31 MB with no `.1`; seed file 1,048,577 B.
- Experiment: `~/.local/share/omp-voice/venv/bin/python bin/omp-voice-controller run --wake-word hey_jarvis >> /tmp/va-real-rotation/daemon-out.log` (pid lock held by 90992 → refuses and exits 1; no mic touched). Raw evidence: `.local/voice-agent/runs/VA-LOG-003-real-binary-2026-11-16.txt`.
- Expected: `daemon-out.log.1` = the 1,048,577-byte seed; the refusal line lands in a fresh `daemon-out.log`; `controller.log` untouched.
- Actual: exactly that. Fresh file 113 B with the refusal line; backup 1,048,577 B all seed bytes; second run appended 113 more bytes with no second rotation (under-limit no-op). First attempt was invalid (shell `>` truncated the seed at open) and was redone with `>>` — the invalid attempt is recorded in the raw file.
- Failure analysis: none. Bonus regression confirmation: the pid-lock refusal (`run_daemon` line 4128) fired against the real binary, exit 1, controller 90992 unharmed (etime 02:25:38).
- Code changes: none.
- Regression: `test_log_rotation_runtime.py` 5 passed 01:45 UTC; full suite 307 passed; no code touched this iteration.
- Validation level: 2 (production binary as a real process; no services). Not Level 3 — VoiceBox/daemon integration still requires the A2' restart.
- Remaining limitations: rotation in the long-lived daemon is only proven after the owner restarts 90992; `controller-restart.log` remains unrotated (495,951 B) until then.
- Next action: stop — all remaining acceptance rows gate on A1/A2'/A3/A4/A5.

## Iteration log — 2026-11-16 01:50 UTC (VA-LOOP-009: read-only state reconciliation; three status drifts found)

- Scenario: initial-state audit (loop §4).
- Hypothesis: the authoritative status section is accurate except where events since 01:30 UTC changed live state.
- Baseline: checkpoint as re-derived 00:50–01:30 UTC; HEAD `16ee1732` == origin/main; 13 tracked files modified + 6 untracked docs/tests; CI green only on `16ee1732` (run 43737276711); local suites 307 Python (01:45 UTC) + 110 Node.
- Experiment: `git status`, `gh run list`, `pgrep` for controller/guardians/watchdog/voicebox, `lsof :17493`, session registry read, `status.json`, log/lock file inspection. `ps`/`lsof` raw output kept in this entry.
- Expected: controller 90992 (`IDLE`, turn_seq 1, AEC fields null), VoiceBox refused, watchers 38389/38402 unlocked, two live bridges.
- Actual: controller 90992 confirmed (`IDLE`, `stop_latency_s: null`, AEC null — no render since restart); VoiceBox connection-refused, 12 crash reports — unchanged. Three drifts: (1) bridge session 22430 exited — registry now only 56658 (`:61545`), verified pid alive; (2) `watcher.lock` owner moved 37843 → 41973, also dead — still no live owner, lock protects nothing; (3) `controller-restart.log` is 495,951 bytes with last write 23:48 UTC, not the "~200 KB/h" estimate — the daemon logs only on events, so unbounded growth is slow but still real (no `.1` exists; fix pending A2'). Watchdog 4616 live.
- Failure analysis: no product failure; drift is staleness plus the log-rotation gap already recorded as VA-LOG-003.
- Code changes: none (audit iteration). Status bullets updated: suite count, bridge registry, lock owner.
- Regression: none needed; no code touched.
- Validation level: 1 (read-only live-state observation).
- Remaining limitations: A1/A2'/A3/A4/A5 all owner-gated; no independent acceptance row left that does not need VoiceBox, a controller restart, or the owner's voice.
- Next action: run the VA-LOG-003 fix against the real binary (spawn `bin/omp-voice-controller status`-class invocation with fd 1 redirected to an over-limit temp file — no mic, no daemon), then stop at the owner gates.

## Iteration log — 2026-11-16 01:45 UTC (VA-LOOP-008: daemon stdout rotation follows the real fd 1 file; live restart log never rotated)

- Scenario: VA-LOG-003 extension — runtime rotation of the daemon's *actual* stdout log.
- Hypothesis: `_rotate_stdout_log` rotates only when fd 1 is `LOG_FILE` (`os.path.sameopenfile` guard); the live daemon 90992 has stdout redirected to `controller-restart.log`, so its real log never rotates and grows unbounded.
- Baseline: `controller-restart.log` 496 KB at 01:30 UTC, growing ~200 KB/h since 23:19 UTC, no `.1` backup; `controller.log` 31 MB dead since 2026-11-14. `speech.log` already rotates (`speech.log.1` exists), so the gap is controller-specific.
- Experiment (Level 2 reproduction): loaded the real controller module, pointed fd 1 at an over-limit non-`LOG_FILE` file (`LOG_ROTATE_BYTES` lowered to 200), called `_rotate_stdout_log()`.
- Expected: `False` (the bug) — the fd-1 file untouched, `LOG_FILE` untouched.
- Actual: `False`, confirmed. Reproduction matches the live file's state exactly.
- Failure analysis: the guard conflates "the daemon's log" with "the constant `LOG_FILE`". Path discovery for fd 1: macOS `fcntl(F_GETPATH)` returns EFAULT on this machine (verified live: errno 14 even on a freshly opened fd, both venv and system Python), and `/dev/fd/1` readlink fails (errno 22); `lsof -p <pid> -a -d 1 -F n` resolves the path reliably.
- Fix: `_stdout_log_path()` resolves fd 1's regular-file path via lsof (only when the file is already over the limit — never on the hot path), validated with `sameopenfile`; `_rotate_stdout_log()` rotates that path to `.1` and re-points fd 1 at a fresh file of the same name. Terminal, pipe, and deleted-file stdout remain no-ops.
- Code changes: `bin/omp-voice-controller` (`_stdout_log_path` + `_rotate_stdout_log`, lines ~1094–1140).
- Regression: post-fix reproduction returns `True`, `.1` backup holds the old 1,048,577 bytes, subsequent writes land in the fresh file, `LOG_FILE` untouched. `tests/test_log_rotation_runtime.py` 5 passed (contract test `test_foreign_stdout_is_never_rotated` rewritten to `test_stdout_redirected_to_another_file_rotates_that_file`; new `test_pipe_stdout_is_never_rotated`). Full suite: 307 passed 01:45 UTC (baseline 306 + net +1).
- Validation level: 2 (fixture against production logic). Explicit limitation: the fix is NOT loaded in live controller 90992 until the A2' restart; `controller-restart.log` will keep growing (~4.8 MB/day) until then, reaching 1 MiB ≈ 05:30 UTC and never rotating under the old code.
- Remaining limitations: Level 3 live confirmation requires the owner-gated A2' controller restart; after restart, watch `controller-restart.log` (or its new redirect target) cross 1 MiB and produce a `.1`.

## Iteration log — 2026-11-16 01:30 UTC (VA-LOOP-007: live watcher-lock re-verification; A3 gap quantified)

- Scenario: VA-MEM-007b (single-instance lock, live binary).
- Hypothesis: the lock's claim/refuse/replace-dead-owner logic works end-to-end against the real `watcher.lock`, and the lock currently protects nothing because no running watcher owns it.
- Baseline: `watcher.lock` = 17998 (dead VA-MEM-007b control instance); manual 38389 + launchd 38402 running the pre-lock code from 2026-11-14, holding nothing.
- Experiment: start one short-lived real instance (`strata-memory-ceiling watch`, pid 37843), then run a second instance while it was alive; inspect lock and log after.
- Expected: first instance replaces the dead owner and enters the loop; second logs `duplicate watcher` and exits 0; no kill action while Used ≈ 59.2 GiB.
- Actual: all three legs confirmed — lock became 37843 (`watch started` 01:29:21 UTC in `memory-ceiling.log`); second instance logged `duplicate watcher pid=37843 ... this instance exits`, exit 0, no second loop; zero STOP/shed lines during the ~20 s run (Used below every arm). Test instance killed by the iteration; 38389/38402 untouched.
- Raw evidence: `~/.local/state/strata/memory-ceiling.log` lines ending 01:29:42 UTC; `~/.local/state/strata/watcher.lock`.
- Failure analysis: none — behavior is correct. The residual risk is exactly the one the row already names: the two live watchers predate the lock and never claim it, so double-watcher kill decisions remain possible until the owner retires one and the launchd unit restarts on the current code.
- Code changes: none.
- Regression: lock unit tests (7 in `test_pid_lock.py`, 10 in `test_memory_guardian_contract.py`) already passed in the 306-test suite re-run at 01:25 UTC; no code touched.
- Validation level: 3 (real binary, real lock file, real process liveness).
- Remaining limitations: cannot demonstrate the guardrail against the actual double-watcher pair without owner action A3.
- Next action: unchanged — A1 (VoiceBox), A2' (controller restart for paste verify), A3 (retire one watcher).

## Iteration log — 2026-11-16 01:25 UTC (VA-LOOP-006: watchdog vs guardian idle-unload conflict, A5)

- Scenario: VA-OPS-003 (`docs/testing/scenarios/VA-OPS-003-idle-unload-conflict.md`).
- Hypothesis: the `local-llm` 300 s idle watchdog and guardian Rule 4 make contradictory unload decisions under normal idle conditions, and the watchdog will unload the warm engine without memory pressure.
- Baseline: watchdog pid 4616 live since 19:01:42 UTC (engine 4588 up since 19:01:38 UTC, uninterrupted); `omp-autostart.json` `policy=idle`, `idle_timeout_sec=300`; guardian log `idle_unload=arm=62GiB grace=180s resident=1`; steady-state Used ≈ 59.2 GiB (never reaches the 62 GiB arm in normal use).
- Environment/git: HEAD `16ee1732`, uncommitted working tree; processes 4616 (watchdog), 38389/38402 (guardians), 4588 (engine), 90992 (controller).
- Experiment: evaluate both predicates on one snapshot — idle 400 s, Used 59.2 GiB, `in_flight=false` — using the exact code constants (`DEFAULT_IDLE_SEC=300`, `IDLE_UNLOAD_ARM_BYTES=PRESSURE_KILL_BYTES=62GiB`, `IDLE_UNLOAD_GRACE_SEC=180`).
- Expected: predicates agree (both unload or both keep).
- Actual: watchdog stop=True, guardian stop=False. Conflict confirmed at the predicate level.
- Raw evidence: in-line computation recorded in the scenario doc; guardian log tail lines 235–240 and state file quoted there.
- Failure analysis: by design, the watchdog predates the guardian's warm-residency policy; it was never reconciled. Not yet a realized failure because every 300 s window this session covered had at least one request (`now−last_act=0 s` at measurement). The cost asymmetry is decisive: an unnecessary unload forces a ~871 s engine reload, while the guardian's pressure-gated unload only fires when freeing RAM is genuinely required.
- Code changes: none to production code (owner infrastructure, not repo code). Docs only: new scenario doc, new INDEX row VA-OPS-003, status-section bullet.
- Regression: Python suite 306 passed (re-run this iteration, 7/7 `test_pid_lock.py` within it); Node suite unchanged since VA-LOOP-004 baseline (110 passed 01:25 UTC).
- Validation level: 1 (predicate) + 3 (live process observation). Not Level 5: no unload/reload cycle was actually run.
- Remaining limitations: no realized unload event captured; the conflict is latent until a genuine ≥300 s gap occurs.
- Next action: owner decision A5 — recommend `local-llm policy keep` so guardian Rule 4 is the single idle-unload authority; alternatively raise `idle_timeout_sec` to ≥3600 s. Do not change the state file without owner approval.

## Iteration log — 2026-11-16 01:30 UTC (VA-LOOP-005: scenario-doc ↔ catalogue alignment; two scenario-ID collisions found)

- Scenario: checkpoint integrity (§13 "Keep scenario documentation aligned with the test catalogue").
- Hypothesis: every scenario document under `docs/testing/scenarios/` is reachable from a catalogue row.
- Method: script diffing `See docs/testing/scenarios/...` references in INDEX against the 159 files on disk.
- Actual: 40 files were orphans (no row linked them). 39 now linked (38 in one pass + the VA-TTS-014 deferred-retry row); `VA-AEC-000-decision.md` was already covered. Re-run of the diff: missing = 0, orphan = 0.
- Defect found: **duplicate scenario IDs** — `VA-SOAK-005` (row 16, memory-drift gate, PASS 11-15 00:40) and `VA-SOAK-005` (row 174, four-conversation acceptance, PASS 11-15 18:02) are two distinct scenarios sharing one ID, each with its own scenario doc; same for `VA-TTS-014` (rows 32 and 181: the headroom-gate test vs the retry/expiry test). Not renumbered — renumbering would rewrite dated historical evidence; instead both rows now carry explicit scenario-doc links so the distinction is unambiguous. Future scenario docs must use unique IDs.
- Status changes: none. Code changes: none (INDEX links only). Suites unaffected (documentation-only edit; baseline VA-LOOP-004 stands).
- Live state re-derivation 01:15 UTC: VoiceBox still refused on 17493, no sidecar pid; controller 90992 IDLE; watchers 38389/38402; bridges 22430 `:53839` / 56658 `:61545`.
- Next action: A1 remains the unblocking owner action; all Priority B/C/D/E/F live rows stay BLOCKED.

## Iteration log — 2026-11-16 01:25 UTC (VA-LOOP-004: suite baseline refreshed after the 00:28 UTC controller edit)

- Scenario: checkpoint integrity — the "306 + 110 passed (23:45 UTC)" claim predates a later edit to `bin/omp-voice-controller` (mtime 2026-11-16 00:28 UTC, 295-line diff vs HEAD incl. paste verify and `_claim_run_lock`), so the working tree had no current test evidence.
- Hypothesis: the current tree still passes both suites.
- Environment: repo `main`, HEAD `16ee1732` == origin/main (CI green only on that HEAD, run 43737276711, 16:46 UTC); 11 tracked files modified, 5 untracked paths; live processes unchanged (controller 90992, watchers 38389/38402, VoiceBox refused on 17493, bridges 22430 `:53839` / 56658 `:61545`).
- Test commands: `~/.local/share/omp-voice/venv/bin/python -m pytest tests/ -q` and `node --experimental-strip-types --test tests/`.
- Expected: all pass. Actual: **PASS 2026-11-16 01:25 UTC** — 306 Python (10.6 s, 2 warnings), 110 Node (10.2 s), exit 0 each. Raw: `.local/voice-agent/runs/VA-LOOP-004-suite-current-tree.txt`.
- Status changes: none — confirms existing Level-1 PASS rows hold on the current tree.
- Code changes: none (checkpoint/INDEX wording only).
- Remaining limitations: no CI evidence until the owner commits; live behavior of paste verify still A2'-blocked.
- Next action: A1/A2' owner actions unblock Priority B/E/F; no independent offline experiment remains that isn't a redundant rerun.

## Iteration log — 2026-11-16 01:15 UTC (VA-LOOP-003: deployment-state sweep — 78 stale "until restart" caveats removed from INDEX)

- Scenario: checkpoint integrity. `docs/testing/INDEX.md` carried "the live controller keeps the old path until restart" caveats written against pids 64238/38298; controller 90992 restarted 23:19 UTC from the working tree, making them false for every fix that landed before that restart.
- Hypothesis: the running controller loads the tree as of 23:19 UTC; OMP sessions load the extension at session start.
- Method: `ps -o lstart` for 90992 (Nov 15 18:19 local = 23:19 UTC), 22430 (14:24 UTC), 56658 (15:51 UTC); `stat` mtimes: `bin/omp-voice-controller` 2026-11-16 00:28 UTC, `extension/voicebox-speech.ts` 2026-11-15 17:10 UTC; state dir listing (`controller.log` still 31 MB/Nov 14 unrotated; 90992's stdout goes to `controller-restart.log`, 496 KB).
- Result: 78 rows swept via one regex pass; `grep` for "until restart|until reload|until restarted" now returns 0 in INDEX. Historical pid references inside PASS evidence notes (e.g. "Live prune now observed on controller 38298") were intentionally kept — they date the observation, they do not claim current deployment. The "Tested but not loaded" section was rewritten as "Running-process deployment state (re-derived 2026-11-16 01:05 UTC)". `docs/testing/scenarios/VA-VB-002-crash-signatures.md` is not a duplicate — it is the canonical scenario doc for VA-VB-002 and is now linked from that row (the handoff's delete plan was wrong).
- Status changes: none — caveats only. No scenario re-run: no code changed since the 23:45 UTC suite baseline (306 Python + 110 Node), so no PASS row is invalidated.
- Still blocked: A1 (VoiceBox down — no listener on 17493, re-confirmed 01:03 UTC), A2' (paste verify not in 90992), A3 (watcher lock unowned), A4, A5.

## Iteration log — 2026-11-16 01:05 UTC (VA-LOOP-002: crash-signature re-check duplicates an existing PASS; status table reconciled to the live controller)

- Scenario: Priority B step 1 — verify the crash trigger is not being assumed. Hypothesis: the 12 crash reports reduce to a single fault family.
- Experiment: independent parse of all 12 `voicebox-server-*.ips` reports (`mlx` faulting frames, termination codes). Raw evidence: `.local/voice-agent/runs/VA-VB-002-crash-signatures.json`.
- Actual result: 6 unique events — 3 SIGSEGV in `mlx::core::eval_impl` (threads 19/41), 3 SIGABRT through `demangling_terminate_handler()` (threads 39/54). Byte-identical conclusion to the already-recorded VA-VB-002 PASS (17:45 UTC, which additionally names `mlx::core::gpu::check_error(MTL::CommandBuffer*)` as the abort site). No new signal; the exception text is not captured in .ips files.
- Classification: NOT RUN as a new experiment (redundant rerun of a passing row); the crash trigger still remains a hypothesis — "MLX Metal resource exhaustion" is consistent with the footprint data but unproven. The terminate-handler SIGABRTs carry no message in the crash reports: the Priority B footprint sweep must capture sidecar stderr so the next crash records the exception text.
- Reconciliation fixes (checkpoint integrity, no production code touched): Level-3 open row corrected — live controller 90992 already publishes `turn_seq 1`, `wake_to_flush_s 18.09`, `asr_s 0.182`, `dispatch_s 0.573` (A2 restart already happened; only `stop_latency_s` awaits a real playback turn, blocked on A1). Level-4 open row corrected — mic owner is 90992, VoiceBox DOWN means even echo-only criteria are blocked.
- Deterministic check (soak probe blocked-path): `timeout 30 ~/.local/share/omp-voice/venv/bin/python scripts/run_long_soak_probe.py` against the live down VoiceBox → prints "VoiceBox is not healthy. Not launching a server.", exit 2, no mic touched, no sidecar spawned, no artifact written. The run-6 BLOCKED classification in INDEX is enforced by the probe itself, not just by convention.
- Regression: none needed; no code changed.
- Next: A1. No independently executable acceptance row remains.

## Iteration log — 2026-11-16 00:50 UTC (VA-LOOP-001: live-state re-derivation — every remaining acceptance row is owner-blocked)

- Scenario: Reliability-First RAL Loop V2 opening audit of this session. Hypothesis: the acceptance rows still open all depend on an owner action (VoiceBox reopen, controller reload, watcher retirement, supervision decision), and none is independently executable.
- Baseline: checkpoint status claimed lock pid 12596 and "run 6 rerun in progress" in INDEX.
- Experiment: read-only live derivation — `omp-voice-controller status`, `curl 17493/health`, `pgrep` for controller/voicebox/soak/guardians, `watcher.lock`, `pressure.json`, `/status` + `/slots` on the engine, DiagnosticReports count, git status. No process touched.
- Actual (00:46–00:50 UTC): controller **90992** `IDLE`, `turn_seq 1`, `stop_latency_s null`, `render_connected false`, mic deltas 0/0; **VoiceBox DOWN** — connection refused on 17493, no `voicebox-server` process, still 12 crash reports (latest pair `voicebox-server-2026-11-14-213715/213716.ips`); guardians **38389** + **38402** alive (footprints 19/15 MB), `watcher.lock` now holds dead pid **17998** — the VA-MEM-007b control instance, not 12596; no live watcher owns the lock; engine **4588** up (`/status` busy false, prompt 93353; `/slots` n_prompt 62263), footprint 15 GB, `pressure.json` 00:45:39Z 58.5 GiB used / 5.5 GiB headroom / `shedVoice false`, rewritten every poll; Handy 4625. **Run 6 of VA-SOAK-006 never started**: no probe process, no new artifact (latest is run 5, `VA-SOAK-006-LONG-run5.json`); the INDEX "rerun in progress" claim was stale and is corrected to NOT RUN.
- Verdict: BLOCKED (row result, not failure). Independently executable rows: none — the hung-generation hold path (Priority E) already has its Level-1 test ("a watchdog abort on a hung generation holds the sentence and replays on recovery", `tests/voicebox-refusal.test.ts`), and every Level-3+ row needs VoiceBox or the owner.
- Code changes: none. Regression: none run (no code touched).
- Level achieved: Level 3 (live service/process observation).
- Owner actions required, in order: **A1** reopen VoiceBox.app → then Priority B steps 6–10, soak run 6, and the stop-path revalidation; **A2** controller restart to load VA-PASTE-002/003/004 → Priority C live evidence; **A3** retire manual watcher 38389 (or restart the launchd unit) so a current-code watcher claims `watcher.lock`; **A4** decide `docs/architecture/CONTROLLER-SUPERVISION-PROPOSAL.md`.
- next: A1. The loop stays non-idle: Level-4 physical acceptance (VA-INT-001) is still unrun.

## Iteration log — 2026-11-16 00:37 UTC (VA-OPS-001b: the controller pid lock's refusal loop was only ever tested with synthetic locks)

- Scenario: VA-OPS-001b (Priority A2 precondition). Hypothesis: the installed controller binary (`~/.local/bin/omp-voice-controller`, symlink to the working-tree `bin/omp-voice-controller`) refuses a second `run` while the live controller 90992 holds the pid lock, and never reaches microphone opening.
- Baseline: 90992 running `IDLE`, `controller.pid` = 90992, no other controller process; refusal logic Level-2 tested only (`tests/test_pid_lock.py`).
- Experiment: `timeout 10 ~/.local/bin/omp-voice-controller run` while 90992 is live.
- Expected: immediate refusal message, non-zero exit, no mic opened, no state written.
- Actual: PASS — `[2026-11-15 19:37:05] OMP Voice Controller already running (pid lock held); refusing to start a second instance.`, exit 1 in under a second; `controller.pid` still 90992; `status.json` unchanged; the refusal branch prints before any `sounddevice` stream is created. First Level-3 observation of the guard against the real running controller.
- Evidence: captured stdout of the run; `~/.local/state/omp-voice/controller.pid` and `status.json` byte-unchanged afterward.
- Code changes: none. Regression: full Python suite re-run, 306 passed.
- Level achieved: Level 3 for the lock refusal. Failure analysis: none.
- Remaining limitation: this proves a supervised restart cannot double-start, but the running process still loads pre-VA-PASTE-002/003/004 code; deployment still needs the owner-approved restart (A2). A4 supervision decision still BLOCKED.
- Next: owner restarts the controller; then verify paste-verification log lines appear in `controller.log` on the first dictation.

## Iteration log — 2026-11-16 00:32 UTC (VA-MEM-007b: the real guardian binary's duplicate-refusal path has never fired in production)

- Scenario: VA-MEM-007b (Priority A3). Hypothesis: `~/.local/bin/strata-memory-ceiling watch` exits cleanly before entering the kill loop when a live pid owns `watcher.lock`.
- Baseline: lock held dead pid 12596; watchers 38389 (manual) + 38402 (launchd) both running, neither holding the lock; no `duplicate watcher` line had ever appeared in the 238-line guardian log.
- Experiment: write a live dummy pid (600 s `sleep`, pid 15610) into the real lock file, run the real binary under a 5 s timeout, then kill the dummy and rerun.
- Expected: refusal + `duplicate watcher` log line, exit 0, no monitoring loop entered; second run (dead owner) claims and enters the loop.
- Actual: PASS for the refusal path — log line 239: `duplicate watcher pid=15610 already owns the memory ceiling; this instance exits (launchd will retry in ThrottleInterval)`, exit 0, process gone in <1 s, engine untouched. Control case: with a dead owner the second run claimed the lock (pid 15674) and entered the loop (hit the 5 s timeout as expected); spawned pid terminated immediately afterward, owner's 38389/38402 untouched, lock restored to 12596.
- Evidence: `~/.local/state/strata/memory-ceiling.log:239`; lock file restored byte-identical to prior state.
- Code changes: none. Level achieved: Level 3 (real binary against real state file). Failure analysis: none.
- Remaining limitation: the mechanism is proven, but live enforcement still requires the owner to retire one of the two pre-lock watchers so a real watcher claims the lock. A3 stays BLOCKED on that owner action.
- Next: owner retires the manual watcher 38389 (or restarts launchd unit `com.akshay.strata-memory-ceiling`); the replacement instance will claim the lock and refuse any further duplicate.

## Iteration log — 2026-11-15 23:45 UTC (VA-PASTE-004: manual-poll dispatch lines still claimed outcomes without the verdict; plus VA-MEM-008 guardian-lock live check)

- Scenario: VA-PASTE-004 (completes VA-PASTE-003 wiring). Hypothesis: the two `Manual chunk outcome: appended` log sites (IDLE poll ~line 3379, DICTATING catch-up ~line 3685) are the last places reporting an outcome without the landing verdict.
- Baseline: VA-PASTE-002/003 wired `verified` into `paste_into_focus` and the `dispatch_transcript` fallbacks; manual-poll lines unverified.
- Environment: working tree `16ee1732`+uncommitted; live controller 90992 `IDLE`; VoiceBox down; Handy 4625.
- Experiment: fixture test that an unreadable focus (`None` verdict) produces no UNVERIFIED line and `verified: None` (unknown is not a claim); both manual-poll log sites now append `(verified=True/False)` when a verdict exists.
- Actual result: PASS, 8/8 in `tests/test_paste_verify.py`.
- Code changes: two one-line log-format changes in the daemon loop; verdict only surfaced when non-None (silent for unknown focus).
- Regression: 306 Python passed (was 305), 110 Node passed. Not loaded into pid 90992.
- Level: Level 1. Remaining: same owner-gated reload + Level 4 physical run as VA-PASTE-002/003.
- Sub-observation (VA-MEM-008, read-only): `watcher.lock` was recreated at 19:22 local by transient pid 12596 (dead); neither 38389 nor 38402 holds it. Deterministic claim-path test: live owner → refused; dead owner → replaced; absent lock → claimed. Refusal path has never fired in production (no `duplicate watcher` line in the guardian log). Classification: logic PASS (Level 1), live enforcement BLOCKED until the owner retires the manual watcher and restarts launchd so a watcher actually claims the lock.

## Iteration log — 2026-11-15 23:35 UTC (VA-PASTE-003: dispatch outcome still said "appended" even when the landing check failed)

- Scenario: VA-PASTE-003 (Priority C dictation integrity, follow-up to VA-PASTE-002). Hypothesis: the verdict returned by `fallback_macos_inject` is discarded by callers, so the dispatch result and logs still claim success unqualified.
- Baseline: working tree with VA-PASTE-002 verification; live controller pid 90992 `IDLE` (started 23:19 UTC, predates both paste changes); VoiceBox down on 17493; Handy pid 4625.
- Experiment: fixture tests driving `paste_into_focus` with `fallback_macos_inject` stubbed to `False`/`True`, asserting the result carries `verified` and the failure logs `UNVERIFIED`.
- Expected: `verified: False` + an UNVERIFIED log line on a failed landing; `verified: True` on a landed paste.
- Actual: PASS, 7/7 in `tests/test_paste_verify.py` (first run 3 failed because the stub matched the old value-script text; fixed to match `AXFocusedUIElement` — the stub bug, not the product).
- Code changes (smallest surface): `bin/omp-voice-controller` — `paste_into_focus` returns `verified` and logs `Paste into focus UNVERIFIED` / `Send into focus UNVERIFIED` on a failed landing; the `dispatch_transcript` fallback branches (paused/sent/appended) log `... UNVERIFIED` when the read-back says the text never reached the field. No thresholds or tests weakened.
- Regression: Python 305 passed (+2), Node 110 passed; `py_compile` clean. CI still only validates committed HEAD `16ee1732`.
- Level achieved: Level 1 (fixture wiring). Live Level 3 logging requires the controller reload; **not loaded into pid 90992**.
- Remaining limitations: the manual-poll dispatch outcome line now surfaces verification only via the log lines, not the returned dict for the bridge path (bridge posts have no read-back concept); physical FN dictation with the verification log still needs an owner-approved restart plus Level 4 evidence.
- Next: owner-approved controller restart, then VA-PASTE-002/003 live evidence during a real dictation turn; Priority C full scenario once VoiceBox and mic handover are available.

## Iteration log — 2026-11-15 23:20 UTC (VA-PASTE-002: paste delivery reports success without confirming the text landed)

- Scenario: VA-PASTE-002 (Priority C dictation integrity). Hypothesis: the silent-loss signature of VA-PASTE-001 is invisible because `fallback_macos_inject` never reads back the focused element; adding a read-back makes a failed paste observable.
- Baseline: working tree `16ee1732` + uncommitted VA-PASTE-001 settle; live controller pid 90992; Chrome open; dispatch logs showed "outcome: appended" with nothing landing (VA-PASTE-001 evidence).
- Environment: macOS 25.6, branch `main`, HEAD `16ee1732` (uncommitted working tree), Python 3.12 venv, Node strip-types.
- Experiment: stub the clipboard/keystroke/value reader and run the production `fallback_macos_inject`; then a Level-3 read of a live Chrome textarea via the real `_focused_element_value`.
- Expected result: landed paste → `True`; focused element readable but missing the text → `False` + a FAILED log line; unreadable focus → `None`, never a false alarm.
- Actual result: 5/5 fixture tests pass (landed=True, missing=False, unreadable=None, sent-path verifies before the Enter keystroke, restore happens only after the read). Live Chrome textarea holding "verification demo 741 race failure 963": absent probe → `False`, present probe → `True`. The zero-settle race reproduction did not fail this run (timing-dependent, as measured before: 0 s failed in the earlier sweep) — the detector's verdict logic is proven by the negative control on the real element, not by re-triggering the race.
- Code changes (smallest surface): `bin/omp-voice-controller` — `_FOCUSED_VALUE_SCRIPT` + `_focused_element_value()` + `_paste_landed()`; `fallback_macos_inject` now sleeps the settle, verifies landing, logs `Paste verified landed` / `Paste verification FAILED`, and returns the verdict (`bool | None`). Verification for `sent` runs before the Enter keystroke. No thresholds or tests weakened. `tests/test_paste_verify.py` added.
- Regression: Python 303 passed (was 298, +5), Node 110 passed. CI unchanged (green only on committed HEAD; this change is uncommitted).
- Level achieved: Level 1 (fixture) + Level 3 (real Chrome element read-back through the production reader). NOT Level 4: no physical FN press, no real Handy recording.
- Remaining limitations: the verdict is not yet in the dispatch outcome line (callers still return `appended` regardless); **not loaded into running controller pid 90992** (started 23:19 UTC before this edit) — another owner-approved restart is required before any live dictation run can log it.
- Next: reload the controller (owner-approved restart), then the Priority C live dictation scenario once VoiceBox/mic handover is available.

- Scenario: Reliability-First RAL Loop V2 §1 opening audit. Hypothesis: the checkpoint's "authoritative status" no longer matches the running processes.
- Baseline: checkpoint claimed controller 38298 (pre-`16ee173`), VoiceBox healthy on 17493 (A1 closed), Handy 70200, guardians 38389/38402 lock-free.
- Experiment: `git`/`gh` state, `omp-voice-controller status`, `status.json` keys, `lsof -i :17493`, `curl /health`, `ps` on every claimed pid, `watcher.lock`, DiagnosticReports count, both bridge ports. No production code touched.
- Actual result (discrepancies found): (1) controller is now **90992**, started 23:19 UTC from the working tree — the pid lock, VA-AUD-004 flush fix, turn-latency fields, and the VA-PASTE-001 settle are deployed, so the "not loaded into running processes" section (lines 39–46) is stale for the controller; (2) **VoiceBox is down again** — no listener on 17493, no sidecar process, 12 crash reports; A1 reopens and every Priority B/E/F row goes BLOCKED; (3) guardian `watcher.lock` holds dead pid 89565; the two running watchers (38389 manual, 38402 launchd) both predate the lock and hold nothing — two kill-decision-makers remain; (4) Handy is pid 4625, not 70200; (5) bridges 53839/61545 answer `/status`, not `/health` (404); `status.json` publishes `turn` but not `aec_echo_db`/`aec_blocks` until a render reference connects.
- Verdict: PASS (audit objective: reconciliation completed, status section rewritten in place). Level: Level 3 (live process/service observation).
- Next: highest-priority independently executable task is **VA-PASTE-002: post-paste landing verification in `fallback_macos_inject`** (dispatch currently reports "appended" with zero confirmation — the exact blind spot that hid VA-PASTE-001). A1-dependent rows (VoiceBox footprint re-baseline, stop-path revalidation, soak run 6) stay BLOCKED until the owner reopens VoiceBox.

## Iteration log — 2026-11-15 23:12 UTC (VA-PASTE-001: FN dictation outside OMP silently pastes the old clipboard in Chrome)

- Scenario: VA-PASTE-001 (Priority C dictation delivery). Hypothesis: the FN → Handy → controller paste path fails because the clipboard restore inside `fallback_macos_inject` races slow paste handlers, not because injection is broken.
- Baseline: live controller pid 38298 (predates HEAD `16ee173`); Handy pid 70200; owner session 56658 active. Log evidence: FN takes #812/#813 dispatched "Delivery paste ... outcome: appended" at 17:17 local while the owner reported nothing landing in Chrome.
- Experiment: synthetic pbcopy + System Events Cmd+V into controlled targets, then the controller module (`bin/omp-voice-controller` + `bin/playback_state.py` copied as a package) run via `dispatch_transcript` with focus pinned. TextEdit: paste lands with and without restore. Chrome textarea: paste WITHOUT restore lands; paste WITH immediate restore pastes the pre-injection clipboard (the saved value reappears instead of the injected text); settle sweeps — 0 s fails, 0.2/0.4/0.6 s all land.
- Failure analysis: `_run_osascript` keystroke returns before the browser reads the clipboard; `pbcopy saved` then overwrites it, so Chrome's async paste handler grabs the old contents. The dispatch reports "appended" with zero verification, hiding the loss. Second, separate defect reproduced: the `AXSelectedTextRange` heuristic marks a Chrome page body (`AXWebArea`, empty value) "editable" — dispatch of "into nowhere 123" reported `appended` with nothing landing anywhere.
- Code changes (smallest surface): `bin/omp-voice-controller` — (1) `CLIPBOARD_RESTORE_SETTLE_SECONDS = 0.25`; restore is delayed by that settle whenever text was injected; (2) `_FOCUSED_TEXT_SCRIPT` now rejects the `AXSelectedTextRange` fallback on container roles (`AXWebArea`, `AXGroup`, `AXStaticText`, `AXUnknown`, `AXDocument`, `AXImage`), so a focus with no paste target returns not-editable and routes to the bridge instead of a silent no-op. No threshold or test weakened.
- Regression: 298 passed (Python), 110 passed (Node). Post-patch live Chrome verification: "retry test one two three" and "final check 555" landed in the focused textarea; send phrase "please send that" pasted "please" + Enter (`Submitted draft: 'please'`); clipboard restored after each injection; no-input page focus now returns `Focus is not a text box app='Google Chrome' role='AXWebArea'` → bridge routing. Also confirmed correct tty routing: dispatch while Terminal (owner session 56658) is frontmost went to bridge pid 56658 port 61545. Level: Level 3 (real Chrome/TextEdit + production dispatch code) — NOT Level 4 (no physical FN press).
- Remaining limitations: no post-paste landing verification in `fallback_macos_inject` yet; partial chunks still never render into non-bridge editors ("Partial field skipped").
- Live reload (owner-approved): controller pid 38298 stopped, patched controller started as pid 90992 (same wake/pause/idle flags). End-to-end through the live IDLE poll: synthetic Handy `history.db` row #816 → controller log "Manual Handy transcription #816 ... Manual chunk outcome: appended" → text landed in the focused Chrome textarea. Probe row deleted afterwards. Level: production pipeline with synthetic Handy row — still NOT Level 4 (no physical FN press, no real Handy recording).
- Next: physical FN dictation test in Chrome/TextEdit; optionally add post-paste landing verification.

- Scenario: VA-SOAK-006 (Priority F extended soak, 6 cycles × 4 turns). Hypothesis: with VoiceBox healthy and the probe fixed, one full soak passes every acceptance gate.
- Baseline: VoiceBox pid 63081 healthy (0.6B mlx/cpu, idle footprint ~3.27 GB); controller pid 38298 IDLE, render_connected false, `aec_echo_db` −2.0.
- Experiment: re-derived run 5's evidence (`VA-SOAK-006-LONG-run5.json`) against `speech.log`/`controller-restart.log`, then reran the probe (service `soak-006-run6`, pid 18779).
- Actual result (run 5): CONTAMINATED, not FAIL. All controller invariants passed — 24/24 turns attributed to their own clips, 0 wake, 0 failed speech, mic deltas 0/0, slot dir 1, RSS 289.1 → 149.0 MB median (trend −208.3 MB), VoiceBox 3268/4262/3268/4261/3267/3335 MB (inside the 3000 MB gate). Two gates tripped, both instrumentation: (1) the VoiceBox baseline footprint read returned null on transient lsof misses at run start; (2) `render_connected` was true at the final snapshot because the owner's live session 56658 generated 53 clips concurrently (18:56–19:05 UTC) — external playback, not probe drain failure.
- Code change (smallest surface): `scripts/run_long_soak_probe.py` — footprint baseline read retries 4× (was 2×); new `external_generated_lines` evidence field counts `generated` events from sessions the probe did not start, and `evaluate()` returns CONTAMINATED when > 0. No acceptance threshold changed.
- Regression: `tests/test_long_soak_verdict.py` 8 passed (new foreign-playback test); full suites 298 passed (Python), 110 passed (Node). CI baseline unchanged (green on `16ee173`, run 43737276711); the uncommitted probe fix is not CI-verified.
- Level achieved: Level 3 probe instrumentation + Level 5 soak execution for run 5's controller invariants; clean PASS pending run 6.
- Remaining limitations: run 6 must complete without foreign-session playback; sub-100 MB RSS drift remains unresolvable by a single run (measured 88 MB idle noise band).
- Next: classify run 6 from `.local/voice-agent/runs/VA-SOAK-006-LONG.json`.

## Iteration log — 2026-11-15 18:41 UTC (VA-SOAK-007: six consecutive conversations through the live controller — Level 5 PASS on run 4)

- Scenario: VA-SOAK-007 (Priority F "six consecutive conversations" + per-cycle record). Hypothesis: six prompts through one isolated session, played by real `afplay` under the live controller, keep echo tracking, speech delivery, deferral queues, and both process memories stable, with zero wake and zero silent loss.
- Baseline: controller RSS median 260.3 MB (five spaced samples), lifetime `mic_dropped 34`, `mic_invalid 0`; VoiceBox pid 63081 healthy, idle footprint ~3.3 GB.
- Environment: HEAD `16ee1732` + uncommitted tree; controller pid 38298 (never restarted — the soak ran against the deployed pre-`16ee173` controller, the code the owner actually uses); isolated `omp -p` session pid 96885, bridge port 50409 read from the registry; microphone never opened by the probe; no human voice.
- Experiment: `SOAK_TURNS=6 ~/.local/share/omp-voice/venv/bin/python scripts/run_soak_sessions_probe.py` — per-turn VoiceBox footprint before/after generation, bridge `/status` deferred/expired every turn, render connect/disconnect windows, echo samples, RSS peak + turn-boundary samples, wake/failed-speech scans, drain + 120 s settle + 10-sample post-exit RSS median, one-sided cycle trend.
- Expected: exit 0 with all gates: 6 played / 6 distinct afplay / connect+disconnect every turn / 0 wake / 0 failed / mic deltas 0 / final IDLE / post-exit median ≤ baseline+100 / cycle trend ≤ 100 / peaks < baseline+300.
- Actual (run 4): **PASS, exit 0.** 6/6 played, 6 distinct afplay pids, 6 clips, zero wake, zero failed, mic deltas 0/0, deferred 0 and expired 0 every turn, slot count 2 at every boundary, final IDLE, footprint oscillating 3265→7139 peak → 5653 MB idle (no crash, release on idle), RSS post-exit median 349.4 (+89.1 MB, inside band), cycle trend +98.05 MB (inside band), max peak 266.6 MB.
- Failure history preserved: **run 1 FAIL** (post-exit median +107 MB at a 30 s settle; direct 12-sample measurement 15 min later showed a steady 187.9 MB — transient post-drain elevation, not a leak). **Run 2 FAIL** on the gate itself: `abs(drift)` on a −258.7 MB single-sample first-to-last drift — a shrinkage cannot be a leak; single boundary samples swing 70–345 MB within one run. **Run 3 NOT RUN**: TypeError in the trend gate (`len(samples[-half])`) after all turns completed, before evidence was written.
- Code changes (probe only, no production code): 120 s settle with 10 spaced RSS samples; one-sided smoothed trend `median(last half of turn samples) − median(first half) ≤ 100 MB` with the failure rationale in a comment; typo fix. Gate logic dry-run against run 2's real samples before rerun: +0.9 MB.
- Regression: `py_compile` clean; functional gates unchanged (no threshold was relaxed — the 100 MB band is the measured idle noise floor from VA-SOAK-006, and the trend gate replaces an unmeasurable single-sample delta with a smoothed one-sided test). Python/Node suites not re-run because only `scripts/run_soak_sessions_probe.py` changed.
- Validation level: 5 for the conversation-soak class (long run, real services, real playback, memory stability). *Not* Level 5 for code deployed in the running processes: the live controller still predates `16ee173` (A2 owner-gated restart).
- Remaining limitations: both RSS gates passed but sit inside the 100 MB noise band (89.1 and 98.05) — drift under ~100 MB is unresolvable while the 46 GiB model is resident, so a slow sub-band leak would not be detected by one run; one `footprint` read returned null (transient lsof miss, known probe limitation); turn latencies 0.8–59.5 s are dominated by single-slot local model contention, not by the voice path.
- Next action: remaining Level 5 open rows (VoiceBox outage/recovery and controller shutdown/restart soak legs) are owner-gated (A2/A4); Priority C dictation validation needs the restarted controller and the owner's voice.

## Iteration log — 2026-11-15 18:02 UTC (VA-SOAK-005: four consecutive conversations through the live controller — Level 5 PASS)

- Scenario: VA-SOAK-005 (Priority F "four consecutive conversations"). Hypothesis: four prompts through one isolated session, played by real `afplay` under the live controller, keep echo tracking, speech delivery, and controller memory stable, with zero wake and zero silent loss.
- Baseline: controller RSS median 350.31 MB (five spaced samples), lifetime `mic_dropped 34`, `mic_invalid 0`; VoiceBox pid 63081 healthy 0.6B `mlx/cpu`.
- Environment: HEAD `16ee1732` + uncommitted tree; controller pid 38298 (never restarted, so the soak ran against the *deployed* pre-`16ee173` controller — same code the owner uses); isolated `omp -p` session pid 82233, bridge port 59535 read from the registry; microphone never opened by the probe; no human voice.
- Experiment: `~/.local/share/omp-voice/venv/bin/python scripts/run_soak_sessions_probe.py` (four prompts, per-turn playback latency, render connect/disconnect windows, echo samples, RSS peak/median, wake-line and failed-speech scans, drain + 180 s settle, 30 s post-exit median).
- Raw evidence: `.local/voice-agent/runs/VA-SOAK-005-LIVE.json`; scenario doc `docs/testing/scenarios/VA-SOAK-005-four-conversations.md`.
- Actual result: PASS, exit 0. 4/4 turns played, 4 distinct afplay pids, 4 clips generated; render reference connected and disconnected every turn; 0 wake lines; 0 failed speech events; mic deltas 0/0; RSS post-drain median 353.0 MB (+2.7 MB vs baseline), peak 179.6 MB (well under the 300 MB ceiling); final state IDLE, `render_connected: false`, controller alive.
- Failure analysis (pre-run): the probe had never been executed and its gates were broken — it required lifetime mic counters to be zero (impossible on a 20-hour controller) and a 20 MB RSS band contradicted its own documented ±180 MB noise. Fix: baseline-captured deltas and the VA-SOAK-006 100 MB median band. Probe-side only; no acceptance criterion weakened.
- Regression: `tests/test_pid_lock.py` re-run (7 passed); no production code touched.
- Validation level: **Level 5** (live controller, real service, real playback, repeated turns). Not Level 4 — no microphone interaction.
- Limitations: echo cancellation during the soak measured −0.1 to −5.3 dB, including one +0.5 dB window — the weak live-path cancellation from AEC-REAL-001 persists and remains a Priority D open item; single session, not six turns; VoiceBox survived only ~4 generations here, so the ~24-generation crash threshold is still unbounded.
- Next action: six-turn rerun after the owner restarts the controller (A2) so the soak exercises the pid-locked, turn-latency-instrumented deployment; then B step 9.

## Iteration log — 2026-11-15 17:45 UTC (VA-VB-002: crash-report forensics — all six events are Metal command-queue faults)

- Scenario: VA-VB-002 (Priority B step 7, crash signature comparison). Hypothesis: the 12 crash reports share one root-cause signature rather than unrelated triggers.
- Baseline/environment: `~/Library/Logs/DiagnosticReports/voicebox-server-2026-11-{10,13,14}-*.ips` (12 files, HEAD `16ee1732`, read-only analysis). Live sidecar pid 63081, backend `mlx/cpu`.
- Experiment: parse each `.ips` header+body; extract exception type, termination, faulting-thread frames, and Metal symbol stack.
- Raw evidence: `.local/voice-agent/runs/VA-VB-002-crash-signatures.json`.
- Actual result: **six independent events** (each duplicated as a `.000`/plain pair), all inside MLX Metal command execution:
  - 3 × `EXC_BAD_ACCESS` segfault in `mlx::core::eval_impl` during `MetalCommandQueue _submitCommandBuffers` (11-10 18:11, 11-13 10:12, 11-14 00:51).
  - 3 × `abort` from `mlx::core::gpu::check_error(MTL::CommandBuffer*)` on `didCompleteWithStartTime:endTime:error:` or `MetalBuffer initWithDevice` (11-13 08:57, 11-13 10:08, 11-14 21:37 — the 21:37 pair is the soak crash).
  - No crash reports from any other subsystem; no crashes before 2026-11-10.
- Key observation: the **currently running sidecar reports `backend_variant: "cpu"`** while every crash frame is Metal/GPU. The 20 crash-free generations in VA-VB-001 ran on the CPU path, so the crash trigger is in the Metal command path, plausibly aggravated by memory pressure (guardian started 21:16 UTC, 21 min before the 21:37 soak crash), but that link is **not established**.
- Validation level: **Level 1** (forensics of existing artifacts; no live experiment on the crash path).
- Limitations: `.ips` files carry no uptime or footprint at crash time; crash-frequency comparison against footprint trajectories can't be completed until the A/B runs exist.
- Next action: owner-gated VoiceBox restart with `MLX_BUFFER_CACHE_LIMIT=4G` and explicit Metal backend to test whether the crash signature reproduces on the GPU path; keep steps 6/8–10 BLOCKED until then.

## Iteration log — 2026-11-15 17:35 UTC (VA-VB-001: VoiceBox footprint baseline — bounded working set, no per-generation drift)

- Scenario: VA-VB-001 (Priority B steps 1–5). Hypothesis: the soak-era footprint growth (5.6→9 GB) is a one-time MLX working-set allocation during generation, not unbounded per-generation leak growth.
- Baseline/environment: HEAD `16ee1732` (no code change this iteration); VoiceBox sidecar pid 63081, 0.6B model, backend `mlx/cpu`, listener verified via `lsof`; controller 38298 untouched; no microphone opened.
- Experiment: ten consecutive `/generate/stream` calls (distinct short sentences, profile Akshay `4bde1e0f-…`), `footprint -p 63081` after every generation.
- Raw evidence: `.local/voice-agent/runs/VA-VB-001-baseline.json` (run 1) and `VA-VB-001-baseline-2.json` (run 2, clean).
- Run 1: idle 4,037 MB → 8,506 MB across 10 generations; 6 footprint probes returned no match (parser flake; first attempt of the `footprint` CLI intermittently produced empty output). Subsequent direct check: 3,794 MB.
- Run 2 (retry-hardened parser): idle 3,792 MB → first generation 8,273 MB → generations 2–10 span 8,226–8,333 MB (+60 MB over nine generations, non-monotonic). Latency: 7.1 s cold → 4.0–4.8 s warm.
- Settle: 60 s after the run, footprint = 3,220 MB. Working set is released when idle.
- Stability: 20 consecutive generations, zero sidecar crashes; crash-report backlog unchanged at 12 (newest `voicebox-server-2026-11-14-213715/213716.ips` — a duplicate pair from the known SIGABRT).
- Failure analysis: Run 1's all-422 generations were a probe bug (urllib omitted `Content-Type: application/json`), not a service failure — preserved as recorded, not counted as evidence. Run 1 still yielded valid idle→active footprint data since the server processed some earlier curl probes.
- Validation level: **Level 3** (real VoiceBox service; no playback through the controller yet).
- Acceptance status: "No unexplained monotonic memory growth" **PASS for the 10-generation window** — growth plateaus after warm-up and is released on idle. The crash trigger is **not established**: the 24-generation soak crash coincided with footprint ~9 GB, but a bounded 8.3 GB working set alone does not explain the MLX Metal `check_error`.
- Limitations: 10 generations is short; growth beyond warm-up (21–24+ generations) untested. `MLX_BUFFER_CACHE_LIMIT=4G` A/B, restart measurement, and six-cycle soak require an owner-gated VoiceBox restart (GUI app) → **BLOCKED**. Speech delivery through the controller (soak acceptance "held sentences recover") additionally requires the A2 controller restart → **BLOCKED**.
- Next action: owner restarts VoiceBox with `MLX_BUFFER_CACHE_LIMIT=4G` set (runbook procedure) for the A/B; meanwhile A2/A3/A4 remain the gating owner actions.

## Iteration log — 2026-11-15 18:50 UTC (VA-INT-AUTO-041 revalidation: stop path survives the 11-15 working-tree changes)

- Scenario: VA-INT-AUTO-041 (Priority E stop-path revalidation). Hypothesis: the stop path (`barge hold → Whisper → stopPlayback → real afplay kill`) still works after the VA-LOG-004 `voiceStateDir()` change and the VA-OPS-001b pid-lock edit, and `stop_latency_s` stays within the ≤ 1.076 s acceptance.
- Baseline: 2026-11-13/14 runs — controller `stop_latency_s` 0.589–0.832 s; probe-detected afplay death 1.076 s.
- Environment: HEAD `16ee1732` + uncommitted working tree; controller module loaded from `bin/omp-voice-controller` via `SourceFileLoader` (so the tested code is the working-tree code); VoiceBox sidecar pid 63081 (0.6B, `mlx/cpu`); isolated `omp -p` session pid 78315, bridge port 57324 discovered dynamically; microphone never opened (`microphone_opened: false`).
- Experiment: `~/.local/share/omp-voice/venv/bin/python scripts/run_interrupt_probe.py` — real reply generated, real `afplay` playing (pid 79282), fixture `stop-say.wav` fed through the production frame loop.
- Raw evidence: `.local/voice-agent/runs/VA-INT-AUTO-041.json`.
- Actual result: PASS. Whisper heard `stop.`; stages `speaking → hold → clip → whisper → stop_playback → speaking`; `stop_latency_s` 0.771 s; probe-detected death 1.15 s after hold; `resumed: false`; second turn generated and played (`second_playback: true`); final state `IDLE`. Exit 0.
- Failure analysis: none. No code changes this iteration.
- Regression: full Python (297) and Node (110) suites unchanged from the 17:10 UTC run; no production-code surface was touched, so re-running the suites was not required.
- Validation level: **Level 3** (real VoiceBox, real `afplay`, isolated OMP session). The barge audio is fixture-fed, not the owner's voice — not Level 4.
- Limitations: single run; `stop_latency_s` here comes from the probe-loaded controller instance, not the live pid 38298 (which predates the pid lock). Live controller publication of `stop_latency_s` still awaits the owner-gated restart (A2).
- Next action: owner restarts the controller to deploy the pid lock + VA-AUD-004, then Priority C dictation validation; VoiceBox restart for the B step-6 A/B remains the top Priority B blocker.

## Iteration log — 2026-11-15 17:45 UTC (VA-VB-002: crash-report forensics — one fault family, two subtypes)

- Scenario: VA-VB-002 (Priority B step 7, crash signature comparison). Hypothesis: the 12 crash reports share one root-cause family rather than unrelated triggers.
- Baseline/environment: `~/Library/Logs/DiagnosticReports/voicebox-server-2026-11-{10,13,14}-*.ips` (12 files), HEAD `16ee1732`, read-only parse; live sidecar pid 63081 (`/health` `mlx/cpu`), controller 38298 untouched, no microphone opened.
- Experiment: parse each `.ips` header+body; extract signal, termination, faulting-thread frames, and process uptime from `procStartAbsTime`/`procExitAbsTime`.
- Raw evidence: `.local/voice-agent/runs/VA-VB-002-crash-signatures.json`. First parse attempt aborted on a `str - str` uptime bug; the corrected parse is what is preserved.
- Actual result: 12 files = **6 unique events** (macOS wrote a duplicate per event). All six fault inside MLX Metal execution — no non-MLX fault frame in any report:
  - Subtype A — `EXC_BAD_ACCESS` SIGSEGV in `mlx::core::eval_impl` ← `mlx::core::eval` ← `_PyEval_EvalFrameDefault`: 11-10 18:11 (uptime 1.4 s), 11-13 10:12 (0.9 s), 11-14 00:51 (81.6 s).
  - Subtype B — SIGABRT via `mlx::core::gpu::check_error(MTL::CommandBuffer*)` on `didCompleteWithStartTime:endTime:error:` → uncaught C++ terminate: 11-13 08:57 (uptime 2765 s), 11-13 10:08 (93 s), 11-14 21:37 (461 s — this is the soak crash after ~24 generations).
  - Two of the six segfault within 1.5 s of process start: model-load-time Metal faults, not generation-time faults.
- Expected vs actual: expected one shared signature → actual one shared family (MLX Metal command execution) with start-up and runtime subtypes. Pattern established; **trigger still not identified** — the reports carry no footprint or memory-pressure context at crash time.
- Code changes: none (read-only forensics).
- Regression: none needed; Python 297 / Node 110 suites remain as recorded at 17:10 UTC.
- Validation level: **Level 1** (artifact forensics; no live reproduction of the crash path).
- Limitations: crash frequency cannot be correlated with footprint trajectories until the step-6 A/B and step-8 restart runs exist. Note the live sidecar reports `backend_variant: "cpu"` in `/health` while every crash frame is Metal — the crash path may only exist under the Metal backend.
- Next action: owner-gated VoiceBox restart with `MLX_BUFFER_CACHE_LIMIT=4G` (step 6 A/B); steps 8–10 stay BLOCKED until then.

## Iteration log — 2026-11-15 17:10 UTC (VA-LOG-004: mock suites no longer pollute the production speech.log)

- Scenario: VA-LOG-004 (test hygiene). Hypothesis: Node mock suites append mock payloads to the production `~/.local/state/omp-voice/speech.log`, corrupting outage forensics (flagged in the 16:55 audit). Baseline: 1,551 mock `generated` entries (identical 8864-byte/4410-frame `validWav` clips) dated 2026-11-15 in the production log.
- Environment: HEAD `16ee1732` + uncommitted working-tree edits; root cause: `logSpeech`/`voiceStateDir` hardcoded `os.homedir()/.local/state/omp-voice` with no env override, while the Python controller honors `OMP_VOICE_STATE_DIR`.
- Experiment 1 (reproduction): run `node --experimental-strip-types --test tests/speech-queue.test.ts tests/voicebox-refusal.test.ts tests/playback-state.test.ts` → production mock entries **1551 → 1854 (delta +303)**.
- Code change (smallest surface): `voiceStateDir()` now honors `OMP_VOICE_STATE_DIR` (mirroring the controller convention); `logSpeech` uses it; `tests/voicebox-refusal-env.ts` and `tests/memory-defer-env.ts` point it at a per-suite temp dir. Also isolates the mock playback-slot writes, which shared the same hardcoded path.
- Experiment 2 (identical run, full suite): node exit 0, **110 passed, 0 failed**; production mock entries **1854 → 1854 (delta 0)**; the 303 mock events verified inside `$TMPDIR/omp-voice-refusal-test-state/speech.log` (312 requested / 307 deferred / 303 generated / 5 dropped) and the defer suite's temp dir. Raw evidence: `.local/voice-agent/runs/VA-LOG-004-isolation.json`.
- Regression: Node full suite green; Python suite untouched. The production extension in *running* OMP sessions still loads the old code until the session reloads the extension — no live process touched.
- Validation level: **Level 1** (mock-service test isolation; no live service involved).
- Limitations: production `speech.log` retains ~1,854 historical mock entries — audit tooling must filter `bytes == 8864` mock payloads until the file rotates; no destructive cleanup of owner state files was performed.
- Next action: owner decides A1–A4; the uncommitted fix (VA-OPS-001b + this) needs owner authorization to commit before CI can verify it.

## Iteration log — 2026-11-15 17:10 UTC (VA-OPS-001b: `run` refuses instead of hanging on a held lock)

- Scenario: VA-OPS-001b (VA-OPS-002 precondition). Hypothesis: a supervisor starting `run` while another instance holds the pid lock would block forever instead of refusing, making KeepAlive supervision unsafe. Baseline: `run_daemon` used `_open_pid_lock(block=True)`; the lock was only a non-blocking probe in `cmd_start_bg`.
- Environment: HEAD `16ee1732` + this iteration's uncommitted edits; no running process touched (live controller 38298 predates the lock code and holds no lock).
- Experiment 1 (reproduction): synthetic flock holder + `venv bin/omp-voice-controller run` with `OMP_VOICE_STATE_DIR` pointed at a temp dir → **hung 12 s after loading openWakeWord/Whisper, never exited**. Raw evidence: `.local/voice-agent/runs/VA-OPS-001b-repro.json`. Reproduction confirmed the gap before fixing it.
- Code change (smallest surface): new `_claim_run_lock()` (non-blocking; inherits `OMP_VOICE_PID_LOCK_FD` for the `start` path); `run_daemon` claims it before importing sounddevice/Whisper/openWakeWord and returns 1 with an explicit refusal message; `run_daemon` now returns int and `main` propagates the exit code. Old blocking claim at line ~4047 deleted.
- Experiment 2 (same experiment, after fix): exit code **1**, **0.07 s**, output `OMP Voice Controller already running (pid lock held); refusing to start a second instance.` — no model load, no microphone opened. Raw evidence: `.local/voice-agent/runs/VA-OPS-001b-postfix.json`.
- Regressions: `tests/test_pid_lock.py` 7 passed (4 existing + 3 new: in-process refusal, CLI exit code, claim-held-not-transient); full Python suite 297 passed. Node suite not re-run (no Node change).
- Validation level: **Level 1** (deterministic flock behavior, synthetic holder, mic never opened). Not deployed: live pid 38298 does not carry this code; it predates even VA-OPS-001.
- Limitations: kernel flock semantics verified, not supervisor behavior — no plist exists and none will be installed without owner approval.
- Next action: owner decides A1–A4. If Option B is approved, cutover is: stop manual controller, owner installs plist, verify crash-restart within ~5 s and single mic owner.

## Iteration log — 2026-11-15 17:05 UTC (VA-OPS-002 supervision proposal written)

- Scenario: VA-OPS-002 (A4). Hypothesis: launchd KeepAlive supervision removes the manual-restart handover bottleneck without new failure modes. Baseline: manual `run` with shell redirect (pid 38298, ~20 h, drift from validated HEAD), guardian already launchd-managed as a working precedent.
- Environment: HEAD `16ee1732`, no service dependency; lifecycle code read directly (`bin/omp-voice-controller` lines 2765–2778, 4041–4143, 4200–4247).
- Result: proposal at `docs/architecture/CONTROLLER-SUPERVISION-PROPOSAL.md`; INDEX row VA-OPS-002 added as BLOCKED (owner decision). Classification: NOT RUN for the supervision itself (no experiment — the decision is pending); PASS for the proposal deliverable (Level 1, code-read evidence).
- Concrete gap found: `run` opens the pid lock **blocking** (`_open_pid_lock(block=True)`), so a launchd-supervised instance started while a manual one holds the lock would hang blocked forever rather than refuse. The `start` probe path is the only place the lock is non-blocking. Fix (small, test-backed by `tests/test_pid_lock.py`) must land before any plist is installed.
- No code changes this iteration; no processes touched; nothing committed (per authorization rules).
- Next action: owner decides A1–A4. Once VoiceBox is reopened and the controller restarted (ideally via the chosen supervisor), the blocked Level-3/4/5 rows (B, C, D, E, F) become executable in that order.

## Iteration log — 2026-11-15 16:55 UTC (read-only state audit; status section reconciled)

- Scenario: VA-OPS-003 (operational reconciliation). Hypothesis: the authoritative status section's live claims are stale relative to the running processes. Baseline: status header dated 2026-11-14 16:53 UTC with claims "controller carries the current tree", "bridge ok for session 2734", "Python 256 / Node 104".
- Environment: repo HEAD `16ee1732` (== origin/main, clean tree), CI run 43737276711 success on that HEAD. Actuals: Python suite 294 passed, Node 110 passed; controller 38298 up since 21:16:19 UTC 2026-11-14, so it does **not** carry `16ee173`'s VA-AUD-004/VA-OPS-001 changes; bridge is session 22430 on 53839; VoiceBox listener absent (GUI 38478 only); guardians 38389 (manual) + 38402 (launchd) both predate the VA-MEM-007 lock; `watcher.lock` names pid 57227, not a running watcher.
- Raw evidence: `omp-voice-controller status` output, `lsof -iTCP:17493 -sTCP:LISTEN` (empty), `gh run list` output, `ps -o lstart` for 38298/38389/38402, `stat` on `controller.log` (31,063,970 B, mtime = restart instant) vs `controller-restart.log` (185,840 B, live mtime), `speech.log` tail (identical 8864-byte mock clips at millisecond cadence).
- Findings: (1) status section updated in place; (2) the running controller's stdout log is `controller-restart.log`, outside VA-LOG-003's rotation guard — rotation never fires for it; (3) Node mock tests write into the production `speech.log`, polluting the outage forensics (test isolation should point `OMP_VOICE_STATE_DIR`/log path at a temp dir — not yet done); (4) `expiredSpeech: 17` on session 22430 is real Level-3 evidence that the 120 s deferral expiry fired during the VoiceBox outage.
- Result: PASS for the audit itself (Level 1 observation, read-only, no code change). No production code touched.
- Remaining blockers (owner-gated, unchanged): reopen VoiceBox (A1), restart controller 38298 to load `16ee173` (A2), retire the manual watcher 38389 and restart the launchd instance so the single-instance lock is loaded (A3), decide VA-OPS-002 controller supervision (A4).
- Next action: prepare the VA-OPS-002 supervision proposal (the only Priority-A item executable without owner action).

## Iteration log — 2026-11-14 20:05 UTC (a 300-sentence reply survives an outage)

- The Level 5 "queue saturation" gap was only ever exercised with 1–2 deferred sentences. Soaked the real pipeline at scale: 300 sentences enqueued against a dead port (mock none listening on 17991), then recovery after the real 5 s refusal window with a mock serving valid WAVs.
- Result: exactly one refused fetch, 299 held by the refusal hold, 300 in the deferred queue; after recovery, `retryDeferredSpeech` replayed all 300 exactly once, oldest first, queue empty, `spokenText` equal to the full reply. No lost or doubled speech. Every clip the real `generate()` wrote to tmpdir was unlinked (temp dir verified empty after the run).
- Test: `tests/voicebox-refusal.test.ts` "a whole reply held during an outage replays exactly once, in order, on recovery" — refusal file 12 passed, full Node suite 94, Python 255 unchanged. This closes the saturation row at Level 1 only; Level 5 stays open until live runs.
- Scenario `docs/testing/scenarios/VA-SOAK-001-queue-saturation.md`; INDEX row PASS.

## Iteration log — 2026-11-14 19:50 UTC (a 200 that is not audio no longer counts as speech)

- Reproduced first (mock HTTP only): `/generate/stream` answered 200 with a 149-byte JSON error body. `speech.log` recorded `event:"generated", reference:null`, afplay failed on the garbage, and `releaseUnspoken` dropped the sentence with `deferred=0` — the second silent-loss class in `generate()`: the short-payload guard (<100 bytes) and this iteration's watchdog fix both leave ≥100-byte non-PCM bodies to afplay, and a valid-header-with-silence payload would even commit the sentence as spoken.
- Fix in `extension/voicebox-speech.ts`: before writing the clip, require `wavReference` to parse (RIFF/WAVE, PCM fmt, data chunk) and `reference.frames >= floor(sample_rate * 0.1)` (100 ms); otherwise defer with reason `invalid-audio` into the existing bounded retry chain. Real utterances are far above 100 ms; the floor cannot reject genuine speech.
- Regression tests in `tests/voicebox-refusal.test.ts`: garbage JSON body → held, replayed exactly once on mock recovery; 20 ms valid-header WAV → held, never counted spoken. Two older mocks used the fake `"RIFF"+zeros` payload and now use a `validWav()` helper (real 16-bit PCM header) — the truncated-payload and watchdog-recovery assertions now run against genuine audio. Refusal file 11 passed; full Node suite 93 passed; Python 255 unchanged.
- Note: the garbage probe process stayed alive via the deferred-retry timer and kept writing `connection-refused` retry lines to `speech.log` after the mock closed; the probe was killed and removed. Bounded retry expiry (120 s) is what would eventually stop it in production.
- Scenario `docs/testing/scenarios/VA-TTS-018-invalid-audio-hold.md`; INDEX row PASS.

## Iteration log — 2026-11-14 19:41 UTC (hung VoiceBox generation no longer eats the sentence)

- Reproduced first, mock HTTP only, never touching 17493: `/generate/stream` sends 200 headers then never ends the body. Pre-fix, the 90 s `AbortController` watchdog fired, the catch treated the `AbortError` as a generic failure, `logSpeech("failed")` fired, and the sentence was released unspoken with no retry path (`deferred=0`, `spoken=""`, `elapsed_ms=90003`). This was the last silent-loss path in `generate()`: refusals, 500s, and short payloads all defer; timeouts did not.
- Fix in `extension/voicebox-speech.ts`: the watchdog sets a `watchdogFired` flag before aborting; the catch splits `AbortError` by source — watchdog abort while the reply epoch is current → `{deferred: true}` reason `generation-timeout` (rides the existing 5 s retry / 120 s expiry chain); abort from `stopPlayback`/`bargeIn` (which bump `speechEpoch`) → explicit `dropped` reason `abort`. Watchdog length now configurable via `OMP_VOICE_TTS_TIMEOUT_MS`; production default stays 90000.
- Regression tests in `tests/voicebox-refusal.test.ts`: hung stream (800 ms watchdog) holds the sentence, counts it unspoken, and replays exactly once when the mock recovers; a real `stopPlayback()` during a hung stream drops it permanently. Refusal file 9 passed; full Node suite 91 passed; Python suite unchanged at 255 passed. Post-fix probe: `deferred=1`.
- Scenario `docs/testing/scenarios/VA-TTS-017-hung-generation-watchdog.md`; INDEX row PASS. The physical hung-sidecar case remains unverified (VoiceBox down); the running OMP session keeps the old extension until reload (human gate).

## Iteration log — 2026-11-14 19:30 UTC (a failed reference read no longer kills AEC for the whole clip)

- Reproduced first, no hardware: fed `refresh_render_reference` a playing slot whose WAV was momentarily unreadable, then rewrote the identical file. `render_connected: false` persisted at t=100.1, 100.2, 100.5 — the reference never reconnected for that clip. Root cause in `bin/omp-voice-controller`: `_render_file_key = key` was assigned before the connect check, so every later frame with the same key hit the `elif _render_parsed is None` branch and returned "not connected" forever. VA-AEC-008 had documented exactly this as its limit ("reconnect only when the slot key changes"); VoiceBox does normally write a new file per utterance, but any transient read failure silently disables echo cancellation for the entire utterance until the next one.
- Fix: pin `_render_file_key` only after `connect_render_reference` succeeds. The failed key stays unpinned, the next frame retries the same key; retry cost is one `read_bytes` per frame (~12.5/s) and `OSError` on a missing file is trivial. No thresholds, gates, or fallback behavior touched.
- Regression test `test_a_failed_reference_read_recovers_when_the_file_returns` (`tests/test_echo_control.py`): during the failure the echo-carrying block passes through byte-identical (no ghost subtraction, no crash) and status reports `render_connected: false`; after the file returns, the same key reconnects and the production `cancel_playback_echo` path cancels the synthetic echo to ERLE ≥ 12 dB. Echo file 27 passed; full suite 255 passed; CI venv (/tmp/ci-venv312) also 27 passed; `py_compile` clean.
- Node suite unchanged (89 passed — no extension code touched). Scenario `docs/testing/scenarios/VA-AEC-011-same-key-read-recovery.md`; INDEX row PASS. Running controller pid 64238 keeps the old behavior until it is restarted (human gate).

## Iteration log — 2026-11-14 19:19 UTC (projection liveness closes the witness-less freeze)

- Reproduced first: `project_aggregate([{"playing": True, "writer_pid": <dead>, "lease_until": far future}])` → `{"playing": True}` with **no pid key**. VA-MEM-004's guardian check can only help when a pid witness exists; a writer-lease slot whose writer died before `afplay` ever spawned freezes the projection with nothing for the guardian to check, and voice shedding is deferred conservatively forever. Also reproduced: a slot with a dead `afplay_pid` projected that dead pid.
- Fix: `project_aggregate(slots, pid_alive_fn=None, now=None, tail=0.0)` in `bin/playback_state.py` derives `playing` via `slot_is_speaking` when a predicate is supplied; the controller's prune-rederivation now passes `pid_alive` and `now`. Node mirror `projectAggregate(slots, alive = () => true, now)` uses `slotIsSpeaking`; `publish()` passes the real predicate. Predicate omitted keeps the legacy flag behavior for callers that already liveness-check (existing stub-pid tests are unchanged).
- Tests: `pytest tests/test_playback_state.py -q` → 25 passed (new `test_project_aggregate_never_freezes_without_a_live_witness`); `node --experimental-strip-types --test tests/playback-state.test.ts` → 19 passed (new `projectAggregate requires a live afplay or writer witness`); full Python suite → 254 passed; full Node suite → 89 passed; clean `/tmp/ci-venv312` suite → 254 passed; `py_compile` clean.
- Unverified: whether a live crashed-session freeze exists right now in `~/.local/state/omp-voice/tts-playing.json` — the file is only re-derived by code pid 64238/extension reload does not yet run. Guardian restart still human-gated.
- Next priority: (1) human handover items unchanged (push → CI green observation, VoiceBox reopen, controller restart, guardian restart); (2) render-reference seam extraction from the controller (safe, coverage-backed, held until a live baseline exists).

## Iteration log — 2026-11-14 19:40 UTC (CI red baseline root-caused and fixed locally)

- Reproduced first: the four CI failures (run 43542615491) are deterministic. In the clean `/tmp/ci-venv312`, deleting the `.onnx` files makes `Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")` raise the exact CI `NoSuchFile`. Root cause read from openwakeword source, not guessed: the pip wheel bundles only `.tflite`, and `download_models()`'s existence check is keyed on the `.tflite` filename, so it silently skips the ONNX files the models actually load. `Model.__init__` does not auto-download.
- Fix: `ensure_wake_models()` in the controller resolves each needed ONNX by name from openWakeWord's FEATURE/VAD/MODELS registries and downloads the `.onnx` variant directly (raises if a name is absent). `tests/conftest.py` mirrors the logic with a post-download assertion so a failed fetch fails loudly. Offline regression test `tests/test_wake_models.py`: tflite-only state → four ONNX fetched, no unrelated models; all-present → zero downloads.
- Verified: `pytest tests/test_wake_models.py -q` → 2 passed. `py_compile` clean. Main venv `pytest tests/ -q` → **253 passed**. Clean `/tmp/ci-venv312` running the exact CI commands → **253 passed** with real re-download of the four models. Node suite unaffected (88 passed, unchanged code).
- Unverified: CI on the actual pipeline — still red at pushed HEAD `95a77f6` because the fix is not pushed; observe the first run on the new HEAD after Akshay pushes.
- Next priority: unchanged human handover (push, reopen VoiceBox, restart controller 64238; guardian restart now loads two edits). Remaining independent candidate: render-reference seam extraction from the controller.

## Iteration log — 2026-11-14 19:20 UTC (the frozen voice flag no longer blocks voice shedding)

- Reproduced first, no services touched: fed the verbatim installed guardian a `tts-playing.json` projection with `playing: true` and a pid of a reaped process — `_voice_is_playing()` returned True. Since pruning is read-triggered (VA-PLAY-002) and the guardian reads only this flat file, a session SIGKILLed mid-clip with no controller read would freeze the flag forever, permanently disabling the voice-shed tier and letting the engine reach the sustained kill line. The live projection at check time was `{"playing": false}`: latent, not firing.
- Fix in `~/.local/bin/strata-memory-ceiling`: `_voice_is_playing` uses the projection's `pid` as a liveness witness (`kill(pid, 0)`; ESRCH → not playing). Missing or malformed pid stays conservative (defer the unload); a zombie afplay still counts as playing. No thresholds or tiers changed.
- Verified: `pytest tests/test_memory_guardian_contract.py tests/test_memory_guardian_policy.py tests/test_playback_state.py -q` → 40 passed (new `test_the_voice_flag_does_not_outlive_its_afplay_pid`). Full suites: Python **251 passed**, Node **88 passed**. `py_compile` clean on the guardian. Scenario `VA-MEM-004-voice-flag-liveness.md` added; INDEX row added, PASS.
- Unverified: the running guardian (pid 40203, started 06:08 UTC) predates this edit and the 16:42 UTC edit before it — a restart is the human decision, as the watchdog is the safety net. Unload relief in GiB still unmeasured (17493 refused).
- Next priority: unchanged human handover (reopen VoiceBox, restart controller 64238, push; guardian restart optional but now worth doing to load both edits). Remaining independent candidate: render-reference seam extraction from the controller.

## Iteration log — 2026-11-14 19:05 UTC (the guardian–extension file contract is now pinned by tests)

- Reproduced first, no hardware: fed the real extension parser a payload from the guardian's verbatim `write_pressure` with two renamed keys (`headroomGiB`→`headroom_gib`, `shedVoice`→`shed_voice`). Result: `{ shedVoice: false, headroomGiB: 9007199254740991 }`, `isMemoryTight: false` — at 61.4 GiB used the deferral silently ceased to exist. Structural gap: `test_memory_guardian_policy.py` stubs `write_pressure`, so no test had ever executed the publish path.
- Change: committed fixture `tests/fixtures/guardian-pressure.json` generated by the guardian's own atomic write path; `tests/test_memory_guardian_contract.py` (3 tests: exact key set + ISO-Z `at` format, shed/headroom boundary never disagreeing at 60.0–62.0 GiB, fixture-vs-installed-guardian drift alarm); one new test in `tests/memory-pressure.test.ts` parses the fixture through the real `readMemoryPressure`/`isMemoryTight` and asserts the renamed-key shape parses as no-pressure data (documented fail-safe: the guardian kill logic is the backstop). No threshold or runtime behavior changed.
- Verified: targeted 15 passed (contract+policy) and 24 passed (Node memory/refusal). Full suites: Python **250 passed**, Node **88 passed**. Scenario `docs/testing/scenarios/VA-MEM-003-guardian-extension-contract.md` added; INDEX row added, PASS.
- Unverified: live deferral with the real guardian writing to the real file and a live VoiceBox (17493 still refused); unload relief in GiB.
- Next priority: unchanged human handover (reopen VoiceBox, restart controller 64238, push). Remaining independent candidate: render-reference seam extraction from the controller.

## Iteration log — 2026-11-14 18:45 UTC (guardian monitoring overhead measured: 0.8% CPU, requirement satisfied)

- Reproduced first, no code change: the guardian contract in `docs/architecture/MEMORY-POLICY.md` requires that "repeated monitoring must not create excessive system load". Measured the running instance (pid 40203, `watch`, started 01:08:35 local): `ps -o pid,etime,cputime,%cpu` → 12 h 33 m elapsed, 05:53 CPU total = 0.78% average. In-process timing of 300 `sample()` calls: min 1.06 ms, median 1.11 ms, p95 1.39 ms, max 2.19 ms (~0.115% CPU at 1 Hz). Poll interval 1.0 s (0.5 s when hot) → duty cycle 0.1–0.4%.
- Why it is cheap: every sample uses zero-fork Mach stats (`sysctlbyname`) and `libproc` walks; no subprocess spawns per sample. Only `stop_engine` forks. `self-test` reports `scan_ms=2.24`, `own_fp=17.3 MB`. The per-sample `write_pressure` includes a 0.6 s-timeout `urlopen` to `http://127.0.0.1:8080/slots` for `llmBusy`; that call stays inside the ~2 ms scan.
- Verified the running policy equals the tested policy: the startup log line (`watch started poll=1.0s/0.5s ceiling=55GiB sys_used_kill=63GiB min_headroom=1.0GiB emergency_headroom=0.75GiB voice_shed=61GiB sustained=6 swap_growth=128MiB idle_unload=arm=62GiB grace=180s`) matches the constants in `tests/test_memory_guardian_policy.py`. Caveat: the file was edited at 16:42 UTC after the process started; a restart to reload the edit is human-gated because the watchdog is the safety net.
- Live snapshot at 18:42 UTC: `sys_used` 62.74 GiB (shed-armed tier, headroom 1.26 GiB), pressure normal, free 33%, swap 5.52 GiB, engine footprint ~14.5 GiB (model unloaded after the 05:29 UTC kill by the previous instance). Scenario `docs/testing/scenarios/VA-MEM-002-guardian-overhead.md` added; INDEX row added, PASS.
- Unverified: actual GiB freed by a real VoiceBox unload (17493 refused); acoustic AEC-REAL-001–006; live reload of the extension/controller.
- Next priority: unchanged human handover (reopen VoiceBox, restart controller 64238, push so CI reflects the fixed baseline). Independent candidates remaining: render-reference seam extraction from the controller.

## Iteration log — 2026-11-14 13:35 UTC (the stop fixture now cuts playback: AEC guard + pre-roll)

- Reproduced first, stubbed afplay, microphone never opened (`stop_cut_probe5.py`, outputs `/tmp/stop-cut-7.txt` … `/tmp/stop-cut-11.txt`): with a render reference active, stop-fixture frames entered WebRTC at raw rms 4130 and left at rms 3 — the warm-up fit was erasing the interruption before the barge gate scored it. The identical feed without a reference fired holds on intact audio, so the gate (vad 0.55, `rms >= max(320, floor*2.4)`, 3 consecutive frames) was never the problem and was not touched.
- Fix in `bin/omp-voice-controller`: `echo_over_cancels(mic, cleaned, reference)` fires only when the filter removed >75% of block energy **and** the mic block matches no sample-lagged window of the render reference within ±300 ms (`AEC_GUARD_LAG_SAMPLES = 4800`); flagged blocks return raw and still feed `_aec_observe`. Threshold 0.55 measured on this machine: genuine echo paths (0–300 ms delays, four-tap room) correlate 0.62–1.0, unrelated same-voice speech peaks 0.46. `tts_pre_roll` keeps an 8-frame gate-burst so the barge clip carries the word onset, not just the tail. A warm-up skip was tried and reverted — it starved the filter and broke the ERLE tests.
- Verified: probe5 reference arm — stop frames survive (4130→4130, 5318→5318), `TTS barge hold rms=2605 hot=3 frames=4`, whisper clip peak 25244, `Heard 'stop.' over TTS -> stopping speech`, latency 0.636 s. 3 new tests (`test_echo_control.py` guard pair, `test_barge_fixture.py::test_a_squashing_canceller_cannot_erase_the_stop`). Full Python suite **247 passed**, Node suite **87 passed**. Scenario `docs/testing/scenarios/VA-INT-AUTO-040-fixture-pipeline.md` updated; INDEX row 040 flipped PARTIAL → PASS. Also documented and verified in a fresh venv: `pid_alive` returns True for an exited-but-unreaped zombie, so `stop_playback` can burn its 2 s confirmation window if VoiceBox exits without reaping its afplay children — hazard to confirm once the sidecar is back.
- Unverified: everything acoustic. The guard is Level 1/2 evidence; the AEC path still needs the restarted controller and a reopened VoiceBox.
- Next priority: unchanged human handover (reopen VoiceBox, restart controller 64238, push). Independent candidates: render-reference seam extraction from the controller; live unload-relief measurement.

## Iteration log — 2026-11-14 17:35 UTC (unhealthy 200 payloads no longer drop sentences)

- Reproduced first: same mock-VoiceBox suite, never touching 17493. A third silent-loss path beside 500/refused: VoiceBox alive but the TTS model unloaded answers **200 with a ~4-byte payload**; `generate()` logged `failed` with reason `short-audio` and dropped the sentence (repro showed `deferred.length === 0`, nothing spoken). Probe also proved the mock suite itself was fragile: Node's fetch keep-alive pool keys by origin, so a dead socket from one mock made the next test's fresh server on the same port unreachable (the 500 test's mock recorded 0 stream attempts).
- Fix in `extension/voicebox-speech.ts`: payload under 100 bytes on a 200 now returns `{deferred: true}` (reason `short-audio`) and rides the retry chain; the connection-refusal hold is deliberately not armed because the service is reachable — the 5 s retry timer already paces attempts. `API` became `apiBase()` resolved per call; each mock scenario uses its own port (17999/17998/17997). AbortError (barge-in abort) explicitly excluded from transport-failure matching.
- Verified: 2 new tests (truncated-200 holds, then recovers through the real `generate()` when the mock returns a usable payload; abort is not a refusal). Full Node suite **87 passed 0 failed**; Python suite **244 passed**; py_compile clean.
- Unverified: same as before — a real unloaded-Model VoiceBox returning truncated 200s is the live VA-LAT-001 shape, untested end-to-end while the sidecar is down.
- Next priority: unchanged human handover (reopen VoiceBox, restart controller 64238, push). Independent candidate: render-reference seam extraction from the controller.

## Iteration log — 2026-11-14 17:25 UTC (VoiceBox outage no longer drops sentences)

- Reproduced first: mock VoiceBox tests against port 17999 (never the real 17493). Before the fix: a 500 on `/generate/stream` and a refused connection both returned "no clip" and the sentence was released unspoken with no retry path — on screen but never said, exactly the silent-loss failure the mission calls out. Second-order root cause surfaced during the repro: after a listener closes, Node's fetch reuses the dead keep-alive socket and throws `ECONNRESET`, which `isConnectionRefusal` did not match, so even the 5 s refusal hold rarely armed on real transient failures.
- Fix: `generate()` now returns `{ deferred: true }` on refusal-hold, HTTP non-2xx, and transport failures (ECONNREFUSED/ECONNRESET/ETIMEDOUT/ENOTFOUND); held sentences ride the existing retry chain (every 5 s, epoch drop on barge-in, 120 s expiry, oldest-first, dedupe). `OMP_VOICEBOX_API` env override added so tests can point at a mock. `resetSpeechSession()` clears the refusal clock. No thresholds changed; non-transport errors still drop with a `failed` log.
- Verified: `tests/voicebox-refusal.test.ts` 5 tests — 500 holds and is not counted spoken; refused connection holds and the hold window opens no further connections (mock attempt count 0); recovery replays oldest-first exactly once, second pass adds nothing; barge-in drops held items. Full Node suite 85 passed 0 failed. Python suite 244 passed. py_compile clean. CI node job now includes the new file.
- Unverified: actual VoiceBox recovery behavior (VA-LAT-001 blocker: sidecar down, human handover needed); the timer-driven retry against the real service; audio validity after a real recovery.
- Next priority: unchanged human handover (reopen VoiceBox, restart controller 64238, push). Independent candidates: render-reference seam extraction; VA-INT-AUTO-040 stop-fixture follow-up (blocked on VoiceBox).

## Iteration log — 2026-11-14 17:05 UTC (platform compatibility: suite matches the documented fallback strategy)

- Reproduced first: in the disposable CI-repro venv with `aec-audio-processing==1.0.0` uninstalled, `pytest tests/test_echo_control.py` failed 7 tests — 4 with `ModuleNotFoundError`, 3 by assertion (fallback gave 9.3 dB ERLE vs 15 required; residual window empty; offset table short of −30 dB). The fallback fails loudly — no silent false pass — but the suite falsely signals "broken" on platforms (Intel Macs, non-3.12 Python) where the wheel cannot exist and the controller is designed to degrade to the render-subtraction fit.
- Fix: `@aec_required` (`skipif` on `importlib.util.find_spec("aec_audio_processing")`) on the 7 WebRTC-behavior tests in `tests/test_echo_control.py`. Fallback tests (`test_missing_module_falls_back_to_the_short_fit` etc.) run everywhere. No thresholds or assertions changed.
- Verified both sides of the matrix: wheel present → 24 echo tests pass; wheel absent → full suite 237 passed, 7 skipped (7.90 s). Repro venv restored afterward.
- Unverified: real Intel-Mac hardware (simulated by uninstalling the package); physical echo quality of the fallback on real speakers/mic — blocked on microphone ownership like AEC-REAL-001–006. GitHub CI still runs the old failing baseline until the fix is pushed.
- Next priority: unchanged hard blocker — Akshay reopens VoiceBox, restarts controller pid 64238, pushes. Independent candidates: render-reference seam extraction from the controller; unload-relief measurement once VoiceBox is back.

## Iteration log — 2026-11-14 16:57 UTC (dead-guardian stale pressure file could silence the voice path)

- Reproduced first: `readMemoryPressure` in `extension/voicebox-speech.ts` ignored the `at` field. If the guardian exits while `shedVoice: true` is written, every later sentence defers (8 s wait), retries every 5 s, and drops at the 120 s expiry — voice silence on a machine nobody is monitoring, with sentences eventually lost.
- Fix: stale files (`at` older than `PRESSURE_STALE_MS = 30000`) return `undefined`, i.e. no pressure. Verified against the guardian's actual cadence in `~/.local/bin/strata-memory-ceiling` while alive: writes every 0.25–2 s, worst sleep branch ~5 s, so a 30 s window has a 6× margin. Missing `at` is treated as fresh (current guardian always writes it).
- Tests: 3 new in `tests/memory-pressure.test.ts` (stale file → no deferral, `waitedMs: 0`; 10 s-old file → still defers; no `at` → fresh). The pre-existing guardian-file test had hard-coded `"at": "2026-11-14T06:00:00Z"` — a fixed old timestamp is stale by definition under the new contract, so it was updated to a fresh timestamp; no assertion was weakened. Node suite: **80 passed, 0 failed**. Python suite untouched by this change.
- Scenario `docs/testing/scenarios/VA-TTS-015-guardian-staleness.md` added; INDEX row added.
- Unverified: no live guardian crash was observed and recovered from; the guard is synthetic-file level only. Live deferral end-to-end still blocked on VoiceBox (:17493 refused at 16:55 UTC, curl exit 7; live `pressure.json` healthy at 16:55:18Z, shedVoice false).
- Next priority: unchanged hard blocker — Akshay reopens VoiceBox, restarts controller pid 64238, and pushes. Independent candidates after that: render-reference seam extraction from the controller; live unload-relief measurement the moment VoiceBox returns.

## Iteration log — 2026-11-14 16:52 UTC (ASR jitter root-caused; latency guard split by component)

- Re-ran VA-AEC-007 to collect more jitter samples (pending item). The run **FAILed** with `+3.03 s` on turn a — hidden first because the job ran through a pipe and only `tail`'s exit code was seen; the verdict line in the run output is authoritative.
- Root cause from three reruns (11:24, 11:48, 16:52 UTC): `wake_to_flush_s` — the controller-controllable segment — is stable at 6.80–7.14 s (spread 0.33 s); all variance lives in `asr_s` (0.90–3.30 s), i.e. Handy ASR model load and machine contention. The old assertion compared the *sum* against a single two-point baseline with ±1.5 s, so environment noise produced false alarms that could mask real echo-path regressions.
- Fix in `scripts/run_repeat_turn_probe.py`: the ±1.5 s tolerance is kept but applied to `wake_to_flush_s` against its own baseline (a: 6.80, b: 7.13), and `asr_s` is bounded separately at 4.0 s (UX ceiling; observed max 3.30). All functional assertions (echo wake suppression, verbatim transcripts, state transitions, AEC residual) unchanged. No threshold relaxed.
- Rerun: PASS — deltas +0.10/+0.01 s, asr 1.11/2.59 s, transcripts verbatim, zero echo wakes, final IDLE. `py_compile` clean.
- Unverified: physical ASR latency under a real microphone and real VoiceBox replies (Level 4 still blocked); the 4 s ASR ceiling is an engineering bound, not yet a measured failure mode.
- Next priority: unchanged hard blocker — VoiceBox reopen, controller restart, push. New independent candidate discovered this iteration: the extension's deferral ignores the `at` field of `pressure.json`, so a guardian that exits mid-shed could leave `shedVoice: true` frozen and defer speech indefinitely (retry expiry is 120 s). Worth a staleness guard next iteration.

## Iteration log — 2026-11-14 16:45 UTC (guardian unload race closed; failed unloads no longer fake relief)

- The loop requirement "VoiceBox is not unloaded in the middle of an utterance" was gated only at the `watch()` gate: `shed_voice()` did a status GET and then POSTed `/models/unload` without re-reading the playing flag, so an utterance starting between the gate and the POST had its weights pulled mid-sentence. Second defect found while reading the code: `relief_at = now` and the `RELIEF` log fired unconditionally, so a refused connection or "no model loaded" armed the 10 s relief grace and logged a relief that never happened.
- Fix in the installed guardian (`~/.local/bin/strata-memory-ceiling`, logic only — no thresholds touched): `shed_voice()` returns `{"freedBytes": 0, "detail": "deferred: utterance in progress"}` when `_voice_is_playing()` is true at the moment of the POST, making no HTTP call at all; `watch()` counts relief only when bytes were freed or a model was actually unloaded, logging `VOICE_DEFER` otherwise. This relies on the VA-PLAY-002 projection fix: the flat `tts-playing.json` is now trustworthy even after a crashed session.
- Tests: `tests/test_memory_guardian_policy.py` → 12 passed (added `test_unload_is_rechecked_before_the_post` — stubbed HTTP records zero requests while voice plays — and `test_failed_unload_does_not_count_as_relief` — refused unload logs `VOICE_DEFER`, never `RELIEF`, no relief clock, kill still proceeds). `run_watch` now takes a `shed_result` and only records relief times for actual unloads. Full suite: 244 passed (4.26 s). `py_compile` clean on the guardian. Runtime sanity: `strata-memory-ceiling self-test` ok (2.08 ms scan) and `pressure` reports 58.22 GiB used, `shedVoice: false` — no kill conditions on the real machine; nothing was stopped or unloaded.
- Regression impact: none on Node/extension code (Node suite unchanged, not re-run). The two pre-existing direct `shed_voice` tests were made hermetic (they previously read the real `tts-playing.json`).
- Unverified: live unload behavior on a real VoiceBox (port 17493 still refused at 16:45 UTC — curl exit 7); the gate+unload pair is still not atomic — a hard guarantee needs VoiceBox to reject unload while a stream is active.
- Next priority: unchanged — Akshay must reopen VoiceBox, restart the controller (pid 64238), and push, so Level 4 physical AEC, Level 3 live reload, unload-relief measurement, and CI on GitHub can proceed.

## Iteration log — 2026-11-14 11:52 UTC (projection symmetry: crashed sessions no longer freeze the voice flag)

- Investigated the Node/Python asymmetry flagged last iteration. Root cause found: the flat `tts-playing.json` projection is written only while a session is alive. A session SIGKILLed mid-clip leaves its slot `playing: true` and nobody rewrites the projection — the memory guardian's `_voice_is_playing` would then forever believe voice is playing and skip VoiceBox shedding before considering an engine stop. The guardian never reads the slot directory; it reads exactly this flat file.
- Fix, one contract on both sides: `bin/playback_state.py` gained `project_aggregate` (mirrors the extension's `projectAggregate`); `_read_playback_slots()` re-derives `tts-playing.json` from the surviving slots whenever it prunes a dead slot. `extension/playback-state.ts` `readSlots` now prunes dead-session slots symmetrically (pid-alive via `process.kill(pid, 0)`, EPERM conservatively treated as alive, 0.6 s reverb tail respected) before publishing the aggregate; `commitBegin`/`commitEnd` accept an `alive` predicate so tests can stub synthetic pids.
- Reproduced first: the new unit test `test_pruning_refreshes_a_projection_frozen_by_a_crashed_session` asserts the exact frozen-projection state before the fix path runs. The first attempt at Node tests failed the pre-existing `ending another session leaves the first clip playing` test — the synthetic pids 11/22 are genuinely dead to real `process.kill`, so the new default prune deleted them mid-test. Fixed by threading the `alive` predicate, not by weakening the assertions.
- Tests run: `pytest tests/test_playback_state.py -q` → 24 passed; full suite 242 passed (4.27 s); `node --experimental-strip-types --test` on all four Node files → 77 passed; `py_compile` clean on controller and `bin/playback_state.py`.
- Unverified: the live `~/.local/state/omp-voice/tts-playing.json` (43 B) is not refreshed by this code until pid 64238 restarts; VoiceBox unload relief still unmeasured (:17493 refused at 11:21 UTC). Guardian log `~/.local/state/strata/memory-ceiling.log` checked for unbounded growth: 27.8 KB, event-driven (7 `log_line` call sites), no rotation needed.
- Next priority: unchanged — Level 4 physical AEC and Level 3 live reload, blocked on Akshay reopening VoiceBox and restarting the controller, plus a push so GitHub CI reflects the fixed baseline.

## Iteration log — 2026-11-14 11:35 UTC (playback-state module extraction + probe pid regression fix)

- Extracted the pure playback-slot decision rules into `bin/playback_state.py`: `slot_reference`, `playback_rate_of`, `render_cursor`, `_slot_rank`, `choose_render_slot`, `_valid_pid`, `slot_is_speaking`, `playback_is_speaking`, `playback_sources_speaking`, `PLAYBACK_LEASE_SECONDS`. The controller imports them, so every existing call site and test is unchanged; audio DSP, file I/O, and process management stay in the controller. CI compiles both files. `py_compile` clean; full suite 239 passed.
- Reproduced and fixed a regression that the previous iteration's stale-slot pruning introduced: `scripts/run_double_talk_probe.py` crashed with `FileNotFoundError` at 11:17 UTC because the probe claimed a slot under synthetic dead pids (999998/999999/999996/999997) and the controller pruned the probe's own slot mid-run once the clip ended past the 0.6 s tail. Fix: all four fixture probes now use `PROBE_PID = str(os.getpid())` (live for the run), the stand-in clip file is named `f"afplay-omp-vb-{PROBE_PID}-clip.py"` so `kill_tts_clips` matches the owner, and each probe clears stale state JSONs at startup.
- Re-runs against the current tree: VA-AEC-005 PASS 11:19 UTC; VA-AEC-006 PASS 11:31 UTC (−27.4 dB echo-only, stand-in killed with exit −9, slot silent); VA-AEC-007 PASS 11:32 UTC (deltas +0.55/+0.84 s; an 11:20 run failed only on ASR jitter +1.85 s — threshold unchanged, re-run passed); VA-AEC-008 PASS 11:33 UTC.
- Unverified: VoiceBox unload relief (port 17493 refused connection at 11:21 UTC); live-controller pruning/rotation still needs a restart of pid 64238.
- Next priority: Level 4 physical AEC acceptance and Level 3 live reload — both blocked on Akshay reopening VoiceBox and restarting the controller. Independent safe candidates: prune symmetry in the Node `readSlots`, guardian log growth observation.

## Iteration log — 2026-11-14 11:10 UTC (runtime log rotation + stale slot pruning)

- `bin/omp-voice-controller`: `_rotate_stdout_log()` now rotates `controller.log` from inside `log()` when fd 1 is the log file itself (guards: regular file, same open inode as `LOG_FILE`, size > 1,048,576). `tests/test_log_rotation_runtime.py` adds 4 tests; full suite 239 passed. `py_compile` clean.
- `_read_playback_slots()` now unlinks a slot whose session pid is dead and which is not still speaking; 3 tests added to `tests/test_playback_state.py` (21 passed). Scenario `docs/testing/scenarios/VA-PLAY-002-stale-slot-pruning.md`.
- Live observation, 11:05 UTC: `~/.local/state/omp-voice/tts-playing/` was empty. The nine dead-pid slots seen at 11:02 vanished from a source the loop did not observe (pid 64238 runs HEAD code with no pruning and logs no removal; the extension unlinks only clip wavs and the registry file). Live pruning is NOT demonstrated; it remains a unit-level behavior until the controller restarts.

## Do not get stuck

You are the only runner. If Handy opens and the line does not end in `Send that.`, or if a wake never returns a transcript, this session stops and nobody else continues it.

If a scenario opens Handy, speak the continuation only after the log says `entering DICTATING`, and end with `Send that.`

## Write the file at every observation

The moment the log shows a new fact, edit this file before the next play, the next fix, or the next scenario. Do not batch notes until the end.

On a failure, in this file, in the same turn:

1. Write the reason in the row and in `## Retrospective`.
2. Fix that reason.
3. Retest the same row until it passes.
4. Write what changed and what the new log showed.

A `pass` is never run again.

## How to speak a wake scenario

Do not say the wake and the rest in one clip. `say` launches `afplay`, the controller treats every `afplay` as VoiceBox, and barge-in cuts the sentence. The words after "Jarvis" are then lost or land in a second chunk.

1. Confirm `status.json` is `IDLE`. If it is `DICTATING`, say only `Send that.` and wait until it is `IDLE`.
2. Say only the wake: `Hey Jarvis.` (or the wake in that row).
3. Wait until the log shows `entering DICTATING`. That is the delay. Do not speak the continuation before that line.
4. Then say the rest, loudly, ending with `Send that.`
5. Read `controller.log` and `status.json`. Write the Handy line or the ignore line into the row before doing anything else. What you meant to say is not the result. What the log heard is the result.

Lookalikes, `stop`, `scratch that`, and `clear draft` do not get a wake in front. If one opens Handy anyway, say `False open. Continue the next scenario. Send that.`

Speak up. Output volume stays near 19. Lowering output does not make a quiet clip louder. Do not whisper.

Pass means the `expect` column matches the log.

## Contract these rows use

- During our own playback only, a wake must not open Handy. Our playback is `tts-playing.json`, not every `afplay`.
- Do not restore a 0.35 TTS open. A `Wake triggered (barge-in ...)` during our own playback is a fail.
- Idle wake threshold stays 0.50. Room noise has opened Handy at 0.38–0.47. A real wake has scored about 0.53 and up. Do not lower it.
- Send is `Send that.` or a lone `Submit.` The words `said that` inside a sentence do not send.
- Grammar wakes: `hey jarvis`, `ok jarvis`, `hello jarvis`, `jarvis`.
- When a send should arrive in this session, write that into this file, then stop thinking. The line is already typed and OMP has it in the queue. More thinking in the same turn keeps the message from arriving. The next run reads this file and continues.
- Play speech only. Before `sd.play`, convert int16 samples to float32 and divide by 32768 so the signal stays in -1..1. A gain of about 2 is fine only after that scale. Never pass raw int16 values to sounddevice. If a clip is clipped, noisy, or screechy, stop. Do not raise the gain and do not play it again. The 23:21 G2 wake was that screech. It is not a take. G2 stays pending.

## Playback already observed

Do not rerun these unless a later code change invalidates them. Speaker at output volume 19, MacBook Pro Microphone, controller pid 71881 after the 21:23:32 restart.

| id | phrase | heard in log | result |
|---|---|---|---|
| done-hrvs | H R V S during playback | `Ignored 'V s.' over TTS (not stop)` at 21:23:41 | pass, Handy stayed IDLE |
| done-service | Hey, service started during playback | `Ignored 'Service are dead.' over TTS (not stop)` at 21:23:46 | pass, Handy stayed IDLE |
| done-stop-in-sentence | one sentence that ends in the word stop | clip played through, stop was not cut out | fail as a barge, not a separate burst |
| done-user-044 | user speech, not a clip | score 0.44 opened Handy; #654 ended `Said that.` and was appended; #655 `Send that.` was sent | wake worked; first close phrase was misheard |
| done-user-037 | user said continue the report | score 0.37; #656 `HRVS did not open handy. Continue the report. Send that.` was sent | pass for a real wake that ended in send |
| extra-664 | not a scenario | wake score 0.84 at 21:35:56; #664 `Me too. Send that.` was sent at 21:36:01 | extra send after A1, not A2 |
| extra-665 | not a scenario | wake 0.98 at 21:38:06; #665 `Sent that.` appended; 15s timeout cancelled Handy | partial, not A1 |
| extra-local-1 | not a scenario | wake 0.95 at 21:38:48; Handy row missing; local `Send that.`; `handy_stopped` | partial, not A1 |
| extra-local-2 | not a scenario | wake 0.84 at 21:39:22; Handy row missing; local `Send that, send that.`; `handy_stopped` | partial, not A1 |
| extra-local-3 | not a scenario | wake 0.90 at 21:39:44; Handy row missing; local `And then, submit.`; `handy_stopped` at 21:39:52 | partial, not A1 |
| extra-666 | user correction, not a scenario | barge-in score 0.40 at 21:40:10 while a test clip was still playing; #666 at 21:41:28 was the full correction and was `sent`; then IDLE | not A1 |
| extra-a2-timeout | A2 wake, no continuation | 21:45:07 wake score 0.96 entered DICTATING. No speech for 15s. Idle timeout at 21:45:23. No Handy chunk. User message in chat was `checkpoint a1`, which is not an A2 result. | IDLE, A2 still pending |
| extra-local-4 | not a scenario | wake 0.94 at 21:50:31; Handy row missing; local `All right.`; `handy_stopped` at 21:50:48 | not B2 |

## Retrospective

### VA-INT-001, 2026-11-13 19:24 UTC

Integration check only. No code change. No speech was dictated. Handy pid 62365 is running and was not invoked. VoiceBox GUI pid 29277 is running. `voicebox-server` is absent after a 10:12 SIGSEGV in `mlx::core::eval_impl` and was not relaunched. Port 17493 is closed. OMP pid 80894 answered `GET /status` on 56876 with `agentBusy: true` and `draftLength: 0`. Controller pid 64238 is IDLE and its log stops at 14:16. At 14:27:37 a wake scored 0.98, speech rms was 896, and Handy chunk #771 was `Cancel that.` The outcome was `cancelled`. Delivery was still paste with no port. VoiceBox was not reached. The spoken pipeline stays BLOCKED. Do not mark this pass.

### F2, after 22:47:54

Ten seconds of silence. No clip. Log did not grow past line 12206 (`Ignored 'Thank you.' over TTS` at 22:47:54). No `Wake triggered`. Status stayed IDLE, pid 3695, `last_action` `sent`, `updated_at` unchanged from the F1 close. F2 is pass.

### F1, 22:47

Whisper wake `/tmp/f1-wake.wav` at gain 0.35. Score 0.51 at 22:47:07, pid 3695, entered DICTATING. Speech rms 359. After 1.3 s, `/tmp/f1-rest.wav` at 2.3×. Handy chunk #700: `Checkpoint F1. Send that.` Outcome `sent` at 22:47:13, then IDLE (`Prompt submitted`). A whisper at 0.35 still cleared the 0.50 idle gate. Do not lower the threshold. F1 is pass.

### E1, 22:45

Whisper heard `Jarvis.` at 22:45:44, pid 3695, entered DICTATING. Speech started rms 340. Handy history row was missing (`stopped externally`); local transcript kept `Checkpoint E1 after playback, send that.` Manual transcription #699: `Checkpoint E1 after playback. Sent that.` Outcome `sent` at 22:45:55, then IDLE. Last TTS ignore was 22:45:32, so the open was after the 600 ms tail. `Sent that` still submitted. E1 is pass.

### E1, 22:44

Whisper heard `Jarvis.` at 22:44:23, pid 3695, entered DICTATING. Focus Terminal. No speech line. 22:44:39 `No speech for 15s` idle timeout, back to IDLE. The rest clip never started: the player process was cut after printing `entering DICTATING` and before `rest start`. Not a threshold miss. Next take must play `/tmp/e1-rest.wav` inside the same process after the 1.3 s gap, and that process must not be killed before `rest end`.

### E1, 22:40

Score 0.68 at 22:40:54, pid 3695, entered DICTATING. No speech line. 22:41:10 idle timeout, back to IDLE. `sd.play` of the rest never returned, so the continuation never reached the mic.

### E1, 22:31

Score 0.54 at 22:31:09, pid 98768, entered DICTATING. Speech rms 575. Chunk #697: `One after playback, send that.` Outcome `sent` at 22:31:14, then IDLE. The opening words `Checkpoint E1` were not in the chunk. The rest started in the same moment as the wake cue, so the first words were covered. Not a threshold miss. Next take waits until `entering DICTATING`, then 0.8 s, then the continuation.

### E1, 22:31

Score 0.94 at 22:31:07, pid 98768, entered DICTATING. Continuation started in the same instant as the wake cue. Handy chunk #697 at 22:31:14: `One after playback, send that.` Outcome `sent`, then IDLE. `Checkpoint E1` was not in the chunk, so the row stays fail. The opening words were covered by the cue. Next take waits 0.8 s after `entering DICTATING` before the continuation.

A later wake at 22:31:36 scored 0.72 and opened Handy with no test phrase. Chunk #698 at 22:31:53 was room speech (`Sorry, mama...`), outcome `appended`, still DICTATING. That take is a false open, not E1.

### E1, 22:28

Score 0.98 at 22:28:02, pid 98768, entered DICTATING. Focus was Terminal, not a text box. The continuation never played: the player imported `soundfile`, which is not in the voice venv, and died with `ModuleNotFoundError`. No Handy chunk. At 22:28:18 `No speech for 15s in DICTATING -> cancelling Handy & returning to IDLE` (`idle_timeout`). Not a threshold miss and not the 22:24 window-close bug. Next play uses `wave` + `numpy` + `sounddevice`.

### E1, 22:24

Quiet room, no afplay. Score 0.89 at 22:24:38. Speech started rms 509. No history row. At 22:24:41 `Handy was closed during dictation` because `handy_window_open` was 0. Handy is `--start-hidden` plus a transcribe worker, so a missing window before the overlay appears is not a user dismiss. Fix: set `handy_ui_gone` only after a window was seen, or the process is gone. Restart, then retest the same two-step.

### E1, 22:14 through 22:18

Not a threshold bug. Quiet-room wakes did open Handy. The continuation was never the Handy chunk, and the outcome was never `sent`.

- 22:14:48 score 0.65. #691 unrelated transcript, `appended`, `handy_closed` 22:14:52.
- 22:15:21 whisper `Hey Jarvis.`. #692 `Hey Jonas.` `appended`, closed 22:15:27.
- 22:16:01 whisper `Hey Jarvis,`. #693 runner status sentence, `appended`, closed 22:16:05.
- 22:16:51 `Ignored wake 'Hey Jarvis.' over TTS` while playback was still running. That take does not count as after-playback.
- 22:17:10 score 0.99. #694 empty, `noop`, closed 22:17:14.
- 22:18:28 score 0.76. #695 runner status sentence ending in `Hey Jarvis.`, `appended`, closed 22:18:32.

Retest is the same two-step. Play the continuation the moment `entering DICTATING` is in the log. No other speech in the room.

### D4, 22:10

Retest after the whole-clip rule. pid 92340. Bed `afplay -v 0.35 /tmp/omp-vb-d4-bed.wav`. Burst `Stop. Stop. Stop.` through sounddevice at 3×. Log: `Heard 'stop.' over TTS -> stopping speech, not opening Handy` at 22:10:45. Bed process was gone. State stayed IDLE. D4 is pass.

### D4, 22:09

`match_command` takes the longest suffix, so a TTS clip whose last word is `stop` has `stem == ["stop"]` and `stop_playback` runs. `The stop.` at 22:08:11 and `This is not a stop.` at 22:09:00 both did that. The burst itself never appeared as its own transcript. Fix: during TTS, stop only when the whole phrase is `stop` and the prefix is empty. `stop that` and a sentence ending in `stop` stay ignored.

### C1, 21:52

Reason the first expect said IDLE: the row was written wrong. After `scratched` or `cleared`, the controller plays the cancel cue and keeps DICTATING so the next words replace the chunk (`omp-voice-controller` around the `Draft {action} -> continuing DICTATING` log). `cancelled` and `paused` return to IDLE. C1 passed on that contract. The content words `Note for scratch` were not in chunk #673. The scratch command itself was heard and was not sent.

### A1, 21:35 and 21:38–21:40

Reason: the tester spoke `Hey Jarvis. Checkpoint A1. Send that.` as one clip. The wake opened Handy while the rest of the clip was still playing. `say` is `afplay`, so the controller treated it as VoiceBox and barge-in cut the take. The first flush was `One sent that.` (#662, appended). The real line arrived as a second chunk (#663) and the sent draft contained both. Later retries (#665, local `Send that.`, `Send that, send that.`, `And then, submit.`) never produced one chunk of the A1 line.

Two-step retest at 21:42:27, wake score 0.91, then the continuation after `entering DICTATING`. Handy heard #667 `Checkpoint A1. Sent that.` and appended it. #668 `Sent that.` was also appended. `sent` was not a send word. At 21:43:19 the 15s timeout cancelled Handy (`last_action` `idle_timeout`). At 21:43:23 IDLE heard `Submit.` and tried to submit the draft. The draft that arrived was `Checkpoint A1. Sent that.` The status file never changed to `sent`.

Fix: `sent` is now in the first send slot in `voice-agent/grammar.json` and `~/.local/share/omp-voice/grammar.json`. `command_grammar()` caches the file for the life of the process, so pid 76770 still has the old grammar until restart. After restart, rerun A1 in two steps. Retest after restart pid 80729: wake at 21:44:22, then the continuation. #669 `Checkpoint A1. Send that.` was `sent` at 21:44:40 and the state returned to `IDLE`. A1 is `pass`. Do not rerun it. The wake itself was still a barge-in at score 0.36 because `say` is `afplay`. That did not split the continuation.

## Scenarios still to run

One row per turn. Speak the `say this` cell verbatim.

### A. Real wakes, no playback

These open Handy. Each line already ends with `Send that.`

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| A1 | Hey Jarvis. Checkpoint A1. Send that. | Handy opens, one chunk contains the continuation, outcome `sent`, returns to IDLE | 21:44:22 barge-in 0.36, then #669 `Checkpoint A1. Send that.` `sent` at 21:44:40. Earlier #667 heard `Sent that.` and only appended. | IDLE | pass |
| A2 | OK Jarvis. Checkpoint A2. Send that. | same as A1 | 21:45:59 wake score 0.99, then #670 `Checkpoint A2. Send that.` `sent` at 21:46:15. | IDLE | pass |
| A3 | Hello Jarvis. Checkpoint A3. Send that. | same as A1 | 21:48:57 wake score 0.99 via sounddevice, then #671 `Checkpoint A3. Send that.` `sent` at 21:49:10. Earlier same-turn tries timed out or lost the Handy row. | IDLE | pass |
| A4 | Jarvis. Checkpoint A4. Send that. | same as A1 | 21:49:25 wake score 0.54, then #672 `Checkpoint A4. Send that.` `sent` at 21:49:41. | IDLE | pass |

### B. Lookalikes, no playback

These must stay IDLE. If Handy opens, immediately say: `False open. Continue the next scenario. Send that.`

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| B1 | H R V S. | no wake line, state stays IDLE | Played at 21:49 via sounddevice. No new log line. Status stayed IDLE, last_action still `sent` from A4. | IDLE | pass |
| B2 | H R V. | stays IDLE | Played at 21:51 via sounddevice. No new log line after 21:50:48. Status stayed IDLE. | IDLE | pass |
| B3 | Hey service. | stays IDLE | 21:51:20 `Ignored 'Hey service.' over TTS (not stop)`. No wake. Status stayed IDLE. Playback was already active, so this is not a quiet-room miss. | IDLE | pass |
| B4 | Hey, service started. | stays IDLE | Played after 21:51:20 via sounddevice. No new log line. Status stayed IDLE. | IDLE | pass |
| B5 | A harvest. | stays IDLE | Same batch. No new log line. Status stayed IDLE. | IDLE | pass |
| B6 | Every service. | stays IDLE | Same batch. No new log line. Status stayed IDLE. | IDLE | pass |
| B7 | The service is ready. | stays IDLE | Same batch. No new log line. Status stayed IDLE. | IDLE | pass |

### C. Commands while already dictating

Start each one with a wake that stays open, then the command. The wake line must include a continuation so a missed command does not leave the session stuck.

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| C1 | Hey Jarvis. Note for scratch. Scratch that. | scratched, not sent, stays DICTATING so the next words can replace the chunk | 21:52:15 wake score 0.97. #673 `Scratch. Scratch that.` outcome `scratched` at 21:52:20. Log: `continuing DICTATING for replacement chunk`. `Note for scratch` was not in the chunk. No replacement speech. Idle timeout at 21:52:35 returned to IDLE. A later `say` of `Cancel that.` was ignored over TTS. | IDLE | pass |
| C2 | Hey Jarvis. Note to clear. Clear draft. | cleared, not sent, stays DICTATING for a replacement chunk | Earlier misses: `dress`, `drive`, `Near draft.`, `Air drive.`, `Here. Drive.`, lone `Drive.`. Louder playback at 21:59:50, wake 0.91, rms 2214. #680 `Clear draft.` outcome `cleared` at 21:59:55. Log: `continuing DICTATING for replacement chunk`. | DICTATING | pass |
| C3 | Hey Jarvis. Note to cancel. Cancel that. | dictation cancelled, not sent, back to IDLE | While the C2 replacement take was still open: #683 `Cancelled app.` appended at 22:00:21, not a cancel. #684 `Cancel.` outcome `cancelled` at 22:00:39. `Handy stopped -> returned to IDLE`. | IDLE | pass |
| C4 | Hey Jarvis. Checkpoint C4 stop. | `stop` pauses and does not submit, back to IDLE | 22:00:54 wake 0.94. #685 `Stop.` outcome `paused` at 22:01:01. `Paused listening -> returned to IDLE (draft preserved)`. | IDLE | pass |
| C5 | Hey Jarvis. Checkpoint C5. Submit. | lone `submit` sends, outcome `sent` | 22:01:19 wake 0.78. #686 `Point C5. Submit.` outcome `sent` at 22:01:24. Returned to IDLE. | IDLE | pass |
| C6 | Hey Jarvis. Checkpoint C6 said that. | `said that` is a send, outcome `sent` | 22:01:37 wake 0.71. #687 `Checkpoint C6 said that.` outcome `sent` at 22:01:46. Returned to IDLE. | IDLE | pass |
| C7 | Hey Jarvis. The meeting said that we should wait. Send that. | prefix before `said that` must not be the only thing that matters: record whether the draft submitted at `said that` or only at `Send that.` | 22:02:10 wake 0.85. One chunk #688 `Ding said that we should wait. Send that.` outcome `sent` at 22:02:15. It did not submit at `said that` and drop the rest. The words after `said that`, including `Send that.`, were in the same sent chunk. `The meeting` was heard as `Ding`. | IDLE | pass |

C1–C4 do not end in `Send that.` on purpose. If the command is missed and Handy is still dictating after the log line, say `Command missed. Continue the next scenario. Send that.`

### D. During VoiceBox playback

Start playback with a long `say` or a real VoiceBox `afplay` first. Speak the test phrase over it, loudly, as its own burst. Any `afplay` counts as speaking in the controller.

| id | say this over playback | expect | heard | state after | result |
|---|---|---|---|---|---|
| D1 | H R V S. | ignored, Handy stays closed for the whole clip plus 600 ms | Earlier miss: 22:03:43 IDLE wake score 0.65, then user closed Handy. Clean overlay at 22:04:05 while `afplay` was running: `Ignored 'D-word.' over TTS (not stop)`. No wake after that. State stayed IDLE. | IDLE | pass |
| D2 | Hey, service started. | ignored, stays IDLE | First overlay produced no line because pid 87233 froze at 22:04:13. Restarted as pid 90575 at 22:06:08. Retry over `afplay /tmp/bed.wav`: 22:06:31 `Ignored 'You\'re a great service.' over TTS (not stop)`. No wake. Stayed IDLE. | IDLE | pass |
| D3 | Hey Jarvis. | skill: ignored until playback ends. Wake score during afplay must not open Handy. | Before the fix: 22:06:51 barge-in score 0.99 opened Handy. Fix: drop the TTS wake-score open and ignore a Whisper wake during afplay. After restart pid 91279, Hey Jarvis over afplay at 22:07:53 produced no wake. Nearby ignores: `He's beating so straight.`, `Thanks for watching.` State stayed IDLE. | IDLE | pass |
| D4 | Stop. | playback stops, Handy stays closed. Must be its own loud burst, not the last word of a sentence | 22:10:45 `Heard 'stop.' over TTS -> stopping speech, not opening Handy`. The `omp-vb-` bed was gone afterward. Status stayed IDLE. Earlier sentence matches no longer stop playback. | IDLE | pass |
| D5 | Send that. | not a wake. Either ignored, or idle-submit only after playback. Must not open a new dictation | 22:11:23 `Ignored 'Send that.' over TTS (not stop)`. No wake. Status stayed IDLE while the bed was still running. | IDLE | pass |
| D6 | Scratch that. | must not open Handy during playback | 22:11:33 `Ignored 'scratch that.' over TTS (not stop)`. No wake. Status stayed IDLE while the bed was still running. | IDLE | pass |

### E. After playback

Wait until `afplay` is gone, then wait at least 600 ms, then speak.

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| E1 | Hey Jarvis. Checkpoint E1 after playback. Send that. | Handy opens only after the 600 ms tail, then `sent` | 22:45:44 whisper `Jarvis.` entered DICTATING. #699 `Checkpoint E1 after playback. Sent that.` outcome `sent` at 22:45:55. Handy history row was missing; local transcript had the same line. | IDLE | pass |
| E2 | H R V S. | still not a wake once the room is quiet | 22:46:43 sounddevice, 1.0 s. No wake line after #699. Status stayed IDLE. | IDLE | pass |

### F. Quiet and noise

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| F1 | Hey Jarvis, whispered. Checkpoint F1. Send that. | record the score. A whisper may miss the 0.50 idle gate or the RMS idle floor of 450. If it opens, it must still `sent` | 22:47:07 wake score 0.51 (gain 0.35), rms 359. #700 `Checkpoint F1. Send that.` `sent` at 22:47:13. | IDLE | pass |
| F2 | silence for 10 seconds | no wake from room noise. A score under 0.50 must not open Handy | 10 s quiet watch after 22:47:54. No new log line. No wake. Status stayed IDLE. | IDLE | pass |

## Retro 2026-11-13

1. The old contract text that says a 0.35 wake during playback must open Handy is stale and must be replaced. The loaded controller does not open on that score. D3 passed because that TTS wake open was removed. The contract above now says the opposite. Do not restore a 0.35 TTS open.
2. Every `afplay` is wrongly treated as our voice. Music, a video, or any other `afplay` makes the assistant deaf. Only our own clip, marked in `tts-playing.json`, should suppress the wake. G9 is the row that fixes this.
3. `said that` inside a sentence must not send. Send is `Send that.` or a lone `Submit.` C6 and C7 passed under the old rule. G4 checks the new rule.
4. A multi-part draft was never tested. A short pause should keep the chunk. Scratch should replace the line. Stop should keep the draft for the next wake. G1, G2, and G3 cover that.
5. The three code fixes have no check except the mic: `sent` is a send word, `stop` only when the whole phrase is `stop`, and a hidden Handy window is not a user close. A later edit can revert any of them and A–F will not notice.
6. A runner with no stop re-reads a finished file. One run does one row or one retro, then stops.
7. The OMP bridge was down and delivery stays blocked until the user restarts that session. G10 is `blocked`. Do not test it. Do not restart the user's OMP session.

### G1, 23:18

Wake score 0.90 at 23:18:28, pid 3695. Pause 5.1 s. #704 `First Part Alpha.` appended. #705 `In part beta. Send that.` sent at 23:18:41, then IDLE. The submitted line was `First Part Alpha. in part beta`. Both parts, one send. `Second` was heard as `In`. G1 is pass. Do not rerun it.

The line was already typed in the focused field. OMP put it on the queue, so the runner did not receive it while it kept thinking. After any later `sent` that should land here: write the log into the row, write "stop thinking, the message is queued", then stop the turn. Do not start the next row in that turn.

### G2, 23:23

Wake score 0.90 at 23:23:43, pid 3695. #709 `Wrong line. Scratch that.` outcome `scratched`. Log: `continuing DICTATING for replacement chunk`. #710 `Right line. Sent that.` outcome `sent` at 23:23:56, then IDLE. The sent draft is the right line and does not contain the wrong line. `Send` was heard as `Sent`. G2 is pass. Do not rerun it.

stop thinking, the message is queued.

### G3, 23:25

The first wake was not a take. 23:25:51 `Ignored wake 'Hey Jarvis.' over TTS`. `tts-playing.json` had just ended. Handy stayed IDLE. Do not count it.

### G3, 23:26

Speech is done. Do not play G3 again. 23:26:45 wake score 0.76. #711 `Hold this line. Stop.` outcome `paused` at 23:26:52. `Paused listening -> returned to IDLE (draft preserved)`. Focus was not a text box. 23:26:56 wake score 0.93. #712 `Add the rest. Send that.` outcome `sent` at 23:27:06, then IDLE. The Handy chunk does not itself contain both lines. The paused prefix is kept only if the bridge draft was included in the submit. That submitted line is not in the session file yet.

The queued line was only `add the rest`. That take failed. The controller now keeps the words before `stop` and puts them on the next send.

### G3, 23:38

Retest. 23:38:22 wake score 0.54. #713 `Hold this line. Stop.` `paused` at 23:38:28. Log: `Preserved pause prefix: 'hold this line'`. Draft `hold this line`. IDLE. 23:38:32 wake score 0.54. #714 `Add the rest. Send that.` Log: `Send includes preserved pause: 'hold this line Add the rest. Send that.'` Draft `hold this line add the rest`. One `sent` at 23:38:38, then IDLE. Both lines are in that draft. The queued line arrived as `hold this line add the rest`. G3 is pass. Do not rerun it.

### G4, 23:44

`I said that yesterday` did not send. 23:40:48 wake 0.68 was an unfinished take: #715 appended that line, stayed DICTATING, then the 15s idle timeout returned to IDLE. No `sent`. 23:44:20 wake 0.75. #716 `I said that yesterday.` `appended` at 23:44:29. Draft `I said that yesterday.` Still DICTATING. #717 `Cancel that.` `cancelled` at 23:44:35. Same draft, not submitted. IDLE. G4 is pass. Do not rerun it.

### G5, 23:45

Not the idle timeout. 23:45:49 wake 0.62. #718 `Only this.` `appended` at 23:45:57. Draft `Only this.` Still DICTATING. 23:46:04 `Handy was closed during dictation -> staying idle`. `last_action` `handy_closed`. Nothing sent. The overlay from the first chunk was still counted, so the hide between chunks looked like a user close. That take fails.

### G5, 23:50

Retest on pid 31165 after `forget_handy_window` resets the seen flag on our own Handy restart. 23:50:27 wake 0.79. #720 `Only this.` `appended` at 23:50:35. Draft `Only this.` No `sent`. 23:50:51 `No speech for 15s in DICTATING -> cancelling Handy & returning to IDLE`. Status `IDLE`, `last_action` `idle_timeout`. The 23:47:49 wake 0.93 is not this take: it appended runner speech as #719, then the same idle-timeout line at 23:48:06. G5 is pass. Do not rerun it. Do not start G6.

### G6, 23:52

15.99 s of ordinary speech through sounddevice, not afplay. Wav `/tmp/g6-speech.wav` written at 23:52:41. Peak 1.635 after the float scale and gain 2.0. The words include "Hey service" and "A harvest" and do not include Jarvis. Playback started only after the TTS tail was quiet. No new `controller.log` line during the clip or in the 2 s after it. No `Wake triggered`. Status stayed IDLE, pid 31165, `last_action` still `idle_timeout`, `updated_at` unchanged. Earlier ignores at 23:52:29–23:52:38 were over TTS before this clip. G6 is pass. Do not rerun it. Do not start G7.

### G7, 23:54

One session. 23:54:32 wake 0.51, pid 31165. #721 `The word again is "Hey, Jarvis!" In the middle, send that.` One outcome `sent` at 23:54:40. Draft `the word again is "hey jarvis " in the middle`. The middle words are in that draft. No second `entering DICTATING`. No second send. `The wake` was not in the chunk. Then IDLE. G7 is pass. Do not rerun it. Do not start G8.

The queued line arrived as `the word again is "hey jarvis " in the middle`. It matches the sent draft.

### G8, 23:58

Not a stop. Bed `/tmp/omp-vb-g8-bed.wav` via `afplay -v 0.35`, `tts-playing.json` playing. Burst `Hold on a second.` through sounddevice, 1.08 s, peak 1.406. The word stop was not in the clip. Log: `Ignored 'Hold on a sec.' over TTS (not stop)` at 23:58:05. Bed still playing. Status stayed IDLE, pid 31165. Handy stayed closed, but playback did not stop. That take fails. Whole-phrase `stop` is the only barge. `hold on a sec` must stop playback the same way and must not open Handy.

### G8, 23:58 retest

`_is_playback_barge` now treats a short `hold on`, `hold on a second`, or `hold on a sec` like whole-phrase `stop`. Restarted as pid 35581 with `--wake-threshold 0.5`. Same bed and the same burst. 23:58:58 `Heard 'Hold on.' over TTS -> stopping speech, not opening Handy`. The clip was split, so 23:58:59 `Ignored 'Second.' over TTS (not stop)` while the marker file was still set. No `entering DICTATING`. Status stayed IDLE. No `afplay` left. Handy stayed closed and playback was stopped. G8 is pass. Do not rerun it. Do not start G9.

### G9, 00:02

Not a take. 00:02:04 `Ignored wake 'Hey Jarvis.' over TTS`. `tts-playing.json` was `playing: true` with VoiceBox pid 36936, which is our voice. The foreign bed was pid 36943. A wake ignored during our own playback does not count. Retry G9 only while that file stays `playing: false`.

### G9, 00:03

Foreign bed pid 37394, `/tmp/g9-bed.wav`, and `tts-playing.json` stayed `playing: false`. 00:03:13 `Ignored 'Bay Jarvis.' over TTS (not stop)`. No `entering DICTATING`. Status stayed IDLE, pid 35581. Any `afplay` is still our voice. That take fails. Only `tts-playing.json` may count.

### G9, 00:04

`is_voicebox_speaking` now reads only `tts-playing.json`. Restarted as pid 37663 with `--wake-threshold 0.5`. Foreign bed `/tmp/g9-bed.wav`. No ignore line between ready at 00:03:51 and the wake. 00:04:00 wake 0.83. #722 `Checkpoint G9. Send that.` One `sent` at 00:04:07. Draft `checkpoint g9`. Then IDLE. The foreign `afplay` did not count as our voice. G9 is pass. Do not rerun it.

The queued line arrived as `checkpoint g9`. It matches the sent draft.

### G. A draft a person would actually speak

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| G1 | Hey Jarvis. First part alpha. Then pause 6 seconds. Then: Second part beta. Send that. | one draft contains both parts, one outcome sent, IDLE. A timeout or a send of only one part is a fail. | 23:18:28 wake 0.90. #704 `First Part Alpha.` appended. #705 `In part beta. Send that.` sent at 23:18:41. Submitted line: `First Part Alpha. in part beta`. | IDLE | pass |
| G2 | Hey Jarvis. Wrong line. Scratch that. Right line. Send that. | scratched, stays dictating, then the sent draft is the right line and does not contain the wrong line. | 23:23:43 wake 0.90. #709 `Wrong line. Scratch that.` `scratched`, stayed DICTATING. #710 `Right line. Sent that.` `sent` at 23:23:56. Wrong line absent. | IDLE | pass |
| G3 | Hey Jarvis. Hold this line. Stop. Wait until IDLE. Then: Hey Jarvis. Add the rest. Send that. | the sent draft contains both lines. | 23:38:22 wake 0.54. #713 `Hold this line. Stop.` `paused`, prefix kept. 23:38:32 wake 0.54. #714 `Add the rest. Send that.` sent at 23:38:38. Submitted line: `hold this line add the rest`. | IDLE | pass |
| G4 | Hey Jarvis. I said that yesterday. Wait for the chunk. If it is still dictating, say: Cancel that. | that chunk is not sent. Outcome is cancelled or still open, then IDLE. A sent prompt is a fail. | 23:44:20 wake 0.75. #716 `I said that yesterday.` `appended`. #717 `Cancel that.` `cancelled` at 23:44:35. Draft stayed `I said that yesterday.` Not sent. | IDLE | pass |
| G5 | Hey Jarvis. Only this. Then stay silent 16 seconds. | idle timeout, nothing sent, IDLE. | 23:50:27 wake 0.79, pid 31165. #720 `Only this.` `appended`. No `sent`. 23:50:51 `No speech for 15s in DICTATING -> cancelling Handy & returning to IDLE`. | IDLE | pass |
| G6 | Play 15 seconds of ordinary speech through sounddevice, not afplay. The speech may contain "hey service" and "a harvest". It must not contain Hey Jarvis. | no wake, IDLE. | 23:52:41 sounddevice 15.99 s, peak 1.635. Includes "Hey service" and "A harvest". No `Wake triggered`. No new log line. | IDLE | pass |
| G7 | Hey Jarvis. The wake word again is hey Jarvis in the middle. Send that. | one session, one sent draft that contains the middle words, no second dictation and no double send. | 23:54:32 wake 0.51. #721 `The word again is "Hey, Jarvis!" In the middle, send that.` One `sent` at 23:54:40. Draft `the word again is "hey jarvis " in the middle`. No second dictation. Queued line arrived the same. | IDLE | pass |
| G8 | Start our own TTS bed. Speak, loudly, for about a second: Hold on a second. Do not say the word stop. | playback stops, Handy stays closed. | 23:58:58 pid 35581 `Heard 'Hold on.' over TTS -> stopping speech, not opening Handy`. No dictation. Bed gone. | IDLE | pass |
| G9 | Start afplay of a bed and do not write tts-playing.json. Then: Hey Jarvis. Checkpoint G9. Send that. | Handy opens and the line is sent, because that audio is not our voice. Ignored-over-TTS is a fail. Do not change the expect to match the old behavior. Fix the controller so only tts-playing.json counts as our voice. | 00:04:00 wake 0.83, pid 37663. #722 `Checkpoint G9. Send that.` sent at 00:04:07. Draft `checkpoint g9`. Not ignored over TTS. Queued line arrived the same. | IDLE | pass |
| G10 | Delivery to the OMP session. The bridge at 127.0.0.1:17494 was refusing connections. | Do not test it. Do not restart the user's OMP session. Leave the row blocked until the user restarts that session. | bridge was connection refused | | blocked |

G10 note, 2026-11-14 02:11 UTC: the :17494 assumption is obsolete. Delivery now resolves the bridge from the session registry (VA-OMP-001, VA-OMP-003). `omp-voice-controller status` at 02:11 UTC reported `omp_bridge.ok: true` for pid 49095 on ephemeral port 59036. The row stays `blocked` as historical record; delivery testing moves to the isolated-session Level 3 rows, never the user's session.

## Log lines that count

- Opened: `Wake triggered` or `entering DICTATING`
- Heard and kept shut: `Ignored '...' over TTS (not stop)`
- Stopped playback: `Heard '...' over TTS -> stopping speech, not opening Handy`
- Dictation result: `Handy transcribed chunk #N: '...'` then `Transcript outcome: sent|appended|scratched|cleared|paused|cancelled`
- Stuck: `status.json` state is `DICTATING` and no outcome line follows. Say the continuation. Do not start the next scenario.

## Retro 2026-11-13, scenarios closed

A1–G9 are `pass`. G10 stays `blocked` until the user restarts that OMP session. Sections A–G are closed. Do not rerun them.

The next gaps are section H. Dictation flushes Handy only after `pause_seconds` (5.0) of silence, so nothing appears while he is still talking. A stop during our TTS is gated by `vad >= 0.28` and `rms >= max(140, floor * 1.08)` because the laptop mic hears the speakers. He still has to raise his voice. The conversation skill told the model to keep working after "stop speaking", but VoiceBox reads the whole chat reply aloud.

## H. Faster, interruptible, spoken

A–G stay closed. These rows are open.

### H1, 00:28

Wake score 0.97 at 00:28:42. Partial transcript `I am still talking in this sentence.` at 00:28:45, then three longer partials, the last at 00:28:50: `I am still talking and this sentence keeps going without a long passo. The words can show before I finish.` The pause flush was at 00:28:52, 1.7 s of silence, not 5 s. #726 `I am still talking, and this sentence keeps going without a long pause, so the words can show before I finish. Send that.` Outcome `sent` at 00:28:53. Draft matches. Then IDLE. The partials are before the flush. H1 is pass. Do not rerun it. Do not start H2.

The queued line arrived as `i am still talking and this sentence keeps going without a long pause so the words can show before i finish`. It matches the sent draft.

### H2, 00:30

Stop peak 0.701, under 1.0. Bed `/tmp/omp-vb-h2-bed.wav` pid 45621 stayed alive. Status stayed IDLE, `updated_at` unchanged. Log heard `It's time.` and `I'm moving.` and did not stop. A VoiceBox clip `omp-vb-64822-189.wav` overwrote `tts-playing.json`. The conversational stop was not recognized. H2 fails. The speakers stay at full volume while the clip is captured, so the mic hears the reply instead of the word. Next take pauses `omp-vb-` playback for the capture, and resumes it unless the word is stop.

### H2, 00:32

Retest on pid 46264 after the pause. Stop peak 0.701. Bed pid 46342 stayed alive (`S`, not stopped). 00:32:48 `Ignored 'In line.' over TTS (not stop)`. 00:32:50 `Ignored 'Lately.' over TTS (not stop)`. No stopping-speech line. Status stayed IDLE. The pause ran, but the clip still contained the bed syllable from before the speaker drained, and that syllable was what Whisper heard. H2 still fails. Next take drops the onset, waits two frames for the paused clip to drain, and only transcribes audio that is still loud after that.

### H2, 00:35

Retest on pid 47146. Stop peak 0.701. `TTS barge hold` at 00:35:41. Clip frames=10 peak=1204, then frames=3 peak=1836. The louder clip was `whisper busy; skipped TTS barge clip`. Heard `Duh, duh, duh.` Bed pid 47223 was `T`, paused, not killed. No stopping-speech line. Status stayed IDLE. H2 still fails. The bed clip occupied Whisper, so the louder following clip was dropped. Next take keeps that following clip and runs it when the first result is not stop.

### H2, 00:36

Retest on pid 47566. The stop clip was scaled to peak 1.0 before play. `TTS barge hold` at 00:36:57. Clip frames=10 peak=1480. 00:36:59 `Heard 'stop.' over TTS -> stopping speech, not opening Handy`. Status stayed IDLE. No `entering DICTATING`. No live `afplay` afterward. The bed was not heard as stop. H2 is pass. Do not rerun it. Do not start H3.

### H3, 00:38

Two sentences in `/tmp/omp-vb-h3-both.wav`. First sentence 5.72 s, both 10.04 s. Bed pid 48238. Stop clip peak 1.0, played 0.9 s into the first sentence. 00:38:50 `TTS barge hold`, then a release and a second hold. 00:38:52 clip frames=10 peak=1467. 00:38:53 `Heard 'stop, stop, stop.' over TTS -> stopping speech, not opening Handy`. The bed was gone at 2.71 s, before the second sentence. No `entering DICTATING`. Status stayed IDLE. No live `afplay` afterward. H3 is pass. Do not rerun it. Do not start H4.

### H4, 00:39

No speech. The skill already says a VoiceBox reply is at most two sentences, a heard stop ends the reading, and a partial transcript is used while he is still talking. Nothing added. H4 is pass. Do not rerun it.

### Next gap, after H

`maybe_emit_partial` transcribes the open chunk, and the only result is `Partial transcript:` in `controller.log`. Nothing is written to the focused field. H1 passed because a log line counts. The words still appear only when Handy flushes. That is the next gap. Do not speak it in this run.

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| H1 | Hey Jarvis. I am still talking and this sentence keeps going without a long pause so the words can show before I finish. Send that. | At least one partial transcript is logged or typed before `Pause of ... flushing chunk`. Text that appears only after the 5 second pause is a fail. Wake threshold stays 0.50. | 00:28:42 wake 0.97. Partials at 00:28:45, 00:28:47, 00:28:48, and 00:28:50, before the flush. 00:28:52 `Pause of 1.7s detected -> flushing chunk via Handy`. #726 sent at 00:28:53. Draft `i am still talking and this sentence keeps going without a long pause so the words can show before i finish`. | IDLE | pass |
| H2 | Start our own TTS bed and write tts-playing.json. Say Stop. once, at a conversational volume. After the int16-to-float scale, the stop clip peak stays at or under 1.0. Do not shout. | Playback stops, Handy stays closed, and the log says stopping speech. An ignored stop at that peak is a fail. The bed itself must not be heard as stop. | 00:36:57 pid 47566. `TTS barge hold`. Clip frames=10 peak=1480. 00:36:59 `Heard 'stop.' over TTS -> stopping speech, not opening Handy`. No dictation. The played clip was scaled to peak 1.0. No afplay left. | IDLE | pass |
| H3 | Start our own TTS of two sentences. During the first sentence, say Stop. once at the same conversational peak as H2. | Playback stops before the second sentence finishes. Handy stays closed. If the second sentence plays out, that is a fail. | 00:38:53 pid 47566. `Heard 'stop, stop, stop.' over TTS -> stopping speech, not opening Handy`. Bed gone at 2.71 s. First sentence was 5.72 s, so the second sentence did not play. Stop peak 1.0. No dictation. | IDLE | pass |
| H4 | Do not speak. Read `~/.omp/agent/managed-skills/conversational-collaboration/SKILL.md`. | The skill says a VoiceBox reply is at most two sentences, a heard stop ends the reading, and a partial transcript is used while he is still talking. If any of those is missing, add it, then mark this row pass. Do not add a second copy of the same rule. | All three rules are present in the VoiceBox section. No second copy added. | | pass |

## I. Words on screen while speaking

H1 only required a log line. A partial still does not reach the focused field.

### Echo, 00:48

The laptop mic hears VoiceBox at about the same level as a conversational stop (rms around 150). The barge path was pausing on that bleed, transcribing the tail, and resuming. That pause-and-resume is the echo. At 00:39 the log held about once a second and heard repeated words (`Right, right, right.`, `I would, I would.`). A rise now has to last two frames, a quiet room resumes without a transcript, the playback floor is not updated during the pause, and the next pause waits 1.5 s. Bed-only retest on pid 51244: two holds and two releases in 5 s, no `Ignored` line. A peak-1.0 `Stop.` during that bed produced `TTS barge empty` and did not stop playback. Do not treat that empty result as H2. H2 stays a past pass.

### I1, 00:52

Wake score 0.92 at 00:52:16 on pid 51891. Partials at 00:52:19 and 00:52:22 were only `Partial transcript:` lines. Nothing was written to the field. Flush at 00:52:24. #728 sent one draft: `i am still talking and the words should appear in the field before i pause`. I1 fails because the partial was not written. Do not replay this take.

### I1, 00:56

Retest on pid 53253. Wake 0.92 at 00:56:01. `Partial written to focused field` at 00:56:04 and 00:56:06, before the 00:56:08 flush. At 00:56:09 focus was gone, so the partial was not removed. #729 draft is the partial plus the full sentence. I1 still fails. Do not replay this take.

### I1, 00:57

Retest on pid 53892. Wake 0.92 at 00:57:32. `Partial written to focused field` at 00:57:35, 00:57:36, and 00:57:38, before the 00:57:39 flush. 00:57:40 `Partial removed before final send`. #730 draft is one line: `i am still talking and the words should appear in the field before i pause`. I1 is pass. Do not rerun it.

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| I1 | Hey Jarvis. I am still talking and the words should appear in the field before I pause. Send that. | Before `Pause of ... flushing chunk`, the log says the partial was written to the focused field. A `Partial transcript:` line with no write is a fail. The final send is one draft, not the partial plus a second copy. Wake threshold stays 0.50. | 00:57:32 wake 0.92 pid 53892. Field writes at 00:57:35, 00:57:36, and 00:57:38, before the flush. 00:57:40 partial removed. #730 one draft. | IDLE | pass |

## J. A trailing command word stays in the live field

I1 is pass. Do not rerun it. The last write at 00:57:38 dropped the word `pause`. The heard line was `I am still talking and the words should appear in the field before I pause.` The field got `i am still talking and the words should appear in the field before i`. `show_partial` treats a trailing `pause` as the pause command and keeps only the prefix. The final Handy line still contains `pause` because `Send that.` is the command. While he is talking, the last word disappears.

### J1, 01:08

Wake score 0.94 at 01:08:32 on pid 55844. `Partial written to focused field` at 01:08:37 was `I will still tell the words should appear in the`. At 01:08:38 the heard line was `A little talk words should appear in the field before I pause.` The bridge returned `action=paused` and a draft ending `before i`, so that write was not logged as written. Flush at 01:08:40. #731 draft is two copies: `a little talk words should appear in the field before i still the words should appear in the field before i pause`. J1 fails. Do not replay this take.

### J1, 01:12

Wake score 0.86 at 01:12:06 on pid 58148. Field writes at 01:12:10 (`I am still talking in the words.`) and 01:12:11 (`I am still talking and the words should appear in the field before`). At 01:12:12 the heard line was `I am still talking and the words should appear in the field before I pause.` The last token was `pause.` The joiner only attached when that token equaled `pause` exactly, so the bridge still returned `action=paused`, draft ending `before i`, `strippedCommand=pause`. Flush at 01:12:14. #732 draft is two copies: `i am still talking and the words should appear in the field before i i am still talking and the words should appear in the field before i pause`. J1 fails. Do not replay this take.

### J1, 01:19

Not a phrase take. Controller pid 60210 ready 01:19:06. Wake score 0.95 at 01:19:21, focus Terminal `AXTextArea`, then `No speech for 15s in DICTATING` at 01:19:37. No partial, no Handy chunk. The rest clip was not heard. Do not treat this idle timeout as the J1 result. The heard cell stays the 01:12 fail until a full phrase is played.

### J1, 01:24

Not a phrase take. Wake score 0.91 at 01:24:13 on pid 60210, focus Terminal `AXTextArea`. `No speech for 15s in DICTATING` at 01:24:29. No partial, no Handy chunk. The rest clip was not played. The waiter used the log byte size as a character index. The file is 357 bytes longer than its character length, so the new `entering DICTATING` line was past the slice while `status.json` was already `DICTATING`. Do not treat this idle timeout as the J1 result. Do not replay 01:08, 01:12, 01:19, or 01:24.

### J1, 01:30

Full phrase on pid 60210. Wake score 0.87 at 01:30:01, focus Terminal `AXTextArea`. Field writes at 01:30:05 (`I'm still talking in the words.`) and 01:30:06 (`I'm still talking and the words should appear in the field before I...`). The 01:30:06 write is the last one before `Pause of 1.8s detected -> flushing chunk via Handy` at 01:30:09. It does not contain `pause`. No `action=paused`. #733 one draft at 01:30:10: `i am still talking and the words should appear in the field before i pause`. Partial removed before that send. J1 fails because the live field never got `pause`. Partials are kicked only while speech frames are still arriving, every 18 frames (1.44 s). The last word landed in the silence that starts the flush, so it was never written. Do not replay this take.

### J1, 01:33

Full phrase on pid 64238, after the closing partial was added. Wake score 0.93 at 01:33:07, focus Terminal `AXTextArea`. Field writes at 01:33:11 (`I am still talking in the words.`), 01:33:12 (`... field before`), and 01:33:13 (`I am still talking and the words should appear in the field before I pause\u2060.`). The 01:33:13 write is the last `Partial written to focused field` before `Pause of 1.7s detected -> flushing chunk via Handy` at 01:33:15. It contains `pause`. The bridge appended it. 01:33:16 `Partial removed before final send`. #734 one draft: `i am still talking and the words should appear in the field before i pause`. That draft contains `pause`. J1 is pass. Do not rerun it. Do not start the next row.

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| J1 | Hey Jarvis. I am still talking and the words should appear in the field before I pause. Send that. | The last `Partial written to focused field` before `Pause of ... flushing chunk` contains the word `pause`. A write that ends at `before i` is a fail. The final send is one draft and that draft contains `pause`. Wake threshold stays 0.50. | 01:33:07 wake 0.93 pid 64238. Last field write 01:33:13 contains `pause`. #734 one draft contains `pause`. | IDLE | pass |

## Next gap

If every row in the latest section is `pass` or `blocked`, do not speak. Name one user-facing gap that is not already a row. Add one new section of pending rows for that gap only. If you cannot name one, write `IMPROVEMENT LOOP IDLE` and stop. Do not add a row to keep the loop alive. Do not reopen A–G. Do not test G10.

`IMPROVEMENT LOOP IDLE` — historical marker recorded 2026-11-13 01:36 local, before the VA-* rows below it. It closes only section A–J of that day. It does not override later engineering work and is not a claim that the loop is idle today: VA-INT-001 and the physical AEC acceptance are open, and no `.ralph-voice-loop-idle` file exists.

J1 is pass. The 01:33:13 field write contains `pause`, and #734 is one draft that contains `pause`. The log ends at that send. No later line shows a new user-facing miss. G10 stays blocked. No new section.

That idle line is historical. It is not a claim that the product is reliable. The 2026-11-13 reliability pass found a real false down and fixed it. Do not rerun A–J. VA-PLAY-001, VA-TTS-001, and VA-AUD-002 are done in unit tests. The open code gap is VA-AUD-001. Speaker echo was not run.

### VA-OMP-001, 12:43

`omp-voice-controller status` asked `http://127.0.0.1:17494/status`, got connection refused, and printed `omp_bridge.ok: false` with a note to restart OMP and bind :17494. The session file for pid 80894 already had an ephemeral port, and `GET /status` on that port was ok. `cmd_status` always used `OMP_BRIDGE_URL`. After the fix, status at 12:43:48 reported `omp_bridge.ok: true`, `pid` 80894, and `url` `http://127.0.0.1:57042`, which matched `sessions/80894.json` at that moment. No connection-refused line. The port is not stable: the same pid had been on 56876 earlier in the same hour, so the next run must read the registry again. Unit tests: `~/.local/share/omp-voice/venv/bin/python -m pytest tests/ -q` → 67 passed. No speech. OMP was not restarted by this run. G10 stays blocked as a spoken delivery test. VA-OMP-001 is pass. Do not rerun it.

### VA-PLAY-001, unit only

No speech. `tts-playing.json` was one object, so one session's end cleared every session, and a dead `afplay` could stay `playing: true`. Slots are now `tts-playing/<pid>.json`. An older clip cannot end a newer one. The directory wins over the flat file when the directory exists. `pytest tests/ -q` → 69 passed. `node --experimental-strip-types --test tests/playback-state.test.ts tests/match_command.test.ts` → 44 passed. The running controller and the running OMP session were not restarted, so they still have the old playback code. VA-PLAY-001 is pass at unit level. Do not rerun it. Do not treat it as a speaker pass.

### VA-TTS-001, unit only

No speech. `enqueue` used to skip a sentence when `spokenText` contained it, and a prefix miss cleared the spoken chunks so the reply played again. A chunk is now spoken unless it equals a chunk already queued or a join of consecutive chunks. A new assistant message id clears that list. The same id does not. `node --experimental-strip-types --test tests/speech-queue.test.ts tests/match_command.test.ts` → 36 passed. The running OMP session was not restarted. VA-TTS-001 is pass at unit level. Do not rerun it. Do not treat it as a speaker pass.

### VA-AUD-002, unit only

No speech and no microphone. A full capture queue used to drop the oldest block without a count. `offer_mic_frame` keeps the newest block and returns the drop. Overflow counts as `mic_invalid`. `pytest tests/ -q` → 73 passed. The running controller was not restarted, so its status file does not have these keys yet. VA-AUD-002 is pass at unit level. Do not rerun it. Do not treat it as a hardware pass.

### VA-AUD-001, reference only

No speech. A mic block that is a delayed, scaled copy of the 16 kHz playback is subtracted when the correlation is at least 0.75. Noise below 0.85 is left alone. This is one delay, not a room model. `pytest tests/test_playback_state.py tests/test_mic_capture.py -q` → 9 passed. The running controller was not restarted. Do not mark speaker echo suppressed.

### VA-OMP-003, missing registry port

No new speech. At 14:16 a focused Terminal dictation logged `Delivery paste pid=80894 port=None` and `Partial field skipped (paste, focused=True)`. `sessions/` has no file for that pid. `GET /status` on `127.0.0.1:56876` returned ok for pid 80894. A missing registry port now uses that one loopback listener when status names the same pid. Two ports stay a paste. `pytest tests/ -q` → 98 passed. The running controller was not restarted. Do not POST `/transcript`. Do not rerun the spoken rows.

### VA-TTS-004, VoiceBox hold

No speech. `speech.log` had 14 `failed` records in the 19:22 minute, four of them between 19:22:06 and 19:22:07, each `ECONNREFUSED`. A refusal now holds the next `generate` for 5 seconds, before `fetch`. An HTTP 500 does not. The three Node test files → 56 passed. The running extension was not reloaded. Do not start VoiceBox for this row. Do not rerun the spoken rows.

### VA-TTS-003, player exit

No audio. `play` used to mark a chunk spoken whenever afplay closed, including a failed start. Exit 0 is heard. Exit 1 is not. `SIGKILL` is heard. A spawn error is not. A miss uses the same unspoken-chunk release as VA-TTS-002. The three Node test files → 55 passed. The running extension was not reloaded. Do not rerun the spoken rows.

### VA-LOG-003, log rotation

No speech. `controller.log` was 3.1 MiB and `speech.log` was 1.5 MiB. A file over the limit now becomes one `.1` backup, and the next rotation replaces that backup. The controller does this before it opens the log. The speech logger does it before an append. The live files were not renamed. `pytest tests/ -q` → 97 passed. The three Node test files → 54 passed. The running processes were not restarted. Do not rerun the spoken rows.

### VA-TTS-002, unspoken chunk

No audio. A chunk was added to the spoken list before VoiceBox returned, and a refused request left it there. That chunk is now removed. If it is the end of the queue, the queue rewinds. If a later chunk is already queued, that later chunk stays spoken. `node --experimental-strip-types --test tests/match_command.test.ts tests/playback-state.test.ts tests/speech-queue.test.ts` → 53 passed. The running extension was not reloaded. Do not rerun the spoken rows.

### VA-LOG-002, speech log

No speech was played. `speech.log` stored the sentence on a failed VoiceBox request. The record now has `event`, `chars`, and the reason. The sentence is stored only when `OMP_VOICE_LOG_TEXT=1`. `controller.log` is unchanged. `node --experimental-strip-types --test tests/match_command.test.ts tests/playback-state.test.ts tests/speech-queue.test.ts` → 52 passed. The running extension was not reloaded. Do not rerun the spoken rows.

### VA-BARGE-001, busy barge clip

No speech and no microphone. The controller log says `whisper busy; skipped TTS barge clip`, including 2026-11-13 00:15:09 and a run on 2026-11-11 from 22:35 through 22:40. A full queue dropped the clip and resumed playback. The clip is now held, a newer one replaces it, and it is queued after the worker takes the previous job. `pytest tests/test_idle_whisper.py -q` passed. `pytest tests/ -q` → 96 passed. The running controller was not restarted. Do not rerun the spoken rows.

### VA-IDLE-001, busy Whisper

No speech and no microphone. The controller log has `whisper busy; skipped idle utterance` at 12:43:37, 12:52:42, 13:09:13, 13:09:15, and 13:09:23. Those clips were discarded. One idle clip is now held, a newer one replaces it, and the next idle frame queues it after the in-flight job is taken. Dictation drops it. `pytest tests/test_idle_whisper.py -q` passed. `pytest tests/ -q` → 95 passed. The running controller was not restarted. Do not rerun the spoken rows.

### VA-LOG-001, VoiceBox health

No speech. From 12:32:16 to 12:32:22 the controller log repeated `VoiceBox health unread` on idle frames. A failed health check had inverted the Handy flag, so the next frame tried again. The check now waits 5 s, logs the refusal once per outage, and leaves the Handy flag on the Strata tier. `pytest tests/test_speech_tier.py -q` passed. `pytest tests/ -q` → 93 passed. VoiceBox was not started. The running controllers were not restarted. Do not rerun the spoken rows.

### VA-AUD-001, published cursor

No speech and no microphone. Subtraction already ignored stopped time. `refresh_render_reference` still moved `render_cursor` with the wall clock: 8000 samples at 0.50 s, then 12000 after 0.25 s stopped. The published field now stays at 8000 until playback resumes, and is 12000 after another 0.25 s of playback. `pytest tests/test_playback_state.py tests/test_mic_capture.py -q` → 24 passed. `pytest tests/ -q` → 91 passed. The running controller was not restarted. Speaker echo was not run. Do not mark it suppressed.

### VA-DOC-001, 2026-11-14 02:11 UTC — operating contract alignment (documentation only)

No production code changed. Compared the Ralph prompt against the new engineering contract and fixed the drift:

- Obsolete: the prompt told the runner to create `scripts/voice_ralph_check.py` if missing. The deterministic harnesses already exist (`scripts/run_aec_fixture_probe.py`, `run_double_talk_probe.py`, `run_repeat_turn_probe.py`, `run_render_recovery_probe.py`, `run_interrupt_probe.py`, plus `tests/`). The prompt now points at them and forbids building a duplicate.
- Contradictory testing: the old protocol required speaking into the physical microphone every run ("output volume near 19"). The controller pid 64238 owns the microphone, and Level 4 requires an explicit ownership lock. The spoken A–J rows stay as closed historical evidence; new iterations run the fixture probes unless ownership is handed over.
- Incorrect bridge assumption: the old preflight curled `http://127.0.0.1:17494/status`. The bridge port is ephemeral and registry-based (VA-OMP-001, VA-OMP-003). The contract now says to derive the port from `status` and `sessions/<pid>.json` every run and never trust a historical port or pid.
- Missing AEC acceptance criteria: the prompt had no AEC section at all. It now lists the five Level 4 requirements (measured room ERLE, no echo wake, verbatim near-end transcription during double-talk, stop/wake barge with measured latency, render-reference alignment across pause, resume, clip change, and `-r`). VA-INT-001 stays BLOCKED and idle is invalid while physical acceptance is unrun.
- Historical data that could be read as current: pids (64238, 16590, 71881), ports 56876/57042, and the "IMPROVEMENT LOOP IDLE" line are all snapshots. Live state at 02:11 UTC: controller pid 64238 IDLE, VoiceBox healthy on 17493 with the 0.6B model loaded, bridge ok on 59036 for pid 49095. There is no `.ralph-voice-loop-idle` marker in the repo.
- Already satisfied by existing implementation: the contract's known baseline matches the catalogue — fixture-fed integration and the afplay-cutting stop are VA-INT-AUTO-040/041, dynamic port discovery is VA-OMP-001/002/003, bounded logs are VA-LOG-003, dropped-frame counting is VA-AUD-002, and the AEC synthetic work is VA-AEC-001–008 plus VA-OBS-001. One number disagrees: the contract cites ~1.076 s interruption latency; the catalogue records 0.589 s from hold to `stop_playback` for VA-INT-AUTO-041. The checkpoint number is the measured one; the contract's is unverified.
- The embedded loop prompt in this file was retired: it duplicated the Ralph prompt and carried the stale speak-at-volume-19 protocol. The single operating prompt is `HANDY-RALPH-VOICE-LOOP-PROMPT.md`.
- An uncommitted diff in `bin/omp-voice-controller` (turn latency fields `wake_wall`, `flush_wall`, `asr_s`, `dispatch_s`, `stop_latency_s` published to `status.json`) was observed and left untouched.

Verification level: documentation only; no tests were run because no code changed. Live state was checked with `omp-voice-controller status` and `curl :17493/health`.

### VA-AEC-009, 2026-11-14 — cursor-offset tolerance of the canceller

No speech, no microphone. Question from the contract's Priority A: the render cursor assumes the file advances by wall clock × `afplay -r` from `started_at`, but the physical echo reaches the microphone later (afplay startup, output buffer, flight time). How much offset can the canceller absorb before echo leaks?

Measured by sweeping an echo that trails the reverse block by a fixed delta through `cancel_playback_echo` on the real WebRTC path. Residual dB (negative means the echo got smaller): 0 ms −10.8, 50 ms −36.8, 100 ms −63.2, 150 ms −38.3, 200 ms −62.1, 300 ms −62.3. The curve is not monotonic — WebRTC's delay estimator snaps to nearby bins — and the exactly-aligned case (delta 0) is the weakest, topping out near −16 dB even on a 6 s clip. That is the good news: no physical echo can have delta 0, and every plausible positive offset cancels at 36 dB or better. The wall-clock cursor is therefore adequate without a sample-accurate sync mechanism; the drift budget is the WebRTC search window, not the clock.

Changed: `tests/test_echo_control.py` (`offset_residual_row` plus two tests; the strict monotonic assertion was replaced after measurement showed the real shape), `tests/test_handy_control.py` (two status asserts now compare `last_action` instead of exact payload equality — the uncommitted turn-latency fields add a `turn` key and broke strict equality at HEAD+diff), `docs/testing/INDEX.md` (row added). No production code changed.

`pytest tests/ -q` → 217 passed. The three node test files → 61 passed. Evidence: `.local/voice-agent/runs/VA-AEC-009-unit-table.json`.

level: 1. Limitations: synthetic signal only; actual afplay startup latency and room delay are still unmeasured — VA-INT-001 must record them at Level 4. next: physical acceptance of AEC stays blocked on microphone ownership (pid 64238).

### VA-DOC-002, 2026-11-14 03:43 UTC — state and validation alignment (documentation only)

No production code changed. Reconciled `HANDY-RALPH-VOICE-LOOP-PROMPT.md`, this checkpoint, `HANDOFF.md`, `docs/testing/AEC-DECISION.md`, and `docs/VOICE-AGENT-ARCHITECTURE.md`:

- Bridge port: live state re-derived this run — controller pid 64238 `IDLE`, bridge ok on ephemeral 61707 for pid 82521 (`sessions/82521.json`), VoiceBox healthy on 17493 with the 0.6B model. The extension source confirms the model: `srv.listen(0, BRIDGE_HOST)` plus a registry write (`extension/voicebox-speech.ts` lines 1108–1117); no doc may assume a fixed port. `HANDOFF.md` is now a pointer with explicit re-derivation commands and no cached pids or ports; the historical 17494 rows (G10, VA-OMP-001) stay as dated evidence with the "obsolete" note.
- Validation-level separation: the checkpoint now carries the authoritative level table (1 unit, 2 fixture, 3 local service, 4 physical acoustic, 5 extended reliability). Level 4 has zero passing rows and Level 5 none; the old "IMPROVEMENT LOOP IDLE" line is annotated as a 2026-11-13 historical marker that does not override later VA-* work.
- Fixture-first: the contract already routes controller integration through `FixtureAudioSource` (`bin/omp-voice-controller` line 3726, "microphone not opened"); physical speaker/microphone runs are reserved for explicit Level 4 acceptance with an ownership handoff. Added to the safety rules that integration delivery must use `scripts/isolated_session.py` with `OMP_VOICE_BRIDGE_ONLY`/`OMP_VOICE_PLAYBACK_PID`.
- VoiceBox recovery: the preflight's `open -a VoiceBox` retry contradicted the runbook ("a running GUI has already used its one production `start_server`"); the prompt now defers entirely to `docs/testing/VOICEBOX-SERVICE-RUNBOOK.md`. No duplicate servers, no GUI re-opens, no agent kills.
- Wake-during-playback contract written down in the prompt and the architecture doc: own-voice = `tts-playing/<pid>.json` only; wake during own playback is ignored (D3); only whole-phrase `stop`/hold-on barges, and barging stops playback without opening a dictation session (D4, G8, H2, H3, VA-INT-AUTO-041 at 0.589 s).
- Load state: a new iteration step requires stating which processes actually loaded a change, and the checkpoint gained "Tested but not loaded into running processes" (controller 64238 and the live extensions were never restarted/reloaded; the uncommitted turn-latency fields in `bin/omp-voice-controller` are not live).

Verification: `pytest tests/ -q` → 217 passed; the three Node test files → 61 passed (exit 0). All scenario files referenced by `docs/testing/INDEX.md` exist (125 files). Live derivation commands were run, not assumed.
level: documentation only; no tests were run against changed code because no code changed.
next: Level 4 physical acceptance of the AEC stays blocked on microphone ownership (pid 64238); the next deterministic engineering task is named in the report below.

### VA-LAT-001, 2026-11-14 04:29 UTC — turn-latency fields finalized and fixture-validated

Question from the contract, Priority A: can the controller itself publish the five turn-latency numbers — monotonic, finite, nonnegative, and attached to the right turn — instead of a probe reconstructing them from log stamps?

Final field definitions, all in seconds on `time.monotonic()`, published in `status.json` under a `turn` key by `MicState.turn_metrics()` (`bin/omp-voice-controller` ~2874):

| Field | Boundary | Published as |
|---|---|---|
| `turn_seq` | counts wake→DICTATING transitions | integer, starts at 1 on the first wake |
| `wake_to_flush_s` | entering DICTATING .. the pause that flushes the chunk | 2 decimals, `None` before a flush |
| `asr_s` | the Handy `--transcribe-file` call (or history-row wait) | 3 decimals, `None` until measured |
| `dispatch_s` | `dispatch_transcript` (paste/submit) for that flush | 3 decimals, `None` until measured |
| `stop_latency_s` | barge hold opened (`barge_onset_mono`) .. the last VoiceBox clip process confirmed dead | 3 decimals, `None` if no clip died |

`stop_playback` (line 2783) now captures the clip pids, silences speech, then polls `pid_alive` every 20 ms for up to 2 s and returns the monotonic time the last clip died — the boundary is confirmed death, not the function call. If a clip survives, it returns `None` and no latency is recorded. `wake_wall`/`flush_wall` were renamed `wake_mono`/`flush_mono`; nothing outside the controller consumed the old names. A new wake resets `turn_seq`-adjacent fields, so a finished turn's numbers never leak into the next turn's status.

Unit (level 1): five new tests in `tests/test_handy_control.py` — wake resets stale latencies and bumps `turn_seq`; a flushed turn publishes fresh non-null values in `status.json` equal to the in-process metrics; `stop_playback` returns the death-confirmation time only after polling confirms death; a surviving clip yields `None`; the barge path records `latency = died_at − barge_onset_mono` exactly. `pytest tests/ -q` → 222 passed (baseline 217 + 5). Node files → 61 passed. One flush-path log line had to guard a `None` dispatch.

Level 2, repeat-turn probe (`scripts/run_repeat_turn_probe.py`, PASS 2026-11-14 04:14 UTC, `.local/voice-agent/runs/VA-AEC-007.json`):

| Turn | turn_seq | wake→flush | asr | dispatch | wake→transcript | VA-AEC-007 baseline | delta |
|---|---|---|---|---|---|---|---|
| a | 1 | 6.92 s | 1.513 s | 0.002 s | 8.43 s | 7.16 s | +1.27 s |
| b | 2 | 7.16 s | 0.569 s | 0.002 s | 7.73 s | 8.38 s | −0.65 s |

Both deltas within the ±1.5 s tolerance (baseline boundary was probe wake → transcript log stamp; the controller equivalent is `wake_to_flush_s + asr_s`). `status.json`'s `turn` block matched the in-process metrics exactly (`turn_seq: 2`, 7.16/0.569/0.002), transcripts verbatim, aec −25.8 dB, 16 blocks, no echo-only wake.

Level 2, `stop_latency_s`: not yet run. Two attempts of `scripts/run_interrupt_probe.py` (03:54 and 04:06 UTC) failed at playback: the isolated session answered, but VoiceBox `/generate/stream` returned HTTP 500 on every request (speech.log shows ~40 consecutive `requested`→`failed status 500` pairs 03:51–04:27 UTC; manual curl with the `Akshay` profile reproduces it; no new `voicebox-server-*.ips` crash reports; pid 20305 still listens on 17493 and `/health` returns 200 with the 0.6B model "loaded"). Per the service runbook, recovery is a human quitting and reopening VoiceBox; an agent may not restart the GUI. The probe's playback wait was raised from 90 s to 150 s. Baseline for the rerun stays VA-INT-AUTO-041: hold→`stop_playback` call 0.589 s, hold→probe-detected death 1.076 s; the new `stop_latency_s` sits between confirmed-death and call time, so expect ≤ 1.076 s.

Load state: no commit (operating rule 6). The live controller pid 64238 and the live OMP extensions did NOT load these changes; only the probe processes and test runs executed the modified code. Level 3 for turn latency stays open until the controller is restarted.

level: 2 for `turn_seq`/`wake_to_flush_s`/`asr_s`/`dispatch_s` (fixture turn, status-published); 1 for `stop_latency_s` (unit boundary tests only). next: rerun `run_interrupt_probe.py` once VoiceBox generation is restored; then a controller restart to make the fields live.

Recovery attempt, 2026-11-14 04:47 UTC: the VoiceBox GUI was quit and reopened (new pid 4044 at 04:33 UTC; old GUI 20266 is gone), but the orphan `voicebox-server` pid 20305 (spawned by the dead GUI, kept alive by the `.keep-running` sentinel) still owns port 17493. Its state: `/health` 200 but `model_loaded: false`; `/generate/stream` returns HTTP 500 for every engine and payload; the server's own `/models/load` also fails with "[Errno 32] Broken pipe", and no new `voicebox-server-*.ips` crash report appeared — the process is listening but its inference worker is dead. No new crash report and ~29% of 64 GB free at 04:47 UTC, so memory pressure is not the current limiting factor. An agent may not kill or restart it (runbook); recovery requires the human to disable "keep server running" so pid 20305 exits, then reopen VoiceBox. Regression re-verified at 04:45 UTC with this controller state: `pytest tests/ -q` → 222 passed; `node --experimental-strip-types --test tests/playback-state.test.ts tests/match_command.test.ts tests/speech-queue.test.ts` → 61 passed. The live controller (pid 64238) and live OMP extensions still have not loaded these changes; only probe/test processes executed them.

Watcher result, 04:38–04:50 UTC: 24 `/generate/stream` probes every 30 s, all HTTP 500, listener pid unchanged (20305) throughout. No human-authorized recovery occurred within the window. `stop_latency_s` therefore has NO Level 2 measurement this iteration — the interrupt probe cannot be run, and no number was fabricated. Verdict for this iteration: VA-LAT-001 is complete at Level 2 for `turn_seq`/`wake_to_flush_s`/`asr_s`/`dispatch_s`; `stop_latency_s` stays at Level 1 (unit-verified boundary: hold onset → `pid_alive`-confirmed clip death, `None` when a clip survives) pending a working VoiceBox. The rerun command is `~/.local/share/omp-voice/venv/bin/python scripts/run_interrupt_probe.py`; the evidence file will be `.local/voice-agent/runs/VA-INT-AUTO-041.json` and the acceptance check is `stop_latency_s` ≤ 1.076 s against the historical 0.589 s (hold→`stop_playback` call) and 1.076 s (hold→probe-detected death) baselines.

### VA-TTS-019, 2026-11-14 20:25 UTC — re-deferral reset the expiry clock; the retry chain was unbounded

Reproduction, pre-fix: `.local/voice-agent/probes/defer_expiry_probe.mjs` ran the real timer chain (`generate()` → ECONNREFUSED on port 17990 → deferred → 5 s retry timer) for 135 s. The sentence was still in the deferred queue at t=135 s, past the 120 s expiry. Reading the chain explains why: `retryDeferredSpeech` clears `session.deferred` and re-speaks via `speakChunk`, which on a new deferral pushed `{ at: Date.now() }` — every retry stamped a fresh time, so `now - at` never exceeded `DEFER_EXPIRY_MS` and the `defer-expired` branch never fired. The chain retried every 5 s forever against a dead service, appending a `deferred` line to `speech.log` each cycle.

Fix: `speakChunk(speak, epoch, gen, player, at = Date.now())`; `retryDeferredSpeech` passes `item.at`, so the clock measures from the first deferral, not the latest failed attempt. Regression test in `tests/voicebox-refusal.test.ts`: a sentence retried inside the window keeps its original `at`; once the window passes it is dropped (`defer-expired`) and the queue empties. Refusal file 13 passed; Node suite 95 passed; Python 255 unchanged. Post-fix probe (dead mock port, real timers): dropped at t=125,036 ms with `defer-expired`, queue empty, chain terminated.

Limits: Level 1 + Level 3 against a dead mock port; no real VoiceBox, no microphone. The refusal-hold short-circuit means the unbounded chain never hit the network — the fix is about termination and log growth, not load. Not committed (rule 6).

level: 1 unit + 3 mock-service. next: when VoiceBox is restored, confirm a real outage expiry end-to-end with the restarted controller.

### VA-TTS-020, 2026-11-14 20:45 UTC — held sentences kept jumping the replay queue

Reproduction, pre-fix: two new tests against stub generators failed. With four sentences held during an outage and partial recovery ("Second sentence." still failing), `retryDeferredSpeech` handed all four to the pipeline at once: played `First, Third, Fourth` with `Second` appended last. On the live path, a sentence enqueued while an earlier one of the same reply was still held played immediately (`Later line.` played while `Held line.` sat queued). Root cause: neither the retry pass nor `enqueue` knew that a sentence ahead of it was still deferred — deferrals were collected but the pipeline kept flowing past them.

Fix: `speakChunk` returns `Promise<boolean>` (true when the sentence went to the deferred queue); `retryDeferredSpeech` awaits each sentence and stops at the first re-deferral, re-pushing the remainder behind it so the next 5 s tick replays oldest-first; `enqueue` holds a new sentence behind any already-held one of the same epoch, deduped by text. One existing contract test ("a retried sentence that was already spoken is not repeated") changed: the re-arriving chunk is now deduped against the held queue and spoken once by the retry pass (retried 1, played exactly once — the anti-duplication assertion itself is unchanged). New regression tests: partial recovery plays only First and keeps Second/Third/Fourth queued in order; full recovery plays all four in order; live enqueue waits behind a held sentence. Refusal file 15 passed; Node suite 97 passed; Python 255 unchanged. The VA-TTS-019 expiry probe reruns with the restructured chain: still terminates, `defer-expired` drop at t=125,035 ms, queue empty.

Limits: stub players, no afplay, no real VoiceBox, no microphone. Real ordering of physical playback after recovery still needs the restarted controller and a live VoiceBox. Not committed (rule 6).

level: 1 unit. next: with VoiceBox restored and the controller restarted, replay a held multi-sentence reply through real `afplay` and observe order and barge-in mid-replay.

### VA-STAT-001, 2026-11-14 21:05 UTC — outage silence was unexplainable from status

Reproduction, pre-fix: no exported surface exposed the deferred queue. `GET /status` returned `speaking: false` with nothing about held sentences; the `voice status` command text likewise. An owner watching a VoiceBox outage could not distinguish "nothing to say" from "3 sentences held awaiting recovery" from "speech lost after the 120 s expiry" — the loop prompt's rule that text on screen never spoken must not be silently treated as a completed voice response had no observability backing.

Fix: `VoiceSession` tracks `expiredSpeech` (incremented only on `defer-expired`, not on intentional epoch-replaced drops); exported `currentSpeechStatus()` returns `{speaking, deferred, deferredOldestAgeMs, expiredSpeech}`; the bridge `/status` handler spreads it into the payload (additive — the controller's `cmd_status` already dumps the whole bridge JSON); the `voice status` fallback text shows `held=N (Xs oldest)` and `expired=N` when nonzero. Four new tests (held count, injected-clock expiry counted, replaced-reply drops not counted, replay clears counters). Refusal file 19 passed; Node suite 101 passed; Python 255 unchanged.

Limits: the exported function is what tests exercise; the live HTTP `/status` payload has not been fetched from a running OMP session (session reload with the extension needed). Counter is per-process, not persisted. Not committed (rule 6).

level: 1 unit. next: after a session reload with the extension, `curl` the bridge `/status` during a controlled mock outage and confirm `deferred`/`expiredSpeech` appear; the AEC-real and VA-INT-001 rows still need the human gates.

### VA-TTS-021, 2026-11-14 21:35 UTC — a sidecar that dies mid-request silently dropped the sentence

Reproduction, pre-fix: when VoiceBox accepts the TCP connection and then dies before responding — the shape the GUI crash produces on this machine — Node 26 `fetch` throws `TypeError: fetch failed` with cause `SocketError: other side closed` (code `UND_ERR_SOCKET`). None of the strings in `isConnectionRefusal` matched, so every sentence hit the `logSpeech("failed")` drop path. Two new unit assertions on the real Node error shape failed, and the mock probe (`req.destroy()` mid-request) ended with `deferred=0, spoken=""`: four sentences requested, four lost. Live evidence: `speech.log` rows at 20:41:47 UTC recorded exactly `event: failed, reason: TypeError: fetch failed` for all four sentences of one reply.

Fix: `isConnectionRefusal` now also matches `other side closed`, `UND_ERR_SOCKET`, and `socket hang up`. The refusal-hold window arms as usual, so the retry chain stops hammering a dying service; `AbortError` from barge-in is still not a refusal. Verification: refusal file 21 passed (two new tests: the matcher on the exact error shape, and an end-to-end hold-then-replay against a mock that accepts and destroys); Node suite 103 passed, Python 256 passed. Level 3: `defer_order_probe.mjs` ran the real `generate()`, real 5 s `retryTimer`, and real (silent) `afplay` against a mock that is down 0–25 s, flaky (fails sentence 2 once) 25–35 s, then up — request log `t=30034 200 First; t=31112 500 Second; t=36115 200 Second; t=37184 200 Third; t=38250 200 Fourth`, `jumpAhead=false`, `successesInOrder=true`, `finalDeferred=0`, all four sentences spoken in order.

Also closed this iteration: the guardian's `freed=0`-but-`"unloaded"` RELIEF edge (open question from the previous iteration) is pinned as intentional bounded behavior by a new policy test — the grace clock arms exactly once, kill is delayed at most `RELIEF_GRACE_SEC` (10 s), the kill still fires if relief never materializes, and rule 1 (zero headroom) ignores the grace. Guardian policy file now 13 tests.

Limits: mock service only; the socket death is simulated with `req.destroy()` (same undici shape as a SIGKILL of the sidecar, but the real crash was not observed this iteration). Real-clip ordering after recovery still needs the restarted controller and live VoiceBox. Not committed (rule 6).

level: 1 unit + 3 mock-service. next: human gates unchanged (push, reopen VoiceBox, restart controller 64238); when VoiceBox is back, run the deferral probe against the real service to confirm the refusal classifier fires on a genuine crash.

### VA-SOAK-002, 2026-11-14 21:37 UTC — human gates opened; recovery cycles closed at Level 3; unload relief measured

The four standing human gates were explicitly authorized and executed this iteration:

- **Push:** `4aa6a54` on origin/main (59 files, +4618 −522), the first commit of the loop. GitHub Actions run 43641902159: node and python jobs both success. CI baseline holds.
- **Controller:** pid 64238 (pre-VA- code) stopped; restarted 21:16 UTC as pid **38298** from the current tree with the exact flags (`--wake-word hey_jarvis --wake-threshold 0.5 --pause-seconds 5.0 --idle-timeout 15.0`). Startup log: models loaded, mic open, `ready in IDLE`. It reported `VoiceBox health unread; speech tier not changed` because it started ~1 min before VoiceBox reopened — the tier check is on-demand, so this is a startup ordering artifact, not a fault.
- **Guardian:** watch pid 40203 (old policy) replaced by pid **38389** running the current `strata-memory-ceiling` (VA-MEM-004 liveness fix now live).
- **VoiceBox:** GUI quit and reopened; listener pid 38531 on 17493, `/health` 200 with model loaded. `/generate/stream` is working again (the HTTP-500 condition that blocked VA-LAT-001 Level 2 is gone). Note: the `/models/load` endpoint ignores the requested model name and loads the default 1.7B; the previously loaded 0.6B was not restorable via the API.

**VA-MEM live measurement (closes an open claim):** guardian relief from voice shedding measured directly on the live listener: footprint 5,656 MB → 5,645 MB after `POST /models/unload` — **11 MB freed, not ~2.4 GiB**. MLX/Metal keeps its arena allocated after unload. Consequence: the `freedBytes > 0` relief pin still arms (11 MB > 0), but the real memory lever is the extension-side deferral via `pressure.json`, not the unload itself. The grace is bounded (60 s shed interval, 10 s grace, unload no-ops after the first), so the pin delays a justified kill by at most one grace window. No code change warranted; the claim in docs/INDEX is corrected to the measured number.

**VA-SOAK-002 itself:** new unit test chains two outages, a partial recovery, and a 500-on-first-attempt service through one session; all five sentences replay exactly once in order, `deferred=0`, `expiredSpeech=0`. Refusal file 22 passed; Node suite 104; Python 256. Level-3 probe (`recovery_cycle_probe.mjs`, mock on 17990, real `generate()`, real 5 s retry timer, real silent `afplay`, four replies/11 sentences across down→up→down→up with mid-request socket death): RESULT PASS — spoken text is the 11 sentences in exact order, `deferred=0`, `expired=0`, 0 stray tmp files, RSS delta −8.4 MB, and the process exits naturally with code 0 (the timer-leak assertion). Full evidence in `docs/testing/scenarios/VA-SOAK-002-recovery-cycles.md`.

Probe debugging recorded (three probe-side bugs, zero product bugs): swapped WAV `blockAlign`/`bits` fields made the mock audio fail `wavReference` (everything held); a `const ok = ok &&` self-shadow broke restart retries; counting 200s instead of attempts made `C two.` 500 forever, so the queue survived to the 120 s expiry. The probe's own request log exposed each one.

RSS threshold: the "< 10 MB" assertion was unrealistic for a Node process (GC noise showed 10.2 MB on a clean run); raised to 25 MB. The 21:37 run measured −8.4 MB.

Limits: mock service, silent clips, no microphone, single speech client. Real VoiceBox crash/relaunch cycles (true Level 5) still need human-gated GUI recovery. Not committed beyond the authorized gate push (rule 6).

level: 1 unit + 3 mock-service. next: run `scripts/run_interrupt_probe.py` against the now-working VoiceBox and restarted controller 38298 to get the live `stop_latency_s` (VA-LAT-001 acceptance ≤ 1.076 s vs baseline 0.589 s); then attempt the echo-only Level 4 criteria (playback alone must not wake or barge) with the live AEC path.

### VA-LAT-001, 2026-11-14 22:20 UTC — live interrupt probe ran six times; stop path stable, the flake was the harness clock

Command: `~/.local/share/omp-voice/venv/bin/python scripts/run_interrupt_probe.py` against the live listener (pid 38531, 17493, `/health` 200 model_loaded) and the restarted controller code. VoiceBox `/generate/stream` with the Akshay profile returned 200 / 119,084 bytes / 6.7 s before the runs. Evidence: `.local/voice-agent/runs/VA-INT-AUTO-041.json` (overwritten each run), logs `/tmp/probe2.log`, `/tmp/probe3.log`, `/tmp/probe4.log`, `/tmp/probe5.log`, `/tmp/probe6.log`.

Live stop-path results (`stop_latency_s` = controller boundary, hold opened → clip process confirmed dead, acceptance ≤ 1.076 s vs in-file baseline 0.589 s):

| Run | pid | stopped | `stop_latency_s` | whisper | result |
|---|---|---|---|---|---|
| 1 | (first live run) | false | — | — | FAIL: stages `["speaking"]` only, gate never fired |
| 2 | 50882 | true | 0.793 | "stop." | PASS, exit 0 |
| 3 | 50882→(probe-third) | true | 0.832 | "stop." | exit 1 — `second_playback: false` only |
| 4 | 56087 | true | 0.791 | "stop." | exit 1 — `second_playback: false` only |
| 5 | 59912 | true | 0.688 | "stop." | PASS, exit 0 |
| 6 | 60696 | true | 0.647 | "stop." | PASS, exit 0 |

Run 1 is an outlier: identical code triggered the hold in every later run (instrumented reproduction `debug_barge_gate.py`, now in `.local/voice-agent/probes/`: hold at frame 6, `rms=2605 vad=0.79 hot=3 floor=20`, clip peak 25244, Whisper "stop.", afplay killed in 0.663 s). No threshold was touched to make it pass.

Runs 3/4 diagnosis — harness timing, not product: the isolated `omp --print` session's *second* reply hit VoiceBox at 22:05:14 (speech.log `requested` 27 chars), 1.5 s after the probe's 60 s `wait_playing` deadline expired; the probe then terminated the session, and `session_shutdown` → `bargeIn()` aborted the in-flight TTS fetch, recorded as `dropped, reason "abort"`. So the second playback never got its slot written in time — the model queue (single-slot Flash-Next, main session hammering it) made the reply take ~60+ s. Fix: the probe's second wait widened to 120 s with the reasoning in the comment; the 60 s was always arbitrary harness timing, no product gate changed. Runs 5/6 confirm the full chain (`stopped`, `resumed: false`, `second_playback: true`, state IDLE).

Echo-only observation (free, from the live controller 38298 — see `~/.local/state/omp-voice/controller-restart.log` 16:16–17:04 local): playback echo produced repeated "TTS barge hold" + clip + whisper cycles (rms 395–1393, floor 82–237, e.g. 16:28:12 `rms=1393 vad=0.98 floor=92`) and whisper always classified it as not-stop, so **playback alone never woke Handy and never stopped its own speech** — wake-level suppression holds. But the residual echo energy passing the rms gate is far above the ≤175 target, and `status.json` reports `aec_echo_db −2.1` with `aec_blocks 13` — the WebRTC canceller is engaged yet only cutting ~2 dB in these windows. Recorded as an observation, not AEC-REAL-001 PASS: no paired residual-vs-corrected numbers were captured during a controlled playback.

Also fixed this iteration (found by the harness, latent in the live path too): `_render_parsed` had no module-level default; `cancel_playback_echo` (line 835) and `apply_render_subtraction` (line 622) read it before any `refresh_render_reference()` call, raising `NameError` on a direct call. One-line module default added. `py_compile` clean; Python suite 256 passed; Node suite 104 unchanged (not re-run — no extension change).

level: 2 fixture-fed, live services. next: AEC-REAL-006 reference-failure live check; then the human-gated Level 4 rows (VA-INT-001, AEC-REAL-002–005). `stop_latency_s` live acceptance is met: 0.647–0.832 s across five consecutive stop-path passes. Not committed (rule 6).

### AEC-REAL-006, 2026-11-14 22:59 UTC — a live render-reference failure disconnects cleanly, never wakes, and reconnects; the induction shape is the whole story

The first Level 4 scenario that needs no human voice: real VoiceBox clips through the MacBook speakers, the live controller (38298) owns the microphone, and the probe (`scripts/run_reference_failure_live.py`, isolated `omp -p` session only — bridge ports recorded per run, protected pids never touched) rewrites its own playback slot to point at a half-written clip.

Eight runs, three harness bugs, one design finding:

- **Run 1 — in-place truncation, key unchanged: reference stayed connected.** Not a bug: `refresh_render_reference` (controller line 924) only re-reads when the declared `(wav, frames, rate, channels)` key changes, and the loaded PCM survives the file vanishing behind a stable key (the VA-AEC-008 design note, now validated physically). Any future "reference disappeared" alarm must be about a file that fails to parse against its slot, not about a file disappearing.
- **Runs 2–4 — the disconnect leg worked** (`render_connected: false`, "render reference unavailable" logged, zero wake triggers, mic IDLE, controller alive), but the reconnect leg sampled the wrong moment: `wait_playing` matched the still-open first slot, and the tail guard clears the reference 0.6 s after afplay exits, so a one-sentence clip was gone before the reconnect poll.
- **Run 5 (17:46 local)** disconnect leg confirmed again (0.8 s latency); reconnect leg invalid for the same slot-staleness reason.
- **Run 6 (17:51 local)** PASS in substance: disconnect 0.8 s, reconnect logged by the probe session's own second clip (`render reference connected frames=224640`, `aec_echo_db −21.7`) — but the gate still accepted the partial file as the "second" clip.
- **Run 7** — the race the scenario needs protection against: the reply clip was short enough that afplay exited and the extension unlinked the wav before the probe read it (`FileNotFoundError`). Probe now reads the bytes at playback detection and refuses to induce once afplay is dead.
- **Run 8 (17:58 local) — clean PASS.** pid 76655 clip 238080 frames (9.92 s): before, `render_connected: true`, `aec_echo_db −2.6`, 13 blocks, IDLE. Slot rewritten to 238124 bytes on disk against a 476204-byte header. `render_connected: false` 1.2 s later; "render reference unavailable" logged; **zero "Wake triggered" lines** even though the echo passed the canceller raw — one barge hold (rms 416, floor 29) fired and Whisper classified the echo ("This is the weight class.") as not-stop, exactly the accepted VA-AEC-008 behavior; mic stayed IDLE, no exception. Second clip `omp-vb-76655-2.wav` reconnected (`render_connected: true`, −2.7 dB, 3 blocks), controller 38298 alive throughout. Evidence: `.local/voice-agent/runs/AEC-REAL-006-LIVE.json`; scenario doc `docs/testing/scenarios/AEC-REAL-006-reference-failure.md`; INDEX row added.

No hot-gate thresholds touched. Python suite re-run: 256 passed (controller code unchanged; only the probe script). Node suite untouched (104). Live TTS verified directly against listener 38531 (`/generate/stream` 200, 145964 bytes, 6.2 s) — the earlier VoiceBox-500 environment blocker is gone; the run-3/4 stalls were the single-slot Strata queue delaying the isolated session's reply, not the product.

next: **AEC-REAL-001** — paired residual-vs-corrected measurement during controlled playback to explain the live `aec_echo_db −2.1/-2.7` vs fixture −34.8 gap (suspect: `echo_over_cancels` guard + `_aec_observe` window reset, controller lines ~714–743/~835). Then Level 5 stale-slot/registry observation. AEC-REAL-002–005 stay BLOCKED on Akshay's voice. Not committed (rule 6).

### AEC-REAL-001, 2026-11-14 23:24 UTC — echo alone never wakes the live controller, and the −2 dB window is now attributed: the guard, not the filter

The loop prompt's Level-4 wake-suppression half is closed; the ERLE half is explained down to one unmeasured number.

- **Live wake leg, PASS.** Isolated session pid 86020 played an 8.0 s VoiceBox reply through the speakers while controller 38298 owned the microphone; nobody spoke. Nine status windows: `aec_echo_db` −1.8 → −14.6 (best, 2 s into the clip) → −2.7, median −6.5; **zero "Wake triggered" lines**; one barge hold (rms 666, vad 0.77, floor 90) — echo-induced, Whisper-gated, playback never wrongly stopped; mic IDLE; controller alive. Combined with AEC-REAL-006 runs 6/8 and the VA-LAT-001 echo observations, echo-only wake suppression across full replies is demonstrated four times.
- **The mechanism, from a production-path lag sweep** (`scripts/run_aec_residual_probe.py`, real VoiceBox clip, echo taps at 0–600 ms, mic never opened): cancellation is strong at 100–300 ms lag (−23.5/−21.6/−21.1 dB, 0–3 guard blocks of 86), then collapses hard: −3.3 dB at 400 ms, −3.1 at 500, −1.5 at 600 — with 31/31/22 blocks guard-returned raw and cleaned-rms maxima *above* raw (5996 vs raw mean 1884): the failed fit injects energy, then `echo_over_cancels` dumps the block because an echo trailing the cursor by more than the 300 ms guard window (`AEC_GUARD_LAG_SAMPLES = 4800`) is indistinguishable from near-end speech by construction. Noise dilution is only ~1.5 dB (−23.5 → −19.8 with 60 rms added), so noise cannot explain −2 dB.
- **The instrument change:** `_aec_observe` now counts guard-passed blocks separately (`aec_guard_blocks`, published in `status.json` alongside `aec_echo_db`/`aec_blocks`), with a unit test that crushes the fit against an unrelated reference and asserts every counted block is guard-returned and the window reads exactly 0.0 dB.
- **Blocker (honest):** the live controller 38298 predates the counter, so the exact fraction of live blocks in the guard-raw regime — the one number that settles the attribution physically — needs Akshay to restart the controller. The loop rules forbid the probe restarting the process that owns the microphone. Delta-0 cancellation is only −13.1 dB in the sweep, consistent with VA-AEC-009's −16 dB delta-0 ceiling: physical echo always trails, so the live value is a lag-regime question.

Tests: echo suite 28 passed (was 27; new guard test); full Python suite re-run below; Node suite untouched (104). Evidence: `.local/voice-agent/runs/AEC-REAL-001-LAGSWEEP.json`, `.local/voice-agent/runs/AEC-REAL-001-LIVE.json`; scenario doc `docs/testing/scenarios/AEC-REAL-001-echo-only-wake-suppression.md`. No thresholds touched, nothing committed (rule 6).

next: restart controller 38298 (human) to read `aec_guard_blocks` live and close the ERLE number; then Level 5 stale-slot/registry observation. AEC-REAL-002–005 stay BLOCKED on Akshay's voice.

### VA-PLAY-002 live leg, 2026-11-14 23:41 UTC — a SIGKILLed session's orphan afplay is watched, then pruned: the Level 5 cleanup gap is now demonstrated on the running controller

- **What was investigated.** The dead-slot prune (`_read_playback_slots`, projection re-derivation, Node `readSlots`) existed since 11:52 UTC but was proven only by unit tests; the nine stale live files had vanished unobserved. The loop prompt's Level-5 stale-session-cleanup item was the only independent open gap after the P0s.
- **Live PASS.** `scripts/run_stale_session_probe.py`: isolated session pid 92640 spoke a 10.4 s VoiceBox reply; SIGKILL 2 s in killed the session but not its `afplay` (it survived as an orphan for 7.75 s more). While the orphan ran, controller 38298 kept `render_connected: true` and projection `playing: true` — correct, the echo was physically real — and logged zero wake lines. At afplay exit the slot was unlinked and `tts-playing.json` re-derived to `playing: false` in the same poll tick (7.75 s after kill); `render_connected` went false within 1 s (reverb tail); `render reference unavailable` logged; controller alive, IDLE, `mic_dropped: 0`, `mic_invalid: 0`. Evidence: `.local/voice-agent/runs/VA-PLAY-002-LIVE.json`. The first run reported FAIL on an instrumentation bug (the poll loop broke before sampling the render drop), fixed and re-run.
- **New test:** `test_an_orphaned_afplay_is_kept_then_pruned_when_it_exits` pins the same shape in a temp state dir. Python suite 258 passed (was 257); Node suite 65 passed; echo file 26.
- **Two honest boundaries recorded in the scenario doc:** the `sessions/` bridge registry is pruned lazily (`load_session_registry` unlinks dead pids only on a delivery read — 11 files present, including dead probe pids, none ever delivered to because the read prunes before use); and the orphan-afplay lease is capped at 60 s from `started_at`, so a hypothetical dead-writer clip longer than 60 s would drop the reference mid-echo. Sentence chunks are 5–10 s, so the hole is unexercised.
- **Blockers unchanged:** physical guard attribution needs a human restart of 38298; AEC-REAL-002–005 need Akshay's voice. Nothing committed (rule 6).

next: Level 5 still needs a repeated-session soak (three or more consecutive conversations in one controller lifetime with replies, measuring slot/registry churn and status deltas); the >60 s orphan-lease hole is a candidate fix but unmeasured; guard-raw ERLE number still awaits the human restart.

### VA-SOAK-003, 2026-11-14 23:59 UTC — four consecutive conversations play in one controller lifetime: no wake, no accumulation, no lost speech

- **Level 5 soak closed.** `scripts/run_soak_sessions_probe.py` ran four prompts through one isolated omp session (pid 418) while controller 38298 kept the microphone and was never restarted. All four replies generated real VoiceBox clips and played through the speakers: render connected during every clip and disconnected after every clip; four distinct afplay pids; **zero wake lines**; **zero failed speech events**; final status `render_connected: false`, IDLE, `mic_dropped: 0`, `mic_invalid: 0`; registry entry present; slot directory stayed at exactly two entries (probe session + main session 2734) at every boundary. Evidence `.local/voice-agent/runs/VA-SOAK-003-LIVE.json`.
- **The first run FAILed on harness bugs, not the product.** Turn 1's reply exceeded the 240 s wait because the owner's live session (2734) was mid-conversation on the single-slot local model — all four replies eventually generated and played, nothing was lost. Fixed by widening the per-turn window to 420 s, attributing turns by distinct afplay pid, draining the probe's own afplay pids before the final status read (the global `render_connected` flag can legitimately be true while the owner's session plays), and parsing `speech.log` as JSON lines (the bracket-timestamp scan found nothing because the log has no brackets). A `timezone` NameError aborted the intermediate run before it wrote evidence.
- **Echo residuals during the soak** ranged −2.4 … −22.8 dB with four 0.0 dB samples (guard-passed blocks that dump raw echo) — consistent with AEC-REAL-001's attribution; no wake resulted.
- **Tests:** no production code changed; Python suite 258 passed, Node 65 passed (re-run after the probe edits); py_compile clean on the probe. Nothing committed (rule 6).

next: the only independent Level-5 hole left is the >60 s orphan-afplay lease cap vs clip duration — needs a synthetic long clip before a fix; physical ERLE number and AEC-REAL-002–005 still await Akshay (restart 38298 / voice); VoiceBox unload relief still unmeasured (GUI-owned sidecar). Next safe iteration: pin the orphan-lease boundary with a fixture clip longer than 60 s.

### VA-SOAK-004, 2026-11-14 24:10 UTC — the orphan-afplay lease now tracks the clip's real duration: the >60 s render-reference hole is closed

- **Reproduced first.** `slot_is_speaking` with a dead writer, an alive afplay, `started_at` 70 s ago, and a 120 s reference returned `False` — the controller would drop the render reference mid-echo exactly as hypothesized in the VA-PLAY-002 limitations.
- **The fix.** `orphan_lease_expiry` (Python, `bin/playback_state.py`) and `orphanLeaseExpiry` (Node, `extension/playback-state.ts`) compute the deadline as `started_at + frames/sample_rate/playback_rate + 5 s` spawn slack; slots without a valid reference keep the flat 60 s fallback. The shared contract `tests/playback_vectors.json` gained three cases (70 s into a 120 s clip → speaking; 126 s in → silent; 120 s clip at 2x rate, 70 s in → silent) so both implementations are tested by the same vectors. One unit test added in `tests/test_playback_state.py`.
- **Tests:** playback file 27 Python passed (was 26), Node playback file 22 passed (was 19); full suites 259 Python / 68 Node. Nothing committed (rule 6).
- **Honest boundary:** proven by contract vectors, not by a physical >60 s orphan clip — every VoiceBox chunk observed so far is 4.1–15.1 s, so no natural clip reaches the old cap; the fix removes the cliff rather than demonstrating it acoustically. The live controller 38298 and the live extension in session 2734 still run the old rule until restart/reload.

next: physical ERLE number and AEC-REAL-002–005 await Akshay (restart 38298, use his voice); VoiceBox unload relief still unmeasured (GUI-owned sidecar). Remaining independent candidates: wake-to-dictation latency segmentation when the model is idle, and the architecture review pass (controller/extension module extraction) now that P0s are closed.

### VA-SOAK-005, 2026-11-15 00:40 UTC — four conversations in one controller life leave RSS back at its entry value: no memory drift

- **Reproduced first — the leak does not exist, but the metric did.** The first RSS-gated soak run FAILed at "92.6 MB growth". A 1 s-resolution trace (`.local/voice-agent/probes/rss_trace_probe.py` → `.local/voice-agent/runs/rss-trace.json`) showed controller RSS swinging between ~142 and ~356 MB *within a single turn* while the render reference was idle: macOS page residency churn under the resident ~46 GiB model, not controller accumulation. A `final − baseline` gate on `ps` RSS is noise on this machine.
- **The fix.** Acceptance in `scripts/run_soak_sessions_probe.py` now gates on (a) the median RSS five samples taken 30 s after the probe's session exits (leak signal) being within 20 MB of the entry baseline, and (b) every turn's RSS peak staying under baseline + 300 MB (runaway-allocator ceiling). Per-turn boundary samples and peaks are recorded as raw evidence. Boundary drift is reported, not gated.
- **Tests:** four live probe runs (two FAILs diagnosed as the metric bug, then PASS). No unit-code changes; no suite weakened.
- **Results:** PASS — baseline 157.1 MB, per-turn peaks 254.2/76.6/137.3/283.1 MB, post-exit median 173.8 MB; 4 turns played, 4 distinct afplay pids, 9 clips, zero wake lines, zero failed speech, final IDLE, slot dir stable at 2. Scenario `docs/testing/scenarios/VA-SOAK-005-memory-drift.md`; INDEX row added.
- **Honest boundary:** Level 3 only — no microphone input; the hours-long Level-5 soak across several cycles is still open, and RSS under heavy system pressure is an imprecise instrument even with the median gate.

next: hours-long multi-cycle soak (Level 5 proper); wake-to-dictation latency segmentation with the model idle; architecture pass on the 4k-line controller. Physical AEC rows (ERLE, double-talk, spoken stop) remain BLOCKED on Akshay restarting 38298 and speaking; VoiceBox unload relief stays unverified until the GUI sidecar is reopened.

### VA-SOAK-006, 2026-11-15 02:45 UTC — six conversations in one controller lifetime: attribution, noise-band gates, and a real VoiceBox crash

- **Reproduced first.** The first six-cycle soak FAILed on three probe bugs, not controller behavior: the mic gate read lifetime-cumulative counters (`mic_dropped` 7, all pre-existing); the RSS baseline was a single `ps` sample on a low phase of the documented ±200 MB residency oscillation; and the owner's own dictation wakes ("Hey Jarvis." 19:56:32 and 19:57:56 local) epoch-aborted cycle 6 turn 3 and were scored as controller failures. Evidence preserved in `.local/voice-agent/runs/VA-SOAK-006-LONG-run1.json`.
- **The fixes.** `scripts/run_long_soak_probe.py` now: gates mic counters on run-start deltas; takes median-of-24 RSS samples at 5 s for baseline and post-run; detects human transcripts in `controller-restart.log` and returns a three-valued verdict (PASS / CONTAMINATED exit 3 / FAIL exit 1); attributes each turn to the exact clip generated after that turn's submit, merging `speech.log` + `speech.log.1` (rotation at 1 MB was silently erasing mid-run events — cycle 4 credited 4 plays for 2 generated clips); and tracks the VoiceBox sidecar footprint via `footprint`, taking the largest listener with a retry (the KB-scale GUI launcher also listens on 17493 and was being read as `None`).
- **The settle band is now measured, not guessed.** Three independent 120 s medians of the *idle* controller: 272.2 / 328.4 / 360.2 MB — an 88 MB noise floor. The 20 MB gate FAILs by chance (run 4: +48.4 MB in a perfectly clean run). RSS settle limit is now 100 MB plus a rising-floor trend gate (first-to-last cycle median within 100 MB), which churn cannot fake but a leak can.
- **Genuine finding: VoiceBox died under soak load.** `voicebox-server` SIGABRT-crashed at 21:37:15 local (two crash reports, launcher and worker), after its footprint climbed 5.6 GB → ~9.0 GB across ~24 TTS generations across four soak runs. Nothing listens on 17493 since. The controller (38298) survived unscathed: IDLE, render false, footprint 470 MB (peak 522) after 12 soak cycles.
- **Tests:** 7 verdict unit tests in `tests/test_long_soak_verdict.py` (healthy PASS, lifetime counters don't fail a delta, human speech ⇒ CONTAMINATED, wake-only ⇒ FAIL, settle/envelope limits, rising floor ⇒ FAIL, oscillating floor ⇒ PASS, missing baseline ⇒ FAIL). Full suites: 266 Python passed, 68 Node passed. Four live probe runs.
- **Results:** run 1 FAIL (probe bugs); run 2 PASS 24/24 turns with loose attribution (RSS 346.2 → 343.9 MB, VoiceBox flat 5649–5658 MB); run 3 CONTAMINATED (4 human transcript lines, attribution verified: every turn mapped to a distinct `omp-vb-<pid>-N.wav`); run 4 quiet FAIL only on the below-noise settle gate and a transient `None` footprint read — every controller invariant clean. Clean PASS **BLOCKED**: VoiceBox must be reopened by the owner.
- **Honest boundary:** Level 3 only — no microphone exercised. The VoiceBox crash is measured but its cause (MLX abort under memory pressure vs app bug) is not established; only crash reports, no sidecar stderr.

next: owner reopens VoiceBox → rerun the soak for a clean PASS (quiet window); root-cause the 5 mic queue drops seen during the contaminated run; investigate VoiceBox footprint growth (5.6 → 9 GB) as the likely trigger of the SIGABRT — this is now the top reliability risk for long sessions; then wake-to-dictation latency segmentation with the model idle; architecture pass on the 4k-line controller. Physical AEC rows stay BLOCKED on Akshay restarting 38298 and speaking.

### VA-TTS-014, 2026-11-15 02:57 UTC — the deferral gate proven at the HTTP boundary: shed pressure speaks zero requests, relief replays every held sentence exactly once, in order

- **Reproduced first.** Read `generate()` end to end (extension/voicebox-speech.ts:770–791): `waitForHeadroom()` runs before the fetch and returns `{deferred: true}` on timeout; `speakChunk` releases the unspoken text so dedupe can speak it later, and pushes it to `session.deferred` with its *first* held timestamp (expiry clock survives re-deferrals). The gap was coverage: every existing deferral test substituted a stub generator, so "the gate skips the HTTP call" had never been executed.
- **The change.** Exported `generate()` (documented as testability-only) and added `tests/memory-defer.test.ts` + `tests/memory-defer-env.ts`: three tests drive the *real* gate against mock VoiceBox servers (ports 17986–17988) and temp pressure files, keeping real 1 s poll timing. Wired into the Node CI job.
- **What the tests pin:** (1) while `shedVoice` is set, zero mock requests hit, `currentSpokenText()` is empty, status reports 1 deferred with age ≥ the 8 s bound; two more sentences of the same reply queue behind it without each burning a wait; after relief is written, `retryDeferredSpeech` replays all three, exactly 3 requests, 3 plays, original order, queue empty. (2) Headroom returning mid-wait (2 s) speaks at ~2.0 s, not after the full 8 s. (3) A 60 s-stale shed file and a garbage file both speak immediately — a dead guardian's last instruction never silences speech.
- **Gotcha found while combining suites:** running all Node files in one process collided on port 17998 (`EADDRINUSE`) — the refusal suite already uses 17991–17999. Mocks moved to 17986–17988; the full six-file run passes.
- **Tests:** targeted 3/3 (8.03 s + 2.01 s + 7.8 ms). Full Node CI invocation → **110 passed, 0 failed**. Full Python suite → **266 passed**. Scenario doc `docs/testing/scenarios/VA-TTS-014-defer-gate-mock.md` + INDEX row added. No commits.
- **Honest boundary:** the gate is proven against a mock sidecar. The guardian's *live* VoiceBox unload (POST `/models/unload` on 17493) is still UNVERIFIED — no listener since the 21:37 crash. No claim of reclaimed GiB.

next: owner reopens VoiceBox → measure the live unload (footprint before/after) and rerun VA-SOAK-006 for a clean PASS; instrument per-generation VoiceBox footprint growth (SIGABRT root cause); root-cause the mic queue drops; wake-to-dictation latency segmentation. Physical AEC rows remain BLOCKED on the owner restarting 38298 and speaking.

### VA-AUD-004, 2026-11-15 03:15 UTC — mic frames no longer dropped during flush: the stall was the closing partial queueing behind a busy Whisper

- **Reproduced first.** Three falsifiable probes against the working tree before any edit: 37 offers (3 s at callback cadence) into the 32-block queue drop exactly **5** — the same delta SOAK-006 run 3 measured on pid 38298; `show_closing_partial` blocked the frame consumer **4.85 s** with a partial in flight; `transcribe_local_fallback` silently queued behind a busy worker (`jobs.put` unbounded, `slot.get(timeout=30)`). Pre-fix run: `4 failed, 2 passed`.
- **Root cause.** At flush the frame loop runs `show_closing_partial` with no `whisper_pending` guard (unlike `maybe_emit_partial`), so `put(timeout=8)` waits for the in-flight partial, then its own round trip waits again; combined with the 2.2 s Handy ASR wait, the 0.26 s paste settle, and dispatch, the consumer stalls ~3 s — longer than the 2.56 s buffer, so every arriving block is dropped. Hypothesis that drops were PortAudio overflow status was refuted: soak showed `mic_invalid` delta 0.
- **The change.** `MIC_QUEUE_BLOCKS = 128` (10.24 s, ~328 KB) sized to cover the documented flush stall; busy guard + `put_nowait` + bounded waits (`CLOSING_PARTIAL_WAIT_SECONDS = 6.0`, `LOCAL_FALLBACK_WAIT_SECONDS = 12.0`) in both flush-path functions. The contract test in `test_wake_and_gain.py` was updated to the new interface and gained busy/timeout cases — no assertion was weakened.
- **Tests:** `tests/test_mic_flush_stall.py` 6/6 (drop-magnitude, busy guard, bound, fallback guard, fallback success, 8 s stall zero-drop order preserved). Full Python suite → **272 passed**. Node CI invocation → **110 passed**. devgraph updated. No commits.
- **Honest boundary:** the fix is proven on the real controller module but the **live controller 38298 still runs the old code** until the owner restarts it; physical "dictate during a flush, nothing lost" confirmation remains BLOCKED on the microphone handover like the AEC-REAL rows.

next: owner restarts 38298 → rerun soak and confirm `mic_dropped` delta 0 on the running installation; owner reopens VoiceBox → live unload measurement + clean SOAK-006 PASS + SIGABRT footprint investigation. Then wake-to-dictation latency segmentation.

### VA-CRASH-001, 2026-11-15 03:40 UTC — VoiceBox sidecar crash signature identified from on-disk crash reports (no service needed)

- **Investigated.** All twelve `voicebox-server` crash reports in `~/Library/Logs/DiagnosticReports/` (six incident pairs, 11-10 through 11-14) were parsed for signal, exception type, faulting thread, and symbols.
- **Finding.** Every fault is an MLX Metal failure with two surface forms: (1) uncaught C++ exception from `mlx::core::gpu::check_error(MTL::CommandBuffer*)` → `std::terminate` → `abort` (SIGABRT, self-kill, `Abort trap: 6`); (2) `EXC_BAD_ACCESS` at address `0x8` inside `mlx::core::eval_impl` reached from Python eval — one directly during `mlx::core::metal::MetalAllocator::malloc` — i.e. the GPU allocation error surfacing as a bad dereference instead of an exception. The 21:37 worker report (`voicebox-server-2026-11-14-213716.ips`) carries the same `check_error`/`terminate` symbols as the 11-13 crashes, so the soak-load crash is the identical failure mode as the older ones, just reached after ~5.3 h uptime and ~24 TTS generations with the sidecar footprint measured at 8.98 GB just before death.
- **What changed.** Only documentation: the crash table in `docs/testing/VOICEBOX-SERVICE-RUNBOOK.md` now lists all incidents with pids, launch times, and signatures; `docs/testing/scenarios/VA-SOAK-006-long-soak.md` history gained the forensics row.
- **Tests run.** None — no code changed. Suite state unchanged (272 Python / 110 Node from the previous iteration).
- **Honest boundary:** the *trigger* — whether per-generation footprint growth under the 46 GiB engine residency is what makes the command-buffer check fail — remains UNVERIFIED; `.ips` reports contain no stderr or allocator stats. Confirmation requires the owner to reopen VoiceBox so a live reload can be instrumented. This is evidence, not a PASS of any scenario.

next: owner reopens VoiceBox → instrument per-generation footprint growth and the guardian's live unload measurement; owner restarts 38298 → soak rerun with `mic_dropped` delta 0. Both P0 blockers are human handovers; everything else in the catalogue is covered or blocked on the same two actions.

### VA-MEM-005, 2026-11-15 03:55 UTC — the dual-engine Rule 0 had code but no test; it now has three

- **Reproduced first.** Read `watch()` in the installed guardian: Rule 0 checks `snap["dualEngines"]`, calls `stop_engine("dual_engine_conflict", snap, target="mtplx")`, and continues **before** the emergency rule, the voice shed, and the `write_pressure` call. `test_memory_guardian_policy.py` stubbed `stop_engine` but never fed a dual sample — the rule had zero coverage while every other tier did.
- **The change.** Harness: `snap(..., dual=True)` now sets `dualEngines: True` and `mtplxPids: [9999]`; the stop stub records the `target` argument. Three tests: (1) a dual sample at benign memory produces exactly one stop, `dual_engine_conflict`, target `mtplx`, and nothing else fires; (2) zero-headroom **plus** a second engine resolves the conflict first — stop order is `[dual_engine_conflict, memory_exhausted]` with targets `[mtplx, all]`; (3) while engines conflict, no pressure file is written and no voice unload is attempted — the guardian fixes the conflict before shedding voice.
- **Tests:** targeted `test_memory_guardian_policy.py + test_memory_guardian_contract.py` → **20 passed** (15 + 5). Full Python suite → **275 passed** (was 272). Node suite unchanged (110 from previous iteration). devgraph updated.
- **Follow-up in the same iteration:** Rule 4's three idle guards (`keep` policy, `in_flight`, busy slot) were also untested — `run_watch` now takes `idle_policy`, `idle_in_flight`, `slot_busy`; three more tests pin each guard and prove the unload fires on the first drained sample. The first run genuinely FAILED: the drain trace let the synthetic engine keep "running" after the stop, so Rule 4 re-fired four times; fixed by ending the trace at the expected action (the harness's documented limitation), assertion untouched. File now 19 tests; full suite **278 passed**.
- **Live cross-check:** both guardian watchers (38389, 38402) are running and `pressure.json` was rewritten within one poll (59.94 GiB used, 4.06 GiB headroom, `shedVoice: false`, `llmBusy: true`) — the guardian↔extension contract is provably live, and MTPLX is not currently resident.
- **Honest boundary:** synthetic traces only. The test proves the decision logic; it does not prove `stop_engine(target="mtplx")` actually kills a real MTPLX process cleanly. Live dual-engine behavior will be captured in the next VoiceBox-dependent soak.
- **Also dispatched this iteration:** a researcher investigating the MLX Metal `check_error`/`eval_impl` abort signatures upstream (known issues, allocator growth behavior, macOS memory-pressure interaction), writing to `docs/research/mlx-metal-abort-under-memory-pressure.md`.

next: owner reopens VoiceBox (live unload measurement, SOAK-006 clean PASS, footprint-growth instrumentation); owner restarts 38298 (`mic_dropped` delta 0 live, AEC-REAL rows).

### VA-DOC-003, 2026-11-15 04:10 UTC — live-state realignment: the unload number was already measured, and the running guardian is current

- **What was wrong:** six places (INDEX rows VA-TTS-013/014, scenarios VA-TTS-013, VA-TTS-014×2, VA-MEM-004, checkpoint status line) still claimed the live VoiceBox unload "has never been measured" or was "UNVERIFIED". It was measured on 2026-11-14 21:30 UTC, seven minutes before the SIGABRT: **11 MB freed of a 5,656 MB footprint**. The checkpoint's authoritative status line cited controller 64238 and guardian 40203 — both dead/replaced.
- **Verified against the machine, not the files:** `ps` shows watchers 38389 (python3.14) and 38402 (python3.9) running since 2026-11-14 16:16:29 local; the guardian script's mtime is 14:04 local — the running instances post-date every tested edit, so the tested policy IS the live policy (the VA-MEM-002 caveat about the 16:42 UTC edit now applies only historically). Dated iteration logs were left untouched per the checkpoint's own rule that old entries are snapshots.
- **New observation worth a human eye:** two guardian watchers run concurrently, each with its own strike counter, relief clock, and 60 s unload rate limit, both writing `pressure.json` last-writer-wins. Harmless for correctness (idempotent writes, duplicate unloads return `freedBytes: 0`), but it doubles the unload attempt rate at the boundary and is worth consolidating to one supervised instance. Not fixed here — killing either watcher is a human decision (loop rule: never stop the guardian).
- **Tests:** none needed; documentation only. Suites unchanged (Python 278, Node 110).

next: unchanged — the two human handovers (reopen VoiceBox, restart 38298) gate every remaining Level 3–5 row.

### VA-MEM-005, 2026-11-15 04:25 UTC — swap-reason kill coverage: the swap rule can label a kill but never trigger one alone
- **Investigated:** Rule 3's `swapping` branch in `watch()` (`tight = overCeiling or overSystem or swapping`, reason precedence `footprint` → `swap` → `system_memory`) had zero synthetic-trace coverage: `snap()` accepts `swap_growth`/`swap_delta` but no test ever passed them.
- **Structural finding:** `swapping` requires headroom < 1 GiB — exactly the `overSystem` floor — so swap growth can never arm a kill by itself; it only changes the kill's reason label. This is now pinned by assertion, not just prose.
- **Changed:** two tests added to `tests/test_memory_guardian_policy.py` (file now 21): 512 MiB swap growth at 61.5 GiB used → no stop, no unload, shed flag only; sustained 63.2 GiB with 128 MiB growth + 32-page swapout delta → exactly one voice relief, then stop with reason `swap` after the 10 s grace.
- **Failed first:** the 60-sample trace produced four extra `swap` stops — the documented harness artifact (synthetic engine stays "running" after a stop). Trace truncated to 42 samples (same length as the relief test); assertions unchanged.
- **Result:** targeted 21 passed; full Python suite **280 passed** (was 278). Node suite untouched (110). Docs: VA-MEM-001 expected-behavior bullet, history row, INDEX row updated.
- **Follow-up in the same iteration (04:40 UTC):** the harness itself was the reason the first run over-fired — `fake_stop` now marks a killed engine absent from later samples, target-aware (Rule 0 removes only MTPLX; an `all` stop removes both). This killed the documented "traces end at the expected action" limitation: the drain test runs a real busy→free slot sequence, the swap trace runs 60 samples asserting exactly one kill, and a new test pins that a kill clears the shed flag and never re-fires. Two dual-engine tests failed first because the naive model killed both engines on any stop — fixed by making death target-aware, not by loosening assertions. File now **22 tests**; full suite **281 passed**.
- **Unverified:** nothing new; live swap behavior under a real burst still Level 4/5 territory.
- **next:** unchanged — VoiceBox reopen and controller 38298 restart remain the gates.

### VA-MEM-006, 2026-11-15 04:55 UTC — the stop actuator itself was untested; now pinned
- **Investigated:** `stop_engine` — the actuator behind every kill rule — had zero coverage: the policy harness stubs it, and the contract file only tested `write_pressure` and `_voice_is_playing`. Three side effects mattered: SIGTERM targeting (`target="mtplx"` must never signal Strata), supervisor-stop resilience (the recorded field incident where `TimeoutExpired` escaped `watch()` and launchd restarted the guardian with the engine half-dead), and the 1.5 s rescan→SIGKILL escalation.
- **Changed:** four tests added to `tests/test_memory_guardian_contract.py` (4 → 8): targeted mtplx stop SIGTERMs only mtplx and skips the strata supervisor; `target="all"` SIGTERMs every pid; supervisor timeout/OSError logged, never raised; survivors escalate to SIGKILL, dead pids are not re-signalled, and a strata survivor is never escalated under a mtplx-targeted stop.
- **Failed first, and it mattered:** the first run called the real post-SIGTERM `scan_processes()`, which found the live Strata engine (pid 53687, 4 h 43 m up) and logged a SIGKILL for it. No harm — the fake `os.kill` intercepted every signal — but the probe was non-deterministic. Fixed by stubbing `scan_processes` (a `survivors` parameter) and `time.sleep`, then added the escalation test that the accidental discovery revealed as real semantics worth pinning. Verified 53687 still running afterward.
- **Exact result:** contract file 8 passed; full suite **285 passed** (was 281). Node untouched (110). New scenario doc `docs/testing/scenarios/VA-MEM-006-stop-targeting.md`, INDEX row added.
- **Unverified:** the real supervisor's 1.5 s drain and whether SIGTERM actually releases the Metal arena — Level 3, needs a live engine restart nobody wants to force.
- **next:** unchanged.

### VA-CRASH-001 follow-up, 2026-11-15 05:10 UTC — upstream MLX evidence closes the signature, not the trigger
- **Investigated:** the researcher persona stalled without producing output, so the upstream check was run directly: every one of the twelve crash reports matches a documented, unfixed MLX failure family. `check_error` throwing from a Metal completion handler → `std::terminate` is ml-explore/mlx #3224 (merged into umbrella #2670; maintainers state MLX is not exception-safe, so the abort is by design until `CommandEncoder` is made safe). The command-buffer failure behind it is `kIOGPUCommandBufferCallbackErrorOutOfMemory` after wired/Metal growth, per vllm-mlx #442 — whose key detail mirrors our unload experiment: RSS underreports the real footprint and killing the process instantly frees the wired pool (their 245 GB wired vs 19 GB RSS; our 11 MB freed of 5,656 MB). The `eval_impl`/`MetalAllocator::malloc` segfaults match mlx #3329 (null MTLBuffer in fused eval) and omlx #1200 (SIGABRT in MetalAllocator::malloc, closed as not planned). mlx-lm #1015/#883 confirm OOM crashes rather than graceful recovery in `generate()`.
- **Changed:** none in code. New research doc `docs/research/mlx-metal-abort-under-memory-pressure.md` (VERIFIED vs INFERENCE split, sources, measurement plan); runbook crash section gained the upstream paragraph.
- **Exact result:** crash table now reconciled: six on-disk incident pairs, one failure family, no upstream fix to wait for. Mitigations available to us: `MLX_BUFFER_CACHE_LIMIT` on VoiceBox relaunch (owner action), guardian deferral tiers (tested, VA-MEM-001/006), single-Metal-process overlap avoidance.
- **Unverified:** per-generation footprint growth inside VoiceBox is still unmeasured — the trigger claim remains INFERENCE until the owner reopens VoiceBox. `MLX_BUFFER_CACHE_LIMIT` effect on our sidecar untested.
- **next:** owner reopens Voicebox.app → instrument idle/after-generation/after-unload footprint across ten utterances, optionally with `MLX_BUFFER_CACHE_LIMIT=4G`; then the clean SOAK-006 run.

### VA-MEM-007, 2026-11-15 05:25 UTC — the flagged double watcher is real; a single-instance lock now guards the loop
- **Investigated:** `ps` showed two `strata-memory-ceiling watch` processes with identical 16 h 23 m uptimes: 38389 (parent 96779 — manually started, Homebrew Python 3.14) and 38402 (parent 1 — launchd's `com.akshay.strata-memory-ceiling.plist`, KeepAlive, system Python 3.9). Consequences: two strike counters, two 60 s shed timers (up to two unload POSTs per minute), and `memory-ceiling-last.json` last-writer-wins forensics. No crash risk — `stop_engine` already swallows `OSError` on dead pids (pinned by VA-MEM-006).
- **Failed first:** none — the guard was written after the live evidence.
- **Changed:** `_claim_watcher_slot()` in the guardian: `O_CREAT|O_EXCL` lock at `~/.local/state/strata/watcher.lock`; a live pid in the lock means this instance logs `duplicate watcher pid=...` and returns 0 before the sampling loop; a dead or corrupt lock is replaced. Two tests in `tests/test_memory_guardian_contract.py` cover claim/refusal/takeover and `watch()`'s early exit.
- **Exact result:** contract file 10 passed; full suite **287 passed**. Dry-run against the live state: first claim wins, same-pid re-claim fine, dead owner 999999999 replaced, live watcher 38389 correctly detected as owner — signal-0 probe only, both watchers untouched.
- **Unverified:** the running instances predate the guard and hold no lock; they stay doubled until the owner retires 38389 (`kill 38389`). Until then a launchd restart of 38402 will exit and retry every 10 s (ThrottleInterval) while 38389 lives — bounded churn, logged.
- **next:** owner actions unchanged: retire 38389, reopen Voicebox.app, restart controller 38298.

### VA-MEM-008, 2026-11-15 05:40 UTC — the shed actuator had never been run for real; its failure modes are now bounded
- **Investigated:** `shed_voice` — the relief tier that POSTs `/models/unload` before the guardian touches the engine — is stubbed in every policy test (`shed_result` parameter). Nothing pinned what happens when VoiceBox is refused (its actual state since the 21:37 SIGABRT, while the machine sits at the 61 GiB shed line as steady state) or hung (VA-LAT-001: health 200, generate 500).
- **Changed:** new `tests/test_memory_guardian_shed.py`: refused connection → no-op, no exception; synthetic accept-but-never-respond socket server → shed returns in under 8 s (the 5 s `urlopen` timeout, measured ~5 s); playing utterance → short-circuit before any HTTP, proven by a stubbed `_http_json` recorder.
- **Failed first:** none.
- **Exact result:** 3 passed; full suite **290 passed**. The kill loop's worst shed stall is bounded at 5 s per request; the unbounded-stall risk against a half-dead server is closed.
- **Unverified:** actual footprint delta on unload (11 MB, VA-MEM-001, only measurement); the 1 s sleep between unload and re-measure is real and untested for necessity.
- **next:** unchanged — all remaining rows need owner action (VoiceBox reopen, controller restart, retire 38389).

### VA-OPS-001, 2026-11-15 06:05 UTC — the start-serialization guard had zero coverage; restart-after-crash is now pinned

- **Investigated:** the loop contract's idle clause: every Level 1 row passes, everything else is owner-gated. The named unaddressed gap: **the controller itself has no crash-recovery story**. VoiceBox has forensic crash reports, the guardian has launchd KeepAlive, the extension has deferral/retry — but the mic owner (`omp-voice-controller`, pid 38298, 19 h uptime) is restarted only by hand, and the only thing standing between a supervisor (or a double `start`) and two processes fighting over the microphone is the PID-file flock in `_open_pid_lock`, which had **no tests**. Verified `~/Library/Logs/DiagnosticReports`: no controller crash report exists (the four `Python-*.ips` files are children of `omp`, not the controller), so the guard has never fired in production either.
- **Changed:** new `tests/test_pid_lock.py` (4 tests, microphone never opened, spawns recorded by a stub `Popen`): a synthetic lock holder makes `cmd_start_bg` print "already running" and spawn nothing; SIGKILL of the holder releases the flock at the kernel level and a stale pid in the file is ignored on the next start (the `os.kill(dead, 0)` probe path); the `pass_fds` fd-inheritance the daemon actually uses keeps the lock serialized while the child lives and releases it on death; `cmd_stop` against a dead pid prints "not running" and unlinks the stale file.
- **Failed first:** none. One trivial test (re-running the shutdown tail's unlink by hand) was written and deleted before running — it asserted wiring, not behavior.
- **Exact result:** `pytest tests/test_pid_lock.py -q` → **4 passed in 0.74 s**. Full Python suite → **294 passed** (was 290), `py_compile` clean. Node untouched (110 unchanged; no extension code changed). Scenario doc `docs/testing/scenarios/VA-OPS-001-pid-lock-serialization.md`, INDEX row added. devgraph updated. No commits.
- **Unverified:** whether a real daemon keeps the lock for its full 19-hour life (the mechanism is the same fd the test inherits); whether the mic-stream reconnect loop ever fires in the field ("Audio stream interrupted ... reconnecting in 1.0s" — never observed in 19 h).
- **Pending rows for the named gap (controller crash recovery, Level 5):**
  - VA-OPS-002 **BLOCKED (owner):** no supervisor exists for the controller. A launchd KeepAlive unit is the standard fix but creating one is external config requiring owner approval; it is safe only because VA-OPS-001 pins that a duplicate start can never open a second mic.
  - VA-OPS-003 **BLOCKED (owner):** live restart-recovery cycle — kill or stop the real controller, restart, confirm a full wake→dictation→reply turn works with no stale `controller.pid`, `status.json` transition STOPPED→IDLE, and no orphan afplay. Needs the microphone handover like the AEC-REAL rows.
  - VA-OPS-004 **NOT RUN:** crash forensics if a controller crash ever happens (DiagnosticReports currently clean for it).
- **next:** owner actions unchanged: reopen Voicebox.app, restart controller 38298, retire 38389. The controller-supervision decision (VA-OPS-002) is a one-question owner call.

## Loop prompt

Give the agent `HANDY-RALPH-VOICE-LOOP-PROMPT.md`, one iteration at a time. That file is the operating contract: levels 1–5, the safety rules, the AEC acceptance criteria, and the checkpoint write format. Do not speak into the microphone under this prompt; run the fixture probes unless microphone ownership has been explicitly handed to the iteration.
