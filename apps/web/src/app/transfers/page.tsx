import type { Metadata } from "next";
import Link from "next/link";
import { TransferBoardView } from "@/features/transfers/TransferBoardView";
import { DataFreshness } from "@/features/shell/DataFreshness";
import { api } from "@/lib/api";

// Transfers change daily during a window, so this page is fresher than the
// rest of the site.
export const revalidate = 60;

export const metadata: Metadata = {
  title: "Transfer tahtası — ScoutGlobe",
  description: "Açık transfer döneminde kim nereye gitti; tarihi ve kaynağıyla birlikte.",
};

/** Windows a scout thinks in, not the season labels the sources disagree on. */
const CURRENT_WINDOW = { label: "2026 yaz dönemi", since: "2026-06-01" };

const WINDOWS: { label: string; since: string; until?: string }[] = [
  CURRENT_WINDOW,
  { label: "2026 kış dönemi", since: "2026-01-01", until: "2026-02-15" },
  { label: "2025 yaz dönemi", since: "2025-06-01", until: "2025-09-15" },
];

export default async function TransfersPage() {
  const [leagues, initialBoard] = await Promise.all([
    api.leagues(),
    api.transfers({ since: CURRENT_WINDOW.since, limit: 100 }),
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
              Transfer tahtası
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-text-muted">
              İki kaynak birleştirilir: Transfermarkt bonservisi verir ama tarihi dönem başına
              yuvarlar, API-Football günü gününe doğrular ve kiralık mı bonservisle mi olduğunu
              söyler. Her satır hangisinden geldiğini yazar.
            </p>
          </div>
          <DataFreshness />
        </header>

        <TransferBoardView
          leagues={leagues}
          windows={WINDOWS}
          initialBoard={initialBoard}
          initialWindow={CURRENT_WINDOW.label}
        />
      </div>
    </main>
  );
}
