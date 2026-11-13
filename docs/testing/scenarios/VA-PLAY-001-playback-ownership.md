# VA-PLAY-001 — Playback ownership

1. **ID:** VA-PLAY-001
2. **Name:** Playback ownership
3. **Objective:** One session ending a clip cannot clear another session's playback, an older clip cannot end a newer clip, and a dead player does not stay speaking.
4. **Failure investigated:** `tts-playing.json` was one object, `{playing, pid, started_at}` or `{playing:false, ended_at}`. `stopPlayback` and a finished `afplay` replaced that object. Session B's end set `playing: false` while session A was still audible. A dead writer left `playing: true` with no expiry.
5. **Preconditions:** Repository checkout. Python 3.12 venv at `~/.local/share/omp-voice/venv`. Node on `PATH` (this machine: v26.11.0; CI uses Node 22 with `--experimental-strip-types`).
6. **Required application versions:** None. This scenario does not launch OMP, Handy, VoiceBox, or `afplay`.
7. **Required services:** None.
8. **Hardware requirements:** None.
9. **Setup:** From the repository root. Do not set a state directory to `~/.local/state/omp-voice`.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_playback_state.py -q
    node --experimental-strip-types --test tests/playback-state.test.ts
    ```
11. **Fixtures:** `tests/playback_vectors.json`. Each case has `now`, `alive`, `tail`, `slots` (`null` means the slot directory is absent), `legacy`, and `expect`.
12. **Expected behavior:**
    - Slot files live in `<state>/tts-playing/<session-pid>.json`. The legacy `<state>/tts-playing.json` is only a projection: `playing: true` while any slot is playing, otherwise `playing: false` plus the latest `ended_at`.
    - Ending session B does not change session A's slot.
    - Ending clip 1 after clip 2 has started leaves clip 2 playing.
    - A slot with `playing: false` is speaking only for 0.6s after `ended_at`.
    - A slot with `playing: true` and a dead `afplay_pid` is not speaking.
    - A dead writer with a live `afplay` is speaking only for 60s after `started_at`.
    - A playing slot with no `afplay_pid` is speaking only while the writer is alive and `now < lease_until`.
    - A legacy file with no `sessions` object keeps the old rule and does not check pids.
    - When the `tts-playing` directory exists, it wins even if it is empty and the legacy file says `playing: true`.
13. **Pass/fail:** PASS when both commands exit 0. FAIL when any vector or transition assertion fails. There is no hardware result.
14. **Metrics:** None.
15. **Evidence:** The two command summaries. Do not copy speech logs.
16. **Cleanup:** Temp directories belong to the test process. Do not delete the user's `tts-playing.json`.
17. **Known failure modes:** The running OMP process keeps the old extension until that session reloads. The running controller keeps the old reader until it restarts. This scenario does not restart either. A projection write can still lose a race against the old reader; the slot directory is the authority for the new reader.
18. **Automation status:** LEVEL 4. Both commands are in CI (`.github/workflows/test.yml`).
19. **Known limitations:** Does not prove the speakers went quiet. Does not prove echo cancellation. A pid reused inside the 60s lease can look like the old `afplay`.
20. **Last verified:** 2026-11-13, working tree on `5540a03` plus the uncommitted playback change. `pytest tests/test_playback_state.py -q` and `node --experimental-strip-types --test tests/playback-state.test.ts` both exited 0. Full `pytest tests/ -q` was run in the same pass. No process was restarted.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-13 before the fix | `5540a03` | FAIL | One shared `tts-playing.json`. Any end replaced it. No pid lease. |
| 2026-11-13 | working tree after `5540a03` | PASS | Vector file shared by Python and Node. Temp-directory commits. No speakers. |
