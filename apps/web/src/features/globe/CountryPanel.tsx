"use client";

import { useEffect } from "react";
import { useClub, useGlobeSummary, useLeague } from "./use-globe-data";
import { useGlobeStore } from "./globe-store";
import { ClubList, LeagueList, SquadList } from "./PanelSections";
import { useCountries } from "./use-countries";

/**
 * Right-hand glass panel (DESIGN.md §4): country -> league -> club -> squad.
 * Covers at most ~35% of the globe on desktop, becomes a bottom sheet on mobile.
 */
export function CountryPanel() {
  const selectedId = useGlobeStore((state) => state.selectedId);
  const selectedLeagueId = useGlobeStore((state) => state.selectedLeagueId);
  const selectedClubId = useGlobeStore((state) => state.selectedClubId);
  const selectCountry = useGlobeStore((state) => state.selectCountry);
  const goBack = useGlobeStore((state) => state.goBack);

  const { data: countries } = useCountries();
  const { data: summary } = useGlobeSummary();
  const { data: league } = useLeague(selectedLeagueId);
  const { data: club } = useClub(selectedClubId);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") goBack();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [goBack]);

  if (!selectedId) {
    return (
      <div className="pointer-events-none absolute inset-x-0 bottom-8 flex justify-center px-4">
        <p className="glass-panel rounded-card px-4 py-2 text-sm text-text-muted">
          Bir ülkeye tıklayarak başla.
        </p>
      </div>
    );
  }

  const meta = countries?.meta[selectedId];
  const countryCode = meta?.code ?? null;

  const level = selectedClubId !== null ? "club" : selectedLeagueId !== null ? "league" : "country";
  const heading =
    level === "club"
      ? (club?.name ?? "Kulüp")
      : level === "league"
        ? (league?.name ?? "Lig")
        : (meta?.nameTr ?? "Bilinmeyen ülke");
  const eyebrow =
    level === "club"
      ? (club?.leagueName ?? "Kadro")
      : level === "league"
        ? (meta?.nameTr ?? "Lig")
        : "Ülke";

  return (
    <aside
      aria-label="Keşif paneli"
      className="glass-panel absolute inset-x-3 bottom-3 flex max-h-[52dvh] flex-col rounded-card p-5 transition-[opacity,transform] duration-200 ease-out md:inset-y-16 md:right-4 md:left-auto md:max-h-none md:w-[clamp(300px,28vw,380px)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="stat text-xs tracking-[0.16em] text-text-muted uppercase">{eyebrow}</p>
          <h2 className="truncate font-[family-name:var(--font-display)] text-2xl leading-tight tracking-[-0.02em]">
            {heading}
          </h2>
        </div>
        <div className="flex shrink-0 gap-1">
          {level !== "country" && (
            <button
              type="button"
              onClick={goBack}
              aria-label="Geri"
              className="rounded-full border border-stroke-panel px-2 py-0.5 text-text-muted transition-colors hover:text-text-primary"
            >
              ←
            </button>
          )}
          <button
            type="button"
            onClick={() => selectCountry(null)}
            aria-label="Paneli kapat"
            className="rounded-full border border-stroke-panel px-2 py-0.5 text-text-muted transition-colors hover:text-text-primary"
          >
            ×
          </button>
        </div>
      </div>

      <div className="mt-4 min-h-0 flex-1 overflow-y-auto border-t border-stroke-panel pt-3">
        {level === "country" && <LeagueList summary={summary} countryCode={countryCode} />}
        {level === "league" && <ClubList league={league} />}
        {level === "club" && <SquadList club={club} />}
      </div>
    </aside>
  );
}
