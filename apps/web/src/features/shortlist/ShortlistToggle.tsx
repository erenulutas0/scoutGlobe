"use client";

import { shortlist, useShortlist } from "./shortlist-store";

/** Add this player to the comparison, or take him out again. */
export function ShortlistToggle({
  playerId,
  name,
  className = "",
}: {
  playerId: number;
  name: string;
  className?: string;
}) {
  const entries = useShortlist();
  const listed = entries.some((entry) => entry.id === playerId);

  return (
    <button
      type="button"
      onClick={() => shortlist.toggle({ id: playerId, name })}
      aria-pressed={listed}
      title={listed ? "Kısa listeden çıkar" : "Karşılaştırmak için kısa listeye ekle"}
      className={`stat shrink-0 rounded-md border px-2 py-1 text-[11px] transition-colors ${className}`}
      style={{
        borderColor: listed
          ? "var(--color-arc-out)"
          : "color-mix(in srgb, var(--color-text-muted) 35%, transparent)",
        color: listed ? "var(--color-arc-out)" : "var(--color-text-muted)",
      }}
    >
      {listed ? "listede" : "+ listeye"}
    </button>
  );
}
