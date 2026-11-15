import assert from "node:assert/strict";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

import "./memory-defer-env.ts";
import {
  currentDeferred,
  currentSpeechStatus,
  currentSpokenText,
  enqueue,
  generate,
  MEMORY_WAIT_MS,
  resetSpeechSession,
  retryDeferredSpeech,
  speechSettled,
  stopDeferredRetry,
  type ClipPlayer,
} from "../extension/voicebox-speech.ts";

// These tests drive the *real* generate() — the path that must not open an HTTP
// connection to VoiceBox while the guardian reports voice-shed. Stub-generator
// queue tests (memory-pressure.test.ts, voicebox-refusal.test.ts) prove the
// retry bookkeeping; none of them proved the gate itself.
//
// The waits are real: waitForHeadroom inside generate sleeps 1 s per poll up
// to MEMORY_WAIT_MS. Only the pressure file and the VoiceBox endpoint are
// synthetic.

function listen(server: http.Server, port: number): Promise<void> {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", resolve);
  });
}

// A real 16-bit PCM WAV: enough for wavReference to accept the payload as audio.
function validWav(frames = 4410): Buffer {
  const data = Buffer.alloc(frames * 2);
  const header = Buffer.alloc(44);
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + data.length, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20);
  header.writeUInt16LE(1, 22);
  header.writeUInt32LE(44100, 24);
  header.writeUInt32LE(2, 28);
  header.writeUInt16LE(2, 32);
  header.writeUInt16LE(16, 34);
  header.write("data", 36);
  header.writeUInt32LE(data.length, 40);
  return Buffer.concat([header, data]);
}

function mockVoiceBox(port: number): { server: http.Server; streamHits: () => number } {
  let hits = 0;
  const server = http.createServer((req, res) => {
    if (req.url === "/generate/stream") {
      hits++;
      res.writeHead(200, { "content-type": "application/octet-stream" });
      res.end(validWav());
      return;
    }
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify([{ name: "test-voice", id: "p-test" }]));
  });
  return { server, streamHits: () => hits };
}

function recordingPlayer(played: string[]): ClipPlayer {
  return async (clip) => {
    played.push(clip.sentence);
  };
}

function freshPressureFile(): { dir: string; file: string } {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "memory-defer-"));
  return { dir, file: path.join(dir, "pressure.json") };
}

function writePressure(file: string, payload: Record<string, unknown>): void {
  fs.writeFileSync(file, JSON.stringify({ at: new Date().toISOString(), ...payload }));
}

function restoreEnv(): void {
  delete process.env.OMP_VOICE_PRESSURE_FILE;
  process.env.OMP_VOICE_PRESSURE_FILE = "/nonexistent-guardian-state.json";
}

test("guardian shed defers real speech without touching VoiceBox, relief replays it in order exactly once", async () => {
  resetSpeechSession();
  stopDeferredRetry();
  process.env.OMP_VOICEBOX_API = "http://127.0.0.1:17988";
  const { dir, file } = freshPressureFile();
  process.env.OMP_VOICE_PRESSURE_FILE = file;
  writePressure(file, { shedVoice: true, headroomGiB: 0.4 });
  const { server, streamHits } = mockVoiceBox(17988);
  await listen(server, 17988);
  const played: string[] = [];
  const player = recordingPlayer(played);
  try {
    enqueue("Deploy is green.", generate, player);
    await speechSettled();
    // The gate held before any HTTP: nothing reached VoiceBox, nothing was
    // counted as spoken, and the sentence is visible as held, not lost.
    assert.equal(streamHits(), 0, "no HTTP request while memory is tight");
    assert.deepEqual(played, []);
    assert.equal(currentSpokenText(), "");
    const st = currentSpeechStatus();
    assert.equal(st.speaking, false);
    assert.equal(st.deferred, 1);
    assert.ok(st.deferredOldestAgeMs >= MEMORY_WAIT_MS, "the full wait bound was exhausted");

    // The rest of the same reply queues behind the held sentence, in order,
    // without each waiting out its own 8 s.
    enqueue("Second sentence.", generate, player);
    enqueue("Third sentence.", generate, player);
    await speechSettled();
    assert.equal(currentDeferred().length, 3);
    assert.equal(streamHits(), 0);

    // Guardian reports relief.
    writePressure(file, { shedVoice: false, headroomGiB: 8.1 });
    const retried = await retryDeferredSpeech(generate, player);
    await speechSettled();
    assert.equal(retried, 3);
    assert.equal(streamHits(), 3, "each held sentence generated exactly once");
    assert.deepEqual(played, ["Deploy is green.", "Second sentence.", "Third sentence."]);
    assert.equal(currentDeferred().length, 0);
    assert.equal(currentSpokenText(), "Deploy is green. Second sentence. Third sentence.");
  } finally {
    stopDeferredRetry();
    server.close();
    restoreEnv();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("speech recovers mid-wait and plays as soon as headroom returns", async () => {
  resetSpeechSession();
  stopDeferredRetry();
  process.env.OMP_VOICEBOX_API = "http://127.0.0.1:17987";
  const { dir, file } = freshPressureFile();
  process.env.OMP_VOICE_PRESSURE_FILE = file;
  writePressure(file, { shedVoice: true, headroomGiB: 1.2 });
  const { server, streamHits } = mockVoiceBox(17987);
  await listen(server, 17987);
  const played: string[] = [];
  const player = recordingPlayer(played);
  const relief = setTimeout(() => {
    writePressure(file, { shedVoice: false, headroomGiB: 7.0 });
  }, 2000);
  const started = Date.now();
  try {
    enqueue("Relief arrived before the timeout.", generate, player);
    await speechSettled();
    const elapsed = Date.now() - started;
    // It waited for the relief (~2 s) instead of burning the full 8 s bound.
    assert.ok(elapsed >= 2000 && elapsed < 6000, `elapsed ${elapsed} ms`);
    assert.equal(streamHits(), 1);
    assert.deepEqual(played, ["Relief arrived before the timeout."]);
    assert.equal(currentDeferred().length, 0);
  } finally {
    clearTimeout(relief);
    stopDeferredRetry();
    server.close();
    restoreEnv();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a stale or corrupt guardian file never silences the real generation path", async () => {
  resetSpeechSession();
  stopDeferredRetry();
  process.env.OMP_VOICEBOX_API = "http://127.0.0.1:17986";
  const { dir, file } = freshPressureFile();
  process.env.OMP_VOICE_PRESSURE_FILE = file;
  const { server, streamHits } = mockVoiceBox(17986);
  await listen(server, 17986);
  const played: string[] = [];
  const player = recordingPlayer(played);
  try {
    // A dead guardian's last "shed voice" must not silence speech forever:
    // its kill logic is gone with it.
    fs.writeFileSync(
      file,
      JSON.stringify({ at: new Date(Date.now() - 60000).toISOString(), shedVoice: true, headroomGiB: 0.1 }),
    );
    enqueue("Stale file must not defer.", generate, player);
    await speechSettled();

    // Garbage is "no pressure data", not a deferral.
    fs.writeFileSync(file, "garbage{{{");
    enqueue("Corrupt file must not defer.", generate, player);
    await speechSettled();

    assert.equal(streamHits(), 2);
    assert.deepEqual(played, ["Stale file must not defer.", "Corrupt file must not defer."]);
    assert.equal(currentDeferred().length, 0);
  } finally {
    stopDeferredRetry();
    server.close();
    restoreEnv();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
