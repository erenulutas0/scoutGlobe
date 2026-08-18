"use client";

import { useQuery } from "@tanstack/react-query";
import { feature } from "topojson-client";
import type { CountryMeta } from "./globe-store";

type Topology = Parameters<typeof feature>[0];

export interface CountryFeature {
  type: "Feature";
  id: string;
  properties: { name: string };
  geometry: unknown;
}

export interface CountriesData {
  features: CountryFeature[];
  meta: Record<string, CountryMeta>;
}

/**
 * Loads the world-atlas 110m topology plus the generated country metadata
 * (ISO code, Turkish name, centroid). Both files are produced by
 * `pnpm seed:countries` and served statically from /public/geo.
 */
async function loadCountries(signal: AbortSignal): Promise<CountriesData> {
  const [topoResponse, metaResponse] = await Promise.all([
    fetch("/geo/countries-110m.json", { signal }),
    fetch("/geo/countries-meta.json", { signal }),
  ]);

  if (!topoResponse.ok || !metaResponse.ok) {
    throw new Error("Ülke geometrisi yüklenemedi.");
  }

  const topology = (await topoResponse.json()) as Topology;
  const meta = (await metaResponse.json()) as Record<string, CountryMeta>;
  const countriesObject = topology.objects.countries;
  if (!countriesObject) {
    throw new Error("Topolojide 'countries' katmanı yok.");
  }

  const collection = feature(topology, countriesObject);
  const features = "features" in collection ? collection.features : [collection];

  return { features: features as unknown as CountryFeature[], meta };
}

export function useCountries() {
  return useQuery({
    queryKey: ["countries", "110m"],
    queryFn: ({ signal }) => loadCountries(signal),
    staleTime: Infinity,
    gcTime: Infinity,
  });
}
