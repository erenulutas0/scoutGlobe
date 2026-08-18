"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Globe, { type GlobeMethods } from "react-globe.gl";
import { Color, MeshPhongMaterial } from "three";
import { useCountries, type CountryFeature } from "./use-countries";
import { useGlobeStore } from "./globe-store";

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
} as const;

const TRANSITION_MS = 200; // DESIGN.md §5 — 180-220ms.

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function GlobeCanvas() {
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  const { data } = useCountries();
  const hoveredId = useGlobeStore((state) => state.hoveredId);
  const selectedId = useGlobeStore((state) => state.selectedId);
  const setHovered = useGlobeStore((state) => state.setHovered);
  const setSelected = useGlobeStore((state) => state.setSelected);

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

  const handleHover = useCallback(
    (polygon: object | null) => {
      const country = polygon as CountryFeature | null;
      setHovered(country?.id ?? null);
    },
    [setHovered],
  );

  const handleClick = useCallback(
    (polygon: object) => {
      const country = polygon as CountryFeature;
      const meta = data?.meta[country.id];
      setSelected(country.id);
      if (meta && globeRef.current) {
        globeRef.current.pointOfView(
          { lat: meta.lat, lng: meta.lng, altitude: 1.35 },
          prefersReducedMotion() ? 0 : 700,
        );
      }
    },
    [data, setSelected],
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

  const label = useCallback(
    (polygon: object) => {
      const country = polygon as CountryFeature;
      const meta = data?.meta[country.id];
      const name = meta?.nameTr ?? country.properties.name;
      const code = meta?.code ?? "—";
      return `<div style="
          font-family: var(--font-sans);
          background: rgba(13,20,38,0.86);
          border: 1px solid rgba(148,163,199,0.18);
          border-radius: 10px;
          padding: 6px 10px;
          color: #E9EDF6;
          font-size: 13px;
          backdrop-filter: blur(8px);
        ">${name}
        <span style="font-family: var(--font-mono); color:#8A96B5; margin-left:6px;">${code}</span>
      </div>`;
    },
    [data],
  );

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
          polygonLabel={label}
          polygonsTransitionDuration={TRANSITION_MS}
          onPolygonHover={handleHover}
          onPolygonClick={handleClick}
        />
      )}
    </div>
  );
}

export default GlobeCanvas;
