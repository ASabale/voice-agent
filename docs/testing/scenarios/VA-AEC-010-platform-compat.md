# VA-AEC-010 — Platform compatibility without the AEC wheel

1. **ID:** VA-AEC-010
2. **Name:** The test suite and controller behave sanely where the WebRTC wheel cannot be installed
3. **Objective:** `aec-audio-processing==1.0.0` ships only an ARM64 CPython 3.12 wheel. On Intel Macs or other Python versions the controller must run with the render-subtraction fallback, and `pytest tests/` must not report false failures for WebRTC-specific behavior.
4. **Failure investigated:** Before 2026-11-14 the seven WebRTC-behavior tests in `tests/test_echo_control.py` were unconditionally executed. Reproduced in a clean Python 3.12 venv with `aec-audio-processing` uninstalled: 7 tests failed — four with `ModuleNotFoundError: No module named 'aec_audio_processing'`, and three by assertion: the multi-path room test measured only 9.3 dB ERLE through the fallback (threshold 15), the residual metric published an empty window, and the offset table left far less than −30 dB. The fallback fails loudly (no silent false pass), but the suite gave a misleading "the system is broken" signal on a platform where the controller is designed to degrade.
5. **Preconditions:** Repository checkout, Python 3.12 venv. No microphone, no services.
6. **Required application versions:** pytest, numpy.
7. **Required services:** None.
8. **Hardware requirements:** None; the venv simulates the missing wheel by uninstalling it.
9. **Setup:** `python -m venv /tmp/ci-venv312 && pip install -r requirements-dev.txt` then `pip uninstall aec-audio-processing` to simulate an Intel Mac.
10. **Execution:**
    ```sh
    python -m pytest tests/ -q
    ```
11. **Fixtures:** Same `say`/`good-morning` fixture wavs as VA-AEC-001–004.
12. **Expected behavior:** With the wheel: all 24 echo tests run and pass. Without it: the seven `@aec_required` tests are skipped, and the fallback tests — including `test_missing_module_falls_back_to_the_short_fit` (asserts `_echo_unavailable is True` and that the short fit is applied) — still run and pass.
13. **Pass/fail:** PASS means the suite is green on both sides of the platform matrix and the fallback path is exercised everywhere.
14. **Metrics:** Counts: 24 passed (wheel present); 237 passed, 7 skipped (wheel absent).
15. **Evidence:** 2026-11-14 17:05 UTC: `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_echo_control.py -q` → 24 passed. `/tmp/ci-venv312/bin/python -m pytest tests/ -q` with the wheel uninstalled → 237 passed, 7 skipped in 7.90 s.
16. **Cleanup:** The simulation venv was restored to the installed state after the run.
17. **Known failure modes:** If a future wheel appears for other platforms, the skip marker vanishes automatically (`importlib.util.find_spec`); no action needed. If the controller's fallback itself regressed, the fallback tests would catch it.
18. **Automation status:** LEVEL 1.
19. **Known limitations:** The Intel-Mac scenario is simulated by removing the package, not by running on an Intel machine. The physical echo quality of the render-subtraction fallback on real hardware is untested (blocked on microphone ownership, same as AEC-REAL-001–006). CI runs `macos-latest` (ARM64), so the skip path is only exercised locally.
20. **Last verified:** 2026-11-14 17:05 UTC.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-14 17:05 | `@aec_required` skipif marker added to 7 WebRTC-specific tests | PASS | README already documented the fallback strategy; the suite now matches it. No assertion thresholds changed. |
