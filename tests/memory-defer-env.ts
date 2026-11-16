// Imported first by memory-defer.test.ts: a nonexistent guardian state must be
// in the environment before voicebox-speech.ts is evaluated, so the real
// generate() never reads the owner's real pressure file. Each test points
// OMP_VOICE_PRESSURE_FILE at its own temp file and OMP_VOICEBOX_API at its own
// mock port (distinct from voicebox-refusal.test.ts's ports).
process.env.OMP_VOICEBOX_PROFILE = "test-voice";
process.env.OMP_VOICE_PRESSURE_FILE = "/nonexistent-guardian-state.json";
// VA-LOG-004: keep mock speech traffic out of the production state directory.
process.env.OMP_VOICE_STATE_DIR = `${process.env.TMPDIR ?? "/tmp"}/omp-voice-defer-test-state`;
