import { MIN_MINUTES_FOR_PER90 } from "./constants";

/**
 * Per-90 rate. Returns null when the sample is too small to be meaningful,
 * so the UI can render "—" instead of a misleading number.
 */
export function per90(total: number | null | undefined, minutes: number | null | undefined): number | null {
  if (total === null || total === undefined) return null;
  if (!minutes || minutes < MIN_MINUTES_FOR_PER90) return null;
  return (total * 90) / minutes;
}

/** True when a season sample clears the per-90 minutes gate. */
export function hasEnoughMinutes(minutes: number | null | undefined): boolean {
  return typeof minutes === "number" && minutes >= MIN_MINUTES_FOR_PER90;
}

/** Age in whole years at a given reference date (defaults to "now" by the caller). */
export function ageAt(birthDate: string | null | undefined, reference: Date): number | null {
  if (!birthDate) return null;
  const born = new Date(birthDate);
  if (Number.isNaN(born.getTime())) return null;

  let age = reference.getUTCFullYear() - born.getUTCFullYear();
  const monthDiff = reference.getUTCMonth() - born.getUTCMonth();
  if (monthDiff < 0 || (monthDiff === 0 && reference.getUTCDate() < born.getUTCDate())) {
    age -= 1;
  }
  return age;
}
