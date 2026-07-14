"""generic — utils node(s). One tool per file (extracted from utils.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class GenericCommandNode(CommandNode):
    """Execute an arbitrary shell command."""
    NODE_ID = 'generic_command'
    DISPLAY_NAME = 'Shell Command'
    CATEGORY = 'utils'
    DESCRIPTION = 'Run any custom shell command'
    SEARCH_ALIASES = ['shell', 'command', 'bash', 'custom', 'script']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('output',)
    REQUIRES_EXTERNAL_TOOLS = False
    SHELL = True
    COMMAND = ['{inputs.command}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'command': ('STRING', {'description': 'Shell command to execute', 'multiline': True})}, 'optional': {'working_dir': ('DIRECTORY', {'description': 'Working directory'}), 'timeout': ('INT', {'default': 3600, 'min': 1, 'description': 'Timeout in seconds'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('command', ''))
