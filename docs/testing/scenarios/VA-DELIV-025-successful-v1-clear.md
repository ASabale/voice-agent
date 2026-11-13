# VA-DELIV-025 — A successful v1 clear drops both holds

1. **ID:** VA-DELIV-025
2. **Checked:** 2026-11-14 01:28 UTC.
3. **Level:** LEVEL 1. No microphone. The injector and osascript are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_successful_v1_clear_drops_the_sentence_and_both_prefixes -q`
5. **Result:** Passed. The successful v2 clear, the failed v1 clear, and the failed v1 scratch still passed.
6. **Clear.** `Ship the notes.` and `ship please` are held. Status GET is version 1. The transcript POST succeeds. The body is `clear draft` only. Nothing is typed. Both holds are cleared. The next `all done` posts `send prompt` only.
7. **Unchanged.** A clear POST that returns nothing still keeps both holds. Scratch still leaves them.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
