"use client";

import dynamic from "next/dynamic";
import { CountryPanel } from "./CountryPanel";
import { GlobeSkeleton } from "./GlobeSkeleton";
import { useCountries } from "./use-countries";

// WebGL cannot run on the server — react-globe.gl must load client-side only.
const GlobeCanvas = dynamic(() => import("./GlobeCanvas").then((m) => m.GlobeCanvas), {
  ssr: false,
  loading: () => <GlobeSkeleton />,
});

export function GlobeScene() {
  const { isPending, isError } = useCountries();

  return (
    <div className="absolute inset-0">
      {isPending && <GlobeSkeleton />}
      {isError && <GlobeSkeleton label="Ülke verisi yüklenemedi" />}
      {!isPending && !isError && <GlobeCanvas />}
      <CountryPanel />
    </div>
  );
}
