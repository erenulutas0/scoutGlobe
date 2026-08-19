"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import type { League, TransferBoard } from "@scoutglobe/core";
import { api } from "@/lib/api";
import { TransferRow } from "@/features/transfers/TransferRow";

const DIRECTIONS: { label: string; value: "all" | "in" | "out" }[] = [
  { label: "Hepsi", value: "all" },
  { label: "Gelenler", value: "in" },
  { label: "Gidenler", value: "out" },
];

const FEES: { label: string; value: number | "" }[] = [
  { label: "Hepsi", value: "" },
  { label: "1M € üstü", value: 1_000_000 },
  { label: "10M € üstü", value: 10_000_000 },
  { label: "30M € üstü", value: 30_000_000 },
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
 * The transfer board.
 *
 * A window is a date range rather than a season label, because the two sources
 * spell seasons differently and a scout thinks in "this summer" anyway.
 */
export function TransferBoardView({
  leagues,
  windows,
  initialBoard,
  initialWindow,
}: {
  leagues: League[];
  windows: { label: string; since: string; until?: string }[];
  initialBoard: TransferBoard;
  initialWindow: string;
}) {
  const [windowKey, setWindowKey] = useState(initialWindow);
  const [leagueId, setLeagueId] = useState<number | "">("");
  const [direction, setDirection] = useState<"all" | "in" | "out">("all");
  const [minFee, setMinFee] = useState<number | "">("");

  const [board, setBoard] = useState<TransferBoard>(initialBoard);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const firstRun = useRef(true);

  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }

    const selected = windows.find((entry) => entry.label === windowKey);
    if (!selected) return;

    const controller = new AbortController();
    api
      .transfers(
        {
          since: selected.since,
          until: selected.until,
          league_id: leagueId === "" ? undefined : leagueId,
          direction,
          min_fee_eur: minFee === "" ? undefined : minFee,
          limit: 100,
        },
        controller.signal,
      )
      .then((next) => {
        startTransition(() => setBoard(next));
        setError(null);
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : "Tahta yüklenemedi.");
      });
    return () => controller.abort();
  }, [windowKey, leagueId, direction, minFee, windows]);

  const live = board.items.filter((item) => item.sources.includes("api-football")).length;

  return (
    <div className="flex flex-col gap-5">
      <section className="glass-panel rounded-card p-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Field label="Dönem">
            <select
              className={SELECT_CLASS}
              value={windowKey}
              onChange={(event) => setWindowKey(event.target.value)}
            >
              {windows.map((entry) => (
                <option key={entry.label} value={entry.label}>
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

          <Field label="Yön">
            <select
              className={SELECT_CLASS}
              value={direction}
              onChange={(event) => setDirection(event.target.value as "all" | "in" | "out")}
              disabled={leagueId === ""}
              title={leagueId === "" ? "Önce bir lig seç" : undefined}
            >
              {DIRECTIONS.map((entry) => (
                <option key={entry.value} value={entry.value}>
                  {entry.label}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Bonservis">
            <select
              className={SELECT_CLASS}
              value={minFee}
              onChange={(event) =>
                setMinFee(event.target.value === "" ? "" : Number(event.target.value))
              }
            >
              {FEES.map((entry) => (
                <option key={entry.label} value={entry.value}>
                  {entry.label}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <p className="stat mt-3 border-t border-stroke-panel pt-3 text-[11px] text-text-muted">
          {board.items.length} hareket · {live} tanesi canlı kaynakla güne kadar doğrulandı.
          Kalanların tarihi Transfermarkt&apos;ın dönem etiketidir, o yüzden gün değil{" "}
          <span style={{ color: "var(--color-scout-amber)" }}>&quot;2026 yazı&quot;</span> yazar.
          Bonservis yalnızca Transfermarkt&apos;ta var; canlı kaynak ücret yayımlamıyor.
        </p>
      </section>

      {error && <p className="glass-panel rounded-card p-4 text-sm text-alert-coral">{error}</p>}
      {board.note && !error && (
        <p className="glass-panel rounded-card p-4 text-sm text-text-muted">{board.note}</p>
      )}

      <div className={`flex flex-col gap-2 transition-opacity ${pending ? "opacity-60" : ""}`}>
        {board.items.map((transfer) => (
          <TransferRow key={transfer.id} transfer={transfer} />
        ))}
      </div>
    </div>
  );
}
