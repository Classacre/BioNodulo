"""Deterministic native file collection contract."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .adapter import PythonUtilityNode, path_value


def _source_paths(value: Any) -> list[Path]:
    if isinstance(value, (list, tuple, set)):
        items = list(value)
    elif value in (None, ""):
        items = []
    else:
        items = [value]
    paths = [Path(path_value(item)) for item in items if path_value(item)]
    return sorted(paths, key=lambda path: (path.name.casefold(), str(path)))


class CollectFilesNode(PythonUtilityNode):
    """Copy distinct files or directories into a freshly-created directory."""

    NODE_ID = "collect_files"
    DISPLAY_NAME = "Collect Files"
    CATEGORY = "utils"
    DESCRIPTION = "Gather files or directories into a deterministic output directory"
    SEARCH_ALIASES = ["collect", "gather", "merge", "directory"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("output_dir",)
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/shutil.html"
    UPSTREAM_SOURCE = "Lib/shutil.py; Lib/pathlib.py"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "files": ("FILE", {"multiple": True, "description": "Files or directories to collect"}),
            },
            "optional": {"output_name": ("STRING", {"default": "collected"})},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _validated(cls, inputs: dict[str, Any], base_dir: Path | None = None) -> tuple[list[Path], str] | str:
        sources = _source_paths(inputs.get("files"))
        if not sources:
            return "Input 'files' requires at least one path"
        missing = [str(path) for path in sources if not path.exists()]
        if missing:
            return f"Collection input not found: {', '.join(missing)}"
        unsupported = [str(path) for path in sources if not (path.is_file() or path.is_dir())]
        if unsupported:
            return f"Collection input is not a file or directory: {', '.join(unsupported)}"

        output_name = str(inputs.get("output_name", "collected") or "collected").strip()
        if output_name in {"", ".", ".."} or Path(output_name).name != output_name:
            return "Input 'output_name' must be a single basename"
        names: dict[str, Path] = {}
        for source in sources:
            collision_key = source.name.casefold()
            if collision_key in names:
                return f"Collection inputs have a basename collision: {source.name}"
            names[collision_key] = source

        if base_dir is not None:
            destination = (base_dir / output_name).resolve()
            for source in sources:
                resolved = source.resolve()
                if resolved == destination or resolved.is_relative_to(destination) or destination.is_relative_to(resolved):
                    return f"Collection input overlaps the output directory: {source}"
        return sources, output_name

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        result = cls._validated(inputs)
        return True if not isinstance(result, str) else result

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        base_dir = Path(getattr(context, "node_dir", ".") if context is not None else ".")
        result = self._validated(kwargs, base_dir)
        if isinstance(result, str):
            raise ValueError(result)
        sources, output_name = result
        destination = base_dir / output_name
        if destination.exists():
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        destination.mkdir(parents=True)
        for source in sources:
            target = destination / source.name
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        return (str(destination),)
