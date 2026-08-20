import Link from "next/link";
import { ApiStatus } from "./ApiStatus";
import { SearchButton } from "./CommandPalette";
import { DataFreshness } from "./DataFreshness";

/** Thin glass top bar (DESIGN.md §4): search, the views, and data freshness. */
export function TopBar() {
  return (
    <header className="glass-panel absolute inset-x-0 top-0 z-10 flex items-center justify-between px-4 py-3 md:px-6">
      <div className="flex items-baseline gap-2">
        <span aria-hidden className="text-grass">
          ◉
        </span>
        <span className="font-[family-name:var(--font-display)] text-lg tracking-[-0.02em]">
          ScoutGlobe
        </span>
      </div>
      <div className="flex items-center gap-4">
        <SearchButton />
        <DataFreshness />
        <Link
          href="/rising"
          className="text-sm text-text-muted transition-colors hover:text-text-primary"
        >
          Yükselenler
        </Link>
        <Link
          href="/transfers"
          className="text-sm text-text-muted transition-colors hover:text-text-primary"
        >
          Transferler
        </Link>
        <Link
          href="/discover"
          className="rounded-md border border-stroke-panel px-3 py-1.5 text-sm transition-colors hover:border-arc-out hover:text-arc-out"
        >
          Keşfet
        </Link>
        <ApiStatus />
      </div>
    </header>
  );
}
