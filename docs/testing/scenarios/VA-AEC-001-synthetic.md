# VA-AEC-001 — Synthetic echo control

1. **ID:** VA-AEC-001
2. **Checked:** 2026-11-13 21:55 UTC. Rate alignment rechecked the same evening.
3. **Level:** LEVEL 1. The WebRTC library runs. The microphone does not. Not acoustic echo cancellation. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_echo_control.py tests/test_barge_fixture.py tests/test_playback_state.py -q`
5. **Result:** `tests/test_echo_control.py` 12 passed. Half a second at rate 1.18 selects samples 8160 through 9439. With 0.25 s held, `cancel_playback_echo` sends samples 3440 through 4719.
6. **Bars, from this machine, last second of a 4 second loop.** One 20 ms copy of `sentence-stop-say.wav` at gain 0.6 loses at least 20 dB. A 20 ms copy plus a 40 ms copy loses at least 12 dB. `good-morning-say.wav` against silence or against the other sentence keeps more than half its tail energy. Mixed with the 20 ms echo, it keeps more than 40 percent of that energy.
7. **Live process.** Controller pid 64238 was not restarted. It still subtracts with the short fit. OMP pid 16590 was not signaled. VoiceBox on port 17493 was not restarted.
