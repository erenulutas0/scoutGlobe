import base from "@scoutglobe/config/eslint/base";
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const config = [
  { ignores: [".next/**", "next-env.d.ts"] },
  ...base,
  ...nextCoreWebVitals,
  ...nextTypescript,
];

export default config;
