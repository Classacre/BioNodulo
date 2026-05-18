"""NodeRegistry - discovers, registers, and manages all BioNodulo nodes.

Supports built-in nodes, custom nodes from external directories, and
ComfyUI v3 adapter nodes.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import pkgutil
import sys
from pathlib import Path
from typing import Any, ClassVar, Iterator, Optional, Type

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode

logger = logging.getLogger(__name__)


class NodeRegistry:
    """Central registry for all node classes in BioNodulo.

    Provides node discovery, registration, metadata queries, and
    dynamic loading of custom node packages.
    """

    _instance: ClassVar[Optional[NodeRegistry]] = None

    _nodes: dict[str, Type[BaseNode]]
    _loaded: set[str]
    _object_info_cache: dict[str, Any] | None

    def __new__(cls) -> NodeRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._nodes = {}
            cls._instance._loaded = set()
            cls._instance._object_info_cache = None
        return cls._instance

    # ── Registration ─────────────────────────────────────────────────

    def register(self, node_class: Type[BaseNode]) -> None:
        """Register a single node class.

        Args:
            node_class: A BaseNode subclass to register.

        Raises:
            ValueError: If NODE_ID is missing or already registered.
        """
        node_id = node_class.NODE_ID
        if not node_id:
            raise ValueError(
                f"Node class {node_class.__name__} missing NODE_ID"
            )
        if node_id in self._nodes:
            logger.warning("Overwriting registered node: %s", node_id)
        self._nodes[node_id] = node_class
        self._object_info_cache = None
        logger.debug("Registered node: %s", node_id)

    def get(self, node_id: str) -> Optional[Type[BaseNode]]:
        """Get a registered node class by ID.

        Args:
            node_id: The unique node identifier.

        Returns:
            The node class or None if not found.
        """
        return self._nodes.get(node_id)

    def has(self, node_id: str) -> bool:
        """Check if a node ID is registered.

        Args:
            node_id: The node identifier to check.

        Returns:
            True if the node is registered.
        """
        return node_id in self._nodes

    def all(self) -> dict[str, Type[BaseNode]]:
        """Return all registered node classes.

        Returns:
            Dictionary mapping node IDs to node classes.
        """
        return dict(self._nodes)

    def object_info(self, node_id: str | None = None) -> dict[str, Any]:
        """Return ComfyUI-compatible object_info metadata.

        Args:
            node_id: Optional specific node ID. If None, returns all nodes.

        Returns:
            Dictionary of node metadata in ComfyUI object_info format.
        """
        if node_id is not None:
            node_class = self._nodes.get(node_id)
            if node_class is None:
                return {}
            return _to_comfy_info(node_class)

        if self._object_info_cache is None:
            self._object_info_cache = {
                nid: _to_comfy_info(nc)
                for nid, nc in sorted(self._nodes.items())
            }
        return self._object_info_cache

    # ── Discovery ────────────────────────────────────────────────────

    def load_builtin_nodes(self) -> int:
        """Import and register all built-in node modules.

        Walks the bionodulo.nodes.builtin package and registers
        all BaseNode subclasses found.

        Returns:
            Number of node classes registered.
        """
        import bionodulo.nodes.builtin as builtin_pkg
        pkg_path = Path(builtin_pkg.__file__).parent
        count = 0

        for _, modname, ispkg in pkgutil.iter_modules([str(pkg_path)]):
            if ispkg or modname.startswith("_"):
                continue
            full_name = f"bionodulo.nodes.builtin.{modname}"
            try:
                module = importlib.import_module(full_name)
                count += self.register_from_module(module)
                self._loaded.add(full_name)
            except Exception as exc:
                logger.warning("Failed to load builtin module %s: %s", full_name, exc)

        logger.info("Loaded %d nodes from builtin modules", count)
        return count

    def load_custom_nodes(self, custom_nodes_dir: str | Path) -> int:
        """Dynamically load custom nodes from a directory.

        Scans the directory for Python files and packages that define
        BaseNode subclasses and registers them.

        Args:
            custom_nodes_dir: Path to the custom_nodes directory.

        Returns:
            Number of node classes registered.
        """
        custom_path = Path(custom_nodes_dir)
        if not custom_path.exists():
            logger.info("Custom nodes directory does not exist: %s", custom_path)
            return 0

        count = 0
        before_custom = set(self._nodes.keys())
        sys.path.insert(0, str(custom_path.parent))

        for entry in sorted(custom_path.iterdir()):
            if entry.name.startswith("_") or entry.name.endswith(".pyc"):
                continue

            try:
                if entry.is_file() and entry.suffix == ".py":
                    module = self._load_module_from_path(
                        entry.stem, entry
                    )
                    if module:
                        count += self.register_from_module(module)
                elif entry.is_dir() and (entry / "__init__.py").exists():
                    module = self._load_module_from_path(
                        entry.name, entry / "__init__.py"
                    )
                    if module:
                        count += self.register_from_module(module)
            except Exception as exc:
                logger.warning("Failed to load custom node %s: %s", entry.name, exc)

        # Validate custom nodes have GIT_URL
        for node_id, node_class in self._nodes.items():
            if node_id in before_custom:
                continue
            if not node_class.GIT_URL:
                logger.warning(
                    "Custom node '%s' (%s) is missing GIT_URL. "
                    "All custom nodes should declare a git repository for dependency resolution.",
                    node_id, node_class.__name__
                )

        logger.info("Loaded %d nodes from custom_nodes", count)
        return count

    def register_from_module(self, module: Any) -> int:
        """Find and register all BaseNode subclasses in a module.

        Args:
            module: Python module to scan.

        Returns:
            Number of node classes registered.
        """
        count = 0
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseNode)
                and obj is not BaseNode
                and obj is not CommandNode
                and obj.NODE_ID
            ):
                self.register(obj)
                count += 1
        return count

    def iter_node_classes(self) -> Iterator[Type[BaseNode]]:
        """Yield all registered node classes including Comfy v3 adapted ones.

        Yields:
            BaseNode subclasses.
        """
        for node_class in self._nodes.values():
            yield node_class
            # If this node also has a Comfy v3 adapter, yield that too
            if hasattr(node_class, "_comfy_v3_class"):
                yield node_class._comfy_v3_class

    def _load_module_from_path(self, name: str, path: Path) -> Any:
        """Dynamically load a module from a file path.

        Args:
            name: Module name.
            path: Path to the Python file.

        Returns:
            Loaded module or None on failure.
        """
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return module
        except Exception as exc:
            logger.warning("Failed to load module %s from %s: %s", name, path, exc)
            return None

    def clear(self) -> None:
        """Clear all registrations (primarily for testing)."""
        self._nodes.clear()
        self._loaded.clear()
        self._object_info_cache = None


def _to_comfy_info(node_class: Type[BaseNode]) -> dict[str, Any]:
    """Convert a BaseNode class to ComfyUI-compatible object_info format.

    Args:
        node_class: The node class to convert.

    Returns:
        Dictionary in ComfyUI object_info format.
    """
    input_types = node_class.INPUT_TYPES()
    required = input_types.get("required", {})
    optional = input_types.get("optional", {})
    hidden = input_types.get("hidden", {})

    comfy_input: dict[str, Any] = {"required": {}, "optional": {}, "hidden": {}}

    for name, spec in required.items():
        type_name = spec[0] if isinstance(spec, (list, tuple)) else spec
        config = spec[1] if isinstance(spec, (list, tuple)) and len(spec) > 1 else {}
        comfy_input["required"][name] = (_comfy_type(type_name), config)

    for name, spec in optional.items():
        type_name = spec[0] if isinstance(spec, (list, tuple)) else spec
        config = spec[1] if isinstance(spec, (list, tuple)) and len(spec) > 1 else {}
        comfy_input["optional"][name] = (_comfy_type(type_name), config)

    for name, spec in hidden.items():
        type_name = spec[0] if isinstance(spec, (list, tuple)) else spec
        config = spec[1] if isinstance(spec, (list, tuple)) and len(spec) > 1 else {}
        comfy_input["hidden"][name] = (_comfy_type(type_name), config)

    return {
        "input": comfy_input,
        "output": list(node_class.RETURN_TYPES),
        "output_name": list(node_class.RETURN_NAMES),
        "name": node_class.NODE_ID,
        "display_name": node_class.DISPLAY_NAME or node_class.NODE_ID,
        "description": node_class.DESCRIPTION,
        "category": node_class.CATEGORY,
        "output_node": node_class.OUTPUT_NODE,
        "visual_only": node_class.VISUAL_ONLY,
        "experimental": node_class.EXPERIMENTAL,
        "version": node_class.VERSION,
        "builtin": node_class.__module__.startswith("bionodulo.nodes.builtin"),
        "python_class": f"{node_class.__module__}.{node_class.__name__}",
        "git_url": node_class.GIT_URL,
        "git_commit": node_class.GIT_COMMIT,
        "required_executables": getattr(node_class, "REQUIRED_EXECUTABLES", []),
        "required_conda_packages": getattr(node_class, "REQUIRED_CONDA_PACKAGES", []),
        "required_r_packages": getattr(node_class, "REQUIRED_R_PACKAGES", []),
    }


def _comfy_type(bionodulo_type: str | list | tuple) -> str:
    """Map BioNodulo type names to ComfyUI-compatible type names.

    Args:
        bionodulo_type: BioNodulo type string (or list/tuple in edge cases).

    Returns:
        ComfyUI-compatible type string.
    """
    while isinstance(bionodulo_type, (list, tuple)):
        bionodulo_type = bionodulo_type[0] if len(bionodulo_type) > 0 else "STRING"
    if not isinstance(bionodulo_type, str):
        bionodulo_type = str(bionodulo_type)
    mapping = {
        "STRING": "STRING",
        "INT": "INT",
        "FLOAT": "FLOAT",
        "BOOLEAN": "BOOLEAN",
        "FILE": "STRING",
        "DIRECTORY": "STRING",
        "FASTQ": "STRING",
        "FASTQ_LIST": "STRING",
        "FASTA": "STRING",
        "SAM": "STRING",
        "BAM": "STRING",
        "VCF": "STRING",
        "VCF_GZ": "STRING",
        "GFF": "STRING",
        "GTF": "STRING",
        "GFF_GTF": "STRING",
        "BED": "STRING",
        "ASSEMBLY": "STRING",
        "CONTIGS": "STRING",
        "SCAFFOLDS": "STRING",
        "ALIGNMENT": "STRING",
        "PHYLOGENY_TREE": "STRING",
        "INDEX_DIR": "STRING",
        "QC_REPORT_DIR": "STRING",
        "MULTIQC_REPORT": "STRING",
        "HTML_REPORT": "STRING",
        "STATS_FILE": "STRING",
        "SAMPLE_SHEET": "STRING",
        "COUNTS": "STRING",
        "TPM_MATRIX": "STRING",
        "ABUNDANCE": "STRING",
        "GENE_EXPRESSION": "STRING",
        "TX_EXPRESSION": "STRING",
        "TRANSCRIPTS": "STRING",
        "KRAKEN_REPORT": "STRING",
        "KRAKEN_OUTPUT": "STRING",
        "METAPHLAN_PROFILE": "STRING",
        "HUMANN_OUTPUT": "STRING",
        "BINS": "STRING",
        "CELL_RANGER_OUT": "STRING",
        "H5AD": "STRING",
        "SEURAT_OBJ": "STRING",
        "PEAKS": "STRING",
        "BIGWIG": "STRING",
        "NARROW_PEAK": "STRING",
        "BROAD_PEAK": "STRING",
        "JSON": "STRING",
        "YAML": "STRING",
        "CSV": "STRING",
        "TSV": "STRING",
        "ANY": "*",
    }
    return mapping.get(bionodulo_type, "STRING")
