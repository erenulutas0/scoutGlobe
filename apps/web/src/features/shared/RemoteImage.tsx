"use client";

import { useState } from "react";

/**
 * An image hosted by the data source, with a text fallback.
 *
 * Two deliberate choices (ARCHITECTURE.md §4 "Görseller neden URL"):
 *
 * - A plain <img>, not next/image. next/image would route every portrait
 *   through our own optimiser, which turns "the visitor's browser loads a
 *   picture from its source" into "we re-serve someone else's images".
 * - The initials sit underneath the picture rather than replacing it on error,
 *   so a slow or blocked load shows a label instead of an empty circle. The
 *   source can stop serving these at any moment and no screen may depend on a
 *   picture arriving.
 */
export function RemoteImage({
  src,
  alt,
  fallback,
  className = "",
  size = 40,
  rounded = "full",
}: {
  src: string | null | undefined;
  alt: string;
  /** Shown when the image is missing or fails; defaults to initials of `alt`. */
  fallback?: string;
  className?: string;
  size?: number;
  rounded?: "full" | "card";
}) {
  const [failed, setFailed] = useState(false);

  const initials =
    fallback ??
    alt
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("");

  const shape = rounded === "full" ? "rounded-full" : "rounded-lg";

  return (
    <span
      className={`relative flex shrink-0 items-center justify-center overflow-hidden border border-stroke-panel bg-white/4 ${shape} ${className}`}
      style={{ width: size, height: size }}
      title={alt}
    >
      <span
        className="stat text-text-muted select-none"
        style={{ fontSize: Math.max(9, size * 0.32) }}
        aria-hidden
      >
        {initials || "—"}
      </span>

      {src && !failed && (
        /* eslint-disable-next-line @next/next/no-img-element -- see the note above */
        <img
          src={src}
          alt={alt}
          width={size}
          height={size}
          loading="lazy"
          decoding="async"
          // Sources commonly reject requests that carry a foreign referrer.
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
          className="absolute inset-0 h-full w-full bg-panel-solid object-contain"
        />
      )}
    </span>
  );
}
