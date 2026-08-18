"use client";

import { useEffect } from "react";
import { useCountries } from "./use-countries";
import { useGlobeStore } from "./globe-store";

/**
 * Right-hand glass panel (DESIGN.md §4). Covers at most ~35% of the globe on
 * desktop and becomes a bottom sheet on narrow viewports.
 */
export function CountryPanel() {
  const selectedId = useGlobeStore((state) => state.selectedId);
  const setSelected = useGlobeStore((state) => state.setSelected);
  const { data } = useCountries();

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setSelected(null);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [setSelected]);

  if (!selectedId) {
    return (
      <div className="pointer-events-none absolute inset-x-0 bottom-8 flex justify-center px-4">
        <p className="glass-panel rounded-card px-4 py-2 text-sm text-text-muted">
          Bir ülkeye tıklayarak başla.
        </p>
      </div>
    );
  }

  const meta = data?.meta[selectedId];
  const name = meta?.nameTr ?? "Bilinmeyen ülke";

  return (
    <aside
      aria-label="Ülke paneli"
      className="glass-panel absolute inset-x-3 bottom-3 max-h-[52dvh] overflow-y-auto rounded-card p-5 transition-[opacity,transform] duration-200 ease-out md:inset-y-16 md:right-4 md:left-auto md:max-h-none md:w-[clamp(300px,28vw,380px)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="stat text-xs tracking-[0.16em] text-text-muted uppercase">Ülke</p>
          <h2 className="font-[family-name:var(--font-display)] text-2xl leading-tight tracking-[-0.02em]">
            {name}
          </h2>
        </div>
        <button
          type="button"
          onClick={() => setSelected(null)}
          aria-label="Paneli kapat"
          className="rounded-full border border-stroke-panel px-2 py-0.5 text-text-muted transition-colors hover:text-text-primary"
        >
          ×
        </button>
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-stroke-panel pt-4">
        <div>
          <dt className="text-xs text-text-muted">ISO kodu</dt>
          <dd className="stat text-base">{meta?.code ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-text-muted">Merkez</dt>
          <dd className="stat text-base">
            {meta ? `${meta.lat.toFixed(1)}, ${meta.lng.toFixed(1)}` : "—"}
          </dd>
        </div>
      </dl>

      <p className="mt-5 border-t border-stroke-panel pt-4 text-sm text-text-muted">
        Lig ve oyuncu katmanı henüz bağlı değil. Veri tabanı doldukça bu panel ülke → lig → oyuncu
        akışını gösterecek.
      </p>
    </aside>
  );
}
