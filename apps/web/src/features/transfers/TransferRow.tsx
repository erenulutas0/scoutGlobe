import Link from "next/link";
import type { Transfer, TransferSide } from "@scoutglobe/core";
import { formatMarketValue } from "@scoutglobe/core";
import { RemoteImage } from "@/features/shared/RemoteImage";

const TYPE_LABELS: Record<string, string> = {
  Transfer: "Bonservisle",
  Loan: "Kiralık",
  "Free agent": "Serbest",
  "Return from loan": "Kiralık dönüşü",
  "N/A": "Belirsiz",
};

const TYPE_COLORS: Record<string, string> = {
  Loan: "var(--color-scout-amber)",
  "Return from loan": "var(--color-scout-amber)",
  "Free agent": "var(--color-arc-out)",
};

/** Turkish month names — Intl would need a locale bundle we do not ship. */
const MONTHS = [
  "Oca",
  "Şub",
  "Mar",
  "Nis",
  "May",
  "Haz",
  "Tem",
  "Ağu",
  "Eyl",
  "Eki",
  "Kas",
  "Ara",
];

function formatDay(iso: string | null | undefined, exact: boolean): string {
  if (!iso) return "—";
  const [year, month, day] = iso.split("-").map(Number);
  if (!year || !month || !day) return iso;
  // An inexact date is Transfermarkt's window bucket. Printing "1 Tem" for it
  // would claim a precision the source never had, so it reads as the window.
  if (!exact) return `${year} yazı`;
  return `${day} ${MONTHS[month - 1]}`;
}

function Side({ side, muted = false }: { side: TransferSide; muted?: boolean }) {
  // Clubs have no page of their own yet — they are reached through the globe —
  // so the name is plain text rather than a link that would 404.
  const name = side.name ?? "serbest";
  return (
    <span className="flex min-w-0 items-center gap-1.5">
      {side.logoUrl && (
        <RemoteImage src={side.logoUrl} alt={name} size={16} rounded="card" className="shrink-0" />
      )}
      <span className={`truncate ${muted ? "text-text-muted" : "text-text-primary"}`}>{name}</span>
    </span>
  );
}

/**
 * One move on the board.
 *
 * The provenance is on the row, not in a footnote: a date confirmed to the day
 * by the live source reads as "11 Ağu", one Transfermarkt filed under the
 * window's opening day reads as "2026 yazı". A scout deciding whether a deal
 * has actually closed needs that difference visible.
 */
export function TransferRow({ transfer }: { transfer: Transfer }) {
  const { player } = transfer;
  const type = transfer.transferType ?? "";
  const typeLabel = TYPE_LABELS[type] ?? type;
  const live = transfer.sources.includes("api-football");

  return (
    <article className="glass-panel rounded-card flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 transition-colors hover:bg-white/4">
      <span
        className="stat w-20 shrink-0 text-xs"
        style={{ color: transfer.dateIsExact ? "var(--color-text-primary)" : "var(--color-text-muted)" }}
        title={transfer.dateIsExact ? "Canlı kaynakla güne kadar doğrulandı" : "Kaynak yalnızca transfer dönemini veriyor"}
      >
        {formatDay(transfer.transferDate, transfer.dateIsExact)}
      </span>

      <RemoteImage src={player.imageUrl} alt={player.fullName} size={32} className="shrink-0" />

      <Link
        href={`/players/${player.id}`}
        className="min-w-[9rem] flex-1 truncate text-sm hover:text-arc-out hover:underline"
      >
        {player.fullName}
      </Link>

      <span className="flex min-w-[16rem] flex-[2] items-center gap-2 text-xs">
        <Side side={transfer.fromClub} muted />
        <span aria-hidden className="shrink-0 text-text-muted">
          →
        </span>
        <Side side={transfer.toClub} />
      </span>

      {typeLabel && (
        <span
          className="stat w-24 shrink-0 text-right text-[11px]"
          style={{ color: TYPE_COLORS[type] ?? "var(--color-text-muted)" }}
        >
          {typeLabel}
        </span>
      )}

      <span className="stat w-24 shrink-0 text-right text-sm">
        {transfer.feeEur ? formatMarketValue(transfer.feeEur) : <span className="text-text-muted">—</span>}
      </span>

      <span
        className="stat w-16 shrink-0 text-right text-[10px] text-text-muted"
        title={`Kaynak: ${transfer.sources.join(", ") || "bilinmiyor"}`}
      >
        {live ? "canlı" : "arşiv"}
      </span>
    </article>
  );
}
