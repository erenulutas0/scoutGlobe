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
  strengthCoef: z.number().nullish(),
  clubCount: z.number().int(),
  playerCount: z.number().int(),
});
export type League = z.infer<typeof leagueSchema>;

export const clubSummarySchema = z.object({
  id: z.number().int(),
  name: z.string(),
  leagueId: z.number().int().nullish(),
  squadSize: z.number().int(),
});
export type ClubSummary = z.infer<typeof clubSummarySchema>;

export const leagueDetailSchema = leagueSchema.extend({
  country: countrySchema.nullish(),
  clubs: z.array(clubSummarySchema),
});
export type LeagueDetail = z.infer<typeof leagueDetailSchema>;

export const playerSummarySchema = z.object({
  id: z.number().int(),
  fullName: z.string(),
  position: z.string().nullish(),
  subPosition: z.string().nullish(),
  birthDate: z.string().nullish(),
  age: z.number().int().nullish(),
  nationalityCode: z.string().nullish(),
  clubId: z.number().int().nullish(),
  clubName: z.string().nullish(),
  leagueId: z.number().int().nullish(),
  marketValueEur: z.number().nullish(),
});
export type PlayerSummary = z.infer<typeof playerSummarySchema>;

export const clubDetailSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  leagueId: z.number().int().nullish(),
  leagueName: z.string().nullish(),
  countryCode: z.string().nullish(),
  squad: z.array(playerSummarySchema),
});
export type ClubDetail = z.infer<typeof clubDetailSchema>;

export const seasonStatsSchema = z.object({
  season: z.string(),
  source: z.string(),
  leagueId: z.number().int().nullish(),
  clubId: z.number().int().nullish(),
  clubName: z.string().nullish(),
  minutes: z.number().int().nullish(),
  matches: z.number().int().nullish(),
  goals: z.number().int().nullish(),
  assists: z.number().int().nullish(),
  xg: z.number().nullish(),
  xa: z.number().nullish(),
  /** Null below the 900-minute gate — the API refuses to invent a rate. */
  goalsPer90: z.number().nullish(),
  assistsPer90: z.number().nullish(),
  keyMetrics: z.record(z.string(), z.unknown()).nullish(),
});
export type SeasonStats = z.infer<typeof seasonStatsSchema>;

export const marketValuePointSchema = z.object({
  date: z.string(),
  valueEur: z.number(),
});
export type MarketValuePoint = z.infer<typeof marketValuePointSchema>;

export const playerDetailSchema = playerSummarySchema.extend({
  leagueName: z.string().nullish(),
  foot: z.string().nullish(),
  heightCm: z.number().int().nullish(),
  contractUntil: z.string().nullish(),
  seasonStats: z.array(seasonStatsSchema),
  marketValueHistory: z.array(marketValuePointSchema),
});
export type PlayerDetail = z.infer<typeof playerDetailSchema>;

export const playerSearchResultSchema = z.object({
  items: z.array(playerSummarySchema),
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
});
export type PlayerSearchResult = z.infer<typeof playerSearchResultSchema>;

/** One node on the globe: a league anchored at its country centroid. */
export const globeLeagueNodeSchema = z.object({
  leagueId: z.number().int(),
  name: z.string(),
  countryCode: z.string(),
  tier: z.number().int(),
  strengthCoef: z.number().nullish(),
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
  fromCountry: z.string(),
  toCountry: z.string(),
  transferCount: z.number().int(),
  totalFeeEur: z.number().nullish(),
  season: z.string().nullish(),
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
