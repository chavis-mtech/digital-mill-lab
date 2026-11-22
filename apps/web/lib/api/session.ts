"use client";

/**
 * Sandbox session id (ADR-006). Created on first visit, stored in localStorage, sent as `X-Demo-Session`.
 * We ask the API to issue one (POST /api/v1/demo/session); if the API is unreachable we fall back to a
 * locally generated UUID v4, which the API accepts as well (it only validates the UUID format).
 */
const KEY = "dml_demo_session";
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function safeGet(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}
function safeSet(v: string) {
  try {
    window.localStorage.setItem(KEY, v);
  } catch {
    /* private mode: keep in memory only */
  }
}

let memory: string | null = null;

export function readSessionId(): string | null {
  const v = memory ?? safeGet();
  return v && UUID_RE.test(v) ? v : null;
}

let inflight: Promise<string> | null = null;

/** Get the session id, creating it once (concurrent callers share one request). */
export function ensureSessionId(): Promise<string> {
  const existing = readSessionId();
  if (existing) return Promise.resolve(existing);
  inflight ??= createSessionId().finally(() => {
    inflight = null;
  });
  return inflight;
}

async function createSessionId(): Promise<string> {
  let id: string | null = null;
  try {
    const res = await fetch("/api/v1/demo/session", { method: "POST", headers: { "X-Demo-Role": "public_viewer" } });
    if (res.ok) {
      const body = (await res.json()) as { session_id?: string };
      if (body.session_id && UUID_RE.test(body.session_id)) id = body.session_id;
    }
  } catch {
    /* API offline: fall back below */
  }
  id ??= crypto.randomUUID();
  memory = id;
  safeSet(id);
  return id;
}

/** Forget the local id (the server-side reset endpoint is POST /api/v1/demo/session/reset). */
export function forgetSessionId() {
  memory = null;
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
