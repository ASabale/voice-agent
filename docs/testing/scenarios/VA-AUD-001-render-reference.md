# VA-AUD-001 — Render reference

1. **ID:** VA-AUD-001
2. **Name:** Playback render reference
3. **Objective:** The playback slot names the WAV file that `afplay` is playing, including its PCM format. This does not cancel echo.
4. **Failure investigated:** VoiceBox audio was written to a temp WAV and played, then deleted. The controller never saw that signal, so an echo canceller would have had no reference.
5. **Preconditions:** Repository checkout. Node on `PATH`. Python venv for the controller check.
6. **Required application versions:** None.
7. **Required services:** None. Do not start VoiceBox.
8. **Hardware requirements:** None for this check. Echo suppression still needs speakers and a microphone, and that check has not been run.
9. **Setup:** From the repository root.
10. **Execution:**
    ```sh
    node --experimental-strip-types --test tests/playback-state.test.ts
    ~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_playback_state.py -q
    ```
11. **Fixtures:** A 160-frame 16 kHz mono 16-bit WAV built in the Node test. No recorded speech.
12. **Expected behavior:** `connect_render_reference` returns the PCM only when the header matches the slot. `best_render_delay` finds a 10-sample delay in a synthetic buffer. `subtract_aligned_render` removes a half-scale copy of that buffer and leaves a residual of at most 1. Uncorrelated noise at correlation 0.85 returns no delay, so the block is not changed. For an 80-sample block that ends at render index 2000, a search of 30 samples from that end finds nothing. `remove_render_from_block` measures the same 10-sample delay from the first sample of the block and leaves a residual of at most 1. `subtract_playback_at` places that block with the capture time. The same block read 0.2 s later, still limited to a 30-sample search, is left unchanged. Before `refresh_render_reference`, a block is unchanged even when a playing slot names a matching WAV. After that refresh, the same half-scale copy is removed without writing `status.json`. If an older live slot is listed first and a newer slot's `afplay` is dead, the older slot is chosen. The newest live slot is loaded even when it is not first, and its half-scale copy is removed. `playback_rate` 1.18 is stored on the slot. 3 is not. At 2x, 0.125 s of wall time is file index 4000. A 30-sample search at 1x misses that copy. The same search at 2x removes it. A 22050 Hz mono file is linearly resampled to 16 kHz. A half-scale copy of that signal is removed and the residual is at most 2. A 16 kHz input is unchanged by the resampler. A filtered copy of uncorrelated samples, with weights 0.40, 0.25, and 0.15, peaks at a delay the old 8-sample search skips. Scoring every sample finds that delay, and eight taps leave a residual of at most 1. A callback 0.25 s after an 1280-sample block stamps the block's end, 5000.0, not the callback's wall time 5000.25. A missing clock keeps the callback time. After the slot disappears and the WAV file is deleted, a block 0.2 s later is still subtracted. A block after the 0.6 s tail is left unchanged. A smooth signal with arrivals at delays 20, 21, and 22 has its correlation peak off the first arrival. The taps around that peak leave a residual of at most 1. An 80 ms block that ends 400 samples into the file keeps its leading samples and removes the half-scale copy in the overlap. The residual there is at most 1. A 32-sample exponential smear scaled to rms 175 leaves more than rms 40 with eight taps. The 48-tap removal leaves less than rms 5. A 0.25 s pause inside 1.0 s of wall time leaves the file at 0.75 s. A 30-sample search at the unpaused cursor misses that copy. The paused cursor removes it. While that pause is still open, `refresh_render_reference` keeps `render_cursor` at the stopped file index. After playback resumes, only the unstopped wall time counts. At 16 kHz, 0.50 s is 8000, another 0.25 s stopped stays 8000, and 0.25 s of playback after that is 12000.
13. **Pass/fail:** PASS for this file means the description matches the WAV bytes. It is not a PASS for echo suppression. Echo suppression stays NOT_RUN.
14. **Metrics:** None.
15. **Evidence:** The two test summaries.
16. **Cleanup:** None. The test WAV is not written to the user's state directory.
17. **Known failure modes:** If VoiceBox returns float WAV or a rate below 8000 Hz, `reference` stays absent and playback still proceeds. A stereo file is loaded and not subtracted. A mono file at another rate is resampled to 16 kHz and can be subtracted. Reverberation is not one delay, so it stays in the microphone.
18. **Automation status:** LEVEL 4 for the description. LEVEL 1 is not written for the acoustic test.
19. **Known limitations:** Publishing the path is not acoustic echo cancellation. The running OMP process does not publish `reference` until that session reloads.
20. **Last verified:** 2026-11-13, working tree on `5540a03`. `pytest tests/test_playback_state.py tests/test_mic_capture.py -q` — 24 passed. `pytest tests/ -q` — 91 passed. Speaker echo was not run.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-13 before this slice | `5540a03` | FAIL | No render description on the slot. |
| 2026-11-13 | working tree after `5540a03` | PASS for the description only | Echo suppression NOT_RUN. |
| 2026-11-13 later | same working tree | PASS for the byte match | Controller keeps the PCM only when the header matches. Echo suppression NOT_RUN. |
| 2026-11-13 subtraction | same working tree | PASS for a synthetic delay | Half-scale copy removed. Noise is not. Speaker echo NOT_RUN. |
| 2026-11-13 block origin | same working tree | PASS for the block start | An 80-sample block is not searched from its end. Speaker echo NOT_RUN. |
| 2026-11-13 capture time | same working tree | PASS for the stamp | A block read 0.2 s late stays at its capture index. Speaker echo NOT_RUN. |
| 2026-11-13 slot load | same working tree | PASS for the load on the block | The WAV is subtracted before any status write. Speaker echo NOT_RUN. |
| 2026-11-13 newest slot | same working tree | PASS for slot choice | A dead newer `afplay` is skipped. The newest live WAV is subtracted. Speaker echo NOT_RUN. |
| 2026-11-13 playback rate | same working tree | PASS for 2x | A 1x cursor misses the copy. The 2x cursor removes it. Speaker echo NOT_RUN. |
| 2026-11-13 sample rate | same working tree | PASS for 22050 Hz | Linear resample onto 16 kHz, then the half-scale copy is removed. Speaker echo NOT_RUN. |
| 2026-11-13 filter taps | same working tree | PASS for a 3-tap copy | An 8-sample search step misses it. Every-sample search removes it. Speaker echo NOT_RUN. |
| 2026-11-13 callback time | same working tree | PASS for the ADC end | A callback 0.25 s late stamps the block end. Speaker echo NOT_RUN. |
| 2026-11-13 reverb hold | same working tree | PASS for 0.6 s | The deleted WAV is still subtracted 0.2 s later, and not after the tail. Speaker echo NOT_RUN. |
| 2026-11-13 tap span | same working tree | PASS for a peak after the first arrival | Taps before and after that peak leave a residual of at most 1. Speaker echo NOT_RUN. |
| 2026-11-13 clip start | same working tree | PASS for a partial block | 400 samples of overlap are removed. The earlier samples stay. Speaker echo NOT_RUN. |
| 2026-11-13 smear length | same working tree | PASS for 48 taps | Eight taps leave a 32-sample smear above rms 40. Forty-eight taps leave it under rms 5. Speaker echo NOT_RUN. |
| 2026-11-13 pause clock | same working tree | PASS for a 0.25 s stop | The file cursor stays at 0.75 s after 1.0 s of wall time. Speaker echo NOT_RUN. |
| 2026-11-13 published cursor | same working tree | PASS for the status field | `render_cursor` stays 8000 across a 0.25 s stop and is 12000 after 0.25 s more of playback. Speaker echo NOT_RUN. |
