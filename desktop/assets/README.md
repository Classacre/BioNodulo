# Bundled assets

This directory holds large, build-time-staged assets that are NOT committed to
git (see `.gitignore`). Populate them before packaging with:

```bash
npm run prepare:assets   # backend + python + uv for the current OS
```

Layout after staging:

```
assets/
  icons/                      # committed: app icon source/output (see icons/README.md)
  bionodulo-backend/          # staged: BioNodulo Python source (Classacre/BioNodulo)
  python-embedded/<os>/       # staged: python-build-standalone interpreter
  uv/<os>/uv[.exe]            # staged: Astral uv binary
```

- `prepare-backend.mjs` copies the BioNodulo source (from `$BIONODULO_BACKEND_SRC`
  or a sibling `../../../BioNodulo` checkout), excluding venvs/caches/node_modules.
- `prepare-python.mjs` downloads the standalone Python distribution and `uv`
  binary for the current platform from their official GitHub releases.

Heavy Python *dependencies* are intentionally NOT bundled here — they are
installed into a per-user virtual environment on first run via `uv`, keeping the
installer thin (ComfyUI Desktop pattern).
