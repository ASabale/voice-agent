# VA-OMP-003 — Missing registry port

1. **ID:** VA-OMP-003
2. **Name:** A live omp process with no session file
3. **Objective:** Delivery uses the bridge when the registry file is gone but the process has one loopback listener that identifies itself.
4. **Failure investigated:** At 14:16 on 2026-11-13 the controller logged `Delivery paste pid=80894 port=None focused_text=True` and `Partial field skipped (paste, focused=True)`. `sessions/` had no file. `GET http://127.0.0.1:56876/status` returned `ok: true` and `pid: 80894`.
5. **Preconditions:** Repository checkout and the project virtualenv.
6. **Required application versions:** None.
7. **Required services:** None for the unit test. Do not POST `/transcript`.
8. **Hardware requirements:** None.
9. **Setup:** From the repository root.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_delivery.py -q
    ```
11. **Fixtures:** lsof-style lines `n127.0.0.1:56876`, two ports, and `n*:80`. No live lsof call.
12. **Expected behavior:** One `127.0.0.1` port is kept. Two ports, or a wildcard listen, is not. A session record whose `pid_bridge_port` returns 56876 is a bridge to that port for the focused tty. A record that still has `port: None` stays a paste.
13. **Pass/fail:** PASS means the delivery tests. It does not mean the running controller used the port.
14. **Metrics:** None.
15. **Evidence:** The pytest summary. The 14:16 lines stay in `controller.log`.
16. **Cleanup:** None.
17. **Known failure modes:** The running controller still pastes until it restarts. A process with two loopback listeners is left as a paste. A `/status` body whose pid does not match is left as a paste.
18. **Automation status:** LEVEL 4.
19. **Known limitations:** The test stubs `pid_bridge_port`. It does not open a socket.
20. **Last verified:** 2026-11-13, commit `96cee6e` plus this working tree. `pytest tests/ -q` — 98 passed.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-13 14:16 | running controller | FAIL | Focused Terminal dictation pasted because the registry file was gone. |
| 2026-11-13 | working tree after `96cee6e` | PASS | Unit test only. The controller was not restarted. |
