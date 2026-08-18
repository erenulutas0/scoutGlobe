"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Globe, { type GlobeMethods } from "react-globe.gl";
import { Color, MeshPhongMaterial } from "three";
import type { GlobeLeagueNode, GlobeTransferArc } from "@scoutglobe/core";
import { useGlobeStore } from "./globe-store";
import { useCountries, type CountryFeature } from "./use-countries";
import { useGlobeSummary } from "./use-globe-data";

/** DESIGN.md §2 tokens, duplicated here because WebGL cannot read CSS variables. */
const COLORS = {
  polygonIdle: "rgba(13, 20, 38, 0.86)",
  // Selection/hover stay on the arc-out blue: --grass is reserved for positive
  // data signals (DESIGN.md §2), not for interaction state.
  polygonHover: "rgba(91, 140, 255, 0.30)",
  polygonSelected: "rgba(91, 140, 255, 0.58)",
  polygonSide: "rgba(91, 140, 255, 0.10)",
  polygonStroke: "rgba(148, 163, 199, 0.34)",
  atmosphere: "#5B8CFF",
  globeSurface: "#0B1428",
  leagueNode: "#F5B241",
  arcFrom: "#5B8CFF",
  arcTo: "#35D98B",
} as const;

const TRANSITION_MS = 200; // DESIGN.md §5 — 180-220ms.

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function tooltip(title: string, detail: string): string {
  return `<div style="
      font-family: var(--font-sans);
      background: rgba(13,20,38,0.86);
      border: 1px solid rgba(148,163,199,0.18);
      border-radius: 10px;
      padding: 6px 10px;
      color: #E9EDF6;
      font-size: 13px;
      backdrop-filter: blur(8px);
    ">${title}
    <span style="font-family: var(--font-mono); color:#8A96B5; margin-left:6px;">${detail}</span>
  </div>`;
}

export function GlobeCanvas() {
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement | null>(null);
  // A league node sits on top of its country polygon, and three-globe delivers
  // both click handlers. Without this the polygon handler would immediately
  // reset the drill-down back to the country level.
  const lastPointClickRef = useRef(0);
  const [size, setSize] = useState({ width: 0, height: 0 });

  const { data } = useCountries();
  const { data: summary } = useGlobeSummary();
  const hoveredId = useGlobeStore((state) => state.hoveredId);
  const selectedId = useGlobeStore((state) => state.selectedId);
  const setHovered = useGlobeStore((state) => state.setHovered);
  const selectCountry = useGlobeStore((state) => state.selectCountry);
  const selectLeague = useGlobeStore((state) => state.selectLeague);

  // Keep the canvas exactly the size of its container (globe is the hero element).
  // Measure once on mount too: ResizeObserver does not deliver notifications
  // while the tab is hidden, which would leave the globe unmounted.
  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;

    const measure = () => {
      const rect = element.getBoundingClientRect();
      setSize({ width: Math.floor(rect.width), height: Math.floor(rect.height) });
    };

    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  // Dark matte earth — no external texture, colour comes from the design tokens.
  const globeMaterial = useMemo(
    () =>
      new MeshPhongMaterial({
        color: new Color(COLORS.globeSurface),
        emissive: new Color("#060B1A"),
        emissiveIntensity: 0.4,
        shininess: 2,
        transparent: true,
        opacity: 0.96,
      }),
    [],
  );

  useEffect(() => {
    const globe = globeRef.current;
    if (!globe) return;

    const controls = globe.controls();
    controls.autoRotate = !prefersReducedMotion();
    controls.autoRotateSpeed = 0.24;
    controls.enableDamping = true;
    controls.minDistance = 180;
    controls.maxDistance = 620;
    globe.pointOfView({ lat: 25, lng: 12, altitude: 2.4 });
  }, [size.width, size.height]);

  const flyTo = useCallback((lat: number, lng: number) => {
    globeRef.current?.pointOfView({ lat, lng, altitude: 1.35 }, prefersReducedMotion() ? 0 : 700);
  }, []);

  const handlePolygonHover = useCallback(
    (polygon: object | null) => setHovered((polygon as CountryFeature | null)?.id ?? null),
    [setHovered],
  );

  const handlePolygonClick = useCallback(
    (polygon: object) => {
      if (performance.now() - lastPointClickRef.current < 400) return;

      const country = polygon as CountryFeature;
      const meta = data?.meta[country.id];
      selectCountry(country.id);
      if (meta) flyTo(meta.lat, meta.lng);
    },
    [data, flyTo, selectCountry],
  );

  const handlePointClick = useCallback(
    (point: object) => {
      lastPointClickRef.current = performance.now();
      const node = point as GlobeLeagueNode;
      // Jump straight into the league, but keep the country context so the
      // panel's back button still walks up the same path.
      const topologyId = Object.entries(data?.meta ?? {}).find(
        ([, meta]) => meta.code === node.countryCode,
      )?.[0];
      if (topologyId) selectCountry(topologyId);
      selectLeague(node.leagueId);
      flyTo(node.lat, node.lng);
    },
    [data, flyTo, selectCountry, selectLeague],
  );

  const capColor = useCallback(
    (polygon: object) => {
      const country = polygon as CountryFeature;
      if (country.id === selectedId) return COLORS.polygonSelected;
      if (country.id === hoveredId) return COLORS.polygonHover;
      return COLORS.polygonIdle;
    },
    [hoveredId, selectedId],
  );

  const altitude = useCallback(
    (polygon: object) => {
      const country = polygon as CountryFeature;
      return country.id === selectedId || country.id === hoveredId ? 0.022 : 0.006;
    },
    [hoveredId, selectedId],
  );

  const polygonLabel = useCallback(
    (polygon: object) => {
      const country = polygon as CountryFeature;
      const meta = data?.meta[country.id];
      return tooltip(meta?.nameTr ?? country.properties.name, meta?.code ?? "—");
    },
    [data],
  );

  const pointLabel = useCallback((point: object) => {
    const node = point as GlobeLeagueNode;
    return tooltip(node.name, `${node.clubCount} kulüp · ${node.playerCount} oyuncu`);
  }, []);

  const arcLabel = useCallback((arc: object) => {
    const flow = arc as GlobeTransferArc;
    return tooltip(`${flow.fromCountry} → ${flow.toCountry}`, `${flow.transferCount} transfer`);
  }, []);

  const reduceMotion = prefersReducedMotion();

  return (
    <div ref={containerRef} className="absolute inset-0">
      {size.width > 0 && (
        <Globe
          ref={globeRef}
          width={size.width}
          height={size.height}
          backgroundColor="rgba(0,0,0,0)"
          globeMaterial={globeMaterial}
          atmosphereColor={COLORS.atmosphere}
          atmosphereAltitude={0.17}
          polygonsData={data?.features ?? []}
          polygonCapColor={capColor}
          polygonSideColor={() => COLORS.polygonSide}
          polygonStrokeColor={() => COLORS.polygonStroke}
          polygonAltitude={altitude}
          polygonLabel={polygonLabel}
          polygonsTransitionDuration={TRANSITION_MS}
          onPolygonHover={handlePolygonHover}
          onPolygonClick={handlePolygonClick}
          pointsData={summary?.leagues ?? []}
          pointLat={(node) => (node as GlobeLeagueNode).lat}
          pointLng={(node) => (node as GlobeLeagueNode).lng}
          pointColor={() => COLORS.leagueNode}
          pointAltitude={(node) => 0.05 + ((node as GlobeLeagueNode).strengthCoef ?? 0.3) * 0.12}
          pointRadius={(node) => 0.35 + Math.min((node as GlobeLeagueNode).clubCount, 40) / 120}
          pointLabel={pointLabel}
          onPointClick={handlePointClick}
          arcsData={summary?.arcs ?? []}
          arcStartLat={(arc) => (arc as GlobeTransferArc).fromLat}
          arcStartLng={(arc) => (arc as GlobeTransferArc).fromLng}
          arcEndLat={(arc) => (arc as GlobeTransferArc).toLat}
          arcEndLng={(arc) => (arc as GlobeTransferArc).toLng}
          arcColor={() => [COLORS.arcFrom, COLORS.arcTo]}
          arcStroke={(arc) => 0.18 + Math.min((arc as GlobeTransferArc).transferCount, 200) / 500}
          arcAltitudeAutoScale={0.4}
          arcDashLength={0.4}
          arcDashGap={0.6}
          // The dash animation is the scene's one living element (DESIGN.md §5),
          // and the first thing to stop when the visitor asks for less motion.
          arcDashAnimateTime={reduceMotion ? 0 : 2600}
          arcLabel={arcLabel}
        />
      )}
    </div>
  );
}

export default GlobeCanvas;
