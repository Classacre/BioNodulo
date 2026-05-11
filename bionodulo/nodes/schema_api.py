"""ComfyUI v3 schema compatibility layer for BioNodulo.

Provides SchemaNode base class, socket type definitions, and the
BioNoduloExtension class for integrating with ComfyUI v3 workflows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Optional


# ── Socket Type Definitions ────────────────────────────────────────

class Socket:
    """Base socket type for schema definitions."""

    def __init__(self, name: str, tooltip: str = "") -> None:
        self.name = name
        self.tooltip = tooltip

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.name, "tooltip": self.tooltip}


class StringSocket(Socket):
    """String socket for file paths, text, and identifiers."""
    def __init__(self, tooltip: str = "") -> None:
        super().__init__("STRING", tooltip)


class IntSocket(Socket):
    """Integer socket for numeric parameters like threads."""
    def __init__(self, tooltip: str = "") -> None:
        super().__init__("INT", tooltip)


class FloatSocket(Socket):
    """Float socket for decimal parameters."""
    def __init__(self, tooltip: str = "") -> None:
        super().__init__("FLOAT", tooltip)


class BooleanSocket(Socket):
    """Boolean socket for flags and toggles."""
    def __init__(self, tooltip: str = "") -> None:
        super().__init__("BOOLEAN", tooltip)


# Bioinformatics-specific sockets
class FASTQSocket(Socket):
    def __init__(self, tooltip: str = "") -> None:
        super().__init__("FASTQ", tooltip)


class FASTASocket(Socket):
    def __init__(self, tooltip: str = "") -> None:
        super().__init__("FASTA", tooltip)


class BAMSocket(Socket):
    def __init__(self, tooltip: str = "") -> None:
        super().__init__("BAM", tooltip)


class VCF_SOCKET(Socket):
    def __init__(self, tooltip: str = "") -> None:
        super().__init__("VCF", tooltip)


# ── Schema Node ────────────────────────────────────────────────────

@dataclass
class SchemaNode:
    """ComfyUI v3 schema-compatible node definition.

    Used for defining nodes in the ComfyUI v3 schema format while
    maintaining compatibility with BioNodulo native nodes.
    """

    name: str
    category: str
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    widgets: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    execute: Optional[Callable] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to ComfyUI v3 node schema dictionary."""
        return {
            "name": self.name,
            "category": self.category,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "widgets": self.widgets,
            "metadata": self.metadata,
        }

    @classmethod
    def define_schema(
        cls,
        name: str,
        category: str,
        input_specs: list[tuple[str, Socket, dict[str, Any]]],
        output_specs: list[tuple[str, Socket, dict[str, Any]]],
        widget_specs: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SchemaNode:
        """Define a schema node with typed inputs and outputs.

        Args:
            name: Node name.
            category: Category for UI grouping.
            input_specs: List of (name, Socket, config) tuples.
            output_specs: List of (name, Socket, config) tuples.
            widget_specs: Optional UI widget definitions.
            metadata: Optional node metadata.

        Returns:
            Configured SchemaNode instance.
        """
        inputs = [
            {"name": n, **sock.to_dict(), **cfg}
            for n, sock, cfg in input_specs
        ]
        outputs = [
            {"name": n, **sock.to_dict(), **cfg}
            for n, sock, cfg in output_specs
        ]
        return SchemaNode(
            name=name,
            category=category,
            inputs=inputs,
            outputs=outputs,
            widgets=widget_specs or [],
            metadata=metadata or {},
        )


# ── BioNodulo Extension ────────────────────────────────────────────

@dataclass
class BioNoduloExtension:
    """ComfyUI v3 extension metadata for BioNodulo.

    Registers BioNodulo as a ComfyUI v3 extension with custom node types.
    """

    name: str = "bionodulo"
    version: str = "Alpha 1.0"
    display_name: str = "BioNodulo"
    description: str = "Visual bioinformatics pipelines, node by node."
    author: str = "BioNodulo Team"
    node_modules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "display_name": self.display_name,
            "description": self.description,
            "author": self.author,
            "node_modules": self.node_modules,
        }


# Convenience module aliases for ComfyUI-style imports
class io:
    """I/O socket type constructors."""
    String = StringSocket
    Int = IntSocket
    Float = FloatSocket
    Boolean = BooleanSocket
    FASTQ = FASTQSocket
    FASTA = FASTASocket
    BAM = BAMSocket
    VCF = VCF_SOCKET


class ui:
    """UI widget constructors for node parameter widgets."""

    @staticmethod
    def slider(
        name: str,
        min_val: float = 0,
        max_val: float = 100,
        default: float = 0,
        step: float = 1,
    ) -> dict[str, Any]:
        return {
            "type": "slider",
            "name": name,
            "min": min_val,
            "max": max_val,
            "default": default,
            "step": step,
        }

    @staticmethod
    def text(name: str, default: str = "", placeholder: str = "") -> dict[str, Any]:
        return {
            "type": "text",
            "name": name,
            "default": default,
            "placeholder": placeholder,
        }

    @staticmethod
    def boolean(name: str, default: bool = False) -> dict[str, Any]:
        return {
            "type": "boolean",
            "name": name,
            "default": default,
        }

    @staticmethod
    def dropdown(
        name: str,
        options: list[str],
        default: str | None = None,
    ) -> dict[str, Any]:
        return {
            "type": "dropdown",
            "name": name,
            "options": options,
            "default": default or (options[0] if options else None),
        }

    @staticmethod
    def file_picker(
        name: str,
        accept: str = "*",
        directory: bool = False,
    ) -> dict[str, Any]:
        return {
            "type": "file_picker",
            "name": name,
            "accept": accept,
            "directory": directory,
        }
