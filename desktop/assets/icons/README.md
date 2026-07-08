# App icons

electron-builder expects these icon files here at package time:

- `icon.icns` — macOS (1024×1024 source)
- `icon.ico` — Windows (multi-resolution: 16–256px)
- `icon.png` — Linux (512×512); electron-builder reads `assets/icons/` for the
  Linux target and auto-generates the icon set.

These binaries are not committed. Generate them from the brand source SVG with
`electron-icon-builder` (or any icon toolchain) before a signed release build.
Builds will still run for unsigned/dev artifacts using Electron's default icon.
