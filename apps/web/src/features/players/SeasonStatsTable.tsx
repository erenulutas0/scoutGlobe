import type { SeasonStats } from "@scoutglobe/core";
import { MIN_MINUTES_FOR_PER90, formatSeason, formatStat } from "@scoutglobe/core";

const SOURCE_LABELS: Record<string, string> = {
  fbref: "FBref",
  understat: "Understat",
  "api-football": "API-Football",
  transfermarkt: "Transfermarkt",
};

function Cell({ children, muted = false }: { children: React.ReactNode; muted?: boolean }) {
  return (
    <td className={`stat px-3 py-2 text-right ${muted ? "text-text-muted" : ""}`}>{children}</td>
  );
}

/**
 * Season statistics, one row per source.
 *
 * Sources are shown side by side rather than merged: FBref and Understat count
 * minutes differently, and hiding that would invent a precision the data does
 * not have. Per-90 columns are empty below the 900-minute gate — the API
 * returns null there and the table says "—" instead of a misleading number.
 */
export function SeasonStatsTable({ stats }: { stats: SeasonStats[] }) {
  if (stats.length === 0) {
    return (
      <p className="stat py-6 text-center text-xs text-text-muted uppercase">
        Sezon istatistiği yok
      </p>
    );
  }

  const belowGate = stats.some(
    (row) => (row.minutes ?? 0) > 0 && (row.minutes ?? 0) < MIN_MINUTES_FOR_PER90,
  );

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-stroke-panel text-xs text-text-muted">
            <th className="px-3 py-2 text-left font-normal">Sezon</th>
            <th className="px-3 py-2 text-left font-normal">Kaynak</th>
            <th className="px-3 py-2 text-right font-normal">Dk</th>
            <th className="px-3 py-2 text-right font-normal">Maç</th>
            <th className="px-3 py-2 text-right font-normal">Gol</th>
            <th className="px-3 py-2 text-right font-normal">Asist</th>
            <th className="px-3 py-2 text-right font-normal">xG</th>
            <th className="px-3 py-2 text-right font-normal">xA</th>
            <th className="px-3 py-2 text-right font-normal">Gol/90</th>
            <th className="px-3 py-2 text-right font-normal">Asist/90</th>
          </tr>
        </thead>
        <tbody>
          {stats.map((row) => (
            <tr
              key={`${row.season}-${row.source}-${row.clubId}`}
              className="border-b border-stroke-panel/60 transition-colors hover:bg-white/4"
            >
              <td className="stat px-3 py-2">{formatSeason(row.season.slice(0, 4))}</td>
              <td className="px-3 py-2 text-xs text-text-muted">
                {SOURCE_LABELS[row.source] ?? row.source}
                {row.clubName ? ` · ${row.clubName}` : ""}
              </td>
              <Cell>{row.minutes ?? "—"}</Cell>
              <Cell>{row.matches ?? "—"}</Cell>
              <Cell>{row.goals ?? "—"}</Cell>
              <Cell>{row.assists ?? "—"}</Cell>
              <Cell muted={row.xg === null || row.xg === undefined}>{formatStat(row.xg, 1)}</Cell>
              <Cell muted={row.xa === null || row.xa === undefined}>{formatStat(row.xa, 1)}</Cell>
              <Cell>{formatStat(row.goalsPer90)}</Cell>
              <Cell>{formatStat(row.assistsPer90)}</Cell>
            </tr>
          ))}
        </tbody>
      </table>

      {belowGate && (
        <p className="mt-3 text-xs text-text-muted">
          Per-90 değerleri {MIN_MINUTES_FOR_PER90} dakikanın altındaki sezonlarda hesaplanmaz —
          küçük örneklemde yanıltıcı olur.
        </p>
      )}
    </div>
  );
}
