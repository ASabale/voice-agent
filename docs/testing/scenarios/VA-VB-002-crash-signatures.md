# VA-VB-002 — VoiceBox crash signature analysis (Level 1, static)

## Question
Priority B says "do not assume the crash trigger has been established." The 12 crash reports had never been signature-analyzed. What do the crashes actually fault on?

## Method
Parsed every `~/Library/Logs/DiagnosticReports/voicebox-server-*.ips` (12 files = 6 crash events; macOS writes a paired EXC_CRASH report alongside the faulting report). Parsed evidence preserved at `.local/voice-agent/runs/VA-VB-002-crash-signatures.json`. Original reports untouched.

## Findings
Six distinct crash events, exactly two fault signatures, both inside MLX — never in the VoiceBox HTTP/serving code:

| Event (local, -0500) | Signature | Faulting frames |
|---|---|---|
| 2026-11-10 18:11 | SIGSEGV, `EXC_BAD_ACCESS` | `mlx::core::eval_impl` ← `mlx::core::eval` ← `_PyEval_EvalFrameDefault` (thread 19) |
| 2026-11-13 08:57 | SIGABRT | `abort` ← `demangling_terminate_handler()` ← `_objc_terminate()` (thread 54) |
| 2026-11-13 10:08 | SIGABRT | same terminate-handler path (thread 39) |
| 2026-11-13 10:12 | SIGSEGV, `EXC_BAD_ACCESS` | `mlx::core::eval_impl` (thread 19) |
| 2026-11-14 00:51 | SIGSEGV, `EXC_BAD_ACCESS` | `mlx::core::eval_impl` (thread 41) |
| 2026-11-14 21:37 | SIGABRT | terminate-handler path (thread 39) — the soak crash after ~24 generations |

- **3 SIGSEGV events**: all fault inside `mlx::core::eval_impl` called from Python `eval` on MLX worker threads. Segfault *during array evaluation*, not during model load or request parsing.
- **3 SIGABRT events**: an uncaught C++ exception reaches `demangling_terminate_handler()` → `abort`. The exception text is not captured in the .ips files; the frame pattern is what MLX raises when an internal (typically Metal resource) throw escapes to Python.
- No crash report implicates the HTTP layer, model load, or the 0.6B vs 1.7B model choice directly.
- The Nov 13 cluster (08:57, 10:08, 10:12 — three crashes in ~75 minutes) shows the owner restarted and hit the same fault repeatedly; crash mode is recurring, not a one-off.

## Interpretation (hypothesis, not established trigger)
Both signatures are consistent with MLX Metal resource exhaustion during sustained generation: the footprint evidence (5.6 GB → 9 GB growth over a soak; unload freeing only 11 MB of a 5,656 MB footprint) and eval-time segfaults/aborts point to arena/buffer-cache growth under repeated eval calls. This is *consistent* with — not proof of — a buffer-cache limit being the lever. `MLX_BUFFER_CACHE_LIMIT=4G` remains an untested A/B variable.

## What the live investigation (Priority B steps 2–10) must prove
1. Per-generation footprint trajectory under ten consecutive generations (monotonic vs stabilizing).
2. Whether `MLX_BUFFER_CACHE_LIMIT=4G` changes the trajectory or crash frequency — do not claim it fixes anything until measured.
3. That a controlled restart restores service and held sentences replay exactly once, in order.
4. Which exception text the SIGABRT events carry — run the sidecar with stderr captured during the footprint sweep so the terminate message is recorded next time.

## Level achieved
Level 1 (static analysis of real crash artifacts). No live reproduction yet; Level 3 requires the owner to reopen VoiceBox (A1).
