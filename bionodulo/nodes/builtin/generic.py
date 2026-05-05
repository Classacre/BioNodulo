from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode


class GenericCommandNode(CommandNode):
    NODE_ID = "generic_command"
    DISPLAY_NAME = "Generic Command"
    CATEGORY = "Utility"
    DESCRIPTION = "Run a simple user-specified command. Useful for prototyping."
    SEARCH_ALIASES = ["shell", "command", "cli", "custom"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("output_dir",)
    REQUIRED_EXECUTABLES = []
    COMMAND = ["{params.command}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {}, "optional": {"command": ("STRING", {"default": "echo hello"})}, "hidden": {}}

    @classmethod
    def render_command(cls, *, inputs: dict[str, Any], outputs: dict[str, Any], params: dict[str, Any]) -> list[str]:
        import shlex

        return shlex.split(str(params.get("command", "echo hello")))

    @classmethod
    def PLAN_OUTPUTS(cls, node_dir: Path, params: dict, inputs: dict) -> dict:
        return {"output_dir": str(node_dir / "generic_command")}


class ViewTextFileNode(BaseNode):
    NODE_ID = "view_text_file"
    DISPLAY_NAME = "View Text File"
    CATEGORY = "Utility"
    DESCRIPTION = "Mark a text file as an inspectable workflow output."
    SEARCH_ALIASES = ["view", "text", "log", "inspect"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("file",)
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {"file": ("FILE", {})}, "optional": {}, "hidden": {}}

    def run(self, context: Any = None, **kwargs: Any) -> dict[str, Any]:
        return {"file": kwargs.get("file")}


class CollectFilesNode(BaseNode):
    NODE_ID = "collect_files"
    DISPLAY_NAME = "Collect Files"
    CATEGORY = "Utility"
    DESCRIPTION = "Collect up to three files or report directories into one run-local directory."
    SEARCH_ALIASES = ["collect", "merge", "reports", "files", "directory"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("directory",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {"first": ("DIRECTORY", {})},
            "optional": {"second": ("DIRECTORY", {}), "third": ("DIRECTORY", {})},
            "hidden": {},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, node_dir: Path, params: dict, inputs: dict) -> dict:
        return {"directory": str(node_dir / "collected")}

    def run(self, context: Any = None, **kwargs: Any) -> dict[str, Any]:
        if context is None:
            raise RuntimeError("CollectFilesNode requires context")
        outputs = context.planned_outputs()
        output_dir = Path(outputs["directory"])
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest = output_dir / "manifest.txt"
        manifest.write_text("\n".join(str(value) for value in kwargs.values() if value) + "\n", encoding="utf-8")
        return outputs
