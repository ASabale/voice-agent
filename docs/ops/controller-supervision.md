# A4 — Who supervises the controller?

**Current state (measured 2026-11-16 05:47 UTC):** the live controller (pid 251, up ~1 h 25 m) has parent pid 1 — it was started detached and nothing restarts it if it dies. The memory guardian is already a launchd unit (`com.akshay.strata-memory-ceiling`), which is the model to follow.

## Option 1 — launchd unit (recommended)
- `~/Library/LaunchAgents/com.akshay.omp-voice-controller.plist` with `KeepAlive: true`, the exact production argv (`run --wake-word hey_jarvis --wake-threshold 0.5 --pause-seconds 5.0 --idle-timeout 15.0`), stdout redirected to the rotating `controller-restart.log` path.
- Pros: auto-restart on crash, survives reboots, one supervisor, matches the guardian pattern; launchd already proved it can re-spawn and claim a lock (A3 consolidation).
- Risks: the mic is exclusive — a restart storm while a probe holds the mic would thrash; the pid lock (`~/.local/state/omp-voice/controller.pid`) already refuses double starts, so a KeepAlive loop is bounded. Log rotation is fd-based (VA-LOG-003), so redirecting launchd stdout to the same file is safe.

## Option 2 — restart wrapper script
- A `nohup` wrapper that runs `run`, traps exit, sleeps 2 s, restarts.
- Pros: trivial, no system config.
- Cons: no reboot survival, the wrapper itself is unmonitored (same problem one level up).

## Install procedure (owner-executed)
1. `launchctl unload ~/Library/LaunchAgents/com.akshay.strata-memory-ceiling.plist` is NOT needed; the controller unit is separate.
2. Stop the current controller: `~/.local/bin/omp-voice-controller stop` (VA-OPS-004 makes this honest: exit 1 if SIGTERM fails).
3. Copy the plist to `~/Library/LaunchAgents/`, then `launchctl load ~/Library/LaunchAgents/com.akshay.omp-voice-controller.plist`.
4. Verify: `launchctl list | grep omp-voice` shows the pid; `status` shows IDLE and the mic.

**Decision needed from Akshay:** approve Option 1 and an agent may create, install, and verify the unit (RALF §2 authorizes restarts; the mic is already held by the controller being replaced).
