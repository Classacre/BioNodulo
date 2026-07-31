# BioNodulo Desktop

Tauri 2 desktop app that wraps the [BioNodulo](https://github.com/Classacre/BioNodulo)
Python backend: a native Rust shell bundles a standalone Python runtime + `uv`,
creates a per-user virtual environment on first run, spawns and supervises the
FastAPI backend, and loads the BioNodulo web UI from the system webview.

Licensed under the BioNodulo Closed Alpha Commercial License (see `LICENSE` at
the repository root).

## Architecture

```
desktop/
  src-tauri/
    src/
      main.rs         Binary entry; suppresses the extra console window on Windows
      lib.rs          App builder, plugin registration (updater, deep-link), setup
      commands.rs     #[tauri::command] handlers exposed to the frontend
      supervisor.rs   Spawn/supervise the backend, health-poll, shutdown
      provision.rs    First-run venv creation + dependency install via bundled uv
      paths.rs        Dev vs. bundled asset/data path resolution
      port.rs         Free-port discovery on loopback (prefers 8188)
      settings.rs     Persisted app settings
      deeplink.rs     bionodulo:// deep-link handling
      security.rs     URL/navigation allowlisting for the webview
    tauri.conf.json   Bundle targets, updater endpoint + pubkey, macOS hardening
  frontend/           Plain HTML/JS shell screens (no framework, no bundler)
    first-run.html    Setup wizard (venv creation, dependency install, progress)
    loading.html      Backend-starting splash + live log
    error.html        Backend-failed screen
  scripts/
    prepare-backend.mjs     Stage BioNodulo source -> assets/bionodulo-backend
    prepare-python.mjs      Fetch python-build-standalone + uv -> assets/
    prepare-cloudflared.mjs Fetch cloudflared (share/collaboration tunnel)
    copy-icons.mjs          Stage app icons
  build/
    entitlements.mac.plist  Hardened-runtime entitlements for the child Python process
  assets/             Build-time, gitignored (see assets/README.md)
```

## Python bundling strategy

Two layers:

1. **Bundled tools** (shipped in the installer as Tauri `resources`):
   - a standalone Python interpreter (python-build-standalone), used only to
     bootstrap the virtual environment;
   - `uv` for fast, deterministic dependency resolution;
   - `bionodulo-backend/` — the BioNodulo Python source + prebuilt `web/dist`;
   - `cloudflared` — used by the share/collaboration tunnel.
2. **Per-user virtual environment**, created on first run and *not* shipped.
   `provision.rs` drives this and streams progress to the first-run screen.

This keeps the installer small while the heavy scientific dependencies land in
the user's data directory on first launch.

## Backend integration notes

`main.py` accepts `--host`, `--port` and `--project-root`. The backend serves
both its API and the web UI on one port. The shell picks a free loopback port
(preferring 8188), loads `http://127.0.0.1:<port>`, and probes `/api/health`
until the backend is live, with a 60 s overall budget and a 2 s per-request
timeout.

## Development

```bash
cd desktop
npm install               # @tauri-apps/cli + cross-env
npm run prepare:assets    # stage backend + python + uv + cloudflared (needs network)
npm run tauri:dev         # BIONODULO_DEV=1 tauri dev
```

Linux additionally needs the WebKitGTK development packages — see the
`Install Linux webview deps` step in `.github/workflows/desktop-release.yml` for
the exact list.

## Building installers

```bash
npm run prepare:assets
npm run tauri:build
```

Bundle targets are declared in `tauri.conf.json`: `nsis` (Windows), `app` and
`dmg` (macOS), `appimage` and `deb` (Linux).

## What runs in CI

`.github/workflows/desktop-release.yml` triggers on `desktop-v*` tags. It builds
the web SPA once on Linux, then runs `tauri-apps/tauri-action` across
macOS (aarch64 + x86_64), Windows and Linux, and publishes the installers as a
GitHub Release.

**Signing status:**

- **macOS** is signed and notarized, using the `APPLE_CERTIFICATE`,
  `APPLE_CERTIFICATE_PASSWORD`, `APPLE_SIGNING_IDENTITY`, `APPLE_ID`,
  `APPLE_PASSWORD` and `APPLE_TEAM_ID` repository secrets. All six must be
  present — `tauri-action` treats an empty `APPLE_CERTIFICATE` as "import this
  certificate" and fails, so there is no partial mode.
- **Windows is unsigned.** No code-signing certificate has been purchased, so
  installers trip SmartScreen. This is a known, deliberate gap.

## Updates

`tauri-plugin-updater` checks the endpoint configured in `tauri.conf.json`
(`releases/latest/download/latest.json`) against a static, minisign-signed
manifest. Update artifacts are produced because `createUpdaterArtifacts` is
enabled.

The release workflow publishes with `releaseDraft: false` and
`prerelease: false`, and **both matter**: GitHub's `/releases/latest` resolves to
the most recent release that is neither a draft nor a prerelease, so marking a
release as either makes it invisible to the updater. Alpha status is carried by
the tag name (`desktop-v0.1.0-alpha.N`), not by the prerelease flag. Do not
change either flag without first moving the updater endpoint off
`/releases/latest`.

Python-side updates are handled separately by re-running the dependency install
in the per-user venv.
