# How should the Voice Controller drive Handy for 5-second pause chunking and Send Phrase interception?

Type: research
Status: resolved
Blocked by:

## Question

What is the cleanest, lowest-latency way on this Mac to integrate with Handy v0.10.0 (`/Applications/Handy.app`) so that:
1. A local Wake Word (`"Hey Jarvis"`) starts capture.
2. A 5-second silence pause flushes and transcribes the spoken chunk and pastes it into the Draft without pressing Enter, while continuing to listen for the next chunk.
3. Spoken command phrases (`"send prompt"`, `"pause listening"`, `"cancel that"`) are intercepted so `"send prompt"` strips the phrase and triggers `Enter` (`Return`), rather than pasting literal `"send prompt"` into OMP.

Specifically compare:
- **Option A — Driving the running Handy GUI instance**: Using `handy --toggle-transcription` / `handy --cancel` + Handy's `paste_method: "external_script"` (`external_script_path` in `~/Library/Application Support/com.pais.handy/settings_store.json`) and watching `~/Library/Logs/com.pais.handy/handy.log` or mic VAD for 5s silence.
- **Option B — Using Handy's headless CLI**: Capturing 16 kHz mono WAV chunks in our own lightweight mic loop (which already has the mic open for Wake Word + 5s VAD pause detection) and calling `/Applications/Handy.app/Contents/MacOS/handy --transcribe-file <wav> --json` (or finding whether `--transcribe-file` reloads the model on every call vs keeping it warm).

Verify how Handy's `external_script_path` (`src/transcription_hook.rs`) works from the binary/logs and measure or verify `--transcribe-file` latency vs `--toggle-transcription`.

## Answer

Drive the **running Handy GUI instance** via `handy --toggle-transcription` (66 ms start, 170 ms Metal transcription on warm `Qwen3-ASR-1.7B-Q8_0.gguf`), never `--transcribe-file` (which cold-starts a worker in 3.9s). Handy does not auto-stop on 5s silence, so our Voice Controller monitors mic VAD and calls `handy --toggle-transcription` after 5s of silence (then re-toggles to stay in `Dictating` until `"send prompt"` or `"pause listening"`). Intercept transcripts via `history.db` / `external_script_path` so command phrases (`"send prompt"`, `"pause listening"`, `"cancel that"`) are stripped before touching the Draft. Detail: [research/01-handy-chunking-and-hook-seam.md](../research/01-handy-chunking-and-hook-seam.md).
