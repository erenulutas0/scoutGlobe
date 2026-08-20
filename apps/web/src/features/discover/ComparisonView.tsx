"use client";

import Link from "next/link";
import type { Comparison, MetricNote } from "@scoutglobe/core";
import { formatMarketValue, formatSeason } from "@scoutglobe/core";
import { RemoteImage } from "@/features/shared/RemoteImage";
import { percentileLabel } from "@/features/discover/PercentileBar";

// One per column, in the order players were chosen.
const COLOURS = [
  "var(--color-arc-out)",
  "var(--color-scout-amber)",
  "var(--color-grass)",
  "var(--color-alert-coral)",
];

const WIDTH = 400;
const HEIGHT = 320;
const CENTRE_X = WIDTH / 2;
const CENTRE_Y = HEIGHT / 2;
const RADIUS = 100;
const RINGS = [0.25, 0.5, 0.75, 1];

function pointAt(index: number, count: number, fraction: number) {
  const angle = (index / count) * Math.PI * 2 - Math.PI / 2;
  return {
    x: CENTRE_X + Math.cos(angle) * RADIUS * fraction,
    y: CENTRE_Y + Math.sin(angle) * RADIUS * fraction,
  };
}

function polygon(points: { x: number; y: number }[]): string {
  return points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
}

/**
 * Two to four players on the axes they all have.
 *
 * Overlaid rather than side by side, because that is the only arrangement in
 * which two profiles can be read against each other at a glance. It only works
 * if every spoke means the same thing for everyone, which is why an axis one
 * player lacks is dropped from the chart and named underneath instead of being
 * left as a gap — a gap in an outline reads as a low score.
 */
export function ComparisonView({ data }: { data: Comparison }) {
  const chart = data.chartAxes;
  const count = chart.length;

  return (
    <div className="flex flex-col gap-5">
      <section className="glass-panel rounded-card p-5">
        <div className="flex flex-wrap items-start gap-6">
          {count >= 3 && (
            <svg
              viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
              className="h-auto w-full max-w-[400px] shrink-0"
              role="img"
              aria-label={`${data.players.map((p) => p.player.fullName).join(", ")} karşılaştırması`}
            >
              {RINGS.map((ring) => (
                <polygon
                  key={ring}
                  points={polygon(chart.map((_, index) => pointAt(index, count, ring)))}
                  fill="none"
                  stroke="var(--color-stroke-panel)"
                  strokeWidth={ring === 0.5 ? 1.2 : 0.6}
                  strokeDasharray={ring === 0.5 ? "3 3" : undefined}
                />
              ))}

              {chart.map((metric, index) => {
                const spoke = pointAt(index, count, 1);
                const label = pointAt(index, count, 1.16);
                const anchor =
                  label.x > CENTRE_X + 4 ? "start" : label.x < CENTRE_X - 4 ? "end" : "middle";
                return (
                  <g key={metric}>
                    <line
                      x1={CENTRE_X}
                      y1={CENTRE_Y}
                      x2={spoke.x}
                      y2={spoke.y}
                      stroke="var(--color-stroke-panel)"
                    />
                    <text
                      x={label.x}
                      y={label.y}
                      textAnchor={anchor}
                      dominantBaseline="middle"
                      fontSize={9}
                      fill="var(--color-text-muted)"
                    >
                      {data.labels[metric]}
                    </text>
                  </g>
                );
              })}

              {data.players.map((player, playerIndex) => {
                const colour = COLOURS[playerIndex % COLOURS.length];
                const shape = chart.map((metric, index) =>
                  pointAt(index, count, player.axes[metric]?.percentile ?? 0),
                );
                return (
                  <polygon
                    key={player.player.id}
                    points={polygon(shape)}
                    fill={colour}
                    fillOpacity={0.12}
                    stroke={colour}
                    strokeWidth={1.8}
                    strokeLinejoin="round"
                  />
                );
              })}
            </svg>
          )}

          <div className="flex min-w-[14rem] flex-1 flex-col gap-3">
            {data.players.map((player, index) => (
              <div key={player.player.id} className="flex items-center gap-3">
                <span
                  aria-hidden
                  className="h-3 w-3 shrink-0 rounded-sm"
                  style={{ backgroundColor: COLOURS[index % COLOURS.length] }}
                />
                <RemoteImage
                  src={player.player.imageUrl}
                  alt={player.player.fullName}
                  size={34}
                  className="shrink-0"
                />
                <span className="min-w-0 flex-1">
                  <Link
                    href={`/players/${player.player.id}`}
                    className="block truncate text-sm hover:text-arc-out hover:underline"
                  >
                    {player.player.fullName}
                  </Link>
                  <span className="stat block truncate text-[11px] text-text-muted">
                    {player.player.age ?? "—"} yaş ·{" "}
                    {formatMarketValue(player.player.marketValueEur)} ·{" "}
                    {formatSeason(player.season)}
                    {player.leagueName ? ` · ${player.leagueName}` : ""}
                    {player.leagueTier != null && player.leagueTier > 1 ? " (2. lig)" : ""}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </div>

        {(data.note || data.droppedLabels.length > 0) && (
          <p className="stat mt-4 border-t border-stroke-panel pt-3 text-[11px] text-text-muted">
            {data.note && (
              <span style={{ color: "var(--color-scout-amber)" }}>{data.note} </span>
            )}
            {data.droppedLabels.length > 0 && (
              <>
                Ortak olmadığı için dışarıda kalan metrikler:{" "}
                {data.droppedLabels.join(", ")}. Birinde eksik bir eksen grafikte boşluk
                bırakır, boşluk da &quot;düşük&quot; diye okunur.
              </>
            )}
          </p>
        )}
      </section>

      <section className="glass-panel rounded-card overflow-x-auto p-5">
        <h2 className="font-[family-name:var(--font-display)] text-xl tracking-[-0.02em]">
          Ortak metrikler
        </h2>
        <p className="mt-1 mb-4 text-sm text-text-muted">
          Renkli rakam persentil, yanındaki soluk rakam per-90 değeri. Her satırın en iyisi
          o oyuncunun renginde.
        </p>

        <table className="w-full min-w-[520px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-stroke-panel text-xs text-text-muted">
              <th className="px-3 py-2 text-left font-normal">Metrik</th>
              {data.players.map((player, index) => (
                <th key={player.player.id} className="px-3 py-2 text-right font-normal">
                  <span style={{ color: COLOURS[index % COLOURS.length] }}>
                    {player.player.fullName}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.axes.map((metric) => {
              const values = data.players.map((player) => player.axes[metric]);
              const best = Math.max(...values.map((note) => note?.percentile ?? 0));
              return (
                <tr key={metric} className="border-b border-stroke-panel/60">
                  <td className="px-3 py-2 text-text-muted">{data.labels[metric]}</td>
                  {values.map((note: MetricNote | undefined, index) => (
                    <td
                      key={data.players[index]?.player.id ?? index}
                      className="stat px-3 py-2 text-right"
                    >
                      <span
                        style={{
                          color:
                            note && note.percentile === best
                              ? COLOURS[index % COLOURS.length]
                              : "var(--color-text-primary)",
                        }}
                      >
                        {note ? percentileLabel(note.percentile) : "—"}
                      </span>
                      <span className="ml-2 text-[11px] text-text-muted">
                        {note?.per90 === null || note?.per90 === undefined
                          ? ""
                          : note.per90.toFixed(2)}
                      </span>
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}
