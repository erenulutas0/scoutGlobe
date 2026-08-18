"use client";

import { formatMarketValue } from "@scoutglobe/core";
import type { ClubDetail, LeagueDetail, PlayerSummary } from "@scoutglobe/core";
import type { GlobeSummary } from "@scoutglobe/core";
import { useGlobeStore } from "./globe-store";

const ROW =
  "flex w-full items-center justify-between gap-3 rounded-lg px-2 py-2 text-left transition-colors hover:bg-white/4";

export function PanelSkeleton({ label = "Yükleniyor" }: { label?: string }) {
  return <p className="stat py-6 text-center text-xs text-text-muted uppercase">{label}</p>;
}

/** Level 1 — leagues of the selected country. */
export function LeagueList({
  summary,
  countryCode,
}: {
  summary: GlobeSummary | undefined;
  countryCode: string | null;
}) {
  const selectLeague = useGlobeStore((state) => state.selectLeague);
  const leagues = (summary?.leagues ?? []).filter((league) => league.countryCode === countryCode);

  if (!summary) return <PanelSkeleton />;
  if (leagues.length === 0) {
    return (
      <p className="py-4 text-sm text-text-muted">
        Bu ülke için henüz lig verisi yok. Şu an Big-5 ve Süper Lig yüklü.
      </p>
    );
  }

  return (
    <ul className="-mx-2 mt-1">
      {leagues.map((league) => (
        <li key={league.leagueId}>
          <button type="button" className={ROW} onClick={() => selectLeague(league.leagueId)}>
            <span className="truncate">{league.name}</span>
            <span className="stat shrink-0 text-xs text-text-muted">
              {league.clubCount} kulüp · {league.playerCount} oyuncu
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Level 2 — clubs of the selected league. */
export function ClubList({ league }: { league: LeagueDetail | undefined }) {
  const selectClub = useGlobeStore((state) => state.selectClub);
  if (!league) return <PanelSkeleton />;

  return (
    <ul className="-mx-2 mt-1">
      {league.clubs.map((club) => (
        <li key={club.id}>
          <button type="button" className={ROW} onClick={() => selectClub(club.id)}>
            <span className="truncate">{club.name}</span>
            <span className="stat shrink-0 text-xs text-text-muted">{club.squadSize}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Level 3 — squad of the selected club. */
export function SquadList({ club }: { club: ClubDetail | undefined }) {
  if (!club) return <PanelSkeleton />;

  return (
    <ul className="-mx-2 mt-1">
      {club.squad.map((player: PlayerSummary) => (
        <li
          key={player.id}
          className="flex items-center justify-between gap-3 rounded-lg px-2 py-2"
        >
          <span className="min-w-0">
            <span className="block truncate">{player.fullName}</span>
            <span className="block truncate text-xs text-text-muted">
              {player.position ?? "—"}
              {player.age !== null && player.age !== undefined ? ` · ${player.age}` : ""}
            </span>
          </span>
          <span className="stat shrink-0 text-xs text-text-muted">
            {formatMarketValue(player.marketValueEur)}
          </span>
        </li>
      ))}
    </ul>
  );
}
