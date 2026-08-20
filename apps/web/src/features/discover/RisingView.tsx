"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import type { League, RisingResult } from "@scoutglobe/core";
import { api } from "@/lib/api";
import { RisingCard } from "@/features/discover/RisingCard";

const POSITIONS: { label: string; value: string }[] = [
  { label: "Hepsi", value: "" },
  { label: "Kaleci", value: "GK" },
  { label: "Defans", value: "DF" },
  { label: "Orta saha", value: "MF" },
  { label: "Forvet", value: "FW" },
];

const AGES = [19, 21, 23, 25];

const BUDGETS: { label: string; value: number | "" }[] = [
  { label: "Sınırsız", value: "" },
  { label: "5M € altı", value: 5_000_000 },
  { label: "15M € altı", value: 15_000_000 },
  { label: "40M € altı", value: 40_000_000 },
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
 * The rising-players view.
 *
 * The score is an opinion built from facts, so the facts travel with it: every
 * card breaks the number into profile, league weight and youth. A scout who
 * disagrees with the weighting can still read the parts.
 */
export function RisingView({
  leagues,
  initialResult,
}: {
  leagues: League[];
  initialResult: RisingResult;
}) {
  const [maxAge, setMaxAge] = useState(initialResult.maxAge);
  const [position, setPosition] = useState("");
  const [maxValue, setMaxValue] = useState<number | "">("");
  const [leagueId, setLeagueId] = useState<number | "">("");

  const [result, setResult] = useState<RisingResult>(initialResult);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const firstRun = useRef(true);

  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }

    const controller = new AbortController();
    api
      .rising(
        {
          max_age: maxAge,
          position_group: position || undefined,
          max_value_eur: maxValue === "" ? undefined : maxValue,
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
        setError(cause instanceof Error ? cause.message : "Liste yüklenemedi.");
      });
    return () => controller.abort();
  }, [maxAge, position, maxValue, leagueId]);

  const priced = result.items.filter((item) => item.momentum).length;

  return (
    <div className="flex flex-col gap-5">
      <section className="glass-panel rounded-card p-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Field label="Yaş tavanı">
            <select
              className={SELECT_CLASS}
              value={maxAge}
              onChange={(event) => setMaxAge(Number(event.target.value))}
            >
              {AGES.map((age) => (
                <option key={age} value={age}>
                  {age} yaş ve altı
                </option>
              ))}
            </select>
          </Field>

          <Field label="Pozisyon">
            <select
              className={SELECT_CLASS}
              value={position}
              onChange={(event) => setPosition(event.target.value)}
            >
              {POSITIONS.map((entry) => (
                <option key={entry.label} value={entry.value}>
                  {entry.label}
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
              {BUDGETS.map((entry) => (
                <option key={entry.label} value={entry.value}>
                  {entry.label}
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
          Skor = profil × lig ağırlığı × 0,7 + gençlik × 0,3. Lig ağırlığı 0,40&apos;ın altına
          inmez: kimsenin izlemediği oyuncuyu bulmak bu işin amacı, zayıf lig indirim yapar ama
          silmez. Piyasa değeri hareketi{" "}
          <span style={{ color: "var(--color-scout-amber)" }}>skora girmez</span> — {priced}/
          {result.items.length} oyuncunun geçmişi var ve olmayanı cezalandırmak, oynadığı için
          değil fiyatlandığı için sıralamak olurdu.
        </p>
      </section>

      {error && <p className="glass-panel rounded-card p-4 text-sm text-alert-coral">{error}</p>}
      {result.note && !error && (
        <p className="glass-panel rounded-card p-4 text-sm text-text-muted">{result.note}</p>
      )}

      <div
        className={`grid gap-3 transition-opacity md:grid-cols-2 xl:grid-cols-3 ${
          pending ? "opacity-60" : ""
        }`}
      >
        {result.items.map((player, index) => (
          <RisingCard key={player.player.id} player={player} rank={index + 1} />
        ))}
      </div>
    </div>
  );
}
