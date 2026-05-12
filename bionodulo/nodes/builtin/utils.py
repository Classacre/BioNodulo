"""Utility nodes for BioNodulo workflows.

Provides generic command execution, file viewing, file collection,
and VCF merging utilities.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class GenericCommandNode(CommandNode):
    """Execute an arbitrary shell command."""
    NODE_ID = "generic_command"
    DISPLAY_NAME = "Shell Command"
    CATEGORY = "utils"
    DESCRIPTION = "Run any custom shell command"
    SEARCH_ALIASES = ["shell", "command", "bash", "custom", "script"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    REQUIRES_EXTERNAL_TOOLS = False
    SHELL = True
    COMMAND = ["{inputs.command}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "command": ("STRING", {"description": "Shell command to execute", "multiline": True}),
            },
            "optional": {
                "working_dir": ("DIRECTORY", {"description": "Working directory"}),
                "timeout": ("INT", {"default": 3600, "min": 1, "description": "Timeout in seconds"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return [str(inputs.get("command", ""))]


class ViewTextFileNode(CommandNode):
    """Mark a text file as a workflow output for viewing."""
    NODE_ID = "view_text_file"
    DISPLAY_NAME = "View Text File"
    CATEGORY = "utils"
    DESCRIPTION = "Display a text file as a workflow output"
    SEARCH_ALIASES = ["view", "display", "cat", "text", "output"]
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("content",)
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = True
    COMMAND = ["cat", "{inputs.file}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"description": "Text file to display"}),
            },
            "optional": {
                "max_lines": ("INT", {"default": 1000, "min": 1, "description": "Maximum lines to display"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple:
        """Override to read and return file contents directly."""
        file_path = kwargs.get("file")
        max_lines = kwargs.get("max_lines", 1000)
        if not file_path:
            return ("No file provided",)
        try:
            with open(file_path) as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"... ({max_lines} lines shown)")
                        break
                    lines.append(line.rstrip())
                return ("\n".join(lines),)
        except Exception as exc:
            return (f"Error reading file: {exc}",)


class CollectFilesNode(CommandNode):
    """Collect multiple files/directories into a single directory."""
    NODE_ID = "collect_files"
    DISPLAY_NAME = "Collect Files"
    CATEGORY = "utils"
    DESCRIPTION = "Gather multiple files or directories into a single output directory"
    SEARCH_ALIASES = ["collect", "gather", "merge", "directory"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("output_dir",)
    REQUIRES_EXTERNAL_TOOLS = False
    COMMAND = []

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "files": ("FILE", {"description": "Files or directories to collect"}),
            },
            "optional": {
                "output_name": ("STRING", {"default": "collected"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return ["echo", "collect_files: no external command needed"]

    async def run(self, **kwargs: Any) -> tuple:
        """Override to handle file collection in Python."""
        import shutil
        files = kwargs.get("files", [])
        output_name = kwargs.get("output_name", "collected")
        output_dir = kwargs.get("_output_dir", ".")
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


class MergeVCFNode(CommandNode):
    """Merge multiple VCF files with bcftools."""
    NODE_ID = "merge_vcf"
    DISPLAY_NAME = "Merge VCF"
    CATEGORY = "utils"
    DESCRIPTION = "Merge multiple VCF/BCF files into one"
    SEARCH_ALIASES = ["merge", "vcf", "combine", "bcftools merge"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("merged_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/bcftools.html"
    VERSION = "1.20"
    COMMAND = [
        "bcftools", "merge",
        "-Oz",
        "-o", "{output}/merged.vcf.gz",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcfs": ("VCF_GZ", {"description": "List of VCF.gz files to merge"}),
            },
            "optional": {
                "force_samples": ("BOOLEAN", {"default": True}),
                "merge": ("STRING", {"default": "both", "description": "snps, indels, both, all, none"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        vcfs = inputs.get("vcfs", [])
        if isinstance(vcfs, str):
            vcfs = [vcfs]
        cmd = [
            "bcftools", "merge",
            "-Oz",
            "-o", f"{inputs.get('output', '.')}/merged.vcf.gz",
        ]
        if inputs.get("force_samples"):
            cmd.append("--force-samples")
        if inputs.get("merge"):
            cmd.extend(["-m", str(inputs["merge"])])
        cmd.extend(list(vcfs))
        return cmd


class RerouteNode(CommandNode):
    """A pass-through node for routing connections cleanly."""
    NODE_ID = "reroute"
    DISPLAY_NAME = "Reroute"
    CATEGORY = "Utility"
    DESCRIPTION = "Pass a connection through a routing point"
    SEARCH_ALIASES = ["reroute", "pass", "through", "junction", "connection"]
    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("output",)
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = False
    COMMAND = []

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("*", {"description": "Any input type"}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple:
        return (kwargs.get("input"),)


class NoteNode(CommandNode):
    """A text note node for workflow annotations."""
    NODE_ID = "note"
    DISPLAY_NAME = "Notes"
    CATEGORY = "Utility"
    DESCRIPTION = "Add a text note or annotation to the workflow"
    SEARCH_ALIASES = ["notes", "note", "text", "comment", "description", "annotation"]
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    REQUIRES_EXTERNAL_TOOLS = False
    OUTPUT_NODE = False
    COMMAND = []

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "text": ("STRING", {"default": "", "multiline": True, "description": "Note text content"}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple:
        return ()
