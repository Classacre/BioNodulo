"""Image preview sink contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import PythonUtilityNode, path_value, validate_regular_file


IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"})


class ImagePreviewNode(PythonUtilityNode):
    """Validate and register one regular image file as a visual sink."""

    NODE_ID = "image_preview"
    DISPLAY_NAME = "Image Preview"
    DESCRIPTION = "Preview an image file directly in the workflow canvas"
    SEARCH_ALIASES = ["image", "preview", "plot", "png", "jpg", "display"]
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    OUTPUT_NODE = True
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/pathlib.html"
    UPSTREAM_SOURCE = "Lib/pathlib.py"
    _IMAGE_EXTS = set(IMAGE_EXTENSIONS)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {"required": {"file": ("FILE", {"label": "Image File", "description": "Path to an image file"})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        return validate_regular_file(
            inputs.get("file"), extensions=IMAGE_EXTENSIONS, label="Image file"
        )

    async def run(self, **kwargs: Any) -> tuple[()]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        path = Path(path_value(kwargs["file"]))
        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(path, label="Image Preview")
        return ()
