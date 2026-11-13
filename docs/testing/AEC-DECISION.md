# AEC decision

Checked 2026-11-13. This is the architecture choice. It is not an acoustic measurement and it does not pass VA-INT-001.

The capture and playback map lives in `docs/VOICE-AGENT-ARCHITECTURE.md`. This file does not repeat it.

## What runs today

`handle_captured_frame` calls `cancel_playback_echo` before VAD and wake. That uses WebRTC when the pinned package imports, and `apply_render_subtraction` only when the import fails. The process that is already running keeps the previous call until it restarts. The reference is the WAV `afplay` was given. The extension writes that path, the PCM header, `started_at`, `afplay_pid`, and `playback_rate` on the session slot. The controller averages a multi-channel file onto mono with `downmix_to_mono`, resamples that to 16 kHz with linear interpolation, keeps it for 0.6 s after the slot ends, and places each 1280-sample block with `render_cursor`. Stereo was previously left unaligned and skipped; it now shares the same mono reference. `afplay` is a different process, so the cursor is wall-clock time times `playback_rate`, minus time spent in SIGSTOP. It is not the speaker's sample clock.

`remove_render_from_block` searches one delay from 0 to 2400 samples (150 ms) and keeps it only when normalized correlation is at least 0.75. It then fits 48 taps around that delay. Those taps are samples -23 through +24, which is 3 ms at 16 kHz. Each coefficient is capped, and the coefficients together are capped. A miss leaves the microphone block unchanged.

White noise, one 1280-sample block, seed 1, measured in this process:

| Planted path | Delay found | RMS in | RMS out | ERLE |
|---|---|---|---|---|
| One copy at 0, 20 ms, or 120 ms | The planted delay | 2329–2802 | 0.1–0.4 | Rounding only |
| 20 ms at gain 0.5 and 40 ms at gain 0.35 | 320 samples | 2865.3 | 1616.8 | 5.0 dB |
| 200 ms, past the search | None | 2294.5 | 2294.5 | 0 dB, block unchanged |

A single bulk delay inside 150 ms is removed. A second arrival 20 ms later is mostly still there. A delay the search does not cover is not touched. That is not a room model. Laptop playback into the laptop microphone is more than one delay. VA-AUD-001 remains a clock and reference test, not echo cancellation.

## Choice

Use WebRTC's desktop echo canceller in the controller, in front of VAD, and keep `afplay`.

Pin `aec-audio-processing==1.0.0`, wheel `aec_audio_processing-1.0.0-cp312-cp312-macosx_15_0_arm64`. The controller venv is CPython 3.12. The wheel's `audio_processing_module.cpp` sets `echo_canceller.enabled` and `mobile_mode = false` on `webrtc::AudioProcessingBuilder`, and it links `libwebrtc-audio-processing-2`. `process_reverse_stream` takes the render. `process_stream` takes the microphone. `GetFrameSize` is 10 ms: 160 samples at 16 kHz. One controller block is eight of those frames, in order.

Construct it with echo cancellation on and noise suppression, gain control, and the wrapper VAD off. The barge path uses RMS. A gain controller would move those thresholds. Silero stays the VAD.

Feed the reverse stream from the same 16 kHz render cursor the subtractor already uses. Call `set_stream_format` before `process_reverse_stream`: the wrapper passes the capture output config as the reverse output config. `set_stream_delay` is only the starting hint. The canceller estimates delay, but a hint that is wrong by more than its search window is a failed integration. Do not run the 48-tap subtractor on the same block. The two would each remove part of the near-end speech.

`aec-audio-processing==1.0.1` is not the pin. Its wheels are Windows only. Installing 1.0.1 here would compile from source.

## Rejected

**A longer least-squares fit on each block.** The 5.0 dB two-path result is the current filter doing what it was built to do. Widening it to a room length, once per 80 ms block, still has no double-talk state. A loud user and the speakers in the same block get treated as one echo path.

**VoiceProcessingIO as the first playback path.** macOS echo cancellation runs only when capture and playback share that audio unit. `afplay` does not. Using it means the controller plays the WAV and the extension stops spawning `afplay`. Pause is SIGSTOP today, and stop kills that `afplay`. Both would have to move. The unit also applies its own level control, which fights the RMS barge gate. It stays the fallback if the desktop canceller cannot hold a MacBook speaker path. It is not this step.

**SpeexDSP.** PyPI `speexdsp` 0.1.1 has no macOS wheel, and it is the older MDF canceller.

**A virtual loopback device.** No second input exists. Controller pid 64238 already holds the MacBook Pro Microphone. A driver is not required for a file-based render reference, and none is installed.

## Synthetic result

`aec-audio-processing==1.0.0` is installed in the controller venv. `tests/test_echo_control.py` plays `sentence-stop-say.wav` as the render and a delayed copy as the microphone. No microphone is opened.

On the last second of a 4 second loop, one 20 ms copy at gain 0.6 was removed by at least 20 dB. Two copies, 20 ms at gain 0.5 and 40 ms at gain 0.35, were removed by at least 12 dB. The old fit managed 5.0 dB on that shape of second arrival. `good-morning-say.wav` played against silence, and against the other sentence, kept more than half its tail energy. The same near-end mixed with the 20 ms echo also kept more than 40 percent of its tail energy. White noise is not the test. With a loud unrelated white-noise render, the canceller gated the near-end down to the same floor as a pure echo.

A synthetic 24 kHz stereo clip (left full speech, right half amplitude) downmixes to the averaged 16 kHz reference and the planted echo through `cancel_playback_echo` lost at least 12 dB of tail energy. That is `VA-AEC-002`. The average is a channel sum assumption, not a measured room response.

The delay hint is 0. Speech delays of 20 ms, 40 ms, and 120 ms still cleared about 40 dB with that hint. A new clip builds a new canceller. Eight 160-sample frames are processed reverse-then-capture and joined in order.

The extension default `afplay -r` is 1.18. Half a second of wall clock then ends at file sample 9440 on the 16 kHz grid, and the 1280-sample reference is samples 8160 through 9439. A 0.25 s pause inside that half second ends at sample 4720, so the reference is samples 3440 through 4719. `cancel_playback_echo` sends that slice. A rate of 1.0 is not assumed.

## Not claimed

No room ERLE. The energy checks are not an intelligibility score. Pid 64238 was not restarted, so the live microphone still takes the old path. Physical playback into that microphone stays blocked while that process owns it.

## Next build

When the live controller can be restarted without taking the user's session, the new path is what it should run. The speaker-to-microphone trial stays blocked until pid 64238 is idle and a test lock owns the device. Do not open the microphone beside it.
