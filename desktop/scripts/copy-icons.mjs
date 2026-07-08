// Validates the Tauri icon set at src-tauri/icons.
//
// The set (32x32.png, 128x128.png, 128x128@2x.png, icon.icns, icon.ico, ...) is
// generated ONCE from a high-res source via `npm run tauri -- icon <src.png>`
// and committed. This script is a no-op when that set is present. It deliberately
// does NOT copy assets/icons/* over the committed set — doing so would clobber the
// generated icon.png with the raw 1024 source and dirty git on every prepare run.
import { existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const desktopRoot = join(here, "..");
const srcIcons = join(desktopRoot, "assets", "icons");
const dstIcons = join(desktopRoot, "src-tauri", "icons");

const REQUIRED = ["32x32.png", "128x128.png", "128x128@2x.png", "icon.icns", "icon.ico"];

mkdirSync(dstIcons, { recursive: true });

const missing = REQUIRED.filter((f) => !existsSync(join(dstIcons, f)));
if (missing.length > 0) {
  const source = existsSync(join(srcIcons, "icon.png"))
    ? "assets/icons/icon.png"
    : "<path-to-1024x1024-source.png>";
  console.warn(
    `[copy-icons] Missing Tauri icons: ${missing.join(", ")}.\n` +
      `[copy-icons] Generate the full set once with:\n` +
      `    npm run tauri -- icon ${source}\n` +
      `[copy-icons] then commit desktop/src-tauri/icons/.`
  );
} else {
  console.log("[copy-icons] Tauri icon set present.");
}
