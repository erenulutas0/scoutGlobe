/**
 * Regenerates packages/core/src/api/schema.ts from the FastAPI OpenAPI document.
 *
 * Two steps, no running server:
 *   1. services/api/scripts/export_openapi.py  -> packages/core/openapi.json
 *   2. openapi-typescript                      -> packages/core/src/api/schema.ts
 *
 * CI runs this and fails if the result differs from what is committed, so the
 * TypeScript contract can never drift away from the Python one.
 */
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const run = (command, args, cwd) =>
  execFileSync(command, args, { cwd: cwd ?? root, stdio: "inherit", shell: process.platform === "win32" });

// Relative paths on purpose: absolute ones break shell quoting when the
// checkout lives under a directory with non-ASCII characters.
run("uv", ["run", "python", "scripts/export_openapi.py"], join(root, "services", "api"));
run("pnpm", [
  "exec",
  "openapi-typescript",
  "packages/core/openapi.json",
  "-o",
  "packages/core/src/api/schema.ts",
]);
