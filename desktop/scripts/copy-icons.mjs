// Ensures the Tauri icon set exists at src-tauri/icons.
//
// Tauri's bundler expects a specific icon set (32x32.png, 128x128.png,
// 128x128@2x.png, icon.icns, icon.ico). The canonical way to produce it is
// `pnpm tauri icon <source.png>`, which generates every platform variant from a
// single high-res PNG. This script copies any already-generated icons from
// assets/icons into src-tauri/icons and, if the required set is incomplete,
// prints the one command needed to generate it.
import { existsSync, mkdirSync, readdirSync, copyFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const desktopRoot = join(here, "..");
const srcIcons = join(desktopRoot, "assets", "icons");
const dstIcons = join(desktopRoot, "src-tauri", "icons");

const REQUIRED = ["32x32.png", "128x128.png", "128x128@2x.png", "icon.icns", "icon.ico"];

mkdirSync(dstIcons, { recursive: true });

if (existsSync(srcIcons)) {
  for (const f of readdirSync(srcIcons)) {
    const from = join(srcIcons, f);
    const to = join(dstIcons, f);
    try {
      copyFileSync(from, to);
    } catch {
      /* skip directories / unreadable entries */
    }
  }
}

const missing = REQUIRED.filter((f) => !existsSync(join(dstIcons, f)));
if (missing.length > 0) {
  const source = existsSync(join(srcIcons, "icon.png"))
    ? "assets/icons/icon.png"
    : "<path-to-1024x1024-source.png>";
  console.warn(
    `[copy-icons] Missing Tauri icons: ${missing.join(", ")}.\n` +
      `[copy-icons] Generate the full set once with:\n` +
      `    pnpm --filter @bionodulo/desktop tauri icon ${source}\n` +
      `[copy-icons] then commit apps/desktop/src-tauri/icons/.`
  );
} else {
  console.log("[copy-icons] Tauri icon set present.");
}
