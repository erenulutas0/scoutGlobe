import Link from "next/link";
import type { Candidate, Difference, SimilarPlayer } from "@scoutglobe/core";
import { formatMarketValue, formatSeason } from "@scoutglobe/core";
import { RemoteImage } from "@/features/shared/RemoteImage";
import { PercentileBar } from "@/features/discover/PercentileBar";
import { ShortlistToggle } from "@/features/shortlist/ShortlistToggle";

const POSITION_COLOR: Record<string, string> = {
  GK: "var(--color-pos-gk)",
  DF: "var(--color-pos-df)",
  MF: "var(--color-pos-mf)",
  FW: "var(--color-pos-fw)",
};

/**
 * Distance is a cosine distance, which means nothing to a scout on its own.
 * These bands are the reading, and they are deliberately coarse: the number
 * separates candidates well but does not support a claim like "87% similar".
 */
function similarityLabel(distance: number): string {
  if (distance < 0.05) return "çok yakın profil";
  if (distance < 0.12) return "yakın profil";
  if (distance < 0.25) return "benzer profil";
  return "uzaktan benzer";
}

function DifferenceRow({ difference }: { difference: Difference }) {
  const better = difference.gap > 0;
  const points = Math.round(Math.abs(difference.gap) * 100);
  return (
    <li className="flex items-center justify-between gap-2 text-xs">
      <span className="truncate text-text-muted">{difference.label}</span>
      <span
        className="stat shrink-0"
        style={{ color: better ? "var(--color-grass)" : "var(--color-alert-coral)" }}
      >
        {better ? "+" : "−"}
        {points} persentil
      </span>
    </li>
  );
}

export function CandidateCard({
  candidate,
  rank,
}: {
  candidate: Candidate | SimilarPlayer;
  rank?: number;
}) {
  const { player } = candidate;
  const similar = "distance" in candidate ? candidate : null;
  const positionColor = POSITION_COLOR[candidate.positionGroup] ?? "var(--color-text-muted)";

  return (
    <article className="glass-panel rounded-card p-4 transition-colors hover:bg-white/4">
      <div className="flex items-start gap-3">
        {rank !== undefined && (
          <span className="stat w-6 shrink-0 pt-1 text-sm text-text-muted">{rank}</span>
        )}

        <RemoteImage src={player.imageUrl} alt={player.fullName} size={48} className="shrink-0" />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <Link
              href={`/players/${player.id}`}
              className="truncate text-base hover:text-arc-out hover:underline"
            >
              {player.fullName}
            </Link>
            <span className="stat text-xs" style={{ color: positionColor }}>
              {candidate.positionGroup}
            </span>
            <ShortlistToggle playerId={player.id} name={player.fullName} className="ml-auto" />
          </div>

          {/* The club alone. The league belongs on the season line, because it
              is where these numbers were earned and not necessarily where the
              player is now: "West Ham United · Primeira Liga" read as though
              West Ham played in Portugal. */}
          <p className="mt-0.5 truncate text-xs text-text-muted">
            {candidate.clubName || "Kulüpsüz"}
          </p>

          <div className="stat mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
            <span>{player.age ?? "—"} yaş</span>
            <span>{formatMarketValue(player.marketValueEur)}</span>
            <span className="flex items-center gap-1.5">
              {formatSeason(candidate.season)}
              {candidate.leagueName && <span>· {candidate.leagueName}</span>}
              {/* Percentiles pool every league and are not strength-adjusted, so
                  a second-tier rank reads higher than it should. */}
              {candidate.leagueTier != null && candidate.leagueTier > 1 && (
                <span
                  className="shrink-0 rounded px-1 text-[10px]"
                  style={{
                    color: "var(--color-scout-amber)",
                    border:
                      "1px solid color-mix(in srgb, var(--color-scout-amber) 40%, transparent)",
                  }}
                  title="İkinci lig. Persentiller lig gücüne göre düzeltilmez."
                >
                  2. lig
                </span>
              )}
              <span>· {candidate.minutes} dk</span>
            </span>
            {similar && (
              <span style={{ color: "var(--color-arc-out)" }}>
                {similarityLabel(similar.distance)}
              </span>
            )}
          </div>
        </div>
      </div>

      {candidate.strengths.length > 0 && (
        <div className="mt-3 border-t border-stroke-panel pt-3">
          <p className="mb-2 text-[11px] tracking-wide text-text-muted uppercase">Neden bu oyuncu</p>
          <div className="flex flex-col gap-1.5">
            {candidate.strengths.map((note) => (
              <PercentileBar key={note.metric} note={note} tone="strength" />
            ))}
          </div>
        </div>
      )}

      {candidate.weaknesses.length > 0 && (
        <div className="mt-3 flex flex-col gap-1.5">
          <p className="text-[11px] tracking-wide text-text-muted uppercase">Zayıf yönü</p>
          {candidate.weaknesses.map((note) => (
            <PercentileBar key={note.metric} note={note} tone="weakness" />
          ))}
        </div>
      )}

      {similar && similar.differences.length > 0 && (
        <div className="mt-3 border-t border-stroke-panel pt-3">
          <p className="mb-2 text-[11px] tracking-wide text-text-muted uppercase">
            Referanstan farkı
          </p>
          <ul className="flex flex-col gap-1">
            {similar.differences.map((difference) => (
              <DifferenceRow key={difference.metric} difference={difference} />
            ))}
          </ul>
        </div>
      )}

      {candidate.strengths.length === 0 && (
        <p className="mt-3 border-t border-stroke-panel pt-3 text-xs text-text-muted">
          Bu sezonda 70. persentili geçen bir yönü yok — listeye başka bir ölçütle girdi.
        </p>
      )}
    </article>
  );
}
