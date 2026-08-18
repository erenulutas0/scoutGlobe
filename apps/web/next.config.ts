import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // packages/core ships TypeScript source (no build step) — Next transpiles it.
  transpilePackages: ["@scoutglobe/core"],
};

export default nextConfig;
