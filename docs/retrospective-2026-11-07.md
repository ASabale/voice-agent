# Retrospective: Stage 1 OMP Hands-Free Voice Loop (2026-11-07)

## 1. What We Built
- **Goal**: Operate OMP completely hands-free in the room using Handy (STT) + VoiceBox (TTS) — wake by voice, dictate in multi-part chunks where 5-second pauses paste to the draft without pressing Enter, submit by voice, undo/scratch mistakes by voice, and interrupt OMP's spoken output (barge-in).
- **Architecture**: Chose **Direct OMP Session Bridge (`Option A`)** over a separate conversational Broker LLM for Stage 1, using OMP's native extension API (`ctx.ui.getEditorText()`, `ctx.ui.setEditorText()`, `pi.sendUserMessage()`, `ctx.abort()`) in `~/.omp/agent/extensions/voicebox-speech.ts` paired with `~/.local/bin/omp-voice-controller`.

## 2. Bugs Encountered in Live Testing & Root Causes (Lessons Learned)

### Lesson 1 — `openWakeWord` API & macOS Microphone Input Gain
- **What broke**:
  1. `Model(wakeword_models=["hey_jarvis"])` without `vad_threshold` does not attach `oww.vad` (`AttributeError: 'Model' object has no attribute 'vad'`).
  2. macOS microphone input volume was set to `29%` (`osascript -e "get volume settings"`), making Akshay's across-the-room voice peak at `779 / 32768` (`2.3%` full scale), while `openWakeWord`'s `hey_jarvis` model also missed bare `"Jarvis"`.
- **Fix**:
  - Instantiate `from openwakeword.vad import VAD` directly (`vad = VAD()`).
  - Set macOS input volume to `85%` on startup (`osascript -e "set volume input volume 85"`).
  - Run a two-path wake detector in `IDLE`: Path 1 (`openWakeWord` with 3x gain normalization when `rms < 1200`) + Path 2 (`faster-whisper tiny.en` int8 CPU verifier on `0.4s–3.2s` speech bursts with `initial_prompt` vocabulary bias).

### Lesson 2 — Never Rely on Log File Parsing (`handy.log`) for IPC State
- **What broke**: Checking whether Handy was recording by reading the tail of `~/Library/Logs/com.pais.handy/handy.log` failed when `handy.log` rotated/truncated, causing `handy_stop_recording()` to think Handy was idle and skip calling `handy --toggle-transcription`.
- **Fix**:
  - **To start recording**: Run `handy --cancel` (idempotent reset to `IDLE`), sleep `80 ms`, then run `handy --toggle-transcription` (guaranteed `RECORDING`).
  - **To stop & transcribe**: Unconditionally call `handy --toggle-transcription` and poll SQLite `~/Library/Application Support/com.pais.handy/history.db` (`SELECT id, COALESCE(post_processed_text, transcription_text, '') FROM transcription_history ORDER BY id DESC LIMIT 1`).

### Lesson 3 — Handy In-Memory Settings Cache (`mute_while_recording`, `selected_language`, `paste_method`)
- **What broke**:
  1. Editing `~/Library/Application Support/com.pais.handy/settings_store.json` on disk does **not** hot-reload into a running Handy process; Handy only reads `settings_store.json` on launch.
  2. Because `mute_while_recording: true` was cached in Handy's RAM, Handy muted macOS system output (`Mute applied`) ~50–600 ms after `--toggle-transcription`, silencing our audio cues.
  3. Because `selected_language: "auto"` was cached, Handy transcribed Akshay saying `"Hey Jarvis stop"` in Devanagari (`"हे जार्बेस स्टॉप"`).
  4. Because `paste_method: "ctrl_v"` was cached, Handy still executed `Cmd+V` (`225 ms`) before `/transcript` arrived.
- **Fix**:
  - Persist `mute_while_recording: false` and `selected_language: "en"` in `settings_store.json` AND actively unmute macOS output (`set volume without output muted`) at `+150 ms` and `+800 ms` after toggling Handy.
  - Wait `260 ms` after Handy finishes transcribing so Handy's native `Cmd+V` completes, then run `deduplicateHandyPaste(currentDraft, rawTranscript)` inside `voicebox-speech.ts` before applying command stripping or `setEditorText()`.

### Lesson 4 — VoiceBox TTS Speed & Smoothness (`Qwen3-TTS-12Hz-0.6B-Base-bf16`)
- **What broke**: Generating and playing one sentence at a time via `POST /generate` + `200 ms` `/history/{id}` polling had an RTF of `0.99x` on short sentences (`35 chars` took `2.54s` for `2.56s` of audio), causing audible gaps between sentences.
- **Fix**:
  - Switch to `POST /generate/stream` (direct WAV bytes in one HTTP call, zero polling, zero SQLite history churn).
  - Send the **first sentence** immediately (`45–90 chars`) for low time-to-first-audio, then coalesce subsequent sentences into `160–220 char` chunks where RTF drops to `0.84x` (`13.1s` generation for `15.7s` audio).
  - Play via `afplay -r 1.18 -q 1` (configurable via `/voice speed <rate>`).

### Lesson 5 — Preventing Cloned-Voice TTS Self-Triggering while Keeping Barge-In
- **What broke**: Because VoiceBox speaks in Akshay's own cloned voice, speaking `"Hey Jarvis"` or `"send prompt"` in an assistant reply could trigger the mic.
- **Fix (3-layer defense)**:
  1. `forSpeech()` scrubs `"Hey Jarvis"`, `"Jarvis"`, `"send prompt/that/it"`, `"scratch/undo that"`, and `"clear draft"` from outbound TTS text before synthesis.
  2. `voicebox-speech.ts` writes `~/.local/state/omp-voice/tts-playing.json` (`playing: true/false`, `pid`, `ended_at` + `450 ms` reverb guard). While `playing` is true, `omp-voice-controller` disables the Whisper short-utterance verifier and disables the 3x mic gain boost while keeping `openWakeWord` active at threshold `0.50` for deliberate Barge-In.
  3. On Barge-In, `/barge-in` kills `afplay`, flushes the TTS queue, and calls `ctx.abort()` if OMP is mid-turn.

### Lesson 6 — CoreAudio Headphone Hotplug in PortAudio (`sounddevice`)
- **What broke**: PortAudio (`sounddevice.InputStream`) binds to the default input device at stream creation and does not switch when Bluetooth headphones/AirPods connect mid-session.
- **Fix**: Poll CoreAudio `kAudioHardwarePropertyDefaultInputDevice` (`0x64496E20`) every `2.0s` via `ctypes`; when the device ID changes, call `sd._terminate()` / `sd._initialize()` and reopen the stream on the new default mic.

### Lesson 7 — Global `Escape` / Manual `fn` Key Collisions & Multi-Session Port Ownership
- **What broke**:
  1. Handy binds `Escape` globally to `cancel` (`bindings.cancel = "escape"`). When Akshay pressed `Escape` inside OMP while `DICTATING` was active, Handy silently cancelled its recording; 5 seconds later, `handy_stop_recording()` called `--toggle-transcription`, which started a brand-new recording instead of flushing the spoken text.
  2. Playing `marimba_start.wav` with `wait=True` (`~1.2s`) before calling `handy_start_recording()` clipped the first words spoken right after `"Hey Jarvis"`.
  3. Starting a new OMP session while an older OMP window was still open left `127.0.0.1:17494` bound to the older session (`EADDRINUSE`).
- **Fix**:
  - **Local Whisper Fallback (`transcribe_local_fallback`)**: Buffer speech frames (`dict_speech_frames`) during `DICTATING`. If Handy produces no new `history.db` row within `2.2s` of stop (because `Escape` cancelled Handy or Handy was closed), transcribe the buffered PCM directly via `faster-whisper tiny.en` so speech is never lost.
  - **Manual `fn` Sync**: Poll `latest_history_row()` inside the `DICTATING` loop so manual `fn` completions are dispatched immediately.
  - **Concurrent Wake Chime**: Play `SOUND_WAKE` with `wait=False` so Handy opens the mic immediately.
  - **Port Takeover (`POST /takeover`)**: On `EADDRINUSE`, the new OMP session sends `POST http://127.0.0.1:17494/takeover` so the old session closes its server and the new session binds `:17494`.

### Lesson 8 — On-Demand Dual-Channel Voice Summarization (`voice-brief` & `/voice human`)
- **What broke**: Reading raw technical output (markdown tables, file paths, timestamps, PIDs, shell commands) out loud via TTS is hard to follow eyes-free, but forcing a `**Voice:**` header globally across all sessions clutters normal keyboard-driven sessions.
- **Fix**:
  - Keep `humanizeMode = false` by default in `voicebox-speech.ts`; enable per-session on demand via `/voice human` (`on`/`off`) or by invoking the `voice-brief` skill (`~/.omp/agent/managed-skills/voice-brief/SKILL.md`).
  - When a reply includes `**Voice:** <summary>` (or `<voice>...</voice>`), `forSpeech()` extracts and speaks **only** that conversational summary while leaving all tables/code/paths on screen.
  - Even when `humanizeMode` is off, `forSpeech()` strips markdown tables, code blocks, long file paths (`/Users/name/.../foo.ts` → `foo.ts`), ISO/log timestamps, UUIDs, and `(pid ...)` metadata before synthesis.

