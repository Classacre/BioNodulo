"""ComfyUI v3 adapter - converts Comfy v3 nodes to BioNodulo BaseNodes.

Provides bidirectional conversion between ComfyUI v3 schema nodes and
BioNodulo native node classes.
"""
from __future__ import annotations

from typing import Any, Callable, Optional, Type

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode
from bionodulo.nodes.schema_api import SchemaNode, Socket


def adapt_comfy_v3_node(schema: SchemaNode) -> Type[BaseNode]:
    """Convert a ComfyUI v3 SchemaNode to a BioNodulo BaseNode subclass.

    Dynamically creates a new BaseNode subclass that wraps the schema node
    execution logic while exposing BioNodulo-compatible metadata.

    Args:
        schema: The ComfyUI v3 SchemaNode to adapt.

    Returns:
        A new BaseNode subclass.
    """
    # Extract input/output types from schema
    input_types_dict: dict[str, dict[str, Any]] = {
        "required": {}, "optional": {}, "hidden": {}
    }
    return_types: list[str] = []
    return_names: list[str] = []

    for inp in schema.inputs:
        name = inp["name"]
        sock_type = inp.get("type", "STRING")
        config = {k: v for k, v in inp.items() if k not in ("name", "type", "tooltip")}
        # Determine if required based on config
        category = "required" if config.pop("required", True) else "optional"
        input_types_dict[category][name] = (sock_type, config)

    for out in schema.outputs:
        return_types.append(out.get("type", "STRING"))
        return_names.append(out["name"])

    # Build execute wrapper
    execute_fn = schema.execute

    async def _run(self: Any, **kwargs: Any) -> tuple:
        if execute_fn is not None:
            result = execute_fn(**kwargs)
            # Handle async execute functions
            if hasattr(result, "__await__"):
                result = await result
            if isinstance(result, dict):
                return tuple(result.get(n) for n in return_names)
            if isinstance(result, (list, tuple)):
                return tuple(result)
            return (result,)
        return tuple(None for _ in return_types)

    # Build return type tuple
    ret_types = tuple(return_types) if return_types else ()
    ret_names = tuple(return_names) if return_names else ()

    # Create dynamic class
    class_dict: dict[str, Any] = {
        "NODE_ID": schema.name.lower().replace(" ", "_").replace("-", "_"),
        "DISPLAY_NAME": schema.metadata.get("display_name", schema.name),
        "CATEGORY": schema.category,
        "DESCRIPTION": schema.metadata.get("description", ""),
        "RETURN_TYPES": ret_types,
        "RETURN_NAMES": ret_names,
        "INPUT_TYPES": classmethod(lambda cls: dict(input_types_dict)),
        "run": _run,
    }

    # Add optional metadata
    if "search_aliases" in schema.metadata:
        class_dict["SEARCH_ALIASES"] = schema.metadata["search_aliases"]
    if "documentation_url" in schema.metadata:
        class_dict["DOCUMENTATION_URL"] = schema.metadata["documentation_url"]
    if "version" in schema.metadata:
        class_dict["VERSION"] = schema.metadata["version"]

    adapted_class = type(
        f"Adapted_{schema.name}",
        (BaseNode,),
        class_dict,
    )

    # Attach reference back
    adapted_class._comfy_v3_schema = schema  # type: ignore[attr-defined]

    return adapted_class


def bionodulo_to_comfy_schema(node_class: Type[BaseNode]) -> SchemaNode:
    """Convert a BioNodulo BaseNode to a ComfyUI v3 SchemaNode.

    Args:
        node_class: A BioNodulo BaseNode subclass.

    Returns:
        Equivalent ComfyUI v3 SchemaNode.
    """
    from bionodulo.nodes.schema_api import io

    input_specs: list[tuple[str, Socket, dict[str, Any]]] = []
    output_specs: list[tuple[str, Socket, dict[str, Any]]] = []

    input_types = node_class.INPUT_TYPES()
    type_to_socket: dict[str, Callable[[str], Socket]] = {
        "STRING": io.String,
        "INT": io.Int,
        "FLOAT": io.Float,
        "BOOLEAN": io.Boolean,
        "FASTQ": io.FASTQ,
        "FASTA": io.FASTA,
        "BAM": io.BAM,
        "VCF": io.VCF,
    }

    for category in ("required", "optional", "hidden"):
        for name, spec in input_types.get(category, {}).items():
            type_name = spec[0] if isinstance(spec, (list, tuple)) else spec
            config = spec[1] if isinstance(spec, (list, tuple)) and len(spec) > 1 else {}
            socket_factory = type_to_socket.get(type_name, io.String)
            cfg = dict(config)
            if category == "required":
                cfg["required"] = True
            else:
                cfg["required"] = False
            input_specs.append((name, socket_factory(""), cfg))

    for i, ret_type in enumerate(node_class.RETURN_TYPES):
        name = (
            node_class.RETURN_NAMES[i]
            if i < len(node_class.RETURN_NAMES)
            else f"output_{i}"
        )
        socket_factory = type_to_socket.get(ret_type, io.String)
        output_specs.append((name, socket_factory(""), {}))

    return SchemaNode.define_schema(
        name=node_class.DISPLAY_NAME or node_class.NODE_ID,
        category=node_class.CATEGORY,
        input_specs=input_specs,
        output_specs=output_specs,
        metadata={
            "display_name": node_class.DISPLAY_NAME,
            "description": node_class.DESCRIPTION,
            "search_aliases": node_class.SEARCH_ALIASES,
            "documentation_url": node_class.DOCUMENTATION_URL,
            "version": node_class.VERSION,
            "node_id": node_class.NODE_ID,
        },
    )
