import Link from "next/link";
import { ApiStatus } from "./ApiStatus";
import { DataFreshness } from "./DataFreshness";

/** Thin glass top bar (DESIGN.md §4). ⌘K search is still to come. */
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
        <DataFreshness />
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
