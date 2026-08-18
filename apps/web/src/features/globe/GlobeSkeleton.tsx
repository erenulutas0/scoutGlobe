/** DESIGN.md §7 — loading state is a dark sphere with a mono label, never a spinner. */
export function GlobeSkeleton({ label = "Veri yükleniyor" }: { label?: string }) {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-6">
      <div
        aria-hidden
        className="size-[min(56vmin,420px)] rounded-full border border-stroke-panel"
        style={{
          background:
            "radial-gradient(circle at 38% 32%, rgba(91,140,255,0.16) 0%, rgba(11,20,40,0.95) 55%, rgba(6,11,26,1) 100%)",
        }}
      />
      <p className="stat text-sm tracking-[0.18em] text-text-muted uppercase">{label}</p>
    </div>
  );
}
