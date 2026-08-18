"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { FormPoint } from "@scoutglobe/core";
import { api } from "@/lib/api";

const METRICS = [
  { key: "goal_contributions", label: "Gol katkısı" },
  { key: "goals", label: "Gol" },
  { key: "assists", label: "Asist" },
  { key: "minutes", label: "Dakika" },
] as const;

const WIDTH = 640;
const HEIGHT = 200;
const PADDING = { top: 14, right: 10, bottom: 26, left: 34 };

function Chip({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full border px-3 py-1 text-xs transition-colors ${
        active
          ? "border-grass/50 bg-grass/12 text-text-primary"
          : "border-stroke-panel text-text-muted hover:text-text-primary"
      }`}
    >
      {children}
    </button>
  );
}

function Curve({ points, label }: { points: FormPoint[]; label: string }) {
  const usable = points.filter((point) => point.rolling !== null && point.rolling !== undefined);
  if (usable.length < 2) {
    return (
      <p className="stat py-8 text-center text-xs text-text-muted uppercase">
        Eğri için yeterli maç yok
      </p>
    );
  }

  const rolling = usable.map((point) => point.rolling as number);
  const raw = usable.map((point) => point.value ?? 0);
  const maxValue = Math.max(...rolling, ...raw, 1);

  const innerWidth = WIDTH - PADDING.left - PADDING.right;
  const innerHeight = HEIGHT - PADDING.top - PADDING.bottom;
  const step = innerWidth / Math.max(usable.length - 1, 1);

  const x = (index: number) => PADDING.left + index * step;
  const y = (value: number) => PADDING.top + innerHeight - (value / maxValue) * innerHeight;

  const line = rolling
    .map((value, index) => `${index === 0 ? "M" : "L"}${x(index).toFixed(1)},${y(value).toFixed(1)}`)
    .join(" ");

  const first = usable[0];
  const last = usable.at(-1);

  // Direction from the first third against the last third, not first point
  // against last: a single hot week at the start would otherwise paint a
  // clearly improving player red, contradicting the season table below.
  const third = Math.max(1, Math.floor(rolling.length / 3));
  const mean = (values: number[]) => values.reduce((sum, value) => sum + value, 0) / values.length;
  const rising = mean(rolling.slice(-third)) >= mean(rolling.slice(0, third));
  const stroke = rising ? "var(--color-grass)" : "var(--color-alert-coral)";

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="mt-3 w-full"
      role="img"
      aria-label={`${label} kayan ortalaması, ${usable.length} maç`}
    >
      {/* Per-match bars behind the curve: the raw signal the average smooths. */}
      {raw.map((value, index) => (
        <rect
          key={usable[index]?.matchId ?? index}
          x={x(index) - Math.min(step * 0.32, 7)}
          y={y(value)}
          width={Math.min(step * 0.64, 14)}
          height={Math.max(PADDING.top + innerHeight - y(value), 0)}
          fill="rgba(148,163,199,0.20)"
          rx="1.5"
        />
      ))}

      <path d={line} fill="none" stroke={stroke} strokeWidth="2.25" strokeLinejoin="round" />
      <circle cx={x(rolling.length - 1)} cy={y(rolling.at(-1) ?? 0)} r="3.5" fill={stroke} />

      <text x={4} y={PADDING.top + 4} className="stat" fontSize="10" fill="var(--color-text-muted)">
        {maxValue % 1 === 0 ? maxValue : maxValue.toFixed(1)}
      </text>
      <text
        x={PADDING.left}
        y={HEIGHT - 8}
        className="stat"
        fontSize="10"
        fill="var(--color-text-muted)"
      >
        {first?.playedOn?.slice(0, 7) ?? ""}
      </text>
      <text
        x={WIDTH - PADDING.right}
        y={HEIGHT - 8}
        textAnchor="end"
        className="stat"
        fontSize="10"
        fill="var(--color-text-muted)"
      >
        {last?.playedOn?.slice(0, 7) ?? ""}
      </text>
    </svg>
  );
}

/**
 * Match-by-match form: bars are single matches, the line is the rolling
 * average. The metric is the scout's choice, because "is he trending up"
 * means something different for a striker than for a holding midfielder.
 */
export function FormChart({ playerId }: { playerId: number }) {
  const [metric, setMetric] = useState<string>("goal_contributions");
  const [window, setWindow] = useState(5);

  const { data, isPending, isError } = useQuery({
    queryKey: ["player-form", playerId, metric, window],
    queryFn: ({ signal }) => api.playerForm(playerId, { metric, window, limit: 60 }, signal),
    staleTime: 5 * 60_000,
  });

  return (
    <section className="glass-panel rounded-card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="font-[family-name:var(--font-display)] text-xl tracking-[-0.02em]">
            Form eğrisi
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Çubuklar tek maç, çizgi {window} maçlık kayan ortalama.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="form-window" className="text-xs text-text-muted">
            Pencere
          </label>
          <select
            id="form-window"
            value={window}
            onChange={(event) => setWindow(Number(event.target.value))}
            className="stat rounded-lg border border-stroke-panel bg-transparent px-2 py-1 text-xs"
          >
            {[3, 5, 10].map((size) => (
              <option key={size} value={size} className="bg-panel-solid">
                {size}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {METRICS.map((option) => (
          <Chip
            key={option.key}
            active={option.key === metric}
            onClick={() => setMetric(option.key)}
          >
            {option.label}
          </Chip>
        ))}
      </div>

      {isPending && (
        <p className="stat py-8 text-center text-xs text-text-muted uppercase">Yükleniyor</p>
      )}
      {isError && (
        <p className="stat py-8 text-center text-xs text-alert-coral uppercase">
          Form verisi alınamadı
        </p>
      )}
      {data && <Curve points={data.series.points} label={data.series.metricLabel} />}

      {data && data.seasons.length > 0 && (
        <div className="mt-4 overflow-x-auto border-t border-stroke-panel pt-4">
          <table className="w-full min-w-[520px] border-collapse text-sm">
            <thead>
              <tr className="text-xs text-text-muted">
                <th className="px-2 py-1 text-left font-normal">Sezon</th>
                <th className="px-2 py-1 text-right font-normal">Maç</th>
                <th className="px-2 py-1 text-right font-normal">Dk</th>
                <th className="px-2 py-1 text-right font-normal">Maç başı dk</th>
                <th className="px-2 py-1 text-right font-normal">Gol</th>
                <th className="px-2 py-1 text-right font-normal">Asist</th>
                <th className="px-2 py-1 text-right font-normal">Gol/90</th>
              </tr>
            </thead>
            <tbody>
              {data.seasons.map((season) => (
                <tr key={season.season} className="border-t border-stroke-panel/60">
                  <td className="stat px-2 py-1.5">{season.season}</td>
                  <td className="stat px-2 py-1.5 text-right">{season.matches}</td>
                  <td className="stat px-2 py-1.5 text-right">{season.minutes}</td>
                  <td className="stat px-2 py-1.5 text-right">{season.minutesPerMatch}</td>
                  <td className="stat px-2 py-1.5 text-right">{season.goals}</td>
                  <td className="stat px-2 py-1.5 text-right">{season.assists}</td>
                  <td className="stat px-2 py-1.5 text-right">
                    {season.goalsPer90 === null || season.goalsPer90 === undefined
                      ? "—"
                      : season.goalsPer90.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
