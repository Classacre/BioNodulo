"""collect — utils node(s). One tool per file (extracted from utils.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class CollectFilesNode(CommandNode):
    """Collect multiple files/directories into a single directory."""
    NODE_ID = 'collect_files'
    DISPLAY_NAME = 'Collect Files'
    CATEGORY = 'utils'
    DESCRIPTION = 'Gather multiple files or directories into a single output directory'
    SEARCH_ALIASES = ['collect', 'gather', 'merge', 'directory']
    RETURN_TYPES = ('DIRECTORY',)
    RETURN_NAMES = ('output_dir',)
    REQUIRES_EXTERNAL_TOOLS = False
    COMMAND = []

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'files': ('FILE', {'description': 'Files or directories to collect'})}, 'optional': {'output_name': ('STRING', {'default': 'collected'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return ['echo', 'collect_files: no external command needed']

    async def run(self, **kwargs: Any) -> tuple:
        """Override to handle file collection in Python."""
        import shutil
        files = kwargs.get('files', [])
        output_name = kwargs.get('output_name', 'collected')
        context = kwargs.pop('context', None)
        output_dir = getattr(context, 'node_dir', '.') if context else '.'
        out = Path(output_dir) / output_name
        out.mkdir(parents=True, exist_ok=True)
        if isinstance(files, str):
            files = [files]
        for f in files:
            src = Path(f)
            if src.is_dir():
                dst = out / src.name
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            elif src.is_file():
                shutil.copy2(src, out / src.name)
        return (str(out),)
