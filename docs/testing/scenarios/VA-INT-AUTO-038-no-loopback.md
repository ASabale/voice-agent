# VA-INT-AUTO-038 — No second audio input

1. **ID:** VA-INT-AUTO-038
2. **Checked:** 2026-11-13 20:58 UTC.
3. **Level:** Discovery only. No fixture was played. This is not LEVEL 4 and not VA-INT-001.
4. **Devices:** `sounddevice` default is input 0 and output 1. Input 0 is `MacBook Pro Microphone` (1 channel). Output 1 is `MacBook Pro Speakers` (2 channels). `ffmpeg` AVFoundation lists the same microphone and no other audio input. `system_profiler SPAudioDataType` marks that microphone as the default input and those speakers as the default output. Sample rate 48000. No BlackHole, Loopback, aggregate, or second input.
5. **Installed driver:** `/Library/Audio/Plug-Ins/HAL/ParrotAudioPlugin.driver` is Apple `com.apple.audio.ParrotAudioPlugin`. It does not appear as a CoreAudio device. `SwitchAudioSource` is not installed. Nothing was installed and `coreaudiod` was not restarted.
6. **Controller stream:** `run_daemon` opens `sounddevice.InputStream` with no device argument, so the stream is the default input. The log line is `Opening microphone input stream`. That default is the MacBook microphone, already owned by controller pid 64238.
7. **Not run:** The wake, dictation, and stop fixtures were not played into that microphone. A second controller was not started. Handy was not toggled. No isolated OMP session was started for this run. `stop_playback` and `resume_tts_clips` were not called.
8. **Why:** Playing the wake into the only input would be a real wake of pid 64238, and that controller posts to the user's OMP session. The session on pid 16590 stays untouched.
9. **VA-INT-001:** Not complete. The path wake → Handy → isolated draft → VoiceBox → spoken stop → second wake has not been demonstrated on a real input.
