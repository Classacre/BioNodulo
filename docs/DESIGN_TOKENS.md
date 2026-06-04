# BioNodulo Design Tokens

Authoritative reference for the CSS custom properties used by the BioNodulo
frontend. Tokens are defined by `ALL_PALETTE_TOKENS` and applied by
`applyPalette()` in `web/src/state/palettes.ts`. Components consume them as
`var(--token-name)` in CSS or inline styles.

When styling new UI, use these tokens instead of literal colors. The palette
system in Settings -> Appearance swaps token values; hard-coded colors do not
follow the selected theme.

---

## Token Contract

Every palette token becomes a root CSS custom property with a `--` prefix.
Palette definitions may provide only the core anchors; `completePalette()`
derives the rest with `color-mix()` and alpha blends. Palette authors can still
override any derived token explicitly when a theme needs tighter control.

| Token | Purpose | Derivation notes |
|---|---|---|
| `--canvas` | Infinite workflow background | Core palette anchor |
| `--surface` | Default panel, modal, menu, and card fill | Core palette anchor |
| `--surface-2` | Subtle alternate fill for inputs, hovers, and group bodies | Derived one step from `--surface` when omitted |
| `--surface-3` | Tertiary fill for recessed controls and progress tracks | Derived further from `--surface` when omitted |
| `--surface-overlay` | Translucent overlay surfaces | Alpha blend from `--surface` |
| `--surface-elevated` | Raised popover or floating-panel surface | Slightly lifted from `--surface` |
| `--surface-sunken` | Recessed or embedded surface | Slightly darkened from `--surface` |
| `--surface-disabled` | Disabled surface fill | Alpha blend from `--surface` |
| `--text` | Primary readable text | Core palette anchor |
| `--text-2` | Secondary text and descriptions | Derived from `--text` when omitted |
| `--text-3` | Tertiary text and compact metadata | Derived from `--text` when omitted |
| `--text-muted` | Low-priority captions and placeholders | Derived from `--text` when omitted |
| `--text-inverse` | Text on dark or saturated surfaces | White in light mode, dark canvas in dark mode unless overridden |
| `--text-link` | Link text | Defaults to `--accent` |
| `--border` | Default 1px border | Core palette anchor |
| `--border-2` | Stronger border and separator | Core palette anchor |
| `--border-strong` | High-emphasis border | Derived from `--text` |
| `--border-subtle` | Low-emphasis divider or hairline | Alpha blend from `--text` |
| `--divider` | Standard section divider | Alpha blend from `--text` |
| `--accent` | Primary brand/action color | Core palette anchor |
| `--accent-light` | Light accent tint | Core palette anchor or mixed from `--accent` |
| `--accent-dark` | Dark accent shade | Core palette anchor or mixed from `--accent` |
| `--accent-hover` | Hover color for accent actions | Mixed from `--accent` |
| `--accent-active` | Pressed/active color for accent actions | Mixed from `--accent` |
| `--accent-soft` | Soft accent background | Alpha blend from `--accent` |
| `--accent-soft-2` | Very soft accent background | Lighter alpha blend from `--accent` |
| `--accent-contrast` | Text/icon color on accent backgrounds | Defaults to white |
| `--danger` | Destructive action and error color | Core status anchor |
| `--warning` | Cautionary status color | Core status anchor |
| `--success` | Success/ready status color | Core status anchor |
| `--info` | Informational status color | Core status anchor |
| `--danger-soft` | Soft destructive background | Alpha blend from `--danger` |
| `--warning-soft` | Soft warning background | Alpha blend from `--warning` |
| `--success-soft` | Soft success background | Alpha blend from `--success` |
| `--info-soft` | Soft informational background | Alpha blend from `--info` |
| `--danger-border` | Destructive border | Alpha blend from `--danger` |
| `--warning-border` | Warning border | Alpha blend from `--warning` |
| `--success-border` | Success border | Alpha blend from `--success` |
| `--info-border` | Informational border | Alpha blend from `--info` |
| `--focus-ring` | Keyboard and focus outline | Alpha blend from `--accent` |
| `--focus-ring-soft` | Secondary focus glow | Softer alpha blend from `--accent` |
| `--selection-bg` | Canvas/UI selection fill | Alpha blend from `--accent` |
| `--selection-fg` | Text on selection fill | Defaults to `--text` |
| `--highlight` | Search hit or transient highlight fill | Alpha blend from `--warning` |
| `--minimap-bg` | Minimap background | Core anchor or mode-specific alpha surface |
| `--minimap-fg` | Minimap node/edge foreground | Alpha blend from `--text` |
| `--minimap-mask` | Minimap viewport mask | Alpha blend from `--accent` |
| `--edge-default` | Default canvas edge stroke | Derived from `--text` |
| `--edge-hover` | Hovered edge stroke | Defaults to `--accent` |
| `--edge-selected` | Selected edge stroke | Defaults to `--accent` |
| `--grid-line` | Canvas grid-line color | Alpha blend from `--text` |
| `--grid-dot` | Canvas dot-grid color | Alpha blend from `--text` |
| `--code-bg` | Code block background | Mode-specific fallback |
| `--code-fg` | Code block text | Defaults to `--text` |
| `--code-comment` | Code comment text | Derived from `--text` |
| `--code-keyword` | Code keyword/accent text | Defaults to `--accent` |
| `--backdrop` | Modal and lightbox backdrop | Alpha black |
| `--scrim` | Soft overlay/scrim | Alpha black or dark canvas |
| `--tooltip-bg` | Tooltip background | Mode-specific fallback |
| `--shadow-color` | Standard shadow color | Alpha black |
| `--shadow-color-strong` | Strong/elevated shadow color | Stronger alpha black |
| `--ring-color` | General ring/outline color | Alpha blend from `--accent` |
| `--badge-bg` | Badge background | Alpha blend from `--accent` |
| `--badge-fg` | Badge text/icon color | Defaults to `--accent` |
| `--kbd-bg` | Keyboard shortcut chip background | Derived from `--surface` |
| `--kbd-fg` | Keyboard shortcut chip text | Defaults to `--text` |

---

## Semantic Groups

| Group | Tokens |
|---|---|
| Surfaces | `--canvas`, `--surface`, `--surface-2`, `--surface-3`, `--surface-overlay`, `--surface-elevated`, `--surface-sunken`, `--surface-disabled` |
| Text | `--text`, `--text-2`, `--text-3`, `--text-muted`, `--text-inverse`, `--text-link` |
| Borders and dividers | `--border`, `--border-2`, `--border-strong`, `--border-subtle`, `--divider` |
| Accent | `--accent`, `--accent-light`, `--accent-dark`, `--accent-hover`, `--accent-active`, `--accent-soft`, `--accent-soft-2`, `--accent-contrast` |
| Status | `--danger`, `--warning`, `--success`, `--info`, `--danger-soft`, `--warning-soft`, `--success-soft`, `--info-soft`, `--danger-border`, `--warning-border`, `--success-border`, `--info-border` |
| Focus and selection | `--focus-ring`, `--focus-ring-soft`, `--selection-bg`, `--selection-fg`, `--highlight` |
| Canvas and graph | `--minimap-bg`, `--minimap-fg`, `--minimap-mask`, `--edge-default`, `--edge-hover`, `--edge-selected`, `--grid-line`, `--grid-dot` |
| Code and mono | `--code-bg`, `--code-fg`, `--code-comment`, `--code-keyword` |
| Overlay | `--backdrop`, `--scrim`, `--tooltip-bg` |
| Shadows and rings | `--shadow-color`, `--shadow-color-strong`, `--ring-color` |
| Small controls | `--badge-bg`, `--badge-fg`, `--kbd-bg`, `--kbd-fg` |

---

## Canvas Pattern Dataset

The active palette also sets `document.documentElement.dataset.canvasPattern`,
which CSS selectors target via
`html[data-canvas-pattern="..."] .workflow-canvas-host`.

Valid values:

| Value | Meaning |
|---|---|
| `none` | Flat canvas, no overlay |
| `dots` | Dot grid |
| `grid` | Square grid lines |
| `mesh` | Irregular interlocking lines |

Built-in mappings:

| Palette | Pattern |
|---|---|
| BioNodulo (`bionodulo`) | `dots` |
| Clinical (`clinical`) | `grid` |
| Field Station (`field`) | `mesh` |
| High Contrast (`contrast`) | `grid` |

---

## Defining A New Palette

A `ThemePalette` lives in `web/src/state/palettes.ts`. The shape is:

```ts
interface ThemePalette {
  id: string;
  name: string;
  description: string;
  preview: string[];
  light: PaletteTokens;
  dark: PaletteTokens;
  canvasPattern?: 'none' | 'dots' | 'grid' | 'mesh';
}
```

`light` and `dark` use token names without the `--` prefix:

```json
{
  "id": "lab",
  "name": "Lab",
  "description": "Neutral lab workstation palette.",
  "preview": ["#0d9488", "#ffffff", "#1d2930"],
  "canvasPattern": "dots",
  "light": {
    "canvas": "#eef3f4",
    "surface": "#ffffff",
    "text": "#1d2930",
    "border": "#d9e1e5",
    "accent": "#0d9488",
    "danger": "#dc2626",
    "warning": "#f59e0b",
    "success": "#16a34a",
    "info": "#2563eb"
  },
  "dark": {
    "canvas": "#0f172a",
    "surface": "#1e293b",
    "text": "#f1f5f9",
    "border": "#475569",
    "accent": "#2dd4bf",
    "danger": "#f87171",
    "warning": "#fbbf24",
    "success": "#4ade80",
    "info": "#60a5fa"
  }
}
```

Custom palettes can be imported through Settings -> Appearance -> Import
Palette as JSON matching this shape.

---

## Z-Index Ladder

BioNodulo does not have z-index tokens yet. Reuse these bands for predictable
stacking:

| z-index | Layer |
|---|---|
| 50 | Workflow stats overlay, hardware monitor, canvas chrome |
| 90 | Inline node-rename input |
| 100 | Context menus |
| 150 | Floating panels and in-canvas info panels |
| 200 | Focus-mode exit pill |
| 300+ | Modal overlay base; `Dialog` increments from here |
| 400 | Image lightbox |

---

## Spacing And Sizing Conventions

These are conventions, not tokens:

| Surface | Convention |
|---|---|
| Compact card padding | `12px 16px` |
| Modal header/footer padding | `16px 20px` |
| Input border radius | `4px` |
| Card border radius | `6px` to `8px` |
| Modal border radius | `12px` |
| Pill border radius | `999px` |
| Caption font size | `10px` |
| Panel row/chip font size | `11px` |
| Default body font size | `12px` |
| Panel title font size | `13px` to `14px` |

If spacing tokens are introduced later, update this section to point to the new
token source and add them to the documentation sync test.
