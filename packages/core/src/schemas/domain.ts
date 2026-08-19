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
  /** Served by the source; may fail to load, so the UI always keeps a fallback. */
  logoUrl: z.string().nullish(),
  countryCode: z.string().length(2),
  tier: z.number().int().min(1),
  strengthCoef: z.number().nullish(),
  /** Season the counts describe; null means they fall back to registered rows. */
  season: z.string().nullish(),
  clubCount: z.number().int(),
  playerCount: z.number().int(),
});
export type League = z.infer<typeof leagueSchema>;

export const clubSummarySchema = z.object({
  id: z.number().int(),
  name: z.string(),
  logoUrl: z.string().nullish(),
  leagueId: z.number().int().nullish(),
  squadSize: z.number().int(),
});
export type ClubSummary = z.infer<typeof clubSummarySchema>;

export const leagueDetailSchema = leagueSchema.extend({
  country: countrySchema.nullish(),
  squadSeason: z.string().nullish(),
  clubs: z.array(clubSummarySchema),
});
export type LeagueDetail = z.infer<typeof leagueDetailSchema>;

export const playerSummarySchema = z.object({
  id: z.number().int(),
  fullName: z.string(),
  imageUrl: z.string().nullish(),
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
  logoUrl: z.string().nullish(),
  leagueId: z.number().int().nullish(),
  leagueName: z.string().nullish(),
  leagueLogoUrl: z.string().nullish(),
  countryCode: z.string().nullish(),
  squadSeason: z.string().nullish(),
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
  clubLogoUrl: z.string().nullish(),
  leagueName: z.string().nullish(),
  leagueLogoUrl: z.string().nullish(),
  foot: z.string().nullish(),
  heightCm: z.number().int().nullish(),
  contractUntil: z.string().nullish(),
  seasonStats: z.array(seasonStatsSchema),
  marketValueHistory: z.array(marketValuePointSchema),
});
export type PlayerDetail = z.infer<typeof playerDetailSchema>;

export const formPointSchema = z.object({
  matchId: z.number().int(),
  playedOn: z.string().nullish(),
  clubName: z.string().nullish(),
  leagueName: z.string().nullish(),
  opponentName: z.string().nullish(),
  isHome: z.boolean().nullish(),
  minutes: z.number().int().nullish(),
  value: z.number().nullish(),
  /** Rolling average over the requested window, ending at this match. */
  rolling: z.number().nullish(),
});
export type FormPoint = z.infer<typeof formPointSchema>;

export const formSeriesSchema = z.object({
  metric: z.string(),
  metricLabel: z.string(),
  window: z.number().int(),
  totalMatches: z.number().int(),
  points: z.array(formPointSchema),
});
export type FormSeries = z.infer<typeof formSeriesSchema>;

export const seasonTrendPointSchema = z.object({
  season: z.string(),
  matches: z.number().int(),
  minutes: z.number().int(),
  minutesPerMatch: z.number(),
  goals: z.number().int(),
  assists: z.number().int(),
  goalsPer90: z.number().nullish(),
  assistsPer90: z.number().nullish(),
});
export type SeasonTrendPoint = z.infer<typeof seasonTrendPointSchema>;

export const playerFormSchema = z.object({
  playerId: z.number().int(),
  series: formSeriesSchema,
  seasons: z.array(seasonTrendPointSchema),
});
export type PlayerForm = z.infer<typeof playerFormSchema>;

export const shotSchema = z.object({
  id: z.number().int(),
  playedOn: z.string().nullish(),
  minute: z.number().int().nullish(),
  xg: z.number().nullish(),
  /** Normalised pitch coordinates: x=1.0 is the opponent's goal line. */
  locationX: z.number().nullish(),
  locationY: z.number().nullish(),
  bodyPart: z.string().nullish(),
  situation: z.string().nullish(),
  result: z.string().nullish(),
  isGoal: z.boolean(),
});
export type Shot = z.infer<typeof shotSchema>;

export const shotZoneSchema = z.object({
  zone: z.string(),
  zoneLabel: z.string(),
  shots: z.number().int(),
  goals: z.number().int(),
  xg: z.number(),
  xgPerShot: z.number(),
});
export type ShotZone = z.infer<typeof shotZoneSchema>;

export const playerShotsSchema = z.object({
  playerId: z.number().int(),
  season: z.string().nullish(),
  totalShots: z.number().int(),
  totalGoals: z.number().int(),
  totalXg: z.number(),
  /** Goals minus xG: positive means finishing above the chances created. */
  xgDifference: z.number(),
  zones: z.array(shotZoneSchema),
  shots: z.array(shotSchema),
});
export type PlayerShots = z.infer<typeof playerShotsSchema>;

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
  logoUrl: z.string().nullish(),
  countryCode: z.string(),
  tier: z.number().int(),
  strengthCoef: z.number().nullish(),
  lat: z.number(),
  lng: z.number(),
  season: z.string().nullish(),
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

export const sourceFreshnessSchema = z.object({
  source: z.string(),
  lastRunAt: z.string().nullish(),
  status: z.string().nullish(),
  rowsWritten: z.number().int().nullish(),
});
export type SourceFreshness = z.infer<typeof sourceFreshnessSchema>;

export const dataFreshnessSchema = z.object({
  /** Latest transfer the dataset knows about — the sharpest freshness signal. */
  lastTransferOn: z.string().nullish(),
  lastMatchOn: z.string().nullish(),
  lastValuationOn: z.string().nullish(),
  latestSeason: z.string().nullish(),
  sources: z.array(sourceFreshnessSchema),
});
export type DataFreshness = z.infer<typeof dataFreshnessSchema>;

export const healthSchema = z.object({
  status: z.literal("ok"),
  service: z.string(),
  version: z.string(),
  database: z.enum(["up", "down", "unknown"]),
});
export type Health = z.infer<typeof healthSchema>;
