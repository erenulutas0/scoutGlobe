/** Formatting helpers. Pure + platform-agnostic (Intl exists in Node, browsers and RN). */

/** "€ 12,5 mn" style compact market value. Returns "—" for missing values. */
export function formatMarketValue(valueEur: number | null | undefined, locale = "tr-TR"): string {
  if (valueEur === null || valueEur === undefined) return "—";
  if (valueEur >= 1_000_000) {
    return `€${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(valueEur / 1_000_000)} mn`;
  }
  if (valueEur >= 1_000) {
    return `€${new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(valueEur / 1_000)} bin`;
  }
  return `€${new Intl.NumberFormat(locale).format(valueEur)}`;
}

/** Fixed-decimal stat, always rendered with a mono font in the UI (DESIGN.md §3). */
export function formatStat(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

/** "2024/25" from a season key like "2024". */
/**
 * "2025-26" -> "2025/26", and "2026" -> "2026".
 *
 * Two shapes are stored, because two shapes exist: a European season spans two
 * years and Brazil, Argentina, MLS, Japan, Korea, Norway and Sweden play theirs
 * inside one. Treating every label as a span printed the Brazilian 2026 season
 * as "2026/27", which names a season that does not exist.
 */
export function formatSeason(season: string): string {
  if (!season.includes("-")) return season;
  const year = Number.parseInt(season, 10);
  if (Number.isNaN(year)) return season;
  return `${year}/${String((year + 1) % 100).padStart(2, "0")}`;
}
