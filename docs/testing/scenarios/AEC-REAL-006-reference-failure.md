# AEC-REAL-006 — A real render reference fails mid-playback on the live controller

1. **ID:** AEC-REAL-006
2. **Name:** Playback reference failure during physical playback
3. **Objective:** With the production controller (the one that owns the microphone) running against real speaker output, induce the crashed-writer shape — the slot announces a clip whose file on disk is only half written — and prove the canceller disconnects safely, stays observable, never wakes on the uncancelled echo, and reconnects when the next real clip arrives.
4. **Failure investigated:** The first induction attempt truncated the playing file in place and the reference stayed connected. That is not a bug: `refresh_render_reference` only re-reads when the slot's declared `(wav, frames, rate, channels)` key changes, and `parse_wav_pcm` derives the frame count from the bytes actually present. A key-unchanged truncation is invisible by design (the VA-AEC-008 design note: "deleting a loaded clip does NOT disconnect the canceller"). The real failure mode is a new key pointing at a half-written file.
5. **Preconditions:** VoiceBox listener answering on :17493, the live controller running and owning the microphone, Handy and Whisper installed. The probe opens no microphone and signals no protected process.
6. **Required application versions:** `aec-audio-processing==1.0.0`, openwakeword, faster-whisper, Handy binary (all the live controller's own dependencies).
7. **Required services:** VoiceBox (:17493), the live controller, the OMP bridge of the probe's own isolated session.
8. **Hardware requirements:** MacBook speakers and microphone in the real room.
9. **Setup:** `scripts/run_reference_failure_live.py` starts an isolated `omp -p` session (its pid/bridge recorded in the evidence file), posts a three-sentence prompt so a real VoiceBox clip plays, grabs the clip bytes at playback start (the extension unlinks the wav when afplay exits), verifies afplay is still alive, then rewrites the session's playback slot so `reference.wav` points at a truncated copy (header announces the full size, only half the PCM on disk). The reconnect leg only counts when the slot carries a *new* clip — neither the original nor the partial — and samples `render_connected` while that clip is playing.
10. **Execution:**
    ```sh
    ~/.local/share/omp-voice/venv/bin/python scripts/run_reference_failure_live.py
    ```
11. **Fixtures:** none — the clips are genuine VoiceBox generations of the probe session's replies.
12. **Expected behavior:** within ~1 s of the slot change, `status.json` reports `render_connected: false`, the controller logs "render reference unavailable", the mic stays IDLE, no wake fires even though the echo now passes the canceller uncancelled, no exception escapes, and a second reply reconnects the reference and cancels again.
13. **Pass/fail:** PASS = connected before, disconnected after (latency measured), "render reference unavailable" logged in the window, zero "Wake triggered" lines, mic IDLE throughout, controller process alive, second playback reconnects with `render_connected: true`.
14. **Metrics:** disconnect latency (s), `aec_echo_db` before/after reconnect, barge-hold events during the failure window, wake count.
15. **Evidence:** see the History table; machine-readable copy in `.local/voice-agent/runs/AEC-REAL-006-LIVE.json`.
16. **Cleanup:** the truncated copy is deleted by the probe; the isolated session is terminated; the slot is overwritten by the next playback as usual.
17. **Known failure modes:** the reply clip can be so short that afplay exits and the extension unlinks the wav before induction (run 7 hit this; the probe now reads the bytes at detection and refuses to induce after afplay dies); the reconnect sample must be taken while the second clip is still playing because the tail guard clears the reference 0.6 s after afplay exits.
18. **Automation status:** LEVEL 4 (real speaker output, real microphone, induced failure, no human voice required).
19. **Known limitations:** the failure is induced by the probe rewriting the slot, not by an actual VoiceBox writer crash; the barge gate does fire on the uncancelled echo (holds and Whisper-classified "not stop") — that is accepted behavior, identical to the VA-AEC-008 fixture observation.
20. **Last verified:** 2026-11-14.

## Design notes

- Two truncations were tried before the working one; the distinction is the crux of the scenario: a truncation that does not change the declared key is invisible (the loaded PCM stays), and only a key change forces the re-read that can fail. Any future "reference disappeared" alarm must therefore be about a file that fails to parse against its slot, not about a file vanishing behind a stable key.
- While the reference is dead, echo reaches the barge gate raw: holds fire (rms 394–1165 against floors ~100), Whisper hears unrelated sentences and classifies them as not-stop, and playback is never wrongly stopped. No wake. This matches the fixture result in VA-AEC-008.

## History

| When | Revision | Result | Note |
|---|---|---|---|
| 2026-11-14 | in-place truncation, key unchanged | FAIL (design, not bug) | Reference stayed connected; PCM cache survives a stable key. |
| 2026-11-14 | slot rewritten to point at a half-written file | see evidence JSON | Disconnect observed, no wake, controller alive; reconnect sampled too late. |
| 2026-11-14 | log window fixed, reconnect sampled during playback | FAIL (harness) | Disconnect leg real: `render_connected` false 0.8 s after the slot rewrite, "render reference unavailable" logged, zero wakes, mic IDLE, controller alive. Reconnect leg invalid: `wait_playing` matched the still-open first slot, so the second clip's reconnect was never actually observed. |
| 2026-11-14 | reconnect gated on a new `reference.wav` in the probe session's own slot | PASS | Disconnect leg real as before; reconnect confirmed from the probe session's own second clip (`render reference connected frames=224640` in the restart log at 17:51:41, `render_connected: true`, `aec_echo_db −21.7`). Label blemish: the gate still matched the partial slot as the "second" clip. |
| 2026-11-14 | short clip raced: afplay exited and the extension unlinked the wav before the probe read it | FAIL (harness) | `FileNotFoundError` on the original clip. Probe now reads the bytes at playback detection and refuses to induce once afplay is dead. |
| 2026-11-14 | hardened probe (bytes read at detection, afplay liveness guard, partial excluded from the reconnect gate) | PASS 2026-11-14 22:59 UTC | pid 76655, clip 238080 frames (9.92 s): connected before (`aec_echo_db −2.6`, 13 blocks, IDLE); slot rewrote to a half-written file (476204 announced vs 238124 on disk) at 17:58:48 local; `render_connected: false` 1.2 s later with "render reference unavailable" logged; zero "Wake triggered" lines; one echo barge hold rms 416 → Whisper "not stop", mic IDLE; second clip `omp-vb-76655-2.wav` reconnected (`render_connected: true`, `aec_echo_db −2.7`, 3 blocks); controller 38298 alive. |
