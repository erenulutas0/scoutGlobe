"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

/** Small connectivity chip: proves web ↔ API wiring at a glance during development. */
export function ApiStatus() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => api.health(signal),
    refetchInterval: 30_000,
  });

  const state = isPending
    ? { label: "API bağlanıyor", color: "bg-text-muted" }
    : isError
      ? { label: "API kapalı", color: "bg-alert-coral" }
      : data?.database === "up"
        ? { label: "API + DB açık", color: "bg-grass" }
        : { label: "API açık · DB kapalı", color: "bg-scout-amber" };

  return (
    <span className="flex items-center gap-2 text-xs text-text-muted" aria-live="polite">
      <span aria-hidden className={`size-1.5 rounded-full ${state.color}`} />
      <span className="stat tracking-[0.08em] uppercase">{state.label}</span>
    </span>
  );
}
