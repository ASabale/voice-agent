# VA-MEM-002 — Guardian monitoring overhead

1. **ID:** VA-MEM-002
2. **Checked:** 2026-11-14 18:45 UTC.
3. **Level:** 3, live observation of the installed guardian. No synthetic trace, no microphone, no model touched.
4. **User-facing failure prevented:** the memory watchdog degrading the machine it is meant to protect — a monitor that burns CPU or spawns processes every sample adds load to a machine already at 62 GiB.
5. **Preconditions:** `strata-memory-ceiling watch` running as pid 40203, started 2026-11-14 06:08 UTC. Engine footprint normal; nothing was deliberately stressed.
6. **Reproduction command:**
   - `ps -o pid,etime,cputime,%cpu -p $(pgrep -f strata-memory-ceiling)` — live process accounting.
   - In-process: compile `~/.local/bin/strata-memory-ceiling` as a module and call `sample()` 300 times, timing each.
   - `~/.local/bin/strata-memory-ceiling self-test` — prints `scan_ms` for one full scan.
7. **Expected:** monitoring cost well under 1% CPU and no subprocess spawn per sample.
8. **Actual:**
   - Live process: 5:53 CPU over 12 h 34 m elapsed = **0.78% average CPU**.
   - `sample()` timing (300 calls): median **1.11 ms**, min 1.06 ms, p95 1.39 ms, max 2.19 ms.
   - `self-test`: `scan_ms=2.24` (includes the full `libproc` process-walk plus footprint of every engine pid).
   - Per sample the loop also writes `pressure.json` and probes `http://127.0.0.1:8080/slots` (`llmBusy`, timeout 0.6 s); polling is 1.0 s, dropping to 0.5 s under pressure. Expected duty from the scan alone is 0.1–0.4%; the measured 0.78% includes those writes and probes. No subprocess is spawned for memory reads — Mach `host_statistics64`, `sysctlbyname`, and `libproc` are direct ctypes calls.
9. **Evidence:** the numbers above, plus the running instance's startup line in `~/.local/state/strata/memory-ceiling.log`: `poll=1.0s/0.5s ceiling=55GiB sys_used_kill=63GiB min_headroom=1.0GiB emergency_headroom=0.75GiB voice_shed=61GiB sustained=6 swap_growth=128MiB idle_unload=arm=62GiB grace=180s resident=1` — identical to the constants in the current script and in `tests/test_memory_guardian_policy.py`.
10. **Limitations:**
    - The script file's mtime is 16:42 UTC, later than the running process's 06:08 UTC start. The startup constants match, so the headline policy is the tested one; the semantics of the 16:42 edit are not diffable (the guardian is not version-controlled). A restart is the only way to guarantee the loaded bytes equal the file bytes; restarting the safety net is a human decision.
    - Kernel-CRITICAL stops logged at 05:10 and 05:29 UTC came from the previous instance, before the tier rewrite was loaded at 06:08 UTC. They are not evidence about the current policy.
11. **Result:** PASS. Monitoring load is ~0.8% CPU sustained across a 12.5 h run that included full-inference periods; no fix needed. No thresholds were changed.
12. **Live snapshot at check time:** `self-test` reported `sys_used=62.74 GiB`, headroom 1.26 GiB, `pressure=1` (normal), free 33%, swap 5.52 GiB — the steady-state operating point the tier policy is designed for.
