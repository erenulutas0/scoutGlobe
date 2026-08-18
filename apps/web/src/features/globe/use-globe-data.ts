"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

/** League nodes, country list and transfer arcs — one cached request (ARCHITECTURE §5). */
export function useGlobeSummary() {
  return useQuery({
    queryKey: ["globe", "summary"],
    queryFn: ({ signal }) => api.globeSummary(undefined, signal),
    staleTime: 5 * 60_000,
  });
}

export function useLeague(leagueId: number | null) {
  return useQuery({
    queryKey: ["league", leagueId],
    queryFn: ({ signal }) => api.league(leagueId as number, signal),
    enabled: leagueId !== null,
  });
}

export function useClub(clubId: number | null) {
  return useQuery({
    queryKey: ["club", clubId],
    queryFn: ({ signal }) => api.club(clubId as number, signal),
    enabled: clubId !== null,
  });
}
