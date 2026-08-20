"use client";

import Link from "next/link";
import { shortlist, useShortlist } from "./shortlist-store";

/**
 * The shortlist, docked at the bottom until it is used.
 *
 * It stays out of the way at zero players and becomes a bar the moment one is
 * added, because the only thing it is for is getting to the comparison.
 */
export function ShortlistBar() {
  const entries = useShortlist();
  if (entries.length === 0) return null;

  const ids = entries.map((entry) => entry.id);
  const ready = entries.length >= 2;

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 flex justify-center px-4 pb-4">
      <div className="glass-panel rounded-card flex max-w-full flex-wrap items-center gap-2 px-3 py-2">
        <span className="stat shrink-0 text-[11px] tracking-wide text-text-muted uppercase">
          Kısa liste
        </span>

        {entries.map((entry) => (
          <span
            key={entry.id}
            className="flex items-center gap-1.5 rounded-md border border-stroke-panel px-2 py-1 text-xs"
          >
            <span className="max-w-[10rem] truncate">{entry.name}</span>
            <button
              type="button"
              onClick={() => shortlist.remove(entry.id)}
              aria-label={`${entry.name} çıkar`}
              className="text-text-muted transition-colors hover:text-alert-coral"
            >
              ×
            </button>
          </span>
        ))}

        {ready ? (
          <Link
            href={`/compare?p=${ids.join(",")}`}
            className="stat rounded-md px-3 py-1.5 text-xs"
            style={{ backgroundColor: "var(--color-arc-out)", color: "var(--color-space)" }}
          >
            Karşılaştır ({entries.length})
          </Link>
        ) : (
          <span className="stat px-2 text-[11px] text-text-muted">
            Karşılaştırmak için bir oyuncu daha ekle
          </span>
        )}

        <button
          type="button"
          onClick={() => shortlist.clear()}
          className="stat px-2 text-[11px] text-text-muted transition-colors hover:text-text-primary"
        >
          Temizle
        </button>
      </div>
    </div>
  );
}
