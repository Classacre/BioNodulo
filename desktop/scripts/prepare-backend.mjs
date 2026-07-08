// Stage the BioNodulo Python backend into assets/bionodulo-backend so Tauri can
// bundle it as a resource.
//
// The desktop app lives at <BioNodulo>/desktop, so the backend is the repo root.
// Source resolution order:
//   1. $BIONODULO_BACKEND_SRC  (explicit path; CI sets this to the repo root)
//   2. ..                       (the parent BioNodulo repo)
//
// Copies the runnable subset — excluding venvs, caches, node_modules, the
// desktop/ dir itself (would recurse), and runtime output/ — into assets/.
import { cp, mkdir, rm, access, readdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const dest = path.join(root, "assets", "bionodulo-backend");

async function resolveSource() {
  const explicit = process.env.BIONODULO_BACKEND_SRC;
  if (explicit) return explicit;
  // The desktop app lives at <BioNodulo>/desktop, so the backend is the repo root.
  const repoRoot = path.resolve(root, "..");
  try {
    await access(path.join(repoRoot, "main.py"));
    return repoRoot;
  } catch {
    return null;
  }
}

const EXCLUDE = new Set([
  ".git", ".venv", "venv", ".pixi", "__pycache__", ".pytest_cache",
  "node_modules", "release", "dist-electron",
  "desktop", "output",
]);

function filter(source) {
  const base = path.basename(source);
  if (EXCLUDE.has(base)) return false;
  if (base.endsWith(".pyc")) return false;
  // Skip the frontend's own node_modules but keep web/dist (prebuilt UI).
  if (source.includes(`${path.sep}web${path.sep}node_modules`)) return false;
  return true;
}

const src = await resolveSource();
if (!src || !existsSync(src)) {
  console.error(
    "[prepare-backend] BioNodulo source not found.\n" +
      "  Set BIONODULO_BACKEND_SRC or check out Classacre/BioNodulo as a sibling directory."
  );
  process.exit(1);
}

console.log(`[prepare-backend] source: ${src}`);
await rm(dest, { recursive: true, force: true });
await mkdir(dest, { recursive: true });
// Copy each top-level entry except excluded ones. We cannot fs.cp the repo root
// as a whole: dest (desktop/assets/bionodulo-backend) is a subdirectory of it,
// and Node rejects copying a directory into a subdirectory of itself. Skipping
// EXCLUDE (which includes desktop/ and output/) at the top level avoids that.
for (const entry of await readdir(src)) {
  if (EXCLUDE.has(entry)) continue;
  await cp(path.join(src, entry), path.join(dest, entry), { recursive: true, filter });
}
console.log(`[prepare-backend] staged backend -> ${dest}`);

// Warn (don't fail) if the prebuilt frontend is missing — the backend serves it.
if (!existsSync(path.join(dest, "web", "dist", "index.html"))) {
  console.warn(
    "[prepare-backend] WARNING: web/dist/index.html missing. " +
      "Run `cd web && npm ci && npm run build` in the BioNodulo checkout before packaging."
  );
}
