# Verify Handy CLI vs direct WAV capture for 5-second pause chunking

Type: research
Status: open
Blocked by:

## Question

We need `Active Dictation` to cut a **Chunk** after 5 seconds of silence, transcribe it with Handy (`Qwen3-ASR-1.7B-Q8_0.gguf`), and immediately continue listening for the next **Chunk** until the **Send Phrase** (`"send prompt"`) or **Pause Phrase** (`"pause listening"`).

Compare the two concrete integration mechanisms available in `/Applications/Handy.app/Contents/MacOS/handy` on this Mac:
1. **Driving the running Handy app via `--toggle-transcription` + `external_script_path`**:
   - If our sidecar monitors mic VAD and runs `handy --toggle-transcription` after 5s of silence, how does Handy behave when toggled off (to transcribe) and immediately toggled back on for the next chunk?
   - How does `external_script_path` (`paste_method: "external_script"`) receive the transcribed text (stdin vs `$1` vs env var), and does it let our script strip `"send prompt"` and decide whether to paste without `Enter` vs paste + `Enter`?
2. **Continuous mic capture in our controller + `handy --transcribe-file <wav> --json`**:
   - Does `handy --transcribe-file <wav> --json` load the 1.7B model cold on every CLI call (slow, extra 3 GB RAM), or does it reuse the running instance?

Inspect the `/Applications/Handy.app/Contents/MacOS/handy` binary strings/symbols and test non-destructively to surface the exact contract and latency of both paths.
