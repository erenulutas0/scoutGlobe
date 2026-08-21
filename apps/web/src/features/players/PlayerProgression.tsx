import type { Progression } from "@scoutglobe/core";
import { ApiError } from "@scoutglobe/core";
import { ProgressionChart } from "./ProgressionChart";
import { api } from "@/lib/api";

/**
 * Loads the development curve, or says why there isn't one.
 *
 * A player under the minutes gate has no measured season and therefore no
 * trend; that is a fact about our data, not about him, so it is stated rather
 * than rendered as an empty chart.
 *
 * Fetch first, render after: JSX built inside the try would look like it caught
 * rendering errors, and React renders the element long after the try has exited.
 */
export async function PlayerProgression({ playerId }: { playerId: number }) {
  let data: Progression | null = null;
  let missing: string | null = null;

  try {
    data = await api.playerProgression(playerId);
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 404) throw error;
    missing = error.problem?.detail ?? "Bu oyuncunun ölçülmüş bir sezonu yok.";
  }

  if (data) return <ProgressionChart data={data} />;

  return (
    <section className="glass-panel rounded-card p-5">
      <h2 className="font-[family-name:var(--font-display)] text-xl tracking-[-0.02em]">
        Gelişim eğrisi
      </h2>
      <p className="mt-2 text-sm text-text-muted">{missing}</p>
    </section>
  );
}
