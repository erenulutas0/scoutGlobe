import type { Metadata } from "next";
import Link from "next/link";
import { DiscoverForm } from "@/features/discover/DiscoverForm";
import { DataFreshness } from "@/features/shell/DataFreshness";
import { api } from "@/lib/api";

export const revalidate = 300;

export const metadata: Metadata = {
  title: "Keşfet — ScoutGlobe",
  description: "Pozisyon, bütçe, yaş ve lige göre oyuncu keşfi; her sonuç gerekçesiyle birlikte.",
};

/**
 * The discovery page.
 *
 * The first list is rendered on the server so the page arrives with players on
 * it rather than an empty form: a scout who opens this should see the season's
 * standout forwards before touching a control.
 */
export default async function DiscoverPage() {
  const [options, leagues] = await Promise.all([api.discoveryOptions(), api.leagues()]);

  const season = options.seasons[0] ?? "";
  const initialResult = await api.discover({ position_group: "FW", season, limit: 24 });

  return (
    <main className="starfield min-h-dvh px-4 py-8 md:px-8">
      <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <Link href="/" className="text-xs text-text-muted hover:text-text-primary">
              ← Globe
            </Link>
            <h1 className="mt-2 font-[family-name:var(--font-display)] text-3xl tracking-[-0.02em]">
              Keşfet
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-text-muted">
              Her oyuncu, kendi pozisyon grubu ve sezonu içinde sıralanır. Yanındaki rakam
              persentil — aynı işi yapan kaç oyuncunun önünde olduğu; <span className="stat">n</span>{" "}
              ise kaç oyuncuyla karşılaştırıldığı. Sıralama tuttuğumuz{" "}
              <em>bütün</em> ligleri aynı havuza koyar ve lig gücüne göre düzeltmez, bu yüzden{" "}
              <span style={{ color: "var(--color-scout-amber)" }}>2. lig</span> işaretli bir
              oyuncunun persentili olduğundan iyi görünür.
            </p>
          </div>
          <DataFreshness />
        </header>

        <DiscoverForm options={options} leagues={leagues} initialResult={initialResult} />
      </div>
    </main>
  );
}
