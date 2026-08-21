"use client";

import { useState } from "react";
import type { Progression, ProgressionSeason } from "@scoutglobe/core";
import { formatSeason } from "@scoutglobe/core";
import { percentileLabel } from "@/features/discover/PercentileBar";

const POSITION_COLOR: Record<string, string> = {
  GK: "var(--color-pos-gk)",
  DF: "var(--color-pos-df)",
  MF: "var(--color-pos-mf)",
  FW: "var(--color-pos-fw)",
};

const WIDTH = 640;
const HEIGHT = 220;
const PAD = { top: 18, right: 22, bottom: 44, left: 34 };
const PLOT_W = WIDTH - PAD.left - PAD.right;
const PLOT_H = HEIGHT - PAD.top - PAD.bottom;

/** The whole scale is a percentile, so the band is always 0-100. */
function y(value: number): number {
  return PAD.top + PLOT_H * (1 - Math.min(1, Math.max(0, value)));
}

function x(index: number, count: number): number {
  if (count <= 1) return PAD.left + PLOT_W / 2;
  return PAD.left + (PLOT_W * index) / (count - 1);
}

/** The value being plotted: the whole profile, or one axis of it. */
function valueOf(season: ProgressionSeason, metric: string): number | null {
  if (metric === "profile") return season.profile ?? null;
  return season.axes[metric]?.percentile ?? null;
}

/**
 * Season by season, on one percentile scale.
 *
 * A single season is a photograph; the question a scout is actually asking is
 * whether the player is getting better. That only reads honestly if the
 * seasons were ranked against comparable fields, so the number of players
 * behind each point is drawn under it — our coverage grew from five leagues to
 * twenty-nine, and an unchanged player's percentile rises on its own when the
 * field widens.
 */
export function ProgressionChart({ data }: { data: Progression }) {
  const [metric, setMetric] = useState("profile");
  const seasons = data.seasons;
  const colour = POSITION_COLOR[seasons.at(-1)?.positionGroup ?? "FW"] ?? "var(--color-arc-out)";

  const points = seasons
    .map((season, index) => {
      const value = valueOf(season, metric);
      return value === null ? null : { index, value, season };
    })
    .filter((point): point is { index: number; value: number; season: ProgressionSeason } =>
      point !== null,
    );

  const first = points.at(0)?.value;
  const last = points.at(-1)?.value;
  const delta = first !== undefined && last !== undefined ? last - first : null;

  const line = points
    .map((point) => `${x(point.index, seasons.length).toFixed(1)},${y(point.value).toFixed(1)}`)
    .join(" ");

  return (
    <section className="glass-panel rounded-card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="font-[family-name:var(--font-display)] text-xl tracking-[-0.02em]">
          Gelişim eğrisi
        </h2>
        {delta !== null && points.length > 1 && (
          <span
            className="stat text-sm"
            style={{
              color:
                delta > 0.02
                  ? "var(--color-grass)"
                  : delta < -0.02
                    ? "var(--color-alert-coral)"
                    : "var(--color-text-muted)",
            }}
          >
            {delta > 0 ? "+" : ""}
            {Math.round(delta * 100)} persentil
          </span>
        )}
      </div>

      <p className="mt-1 text-sm text-text-muted">
        Her nokta bir sezonun persentili. Altındaki rakam o sezon kaç oyuncuyla
        karşılaştırıldığı.
      </p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {[{ metric: "profile", label: "Genel profil" }].concat(
          data.axes.map((axis) => ({ metric: axis, label: data.labels[axis] ?? axis })),
        ).map((option) => (
          <button
            key={option.metric}
            type="button"
            onClick={() => setMetric(option.metric)}
            className="stat rounded-md border px-2 py-1 text-[11px] transition-colors"
            style={{
              borderColor:
                metric === option.metric
                  ? colour
                  : "color-mix(in srgb, var(--color-text-muted) 30%, transparent)",
              color: metric === option.metric ? colour : "var(--color-text-muted)",
            }}
          >
            {option.label}
          </button>
        ))}
      </div>

      {points.length === 0 ? (
        <p className="mt-4 text-sm text-text-muted">
          Bu metrik hiçbir sezonda yeterli örnekle ölçülmemiş.
        </p>
      ) : (
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="mt-3 h-auto w-full"
          role="img"
          aria-label={points
            .map(
              (point) =>
                `${point.season.season}: ${percentileLabel(point.value)}. persentil`,
            )
            .join(", ")}
        >
          {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
            <g key={tick}>
              <line
                x1={PAD.left}
                y1={y(tick)}
                x2={WIDTH - PAD.right}
                y2={y(tick)}
                stroke="var(--color-stroke-panel)"
                strokeWidth={tick === 0.5 ? 1 : 0.5}
                strokeDasharray={tick === 0.5 ? "3 3" : undefined}
              />
              <text
                x={PAD.left - 7}
                y={y(tick)}
                textAnchor="end"
                dominantBaseline="middle"
                fontSize={9}
                fill="var(--color-text-muted)"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                {tick * 100}
              </text>
            </g>
          ))}

          {points.length > 1 && (
            <polyline
              points={line}
              fill="none"
              stroke={colour}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )}

          {points.map((point) => (
            <g key={point.season.season}>
              <circle
                cx={x(point.index, seasons.length)}
                cy={y(point.value)}
                r={4}
                fill={colour}
              />
              <text
                x={x(point.index, seasons.length)}
                y={y(point.value) - 11}
                textAnchor="middle"
                fontSize={10}
                fill={colour}
                style={{ fontFamily: "var(--font-mono)" }}
              >
                {percentileLabel(point.value)}
              </text>
            </g>
          ))}

          {seasons.map((season, index) => (
            <g key={season.season}>
              <text
                x={x(index, seasons.length)}
                y={HEIGHT - PAD.bottom + 17}
                textAnchor="middle"
                fontSize={10}
                fill="var(--color-text-muted)"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                {formatSeason(season.season)}
              </text>
              <text
                x={x(index, seasons.length)}
                y={HEIGHT - PAD.bottom + 30}
                textAnchor="middle"
                fontSize={9}
                fill="var(--color-text-muted)"
                style={{ fontFamily: "var(--font-mono)", opacity: 0.7 }}
              >
                n={season.population} · {season.minutes} dk
              </text>
            </g>
          ))}
        </svg>
      )}

      <div className="mt-3 flex flex-col gap-1 border-t border-stroke-panel pt-3">
        {seasons.map((season) => (
          <p key={season.season} className="stat text-[11px] text-text-muted">
            {formatSeason(season.season)} · {season.clubName ?? "kulüpsüz"}
            {season.leagueName ? ` · ${season.leagueName}` : ""}
            {season.leagueTier != null && season.leagueTier > 1 ? " (2. lig)" : ""} ·{" "}
            {season.positionGroup}
          </p>
        ))}
        {data.note && (
          <p className="stat mt-1 text-[11px]" style={{ color: "var(--color-scout-amber)" }}>
            {data.note}
          </p>
        )}
      </div>
    </section>
  );
}
