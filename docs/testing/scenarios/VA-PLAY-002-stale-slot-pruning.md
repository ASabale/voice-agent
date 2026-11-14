# VA-PLAY-002 — Dead-session playback slots are pruned

1. **ID:** VA-PLAY-002
2. **Name:** The playback state directory does not accumulate forever
3. **Objective:** A playback slot whose session process is gone is removed on read, so long-lived installations do not grow unbounded and never re-read dead sessions.
4. **Failure investigated:** On 2026-11-14 `~/.local/state/omp-voice/tts-playing/` held nine slot files (10 to 19 hours old) whose session pids were all dead. Nothing in the controller or the extension unlinked them; every mic frame re-read all of them.
5. **Preconditions:** Repository checkout, the project virtualenv.
6. **Required application versions:** None.
7. **Required services:** None. Do not start or stop the controller.
8. **Hardware requirements:** None.
9. **Setup:** From the repository root. Tests use temporary directories.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_playback_state.py -q
    ```
11. **Fixtures:** Slot files with stubbed `pid_alive`. No audio.
12. **Expected behavior:** `_read_playback_slots` unlinks a slot when its session pid is dead and the slot is not currently speaking (past the 0.6 s reverb tail, or its `afplay`/writer pids are dead). A slot inside the reverb tail is kept and still counts as speaking. A live session pid is never pruned. When the controller prunes any slot, it re-derives the flat `tts-playing.json` projection from the surviving slots, because a session SIGKILLed mid-clip would otherwise freeze the projection at `playing: true` forever — which would make the memory guardian skip voice shedding permanently. The Node extension's `readSlots` prunes symmetrically (dead session pid, not speaking) before publishing the aggregate.
13. **Pass/fail:** PASS when the assertions pass. Not a live-controller result.
14. **Metrics:** File existence after read; projection JSON contents after prune.
15. **Evidence:** `tests/test_playback_state.py` 25 passed (2026-11-14 19:19 UTC, incl. `test_project_aggregate_never_freezes_without_a_live_witness`); full suite 254 passed (also 254 in a clean Python 3.12 CI venv after the VA-CI-001 model fix); Node `tests/playback-state.test.ts` 19 passed incl. `projectAggregate requires a live afplay or writer witness`; full Node suite 89 passed. Earlier runs (2026-11-14 11:52 UTC): 24 + 77 with the first three projection tests. The nine live stale files disappeared during the earlier iteration from a source the loop did not observe (controller pid 64238 runs HEAD code with no pruning and logs no removal); the pruning behavior itself is proven only by the unit tests.
16. **Known failure modes:** Pruning happens only on read. If no controller read and no session publish occurs after a crash, the stale projection survives until the next read — the guardian's own afplay-pid liveness check (VA-MEM-004, 2026-11-14 19:20 UTC) is now the backstop for that frozen state. Before 2026-11-14 19:19 UTC the projection itself trusted the bare `playing` flag: a writer-lease slot whose writer died before `afplay` ever spawned projected `playing: true` with **no pid at all**, so the guardian had no witness to check and deferred voice shedding conservatively and forever. `project_aggregate` (Python, and `projectAggregate` in the extension) now takes a `pid_alive_fn`/`alive` predicate and derives `playing` with the same rule `slot_is_speaking` uses; callers that already liveness-check their slots (legacy tests with stub pids) keep the flag-only path by omitting the predicate. EPERM from `process.kill(pid, 0)` is treated as alive (conservative). Fixture probes must claim their slot under a live pid (`os.getpid()`); a synthetic dead pid gets its slot pruned mid-run — this actually happened: `run_double_talk_probe.py` crashed with `FileNotFoundError` on 2026-11-14 11:17 UTC.
17. **Cleanup:** Tests delete their temporary directories.
18. **Automation status:** LEVEL 1.
19. **Known limitations:** Does not demonstrate the running controller pruning; pid 64238 must restart with this code for that.
20. **Last verified:** 2026-11-14 19:19 UTC, working tree on top of `95a77f6`.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-14 before fix | working tree | FAIL (observation) | Nine dead-pid slot files accumulated; no code unlinked them. |
| 2026-11-14 11:10 | prune-on-read + 3 tests | PASS | Level 1. Live pruning not yet observed; controller not restarted. |
| 2026-11-14 11:17 | pruning vs fixture probes | FAIL → fixed | `run_double_talk_probe.py` crashed: the probe's synthetic dead session pid caused its own slot to be pruned mid-run. Fixed by using `os.getpid()` as the probe session pid and matching stand-in clip names; all four fixture probes re-ran PASS by 11:33 UTC. |
| 2026-11-14 11:52 | projection symmetry + Node prune | PASS (Level 1) | Found that `tts-playing.json` is only written by live sessions: a session killed mid-clip freezes the projection at `playing: true`, permanently blocking the guardian's voice shed. Controller prune now re-derives the projection; Node `readSlots` prunes dead sessions (pid-alive via `process.kill(pid, 0)`, EPERM=alive) and `commitBegin`/`commitEnd` accept an `alive` predicate. 3 Python + 3 Node tests added; 242 Python + 77 Node pass. Live stale projection in `~/.local/state/omp-voice/tts-playing.json` not yet refreshed — pid 64238 runs HEAD code. |