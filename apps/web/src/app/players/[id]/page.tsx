import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ApiError, formatMarketValue } from "@scoutglobe/core";
import type { PlayerDetail } from "@scoutglobe/core";
import { FormChart } from "@/features/players/FormChart";
import { MarketValueChart } from "@/features/players/MarketValueChart";
import { ShotMap } from "@/features/players/ShotMap";
import { RemoteImage } from "@/features/shared/RemoteImage";
import { SeasonStatsTable } from "@/features/players/SeasonStatsTable";
import { api } from "@/lib/api";

// The API is the source of truth and changes only when an ETL runs.
export const revalidate = 300;

async function loadPlayer(id: string): Promise<PlayerDetail> {
  const playerId = Number.parseInt(id, 10);
  if (!Number.isFinite(playerId)) notFound();

  try {
    return await api.player(playerId);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const player = await api.player(Number.parseInt(id, 10));
    return {
      title: `${player.fullName} — ScoutGlobe`,
      description: [player.clubName, player.leagueName, player.position]
        .filter(Boolean)
        .join(" · "),
    };
  } catch {
    return { title: "Oyuncu — ScoutGlobe" };
  }
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd className="stat mt-0.5 text-base">{value}</dd>
    </div>
  );
}

export default async function PlayerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const player = await loadPlayer(id);

  const contract = player.contractUntil
    ? new Date(player.contractUntil).toLocaleDateString("tr-TR", {
        year: "numeric",
        month: "short",
      })
    : "—";

  return (
    <main className="starfield min-h-dvh w-full">
      <header className="glass-panel sticky top-0 z-10 flex items-center justify-between px-4 py-3 md:px-6">
        <Link href="/" className="flex items-baseline gap-2">
          <span aria-hidden className="text-grass">
            ◉
          </span>
          <span className="font-[family-name:var(--font-display)] text-lg tracking-[-0.02em]">
            ScoutGlobe
          </span>
        </Link>
        <Link href="/" className="text-sm text-text-muted transition-colors hover:text-text-primary">
          ← Dünyaya dön
        </Link>
      </header>

      <div className="mx-auto grid max-w-6xl gap-4 px-4 py-6 md:grid-cols-[minmax(280px,360px)_1fr] md:px-6">
        <div className="flex flex-col gap-4">
          <section className="glass-panel rounded-card p-5">
            <div className="flex items-start gap-4">
              <RemoteImage
                src={player.imageUrl}
                alt={player.fullName}
                size={64}
                rounded="card"
              />
              <div className="min-w-0">
                <p className="stat text-xs tracking-[0.16em] text-text-muted uppercase">
                  {player.position ?? "Oyuncu"}
                  {player.subPosition ? ` · ${player.subPosition}` : ""}
                </p>
                <h1 className="mt-1 font-[family-name:var(--font-display)] text-2xl leading-tight tracking-[-0.02em] text-balance xl:text-3xl">
                  {player.fullName}
                </h1>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-text-muted">
              {player.clubName && (
                <span className="flex items-center gap-2">
                  <RemoteImage
                    src={player.clubLogoUrl}
                    alt={player.clubName}
                    size={22}
                    rounded="card"
                  />
                  {player.clubName}
                </span>
              )}
              {player.leagueName && (
                <span className="flex items-center gap-2">
                  <RemoteImage
                    src={player.leagueLogoUrl}
                    alt={player.leagueName}
                    size={22}
                    rounded="card"
                  />
                  {player.leagueName}
                </span>
              )}
              {!player.clubName && !player.leagueName && <span>Kulüpsüz</span>}
            </div>

            <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-4 border-t border-stroke-panel pt-4">
              <Fact label="Yaş" value={player.age ?? "—"} />
              <Fact label="Uyruk" value={player.nationalityCode ?? "—"} />
              <Fact label="Ayak" value={player.foot ?? "—"} />
              <Fact label="Boy" value={player.heightCm ? `${player.heightCm} cm` : "—"} />
              <Fact label="Sözleşme" value={contract} />
              <Fact label="Değer" value={formatMarketValue(player.marketValueEur)} />
            </dl>
          </section>

          <section className="glass-panel rounded-card p-5">
            <MarketValueChart points={player.marketValueHistory} />
          </section>
        </div>

        <div className="flex min-w-0 flex-col gap-4">
          <FormChart playerId={player.id} />

          <ShotMap playerId={player.id} />

          <section className="glass-panel rounded-card p-5">
            <h2 className="font-[family-name:var(--font-display)] text-xl tracking-[-0.02em]">
              Sezon istatistikleri
            </h2>
            <p className="mt-1 mb-4 text-sm text-text-muted">
              Her kaynak kendi satırında; rakamlar birleştirilmez.
            </p>
            <SeasonStatsTable stats={player.seasonStats} />
          </section>
        </div>
      </div>
    </main>
  );
}
