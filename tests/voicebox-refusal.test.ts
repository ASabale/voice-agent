import assert from "node:assert/strict";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

import "./voicebox-refusal-env.ts";
import {
  currentDeferred,
  currentSpeechStatus,
  currentSpokenText,
  DEFER_EXPIRY_MS,
  enqueue,
  isConnectionRefusal,
  resetSpeechSession,
  retryDeferredSpeech,
  speechSettled,
  stopDeferredRetry,
  stopPlayback,
  type ClipGenerator,
  type ClipPlayer,
} from "../extension/voicebox-speech.ts";

function listen(server: http.Server, port: number): Promise<void> {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", resolve);
  });
}

function stubPlayer(played: string[]): ClipPlayer {
  return async (clip) => {
    played.push(clip.sentence);
  };
}

// A real 16-bit PCM WAV header plus `frames` samples: enough for wavReference
// to parse, so generate() treats the payload as genuine audio.
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

const upGenerator: ClipGenerator = async (text: string) => ({
  clip: { wav: "mock.wav", sentence: text, clip: 1, reference: null },
});

test("a 200 with a truncated audio payload holds the sentence instead of dropping it", async () => {
  resetSpeechSession();
  // Each scenario gets its own port: Node's keep-alive pool keys by origin and
  // a dead socket from one mock poisons the next test's fresh server.
  process.env.OMP_VOICEBOX_API = "http://127.0.0.1:17999";
  let goodTurn = false;
  const server = http.createServer((req, res) => {
    if (req.url === "/generate/stream") {
      if (goodTurn) {
        res.writeHead(200, { "content-type": "application/octet-stream" });
        res.end(validWav());
      } else {
        // VoiceBox alive but the model unloaded: 200 with ~nothing in it.
        res.writeHead(200, { "content-type": "application/octet-stream" });
        res.end(Buffer.from("RIFF"));
      }
      return;
    }
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify([{ name: "test-voice", id: "p-tiny" }]));
  });
  await listen(server, 17999);
  try {
    const played: string[] = [];
    enqueue("the payload came back empty", undefined, stubPlayer(played));
    await speechSettled();
    assert.equal(currentSpokenText(), "");
    assert.equal(currentDeferred().length, 1, "a 200 with no audio must not count as spoken or lost");
    goodTurn = true;
    // Recovery through the real generate(): the mock now answers 200 with a
    // usable payload and the retry chain replays the held sentence.
    await retryDeferredSpeech(undefined, stubPlayer(played), Date.now());
    await speechSettled();
    assert.deepEqual(played, ["the payload came back empty"]);
    assert.equal(currentDeferred().length, 0);
  } finally {
    stopDeferredRetry();
    server.closeAllConnections();
    server.close();
  }
});

test("an abort from the 90 second timeout is not treated as a refusal", () => {
  // An aborted request means the caller cancelled it (barge-in path), not that
  // VoiceBox is unreachable; epoch handling owns it.
  assert.equal(isConnectionRefusal(new Error("AbortError: This operation was aborted")), false);
});

test("keep-alive resets and timeouts count as VoiceBox being unreachable", () => {
  // The real shape Node's fetch produces when the peer dies: TypeError with
  // the transport error in the cause.
  assert.equal(isConnectionRefusal(new TypeError("fetch failed", { cause: new Error("read ECONNRESET") })), true);
  assert.equal(isConnectionRefusal(new TypeError("fetch failed", { cause: new Error("connect ETIMEDOUT 127.0.0.1:17493") })), true);
  assert.equal(isConnectionRefusal(new TypeError("fetch failed", { cause: new Error("connect ECONNREFUSED 127.0.0.1:17493") })), true);
  // An abort from barge-in is not a transport failure; epoch drop handles it.
  assert.equal(isConnectionRefusal(new Error("AbortError: This operation was aborted")), false);
});

test("a socket closed mid-request by the sidecar is a refusal, not a loss", () => {
  // VA-TTS-021: when VoiceBox accepts the connection and then dies mid-request
  // (the sidecar crash shape seen in speech.log), Node 26's fetch throws
  // TypeError("fetch failed") with cause SocketError("other side closed",
  // code UND_ERR_SOCKET). That shape was silently dropping the sentence.
  const socketError = new Error("SocketError: other side closed");
  (socketError as { code?: string }).code = "UND_ERR_SOCKET";
  assert.equal(isConnectionRefusal(new TypeError("fetch failed", { cause: socketError })), true);
  assert.equal(isConnectionRefusal(new TypeError("fetch failed", { cause: new Error("socket hang up") })), true);
});

test("a VoiceBox answering 500 holds the sentence instead of dropping it", async () => {
  resetSpeechSession();
  process.env.OMP_VOICEBOX_API = "http://127.0.0.1:17998";
  let streamAttempts = 0;
  const server = http.createServer((req, res) => {
    if (req.url === "/generate/stream") {
      streamAttempts++;
      res.writeHead(500, { "content-type": "text/plain" });
      res.end("model not loaded");
      return;
    }
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify([{ name: "test-voice", id: "p-test" }]));
  });
  await listen(server, 17998);
  try {
    const played: string[] = [];
    enqueue("the machine is learning a new trick", undefined, stubPlayer(played));
    await speechSettled();
    assert.equal(streamAttempts, 1);
    assert.equal(currentDeferred().length, 1);
    assert.equal(currentDeferred()[0].text, "the machine is learning a new trick");
    assert.equal(played.length, 0);
    // Held, never counted as spoken: rollback/dedupe must be able to say it later.
    assert.equal(currentSpokenText(), "");
    stopDeferredRetry();
  } finally {
    server.closeAllConnections();
    server.close();
  }
});

test("a sidecar dying mid-request holds the sentence and replays it on recovery", async () => {
  // VA-TTS-021 end-to-end repro: VoiceBox accepts the TCP connection, then the
  // socket closes before any response — the exact shape speech.log recorded as
  // `event: failed, reason: TypeError: fetch failed` when the GUI died.
  resetSpeechSession();
  process.env.OMP_VOICEBOX_API = "http://127.0.0.1:17992";
  let streamAttempts = 0;
  let serveWell = false;
  const server = http.createServer((req, res) => {
    if (req.url === "/generate/stream") {
      streamAttempts++;
      if (!serveWell) {
        req.destroy();
        return;
      }
      res.writeHead(200, { "content-type": "audio/wav" });
      res.end(validWav());
      return;
    }
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify([{ name: "test-voice", id: "p-test" }]));
  });
  await listen(server, 17992);
  try {
    const played: string[] = [];
    enqueue("the sidecar crashed while this was streaming", undefined, stubPlayer(played));
    await speechSettled();
    assert.equal(streamAttempts, 1);
    assert.equal(currentDeferred().length, 1, "a mid-request socket death must hold, not drop");
    assert.equal(currentSpokenText(), "");
    serveWell = true;
    // The mid-request death armed the 5 s refusal hold window, so the real
    // generate() would correctly decline to reconnect yet. Replay through a
    // stub generator: the hold itself is already proven against the real mock.
    const upGen: ClipGenerator = async (text: string) => ({
      clip: { wav: "mock.wav", sentence: text, clip: 2, reference: null },
    });
    await retryDeferredSpeech(upGen, stubPlayer(played), Date.now());
    await speechSettled();
    assert.deepEqual(played, ["the sidecar crashed while this was streaming"]);
    assert.equal(currentDeferred().length, 0);
  } finally {
    stopDeferredRetry();
    server.closeAllConnections();
    server.close();
  }
});

test("a refused connection holds the sentence and the hold window stops hammering", async () => {
  resetSpeechSession();
  process.env.OMP_VOICEBOX_API = "http://127.0.0.1:17997";
  const played: string[] = [];
  // Nothing is listening on 17997: fetch fails with ECONNREFUSED.
  enqueue("first sentence while voicebox is down", undefined, stubPlayer(played));
  await speechSettled();
  assert.equal(currentDeferred().length, 1);

  // Inside the refusal window a second sentence must also be held, and it must
  // not open another connection to a known-dead VoiceBox.
  let laterAttempts = 0;
  const server = http.createServer((_req, res) => {
    laterAttempts++;
    res.writeHead(200, { "content-type": "application/json" });
    res.end("[]");
  });
  await listen(server, 17997);
  try {
    enqueue("second sentence during the hold", undefined, stubPlayer(played));
    await speechSettled();
    assert.equal(laterAttempts, 0);
    assert.equal(currentDeferred().length, 2);
    assert.deepEqual(currentDeferred().map((item) => item.text), [
      "first sentence while voicebox is down",
      "second sentence during the hold",
    ]);
    stopDeferredRetry();
  } finally {
    server.closeAllConnections();
    server.close();
  }
});

test("held sentences are spoken oldest first when the service recovers", async () => {
  resetSpeechSession();
  const down: ClipGenerator = async () => ({ deferred: true });
  const played: string[] = [];
  const player = stubPlayer(played);
  enqueue("alpha first", down, player);
  enqueue("beta second", down, player);
  await speechSettled();
  assert.equal(currentDeferred().length, 2);

  const retried = await retryDeferredSpeech(upGenerator, player, Date.now());
  assert.equal(retried, 2);
  await speechSettled();
  assert.deepEqual(played, ["alpha first", "beta second"]);
  assert.equal(currentDeferred().length, 0);
  // A second pass must not duplicate: the sentences are now committed.
  assert.equal(await retryDeferredSpeech(upGenerator, player, Date.now()), 0);
  stopDeferredRetry();
});

test("a barge-in while sentences are held drops them with the reply", async () => {
  resetSpeechSession();
  const down: ClipGenerator = async () => ({ deferred: true });
  const played: string[] = [];
  enqueue("never spoken after barge-in", down, stubPlayer(played));
  await speechSettled();
  assert.equal(currentDeferred().length, 1);
  // stopPlayback increments the epoch; deferred items tied to the old epoch
  // must be dropped rather than resurrected after a barge-in.
  stopPlayback();
  const retried = await retryDeferredSpeech(upGenerator, stubPlayer(played), Date.now());
  assert.equal(retried, 0);
  assert.equal(currentDeferred().length, 0);
  assert.equal(played.length, 0);
  stopDeferredRetry();
});

test("a watchdog abort on a hung generation holds the sentence and replays on recovery", async () => {
  resetSpeechSession();
  process.env.OMP_VOICEBOX_API = "http://127.0.0.1:17996";
  process.env.OMP_VOICE_TTS_TIMEOUT_MS = "800";
  let streamAttempts = 0;
  const server = http.createServer((req, res) => {
    if (req.url === "/generate/stream") {
      streamAttempts++;
      if (streamAttempts === 1) {
        // Headers sent, body never ends: the watchdog aborts at 800 ms.
        res.writeHead(200, { "content-type": "application/octet-stream" });
        return;
      }
      res.writeHead(200, { "content-type": "application/octet-stream" });
      res.end(validWav());
      return;
    }
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify([{ name: "test-voice", id: "p-test" }]));
  });
  await listen(server, 17996);
  try {
    const played: string[] = [];
    const player = stubPlayer(played);
    enqueue("the sidecar hung mid sentence", undefined, player);
    await speechSettled();
    assert.equal(streamAttempts, 1);
    assert.equal(currentDeferred().length, 1);
    assert.equal(currentSpokenText(), "");
    assert.equal(played.length, 0);
    stopDeferredRetry();
    // Recovery: the same generate path succeeds on the retry and the sentence
    // is spoken exactly once.
    const retried = await retryDeferredSpeech(undefined, player, Date.now());
    assert.equal(retried, 1);
    await speechSettled();
    assert.equal(streamAttempts, 2);
    assert.deepEqual(played, ["the sidecar hung mid sentence"]);
  } finally {
    delete process.env.OMP_VOICE_TTS_TIMEOUT_MS;
    server.closeAllConnections();
    server.close();
  }
});

test("a player hung until the watchdog kills it is never counted as spoken", async () => {
  resetSpeechSession();
  // The real `play()` runs: a fake `afplay` on PATH spawns and busy-loops
  // forever, so only the playback watchdog ends it. No generation is needed
  // — the failure is purely on the player side.
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "va-hung-player-"));
  const wav = path.join(dir, "clip.wav");
  fs.writeFileSync(wav, validWav(4410));
  fs.writeFileSync(path.join(dir, "afplay"), "#!/bin/sh\nwhile :; do :; done\n");
  fs.chmodSync(path.join(dir, "afplay"), 0o755);
  const savedPath = process.env.PATH;
  process.env.PATH = `${dir}:${savedPath}`;
  process.env.OMP_PLAY_WATCHDOG_MS = "300";
  const gen: ClipGenerator = () =>
    Promise.resolve({ clip: { wav, sentence: "the player hung and the watchdog killed it", clip: 1, reference: null } });
  try {
    enqueue("the player hung and the watchdog killed it", gen);
    await speechSettled();
    const status = currentSpeechStatus();
    assert.equal(status.speaking, false);
    // A killed, never-played clip must stay recoverable, not silently spoken.
    assert.equal(currentSpokenText(), "");
  } finally {
    stopDeferredRetry();
    process.env.PATH = savedPath;
    delete process.env.OMP_PLAY_WATCHDOG_MS;
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a watchdog-killed hung player defers the sentence into the retry chain", async () => {
  resetSpeechSession();
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "va-hung-player-defer-"));
  const wav = path.join(dir, "clip.wav");
  fs.writeFileSync(wav, validWav(4410));
  fs.writeFileSync(path.join(dir, "afplay"), "#!/bin/sh\nwhile :; do :; done\n");
  fs.chmodSync(path.join(dir, "afplay"), 0o755);
  const savedPath = process.env.PATH;
  process.env.PATH = `${dir}:${savedPath}`;
  process.env.OMP_PLAY_WATCHDOG_MS = "300";
  const sentence = "the player hung and the sentence must be retried";
  const gen: ClipGenerator = () =>
    Promise.resolve({ clip: { wav, sentence, clip: 1, reference: null } });
  try {
    enqueue(sentence, gen);
    await speechSettled();
    // A released-but-never-spoken sentence must be held for retry, like a
    // hung generation — otherwise nothing in the pipeline ever speaks it again.
    assert.equal(currentDeferred().length, 1);
    assert.equal(currentDeferred()[0].text, sentence);
    assert.equal(currentSpeechStatus().deferred, 1);
    // Recovery: a working player replays it exactly once, oldest first.
    const played: string[] = [];
    const retried = await retryDeferredSpeech(gen, stubPlayer(played), Date.now());
    assert.equal(retried, 1);
    await speechSettled();
    assert.deepEqual(played, [sentence]);
    assert.equal(currentDeferred().length, 0);
    assert.equal(currentSpokenText(), sentence);
  } finally {
    stopDeferredRetry();
    process.env.PATH = savedPath;
    delete process.env.OMP_PLAY_WATCHDOG_MS;
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a player process that exits with a failure code defers the sentence", async () => {
  resetSpeechSession();
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "va-player-fail-"));
  const wav = path.join(dir, "clip.wav");
  fs.writeFileSync(wav, validWav(4410));
  fs.writeFileSync(path.join(dir, "afplay"), "#!/bin/sh\nexit 1\n");
  fs.chmodSync(path.join(dir, "afplay"), 0o755);
  const savedPath = process.env.PATH;
  process.env.PATH = `${dir}:${savedPath}`;
  const sentence = "the player failed and the sentence must be retried";
  const gen: ClipGenerator = () =>
    Promise.resolve({ clip: { wav, sentence, clip: 1, reference: null } });
  try {
    enqueue(sentence, gen);
    await speechSettled();
    // Exit code 1 means nothing was heard: the sentence must be held for
    // retry, not released into nothing.
    assert.equal(currentSpokenText(), "");
    assert.equal(currentDeferred().length, 1);
    const played: string[] = [];
    const retried = await retryDeferredSpeech(gen, stubPlayer(played), Date.now());
    await speechSettled();
    assert.equal(retried, 1);
    assert.deepEqual(played, [sentence]);
    assert.equal(currentSpokenText(), sentence);
  } finally {
    stopDeferredRetry();
    process.env.PATH = savedPath;
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("re-enqueueing a watchdog-held sentence does not duplicate its deferral", async () => {
  resetSpeechSession();
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "va-hung-player-recovery-"));
  const wav = path.join(dir, "clip.wav");
  fs.writeFileSync(wav, validWav(4410));
  fs.writeFileSync(path.join(dir, "afplay"), "#!/bin/sh\nwhile :; do :; done\n");
  fs.chmodSync(path.join(dir, "afplay"), 0o755);
  const savedPath = process.env.PATH;
  process.env.PATH = `${dir}:${savedPath}`;
  process.env.OMP_PLAY_WATCHDOG_MS = "300";
  const sentence = "the player hung but the sentence is not lost";
  const gen: ClipGenerator = () =>
    Promise.resolve({ clip: { wav, sentence, clip: 1, reference: null } });
  try {
    // Turn 1: the real player hangs, the watchdog releases the sentence into
    // the retry chain.
    enqueue(sentence, gen);
    await speechSettled();
    assert.equal(currentSpokenText(), "");
    assert.equal(currentDeferred().length, 1);
    // A repeated enqueue of the same held sentence must not create a second
    // deferral entry: it is replayed exactly once when the chain runs.
    enqueue(sentence, gen, stubPlayer([]));
    assert.equal(currentDeferred().length, 1);
    const played: string[] = [];
    await retryDeferredSpeech(gen, stubPlayer(played), Date.now());
    await speechSettled();
    assert.deepEqual(played, [sentence]);
    assert.equal(currentSpokenText(), sentence);
  } finally {
    stopDeferredRetry();
    process.env.PATH = savedPath;
    delete process.env.OMP_PLAY_WATCHDOG_MS;
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a 200 whose body is an error page, not PCM, holds the sentence", async () => {
  resetSpeechSession();
  process.env.OMP_VOICEBOX_API = "http://127.0.0.1:17994";
  let streamAttempts = 0;
  let serveGarbage = true;
  const server = http.createServer((req, res) => {
    if (req.url === "/generate/stream") {
      streamAttempts++;
      if (serveGarbage) {
        // 200, over the old 100-byte floor, but not audio at all: a JSON error
        // body from a wedged service would have gone to afplay and been lost.
        res.writeHead(200, { "content-type": "application/json" });
        res.end(JSON.stringify({ error: "model unloaded mid stream", detail: "x".repeat(100) }));
        return;
      }
      res.writeHead(200, { "content-type": "application/octet-stream" });
      res.end(validWav());
      return;
    }
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify([{ name: "test-voice", id: "p-test" }]));
  });
  await listen(server, 17994);
  try {
    const played: string[] = [];
    const player = stubPlayer(played);
    enqueue("a garbage body must not count as speech", undefined, player);
    await speechSettled();
    assert.equal(streamAttempts, 1);
    assert.equal(currentDeferred().length, 1);
    assert.equal(currentSpokenText(), "");
    assert.equal(played.length, 0);
    stopDeferredRetry();
    serveGarbage = false;
    assert.equal(await retryDeferredSpeech(undefined, player, Date.now()), 1);
    await speechSettled();
    assert.deepEqual(played, ["a garbage body must not count as speech"]);
  } finally {
    server.closeAllConnections();
    server.close();
  }
});

test("a valid WAV header with effectively no audio holds the sentence", async () => {
  resetSpeechSession();
  process.env.OMP_VOICEBOX_API = "http://127.0.0.1:17993";
  const server = http.createServer((req, res) => {
    if (req.url === "/generate/stream") {
      // 20 ms of PCM: a correct header afplay would "successfully" play as
      // silence, silently counting the sentence as spoken.
      res.writeHead(200, { "content-type": "application/octet-stream" });
      res.end(validWav(400));
      return;
    }
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify([{ name: "test-voice", id: "p-test" }]));
  });
  await listen(server, 17993);
  try {
    const played: string[] = [];
    enqueue("silence is not a spoken sentence", undefined, stubPlayer(played));
    await speechSettled();
    assert.equal(currentDeferred().length, 1);
    assert.equal(currentSpokenText(), "");
    assert.equal(played.length, 0);
    stopDeferredRetry();
  } finally {
    server.closeAllConnections();
    server.close();
  }
});

test("a real stop during a hung generation drops the sentence, not defers it", async () => {
  resetSpeechSession();
  process.env.OMP_VOICEBOX_API = "http://127.0.0.1:17995";
  process.env.OMP_VOICE_TTS_TIMEOUT_MS = "5000";
  const server = http.createServer((req, res) => {
    if (req.url === "/generate/stream") {
      res.writeHead(200, { "content-type": "application/octet-stream" });
      return; // hang forever; the stop must kill it
    }
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify([{ name: "test-voice", id: "p-test" }]));
  });
  await listen(server, 17995);
  try {
    const played: string[] = [];
    enqueue("interrupted while the sidecar hangs", undefined, stubPlayer(played));
    await new Promise((resolve) => setTimeout(resolve, 100)); // fetch is in flight
    stopPlayback(); // bumps the epoch and aborts the active request
    await new Promise((resolve) => setTimeout(resolve, 100));
    assert.equal(currentDeferred().length, 0);
    assert.equal(played.length, 0);
    assert.equal(currentSpokenText(), "");
    stopDeferredRetry();
  } finally {
    delete process.env.OMP_VOICE_TTS_TIMEOUT_MS;
    server.closeAllConnections();
    server.close();
  }
});

test("a repeatedly deferred sentence keeps its original deferral time and eventually expires", async () => {
  // The retry timer re-arms every DEFER_RETRY_MS. If each re-deferral stamped
  // a fresh time, `now - at` would never exceed DEFER_EXPIRY_MS and a sentence
  // would retry forever against a permanently dead VoiceBox.
  resetSpeechSession();
  stopDeferredRetry();
  try {
    const played: string[] = [];
    const player = stubPlayer(played);
    const gen: ClipGenerator = async () => ({ deferred: true });
    enqueue("a line that outlives the retry window", gen, player);
    await speechSettled();
    const firstAt = currentDeferred()[0].at;
    // Retried inside the window: held again, clock unchanged.
    assert.equal(await retryDeferredSpeech(gen, player, firstAt + 60000), 1);
    await speechSettled();
    assert.equal(currentDeferred()[0].at, firstAt);
    // Once the window has passed, it is dropped, not retried forever.
    assert.equal(await retryDeferredSpeech(gen, player, firstAt + DEFER_EXPIRY_MS + 1000), 0);
    assert.equal(currentDeferred().length, 0);
    assert.deepEqual(played, []);
  } finally {
    stopDeferredRetry();
  }
});

test("a sentence still held during replay does not let later sentences jump ahead of it", async () => {
  // Partial recovery: the service is back, but one sentence of the held reply
  // still fails. The sentences after it must wait, not play out of order.
  resetSpeechSession();
  stopDeferredRetry();
  try {
    const sentences = ["First sentence.", "Second sentence.", "Third sentence.", "Fourth sentence."];
    const down: ClipGenerator = async () => ({ deferred: true });
    const played: string[] = [];
    const player = stubPlayer(played);
    for (const sentence of sentences) enqueue(sentence, down, player);
    await speechSettled();
    assert.equal(currentDeferred().length, 4);
    const flaky: ClipGenerator = async (text) => {
      if (text === "Second sentence.") return { deferred: true };
      return { clip: { wav: "", sentence: text, clip: 0, reference: null } };
    };
    // First plays, Second re-defers, and the pass stops there: the rest stay
    // queued behind the held sentence so the reply plays in its original order.
    assert.equal(await retryDeferredSpeech(flaky, player), 2);
    await speechSettled();
    assert.deepEqual(played, ["First sentence."]);
    assert.deepEqual(currentDeferred().map((item) => item.text), [
      "Second sentence.",
      "Third sentence.",
      "Fourth sentence.",
    ]);
    // Full recovery: replay resumes from the held sentence, order intact.
    const up: ClipGenerator = async (text) => ({ clip: { wav: "", sentence: text, clip: 0, reference: null } });
    assert.equal(await retryDeferredSpeech(up, player), 3);
    await speechSettled();
    assert.deepEqual(played, sentences);
  } finally {
    stopDeferredRetry();
  }
});

test("a new sentence arriving while earlier ones are held waits behind them", async () => {
  // Same ordering rule on the live enqueue path: once a reply has a held
  // sentence, nothing later in the reply may play before it.
  resetSpeechSession();
  stopDeferredRetry();
  try {
    const down: ClipGenerator = async () => ({ deferred: true });
    const flaky: ClipGenerator = async (text) =>
      text === "Held line." ? { deferred: true } : { clip: { wav: "", sentence: text, clip: 0, reference: null } };
    const played: string[] = [];
    const player = stubPlayer(played);
    enqueue("Held line.", flaky, player);
    await speechSettled();
    assert.equal(currentDeferred().length, 1);
    enqueue("Later line.", flaky, player); // the service works for this one
    await speechSettled();
    assert.deepEqual(played, []);
    assert.deepEqual(currentDeferred().map((item) => item.text), ["Held line.", "Later line."]);
    const up: ClipGenerator = async (text) => ({ clip: { wav: "", sentence: text, clip: 0, reference: null } });
    assert.equal(await retryDeferredSpeech(up, player), 2);
    await speechSettled();
    assert.deepEqual(played, ["Held line.", "Later line."]);
  } finally {
    stopDeferredRetry();
  }
});

test("the status surface reports sentences held during an outage", async () => {
  // Silence during an outage must be explainable: the status payload carries
  // the held count and how long the oldest sentence has waited.
  resetSpeechSession();
  stopDeferredRetry();
  try {
    const down: ClipGenerator = async () => ({ deferred: true });
    const player = stubPlayer([]);
    enqueue("First held line.", down, player);
    enqueue("Second held line.", down, player);
    await speechSettled();
    const st = currentSpeechStatus();
    assert.equal(st.speaking, false);
    assert.equal(st.deferred, 2);
    assert.ok(st.deferredOldestAgeMs >= 0);
    assert.equal(st.expiredSpeech, 0);
  } finally {
    stopDeferredRetry();
  }
});

test("held sentences that expire are reported as unspoken speech", async () => {
  resetSpeechSession();
  stopDeferredRetry();
  try {
    const down: ClipGenerator = async () => ({ deferred: true });
    const player = stubPlayer([]);
    enqueue("Lost to long pressure.", down, player);
    await speechSettled();
    const expired = await retryDeferredSpeech(down, player, Date.now() + DEFER_EXPIRY_MS + 1000);
    assert.equal(expired, 0);
    const st = currentSpeechStatus();
    assert.equal(st.deferred, 0);
    assert.equal(st.expiredSpeech, 1);
  } finally {
    stopDeferredRetry();
  }
});

test("a replaced reply's dropped sentences are not counted as expired speech", async () => {
  // The user replaced the reply intentionally; those sentences were never
  // promised as speech the user should hear.
  resetSpeechSession();
  stopDeferredRetry();
  try {
    const down: ClipGenerator = async () => ({ deferred: true });
    const player = stubPlayer([]);
    enqueue("Line from the superseded reply.", down, player);
    await speechSettled();
    stopPlayback();
    await retryDeferredSpeech(down, player);
    const st = currentSpeechStatus();
    assert.equal(st.deferred, 0);
    assert.equal(st.expiredSpeech, 0);
  } finally {
    stopDeferredRetry();
  }
});

test("a full replay clears the held state from the status surface", async () => {
  resetSpeechSession();
  stopDeferredRetry();
  try {
    const down: ClipGenerator = async () => ({ deferred: true });
    const up: ClipGenerator = async (text) => ({ clip: { wav: "", sentence: text, clip: 0, reference: null } });
    const player = stubPlayer([]);
    enqueue("Recoverable line.", down, player);
    await speechSettled();
    assert.equal(currentSpeechStatus().deferred, 1);
    assert.equal(await retryDeferredSpeech(up, player), 1);
    await speechSettled();
    const st = currentSpeechStatus();
    assert.equal(st.deferred, 0);
    assert.equal(st.expiredSpeech, 0);
  } finally {
    stopDeferredRetry();
  }
});

test("a whole reply held during an outage replays exactly once, in order, on recovery", async () => {
  // Level 1 stand-in for the Level 5 "queue saturation" row: an entire
  // multi-sentence reply is generated while VoiceBox is down, then the
  // service returns. Nothing may be lost, doubled, or left in the queue.
  resetSpeechSession();
  stopDeferredRetry();
  process.env.OMP_VOICEBOX_API = "http://127.0.0.1:17991";
  const N = 300;
  const sentences = Array.from({ length: N }, (_, i) => `saturation sentence number ${i}.`);
  const played: string[] = [];
  const player: ClipPlayer = async (clip) => {
    played.push(clip.sentence);
    try {
      fs.unlinkSync(clip.wav);
    } catch {
      // stub never played a real clip file on this path
    }
  };
  try {
    // Outage: nothing listens on 17991. The first generate is refused; the
    // refusal hold must keep the remaining 299 from hammering a dead port.
    for (const sentence of sentences) enqueue(sentence, undefined, player);
    await speechSettled();
    assert.equal(played.length, 0);
    assert.equal(currentDeferred().length, N);

    // The hold window is real wall-clock time (5 s), so recovery is observed
    // after it elapses, not injected.
    stopDeferredRetry();
    await new Promise((resolve) => setTimeout(resolve, 5200));
    const server = http.createServer((req, res) => {
      if (req.url === "/generate/stream") {
        res.writeHead(200, { "content-type": "application/octet-stream" });
        res.end(validWav());
        return;
      }
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify([{ name: "test-voice", id: "p-test" }]));
    });
    await listen(server, 17991);
    try {
      const retried = await retryDeferredSpeech(undefined, player);
      assert.equal(retried, N);
      await speechSettled();
      assert.deepEqual(played, sentences);
      assert.equal(currentDeferred().length, 0);
      assert.equal(currentSpokenText(), sentences.join(" "));
    } finally {
      server.closeAllConnections();
      server.close();
    }
  } finally {
    stopDeferredRetry();
  }
});

// VA-SOAK-002: a VoiceBox that dies and recovers repeatedly is the realistic
// outage shape (GUI crash, human relaunch, crash again). Each cycle must speak
// every sentence exactly once, in order, and never double or drop across
// cycles. The phase-keyed stub generator lets the whole chain run on the
// injected clock with no network.
test("repeated outage and recovery cycles speak every sentence exactly once", async () => {
  resetSpeechSession();
  const played: string[] = [];
  const player = stubPlayer(played);
  let phase: "down" | "up" = "down";
  const flaky = new Set<string>();
  const gen: ClipGenerator = async (text: string) => {
    if (phase === "down" || flaky.has(text)) return { deferred: true };
    return { clip: { wav: "mock.wav", sentence: text, clip: 1, reference: null } };
  };

  // Cycle 1: a reply arrives during the outage; both sentences are held.
  enqueue("alpha one", gen, player);
  enqueue("alpha two", gen, player);
  await speechSettled();
  assert.equal(currentDeferred().length, 2);

  // Recovery: the whole reply replays, oldest first.
  phase = "up";
  await retryDeferredSpeech(gen, player, Date.now());
  await speechSettled();
  assert.deepEqual(played, ["alpha one", "alpha two"]);

  // Cycle 2: the service dies again with a new reply in flight.
  phase = "down";
  enqueue("beta one", gen, player);
  enqueue("beta two", gen, player);
  enqueue("beta three", gen, player);
  await speechSettled();
  assert.equal(currentDeferred().length, 3);

  // Partial recovery: beta one plays, beta two fails again, and beta three
  // waits behind beta two instead of jumping ahead of it.
  phase = "up";
  flaky.add("beta two");
  await retryDeferredSpeech(gen, player, Date.now());
  await speechSettled();
  assert.deepEqual(played, ["alpha one", "alpha two", "beta one"]);
  assert.deepEqual(currentDeferred().map((item) => item.text), ["beta two", "beta three"]);

  // Final recovery: every held sentence plays exactly once, in order, and
  // nothing from the earlier cycles replays.
  flaky.delete("beta two");
  await retryDeferredSpeech(gen, player, Date.now());
  await speechSettled();
  assert.deepEqual(played, ["alpha one", "alpha two", "beta one", "beta two", "beta three"]);
  assert.equal(currentDeferred().length, 0);
  assert.equal(currentSpeechStatus().expiredSpeech, 0);
  stopDeferredRetry();
});
