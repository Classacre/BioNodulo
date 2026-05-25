"""Re-layout template workflows and emit thumbnail PNGs with embedded workflow.

Each `templates/*.json` is re-laid-out into columns by topological depth, then
rendered as a 640x400 thumbnail. The original JSON is embedded into the PNG via
the BioNodulo tEXt chunk used everywhere else in the codebase, so the thumbnail
itself can be drag-and-dropped to load the workflow.

Usage:
    python scripts/relayout_templates.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"

# Sync with web/src/components/canvas/LiteGraphCanvas.tsx constants so the
# laid-out positions render cleanly in the browser canvas.
NODE_WIDTH = 220
NODE_HEADER_H = 32
NODE_PIN_H = 18
WIDGET_ROW_H = 24
WIDGET_BLOCK_PAD = 8
COL_GAP = 360  # column-to-column distance in workflow space
ROW_GAP = 60   # vertical gap between stacked nodes in the same column
ORIGIN_X = 80
ORIGIN_Y = 80

sys.path.insert(0, str(REPO_ROOT))
from bionodulo.provenance.workflow_embed import _embed_in_png  # noqa: E402
from bionodulo.nodes.registry import NodeRegistry  # noqa: E402


# Build the same node registry the API uses so we can read each node's
# input_types and return_types, which drive the real rendered height.
_registry = NodeRegistry.create_isolated()
try:
    _registry.load_builtin_nodes()
except Exception as exc:  # pragma: no cover - best-effort
    print(f"warning: could not load builtin nodes: {exc}", file=sys.stderr)
_OBJECT_INFO: dict[str, dict[str, Any]] = _registry.object_info() if _registry else {}

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - dev tooling
    print(f"Pillow is required: {exc}", file=sys.stderr)
    sys.exit(1)


def is_note(node: dict[str, Any]) -> bool:
    return node.get("type") == "note"


def is_reroute(node: dict[str, Any]) -> bool:
    return node.get("type") == "reroute"


def _is_interactive_spec(spec: Any) -> bool:
    """Mirror isInteractiveWidgetSpec in LiteGraphCanvas.tsx so heights match the UI.

    The registry returns ComfyUI v3-style specs as ``(type, options_dict)``
    tuples; the frontend normalizes those into flat dicts. We accept both.
    """
    type_name: Any
    options: Any
    force_input = False
    if isinstance(spec, (list, tuple)):
        if not spec:
            return False
        type_name = spec[0]
        if isinstance(type_name, (list, tuple)) and type_name:
            # ComfyUI represents an option-list type as the list of options itself.
            options = list(type_name)
            type_name = "STRING"
        else:
            options = None
        config = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
        if options is None:
            options = config.get("options")
        force_input = bool(config.get("forceInput"))
    elif isinstance(spec, dict):
        type_name = spec.get("type")
        if isinstance(type_name, (list, tuple)) and type_name:
            options = list(type_name)
            type_name = "STRING"
        else:
            options = spec.get("options")
        force_input = bool(spec.get("forceInput"))
    else:
        return False

    if type_name == "BOOLEAN":
        return True
    if isinstance(options, (list, tuple)) and len(options) > 0:
        return True
    if type_name in ("INT", "FLOAT"):
        return True
    if type_name == "STRING" and not force_input:
        return True
    return False


def _node_meta(node_type: str) -> dict[str, Any]:
    """Return a frontend-shaped metadata dict for a node type."""
    raw = _OBJECT_INFO.get(node_type) or {}
    if "input_types" in raw:
        return raw
    inputs = raw.get("input") or {}
    return {
        "id": raw.get("name") or node_type,
        "description": raw.get("description"),
        "input_types": {
            "required": (inputs.get("required") or {}),
            "optional": (inputs.get("optional") or {}),
        },
        "return_types": list(raw.get("output") or []),
    }


def estimate_node_height(node: dict[str, Any]) -> int:
    """Mirror calcNodeHeight in LiteGraphCanvas.tsx for the laid-out positions."""
    if is_reroute(node):
        return 20
    if is_note(node):
        text = str((node.get("params") or {}).get("text", ""))
        lines = max(1, text.count("\n") + 1 + len(text) // 60)
        return NODE_HEADER_H + max(40, lines * 15 + 20)

    meta = _node_meta(node.get("type") or "")
    input_types = meta.get("input_types") or {}
    required = input_types.get("required") or {}
    optional = input_types.get("optional") or {}
    all_specs = {**required, **optional}

    ins = len(required) + len(optional)
    outs = len(meta.get("return_types") or [])
    io_height = max(ins, outs, 1) * NODE_PIN_H

    widget_count = sum(1 for spec in all_specs.values() if _is_interactive_spec(spec))
    widget_height = widget_count * WIDGET_ROW_H + WIDGET_BLOCK_PAD if widget_count else 0

    params = node.get("params") or {}
    visible_params = sum(1 for key in params if key != "text")
    summary_height = min(3, visible_params) * 15 + 10 if widget_count == 0 and visible_params > 0 else 0
    description_height = 28 if widget_count == 0 and visible_params == 0 and meta.get("description") else 0

    base = NODE_HEADER_H + io_height + widget_height + summary_height + description_height + 12
    if meta.get("id") == "image_preview":
        base += 120
    return base


def topological_layers(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    """Assign a column index to each non-note, non-reroute node by longest-path depth."""
    adj: dict[str, list[str]] = defaultdict(list)
    in_deg: dict[str, int] = defaultdict(int)
    ids = {node["id"] for node in nodes if not is_note(node)}
    for node_id in ids:
        in_deg.setdefault(node_id, 0)
    for edge in edges:
        a = edge.get("from", {}).get("node")
        b = edge.get("to", {}).get("node")
        if a in ids and b in ids:
            adj[a].append(b)
            in_deg[b] += 1
    queue: deque[str] = deque(node_id for node_id, deg in in_deg.items() if deg == 0)
    order: list[str] = []
    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for nxt in adj[node_id]:
            in_deg[nxt] -= 1
            if in_deg[nxt] == 0:
                queue.append(nxt)
    layer: dict[str, int] = {node_id: 0 for node_id in ids}
    for node_id in order:
        for nxt in adj[node_id]:
            if layer[nxt] < layer[node_id] + 1:
                layer[nxt] = layer[node_id] + 1
    return layer


def relayout(workflow: dict[str, Any]) -> dict[str, Any]:
    nodes = list(workflow.get("nodes") or [])
    edges = list(workflow.get("edges") or [])
    layer = topological_layers(nodes, edges)

    columns: dict[int, list[dict[str, Any]]] = defaultdict(list)
    notes: list[dict[str, Any]] = []
    for node in nodes:
        if is_note(node):
            notes.append(node)
            continue
        columns[layer.get(node["id"], 0)].append(node)

    # Stable ordering within a column: keep edge-source order where possible,
    # falling back to insertion order to keep diffs minimal.
    incoming_index: dict[str, int] = {}
    for index, edge in enumerate(edges):
        target = edge.get("to", {}).get("node")
        if target and target not in incoming_index:
            incoming_index[target] = index

    new_nodes = []
    for col_index in sorted(columns):
        column_nodes = sorted(
            columns[col_index],
            key=lambda n: (incoming_index.get(n["id"], 10_000 + nodes.index(n)), n.get("id") or ""),
        )
        x = ORIGIN_X + col_index * COL_GAP
        y = ORIGIN_Y
        for node in column_nodes:
            height = estimate_node_height(node)
            new_node = dict(node)
            new_node["position"] = [x, y]
            new_nodes.append(new_node)
            y += height + ROW_GAP

    # Stack notes vertically on the left at negative X so they stay out of the main flow.
    note_y = ORIGIN_Y
    for note in notes:
        new_note = dict(note)
        new_note["position"] = [ORIGIN_X - 320, note_y]
        new_nodes.append(new_note)
        note_y += estimate_node_height(note) + ROW_GAP

    # Preserve original ordering so JSON diffs are smaller.
    by_id = {node["id"]: node for node in new_nodes}
    ordered = [by_id[node["id"]] for node in nodes if node["id"] in by_id]

    out = dict(workflow)
    out["nodes"] = ordered
    return out


def render_thumbnail(workflow: dict[str, Any], width: int = 640, height: int = 400) -> Image.Image:
    nodes = workflow.get("nodes") or []
    edges = workflow.get("edges") or []
    if not nodes:
        img = Image.new("RGB", (width, height), color=(15, 23, 42))
        return img

    min_x = min(node["position"][0] for node in nodes)
    min_y = min(node["position"][1] for node in nodes)
    max_x = max(node["position"][0] + (40 if is_reroute(node) else NODE_WIDTH) for node in nodes)
    max_y = max(node["position"][1] + estimate_node_height(node) for node in nodes)

    pad = 24
    bbox_w = max_x - min_x + pad * 2
    bbox_h = max_y - min_y + pad * 2
    scale = min(width / bbox_w, height / bbox_h)
    off_x = (width - bbox_w * scale) / 2 + (pad - min_x) * scale
    off_y = (height - bbox_h * scale) / 2 + (pad - min_y) * scale

    def to_screen(x: float, y: float) -> tuple[float, float]:
        return x * scale + off_x, y * scale + off_y

    img = Image.new("RGB", (width, height), color=(15, 23, 42))
    draw = ImageDraw.Draw(img, "RGBA")

    try:
        font = ImageFont.truetype("arial.ttf", max(10, int(11 * scale)))
    except OSError:
        font = ImageFont.load_default()

    # Edges first so nodes draw over them.
    by_id = {node["id"]: node for node in nodes}
    for edge in edges:
        a = by_id.get(edge.get("from", {}).get("node"))
        b = by_id.get(edge.get("to", {}).get("node"))
        if not a or not b:
            continue
        a_w = 40 if is_reroute(a) else NODE_WIDTH
        a_h = estimate_node_height(a)
        b_h = estimate_node_height(b)
        ax, ay = to_screen(a["position"][0] + a_w, a["position"][1] + a_h / 2)
        bx, by = to_screen(b["position"][0], b["position"][1] + b_h / 2)
        # Cheap cubic-ish curve via two segments.
        midx = (ax + bx) / 2
        draw.line([(ax, ay), (midx, ay), (midx, by), (bx, by)], fill=(148, 163, 184), width=2)

    for node in nodes:
        nx, ny = node["position"]
        nw = 40 if is_reroute(node) else NODE_WIDTH
        nh = estimate_node_height(node)
        x0, y0 = to_screen(nx, ny)
        x1, y1 = to_screen(nx + nw, ny + nh)
        ui = node.get("ui") or {}
        color = ui.get("color") or _color_for_type(node.get("type", ""))
        if is_note(node):
            fill = (245, 158, 11, 60)
            border = (245, 158, 11, 255)
        elif is_reroute(node):
            cx = (x0 + x1) / 2
            cy = (y0 + y1) / 2
            r = max(3, min((x1 - x0), (y1 - y0)) / 2)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_hex_to_rgba(color), outline=(255, 255, 255, 220), width=1)
            continue
        else:
            fill = (30, 41, 59, 230)
            border = _hex_to_rgba(color)
        draw.rounded_rectangle([x0, y0, x1, y1], radius=max(2, int(8 * scale)), fill=fill, outline=border, width=max(1, int(1.5)))
        # Header band in the node color.
        header_h = max(6, int(NODE_HEADER_H * scale))
        draw.rounded_rectangle([x0, y0, x1, y0 + header_h], radius=max(2, int(8 * scale)), fill=_hex_to_rgba(color))
        # Title (truncate to fit).
        label = ui.get("title") or node.get("type", "node")
        max_chars = max(6, int((nw - 12) * scale / 6))
        if len(label) > max_chars:
            label = label[: max_chars - 1] + "..."
        draw.text((x0 + 4, y0 + 2), label, fill=(255, 255, 255), font=font)

    # Subtle frame so the thumbnail reads as a single asset on light/dark UIs.
    draw.rounded_rectangle([0, 0, width - 1, height - 1], radius=8, outline=(45, 212, 191, 90), width=1)
    return img


def _hex_to_rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    text = value.lstrip("#") if isinstance(value, str) else ""
    if len(text) == 6:
        try:
            return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16), alpha)
        except ValueError:
            pass
    return (45, 212, 191, alpha)


_CATEGORY_COLORS = {
    # Exact Title-Case categories from the legacy frontend COLORS table.
    "Input": "#0d9488",
    "Quality Control": "#ec4899",
    "Read Preprocessing": "#f59e0b",
    "Alignment": "#3b82f6",
    "SAM/BAM Processing": "#60a5fa",
    "Variant Calling": "#ef4444",
    "Assembly": "#22c55e",
    "Annotation": "#a855f7",
    "Phylogenetics": "#14b8a6",
    "RNA-Seq": "#f97316",
    "Metagenomics": "#8b5cf6",
    "ChIP-Seq": "#06b6d4",
    "Single Cell": "#d946ef",
    "HPC": "#6366f1",
    "Utility": "#64748b",
}

# Lowercase substring rules — mirror COLOR_KEYWORD_RULES in
# web/src/components/canvas/LiteGraphCanvas.tsx. Order matters: first match
# wins, so specific keywords come before generic ones.
_KEYWORD_RULES: list[tuple[str, str]] = [
    ("input", "#0d9488"),
    ("qc", "#ec4899"),
    ("quality", "#ec4899"),
    ("preprocess", "#f59e0b"),
    ("trim", "#f59e0b"),
    ("cutadapt", "#f59e0b"),
    ("fastp", "#f59e0b"),
    ("samtools", "#60a5fa"),
    ("sam/bam", "#60a5fa"),
    ("align", "#3b82f6"),
    ("hisat", "#3b82f6"),
    ("bowtie", "#3b82f6"),
    ("bwa", "#3b82f6"),
    ("minimap", "#3b82f6"),
    ("star", "#3b82f6"),
    ("variant", "#ef4444"),
    ("gatk", "#ef4444"),
    ("bcftools", "#ef4444"),
    ("freebayes", "#ef4444"),
    ("vcftools", "#ef4444"),
    ("assembly", "#22c55e"),
    ("spades", "#22c55e"),
    ("canu", "#22c55e"),
    ("flye", "#22c55e"),
    ("unicycler", "#22c55e"),
    ("megahit", "#22c55e"),
    ("quast", "#22c55e"),
    ("annotation", "#a855f7"),
    ("prokka", "#a855f7"),
    ("bakta", "#a855f7"),
    ("eggnog", "#a855f7"),
    ("phylo", "#14b8a6"),
    ("mafft", "#14b8a6"),
    ("iqtree", "#14b8a6"),
    ("fasttree", "#14b8a6"),
    ("raxml", "#14b8a6"),
    ("clustalo", "#14b8a6"),
    ("single", "#d946ef"),
    ("cellranger", "#d946ef"),
    ("metag", "#8b5cf6"),
    ("kraken", "#8b5cf6"),
    ("bracken", "#8b5cf6"),
    ("metaphlan", "#8b5cf6"),
    ("humann", "#8b5cf6"),
    ("checkm", "#8b5cf6"),
    ("maxbin", "#8b5cf6"),
    ("quantif", "#a855f7"),
    ("count", "#a855f7"),
    ("featurecounts", "#a855f7"),
    ("kallisto", "#a855f7"),
    ("salmon", "#a855f7"),
    ("stringtie", "#a855f7"),
    ("differential", "#ef4444"),
    ("deseq", "#ef4444"),
    ("expression", "#a855f7"),
    ("peak", "#06b6d4"),
    ("macs", "#06b6d4"),
    ("chip", "#06b6d4"),
    ("deeptools", "#3b82f6"),
    ("bedtools", "#60a5fa"),
    ("hpc", "#6366f1"),
    ("biopython", "#a855f7"),
    ("biostrings", "#a855f7"),
    ("blast", "#a855f7"),
    ("plot", "#ec4899"),
    ("heatmap", "#ec4899"),
    ("viz", "#ec4899"),
    ("note", "#f59e0b"),
]


def _color_for_type(node_type: str) -> str:
    meta = _OBJECT_INFO.get(node_type) or {}
    category = meta.get("category") or ""
    if category in _CATEGORY_COLORS:
        return _CATEGORY_COLORS[category]
    haystack = f"{category} {node_type} {meta.get('display_name', '')}".lower()
    for keyword, color in _KEYWORD_RULES:
        if keyword in haystack:
            return color
    return "#64748b"


def write_thumbnail_with_workflow(workflow: dict[str, Any], out_path: Path) -> None:
    img = render_thumbnail(workflow)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    _embed_in_png(out_path, {"workflow": workflow, "bionodulo_version": "2.0"})


def process_one(path: Path, *, dry_run: bool) -> str:
    workflow = json.loads(path.read_text(encoding="utf-8"))
    repositioned = relayout(workflow)
    if dry_run:
        return f"  dry-run: would update {path.name}"
    path.write_text(json.dumps(repositioned, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    thumbnail_path = path.with_suffix(".png")
    write_thumbnail_with_workflow(repositioned, thumbnail_path)
    return f"  ok: {path.name} -> {thumbnail_path.name}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing.")
    parser.add_argument("templates", nargs="*", help="Specific template JSON files (default: all).")
    args = parser.parse_args()

    targets: list[Path]
    if args.templates:
        targets = [Path(name) if "/" in name or "\\" in name else TEMPLATES_DIR / name for name in args.templates]
    else:
        targets = sorted(TEMPLATES_DIR.glob("*.json"))

    print(f"Re-laying out {len(targets)} templates in {TEMPLATES_DIR}")
    for target in targets:
        if not target.exists():
            print(f"  skip (missing): {target}")
            continue
        try:
            print(process_one(target, dry_run=args.dry_run))
        except Exception as exc:  # noqa: BLE001 - dev tool, report per-file
            print(f"  fail: {target.name}: {exc}")


if __name__ == "__main__":
    main()
