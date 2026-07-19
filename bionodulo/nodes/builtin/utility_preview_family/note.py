"""Product-native visual workflow annotation node."""

from __future__ import annotations

from typing import Any

from .adapter import PythonUtilityNode


class NoteNode(PythonUtilityNode):
    """Retain annotation text in the workflow without runtime outputs."""

    NODE_ID = "note"
    DISPLAY_NAME = "Notes"
    DESCRIPTION = "Add a text note or annotation to the workflow"
    SEARCH_ALIASES = ["notes", "note", "text", "comment", "description", "annotation"]
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    VISUAL_ONLY = True
    VERSION = "1.0.0"
    UPSTREAM_SOURCE = "BioNodulo native workflow representation"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "text": ("STRING", {"default": "", "multiline": True, "description": "Note text content"}),
            }
        }

    async def run(self, **kwargs: Any) -> tuple[()]:
        return ()
