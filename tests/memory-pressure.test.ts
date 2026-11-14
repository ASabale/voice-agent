import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import {
  currentDeferred,
  currentSpokenText,
  DEFER_EXPIRY_MS,
  enqueue,
  isMemoryTight,
  MEMORY_DEFER_HEADROOM_GIB,
  readMemoryPressure,
  resetSpeechSession,
  retryDeferredSpeech,
  speechSettled,
  stopDeferredRetry,
  stopPlayback,
  waitForHeadroom,
  type ClipGenerator,
  type ClipPlayer,
} from "../extension/voicebox-speech.ts";

const noNap = () => Promise.resolve();

test("the guardian fixture written by the real write path defers speech", () => {
  // Pin the cross-system contract: tests/fixtures/guardian-pressure.json is
  // produced by the guardian's own write_pressure (see
  // tests/test_memory_guardian_contract.py). Unknown or renamed keys are not
  // an error, they are "no pressure data": the guardian's kill logic remains
  // the backstop, so the voice path must not invent a deferral from them.
  const raw = JSON.parse(fs.readFileSync(new URL("fixtures/guardian-pressure.json", import.meta.url), "utf8"));
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "voice-contract-"));
  const file = path.join(dir, "pressure.json");
  process.env.OMP_VOICE_PRESSURE_FILE = file;
  try {
    fs.writeFileSync(file, JSON.stringify({ ...raw, at: new Date().toISOString() }));
    const pressure = readMemoryPressure();
    assert.deepEqual(pressure, { shedVoice: true, headroomGiB: 2.6 });
    assert.equal(isMemoryTight(pressure), true);

    // The drift shape: a guardian that renamed the fields parses as no data.
    fs.writeFileSync(file, JSON.stringify({ at: new Date().toISOString(), headroom_gib: 2.6, shed_voice: true }));
    assert.equal(isMemoryTight(readMemoryPressure()), false);
  } finally {
    delete process.env.OMP_VOICE_PRESSURE_FILE;
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("the real guardian file is parsed and its shed flag respected", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "voice-pressure-"));
  const file = path.join(dir, "pressure.json");
  process.env.OMP_VOICE_PRESSURE_FILE = file;
  try {
    fs.writeFileSync(file, JSON.stringify({ at: new Date().toISOString(), systemUsedGiB: 61.4, headroomGiB: 2.6, shedVoice: true, llmBusy: true }));
    const pressure = readMemoryPressure();
    assert.deepEqual(pressure, { shedVoice: true, headroomGiB: 2.6 });
    assert.equal(isMemoryTight(pressure), true);

    fs.writeFileSync(file, JSON.stringify({ systemUsedGiB: 54.1, headroomGiB: 9.9, shedVoice: false }));
    assert.equal(isMemoryTight(readMemoryPressure()), false);

    fs.writeFileSync(file, "not json");
    assert.equal(isMemoryTight(readMemoryPressure()), false);
  } finally {
    delete process.env.OMP_VOICE_PRESSURE_FILE;
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("missing guardian state does not silence the voice path", () => {
  assert.equal(isMemoryTight(undefined), false);
});

test("the guardian's shed flag silences speech", () => {
  assert.equal(isMemoryTight({ shedVoice: true, headroomGiB: 3.0 }), true);
  assert.equal(isMemoryTight({ shedVoice: false, headroomGiB: 9.9 }), false);
});

test("headroom below the defer line silences speech even without the flag", () => {
  assert.equal(isMemoryTight({ shedVoice: false, headroomGiB: MEMORY_DEFER_HEADROOM_GIB - 0.1 }), true);
  assert.equal(isMemoryTight({ shedVoice: false, headroomGiB: MEMORY_DEFER_HEADROOM_GIB }), false);
});

test("a corrupt pressure file is treated as no pressure", () => {
  assert.equal(isMemoryTight({ shedVoice: false, headroomGiB: Number.NaN }), false);
});

test("speech waits for headroom and speaks once it returns", async () => {
  const readings = [
    { shedVoice: true, headroomGiB: 2.1 },
    { shedVoice: true, headroomGiB: 2.4 },
    { shedVoice: false, headroomGiB: 6.2 },
  ];
  let call = 0;
  const result = await waitForHeadroom(8000, () => readings[call++], noNap);
  assert.equal(result.ok, true);
  assert.equal(result.waitedMs, 2000);
  assert.equal(result.headroomGiB, 6.2);
});

test("speech gives up rather than adding load while memory is exhausted", async () => {
  const result = await waitForHeadroom(3000, () => ({ shedVoice: true, headroomGiB: 0.4 }), noNap);
  assert.equal(result.ok, false);
  assert.equal(result.waitedMs, 3000);
});

let clipCounter = 0;

function recordingPlayer(played: string[]): ClipPlayer {
  return async (clip) => {
    played.push(clip.sentence);
  };
}

test("a deferred sentence is never counted as spoken", async () => {
  resetSpeechSession();
  stopDeferredRetry();
  try {
    const played: string[] = [];
    const gen: ClipGenerator = async () => ({ deferred: true });
    enqueue("Ship the patch tonight.", gen, recordingPlayer(played));
    await speechSettled();
    assert.deepEqual(played, []);
    assert.equal(currentSpokenText(), "");
    assert.equal(currentDeferred().length, 1);
  } finally {
    stopDeferredRetry();
  }
});

test("deferred sentences retry in order once headroom returns", async () => {
  resetSpeechSession();
  stopDeferredRetry();
  try {
    const played: string[] = [];
    let tight = true;
    const gen: ClipGenerator = async (text) => {
      if (tight) return { deferred: true };
      return { clip: { wav: `fake-${++clipCounter}.wav`, sentence: text, clip: clipCounter, reference: null } };
    };
    enqueue("First sentence.", gen, recordingPlayer(played));
    enqueue("Second sentence.", gen, recordingPlayer(played));
    await speechSettled();
    assert.equal(currentDeferred().length, 2);
    tight = false;
    const retried = await retryDeferredSpeech(gen, recordingPlayer(played));
    assert.equal(retried, 2);
    await speechSettled();
    assert.deepEqual(played, ["First sentence.", "Second sentence."]);
    assert.equal(currentDeferred().length, 0);
    assert.equal(currentSpokenText(), "First sentence. Second sentence.");
  } finally {
    stopDeferredRetry();
  }
});

test("a retry while pressure persists stays deferred and silent", async () => {
  resetSpeechSession();
  stopDeferredRetry();
  try {
    const played: string[] = [];
    const gen: ClipGenerator = async () => ({ deferred: true });
    enqueue("Keep watching the build.", gen, recordingPlayer(played));
    await speechSettled();
    await retryDeferredSpeech(gen, recordingPlayer(played));
    await speechSettled();
    assert.deepEqual(played, []);
    assert.equal(currentDeferred().length, 1);
    assert.equal(currentSpokenText(), "");
  } finally {
    stopDeferredRetry();
  }
});

test("a new reply before recovery drops the stale deferrals", async () => {
  resetSpeechSession();
  stopDeferredRetry();
  try {
    const played: string[] = [];
    const gen: ClipGenerator = async () => ({ deferred: true });
    enqueue("Line from the old reply.", gen, recordingPlayer(played));
    await speechSettled();
    assert.equal(currentDeferred().length, 1);
    stopPlayback(); // a new reply bumps the epoch; the deferred line belongs to the old one
    const retried = await retryDeferredSpeech(gen, recordingPlayer(played));
    assert.equal(retried, 0);
    assert.equal(currentDeferred().length, 0);
    assert.deepEqual(played, []);
  } finally {
    stopDeferredRetry();
  }
});

test("deferrals expire after the pressure window instead of retrying forever", async () => {
  resetSpeechSession();
  stopDeferredRetry();
  try {
    const played: string[] = [];
    const gen: ClipGenerator = async () => ({ deferred: true });
    enqueue("A line lost to long pressure.", gen, recordingPlayer(played));
    await speechSettled();
    const expired = await retryDeferredSpeech(gen, recordingPlayer(played), Date.now() + DEFER_EXPIRY_MS + 1000);
    assert.equal(expired, 0);
    assert.equal(currentDeferred().length, 0);
    assert.deepEqual(played, []);
  } finally {
    stopDeferredRetry();
  }
});

test("a retried sentence that was already spoken is not repeated", async () => {
  resetSpeechSession();
  stopDeferredRetry();
  try {
    const played: string[] = [];
    let tight = true;
    const gen: ClipGenerator = async (text) => {
      if (tight) return { deferred: true };
      return { clip: { wav: `fake-${++clipCounter}.wav`, sentence: text, clip: clipCounter, reference: null } };
    };
    const player = recordingPlayer(played);
    enqueue("Done with the deploy.", gen, player);
    await speechSettled();
    tight = false;
    // The same chunk arrives again while the first copy is still held: it is
    // deduped against the held queue, then spoken once by the retry pass.
    enqueue("Done with the deploy.", gen, player);
    await speechSettled();
    const retried = await retryDeferredSpeech(gen, player);
    await speechSettled();
    assert.equal(retried, 1);
    assert.deepEqual(played, ["Done with the deploy."]);
    assert.equal(currentDeferred().length, 0);
  } finally {
    stopDeferredRetry();
  }
});

test("a stale pressure file left by a dead guardian never defers speech", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "voice-stale-"));
  const file = path.join(dir, "pressure.json");
  process.env.OMP_VOICE_PRESSURE_FILE = file;
  try {
    fs.writeFileSync(file, JSON.stringify({
      at: new Date(Date.now() - 60000).toISOString(),
      shedVoice: true,
      headroomGiB: 0.4,
    }));
    assert.equal(readMemoryPressure(), undefined);
    const result = await waitForHeadroom(8000, readMemoryPressure, noNap);
    assert.equal(result.ok, true);
    assert.equal(result.waitedMs, 0);
  } finally {
    delete process.env.OMP_VOICE_PRESSURE_FILE;
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("pressure inside the staleness window is still respected", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "voice-fresh-"));
  const file = path.join(dir, "pressure.json");
  process.env.OMP_VOICE_PRESSURE_FILE = file;
  try {
    fs.writeFileSync(file, JSON.stringify({
      at: new Date(Date.now() - 10000).toISOString(),
      shedVoice: true,
      headroomGiB: 0.4,
    }));
    const result = await waitForHeadroom(3000, readMemoryPressure, noNap);
    assert.equal(result.ok, false);
    assert.equal(result.waitedMs, 3000);
  } finally {
    delete process.env.OMP_VOICE_PRESSURE_FILE;
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a pressure file with no timestamp is treated as fresh, not stale", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "voice-noat-"));
  const file = path.join(dir, "pressure.json");
  process.env.OMP_VOICE_PRESSURE_FILE = file;
  try {
    fs.writeFileSync(file, JSON.stringify({ shedVoice: true, headroomGiB: 0.4 }));
    assert.deepEqual(readMemoryPressure(), { shedVoice: true, headroomGiB: 0.4 });
  } finally {
    delete process.env.OMP_VOICE_PRESSURE_FILE;
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
