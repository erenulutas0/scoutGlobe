import type { MetricNote } from "@scoutglobe/core";

/**
 * One metric, shown as where the player sits among his peers.
 *
 * The bar is the percentile and the number beside it is the per-90 rate, because
 * a scout checks the rate and argues with the rank. The population size is
 * always printed: expected-goals metrics are ranked against five leagues while
 * shooting volume covers twelve, and a percentile that hides which one it came
 * from is claiming a comparison nobody made.
 *
 * Percentiles are floored, never rounded. The best of 822 players sits at
 * 0.9994, and rounding that to "100" would say he is ahead of everyone
 * including himself.
 */

const TONE = {
  strength: "var(--color-grass)",
  weakness: "var(--color-alert-coral)",
  neutral: "var(--color-arc-out)",
} as const;

export type Tone = keyof typeof TONE;

export function percentileLabel(percentile: number): string {
  return String(Math.floor(percentile * 100));
}

export function PercentileBar({ note, tone = "strength" }: { note: MetricNote; tone?: Tone }) {
  const percent = Math.min(100, Math.max(0, note.percentile * 100));

  return (
    <div className="flex items-center gap-3">
      <span className="min-w-0 flex-1 truncate text-xs text-text-primary">{note.label}</span>

      <div
        className="h-1.5 w-24 shrink-0 overflow-hidden rounded-full bg-white/8"
        role="img"
        aria-label={`${note.label}: ${percentileLabel(note.percentile)}. persentil, ${note.sampleSize} oyuncu içinde`}
      >
        <div
          className="h-full rounded-full"
          style={{ width: `${percent}%`, backgroundColor: TONE[tone] }}
        />
      </div>

      <span className="stat w-8 shrink-0 text-right text-xs" style={{ color: TONE[tone] }}>
        {percentileLabel(note.percentile)}
      </span>

      <span className="stat w-20 shrink-0 text-right text-[11px] text-text-muted">
        {note.per90 === null || note.per90 === undefined ? "—" : note.per90.toFixed(2)}
        <span className="ml-1 opacity-70">n={note.sampleSize}</span>
      </span>
    </div>
  );
}
