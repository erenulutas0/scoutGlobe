import type { Metadata } from "next";
import Link from "next/link";
import { RisingView } from "@/features/discover/RisingView";
import { SearchButton } from "@/features/shell/CommandPalette";
import { DataFreshness } from "@/features/shell/DataFreshness";
import { api } from "@/lib/api";

export const revalidate = 300;

export const metadata: Metadata = {
  title: "Yükselenler — ScoutGlobe",
  description: "Genç, çoktan üretiyor ve henüz pahalı değil; skorun her parçası görünür.",
};

export default async function RisingPage() {
  const [leagues, initialResult] = await Promise.all([
    api.leagues(),
    api.rising({ limit: 24 }),
  ]);

  return (
    <main className="starfield min-h-dvh px-4 py-8 md:px-8">
      <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <Link href="/" className="text-xs text-text-muted hover:text-text-primary">
              ← Globe
            </Link>
            <h1 className="mt-2 font-[family-name:var(--font-display)] text-3xl tracking-[-0.02em]">
              Yükselenler
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-text-muted">
              &quot;Şu an kim iyi&quot; değil, &quot;kim iyi oluyor&quot;. Skor bir görüş, parçaları
              ise olgu — her kart profilini, oynadığı ligin ağırlığını ve yaşını ayrı ayrı
              gösterir ki ağırlıklandırmaya katılmayan da kendi kararını verebilsin.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <SearchButton />
            <DataFreshness />
          </div>
        </header>

        <RisingView leagues={leagues} initialResult={initialResult} />
      </div>
    </main>
  );
}
