"""AMAS alignment manipulation wrapper contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_phylogeny_assembly_family.evidence import pin_contract

class AMASSummaryNode(CommandNode):
    """Summarize sequence alignments with AMAS summary."""

    LEGACY_NODE_ID = "amas_summary"
    DISPLAY_NAME = "AMAS Summary"
    REQUIRED_CONDA_PACKAGES = ["amas"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Calculate alignment summary statistics and optional per-taxon summaries with AMAS."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AMAS",
        "amas summary",
        "alignment summary",
        "alignment manipulation",
        "phylogenomics",
        "missing data",
        "parsimony informative sites",
    ]
    RETURN_TYPES = ("TEXT", "DIRECTORY")
    RETURN_NAMES = ("summary_out", "taxon_summaries")
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://github.com/marekborowiec/AMAS"
    CITATION_DOIS = [AMAS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{AMAS_CITATION_DOI}"]
    CITATION_TEXT = AMAS_CITATION_TEXT
    VERSION = "1.0+galaxy0"
    SHELL = True

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        input_format = str(inputs.get("input_format", "") or "")
        if input_format == "nex":
            return "nexus"
        if input_format in {"fasta", "phylip", "phylip-int", "nexus", "nexus-int"}:
            return input_format
        input_files = _as_list(inputs.get("input_files"))
        suffix = Path(input_files[0]).suffix.lower() if input_files else ""
        return {".nex": "nexus", ".nexus": "nexus", ".phy": "phylip", ".phylip": "phylip"}.get(
            suffix,
            "fasta",
        )

    @classmethod
    def _tool_directory(cls, inputs: dict[str, Any]) -> str:
        tool_directory = inputs.get("tool_directory")
        if tool_directory:
            return shlex.quote(str(tool_directory))
        return '"${BIONODULO_AMAS_TOOL_DIR:-.}"'

    @classmethod
    def _input_labels(cls, inputs: dict[str, Any]) -> list[str]:
        files = _as_list(inputs.get("input_files"))
        labels = _as_list(inputs.get("input_labels"))
        if not labels:
            labels = _as_list(inputs.get("element_identifiers"))
        if not labels:
            labels = [Path(path).name for path in files]
        if len(labels) < len(files):
            labels.extend(Path(path).name for path in files[len(labels) :])
        return labels

    @classmethod
    def _safe_input_names(cls, inputs: dict[str, Any]) -> list[str]:
        return [_safe_identifier(label) for label in cls._input_labels(inputs)]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        files = _as_list(inputs.get("input_files"))
        safe_names = cls._safe_input_names(inputs)
        input_format = cls._input_format(inputs)
        tool_directory = cls._tool_directory(inputs)
        parts = [
            "set -eu",
            (
                f"IN_FORMAT=$(python {tool_directory}/check_interleaved.py "
                f"{' '.join(shlex.quote(path) for path in files)} --format {shlex.quote(input_format)})"
            ),
        ]
        parts.extend(
            f"ln -sf {shlex.quote(path)} {shlex.quote(safe_name)}"
            for path, safe_name in zip(files, safe_names, strict=False)
        )

        amas_parts = [
            "python",
            "-m",
            "amas.AMAS",
            "summary",
        ]
        if inputs.get("by_taxon"):
            amas_parts.append("--by-taxon")
        amas_parts.append("--in-files")
        amas_parts.extend(safe_names)
        amas_parts.extend(
            [
                "--in-format",
                "${IN_FORMAT}",
                "--data-type",
                str(inputs.get("data_type", "aa")),
                "--cores",
                "${GALAXY_SLOTS:-1}",
            ]
        )
        if inputs.get("check_align"):
            amas_parts.append("--check-align")
        command = " ".join(shlex.quote(part) for part in amas_parts)
        command = command.replace("'${IN_FORMAT}'", '"${IN_FORMAT}"')
        command = command.replace("'${GALAXY_SLOTS:-1}'", '"${GALAXY_SLOTS:-1}"')
        parts.append(command)

        if inputs.get("by_taxon"):
            taxon_dir = f"{_out(inputs)}/taxon_summaries"
            parts.extend(
                [
                    f"mkdir -p {shlex.quote(taxon_dir)}",
                    f"find . -maxdepth 1 -name '*-seq-summary.txt' -exec mv {{}} {shlex.quote(taxon_dir)}/ \\;",
                ]
            )
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "summary.txt"]
        if inputs.get("by_taxon"):
            taxon_dir = out / "taxon_summaries"
            taxon_dir.mkdir(parents=True, exist_ok=True)
            outputs.append(taxon_dir)
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_files": (
                    "ALIGNMENT",
                    {
                        "list": True,
                        "description": "One or more pre-aligned FASTA, PHYLIP, or NEXUS alignment files",
                    },
                ),
                "data_type": (
                    "STRING",
                    {"default": "aa", "options": ["aa", "dna"], "description": "Protein or nucleotide alignment"},
                ),
            },
            "optional": {
                "input_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "phylip", "phylip-int", "nexus", "nexus-int", "nex"],
                        "description": "Input alignment format; NEXUS can be supplied as nex or nexus",
                    },
                ),
                "by_taxon": (
                    "BOOLEAN",
                    {"default": False, "description": "Also emit per-taxon summaries for each input alignment"},
                ),
                "check_align": (
                    "BOOLEAN",
                    {"default": False, "description": "Check that input sequences are aligned before summarising"},
                ),
                "input_labels": (
                    "STRING",
                    {
                        "default": "",
                        "list": True,
                        "description": "Optional Galaxy element identifiers used for safe symlink names",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {}), "tool_directory": ("STRING", {})},
        }

class AMASConcatNode(AMASSummaryNode):
    """Concatenate multiple sequence alignments with AMAS concat."""

    LEGACY_NODE_ID = "amas_concat"
    DISPLAY_NAME = "AMAS Concat"
    DESCRIPTION = "Concatenate multiple pre-aligned sequence files and emit a partition map with AMAS."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AMAS",
        "amas concat",
        "alignment concatenation",
        "supermatrix",
        "partition file",
        "phylogenomics",
        "RAxML partitions",
    ]
    RETURN_TYPES = ("ALIGNMENT", "TEXT")
    RETURN_NAMES = ("output", "partitions_out")

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "fasta") or "fasta")
        return out_format if out_format in {"fasta", "phylip", "phylip-int", "nexus", "nexus-int"} else "fasta"

    @classmethod
    def _part_format(cls, inputs: dict[str, Any]) -> str:
        part_format = str(inputs.get("part_format", "unspecified") or "unspecified")
        return part_format if part_format in {"unspecified", "nexus", "raxml"} else "unspecified"

    @classmethod
    def _alignment_suffix(cls, inputs: dict[str, Any]) -> str:
        return {
            "fasta": ".fasta",
            "phylip": ".phy",
            "phylip-int": ".phy",
            "nexus": ".nex",
            "nexus-int": ".nex",
        }[cls._out_format(inputs)]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        files = _as_list(inputs.get("input_files"))
        safe_names = cls._safe_input_names(inputs)
        input_format = cls._input_format(inputs)
        tool_directory = cls._tool_directory(inputs)
        parts = [
            "set -eu",
            (
                f"IN_FORMAT=$(python {tool_directory}/check_interleaved.py "
                f"{' '.join(shlex.quote(path) for path in files)} --format {shlex.quote(input_format)})"
            ),
        ]
        parts.extend(
            f"ln -sf {shlex.quote(path)} {shlex.quote(safe_name)}"
            for path, safe_name in zip(files, safe_names, strict=False)
        )

        amas_parts = [
            "python",
            "-m",
            "amas.AMAS",
            "concat",
            "--concat-part",
            "partitions.txt",
            "--concat-out",
            "concatenated.out",
            "--part-format",
            cls._part_format(inputs),
            "--out-format",
            cls._out_format(inputs),
            "--in-files",
            *safe_names,
            "--in-format",
            "${IN_FORMAT}",
            "--data-type",
            str(inputs.get("data_type", "aa")),
            "--cores",
            "${GALAXY_SLOTS:-1}",
        ]
        if inputs.get("check_align"):
            amas_parts.append("--check-align")
        command = " ".join(shlex.quote(part) for part in amas_parts)
        command = command.replace("'${IN_FORMAT}'", '"${IN_FORMAT}"')
        command = command.replace("'${GALAXY_SLOTS:-1}'", '"${GALAXY_SLOTS:-1}"')
        parts.append(command)
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        partition_suffix = ".nex" if cls._part_format(inputs) == "nexus" else ".txt"
        return [
            out / f"concatenated{cls._alignment_suffix(inputs)}",
            out / f"partitions{partition_suffix}",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_files": (
                    "ALIGNMENT",
                    {
                        "list": True,
                        "description": "Two or more pre-aligned FASTA, PHYLIP, or NEXUS alignment files",
                    },
                ),
                "out_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "phylip", "phylip-int", "nexus", "nexus-int"],
                        "description": "Output format for the concatenated alignment",
                    },
                ),
                "part_format": (
                    "STRING",
                    {
                        "default": "unspecified",
                        "options": ["unspecified", "nexus", "raxml"],
                        "description": "Partition file format",
                    },
                ),
                "data_type": (
                    "STRING",
                    {"default": "aa", "options": ["aa", "dna"], "description": "Protein or nucleotide alignment"},
                ),
            },
            "optional": {
                "input_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "phylip", "phylip-int", "nexus", "nexus-int", "nex"],
                        "description": "Input alignment format; NEXUS can be supplied as nex or nexus",
                    },
                ),
                "check_align": (
                    "BOOLEAN",
                    {"default": False, "description": "Check that input sequences are aligned before concatenating"},
                ),
                "input_labels": (
                    "STRING",
                    {
                        "default": "",
                        "list": True,
                        "description": "Optional Galaxy element identifiers used for safe symlink names",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {}), "tool_directory": ("STRING", {})},
        }

class AMASSplitNode(AMASSummaryNode):
    """Split a concatenated alignment into partition alignments with AMAS split."""

    LEGACY_NODE_ID = "amas_split"
    DISPLAY_NAME = "AMAS Split"
    DESCRIPTION = "Split a concatenated sequence alignment into per-partition alignment files with AMAS."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AMAS",
        "amas split",
        "alignment splitting",
        "partition file",
        "concatenated alignment",
        "phylogenomics",
        "locus extraction",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("split_alignments",)

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "fasta") or "fasta")
        return out_format if out_format in {"fasta", "phylip", "phylip-int", "nexus", "nexus-int"} else "fasta"

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        input_format = str(inputs.get("input_format", "") or "")
        if input_format == "nex":
            return "nexus"
        if input_format in {"fasta", "phylip", "phylip-int", "nexus", "nexus-int"}:
            return input_format
        input_file = str(inputs.get("input_file", "") or "")
        suffix = Path(input_file).suffix.lower()
        return {".nex": "nexus", ".nexus": "nexus", ".phy": "phylip", ".phylip": "phylip"}.get(
            suffix,
            "fasta",
        )

    @classmethod
    def _safe_input_name(cls, inputs: dict[str, Any]) -> str:
        label = str(inputs.get("input_label", "") or "")
        if not label:
            labels = _as_list(inputs.get("input_labels"))
            label = str(labels[0]) if labels else ""
        if not label:
            label = str(inputs.get("element_identifier", "") or "")
        if not label:
            label = Path(str(inputs.get("input_file", "") or "input")).name
        return _safe_identifier(label)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_file = str(inputs.get("input_file", ""))
        safe_name = cls._safe_input_name(inputs)
        input_format = cls._input_format(inputs)
        tool_directory = cls._tool_directory(inputs)
        split_alignments_dir = f"{_out(inputs)}/split_alignments"
        parts = [
            "set -eu",
            (
                f"IN_FORMAT=$(python {tool_directory}/check_interleaved.py "
                f"{shlex.quote(input_file)} --format {shlex.quote(input_format)})"
            ),
            f"ln -sf {shlex.quote(input_file)} {shlex.quote(safe_name)}",
        ]

        amas_parts = [
            "python",
            "-m",
            "amas.AMAS",
            "split",
            "--split-by",
            str(inputs.get("split_by", "")),
        ]
        if inputs.get("remove_empty"):
            amas_parts.append("--remove-empty")
        amas_parts.extend(
            [
                "--out-format",
                cls._out_format(inputs),
                "--in-files",
                safe_name,
                "--in-format",
                "${IN_FORMAT}",
                "--data-type",
                str(inputs.get("data_type", "aa")),
                "--cores",
                "${GALAXY_SLOTS:-1}",
            ]
        )
        if inputs.get("check_align"):
            amas_parts.append("--check-align")
        command = " ".join(shlex.quote(part) for part in amas_parts)
        command = command.replace("'${IN_FORMAT}'", '"${IN_FORMAT}"')
        command = command.replace("'${GALAXY_SLOTS:-1}'", '"${GALAXY_SLOTS:-1}"')
        parts.extend(
            [
                command,
                f"mkdir -p {shlex.quote(split_alignments_dir)}",
                f"find . -maxdepth 1 -name '*-out.*' -exec mv {{}} {shlex.quote(split_alignments_dir)}/ \\;",
            ]
        )
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        split_alignments_dir = out / "split_alignments"
        split_alignments_dir.mkdir(parents=True, exist_ok=True)
        return [split_alignments_dir]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "ALIGNMENT",
                    {
                        "description": "Concatenated pre-aligned FASTA, PHYLIP, or NEXUS alignment file to split",
                    },
                ),
                "split_by": (
                    "TEXT",
                    {
                        "description": "Unspecified-format partitions file defining alignment coordinate ranges",
                    },
                ),
                "out_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "phylip", "phylip-int", "nexus", "nexus-int"],
                        "description": "Output format for the split alignment files",
                    },
                ),
                "data_type": (
                    "STRING",
                    {"default": "aa", "options": ["aa", "dna"], "description": "Protein or nucleotide alignment"},
                ),
            },
            "optional": {
                "input_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "phylip", "phylip-int", "nexus", "nexus-int", "nex"],
                        "description": "Input alignment format; NEXUS can be supplied as nex or nexus",
                    },
                ),
                "remove_empty": (
                    "BOOLEAN",
                    {"default": False, "description": "Remove taxa that are entirely missing within a partition"},
                ),
                "check_align": (
                    "BOOLEAN",
                    {"default": False, "description": "Check that input sequences are aligned before splitting"},
                ),
                "input_label": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Optional Galaxy element identifier used for a safe symlink name",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {}), "tool_directory": ("STRING", {})},
        }

class AMASRemoveNode(AMASConcatNode):
    """Remove selected taxa from one or more alignments with AMAS remove."""

    LEGACY_NODE_ID = "amas_remove"
    DISPLAY_NAME = "AMAS Remove"
    DESCRIPTION = "Remove named taxa from one or more sequence alignments with AMAS."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AMAS",
        "amas remove",
        "remove taxa",
        "taxon filtering",
        "alignment subset",
        "phylogenomics",
        "outgroup removal",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("reduced_alignments",)

    @classmethod
    def _taxa_to_remove(cls, inputs: dict[str, Any]) -> list[str]:
        taxa = inputs.get("taxa_to_remove", "")
        if isinstance(taxa, (list, tuple)):
            return [str(taxon) for taxon in taxa if str(taxon)]
        return [taxon for taxon in str(taxa).split() if taxon]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        files = _as_list(inputs.get("input_files"))
        safe_names = cls._safe_input_names(inputs)
        input_format = cls._input_format(inputs)
        tool_directory = cls._tool_directory(inputs)
        reduced_alignments_dir = f"{_out(inputs)}/reduced_alignments"
        parts = [
            "set -eu",
            (
                f"IN_FORMAT=$(python {tool_directory}/check_interleaved.py "
                f"{' '.join(shlex.quote(path) for path in files)} --format {shlex.quote(input_format)})"
            ),
        ]
        parts.extend(
            f"ln -sf {shlex.quote(path)} {shlex.quote(safe_name)}"
            for path, safe_name in zip(files, safe_names, strict=False)
        )

        amas_parts = [
            "python",
            "-m",
            "amas.AMAS",
            "remove",
            "--taxa-to-remove",
            *cls._taxa_to_remove(inputs),
            "--out-format",
            cls._out_format(inputs),
            "--in-files",
            *safe_names,
            "--in-format",
            "${IN_FORMAT}",
            "--data-type",
            str(inputs.get("data_type", "aa")),
            "--cores",
            "${GALAXY_SLOTS:-1}",
        ]
        if inputs.get("check_align"):
            amas_parts.append("--check-align")
        command = " ".join(shlex.quote(part) for part in amas_parts)
        command = command.replace("'${IN_FORMAT}'", '"${IN_FORMAT}"')
        command = command.replace("'${GALAXY_SLOTS:-1}'", '"${GALAXY_SLOTS:-1}"')
        parts.extend(
            [
                command,
                f"mkdir -p {shlex.quote(reduced_alignments_dir)}",
                f"find . -maxdepth 1 -name '*-out.*' -exec mv {{}} {shlex.quote(reduced_alignments_dir)}/ \\;",
            ]
        )
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        reduced_alignments_dir = out / "reduced_alignments"
        reduced_alignments_dir.mkdir(parents=True, exist_ok=True)
        return [reduced_alignments_dir]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_files": (
                    "ALIGNMENT",
                    {
                        "list": True,
                        "description": "One or more pre-aligned FASTA, PHYLIP, or NEXUS alignment files",
                    },
                ),
                "taxa_to_remove": (
                    "STRING",
                    {
                        "description": "Space-separated taxon names to remove; use underscores for sequence-name spaces",
                    },
                ),
                "out_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "phylip", "phylip-int", "nexus", "nexus-int"],
                        "description": "Output format for alignments with taxa removed",
                    },
                ),
                "data_type": (
                    "STRING",
                    {"default": "aa", "options": ["aa", "dna"], "description": "Protein or nucleotide alignment"},
                ),
            },
            "optional": {
                "input_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "phylip", "phylip-int", "nexus", "nexus-int", "nex"],
                        "description": "Input alignment format; NEXUS can be supplied as nex or nexus",
                    },
                ),
                "check_align": (
                    "BOOLEAN",
                    {"default": False, "description": "Check that input sequences are aligned before removing taxa"},
                ),
                "input_labels": (
                    "STRING",
                    {
                        "default": "",
                        "list": True,
                        "description": "Optional Galaxy element identifiers used for safe symlink names",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {}), "tool_directory": ("STRING", {})},
        }

class AMASReplicateNode(AMASConcatNode):
    """Generate replicate alignments by sampling loci with AMAS replicate."""

    LEGACY_NODE_ID = "amas_replicate"
    DISPLAY_NAME = "AMAS Replicate"
    DESCRIPTION = "Generate replicate alignment datasets by sampling loci from multiple alignments with AMAS."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AMAS",
        "amas replicate",
        "alignment replicate",
        "phylogenetic jackknife",
        "loci sampling",
        "bootstrap loci",
        "phylogenomics",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("replicate_alignments",)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        files = _as_list(inputs.get("input_files"))
        safe_names = cls._safe_input_names(inputs)
        input_format = cls._input_format(inputs)
        tool_directory = cls._tool_directory(inputs)
        replicate_alignments_dir = f"{_out(inputs)}/replicate_alignments"
        parts = [
            "set -eu",
            (
                f"IN_FORMAT=$(python {tool_directory}/check_interleaved.py "
                f"{' '.join(shlex.quote(path) for path in files)} --format {shlex.quote(input_format)})"
            ),
        ]
        parts.extend(
            f"ln -sf {shlex.quote(path)} {shlex.quote(safe_name)}"
            for path, safe_name in zip(files, safe_names, strict=False)
        )

        amas_parts = [
            "python",
            "-m",
            "amas.AMAS",
            "replicate",
            "--rep-aln",
            str(inputs.get("replicate_replicates", 10)),
            str(inputs.get("replicate_loci", 2)),
            "--out-format",
            cls._out_format(inputs),
            "--in-files",
            *safe_names,
            "--in-format",
            "${IN_FORMAT}",
            "--data-type",
            str(inputs.get("data_type", "aa")),
            "--cores",
            "${GALAXY_SLOTS:-1}",
        ]
        if inputs.get("check_align"):
            amas_parts.append("--check-align")
        command = " ".join(shlex.quote(part) for part in amas_parts)
        command = command.replace("'${IN_FORMAT}'", '"${IN_FORMAT}"')
        command = command.replace("'${GALAXY_SLOTS:-1}'", '"${GALAXY_SLOTS:-1}"')
        parts.extend(
            [
                command,
                f"mkdir -p {shlex.quote(replicate_alignments_dir)}",
                f"find . -maxdepth 1 -name '*-out.*' -exec mv {{}} {shlex.quote(replicate_alignments_dir)}/ \\;",
            ]
        )
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        replicate_alignments_dir = out / "replicate_alignments"
        replicate_alignments_dir.mkdir(parents=True, exist_ok=True)
        return [replicate_alignments_dir]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_files": (
                    "ALIGNMENT",
                    {
                        "list": True,
                        "description": "Multiple pre-aligned FASTA, PHYLIP, or NEXUS alignment files, one per locus",
                    },
                ),
                "replicate_replicates": (
                    "INT",
                    {"default": 10, "min": 1, "description": "Number of replicate datasets to build"},
                ),
                "replicate_loci": (
                    "INT",
                    {"default": 2, "min": 1, "description": "Number of loci to sample per replicate"},
                ),
                "out_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "phylip", "phylip-int", "nexus", "nexus-int"],
                        "description": "Output format for replicated alignments",
                    },
                ),
                "data_type": (
                    "STRING",
                    {"default": "aa", "options": ["aa", "dna"], "description": "Protein or nucleotide alignment"},
                ),
            },
            "optional": {
                "input_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "phylip", "phylip-int", "nexus", "nexus-int", "nex"],
                        "description": "Input alignment format; NEXUS can be supplied as nex or nexus",
                    },
                ),
                "check_align": (
                    "BOOLEAN",
                    {"default": False, "description": "Check that input sequences are aligned before sampling loci"},
                ),
                "input_labels": (
                    "STRING",
                    {
                        "default": "",
                        "list": True,
                        "description": "Optional Galaxy element identifiers used for safe symlink names",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {}), "tool_directory": ("STRING", {})},
        }

pin_contract(AMASSummaryNode)
pin_contract(AMASConcatNode)
pin_contract(AMASSplitNode)
pin_contract(AMASRemoveNode)
pin_contract(AMASReplicateNode)

__all__ = ["AMASSummaryNode","AMASConcatNode","AMASSplitNode","AMASRemoveNode","AMASReplicateNode"]
