# Voice agent test catalogue

Commands assume the repository root. The unit interpreter is `~/.local/share/omp-voice/venv/bin/python`. Hardware rows are not run from this index.

| ID | Validates | Level | Prerequisites | Command | Status | Limitations |
|---|---|---|---|---|---|---|
| VA-OMP-001 | Status reports the session registry port and does not treat a missing :17494 listener as a down bridge | Unit LEVEL 4; live check LEVEL 2 | Venv. Live check needs one registry file whose pid is alive | `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_delivery.py -q -k "status_targets or probe_"` | PASS 2026-11-13 | Does not submit a draft. See `docs/testing/scenarios/VA-OMP-001-session-bridge-status.md` |
| VA-PLAY-001 | One session cannot clear another's playback, and a dead player is not speaking | Unit LEVEL 4 | Venv and Node. No audio | `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_playback_state.py -q` and `node --experimental-strip-types --test tests/playback-state.test.ts` | PASS 2026-11-13 | Not a speaker test. The live processes still run the old code until restart. See `docs/testing/scenarios/VA-PLAY-001-playback-ownership.md` |
| VA-TTS-001 | A chunk is spoken once per reply, a substring is not treated as already spoken, and a new message id can repeat a sentence | Unit LEVEL 4 | Node. No VoiceBox | `node --experimental-strip-types --test tests/speech-queue.test.ts` | PASS 2026-11-13 | Does not play audio. The running OMP session keeps the old extension until reload. See `docs/testing/scenarios/VA-TTS-001-speak-once.md` |
| VA-TTS-002 | A chunk VoiceBox never returned is not treated as spoken, and a later chunk is not replayed | Unit LEVEL 4 | Node. No VoiceBox | `node --experimental-strip-types --test tests/speech-queue.test.ts` | PASS 2026-11-13 | Does not play audio. The running extension keeps the old queue until reload. See `docs/testing/scenarios/VA-TTS-002-unspoken-chunk.md` |
| VA-TTS-003 | Exit code 1 or a spawn error is not heard. A kill signal is heard | Unit LEVEL 4 | Node. No afplay | `node --experimental-strip-types --test tests/speech-queue.test.ts` | PASS 2026-11-13 | Does not spawn afplay. The running extension keeps the old completion until reload. See `docs/testing/scenarios/VA-TTS-003-player-exit.md` |
| VA-LOG-002 | `speech.log` records the length and the reason, not the sentence, unless `OMP_VOICE_LOG_TEXT=1` | Unit LEVEL 4 | Node. No VoiceBox | `node --experimental-strip-types --test tests/speech-queue.test.ts` | PASS 2026-11-13 | Does not change `controller.log`. The running extension keeps the old logger until reload. See `docs/testing/scenarios/VA-LOG-002-speech-log.md` |
| VA-LOG-003 | A log over 1 MiB becomes one `.1` backup, and a second rotation replaces that backup | Unit LEVEL 4 | Venv and Node. No services | `pytest tests/test_speech_tier.py -q` and `node --experimental-strip-types --test tests/speech-queue.test.ts` | PASS 2026-11-13 | Temp files only. The live logs were not renamed. See `docs/testing/scenarios/VA-LOG-003-log-rotation.md` |
| VA-AUD-002 | A full mic queue drops the oldest block and the loss is counted without storing samples | Unit LEVEL 4 | Venv. No microphone | `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_mic_capture.py -q` | PASS 2026-11-13 | Does not open the microphone. The running controller keeps the old callback until restart. See `docs/testing/scenarios/VA-AUD-002-dropped-frames.md` |
| VA-LOG-001 | A down VoiceBox is retried after 5 s, not on every mic frame, and the Handy flag stays on the Strata tier | Unit LEVEL 4 | Venv. No VoiceBox | `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_speech_tier.py -q` | PASS 2026-11-13 | Does not start VoiceBox or Handy. The running controllers keep the old check until restart. See `docs/testing/scenarios/VA-LOG-001-voicebox-health.md` |
| VA-IDLE-001 | A busy Whisper keeps the newest idle clip and queues it when the in-flight job finishes | Unit LEVEL 4 | Venv. No microphone | `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_idle_whisper.py -q` | PASS 2026-11-13 | Does not run Whisper. The running controller still drops the clip until restart. See `docs/testing/scenarios/VA-IDLE-001-busy-whisper.md` |
| VA-BARGE-001 | A full Whisper queue keeps the newest barge clip and does not resume playback | Unit LEVEL 4 | Venv. No microphone | `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_idle_whisper.py -q` | PASS 2026-11-13 | Does not play audio. The running controller still drops the clip until restart. See `docs/testing/scenarios/VA-BARGE-001-busy-barge.md` |
| VA-AUD-001 | A SIGSTOP pause does not advance the subtraction index or the published `render_cursor`. Speaker echo is not run | Unit LEVEL 4 for that clock. Hardware not run | Venv. No microphone | `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_playback_state.py tests/test_mic_capture.py -q` | PASS for the pause clock, NOT_RUN for speakers | See `docs/testing/scenarios/VA-AUD-001-render-reference.md` |
| VA-OMP-002 | `choose_delivery` routes a focused text control and the newest session | Unit LEVEL 4 | Venv | `pytest tests/test_delivery.py -q -k "focused or non_text or paste or list_role"` | PASS 2026-11-13 (included in the 67) | Not a spoken end-to-end delivery test |
| A–J | Wake, commands, barge-in, partials on the real mic | Hardware | Controller, mic, and the checkpoint procedure | Spoken rows in `HANDY-SCENARIO-CHECKPOINT.md` | PASS except G10 BLOCKED | Do not rerun a pass. G10 must not be tested until the user restarts that session |

Full unit suite, no microphone:

```sh
~/.local/share/omp-voice/venv/bin/python -m pytest tests/ -q
```

2026-11-13 result: 97 passed. Node files in CI: 55 passed. The earlier 54-pass note was before the player-exit test.

Machine-specific run notes belong in `.local/voice-agent/` (gitignored). Do not store raw transcripts there.
