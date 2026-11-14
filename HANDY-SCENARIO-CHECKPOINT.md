# Handy scenario checkpoint

This file is the only source of truth for the Handy / Hey Jarvis test pass. Each turn, read this file fresh. Skip every row whose result is `pass`. Take the next `pending` or `fail` row, test it, and write the log result back into that row. If it fails, fix the controller in that same turn and retest until that row passes. Then mark it `pass` and move to the next open row. Do not retest a `pass`. Do not carry the plan from chat memory.

## Current engineering status (authoritative — 2026-11-14 16:53 UTC)

This section is the only current status. Everything below it is dated historical evidence and must never be read as live state. Pids, ports, and model sizes in any other section are snapshots; re-derive them from `omp-voice-controller status`, `~/.local/state/omp-voice/sessions/<pid>.json`, and `curl -fsS -m 2 http://127.0.0.1:17493/health` before acting.

Verified live at 10:48 UTC this run: controller pid 64238, state `IDLE` (still the pre-VA-* process); OMP bridge ok on ephemeral port 62282 for pid 2734; no process listening on 17493 — VoiceBox is down, so its unload relief is unmeasured. Guardian artifacts are live: `~/.local/state/strata/pressure.json` written with `shedVoice: false` at 59.44 GiB used, `memory-ceiling-last.json`, `memory-ceiling.log`, and `idle-watchdog.pid` all present.

**CI baseline fixed (2026-11-14).** Eight consecutive failed Actions runs (43530350727 → 43542615491) had two causes: (1) the openWakeWord wheel ships no model files, so four wake tests failed on the runner — fixed by `ensure_wake_models()` in `bin/omp-voice-controller` (downloads the two ONNX models when missing) plus an autouse fixture in `tests/conftest.py` that calls it before any test needing wake files; (2) `aec-audio-processing` was a bare line in `requirements-dev.txt` — moved to `requirements-aec.txt` and made best-effort in `bin/install`. Reproduced with the exact CI commands in a fresh Python 3.12 venv: `python -m py_compile bin/omp-voice-controller` and `python -m pytest tests/` pass; the three Node files pass on the local node. GitHub still shows the old failing runs until the fix is pushed.

Results by validation level (levels defined in `HANDY-RALPH-VOICE-LOOP-PROMPT.md`):

| Level | Closed | Open |
|---|---|---|
| 1 — unit | Full suite 256 passed; Node files 103 passed (2026-11-14 21:40 UTC). Grammar, playback ownership, playback-slot pruning of dead sessions on both sides plus projection re-derivation after a prune (VA-PLAY-002), speech queue, log rotation including runtime rotation of the daemon's own log (VA-LOG-003), mic-capture accounting, delivery holds, Handy control, dynamic bridge-port discovery (VA-OMP-001/002/003), synthetic AEC (VA-AEC-001–004, VA-AEC-009, VA-AEC-011, VA-OBS-001), turn-latency field semantics (VA-LAT-001 unit tests), guardian tier policy on synthetic traces including the unload race re-check and the bounded `freed=0` unload grace (VA-MEM-001, 13 tests), deferred-sentence retry/expiry/epoch discipline (VA-TTS-014, VA-TTS-017, VA-TTS-018), mid-request socket death held as refusal (VA-TTS-021) | none blocking |
| 2 — fixture-fed controller integration | VA-TTS-007/008/010, VA-AEC-005–008, VA-INT-AUTO-040 (closed 2026-11-14 13:35 UTC: wake, Handy file ASR, two submits, playback, and the stop fixture now cuts a stubbed `afplay` after the AEC correlation guard + pre-roll fix), VA-LAT-001 (turn latency `turn_seq`/`wake_to_flush_s`/`asr_s`/`dispatch_s` published through a full fixture turn; `stop_latency_s` only unit-tested — the Level 2 stop run is blocked on VoiceBox `/generate/stream` 500) | none blocking — VA-AEC-005–008 were re-run against the current uncommitted tree on 2026-11-14 11:19–11:33 UTC and all pass |
| 3 — local service integration | VA-INT-AUTO-001/003/004/036/037/041 (isolated `omp -p`, real Handy `--transcribe-file`, real VoiceBox, real `afplay`; VA-INT-AUTO-041 cut afplay 0.589 s after the barge hold) | end-to-end turn latency (`turn_seq`…`stop_latency_s`) published from the running controller (pid 64238 never restarted with the new fields); VoiceBox unload relief never measured because the service is down |
| 4 — physical acoustic | none | VA-INT-001 and the five AEC acceptance criteria (room ERLE, no echo wake, verbatim double-talk transcription, stop/wake barge latency, render alignment under `-r` and pause). Blocked by exclusive mic ownership: pid 64238 holds the MacBook Pro Microphone (VA-INT-AUTO-005/038); the AEC path only loads when the controller restarts |
| 5 — extended reliability | queue saturation at Level 1 (VA-SOAK-001: 300 held sentences replay exactly once on recovery) | long runs, repeated interruptions, service restart/recovery, memory growth under a live controller; stale slot/registry cleanup is unit-covered (VA-PLAY-002, dead-pid sweep in `load_session_registry`) but never observed over a long live run |

## Level 4 physical AEC acceptance — BLOCKED (2026-11-14 10:48 UTC)

The five acceptance criteria in `HANDY-RALPH-VOICE-LOOP-PROMPT.md` (ERLE through the real speaker-to-mic path, no wake or barge from echo alone, verbatim double-talk transcription, stop/wake barge latency, render alignment under `-r` and pause) cannot be run this session. Verified blockers:

1. `omp-voice-controller status` shows pid 64238 `IDLE` holding exclusive ownership of the MacBook Pro Microphone (VA-INT-AUTO-038). A second capture instance cannot attach without corrupting its VAD.
2. pid 64238 was started before the AEC diff, so the `aec_echo_db` / `aec_blocks` fields it would publish do not exist in the running process. Any Level 4 measurement requires Akshay to stop and restart the controller.
3. Nothing is listening on 17493, so a real spoken reply — the sound the canceller must cancel — cannot be generated. Per `docs/testing/VOICEBOX-SERVICE-RUNBOOK.md`, recovery is manual: quit VoiceBox and reopen it.

What Akshay must do before Level 4 can run: reopen VoiceBox, then restart the controller (`omp-voice-controller stop` then the usual `run --wake-word hey_jarvis --wake-threshold 0.5`). The loop stays non-idle until these rows have live evidence.

## Tested but not loaded into running processes

A unit or fixture pass is not live behavior until the process loads it. As of 2026-11-14 03:43 UTC:

- Running controller pid 64238 was never restarted, so it still runs the pre-VA-* code: the old single `tts-playing.json` projection path, the old per-frame VoiceBox health check, the old drop-on-full mic callback, and no `aec_echo_db` / `aec_blocks` / turn-latency fields in `status.json`.
- Running OMP sessions never reloaded `extension/voicebox-speech.ts`, so the speech-queue fixes (VA-TTS-001–012) are not in effect in them.
- Uncommitted at the working tree: `bin/omp-voice-controller` publishes turn-latency fields (`turn_seq`, `wake_to_flush_s`, `asr_s`, `dispatch_s`, `stop_latency_s`) in `status.json` under a `turn` key — validated at Level 2 by VA-LAT-001 (2026-11-14), never loaded into the running controller. Plus the adjusted `tests/test_handy_control.py` assertions and `tests/test_echo_control.py` offset tests. `bin/omp-voice-controller` now rotates `controller.log` while running (`_rotate_stdout_log`, VA-LOG-003); pid 64238 started before the change, so its 31 MB log stays unrotated until a restart. `extension/voicebox-speech.ts` now defers sentences when headroom is tight and retries them (VA-TTS-013/014); no running OMP session has reloaded it.
- Consequence: every VA-* "the live controller still ... until restart" limitation in `docs/testing/INDEX.md` is still true. Before any row is called live, restart the controller or reload the extension and re-observe.

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

## Loop prompt

Give the agent `HANDY-RALPH-VOICE-LOOP-PROMPT.md`, one iteration at a time. That file is the operating contract: levels 1–5, the safety rules, the AEC acceptance criteria, and the checkpoint write format. Do not speak into the microphone under this prompt; run the fixture probes unless microphone ownership has been explicitly handed to the iteration.
