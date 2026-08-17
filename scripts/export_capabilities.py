#!/usr/bin/env python3
"""Export the node capability/requirements artifact.

Writes ``bionodulo/nodes/node_capabilities.json`` mapping every builtin node
to ``{"requires_gpu": bool, "required_executables": [...]}`` — the engine-side
input for capability preflight (GPU availability, executable presence) and the
same data ``WorkflowExecutor.dry_run`` aggregates into its ``requirements``
block.

Companion to ``scripts/gen_node_index.py``: regenerate after changing
``REQUIRES_GPU`` / ``REQUIRED_EXECUTABLES`` declarations.

Usage:  python scripts/export_capabilities.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

OUTPUT_PATH = _REPO_ROOT / "bionodulo" / "nodes" / "node_capabilities.json"


def build_capabilities(registry: Any) -> dict[str, dict[str, Any]]:
    """Return ``{node_id: {requires_gpu, required_executables}}`` (sorted)."""
    capabilities: dict[str, dict[str, Any]] = {}
    for node_id, node_class in registry.all().items():
        capabilities[str(node_id)] = {
            "requires_gpu": bool(getattr(node_class, "REQUIRES_GPU", False)),
            "required_executables": sorted(
                str(item) for item in getattr(node_class, "REQUIRED_EXECUTABLES", []) or []
            ),
        }
    return dict(sorted(capabilities.items()))


def main() -> int:
    from bionodulo.nodes.registry import NodeRegistry

    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes(strict=True)
    capabilities = build_capabilities(registry)
    payload = json.dumps(capabilities, indent=2, sort_keys=True) + "\n"
    OUTPUT_PATH.write_text(payload, encoding="utf-8")
    gpu_nodes = [node_id for node_id, cap in capabilities.items() if cap["requires_gpu"]]
    print(
        f"Wrote {OUTPUT_PATH.name} ({len(capabilities)} nodes, "
        f"{len(gpu_nodes)} GPU): {', '.join(gpu_nodes)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
