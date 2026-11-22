"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import type { DemoRole, Schema } from "@dml/contracts";
import { apiPost, type DemoRequestContext } from "@/lib/api/client";
import { isApiRequestError } from "@/lib/api/errors";
import { ensureSessionId, readSessionId } from "@/lib/api/session";
import { useLocale } from "@/lib/i18n/client";
import type { Locale } from "@/lib/i18n/config";
import {
  LIVE_STEP_MINUTES,
  LIVE_TICK_MS,
  PLAYBACK_MODES,
  PLAYBACK_PERIOD,
  ROLES,
  SCENARIO_CODES,
  type Period,
  type PlaybackMode,
  type ScenarioCode,
} from "./constants";

/**
 * DemoContext (ADR-005/006/007): the client owns the demo clock (`as_of`), the scenario, the playback mode
 * and the simulated role. State is mirrored to URL search params (shareable links) and localStorage
 * (survives navigation/reload). Precedence on load: URL > localStorage > defaults.
 */
export type DemoState = {
  /** Explicit demo clock (ISO). `null` = let the server resolve (scenario focus_ts, else default as_of). */
  asOf: string | null;
  scenarioId: ScenarioCode | null;
  playback: PlaybackMode;
  role: DemoRole;
};

export type LiveStatus = "off" | "running" | "unavailable" | "error";

export type DemoContextValue = DemoState & {
  locale: Locale;
  sessionId: string | null;
  /** True once the URL/localStorage state and the visitor session id have been read (client only).
   *  Data queries wait for it so the first request already carries the right clock, role and session
   *  (before this, every page fired one request with the defaults and a second one after hydration). */
  ready: boolean;
  /** `period` query value derived from playback (for endpoints that accept `period`). */
  period: Period;
  /** Query + headers to send with every API call. */
  request: DemoRequestContext;
  live: { status: LiveStatus; last: Schema<"TickResponse"> | null; message: string | null };
  setScenario: (code: ScenarioCode | null) => void;
  setPlayback: (mode: PlaybackMode) => void;
  setAsOf: (iso: string | null) => void;
  setRole: (role: DemoRole) => void;
  /** Apply several fields at once (used by the guided tour). */
  apply: (patch: Partial<DemoState>) => void;
  reset: () => void;
};

const STORAGE_KEY = "dml_demo_ctx";
const DEFAULT_STATE: DemoState = { asOf: null, scenarioId: null, playback: "today", role: "public_viewer" };

const Ctx = createContext<DemoContextValue | null>(null);

function sanitize(raw: Partial<Record<keyof DemoState, unknown>>): Partial<DemoState> {
  const out: Partial<DemoState> = {};
  if (typeof raw.asOf === "string" && raw.asOf.length <= 40 && !Number.isNaN(Date.parse(raw.asOf))) out.asOf = raw.asOf;
  if (typeof raw.scenarioId === "string" && (SCENARIO_CODES as readonly string[]).includes(raw.scenarioId))
    out.scenarioId = raw.scenarioId as ScenarioCode;
  if (typeof raw.playback === "string" && (PLAYBACK_MODES as readonly string[]).includes(raw.playback))
    out.playback = raw.playback as PlaybackMode;
  if (typeof raw.role === "string" && (ROLES as readonly string[]).includes(raw.role)) out.role = raw.role as DemoRole;
  return out;
}

function readStorage(): Partial<DemoState> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? sanitize(JSON.parse(raw) as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function readUrl(params: URLSearchParams): Partial<DemoState> {
  return sanitize({
    asOf: params.get("as_of") ?? undefined,
    scenarioId: params.get("scenario") ?? undefined,
    playback: params.get("playback") ?? undefined,
    role: params.get("role") ?? undefined,
  });
}

/** Paths whose URL carries demo params. Public marketing pages stay clean. */
function syncsUrl(pathname: string) {
  return pathname.startsWith("/demo") || pathname.startsWith("/docs");
}

export function DemoProvider({ children }: { children: ReactNode }) {
  const { locale } = useLocale();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [state, setState] = useState<DemoState>(DEFAULT_STATE);
  const [hydrated, setHydrated] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [live, setLive] = useState<DemoContextValue["live"]>({ status: "off", last: null, message: null });

  // Hydrate once on the client: URL > localStorage > defaults.
  useEffect(() => {
    const fromUrl = readUrl(new URLSearchParams(window.location.search));
    // A URL that carries demo params is authoritative: a missing `as_of` means "server-resolved clock".
    const urlPatch = Object.keys(fromUrl).length ? { asOf: null, ...fromUrl } : {};
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time hydration from browser-only storage
    setState({ ...DEFAULT_STATE, ...readStorage(), ...urlPatch });
    setSessionId(readSessionId());
    setHydrated(true);
    void ensureSessionId().then(setSessionId);
  }, []);

  // Back/forward or a pasted link with params: adopt URL values.
  const urlKey = searchParams.toString();
  useEffect(() => {
    if (!hydrated) return;
    const fromUrl = readUrl(new URLSearchParams(urlKey));
    if (Object.keys(fromUrl).length === 0) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- external (URL) source of truth
    setState((s) => {
      const next = { ...s, asOf: null, ...fromUrl };
      return JSON.stringify(next) === JSON.stringify(s) ? s : next;
    });
  }, [urlKey, hydrated]);

  // Persist + mirror to URL (replaceState: no navigation, no history spam).
  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      /* ignore */
    }
    // Only mirror when the router has settled on this path (never rewrite history mid-navigation).
    if (!syncsUrl(pathname) || window.location.pathname !== pathname) return;
    const params = new URLSearchParams(window.location.search);
    const set = (k: string, v: string | null, dflt?: string) => (v && v !== dflt ? params.set(k, v) : params.delete(k));
    set("as_of", state.asOf);
    set("scenario", state.scenarioId);
    set("playback", state.playback, "today");
    set("role", state.role, "public_viewer");
    const qs = params.toString();
    const next = `${pathname}${qs ? `?${qs}` : ""}${window.location.hash}`;
    if (next !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
      window.history.replaceState(window.history.state, "", next);
    }
  }, [state, pathname, hydrated]);

  const apply = useCallback((patch: Partial<DemoState>) => setState((s) => ({ ...s, ...patch })), []);
  const setScenario = useCallback(
    (code: ScenarioCode | null) =>
      setState((s) => ({
        ...s,
        scenarioId: code,
        asOf: null, // server resolves the scenario's focus_ts (ADR-011)
        playback: code ? "scenario_date" : s.playback === "scenario_date" ? "today" : s.playback,
      })),
    [],
  );
  const setPlayback = useCallback(
    (mode: PlaybackMode) =>
      setState((s) => ({
        ...s,
        playback: mode,
        // Leaving live mode or jumping to a preset returns to the server-resolved clock.
        asOf: mode === "simulated_live" ? s.asOf : mode === "scenario_date" ? null : s.playback === "simulated_live" ? null : s.asOf,
      })),
    [],
  );
  const setAsOf = useCallback((iso: string | null) => setState((s) => ({ ...s, asOf: iso })), []);
  const setRole = useCallback((role: DemoRole) => setState((s) => ({ ...s, role })), []);
  const reset = useCallback(() => setState(DEFAULT_STATE), []);

  const request = useMemo<DemoRequestContext>(() => {
    const query: DemoRequestContext["query"] = {};
    if (state.asOf) query.as_of = state.asOf;
    if (state.scenarioId) query.scenario_id = state.scenarioId;
    const headers: DemoRequestContext["headers"] = { "X-Demo-Role": state.role };
    if (sessionId) headers["X-Demo-Session"] = sessionId;
    return { query, headers };
  }, [state.asOf, state.scenarioId, state.role, sessionId]);

  // Simulated live: the client advances its own clock via POST /demo/tick (ADR-005). If the endpoint is a
  // 501 stub we stop and say so — we never invent a clock or data client-side.
  const requestRef = useRef(request);
  useEffect(() => {
    requestRef.current = request;
  }, [request]);
  useEffect(() => {
    if (!hydrated || state.playback !== "simulated_live") {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reset derived status when leaving live mode
      setLive((l) => (l.status === "off" ? l : { status: "off", last: null, message: null }));
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      try {
        const res = await apiPost("/api/v1/demo/tick", { body: { step_minutes: LIVE_STEP_MINUTES } }, requestRef.current);
        if (cancelled) return;
        setLive({ status: "running", last: res, message: res.label });
        setState((s) => ({ ...s, asOf: res.next_as_of }));
        timer = setTimeout(tick, LIVE_TICK_MS);
      } catch (e) {
        if (cancelled) return;
        if (isApiRequestError(e) && e.isNotImplemented) {
          setLive({ status: "unavailable", last: null, message: e.message });
        } else {
          setLive({ status: "error", last: null, message: e instanceof Error ? e.message : String(e) });
        }
      }
    };
    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [state.playback, hydrated]);

  const value = useMemo<DemoContextValue>(
    () => ({
      ...state,
      locale,
      sessionId,
      ready: hydrated && sessionId !== null,
      period: PLAYBACK_PERIOD[state.playback],
      request,
      live,
      setScenario,
      setPlayback,
      setAsOf,
      setRole,
      apply,
      reset,
    }),
    [state, locale, sessionId, hydrated, request, live, setScenario, setPlayback, setAsOf, setRole, apply, reset],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useDemo(): DemoContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useDemo must be used inside <DemoProvider>");
  return v;
}
