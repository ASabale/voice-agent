# Underdog Woof

Checked 2026-11-08 against the model card, not by running the model.

Underdog Woof is a small English text-to-speech model from Underdog (Hugging Face: ConwayResearch). It has two fixed voices, Juno (default) and Mira. It does not clone a voice. Output is 24 kHz mono. The audio decoder is adapted from Kyutai's Mimi codec.

Sources: https://huggingface.co/ConwayResearch/Underdog-Woof and https://techcrunch.com/2026/11/06/underdog-shows-off-a-32mb-speech-model-in-new-demo/

## Sizes

| Build | Download | Parameters | Where it runs |
|---|---|---|---|
| One voice | 31.7 MB | 30.7M | Browser demo at underdog.ai/woof, and CPU |
| Two voices (Juno and Mira) | 40.6 MB | 38.24M (22.95M speech + 15.3M decoder) | CPU, numpy only |

The two-voice card says peak memory is about 402 MB for Juno on one CPU thread, and speed is 13.8× real time on one Apple M5 Max thread. The one-voice card says 18× real time on that same class of thread, with PyTorch int8 weights. Those timings are the vendor's, on an M5 Max, not this M5 Pro.

## What it is good at

The card says a rule-based normalizer reads phone numbers, dates, times, prices, codes, and symbols the way a person would, and respells hard names from a lexicon. Long text is split into sentences. A sentence over 120 characters is split again at commas, semicolons, or dashes. A seed makes the same text produce the same audio.

Vendor score, not an independent rerun: Mira's word error rate is 1.42% on Gradium TTS Hard Cases (English). They compare that with Fish Audio Drama 3 at 1.89% and a 41.5 GB download. Transcripts in that test were made by another model. Treat the ranking as Underdog's claim.

## License

Free for personal projects, research, teaching, and non-profits, with credit. Credit must say "Underdog Woof" or "underdog.ai", and an app must show "Voice by Underdog Woof". Commercial use needs a license from license@conway.tech. It is not Apache-2.0.

## Not the same model

`ConwayResearch/Underdog-Woof-4B-1.1` is a separate 4-bit MLX Qwen 3 4B checkpoint that Underdog post-trained for their harness. It is not the speech model.

## Fit for this voice loop

Woof can speak English on the CPU without VoiceBox or a GPU. It cannot speak in a cloned voice. Replacing VoiceBox with it would drop the current profile and accept the non-commercial license.
