# BioNodulo Design Tokens

Authoritative reference for the CSS custom properties used throughout the
BioNodulo frontend. Tokens are applied to the document root in `applyPalette()`
(`web/src/state/palettes.ts`) and consumed via `var(--name)` in `index.css`
and inline styles.

If you're styling something new: **use a token, not a literal**. The palette
system (Settings → Appearance → Palette) only swaps tokens — anything hard-
coded won't follow the theme.

---

## Core surface tokens

| Token | Purpose | Notes |
|---|---|---|
| `--canvas` | The infinite workflow background | Drawn by `.litegraph-host`; canvas patterns layer on top |
| `--surface` | Panels, modals, tooltips | The default "card" colour |
| `--surface-2` | Subtle alternate fill (input backgrounds, hover state, group bodies) | One step away from `--surface` toward `--canvas` |
| `--surface-3` | Tertiary fill (progress bar tracks, recessed pills) | One step further than `--surface-2` |

## Text

| Token | Purpose |
|---|---|
| `--text` | Primary body text |
| `--text-2` | Secondary paragraph text — descriptions, longer copy |
| `--muted` | Captions, placeholder text, low-priority metadata |

## Structure

| Token | Purpose |
|---|---|
| `--border` | Default 1px borders everywhere (modals, inputs, cards) |
| `--border-2` | Stronger border for emphasised separators |

## Accent / brand

| Token | Purpose | Where it shows |
|---|---|---|
| `--accent` | Primary brand colour | Primary buttons, focused inputs, selection chrome, link colour |
| `--accent-light` | Soft accent tint | Used as backdrop on accent chips and badges |
| `--accent-dark` | Strong accent variant | Hover state for accent surfaces, wiki section titles |

## Status

| Token | Purpose | Default |
|---|---|---|
| `--danger` | Destructive actions, error states | Red |
| `--warning` | Cautionary states | Amber |
| `--success` | Successful execution, OK chips | Green |

## Minimap

| Token | Purpose |
|---|---|
| `--minimap-bg` | Minimap container background (already alpha-blended) |

---

## Canvas pattern dataset

The active palette also sets `document.documentElement.dataset.canvasPattern`,
which CSS selectors target via `html[data-canvas-pattern="…"] .litegraph-host`.
Valid values:

- `none` — flat canvas (no overlay)
- `dots` — light dot grid
- `grid` — square grid lines
- `mesh` — irregular interlocking lines

`applyPalette()` reads `palette.canvasPattern` from the active `ThemePalette`
and writes the dataset attribute. Built-in mappings:

| Palette | Pattern |
|---|---|
| BioNodulo (`bionodulo`) | `dots` |
| Clinical (`clinical`) | `grid` |
| Field (`field`) | `mesh` |
| Contrast (`contrast`) | `none` |

---

## Defining a new palette

A `ThemePalette` lives in `web/src/state/palettes.ts`. The shape is:

```ts
interface ThemePalette {
  id: string;
  name: string;
  description?: string;
  preview: [string, string, string];   // 3-swatch preview shown in Settings
  canvasPattern?: 'none' | 'dots' | 'grid' | 'mesh';
  light: PaletteTokens;
  dark: PaletteTokens;
}
```

Every key in `PaletteTokens` is a CSS custom property name (without the `--`
prefix). The fields above are required for full coverage — omitting one
falls back to the previous palette's value, which usually clashes.

Custom palettes can also be imported via Settings → Appearance →
Import Palette as a JSON file matching the same shape.

---

## Z-index ladder

BioNodulo doesn't have z-index tokens, but the rough scale is:

| z-index | Layer |
|---|---|
| 50 | Workflow stats overlay, hardware monitor (canvas chrome) |
| 90 | Inline node-rename input |
| 100 | Context menus |
| 150 | Floating panels, in-canvas info panels |
| 200 | Focus-mode exit pill |
| 300+ | Modal overlay base (`Dialog` ladders up from here) |
| 400 | Image lightbox |

Reuse these bands when adding new overlays so stacking is predictable.

---

## Spacing & sizing conventions

These aren't tokens (yet) — but the codebase is fairly consistent:

- Card padding: `12px 16px` for compact, `16px 20px` for modal headers/footers.
- Border radius: `4px` for inputs, `6-8px` for cards, `12px` for modals, `999px` for pills.
- Font size scale: `10px` (captions / pills), `11px` (panel rows / chips),
  `12px` (default body), `13-14px` (panel titles), `16px+` (modal H3+).

If a future wave introduces spacing tokens (eg `--space-2`, `--space-4`),
update this section to point to them.
