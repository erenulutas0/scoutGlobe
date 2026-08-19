"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import type { DiscoverResult, DiscoveryOptions, League } from "@scoutglobe/core";
import { formatSeason } from "@scoutglobe/core";
import { api } from "@/lib/api";
import { CandidateCard } from "@/features/discover/CandidateCard";

const POSITION_LABELS: Record<string, string> = {
  GK: "Kaleci",
  DF: "Defans",
  MF: "Orta saha",
  FW: "Forvet",
};

// Budgets a club actually thinks in, rather than a slider nobody can aim.
const BUDGETS: { label: string; value: number | "" }[] = [
  { label: "Sınırsız", value: "" },
  { label: "5M € altı", value: 5_000_000 },
  { label: "15M € altı", value: 15_000_000 },
  { label: "30M € altı", value: 30_000_000 },
  { label: "60M € altı", value: 60_000_000 },
];

const AGES: { label: string; value: number | "" }[] = [
  { label: "Fark etmez", value: "" },
  { label: "21 yaş altı", value: 20 },
  { label: "24 yaş altı", value: 23 },
  { label: "27 yaş altı", value: 26 },
];

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex min-w-0 flex-col gap-1.5">
      <span className="text-[11px] tracking-wide text-text-muted uppercase">{label}</span>
      {children}
    </label>
  );
}

const SELECT_CLASS =
  "h-9 w-full rounded-md border border-stroke-panel bg-panel-solid px-2.5 text-sm " +
  "text-text-primary outline-none focus:border-arc-out";

/**
 * The discovery form.
 *
 * Every control maps to a filter the API can honour exactly; nothing here is
 * approximated client-side. The metric picker prints each metric's coverage
 * because choosing "xG" silently narrows the search from twelve leagues to
 * five, and a scout who is not told that will read an absence of Turkish
 * players as an absence of Turkish talent.
 */
export function DiscoverForm({
  options,
  leagues,
  initialResult,
}: {
  options: DiscoveryOptions;
  leagues: League[];
  initialResult: DiscoverResult;
}) {
  const [positionGroup, setPositionGroup] = useState(initialResult.positionGroup);
  const [season, setSeason] = useState(initialResult.season);
  const [metric, setMetric] = useState<string>("");
  const [maxValue, setMaxValue] = useState<number | "">("");
  const [maxAge, setMaxAge] = useState<number | "">("");
  const [leagueId, setLeagueId] = useState<number | "">("");

  const [result, setResult] = useState<DiscoverResult>(initialResult);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  // The server already rendered the default query; refetching it on mount
  // would be a wasted round trip and a visible flash of the same list. A ref,
  // not state: flipping it must not schedule a render of its own.
  const firstRun = useRef(true);

  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }

    const controller = new AbortController();
    api
      .discover(
        {
          position_group: positionGroup,
          season,
          metric: metric || undefined,
          max_value_eur: maxValue === "" ? undefined : maxValue,
          max_age: maxAge === "" ? undefined : maxAge,
          league_id: leagueId === "" ? undefined : [leagueId],
          limit: 24,
        },
        controller.signal,
      )
      .then((next) => {
        startTransition(() => setResult(next));
        setError(null);
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : "Arama başarısız oldu.");
      });
    return () => controller.abort();
  }, [positionGroup, season, metric, maxValue, maxAge, leagueId]);

  const selectedMetric = options.metrics.find((option) => option.metric === metric);

  return (
    <div className="flex flex-col gap-5">
      <section className="glass-panel rounded-card p-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          <Field label="Pozisyon">
            <select
              className={SELECT_CLASS}
              value={positionGroup}
              onChange={(event) => setPositionGroup(event.target.value as typeof positionGroup)}
            >
              {options.positionGroups.map((group) => (
                <option key={group} value={group}>
                  {POSITION_LABELS[group] ?? group}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Sezon">
            <select
              className={SELECT_CLASS}
              value={season}
              onChange={(event) => setSeason(event.target.value)}
            >
              {options.seasons.map((value) => (
                <option key={value} value={value}>
                  {formatSeason(value)}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Metrik">
            <select
              className={SELECT_CLASS}
              value={metric}
              onChange={(event) => setMetric(event.target.value)}
            >
              <option value="">En güçlü yönüne göre</option>
              {options.metrics.map((option) => (
                <option key={option.metric} value={option.metric}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Bütçe">
            <select
              className={SELECT_CLASS}
              value={maxValue}
              onChange={(event) =>
                setMaxValue(event.target.value === "" ? "" : Number(event.target.value))
              }
            >
              {BUDGETS.map((option) => (
                <option key={option.label} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Yaş">
            <select
              className={SELECT_CLASS}
              value={maxAge}
              onChange={(event) =>
                setMaxAge(event.target.value === "" ? "" : Number(event.target.value))
              }
            >
              {AGES.map((option) => (
                <option key={option.label} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Lig">
            <select
              className={SELECT_CLASS}
              value={leagueId}
              onChange={(event) =>
                setLeagueId(event.target.value === "" ? "" : Number(event.target.value))
              }
            >
              <option value="">Tüm ligler</option>
              {leagues.map((league) => (
                <option key={league.id} value={league.id}>
                  {league.name}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <p className="stat mt-3 border-t border-stroke-panel pt-3 text-[11px] text-text-muted">
          {options.minMinutes} dakikanın altında oynayanlar listeye girmez — bu kadar az
          örnekte per-90 oyuncuyu değil örneklemi anlatır.
          {selectedMetric && (
            <>
              {" "}
              <span style={{ color: "var(--color-scout-amber)" }}>
                {selectedMetric.label} {selectedMetric.coverage} oyuncu-sezonda ölçülü
              </span>
              {selectedMetric.coverage < 3000 && " — bu metrik tüm liglerde yok."}
            </>
          )}
        </p>
      </section>

      {error && (
        <p className="glass-panel rounded-card p-4 text-sm text-alert-coral">{error}</p>
      )}

      {result.note && !error && (
        <p className="glass-panel rounded-card p-4 text-sm text-text-muted">{result.note}</p>
      )}

      <div
        className={`grid gap-3 transition-opacity md:grid-cols-2 xl:grid-cols-3 ${
          pending ? "opacity-60" : ""
        }`}
      >
        {result.items.map((candidate, index) => (
          <CandidateCard key={candidate.player.id} candidate={candidate} rank={index + 1} />
        ))}
      </div>
    </div>
  );
}
