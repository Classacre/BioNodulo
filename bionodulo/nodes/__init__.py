"""BioNodulo nodes package.

Provides the core node system including base classes, type system,
registry, schema helpers, and built-in bioinformatics nodes.
"""
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from bionodulo.nodes.base import BaseNode
    from bionodulo.nodes.command_node import CommandNode
    from bionodulo.nodes.registry import NodeRegistry
    from bionodulo.nodes.schema_api import io, ui

__all__ = [
    "BaseNode",
    "CommandNode",
    "NodeRegistry",
    "io",
    "ui",
]


def __getattr__(name: str) -> Any:
    if name == "BaseNode":
        from bionodulo.nodes.base import BaseNode

        value = BaseNode
    elif name == "CommandNode":
        from bionodulo.nodes.command_node import CommandNode

        value = CommandNode
    elif name == "NodeRegistry":
        from bionodulo.nodes.registry import NodeRegistry

        value = NodeRegistry
    elif name == "io":
        from bionodulo.nodes.schema_api import io

        value = io
    elif name == "ui":
        from bionodulo.nodes.schema_api import ui

        value = ui
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    globals()[name] = value
    return value
