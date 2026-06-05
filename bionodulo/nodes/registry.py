"""NodeRegistry - discovers, registers, and manages all BioNodulo nodes.

Supports built-in nodes and custom nodes from external directories.
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
            cls._initialise_instance(cls._instance)
        return cls._instance

    @classmethod
    def create_isolated(cls) -> NodeRegistry:
        """Create a non-singleton registry for tests and isolated runtimes."""
        registry = super().__new__(cls)
        cls._initialise_instance(registry)
        return registry

    @staticmethod
    def _initialise_instance(registry: NodeRegistry) -> None:
        registry._nodes = {}
        registry._loaded = set()
        registry._object_info_cache = None

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
        validate_metadata_contract = getattr(node_class, "validate_metadata_contract", None)
        if callable(validate_metadata_contract):
            validate_metadata_contract()
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
        """Return node metadata for the frontend registry.

        Args:
            node_id: Optional specific node ID. If None, returns all nodes.

        Returns:
            Dictionary of node metadata keyed by node ID.
        """
        if node_id is not None:
            node_class = self._nodes.get(node_id)
            if node_class is None:
                return {}
            return _to_node_info(node_class)

        if self._object_info_cache is None:
            self._object_info_cache = {
                nid: _to_node_info(nc)
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
        """Yield all registered node classes.

        Yields:
            BaseNode subclasses.
        """
        for node_class in self._nodes.values():
            yield node_class

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


def _to_node_info(node_class: Type[BaseNode]) -> dict[str, Any]:
    """Convert a BaseNode class to frontend registry metadata.

    Args:
        node_class: The node class to convert.

    Returns:
        Dictionary consumed by the frontend node registry.
    """
    input_types = node_class.INPUT_TYPES()
    required = input_types.get("required", {})
    optional = input_types.get("optional", {})
    hidden = input_types.get("hidden", {})

    node_input: dict[str, Any] = {"required": {}, "optional": {}, "hidden": {}}

    for name, spec in required.items():
        node_input["required"][name] = _to_frontend_input_spec(spec)

    for name, spec in optional.items():
        node_input["optional"][name] = _to_frontend_input_spec(spec)

    for name, spec in hidden.items():
        node_input["hidden"][name] = _to_frontend_input_spec(spec)

    return {
        "input": node_input,
        "output": list(node_class.RETURN_TYPES),
        "output_name": list(node_class.RETURN_NAMES),
        "name": node_class.NODE_ID,
        "display_name": node_class.DISPLAY_NAME or node_class.NODE_ID,
        "description": node_class.DESCRIPTION,
        "search_aliases": list(node_class.SEARCH_ALIASES),
        "category": node_class.CATEGORY,
        "output_node": node_class.OUTPUT_NODE,
        "visual_only": node_class.VISUAL_ONLY,
        "experimental": node_class.EXPERIMENTAL,
        "requires_external_tools": getattr(node_class, "REQUIRES_EXTERNAL_TOOLS", True),
        "version": node_class.VERSION,
        "deprecated": node_class.DEPRECATED,
        "deprecation_message": node_class.DEPRECATION_MESSAGE,
        "replaced_by": node_class.REPLACED_BY,
        "lifecycle": node_class.lifecycle_metadata(),
        "versioning": node_class.versioning_metadata(),
        "builtin": node_class.__module__.startswith("bionodulo.nodes.builtin"),
        "python_class": f"{node_class.__module__}.{node_class.__name__}",
        "git_url": node_class.GIT_URL,
        "git_commit": node_class.GIT_COMMIT,
        "required_executables": getattr(node_class, "REQUIRED_EXECUTABLES", []),
        "required_conda_packages": getattr(node_class, "REQUIRED_CONDA_PACKAGES", []),
        "required_r_packages": getattr(node_class, "REQUIRED_R_PACKAGES", []),
    }


def _to_frontend_input_spec(spec: Any) -> tuple[str, dict[str, Any]]:
    type_name = spec[0] if isinstance(spec, (list, tuple)) else spec
    raw_config = spec[1] if isinstance(spec, (list, tuple)) and len(spec) > 1 else {}
    config = dict(raw_config) if isinstance(raw_config, dict) else {}
    if isinstance(type_name, (list, tuple)):
        config.setdefault("options", list(type_name))
    return (_node_type(type_name), config)


def _node_type(bionodulo_type: str | list | tuple) -> str:
    """Map BioNodulo type names to frontend socket type names.

    Args:
        bionodulo_type: BioNodulo type string (or list/tuple in edge cases).

    Returns:
        Frontend socket type string.
    """
    while isinstance(bionodulo_type, (list, tuple)):
        bionodulo_type = bionodulo_type[0] if len(bionodulo_type) > 0 else "STRING"
    if not isinstance(bionodulo_type, str):
        bionodulo_type = str(bionodulo_type)
    passthrough_types = {
        "STRING",
        "INT",
        "FLOAT",
        "BOOLEAN",
        "FILE",
        "DIRECTORY",
        "FASTQ",
        "FASTQ_LIST",
        "FASTA",
        "FASTA_INDEX",
        "SAM",
        "BAM",
        "BAI",
        "CRAM",
        "VCF",
        "VCF_GZ",
        "BCF",
        "VCF_INDEX",
        "GFF",
        "GTF",
        "GFF_GTF",
        "BED",
        "ASSEMBLY",
        "CONTIGS",
        "SCAFFOLDS",
        "GFA",
        "ODGI",
        "IMAGE",
        "JSON",
        "CSV",
        "TSV",
        "EMBEDDING",
    }
    if bionodulo_type in passthrough_types:
        return bionodulo_type
    if bionodulo_type == "ANY":
        return "*"
    return "STRING"
