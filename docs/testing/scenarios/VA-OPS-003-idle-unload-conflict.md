# VA-OPS-003 — Watchdog and guardian disagree on idle unload

1. **ID:** VA-OPS-003
2. **Checked:** 2026-11-16 01:25 UTC.
3. **Level:** Level 1 predicate comparison plus Level 3 process observation. No engine was unloaded or restarted.
4. **Two unload paths exist.**
   - `~/.local/bin/local-llm` watchdog (live pid 4616, started 2026-11-15 19:01:42 UTC): `policy=idle`, `idle_timeout_sec=300`, `DEFAULT_IDLE_SEC=300` (line 19). Stops the engine after 300 s of zero requests **regardless of memory pressure**.
   - `~/.local/bin/strata-memory-ceiling` Rule 4 (live pid 38402): idle unload only when `systemUsedBytes >= 62 GiB` (arm == kill line) **and** idle ≥ 180 s. Below the arm line the guardian deliberately keeps the model resident so the KV prefix survives (guardian log line 235-240: `idle_unload=arm=62GiB grace=180s resident=1`).
5. **Reproduced conflict.** One synthetic snapshot — idle 400 s, system Used 59.2 GiB (measured steady state), not in flight — evaluates: watchdog `stop=True`, guardian `stop=False`. A five-minute gap between dictation bursts unconditionally unloads a 46 GiB engine that the guardian is explicitly trying to keep warm. Engine reload was measured at ~871 s in the launch profile, so the first turn after such a gap stalls ~15 minutes.
6. **Why it has not bitten yet.** `last_activity` (omp-autostart.json) and the engine log mtimes are refreshed by every agent request; the loop's own sessions keep the engine above the 300 s line continuously. The predicate conflict is latent, not yet a realized failure.
7. **Not done.** No engine unload/reload was performed. Owner decision required (A5): either set `local-llm policy keep` and let guardian Rule 4 own idle unload, or raise `idle_timeout_sec` to a value consistent with the voice usage pattern.
