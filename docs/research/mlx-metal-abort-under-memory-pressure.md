# MLX Metal aborts under memory pressure — upstream evidence

Question: why does `voicebox-server` SIGABRT/SIGSEGV on this machine, and is the pattern known upstream?

## VERIFIED — the crash signatures are known MLX failure modes

1. **`check_error` → `std::terminate` → abort is MLX's documented unhandled-GPU-error path.**
   ml-explore/mlx #3224 (closed, merged into #2670): "When a Metal command buffer completes with an error status, `mlx::core::gpu::check_error(MTL::CommandBuffer*)` throws a C++ exception. If no catch block exists on the current thread, `std::terminate` is called and the process aborts." Maintainer response: MLX is not exception-safe; making `CommandEncoder` exception-safe is the prerequisite for a fix. The crash stack in #3224 (`check_error` → `__cxa_throw` → `demangling_terminate_handler` → `_objc_terminate` → `std::__terminate`) is the same chain our `voicebox-server-*.ips` reports show (2026-11-14 21:37 local, footprint 8.98 GB just before death).
   Sources: https://github.com/ml-explore/mlx/issues/3224, https://github.com/ml-explore/mlx/issues/3317, https://github.com/ml-explore/mlx-swift/issues/407 (same throw-from-completion-handler bug on iOS).

2. **The exception is thrown because the Metal command buffer fails with *Out of Memory*.**
   waybarrios/vllm-mlx #442: MLX-backed servers "grow native wired/Metal memory over time" under sustained request traffic until the log ends with
   `libc++abi: terminating due to uncaught exception of type std::runtime_error: [METAL] Command buffer execution failed: Insufficient Memory (00000008:kIOGPUCommandBufferCallbackErrorOutOfMemory)`.
   The reporter notes Python RSS *underreports* the pressure — wired/Metal allocations are the real ones (245 GB wired vs 19 GB RSS). Our unload experiment (11 MB freed of 5,656 MB; MLX arena persists) matches this: MLX's Metal allocator retains its pool.
   Source: https://github.com/waybarrios/vllm-mlx/issues/442

3. **The SIGSEGV variant maps to null-buffer eval crashes.**
   ml-explore/mlx #3329: SIGSEGV in `Compiled::eval_gpu` when a fused kernel receives a lazy/mmap'd array with a **null MTLBuffer** — consistent with our 2026-11-13 10:08–10:12 pair (`EXC_BAD_ACCESS` at `0x8` in `eval_impl`, one inside `MetalAllocator::malloc`). jundot/omlx #1200 reports SIGABRT in `mlx::core::metal::MetalAllocator::malloc` on M-series under memory pressure (closed as not planned, no fix). mlx #3216 shows the same terminate-chain stack during long generation on an M2 Ultra.
   Sources: https://github.com/ml-explore/mlx/issues/3329, https://github.com/ml-explore/mlx/issues/3216, https://github.com/jundot/omlx/issues/1200

4. **Concurrency of Metal processes is a known fast trigger.**
   vllm-mlx #442 comment (Thump604): "Concurrent Metal processes are the fast path to this crash... even a stray `python -c 'import mlx...'` can trigger it." Our steady state is exactly two Metal-heavy processes (Strata engine ~40–46 GiB wired, VoiceBox sidecar 3–12 GiB), with kernel VM pressure CRITICAL as the normal operating point. mlx-lm #1015 and #883 confirm `generate()`/`mlx_lm.server` crash rather than recover on Metal OOM.
   Sources: https://github.com/ml-explore/mlx-lm/issues/1015, https://github.com/ml-explore/mlx-lm/issues/883

5. **Mitigations that upstream reports as effective:**
   - `MLX_BUFFER_CACHE_LIMIT` (env var) bounds the retained Metal buffer pool; a reporter with multi-day stable runs credits it plus single-process serving.
   - Capping KV/context (`max_kv_size`) and concurrency bounds per-generation footprint growth.
   - Not keeping a second Metal process resident while the first is near the unified-memory ceiling.
   Sources: vllm-mlx #442 comments.

## INFERENCE — how this maps to VoiceBox here

- VoiceBox's per-generation footprint growth (3 GiB idle → 11.8 GiB during a burst, never returning) is consistent with the buffer-cache retention described upstream; we have not instrumented it per generation. [INFERENCE]
- The SIGABRT at 21:37 local, seven minutes after a guardian `/models/unload` that freed only 11 MB, fits "command buffer fails with Insufficient Memory while Strata is resident", but the exact failing buffer is unverified. [INFERENCE]
- `MLX_BUFFER_CACHE_LIMIT` cannot be tested without relaunching the VoiceBox GUI app (owner action); it is the first thing to try on the next reopen. [INFERENCE — the env var itself is upstream-documented]

## What to measure next

1. On VoiceBox reopen: record sidecar footprint at idle, after each generation, and after `/models/unload` — three points per utterance, 10 utterances. Growth that never returns = buffer-cache retention.
2. Launch VoiceBox with `MLX_BUFFER_CACHE_LIMIT=4G` (if the GUI accepts env) and repeat; compare the growth curve.
3. Watch whether a SIGABRT ever occurs while the Strata engine is unloaded (single Metal process) — upstream says concurrency is the fast path.
4. Keep the guardian deferral gate as the operational control: it prevents the burst from landing on top of the engine's 46 GiB.

## Reconciliation with our crash table

All twelve on-disk reports (six pairs, Nov 10–14) share one family: uncaught Metal error → abort, or null-buffer eval crash. Upstream has *no* exception-safe path yet (mlx #2670 is the umbrella). The only levers on our side are the guardian tiers (already tested, VA-MEM-001/006) and keeping Metal processes from overlapping — which is exactly what the deferral gate does.
