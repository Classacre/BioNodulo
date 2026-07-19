"""UCSC chain anti-repeat node."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_beacon_ucsc_family.adapter import (
    KENT_482_GIT_COMMIT,
    KENT_GIT_URL,
    pin_contract,
)

class UcscChainAntiRepeatNode(CommandNode):
    """Remove repeat-dominated UCSC chains."""

    NODE_ID = "ucsc_chainantirepeat"
    DISPLAY_NAME = "chainAntiRepeat"
    REQUIRED_CONDA_PACKAGES = ["ucsc-chainantirepeat"]
    CATEGORY = "genomics"
    DESCRIPTION = "Remove UCSC chains that primarily represent repeats or degenerate DNA."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_chainantirepeat",
        "chainAntiRepeat",
        "UCSC chain",
        "twoBit",
        "repeat chains",
        "degenerate DNA",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["chainAntiRepeat"]
    DOCUMENTATION_URL = "https://genome.ucsc.edu/goldenPath/help/chain.html"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.chain"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "chainAntiRepeat",
            str(inputs.get("in_target", "")),
            str(inputs.get("in_query", "")),
            str(inputs.get("in_chain", "")),
            cls._output_path(inputs),
        ]
        if str(inputs.get("minScore", "")) != "":
            cmd.append(f"-minScore={inputs.get('minScore')}")
        if str(inputs.get("noCheckScore", "")) != "":
            cmd.append(f"-noCheckScore={inputs.get('noCheckScore')}")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.chain"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("in_target", "in_query", "in_chain"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"
        for name in ("minScore", "noCheckScore"):
            value = inputs.get(name, "")
            if str(value) != "" and int(value) < 0:
                return f"{name} must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_target": ("FILE", {"description": "TwoBit file containing the target sequence"}),
                "in_query": ("FILE", {"description": "TwoBit file containing the query sequence"}),
                "in_chain": ("FILE", {"description": "UCSC chain file to filter"}),
            },
            "optional": {
                "minScore": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum post-repeat score required to pass"},
                ),
                "noCheckScore": (
                    "INT",
                    {"default": "", "min": 0, "description": "Score threshold that passes chains without repeat checks"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(
    [UcscChainAntiRepeatNode],
    runtime_version="482",
    runtime_git_url=KENT_GIT_URL,
    runtime_git_commit=KENT_482_GIT_COMMIT,
    package_constraint="ucsc-chainantirepeat==482",
)
