import type { ApiError as ApiErrorEnvelope } from "@dml/contracts";

/**
 * Normalised API failure. Every non-2xx from the API uses the envelope
 * `{"error": {"code", "message", "details"}}` (the build plan §3); network/proxy failures are mapped too.
 */
export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId: string | null;
  readonly path: string;

  constructor(init: { status: number; code: string; message: string; details?: unknown; requestId?: string | null; path: string }) {
    super(init.message);
    this.name = "ApiRequestError";
    this.status = init.status;
    this.code = init.code;
    this.details = init.details ?? null;
    this.requestId = init.requestId ?? null;
    this.path = init.path;
  }

  /** Contract stub (HTTP 501, ADR-015): render <NotImplementedState>. */
  get isNotImplemented() {
    return this.status === 501 || this.code === "not_implemented";
  }
  /** API process unreachable / proxy failure. */
  get isUnavailable() {
    return this.status === 0 || this.code === "network_error" || this.code === "upstream_unavailable";
  }
  get isForbidden() {
    return this.status === 403;
  }
  get isRateLimited() {
    return this.status === 429;
  }
  /** Owner/task metadata from a 501 envelope (`details.owner`, `details.task`). */
  get stubInfo(): { owner?: string; task?: string } {
    const d = this.details as { owner?: unknown; task?: unknown } | null;
    return {
      owner: typeof d?.owner === "string" ? d.owner : undefined,
      task: typeof d?.task === "string" ? d.task : undefined,
    };
  }
}

export function isApiRequestError(e: unknown): e is ApiRequestError {
  return e instanceof ApiRequestError;
}

function isEnvelope(body: unknown): body is ApiErrorEnvelope {
  return (
    typeof body === "object" &&
    body !== null &&
    "error" in body &&
    typeof (body as { error: unknown }).error === "object" &&
    (body as { error: { code?: unknown } }).error !== null &&
    typeof (body as { error: { code?: unknown } }).error.code === "string"
  );
}

/** Build an ApiRequestError from a failed openapi-fetch result. */
export function toApiError(path: string, response: Response | undefined, body: unknown): ApiRequestError {
  const status = response?.status ?? 0;
  const requestId = response?.headers.get("x-request-id") ?? null;
  if (isEnvelope(body)) {
    return new ApiRequestError({
      status,
      code: body.error.code,
      message: body.error.message,
      details: body.error.details,
      requestId,
      path,
    });
  }
  if (status >= 500 || status === 0) {
    return new ApiRequestError({
      status,
      code: status === 0 ? "network_error" : "upstream_unavailable",
      message: status === 0 ? "The API could not be reached." : `The API returned HTTP ${status}.`,
      requestId,
      path,
    });
  }
  return new ApiRequestError({ status, code: "http_error", message: `HTTP ${status}`, requestId, path });
}
