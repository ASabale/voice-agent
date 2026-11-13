# VA-OMP-001 — Session bridge status

1. **ID:** VA-OMP-001
2. **Name:** Session bridge status
3. **Objective:** `omp-voice-controller status` reports the bridge that the session registry names, and does not call a healthy ephemeral bridge down because nothing is listening on port 17494.
4. **Failure investigated:** Status always requested `http://127.0.0.1:17494/status`. On 2026-11-13 that port refused the connection while `sessions/<pid>.json` pointed at a live bridge (`ok: true`). The printed note told the user to restart OMP and bind :17494.
5. **Preconditions:** Repository checkout. Dev venv at `~/.local/share/omp-voice/venv`. For the live check only: one OMP session whose extension has written `~/.local/state/omp-voice/sessions/<pid>.json`, and that pid still alive.
6. **Required application versions:** Not pinned. The live check on 2026-11-13 used the extension in this repo (`version: 2` on `/status`) and the controller script in `bin/omp-voice-controller`. macOS 26.6.2 (25G83), arm64. Python 3.12.13 in the venv.
7. **Required services:** None for the unit tests. Live check: the OMP session that owns the registry file. Do not start or restart it.
8. **Hardware requirements:** None. Do not play audio.
9. **Setup:** From the repository root. Do not set `OMP_VOICE_BRIDGE_URL`. Do not submit a transcript.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_delivery.py -q -k "status_targets or probe_"
    ```
    Live check, only when a session file exists:
    ```sh
    python3 -c 'import json,pathlib; p=pathlib.Path.home()/".local/state/omp-voice/sessions";
    [print(f.name, f.read_text()) for f in sorted(p.glob("*.json"))]'
    ~/.local/bin/omp-voice-controller status
    ```
    `~/.local/bin/omp-voice-controller` is a symlink to `bin/omp-voice-controller` after `./bin/install`.
11. **Fixtures:** None. The unit tests pass the port list in process and replace `bridge_request`.
12. **Expected behavior:** Targets for a session port and no legacy owner are only `http://127.0.0.1:<port>`. An empty registry and no legacy listener produce no targets and the note `No session bridge responded`, with no mention of 17494. A probe of a healthy delivery port returns that payload plus `url`. Live status sets `omp_bridge.ok` true and `omp_bridge.url` to the port in the current registry file. Stdout has no `bridge_request http://127.0.0.1:17494/status failed` line unless `lsof` shows a listener on 17494.
13. **Pass/fail:** PASS when the pytest command exits 0 and, if a live session file exists, `omp_bridge.url` ends with that file's `port` and `omp_bridge.ok` is true. FAIL when status reports ok false while that port's `/status` returns ok true. BLOCKED when no session file exists and a live check was required. The unit tests alone are not a live PASS.
14. **Metrics:** None. One status process, one GET per probed base, stop at the first `ok: true`.
15. **Evidence:** Pytest summary. The status JSON. The registry file contents. Do not copy the controller log into this file.
16. **Cleanup:** None. The status command does not write the registry or the draft.
17. **Known failure modes:** A dead pid leaves a registry file; `load_session_registry` deletes it when the pid is not alive. A focused non-text surface still selects the newest session. A focused text control whose tty does not match a session is a paste; the bridge can still be up. Caching a port from an earlier run fails because the extension binds with `listen(0)` again on session start.
18. **Automation status:** LEVEL 4 for target selection and probe order (`tests/test_delivery.py`). The live registry comparison is LEVEL 2: the command is documented, and a person or agent still has to read the JSON.
19. **Known limitations:** This scenario does not submit a dictation and does not prove the draft changed. G10 in `HANDY-SCENARIO-CHECKPOINT.md` stays blocked. `bridge_base` still falls back to 17494 when a delivery dict has no port; status does not use that fallback.
20. **Last verified:** 2026-11-13, working tree on commit `5540a03` plus the uncommitted status change. Unit suite `pytest tests/ -q`: 67 passed. Live status at 12:43:48 local reported `url` `http://127.0.0.1:57042` for pid 80894, matching `sessions/80894.json` then. Earlier the same hour that pid's file said port 56876. Do not treat either port as the bridge address.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-13 before the fix | `5540a03` | FAIL | Status probed :17494, connection refused, while the registry port answered `/status`. |
| 2026-11-13 12:43 | working tree after `5540a03` | PASS | Unit tests 67 passed. Live `omp_bridge.ok` true at the registry port. No speech. |
