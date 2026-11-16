# VA-OPS-002 — Controller supervision proposal (owner decision required)

Status: PROPOSED. No supervisor has been installed. Owner decides; the loop will not create the plist without approval.

## 1. Current responsibilities (manual operation)

- The controller is started by hand: `python bin/omp-voice-controller run --wake-word hey_jarvis --wake-threshold 0.5 ...`, stdout redirected by the shell to `~/.local/state/omp-voice/controller-restart.log`.
- Lifecycle code in `bin/omp-voice-controller`:
  - `run` (foreground): takes the PID-file flock (`_open_pid_lock(block=True)`, line 2765), installs SIGINT/SIGTERM handlers that set `running = False`, exits gracefully (cancel Handy, write `STOPPED`, unlink `controller.pid`).
  - `start` (background): probes the lock non-blocking, spawns `run` in a new session with stdout/stderr → `controller.log` and the held lock fd passed via `pass_fds`/`OMP_VOICE_PID_LOCK_FD`.
  - `stop`: SIGTERM, 1.5 s confirmation, unlink the pid file.
- Crash behavior today: none. If the process dies (not observed yet — 38298 has run ~20 h), nothing restarts it; the voice path is silently dead until the owner notices via `status`.
- Deployment gap this creates: the running controller is a snapshot of the tree at start time. As of 2026-11-15 the live pid 38298 predates commit `16ee173` (VA-AUD-004 mic flush, VA-OPS-001 pid lock), so "tested" and "running" diverge — the exact separation the checkpoint must track.

## 2. The two supervision options

### Option A — keep manual operation (baseline)
- Pros: zero new moving parts; owner controls exactly when the mic is opened; restarts are deliberate.
- Cons: no crash recovery; every A2-style restart is a human round trip (three such handovers already blocked iterations); drift between validated HEAD and the running process is invisible unless someone checks start times.

### Option B — launchd-managed controller (recommended)
Mirror the working guardian pattern (`~/Library/LaunchAgents/com.akshay.strata-memory-ceiling.plist`, KeepAlive, currently pid 38402):

```xml
<key>Label</key>            <string>com.akshay.omp-voice-controller</string>
<key>ProgramArguments</key> <array>
  <string>/Users/akshay/.local/share/omp-voice/venv/bin/python</string>
  <string>/Users/akshay/Development/voice-agent/bin/omp-voice-controller</string>
  <string>run</string>
</array>
<key>KeepAlive</key>        <true/>
<key>RestartInterval</key>  <integer>5</integer>   <!-- avoid restart storms -->
<key>StandardOutPath</key>  <string>/Users/akshay/.local/state/omp-voice/controller.log</string>
<key>StandardErrorPath</key> <string>/Users/akshay/.local/state/omp-voice/controller.log</string>
```

- Restart behavior: SIGTERM on unload/`launchctl stop` → the existing graceful path; on crash or SIGKILL, launchd re-executes within `RestartInterval`. The PID-file flock is released automatically on process death (VA-OPS-001 Level-1 tested).
- Microphone ownership: launchd guarantees one supervised instance; the flock (with the fix below) guarantees no overlap with a manually started one. The controller already self-heals stream-level mic failures internally (reconnect 1.0 s, rebind on device change at lines 4069–4133), so only process-level death needs the supervisor.
- Logging: launchd's redirect makes fd 1 *the* `controller.log`, which is exactly the condition VA-LOG-003's runtime rotation guard tests — rotation would finally apply (today the restart-path log `controller-restart.log` is unrotated).
- Shutdown semantics: deliberate stop = `launchctl unload` (graceful, Handy cancelled, status `STOPPED`); the `stop` subcommand stays for the manual path. Recovery after a crash is automatic and observable via `launchctl list`.

## 3. Supervision precondition — implemented, tested, not yet deployed

`run` originally opened the lock **blocking** (`_open_pid_lock(block=True)`); a launchd instance started while another instance held the lock hung on the flock forever (reproduced: 12 s hang, `.local/voice-agent/runs/VA-OPS-001b-repro.json`). The working tree now has `_claim_run_lock()`: a non-blocking claim, refusal with exit code 1 and an explicit "already running" message when held (re-tested: exit 1 in 0.07 s), with the claim taken before any model import or microphone access. `tests/test_pid_lock.py` covers it (7 tests, Level 1). The live controller 38298 predates all of this and holds no lock at all — the guard only takes effect once the controller is restarted (A2).

## 4. Recommended decision

Option B with the `run`-lock fix, plus a documented cutover:
1. Owner stops the manual controller (A2 restart happens as part of cutover, loading the current tree).
2. Owner installs the plist and `launchctl load`s it.
3. Verify: single pid, mic owned by that pid, crash restart works (`kill -9`, expect relaunch within ~5 s), graceful stop works.
4. Rollback: `launchctl unload` and delete the plist; the binary and pid file are unchanged, so manual `run` works again immediately.

Risks accepted: restart storm if the venv breaks (bounded by RestartInterval, visible in `controller.log`); unattended mic re-open after a crash (the owner is the only user of this machine; wake threshold stays 0.50).
