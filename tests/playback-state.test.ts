import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, existsSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
  beginSlot,
  commitBegin,
  commitEnd,
  endSlot,
  pidAlive,
  projectAggregate,
  readSlots,
  sourcesSpeaking,
  wavReference,
  type PlaybackSlot,
} from "../extension/playback-state.ts";

type Vector = {
  name: string;
  now: number;
  alive: number[];
  tail: number;
  slots: Array<Record<string, unknown>> | null;
  legacy: Record<string, unknown> | null;
  expect: boolean;
};

const vectors = JSON.parse(readFileSync(new URL("./playback_vectors.json", import.meta.url), "utf8")) as Vector[];

for (const vector of vectors) {
  test(vector.name, () => {
    const alive = new Set(vector.alive);
    const got = sourcesSpeaking(vector.slots, vector.legacy, vector.now, (pid) => alive.has(pid), vector.tail);
    assert.equal(got, vector.expect);
  });
}

test("ending another session leaves the first clip playing", () => {
  const dir = mkdtempSync(join(tmpdir(), "va-play-"));
  try {
    const alive = new Set([11, 22, 111, 222]);
    const isAlive = (pid: number) => alive.has(pid);
    commitBegin(dir, "11", 1, 1, 11, 111, 1000, null, undefined, isAlive);
    commitBegin(dir, "22", 1, 1, 22, 222, 1001, null, undefined, isAlive);
    commitEnd(dir, "22", 1, 1, 1002, isAlive);
    const first = JSON.parse(readFileSync(join(dir, "tts-playing", "11.json"), "utf8")) as PlaybackSlot;
    const aggregate = JSON.parse(readFileSync(join(dir, "tts-playing.json"), "utf8")) as { playing: boolean; pid?: number };
    assert.equal(first.playing, true);
    assert.equal(first.clip, 1);
    assert.equal(aggregate.playing, true);
    assert.equal(aggregate.pid, 111);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("an older end does not clear the newer clip", () => {
  const started = beginSlot(beginSlot(null, 1, 1, 11, 111, 1000), 1, 2, 11, 112, 1001);
  const ended = endSlot(started, 1, 1, 1002);
  assert.equal(ended?.clip, 2);
  assert.equal(ended?.playing, true);
  assert.equal(ended?.reason, "begin");
});

test("ending the current clip records the reason", () => {
  const ended = endSlot(beginSlot(null, 1, 1, 11, 111, 1000), 1, 1, 1002);
  assert.equal(ended?.playing, false);
  assert.equal(ended?.reason, "end");
  assert.equal(ended?.ended_at, 1002);
  assert.equal(ended?.writer_pid, 11);
});

function pcmWav(samples: number, rate: number): Buffer {
  const dataBytes = samples * 2;
  const buf = Buffer.alloc(44 + dataBytes);
  buf.write("RIFF", 0);
  buf.writeUInt32LE(36 + dataBytes, 4);
  buf.write("WAVE", 8);
  buf.write("fmt ", 12);
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20);
  buf.writeUInt16LE(1, 22);
  buf.writeUInt32LE(rate, 24);
  buf.writeUInt32LE(rate * 2, 28);
  buf.writeUInt16LE(2, 32);
  buf.writeUInt16LE(16, 34);
  buf.write("data", 36);
  buf.writeUInt32LE(dataBytes, 40);
  return buf;
}

test("the playback wav is the render reference, and ending the clip drops it", () => {
  const bytes = pcmWav(160, 16000);
  const wav = "/tmp/omp-vb-test-1.wav";
  const reference = wavReference(bytes, wav);
  assert.deepEqual(reference, { sample_rate: 16000, channels: 1, frames: 160, wav });
  assert.equal(wavReference(Buffer.from("not a wav"), wav), null);
  const started = beginSlot(null, 1, 1, 11, 111, 1000, reference);
  assert.deepEqual(started.reference, reference);
  assert.equal(started.playback_rate, undefined);
  const rated = beginSlot(null, 1, 1, 11, 111, 1000, reference, 1.18);
  assert.equal(rated.playback_rate, 1.18);
  assert.equal(beginSlot(null, 1, 1, 11, 111, 1000, reference, 3).playback_rate, undefined);
  const ended = endSlot(started, 1, 1, 1001);
  assert.equal(ended?.playing, false);
  assert.equal(ended?.reference, undefined);
});

test("pidAlive sees a killed process as dead", async () => {
  const child = spawn("sleep", ["5"]);
  const pid = child.pid as number;
  assert.equal(pidAlive(pid), true);
  child.kill("SIGKILL");
  const { promise, resolve } = Promise.withResolvers<void>();
  child.on("exit", resolve);
  await promise;
  assert.equal(pidAlive(pid), false);
});

test("readSlots prunes dead sessions outside the reverb tail", () => {
  const dir = mkdtempSync(join(tmpdir(), "va-prune-"));
  try {
    const slotDir = join(dir, "tts-playing");
    mkdirSync(slotDir);
    const now = 1000;
    writeFileSync(join(slotDir, "11.json"), JSON.stringify({ playing: false, ended_at: now - 100, reason: "end" }));
    writeFileSync(join(slotDir, "22.json"), JSON.stringify({ playing: true, writer_pid: 22, afplay_pid: 222, started_at: now - 100 }));
    writeFileSync(join(slotDir, "33.json"), JSON.stringify({ playing: false, ended_at: now - 0.3, reason: "end" }));
    writeFileSync(join(slotDir, "44.json"), JSON.stringify({ playing: true, writer_pid: 44, lease_until: now + 60, reason: "begin" }));
    const alive = new Set([44]);
    const slots = readSlots(dir, (pid) => alive.has(pid), now);
    assert.equal(slots.length, 2);
    assert.ok(!existsSync(join(slotDir, "11.json")));
    assert.ok(!existsSync(join(slotDir, "22.json")));
    assert.ok(existsSync(join(slotDir, "33.json")));
    assert.ok(existsSync(join(slotDir, "44.json")));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("a publish prunes a crashed session slot from the projection", async () => {
  const dir = mkdtempSync(join(tmpdir(), "va-prune-proj-"));
  try {
    const child = spawn("sleep", ["5"]);
    const deadPid = child.pid as number;
    child.kill("SIGKILL");
    const { promise, resolve } = Promise.withResolvers<void>();
    child.on("exit", resolve);
    await promise;
    const slotDir = join(dir, "tts-playing");
    mkdirSync(slotDir);
    const now = Date.now() / 1000;
    writeFileSync(
      join(slotDir, `${deadPid}.json`),
      JSON.stringify({ playing: true, writer_pid: deadPid, afplay_pid: deadPid, started_at: now - 100 }),
    );
    // The projection frozen at the crash's pid must be re-derived on publish.
    writeFileSync(join(dir, "tts-playing.json"), JSON.stringify({ playing: true, pid: deadPid }));
    commitBegin(dir, String(process.pid), 1, 1, process.pid, process.pid, now);
    const aggregate = JSON.parse(readFileSync(join(dir, "tts-playing.json"), "utf8")) as { playing: boolean; pid?: number };
    assert.equal(aggregate.playing, true);
    assert.equal(aggregate.pid, process.pid);
    assert.ok(!existsSync(join(slotDir, `${deadPid}.json`)));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("projectAggregate requires a live afplay or writer witness", () => {
  const dead = (_pid: number) => false;
  const alive22 = (pid: number) => pid === 22;
  assert.deepEqual(
    projectAggregate([{ playing: true, started_at: 10, afplay_pid: 22 }], alive22, 100),
    { playing: true, started_at: 10, pid: 22 },
  );
  assert.deepEqual(
    projectAggregate([{ playing: true, started_at: 10, afplay_pid: 22 }], dead, 100),
    { playing: false },
  );
  assert.deepEqual(
    projectAggregate([{ playing: true, started_at: 10, writer_pid: 22, lease_until: 1000 }], alive22, 100),
    { playing: true, started_at: 10 },
  );
  assert.deepEqual(
    projectAggregate([{ playing: true, started_at: 10, writer_pid: 22, lease_until: 1000 }], dead, 100),
    { playing: false },
  );
});
