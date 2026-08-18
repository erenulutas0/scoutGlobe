import type { PositionGroup } from "../schemas/domain";

const POSITION_LOOKUP: Record<string, PositionGroup> = {
  goalkeeper: "GK",
  keeper: "GK",
  gk: "GK",
  defender: "DF",
  defence: "DF",
  df: "DF",
  "centre-back": "DF",
  "center-back": "DF",
  "left-back": "DF",
  "right-back": "DF",
  midfield: "MF",
  midfielder: "MF",
  mf: "MF",
  attack: "FW",
  attacker: "FW",
  forward: "FW",
  fw: "FW",
  striker: "FW",
  winger: "FW",
};

/**
 * Maps a free-text position coming from any source (Transfermarkt, FBref,
 * API-Football) onto one of the four position groups. Returns null when the
 * value is unknown — callers must not silently guess (see CLAUDE.md).
 */
export function toPositionGroup(position: string | null | undefined): PositionGroup | null {
  if (!position) return null;
  const normalized = position.trim().toLowerCase();
  const direct = POSITION_LOOKUP[normalized];
  if (direct) return direct;

  for (const [key, group] of Object.entries(POSITION_LOOKUP)) {
    if (normalized.includes(key)) return group;
  }
  return null;
}
