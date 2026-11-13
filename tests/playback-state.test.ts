import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
  beginSlot,
  commitBegin,
  commitEnd,
  endSlot,
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
    commitBegin(dir, "11", 1, 1, 11, 111, 1000);
    commitBegin(dir, "22", 1, 1, 22, 222, 1001);
    commitEnd(dir, "22", 1, 1, 1002);
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
