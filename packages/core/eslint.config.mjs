import base from "@scoutglobe/config/eslint/base";

export default [
  ...base,
  {
    files: ["src/**/*.ts"],
    languageOptions: {
      // packages/core is platform-agnostic: no DOM globals allowed here.
      globals: { fetch: "readonly", AbortSignal: "readonly", console: "readonly" },
    },
    rules: {
      "no-restricted-globals": [
        "error",
        { name: "window", message: "packages/core must stay platform-agnostic (mobile-ready)." },
        { name: "document", message: "packages/core must stay platform-agnostic (mobile-ready)." },
        { name: "localStorage", message: "packages/core must stay platform-agnostic (mobile-ready)." },
      ],
    },
  },
];
