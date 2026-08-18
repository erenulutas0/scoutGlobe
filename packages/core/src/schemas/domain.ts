import { z } from "zod";

/**
 * Domain schemas mirror the DB schema in docs/ARCHITECTURE.md §4.
 * Types are inferred from the schemas so there is a single source of truth.
 */

export const positionGroupSchema = z.enum(["GK", "DF", "MF", "FW"]);
export type PositionGroup = z.infer<typeof positionGroupSchema>;

export const countrySchema = z.object({
  code: z.string().length(2),
  name: z.string(),
  nameTr: z.string().nullable(),
  // null for countries the 110m map does not draw (Malta, Monaco, ...).
  lat: z.number().min(-90).max(90).nullable(),
  lng: z.number().min(-180).max(180).nullable(),
});
export type Country = z.infer<typeof countrySchema>;

export const leagueSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  countryCode: z.string().length(2),
  tier: z.number().int().min(1),
  strengthCoef: z.number().nullable(),
  apiFootballId: z.number().int().nullable(),
  fbrefId: z.string().nullable(),
});
export type League = z.infer<typeof leagueSchema>;

export const clubSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  leagueId: z.number().int().nullable(),
  lat: z.number().nullable(),
  lng: z.number().nullable(),
});
export type Club = z.infer<typeof clubSchema>;

export const playerSchema = z.object({
  id: z.number().int(),
  fullName: z.string(),
  birthDate: z.string().nullable(),
  nationalityCode: z.string().nullable(),
  position: z.string().nullable(),
  subPosition: z.string().nullable(),
  foot: z.string().nullable(),
  heightCm: z.number().int().nullable(),
  currentClubId: z.number().int().nullable(),
  marketValueEur: z.number().nullable(),
  contractUntil: z.string().nullable(),
});
export type Player = z.infer<typeof playerSchema>;

export const playerSeasonStatsSchema = z.object({
  playerId: z.number().int(),
  season: z.string(),
  leagueId: z.number().int().nullable(),
  clubId: z.number().int().nullable(),
  source: z.string(),
  minutes: z.number().int().nullable(),
  matches: z.number().int().nullable(),
  goals: z.number().int().nullable(),
  assists: z.number().int().nullable(),
  xg: z.number().nullable(),
  xa: z.number().nullable(),
  keyMetrics: z.record(z.string(), z.unknown()).nullable(),
});
export type PlayerSeasonStats = z.infer<typeof playerSeasonStatsSchema>;

/** One node on the globe: a league anchored at its country centroid. */
export const globeLeagueNodeSchema = z.object({
  leagueId: z.number().int(),
  name: z.string(),
  countryCode: z.string(),
  tier: z.number().int(),
  strengthCoef: z.number().nullable(),
  lat: z.number(),
  lng: z.number(),
  clubCount: z.number().int(),
  playerCount: z.number().int(),
});
export type GlobeLeagueNode = z.infer<typeof globeLeagueNodeSchema>;

/** One animated transfer arc (aggregated country -> country). */
export const globeTransferArcSchema = z.object({
  fromLat: z.number(),
  fromLng: z.number(),
  toLat: z.number(),
  toLng: z.number(),
  transferCount: z.number().int(),
  totalFeeEur: z.number().nullable(),
  season: z.string().nullable(),
});
export type GlobeTransferArc = z.infer<typeof globeTransferArcSchema>;

export const globeSummarySchema = z.object({
  countries: z.array(countrySchema),
  leagues: z.array(globeLeagueNodeSchema),
  arcs: z.array(globeTransferArcSchema),
  generatedAt: z.string(),
});
export type GlobeSummary = z.infer<typeof globeSummarySchema>;

export const healthSchema = z.object({
  status: z.literal("ok"),
  service: z.string(),
  version: z.string(),
  database: z.enum(["up", "down", "unknown"]),
});
export type Health = z.infer<typeof healthSchema>;
