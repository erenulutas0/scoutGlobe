"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

function formatDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleDateString("tr-TR", { day: "numeric", month: "short", year: "numeric" });
}

function daysSince(value: string | null | undefined): number | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return Math.floor((Date.now() - parsed.getTime()) / 86_400_000);
}

/**
 * Says how far the data reaches.
 *
 * Every number on these screens is a snapshot, and a snapshot shown without a
 * date reads as "today" — which is how a departed player keeps appearing in a
 * squad. The colour follows the age of the newest transfer, because that is
 * what goes stale first.
 */
export function DataFreshness() {
  const { data } = useQuery({
    queryKey: ["freshness"],
    queryFn: ({ signal }) => api.freshness(signal),
    staleTime: 10 * 60_000,
  });

  if (!data) return null;

  const transferDate = formatDate(data.lastTransferOn);
  const age = daysSince(data.lastTransferOn);
  if (!transferDate || age === null) return null;

  const tone =
    age <= 7
      ? "text-grass"
      : age <= 30
        ? "text-scout-amber"
        : "text-alert-coral";

  return (
    <span
      className="stat hidden items-center gap-1.5 text-xs text-text-muted sm:flex"
      title={[
        `Son transfer: ${transferDate}`,
        data.lastMatchOn ? `Son maç: ${formatDate(data.lastMatchOn)}` : null,
        data.lastValuationOn ? `Son değerleme: ${formatDate(data.lastValuationOn)}` : null,
        data.latestSeason ? `Son sezon: ${data.latestSeason}` : null,
      ]
        .filter(Boolean)
        .join(" · ")}
    >
      <span className={tone} aria-hidden>
        ●
      </span>
      <span className="tracking-[0.06em] uppercase">
        veri {transferDate}
        {age > 0 ? ` · ${age} gün` : ""}
      </span>
    </span>
  );
}
