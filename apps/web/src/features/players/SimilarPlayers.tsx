import { ApiError } from "@scoutglobe/core";
import { CandidateCard } from "@/features/discover/CandidateCard";
import { PercentileBar } from "@/features/discover/PercentileBar";
import { api } from "@/lib/api";

/**
 * Players whose role profile points the same way as this one.
 *
 * Rendered on the server alongside the profile, and silent about nothing: a
 * player under the 900-minute gate, a goalkeeper, or an unmatched profile each
 * get the reason instead of an empty list.
 */
export async function SimilarPlayers({ playerId }: { playerId: number }) {
  let data;
  try {
    data = await api.similarPlayers(playerId, { limit: 6 });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return (
        <section className="glass-panel rounded-card p-5">
          <h2 className="font-[family-name:var(--font-display)] text-xl tracking-[-0.02em]">
            Benzer profiller
          </h2>
          <p className="mt-2 text-sm text-text-muted">
            {error.problem?.detail ??
              "Bu oyuncunun karşılaştırılabilir bir sezonu yok, benzerlik hesaplanamadı."}
          </p>
        </section>
      );
    }
    throw error;
  }

  return (
    <section className="glass-panel rounded-card p-5">
      <h2 className="font-[family-name:var(--font-display)] text-xl tracking-[-0.02em]">
        Benzer profiller
      </h2>
      <p className="mt-1 text-sm text-text-muted">
        {data.reference.season} sezonu, {data.reference.positionGroup} grubu içinde
        karşılaştırıldı. Benzerlik oyuncunun profilinin <em>şekline</em> bakar; daha ucuz bir
        oyuncunun aynı işi biraz daha az yapması onu benzer olmaktan çıkarmaz.
      </p>

      {data.reference.strengths.length > 0 && (
        <div className="mt-4 rounded-md border border-stroke-panel p-3">
          <p className="mb-2 text-[11px] tracking-wide text-text-muted uppercase">
            Referans profili
          </p>
          <div className="flex flex-col gap-1.5">
            {data.reference.strengths.map((note) => (
              <PercentileBar key={note.metric} note={note} tone="neutral" />
            ))}
          </div>
        </div>
      )}

      {data.note && <p className="mt-4 text-sm text-text-muted">{data.note}</p>}

      {/* One column: two columns squeeze the metric labels down to "İsabet or…",
          and the label is the entire point of showing a percentile. */}
      {data.items.length > 0 && (
        <div className="mt-4 flex flex-col gap-3">
          {data.items.map((candidate, index) => (
            <CandidateCard key={candidate.player.id} candidate={candidate} rank={index + 1} />
          ))}
        </div>
      )}
    </section>
  );
}
