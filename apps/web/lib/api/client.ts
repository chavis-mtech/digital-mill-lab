import createClient from "openapi-fetch";
import type { paths } from "@dml/contracts";
import type { MaybeOptionalInit } from "openapi-fetch";
import type { PathsWithMethod } from "openapi-typescript-helpers";
import { toApiError, ApiRequestError } from "./errors";

/**
 * Typed fetch client generated from the OpenAPI contract (ADR-004). In the browser we call the same
 * origin (`/api/v1/*` is rewritten to FastAPI by next.config.ts). On the server we call the API directly.
 */
function baseUrl() {
  if (typeof window !== "undefined") return "";
  return (process.env.API_INTERNAL_URL ?? `http://127.0.0.1:${process.env.API_PORT ?? "8000"}`).replace(/\/$/, "");
}

export const api = createClient<paths>({ baseUrl: baseUrl() });

export type GetPath = PathsWithMethod<paths, "get">;
export type PostPath = PathsWithMethod<paths, "post">;

type JsonOf<R> = R extends { content: { "application/json": infer J } } ? J : never;
type Ok<Op> = Op extends { responses: infer Rs }
  ? 200 extends keyof Rs
    ? JsonOf<Rs[200]>
    : 201 extends keyof Rs
      ? JsonOf<Rs[201]>
      : never
  : never;

/** Success JSON body of `GET path`. */
export type GetData<P extends GetPath> = Ok<paths[P]["get"]>;
/** Success JSON body of `POST path`. */
export type PostData<P extends PostPath> = Ok<paths[P]["post"]>;
export type GetInit<P extends GetPath> = MaybeOptionalInit<paths[P], "get">;
export type PostInit<P extends PostPath> = MaybeOptionalInit<paths[P], "post">;
/** JSON request body of `POST path`. */
export type PostBody<P extends PostPath> = paths[P]["post"] extends { requestBody?: { content: { "application/json": infer B } } } ? B : never;

/** Demo request context injected into every call (the build plan §3). */
export type DemoRequestContext = {
  query: { as_of?: string; scenario_id?: string };
  headers: { "X-Demo-Session"?: string; "X-Demo-Role"?: string };
};

type AnyInit = { params?: { query?: Record<string, unknown>; path?: Record<string, unknown> }; body?: unknown; headers?: Record<string, string> };

function mergeInit(init: AnyInit | undefined, ctx: DemoRequestContext | null, withClock: boolean): AnyInit {
  const query = { ...(withClock && ctx ? ctx.query : {}), ...(init?.params?.query ?? {}) };
  return {
    ...init,
    params: { ...init?.params, query },
    headers: { ...(ctx?.headers ?? {}), ...(init?.headers ?? {}) } as Record<string, string>,
  };
}

async function run<T>(path: string, call: () => Promise<{ data?: unknown; error?: unknown; response: Response }>): Promise<T> {
  let result: { data?: unknown; error?: unknown; response: Response };
  try {
    result = await call();
  } catch (e) {
    if (e instanceof ApiRequestError) throw e;
    throw new ApiRequestError({ status: 0, code: "network_error", message: "The API could not be reached.", path });
  }
  const { data, error, response } = result;
  if (!response.ok || error !== undefined) {
    let body = error;
    if (typeof body === "string") {
      try {
        body = JSON.parse(body);
      } catch {
        /* non-JSON proxy error page */
      }
    }
    throw toApiError(path, response, body);
  }
  return data as T;
}

/**
 * Imperative typed GET. Prefer `useApiQuery` in components.
 * `withClock: false` omits `as_of` / `scenario_id` (e.g. for catalog endpoints).
 */
export function apiGet<P extends GetPath>(
  path: P,
  init: GetInit<P> | undefined,
  ctx: DemoRequestContext | null,
  opts: { withClock?: boolean; signal?: AbortSignal } = {},
): Promise<GetData<P>> {
  const merged = mergeInit(init as AnyInit | undefined, ctx, opts.withClock ?? true);
  return run<GetData<P>>(path, () =>
    (api.GET as (p: string, i: unknown) => Promise<{ data?: unknown; error?: unknown; response: Response }>)(path, {
      ...merged,
      signal: opts.signal,
    }),
  );
}

/** Imperative typed POST (writes need X-Demo-Session; the server answers 428 otherwise). */
export function apiPost<P extends PostPath>(
  path: P,
  init: PostInit<P> | undefined,
  ctx: DemoRequestContext | null,
  opts: { withClock?: boolean } = {},
): Promise<PostData<P>> {
  const merged = mergeInit(init as AnyInit | undefined, ctx, opts.withClock ?? true);
  return run<PostData<P>>(path, () =>
    (api.POST as (p: string, i: unknown) => Promise<{ data?: unknown; error?: unknown; response: Response }>)(path, merged),
  );
}
