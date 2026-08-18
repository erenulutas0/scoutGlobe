/**
 * Shared, platform-agnostic constants.
 * Rationale for the per-90 threshold: docs/CLAUDE.md — below 900 minutes per-90
 * rates are noise, so every derived metric must respect this gate.
 */
export const MIN_MINUTES_FOR_PER90 = 900;

/** Position-group colour ramp — must match docs/DESIGN.md §2. */
export const POSITION_GROUP_COLORS = {
  GK: "#8A96B5",
  DF: "#5B8CFF",
  MF: "#35D98B",
  FW: "#F5B241",
} as const;

/** Turkish labels for position groups (UI copy language is Turkish). */
export const POSITION_GROUP_LABELS_TR = {
  GK: "Kaleci",
  DF: "Defans",
  MF: "Orta saha",
  FW: "Forvet",
} as const;
