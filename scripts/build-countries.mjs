/**
 * Generates the country reference data used by both the globe and the DB seed.
 *
 * Two different needs, deliberately kept apart:
 *   - countries.csv       -> the FULL ISO 3166-1 list. Players hold nationalities
 *                            from micro-states (Malta, Monaco, Cape Verde...) that
 *                            the 110m map does not draw, so deriving this table
 *                            from geometry would silently drop them.
 *   - countries-meta.json -> only the countries the globe can actually render,
 *                            keyed by the topology's numeric id.
 *
 * Sources (no hand-typed coordinates — everything is derived):
 *   - geometry + numeric ISO ids : world-atlas (Natural Earth 110m)
 *   - centroids                  : d3-geo geoCentroid over that geometry
 *   - alpha-2 code + EN/TR names : i18n-iso-countries
 */
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { geoArea, geoCentroid } from "d3-geo";
import countries from "i18n-iso-countries";
import { feature } from "topojson-client";

const require = createRequire(import.meta.url);
const topology = require("world-atlas/countries-110m.json");
countries.registerLocale(require("i18n-iso-countries/langs/en.json"));
countries.registerLocale(require("i18n-iso-countries/langs/tr.json"));

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const collection = feature(topology, topology.objects.countries);

/**
 * Centroid of the largest landmass, not of the whole geometry: France's overseas
 * departments (and Alaska, Svalbard, the Azores...) would otherwise drag the
 * camera target into the ocean.
 */
function mainlandCentroid(feat) {
  const geometry = feat.geometry;
  if (geometry?.type !== "MultiPolygon" || geometry.coordinates.length < 2) {
    return geoCentroid(feat);
  }

  let largest = null;
  let largestArea = -1;
  for (const coordinates of geometry.coordinates) {
    const polygon = { type: "Polygon", coordinates };
    const area = geoArea(polygon);
    if (area > largestArea) {
      largestArea = area;
      largest = polygon;
    }
  }
  return geoCentroid(largest);
}

const centroidByCode = new Map();
const meta = {};
const geometryWithoutIsoCode = [];

for (const country of collection.features) {
  const numericId = String(country.id).padStart(3, "0");
  const code = countries.numericToAlpha2(numericId);
  const name = code ? countries.getName(code, "en") : null;

  if (!code || !name) {
    // Never skip silently (CLAUDE.md): report what could not be matched.
    geometryWithoutIsoCode.push(`${country.id} ${country.properties?.name ?? "?"}`);
    continue;
  }

  const [lng, lat] = mainlandCentroid(country);
  centroidByCode.set(code, { lat, lng });
  meta[String(country.id)] = {
    code,
    name,
    nameTr: countries.getName(code, "tr") ?? name,
    lat: Number(lat.toFixed(4)),
    lng: Number(lng.toFixed(4)),
  };
}

const rows = Object.keys(countries.getAlpha2Codes())
  .map((code) => {
    const name = countries.getName(code, "en");
    if (!name) return null;
    const centroid = centroidByCode.get(code) ?? null;
    return {
      code,
      name,
      nameTr: countries.getName(code, "tr") ?? name,
      lat: centroid ? centroid.lat : null,
      lng: centroid ? centroid.lng : null,
    };
  })
  .filter(Boolean)
  .sort((a, b) => a.code.localeCompare(b.code));

const csvEscape = (value) => (/[",\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value);
const csv = [
  "code,name,name_tr,lat,lng",
  ...rows.map((r) =>
    [
      csvEscape(r.code),
      csvEscape(r.name),
      csvEscape(r.nameTr),
      r.lat === null ? "" : r.lat.toFixed(4),
      r.lng === null ? "" : r.lng.toFixed(4),
    ].join(","),
  ),
].join("\n");

const geoDir = join(root, "apps", "web", "public", "geo");
await mkdir(join(root, "data", "reference"), { recursive: true });
await mkdir(geoDir, { recursive: true });

await writeFile(join(root, "data", "reference", "countries.csv"), `${csv}\n`, "utf8");
await writeFile(join(geoDir, "countries-110m.json"), JSON.stringify(topology), "utf8");
await writeFile(join(geoDir, "countries-meta.json"), JSON.stringify(meta), "utf8");

const withoutCentroid = rows.filter((r) => r.lat === null).length;
console.log(`countries.csv        : ${rows.length} rows (${withoutCentroid} without a centroid)`);
console.log(`countries-meta.json  : ${Object.keys(meta).length} renderable countries`);
if (geometryWithoutIsoCode.length > 0) {
  console.warn(
    `geometry without ISO id: ${geometryWithoutIsoCode.length} -> ${geometryWithoutIsoCode.join(", ")}`,
  );
}
