# Select local wake-word and VAD stack on macOS arm64

Type: research
Status: open
Blocked by:

## Question

What is already installed or fastest to install on this M5 Pro Mac (Python / Node / Rust) for:
1. Low-CPU local **Wake Word** detection (`"Hey Jarvis"`) on a 16 kHz mono mic stream (e.g. `openwakeword` with `hey_jarvis` ONNX model vs `pvporcupine` vs lightweight phrase spotter).
2. 5-second silence **VAD** detection on the same audio stream without conflicting with Handy's CoreAudio microphone stream when Handy records.

Check local Python/uv/conda environments and verify whether macOS CoreAudio allows both the wake-word/VAD tap and Handy to read the MacBook Pro Microphone simultaneously.
