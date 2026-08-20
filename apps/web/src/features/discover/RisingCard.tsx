import Link from "next/link";
import type { RisingPlayer } from "@scoutglobe/core";
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
 * One part of the score, drawn as the share of the bar it fills.
 *
 * The parts are shown because the total is an opinion and the parts are facts.
 * A scout who disagrees with the weighting can still read "85th percentile, in
 * a league worth 0.81, at eighteen" and make his own call.
 */
function Component({ label, value, hint }: { label: string; value: number; hint: string }) {
  return (
    <div className="flex items-center gap-2" title={hint}>
      <span className="w-[5.5rem] shrink-0 truncate text-[11px] text-text-muted">{label}</span>
      <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/8">
        <div
          className="h-full rounded-full"
          style={{
            width: `${Math.min(100, Math.max(0, value * 100))}%`,
            backgroundColor: "var(--color-arc-out)",
          }}
        />
      </div>
      <span className="stat w-9 shrink-0 text-right text-[11px] text-text-muted">
        {value.toFixed(2)}
      </span>
    </div>
  );
}

function Momentum({ player }: { player: RisingPlayer }) {
  const momentum = player.momentum;
  if (!momentum) {
    return (
      <p className="text-[11px] text-text-muted">
        Piyasa değeri geçmişi yok — bu satırda momentum ölçülemedi.
      </p>
    );
  }

  const rose = momentum.changeRatio > 1;
  return (
    <p className="stat flex flex-wrap items-baseline gap-x-2 text-[11px] text-text-muted">
      <span>{formatMarketValue(momentum.fromEur)}</span>
      <span aria-hidden>→</span>
      <span className="text-text-primary">{formatMarketValue(momentum.toEur)}</span>
      <span style={{ color: rose ? "var(--color-grass)" : "var(--color-alert-coral)" }}>
        ×{momentum.changeRatio}
      </span>
      <span className="opacity-70">son 1 yıl</span>
    </p>
  );
}

export function RisingCard({ player, rank }: { player: RisingPlayer; rank: number }) {
  const { rising } = player;
  const positionColor = POSITION_COLOR[player.positionGroup] ?? "var(--color-text-muted)";

  return (
    <article className="glass-panel rounded-card p-4 transition-colors hover:bg-white/4">
      <div className="flex items-start gap-3">
        <span className="stat w-6 shrink-0 pt-1 text-sm text-text-muted">{rank}</span>
        <RemoteImage
          src={player.player.imageUrl}
          alt={player.player.fullName}
          size={48}
          className="shrink-0"
        />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <Link
              href={`/players/${player.player.id}`}
              className="truncate text-base hover:text-arc-out hover:underline"
            >
              {player.player.fullName}
            </Link>
            <span className="stat text-xs" style={{ color: positionColor }}>
              {player.positionGroup}
            </span>
            <span className="stat text-xs" style={{ color: "var(--color-scout-amber)" }}>
              {rising.age} yaş
            </span>
            <ShortlistToggle
              playerId={player.player.id}
              name={player.player.fullName}
              className="ml-auto"
            />
          </div>

          <p className="mt-0.5 truncate text-xs text-text-muted">
            {player.clubName || "Kulüpsüz"}
          </p>

          <div className="stat mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
            <span>{formatMarketValue(player.player.marketValueEur)}</span>
            <span className="flex items-center gap-1.5">
              {formatSeason(player.season)}
              {player.leagueName && <span>· {player.leagueName}</span>}
              {player.leagueTier != null && player.leagueTier > 1 && (
                <span
                  className="shrink-0 rounded px-1 text-[10px]"
                  style={{
                    color: "var(--color-scout-amber)",
                    border:
                      "1px solid color-mix(in srgb, var(--color-scout-amber) 40%, transparent)",
                  }}
                >
                  2. lig
                </span>
              )}
              <span>· {player.minutes} dk</span>
            </span>
          </div>
        </div>

        <span
          className="stat shrink-0 text-right text-lg"
          style={{ color: "var(--color-arc-out)" }}
          title="Profil × lig ağırlığı × 0.7 + gençlik × 0.3"
        >
          {rising.score.toFixed(2)}
        </span>
      </div>

      <div className="mt-3 flex flex-col gap-1.5 border-t border-stroke-panel pt-3">
        <p className="mb-0.5 text-[11px] tracking-wide text-text-muted uppercase">Skor neyden</p>
        <Component
          label="Profil"
          value={rising.profile}
          hint={`Pozisyonunun ${rising.axesMeasured} ekseninde ortalama persentil`}
        />
        <Component
          label="Lig ağırlığı"
          value={rising.leagueWeight}
          hint="Zayıf lig indirim yapar ama sıfırlamaz — kimsenin izlemediği oyuncuyu bulmak amaç"
        />
        <Component label="Gençlik" value={rising.youth} hint="16 yaşında 1.0, yaş tavanında 0" />
      </div>

      {player.strengths.length > 0 && (
        <div className="mt-3 flex flex-col gap-1.5 border-t border-stroke-panel pt-3">
          <p className="text-[11px] tracking-wide text-text-muted uppercase">En güçlü yönü</p>
          {player.strengths.slice(0, 2).map((note) => (
            <PercentileBar key={note.metric} note={note} tone="strength" />
          ))}
        </div>
      )}

      <div className="mt-3 border-t border-stroke-panel pt-3">
        <Momentum player={player} />
      </div>
    </article>
  );
}
