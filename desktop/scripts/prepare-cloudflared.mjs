// Fetch the cloudflared binary for the current OS into assets/cloudflared/<os>/,
// mirroring the uv fetch in prepare-python.mjs.
//
//   assets/cloudflared/<os>/cloudflared[.exe]
//
// Run once per build machine before tauri build. Idempotent.
import { mkdir, rm, chmod, copyFile } from "node:fs/promises";
import { existsSync, createWriteStream } from "node:fs";
import { spawn } from "node:child_process";
import path from "node:path";
import os from "node:os";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");

const CLOUDFLARED_VERSION =
  process.env.BIONODULO_CLOUDFLARED_VERSION || "2024.12.2";

function osKey() {
  if (process.platform === "win32") return "windows";
  if (process.platform === "darwin") return "macos";
  return "linux";
}

function arch() {
  return process.arch === "arm64" ? "arm64" : "x64";
}

function cloudflaredAsset() {
  const a = arch();
  switch (process.platform) {
    case "win32":
      return {
        url: a === "arm64" ? "cloudflared-windows-arm64.exe" : "cloudflared-windows-amd64.exe",
        bin: "cloudflared.exe",
        extract: false,
      };
    case "darwin":
      return {
        url: a === "arm64" ? "cloudflared-darwin-arm64.tgz" : "cloudflared-darwin-amd64.tgz",
        bin: "cloudflared",
        extract: true,
      };
    default:
      return {
        url: a === "arm64" ? "cloudflared-linux-arm64" : "cloudflared-linux-amd64",
        bin: "cloudflared",
        extract: false,
      };
  }
}

async function download(url, dest) {
  console.log(`[prepare-cloudflared] downloading ${url}`);
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

async function findFile(dir, name) {
  const { readdir } = await import("node:fs/promises");
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

async function prepareCloudflared() {
  const { url, bin, extract: needsExtract } = cloudflaredAsset();
  const destDir = path.join(root, "assets", "cloudflared", osKey());
  const destBin = path.join(destDir, bin);

  if (existsSync(destBin)) {
    console.log(`[prepare-cloudflared] cloudflared already present for ${osKey()}`);
    return;
  }

  const releaseUrl = `https://github.com/cloudflare/cloudflared/releases/download/${CLOUDFLARED_VERSION}/${url}`;
  const tmp = path.join(os.tmpdir(), `cloudflared-${Date.now()}-${url}`);
  await download(releaseUrl, tmp);

  await mkdir(destDir, { recursive: true });

  if (needsExtract) {
    const extractDir = path.join(os.tmpdir(), `cloudflared-extract-${Date.now()}`);
    await extract(tmp, extractDir);
    const found = await findFile(extractDir, bin);
    if (!found) throw new Error(`cloudflared binary not found after extracting ${url}`);
    await copyFile(found, destBin);
    await rm(extractDir, { recursive: true, force: true });
  } else {
    await copyFile(tmp, destBin);
  }

  if (process.platform !== "win32") await chmod(destBin, 0o755);
  await rm(tmp, { force: true });
  console.log(`[prepare-cloudflared] staged cloudflared -> ${destBin}`);
}

try {
  await prepareCloudflared();
  console.log("[prepare-cloudflared] done.");
} catch (err) {
  console.error("[prepare-cloudflared] FAILED:", err.message);
  console.error(
    "  cloudflared is required for collab tunnels. In CI ensure network access to GitHub releases."
  );
  process.exit(1);
}
