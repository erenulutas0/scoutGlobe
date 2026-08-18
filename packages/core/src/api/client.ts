import { z } from "zod";
import { globeSummarySchema, healthSchema, leagueSchema } from "../schemas/domain";

/**
 * Minimal structural fetch type. We deliberately do NOT depend on DOM or Node
 * typings here so packages/core stays platform-agnostic (ARCHITECTURE.md §8).
 */
export type FetchLike = (
  input: string,
  init?: {
    method?: string;
    headers?: Record<string, string>;
    body?: string;
    signal?: unknown;
  },
) => Promise<{
  ok: boolean;
  status: number;
  json: () => Promise<unknown>;
  text: () => Promise<string>;
}>;

/** RFC 7807 problem+json — the API's single error shape (ARCHITECTURE.md §5). */
export const problemSchema = z.object({
  type: z.string().default("about:blank"),
  title: z.string(),
  status: z.number().int(),
  detail: z.string().optional(),
  instance: z.string().optional(),
});
export type Problem = z.infer<typeof problemSchema>;

export class ApiError extends Error {
  readonly status: number;
  readonly problem: Problem | null;

  constructor(message: string, status: number, problem: Problem | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.problem = problem;
  }
}

export interface ApiClientOptions {
  baseUrl: string;
  fetchImpl?: FetchLike;
}

function resolveFetch(explicit?: FetchLike): FetchLike {
  if (explicit) return explicit;
  const globalFetch = (globalThis as { fetch?: FetchLike }).fetch;
  if (!globalFetch) {
    throw new Error("No fetch implementation available — pass one via ApiClientOptions.fetchImpl.");
  }
  return globalFetch;
}

export function createApiClient({ baseUrl, fetchImpl }: ApiClientOptions) {
  const doFetch = resolveFetch(fetchImpl);
  const root = baseUrl.replace(/\/+$/, "");

  async function request<T>(
    path: string,
    schema: z.ZodType<T>,
    init?: { method?: string; body?: unknown; signal?: unknown },
  ): Promise<T> {
    const response = await doFetch(`${root}${path}`, {
      method: init?.method ?? "GET",
      headers: { "content-type": "application/json", accept: "application/json" },
      body: init?.body === undefined ? undefined : JSON.stringify(init.body),
      signal: init?.signal,
    });

    if (!response.ok) {
      const problem = problemSchema.safeParse(await response.json().catch(() => null));
      throw new ApiError(
        problem.success ? problem.data.title : `Request failed: ${path}`,
        response.status,
        problem.success ? problem.data : null,
      );
    }

    return schema.parse(await response.json());
  }

  return {
    request,
    health: (signal?: unknown) => request("/health", healthSchema, { signal }),
    globeSummary: (signal?: unknown) => request("/globe/summary", globeSummarySchema, { signal }),
    leagues: (signal?: unknown) => request("/leagues", z.array(leagueSchema), { signal }),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
