# VA-OPS-004 — cmd_stop must not claim success when the process survives SIGTERM

Level: 1 (unit, real subprocess) → 2 (production binary path) after suite run.

## Defect
`cmd_stop()` (bin/omp-voice-controller) sent SIGTERM, polled `kill(pid, 0)` 30 × 50 ms, then **unconditionally** printed `Stopped OMP Voice Controller (pid X)`, unlinked `controller.pid`, and returned 0 — even when the process was still alive at the end of the window. A failed stop therefore erased the only evidence the controller was running: `status` reported "not running" while the mic-owning daemon kept listening.

Secondary defect: `kill(pid, 0)` succeeds on a zombie. A stop invoked from the process that spawned the daemon (supervisor, test harness, `start_bg` caller) would classify an exited child as still alive.

## Acceptance criteria (written before implementation)
1. Process exits on SIGTERM within the 1.5 s window → `cmd_stop()` returns 0, prints "Stopped", removes `controller.pid`.
2. Process survives SIGTERM → returns 1, prints "still alive", keeps `controller.pid` intact.
3. Stale pid file pointing at a dead pid → returns 0, prints "not running", removes the file (existing behavior preserved).
4. A terminated-but-not-yet-reaped child (zombie) is classified as exited, not alive.

## Implementation
- `_process_exited(pid)` helper: `os.waitpid(pid, os.WNOHANG)` reaps own-child zombies; falls back to the `kill(pid, 0)` liveness probe for non-children.
- `cmd_stop()` branches on the poll result; failure path returns 1 and does not unlink.

## Evidence
- `tests/test_pid_lock.py`: `test_stop_reports_success_when_the_process_exits_on_sigterm`, `test_stop_reports_failure_when_the_process_survives_sigterm`, `test_stop_reaps_a_terminated_child_instead_of_calling_it_alive`; stale-pid row covered by existing `test_stop_on_a_dead_pid_file_leaves_no_stale_state`.
- Full Python suite result recorded in the checkpoint iteration log.

## Limitations
- Live-controller Level-3 stop against the real daemon 90992 is owner-gated (A2'): stopping 90992 is the owner's restart decision, not this iteration's.
- The 1.5 s window matches the daemon's observed graceful shutdown; a slow shutdown would now surface as a reported failure rather than a false success. Escalation (SIGKILL) deliberately not added — reporting honestly is the contract; force-kill is a policy decision.
