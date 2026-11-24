// F1/F3/F4: the per-session bridge must reject every request that does not
// carry the session token, an Origin, or a non-loopback Host. The seam is the
// HTTP interface itself: real requests against createBridgeServer.

import assert from "node:assert/strict";
import http from "node:http";
import { test } from "node:test";

import {
  BRIDGE_TOKEN_HEADER,
  createBridgeServer,
  newBridgeToken,
} from "../extension/voicebox-speech.ts";

function listenEphemeral(server: http.Server): Promise<number> {
  const { promise, resolve, reject } = Promise.withResolvers<number>();
  server.once("error", reject);
  server.listen(0, "127.0.0.1", () => {
    const addr = server.address();
    resolve(typeof addr === "object" && addr ? addr.port : 0);
  });
  return promise;
}

function makeBridge(): { server: http.Server; token: string; port: Promise<number> } {
  const token = newBridgeToken();
  const server = createBridgeServer(
    {
      status: () => ({ ok: true, draft: "secret draft", draftLength: 12 }),
      // Real applyTranscript returns a bare action; the seam must add ok:true or the controller pastes twice.
      transcript: (text: string, wake: boolean) => ({ action: "appended", draft: text, wake }),
      takeover: () => ({ ok: true, releasedBy: "test" }),
      bargeIn: (body: string) => ({ ok: true, body }),
    },
    token,
  );
  return { server, token, port: listenEphemeral(server) };
}

type BridgeResponse = { status: number; json: Record<string, unknown> | null };

function request(
  port: number,
  method: string,
  opts: { path: string; headers?: Record<string, string>; body?: string },
): Promise<BridgeResponse> {
  const { promise, resolve, reject } = Promise.withResolvers<BridgeResponse>();
  const req = http.request(
    { host: "127.0.0.1", port, method, path: opts.path, headers: opts.headers },
    (res) => {
      let body = "";
      res.on("data", (chunk) => (body += String(chunk)));
      res.on("end", () => resolve({ status: res.statusCode ?? 0, json: body ? (JSON.parse(body) as Record<string, unknown>) : null }));
    },
  );
  req.on("error", reject);
  if (opts.body) req.write(opts.body);
  req.end();
  return promise;
}

function errorOf(json: Record<string, unknown> | null): string | undefined {
  return json && typeof json.error === "string" ? json.error : undefined;
}

test("the session token is 32 random bytes in hex", () => {
  const a = newBridgeToken();
  const b = newBridgeToken();
  assert.match(a, /^[0-9a-f]{64}$/);
  assert.notEqual(a, b);
});

test("every bridge route rejects a request without the session token", async () => {
  const { server, port } = makeBridge();
  const p = await port;
  try {
    const status = await request(p, "GET", { path: "/status" });
    assert.equal(status.status, 401);
    const transcript = await request(p, "POST", {
      path: "/transcript",
      headers: { "content-type": "application/json", [BRIDGE_TOKEN_HEADER]: "deadbeef".repeat(8) },
      body: JSON.stringify({ text: "hello" }),
    });
    assert.equal(transcript.status, 401);
  } finally {
    server.closeAllConnections();
    server.close();
  }
});

test("a request carrying an Origin header is refused even with the token", async () => {
  const { server, token, port } = makeBridge();
  const p = await port;
  try {
    const res = await request(p, "GET", {
      path: "/status",
      headers: { [BRIDGE_TOKEN_HEADER]: token, origin: "https://evil.example.com" },
    });
    assert.equal(res.status, 403);
    assert.equal(errorOf(res.json), "origin_not_allowed");
  } finally {
    server.closeAllConnections();
    server.close();
  }
});

test("a Host header that is not 127.0.0.1:<port> is refused (DNS rebinding)", async () => {
  const { server, token, port } = makeBridge();
  const p = await port;
  try {
    const rebinding = await request(p, "GET", {
      path: "/status",
      headers: { [BRIDGE_TOKEN_HEADER]: token, host: "evil.example.com" },
    });
    assert.equal(rebinding.status, 403);
    assert.equal(errorOf(rebinding.json), "host_not_allowed");
    const localhost = await request(p, "GET", {
      path: "/status",
      headers: { [BRIDGE_TOKEN_HEADER]: token, host: "localhost" },
    });
    assert.equal(localhost.status, 403);
  } finally {
    server.closeAllConnections();
    server.close();
  }
});

test("POST with a content type other than application/json is refused", async () => {
  const { server, token, port } = makeBridge();
  const p = await port;
  try {
    const res = await request(p, "POST", {
      path: "/transcript",
      headers: { [BRIDGE_TOKEN_HEADER]: token, "content-type": "text/plain" },
      body: '{"text": "cross-site send prompt"}',
    });
    assert.equal(res.status, 415);
    assert.equal(errorOf(res.json), "content_type_not_allowed");
  } finally {
    server.closeAllConnections();
    server.close();
  }
});

test("authenticated loopback requests reach the handlers, including the draft in /status", async () => {
  const { server, token, port } = makeBridge();
  const p = await port;
  try {
    const status = await request(p, "GET", { path: "/status", headers: { [BRIDGE_TOKEN_HEADER]: token } });
    assert.equal(status.status, 200);
    assert.deepEqual(status.json, { ok: true, draft: "secret draft", draftLength: 12 });
    const transcript = await request(p, "POST", {
      path: "/transcript",
      headers: { [BRIDGE_TOKEN_HEADER]: token, "content-type": "application/json" },
      body: JSON.stringify({ text: "hey jarvis zoom in", wake: true }),
    });
    assert.equal(transcript.status, 200);
    assert.deepEqual(transcript.json, { ok: true, action: "appended", draft: "hey jarvis zoom in", wake: true });
    const barge = await request(p, "POST", {
      path: "/barge-in",
      headers: { [BRIDGE_TOKEN_HEADER]: token, "content-type": "application/json" },
      body: JSON.stringify({ abortAgent: false }),
    });
    assert.equal(barge.status, 200);
    const unknown = await request(p, "GET", { path: "/nope", headers: { [BRIDGE_TOKEN_HEADER]: token } });
    assert.equal(unknown.status, 404);
  } finally {
    server.closeAllConnections();
    server.close();
  }
});
