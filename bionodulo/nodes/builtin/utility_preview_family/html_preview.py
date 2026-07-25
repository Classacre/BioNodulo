"""HTML preview sink contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import PythonUtilityNode, path_value, validate_regular_file


HTML_EXTENSIONS = frozenset({".html", ".htm"})


class HtmlPreviewNode(PythonUtilityNode):
    """Validate and register one regular HTML file as a visual sink."""

    NODE_ID = "html_preview"
    DISPLAY_NAME = "HTML Preview"
    DESCRIPTION = "Preview an HTML report directly in the workflow canvas"
    SEARCH_ALIASES = ["html", "report", "preview", "multiqc", "fastqc", "viewer"]
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    OUTPUT_NODE = True
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/pathlib.html"
    UPSTREAM_SOURCE = "Lib/pathlib.py"
    _HTML_EXTS = set(HTML_EXTENSIONS)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {"required": {"file": ("FILE", {"label": "HTML File", "description": "Path to an HTML report file"})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        return validate_regular_file(inputs.get("file"), extensions=HTML_EXTENSIONS, label="HTML file")

    async def run(self, **kwargs: Any) -> tuple[()]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        path = Path(path_value(kwargs["file"]))
        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(path, label="HTML Preview")
        return ()
