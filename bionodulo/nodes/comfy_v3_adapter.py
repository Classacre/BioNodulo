from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode


class NumberDisplay:
    slider = "slider"
    number = "number"


@dataclass
class _Socket:
    name: str
    type: str
    default: Any = None
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    description: str = ""
    display_name: str | None = None
    display_mode: str | None = None
    multiline: bool = False

    def options(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key in ("default", "min", "max", "step", "description"):
            value = getattr(self, key)
            if value not in (None, ""):
                result[key] = value
        if self.display_mode:
            result["widget"] = self.display_mode
        if self.multiline:
            result["multiline"] = True
            result.setdefault("widget", "textarea")
        if self.display_name:
            result["display_name"] = self.display_name
        if self.description:
            result["tooltip"] = self.description
        return result


class _TypedSocket:
    type_name = "STRING"

    @classmethod
    def Input(cls, name: str, **kwargs: Any) -> _Socket:  # noqa: N802 - mirrors Comfy API naming
        return _Socket(name=name, type=cls.type_name, **_normalize_kwargs(kwargs))

    @classmethod
    def Output(cls, name: str | None = None, **kwargs: Any) -> _Socket:  # noqa: N802
        return _Socket(name=name or kwargs.get("display_name") or cls.type_name.lower(), type=cls.type_name, **_normalize_kwargs(kwargs))


class String(_TypedSocket):
    type_name = "STRING"


class Int(_TypedSocket):
    type_name = "INT"


class Boolean(_TypedSocket):
    type_name = "BOOLEAN"


@dataclass
class Schema:
    node_id: str
    display_name: str = ""
    category: str = "example"
    description: str = ""
    inputs: list[_Socket] = field(default_factory=list)
    outputs: list[_Socket] = field(default_factory=list)
    is_output_node: bool = False


class NodeOutput:
    def __init__(self, *values: Any, ui: Any | None = None, **named_values: Any) -> None:
        self.values = values
        self.named_values = named_values
        self.ui = ui


class SchemaNode:
    @classmethod
    def define_schema(cls) -> Schema:
        raise NotImplementedError


class BioNoduloExtension:
    async def get_node_list(self) -> list[type[SchemaNode]]:
        return []


ComfyNode = SchemaNode
ComfyExtension = BioNoduloExtension


class _PreviewUI:
    @staticmethod
    def Text(path: str, *, label: str = "Preview") -> dict[str, Any]:  # noqa: N802
        return {"type": "text_preview", "path": path, "label": label}


class _IoNamespace:
    SchemaNode = SchemaNode
    ComfyNode = SchemaNode
    Schema = Schema
    NodeOutput = NodeOutput
    String = String
    Int = Int
    Boolean = Boolean
    NumberDisplay = NumberDisplay


class _UiNamespace:
    PreviewText = staticmethod(_PreviewUI.Text)


io = _IoNamespace()
ui = _UiNamespace()


def adapt_comfy_v3_node(node_cls: type) -> type[BaseNode] | None:
    if not callable(getattr(node_cls, "define_schema", None)) or not callable(getattr(node_cls, "execute", None)):
        return None
    try:
        schema = node_cls.define_schema()
    except Exception:
        return None

    inputs = _schema_inputs(schema)
    outputs = _schema_outputs(schema)

    class AdaptedComfyNode(BaseNode):
        NODE_ID = _attr(schema, "node_id", node_cls.__name__)
        DISPLAY_NAME = _attr(schema, "display_name", NODE_ID)
        CATEGORY = _attr(schema, "category", "example")
        DESCRIPTION = _attr(schema, "description", "")
        RETURN_TYPES = tuple(output.type for output in outputs)
        RETURN_NAMES = tuple(output.name for output in outputs)
        FUNCTION = "execute"
        OUTPUT_NODE = bool(_attr(schema, "is_output_node", False))
        VERSION = "comfy-v3"
        COMFY_V3_CLASS = node_cls

        @classmethod
        def INPUT_TYPES(cls) -> dict:
            return {"required": {item.name: (item.type, item.options()) for item in inputs}, "optional": {}, "hidden": {}}

        @classmethod
        def PLAN_OUTPUTS(cls, node_dir: Path, params: dict[str, Any], resolved_inputs: dict[str, Any]) -> dict[str, Any]:
            output_dir = Path(params.get("output_dir") or resolved_inputs.get("output_dir") or node_dir)
            names = [output.name for output in outputs]
            return {name: str(output_dir / f"{name}.txt") for name in names}

        def run(self, context: Any = None, **kwargs: Any) -> dict[str, Any]:
            if context is not None:
                kwargs.setdefault("output_dir", str(context.node_dir))
            result = node_cls.execute(**kwargs)
            return _node_output_to_dict(result, outputs)

    AdaptedComfyNode.__name__ = f"{node_cls.__name__}BioNoduloAdapter"
    return AdaptedComfyNode


def _normalize_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    if "display_mode" in kwargs and not isinstance(kwargs["display_mode"], str):
        kwargs["display_mode"] = str(kwargs["display_mode"])
    return kwargs


def _schema_inputs(schema: Any) -> list[_Socket]:
    return [_coerce_socket(item, fallback_name=f"input_{index}") for index, item in enumerate(_attr(schema, "inputs", []) or [])]


def _schema_outputs(schema: Any) -> list[_Socket]:
    return [_coerce_socket(item, fallback_name=f"output_{index}") for index, item in enumerate(_attr(schema, "outputs", []) or [])]


def _coerce_socket(item: Any, *, fallback_name: str) -> _Socket:
    if isinstance(item, _Socket):
        return item
    return _Socket(
        name=_attr(item, "name", _attr(item, "display_name", fallback_name)),
        type=_attr(item, "type", _attr(item, "io_type", "STRING")),
        default=_attr(item, "default", None),
        min=_attr(item, "min", None),
        max=_attr(item, "max", None),
        step=_attr(item, "step", None),
        description=_attr(item, "description", ""),
        display_name=_attr(item, "display_name", None),
        display_mode=_attr(item, "display_mode", None),
        multiline=bool(_attr(item, "multiline", False)),
    )


def _node_output_to_dict(result: Any, outputs: list[_Socket]) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    if isinstance(result, NodeOutput):
        if result.named_values:
            return dict(result.named_values)
        return {output.name: value for output, value in zip(outputs, result.values, strict=False)}
    if isinstance(result, tuple):
        return {output.name: value for output, value in zip(outputs, result, strict=False)}
    if len(outputs) == 1:
        return {outputs[0].name: result}
    return {}


def _attr(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)
