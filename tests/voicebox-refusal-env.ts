// Imported first by voicebox-refusal.test.ts: OMP_VOICEBOX_API must be set
// before voicebox-speech.ts evaluates its API constant, so a static import of
// the test subject in the same file (which hoists above statements) cannot
// redirect it to the mock. This module exists only for that ordering.
process.env.OMP_VOICEBOX_API = "http://127.0.0.1:17999";
process.env.OMP_VOICEBOX_PROFILE = "test-voice";
process.env.OMP_VOICE_PRESSURE_FILE = "/nonexistent-guardian-state.json";
