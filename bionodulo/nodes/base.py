"""BaseNode class - the abstract base for all BioNodulo nodes."""
from __future__ import annotations

import abc
import json
import hashlib
import re
from pathlib import Path
from typing import Any, ClassVar, Union

from bionodulo.nodes.types import file_extension_for


class BaseNode(abc.ABC):
    """Abstract base class for all BioNodulo workflow nodes."""

    NODE_ID: ClassVar[str] = ""
    DISPLAY_NAME: ClassVar[str] = ""
    CATEGORY: ClassVar[str] = "general"
    DESCRIPTION: ClassVar[str] = ""
    SEARCH_ALIASES: ClassVar[list[str]] = []
    RETURN_TYPES: ClassVar[tuple[str, ...]] = ()
    RETURN_NAMES: ClassVar[tuple[str, ...]] = ()
    FUNCTION: ClassVar[str] = "run"
    OUTPUT_NODE: ClassVar[bool] = False
    VISUAL_ONLY: ClassVar[bool] = False
    EXPERIMENTAL: ClassVar[bool] = False
    REQUIRES_EXTERNAL_TOOLS: ClassVar[bool] = True
    REQUIRED_EXECUTABLES: ClassVar[list[str]] = []
    REQUIRED_CONDA_PACKAGES: ClassVar[list[str]] = []
    REQUIRED_R_PACKAGES: ClassVar[list[str]] = []
    DOCUMENTATION_URL: ClassVar[str] = ""
    VERSION: ClassVar[str] = "1.0.0"
    ENVIRONMENT: ClassVar[dict[str, Any]] = {}
    GIT_URL: ClassVar[str] = ""  # Required for custom nodes: source repository
    GIT_COMMIT: ClassVar[str] = ""  # Optional: pinned commit hash
    _SUBCLASSES: ClassVar[list[type[BaseNode]]] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if abc.ABC not in cls.__bases__:
            BaseNode._SUBCLASSES.append(cls)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        """Declare input ports: required, optional, hidden."""
        return {"required": {}, "optional": {}, "hidden": {}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        """Validate inputs before execution. Return True or error message."""
        input_types = cls.INPUT_TYPES()
        for category in ("required", "optional"):
            for name, spec in input_types.get(category, {}).items():
                type_name = spec[0] if isinstance(spec, (list, tuple)) else spec
                value = inputs.get(name)
                if category == "required" and value is None:
                    return f"Required input '{name}' is missing"
                if value is not None:
                    if type_name == "BOOLEAN" and not isinstance(value, bool):
                        return f"Input '{name}' must be a boolean"
                    if type_name == "INT" and not isinstance(value, int):
                        return f"Input '{name}' must be an integer"
                    if type_name == "FLOAT" and not isinstance(value, (int, float)):
                        return f"Input '{name}' must be a number"
        return True

    @classmethod
    def IS_CHANGED(cls, inputs: dict[str, Any]) -> str:
        """Return a hash representing current input state for cache invalidation."""
        serialized = cls._serialize_inputs(inputs)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        """Plan output file paths for this node."""
        output_dir = Path(output_dir)
        paths: list[Path] = []
        for i, ret_type in enumerate(cls.RETURN_TYPES):
            name = cls.RETURN_NAMES[i] if i < len(cls.RETURN_NAMES) else f"output_{i}"
            ext = file_extension_for(ret_type)
            paths.append(output_dir / cls.NODE_ID / f"{name}{ext}")
        return paths

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        """Return complete metadata dictionary for UI discovery."""
        return {
            "node_id": cls.NODE_ID,
            "display_name": cls.DISPLAY_NAME or cls.NODE_ID,
            "category": cls.CATEGORY,
            "description": cls.DESCRIPTION,
            "search_aliases": cls.SEARCH_ALIASES,
            "return_types": list(cls.RETURN_TYPES),
            "return_names": list(cls.RETURN_NAMES),
            "function": cls.FUNCTION,
            "output_node": cls.OUTPUT_NODE,
            "experimental": cls.EXPERIMENTAL,
            "requires_external_tools": cls.REQUIRES_EXTERNAL_TOOLS,
            "required_executables": cls.REQUIRED_EXECUTABLES,
            "required_conda_packages": cls.REQUIRED_CONDA_PACKAGES,
            "required_r_packages": cls.REQUIRED_R_PACKAGES,
            "documentation_url": cls.DOCUMENTATION_URL,
            "version": cls.VERSION,
            "environment": cls.ENVIRONMENT,
            "git_url": cls.GIT_URL,
            "git_commit": cls.GIT_COMMIT,
            "input_types": cls.INPUT_TYPES(),
        }

    @abc.abstractmethod
    async def run(self, **kwargs: Any) -> Union[tuple[Any, ...], dict[str, Any]]:
        """Execute node logic. Called by the workflow engine."""
        ...

    @classmethod
    def _serialize_inputs(cls, inputs: dict[str, Any]) -> str:
        """Serialize inputs into a stable string for hashing."""
        def _serialize(val: Any) -> Any:
            if isinstance(val, Path):
                return str(val)
            if isinstance(val, (list, tuple)):
                return [_serialize(v) for v in val]
            if isinstance(val, dict):
                return {k: _serialize(v) for k, v in sorted(val.items())}
            return val
        return json.dumps(_serialize(inputs), sort_keys=True, default=str)

    @classmethod
    def _default_output_name(
        cls,
        input_value: Any,
        suffix: str = "",
        extension: str = ".out",
        output_dir: str | Path | None = None,
    ) -> Path:
        """Generate a default output file name from an input value."""
        if input_value is None:
            stem = cls.NODE_ID
        else:
            stem = Path(str(input_value)).stem
            stem = re.sub(r'\.(gz|bz2|xz|zip)$', "", stem)
        if suffix:
            name = f"{stem}_{suffix}{extension}"
        else:
            name = f"{stem}{extension}"
        if output_dir is not None:
            return Path(output_dir) / cls.NODE_ID / name
        return Path(name)
