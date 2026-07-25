"""Focused bigscape node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin._variant_assembly_contracts import pin_contract

class BiGSCAPENode(CommandNode):
    """Construct BGC sequence similarity networks and gene cluster families with BiG-SCAPE."""

    NODE_ID = "bigscape"
    DISPLAY_NAME = "BiG-SCAPE"
    REQUIRED_CONDA_PACKAGES = ["bigscape"]
    CATEGORY = "secondary_metabolism"
    DESCRIPTION = "Construct sequence similarity networks of biosynthetic gene clusters and group them into gene cluster families."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BiG-SCAPE",
        "BiG-SCAPE gene cluster families",
        "biosynthetic gene clusters",
        "BGC networks",
        "GCF clustering",
        "MIBiG",
        "Pfam-A",
    ]
    RETURN_TYPES = ("HTML_REPORT", "DIRECTORY", "DIRECTORY", "DIRECTORY", "DIRECTORY", "TXT")
    RETURN_NAMES = ("html", "network_annotations", "clan_tables", "clustering_tables", "network_files", "logfile")
    REQUIRED_EXECUTABLES = ["bigscape", "hmmpress"]
    DOCUMENTATION_URL = "https://github.com/medema-group/BiG-SCAPE"
    CITATION_DOIS = ["10.1038/s41589-019-0400-9"]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41589-019-0400-9"]
    CITATION_TEXT = "BiG-SCAPE and CORASON identify biosynthetic gene cluster families."
    VERSION = "1.1.9"
    SHELL = True

    MIBIG_OPTIONS = ["", "--mibig", "--mibig21", "--mibig14", "--mibig13"]

    @classmethod
    def _inputs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("inputdir", inputs.get("inputs")))

    @classmethod
    def _identifiers(cls, inputs: dict[str, Any], files: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("element_identifiers", inputs.get("identifiers")))
        return [
            _safe_identifier(identifiers[index]) if index < len(identifiers) and identifiers[index] else _safe_name(path)
            for index, path in enumerate(files)
        ]

    @classmethod
    def _cutoffs(cls, inputs: dict[str, Any]) -> list[str]:
        cutoffs = _as_list(inputs.get("cutoffs", inputs.get("cutoff")))
        return cutoffs or ["0.3"]

    @classmethod
    def _clan_cutoff(cls, inputs: dict[str, Any]) -> list[str]:
        raw = _as_list(inputs.get("clan_cutoff", inputs.get("clan_cutoffs")))
        if len(raw) >= 2:
            return raw[:2]
        return []

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        input_dir = f"{out}/input"
        result_dir = f"{out}/result"
        pfam_dir = f"{out}/pfam"
        html_files = f"{out}/html_extra_files"
        cmd = ["mkdir", "-p", html_files, result_dir, input_dir, pfam_dir]
        input_files = cls._inputs(inputs)
        for path, identifier in zip(input_files, cls._identifiers(inputs, input_files), strict=False):
            cmd.extend(["&&", "ln", "-s", path, f"{input_dir}/region.{identifier}.gbk"])
        cmd.extend(["&&", "ln", "-s", str(inputs.get("pfam_dir", "")), f"{pfam_dir}/Pfam-A.hmm"])
        cmd.extend(["&&", "hmmpress", f"{pfam_dir}/Pfam-A.hmm"])
        anchorfile = str(inputs.get("anchorfile", "") or "")
        anchor_identifier = _safe_identifier(str(inputs.get("anchor_identifier", Path(anchorfile).name or "anchorfile.txt")))
        if anchorfile:
            cmd.extend(["&&", "ln", "-s", anchorfile, f"{out}/{anchor_identifier}"])
        cmd.extend(
            [
                "&&",
                "bigscape",
                "--inputdir",
                input_dir,
            ]
        )
        mibig = str(inputs.get("mibig", "") or "")
        if mibig:
            cmd.append(mibig)
        cmd.extend(["--outputdir", result_dir])
        if inputs.get("label"):
            cmd.extend(["--label", str(inputs.get("label"))])
        cmd.extend(["--pfam_dir", pfam_dir, "--cores", f"${{GALAXY_SLOTS:-{inputs.get('threads', 8)}}}"])
        if inputs.get("verbose"):
            cmd.append("--verbose")
        if inputs.get("include_singletons"):
            cmd.append("--include_singletons")
        cmd.extend(
            [
                "--domain_overlap_cutoff",
                str(inputs.get("domain_overlap_cutoff", 0.1)),
                "--min_bgc_size",
                str(inputs.get("min_big_size", inputs.get("min_bgc_size", 0))),
            ]
        )
        if inputs.get("mix"):
            cmd.append("--mix")
        if inputs.get("no_classify"):
            cmd.append("--no_classify")
        banned_classes = _as_list(inputs.get("banned_classes"))
        if banned_classes:
            cmd.append("--banned_classes")
            cmd.extend(banned_classes)
        cmd.append("--cutoffs")
        cmd.extend(cls._cutoffs(inputs))
        if inputs.get("clans_off"):
            cmd.append("--clans-off")
        clan_cutoff = cls._clan_cutoff(inputs)
        if clan_cutoff:
            cmd.extend(["--clan_cutoff", *clan_cutoff])
        if inputs.get("hybrids_off"):
            cmd.append("--hybrids-off")
        cmd.extend(["--mode", str(inputs.get("mode", "glocal"))])
        if anchorfile:
            cmd.extend(["--anchorfile", anchor_identifier])
        if inputs.get("force_hmmscan"):
            cmd.append("--force_hmmscan")
        if inputs.get("domain_includelist"):
            cmd.append("--domain_includelist")
        if inputs.get("log"):
            cmd.extend([">", f"{out}/log.txt"])
        cmd.extend(
            [
                "&&",
                "cp",
                f"{result_dir}/index.html",
                f"{out}/index.html",
                "&&",
                "cp",
                "-r",
                f"{result_dir}/html_content",
                html_files,
            ]
        )
        if inputs.get("log"):
            cmd.extend(["&&", "cp", f"{out}/log.txt", f"{out}/bigscape.log"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        for directory in ["network_annotations", "clan_tables", "clustering_tables", "network_files"]:
            (out / directory).mkdir(parents=True, exist_ok=True)
        outputs = [out / "index.html", out / "network_annotations"]
        if not inputs.get("clans_off"):
            outputs.append(out / "clan_tables")
        outputs.extend([out / "clustering_tables", out / "network_files"])
        if inputs.get("log"):
            outputs.append(out / "bigscape.log")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        class_options = ["PKSI", "PKSother", "NRPS", "RiPPs", "Saccharides", "Terpene", "PKS-NRP_Hybrids", "Others"]
        return {
            "required": {
                "inputdir": ("FILE_LIST", {"multiple": True, "description": "GenBank BGC files to include in clustering"}),
                "pfam_dir": ("FILE", {"description": "Pfam-A.hmm HMM database file"}),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "advanced": True, "description": "Galaxy collection element identifiers"},
                ),
                "mibig": ("STRING", {"default": "", "options": cls.MIBIG_OPTIONS, "description": "Optional MIBiG database flag"}),
                "label": ("STRING", {"default": "", "description": "Extra label added to BiG-SCAPE run names"}),
                "verbose": ("BOOLEAN", {"default": False, "description": "Print detailed progress information"}),
                "log": ("BOOLEAN", {"default": False, "description": "Capture BiG-SCAPE stdout to a log output"}),
                "include_singletons": ("BOOLEAN", {"default": False, "description": "Include BGCs below the cutoff distance"}),
                "domain_overlap_cutoff": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0}),
                "min_big_size": ("INT", {"default": 0, "min": 0, "description": "Minimum BGC size in bp"}),
                "mix": ("BOOLEAN", {"default": False, "description": "Mix all BGC classes in the analysis"}),
                "no_classify": ("BOOLEAN", {"default": False, "description": "Disable product-class based output"}),
                "banned_classes": ("STRING_LIST", {"default": [], "options": class_options, "description": "Classes excluded from classification"}),
                "cutoffs": ("FLOAT_LIST", {"default": [0.3], "description": "Raw distance cutoff values"}),
                "clans_off": ("BOOLEAN", {"default": False, "description": "Turn off second-layer GCF-to-GCC clustering"}),
                "clan_cutoff": ("FLOAT_LIST", {"default": [], "description": "Optional GCF and GCC clan cutoff values"}),
                "hybrids_off": ("BOOLEAN", {"default": False, "description": "Exclude hybrid predicted products"}),
                "mode": ("STRING", {"default": "glocal", "options": ["glocal", "global", "auto"], "description": "Alignment mode"}),
                "anchorfile": ("FILE", {"default": "", "description": "Optional custom anchor domain file"}),
                "anchor_identifier": ("STRING", {"default": "", "advanced": True, "description": "Safe filename for the staged anchor file"}),
                "force_hmmscan": ("BOOLEAN", {"default": False, "description": "Force hmmscan domain prediction"}),
                "domain_includelist": ("FILE", {"default": "", "description": "Optional domain include list"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._inputs(inputs):
            return "at least one GenBank BGC input is required"
        if not str(inputs.get("pfam_dir", "")).strip():
            return "Pfam-A.hmm input is required"
        domain_overlap = float(inputs.get("domain_overlap_cutoff", 0.1))
        if domain_overlap < 0 or domain_overlap > 1:
            return "domain_overlap_cutoff must be between 0 and 1"
        for cutoff in cls._cutoffs(inputs):
            value = float(cutoff)
            if value < 0.1 or value > 1.0:
                return "cutoff values must be between 0.1 and 1.0"
        clan_cutoff = cls._clan_cutoff(inputs)
        if clan_cutoff:
            if len(clan_cutoff) != 2:
                return "clan_cutoff requires exactly two values"
            for cutoff in clan_cutoff:
                value = float(cutoff)
                if value < 0.1 or value > 1.0:
                    return "clan_cutoff values must be between 0.1 and 1.0"
        return super().VALIDATE_INPUTS(inputs)

pin_contract(BiGSCAPENode)

__all__ = ['BiGSCAPENode']
