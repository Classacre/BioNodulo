"""image — Utility node(s). One tool per file (extracted from utils.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class ImagePreviewNode(CommandNode):
    """Display an image file inline in the canvas — a visual sink node."""
    NODE_ID = 'image_preview'
    DISPLAY_NAME = 'Image Preview'
    CATEGORY = 'Utility'
    DESCRIPTION = 'Preview an image file directly in the workflow canvas'
    SEARCH_ALIASES = ['image', 'preview', 'plot', 'png', 'jpg', 'display']
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = True
    COMMAND = []
    _IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg'}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'file': ('FILE', {'label': 'Image File', 'description': 'Path to an image file'})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        file_path = inputs.get('file')
        if not file_path:
            return "Required input 'file' is missing"
        path = Path(str(file_path))
        if path.suffix.lower() not in cls._IMAGE_EXTS:
            return f"File must be an image ({', '.join(cls._IMAGE_EXTS)}), got: {path.suffix}"
        if not path.exists():
            return f'Image file not found: {file_path}'
        return True

    async def run(self, **kwargs: Any) -> tuple:
        file_path = kwargs.get('file')
        context = kwargs.pop('context', None)
        if context is not None and hasattr(context, 'register_preview'):
            context.register_preview(Path(str(file_path or '.')), label='Image Preview')
        return ()
