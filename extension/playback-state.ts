// Per-session playback slots. The legacy tts-playing.json file is only a projection.
import * as fs from "node:fs";
import * as path from "node:path";

export const PLAYBACK_LEASE_SECONDS = 60;

export type PlaybackReason = "begin" | "end";

export type WavReference = {
  sample_rate: number;
  channels: number;
  frames: number;
  wav: string;
};

export type PlaybackSlot = {
  playing: boolean;
  turn: number;
  clip: number;
  writer_pid: number;
  afplay_pid?: number;
  started_at?: number;
  ended_at?: number;
  lease_until?: number;
  playback_rate?: number;
  reason: PlaybackReason;
  reference?: WavReference;
};

export type LegacyPlayback = {
  playing: boolean;
  pid?: number;
  started_at?: number;
  ended_at?: number;
};

export function validPid(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isInteger(value) || value <= 0) return null;
  return value;
}

function strictlyNewer(prev: PlaybackSlot, turn: number, clip: number): boolean {
  return prev.turn > turn || (prev.turn === turn && prev.clip > clip);
}

export function beginSlot(
  prev: PlaybackSlot | null,
  turn: number,
  clip: number,
  writerPid: number,
  afplayPid: number | undefined,
  now: number,
  reference?: WavReference | null,
  playbackRate?: number,
): PlaybackSlot {
  if (prev && strictlyNewer(prev, turn, clip)) return prev;
  const next: PlaybackSlot = {
    playing: true,
    turn,
    clip,
    writer_pid: writerPid,
    started_at: now,
    lease_until: now + PLAYBACK_LEASE_SECONDS,
    reason: "begin",
  };
  if (typeof playbackRate === "number" && Number.isFinite(playbackRate) && playbackRate >= 0.7 && playbackRate <= 2) {
    next.playback_rate = playbackRate;
  }
  const afplay = validPid(afplayPid);
  if (afplay !== null) next.afplay_pid = afplay;
  if (reference) next.reference = reference;
  return next;
}

function ascii(bytes: Uint8Array, offset: number, length: number): string {
  let out = "";
  for (let i = 0; i < length; i++) out += String.fromCharCode(bytes[offset + i] ?? 0);
  return out;
}

/** PCM format of the WAV afplay is about to play. Not an echo canceller. */
export function wavReference(bytes: Uint8Array, wav: string): WavReference | null {
  if (bytes.byteLength < 44 || !wav.endsWith(".wav")) return null;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (ascii(bytes, 0, 4) !== "RIFF" || ascii(bytes, 8, 4) !== "WAVE") return null;
  let offset = 12;
  let format = 0;
  let channels = 0;
  let sampleRate = 0;
  let blockAlign = 0;
  let bits = 0;
  let dataBytes = 0;
  while (offset + 8 <= bytes.byteLength) {
    const id = ascii(bytes, offset, 4);
    const size = view.getUint32(offset + 4, true);
    const body = offset + 8;
    if (body + size > bytes.byteLength) return null;
    if (id === "fmt " && size >= 16) {
      format = view.getUint16(body, true);
      channels = view.getUint16(body + 2, true);
      sampleRate = view.getUint32(body + 4, true);
      blockAlign = view.getUint16(body + 12, true);
      bits = view.getUint16(body + 14, true);
    } else if (id === "data") {
      dataBytes = size;
    }
    offset = body + size + (size % 2);
  }
  if (format !== 1 || bits !== 16 || channels < 1 || sampleRate < 8000) return null;
  if (blockAlign !== channels * 2 || dataBytes < blockAlign || dataBytes % blockAlign !== 0) return null;
  return { sample_rate: sampleRate, channels, frames: dataBytes / blockAlign, wav };
}

export function endSlot(prev: PlaybackSlot | null, turn: number, clip: number, now: number): PlaybackSlot | null {
  if (!prev) return null;
  if (strictlyNewer(prev, turn, clip)) return prev;
  const next: PlaybackSlot = { ...prev, playing: false, ended_at: now, reason: "end" };
  delete next.reference;
  return next;
}

export function slotIsSpeaking(
  slot: object | null | undefined,
  now: number,
  alive: (pid: number) => boolean,
  tail: number,
): boolean {
  if (!slot || typeof slot !== "object") return false;
  const row = slot as Record<string, unknown>;
  const ended = typeof row.ended_at === "number" && Number.isFinite(row.ended_at) ? row.ended_at : 0;
  if (row.playing !== true) return ended > 0 && now - ended < tail;
  const afplay = validPid(row.afplay_pid);
  const writer = validPid(row.writer_pid);
  if (afplay !== null) {
    if (!alive(afplay)) return false;
    if (writer !== null && !alive(writer)) {
      const started = typeof row.started_at === "number" ? row.started_at : 0;
      return now < started + PLAYBACK_LEASE_SECONDS;
    }
    return true;
  }
  if (writer === null || !alive(writer)) return false;
  const lease = typeof row.lease_until === "number" ? row.lease_until : 0;
  return now < lease;
}

export function playbackIsSpeaking(
  data: Record<string, unknown> | null | undefined,
  now: number,
  alive: (pid: number) => boolean,
  tail: number,
): boolean {
  if (!data) return false;
  const sessions = data.sessions;
  if (sessions && typeof sessions === "object" && !Array.isArray(sessions)) {
    return Object.values(sessions as Record<string, unknown>).some((slot) =>
      slot && typeof slot === "object" ? slotIsSpeaking(slot, now, alive, tail) : false,
    );
  }
  if (data.playing === true && (data.ended_at === undefined || data.ended_at === null)) return true;
  const ended = typeof data.ended_at === "number" ? data.ended_at : 0;
  return ended > 0 && now - ended < tail;
}

export function sourcesSpeaking(
  slots: Array<Record<string, unknown>> | null,
  legacy: Record<string, unknown> | null,
  now: number,
  alive: (pid: number) => boolean,
  tail: number,
): boolean {
  if (slots !== null) return slots.some((slot) => slotIsSpeaking(slot, now, alive, tail));
  return playbackIsSpeaking(legacy, now, alive, tail);
}

export function projectAggregate(slots: PlaybackSlot[]): LegacyPlayback {
  const live = slots.filter((slot) => slot.playing === true);
  if (live.length) {
    const pick = live.reduce((best, slot) => ((slot.started_at ?? 0) >= (best.started_at ?? 0) ? slot : best));
    const out: LegacyPlayback = { playing: true };
    if (typeof pick.started_at === "number") out.started_at = pick.started_at;
    const pid = validPid(pick.afplay_pid);
    if (pid !== null) out.pid = pid;
    return out;
  }
  let ended = 0;
  for (const slot of slots) {
    if (typeof slot.ended_at === "number" && slot.ended_at > ended) ended = slot.ended_at;
  }
  const out: LegacyPlayback = { playing: false };
  if (ended > 0) out.ended_at = ended;
  return out;
}

function readJson(file: string): unknown {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return null;
  }
}

function writeJsonAtomic(file: string, value: unknown): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.${Date.now()}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(value));
  fs.renameSync(tmp, file);
}

export function readSlots(stateDir: string): PlaybackSlot[] {
  const dir = path.join(stateDir, "tts-playing");
  if (!fs.existsSync(dir)) return [];
  const slots: PlaybackSlot[] = [];
  for (const name of fs.readdirSync(dir)) {
    if (!/^\d+\.json$/.test(name)) continue;
    const data = readJson(path.join(dir, name));
    if (data && typeof data === "object") slots.push(data as PlaybackSlot);
  }
  return slots;
}

function readOwnSlot(stateDir: string, sessionId: string): PlaybackSlot | null {
  if (!/^\d+$/.test(sessionId)) throw new Error(`bad session id ${sessionId}`);
  const data = readJson(path.join(stateDir, "tts-playing", `${sessionId}.json`));
  if (!data || typeof data !== "object") return null;
  return data as PlaybackSlot;
}

function publish(stateDir: string, sessionId: string, slot: PlaybackSlot): void {
  if (!/^\d+$/.test(sessionId)) throw new Error(`bad session id ${sessionId}`);
  writeJsonAtomic(path.join(stateDir, "tts-playing", `${sessionId}.json`), slot);
  writeJsonAtomic(path.join(stateDir, "tts-playing.json"), projectAggregate(readSlots(stateDir)));
}

export function commitBegin(
  stateDir: string,
  sessionId: string,
  turn: number,
  clip: number,
  writerPid: number,
  afplayPid: number | undefined,
  now: number,
  reference?: WavReference | null,
  playbackRate?: number,
): PlaybackSlot {
  const next = beginSlot(readOwnSlot(stateDir, sessionId), turn, clip, writerPid, afplayPid, now, reference, playbackRate);
  publish(stateDir, sessionId, next);
  return next;
}

export function commitEnd(
  stateDir: string,
  sessionId: string,
  turn: number,
  clip: number,
  now: number,
): PlaybackSlot | null {
  const next = endSlot(readOwnSlot(stateDir, sessionId), turn, clip, now);
  if (next) publish(stateDir, sessionId, next);
  return next;
}
