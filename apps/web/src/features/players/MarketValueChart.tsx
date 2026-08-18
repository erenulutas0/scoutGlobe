import type { MarketValuePoint } from "@scoutglobe/core";
import { formatMarketValue } from "@scoutglobe/core";

const WIDTH = 520;
const HEIGHT = 180;
const PADDING = { top: 12, right: 8, bottom: 22, left: 8 };

/**
 * Market value over time, drawn as plain SVG — no client-side charting library
 * and no JavaScript at all, so the profile page stays a server component.
 *
 * The colour carries meaning (DESIGN.md §2): rising value is --grass, a decline
 * is --alert-coral. It is never decoration.
 */
export function MarketValueChart({ points }: { points: MarketValuePoint[] }) {
  if (points.length < 2) {
    return (
      <p className="stat py-6 text-center text-xs text-text-muted uppercase">
        Değer geçmişi için yeterli veri yok
      </p>
    );
  }

  const values = points.map((point) => point.valueEur);
  const times = points.map((point) => new Date(point.date).getTime());
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const minTime = Math.min(...times);
  const maxTime = Math.max(...times);

  const innerWidth = WIDTH - PADDING.left - PADDING.right;
  const innerHeight = HEIGHT - PADDING.top - PADDING.bottom;
  const spanValue = maxValue - minValue || 1;
  const spanTime = maxTime - minTime || 1;

  const x = (time: number) => PADDING.left + ((time - minTime) / spanTime) * innerWidth;
  const y = (value: number) =>
    PADDING.top + innerHeight - ((value - minValue) / spanValue) * innerHeight;

  const coordinates = points.map((point, index) => ({
    x: x(times[index] ?? minTime),
    y: y(point.valueEur),
  }));

  const line = coordinates
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(1)},${point.y.toFixed(1)}`)
    .join(" ");
  const area = `${line} L${(coordinates.at(-1)?.x ?? 0).toFixed(1)},${PADDING.top + innerHeight} L${(coordinates[0]?.x ?? 0).toFixed(1)},${PADDING.top + innerHeight} Z`;

  const first = values[0] ?? 0;
  const last = values.at(-1) ?? 0;
  const rising = last >= first;
  const stroke = rising ? "var(--color-grass)" : "var(--color-alert-coral)";
  const gradientId = rising ? "value-up" : "value-down";

  const firstYear = new Date(points[0]?.date ?? "").getFullYear();
  const lastYear = new Date(points.at(-1)?.date ?? "").getFullYear();

  return (
    <figure className="mt-1">
      <figcaption className="flex items-baseline justify-between">
        <span className="text-xs text-text-muted">Piyasa değeri geçmişi</span>
        <span className="stat text-xs" style={{ color: stroke }}>
          {rising ? "↑" : "↓"} {formatMarketValue(first)} → {formatMarketValue(last)}
        </span>
      </figcaption>

      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="mt-2 w-full"
        role="img"
        aria-label={`Piyasa değeri ${firstYear} yılında ${formatMarketValue(first)}, ${lastYear} yılında ${formatMarketValue(last)}`}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity="0.28" />
            <stop offset="100%" stopColor={stroke} stopOpacity="0" />
          </linearGradient>
        </defs>

        <path d={area} fill={`url(#${gradientId})`} />
        <path d={line} fill="none" stroke={stroke} strokeWidth="2" strokeLinejoin="round" />

        {coordinates.map((point, index) => (
          <circle
            key={points[index]?.date ?? index}
            cx={point.x}
            cy={point.y}
            r={index === coordinates.length - 1 ? 3.5 : 2}
            fill={index === coordinates.length - 1 ? stroke : "var(--color-panel-solid)"}
            stroke={stroke}
            strokeWidth="1.5"
          />
        ))}

        <text
          x={PADDING.left}
          y={HEIGHT - 6}
          className="stat"
          fontSize="11"
          fill="var(--color-text-muted)"
        >
          {firstYear}
        </text>
        <text
          x={WIDTH - PADDING.right}
          y={HEIGHT - 6}
          textAnchor="end"
          className="stat"
          fontSize="11"
          fill="var(--color-text-muted)"
        >
          {lastYear}
        </text>
      </svg>
    </figure>
  );
}
