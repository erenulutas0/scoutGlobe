import { z } from "zod";
import {
  clubDetailSchema,
  dataFreshnessSchema,
  discoverResultSchema,
  discoveryOptionsSchema,
  globeSummarySchema,
  healthSchema,
  leagueDetailSchema,
  leagueSchema,
  playerDetailSchema,
  playerFormSchema,
  playerSearchResultSchema,
  playerRadarSchema,
  playerShotsSchema,
  similarPlayersSchema,
  transferBoardSchema,
} from "../schemas/domain";
import type { operations } from "./schema";

/** Query parameters, taken straight from the generated OpenAPI contract. */
export type PlayerSearchParams = NonNullable<
  operations["search_players_players_search_get"]["parameters"]["query"]
>;
export type LeagueListParams = NonNullable<
  operations["list_leagues_leagues_get"]["parameters"]["query"]
>;
export type DiscoverParams = NonNullable<
  operations["discover_players_discover_get"]["parameters"]["query"]
>;
export type SimilarParams = NonNullable<
  operations["similar_discover_similar__player_id__get"]["parameters"]["query"]
>;
export type TransferBoardParams = NonNullable<
  operations["transfer_board_transfers_get"]["parameters"]["query"]
>;

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

  /**
   * Serialises query parameters with encodeURIComponent rather than
   * URLSearchParams: the latter is a host object, and packages/core must not
   * depend on DOM or Node typings (ARCHITECTURE.md §8).
   */
  function withQuery(path: string, params?: Record<string, unknown>): string {
    if (!params) return path;

    const parts: string[] = [];
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null || value === "") continue;
      // Repeated keys, not a comma-joined string: FastAPI reads `league_id=1&
      // league_id=2` as a list, and a joined value would arrive as one bad int.
      const values = Array.isArray(value) ? value : [value];
      for (const entry of values) {
        if (entry === undefined || entry === null || entry === "") continue;
        parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(entry))}`);
      }
    }
    return parts.length > 0 ? `${path}?${parts.join("&")}` : path;
  }

  return {
    request,
    health: (signal?: unknown) => request("/health", healthSchema, { signal }),

    freshness: (signal?: unknown) => request("/meta/freshness", dataFreshnessSchema, { signal }),

    globeSummary: (params?: { season?: string }, signal?: unknown) =>
      request(withQuery("/globe/summary", params), globeSummarySchema, { signal }),

    leagues: (params?: LeagueListParams, signal?: unknown) =>
      request(withQuery("/leagues", params), z.array(leagueSchema), { signal }),

    league: (leagueId: number, signal?: unknown) =>
      request(`/leagues/${leagueId}`, leagueDetailSchema, { signal }),

    club: (clubId: number, signal?: unknown) =>
      request(`/clubs/${clubId}`, clubDetailSchema, { signal }),

    player: (playerId: number, signal?: unknown) =>
      request(`/players/${playerId}`, playerDetailSchema, { signal }),

    playerForm: (
      playerId: number,
      params?: { metric?: string; window?: number; limit?: number },
      signal?: unknown,
    ) => request(withQuery(`/players/${playerId}/form`, params), playerFormSchema, { signal }),

    playerShots: (
      playerId: number,
      params?: { season?: string; limit?: number },
      signal?: unknown,
    ) => request(withQuery(`/players/${playerId}/shots`, params), playerShotsSchema, { signal }),

    searchPlayers: (params?: PlayerSearchParams, signal?: unknown) =>
      request(withQuery("/players/search", params), playerSearchResultSchema, { signal }),

    discoveryOptions: (signal?: unknown) =>
      request("/discover/options", discoveryOptionsSchema, { signal }),

    discover: (params: DiscoverParams, signal?: unknown) =>
      request(withQuery("/discover", params), discoverResultSchema, { signal }),

    transfers: (params?: TransferBoardParams, signal?: unknown) =>
      request(withQuery("/transfers", params), transferBoardSchema, { signal }),

    playerRadar: (playerId: number, params?: { season?: string }, signal?: unknown) =>
      request(withQuery(`/discover/radar/${playerId}`, params), playerRadarSchema, { signal }),

    similarPlayers: (playerId: number, params?: SimilarParams, signal?: unknown) =>
      request(withQuery(`/discover/similar/${playerId}`, params), similarPlayersSchema, {
        signal,
      }),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
