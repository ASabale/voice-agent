# VA-DELIV-013 — An up bridge sends both prefixes once

1. **ID:** VA-DELIV-013
2. **Checked:** 2026-11-14 00:16 UTC.
3. **Level:** LEVEL 1. No microphone. The injector is stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_an_up_bridge_sends_both_prefixes_once -q`
5. **Result:** Passed. The failed-status second-prefix test and the retried-send test still passed.
6. **Up bridge.** `Ship the notes.` and `ship` are held. Status GET is ok. `please all done` posts `Ship the notes. ship please send prompt` once and does not type. Both holds are cleared. The next `please all done` posts `please send prompt` only.
7. **Code.** The send join already included the stored prefix. This slice locks the successful first post. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
