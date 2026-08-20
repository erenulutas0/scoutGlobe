"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { SearchHit } from "@scoutglobe/core";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { RemoteImage } from "@/features/shared/RemoteImage";
import { useGlobeStore } from "@/features/globe/globe-store";
import { usePaletteStore } from "./palette-store";

const KIND_LABELS: Record<string, string> = {
  player: "Oyuncular",
  club: "Kulüpler",
  league: "Ligler",
};

const KIND_ORDER = ["player", "club", "league"];

// Long enough that a keystroke does not cost a round trip, short enough that
// the list feels attached to the keyboard.
const DEBOUNCE_MS = 180;
const MIN_QUERY = 2;

/**
 * ISO alpha-2 -> the numeric topology id the globe store keys on.
 *
 * Only the metadata file, and only once the palette is open. The globe's own
 * hook also pulls the 108KB topology, which this needs none of and which would
 * otherwise be downloaded on every page that carries a search box.
 */
function useCountryTopologyIds() {
  return useQuery({
    queryKey: ["country-topology-ids"],
    staleTime: Infinity,
    gcTime: Infinity,
    queryFn: async ({ signal }) => {
      const response = await fetch("/geo/countries-meta.json", { signal });
      if (!response.ok) throw new Error("Ülke verisi yüklenemedi");
      const meta = (await response.json()) as Record<string, { code: string }>;
      const byCode: Record<string, string> = {};
      for (const [topologyId, entry] of Object.entries(meta)) {
        if (entry?.code) byCode[entry.code.toUpperCase()] = topologyId;
      }
      return byCode;
    },
  });
}

/**
 * The open palette.
 *
 * A separate component so that closing it unmounts the query, the results and
 * the highlighted row together. Clearing them by hand in an effect is the same
 * thing said worse, and it is what React's lint rule about synchronous state
 * updates inside effects is pointing at.
 */
function PaletteDialog({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: topologyIds } = useCountryTopologyIds();
  const selectCountry = useGlobeStore((state) => state.selectCountry);
  const selectLeague = useGlobeStore((state) => state.selectLeague);
  const selectClub = useGlobeStore((state) => state.selectClub);

  const ready = query.trim().length >= MIN_QUERY;

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < MIN_QUERY) return undefined;

    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      api
        .search({ q: trimmed, limit: 6 }, controller.signal)
        .then((result) => {
          setHits(result.items);
          setNote(result.note ?? null);
          setActive(0);
        })
        .catch((cause: unknown) => {
          if (controller.signal.aborted) return;
          setNote(cause instanceof Error ? cause.message : "Arama başarısız oldu.");
        })
        .finally(() => setLoading(false));
    }, DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  // Results are kept while a new query is typed rather than blanked, so the
  // list does not flash empty between keystrokes. They are simply not shown
  // once the query is too short to have produced them.
  const grouped = useMemo(() => {
    if (!ready) return [];
    const ordered = KIND_ORDER.flatMap((kind) => hits.filter((hit) => hit.kind === kind));
    // The group heading is decided here rather than tracked while rendering:
    // a row knows whether it opens its section, so the list stays a pure map.
    return ordered.map((hit, index) => ({
      hit,
      header: hit.kind !== ordered[index - 1]?.kind ? (KIND_LABELS[hit.kind] ?? null) : null,
    }));
  }, [hits, ready]);

  const choose = useCallback(
    (hit: SearchHit) => {
      onClose();
      if (hit.kind === "player") {
        router.push(`/players/${hit.id}`);
        return;
      }

      // Clubs and leagues have no page: they live in the globe's country ->
      // league -> club drill-down, which is state rather than a route.
      const topologyId = hit.countryCode
        ? (topologyIds?.[hit.countryCode.toUpperCase()] ?? null)
        : null;
      if (topologyId) selectCountry(topologyId);
      if (hit.leagueId != null) selectLeague(hit.leagueId);
      if (hit.kind === "club") selectClub(hit.id);
      router.push("/");
    },
    [onClose, router, selectClub, selectCountry, selectLeague, topologyIds],
  );

  function onInputKey(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => Math.min(index + 1, grouped.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      const entry = grouped[active];
      if (entry) choose(entry.hit);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-space/70 px-4 pt-[12vh] backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Ara"
      onClick={onClose}
    >
      <div
        className="glass-panel rounded-card w-full max-w-xl overflow-hidden"
        onClick={(event) => event.stopPropagation()}
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={onInputKey}
          placeholder="Oyuncu, kulüp veya lig ara — Türkçe karakter gerekmez"
          className="w-full border-b border-stroke-panel bg-transparent px-4 py-3 text-sm text-text-primary outline-none placeholder:text-text-muted"
        />

        <div className="max-h-[52vh] overflow-y-auto">
          {grouped.map(({ hit, header }, index) => {
            return (
              <div key={`${hit.kind}-${hit.id}`}>
                {header && (
                  <p className="px-4 pt-3 pb-1 text-[11px] tracking-wide text-text-muted uppercase">
                    {header}
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => choose(hit)}
                  onMouseEnter={() => setActive(index)}
                  className={`flex w-full items-center gap-3 px-4 py-2 text-left transition-colors ${
                    index === active ? "bg-white/8" : "hover:bg-white/4"
                  }`}
                >
                  <RemoteImage
                    src={hit.imageUrl}
                    alt={hit.label}
                    size={26}
                    rounded={hit.kind === "player" ? "full" : "card"}
                    className="shrink-0"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm text-text-primary">{hit.label}</span>
                    {hit.detail && (
                      <span className="block truncate text-xs text-text-muted">{hit.detail}</span>
                    )}
                  </span>
                </button>
              </div>
            );
          })}

          {ready && grouped.length === 0 && (
            <p className="px-4 py-6 text-center text-sm text-text-muted">
              {loading ? "Aranıyor…" : (note ?? "Eşleşme yok.")}
            </p>
          )}
          {!ready && (
            <p className="px-4 py-6 text-center text-sm text-text-muted">
              En az {MIN_QUERY} harf yaz. ↑↓ ile gez, Enter ile aç.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * ⌘K, the way into everything. Mounted once, in the root layout.
 *
 * A scouting tool's first move is "find this player", and until now the only
 * way was drilling through the globe country by country. Search folds accents
 * on both sides, so "kokcu" finds Kökçü — on a Turkish keyboard or without one.
 *
 * The listener lives here rather than beside the button because a shortcut
 * that only works on the pages carrying a search box is not a shortcut: ⌘K did
 * nothing on a player profile, which is where a scout spends his time.
 */
export function CommandPaletteHost() {
  const open = usePaletteStore((state) => state.open);
  const setOpen = usePaletteStore((state) => state.setOpen);
  const toggle = usePaletteStore((state) => state.toggle);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        toggle();
        return;
      }
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setOpen, toggle]);

  if (!open) return null;
  return <PaletteDialog onClose={() => setOpen(false)} />;
}

/** The affordance. Says the shortcut exists, for anyone who would not guess. */
export function SearchButton() {
  const setOpen = usePaletteStore((state) => state.setOpen);

  return (
    <button
      type="button"
      onClick={() => setOpen(true)}
      className="stat flex items-center gap-2 rounded-md border border-stroke-panel px-2.5 py-1.5 text-xs text-text-muted transition-colors hover:border-arc-out hover:text-text-primary"
    >
      <span>Ara</span>
      <span className="opacity-60">⌘K</span>
    </button>
  );
}
