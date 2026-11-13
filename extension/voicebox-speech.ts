// Speak sentence by sentence via VoiceBox and accept hands-free dictated chunks
// + voice submit ("send prompt") + Barge-in from omp-voice-controller.
//
// One HTTP server per omp session, on an ephemeral 127.0.0.1 port.
// The controller reads ~/.local/state/omp-voice/sessions/<pid>.json and
// sends /transcript to the focused session, not to whichever process
// happened to bind a single shared port.
// - GET  /status     -> { speaking, draft, draftLength, pid }
// - POST /barge-in   -> kills active afplay and flushes pending TTS queue
// - POST /transcript -> { text } -> appends to OMP editor Draft or submits on command phrase

import { type ChildProcess, spawn } from "node:child_process";
import * as fs from "node:fs";
import * as http from "node:http";
import * as os from "node:os";
import * as path from "node:path";

const API = "http://127.0.0.1:17493";
const BRIDGE_HOST = "127.0.0.1";
const HTTP_BODY_CAP = 65536;
let boundBridgePort = 0;
function ttsModelSize(): "0.6B" | "1.7B" {
  try {
    const raw = fs
      .readFileSync(path.join(os.homedir(), ".local", "state", "omp-voice", "tts-model"), "utf8")
      .trim();
    if (raw === "0.6B" || raw === "1.7B") return raw;
  } catch {
    // controller writes this when Strata starts or stops
  }
  return "0.6B";
}

function profileName(): string {
  const fromEnv = process.env.OMP_VOICEBOX_PROFILE?.trim();
  if (fromEnv) return fromEnv;
  try {
    return fs
      .readFileSync(path.join(os.homedir(), ".local", "state", "omp-voice", "profile"), "utf8")
      .trim();
  } catch {
    return "";
  }
}

export class VoiceSession {
  playbackRate = Number(process.env.OMP_VOICE_RATE ?? "1.18") || 1.18;
  queued = "";
  readonly spoken = new Set<string>();
  // Sentences whose audio finished. Aborted clips stay out of this list so a later
  // reply can speak them. `inflight` is the queue that stopPlayback rolls back.
  readonly committed: string[] = [];
  readonly inflight: string[] = [];
  spokenText = "";
  genTail: Promise<void> = Promise.resolve();
  playTail: Promise<void> = Promise.resolve();
  speechEpoch = 0;
  lastPlain = "";
  // Set on barge-in to the reply that was playing. Later deltas of that same
  // reply must not be spoken after Handy closes. A different reply clears it.
  droppedPlain: string | null = null;
  clipSeq = 0;
  activeAfplay: ChildProcess | null = null;
  activeAbort: AbortController | null = null;
  isSpeaking = false;
  readonly loggedOnce = new Set<string>();

  reset(): void {
    this.playbackRate = Number(process.env.OMP_VOICE_RATE ?? "1.18") || 1.18;
    this.queued = "";
    this.spoken.clear();
    this.committed.length = 0;
    this.inflight.length = 0;
    this.spokenText = "";
    this.genTail = Promise.resolve();
    this.playTail = Promise.resolve();
    this.speechEpoch = 0;
    this.lastPlain = "";
    this.droppedPlain = null;
    this.clipSeq = 0;
    this.activeAfplay = null;
    this.activeAbort = null;
    this.isSpeaking = false;
    this.loggedOnce.clear();
  }
}

const session = new VoiceSession();

export function resetSpeechSession(): void {
  session.reset();
}

function logOnce(key: string, err: unknown): void {
  if (session.loggedOnce.has(key)) return;
  session.loggedOnce.add(key);
  logSpeech("error", key, { error: String(err) });
}

function writeJsonAtomic(filePath: string, value: unknown): void {
  const tmp = `${filePath}.${process.pid}.tmp`;
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(tmp, JSON.stringify(value));
  fs.renameSync(tmp, filePath);
}

function readBody(req: http.IncomingMessage, onEnd: (body: string) => void): void {
  let body = "";
  let tooBig = false;
  req.on("data", (chunk) => {
    if (tooBig) return;
    body += String(chunk);
    if (body.length > HTTP_BODY_CAP) {
      tooBig = true;
      req.destroy();
    }
  });
  req.on("end", () => {
    if (!tooBig) onEnd(body);
  });
}

export type TranscriptAction =
  | { action: "sent"; draft: string; strippedCommand: string }
  | { action: "paused"; draft: string; strippedCommand: string }
  | { action: "cancelled"; draft: string; strippedCommand: string }
  | { action: "scratched"; draft: string; strippedCommand: string }
  | { action: "cleared"; draft: string; strippedCommand: string }
  | { action: "appended"; draft: string }
  | { action: "noop"; draft: string };

type GrammarAction = {
  action: "sent" | "paused" | "cancelled" | "scratched" | "cleared";
  slots: string[][];
};
type CommandGrammar = { wake: string[][]; actions: GrammarAction[] };

let commandGrammar: CommandGrammar | null = null;

function loadCommandGrammar(): CommandGrammar {
  if (commandGrammar) return commandGrammar;
  const grammarPath = path.join(os.homedir(), ".local", "share", "omp-voice", "grammar.json");
  commandGrammar = JSON.parse(fs.readFileSync(grammarPath, "utf8")) as CommandGrammar;
  commandGrammar.wake.sort((a, b) => b.length - a.length);
  return commandGrammar;
}

export type CommandMatch = { action: GrammarAction["action"]; prefix: string; phrase: string };

function sameTokens(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((token, i) => token === b[i]);
}

function slotsMatch(words: string[], slots: string[][]): boolean {
  return words.length === slots.length && slots.every((choices, i) => choices.includes(words[i] ?? ""));
}

/** Longest suffix that is an optional wake plus one word from each slot, in order. */
export function matchCommand(raw: string, grammar: CommandGrammar = loadCommandGrammar()): CommandMatch | null {
  const tokens = raw
    .toLowerCase()
    .replace(/[\s.,!?;:]+/g, " ")
    .trim()
    .split(" ")
    .filter(Boolean);
  let best: { span: number; action: GrammarAction["action"]; content: string[] } | null = null;
  for (let i = 0; i < tokens.length; i++) {
    const span = tokens.slice(i);
    for (const wake of [[] as string[], ...grammar.wake]) {
      if (wake.length > 0 && !sameTokens(span.slice(0, wake.length), wake)) continue;
      const rest = span.slice(wake.length);
      for (const group of grammar.actions) {
        if (!slotsMatch(rest, group.slots)) continue;
        if (best === null || span.length > best.span) {
          best = { span: span.length, action: group.action, content: tokens.slice(0, i) };
        }
      }
    }
  }
  if (!best) return null;
  const phraseTokens = tokens.slice(tokens.length - best.span);
  return { action: best.action, prefix: best.content.join(" "), phrase: phraseTokens.join(" ") };
}

export function deduplicateHandyPaste(currentEditorText: string, rawTranscript: string): string {
  const trimmedRaw = rawTranscript.trim();
  if (!trimmedRaw) return currentEditorText;
  const trimmedEditor = currentEditorText.trimEnd();
  if (trimmedEditor.endsWith(trimmedRaw)) {
    return trimmedEditor.slice(0, trimmedEditor.length - trimmedRaw.length).trimEnd();
  }
  return currentEditorText;
}

export function parseVoiceTranscript(
  rawTranscript: string,
  currentDraft: string,
  previousDraft?: string,
): { result: TranscriptAction; nextEditorText: string; submitText?: string } {
  const baseDraft = deduplicateHandyPaste(currentDraft, rawTranscript);
  const cleaned = rawTranscript.replace(/\s+/g, " ").trim();
  if (!cleaned) {
    return {
      result: { action: "noop", draft: baseDraft },
      nextEditorText: baseDraft,
    };
  }

  const command = matchCommand(cleaned);
  if (command?.action === "cleared") {
    return {
      result: { action: "cleared", draft: "", strippedCommand: command.phrase },
      nextEditorText: "",
    };
  }
  if (command?.action === "scratched") {
    const revertedDraft = command.prefix
      ? baseDraft
      : previousDraft !== undefined
        ? previousDraft
        : baseDraft.replace(/(?:^|\s+)\S+[^.!?\n]*[.!?]*\s*$/, "").trimEnd();
    return {
      result: { action: "scratched", draft: revertedDraft, strippedCommand: command.phrase },
      nextEditorText: revertedDraft,
    };
  }
  if (command?.action === "cancelled") {
    return {
      result: { action: "cancelled", draft: baseDraft, strippedCommand: command.phrase },
      nextEditorText: baseDraft,
    };
  }
  if (command?.action === "paused") {
    const nextDraft = command.prefix
      ? baseDraft.trim()
        ? `${baseDraft.trimEnd()} ${command.prefix}`
        : command.prefix
      : baseDraft;
    return {
      result: { action: "paused", draft: nextDraft, strippedCommand: command.phrase },
      nextEditorText: nextDraft,
    };
  }
  if (command?.action === "sent") {
    const combined = command.prefix
      ? baseDraft.trim()
        ? `${baseDraft.trimEnd()} ${command.prefix}`
        : command.prefix
      : baseDraft.trim();
    return {
      result: { action: "sent", draft: combined, strippedCommand: command.phrase },
      nextEditorText: "",
      submitText: combined,
    };
  }

  // 4. Normal chunk -> append to Draft without submitting
  const nextDraft = baseDraft.trim()
    ? `${baseDraft.trimEnd()} ${cleaned}`
    : cleaned;
  return {
    result: { action: "appended", draft: nextDraft },
    nextEditorText: nextDraft,
  };
}

export function continuesDroppedReply(dropped: string | null, plain: string): boolean {
  if (dropped === null || dropped.length === 0) return false;
  return plain.startsWith(dropped) || dropped.startsWith(plain);
}

function rollbackInflight(): void {
  for (const sentence of session.inflight) session.spoken.delete(sentence);
  session.inflight.length = 0;
  session.spokenText = session.committed.join(" ");
}

function commitSpoken(sentence: string): void {
  const index = session.inflight.indexOf(sentence);
  if (index >= 0) session.inflight.splice(index, 1);
  if (!session.committed.includes(sentence)) session.committed.push(sentence);
  session.spoken.add(sentence);
  session.spokenText = [...session.committed, ...session.inflight].join(" ");
}

export function stopPlayback(): boolean {
  const wasSpeaking = session.isSpeaking || session.activeAfplay !== null || session.activeAbort !== null;
  session.speechEpoch++;
  // A new turn or a barge-in aborts clips that have not finished. Forgetting
  // them here is what left the next reply silent when it repeated that text.
  rollbackInflight();
  session.queued = "";
  session.genTail = Promise.resolve();
  session.playTail = Promise.resolve();
  if (session.activeAbort) {
    try {
      session.activeAbort.abort();
    } catch {
      // ignore
    }
    session.activeAbort = null;
  }
  if (session.activeAfplay) {
    try {
      session.activeAfplay.kill("SIGTERM");
    } catch {
      // ignore
    }
    session.activeAfplay = null;
  }
  session.isSpeaking = false;
  const statePath = path.join(os.homedir(), ".local", "state", "omp-voice", "tts-playing.json");
  try {
    fs.mkdirSync(path.dirname(statePath), { recursive: true });
    writeJsonAtomic(statePath, { playing: false, ended_at: Date.now() / 1000 });
  } catch (err) {
    logOnce("tts-playing-write", err);
  }
  return wasSpeaking;
}

export function bargeIn(): boolean {
  // A real interrupt (wake, fn, typed stop). Remember the reply so it does not resume.
  // Do not forget sentences already spoken: a sub-agent turn replays the parent text,
  // and clearing this set makes that text play again from the start.
  session.droppedPlain = session.lastPlain.length > 0 ? session.lastPlain : null;
  return stopPlayback();
}

function textBlocks(message: unknown): string[] {
  if (!message || typeof message !== "object") return [];
  const content = "content" in message ? message.content : undefined;
  if (typeof content === "string") return [content];
  if (!Array.isArray(content)) return [];
  let start = 0;
  content.forEach((block, index) => {
    if (!block || typeof block !== "object" || !("type" in block)) return;
    const type = String(block.type);
    if (type === "toolCall" || type === "tool_use") start = index + 1;
  });
  const lines: string[] = [];
  for (const block of content.slice(start)) {
    if (!block || typeof block !== "object" || !("type" in block) || !("text" in block)) continue;
    if (block.type === "text" && typeof block.text === "string") lines.push(block.text);
  }
  return lines;
}

let speechCacheRaw = "";
let speechCachePlain = "";

export function forSpeech(raw: string): string {
  if (raw === speechCacheRaw) return speechCachePlain;
  // 1. If the assistant emitted a dedicated spoken summary (<voice>...</voice> or **Voice:** ...),
  //    speak ONLY that human-friendly summary instead of reading tables/paths/commands out loud!
  const voiceTagMatch = raw.match(/<voice>([\s\S]*?)<\/voice>/i);
  const voiceLineMatch = !voiceTagMatch
    ? raw.match(/(?:^|\n)\s*(?:\*\*|__)?(?:🔊\s*)?(?:Voice|Spoken|Audio\s+summary)(?:\*\*|__)?\s*:\s*([^\n]+(?:\n(?![\s\n]*[-*#|`<\d])[^\n]+)*)/i)
    : null;
  const source = voiceTagMatch ? voiceTagMatch[1]! : voiceLineMatch ? voiceLineMatch[1]! : raw;

  const plain = source
    .replace(/\r\n/g, "\n")
    // Strip fenced code blocks and markdown tables completely
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/^[ \t]*\|.*\|[ \t]*$/gm, " ")
    // Strip URLs and file:// links
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/https?:\/\/\S+/gi, " ")
    .replace(/file:\/\/\S+/gi, " ")
    // Collapse long unix paths (/Users/name/foo/bar.ts -> bar.ts) so TTS doesn't read every slash
    .replace(/(?:~|\/Users\/[A-Za-z0-9._-]+|\/opt\/homebrew)(?:\/[A-Za-z0-9._-]+)+\/([A-Za-z0-9._-]+)/g, "$1")
    // Strip ISO timestamps, log bracket timestamps ([2026-11-07 17:30:11]), and hex hashes/UUIDs
    .replace(/\[\d{4}-\d{2}-\d{2}[^\]]*\]/g, " ")
    .replace(/\b\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?Z?)?\b/g, " ")
    .replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi, " ")
    // Clean parenthetical metadata like (pid 32894) or (score=0.94) when reading full prose
    .replace(/\((?:pid|score|vad|rms|id|line|lines)\s*[^)]*\)/gi, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    // Strip leading emojis/bullet symbols and pronunciation-heavy paths/identifiers
    .replace(/[\p{Emoji_Presentation}\p{Extended_Pictographic}]/gu, " ")
    // Prevent VoiceBox TTS from ever speaking the wake word or command phrases out loud into the room mic
    .replace(/\bhey[\s,]+jarvis\b/gi, "the wake phrase")
    .replace(/\bjarvis\b/gi, "the wake word")
    .replace(/\bsend[\s,]+(prompt|that|it|message)\b/gi, "the send phrase")
    .replace(/\bprompt[\s,]+this\b/gi, "the send phrase")
    .replace(/\bstop(?:[\s,]+(?:it|that|talking|speaking|listening|dictation))?\b/gi, "the pause command")
    .replace(/\b(scratch|undo|delete|erase)[\s,]+(that|last|all)\b/gi, "the undo phrase")
    .replace(/\bclear[\s,]+(draft|all|text|box)\b/gi, "the clear phrase")
    .replace(/[*_~>|]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  speechCacheRaw = raw;
  speechCachePlain = plain;
  return plain;
}

function endsSentence(text: string, index: number, flush: boolean): boolean {
  const mark = text[index];
  if (mark !== "." && mark !== "!" && mark !== "?" && mark !== ":" && mark !== ";") return false;
  const prev = text[index - 1] ?? "";
  const next = text[index + 1] ?? "";
  // 1.25, or a streamed "1." whose next digit has not arrived yet, or "127.0.0.1:17494"
  if ((mark === "." || mark === ":") && /\d/.test(prev) && (/\d/.test(next) || (next === "" && !flush))) return false;
  if (next !== "" && !/\s/.test(next)) return false;
  return text.slice(0, index).trim().length >= 2;
}

export function takeSentences(fresh: string, flush: boolean): string[] {
  const out: string[] = [];
  let rest = fresh.trimStart();
  while (rest.length >= 12) {
    let cut = -1;
    for (let i = 0; i < rest.length; i++) {
      if (!endsSentence(rest, i, flush)) continue;
      cut = i + 1;
      while (rest[cut] === " ") cut++;
      break;
    }
    if (cut === -1) break;
    out.push(rest.slice(0, cut).trim());
    rest = rest.slice(cut).trimStart();
  }
  if (flush && rest.length >= 8) {
    out.push(rest.trim());
  }
  return out;
}

let cachedProfileId = "";
let cachedProfileName = "";

async function profileId(): Promise<string | undefined> {
  const name = profileName();
  if (!name) return undefined;
  if (cachedProfileId && cachedProfileName === name) return cachedProfileId;
  const res = await fetch(`${API}/profiles`);
  const rows: unknown = await res.json().catch(() => null);
  if (!Array.isArray(rows)) return undefined;
  for (const row of rows) {
    if (!row || typeof row !== "object" || !("name" in row) || !("id" in row)) continue;
    if (row.name === name && typeof row.id === "string") {
      cachedProfileName = name;
      cachedProfileId = row.id;
      return row.id;
    }
  }
  return undefined;
}

function logSpeech(event: string, text: string, extra: Record<string, unknown> = {}): void {
  try {
    const dir = path.join(os.homedir(), ".local", "state", "omp-voice");
    fs.mkdirSync(dir, { recursive: true });
    fs.appendFileSync(
      path.join(dir, "speech.log"),
      `${JSON.stringify({ t: new Date().toISOString(), event, chars: text.length, text, ...extra })}\n`,
    );
  } catch {
    // ignore
  }
}

async function generate(text: string, epoch: number): Promise<{ wav: string; sentence: string } | undefined> {
  if (epoch !== session.speechEpoch) {
    logSpeech("dropped", text, { reason: "epoch" });
    return undefined;
  }
  const controller = new AbortController();
  session.activeAbort = controller;
  const timer = setTimeout(() => controller.abort(), 90000);
  try {
    const id = await profileId();
    if (!id || epoch !== session.speechEpoch) {
      logSpeech("dropped", text, { reason: id ? "epoch" : "profile" });
      return undefined;
    }
    logSpeech("requested", text);
    // Use /generate/stream directly to eliminate 200ms polling latency + SQLite history churn
    const res = await fetch(`${API}/generate/stream`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        profile_id: id,
        text,
        language: "en",
        engine: "qwen",
        model_size: ttsModelSize(),
        personality: false,
        crossfade_ms: 25,
      }),
      signal: controller.signal,
    });
    if (!res.ok) {
      logSpeech("failed", text, { reason: "http", status: res.status });
      return undefined;
    }
    const arrayBuf = await res.arrayBuffer();
    if (epoch !== session.speechEpoch || arrayBuf.byteLength < 100) {
      logSpeech("failed", text, { reason: epoch !== session.speechEpoch ? "epoch" : "short-audio", bytes: arrayBuf.byteLength });
      return undefined;
    }
    const wavPath = path.join(os.tmpdir(), `omp-vb-${process.pid}-${++session.clipSeq}.wav`);
    fs.writeFileSync(wavPath, Buffer.from(arrayBuf));
    logSpeech("generated", text, { bytes: arrayBuf.byteLength, wav: path.basename(wavPath) });
    return { wav: wavPath, sentence: text };
  } catch (err) {
    logSpeech("failed", text, { reason: String(err) });
    return undefined;
  } finally {
    clearTimeout(timer);
    if (session.activeAbort === controller) session.activeAbort = null;
  }
}

async function play(clip: { wav: string; sentence: string }, epoch: number): Promise<void> {
  if (epoch !== session.speechEpoch) {
    try {
      fs.unlinkSync(clip.wav);
    } catch {
      // ignore
    }
    return;
  }
  session.isSpeaking = true;
  const { promise, resolve } = Promise.withResolvers<void>();
  const args = session.playbackRate !== 1.0
    ? ["-r", String(session.playbackRate), "-q", "1", clip.wav]
    : [clip.wav];
  if (epoch !== session.speechEpoch) {
    session.isSpeaking = false;
    try {
      fs.unlinkSync(clip.wav);
    } catch {
      // ignore
    }
    return;
  }
  const child = spawn("afplay", args, { stdio: "ignore" });
  if (epoch !== session.speechEpoch) {
    try {
      child.kill("SIGKILL");
    } catch {
      // ignore
    }
    session.isSpeaking = false;
    try {
      fs.unlinkSync(clip.wav);
    } catch {
      // ignore
    }
    return;
  }
  session.activeAfplay = child;
  const statePath = path.join(os.homedir(), ".local", "state", "omp-voice", "tts-playing.json");
  try {
    fs.mkdirSync(path.dirname(statePath), { recursive: true });
    writeJsonAtomic(statePath, { playing: true, pid: child.pid, started_at: Date.now() / 1000 });
  } catch (err) {
    logOnce("tts-playing-write", err);
  }
  let settled = false;
  const finish = () => {
    if (settled) return;
    settled = true;
    resolve();
  };
  const watchdog = setTimeout(() => {
    try {
      child.kill("SIGKILL");
    } catch {
      // ignore
    }
    finish();
  }, 45000);
  child.on("close", finish);
  child.on("exit", finish);
  child.on("error", finish);
  await promise;
  if (epoch === session.speechEpoch) commitSpoken(clip.sentence);
  clearTimeout(watchdog);
  if (session.activeAfplay === child) {
    session.activeAfplay = null;
    session.isSpeaking = false;
    try {
      writeJsonAtomic(statePath, { playing: false, ended_at: Date.now() / 1000 });
    } catch (err) {
      logOnce("tts-playing-write", err);
    }
  }
  try {
    fs.unlinkSync(clip.wav);
  } catch {
    // ignore
  }
}

function enqueue(sentence: string): void {
  if (session.spoken.has(sentence) || session.spokenText.includes(sentence)) return;
  session.spoken.add(sentence);
  session.inflight.push(sentence);
  session.spokenText = [...session.committed, ...session.inflight].join(" ");
  const epoch = session.speechEpoch;
  const ready = session.genTail.then(() => generate(sentence, epoch));
  session.genTail = ready.then(() => undefined);
  session.playTail = session.playTail.then(async () => {
    const clip = await ready;
    if (clip) await play(clip, epoch);
  });
}

const VOICE_SYSTEM_INSTRUCTION = `
<voice-output-contract>
Your response will be read aloud by VoiceBox TTS while the user is away from the screen, AND displayed in the terminal.
- Keep your normal detailed visual response (tables, file paths, code blocks, timestamps) on screen as usual.
- Whenever your reply contains tables, file paths, shell commands, code blocks, timestamps, or more than 3 sentences, START your reply with a **Voice:** line (1–3 natural, conversational sentences summarizing the takeaway in plain human English with zero file paths, zero commands, zero timestamps, and zero symbols):
  **Voice:** <concise human-friendly spoken summary>
- The VoiceBox TTS engine automatically reads ONLY the **Voice:** summary when present, while leaving the full technical details below it on screen.
</voice-output-contract>`.trim();

function push(message: unknown, flush: boolean): void {
  const raw = textBlocks(message).join("\n");
  // If the assistant started with "**Voice:** ...", wait until that paragraph finishes (newline or flush)
  // and speak ONLY the Voice summary so tables/commands below it are never read aloud!
  const hasVoiceHeader = /(?:^|\n)\s*(?:\*\*|__)?(?:🔊\s*)?(?:Voice|Spoken|Audio\s+summary)(?:\*\*|__)?\s*:/i.test(raw);
  if (hasVoiceHeader && !flush) {
    const afterHeader = raw.split(/(?:^|\n)\s*(?:\*\*|__)?(?:🔊\s*)?(?:Voice|Spoken|Audio\s+summary)(?:\*\*|__)?\s*:/i)[1] ?? "";
    if (!afterHeader.includes("\n")) {
      // Wait until the single-paragraph **Voice:** line completes before synthesizing it
      return;
    }
  }
  const plain = forSpeech(raw);
  if (!plain) return;
  if (continuesDroppedReply(session.droppedPlain, plain)) return;
  session.lastPlain = plain;
  if (session.queued && !plain.startsWith(session.queued)) {
    // forSpeech rewrites command words as the message grows, so the normalized
    // text no longer starts with what we already queued. Replaying from the
    // start is what looped the last reply. Keep going after the covered part.
    const covered = session.spokenText.trim();
    const head = covered.slice(0, 48);
    const at = head ? plain.indexOf(head) : -1;
    if (at >= 0) {
      let i = 0;
      while (i < covered.length && at + i < plain.length && plain[at + i] === covered[i]) i++;
      session.queued = plain.slice(0, at + i);
    } else {
      session.queued = "";
      session.spoken.clear();
      session.committed.length = 0;
      session.inflight.length = 0;
      session.spokenText = "";
    }
  }
  const base = session.queued.length;
  const fresh = plain.slice(base);
  const rawSentences = takeSentences(fresh, flush);
  if (rawSentences.length === 0) return;

  // Coalesce consecutive ready sentences into up to ~200 chars, EXCEPT only emit a coalesced group
  // once the NEXT sentence after it has also started/completed (or on flush=true), so a group's text
  // NEVER grows on subsequent streaming deltas (which previously caused "A" then "A B" to both play!).
  let consumedLen = 0;
  let rest = fresh.trimStart();
  const leadingWs = fresh.length - rest.length;
  consumedLen += leadingWs;

  let group = "";
  let groupEndOffset = consumedLen;

  for (let i = 0; i < rawSentences.length; i++) {
    const s = rawSentences[i]!;
    const at = rest.indexOf(s);
    if (at < 0) break;
    const afterSentenceOffset = groupEndOffset + at + s.length;
    const trailing = rest.slice(at + s.length);
    const wsAfter = trailing.length - trailing.trimStart().length;
    const nextOffset = afterSentenceOffset + wsAfter;

    const targetMax = session.spoken.size === 0 ? 85 : 190;
    if (!group) {
      group = s;
      groupEndOffset = nextOffset;
    } else if (group.length + 1 + s.length <= targetMax) {
      group = `${group} ${s}`;
      groupEndOffset = nextOffset;
    } else {
      enqueue(group);
      session.queued = plain.slice(0, base + groupEndOffset);
      group = s;
      groupEndOffset = nextOffset;
    }
    rest = trailing.trimStart();
  }

  if (group) {
    // Emit the final group immediately if:
    // - flush is true (end of message), OR
    // - it's the very first sentence of the reply (so audio starts with zero delay), OR
    // - the group is already >= 110 chars (so it won't need to wait for another sentence).
    if (flush || session.spoken.size === 0 || group.length >= 110) {
      enqueue(group);
      session.queued = plain.slice(0, base + groupEndOffset);
    }
  }
}

type VoiceUiCtx = {
  isIdle?: () => boolean;
  abort?: () => void;
  ui?: {
    getEditorText?: () => string;
    setEditorText?: (text: string) => void;
    notify?: (message: string, level?: string) => void;
    setStatus?: (key: string, text: string | undefined) => void;
  };
};

export default function voiceboxSpeech(pi: {
  on: (event: string, handler: (event: unknown, ctx?: VoiceUiCtx) => void) => void;
  sendUserMessage?: (content: string, options?: { deliverAs?: "steer" | "followUp" }) => void;
  registerCommand?: (
    name: string,
    spec: { description: string; handler: (args: string, ctx: VoiceUiCtx) => Promise<void> | void },
  ) => void;
}): void {
  let latestCtx: VoiceUiCtx | undefined;
  let server: http.Server | undefined;
  let humanizeMode = false;
  const draftHistory: string[] = [];
  const registryFile = path.join(
    os.homedir(),
    ".local",
    "state",
    "omp-voice",
    "sessions",
    `${process.pid}.json`,
  );
  const clearSessionRegistry = () => {
    try {
      fs.unlinkSync(registryFile);
    } catch {
      // ignore
    }
  };
  const sessionTty = (): string | null => {
    try {
      const dest = fs.readlinkSync("/dev/fd/0");
      return dest.startsWith("/dev/tty") ? dest : null;
    } catch {
      return null;
    }
  };

  void fetch(`${API}/settings/generation`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ autoplay_on_generate: false }),
  }).catch(() => undefined);

  const applyTranscript = (text: string): TranscriptAction => {
    const currentDraft = latestCtx?.ui?.getEditorText?.() ?? "";
    const baseDraft = deduplicateHandyPaste(currentDraft, text);
    const prevDraft = draftHistory.length > 0 ? draftHistory[draftHistory.length - 1] : "";
    const { result, nextEditorText, submitText } = parseVoiceTranscript(text, currentDraft, prevDraft);
    if (result.action === "appended") {
      draftHistory.push(baseDraft);
      if (draftHistory.length > 30) draftHistory.shift();
      latestCtx?.ui?.setEditorText?.(nextEditorText);
    } else if (result.action === "scratched") {
      if (draftHistory.length > 0 && nextEditorText === prevDraft) {
        draftHistory.pop();
      }
      latestCtx?.ui?.setEditorText?.(nextEditorText);
    } else if (result.action === "cleared") {
      draftHistory.length = 0;
      latestCtx?.ui?.setEditorText?.("");
    } else if (result.action === "paused" || result.action === "cancelled") {
      latestCtx?.ui?.setEditorText?.(nextEditorText);
    } else if (result.action === "sent") {
      draftHistory.length = 0;
      latestCtx?.ui?.setEditorText?.("");
      if (submitText && typeof pi.sendUserMessage === "function") {
        pi.sendUserMessage(submitText);
      }
    }
    return result;
  };

  const startBridgeServer = () => {
    if (server) return;
    const createSrv = () =>
      http.createServer((req, res) => {
        const sendJson = (code: number, payload: unknown) => {
          res.writeHead(code, { "content-type": "application/json" });
          res.end(JSON.stringify(payload));
        };

        if (req.method === "GET" && req.url === "/status") {
          const draft = latestCtx?.ui?.getEditorText?.() ?? "";
          const idle = latestCtx?.isIdle?.() ?? true;
          sendJson(200, {
            ok: true,
            version: 2,
            pid: process.pid,
            speaking: session.isSpeaking || session.activeAfplay !== null,
            agentBusy: !idle,
            draft,
            draftLength: draft.length,
          });
          return;
        }

        if (req.method === "POST" && req.url === "/takeover") {
          bargeIn();
          sendJson(200, { ok: true, releasedBy: process.pid });
          if (server) {
            try {
              server.close();
            } catch {
              // ignore
            }
            server = undefined;
          }
          return;
        }

        if (req.method === "POST" && req.url === "/barge-in") {
          readBody(req, (body) => {
            let abortAgent = false;
            try {
              const parsed = JSON.parse(body || "{}") as { abortAgent?: boolean };
              abortAgent = Boolean(parsed.abortAgent);
            } catch {
              // ignore
            }
            const stopped = bargeIn();
            let abortedTurn = false;
            if (abortAgent && latestCtx?.isIdle && !latestCtx.isIdle()) {
              try {
                latestCtx.abort?.();
                abortedTurn = true;
              } catch {
                // ignore
              }
            }
            sendJson(200, { ok: true, stopped, abortedTurn });
          });
          return;
        }

        if (req.method === "POST" && req.url === "/transcript") {
          readBody(req, (body) => {
            try {
              const parsed = JSON.parse(body || "{}") as { text?: string };
              const text = typeof parsed.text === "string" ? parsed.text : "";
              const out = applyTranscript(text);
              sendJson(200, { ok: true, ...out });
            } catch (err) {
              sendJson(400, { ok: false, error: String(err) });
            }
          });
          return;
        }

        sendJson(404, { ok: false, error: "not_found" });
      });

    const srv = createSrv();
    srv.on("error", () => {
      clearSessionRegistry();
    });
    srv.listen(0, BRIDGE_HOST, () => {
      const addr = srv.address();
      const port = typeof addr === "object" && addr ? addr.port : 0;
      boundBridgePort = port;
      fs.mkdirSync(path.dirname(registryFile), { recursive: true });
      fs.writeFileSync(
        registryFile,
        JSON.stringify({
          pid: process.pid,
          port,
          tty: sessionTty(),
          startedAt: Date.now() / 1000,
        }),
      );
      srv.unref();
    });
    server = srv;
  };

  pi.on("session_start", (_event, ctx) => {
    latestCtx = ctx;
    startBridgeServer();
    const child = spawn(
      `${os.homedir()}/.local/bin/omp-voice-controller`,
      ["start"],
      { stdio: "ignore", detached: true },
    );
    child.unref();
  });

  pi.on("session_shutdown", () => {
    bargeIn();
    clearSessionRegistry();
    if (server) {
      try {
        server.close();
      } catch {
        // ignore
      }
      server = undefined;
    }
  });

  pi.on("before_agent_start", (event, ctx) => {
    if (ctx) latestCtx = ctx;
    if (humanizeMode && event && typeof event === "object" && "systemPrompt" in event && Array.isArray(event.systemPrompt)) {
      return {
        systemPrompt: [...(event.systemPrompt as string[]), VOICE_SYSTEM_INSTRUCTION],
      };
    }
    return undefined;
  });

  pi.on("turn_start", (_event, ctx) => {
    if (ctx) latestCtx = ctx;
    // Cut audio for a new user message. Do not mark the reply dropped and do not
    // forget spoken sentences: tool and sub-agent rounds also start a turn, and
    // the parent text is delivered again on each one.
    stopPlayback();
  });

  // If any assistant speech occurs while Handy is recording in DICTATING, silence it immediately!
  let dictatingCacheAt = 0;
  let dictatingCache = false;
  const isControllerDictating = (): boolean => {
    const now = Date.now();
    if (now - dictatingCacheAt < 200) return dictatingCache;
    dictatingCacheAt = now;
    try {
      const ctrlPath = path.join(os.homedir(), ".local", "state", "omp-voice", "status.json");
      if (!fs.existsSync(ctrlPath)) {
        dictatingCache = false;
        return false;
      }
      const parsed = JSON.parse(fs.readFileSync(ctrlPath, "utf8")) as { state?: string; updated_at?: number };
      dictatingCache = parsed.state === "DICTATING" && Date.now() / 1000 - (parsed.updated_at ?? 0) < 60;
      return dictatingCache;
    } catch (err) {
      logOnce("status-read", err);
      dictatingCache = false;
      return false;
    }
  };

  pi.on("message_update", (event, ctx) => {
    if (ctx) latestCtx = ctx;
    if (isControllerDictating()) return;
    if (!event || typeof event !== "object" || !("message" in event)) return;
    const kind =
      "assistantMessageEvent" in event &&
      event.assistantMessageEvent &&
      typeof event.assistantMessageEvent === "object" &&
      "type" in event.assistantMessageEvent
        ? String(event.assistantMessageEvent.type)
        : "";
    if (kind === "thinking_delta" || kind === "thinking_end" || kind === "toolcall_delta" || kind === "text_end") return;
    push(event.message, false);
  });

  pi.on("message_end", (event, ctx) => {
    if (ctx) latestCtx = ctx;
    if (isControllerDictating()) return;
    if (!event || typeof event !== "object" || !("message" in event)) return;
    const message = event.message;
    if (!message || typeof message !== "object" || !("role" in message) || message.role !== "assistant") return;
    push(message, true);
  });

  if (typeof pi.registerCommand === "function") {
    pi.registerCommand("voice", {
      description: "Control OMP hands-free voice loop (status | stop-tts | send)",
      handler: async (args, ctx) => {
        latestCtx = ctx;
        const sub = args.trim().toLowerCase();
      if (sub === "start") {
          const child = spawn(
            `${os.homedir()}/.local/bin/omp-voice-controller`,
            ["start"],
            { stdio: "ignore", detached: true },
          );
          child.unref();
          ctx.ui?.notify?.("Started OMP Voice Controller ('Hey Jarvis' -> 5s pause -> 'send prompt').", "info");
          return;
        }
        if (sub === "stop-daemon") {
          const child = spawn(
            `${os.homedir()}/.local/bin/omp-voice-controller`,
            ["stop"],
            { stdio: "ignore", detached: true },
          );
          child.unref();
          ctx.ui?.notify?.("Stopped OMP Voice Controller daemon.", "info");
          return;
        }
        if (sub === "stop" || sub === "stop-tts" || sub === "barge-in") {
          const stopped = bargeIn();
          ctx.ui?.notify?.(stopped ? "Stopped VoiceBox speech." : "VoiceBox was not speaking.", "info");
          return;
        }
        if (sub === "scratch" || sub === "undo") {
          const out = applyTranscript("scratch that");
          ctx.ui?.notify?.(`Scratched last chunk (draft is now ${out.draft.length} chars).`, "info");
          return;
        }
        if (sub === "clear") {
          applyTranscript("clear draft");
          ctx.ui?.notify?.("Cleared editor draft.", "info");
          return;
        }
        if (sub === "send") {
          const draft = (ctx.ui?.getEditorText?.() ?? "").trim();
          if (!draft) {
            ctx.ui?.notify?.("Draft is empty.", "warning");
            return;
          }
          ctx.ui?.setEditorText?.("");
          pi.sendUserMessage?.(draft);
          return;
        }
        if (sub === "human" || sub === "humanize" || sub === "summary" || sub === "concise") {
          humanizeMode = !humanizeMode;
          ctx.ui?.notify?.(
            `Voice humanize/summary mode is now ${humanizeMode ? "ON" : "OFF"} for this session.`,
            "info",
          );
          return;
        }
        if (sub === "human on" || sub === "humanize on" || sub === "summary on") {
          humanizeMode = true;
          ctx.ui?.notify?.("Voice humanize/summary mode enabled for this session.", "info");
          return;
        }
        if (sub === "human off" || sub === "humanize off" || sub === "summary off") {
          humanizeMode = false;
          ctx.ui?.notify?.("Voice humanize/summary mode disabled for this session.", "info");
          return;
        }
        if (sub.startsWith("rate") || sub.startsWith("speed")) {
          const val = Number(sub.split(/\s+/)[1]);
          if (Number.isFinite(val) && val >= 0.7 && val <= 2.0) {
            session.playbackRate = val;
            ctx.ui?.notify?.(`Set VoiceBox playback speed to ${session.playbackRate}x (afplay -r ${session.playbackRate} -q 1).`, "info");
          } else {
            ctx.ui?.notify?.(`Current playback speed: ${session.playbackRate}x. Usage: /voice speed 1.2`, "info");
          }
          return;
        }
        const draft = ctx.ui?.getEditorText?.() ?? "";
        ctx.ui?.notify?.(
          `OMP Voice Bridge listening on http://${BRIDGE_HOST}:${boundBridgePort} (speaking=${session.isSpeaking}, rate=${session.playbackRate}x, humanize=${humanizeMode}, draft=${draft.length} chars)`,
          "info",
        );
      },
    });
  }
}
