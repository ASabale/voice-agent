# VA-INT-AUTO-005 — No safe LEVEL 4 input

1. **ID:** VA-INT-AUTO-005
2. **Checked:** 2026-11-13 20:09 UTC.
3. **Level:** Not run. LEVEL 4 needs an input the live controller is not already using.
4. **Devices:** `sounddevice` lists input 0 `MacBook Pro Microphone` and output 1 `MacBook Pro Speakers`. `ffmpeg` AVFoundation audio lists only `MacBook Pro Microphone`. No BlackHole, Loopback, or aggregate device. `SwitchAudioSource` is not installed.
5. **Why speaker playback is not a test:** Pid 64238 already owns that microphone. A played wake phrase is a real wake. `silence_speech` then posts `/barge-in` to every bridge and calls `kill_tts_clips`. Pid 16590 is `agentBusy` on port 62283. Do not play a wake into this mic.
6. **Why the input cannot be switched:** The controller pins the device when the stream opens. Changing the default input, or restarting pid 64238, takes the user's microphone. Do not do either from an iteration.
7. **What still works:** LEVEL 3 on an isolated `omp` pty, posting only to that process's bridge. See VA-INT-AUTO-003 and VA-INT-AUTO-004.
8. **What LEVEL 4 needs:** A second input device that is not the default, and a controller started against that device while pid 64238 stays on the MacBook mic. That controller does not exist. Installing one is a user decision because it changes the audio setup.
9. **Not a substitute:** `omp-voice-controller inject` calls `dispatch_transcript`, which follows the live delivery target. `barge-in` calls `bridge_request("/barge-in")` with no port. Do not run either while pid 16590 is up. A later isolated post must go through `scripts/isolated_session.py`, which refuses that pid's port.
