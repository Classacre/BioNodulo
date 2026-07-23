"""Focused owner for ``mash_paste``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.comparative_genomics_family.contracts import ToolsIUCCommandContract

class MashPasteNode(ToolsIUCCommandContract):
    """Create a single Mash sketch file from multiple sketch files."""

    NODE_ID = "mash_paste"
    DISPLAY_NAME = "Mash Paste"
    REQUIRED_CONDA_PACKAGES = ["mash"]
    CATEGORY = "genomics"
    DESCRIPTION = "Create a single Mash sketch file from multiple Mash sketch files."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "mash", "mash paste", "minhash", "sketch merge", "merge sketches", "msh"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("sketch",)
    REQUIRED_EXECUTABLES = ["mash"]
    DOCUMENTATION_URL = "https://mash.readthedocs.io/en/latest/sketches.html"
    CITATION_DOIS = ["10.1186/s13059-016-0997-x"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s13059-016-0997-x"]
    CITATION_TEXT = "Mash: fast genome and metagenome distance estimation using MinHash."
    VERSION = "2.3"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        sketch_files = _as_list(inputs.get("msh_files"))
        linked_files = [_safe_name(path) for path in sketch_files]
        link_commands = [
            f"ln -sf {shlex.quote(path)} {shlex.quote(linked)}"
            for path, linked in zip(sketch_files, linked_files, strict=False)
        ]
        cmd = ["mash", "paste", f"{out}/sketch", *linked_files]
        return " && ".join([*link_commands, shlex.join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "sketch.msh"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        sketches = _as_list(inputs.get("msh_files"))
        if not sketches or any(not str(path).strip() for path in sketches):
            return "At least one Mash sketch is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "msh_files": ("FILE", {"list": True, "description": "Mash sketch files to merge"}),
            },
            "hidden": {"output": ("STRING", {})},
        }
