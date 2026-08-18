import { ApiStatus } from "./ApiStatus";

/** Thin glass top bar (DESIGN.md §4). Search and "Keşfet" arrive in Faz 3/4. */
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
      <ApiStatus />
    </header>
  );
}
