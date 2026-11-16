# VA-OPS-005 — `cmd_start_bg` must not claim "Started" for a daemon that never registered

1. **ID:** VA-OPS-005
2. **User-facing failure prevented:** A `start` (or a supervisor's restart attempt) that prints "Started OMP Voice Controller in background (pid N)" while the spawned process died instantly. The user believes the mic agent is live; `status` later contradicts it, and the only stdout evidence sits in a log file nobody reads. Same false-success class as VA-OPS-004, on the spawn side.
3. **Preconditions:** no microphone, no live services; isolated `OMP_VOICE_STATE_DIR`; stub child processes only.
4. **Exact reproduction command:** `~/.local/share/omp-voice/venv/bin/python .local/voice-agent/probes/repro_start_bg_false_success.py` — runs `cmd_start_bg` with `subprocess.Popen` pointed at a stub that prints `boom` and exits 3.
5. **Expected behavior:** exit 1, message naming the exit code and the log file; no pid ever claimed.
6. **Actual behavior (before fix):** printed `Started OMP Voice Controller in background (pid 92505, ...)` and returned 0 after a blind `time.sleep(START_SPAWN_WAIT_SECONDS)`. The spawn result was never inspected.
7. **Evidence:** repro output recorded above (pre-fix run 2026-11-16 04:05 UTC); post-fix run prints `Controller spawn failed: pid 93762 exited with code 3; see /tmp/.../controller.log` and returns 1.
8. **Level:** LEVEL 1 (unit, real subprocess, microphone never opened) + LEVEL 2 (production binary `start` against a held lock → refusal path unchanged).
9. **What was reproduced first:** the false-success print, exactly as shipped.
10. **Root cause:** `cmd_start_bg` slept 1.2 s and unconditionally printed/returned success; `proc.poll()` was never checked.
11. **Fix:** `cmd_start_bg` polls inside the spawn window: child exited → "spawn failed: pid N exited with code C" → 1; pid file names the child → "Started" → 0; window expires with the child alive but unregistered → "spawned ... but did not register within Xs ... it is still running" → 1. No force-kill: honest reporting, escalation stays owner policy.
12. **Tests run:** `tests/test_pid_lock.py` 13 passed (3 new: dies-before-register, registers-then-success, alive-but-unregistered). Full Python suite 314 passed. The pre-existing fake-spawn tests needed `_Fake.poll()` and a registration write — that is the new contract, not a weakening.
13. **Result:** PASS 2026-11-16 04:10 UTC.
14. **Latencies measured:** registration normally observed within ~0.1 s of spawn (pid file is written before model imports); the 1.2 s window is unchanged.
15. **Boundary behavior:** the flock open itself creates an empty pid file, so "file exists" is not the success signal — the file must *name the child*. A stale pid from a previous daemon never matches the new child's pid.
16. **Cleanup:** stubs live only in pytest `tmp_path` and the probe's temp dir; probe file stays in `.local/voice-agent/probes/`.
17. **Automation status:** LEVEL 1 suite, rerunnable anywhere.
18. **Known limitations:** a daemon that registers (pid file written) and *then* dies within the window — e.g., an import crash a second later — is still reported as "Started" at the moment of the check; that outcome is caught by `status`/`stop`, since the pid file no longer names a live process. Live end-to-end restart of controller 90992 remains owner-gated (A2').
19. **Last verified:** 2026-11-16 04:10 UTC.
