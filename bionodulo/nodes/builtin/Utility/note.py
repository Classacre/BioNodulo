"""note — Utility node(s). One tool per file (extracted from utils.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class NoteNode(CommandNode):
    """A text note node for workflow annotations."""
    NODE_ID = 'note'
    DISPLAY_NAME = 'Notes'
    CATEGORY = 'Utility'
    DESCRIPTION = 'Add a text note or annotation to the workflow'
    SEARCH_ALIASES = ['notes', 'note', 'text', 'comment', 'description', 'annotation']
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = False
    VISUAL_ONLY = True
    COMMAND = []

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'text': ('STRING', {'default': '', 'multiline': True, 'description': 'Note text content'})}}

    async def run(self, **kwargs: Any) -> tuple:
        return ()
