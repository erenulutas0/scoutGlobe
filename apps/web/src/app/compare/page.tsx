import type { Metadata } from "next";
import Link from "next/link";
import { ApiError } from "@scoutglobe/core";
import type { Comparison } from "@scoutglobe/core";
import { ComparisonView } from "@/features/discover/ComparisonView";
import { SearchButton } from "@/features/shell/CommandPalette";
import { DataFreshness } from "@/features/shell/DataFreshness";
import { api } from "@/lib/api";

export const revalidate = 300;

export const metadata: Metadata = {
  title: "Karşılaştır — ScoutGlobe",
  description: "İki ile dört oyuncuyu ortak eksenlerde yan yana koy.",
};

/** The comparison is in the URL so a scout can send it to someone else. */
function parseIds(value: string | string[] | undefined): number[] {
  const raw = Array.isArray(value) ? value.join(",") : (value ?? "");
  return raw
    .split(",")
    .map((part) => Number.parseInt(part.trim(), 10))
    .filter((id) => Number.isFinite(id) && id > 0)
    .slice(0, 4);
}

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ p?: string | string[] }>;
}) {
  const { p } = await searchParams;
  const ids = parseIds(p);

  // Fetch first, render after. Building JSX inside the try would look like it
  // caught rendering errors, and it would not: React renders the element later.
  let data: Comparison | null = null;
  let failure: string | null = null;

  if (ids.length < 2) {
    failure =
      'Karşılaştırma en az iki oyuncu ister. Keşfet, Yükselenler veya bir oyuncu ' +
      'sayfasından "+ listeye" ile ekle, sonra alttaki çubuktan karşılaştır.';
  } else {
    try {
      data = await api.compare(ids);
    } catch (error) {
      failure =
        error instanceof ApiError
          ? (error.problem?.detail ?? error.message)
          : "Karşılaştırma yüklenemedi.";
    }
  }

  if (data && data.players.length < 2) {
    failure = data.note ?? "Seçilen oyuncuların karşılaştırılabilir bir sezonu yok.";
    data = null;
  }

  return (
    <main className="starfield min-h-dvh px-4 py-8 pb-24 md:px-8">
      <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <Link href="/" className="text-xs text-text-muted hover:text-text-primary">
              ← Globe
            </Link>
            <h1 className="mt-2 font-[family-name:var(--font-display)] text-3xl tracking-[-0.02em]">
              Karşılaştır
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-text-muted">
              Oyuncular üst üste bindirilir, çünkü iki profil ancak böyle bir bakışta okunur.
              Bu da her telin herkes için aynı şeyi göstermesini gerektirir: birinde ölçülmemiş
              bir eksen grafiğe girmez, altta adıyla yazılır.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <SearchButton />
            <DataFreshness />
          </div>
        </header>

        {data ? (
          <ComparisonView data={data} />
        ) : (
          <p className="glass-panel rounded-card p-5 text-sm text-text-muted">{failure}</p>
        )}
      </div>
    </main>
  );
}
