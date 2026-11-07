# Research 01: Handy v0.10.0 Chunking, CLI, and Hook Seam

Ticket: [issues/01-handy-chunking-and-hook-seam.md](../issues/01-handy-chunking-and-hook-seam.md)

## 1. Verified Handy v0.10.0 Capabilities on this Mac

1. **CLI IPC (`--toggle-transcription` / `--cancel`)**:
   - `/Applications/Handy.app/Contents/MacOS/handy --toggle-transcription` sends a `single-instance` message to the running Handy process (`pid 5561`).
   - From `~/Library/Logs/com.pais.handy/handy.log`, starting recording takes **66 ms** (`Microphone stream initialized in 66.3ms`) and stopping + transcribing a 6.6s chunk on Metal (`Qwen3-ASR-1.7B-Q8_0.gguf` on `MTL0`) takes **170 ms** (~39x real-time) when the model worker is warm, followed by **232 ms** for `Cmd+V` paste.
   - By contrast, headless `handy --transcribe-file <wav> --json` spawns a fresh `transcribe_worker` every time (516 ms model load + 3.9s wall time). **Verdict: Never use `--transcribe-file` in the live loop; always drive the warm running Handy instance or keep the worker warm.**
2. **Model Unload Timeout (`model_unload_timeout`)**:
   - Currently set to `"min2"` (unloads after 120s idle).
   - Binary enum `ModelUnloadTimeout` supports: `"never"`, `"immediately"`, `"sec15"`, `"min2"`, `"min5"`, `"min10"`, `"min15"`, `"hour1"`. Setting `"hour1"` or `"never"` keeps `Qwen3-ASR-1.7B-Q8_0.gguf` (~1.8 GB) warm during an active session.
3. **Output & Interception Seams**:
   - **SQLite History (`~/Library/Application Support/com.pais.handy/history.db`)**: Every completed transcription immediately writes a row to `transcription_history (id, file_name, timestamp, title, transcription_text, ...)` *before* pasting (`Saved history entry with id 71`).
   - **Paste Method (`paste_method` in `settings_store.json`)**:
     - Currently `"ctrl_v"` (writes to clipboard if needed, presses `Cmd+V` via `enigo`, then restores clipboard).
     - Also supports `"external_script"` with `external_script_path` (`src/clipboard.rs`: `Failed to execute external script`) and `"none"` (`PasteMethod::None selected - skipping paste action`), plus `clipboard_handling: "copy_to_clipboard"`.

## 2. How 5-Second Pause Chunking + Send Phrase Interception Works Best

Handy's internal `long_form_chunking: true` only chunks audio *after* `TranscribeAction::stop` is called (to keep accuracy on >30s recordings); it does **not** auto-stop recording or paste mid-recording on a 5-second pause.

Therefore, to get:
- **Wake Word (`"Hey Jarvis"`)** → start listening
- **5-second silence pause** → transcribe spoken section & append to OMP input box *without* Enter, and keep listening for next section
- **Send Phrase (`"send prompt"`)** → strip `"send prompt"` and press Enter

The cleanest architecture is:
1. **Voice Controller owns the lightweight 16 kHz mic tap** (for Wake Word detection + Silero/energy VAD pause timer).
2. When `"Hey Jarvis"` is detected:
   - Play Wake chime.
   - Call `handy --toggle-transcription` to start Handy recording (also Set `mute_while_recording: false` in Handy settings so Handy doesn't mute system audio cues).
3. While in `Dictating`, the Voice Controller watches mic energy/VAD:
   - Once speech has occurred in the current chunk and **5.0 seconds of continuous silence** elapses (or the user speaks a short stop/send phrase followed by a brief 1.2s pause), the controller calls `handy --toggle-transcription` to flush the chunk.
4. **Intercepting the Transcript (No literal `"send prompt"` pasted)**:
   - Instead of letting Handy blindly press `Cmd+V` into whatever window is focused, set Handy's `paste_method` to `"external_script"` pointing to our controller hook script (or read the new row from `history.db` with `paste_method: "none"`).
   - The hook script receives the transcribed text, checks for trailing/standalone command phrases (`"send prompt"`, `"pause listening"`, `"cancel that"`):
     - Normal chunk → appends text (plus trailing space) directly into the OMP editor Draft (`ctx.ui.pasteToEditor` or terminal paste), plays the Chunk tick sound, and immediately calls `handy --toggle-transcription` again to continue the `Dictating` session!
     - Ends with `"send prompt"` → strips `"send prompt"`, appends any preceding text to the OMP Draft, submits the OMP prompt (`Enter`), plays the Send chime, and transitions the Voice Controller back to `Idle` (does not restart Handy).
     - Ends with `"pause listening"` → strips `"pause listening"`, appends any preceding text to the OMP Draft (no Enter), plays the Pause tone, and returns to `Idle`.
     - `"cancel that"` → discards the chunk, plays Cancel tone, and returns to `Idle`.
