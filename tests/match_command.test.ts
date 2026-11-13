import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  VoiceSession,
  deduplicateHandyPaste,
  forSpeech,
  matchCommand,
  takeSentences,
} from "../extension/voicebox-speech.ts";

const grammar = JSON.parse(readFileSync(new URL("../grammar.json", import.meta.url), "utf8"));
const vectors = JSON.parse(readFileSync(new URL("./command_vectors.json", import.meta.url), "utf8")) as Array<{
  raw: string;
  action: string | null;
  prefix: string;
  phrase: string;
}>;

for (const vector of vectors) {
  test(`matchCommand ${vector.raw}`, () => {
    const matched = matchCommand(vector.raw, grammar);
    if (vector.action === null) {
      assert.equal(matched, null);
      return;
    }
    assert.ok(matched);
    assert.equal(matched.action, vector.action);
    assert.equal(matched.prefix, vector.prefix);
    assert.equal(matched.phrase, vector.phrase);
  });
}

test("longest suffix beats a shorter stop", () => {
  const matched = matchCommand("stop listening", grammar);
  assert.equal(matched?.phrase, "stop listening");
});

test("forSpeech strips a code fence and keeps the sentence", () => {
  const spoken = forSpeech("See this.\n```\nls -la\n```\nDone.");
  assert.equal(spoken.includes("ls -la"), false);
  assert.equal(spoken.includes("Done"), true);
});

test("forSpeech returns the same string for the same text", () => {
  const raw = "Hello there.";
  assert.equal(forSpeech(raw), forSpeech(raw));
});

test("forSpeech rewrites the word stop so the room mic does not hear the pause command", () => {
  const spoken = forSpeech("after the stop");
  assert.equal(spoken, "after the the pause command");
  assert.equal(spoken.length, 27);
});

test("forSpeech leaves pause, resume, and hold on as spoken words", () => {
  assert.equal(forSpeech("please pause"), "please pause");
  assert.equal(forSpeech("hold on a second"), "hold on a second");
  assert.equal(forSpeech("resume playback"), "resume playback");
});

test("takeSentences keeps a finished sentence and waits on a stub", () => {
  assert.deepEqual(takeSentences("Hello there. Still going", false), ["Hello there."]);
  assert.deepEqual(takeSentences("Hello there. Still going on", true), ["Hello there.", "Still going on"]);
});

test("deduplicateHandyPaste drops a transcript already pasted at the end", () => {
  assert.equal(deduplicateHandyPaste("draft send prompt", "send prompt"), "draft");
  assert.equal(deduplicateHandyPaste("draft", "send prompt"), "draft");
});

test("VoiceSession instances do not share spoken state", () => {
  const first = new VoiceSession();
  const second = new VoiceSession();
  first.spoken.add("hello");
  first.spokenText = "hello";
  assert.equal(second.spoken.size, 0);
  assert.equal(second.spokenText, "");
  first.reset();
  assert.equal(first.spoken.size, 0);
  assert.equal(first.spokenText, "");
});
