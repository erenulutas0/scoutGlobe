import type { MetricNote, PlayerRadar } from "@scoutglobe/core";
import { ApiError } from "@scoutglobe/core";
import { percentileLabel } from "@/features/discover/PercentileBar";
import { api } from "@/lib/api";

const POSITION_COLOR: Record<string, string> = {
  GK: "var(--color-pos-gk)",
  DF: "var(--color-pos-df)",
  MF: "var(--color-pos-mf)",
  FW: "var(--color-pos-fw)",
};

// Wider than tall: the labels sit outside the outer ring and the longest of
// them ("xG (beklenen gol)") needs room on both sides or it is clipped.
const WIDTH = 380;
const HEIGHT = 290;
const CENTRE_X = WIDTH / 2;
const CENTRE_Y = HEIGHT / 2;
const RADIUS = 92;
// The grid a reader counts against: median, then the two bands that matter.
const RINGS = [0.25, 0.5, 0.75, 1];

type Point = { x: number; y: number };

function pointAt(index: number, count: number, fraction: number): Point {
  // Start at twelve o'clock and go clockwise, which is how these are read.
  const angle = (index / count) * Math.PI * 2 - Math.PI / 2;
  return {
    x: CENTRE_X + Math.cos(angle) * RADIUS * fraction,
    y: CENTRE_Y + Math.sin(angle) * RADIUS * fraction,
  };
}

function polygon(points: Point[]): string {
  return points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
}

/**
 * A percentile profile drawn on the axes the player's position is judged on.
 *
 * Two honesty constraints shape it. An axis with no ranking is absent rather
 * than drawn at the centre, because a spoke at zero reads as "worst in the
 * league" and not as "we did not measure this" — and expected-goals metrics
 * cover a fraction of our leagues. And the sample each axis was ranked against
 * is printed beside it, because a rank among 1,800 forwards and one among 40
 * look identical on a chart.
 */
function Axis({
  note,
  index,
  count,
  colour,
}: {
  note: MetricNote;
  index: number;
  count: number;
  colour: string;
}) {
  const spoke = pointAt(index, count, 1);
  const label = pointAt(index, count, 1.18);
  // A label to the right of centre grows rightward, one to the left grows
  // leftward; only the top and bottom spokes are centred. Getting this wrong
  // is what clipped "xG (beklenen gol)" at the edge of the box.
  const anchor = label.x > CENTRE_X + 4 ? "start" : label.x < CENTRE_X - 4 ? "end" : "middle";

  return (
    <g>
      <line
        x1={CENTRE_X}
        y1={CENTRE_Y}
        x2={spoke.x}
        y2={spoke.y}
        stroke="var(--color-stroke-panel)"
        strokeWidth={1}
      />
      <text
        x={label.x}
        y={label.y}
        textAnchor={anchor}
        dominantBaseline="middle"
        fontSize={9}
        fill="var(--color-text-muted)"
      >
        {note.label}
      </text>
      <text
        x={label.x}
        y={label.y + 10}
        textAnchor={anchor}
        dominantBaseline="middle"
        fontSize={10}
        fill={colour}
        style={{ fontFamily: "var(--font-mono)" }}
      >
        {percentileLabel(note.percentile)}
      </text>
    </g>
  );
}

function Chart({ axes, colour }: { axes: MetricNote[]; colour: string }) {
  const count = axes.length;
  const shape = axes.map((note, index) => pointAt(index, count, note.percentile));

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="h-auto w-full max-w-[380px] shrink-0"
      role="img"
      aria-label={axes
        .map((note) => `${note.label}: ${percentileLabel(note.percentile)}. persentil`)
        .join(", ")}
    >
      {RINGS.map((ring) => (
        <polygon
          key={ring}
          points={polygon(axes.map((_, index) => pointAt(index, count, ring)))}
          fill="none"
          stroke="var(--color-stroke-panel)"
          strokeWidth={ring === 0.5 ? 1.2 : 0.6}
          strokeDasharray={ring === 0.5 ? "3 3" : undefined}
        />
      ))}

      {axes.map((note, index) => (
        <Axis key={note.metric} note={note} index={index} count={count} colour={colour} />
      ))}

      <polygon
        points={polygon(shape)}
        fill={colour}
        fillOpacity={0.18}
        stroke={colour}
        strokeWidth={1.6}
        strokeLinejoin="round"
      />
      {shape.map((point, index) => (
        <circle key={axes[index]?.metric} cx={point.x} cy={point.y} r={2.5} fill={colour} />
      ))}
    </svg>
  );
}

export async function PercentileRadar({ playerId }: { playerId: number }) {
  let data: PlayerRadar;
  try {
    data = await api.playerRadar(playerId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return (
        <section className="glass-panel rounded-card p-5">
          <h2 className="font-[family-name:var(--font-display)] text-xl tracking-[-0.02em]">
            Persentil profili
          </h2>
          <p className="mt-2 text-sm text-text-muted">
            {error.problem?.detail ?? "Bu oyuncunun persentil profili yok."}
          </p>
        </section>
      );
    }
    throw error;
  }

  const colour = POSITION_COLOR[data.positionGroup] ?? "var(--color-arc-out)";
  const sample = data.axes[0]?.sampleSize;

  return (
    <section className="glass-panel rounded-card p-5">
      <h2 className="font-[family-name:var(--font-display)] text-xl tracking-[-0.02em]">
        Persentil profili
      </h2>
      <p className="mt-1 text-sm text-text-muted">
        {data.season} · {data.leagueName ?? "lig bilinmiyor"}
        {data.leagueTier != null && data.leagueTier > 1 && (
          <span style={{ color: "var(--color-scout-amber)" }}> · 2. lig</span>
        )}{" "}
        · {data.minutes} dk. Dış halka 100. persentil, kesikli halka medyan.
      </p>

      {data.axes.length > 0 ? (
        <div className="mt-4 flex flex-wrap items-center gap-6">
          <Chart axes={data.axes} colour={colour} />
          <dl className="stat min-w-[12rem] flex-1 text-xs">
            {data.axes.map((note) => (
              <div
                key={note.metric}
                className="flex items-baseline justify-between gap-3 border-b border-stroke-panel/60 py-1"
              >
                <dt className="truncate text-text-muted">{note.label}</dt>
                <dd className="shrink-0">
                  {note.per90 === null || note.per90 === undefined
                    ? "—"
                    : note.per90.toFixed(2)}
                  <span className="ml-2" style={{ color: colour }}>
                    {percentileLabel(note.percentile)}
                  </span>
                </dd>
              </div>
            ))}
          </dl>
        </div>
      ) : (
        <p className="mt-3 text-sm text-text-muted">
          {data.note ?? "Çizilecek ölçülmüş eksen yok."}
        </p>
      )}

      <p className="stat mt-4 border-t border-stroke-panel pt-3 text-[11px] text-text-muted">
        {sample ? `Aynı pozisyon ve sezondaki ${sample} oyuncuya göre. ` : ""}
        Ölçülmemiş bir eksen çizilmez — merkezde göstermek &quot;ligin en kötüsü&quot; diye
        okunurdu.
        {data.axes.length > 0 && data.note && (
          <span style={{ color: "var(--color-scout-amber)" }}> {data.note}</span>
        )}
      </p>
    </section>
  );
}
