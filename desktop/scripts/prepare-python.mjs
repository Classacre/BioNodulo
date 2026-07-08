// Fetch the embedded/standalone Python distribution and the `uv` binary for the
// current OS into assets/, mirroring ComfyUI Desktop's bundled-tools layout:
//
//   assets/uv/<os>/uv[.exe]
//   assets/python-embedded/<os>/...   (python-build-standalone, or win-embeddable)
//
// Heavy Python *dependencies* are NOT bundled — they're installed at first run
// into a per-user venv via uv (keeps the installer ~thin, ComfyUI pattern).
//
// Run this once per build machine before electron-builder. Idempotent.
import { mkdir, rm, chmod, rename, readdir } from "node:fs/promises";
import { existsSync, createWriteStream } from "node:fs";
import { spawn } from "node:child_process";
import path from "node:path";
import os from "node:os";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");

const PY_VERSION = process.env.BIONODULO_PY_VERSION || "3.12.8";
const UV_VERSION = process.env.BIONODULO_UV_VERSION || "0.5.11";
// python-build-standalone release tag matching the Python version above.
const PBS_TAG = process.env.BIONODULO_PBS_TAG || "20241219";

function osKey() {
  if (process.platform === "win32") return "windows";
  if (process.platform === "darwin") return "macos";
  return "linux";
}

function arch() {
  return process.arch === "arm64" ? "arm64" : "x64";
}

// --- uv ---------------------------------------------------------------------
function uvAsset() {
  const a = arch();
  switch (process.platform) {
    case "win32":
      return { url: `uv-${a === "arm64" ? "aarch64" : "x86_64"}-pc-windows-msvc.zip`, bin: "uv.exe" };
    case "darwin":
      return { url: `uv-${a === "arm64" ? "aarch64" : "x86_64"}-apple-darwin.tar.gz`, bin: "uv" };
    default:
      return { url: `uv-${a === "arm64" ? "aarch64" : "x86_64"}-unknown-linux-gnu.tar.gz`, bin: "uv" };
  }
}

// --- python-build-standalone -------------------------------------------------
function pythonAsset() {
  const a = arch();
  const base = `cpython-${PY_VERSION}+${PBS_TAG}`;
  switch (process.platform) {
    case "win32":
      return `${base}-${a === "arm64" ? "aarch64" : "x86_64"}-pc-windows-msvc-install_only.tar.gz`;
    case "darwin":
      return `${base}-${a === "arm64" ? "aarch64" : "x86_64"}-apple-darwin-install_only.tar.gz`;
    default:
      return `${base}-${a === "arm64" ? "aarch64" : "x86_64"}-unknown-linux-gnu-install_only.tar.gz`;
  }
}

async function download(url, dest) {
  console.log(`[prepare-python] downloading ${url}`);
  const res = await fetch(url, { redirect: "follow" });
  if (!res.ok) throw new Error(`download failed ${res.status} for ${url}`);
  await mkdir(path.dirname(dest), { recursive: true });
  const file = createWriteStream(dest);
  const reader = res.body.getReader();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    file.write(Buffer.from(value));
  }
  await new Promise((resolve, reject) => file.end((err) => (err ? reject(err) : resolve())));
}

function runCmd(cmd, args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { cwd, stdio: "inherit" });
    child.on("error", reject);
    child.on("exit", (code) => (code === 0 ? resolve() : reject(new Error(`${cmd} exited ${code}`))));
  });
}

async function extract(archivePath, destDir) {
  await mkdir(destDir, { recursive: true });
  if (archivePath.endsWith(".zip")) {
    if (process.platform === "win32") {
      await runCmd("powershell", [
        "-NoProfile",
        "-Command",
        `Expand-Archive -Force -LiteralPath '${archivePath}' -DestinationPath '${destDir}'`,
      ]);
    } else {
      await runCmd("unzip", ["-o", archivePath, "-d", destDir]);
    }
  } else {
    await runCmd("tar", ["-xzf", archivePath, "-C", destDir]);
  }
}

async function prepareUv() {
  const { url, bin } = uvAsset();
  const destDir = path.join(root, "assets", "uv", osKey());
  if (existsSync(path.join(destDir, bin))) {
    console.log(`[prepare-python] uv already present for ${osKey()}`);
    return;
  }
  const tmp = path.join(os.tmpdir(), `uv-${Date.now()}-${url}`);
  await download(`https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/${url}`, tmp);
  const extractDir = path.join(os.tmpdir(), `uv-extract-${Date.now()}`);
  await extract(tmp, extractDir);

  // Archives may nest the binary one directory deep; find it.
  const found = await findFile(extractDir, bin);
  if (!found) throw new Error(`uv binary not found after extracting ${url}`);
  await mkdir(destDir, { recursive: true });
  await rename(found, path.join(destDir, bin));
  if (process.platform !== "win32") await chmod(path.join(destDir, bin), 0o755);
  await rm(tmp, { force: true });
  await rm(extractDir, { recursive: true, force: true });
  console.log(`[prepare-python] staged uv -> ${path.join(destDir, bin)}`);
}

async function preparePython() {
  const asset = pythonAsset();
  const destDir = path.join(root, "assets", "python-embedded", osKey());
  if (existsSync(destDir) && (await readdir(destDir).catch(() => [])).length > 0) {
    console.log(`[prepare-python] python-embedded already present for ${osKey()}`);
    return;
  }
  const tmp = path.join(os.tmpdir(), `py-${Date.now()}.tar.gz`);
  await download(
    `https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/${asset}`,
    tmp
  );
  await mkdir(destDir, { recursive: true });
  // install_only archives extract a top-level `python/` dir; flatten it.
  const extractDir = path.join(os.tmpdir(), `py-extract-${Date.now()}`);
  await extract(tmp, extractDir);
  const inner = path.join(extractDir, "python");
  await cpDir(existsSync(inner) ? inner : extractDir, destDir);
  await rm(tmp, { force: true });
  await rm(extractDir, { recursive: true, force: true });
  await pruneUnused(destDir);
  await slimNativeLibs(destDir);
  console.log(`[prepare-python] staged python-embedded -> ${destDir}`);
}

// The install_only distribution ships an UNSTRIPPED libpython (~200MB), and our
// dereferencing copy (cpDir) duplicates the bare linker stub (libpython3.12.so ==
// libpython3.12.so.1.0). Runtime needs only the versioned soname, stripped.
// Unix-only + best-effort: failures never abort the build. (~470MB -> ~75MB.)
async function slimNativeLibs(destDir) {
  if (process.platform === "win32") return; // Windows uses pythonNNN.dll, no bloat
  // 1. Drop bare linker stubs duplicated by dereferencing (keep versioned soname).
  const libDir = path.join(destDir, "lib");
  try {
    for (const name of await readdir(libDir)) {
      if (/^libpython[0-9.]+\.so$/.test(name) && existsSync(path.join(libDir, `${name}.1.0`))) {
        await rm(path.join(libDir, name), { force: true });
      }
    }
  } catch {
    /* lib/ layout differs; skip */
  }
  // 2. Strip debug symbols from every native shared object.
  const stripFlag = process.platform === "darwin" ? "-S" : "--strip-debug";
  const nativeLibs = await findFilesBy(destDir, (n) => /\.(so|dylib)(\.[0-9.]+)?$/.test(n));
  for (const lib of nativeLibs) {
    try {
      await runCmd("strip", [stripFlag, lib]);
    } catch {
      /* not strippable / strip unavailable — best effort */
    }
  }
}

async function findFilesBy(dir, pred) {
  const out = [];
  const entries = await readdir(dir, { withFileTypes: true });
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      out.push(...(await findFilesBy(full, pred)));
    } else if (e.isFile() && pred(e.name)) {
      out.push(full);
    }
  }
  return out;
}

// Subtrees the headless FastAPI backend never needs: GUI toolkits (Tk/Tcl/Tix —
// there is no libtk runtime and no DISPLAY, so tkinter cannot function anyway),
// the curses terminfo DB, dev/legacy tooling (idle, 2to3, lib2to3, turtledemo),
// help() data, and ensurepip (uv `--seed` provides pip from its own wheels).
// Best-effort: paths absent on a given OS layout are skipped (rm force). Covers
// both the linux/macos (`lib/`, lowercase) and Windows (`Lib/`, `tcl/`) layouts.
const PRUNE_UNUSED = [
  // linux / macos layout
  "lib/python3.12/turtledemo",
  "lib/python3.12/idlelib",
  "lib/python3.12/lib2to3",
  "lib/python3.12/tkinter",
  "lib/python3.12/ensurepip",
  "lib/python3.12/pydoc_data",
  "lib/tcl8.6",
  "lib/tcl8",
  "lib/tk8.6",
  "lib/Tix8.4.3",
  "lib/itcl4.2.2",
  "lib/thread2.8.7",
  "share/man",
  "share/terminfo",
  "bin/idle3",
  "bin/idle3.12",
  "bin/2to3",
  "bin/2to3-3.12",
  // Windows layout
  "Lib/turtledemo",
  "Lib/idlelib",
  "Lib/lib2to3",
  "Lib/tkinter",
  "Lib/ensurepip",
  "Lib/pydoc_data",
  "tcl",
];

async function pruneUnused(destDir) {
  for (const rel of PRUNE_UNUSED) {
    await rm(path.join(destDir, rel), { recursive: true, force: true });
  }
}

async function cpDir(src, dest) {
  const { cp } = await import("node:fs/promises");
  // `dereference: true` is REQUIRED. python-build-standalone ships ~1000
  // symlinks (python3 -> python3.12, libpython, pkgconfig, terminfo). Node's
  // fs.cp default rewrites each symlink to its RESOLVED ABSOLUTE path, which
  // points into the temp extraction dir and dangles once that dir is removed —
  // and Tauri's resource bundler refuses to bundle a path that "doesn't exist".
  // Dereferencing copies real file content, producing a symlink-free tree.
  await cp(src, dest, { recursive: true, dereference: true });
}

async function findFile(dir, name) {
  const entries = await readdir(dir, { withFileTypes: true });
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      const found = await findFile(full, name);
      if (found) return found;
    } else if (e.name === name) {
      return full;
    }
  }
  return null;
}

try {
  await prepareUv();
  await preparePython();
  console.log("[prepare-python] done.");
} catch (err) {
  console.error("[prepare-python] FAILED:", err.message);
  console.error(
    "  These assets are required for packaging. In CI ensure network access to GitHub releases."
  );
  process.exit(1);
}
