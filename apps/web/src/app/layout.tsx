import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Instrument_Sans } from "next/font/google";
import { CommandPaletteHost } from "@/features/shell/CommandPalette";
import { ShortlistBar } from "@/features/shortlist/ShortlistBar";
import { Providers } from "./providers";
import "./globals.css";

const instrumentSans = Instrument_Sans({
  subsets: ["latin", "latin-ext"],
  variable: "--font-instrument-sans",
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600"],
  variable: "--font-ibm-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ScoutGlobe — Dünyayı tara, oyuncuyu bul",
  description:
    "Dünya liglerini uzaydan tara; kulüp ihtiyacına göre transfer önerisi ve yükselen oyuncu keşfi.",
};

export const viewport: Viewport = {
  themeColor: "#060B1A",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr" className={`${instrumentSans.variable} ${ibmPlexMono.variable}`}>
      <head>
        {/* Display font (Clash Display) is served by Fontshare — see docs/DESIGN.md §3. */}
        <link rel="preconnect" href="https://api.fontshare.com" crossOrigin="anonymous" />
        <link
          href="https://api.fontshare.com/v2/css?f[]=clash-display@500,600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased">
        <Providers>
          {children}
          <CommandPaletteHost />
          <ShortlistBar />
        </Providers>
      </body>
    </html>
  );
}
