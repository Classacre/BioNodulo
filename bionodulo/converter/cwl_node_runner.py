"""Run selected BioNodulo built-in nodes from exported CWL tools."""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from bionodulo.nodes.registry import NodeRegistry


SUPPORTED_NODE_TYPES = {
    "extract_columns",
    "filter_rows",
    "merge_tables",
    "normalize_data",
    "replace_text",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Execute a BioNodulo node for CWL export")
    parser.add_argument("--node-type", required=True)
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--input", nargs=2, action="append", metavar=("NAME", "VALUE"), default=[])
    args = parser.parse_args(argv)

    try:
        return asyncio.run(_run(args.node_type, Path(args.output_dir), dict(args.input)))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


async def _run(node_type: str, output_dir: Path, inputs: dict[str, str]) -> int:
    if node_type not in SUPPORTED_NODE_TYPES:
        raise ValueError(f"Cannot execute unsupported CWL runner node type: {node_type}")

    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_type)
    if node_class is None:
        raise ValueError(f"Unknown BioNodulo node type: {node_type}")

    kwargs = _coerce_inputs(node_class, inputs)
    context = SimpleNamespace(node_dir=output_dir.resolve())
    raw = await node_class().run(context=context, **kwargs)
    outputs = _normalize_result(raw, node_class)
    _materialize_outputs(outputs, node_class, output_dir)
    return 0


def _coerce_inputs(node_class: Any, inputs: dict[str, str]) -> dict[str, Any]:
    types = _input_types(node_class)
    return {name: _coerce_value(value, types.get(name, "STRING")) for name, value in inputs.items()}


def _input_types(node_class: Any) -> dict[str, Any]:
    input_types = node_class.INPUT_TYPES()
    types: dict[str, Any] = {}
    for section in ("required", "optional", "hidden"):
        for name, spec in input_types.get(section, {}).items():
            types[name] = spec[0] if isinstance(spec, (list, tuple)) else spec
    return types


def _coerce_value(value: str, type_name: Any) -> Any:
    if isinstance(type_name, list):
        return value
    normalized = str(type_name).upper()
    if normalized == "INT":
        return int(value)
    if normalized == "FLOAT":
        return float(value)
    if normalized == "BOOLEAN":
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if normalized in {"JSON", "ANY"}:
        return json.loads(value)
    return value


def _normalize_result(raw: Any, node_class: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        outputs = raw.get("outputs")
        if not isinstance(outputs, dict):
            raise ValueError("Node result dict must return an 'outputs' mapping")
        return outputs
    if isinstance(raw, tuple):
        names = getattr(node_class, "RETURN_NAMES", ()) or ()
        return {names[index] if index < len(names) else f"output_{index}": value for index, value in enumerate(raw)}
    if raw is None:
        raise ValueError("Node did not return outputs")
    names = getattr(node_class, "RETURN_NAMES", ()) or ()
    return {names[0] if names else "default": raw}


def _materialize_outputs(outputs: dict[str, Any], node_class: Any, output_dir: Path) -> None:
    for output_name in getattr(node_class, "RETURN_NAMES", ()) or outputs.keys():
        if output_name not in outputs:
            continue
        value = outputs[output_name]
        target = output_dir / f"{output_name}_output"
        if isinstance(value, (str, Path)) and Path(value).exists():
            _copy_path(Path(value), target)
        else:
            target.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _copy_path(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == target.resolve():
        return
    if source.is_dir():
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)


if __name__ == "__main__":
    raise SystemExit(main())
