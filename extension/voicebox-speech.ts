// Speak sentence by sentence via VoiceBox and accept hands-free dictated chunks
// + voice submit ("send prompt") + Barge-in from omp-voice-controller.
//
// Local control HTTP server on 127.0.0.1:17494:
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
const BRIDGE_PORT = 17494;
const PROFILE = process.env.OMP_VOICEBOX_PROFILE ?? "";

let playbackRate = Number(process.env.OMP_VOICE_RATE ?? "1.18") || 1.18;
let queued = "";
const spoken = new Set<string>();
let genTail: Promise<void> = Promise.resolve();
let playTail: Promise<void> = Promise.resolve();
let speechEpoch = 0;
let clipSeq = 0;
let activeAfplay: ChildProcess | null = null;
let activeAbort: AbortController | null = null;
let isSpeaking = false;

export type TranscriptAction =
  | { action: "sent"; draft: string; strippedCommand: string }
  | { action: "paused"; draft: string; strippedCommand: string }
  | { action: "cancelled"; draft: string; strippedCommand: string }
  | { action: "scratched"; draft: string; strippedCommand: string }
  | { action: "cleared"; draft: string; strippedCommand: string }
  | { action: "appended"; draft: string }
  | { action: "noop"; draft: string };

const SEND_PHRASES = [
  "send prompt",
  "submit prompt",
  "send message",
  "send that",
  "send it",
  "press enter",
  "ship it",
  "hey jarvis send",
  "jarvis send",
];

const PAUSE_PHRASES = [
  "pause listening",
  "stop listening",
  "go to sleep",
  "hey jarvis stop",
  "jarvis stop",
  "stop dictation",
  "stop",
];

const SCRATCH_PHRASES = [
  "scratch that",
  "scratch last",
  "undo that",
  "delete that",
  "erase that",
  "remove last",
  "hey jarvis scratch",
  "jarvis scratch",
];

const CLEAR_PHRASES = [
  "clear draft",
  "clear all",
  "clear text",
  "clear box",
  "scratch all",
  "start over",
  "hey jarvis clear",
  "jarvis clear",
];

const CANCEL_PHRASES = [
  "cancel that",
  "discard chunk",
  "cancel dictation",
  "hey jarvis cancel",
  "jarvis cancel",
];

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
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

  const matchTrailingPhrase = (phrases: string[]): { prefix: string; phrase: string } | null => {
    for (const phrase of phrases) {
      const re = new RegExp(`^(.*?)(?:[\\s,.;:!?-]+|^)(${escapeRegex(phrase)})[\\s,.;:!?]*$`, "i");
      const m = cleaned.match(re);
      if (m) {
        const prefix = (m[1] ?? "").replace(/[\s,.;:-]+$/, "").trim();
        return { prefix, phrase: m[2] ?? phrase };
      }
    }
    return null;
  };

  // 0. Check Clear All Phrase ("clear draft", "clear all", "start over")
  const clearMatch = matchTrailingPhrase(CLEAR_PHRASES);
  if (clearMatch) {
    return {
      result: { action: "cleared", draft: "", strippedCommand: clearMatch.phrase },
      nextEditorText: "",
    };
  }

  // 1. Check Scratch / Undo Phrase ("scratch that", "undo that", "delete that")
  //    - If the user spoke words in this chunk before "... scratch that", discard this chunk (stays at baseDraft).
  //    - If the user just said "scratch that" (no prefix), also pop the previously pasted chunk from the screen!
  const scratchMatch = matchTrailingPhrase(SCRATCH_PHRASES);
  if (scratchMatch) {
    const revertedDraft = scratchMatch.prefix
      ? baseDraft
      : previousDraft !== undefined
        ? previousDraft
        : baseDraft.replace(/(?:^|\s+)\S+[^.!?\n]*[.!?]*\s*$/, "").trimEnd();
    return {
      result: { action: "scratched", draft: revertedDraft, strippedCommand: scratchMatch.phrase },
      nextEditorText: revertedDraft,
    };
  }

  // 2. Check Cancel Phrase
  const cancelMatch = matchTrailingPhrase(CANCEL_PHRASES);
  if (cancelMatch) {
    return {
      result: { action: "cancelled", draft: baseDraft, strippedCommand: cancelMatch.phrase },
      nextEditorText: baseDraft,
    };
  }

  // 2. Check Pause Phrase
  const pauseMatch = matchTrailingPhrase(PAUSE_PHRASES);
  if (pauseMatch) {
    const nextDraft = pauseMatch.prefix
      ? baseDraft.trim()
        ? `${baseDraft.trimEnd()} ${pauseMatch.prefix}`
        : pauseMatch.prefix
      : baseDraft;
    return {
      result: { action: "paused", draft: nextDraft, strippedCommand: pauseMatch.phrase },
      nextEditorText: nextDraft,
    };
  }

  // 3. Check Send Phrase
  const sendMatch = matchTrailingPhrase(SEND_PHRASES);
  if (sendMatch) {
    const combined = sendMatch.prefix
      ? baseDraft.trim()
        ? `${baseDraft.trimEnd()} ${sendMatch.prefix}`
        : sendMatch.prefix
      : baseDraft.trim();
    return {
      result: { action: "sent", draft: combined, strippedCommand: sendMatch.phrase },
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

export function bargeIn(): boolean {
  const wasSpeaking = isSpeaking || activeAfplay !== null || activeAbort !== null;
  speechEpoch++;
  queued = "";
  spoken.clear();
  genTail = Promise.resolve();
  playTail = Promise.resolve();
  if (activeAbort) {
    try {
      activeAbort.abort();
    } catch {
      // ignore
    }
    activeAbort = null;
  }
  if (activeAfplay) {
    try {
      activeAfplay.kill("SIGTERM");
    } catch {
      // ignore
    }
    activeAfplay = null;
  }
  isSpeaking = false;
  const statePath = path.join(os.homedir(), ".local", "state", "omp-voice", "tts-playing.json");
  try {
    fs.mkdirSync(path.dirname(statePath), { recursive: true });
    fs.writeFileSync(statePath, JSON.stringify({ playing: false, ended_at: Date.now() / 1000 }));
  } catch {
    // ignore
  }
  return wasSpeaking;
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

export function forSpeech(raw: string): string {
  // 1. If the assistant emitted a dedicated spoken summary (<voice>...</voice> or **Voice:** ...),
  //    speak ONLY that human-friendly summary instead of reading tables/paths/commands out loud!
  const voiceTagMatch = raw.match(/<voice>([\s\S]*?)<\/voice>/i);
  const voiceLineMatch = !voiceTagMatch
    ? raw.match(/(?:^|\n)\s*(?:\*\*|__)?(?:🔊\s*)?(?:Voice|Spoken|Audio\s+summary)(?:\*\*|__)?\s*:\s*([^\n]+(?:\n(?![\s\n]*[-*#|`<\d])[^\n]+)*)/i)
    : null;
  const source = voiceTagMatch ? voiceTagMatch[1]! : voiceLineMatch ? voiceLineMatch[1]! : raw;

  return source
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
    .replace(/\b(scratch|undo|delete|erase)[\s,]+(that|last|all)\b/gi, "the undo phrase")
    .replace(/\bclear[\s,]+(draft|all|text|box)\b/gi, "the clear phrase")
    .replace(/[*_~>|]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
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

function takeSentences(fresh: string, flush: boolean): string[] {
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

async function profileId(): Promise<string | undefined> {
  if (cachedProfileId) return cachedProfileId;
  const res = await fetch(`${API}/profiles`);
  const rows: unknown = await res.json().catch(() => null);
  if (!Array.isArray(rows)) return undefined;
  for (const row of rows) {
    if (!row || typeof row !== "object" || !("name" in row) || !("id" in row)) continue;
    if (row.name === PROFILE && typeof row.id === "string") {
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

async function generate(text: string, epoch: number): Promise<{ wav: string } | undefined> {
  if (epoch !== speechEpoch) {
    logSpeech("dropped", text, { reason: "epoch" });
    return undefined;
  }
  const controller = new AbortController();
  activeAbort = controller;
  const timer = setTimeout(() => controller.abort(), 90000);
  try {
    const id = await profileId();
    if (!id || epoch !== speechEpoch) {
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
        model_size: "0.6B",
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
    if (epoch !== speechEpoch || arrayBuf.byteLength < 100) {
      logSpeech("failed", text, { reason: epoch !== speechEpoch ? "epoch" : "short-audio", bytes: arrayBuf.byteLength });
      return undefined;
    }
    const wavPath = path.join(os.tmpdir(), `omp-vb-${process.pid}-${++clipSeq}.wav`);
    fs.writeFileSync(wavPath, Buffer.from(arrayBuf));
    logSpeech("generated", text, { bytes: arrayBuf.byteLength, wav: path.basename(wavPath) });
    return { wav: wavPath };
  } catch (err) {
    logSpeech("failed", text, { reason: String(err) });
    return undefined;
  } finally {
    clearTimeout(timer);
    if (activeAbort === controller) activeAbort = null;
  }
}

async function play(clip: { wav: string }, epoch: number): Promise<void> {
  if (epoch !== speechEpoch) {
    try {
      fs.unlinkSync(clip.wav);
    } catch {
      // ignore
    }
    return;
  }
  isSpeaking = true;
  const { promise, resolve } = Promise.withResolvers<void>();
  const args = playbackRate !== 1.0
    ? ["-r", String(playbackRate), "-q", "1", clip.wav]
    : [clip.wav];
  const child = spawn("afplay", args, { stdio: "ignore" });
  activeAfplay = child;
  const statePath = path.join(os.homedir(), ".local", "state", "omp-voice", "tts-playing.json");
  try {
    fs.mkdirSync(path.dirname(statePath), { recursive: true });
    fs.writeFileSync(statePath, JSON.stringify({ playing: true, pid: child.pid, started_at: Date.now() / 1000 }));
  } catch {
    // ignore
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
  clearTimeout(watchdog);
  if (activeAfplay === child) {
    activeAfplay = null;
    isSpeaking = false;
    try {
      fs.writeFileSync(statePath, JSON.stringify({ playing: false, ended_at: Date.now() / 1000 }));
    } catch {
      // ignore
    }
  }
  try {
    fs.unlinkSync(clip.wav);
  } catch {
    // ignore
  }
}

function enqueue(sentence: string): void {
  if (spoken.has(sentence)) return;
  spoken.add(sentence);
  const epoch = speechEpoch;
  const ready = genTail.then(() => generate(sentence, epoch));
  genTail = ready.then(() => undefined);
  playTail = playTail.then(async () => {
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
  if (queued && !plain.startsWith(queued)) {
    // Only reset if this is genuinely a brand-new message turn (where none of its sentences were spoken yet)
    const allSentences = takeSentences(plain, true);
    if (allSentences.some((s) => spoken.has(s))) {
      // Same message whose normalized prefix shifted slightly mid-stream: advance only beyond spoken sentences
      for (const s of allSentences) {
        if (!spoken.has(s)) {
          enqueue(s);
        }
      }
      queued = plain;
      return;
    }
    queued = "";
    spoken.clear();
  }
  const base = queued.length;
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

    const targetMax = spoken.size === 0 ? 85 : 190;
    if (!group) {
      group = s;
      groupEndOffset = nextOffset;
    } else if (group.length + 1 + s.length <= targetMax) {
      group = `${group} ${s}`;
      groupEndOffset = nextOffset;
    } else {
      enqueue(group);
      queued = plain.slice(0, base + groupEndOffset);
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
    if (flush || spoken.size === 0 || group.length >= 110) {
      enqueue(group);
      queued = plain.slice(0, base + groupEndOffset);
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
            speaking: isSpeaking || activeAfplay !== null,
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
          let body = "";
          req.on("data", (chunk) => {
            body += String(chunk);
          });
          req.on("end", () => {
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
          let body = "";
          req.on("data", (chunk) => {
            body += String(chunk);
          });
          req.on("end", () => {
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
    let retried = false;
    srv.on("error", (err: NodeJS.ErrnoException) => {
      if (err.code === "EADDRINUSE" && !retried) {
        retried = true;
        // Ask the older OMP session to release 127.0.0.1:17494 so the newest session always owns voice input
        void fetch(`http://${BRIDGE_HOST}:${BRIDGE_PORT}/takeover`, { method: "POST" })
          .catch(() => undefined)
          .finally(() => {
            setTimeout(() => {
              const retrySrv = createSrv();
              retrySrv.on("error", () => {});
              retrySrv.listen(BRIDGE_PORT, BRIDGE_HOST, () => {
                retrySrv.unref();
              });
              server = retrySrv;
            }, 150);
          });
      }
    });

    srv.listen(BRIDGE_PORT, BRIDGE_HOST, () => {
      srv.unref();
    });
    server = srv;
  };

  pi.on("session_start", (_event, ctx) => {
    latestCtx = ctx;
    startBridgeServer();
    const child = spawn(
      `${process.env.HOME}/.local/bin/omp-voice-controller`,
      ["start"],
      { stdio: "ignore", detached: true },
    );
    child.unref();
  });

  pi.on("session_shutdown", () => {
    bargeIn();
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
    queued = "";
    spoken.clear();
  });

  // If any assistant speech occurs while Handy is recording in DICTATING, silence it immediately!
  const isControllerDictating = (): boolean => {
    try {
      const ctrlPath = path.join(os.homedir(), ".local", "state", "omp-voice", "status.json");
      if (!fs.existsSync(ctrlPath)) return false;
      const parsed = JSON.parse(fs.readFileSync(ctrlPath, "utf8")) as { state?: string; updated_at?: number };
      return parsed.state === "DICTATING" && Date.now() / 1000 - (parsed.updated_at ?? 0) < 60;
    } catch {
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
            `${process.env.HOME}/.local/bin/omp-voice-controller`,
            ["start"],
            { stdio: "ignore", detached: true },
          );
          child.unref();
          ctx.ui?.notify?.("Started OMP Voice Controller ('Hey Jarvis' -> 5s pause -> 'send prompt').", "info");
          return;
        }
        if (sub === "stop-daemon") {
          const child = spawn(
            `${process.env.HOME}/.local/bin/omp-voice-controller`,
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
            playbackRate = val;
            ctx.ui?.notify?.(`Set VoiceBox playback speed to ${playbackRate}x (afplay -r ${playbackRate} -q 1).`, "info");
          } else {
            ctx.ui?.notify?.(`Current playback speed: ${playbackRate}x. Usage: /voice speed 1.2`, "info");
          }
          return;
        }
        const draft = ctx.ui?.getEditorText?.() ?? "";
        ctx.ui?.notify?.(
          `OMP Voice Bridge listening on http://${BRIDGE_HOST}:${BRIDGE_PORT} (speaking=${isSpeaking}, rate=${playbackRate}x, humanize=${humanizeMode}, draft=${draft.length} chars)`,
          "info",
        );
      },
    });
  }
}
