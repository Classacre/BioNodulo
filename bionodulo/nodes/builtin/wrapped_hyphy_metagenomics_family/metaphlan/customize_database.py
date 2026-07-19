"""Focused owner for ``customize_metaphlan_database``."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from ..contracts import ToolsIUCCommandContract

class CustomizeMetaPhlAnDatabaseNode(ToolsIUCCommandContract):
    """Customize marker sequences and metadata for a MetaPhlAn database."""

    NODE_ID = "customize_metaphlan_database"
    DISPLAY_NAME = "Customize MetaPhlAn DB"
    REQUIRED_CONDA_PACKAGES = ["metaphlan", "seqtk"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Add, remove, or keep marker sequences and marker metadata for a custom MetaPhlAn database."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "MetaPhlAn",
        "customizemetadata.py",
        "add marker",
        "remove markers",
        "keep markers",
        "seqtk subseq",
    ]
    RETURN_TYPES = ("FASTA", "JSON")
    RETURN_NAMES = ("out_fasta", "out_json")
    REQUIRED_EXECUTABLES = ["python", "seqtk"]
    DOCUMENTATION_URL = "https://github.com/biobakery/MetaPhlAn"
    CITATION_DOIS = [METAPHLAN_DOI]
    CITATION_URLS = [f"{DOI_URL}{METAPHLAN_DOI}"]
    CITATION_TEXT = METAPHLAN_CITATION_TEXT
    VERSION = "4.2.4"
    SHELL = True

    TAXONOMY_LIST_INPUTS = [
        "genome_lengths",
        "genbank_accessions",
        "kingdom_names",
        "kingdom_ids",
        "phylum_names",
        "phylum_ids",
        "class_names",
        "class_ids",
        "order_names",
        "order_ids",
        "family_names",
        "family_ids",
        "genus_names",
        "genus_ids",
        "species_names",
        "species_ids",
        "strain_names",
    ]

    TAXONOMY_FLAGS = [
        ("genome_lengths", "--g_length"),
        ("genbank_accessions", "--gca"),
        ("kingdom_names", "--k_name"),
        ("kingdom_ids", "--k_id"),
        ("phylum_names", "--p_name"),
        ("phylum_ids", "--p_id"),
        ("class_names", "--c_name"),
        ("class_ids", "--c_id"),
        ("order_names", "--o_name"),
        ("order_ids", "--o_id"),
        ("family_names", "--f_name"),
        ("family_ids", "--f_id"),
        ("genus_names", "--g_name"),
        ("genus_ids", "--g_id"),
        ("species_names", "--s_name"),
        ("species_ids", "--s_id"),
        ("strain_names", "--t_name"),
    ]

    @classmethod
    def _out_fasta(cls, out: str) -> str:
        return f"{out}/custom_marker_sequences.fasta"

    @classmethod
    def _out_json(cls, out: str) -> str:
        return f"{out}/custom_marker_metadata.json"

    @classmethod
    def _kept_markers(cls) -> str:
        return "kept_markers.txt"

    @classmethod
    def _script(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("customizemetadata_script", "customizemetadata.py"))

    @classmethod
    def _operation(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("operation", "add_marker"))

    @classmethod
    def _taxonomy_values(cls, inputs: dict[str, Any], key: str) -> list[str]:
        values = _as_list(inputs.get(key))
        if not values and key == "genbank_accessions":
            values = [""] * len(_as_list(inputs.get("genome_lengths")))
        return values

    @classmethod
    def _add_marker_command(cls, inputs: dict[str, Any], out: str) -> str:
        cmd = [
            "python",
            cls._script(inputs),
            "add_marker",
            "--in_json",
            str(inputs.get("marker_metadata", "")),
            "--out_json",
            cls._out_json(out),
            "--name",
            str(inputs.get("marker_name", "")),
            "--m_length",
            str(inputs.get("marker_length", "")),
        ]
        genome_count = len(_as_list(inputs.get("genome_lengths")))
        for index in range(genome_count):
            for key, flag in cls.TAXONOMY_FLAGS:
                cmd.extend([flag, cls._taxonomy_values(inputs, key)[index]])

        cat_cmd = [
            "cat",
            str(inputs.get("marker_sequences", "")),
            str(inputs.get("new_marker_sequences", "")),
        ]
        _add_shell_redirect(cat_cmd, cls._out_fasta(out))
        return f"{shlex.join(cmd)} && {_shell_join(cat_cmd)}"

    @classmethod
    def _remove_markers_command(cls, inputs: dict[str, Any], out: str) -> str:
        kept_markers = cls._kept_markers()
        cmd = [
            "python",
            cls._script(inputs),
            "remove_markers",
            "--in_json",
            str(inputs.get("marker_metadata", "")),
            "--markers",
            str(inputs.get("markers", "")),
            "--out_json",
            cls._out_json(out),
            "--kept_markers",
            kept_markers,
        ]
        seqtk_cmd = ["seqtk", "subseq", str(inputs.get("marker_sequences", "")), kept_markers]
        _add_shell_redirect(seqtk_cmd, cls._out_fasta(out))
        return f"{shlex.join(cmd)} && {_shell_join(seqtk_cmd)}"

    @classmethod
    def _keep_markers_command(cls, inputs: dict[str, Any], out: str) -> str:
        marker_list = str(inputs.get("markers", ""))
        cmd = [
            "python",
            cls._script(inputs),
            "keep_markers",
            "--in_json",
            str(inputs.get("marker_metadata", "")),
            "--markers",
            marker_list,
            "--out_json",
            cls._out_json(out),
        ]
        seqtk_cmd = ["seqtk", "subseq", str(inputs.get("marker_sequences", "")), marker_list]
        _add_shell_redirect(seqtk_cmd, cls._out_fasta(out))
        return f"{shlex.join(cmd)} && {_shell_join(seqtk_cmd)}"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for required_input in ("marker_sequences", "marker_metadata"):
            if inputs.get(required_input) is None:
                return f"Required input '{required_input}' is missing"
        operation = cls._operation(inputs)
        if operation not in {"add_marker", "remove_markers", "keep_markers"}:
            return "operation must be one of add_marker, remove_markers, or keep_markers"
        if operation == "add_marker":
            if not inputs.get("new_marker_sequences"):
                return "new_marker_sequences is required when adding a marker"
            if not inputs.get("marker_name"):
                return "marker_name is required when adding a marker"
            if not inputs.get("marker_length"):
                return "marker_length is required when adding a marker"
            genome_count = len(_as_list(inputs.get("genome_lengths")))
            if genome_count == 0:
                return "genome_lengths must contain at least one value when adding a marker"
            for key in cls.TAXONOMY_LIST_INPUTS:
                values = cls._taxonomy_values(inputs, key)
                if len(values) != genome_count:
                    return "Add-marker taxonomy fields must have the same number of values as genome_lengths"
        elif not inputs.get("markers"):
            return "markers is required when removing or keeping markers"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        operation = cls._operation(inputs)
        if operation == "add_marker":
            return cls._add_marker_command(inputs, out)
        if operation == "remove_markers":
            return cls._remove_markers_command(inputs, out)
        return cls._keep_markers_command(inputs, out)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "custom_marker_sequences.fasta", out / "custom_marker_metadata.json"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        taxonomy_description = "Repeat-list value aligned by index to genome_lengths for add_marker mode"
        return {
            "required": {
                "marker_sequences": ("FASTA", {"description": "Existing MetaPhlAn marker sequences FASTA"}),
                "marker_metadata": ("JSON", {"description": "Existing MetaPhlAn marker metadata JSON"}),
            },
            "optional": {
                "operation": (
                    "STRING",
                    {
                        "default": "add_marker",
                        "options": ["add_marker", "remove_markers", "keep_markers"],
                        "description": "Customization mode matching the Galaxy MetaPhlAn wrapper",
                    },
                ),
                "new_marker_sequences": (
                    "FASTA",
                    {"default": "", "description": "FASTA sequences for the new marker when operation is add_marker"},
                ),
                "marker_name": ("STRING", {"default": "", "description": "Name of the new marker"}),
                "marker_length": ("INT", {"default": 0, "min": 0, "description": "Length of the new marker"}),
                "markers": (
                    "TEXT",
                    {"default": "", "description": "Text or tabular file with one marker per line for remove/keep modes"},
                ),
                "genome_lengths": ("INT", {"default": [], "multiple": True, "description": taxonomy_description}),
                "genbank_accessions": ("STRING", {"default": [], "multiple": True, "description": taxonomy_description}),
                "kingdom_names": ("STRING", {"default": [], "multiple": True, "description": taxonomy_description}),
                "kingdom_ids": ("INT", {"default": [], "multiple": True, "description": taxonomy_description}),
                "phylum_names": ("STRING", {"default": [], "multiple": True, "description": taxonomy_description}),
                "phylum_ids": ("INT", {"default": [], "multiple": True, "description": taxonomy_description}),
                "class_names": ("STRING", {"default": [], "multiple": True, "description": taxonomy_description}),
                "class_ids": ("INT", {"default": [], "multiple": True, "description": taxonomy_description}),
                "order_names": ("STRING", {"default": [], "multiple": True, "description": taxonomy_description}),
                "order_ids": ("INT", {"default": [], "multiple": True, "description": taxonomy_description}),
                "family_names": ("STRING", {"default": [], "multiple": True, "description": taxonomy_description}),
                "family_ids": ("INT", {"default": [], "multiple": True, "description": taxonomy_description}),
                "genus_names": ("STRING", {"default": [], "multiple": True, "description": taxonomy_description}),
                "genus_ids": ("INT", {"default": [], "multiple": True, "description": taxonomy_description}),
                "species_names": ("STRING", {"default": [], "multiple": True, "description": taxonomy_description}),
                "species_ids": ("INT", {"default": [], "multiple": True, "description": taxonomy_description}),
                "strain_names": ("STRING", {"default": [], "multiple": True, "description": taxonomy_description}),
                "customizemetadata_script": (
                    "FILE",
                    {
                        "default": "customizemetadata.py",
                        "description": "Path to MetaPhlAn customizemetadata.py used to edit marker metadata JSON",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
