// Stage the BioNodulo Python backend into assets/bionodulo-backend so Tauri can
// bundle it as a resource.
//
// The desktop app lives at <BioNodulo>/desktop, so the backend is the repo root.
// Source resolution order:
//   1. $BIONODULO_BACKEND_SRC  (explicit path; CI sets this to the repo root)
//   2. ..                       (the parent BioNodulo repo)
//
// Copy only the runtime files listed in backend-files.mjs.
import { access } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { stageBackend } from "./backend-files.mjs";

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

const src = await resolveSource();
if (!src || !existsSync(src)) {
  console.error(
    "[prepare-backend] BioNodulo source not found.\n" +
      "  Set BIONODULO_BACKEND_SRC or use the desktop directory inside the BioNodulo checkout."
  );
  process.exit(1);
}

console.log(`[prepare-backend] source: ${src}`);
const assetsRoot = path.resolve(root, "assets");
await stageBackend(src, dest, assetsRoot);
console.log(`[prepare-backend] staged backend -> ${dest}`);
