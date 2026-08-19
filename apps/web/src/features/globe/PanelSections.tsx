"use client";

import Link from "next/link";
import { formatMarketValue } from "@scoutglobe/core";
import { RemoteImage } from "@/features/shared/RemoteImage";
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
            <RemoteImage src={league.logoUrl} alt={league.name} size={26} rounded="card" />
            <span className="min-w-0 flex-1">
              <span className="block truncate">{league.name}</span>
              <span className="stat block truncate text-xs text-text-muted">
                {league.season ?? "sezon verisi yok"}
              </span>
            </span>
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
    <>
      <p className="stat px-2 pb-2 text-xs text-text-muted">
        {league.squadSource === "live"
          ? "güncel kadro büyüklükleri"
          : league.squadSeason
            ? `${league.squadSeason} kadro büyüklükleri`
            : "kayıtlı oyuncu sayıları"}
      </p>
      <ul className="-mx-2 mt-1">
        {league.clubs.map((club) => (
          <li key={club.id}>
            <button type="button" className={ROW} onClick={() => selectClub(club.id)}>
              <RemoteImage src={club.logoUrl} alt={club.name} size={24} rounded="card" />
              <span className="flex-1 truncate">{club.name}</span>
              <span className="stat shrink-0 text-xs text-text-muted">{club.squadSize}</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

/** Level 3 — squad of the selected club. */
export function SquadList({ club }: { club: ClubDetail | undefined }) {
  if (!club) return <PanelSkeleton />;

  // Say what the list is: a live squad and a season's appearances are
  // different questions, and a January departure belongs only in the second.
  const basis =
    club.squadSource === "live"
      ? "güncel kadro"
      : club.squadSeason
        ? `${club.squadSeason} sezonunda oynayanlar`
        : "kayıtlı oyuncular";

  return (
    <>
      <p className="stat px-2 pb-2 text-xs text-text-muted">{basis}</p>
      <ul className="-mx-2 mt-1">
        {club.squad.map((player: PlayerSummary) => (
          <li key={player.id}>
            <Link href={`/players/${player.id}`} className={ROW}>
              <RemoteImage src={player.imageUrl} alt={player.fullName} size={30} />
              <span className="min-w-0 flex-1">
                <span className="block truncate">{player.fullName}</span>
                <span className="block truncate text-xs text-text-muted">
                  {player.position ?? "—"}
                  {player.age !== null && player.age !== undefined ? ` · ${player.age}` : ""}
                </span>
              </span>
              <span className="stat shrink-0 text-xs text-text-muted">
                {formatMarketValue(player.marketValueEur)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
