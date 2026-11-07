# Wire Barge-in to voicebox-speech.ts playback

Type: task
Status: open
Blocked by: 02

## Question

Update `~/.omp/agent/extensions/voicebox-speech.ts` (and/or the voice controller) so that:
1. While VoiceBox TTS is playing (`afplay`), the controller knows playback is active (or kills `afplay` on **Wake Word**) and ignores normal speech so `omp` never transcribes its own voice.
2. Speaking the **Wake Word** (`"Hey Jarvis"`) while `afplay` is running immediately kills `afplay`, clears the remaining speech queue for that turn in `voicebox-speech.ts`, plays the Wake **Audio Cue**, and starts **Active Dictation**.
