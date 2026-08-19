"use client";

import { useQuery } from "@tanstack/react-query";
import type { Shot } from "@scoutglobe/core";
import { api } from "@/lib/api";

// The attacking third, drawn to real proportions (105x68m pitch). Cropping at
// 40m rather than the halfway line keeps the shots filling the frame: almost
// nothing is struck from further out, and the empty grass would only shrink
// the part a scout actually reads.
const PITCH_LENGTH = 105;
const PITCH_WIDTH = 68;
const VIEW_DEPTH = 40;
const SCALE = 8;
const WIDTH = PITCH_WIDTH * SCALE;
const HEIGHT = VIEW_DEPTH * SCALE;

/** Understat x/y (0-1, attacking right) -> SVG point on a vertical half pitch. */
function toPoint(shot: Shot): { x: number; y: number } | null {
  if (shot.locationX === null || shot.locationX === undefined) return null;
  if (shot.locationY === null || shot.locationY === undefined) return null;

  const metresFromGoal = (1 - shot.locationX) * PITCH_LENGTH;
  // Long-range efforts are pinned to the edge instead of dropped: a shot from
  // 45m is rare but real, and silently losing it would misstate the totals.
  const clamped = Math.min(metresFromGoal, VIEW_DEPTH - 1);
  if (metresFromGoal < 0) return null;

  return {
    x: shot.locationY * WIDTH,
    y: clamped * SCALE,
  };
}

function Pitch() {
  const line = "rgba(148,163,199,0.28)";
  const box = { depth: 16.5 * SCALE, width: 40.3 * SCALE };
  const six = { depth: 5.5 * SCALE, width: 18.3 * SCALE };

  return (
    <g fill="none" stroke={line} strokeWidth="1.5">
      <rect x="0.75" y="0.75" width={WIDTH - 1.5} height={HEIGHT - 1.5} rx="2" />
      <rect
        x={(WIDTH - box.width) / 2}
        y={0.75}
        width={box.width}
        height={box.depth}
      />
      <rect
        x={(WIDTH - six.width) / 2}
        y={0.75}
        width={six.width}
        height={six.depth}
      />
      <circle cx={WIDTH / 2} cy={11 * SCALE} r="1.8" fill={line} stroke="none" />
      <path
        d={`M ${(WIDTH - 18.3 * SCALE) / 2 - 20} ${box.depth} A 60 60 0 0 0 ${(WIDTH + 18.3 * SCALE) / 2 + 20} ${box.depth}`}
      />
    </g>
  );
}

/**
 * Shots on half a pitch: radius follows xG, colour separates goals from the
 * rest. This is as close to positional data as free sources reach — a real
 * touch heat map would need every touch, which none of them publish.
 */
export function ShotMap({ playerId }: { playerId: number }) {
  const { data, isPending, isError } = useQuery({
    queryKey: ["player-shots", playerId],
    queryFn: ({ signal }) => api.playerShots(playerId, { limit: 400 }, signal),
    staleTime: 5 * 60_000,
  });

  if (isPending) {
    return (
      <section className="glass-panel rounded-card p-5">
        <p className="stat py-8 text-center text-xs text-text-muted uppercase">Şut haritası yükleniyor</p>
      </section>
    );
  }

  if (isError || !data || data.totalShots === 0) {
    return (
      <section className="glass-panel rounded-card p-5">
        <h2 className="font-[family-name:var(--font-display)] text-xl tracking-[-0.02em]">
          Şut haritası
        </h2>
        <p className="mt-2 text-sm text-text-muted">
          Bu oyuncu için şut verisi yok. Konumlu şut verisi Understat kapsamındaki beş ligle
          sınırlı.
        </p>
      </section>
    );
  }

  const drawn = data.shots.map((shot) => ({ shot, point: toPoint(shot) }));
  const overperforming = data.xgDifference >= 0;

  return (
    <section className="glass-panel rounded-card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="font-[family-name:var(--font-display)] text-xl tracking-[-0.02em]">
            Şut haritası
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Daire büyüklüğü xG, yeşil olanlar gol.
          </p>
        </div>
        <p className="stat text-xs text-text-muted">
          {data.totalShots} şut · {data.totalGoals} gol · xG {data.totalXg.toFixed(1)} ·{" "}
          <span style={{ color: overperforming ? "var(--color-grass)" : "var(--color-alert-coral)" }}>
            {overperforming ? "+" : ""}
            {data.xgDifference.toFixed(1)}
          </span>
        </p>
      </div>

      <div className="mt-4 flex flex-col gap-4 md:flex-row md:items-start">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="w-full max-w-[320px] shrink-0"
          role="img"
          aria-label={`${data.totalShots} şutun konum haritası, ${data.totalGoals} gol`}
        >
          <rect width={WIDTH} height={HEIGHT} fill="rgba(11,20,40,0.55)" rx="3" />
          <Pitch />
          {drawn.map(({ shot, point }) =>
            point === null ? null : (
              <circle
                key={shot.id}
                cx={point.x}
                cy={point.y}
                r={3 + Math.sqrt(shot.xg ?? 0) * 9}
                fill={shot.isGoal ? "rgba(53,217,139,0.55)" : "rgba(148,163,199,0.20)"}
                stroke={shot.isGoal ? "var(--color-grass)" : "rgba(148,163,199,0.45)"}
                strokeWidth="1"
              />
            ),
          )}
        </svg>

        <div className="min-w-0 flex-1 overflow-x-auto">
          <table className="w-full min-w-[320px] border-collapse text-sm">
            <thead>
              <tr className="text-xs text-text-muted">
                <th className="px-2 py-1 text-left font-normal">Bölge</th>
                <th className="px-2 py-1 text-right font-normal">Şut</th>
                <th className="px-2 py-1 text-right font-normal">Gol</th>
                <th className="px-2 py-1 text-right font-normal">xG</th>
                <th className="px-2 py-1 text-right font-normal">Şut başı xG</th>
              </tr>
            </thead>
            <tbody>
              {data.zones.map((zone) => (
                <tr key={zone.zone} className="border-t border-stroke-panel/60">
                  <td className="px-2 py-1.5">{zone.zoneLabel}</td>
                  <td className="stat px-2 py-1.5 text-right">{zone.shots}</td>
                  <td className="stat px-2 py-1.5 text-right">{zone.goals}</td>
                  <td className="stat px-2 py-1.5 text-right">{zone.xg.toFixed(1)}</td>
                  <td className="stat px-2 py-1.5 text-right">{zone.xgPerShot.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-text-muted">
            xG farkı, golden beklenen gol çıkarılarak bulunur: artı değer, yakaladığı fırsatların
            üzerinde bitirdiğini gösterir.
          </p>
        </div>
      </div>
    </section>
  );
}
