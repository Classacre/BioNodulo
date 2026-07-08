# BioNodulo Desktop

Electron desktop app that wraps the open-source [BioNodulo](https://github.com/Classacre/BioNodulo)
Python backend, following the ComfyUI-Desktop architecture: a thin Electron shell
bundles an embedded Python runtime + `uv`, creates a per-user virtual environment
on first run, spawns and supervises the FastAPI backend, and loads the BioNodulo
web UI in a sandboxed Chromium renderer.

The Electron shell is proprietary; the BioNodulo core it wraps is GPL-3.

## Architecture

```
apps/desktop/
  src/
    main/
      index.ts          App lifecycle, window, first-run vs. normal boot,
                        single-instance lock, deep links, graceful shutdown
      ipc.ts            All ipcMain.handle channels (app/settings/python/setup/shell)
      preload.ts        contextBridge -> window.bionoduloAPI (sandboxed, no Node)
      python-process.ts Spawn/supervise backend, health-poll, log ring buffer, SIGTERM+SIGKILL
      python-env.ts     First-run venv creation + dependency install via bundled uv (Tier-2 updates too)
      paths.ts          Dev vs. packaged asset/data path resolution (space-safe)
      portable.ts       Portable-mode detection + data-dir selection
      port.ts           Free-port discovery (loopback)
      updater.ts        electron-updater (Tier-1 shell updates, GitHub feed)
      store.ts          electron-store schema (encrypted at rest)
    renderer/
      first-run.html    Setup wizard (data dir, venv, deps, progress)
      loading.html      Backend-starting splash + live log
      error.html        Backend-failed screen (open logs / retry)
    types/global.d.ts   window.bionoduloAPI typing
  scripts/
    prepare-backend.mjs Stage BioNodulo source -> assets/bionodulo-backend
    prepare-python.mjs  Fetch python-build-standalone + uv -> assets/
    copy-renderer.mjs   Copy renderer HTML into dist/ after tsc
  build/
    installer.nsh       NSIS custom install (deep-link protocol registration)
    entitlements.mac.plist  Hardened-runtime entitlements for child Python process
  assets/               Build-time, gitignored (see assets/README.md)
```

## Python bundling strategy

Two layers, exactly like ComfyUI Desktop:

1. **Bundled tools** (shipped in the installer via `extraResources`):
   - `python-embedded/<os>/` — a standalone Python interpreter
     (python-build-standalone; Windows uses the same install-only build).
   - `uv/<os>/uv[.exe]` — Astral's `uv` for fast, deterministic dependency
     resolution.
   - `bionodulo-backend/` — the BioNodulo Python source + prebuilt `web/dist`.
2. **Per-user virtual environment** (created on first run, NOT shipped):
   - `uv venv <userData>/venv --python <embedded> --seed`
   - `uv pip install -e <backend>` installs BioNodulo and all its deps.

This keeps the installer thin (~tens of MB) while heavy scientific deps land in
the user's data dir on first launch.

## Backend integration notes

The real `main.py` accepts `--host`, `--port`, `--project-root` (the spec's
`--listen`/`--workspace` names do not exist), so the process manager uses those.
The backend serves both its API and the web UI on one port; liveness is probed at
`/api/health` (with `/health` and `/` as fallbacks). The desktop picks a free
port (prefers 8188) and loads `http://127.0.0.1:<port>`.

## Development

```bash
cd apps/desktop
ELECTRON_SKIP_BINARY_DOWNLOAD=1 pnpm install   # types only; skip the Electron binary
pnpm run prepare:assets                         # stage backend + python + uv (needs network)
pnpm run dev                                    # tsc + electron --dev-tools
```

For a UI-only loop without the full Python stack, point the backend at any local
BioNodulo dev server, or stub the health endpoint.

## Building installers

```bash
pnpm run prepare:assets
pnpm run build:win          # NSIS + portable (Windows)
pnpm run build:mac          # DMG + zip (arm64 + x64)
pnpm run build:linux        # AppImage + deb + tar.gz
```

## What runs in CI

`.github/workflows/desktop-release.yml` (repo root) builds on `desktop-v*` tags
across windows-latest / macos-latest (arm64) / macos-13 (x64) / ubuntu-latest:
checks out `Classacre/BioNodulo`, builds its web frontend, stages assets, runs
`electron-builder`, and uploads installers as a **draft** GitHub Release.

Code signing / notarization are wired via env secrets (`WIN_CSC_LINK`,
`MAC_CSC_LINK`, `APPLE_ID`, `APPLE_TEAM_ID`, …) and are optional — unsigned dev
builds work without them. Auto-update feed points at `Classacre/BioNodulo`
releases (override with `BIONODULO_UPDATE_FEED`).

## Updates (two tiers)

- **Tier 1 — shell**: `electron-updater` checks the GitHub Releases feed on
  startup, downloads in the background, prompts to restart. Disabled in portable
  mode.
- **Tier 2 — Python deps**: `python:update-dependencies` IPC re-runs
  `uv pip install --upgrade -e <backend>` in the venv with progress streamed to
  the renderer.

## Portable mode

Detected via `BIONODULO_PORTABLE=1`, `--portable`, a `portable.ini` or `data/`
dir next to the executable, or electron-builder's `PORTABLE_EXECUTABLE_DIR`. In
portable mode all data (venv, workspace, logs, settings) lives in `data/` next to
the binary and the auto-updater is disabled.
