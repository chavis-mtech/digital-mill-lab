"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useDemo } from "@/lib/demo/context";
import {
  apiGet,
  apiPost,
  type GetData,
  type GetInit,
  type GetPath,
  type PostData,
  type PostInit,
  type PostPath,
} from "./client";
import type { ApiRequestError } from "./errors";

export type ApiQueryOptions<TData> = Omit<UseQueryOptions<TData, ApiRequestError, TData>, "queryKey" | "queryFn"> & {
  /** Send the demo clock (`as_of`, `scenario_id`). Default true. Set false for catalogs/static metadata. */
  withClock?: boolean;
};

/** Stable query key: path + params + demo context (so switching scenario/role/clock refetches). */
export function apiQueryKey(path: string, init: unknown, ctx: { query: unknown; headers: unknown } | null) {
  return ["api", path, init ?? null, ctx?.query ?? null, (ctx?.headers as Record<string, string> | undefined)?.["X-Demo-Role"] ?? null] as const;
}

/**
 * Typed GET bound to DemoContext.
 *
 * @example
 *   const q = useApiQuery("/api/v1/executive/kpis", { params: { query: { period } } });
 *   return <QueryState query={q}>{(data) => <KpiGrid kpis={data.kpis} />}</QueryState>;
 */
export function useApiQuery<P extends GetPath>(
  path: P,
  init?: GetInit<P>,
  options: ApiQueryOptions<GetData<P>> = {},
): UseQueryResult<GetData<P>, ApiRequestError> {
  const demo = useDemo();
  const { withClock = true, ...rest } = options;
  const ctx = withClock ? demo.request : { query: {}, headers: demo.request.headers };
  const { enabled, ...restOptions } = rest;
  return useQuery<GetData<P>, ApiRequestError>({
    queryKey: apiQueryKey(path, init, ctx),
    queryFn: ({ signal }) => apiGet(path, init, ctx, { withClock, signal }),
    ...restOptions,
    // Wait for the demo state (clock, role, session) to be read from the URL/storage: otherwise the first request
    // is sent with defaults and repeated after hydration (double API load, flash of wrong-clock data).
    enabled: (query) => demo.ready && (typeof enabled === "function" ? enabled(query) : (enabled ?? true)),
  });
}

/**
 * Typed POST bound to DemoContext (session + role headers, clock). Invalidates `invalidate` path prefixes
 * on success. UI rule (SPEC §0.4): wrap record-changing calls in <ConfirmDialog> first.
 */
export function useApiMutation<P extends PostPath>(
  path: P,
  options: Omit<UseMutationOptions<PostData<P>, ApiRequestError, PostInit<P>>, "mutationFn"> & {
    invalidate?: GetPath[];
    withClock?: boolean;
  } = {},
) {
  const demo = useDemo();
  const qc = useQueryClient();
  const { invalidate = [], withClock = true, onSuccess, ...rest } = options;
  return useMutation<PostData<P>, ApiRequestError, PostInit<P>>({
    mutationFn: (init) => apiPost(path, init, demo.request, { withClock }),
    onSuccess: async (...args) => {
      await Promise.all(invalidate.map((p) => qc.invalidateQueries({ queryKey: ["api", p] })));
      await onSuccess?.(...args);
    },
    ...rest,
  });
}
