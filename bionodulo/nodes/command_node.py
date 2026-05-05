from __future__ import annotations

import re
from typing import Any, ClassVar

from bionodulo.nodes.base import BaseNode


_TOKEN_RE = re.compile(r"\{([^{}]+)\}")


class AttrDict(dict):
    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


def render_template(value: str, *, inputs: dict[str, Any], outputs: dict[str, Any], params: dict[str, Any]) -> str:
    namespace = {
        "inputs": AttrDict(inputs),
        "outputs": AttrDict(outputs),
        "params": AttrDict(params),
    }

    def replace(match: re.Match[str]) -> str:
        expression = match.group(1)
        try:
            resolved = eval(expression, {"__builtins__": {}}, namespace)  # noqa: S307 - constrained command templating
        except Exception as exc:
            raise ValueError(f"Could not render {{{expression}}}: {exc}") from exc
        return str(resolved)

    return _TOKEN_RE.sub(replace, value)


class CommandNode(BaseNode):
    COMMAND: ClassVar[list[str]] = []
    REQUIRES_EXTERNAL_TOOLS: ClassVar[bool] = True

    @classmethod
    def render_command(cls, *, inputs: dict[str, Any], outputs: dict[str, Any], params: dict[str, Any]) -> list[str]:
        return [
            render_template(part, inputs=inputs, outputs=outputs, params=params)
            for part in cls.COMMAND
        ]

    async def run(self, context: Any = None, **kwargs: Any) -> dict[str, Any]:
        if context is None:
            raise RuntimeError("CommandNode requires an execution context")
        params = dict(context.params)
        inputs = dict(kwargs)
        outputs = context.planned_outputs()
        command = self.render_command(inputs=inputs, outputs=outputs, params=params)
        return await context.run_command(command=command, outputs=outputs)
