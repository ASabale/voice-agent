import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import {
  beginReplyStopsPlayback,
  currentSpeechEpoch,
  isNewReply,
  isSpokenChunk,
  onTurnStart,
  stopPlayback,
  messageKey,
  noteUnspoken,
  playbackHeard,
  isConnectionRefusal,
  queuedAfterRewrite,
  refusalHold,
  rotateLogFile,
  speechAfterSpoken,
  speechLogRecord,
} from "../extension/voicebox-speech.ts";

test("a short sentence inside an older chunk is not already spoken", () => {
  const chunks = ["The cat sat. Then he left."];
  assert.equal(isSpokenChunk(chunks, "sat."), false);
  assert.equal(isSpokenChunk(chunks, "The cat sat. Then he left."), true);
});

test("a join of consecutive chunks is already spoken", () => {
  const chunks = ["The cat sat.", "Then he left."];
  assert.equal(isSpokenChunk(chunks, "The cat sat."), true);
  assert.equal(isSpokenChunk(chunks, "The cat sat. Then he left."), true);
  assert.equal(isSpokenChunk(chunks, "Then he left."), true);
});

test("the same sentence can be admitted once the chunk list is cleared", () => {
  const chunks = ["Done."];
  assert.equal(isSpokenChunk(chunks, "Done."), true);
  assert.equal(isSpokenChunk([], "Done."), false);
});

test("a prefix rewrite does not ask the caller to forget spoken chunks", () => {
  const queued = queuedAfterRewrite(
    "The file is ready. ",
    "The file is ready.",
    "The path changed. Open it next.",
  );
  assert.equal(queued, "");
  assert.equal(isSpokenChunk(["The file is ready."], "The file is ready."), true);
  assert.equal(isSpokenChunk(["The file is ready."], "The path changed."), false);
});

test("an aligned rewrite keeps the covered prefix", () => {
  const spoken = "The file is ready. Open it next.";
  const plain = "Note. The file is ready. Open it next. Then stop.";
  const queued = queuedAfterRewrite("The file is ready. ", spoken, plain);
  assert.equal(queued.startsWith("Note. The file is ready."), true);
  assert.equal(plain.startsWith(queued), true);
});

test("a turn start does not abort the playing clip", () => {
  const epoch = currentSpeechEpoch();
  onTurnStart();
  assert.equal(currentSpeechEpoch(), epoch);
  stopPlayback();
  assert.equal(currentSpeechEpoch(), epoch + 1);
  onTurnStart();
  assert.equal(currentSpeechEpoch(), epoch + 1);
});

test("a longer sentence does not speak the words already queued", () => {
  assert.equal(speechAfterSpoken(["I will leave."], "I will leave the player."), "the player");
  assert.equal(speechAfterSpoken(["I will leave the player."], "I will leave the player."), "");
  assert.equal(speechAfterSpoken(["I will leave."], "A different line."), "A different line.");
  assert.equal(speechAfterSpoken([], "I will leave."), "I will leave.");
  assert.equal(
    speechAfterSpoken(["The reply was cut.", "I will leave."], "I will leave the player."),
    "the player",
  );
});

test("a continued reply with a new message id does not stop playback", () => {
  assert.equal(
    beginReplyStopsPlayback("msg-1", "msg-2", "The file is ready.", "The file is ready. Open it next."),
    false,
  );
  assert.equal(
    beginReplyStopsPlayback("msg-1", "msg-2", "The file is ready. Open it next.", "The file is ready."),
    false,
  );
  assert.equal(
    beginReplyStopsPlayback("msg-1", "msg-2", "The file is ready.", "A different answer."),
    true,
  );
  assert.equal(beginReplyStopsPlayback("msg-1", "msg-1", "The file is ready.", "A different answer."), false);
  assert.equal(beginReplyStopsPlayback("msg-1", "msg-2", "", "The file is ready."), true);
  assert.equal(
    beginReplyStopsPlayback("msg-1", "msg-2", "I will leave.", "I will leave the player."),
    false,
  );
  assert.equal(
    beginReplyStopsPlayback("msg-1", "msg-2", "I will leave the player.", "I will leave."),
    false,
  );
  assert.equal(
    beginReplyStopsPlayback("msg-1", "msg-2", "I will leave the player.", "A different answer."),
    true,
  );
});

test("a new assistant message id starts a fresh reply", () => {
  assert.equal(isNewReply("msg-1", "msg-2"), true);
  assert.equal(isNewReply("msg-1", "msg-1"), false);
  assert.equal(isNewReply("", "msg-1"), false);
  assert.equal(messageKey({ id: "msg-2", role: "assistant" }), "msg-2");
  assert.equal(messageKey({ role: "assistant" }), "");
});

test("a refused VoiceBox holds the next request until the retry time", () => {
  assert.equal(refusalHold(10, 15), true);
  assert.equal(refusalHold(15, 15), false);
  assert.equal(isConnectionRefusal(new TypeError("ECONNREFUSED")), true);
  const wrapped = new TypeError("fetch failed");
  (wrapped as { cause?: unknown }).cause = new Error("connect ECONNREFUSED 127.0.0.1:17493");
  assert.equal(isConnectionRefusal(wrapped), true);
  assert.equal(isConnectionRefusal(new Error("http 500")), false);
});

test("a player error is not heard and a kill signal is", () => {
  assert.equal(playbackHeard(0, null, false), true);
  assert.equal(playbackHeard(1, null, false), false);
  assert.equal(playbackHeard(null, "SIGKILL", false), true);
  assert.equal(playbackHeard(null, null, true), false);
});

test("a chunk that never played is not treated as spoken", () => {
  const failed = "The file is ready.";
  const later = "Open it next.";
  const held = noteUnspoken([failed, later], [], `${failed} ${later}`, failed);
  assert.deepEqual(held.inflight, [later]);
  assert.equal(held.queued, `${failed} ${later}`);
  assert.equal(held.forget, true);
  assert.equal(isSpokenChunk(held.inflight, failed), false);
  assert.equal(isSpokenChunk(held.inflight, later), true);
  const tail = noteUnspoken([failed], [], failed, failed);
  assert.deepEqual(tail.inflight, []);
  assert.equal(tail.queued, "");
  const kept = noteUnspoken([failed], [failed], failed, failed);
  assert.equal(kept.forget, false);
  assert.equal(kept.queued, "");
});

test("a speech log rotates once it passes the limit and keeps one backup", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "omp-speech-log-"));
  const file = path.join(dir, "speech.log");
  fs.writeFileSync(file, "old-line\n");
  assert.equal(rotateLogFile(file, 4), true);
  assert.equal(fs.existsSync(file), false);
  assert.equal(fs.readFileSync(`${file}.1`, "utf8"), "old-line\n");
  fs.writeFileSync(file, "next-line\n");
  assert.equal(rotateLogFile(file, 4), true);
  assert.equal(fs.readFileSync(`${file}.1`, "utf8"), "next-line\n");
  assert.equal(rotateLogFile(file, 100), false);
  fs.rmSync(dir, { recursive: true, force: true });
});

test("a speech log record keeps the length and the reason, not the sentence", () => {
  const sentence = "The weather is fine today.";
  const hidden = speechLogRecord("failed", sentence, { reason: "refused" }, false);
  assert.equal("text" in hidden, false);
  assert.equal(hidden.chars, sentence.length);
  assert.equal(hidden.event, "failed");
  assert.equal(hidden.reason, "refused");
  const shown = speechLogRecord("failed", sentence, { reason: "refused" }, true);
  assert.equal(shown.text, sentence);
  const fallback = speechLogRecord("failed", sentence, { reason: "refused" });
  if (process.env.OMP_VOICE_LOG_TEXT === "1") assert.equal(fallback.text, sentence);
  else assert.equal("text" in fallback, false);
});
