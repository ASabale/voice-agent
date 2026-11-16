# A4 — Who supervises the controller?

**RESOLVED (2026-11-16 07:16 UTC): Option 1 installed.** Owner approved; the unit `~/Library/LaunchAgents/com.akshay.omp-voice-controller.plist` (copy kept at `docs/ops/com.akshay.omp-voice-controller.plist`) runs `run --wake-word hey_jarvis --wake-threshold 0.5 --pause-seconds 5.0 --idle-timeout 15.0` with `KeepAlive: true`, `ThrottleInterval: 10`, stdout/stderr → `~/.local/state/omp-voice/controller-restart.log`. Verified: SIGINT to pid 4085 → launchd respawned pid 4387 in ~14 s, `status` IDLE holding the mic. The old unsupervised pid 251 was stopped cleanly (`stop` exit 0).

**Previous state (measured 2026-11-16 05:47 UTC):** the live controller (pid 251, up ~1 h 25 m) had parent pid 1 — nothing restarted it if it died.

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
