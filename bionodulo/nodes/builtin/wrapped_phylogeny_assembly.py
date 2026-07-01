"""BioNodulo built-in wrapped tool nodes split by tool family."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

class AssemblyStatsNode(CommandNode):
    """Render assembly metric visualisations using assembly-stats."""

    NODE_ID = "assembly_stats"
    DISPLAY_NAME = "Assembly Stats"
    REQUIRED_CONDA_PACKAGES = ["rjchallis-assembly-stats"]
    CATEGORY = "assembly"
    DESCRIPTION = "Generate assembly metric visualisations or JSON statistics from a genome FASTA file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "assembly-stats",
        "Assembly stats",
        "asm2stats.minmaxgc.pl",
        "genome assembly metrics",
        "assembly visualisation",
        "snail plot",
        "N50",
        "GC content",
    ]
    RETURN_TYPES = ("HTML_REPORT", "JSON")
    RETURN_NAMES = ("output_html", "output_json")
    REQUIRED_EXECUTABLES = ["asm2stats.minmaxgc.pl"]
    DOCUMENTATION_URL = "https://github.com/rjchallis/assembly-stats"
    CITATION_DOIS = [ASSEMBLY_STATS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ASSEMBLY_STATS_CITATION_DOI}"]
    CITATION_TEXT = ASSEMBLY_STATS_CITATION_TEXT
    VERSION = "17.02"
    SHELL = True

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        output_format = str(inputs.get("output_format", "html") or "html").lower()
        return "json" if output_format == "json" else "html"

    @classmethod
    def _tool_directory(cls, inputs: dict[str, Any]) -> str:
        tool_directory = inputs.get("tool_directory")
        if tool_directory:
            return shlex.quote(str(tool_directory))
        return '"${BIONODULO_ASSEMBLY_STATS_TOOL_DIR:-.}"'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_fasta = shlex.quote(str(inputs.get("input_fasta", "")))
        if cls._output_format(inputs) == "json":
            return f"asm2stats.minmaxgc.pl {input_fasta} > {shlex.quote(f'{out}/output.json')}"

        output_files = f"{out}/output_files"
        json_dir = f"{output_files}/json"
        tool_directory = cls._tool_directory(inputs)
        parts = [
            'SRC="$(dirname $(which asm2stats.pl))/../opt/assembly-stats"',
            f"mkdir -p {shlex.quote(json_dir)}",
            f'cp -r "$SRC/css/" {shlex.quote(output_files)}',
            f'cp -r "$SRC/js/" {shlex.quote(output_files)}',
            f"cp {tool_directory}/d3-tip.js {shlex.quote(f'{output_files}/js/d3-tip.js')}",
            f"cp {tool_directory}/assembly-stats.html {shlex.quote(f'{out}/output.html')}",
            f"cp {tool_directory}/assembly-stats.html {shlex.quote(output_files)}",
            f"asm2stats.minmaxgc.pl {input_fasta} > {shlex.quote(f'{json_dir}/output.assembly-stats.json')}",
        ]
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = ".json" if cls._output_format(inputs) == "json" else ".html"
        return [out / f"output{suffix}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Genome assembly FASTA"}),
            },
            "optional": {
                "output_format": (
                    "STRING",
                    {"default": "html", "options": ["html", "json"], "description": "Galaxy output format"},
                ),
            },
            "hidden": {"output": ("STRING", {}), "tool_directory": ("STRING", {})},
        }

class AMASSummaryNode(CommandNode):
    """Summarize sequence alignments with AMAS summary."""

    NODE_ID = "amas_summary"
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
    VERSION = "1.0"
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
                str(inputs.get("data_type", "dna")),
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
                    {"default": "dna", "options": ["dna", "aa"], "description": "Nucleotide or protein alignment"},
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

    NODE_ID = "amas_concat"
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
            str(inputs.get("data_type", "dna")),
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
                    {"default": "dna", "options": ["dna", "aa"], "description": "Nucleotide or protein alignment"},
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

    NODE_ID = "amas_split"
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
                str(inputs.get("data_type", "dna")),
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
                    {"default": "dna", "options": ["dna", "aa"], "description": "Nucleotide or protein alignment"},
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

    NODE_ID = "amas_remove"
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
            str(inputs.get("data_type", "dna")),
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
                    {"default": "dna", "options": ["dna", "aa"], "description": "Nucleotide or protein alignment"},
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

    NODE_ID = "amas_replicate"
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
            str(inputs.get("data_type", "dna")),
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
                    {"default": "dna", "options": ["dna", "aa"], "description": "Nucleotide or protein alignment"},
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

class ClustalWNode(CommandNode):
    """Align DNA or protein FASTA sequences with ClustalW."""

    NODE_ID = "clustalw"
    DISPLAY_NAME = "ClustalW"
    REQUIRED_CONDA_PACKAGES = ["clustalw"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Align DNA or protein FASTA sequences with ClustalW and emit the alignment plus guide tree."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ClustalW",
        "clustalw2",
        "clustal",
        "multiple sequence alignment",
        "DNA alignment",
        "protein alignment",
        "guide tree",
    ]
    RETURN_TYPES = ("ALIGNMENT", "PHYLOGENY_TREE")
    RETURN_NAMES = ("alignment", "guide_tree")
    REQUIRED_EXECUTABLES = ["clustalw2"]
    DOCUMENTATION_URL = "http://www.clustal.org/clustal2/"
    CITATION_DOIS = [CLUSTALW_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CLUSTALW_CITATION_DOI}"]
    CITATION_TEXT = CLUSTALW_CITATION_TEXT
    VERSION = "2.1"
    SHELL = True

    OUTPUT_EXTENSIONS = {
        "clustal": "aln",
        "phylip": "phy",
        "fasta": "fasta",
    }

    @classmethod
    def _alignment_output(cls, inputs: dict[str, Any]) -> str:
        outform = str(inputs.get("outform", "clustal") or "clustal").lower()
        ext = cls.OUTPUT_EXTENSIONS.get(outform, "aln")
        return f"{_out(inputs)}/alignment.{ext}"

    @classmethod
    def _append_value_option(cls, cmd: list[str], flag: str, value: Any) -> None:
        if value is not None and str(value) != "":
            cmd.append(f"{flag}={value}")

    @classmethod
    def _append_multiple_alignment_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cls._append_value_option(cmd, "-GAPOPEN", inputs.get("gapopen"))
        cls._append_value_option(cmd, "-GAPEXT", inputs.get("gapext"))
        if inputs.get("endgaps"):
            cmd.append("-ENDGAPS")
        cls._append_value_option(cmd, "-GAPDIST", inputs.get("gapdist"))
        if inputs.get("nopgap"):
            cmd.append("-NOPGAP")
        if inputs.get("nohgap"):
            cmd.append("-NOHGAP")
        cls._append_value_option(cmd, "-MAXDIV", inputs.get("maxdiv"))
        if inputs.get("negative"):
            cmd.append("-NEGATIVE")
        cls._append_value_option(cmd, "-TRANSWEIGHT", inputs.get("transweight"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        sequence_type = str(inputs.get("sequence_type", "DNA") or "DNA").upper()
        outform = str(inputs.get("outform", "clustal") or "clustal").lower()
        clustal_output = {"clustal": "CLUSTAL", "phylip": "PHYLIP", "fasta": "FASTA"}.get(outform, "CLUSTAL")
        input_fasta = str(inputs.get("input", ""))
        cmd = [
            "clustalw2",
            "-INFILE=input.fasta",
            f"-OUTFILE={cls._alignment_output(inputs)}",
            f"-OUTORDER={inputs.get('out_order', 'ALIGNED')}",
            f"-TYPE={sequence_type}",
            f"-OUTPUT={clustal_output}",
        ]
        if outform == "clustal" and inputs.get("out_seqnos"):
            cmd.append("-SEQNOS=ON")
        if str(inputs.get("range_mode", "complete")) == "part":
            cmd.append(f"-RANGE={inputs.get('seq_range_start', 1)},{inputs.get('seq_range_end', 99999)}")

        algorithm = str(inputs.get("algorithm", "slow") or "slow").lower()
        if sequence_type == "PROTEIN":
            if algorithm == "fast":
                cmd.append("-QUICKTREE")
                for flag, key in (
                    ("-KTUPLE", "ktuple"),
                    ("-TOPDIAGS", "topdiags"),
                    ("-WINDOW", "window"),
                    ("-PAIRGAP", "pairgap"),
                    ("-SCORE", "score"),
                ):
                    cls._append_value_option(cmd, flag, inputs.get(key))
            else:
                cls._append_value_option(cmd, "-PWMATRIX", inputs.get("pwmatrix", "GONNET"))
                cls._append_value_option(cmd, "-PWGAPOPEN", inputs.get("pwgapopen"))
                cls._append_value_option(cmd, "-PWGAPEXT", inputs.get("pwgapext"))
            cls._append_value_option(cmd, "-MATRIX", inputs.get("matrix", "GONNET"))
        else:
            if algorithm == "fast":
                cmd.append("-QUICKTREE")
                for flag, key in (
                    ("-KTUPLE", "ktuple"),
                    ("-TOPDIAGS", "topdiags"),
                    ("-WINDOW", "window"),
                    ("-PAIRGAP", "pairgap"),
                    ("-SCORE", "score"),
                ):
                    cls._append_value_option(cmd, flag, inputs.get(key))
            else:
                cls._append_value_option(cmd, "-PWDNAMATRIX", inputs.get("pwdnamatrix", "IUB"))
                cls._append_value_option(cmd, "-PWGAPOPEN", inputs.get("pwgapopen"))
                cls._append_value_option(cmd, "-PWGAPEXT", inputs.get("pwgapext"))
            cls._append_value_option(cmd, "-DNAMATRIX", inputs.get("dn_matrix", "IUB"))
        cls._append_multiple_alignment_options(cmd, inputs)
        cls._append_value_option(cmd, "-OUTPUTTREE", inputs.get("outputtree", "PHYLIP"))
        if inputs.get("kimura"):
            cmd.append("-KIMURA")
        if inputs.get("tossgaps"):
            cmd.append("-TOSSGAPS")
        return (
            f"ln -sf {shlex.quote(input_fasta)} input.fasta && "
            f"{' '.join(shlex.quote(part) for part in cmd)} && "
            f"cp input.dnd {shlex.quote(f'{_out(inputs)}/guide_tree.dnd')}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outform = str(inputs.get("outform", "clustal") or "clustal").lower()
        ext = cls.OUTPUT_EXTENSIONS.get(outform, "aln")
        return [out / f"alignment.{ext}", out / "guide_tree.dnd"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input"):
            return "input FASTA is required"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "FASTA sequences to align"}),
                "sequence_type": (
                    "STRING",
                    {"default": "DNA", "options": ["DNA", "PROTEIN"], "description": "DNA/RNA or protein sequences"},
                ),
                "outform": (
                    "STRING",
                    {"default": "clustal", "options": ["clustal", "phylip", "fasta"], "description": "Alignment output format"},
                ),
            },
            "optional": {
                "out_order": (
                    "STRING",
                    {"default": "ALIGNED", "options": ["ALIGNED", "INPUT"], "description": "Output aligned or input order"},
                ),
                "out_seqnos": ("BOOLEAN", {"default": False, "description": "Show residue numbers in Clustal output"}),
                "range_mode": (
                    "STRING",
                    {"default": "complete", "options": ["complete", "part"], "description": "Output complete alignment or a range"},
                ),
                "seq_range_start": ("INT", {"default": 1, "min": 1, "advanced": True}),
                "seq_range_end": ("INT", {"default": 99999, "min": 1, "advanced": True}),
                "algorithm": (
                    "STRING",
                    {"default": "slow", "options": ["slow", "fast"], "description": "Guide-tree algorithm"},
                ),
                "pwdnamatrix": ("STRING", {"default": "IUB", "options": ["IUB", "CLUSTALW"], "advanced": True}),
                "dn_matrix": ("STRING", {"default": "IUB", "options": ["IUB", "CLUSTALW"], "advanced": True}),
                "pwmatrix": ("STRING", {"default": "GONNET", "options": ["BLOSUM", "PAM", "GONNET", "ID"], "advanced": True}),
                "matrix": ("STRING", {"default": "GONNET", "options": ["BLOSUM", "PAM", "GONNET", "ID"], "advanced": True}),
                "pwgapopen": ("INT", {"default": "", "min": 0, "advanced": True}),
                "pwgapext": ("FLOAT", {"default": "", "min": 0, "advanced": True}),
                "ktuple": ("INT", {"default": "", "min": 0, "advanced": True}),
                "topdiags": ("INT", {"default": "", "min": 0, "advanced": True}),
                "window": ("INT", {"default": "", "min": 0, "advanced": True}),
                "pairgap": ("INT", {"default": "", "min": 0, "advanced": True}),
                "score": ("STRING", {"default": "PERCENT", "options": ["PERCENT", "ABSOLUTE"], "advanced": True}),
                "gapopen": ("INT", {"default": "", "min": 0, "advanced": True}),
                "gapext": ("FLOAT", {"default": "", "min": 0, "advanced": True}),
                "endgaps": ("BOOLEAN", {"default": False, "advanced": True}),
                "gapdist": ("INT", {"default": "", "min": 0, "advanced": True}),
                "nopgap": ("BOOLEAN", {"default": False, "advanced": True}),
                "nohgap": ("BOOLEAN", {"default": False, "advanced": True}),
                "maxdiv": ("INT", {"default": "", "min": 0, "max": 100, "advanced": True}),
                "negative": ("BOOLEAN", {"default": False, "advanced": True}),
                "transweight": ("FLOAT", {"default": "", "min": 0, "max": 1, "advanced": True}),
                "outputtree": (
                    "STRING",
                    {"default": "PHYLIP", "options": ["PHYLIP", "DIST", "NJ", "NEXUS"], "advanced": True},
                ),
                "kimura": ("BOOLEAN", {"default": False, "advanced": True}),
                "tossgaps": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class QuicktreeNode(CommandNode):
    """Build phylogenetic trees or distance matrices with Quicktree."""

    NODE_ID = "quicktree"
    DISPLAY_NAME = "Quicktree"
    REQUIRED_CONDA_PACKAGES = ["quicktree", "hmmer"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Construct phylogenetic trees or distance matrices from alignments with Quicktree."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Quicktree",
        "quicktree",
        "neighbor joining",
        "distance matrix",
        "UPGMA",
        "Kimura",
        "bootstrap",
    ]
    RETURN_TYPES = ("PHYLOGENY_TREE",)
    RETURN_NAMES = ("output_file",)
    REQUIRED_EXECUTABLES = ["quicktree", "esl-reformat"]
    DOCUMENTATION_URL = "https://github.com/khowe/quicktree"
    CITATION_DOIS = [QUICKTREE_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{QUICKTREE_CITATION_DOI}"]
    CITATION_TEXT = QUICKTREE_CITATION_TEXT
    VERSION = "2.5"
    SHELL = True

    @classmethod
    def _output_suffix(cls, inputs: dict[str, Any]) -> str:
        return ".dist" if str(inputs.get("output_type", "tree_out")) == "dist_out" else ".nwk"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_file{cls._output_suffix(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_format = str(inputs.get("format", "align"))
        input_file = str(inputs.get("input_file", ""))
        if input_format == "dist":
            stage = f"ln -s {shlex.quote(input_file)} input.quicktree"
            in_mode = "m"
        else:
            stage = f"esl-reformat -o input.quicktree stockholm {shlex.quote(input_file)}"
            in_mode = "a"
        out_mode = "m" if str(inputs.get("output_type", "tree_out")) == "dist_out" else "t"
        cmd = ["quicktree", "-in", in_mode, "-out", out_mode]
        if inputs.get("upgma"):
            cmd.append("-upgma")
        if inputs.get("kimura"):
            cmd.append("-kimura")
        if inputs.get("boot") not in (None, ""):
            cmd.extend(["-boot", str(inputs.get("boot"))])
        cmd.append("input.quicktree")
        return f"{stage} && {_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"output_file{cls._output_suffix(inputs)}"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input_file"):
            return "input alignment or distance matrix is required"
        if inputs.get("boot") not in (None, ""):
            try:
                boot = int(inputs.get("boot"))
            except (TypeError, ValueError):
                return "boot must be an integer"
            if boot < 0:
                return "boot must be >= 0"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "format": (
                    "STRING",
                    {"default": "align", "options": ["align", "dist"], "description": "Input alignment or distance matrix"},
                ),
                "input_file": ("ALIGNMENT", {"description": "Alignment or PHYLIP-format distance matrix"}),
                "output_type": (
                    "STRING",
                    {"default": "tree_out", "options": ["tree_out", "dist_out"], "description": "Newick tree or distance matrix output"},
                ),
            },
            "optional": {
                "upgma": ("BOOLEAN", {"default": False, "description": "Use UPGMA instead of neighbor joining"}),
                "kimura": ("BOOLEAN", {"default": False, "description": "Apply Kimura translation to pairwise distances"}),
                "boot": ("INT", {"default": "", "min": 0, "description": "Bootstrap iterations"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RapidNJNode(CommandNode):
    """Build neighbour-joining trees or distance matrices with RapidNJ."""

    NODE_ID = "rapidnj"
    DISPLAY_NAME = "RapidNJ"
    REQUIRED_CONDA_PACKAGES = ["rapidnj"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Construct neighbour-joining phylogenetic trees or distance matrices rapidly with RapidNJ."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "RapidNJ",
        "rapidnj",
        "neighbor joining",
        "neighbour joining",
        "distance matrix",
        "Kimura",
        "Jukes-Cantor",
        "bootstrap",
    ]
    RETURN_TYPES = ("PHYLOGENY_TREE",)
    RETURN_NAMES = ("distances",)
    REQUIRED_EXECUTABLES = ["rapidnj"]
    DOCUMENTATION_URL = "https://birc.au.dk/software/rapidnj"
    CITATION_DOIS = [RAPIDNJ_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{RAPIDNJ_CITATION_DOI}"]
    CITATION_TEXT = RAPIDNJ_CITATION_TEXT
    VERSION = "2.3.2"
    SHELL = True

    INPUT_FORMAT_OPTIONS = ["fasta", "stockholm", "phylip"]
    INPUT_FORMAT_FLAGS = {
        "fasta": ("fa", "fa"),
        "stockholm": ("sth", "sth"),
        "phylip": ("pd", "pd"),
    }
    OUTPUT_FORMAT_OPTIONS = ["t", "m"]
    EVOLUTION_MODEL_OPTIONS = ["kim", "jc"]
    ALIGNMENT_TYPE_OPTIONS = ["p", "d"]

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_format", "fasta") or "fasta")

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output_format", "t") or "t")

    @classmethod
    def _output_suffix(cls, inputs: dict[str, Any]) -> str:
        return ".tsv" if cls._output_format(inputs) == "m" else ".nhx"

    @classmethod
    def _staged_input(cls, inputs: dict[str, Any]) -> str:
        input_format = cls._input_format(inputs)
        _rapidnj_format, suffix = cls.INPUT_FORMAT_FLAGS.get(input_format, cls.INPUT_FORMAT_FLAGS["fasta"])
        return f"{_out(inputs)}/input.{suffix}"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/distances{cls._output_suffix(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_format = cls._input_format(inputs)
        rapidnj_format, _suffix = cls.INPUT_FORMAT_FLAGS.get(input_format, cls.INPUT_FORMAT_FLAGS["fasta"])
        staged_input = cls._staged_input(inputs)
        cmd = [
            "rapidnj",
            staged_input,
            "--input-format",
            rapidnj_format,
            "--output-format",
            cls._output_format(inputs),
            "--evolution-model",
            str(inputs.get("evolution_model", "kim") or "kim"),
            "--cores",
            str(inputs.get("threads", 1) or 1),
        ]
        if inputs.get("bootstrap") not in (None, ""):
            cmd.extend(["--bootstrap", str(inputs.get("bootstrap"))])
        cmd.extend(["--alignment-type", str(inputs.get("alignment_type", "p") or "p")])
        if inputs.get("no_negative_length"):
            cmd.append("--no-negative-length")
        cmd.extend([">", cls._output_path(inputs)])
        return " && ".join(
            [
                f"mkdir -p {shlex.quote(out)}",
                _shell_join(["ln", "-s", str(inputs.get("alignments", "")), staged_input]),
                _shell_join(cmd),
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"distances{cls._output_suffix(inputs)}"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("alignments", "")).strip():
            return "alignments is required"
        input_format = cls._input_format(inputs)
        if input_format not in cls.INPUT_FORMAT_OPTIONS:
            return f"input_format must be one of: {', '.join(cls.INPUT_FORMAT_OPTIONS)}"
        output_format = cls._output_format(inputs)
        if output_format not in cls.OUTPUT_FORMAT_OPTIONS:
            return f"output_format must be one of: {', '.join(cls.OUTPUT_FORMAT_OPTIONS)}"
        evolution_model = str(inputs.get("evolution_model", "kim") or "kim")
        if evolution_model not in cls.EVOLUTION_MODEL_OPTIONS:
            return f"evolution_model must be one of: {', '.join(cls.EVOLUTION_MODEL_OPTIONS)}"
        alignment_type = str(inputs.get("alignment_type", "p") or "p")
        if alignment_type not in cls.ALIGNMENT_TYPE_OPTIONS:
            return f"alignment_type must be one of: {', '.join(cls.ALIGNMENT_TYPE_OPTIONS)}"
        if inputs.get("bootstrap") not in (None, ""):
            try:
                bootstrap = int(inputs.get("bootstrap"))
            except (TypeError, ValueError):
                return "bootstrap must be an integer"
            if bootstrap < 0:
                return "bootstrap must be >= 0"
        try:
            threads = int(inputs.get("threads", 1) or 1)
        except (TypeError, ValueError):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be >= 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignments": ("ALIGNMENT", {"description": "FASTA, Stockholm, or PHYLIP alignment/distance input"}),
            },
            "optional": {
                "input_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": cls.INPUT_FORMAT_OPTIONS,
                        "description": "Input format: FASTA, Stockholm, or PHYLIP distance/alignment",
                    },
                ),
                "output_format": (
                    "STRING",
                    {
                        "default": "t",
                        "options": cls.OUTPUT_FORMAT_OPTIONS,
                        "description": "Output a Newick/NHX tree or distance matrix",
                    },
                ),
                "evolution_model": (
                    "STRING",
                    {"default": "kim", "options": cls.EVOLUTION_MODEL_OPTIONS, "description": "Sequence evolution model"},
                ),
                "bootstrap": ("INT", {"default": "", "min": 0, "description": "Bootstrap samples"}),
                "alignment_type": (
                    "STRING",
                    {"default": "p", "options": cls.ALIGNMENT_TYPE_OPTIONS, "description": "Protein or DNA alignment"},
                ),
                "no_negative_length": (
                    "BOOLEAN",
                    {"default": False, "description": "Adjust negative branch lengths"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "description": "Number of CPU cores"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class PhyMLNode(CommandNode):
    """Infer maximum-likelihood phylogenies with PhyML."""

    NODE_ID = "phyml"
    DISPLAY_NAME = "PhyML"
    REQUIRED_CONDA_PACKAGES = ["phyml"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Infer maximum-likelihood phylogenies from PHYLIP alignments with PhyML."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "PhyML",
        "phyml",
        "maximum likelihood",
        "phylogeny",
        "PHYLIP",
        "bootstrap",
        "aLRT",
        "SH-like branch support",
    ]
    RETURN_TYPES = ("PHYLOGENY_TREE", "TXT", "TXT")
    RETURN_NAMES = ("output_tree", "output_stats", "output_stdout")
    REQUIRED_EXECUTABLES = ["phyml"]
    DOCUMENTATION_URL = f"{DOI_URL}{PHYML_CITATION_DOI}"
    CITATION_DOIS = [PHYML_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{PHYML_CITATION_DOI}"]
    CITATION_TEXT = PHYML_CITATION_TEXT
    VERSION = "3.3.20220408+galaxy0"
    SHELL = True

    PHYLIP_FORMAT_OPTIONS = ["", "--sequential"]
    TYPE_OPTIONS = ["nt", "aa"]
    NT_MODEL_OPTIONS = ["HKY85", "JC69", "K80", "F81", "F84", "TN93", "GTR"]
    AA_MODEL_OPTIONS = [
        "LG",
        "WAG",
        "JTT",
        "MtREV",
        "Dayhoff",
        "DCMut",
        "RtREV",
        "CpREV",
        "VT",
        "Blosum62",
        "MtMam",
        "MtArt",
        "HIVw",
        "HIVb",
    ]
    EQUI_FREQ_OPTIONS = ["m", "e"]
    MOVE_OPTIONS = ["NNI", "SPR", "BEST"]
    OPTIMISATION_OPTIONS = ["tlr", "tl", "l", "r", "n"]
    BRANCH_SUPPORT_OPTIONS = ["0", "1", "-1", "-2", "-4", "-5"]

    @staticmethod
    def _staged_name(path: str) -> str:
        return sub(r"[^\s\w\-]", "_", Path(path).name or "input")

    @classmethod
    def _model(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get("type_of_seq", "nt")) == "aa":
            return str(inputs.get("aa_model", "LG"))
        return str(inputs.get("nt_model", inputs.get("model", "HKY85")))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_file = str(inputs.get("input", ""))
        staged_input = cls._staged_name(input_file)
        commands = [_shell_join(["ln", "-sf", input_file, staged_input])]
        user_tree = str(inputs.get("userInputTree", "") or "")
        staged_tree = ""
        if user_tree:
            staged_tree = cls._staged_name(user_tree)
            commands.append(_shell_join(["ln", "-sf", user_tree, staged_tree]))

        branch_support = str(inputs.get("branchSupport", "-4"))
        bootstrap = str(inputs.get("replicate", 100)) if branch_support == "1" else branch_support
        cmd = [
            "phyml",
            "--input",
            staged_input,
        ]
        phylip_format = str(inputs.get("phylip_format", ""))
        if phylip_format:
            cmd.append(phylip_format)
        type_of_seq = str(inputs.get("type_of_seq", "nt"))
        cmd.extend([
            "--datatype",
            type_of_seq,
            "--multiple",
            str(inputs.get("nb_data_set", 1)),
            "--bootstrap",
            bootstrap,
            "--model",
            cls._model(inputs),
        ])
        if type_of_seq == "nt":
            cmd.extend(["-t", str(inputs.get("tstv", "e"))])
        cmd.extend([
            "-f",
            str(inputs.get("equi_freq", "m")),
            "--pinv",
            str(inputs.get("prop_invar", "e")),
            "--nclasses",
            str(inputs.get("nbSubstCat", 4)),
        ])
        if str(inputs.get("nbSubstCat", 4)) != "1":
            cmd.extend(["--alpha", str(inputs.get("gamma", "e"))])
        cmd.extend([
            "--search",
            str(inputs.get("move", "NNI")),
            "-o",
            str(inputs.get("optimisationTopology", "tlr")),
        ])
        if staged_tree:
            cmd.extend(["--inputtree", staged_tree])
        if str(inputs.get("numStartSeed", 0)) != "0":
            cmd.extend(["--r_seed", str(inputs.get("numStartSeed"))])
        cmd.extend(["--no_memory_check", "|", "tee", f"{_out(inputs)}/output_stdout.txt"])
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [
            out / "output_tree.nwk",
            out / "output_stats.txt",
            out / "output_stdout.txt",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input alignment is required"
        phylip_format = str(inputs.get("phylip_format", ""))
        if phylip_format not in cls.PHYLIP_FORMAT_OPTIONS:
            return f"phylip_format must be one of: {', '.join(cls.PHYLIP_FORMAT_OPTIONS)}"
        type_of_seq = str(inputs.get("type_of_seq", "nt"))
        if type_of_seq not in cls.TYPE_OPTIONS:
            return f"type_of_seq must be one of: {', '.join(cls.TYPE_OPTIONS)}"
        if type_of_seq == "nt":
            nt_model = str(inputs.get("nt_model", inputs.get("model", "HKY85")))
            if nt_model not in cls.NT_MODEL_OPTIONS:
                return f"nt_model must be one of: {', '.join(cls.NT_MODEL_OPTIONS)}"
        else:
            aa_model = str(inputs.get("aa_model", "LG"))
            if aa_model not in cls.AA_MODEL_OPTIONS:
                return f"aa_model must be one of: {', '.join(cls.AA_MODEL_OPTIONS)}"
        if int(inputs.get("nb_data_set", 1)) < 1:
            return "nb_data_set must be >= 1"
        if int(inputs.get("nbSubstCat", 4)) < 1:
            return "nbSubstCat must be >= 1"
        branch_support = str(inputs.get("branchSupport", "-4"))
        if branch_support not in cls.BRANCH_SUPPORT_OPTIONS:
            return f"branchSupport must be one of: {', '.join(cls.BRANCH_SUPPORT_OPTIONS)}"
        if branch_support == "1" and int(inputs.get("replicate", 100)) < 1:
            return "replicate must be >= 1 when branchSupport is 1"
        move = str(inputs.get("move", "NNI"))
        if move not in cls.MOVE_OPTIONS:
            return f"move must be one of: {', '.join(cls.MOVE_OPTIONS)}"
        optimisation = str(inputs.get("optimisationTopology", "tlr"))
        if optimisation not in cls.OPTIMISATION_OPTIONS:
            return f"optimisationTopology must be one of: {', '.join(cls.OPTIMISATION_OPTIONS)}"
        equi_freq = str(inputs.get("equi_freq", "m"))
        if equi_freq not in cls.EQUI_FREQ_OPTIONS:
            return f"equi_freq must be one of: {', '.join(cls.EQUI_FREQ_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "FILE",
                    {"description": "PHYLIP alignment file for PhyML"},
                ),
            },
            "optional": {
                "phylip_format": (
                    "STRING",
                    {"default": "", "options": cls.PHYLIP_FORMAT_OPTIONS, "description": "Interleaved or sequential PHYLIP"},
                ),
                "nb_data_set": ("INT", {"default": 1, "min": 1, "description": "Number of datasets"}),
                "type_of_seq": (
                    "STRING",
                    {"default": "nt", "options": cls.TYPE_OPTIONS, "description": "Nucleotide or amino-acid alignment"},
                ),
                "tstv": (
                    "STRING",
                    {"default": "e", "description": "Transition/transversion ratio or e to estimate", "advanced": True},
                ),
                "nt_model": (
                    "STRING",
                    {"default": "HKY85", "options": cls.NT_MODEL_OPTIONS, "description": "Nucleotide substitution model"},
                ),
                "aa_model": (
                    "STRING",
                    {"default": "LG", "options": cls.AA_MODEL_OPTIONS, "description": "Amino-acid evolution model"},
                ),
                "prop_invar": (
                    "STRING",
                    {"default": "e", "description": "Invariant-site proportion or e to estimate"},
                ),
                "equi_freq": (
                    "STRING",
                    {"default": "m", "options": cls.EQUI_FREQ_OPTIONS, "description": "Equilibrium frequencies"},
                ),
                "nbSubstCat": (
                    "INT",
                    {"default": 4, "min": 1, "description": "Discrete gamma model category count"},
                ),
                "gamma": (
                    "STRING",
                    {"default": "e", "description": "Gamma model alpha parameter or e to estimate"},
                ),
                "move": (
                    "STRING",
                    {"default": "NNI", "options": cls.MOVE_OPTIONS, "description": "Tree topology search"},
                ),
                "optimisationTopology": (
                    "STRING",
                    {"default": "tlr", "options": cls.OPTIMISATION_OPTIONS, "description": "Optimized parameters"},
                ),
                "branchSupport": (
                    "STRING",
                    {
                        "default": "-4",
                        "options": cls.BRANCH_SUPPORT_OPTIONS,
                        "description": "Bootstrap or approximate branch support test",
                    },
                ),
                "replicate": (
                    "INT",
                    {"default": 100, "min": 1, "description": "Bootstrap replicate count when branchSupport is 1"},
                ),
                "numStartSeed": (
                    "INT",
                    {"default": 0, "description": "Random seed; 0 asks PhyML to choose a seed"},
                ),
                "userInputTree": (
                    "PHYLOGENY_TREE",
                    {"default": "", "description": "Optional Newick/NHX starting tree", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class FLASHNode(CommandNode):
    """Merge overlapping paired-end reads with FLASH."""

    NODE_ID = "flash"
    DISPLAY_NAME = "FLASH"
    REQUIRED_CONDA_PACKAGES = ["flash"]
    CATEGORY = "trimming"
    DESCRIPTION = "Merge paired-end reads with FLASH and emit merged, unmerged, log, and histogram outputs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "FLASH",
        "flash",
        "read merging",
        "paired-end merge",
        "overlap",
        "Fast Length Adjustment of SHort reads",
    ]
    RETURN_TYPES = (
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "TSV",
        "STATS_FILE",
        "STATS_FILE",
        "TSV",
        "TSV",
        "STATS_FILE",
        "STATS_FILE",
    )
    RETURN_NAMES = (
        "merged_reads",
        "unmerged_forward_reads",
        "unmerged_reverse_reads",
        "histogram_table",
        "raw_log",
        "histogram_text",
        "innie_histogram_table",
        "outie_histogram_table",
        "innie_histogram_text",
        "outie_histogram_text",
    )
    REQUIRED_EXECUTABLES = ["flash"]
    DOCUMENTATION_URL = "https://ccb.jhu.edu/software/FLASH/"
    CITATION_DOIS = [FLASH_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{FLASH_CITATION_DOI}"]
    CITATION_TEXT = FLASH_CITATION_TEXT
    VERSION = "1.2.11"
    SHELL = True

    @classmethod
    def _read_pair(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        if str(inputs.get("layout", "individual") or "individual") == "collection":
            reads = inputs.get("reads")
            if isinstance(reads, dict):
                return str(reads.get("forward", "")), str(reads.get("reverse", ""))
            read_list = _as_list(reads)
            return (read_list[0] if read_list else "", read_list[1] if len(read_list) > 1 else "")
        return str(inputs.get("forward", "")), str(inputs.get("reverse", ""))

    @classmethod
    def _fastq_suffix(cls, inputs: dict[str, Any]) -> str:
        return ".fastq.gz" if bool(inputs.get("gzip", False)) else ".fastq"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        forward, reverse = cls._read_pair(inputs)
        cmd = [
            "flash",
            f"--threads=${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}",
            "-m",
            str(inputs.get("min_overlap", 10)),
            "-M",
            str(inputs.get("max_overlap", 65)),
            "-x",
            str(inputs.get("max_mismatch_density", 0.25)),
        ]
        if inputs.get("allow_outies"):
            cmd.append("--allow-outies")
        cmd.extend([forward, reverse, "-p", str(inputs.get("phred_offset", 33))])
        if inputs.get("gzip"):
            cmd.append("-z")
        cmd.extend(["--output-prefix", f"{_out(inputs)}/out", "--output-suffix="])
        if inputs.get("save_log"):
            _add_shell_redirect(cmd, f"{_out(inputs)}/flash.log")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = cls._fastq_suffix(inputs)
        outputs = [
            out / f"out.extendedFrags{suffix}",
            out / f"out.notCombined_1{suffix}",
            out / f"out.notCombined_2{suffix}",
            out / "out.hist",
        ]
        if inputs.get("save_log"):
            outputs.append(out / "flash.log")
        if inputs.get("generate_histogram"):
            outputs.append(out / "out.histogram")
        if inputs.get("allow_outies"):
            outputs.extend([out / "out.hist.innie", out / "out.hist.outie"])
            if inputs.get("generate_histogram"):
                outputs.extend([out / "out.histogram.innie", out / "out.histogram.outie"])
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        forward, reverse = cls._read_pair(inputs)
        if str(inputs.get("layout", "individual") or "individual") == "collection":
            if not forward or not reverse:
                return "paired collection requires forward and reverse reads"
        elif not forward or not reverse:
            return "forward and reverse reads are required"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "layout": (
                    "STRING",
                    {
                        "default": "individual",
                        "options": ["individual", "collection"],
                        "description": "Use individual forward/reverse datasets or a paired collection",
                    },
                ),
                "forward": ("FASTQ", {"description": "Forward reads for individual dataset mode"}),
                "reverse": ("FASTQ", {"description": "Reverse reads for individual dataset mode"}),
            },
            "optional": {
                "reads": ("FASTQ_LIST", {"default": "", "description": "Paired collection [forward, reverse] or mapping"}),
                "min_overlap": ("INT", {"default": 10, "min": 1, "description": "Minimum required overlap length"}),
                "max_overlap": ("INT", {"default": 65, "min": 1, "description": "Maximum expected overlap length"}),
                "max_mismatch_density": (
                    "FLOAT",
                    {"default": 0.25, "min": 0, "description": "Maximum mismatch-to-overlap ratio"},
                ),
                "allow_outies": ("BOOLEAN", {"default": False, "description": "Try combining read pairs in both orientations"}),
                "generate_histogram": ("BOOLEAN", {"default": False, "description": "Emit text histogram outputs"}),
                "save_log": ("BOOLEAN", {"default": False, "description": "Save FLASH console log"}),
                "phred_offset": ("INT", {"default": 33, "options": [33, 64], "description": "FASTQ quality score offset"}),
                "gzip": ("BOOLEAN", {"default": False, "description": "Write gzip-compressed FASTQ outputs"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class PEARNode(CommandNode):
    """Merge paired-end reads with the Galaxy IUC PEAR wrapper behavior."""

    NODE_ID = "iuc_pear"
    DISPLAY_NAME = "Pear"
    REQUIRED_CONDA_PACKAGES = ["pear"]
    CATEGORY = "trimming"
    DESCRIPTION = "Merge paired-end reads with PEAR and emit selected assembled, unassembled, or discarded reads."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "PEAR",
        "Pear",
        "iuc_pear",
        "PEAR paired-end read merger",
        "paired-end read merger",
        "read merging",
        "Illumina paired-end merge",
    ]
    RETURN_TYPES = ("FASTQ", "FASTQ", "FASTQ", "FASTQ")
    RETURN_NAMES = (
        "assembled_reads",
        "unassembled_forward_reads",
        "unassembled_reverse_reads",
        "discarded_reads",
    )
    REQUIRED_EXECUTABLES = ["pear"]
    DOCUMENTATION_URL = "https://sco.h-its.org/exelixis/web/software/pear/doc.html"
    CITATION_DOIS = [PEAR_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{PEAR_CITATION_DOI}"]
    CITATION_TEXT = PEAR_CITATION_TEXT
    VERSION = "0.9.6.4"
    SHELL = True
    OUTPUT_CHOICES = ["assembled", "unassembled_forward", "unassembled_reverse", "discarded"]
    OUTPUT_FILES = {
        "assembled": "pear.assembled.fastq",
        "unassembled_forward": "pear.unassembled.forward.fastq",
        "unassembled_reverse": "pear.unassembled.reverse.fastq",
        "discarded": "pear.discarded.fastq",
    }
    TEST_METHODS = ["1", "2"]
    SCORE_METHODS = ["1", "2", "3"]

    @classmethod
    def _read_pair(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        if str(inputs.get("library_type", "paired") or "paired") == "paired_collection":
            collection = inputs.get("input_collection")
            if isinstance(collection, dict):
                return str(collection.get("forward", "")), str(collection.get("reverse", ""))
            reads = _as_list(collection)
            return (reads[0] if reads else "", reads[1] if len(reads) > 1 else "")
        return str(inputs.get("forward", "")), str(inputs.get("reverse", ""))

    @classmethod
    def _outputs(cls, inputs: dict[str, Any]) -> list[str]:
        outputs = _as_list(inputs.get("outputs"))
        return outputs if outputs else ["assembled"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        forward, reverse = cls._read_pair(inputs)
        cmd = [
            "pear",
            "-f",
            forward,
            "-r",
            reverse,
            "--phred-base",
            str(inputs.get("phred_base", "33")),
            "--output",
            f"{_out(inputs)}/pear",
            "--p-value",
            str(inputs.get("pvalue", 0.01)),
            "--min-overlap",
            str(inputs.get("min_overlap", 10)),
        ]
        max_assembly_length = int(inputs.get("max_assembly_length", 0) or 0)
        if max_assembly_length > 0:
            cmd.extend(["--max-asm-length", str(max_assembly_length)])
        cmd.extend(
            [
                "--min-asm-length",
                str(inputs.get("min_assembly_length", 50)),
                "--min-trim-length",
                str(inputs.get("min_trim_length", 1)),
                "--quality-theshold",
                str(inputs.get("quality_threshold", 0)),
                "--max-uncalled-base",
                str(inputs.get("max_uncalled_base", 1.0)),
                "--test-method",
                str(inputs.get("test_method", "1")),
                "--threads",
                f"${{GALAXY_SLOTS:-{inputs.get('threads', 8)}}}",
                "--score-method",
                str(inputs.get("score_method", "2")),
                "--cap",
                str(inputs.get("cap", 40)),
            ]
        )
        if inputs.get("empirical_freqs"):
            cmd.append("--empirical-freqs")
        if inputs.get("nbase"):
            cmd.append("--nbase")
        command = _shell_join(cmd)
        slot_token = f"${{GALAXY_SLOTS:-{inputs.get('threads', 8)}}}"
        return command.replace(shlex.quote(slot_token), slot_token)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILES[output] for output in cls._outputs(inputs) if output in cls.OUTPUT_FILES]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        library_type = str(inputs.get("library_type", "paired") or "paired")
        if library_type not in {"paired", "paired_collection"}:
            return "library_type must be one of: paired, paired_collection"
        forward, reverse = cls._read_pair(inputs)
        if library_type == "paired_collection":
            if not forward or not reverse:
                return "paired collection requires forward and reverse reads"
        elif not forward or not reverse:
            return "forward and reverse reads are required"

        if str(inputs.get("phred_base", "33")) not in {"33", "64"}:
            return "phred_base must be one of: 33, 64"
        if str(inputs.get("test_method", "1")) not in cls.TEST_METHODS:
            return "test_method must be one of: 1, 2"
        if str(inputs.get("score_method", "2")) not in cls.SCORE_METHODS:
            return "score_method must be one of: 1, 2, 3"

        for name in ("pvalue", "max_uncalled_base"):
            try:
                value = float(inputs.get(name, {"pvalue": 0.01, "max_uncalled_base": 1.0}[name]))
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if value < 0 or value > 1:
                return f"{name} must be between 0 and 1"
        for name, default in (
            ("min_overlap", 10),
            ("max_assembly_length", 0),
            ("min_assembly_length", 50),
            ("min_trim_length", 1),
            ("quality_threshold", 0),
            ("cap", 40),
        ):
            try:
                value = int(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 0:
                return f"{name} must be >= 0"
        unsupported_outputs = [output for output in cls._outputs(inputs) if output not in cls.OUTPUT_CHOICES]
        if unsupported_outputs:
            return f"outputs contains unsupported values: {', '.join(unsupported_outputs)}"

        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "library_type": (
                    "STRING",
                    {
                        "default": "paired",
                        "options": ["paired", "paired_collection"],
                        "description": "Use individual forward/reverse datasets or a paired collection",
                    },
                ),
            },
            "optional": {
                "forward": ("FASTQ", {"default": "", "description": "Forward reads for paired dataset mode"}),
                "reverse": ("FASTQ", {"default": "", "description": "Reverse reads for paired dataset mode"}),
                "input_collection": (
                    "FASTQ_LIST",
                    {"default": "", "description": "Paired collection [forward, reverse] or mapping"},
                ),
                "phred_base": (
                    "STRING",
                    {"default": "33", "options": ["33", "64"], "description": "FASTQ PHRED quality score base"},
                ),
                "pvalue": (
                    "FLOAT",
                    {
                        "default": 0.01,
                        "min": 0,
                        "max": 1,
                        "description": "P-value threshold for accepting an assembly overlap",
                    },
                ),
                "min_overlap": ("INT", {"default": 10, "min": 0, "description": "Minimum overlap size"}),
                "max_assembly_length": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Maximum assembled sequence length; 0 disables the cap"},
                ),
                "min_assembly_length": ("INT", {"default": 50, "min": 0, "description": "Minimum assembled sequence length"}),
                "min_trim_length": (
                    "INT",
                    {"default": 1, "min": 0, "description": "Minimum read length after low-quality trimming"},
                ),
                "quality_threshold": (
                    "INT",
                    {"default": 0, "description": "Quality threshold for trimming low-quality read tails"},
                ),
                "max_uncalled_base": (
                    "FLOAT",
                    {"default": 1.0, "min": 0, "max": 1, "description": "Maximum proportion of uncalled bases"},
                ),
                "cap": ("INT", {"default": 40, "min": 0, "description": "Upper bound for resulting quality scores"}),
                "test_method": (
                    "STRING",
                    {"default": "1", "options": cls.TEST_METHODS, "description": "Statistical test method"},
                ),
                "empirical_freqs": (
                    "BOOLEAN",
                    {"default": False, "description": "Disable empirical base frequencies"},
                ),
                "nbase": (
                    "BOOLEAN",
                    {"default": False, "description": "Use N when a merged base is uncertain"},
                ),
                "score_method": (
                    "STRING",
                    {"default": "2", "options": cls.SCORE_METHODS, "description": "PEAR scoring method"},
                ),
                "threads": ("INT", {"default": 8, "min": 1, "max": 128, "display": "slider"}),
                "outputs": (
                    "STRING",
                    {
                        "default": ["assembled"],
                        "multiple": True,
                        "options": cls.OUTPUT_CHOICES,
                        "description": "Selected PEAR FASTQ outputs",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class FragGeneScanNode(CommandNode):
    """Find complete and fragmented genes in short reads or assemblies."""

    NODE_ID = "fraggenescan"
    DISPLAY_NAME = "FragGeneScan"
    REQUIRED_CONDA_PACKAGES = ["fraggenescan"]
    CATEGORY = "annotation"
    DESCRIPTION = "Find complete and fragmented genes in short reads, incomplete assemblies, or complete genomes."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "FragGeneScan",
        "fraggenescan",
        "run_FragGeneScan.pl",
        "fragmented genes",
        "gene prediction",
        "short reads",
        "prokaryotic genes",
    ]
    RETURN_TYPES = ("TSV", "FASTA", "FASTA", "GFF")
    RETURN_NAMES = ("coordinates", "nucleotide_sequences", "protein_sequences", "gff")
    REQUIRED_EXECUTABLES = ["run_FragGeneScan.pl"]
    DOCUMENTATION_URL = "https://omics.informatics.indiana.edu/FragGeneScan/"
    CITATION_DOIS = [FRAGGENESCAN_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{FRAGGENESCAN_CITATION_DOI}"]
    CITATION_TEXT = FRAGGENESCAN_CITATION_TEXT
    VERSION = "1.30"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        complete = "1" if inputs.get("complete") else "0"
        return [
            "run_FragGeneScan.pl",
            "-genome",
            str(inputs.get("genome", "")),
            "-out",
            f"{_out(inputs)}/output_file_name",
            "-complete",
            complete,
            "-train",
            str(inputs.get("train", "complete")),
            f"-thread=${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}",
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [
            out / "output_file_name.out",
            out / "output_file_name.ffn",
            out / "output_file_name.faa",
            out / "output_file_name.gff",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("genome"):
            return "input FASTA is required"
        threads = inputs.get("threads", 4)
        try:
            if int(threads) < 1:
                return "threads must be >= 1"
        except (TypeError, ValueError):
            return "threads must be an integer"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genome": ("FASTA", {"description": "Input sequence file"}),
            },
            "optional": {
                "complete": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat input as complete genomic sequences"},
                ),
                "train": (
                    "STRING",
                    {
                        "default": "complete",
                        "options": [
                            "454_5",
                            "454_10",
                            "454_30",
                            "complete",
                            "gene",
                            "illumina_1",
                            "illumina_5",
                            "illumina_10",
                            "noncoding",
                            "pwm",
                            "rgene",
                            "sanger_5",
                            "sanger_10",
                            "start",
                            "start1",
                            "stop",
                            "stop1",
                        ],
                        "description": "FragGeneScan training model",
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ProdigalNode(CommandNode):
    """Predict protein-coding genes in microbial genomes with Prodigal."""

    NODE_ID = "prodigal"
    DISPLAY_NAME = "Prodigal Gene Predictor"
    REQUIRED_CONDA_PACKAGES = ["prodigal"]
    CATEGORY = "annotation"
    DESCRIPTION = "Predict protein-coding genes in microbial genomes, draft assemblies, and metagenomic sequences."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Prodigal",
        "prodigal",
        "gene prediction",
        "microbial genomes",
        "protein-coding genes",
        "translation initiation sites",
        "metagenomic gene prediction",
    ]
    RETURN_TYPES = ("FILE", "FASTA", "FASTA", "TSV")
    RETURN_NAMES = ("coordinates", "protein_translations", "nucleotide_sequences", "start_sites")
    REQUIRED_EXECUTABLES = ["prodigal"]
    DOCUMENTATION_URL = "https://github.com/hyattpd/Prodigal"
    CITATION_DOIS = [PRODIGAL_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{PRODIGAL_CITATION_DOI}"]
    CITATION_TEXT = PRODIGAL_CITATION_TEXT
    VERSION = "2.6.3"

    OUTPUT_FORMATS = {
        "gbk": "gbk",
        "gff": "gff3",
        "sqn": "sqn",
        "sco": "sco",
    }

    @classmethod
    def _coordinates_output(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "gbk") or "gbk")
        ext = cls.OUTPUT_FORMATS.get(out_format, "gbk")
        return f"{_out(inputs)}/output.{ext}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["prodigal", "-i", str(inputs.get("input_fa", ""))]
        if inputs.get("input_train"):
            cmd.extend(["-t", str(inputs.get("input_train"))])
        cmd.extend(
            [
                "-o",
                cls._coordinates_output(inputs),
                "-f",
                str(inputs.get("out_format", "gbk") or "gbk"),
                "-p",
                str(inputs.get("procedure", "single") or "single"),
                "-g",
                str(inputs.get("trans_table", "11") or "11"),
                "-a",
                f"{_out(inputs)}/output.faa",
                "-d",
                f"{_out(inputs)}/output.fnn",
                "-s",
                f"{_out(inputs)}/output.start",
            ]
        )
        if inputs.get("closed"):
            cmd.append("-c")
        if inputs.get("force_nonsd"):
            cmd.append("-n")
        if inputs.get("masked_seq"):
            cmd.append("-m")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        ext = cls.OUTPUT_FORMATS.get(str(inputs.get("out_format", "gbk") or "gbk"), "gbk")
        return [
            out / f"output.{ext}",
            out / "output.faa",
            out / "output.fnn",
            out / "output.start",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input_fa"):
            return "input FASTA is required"
        out_format = str(inputs.get("out_format", "gbk") or "gbk")
        if out_format not in cls.OUTPUT_FORMATS:
            return "out_format must be one of: gbk, gff, sqn, sco"
        procedure = str(inputs.get("procedure", "single") or "single")
        if procedure not in {"single", "meta"}:
            return "procedure must be one of: single, meta"
        trans_table = inputs.get("trans_table", "11") or "11"
        try:
            trans_table_int = int(trans_table)
        except (TypeError, ValueError):
            return "trans_table must be an integer from 1 to 25"
        if not 1 <= trans_table_int <= 25:
            return "trans_table must be an integer from 1 to 25"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fa": ("FASTA", {"description": "Input microbial genome, assembly, or metagenomic FASTA"}),
            },
            "optional": {
                "input_train": ("FASTA", {"default": "", "description": "Optional Prodigal training file"}),
                "out_format": (
                    "STRING",
                    {
                        "default": "gbk",
                        "options": ["gbk", "gff", "sqn", "sco"],
                        "description": "Coordinates output format",
                    },
                ),
                "procedure": (
                    "STRING",
                    {
                        "default": "single",
                        "options": ["single", "meta"],
                        "description": "Single-genome or metagenomic prediction mode",
                    },
                ),
                "trans_table": (
                    "STRING",
                    {
                        "default": "11",
                        "options": [str(value) for value in range(1, 26)],
                        "description": "NCBI translation table",
                    },
                ),
                "closed": ("BOOLEAN", {"default": False, "description": "Do not allow partial genes at sequence edges"}),
                "force_nonsd": (
                    "BOOLEAN",
                    {"default": False, "description": "Scan for motifs instead of using the Shine-Dalgarno RBS finder"},
                ),
                "masked_seq": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat runs of N as masked sequence"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class EukRepNode(CommandNode):
    """Classify eukaryotic and prokaryotic metagenomic sequences."""

    NODE_ID = "eukrep"
    DISPLAY_NAME = "EukRep"
    REQUIRED_CONDA_PACKAGES = ["eukrep"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Classify eukaryotic and prokaryotic sequences from metagenomic datasets with EukRep."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "EukRep",
        "eukrep",
        "metagenomic eukaryotes",
        "eukaryotic scaffolds",
        "prokaryotic sequences",
        "metagenome classification",
        "SVM k-mer classifier",
    ]
    RETURN_TYPES = ("FASTA", "FASTA", "STATS_FILE", "STATS_FILE")
    RETURN_NAMES = ("eukaryote_sequences", "prokaryote_sequences", "eukaryote_names", "prokaryote_names")
    REQUIRED_EXECUTABLES = ["EukRep"]
    DOCUMENTATION_URL = "https://github.com/patrickwest/EukRep"
    CITATION_DOIS = [EUKREP_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{EUKREP_CITATION_DOI}"]
    CITATION_TEXT = EUKREP_CITATION_TEXT
    VERSION = "0.6.7"
    SHELL = True

    @classmethod
    def _staged_input_name(cls, input_path: Any) -> str:
        suffixes = Path(str(input_path or "")).suffixes
        if len(suffixes) >= 2 and suffixes[-2:] == [".fa", ".gz"]:
            return "input.fa.gz"
        if len(suffixes) >= 2 and suffixes[-2:] == [".fasta", ".gz"]:
            return "input.fasta.gz"
        suffix = suffixes[-1] if suffixes else ".fa"
        return f"input{suffix}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged = cls._staged_input_name(inputs.get("input"))
        cmd = [
            "EukRep",
            "-i",
            staged,
            "-o",
            f"{_out(inputs)}/output.fa",
            "--min",
            str(inputs.get("min", 3000)),
            "--kmer_len",
            str(inputs.get("kmer_len", 5)),
        ]
        if inputs.get("prokarya"):
            cmd.extend(["--prokarya", f"{_out(inputs)}/output_prokarya.fa"])
        if inputs.get("seq_names"):
            cmd.append("--seq_names")
        cmd.extend(
            [
                "-m",
                str(inputs.get("stringency", "balanced") or "balanced"),
                "--tie",
                str(inputs.get("tie", "euk") or "euk"),
            ]
        )
        return f"ln -s {shlex.quote(str(inputs.get('input', '')))} {staged} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "output.fa"]
        if inputs.get("prokarya"):
            outputs.append(out / "output_prokarya.fa")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input"):
            return "input FASTA is required"
        try:
            min_length = int(inputs.get("min", 3000))
        except (TypeError, ValueError):
            return "min must be an integer"
        if min_length < 0:
            return "min must be >= 0"
        try:
            kmer_len = int(inputs.get("kmer_len", 5))
        except (TypeError, ValueError):
            return "kmer_len must be an integer"
        if not 3 <= kmer_len <= 6:
            return "kmer_len must be between 3 and 6"
        stringency = str(inputs.get("stringency", "balanced") or "balanced")
        if stringency not in {"strict", "balanced", "lenient"}:
            return "stringency must be one of: strict, balanced, lenient"
        tie = str(inputs.get("tie", "euk") or "euk")
        if tie not in {"euk", "prok", "rand", "skip"}:
            return "tie must be one of: euk, prok, rand, skip"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "Metagenomic sequences in FASTA or FASTA.GZ format"}),
            },
            "optional": {
                "min": ("INT", {"default": 3000, "min": 0, "description": "Minimum sequence length for prediction"}),
                "kmer_len": ("INT", {"default": 5, "min": 3, "max": 6, "description": "K-mer length"}),
                "prokarya": ("BOOLEAN", {"default": False, "description": "Also output predicted prokaryotic sequences"}),
                "seq_names": ("BOOLEAN", {"default": False, "description": "Output sequence headers instead of full FASTA records"}),
                "stringency": (
                    "STRING",
                    {
                        "default": "balanced",
                        "options": ["strict", "balanced", "lenient"],
                        "description": "Eukaryotic scaffold classification stringency",
                    },
                ),
                "tie": (
                    "STRING",
                    {
                        "default": "euk",
                        "options": ["euk", "prok", "rand", "skip"],
                        "description": "How to handle equal eukaryotic/prokaryotic chunk predictions",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class GAMMANode(CommandNode):
    """Find and annotate microbial gene matches with GAMMA."""

    NODE_ID = "gamma"
    DISPLAY_NAME = "GAMMA"
    REQUIRED_CONDA_PACKAGES = ["GAMMA"]
    CATEGORY = "annotation"
    DESCRIPTION = "Find and annotate gene matches in microbial assemblies using protein-coding identity with GAMMA."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "GAMMA",
        "Gene Allele Mutation Microbial Assessment",
        "gene match annotation",
        "antimicrobial resistance genes",
        "virulence genes",
        "protein coding identity",
    ]
    RETURN_TYPES = ("TSV", "GFF", "FASTA")
    RETURN_NAMES = ("gamma_out", "gamma_gff", "gamma_fasta")
    REQUIRED_EXECUTABLES = ["GAMMA.py"]
    DOCUMENTATION_URL = "https://github.com/rastanton/GAMMA"
    CITATION_DOIS = [GAMMA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{GAMMA_CITATION_DOI}"]
    CITATION_TEXT = GAMMA_CITATION_TEXT
    VERSION = "2.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "GAMMA.py",
            str(inputs.get("input_fasta", "")),
            str(inputs.get("input_db", "")),
            f"{_out(inputs)}/gamma_out",
        ]
        if inputs.get("all"):
            cmd.append("-a")
        cmd.extend(["-i", str(inputs.get("identity", 90))])
        if inputs.get("extended"):
            cmd.append("-e")
        if inputs.get("fasta"):
            cmd.append("-f")
        if inputs.get("gff"):
            cmd.append("-g")
        if inputs.get("headless"):
            cmd.append("-l")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "gamma_out.gamma"]
        if inputs.get("gff"):
            outputs.append(out / "gamma_out.gff")
        if inputs.get("fasta"):
            outputs.append(out / "gamma_out.fasta")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input_fasta"):
            return "input FASTA is required"
        if not inputs.get("input_db"):
            return "gene database FASTA is required"
        try:
            identity = int(inputs.get("identity", 90))
        except (TypeError, ValueError):
            return "identity must be an integer"
        if not 0 <= identity <= 100:
            return "identity must be between 0 and 100"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Genome or assembly FASTA to screen"}),
                "input_db": ("FASTA", {"description": "Multifasta coding-sequence gene database"}),
            },
            "optional": {
                "all": ("BOOLEAN", {"default": False, "description": "Include all gene matches, including overlaps"}),
                "identity": ("INT", {"default": 90, "min": 0, "max": 100, "description": "Minimum BLAT nucleotide identity percent"}),
                "extended": ("BOOLEAN", {"default": False, "description": "Return all gene mutations"}),
                "fasta": ("BOOLEAN", {"default": False, "description": "Write matched genes as FASTA"}),
                "gff": ("BOOLEAN", {"default": False, "description": "Write matched genes as GFF"}),
                "headless": ("BOOLEAN", {"default": False, "description": "Remove column headers from the GAMMA table"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class GAMMASNode(CommandNode):
    """Find nucleotide or protein gene matches with GAMMA-S."""

    NODE_ID = "gamma_s"
    DISPLAY_NAME = "GAMMA-S"
    REQUIRED_CONDA_PACKAGES = ["GAMMA"]
    CATEGORY = "annotation"
    DESCRIPTION = "Find gene matches in microbial assemblies using nucleotide identity with GAMMA-S."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "GAMMA-S",
        "gamma_s",
        "Gene Allele Mutation Microbial Assessment Sequence",
        "nucleotide gene matching",
        "protein-protein comparisons",
        "gene match annotation",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("gamma_s_out",)
    REQUIRED_EXECUTABLES = ["GAMMA-S.py"]
    DOCUMENTATION_URL = "https://github.com/rastanton/GAMMA"
    CITATION_DOIS = [GAMMA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{GAMMA_CITATION_DOI}"]
    CITATION_TEXT = GAMMA_CITATION_TEXT
    VERSION = "2.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "GAMMA-S.py",
            str(inputs.get("input_fasta", "")),
            str(inputs.get("input_db", "")),
            f"{_out(inputs)}/gamma-s_out",
        ]
        if inputs.get("all"):
            cmd.append("-a")
        cmd.extend(["-i", str(inputs.get("identity", 90))])
        if inputs.get("extended"):
            cmd.append("-e")
        if inputs.get("protein"):
            cmd.append("-p")
        cmd.extend(["-m", str(inputs.get("minimum", 20))])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "gamma-s_out.gamma"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input_fasta"):
            return "input FASTA is required"
        if not inputs.get("input_db"):
            return "gene database FASTA is required"
        for key in ("identity", "minimum"):
            try:
                value = int(inputs.get(key, 90 if key == "identity" else 20))
            except (TypeError, ValueError):
                return f"{key} must be an integer"
            if not 0 <= value <= 100:
                return f"{key} must be between 0 and 100"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Genome, assembly, or protein FASTA to screen"}),
                "input_db": ("FASTA", {"description": "Multifasta gene or protein database"}),
            },
            "optional": {
                "all": ("BOOLEAN", {"default": False, "description": "Include all gene matches, including overlaps"}),
                "identity": ("INT", {"default": 90, "min": 0, "max": 100, "description": "Minimum identity percent"}),
                "extended": ("BOOLEAN", {"default": False, "description": "Return all gene mutations"}),
                "protein": ("BOOLEAN", {"default": False, "description": "Perform protein-protein comparisons"}),
                "minimum": (
                    "INT",
                    {"default": 20, "min": 0, "max": 100, "description": "Minimum length percent match"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RedNode(CommandNode):
    """Detect and mask genomic repeats with RED."""

    NODE_ID = "red"
    DISPLAY_NAME = "Red"
    REQUIRED_CONDA_PACKAGES = ["red"]
    CATEGORY = "genomics"
    DESCRIPTION = "Detect and mask repeats de novo in genome FASTA sequences with RED."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Red",
        "RED",
        "REpeat Detector",
        "repeat masking",
        "de novo repeats",
        "genome masking",
    ]
    RETURN_TYPES = ("FASTA", "BED")
    RETURN_NAMES = ("masked", "bed")
    REQUIRED_EXECUTABLES = ["Red"]
    DOCUMENTATION_URL = "https://github.com/BioinformaticsToolsmith/Red"
    CITATION_DOIS = [RED_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{RED_CITATION_DOI}"]
    CITATION_TEXT = RED_CITATION_TEXT
    VERSION = "2018.09.10"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"
        cmd = [
            "Red",
            "-gnm",
            f"{out}/input/",
            "-msk",
            f"{out}/output/",
            "-rpt",
            f"{out}/output/",
            "-frm",
            "2",
            "-cor",
            slots,
        ]
        command = _shell_join(cmd).replace(shlex.quote(slots), slots)
        return (
            f"mkdir -p {shlex.quote(f'{out}/input')} {shlex.quote(f'{out}/output')} && "
            f"ln -s {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(f'{out}/input/genome.fa')} && "
            f"{command}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "output"
        out.mkdir(parents=True, exist_ok=True)
        return [out / "genome.msk", out / "genome.bed"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input"):
            return "genome FASTA is required"
        try:
            threads = int(inputs.get("threads", 1))
        except (TypeError, ValueError):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be >= 1"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "Genome FASTA sequence to mask"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AbriTAMRNode(CommandNode):
    """Run abriTAMR antimicrobial resistance gene detection."""

    NODE_ID = "abritamr"
    DISPLAY_NAME = "abriTAMR"
    REQUIRED_CONDA_PACKAGES = ["abritamr"]
    CATEGORY = "annotation"
    DESCRIPTION = "Detect and collate antimicrobial resistance genes, partial genes, and virulence factors with abriTAMR."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "abriTAMR",
        "abritamr",
        "AMR gene detection",
        "AMRFinderPlus",
        "antimicrobial resistance",
        "virulence summary",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV", "TSV", "STATS_FILE")
    RETURN_NAMES = ("abriTAMR_output", "matches_summary", "partials_summary", "virulence_summary", "log")
    REQUIRED_EXECUTABLES = ["abritamr"]
    DOCUMENTATION_URL = "https://github.com/MDU-PHL/abritamr"
    CITATION_DOIS = [ABRITAMR_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ABRITAMR_CITATION_DOI}"]
    CITATION_TEXT = ABRITAMR_CITATION_TEXT
    VERSION = "1.3.0"
    SHELL = True

    VALID_SPECIES = {
        "Neisseria",
        "Clostridioides_difficile",
        "Acinetobacter_baumannii",
        "Campylobacter",
        "Enterococcus_faecalis",
        "Enterococcus_faecium",
        "Escherichia",
        "Klebsiella",
        "Salmonella",
        "Staphylococcus_aureus",
        "Staphylococcus_pseudintermedius",
        "Streptococcus_agalactiae",
        "Streptococcus_pneumoniae",
        "Streptococcus_pyogenes",
    }

    @classmethod
    def _contigs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("contig"))

    @classmethod
    def _contig_labels(cls, inputs: dict[str, Any], contigs: list[str]) -> list[str]:
        labels = _as_list(inputs.get("contig_labels"))
        if len(labels) != len(contigs):
            return [Path(contig).name for contig in contigs]
        return labels

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        contigs = cls._contigs(inputs)
        labels = cls._contig_labels(inputs, contigs)
        manifest = f"{out}/input.tsv"
        printf_args = ["printf", "%s\\t%s\\n"]
        for label, contig in zip(labels, contigs):
            printf_args.extend([label, contig])
        setup = f"{_shell_join(printf_args)} > {shlex.quote(manifest)}"
        slots = f"${{GALAXY_SLOTS:-{inputs.get('jobs', 4)}}}"
        cmd = ["abritamr", "run", "--contigs", manifest]
        if inputs.get("species"):
            cmd.extend(["--species", str(inputs.get("species"))])
        if inputs.get("identity") not in (None, ""):
            cmd.extend(["--identity", str(inputs.get("identity"))])
        cmd.extend(["--jobs", slots])
        command = _shell_join(cmd).replace(shlex.quote(slots), slots)
        return f"{setup} && {command}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "abritamr.txt",
            out / "summary_matches.txt",
            out / "summary_partials.txt",
            out / "summary_virulence.txt",
        ]
        if inputs.get("log_file"):
            outputs.append(out / "abritamr.log")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._contigs(inputs):
            return "at least one contig FASTA is required"
        if inputs.get("species") not in (None, "") and str(inputs.get("species")) not in cls.VALID_SPECIES:
            return "species must be one of the supported abriTAMR species"
        if inputs.get("identity") not in (None, ""):
            try:
                identity = float(inputs.get("identity"))
            except (TypeError, ValueError):
                return "identity must be a number"
            if not 0 <= identity <= 1:
                return "identity must be between 0 and 1"
        try:
            jobs = int(inputs.get("jobs", 4))
        except (TypeError, ValueError):
            return "jobs must be an integer"
        if jobs < 1:
            return "jobs must be >= 1"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        species = sorted(cls.VALID_SPECIES)
        return {
            "required": {
                "contig": ("FASTA", {"list": True, "description": "One or more isolate contig FASTA files"}),
            },
            "optional": {
                "species": (
                    "STRING",
                    {"default": "", "options": species, "description": "Species for point-mutation resistance mechanisms"},
                ),
                "identity": (
                    "FLOAT",
                    {"default": "", "min": 0, "max": 1, "description": "Minimum AMRFinder identity threshold"},
                ),
                "log_file": ("BOOLEAN", {"default": False, "description": "Return the abriTAMR log file"}),
                "jobs": ("INT", {"default": 4, "min": 1, "max": 128, "description": "Worker processes"}),
                "contig_labels": (
                    "STRING",
                    {"default": "", "list": True, "advanced": True, "description": "Optional sample labels for the manifest"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class NonpareilNode(CommandNode):
    """Estimate metagenomic coverage and redundancy with Nonpareil."""

    NODE_ID = "nonpareil"
    DISPLAY_NAME = "Nonpareil"
    REQUIRED_CONDA_PACKAGES = ["nonpareil"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Estimate metagenomic coverage and generate Nonpareil redundancy curves from FASTA or FASTQ reads."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Nonpareil",
        "nonpareil",
        "metagenomic coverage",
        "redundancy curve",
        "sequencing effort",
        "library complexity",
    ]
    RETURN_TYPES = ("TSV", "TSV", "STATS_FILE", "JSON", "TSV")
    RETURN_NAMES = ("summary", "all_data_output", "log", "json_output", "mating_vector_output")
    REQUIRED_EXECUTABLES = ["nonpareil", "NonpareilCurves.R"]
    DOCUMENTATION_URL = "https://nonpareil.readthedocs.io/"
    CITATION_DOIS = [NONPAREIL_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{NONPAREIL_CITATION_DOI}"]
    CITATION_TEXT = NONPAREIL_CITATION_TEXT
    VERSION = "3.5.5"
    SHELL = True

    @classmethod
    def _summary_label(cls, inputs: dict[str, Any]) -> str:
        label = str(inputs.get("summary_label", Path(str(inputs.get("input", "nonpareil"))).name) or "nonpareil")
        return _safe_label(label)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        staged = f"{out}/input"
        summary_path = f"{out}/{cls._summary_label(inputs)}"
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 2)}}}"
        memory = f"${{NONPAREIL_MAX_MEMORY:-{inputs.get('max_memory', 1024)}}}"
        cmd = [
            "nonpareil",
            "-s",
            staged,
            "-T",
            str(inputs.get("algo", "kmer")),
            "-f",
            str(inputs.get("input_format", "fastq")),
            "-d",
            str(inputs.get("subsampling", 0.7)),
            "-n",
            str(inputs.get("subsample_per_point", 1024)),
            "-L",
            str(inputs.get("min_overlapping", 50)),
            "-X",
            str(inputs.get("max_query_reads", 1000)),
            "-R",
            memory,
            "-t",
            slots,
            "-b",
            f"{out}/output",
            "-a",
            f"{out}/all_data_output.tsv",
            "-C",
            f"{out}/mating_vector_output.tsv",
        ]
        if inputs.get("log_test"):
            cmd.extend(["-l", f"{out}/nonpareil.log"])
        cmd.extend(["-o", summary_path])
        if inputs.get("use_portion_in_output"):
            cmd.append("-F")
        cmd.extend(
            [
                "-m",
                str(inputs.get("min_sampling_portion", 0)),
                "-M",
                str(inputs.get("max_sampling_portion", 1)),
                "-i",
                str(inputs.get("sampling_portion_interval", 0.01)),
            ]
        )
        if inputs.get("use_rev_comp"):
            cmd.append("-c")
        if inputs.get("n_as_mismatches"):
            cmd.append("-N")
        if inputs.get("sim_thres") not in (None, ""):
            cmd.extend(["-S", str(inputs.get("sim_thres"))])
        cmd.extend(["-k", str(inputs.get("kmer_size", 24))])
        if inputs.get("proba") not in (None, ""):
            cmd.extend(["-x", str(inputs.get("proba"))])
        cmd.extend(["-r", str(inputs.get("seed", 1000))])
        command = _shell_join(cmd)
        command = command.replace(shlex.quote(memory), memory).replace(shlex.quote(slots), slots)
        parts = [
            f"ln -s {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(staged)}",
            command,
            f"cp {shlex.quote(summary_path)} {shlex.quote(f'{out}/summary.tsv')}",
        ]
        if inputs.get("json_object"):
            parts.append(f"NonpareilCurves.R --json {shlex.quote(f'{out}/curves.json')} {shlex.quote(summary_path)}")
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "summary.tsv", out / "all_data_output.tsv"]
        if inputs.get("log_test"):
            outputs.append(out / "nonpareil.log")
        if inputs.get("json_object"):
            outputs.append(out / "curves.json")
        outputs.append(out / "mating_vector_output.tsv")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input"):
            return "input sequences are required"
        algo = str(inputs.get("algo", "kmer") or "kmer")
        if algo not in {"alignment", "kmer"}:
            return "algo must be one of: alignment, kmer"
        input_format = str(inputs.get("input_format", "fastq") or "fastq")
        if input_format not in {"fasta", "fastq"}:
            return "input_format must be one of: fasta, fastq"
        for key in ("subsampling", "min_sampling_portion", "max_sampling_portion", "sampling_portion_interval"):
            try:
                value = float(inputs.get(key, {"subsampling": 0.7, "max_sampling_portion": 1, "sampling_portion_interval": 0.01}.get(key, 0)))
            except (TypeError, ValueError):
                return f"{key} must be a number"
            if value < 0:
                return f"{key} must be >= 0"
        for key, default in (
            ("subsample_per_point", 1024),
            ("max_query_reads", 1000),
            ("kmer_size", 24),
            ("seed", 1000),
            ("threads", 2),
            ("max_memory", 1024),
        ):
            try:
                value = int(inputs.get(key, default))
            except (TypeError, ValueError):
                return f"{key} must be an integer"
            if value < 0:
                return f"{key} must be >= 0"
            if key in {"threads", "max_memory"} and value < 1:
                return f"{key} must be >= 1"
        try:
            min_overlapping = int(inputs.get("min_overlapping", 50))
        except (TypeError, ValueError):
            return "min_overlapping must be an integer"
        if not 0 <= min_overlapping <= 100:
            return "min_overlapping must be between 0 and 100"
        for key in ("sim_thres", "proba"):
            if inputs.get(key) in (None, ""):
                continue
            try:
                value = float(inputs.get(key))
            except (TypeError, ValueError):
                return f"{key} must be a number"
            if value < 0:
                return f"{key} must be >= 0"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTQ", {"description": "Input FASTQ or FASTA sequences"}),
                "algo": ("STRING", {"default": "kmer", "options": ["kmer", "alignment"], "description": "Nonpareil algorithm"}),
                "input_format": ("STRING", {"default": "fastq", "options": ["fastq", "fasta"], "description": "Sequence file format"}),
            },
            "optional": {
                "subsampling": ("FLOAT", {"default": 0.7, "min": 0, "description": "Iterative subsampling factor"}),
                "subsample_per_point": ("INT", {"default": 1024, "min": 0, "description": "Subsamples per point"}),
                "min_overlapping": ("INT", {"default": 50, "min": 0, "max": 100, "description": "Minimum aligned overlap percent"}),
                "max_query_reads": ("INT", {"default": 1000, "min": 0, "description": "Maximum query reads"}),
                "use_portion_in_output": ("BOOLEAN", {"default": False, "description": "Report sampled portions as fractions"}),
                "min_sampling_portion": ("FLOAT", {"default": 0, "min": 0, "advanced": True}),
                "max_sampling_portion": ("FLOAT", {"default": 1, "min": 0, "advanced": True}),
                "sampling_portion_interval": ("FLOAT", {"default": 0.01, "min": 0, "advanced": True}),
                "use_rev_comp": ("BOOLEAN", {"default": False, "description": "Do not use reverse-complement matching"}),
                "n_as_mismatches": ("BOOLEAN", {"default": False, "description": "Treat Ns as mismatches"}),
                "sim_thres": ("FLOAT", {"default": "", "min": 0, "description": "Similarity threshold"}),
                "kmer_size": ("INT", {"default": 24, "min": 0, "description": "K-mer size"}),
                "proba": ("FLOAT", {"default": "", "min": 0, "description": "Probability of using a sequence as query"}),
                "seed": ("INT", {"default": 1000, "min": 0, "description": "Random seed"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 128}),
                "max_memory": ("INT", {"default": 1024, "min": 1, "description": "Fallback maximum memory in MB"}),
                "log_test": ("BOOLEAN", {"default": False, "description": "Return Nonpareil log"}),
                "json_object": ("BOOLEAN", {"default": False, "description": "Extract Nonpareil curve object as JSON"}),
                "summary_label": ("STRING", {"default": "", "advanced": True, "description": "Label used for intermediate summary file"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BBToolsBBDukNode(CommandNode):
    """Filter, trim, and mask reads with BBTools BBDuk."""

    NODE_ID = "bbtools_bbduk"
    DISPLAY_NAME = "BBTools BBDuk"
    REQUIRED_CONDA_PACKAGES = ["bbmap", "samtools"]
    CATEGORY = "trimming"
    DESCRIPTION = "Filter, trim, and mask FASTQ reads with k-mer matching, entropy filtering, and BBDuk statistics."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BBTools",
        "BBDuk",
        "bbduk",
        "bbtools_bbduk",
        "kmer decontamination",
        "adapter trimming",
        "entropy filtering",
        "FASTQ filtering",
        "quality histograms",
    ]
    RETURN_TYPES = (
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "TSV",
        "TSV",
        "TSV",
        "FASTA",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "TSV",
        "STATS_FILE",
    )
    RETURN_NAMES = (
        "forward_unmatched",
        "reverse_unmatched",
        "forward_matched",
        "reverse_matched",
        "singletons",
        "stats",
        "refstats",
        "rpkm",
        "dump",
        "base_composition_histogram",
        "quality_histogram",
        "quality_count_histogram",
        "average_quality_histogram",
        "boxplot_quality_histogram",
        "read_length_histogram",
        "polymer_length_histogram",
        "gc_histogram",
        "entropy_histogram",
        "log",
    )
    REQUIRED_EXECUTABLES = ["bbduk.sh"]
    DOCUMENTATION_URL = "https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/bbduk-guide/"
    CITATION_DOIS = [BBTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BBTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BBTOOLS_CITATION_TEXT
    VERSION = "39.08"
    SHELL = True

    STAT_OUTPUTS = {
        "stats": ("stats", "stats.tsv"),
        "ref": ("refstats", "refstats.tsv"),
        "rpkm": ("rpkm", "rpkm.tsv"),
        "dump": ("dump", "kmer_dump.fasta"),
    }
    HIST_OUTPUTS = {
        "bhist": ("bhist", "base_composition_histogram.tsv"),
        "quhist": ("qhist", "quality_histogram.tsv"),
        "quchist": ("qchist", "quality_count_histogram.tsv"),
        "aqhist": ("aqhist", "average_quality_histogram.tsv"),
        "bqhist": ("bqhist", "boxplot_quality_histogram.tsv"),
        "lhist": ("lhist", "read_length_histogram.tsv"),
        "phist": ("phist", "polymer_length_histogram.tsv"),
        "gchist": ("gchist", "gc_histogram.tsv"),
        "enthist": ("enthist", "entropy_histogram.tsv"),
    }

    @classmethod
    def _read_pair(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        input_type = cls._input_type(inputs)
        if input_type == "paired":
            collection = inputs.get("reads_collection")
            if isinstance(collection, dict):
                return str(collection.get("forward", "")), str(collection.get("reverse", ""))
            reads = _as_list(collection or inputs.get("reads"))
            return (reads[0] if reads else "", reads[1] if len(reads) > 1 else "")
        return str(inputs.get("read1", "")), str(inputs.get("read2", ""))

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        input_type = str(inputs.get("input_type", "single") or "single")
        return input_type if input_type in {"single", "pair", "paired"} else "single"

    @classmethod
    def _fastq_ext(cls, path: str) -> str:
        return ".fastq.gz" if str(path).endswith(".gz") else ".fastq"

    @classmethod
    def _selected(cls, inputs: dict[str, Any], key: str, default: str | None = None) -> set[str]:
        values = [default] if key not in inputs and default else _as_list(inputs.get(key))
        selected: set[str] = set()
        for value in values:
            selected.update(part.strip() for part in str(value).split(",") if part.strip())
        return selected

    @classmethod
    def _bool_value(cls, inputs: dict[str, Any], key: str, default: bool) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            return value if value in {"t", "f"} else ("t" if value.lower() in {"true", "yes", "1"} else "f")
        return "t" if bool(value) else "f"

    @classmethod
    def _stage_references(cls, inputs: dict[str, Any], out: str) -> tuple[list[str], str]:
        reference_type = str(inputs.get("reference_type", "no_reference") or "no_reference")
        if reference_type == "keywords":
            return [], ",".join(_as_list(inputs.get("reference")))
        if reference_type != "files":
            return [], ""

        setup: list[str] = []
        staged_refs: list[str] = []
        for ref in _as_list(inputs.get("reference")):
            staged = f"{out}/{Path(ref).name}.fa"
            staged_refs.append(staged)
            if ref.endswith(".gz"):
                setup.append(f"gunzip -c {shlex.quote(ref)} > {shlex.quote(staged)}")
            else:
                setup.append(f"ln -s {shlex.quote(ref)} {shlex.quote(staged)}")
        return setup, ",".join(staged_refs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_type = cls._input_type(inputs)
        read1, read2 = cls._read_pair(inputs)
        read1_file = f"{out}/forward{cls._fastq_ext(read1)}"
        setup = [f"ln -s {shlex.quote(read1)} {shlex.quote(read1_file)}"]
        if input_type in {"pair", "paired"}:
            read2_file = f"{out}/reverse{cls._fastq_ext(read1)}"
            setup.append(f"ln -s {shlex.quote(read2)} {shlex.quote(read2_file)}")
        else:
            read2_file = ""

        ref_setup, refs = cls._stage_references(inputs, out)
        setup.extend(ref_setup)

        outputs_select = cls._selected(inputs, "outputs_select", "outu")
        cmd = ["bbduk.sh", f"in={read1_file}"]
        if input_type in {"pair", "paired"}:
            cmd.append(f"in2={read2_file}")
        if "outu" in outputs_select:
            cmd.append(f"out={out}/forward_unmatched.fastq")
            if input_type in {"pair", "paired"}:
                cmd.append(f"out2={out}/reverse_unmatched.fastq")
        if "outm" in outputs_select:
            cmd.append(f"outm={out}/forward_matched.fastq")
            if input_type in {"pair", "paired"}:
                cmd.append(f"outm2={out}/reverse_matched.fastq")
        if "outs" in outputs_select:
            cmd.append(f"outs={out}/singletons.fastq")

        if refs:
            cmd.append(f"ref={refs}")
            cmd.append(f"k={inputs.get('k', 27)}")
            if inputs.get("ktrim") not in (None, "", "no"):
                cmd.append(f"ktrim={inputs.get('ktrim')}")
                cmd.append(f"minlength={inputs.get('minlength', 10)}")

        for key, default in (
            ("rcomp", True),
            ("maskmiddle", True),
            ("minkmerhits", 1),
            ("minkmerfraction", 0),
            ("mincovfraction", 0),
            ("hammingdistance", 0),
            ("qhdist", 0),
            ("editdistance", 0),
            ("forbidn", False),
            ("trimfailures", False),
            ("findbestmatch", False),
            ("skipr1", False),
            ("skipr2", False),
        ):
            if isinstance(default, bool):
                cmd.append(f"{key}={cls._bool_value(inputs, key, default)}")
            else:
                cmd.append(f"{key}={inputs.get(key, default)}")

        if float(inputs.get("entropy", 0) or 0) > 0:
            cmd.append(f"entropy={inputs.get('entropy')}")
            cmd.append(f"entropymask={inputs.get('entropymask', 'f')}")
            cmd.append(f"entropywindow={inputs.get('entropywindow', 50)}")
            cmd.append(f"entropyk={inputs.get('entropyk', 5)}")

        for selected, (argument, filename) in cls.STAT_OUTPUTS.items():
            if selected in cls._selected(inputs, "output_stats_select"):
                cmd.append(f"{argument}={out}/{filename}")
        for selected, (argument, filename) in cls.HIST_OUTPUTS.items():
            if selected in cls._selected(inputs, "output_hists_select"):
                cmd.append(f"{argument}={out}/{filename}")

        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"
        cmd.append(f"t={slots}")
        command = _shell_join(cmd).replace(shlex.quote(f"t={slots}"), f"t={slots}")
        if inputs.get("log_file"):
            command = f"{command} 2> >(tee {shlex.quote(f'{out}/bbduk.log')} >&2)"
        return " && ".join(setup + [command])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        input_type = cls._input_type(inputs)
        outputs: list[Path] = []
        outputs_select = cls._selected(inputs, "outputs_select", "outu")
        if "outu" in outputs_select:
            outputs.append(out / "forward_unmatched.fastq")
            if input_type in {"pair", "paired"}:
                outputs.append(out / "reverse_unmatched.fastq")
        if "outm" in outputs_select:
            outputs.append(out / "forward_matched.fastq")
            if input_type in {"pair", "paired"}:
                outputs.append(out / "reverse_matched.fastq")
        if "outs" in outputs_select:
            outputs.append(out / "singletons.fastq")
        for selected, (_argument, filename) in cls.STAT_OUTPUTS.items():
            if selected in cls._selected(inputs, "output_stats_select"):
                outputs.append(out / filename)
        for selected, (_argument, filename) in cls.HIST_OUTPUTS.items():
            if selected in cls._selected(inputs, "output_hists_select"):
                outputs.append(out / filename)
        if inputs.get("log_file"):
            outputs.append(out / "bbduk.log")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        read1, read2 = cls._read_pair(inputs)
        if not read1:
            return "read1 FASTQ is required"
        if input_type in {"pair", "paired"} and not read2:
            return "read2 FASTQ is required for paired input"
        reference_type = str(inputs.get("reference_type", "no_reference") or "no_reference")
        if reference_type == "files" and not _as_list(inputs.get("reference")):
            return "at least one reference FASTA is required when reference_type is files"
        if reference_type == "keywords" and not _as_list(inputs.get("reference")):
            return "at least one reference keyword is required when reference_type is keywords"
        if not cls._selected(inputs, "outputs_select", "outu"):
            return "at least one read output must be selected"
        for key in ("k", "minkmerhits", "entropywindow", "entropyk", "threads"):
            try:
                value = int(inputs.get(key, {"k": 27, "minkmerhits": 1, "entropywindow": 50, "entropyk": 5, "threads": 4}[key]))
            except (TypeError, ValueError):
                return f"{key} must be an integer"
            if value < 1:
                return f"{key} must be >= 1"
        for key in ("hammingdistance", "qhdist", "editdistance", "minlength"):
            if inputs.get(key) in (None, ""):
                continue
            try:
                value = int(inputs.get(key))
            except (TypeError, ValueError):
                return f"{key} must be an integer"
            if value < 0:
                return f"{key} must be >= 0"
        for key in ("minkmerfraction", "mincovfraction"):
            try:
                value = float(inputs.get(key, 0))
            except (TypeError, ValueError):
                return f"{key} must be a number"
            if value < 0:
                return f"{key} must be >= 0"
        try:
            entropy = float(inputs.get("entropy", 0) or 0)
        except (TypeError, ValueError):
            return "entropy must be a number"
        if not 0 <= entropy <= 1:
            return "entropy must be between 0 and 1"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": (
                    "STRING",
                    {"default": "single", "options": ["single", "pair", "paired"], "description": "Galaxy input mode"},
                ),
                "read1": ("FASTQ", {"description": "Single, forward, or paired-collection forward FASTQ reads"}),
            },
            "optional": {
                "read2": ("FASTQ", {"default": "", "description": "Reverse FASTQ reads for paired input"}),
                "reads_collection": ("FASTQ_LIST", {"default": "", "description": "Paired collection mapping or [forward, reverse]"}),
                "reference_type": (
                    "STRING",
                    {"default": "no_reference", "options": ["no_reference", "files", "keywords"], "description": "Reference source"},
                ),
                "reference": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "options": ["adapters", "artifacts", "phix", "lambda", "pjet", "mtst", "kapa"],
                        "description": "Reference FASTA paths or BBDuk keyword references",
                    },
                ),
                "outputs_select": (
                    "STRING_LIST",
                    {"default": ["outu"], "options": ["outu", "outm", "outs"], "description": "Read outputs to write"},
                ),
                "output_stats_select": (
                    "STRING_LIST",
                    {"default": [], "options": list(cls.STAT_OUTPUTS), "description": "Optional statistics outputs"},
                ),
                "output_hists_select": (
                    "STRING_LIST",
                    {"default": [], "options": list(cls.HIST_OUTPUTS), "description": "Optional histogram outputs"},
                ),
                "k": ("INT", {"default": 27, "min": 1, "description": "K-mer length used for contaminant matching"}),
                "ktrim": ("STRING", {"default": "", "options": ["", "r", "l"], "description": "Trim to the right or left after reference k-mer hits"}),
                "minlength": ("INT", {"default": 10, "min": 0, "description": "Minimum read length after k-trimming"}),
                "rcomp": ("BOOLEAN", {"default": True, "description": "Search reverse-complement k-mers"}),
                "maskmiddle": ("BOOLEAN", {"default": True, "description": "Treat middle k-mer base as wildcard"}),
                "minkmerhits": ("INT", {"default": 1, "min": 1, "description": "Minimum matching k-mers"}),
                "minkmerfraction": ("FLOAT", {"default": 0, "min": 0, "description": "Minimum fraction of k-mers matching"}),
                "mincovfraction": ("FLOAT", {"default": 0, "min": 0, "description": "Minimum base coverage by reference k-mers"}),
                "hammingdistance": ("INT", {"default": 0, "min": 0, "description": "Reference k-mer Hamming distance"}),
                "qhdist": ("INT", {"default": 0, "min": 0, "description": "Query k-mer Hamming distance"}),
                "editdistance": ("INT", {"default": 0, "min": 0, "description": "Reference k-mer edit distance"}),
                "forbidn": ("BOOLEAN", {"default": False, "description": "Reject k-mers containing N"}),
                "trimfailures": ("BOOLEAN", {"default": False, "description": "Trim failed reads to 1bp instead of discarding"}),
                "findbestmatch": ("BOOLEAN", {"default": False, "description": "Associate reads with best matching reference"}),
                "skipr1": ("BOOLEAN", {"default": False, "description": "Skip read 1 for k-mer operations"}),
                "skipr2": ("BOOLEAN", {"default": False, "description": "Skip read 2 for k-mer operations"}),
                "entropy": ("FLOAT", {"default": 0, "min": 0, "max": 1, "description": "Entropy threshold"}),
                "entropymask": ("STRING", {"default": "f", "options": ["f", "t", "lc"], "description": "Entropy mask mode"}),
                "entropywindow": ("INT", {"default": 50, "min": 1, "description": "Sliding entropy window"}),
                "entropyk": ("INT", {"default": 5, "min": 1, "description": "Entropy k-mer size"}),
                "log_file": ("BOOLEAN", {"default": False, "description": "Return BBDuk log output"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BBToolsBBMergeNode(CommandNode):
    """Merge paired reads with BBTools BBMerge."""

    NODE_ID = "bbtools_bbmerge"
    DISPLAY_NAME = "BBTools BBMerge"
    REQUIRED_CONDA_PACKAGES = ["bbmap", "samtools"]
    CATEGORY = "trimming"
    DESCRIPTION = "Merge overlapping paired-end reads with BBMerge and report unmerged reads plus insert-length histograms."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BBTools",
        "BBMerge",
        "bbmerge",
        "bbtools_bbmerge",
        "overlapping mates",
        "paired-end merge",
        "read merging",
        "insert length histogram",
        "error correction",
    ]
    RETURN_TYPES = ("FASTQ", "FASTQ", "TSV")
    RETURN_NAMES = ("merged_reads", "unmerged_reads", "insert_length_histogram")
    REQUIRED_EXECUTABLES = ["bbmerge.sh"]
    DOCUMENTATION_URL = "https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/bbmerge-guide/"
    CITATION_DOIS = [BBTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BBTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BBTOOLS_CITATION_TEXT
    VERSION = "39.08"
    SHELL = True

    STRICTNESS_OPTIONS = {"xstrict", "ustrict", "vstrict", "strict", "default", "loose", "vloose", "uloose", "xloose", "fast"}

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_type", "single") or "single")

    @classmethod
    def _read_pair(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        input_type = cls._input_type(inputs)
        if input_type == "paired":
            collection = inputs.get("reads_collection")
            if isinstance(collection, dict):
                return str(collection.get("forward", "")), str(collection.get("reverse", ""))
            reads = _as_list(collection or inputs.get("reads"))
            return (reads[0] if reads else "", reads[1] if len(reads) > 1 else "")
        return str(inputs.get("read1", "")), str(inputs.get("read2", ""))

    @classmethod
    def _fastq_ext(cls, path: str) -> str:
        return ".fastq.gz" if str(path).endswith(".gz") else ".fastq"

    @classmethod
    def _bool_value(cls, inputs: dict[str, Any], key: str, default: bool) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            if value in {"t", "f"}:
                return value
            return "t" if value.lower() in {"true", "yes", "1"} else "f"
        return "t" if bool(value) else "f"

    @classmethod
    def _java_memory_guard(cls, inputs: dict[str, Any]) -> str:
        memory = inputs.get("memory_mb", 4096)
        return (
            'if [[ "${_JAVA_OPTIONS}" != *-Xmx* && "${JAVA_TOOL_OPTIONS}" != *-Xmx* ]]; then '
            f'export _JAVA_OPTIONS="${{_JAVA_OPTIONS}} -Xmx${{GALAXY_MEMORY_MB:-{memory}}}m -Xms256m"; fi'
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_type = cls._input_type(inputs)
        read1, read2 = cls._read_pair(inputs)
        read1_file = f"{out}/forward{cls._fastq_ext(read1)}"
        setup = [f"ln -s {shlex.quote(read1)} {shlex.quote(read1_file)}"]
        if input_type in {"pair", "paired"}:
            read2_file = f"{out}/reverse{cls._fastq_ext(read1)}"
            setup.append(f"ln -s {shlex.quote(read2)} {shlex.quote(read2_file)}")
        else:
            read2_file = ""

        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 2)}}}"
        cmd = ["bbmerge.sh", 'tmpdir="$TMPDIR"', f't="{slots}"']
        if input_type == "single":
            cmd.extend([f"in={read1_file}", "interleaved=t"])
        else:
            cmd.extend([f"in1={read1_file}", f"in2={read2_file}", "interleaved=f"])
        cmd.extend(
            [
                f"out={out}/merged.fastq",
                f"outu={out}/unmerged.fastq",
                f"ihist={out}/ihist.tabular",
                "touppercase=t",
                f"qtrim={inputs.get('qtrim', 'f')}",
                f"trimq={inputs.get('trimq', 6)}",
                f"minlength={inputs.get('minlength_after_trim', 60)}",
                f"usequality={cls._bool_value(inputs, 'qt_usequality', True)}",
                "usejni=f",
                f"ecco={cls._bool_value(inputs, 'ecco', False)}",
                f"trimnonoverlapping={cls._bool_value(inputs, 'trimnonoverlapping', False)}",
                f"mininsert={inputs.get('mininsert', 35)}",
                f"minoverlap={inputs.get('minoverlap', 12)}",
                f"minq={inputs.get('minq', 9)}",
                f"maxq={inputs.get('maxq', 41)}",
                f"entropy={cls._bool_value(inputs, 'entropy', True)}",
                f"efilter={inputs.get('efilter', 6)}",
                f"pfilter={inputs.get('pfilter', '0.00004')}",
                f"kfilter={inputs.get('kfilter', 41)}",
                f"usequality={cls._bool_value(inputs, 'merge_usequality', True)}",
            ]
        )
        if inputs.get("adapter1") not in (None, "") or inputs.get("adapter2") not in (None, ""):
            cmd.extend([f"adapter1={inputs.get('adapter1', '')}", f"adapter2={inputs.get('adapter2', '')}"])
        if str(inputs.get("merge_mode", "Ratio mode")) == "Flat mode":
            cmd.extend(
                [
                    f"margin={inputs.get('margin', 2)}",
                    f"mismatches={inputs.get('mismatches', 3)}",
                    f"requireratiomatch={cls._bool_value(inputs, 'requireratiomatch', False)}",
                ]
            )
        else:
            cmd.extend(
                [
                    f"maxratio={inputs.get('maxratio', 0.09)}",
                    f"ratiomargin={inputs.get('ratiomargin', 5.5)}",
                    f"ratiooffset={inputs.get('ratiooffset', 0.55)}",
                    f"maxmismatches={inputs.get('maxmismatches', 20)}",
                    "ratiominoverlapreduction=0",
                    f"minsecondratio={inputs.get('minsecondratio', 0.1)}",
                ]
            )
        cmd.append(f"{inputs.get('strictness', 'default')}=t")
        command = _shell_join(cmd)
        command = command.replace(shlex.quote('tmpdir="$TMPDIR"'), 'tmpdir="$TMPDIR"')
        command = command.replace(shlex.quote(f't="{slots}"'), f't="{slots}"')
        return " && ".join(setup + [cls._java_memory_guard(inputs), command])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "merged.fastq", out / "unmerged.fastq", out / "ihist.tabular"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        if input_type not in {"single", "pair", "paired"}:
            return "input_type must be one of: single, pair, paired"
        read1, read2 = cls._read_pair(inputs)
        if not read1:
            return "read1 FASTQ is required"
        if input_type in {"pair", "paired"} and not read2:
            return "read2 FASTQ is required for paired input"
        if str(inputs.get("strictness", "default")) not in cls.STRICTNESS_OPTIONS:
            return "strictness must be one of the BBMerge strictness modes"
        for key, default in (
            ("threads", 2),
            ("memory_mb", 4096),
            ("trimq", 6),
            ("minlength_after_trim", 60),
            ("mininsert", 35),
            ("minoverlap", 12),
            ("minq", 9),
            ("maxq", 41),
            ("efilter", 6),
            ("kfilter", 41),
            ("maxmismatches", 20),
            ("margin", 2),
            ("mismatches", 3),
        ):
            try:
                value = int(inputs.get(key, default))
            except (TypeError, ValueError):
                return f"{key} must be an integer"
            if value < 1 and key in {"threads", "memory_mb", "minoverlap"}:
                return f"{key} must be >= 1"
            if value < 0 and key not in {"efilter"}:
                return f"{key} must be >= 0"
        for key, default in (
            ("pfilter", 0.00004),
            ("maxratio", 0.09),
            ("ratiomargin", 5.5),
            ("ratiooffset", 0.55),
            ("minsecondratio", 0.1),
        ):
            try:
                value = float(inputs.get(key, default))
            except (TypeError, ValueError):
                return f"{key} must be a number"
            if value < 0:
                return f"{key} must be >= 0"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": (
                    "STRING",
                    {"default": "single", "options": ["single", "pair", "paired"], "description": "Galaxy input mode"},
                ),
                "read1": ("FASTQ", {"description": "Single interleaved, forward, or paired-collection forward FASTQ"}),
            },
            "optional": {
                "read2": ("FASTQ", {"default": "", "description": "Reverse FASTQ reads for paired input"}),
                "reads_collection": ("FASTQ_LIST", {"default": "", "description": "Paired collection mapping or [forward, reverse]"}),
                "qtrim": ("STRING", {"default": "f", "options": ["f", "l", "r", "lr"], "description": "Quality trim mode"}),
                "trimq": ("INT", {"default": 6, "min": 0, "description": "Trim below this average quality"}),
                "minlength_after_trim": ("INT", {"default": 60, "min": 0, "description": "Minimum length after trimming"}),
                "qt_usequality": ("BOOLEAN", {"default": True, "description": "Use quality scores for trimming seeds"}),
                "ecco": ("BOOLEAN", {"default": False, "description": "Error-correct overlapping portions without merging"}),
                "trimnonoverlapping": ("BOOLEAN", {"default": False, "description": "Trim all non-overlapping sequence"}),
                "mininsert": ("INT", {"default": 35, "min": 0, "description": "Minimum insert size"}),
                "minoverlap": ("INT", {"default": 12, "min": 1, "description": "Minimum overlap length"}),
                "minq": ("INT", {"default": 9, "min": 0, "description": "Ignore bases below this quality"}),
                "maxq": ("INT", {"default": 41, "min": 0, "description": "Cap output qualities"}),
                "entropy": ("BOOLEAN", {"default": True, "description": "Increase overlap requirement for low-complexity reads"}),
                "efilter": ("INT", {"default": 6, "description": "Expected-error overlap filter; -1 disables"}),
                "pfilter": ("FLOAT", {"default": 0.00004, "min": 0, "description": "Probability filter for improbable overlaps"}),
                "kfilter": ("INT", {"default": 41, "min": 0, "description": "Low-count k-mer overlap filter"}),
                "merge_usequality": ("BOOLEAN", {"default": True, "description": "Use quality values in overlap detection"}),
                "adapter1": ("STRING", {"default": "", "description": "Left adapter sequence"}),
                "adapter2": ("STRING", {"default": "", "description": "Right adapter sequence"}),
                "merge_mode": ("STRING", {"default": "Ratio mode", "options": ["Ratio mode", "Flat mode"], "description": "Overlap scoring mode"}),
                "maxratio": ("FLOAT", {"default": 0.09, "min": 0, "description": "Ratio-mode maximum error rate"}),
                "ratiomargin": ("FLOAT", {"default": 5.5, "min": 0, "description": "Ratio-mode margin"}),
                "ratiooffset": ("FLOAT", {"default": 0.55, "min": 0, "description": "Ratio-mode offset"}),
                "maxmismatches": ("INT", {"default": 20, "min": 0, "description": "Ratio-mode maximum mismatches"}),
                "minsecondratio": ("FLOAT", {"default": 0.1, "min": 0, "description": "Ratio-mode second-best cutoff"}),
                "margin": ("INT", {"default": 2, "min": 0, "description": "Flat-mode best-overlap margin"}),
                "mismatches": ("INT", {"default": 3, "min": 0, "description": "Flat-mode maximum mismatches"}),
                "requireratiomatch": ("BOOLEAN", {"default": False, "description": "Require ratio and flat modes to agree"}),
                "strictness": ("STRING", {"default": "default", "options": sorted(cls.STRICTNESS_OPTIONS), "description": "BBMerge strictness preset"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 128}),
                "memory_mb": ("INT", {"default": 4096, "min": 1, "description": "Fallback Java heap in MB"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BBToolsBBNormNode(CommandNode):
    """Normalize sequencing coverage with BBTools BBNorm."""

    NODE_ID = "bbtools_bbnorm"
    DISPLAY_NAME = "BBTools BBNorm"
    REQUIRED_CONDA_PACKAGES = ["bbmap", "samtools"]
    CATEGORY = "qc"
    DESCRIPTION = "Normalize sequencing coverage with BBNorm count-min-sketch k-mer depth estimates."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BBTools",
        "BBNorm",
        "bbnorm",
        "bbtools_bbnorm",
        "coverage normalization",
        "digital normalization",
        "kmer depth",
        "count-min sketch",
        "read downsampling",
    ]
    RETURN_TYPES = ("FASTQ", "FASTQ", "FASTQ", "FASTQ", "TSV", "TSV")
    RETURN_NAMES = (
        "normalised_R1",
        "normalised_R2",
        "normalised_pair",
        "discarded_reads",
        "kmer_hist_input",
        "kmer_hist_output",
    )
    REQUIRED_EXECUTABLES = ["bbnorm.sh"]
    DOCUMENTATION_URL = "https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/bbnorm-guide/"
    CITATION_DOIS = [BBTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BBTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BBTOOLS_CITATION_TEXT
    VERSION = "39.08"
    SHELL = True

    INPUT_TYPES_ALLOWED = {"single_end", "PE_1file", "PE_2files", "paired"}

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_type", "PE_2files") or "PE_2files")

    @classmethod
    def _read_pair(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        input_type = cls._input_type(inputs)
        if input_type == "paired":
            collection = inputs.get("reads_collection")
            if isinstance(collection, dict):
                return str(collection.get("forward", "")), str(collection.get("reverse", ""))
            reads = _as_list(collection or inputs.get("reads"))
            return (reads[0] if reads else "", reads[1] if len(reads) > 1 else "")
        return str(inputs.get("read1", "")), str(inputs.get("read2", ""))

    @classmethod
    def _fastq_ext(cls, path: str) -> str:
        return ".fastq.gz" if str(path).endswith(".gz") else ".fastq"

    @classmethod
    def _bool_value(cls, inputs: dict[str, Any], key: str, default: bool) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            if value in {"t", "f"}:
                return value
            return "t" if value.lower() in {"true", "yes", "1"} else "f"
        return "t" if bool(value) else "f"

    @classmethod
    def _java_memory_guard(cls, inputs: dict[str, Any]) -> str:
        memory = inputs.get("memory_mb", 4096)
        return (
            'if [[ "${_JAVA_OPTIONS}" != *-Xmx* && "${JAVA_TOOL_OPTIONS}" != *-Xmx* ]]; then '
            f'export _JAVA_OPTIONS="${{_JAVA_OPTIONS}} -Xmx${{GALAXY_MEMORY_MB:-{memory}}}m -Xms256m"; fi'
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_type = cls._input_type(inputs)
        read1, read2 = cls._read_pair(inputs)
        read1_file = f"{out}/forward{cls._fastq_ext(read1)}"
        setup = [f"ln -s {shlex.quote(read1)} {shlex.quote(read1_file)}"]
        if input_type in {"PE_2files", "paired"}:
            read2_file = f"{out}/reverse{cls._fastq_ext(read2)}"
            setup.append(f"ln -s {shlex.quote(read2)} {shlex.quote(read2_file)}")
        else:
            read2_file = ""

        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 2)}}}"
        cmd = ["bbnorm.sh", 'tmpdir="$TMPDIR"', f't="{slots}"']
        if input_type == "single_end":
            cmd.extend([f"in={read1_file}", "interleaved=f"])
        elif input_type == "PE_1file":
            cmd.extend([f"in={read1_file}", "interleaved=t"])
        else:
            cmd.extend([f"in1={read1_file}", f"in2={read2_file}", "interleaved=f"])

        cmd.append(f"out={out}/normalised_R1.fastq")
        if input_type in {"PE_2files", "paired"}:
            cmd.append(f"out2={out}/normalised_R2.fastq")
        if inputs.get("save_discarded_reads"):
            cmd.append(f"outt={out}/discarded.fastq")
        cmd.append("touppercase=t")
        if inputs.get("save_kmer_hists"):
            cmd.extend([f"hist={out}/kmer_hist_input.tabular", f"histout={out}/kmer_hist_output.tabular"])

        cmd.extend(
            [
                f"k={inputs.get('k', 31)}",
                f"bits={inputs.get('bits', 16)}",
                f"hashes={inputs.get('hashes', 3)}",
            ]
        )
        if inputs.get("prefilter"):
            cmd.extend(
                [
                    "prefilter=t",
                    f"prehashes={inputs.get('prehashes', 2)}",
                    f"prefilterbits={inputs.get('prefilterbits', 2)}",
                    f"prefiltersize={inputs.get('prefiltersize', 0.35)}",
                ]
            )
        cmd.extend(
            [
                f"buildpasses={inputs.get('buildpasses', 1)}",
                f"minq={inputs.get('minq', 6)}",
                f"minprob={inputs.get('minprob', 0.5)}",
                f"rdk={cls._bool_value(inputs, 'rdk', True)}",
                f"fixspikes={cls._bool_value(inputs, 'fixspikes', False)}",
                f"target={inputs.get('target', 100)}",
                f"maxdepth={inputs.get('maxdepth', -1)}",
                f"mindepth={inputs.get('mindepth', 5)}",
                f"minkmers={inputs.get('minkmers', 15)}",
                f"percentile={inputs.get('percentile', 54)}",
                f"uselowerdepth={cls._bool_value(inputs, 'uselowerdepth', True)}",
                f"deterministic={cls._bool_value(inputs, 'deterministic', True)}",
                f"passes={inputs.get('passes', 2)}",
                f"hdp={inputs.get('hdp', 90)}",
                f"ldp={inputs.get('ldp', 25)}",
                f"tossbadreads={cls._bool_value(inputs, 'tossbadreads', False)}",
                f"requirebothbad={cls._bool_value(inputs, 'requirebothbad', False)}",
                f"errordetectratio={inputs.get('errordetectratio', 125)}",
                f"highthresh={inputs.get('highthresh', 12)}",
                f"lowthresh={inputs.get('lowthresh', 3)}",
            ]
        )
        if inputs.get("ecc"):
            cmd.extend(
                [
                    "ecc=t",
                    f"ecclimit={inputs.get('ecclimit', 3)}",
                    f"errorcorrectratio={inputs.get('errorcorrectratio', 140)}",
                    f"echighthresh={inputs.get('echighthresh', 22)}",
                    f"eclowthresh={inputs.get('eclowthresh', 2)}",
                    f"eccmaxqual={inputs.get('eccmaxqual', 127)}",
                    f"meo={cls._bool_value(inputs, 'meo', False)}",
                    f"mue={cls._bool_value(inputs, 'mue', True)}",
                    f"overlap={cls._bool_value(inputs, 'overlap', False)}",
                ]
            )

        command = _shell_join(cmd)
        command = command.replace(shlex.quote('tmpdir="$TMPDIR"'), 'tmpdir="$TMPDIR"')
        command = command.replace(shlex.quote(f't="{slots}"'), f't="{slots}"')
        return " && ".join(setup + [cls._java_memory_guard(inputs), command])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        input_type = cls._input_type(inputs)
        outputs = [out / "normalised_R1.fastq"]
        if input_type in {"PE_2files", "paired"}:
            outputs.append(out / "normalised_R2.fastq")
        if inputs.get("save_discarded_reads"):
            outputs.append(out / "discarded.fastq")
        if inputs.get("save_kmer_hists"):
            outputs.extend([out / "kmer_hist_input.tabular", out / "kmer_hist_output.tabular"])
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        if input_type not in cls.INPUT_TYPES_ALLOWED:
            return "input_type must be one of: single_end, PE_1file, PE_2files, paired"
        read1, read2 = cls._read_pair(inputs)
        if not read1:
            return "read1 FASTQ is required"
        if input_type in {"PE_2files", "paired"} and not read2:
            return "read2 FASTQ is required for paired input"

        min_one_keys = ("target", "k", "hashes", "buildpasses", "threads", "memory_mb", "prehashes", "prefilterbits", "passes")
        non_negative_keys = (
            "mindepth",
            "minkmers",
            "minq",
            "hdp",
            "ldp",
            "errordetectratio",
            "highthresh",
            "lowthresh",
            "ecclimit",
            "errorcorrectratio",
            "echighthresh",
            "eclowthresh",
            "eccmaxqual",
        )
        defaults = {
            "target": 100,
            "k": 31,
            "hashes": 3,
            "buildpasses": 1,
            "threads": 2,
            "memory_mb": 4096,
            "prehashes": 2,
            "prefilterbits": 2,
            "passes": 2,
            "mindepth": 5,
            "minkmers": 15,
            "minq": 6,
            "hdp": 90,
            "ldp": 25,
            "errordetectratio": 125,
            "highthresh": 12,
            "lowthresh": 3,
            "ecclimit": 3,
            "errorcorrectratio": 140,
            "echighthresh": 22,
            "eclowthresh": 2,
            "eccmaxqual": 127,
        }
        for key in (*min_one_keys, *non_negative_keys):
            try:
                value = int(inputs.get(key, defaults[key]))
            except (TypeError, ValueError):
                return f"{key} must be an integer"
            if key in min_one_keys and value < 1:
                return f"{key} must be >= 1"
            if key in non_negative_keys and value < 0:
                return f"{key} must be >= 0"

        try:
            percentile = int(inputs.get("percentile", 54))
        except (TypeError, ValueError):
            return "percentile must be an integer"
        if not 1 <= percentile <= 100:
            return "percentile must be between 1 and 100"
        for key, default in (("minprob", 0.5), ("prefiltersize", 0.35)):
            try:
                value = float(inputs.get(key, default))
            except (TypeError, ValueError):
                return f"{key} must be a number"
            if not 0 <= value <= 1:
                return f"{key} must be between 0 and 1"
        for key in ("bits",):
            try:
                value = int(inputs.get(key, 16))
            except (TypeError, ValueError):
                return f"{key} must be an integer"
            if value not in {2, 4, 8, 16, 32}:
                return "bits must be one of: 2, 4, 8, 16, 32"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": (
                    "STRING",
                    {
                        "default": "PE_2files",
                        "options": ["single_end", "PE_1file", "PE_2files", "paired"],
                        "description": "Galaxy input mode",
                    },
                ),
                "read1": ("FASTQ", {"description": "Single-end, interleaved, forward, or paired-collection forward FASTQ"}),
            },
            "optional": {
                "read2": ("FASTQ", {"default": "", "description": "Reverse FASTQ reads for two-file paired input"}),
                "reads_collection": ("FASTQ_LIST", {"default": "", "description": "Paired collection mapping or [forward, reverse]"}),
                "target": ("INT", {"default": 100, "min": 1, "description": "Target normalization k-mer depth"}),
                "maxdepth": ("INT", {"default": -1, "description": "Disable downsampling below this k-mer depth"}),
                "mindepth": ("INT", {"default": 5, "min": 0, "description": "Ignore k-mers below this depth"}),
                "minkmers": ("INT", {"default": 15, "min": 0, "description": "Minimum retained k-mers over depth threshold"}),
                "percentile": ("INT", {"default": 54, "min": 1, "max": 100, "description": "Percentile used to infer read depth"}),
                "uselowerdepth": ("BOOLEAN", {"default": True, "description": "Use lower mate depth for pairs"}),
                "deterministic": ("BOOLEAN", {"default": True, "description": "Generate random numbers deterministically"}),
                "fixspikes": ("BOOLEAN", {"default": False, "description": "Correct high-depth Bloom-filter collision spikes"}),
                "passes": ("INT", {"default": 2, "min": 1, "description": "Normalization passes"}),
                "k": ("INT", {"default": 31, "min": 1, "description": "K-mer length"}),
                "bits": ("INT", {"default": 16, "options": [2, 4, 8, 16, 32], "description": "Bits per count-min-sketch cell"}),
                "hashes": ("INT", {"default": 3, "min": 1, "description": "Number of hashes per k-mer"}),
                "prefilter": ("BOOLEAN", {"default": False, "description": "Enable low-depth k-mer prefilter"}),
                "prehashes": ("INT", {"default": 2, "min": 1, "description": "Prefilter hash count"}),
                "prefilterbits": ("INT", {"default": 2, "min": 1, "description": "Prefilter bits per cell"}),
                "prefiltersize": ("FLOAT", {"default": 0.35, "min": 0, "max": 1, "description": "Prefilter memory fraction"}),
                "buildpasses": ("INT", {"default": 1, "min": 1, "description": "Hashtable build passes"}),
                "minq": ("INT", {"default": 6, "min": 0, "description": "Ignore k-mers containing lower-quality bases"}),
                "minprob": ("FLOAT", {"default": 0.5, "min": 0, "max": 1, "description": "Minimum k-mer correctness probability"}),
                "rdk": ("BOOLEAN", {"default": True, "description": "Remove duplicate k-mers per read pair"}),
                "hdp": ("INT", {"default": 90, "min": 0, "max": 100, "description": "High-depth percentile"}),
                "ldp": ("INT", {"default": 25, "min": 0, "max": 100, "description": "Low-depth percentile"}),
                "tossbadreads": ("BOOLEAN", {"default": False, "description": "Discard reads detected as erroneous"}),
                "requirebothbad": ("BOOLEAN", {"default": False, "description": "Discard bad pairs only if both reads are bad"}),
                "errordetectratio": ("INT", {"default": 125, "min": 0, "description": "Error-detection depth ratio"}),
                "highthresh": ("INT", {"default": 12, "min": 0, "description": "High k-mer threshold"}),
                "lowthresh": ("INT", {"default": 3, "min": 0, "description": "Low k-mer threshold"}),
                "ecc": ("BOOLEAN", {"default": False, "description": "Correct detected errors when possible"}),
                "ecclimit": ("INT", {"default": 3, "min": 1, "description": "Maximum corrected errors per read"}),
                "errorcorrectratio": ("INT", {"default": 140, "min": 0, "description": "Error-correction depth ratio"}),
                "echighthresh": ("INT", {"default": 22, "min": 0, "description": "High threshold for correction"}),
                "eclowthresh": ("INT", {"default": 2, "min": 0, "description": "Low threshold for correction"}),
                "eccmaxqual": ("INT", {"default": 127, "min": 0, "description": "Do not correct bases above this quality"}),
                "meo": ("BOOLEAN", {"default": False, "description": "Mark errors only"}),
                "mue": ("BOOLEAN", {"default": True, "description": "Mark errors only on uncorrectable reads"}),
                "overlap": ("BOOLEAN", {"default": False, "description": "Correct errors using read overlap"}),
                "save_discarded_reads": ("BOOLEAN", {"default": False, "description": "Return discarded reads"}),
                "save_kmer_hists": ("BOOLEAN", {"default": False, "description": "Return input/output k-mer histograms"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 128}),
                "memory_mb": ("INT", {"default": 4096, "min": 1, "description": "Fallback Java heap in MB"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BBToolsTadpoleNode(CommandNode):
    """Assemble, extend, or correct reads with BBTools Tadpole."""

    NODE_ID = "bbtools_tadpole"
    DISPLAY_NAME = "BBTools Tadpole"
    REQUIRED_CONDA_PACKAGES = ["bbmap", "samtools"]
    CATEGORY = "assembly"
    DESCRIPTION = "Assemble, extend, or correct reads with Tadpole k-mer processing from BBTools."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BBTools",
        "Tadpole",
        "tadpole",
        "bbtools_tadpole",
        "kmer assembler",
        "error correction",
        "read extension",
        "contig mode",
        "fastadump",
    ]
    RETURN_TYPES = ("FASTQ", "FASTQ", "FASTA")
    RETURN_NAMES = ("output", "reverse_output", "fastadump")
    REQUIRED_EXECUTABLES = ["tadpole.sh"]
    DOCUMENTATION_URL = "https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/tadpole-guide/"
    CITATION_DOIS = [BBTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BBTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BBTOOLS_CITATION_TEXT
    VERSION = "39.08"
    SHELL = True

    VALID_MODES = {"contig", "extend", "correct"}
    VALID_INPUT_TYPES = {"single", "pair", "paired"}

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_type", "single") or "single")

    @classmethod
    def _read_pair(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        input_type = cls._input_type(inputs)
        if input_type == "paired":
            collection = inputs.get("reads_collection")
            if isinstance(collection, dict):
                return str(collection.get("forward", "")), str(collection.get("reverse", ""))
            reads = _as_list(collection or inputs.get("reads"))
            return (reads[0] if reads else "", reads[1] if len(reads) > 1 else "")
        return str(inputs.get("read1", "")), str(inputs.get("read2", ""))

    @classmethod
    def _fastq_ext(cls, path: str) -> str:
        return ".fastq.gz" if str(path).endswith(".gz") else ".fastq"

    @classmethod
    def _bool_value(cls, inputs: dict[str, Any], key: str, default: bool) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            if value in {"t", "f"}:
                return value
            return "t" if value.lower() in {"true", "yes", "1"} else "f"
        return "t" if bool(value) else "f"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_type = cls._input_type(inputs)
        read1, read2 = cls._read_pair(inputs)
        read1_file = f"{out}/forward{cls._fastq_ext(read1)}"
        setup = [f"ln -s {shlex.quote(read1)} {shlex.quote(read1_file)}"]
        if input_type in {"pair", "paired"}:
            read2_file = f"{out}/reverse{cls._fastq_ext(read1)}"
            setup.append(f"ln -s {shlex.quote(read2)} {shlex.quote(read2_file)}")
        else:
            read2_file = ""

        mode = str(inputs.get("mode", "contig") or "contig")
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"
        cmd = [
            "tadpole.sh",
            f"in={read1_file}",
        ]
        if input_type in {"pair", "paired"}:
            cmd.append(f"in2={read2_file}")
        cmd.extend(
            [
                f"fastadump={cls._bool_value(inputs, 'fastadump', True)}",
                f"mincounttodump={inputs.get('mincounttodump', 1)}",
            ]
        )
        if inputs.get("fastadump", True):
            cmd.append(f"dump={out}/fastadump.fasta")
        cmd.append(f"out={out}/output.fastq")
        if input_type in {"pair", "paired"} and mode != "contig":
            cmd.append(f"out2={out}/reverse_output.fastq")
        cmd.extend([f"mode={mode}", f"threads={slots}", "overwrite=true"])
        command = _shell_join(cmd).replace(shlex.quote(f"threads={slots}"), f"threads={slots}")
        return " && ".join(setup + [command])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        input_type = cls._input_type(inputs)
        mode = str(inputs.get("mode", "contig") or "contig")
        outputs = [out / "output.fastq"]
        if input_type in {"pair", "paired"} and mode != "contig":
            outputs.append(out / "reverse_output.fastq")
        if inputs.get("fastadump", True):
            outputs.append(out / "fastadump.fasta")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        if input_type not in cls.VALID_INPUT_TYPES:
            return "input_type must be one of: single, pair, paired"
        read1, read2 = cls._read_pair(inputs)
        if not read1:
            return "read1 FASTQ is required"
        if input_type in {"pair", "paired"} and not read2:
            return "read2 FASTQ is required for paired input"
        mode = str(inputs.get("mode", "contig") or "contig")
        if mode not in cls.VALID_MODES:
            return "mode must be one of: contig, extend, correct"
        for key, default in (("mincounttodump", 1), ("threads", 4)):
            try:
                value = int(inputs.get(key, default))
            except (TypeError, ValueError):
                return f"{key} must be an integer"
            if value < 1:
                return f"{key} must be >= 1"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": (
                    "STRING",
                    {"default": "single", "options": ["single", "pair", "paired"], "description": "Galaxy input mode"},
                ),
                "read1": ("FASTQ", {"description": "Single, forward, or paired-collection forward FASTQ"}),
            },
            "optional": {
                "read2": ("FASTQ", {"default": "", "description": "Reverse FASTQ reads for paired input"}),
                "reads_collection": ("FASTQ_LIST", {"default": "", "description": "Paired collection mapping or [forward, reverse]"}),
                "mode": ("STRING", {"default": "contig", "options": ["contig", "extend", "correct"], "description": "Tadpole processing mode"}),
                "fastadump": ("BOOLEAN", {"default": True, "description": "Write k-mers and counts as FASTA"}),
                "mincounttodump": ("INT", {"default": 1, "min": 1, "description": "Minimum k-mer depth to dump"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BBToolsCallVariantsNode(CommandNode):
    """Call variants from BAM alignments with BBTools CallVariants."""

    NODE_ID = "bbtools_callvariants"
    DISPLAY_NAME = "BBTools CallVariants"
    REQUIRED_CONDA_PACKAGES = ["bbmap", "samtools"]
    CATEGORY = "variant"
    DESCRIPTION = "Call variants from aligned BAM files with BBTools CallVariants."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BBTools",
        "CallVariants",
        "callvariants",
        "bbtools_callvariants",
        "variant caller",
        "BAM variants",
        "ploidy",
        "variant score histogram",
    ]
    RETURN_TYPES = ("VCF", "TSV", "TSV", "TSV")
    RETURN_NAMES = ("variants", "score_histogram", "zygosity_histogram", "quality_histogram")
    REQUIRED_EXECUTABLES = ["callvariants.sh"]
    DOCUMENTATION_URL = "https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/callvariants-guide/"
    CITATION_DOIS = [BBTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BBTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BBTOOLS_CITATION_TEXT
    VERSION = "39.08"
    SHELL = True

    OUTPUT_EXTENSIONS = {"vcf": ".vcf", "gff": ".gff", "txt": ".txt"}
    OUTPUT_ARGUMENTS = {"vcf": "vcf=out.vcf", "gff": "outgff=out.gff", "txt": "out=output.txt"}
    OUTPUT_TEMP_FILES = {"vcf": "out.vcf", "gff": "out.gff", "txt": "output.txt"}

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output_format", "vcf") or "vcf")

    @classmethod
    def _variants_output(cls, inputs: dict[str, Any], output_dir: str | Path) -> Path:
        return Path(output_dir) / cls.NODE_ID / f"variants{cls.OUTPUT_EXTENSIONS.get(cls._output_format(inputs), '.vcf')}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        staged_input = f"{out}/{_safe_name(str(inputs.get('input', '')))}.bam"
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"
        output_format = cls._output_format(inputs)
        cmd = [
            "callvariants.sh",
            f"in={staged_input}",
            f"threads={slots}",
            f"ref={inputs.get('reference', '')}",
            f"ploidy={inputs.get('ploidy', 1)}",
        ]
        if inputs.get("output_variant_score_hist"):
            cmd.append(f"shist={out}/score_histogram.tsv")
        if inputs.get("output_zygosity_hist"):
            cmd.append(f"zhist={out}/zygosity_histogram.tsv")
        if inputs.get("output_quality_hist"):
            cmd.append(f"qhist={out}/quality_histogram.tsv")
        cmd.append(cls.OUTPUT_ARGUMENTS.get(output_format, "vcf=out.vcf"))
        command = _shell_join(cmd).replace(shlex.quote(f"threads={slots}"), f"threads={slots}")
        temp_output = cls.OUTPUT_TEMP_FILES.get(output_format, "out.vcf")
        final_output = f"{out}/variants{cls.OUTPUT_EXTENSIONS.get(output_format, '.vcf')}"
        return (
            f"ln -s {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(staged_input)} && "
            f"{command} && mv {shlex.quote(temp_output)} {shlex.quote(final_output)}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [cls._variants_output(inputs, output_dir)]
        if inputs.get("output_variant_score_hist"):
            outputs.append(out / "score_histogram.tsv")
        if inputs.get("output_zygosity_hist"):
            outputs.append(out / "zygosity_histogram.tsv")
        if inputs.get("output_quality_hist"):
            outputs.append(out / "quality_histogram.tsv")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input"):
            return "input BAM is required"
        if not inputs.get("reference"):
            return "reference FASTA is required"
        output_format = cls._output_format(inputs)
        if output_format not in cls.OUTPUT_EXTENSIONS:
            return "output_format must be one of: vcf, gff, txt"
        for key, default in (("ploidy", 1), ("threads", 4)):
            try:
                value = int(inputs.get(key, default))
            except (TypeError, ValueError):
                return f"{key} must be an integer"
            if value < 1:
                return f"{key} must be >= 1"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM alignment file; BBMap output is recommended"}),
                "reference": ("FASTA", {"description": "Reference genome FASTA"}),
            },
            "optional": {
                "ploidy": ("INT", {"default": 1, "min": 1, "description": "Sample ploidy"}),
                "output_format": ("STRING", {"default": "vcf", "options": ["vcf", "gff", "txt"], "description": "Variant output format"}),
                "output_variant_score_hist": ("BOOLEAN", {"default": False, "description": "Return variant score histogram"}),
                "output_zygosity_hist": ("BOOLEAN", {"default": False, "description": "Return zygosity histogram"}),
                "output_quality_hist": ("BOOLEAN", {"default": False, "description": "Return variant quality histogram"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BBToolsBBMapNode(CommandNode):
    """Map short reads with BBTools BBMap."""

    NODE_ID = "bbtools_bbmap"
    DISPLAY_NAME = "BBTools BBMap"
    REQUIRED_CONDA_PACKAGES = ["bbmap", "samtools"]
    CATEGORY = "alignment"
    DESCRIPTION = "Map short reads to a reference genome with BBMap and emit all, unmapped, and mapped BAM files."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BBTools",
        "BBMap",
        "bbmap",
        "bbtools_bbmap",
        "short-read aligner",
        "read mapping",
        "BAM output",
        "mapped reads",
    ]
    RETURN_TYPES = ("BAM", "BAM", "BAM")
    RETURN_NAMES = ("all_reads", "unmapped_reads", "mapped_reads")
    REQUIRED_EXECUTABLES = ["bbmap.sh", "samtools"]
    DOCUMENTATION_URL = "https://jgi.doe.gov/data-and-tools/software-tools/bbtools/bb-tools-user-guide/bbmap-guide/"
    CITATION_DOIS = [BBTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BBTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BBTOOLS_CITATION_TEXT
    VERSION = "39.08"
    SHELL = True

    VALID_INPUT_TYPES = {"single", "pair", "paired"}
    VALID_OUTPUT_SORTS = {"coordinate", "name", "unsorted"}

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_type", "single") or "single")

    @classmethod
    def _read_pair(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        input_type = cls._input_type(inputs)
        if input_type == "paired":
            collection = inputs.get("reads_collection")
            if isinstance(collection, dict):
                return str(collection.get("forward", "")), str(collection.get("reverse", ""))
            reads = _as_list(collection or inputs.get("reads"))
            return (reads[0] if reads else "", reads[1] if len(reads) > 1 else "")
        return str(inputs.get("read1", "")), str(inputs.get("read2", ""))

    @classmethod
    def _fastq_ext(cls, path: str) -> str:
        return ".fastq.gz" if str(path).endswith(".gz") else ".fastq"

    @classmethod
    def _bool_value(cls, inputs: dict[str, Any], key: str, default: bool) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            if value in {"t", "f"}:
                return value
            return "t" if value.lower() in {"true", "yes", "1"} else "f"
        return "t" if bool(value) else "f"

    @classmethod
    def _add_output_sort(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        out = _out(inputs)
        output_sort = str(inputs.get("output_sort", "coordinate") or "coordinate")
        cmd.extend(["out=all_reads.bam", "outu=unmapped_reads.bam", "outm=mapped_reads.bam"])
        if output_sort == "coordinate":
            sort_flag = ""
        elif output_sort == "name":
            sort_flag = "-n "
        else:
            cmd.extend(
                [
                    "&&",
                    "mv",
                    "all_reads.bam",
                    f"{out}/all_reads.bam",
                    "&&",
                    "mv",
                    "unmapped_reads.bam",
                    f"{out}/unmapped_reads.bam",
                    "&&",
                    "mv",
                    "mapped_reads.bam",
                    f"{out}/mapped_reads.bam",
                ]
            )
            return
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"
        for source, target in (
            ("all_reads.bam", f"{out}/all_reads.bam"),
            ("unmapped_reads.bam", f"{out}/unmapped_reads.bam"),
            ("mapped_reads.bam", f"{out}/mapped_reads.bam"),
        ):
            cmd.extend(
                [
                    "&&",
                    "samtools",
                    "sort",
                    "--no-PG",
                    f"-@{slots}",
                ]
            )
            if sort_flag:
                cmd.append(sort_flag.strip())
            cmd.extend(["-T", "${TMPDIR:-.}", "-O", "bam", "-o", target, source])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_type = cls._input_type(inputs)
        read1, read2 = cls._read_pair(inputs)
        read1_file = f"{out}/forward{cls._fastq_ext(read1)}"
        setup = [f"ln -s {shlex.quote(read1)} {shlex.quote(read1_file)}"]
        if input_type in {"pair", "paired"}:
            read2_file = f"{out}/reverse{cls._fastq_ext(read1)}"
            setup.append(f"ln -s {shlex.quote(read2)} {shlex.quote(read2_file)}")
        else:
            read2_file = ""

        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}"
        cmd = [
            "bbmap.sh",
            "nodisk=f",
            f"ref={inputs.get('reference', '')}",
            "k=13",
            "usemodulo=f",
            "rebuild=f",
            f"in={read1_file}",
        ]
        if input_type in {"pair", "paired"}:
            cmd.append(f"in2={read2_file}")
        cmd.extend(
            [
                "fastareadlen=500",
                "unpigz=f",
                "touppercase=t",
                "reads=-1",
                "samplerate=1",
                "skipreads=0",
                f"maxindel={inputs.get('maxindel', 16000)}",
                f"strictmaxindel={cls._bool_value(inputs, 'strictmaxindel', False)}",
                f"tipsearch={inputs.get('tipsearch', 100)}",
                f"minid={inputs.get('minid', 0.76)}",
                f"minhits={inputs.get('minhits', 1)}",
                f"local={cls._bool_value(inputs, 'local', False)}",
                f"perfectmode={cls._bool_value(inputs, 'perfectmode', False)}",
                f"semiperfectmode={cls._bool_value(inputs, 'semiperfectmode', False)}",
                f"threads={slots}",
                f"ambiguous={inputs.get('ambiguous', 'best')}",
                f"samestrandpairs={cls._bool_value(inputs, 'samestrandpairs', False)}",
                f"requirecorrectstrand={cls._bool_value(inputs, 'requirecorrectstrand', True)}",
                f"killbadpairs={cls._bool_value(inputs, 'killbadpairs', False)}",
                f"pairedonly={cls._bool_value(inputs, 'pairedonly', False)}",
                f"rcomp={cls._bool_value(inputs, 'rcomp', False)}",
                f"rcompmate={cls._bool_value(inputs, 'rcompmate', False)}",
                f"pairlen={inputs.get('pairlen', 32000)}",
                f"rescuedist={inputs.get('rescuedist', 1200)}",
                f"rescuemismatches={inputs.get('rescuemismatches', 32)}",
                f"averagepairdist={inputs.get('averagepairdist', 100)}",
                f"deterministic={cls._bool_value(inputs, 'deterministic', False)}",
                f"bandwidthratio={inputs.get('bandwidthratio', 0)}",
                f"bandwidth={inputs.get('bandwidth', 0)}",
                "usejni=f",
                f"maxsites2={inputs.get('maxsites2', 800)}",
                f"ignorefrequentkmers={cls._bool_value(inputs, 'ignorefrequentkmers', True)}",
                f"excludefraction={inputs.get('excludefraction', 0.03)}",
                f"greedy={cls._bool_value(inputs, 'greedy', True)}",
                f"kfilter={inputs.get('kfilter', 0)}",
                "qin=auto",
                "qout=auto",
                f"qtrim={inputs.get('qtrim', 'f')}",
                f"untrim={cls._bool_value(inputs, 'untrim', False)}",
                f"trimq={inputs.get('trimq', 6)}",
                f"mintrimlength={inputs.get('mintrimlength', 60)}",
                f"fakefastaquality={inputs.get('fakefastaquality', -1)}",
                f"ignorebadquality={cls._bool_value(inputs, 'ignorebadquality', False)}",
                f"usequality={cls._bool_value(inputs, 'usequality', True)}",
                f"minaveragequality={inputs.get('minaveragequality', 0)}",
                f"maqb={inputs.get('maqb', 0)}",
                f"idfilter={inputs.get('idfilter', 0)}",
                f"subfilter={inputs.get('subfilter', -1)}",
                f"insfilter={inputs.get('insfilter', -1)}",
                f"delfilter={inputs.get('delfilter', -1)}",
                f"indelfilter={inputs.get('indelfilter', -1)}",
                f"editfilter={inputs.get('editfilter', -1)}",
                f"inslenfilter={inputs.get('inslenfilter', -1)}",
                f"dellenfilter={inputs.get('dellenfilter', -1)}",
                f"nfilter={inputs.get('nfilter', -1)}",
                f"secondary={cls._bool_value(inputs, 'secondary', False)}",
                f"maxsites={inputs.get('maxsites', 5)}",
                f"sssr={inputs.get('sssr', 0.95)}",
                f"ssao={cls._bool_value(inputs, 'ssao', False)}",
                f"quickmatch={cls._bool_value(inputs, 'quickmatch', False)}",
                f"trimreaddescriptions={cls._bool_value(inputs, 'trimreaddescriptions', False)}",
                f"machineout={cls._bool_value(inputs, 'machineout', False)}",
                f"printunmappedcount={cls._bool_value(inputs, 'printunmappedcount', False)}",
                f"renamebyinsert={cls._bool_value(inputs, 'renamebyinsert', False)}",
            ]
        )
        cls._add_output_sort(cmd, inputs)
        command = _shell_join(cmd)
        command = command.replace(shlex.quote(f"threads={slots}"), f"threads={slots}")
        command = command.replace(shlex.quote(f"-@{slots}"), f"-@{slots}")
        command = command.replace(shlex.quote("${TMPDIR:-.}"), "${TMPDIR:-.}")
        return " && ".join(setup + [command])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "all_reads.bam", out / "unmapped_reads.bam", out / "mapped_reads.bam"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        if input_type not in cls.VALID_INPUT_TYPES:
            return "input_type must be one of: single, pair, paired"
        read1, read2 = cls._read_pair(inputs)
        if not read1:
            return "read1 FASTQ is required"
        if input_type in {"pair", "paired"} and not read2:
            return "read2 FASTQ is required for paired input"
        if not inputs.get("reference"):
            return "reference FASTA is required"
        output_sort = str(inputs.get("output_sort", "coordinate") or "coordinate")
        if output_sort not in cls.VALID_OUTPUT_SORTS:
            return "output_sort must be one of: coordinate, name, unsorted"
        for key, default in (("threads", 4), ("minhits", 1), ("maxsites", 5), ("maxsites2", 800)):
            try:
                value = int(inputs.get(key, default))
            except (TypeError, ValueError):
                return f"{key} must be an integer"
            if value < 1:
                return f"{key} must be >= 1"
        try:
            minid = float(inputs.get("minid", 0.76))
        except (TypeError, ValueError):
            return "minid must be a number"
        if not 0 <= minid <= 1:
            return "minid must be between 0 and 1"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": (
                    "STRING",
                    {"default": "single", "options": ["single", "pair", "paired"], "description": "Galaxy input mode"},
                ),
                "read1": ("FASTQ", {"description": "Single, forward, or paired-collection forward FASTQ"}),
                "reference": ("FASTA", {"description": "Reference genome FASTA"}),
            },
            "optional": {
                "read2": ("FASTQ", {"default": "", "description": "Reverse FASTQ reads for paired input"}),
                "reads_collection": ("FASTQ_LIST", {"default": "", "description": "Paired collection mapping or [forward, reverse]"}),
                "output_sort": ("STRING", {"default": "coordinate", "options": ["coordinate", "name", "unsorted"], "description": "BAM sorting mode"}),
                "maxindel": ("INT", {"default": 16000, "description": "Maximum indel length"}),
                "strictmaxindel": ("BOOLEAN", {"default": False, "description": "Strictly disallow longer indels"}),
                "tipsearch": ("INT", {"default": 100, "description": "Read-end deletion search distance"}),
                "minid": ("FLOAT", {"default": 0.76, "min": 0, "max": 1, "description": "Approximate minimum identity"}),
                "minhits": ("INT", {"default": 1, "min": 1, "description": "Minimum seed hits"}),
                "local": ("BOOLEAN", {"default": False, "description": "Use local alignments"}),
                "ambiguous": ("STRING", {"default": "best", "options": ["best", "toss", "random", "all"], "description": "Ambiguous mapping behavior"}),
                "qtrim": ("STRING", {"default": "f", "options": ["f", "l", "r", "lr"], "description": "Quality trim mode"}),
                "trimq": ("INT", {"default": 6, "description": "Trim quality threshold"}),
                "secondary": ("BOOLEAN", {"default": False, "description": "Output secondary alignments"}),
                "maxsites": ("INT", {"default": 5, "min": 1, "description": "Maximum alignments per read"}),
                "idfilter": ("INT", {"default": 0, "min": 0, "max": 1, "description": "Minimum output alignment identity"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class PlasClassNode(CommandNode):
    """Classify assembled contigs as plasmid or chromosome sequences."""

    NODE_ID = "plasclass"
    DISPLAY_NAME = "PlasClass"
    REQUIRED_CONDA_PACKAGES = ["plasclass"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Classify plasmid and chromosome sequences in metagenomic or isolate assemblies with PlasClass."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "PlasClass",
        "plasclass",
        "plasmid sequence classification",
        "plasmid classifier",
        "chromosome classification",
        "metagenomic contigs",
        "isolate assemblies",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("classification_scores",)
    REQUIRED_EXECUTABLES = ["classify_fasta.py"]
    DOCUMENTATION_URL = "https://github.com/Shamir-Lab/PlasClass"
    CITATION_DOIS = [PLASCLASS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{PLASCLASS_CITATION_DOI}"]
    CITATION_TEXT = PLASCLASS_CITATION_TEXT
    VERSION = "0.1.1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return [
            "classify_fasta.py",
            "--fasta",
            str(inputs.get("fasta", "")),
            "--outfile",
            f"{_out(inputs)}/classification_scores.tsv",
            "--num_processes",
            f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}",
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "classification_scores.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("fasta"):
            return "input FASTA is required"
        threads = inputs.get("threads", 1)
        try:
            if int(threads) < 1:
                return "threads must be >= 1"
        except (TypeError, ValueError):
            return "threads must be an integer"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fasta": ("FASTA", {"description": "FASTA sequences to classify as plasmid or chromosome contigs"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class PlasFlowNode(CommandNode):
    """Predict plasmid-origin contigs with PlasFlow."""

    NODE_ID = "plasflow"
    DISPLAY_NAME = "PlasFlow"
    REQUIRED_CONDA_PACKAGES = ["plasflow"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Predict plasmid sequences in metagenomic contigs with PlasFlow genome-signature models."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "PlasFlow",
        "plasflow",
        "plasmid prediction",
        "metagenomic contigs",
        "genome signatures",
        "chromosome classification",
    ]
    RETURN_TYPES = ("TSV", "FASTA", "FASTA", "FASTA")
    RETURN_NAMES = ("probability_table", "chromosomes", "plasmids", "unclassified")
    REQUIRED_EXECUTABLES = ["PlasFlow.py"]
    DOCUMENTATION_URL = "https://github.com/smaegol/PlasFlow"
    CITATION_DOIS = [PLASFLOW_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{PLASFLOW_CITATION_DOI}"]
    CITATION_TEXT = PLASFLOW_CITATION_TEXT
    VERSION = "1.1.0"
    SHELL = True

    @classmethod
    def _is_gzipped_fasta(cls, input_path: Any) -> bool:
        return Path(str(input_path or "")).suffixes[-2:] == [".fasta", ".gz"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        read_file = str(inputs.get("read_file", ""))
        if cls._is_gzipped_fasta(read_file):
            stage = f"gunzip -c {shlex.quote(read_file)} > reads.fasta"
        else:
            stage = f"ln -s {shlex.quote(read_file)} reads.fasta"
        cmd = [
            "PlasFlow.py",
            "--input",
            "reads.fasta",
            "--output",
            f"{_out(inputs)}/output",
            "--threshold",
            str(inputs.get("threshold", 0.7)),
        ]
        return f"{stage} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [
            out / "output",
            out / "output_chromosomes.fasta",
            out / "output_plasmids.fasta",
            out / "output_unclassified.fasta",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("read_file"):
            return "contig FASTA is required"
        try:
            threshold = float(inputs.get("threshold", 0.7))
        except (TypeError, ValueError):
            return "threshold must be a number"
        if not 0 <= threshold <= 1:
            return "threshold must be between 0 and 1"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "read_file": ("FASTA", {"description": "Metagenomic contig sequences in FASTA or FASTA.GZ format"}),
            },
            "optional": {
                "threshold": (
                    "FLOAT",
                    {"default": 0.7, "min": 0, "max": 1, "description": "Probability threshold for classification"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MiniaNode(CommandNode):
    """Assemble short reads with the Minia de Bruijn graph assembler."""

    NODE_ID = "minia"
    DISPLAY_NAME = "Minia"
    REQUIRED_CONDA_PACKAGES = ["minia"]
    CATEGORY = "assembly"
    DESCRIPTION = "Assemble short reads into contigs with Minia, a compact de Bruijn graph assembler."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Minia",
        "minia",
        "short-read assembler",
        "de Bruijn graph",
        "Bloom filter",
        "contig assembly",
        "k-mer assembler",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("contigs",)
    REQUIRED_EXECUTABLES = ["minia"]
    DOCUMENTATION_URL = "https://github.com/GATB/minia"
    CITATION_DOIS = [MINIA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{MINIA_CITATION_DOI}"]
    CITATION_TEXT = MINIA_CITATION_TEXT
    VERSION = "3.2.6"
    SHELL = True

    @classmethod
    def _staged_input_name(cls, input_path: Any) -> str:
        suffixes = Path(str(input_path or "")).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == ".gz":
            return f"infile{suffixes[-2]}{suffixes[-1]}"
        suffix = suffixes[-1] if suffixes else ".fa"
        return f"infile{suffix}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged = cls._staged_input_name(inputs.get("in"))
        cmd = [
            "minia",
            "-in",
            staged,
            "-kmer-size",
            str(inputs.get("kmer_size", 31)),
        ]
        if inputs.get("abundance_min") not in (None, ""):
            cmd.extend(["-abundance-min", str(inputs.get("abundance_min"))])
        if inputs.get("abundance_max") not in (None, ""):
            cmd.extend(["-abundance-max", str(inputs.get("abundance_max"))])
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"
        cmd.extend(
            [
                "-nb-cores",
                slots,
                "-out",
                f"{_out(inputs)}/output",
            ]
        )
        command = _shell_join(cmd).replace(shlex.quote(slots), slots)
        return f"ln -s {shlex.quote(str(inputs.get('in', '')))} {staged} && {command}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.contigs.fa"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("in"):
            return "input reads are required"
        for key, message in (
            ("kmer_size", "kmer_size must be >= 1"),
            ("threads", "threads must be >= 1"),
        ):
            try:
                value = int(inputs.get(key, 31 if key == "kmer_size" else 1))
            except (TypeError, ValueError):
                return message.replace(">=", "must be an integer >=")
            if value < 1:
                return message
        for key in ("abundance_min", "abundance_max"):
            if inputs.get(key) in (None, ""):
                continue
            try:
                value = int(inputs.get(key))
            except (TypeError, ValueError):
                return f"{key} must be an integer"
            if value < 0:
                return f"{key} must be >= 0"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in": ("FASTQ", {"description": "Reads in FASTA, FASTQ, or compressed FASTA/FASTQ format"}),
            },
            "optional": {
                "kmer_size": ("INT", {"default": 31, "min": 1, "description": "K-mer size"}),
                "abundance_min": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum abundance threshold for solid k-mers"},
                ),
                "abundance_max": (
                    "INT",
                    {"default": "", "min": 0, "description": "Maximum abundance threshold for solid k-mers"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class GenomeScopeNode(CommandNode):
    """Profile genomes from k-mer spectra with GenomeScope 2.0."""

    NODE_ID = "genomescope"
    DISPLAY_NAME = "GenomeScope"
    REQUIRED_CONDA_PACKAGES = ["genomescope2"]
    CATEGORY = "assembly"
    DESCRIPTION = "Profile genomes from k-mer frequency histograms with the GenomeScope 2.0 model."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "GenomeScope",
        "GenomeScope 2.0",
        "genomescope2",
        "reference-free genome profiling",
        "k-mer spectrum",
        "kmer histogram",
        "polyploid genome profiling",
    ]
    RETURN_TYPES = ("IMAGE", "IMAGE", "IMAGE", "IMAGE", "TEXT", "TEXT", "TEXT", "TSV")
    RETURN_NAMES = (
        "linear_plot",
        "log_plot",
        "transformed_linear_plot",
        "transformed_log_plot",
        "model",
        "summary",
        "progress",
        "model_params",
    )
    REQUIRED_EXECUTABLES = ["genomescope2"]
    DOCUMENTATION_URL = "https://github.com/tbenavi1/genomescope2.0"
    CITATION_DOIS = GENOMESCOPE_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in GENOMESCOPE_CITATION_DOIS]
    CITATION_TEXT = GENOMESCOPE_CITATION_TEXT
    VERSION = "2.1.0+galaxy0"
    OUTPUT_CHOICES = ["model_output", "summary_output", "progress_output"]
    OUTPUT_FILES = {
        "model_output": "model.txt",
        "summary_output": "summary.txt",
        "progress_output": "progress.txt",
    }

    @classmethod
    def _output_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("output_files"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "genomescope2",
            "--input",
            str(inputs.get("input", "")),
            "--output",
            _out(inputs),
            "--kmer_length",
            str(inputs.get("kmer_length", 21)),
        ]
        if inputs.get("no_unique_sequence"):
            cmd.append("--no_unique_sequence")
        if inputs.get("testing"):
            cmd.append("--testing")
        if inputs.get("trace_flag"):
            cmd.append("--trace_flag")
        for name, flag in (
            ("ploidy", "--ploidy"),
            ("lambda", "--lambda"),
            ("max_kmercov", "--max_kmercov"),
            ("topology", "--topology"),
            ("initial_repetitiveness", "--initial_repetitiveness"),
            ("initial_heterozygosities", "--initial_heterozygosities"),
            ("transform_exp", "--transform_exp"),
            ("true_params", "--true_params"),
            ("num_rounds", "--num_rounds"),
        ):
            _add_if_value(cmd, flag, inputs.get(name))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "linear_plot.png",
            out / "log_plot.png",
            out / "transformed_linear_plot.png",
            out / "transformed_log_plot.png",
        ]
        outputs.extend(out / cls.OUTPUT_FILES[output] for output in cls._output_files(inputs) if output in cls.OUTPUT_FILES)
        if inputs.get("testing"):
            outputs.append(out / "SIMULATED_testing.tsv")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input histogram is required"
        for name, default, minimum, maximum in (
            ("kmer_length", 21, 1, None),
            ("ploidy", None, 1, 6),
            ("lambda", None, 1, None),
            ("max_kmercov", None, 1, None),
            ("topology", None, 1, None),
            ("transform_exp", None, 1, None),
            ("num_rounds", None, 1, None),
        ):
            raw = inputs.get(name, default)
            if raw in (None, ""):
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if minimum is not None and value < minimum:
                return f"{name} must be >= {minimum}"
            if maximum is not None and value > maximum:
                return f"{name} must be between {minimum} and {maximum}"
        repetitiveness = inputs.get("initial_repetitiveness")
        if repetitiveness not in (None, ""):
            try:
                repetitiveness_value = float(repetitiveness)
            except (TypeError, ValueError):
                return "initial_repetitiveness must be a number"
            if repetitiveness_value < 0 or repetitiveness_value > 1:
                return "initial_repetitiveness must be between 0 and 1"
        unsupported_outputs = [output for output in cls._output_files(inputs) if output not in cls.OUTPUT_CHOICES]
        if unsupported_outputs:
            return f"output_files contains unsupported values: {', '.join(unsupported_outputs)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "Two-column k-mer histogram, such as a Jellyfish histo output"}),
                "kmer_length": ("INT", {"default": 21, "min": 1, "description": "K-mer length used to calculate the spectra"}),
            },
            "optional": {
                "ploidy": ("INT", {"default": "", "min": 1, "max": 6, "description": "Ploidy for the GenomeScope model"}),
                "lambda": ("INT", {"default": "", "min": 1, "description": "Initial k-mer coverage estimate"}),
                "max_kmercov": ("INT", {"default": "", "min": 1, "description": "Maximum k-mer coverage threshold"}),
                "output_files": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "options": cls.OUTPUT_CHOICES,
                        "description": "Optional model, summary, and optimization progress reports",
                    },
                ),
                "no_unique_sequence": (
                    "BOOLEAN",
                    {"default": False, "description": "Turn off the yellow unique-sequence line in plots"},
                ),
                "topology": (
                    "INT",
                    {"default": "", "min": 1, "description": "Ploidy topology flag for homologous chromosome relationships"},
                ),
                "initial_repetitiveness": (
                    "FLOAT",
                    {"default": "", "min": 0, "max": 1, "description": "Initial repetitiveness value"},
                ),
                "initial_heterozygosities": (
                    "STRING",
                    {"default": "", "description": "Comma-separated initial nucleotide heterozygosity rates"},
                ),
                "transform_exp": (
                    "INT",
                    {"default": "", "min": 1, "description": "Exponent for transformed k-mer histogram fitting"},
                ),
                "testing": ("BOOLEAN", {"default": False, "description": "Create SIMULATED_testing.tsv with model parameters"}),
                "true_params": (
                    "STRING",
                    {"default": "", "description": "Comma-separated true simulated parameters for testing mode"},
                ),
                "trace_flag": (
                    "BOOLEAN",
                    {"default": False, "description": "Print nlsLM iteration progress"},
                ),
                "num_rounds": ("INT", {"default": "", "min": 1, "description": "Number of optimization rounds"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ARTIlluminaNode(CommandNode):
    """Simulate Illumina reads with ART using the Galaxy IUC wrapper options."""

    NODE_ID = "art_illumina"
    DISPLAY_NAME = "ART Illumina"
    REQUIRED_CONDA_PACKAGES = ["art"]
    CATEGORY = "simulation"
    DESCRIPTION = "Simulate Illumina sequencing reads from DNA or RNA reference sequences with ART."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ART",
        "ART Illumina",
        "art_illumina",
        "Illumina read simulator",
        "synthetic sequencing reads",
        "NGS read simulation",
        "paired-end simulation",
    ]
    RETURN_TYPES = ("FASTQ", "FASTQ", "FASTQ", "SAM", "TEXT", "TEXT", "TEXT")
    RETURN_NAMES = (
        "output_fq1_single",
        "output_fq1_paired",
        "output_fq2_paired",
        "output_sam",
        "output_aln1_single",
        "output_aln1_paired",
        "output_aln2_paired",
    )
    REQUIRED_EXECUTABLES = ["art_illumina"]
    DOCUMENTATION_URL = "https://www.niehs.nih.gov/research/resources/software/biostatistics/art"
    CITATION_DOIS = [ART_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ART_CITATION_DOI}"]
    CITATION_TEXT = ART_CITATION_TEXT
    VERSION = "2016.06.05+galaxy2016.06.05"
    GENERATE_CHOICES = ["single_end", "paired_end", "mate_pair"]

    @classmethod
    def _generate_choice(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("generate_choice", "single_end") or "single_end")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        choice = cls._generate_choice(inputs)
        cmd = ["art_illumina"]
        if inputs.get("sam"):
            cmd.append("--samout")
        if not inputs.get("aln", True):
            cmd.append("--noALN")
        if choice == "paired_end":
            cmd.append("--paired")
            cmd.extend(["--mflen", str(inputs.get("fragment_size", 200)), "--sdev", str(inputs.get("fragment_sd", 0))])
        elif choice == "mate_pair":
            cmd.append("--matepair")
            cmd.extend(["--mflen", str(inputs.get("fragment_size", 200)), "--sdev", str(inputs.get("fragment_sd", 0))])
        cmd.extend(
            [
                "--in",
                str(inputs.get("input_seq_file", "")),
                "--len",
                str(inputs.get("read_length", 100)),
                "--fcov",
                str(inputs.get("fold_coverage", 20)),
            ]
        )
        if inputs.get("amplicon"):
            cmd.append("--amplicon")
        cmd.extend(
            [
                "--insRate",
                str(inputs.get("insRate", "0.00009")),
                "--insRate2",
                str(inputs.get("insRate2", "0.00015")),
                "--delRate",
                str(inputs.get("delRate", "0.00011")),
                "--delRate2",
                str(inputs.get("delRate2", "0.00023")),
            ]
        )
        rnd_seed = int(inputs.get("rndSeed", -1) or -1)
        if rnd_seed > -1:
            cmd.extend(["--rndSeed", str(rnd_seed)])
        cmd.extend(["--out", f"{_out(inputs)}/output"])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        choice = cls._generate_choice(inputs)
        if choice == "single_end":
            outputs = [out / "output.fq"]
            if inputs.get("sam"):
                outputs.append(out / "output.sam")
            if inputs.get("aln", True):
                outputs.append(out / "output.aln")
            return outputs

        outputs = [out / "output1.fq", out / "output2.fq"]
        if inputs.get("sam"):
            outputs.append(out / "output.sam")
        if inputs.get("aln", True):
            outputs.extend([out / "output1.aln", out / "output2.aln"])
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_seq_file", "")).strip():
            return "input_seq_file is required"
        choice = cls._generate_choice(inputs)
        if choice not in cls.GENERATE_CHOICES:
            return f"generate_choice must be one of: {', '.join(cls.GENERATE_CHOICES)}"
        for name, default, minimum in (
            ("read_length", 100, 1),
            ("fold_coverage", 20, 1),
        ):
            try:
                value = int(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        if choice != "single_end":
            try:
                fragment_size = int(inputs.get("fragment_size", 200))
            except (TypeError, ValueError):
                return "fragment_size must be an integer"
            if fragment_size < 1:
                return f"fragment_size must be >= 1 for {choice} input"
            try:
                fragment_sd = int(inputs.get("fragment_sd", 0))
            except (TypeError, ValueError):
                return "fragment_sd must be an integer"
            if fragment_sd < 0:
                return f"fragment_sd must be >= 0 for {choice} input"
        for name, default in (
            ("insRate", 0.00009),
            ("insRate2", 0.00015),
            ("delRate", 0.00011),
            ("delRate2", 0.00023),
        ):
            try:
                value = float(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if value < 0:
                return f"{name} must be >= 0"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_seq_file": ("FASTA", {"description": "DNA or RNA reference sequence"}),
                "generate_choice": (
                    "STRING",
                    {
                        "default": "single_end",
                        "options": cls.GENERATE_CHOICES,
                        "description": "Generate single-end, paired-end, or mate-pair reads",
                    },
                ),
            },
            "optional": {
                "fold_coverage": ("INT", {"default": 20, "min": 1, "description": "Fold read coverage over references"}),
                "read_length": ("INT", {"default": 100, "min": 1, "description": "Simulated read length"}),
                "amplicon": ("BOOLEAN", {"default": False, "description": "Enable amplicon sequencing simulation"}),
                "fragment_size": (
                    "INT",
                    {"default": 200, "min": 1, "description": "Average DNA fragment size for paired or mate-pair reads"},
                ),
                "fragment_sd": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Fragment size standard deviation"},
                ),
                "aln": ("BOOLEAN", {"default": True, "description": "Output ART ALN alignment files"}),
                "sam": ("BOOLEAN", {"default": False, "description": "Output SAM alignment file"}),
                "insRate": ("FLOAT", {"default": 0.00009, "min": 0, "description": "First-read insertion rate"}),
                "insRate2": ("FLOAT", {"default": 0.00015, "min": 0, "description": "Second-read insertion rate"}),
                "delRate": ("FLOAT", {"default": 0.00011, "min": 0, "description": "First-read deletion rate"}),
                "delRate2": ("FLOAT", {"default": 0.00023, "min": 0, "description": "Second-read deletion rate"}),
                "rndSeed": ("INT", {"default": -1, "description": "Fixed random seed; -1 requests a random seed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ART454Node(CommandNode):
    """Simulate Roche 454 reads with ART using the Galaxy IUC wrapper options."""

    NODE_ID = "art_454"
    DISPLAY_NAME = "ART 454"
    REQUIRED_CONDA_PACKAGES = ["art"]
    CATEGORY = "simulation"
    DESCRIPTION = "Simulate Roche 454 pyrosequencing reads from DNA or RNA reference sequences with ART."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ART",
        "ART 454",
        "art_454",
        "454 pyrosequencing simulator",
        "Roche 454 read simulator",
        "synthetic pyrosequencing reads",
        "amplicon sequencing simulation",
    ]
    RETURN_TYPES = ("FASTQ", "FASTQ", "FASTQ", "SAM", "TEXT", "TEXT", "TEXT")
    RETURN_NAMES = (
        "output_fq1_single",
        "output_fq1_paired",
        "output_fq2_paired",
        "output_sam",
        "output_aln1_single",
        "output_aln1_paired",
        "output_aln2_paired",
    )
    REQUIRED_EXECUTABLES = ["art_454"]
    DOCUMENTATION_URL = "https://www.niehs.nih.gov/research/resources/software/biostatistics/art"
    CITATION_DOIS = [ART_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ART_CITATION_DOI}"]
    CITATION_TEXT = ART_CITATION_TEXT
    VERSION = "2016.06.05+galaxy2016.06.05"
    GENERATE_CHOICES = ["single_end", "paired_end"]

    @classmethod
    def _generate_choice(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("generate_choice", "single_end") or "single_end")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        choice = cls._generate_choice(inputs)
        cmd = ["art_454"]
        if inputs.get("t"):
            cmd.append("-t")
        if inputs.get("aln"):
            cmd.append("-a")
        if inputs.get("sam"):
            cmd.append("-s")
        rnd_seed = int(inputs.get("rndSeed", -1) or -1)
        if rnd_seed > -1:
            cmd.extend(["-r", str(rnd_seed)])
        if inputs.get("c", 100) not in (None, ""):
            cmd.extend(["-c", str(inputs.get("c", 100))])
        if inputs.get("amplicon"):
            cmd.append("-A" if choice == "single_end" else "-B")
        cmd.extend([str(inputs.get("input_seq_file", "")), f"{_out(inputs)}/output", str(inputs.get("fold_coverage", 20))])
        if choice != "single_end":
            cmd.extend([str(inputs.get("fragment_size", 200)), str(inputs.get("fragment_sd", 0))])
        if inputs.get("amplicon"):
            if choice == "single_end":
                cmd.append(str(inputs.get("reads_per_amplicon", 0)))
            else:
                cmd.append(str(inputs.get("read_pairs_per_amplicon", 0)))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        choice = cls._generate_choice(inputs)
        if choice == "single_end":
            outputs = [out / "output.fq"]
            if inputs.get("sam"):
                outputs.append(out / "output.sam")
            if inputs.get("aln"):
                outputs.append(out / "output.aln")
            return outputs

        outputs = [out / "output1.fq", out / "output2.fq"]
        if inputs.get("sam"):
            outputs.append(out / "output.sam")
        if inputs.get("aln"):
            outputs.append(out / "output1.aln")
        if inputs.get("amplicon"):
            outputs.append(out / "output2.aln")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_seq_file", "")).strip():
            return "input_seq_file is required"
        choice = cls._generate_choice(inputs)
        if choice not in cls.GENERATE_CHOICES:
            return f"generate_choice must be one of: {', '.join(cls.GENERATE_CHOICES)}"
        for name, default, minimum in (
            ("fold_coverage", 20, 1),
            ("c", 100, 1),
            ("rndSeed", -1, -1),
        ):
            raw = inputs.get(name, default)
            if raw in (None, "") and name == "c":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        if choice != "single_end":
            try:
                fragment_size = int(inputs.get("fragment_size", 200))
            except (TypeError, ValueError):
                return "fragment_size must be an integer"
            if fragment_size < 1:
                return f"fragment_size must be >= 1 for {choice} input"
            try:
                fragment_sd = int(inputs.get("fragment_sd", 0))
            except (TypeError, ValueError):
                return "fragment_sd must be an integer"
            if fragment_sd < 0:
                return f"fragment_sd must be >= 0 for {choice} input"
        if inputs.get("amplicon"):
            amplicon_count_name = "reads_per_amplicon" if choice == "single_end" else "read_pairs_per_amplicon"
            try:
                amplicon_count = int(inputs.get(amplicon_count_name, 0))
            except (TypeError, ValueError):
                return f"{amplicon_count_name} must be an integer"
            if amplicon_count < 0:
                return f"{amplicon_count_name} must be >= 0"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_seq_file": ("FASTA", {"description": "DNA or RNA reference sequence"}),
                "generate_choice": (
                    "STRING",
                    {
                        "default": "single_end",
                        "options": cls.GENERATE_CHOICES,
                        "description": "Generate single-end or paired-end 454 reads",
                    },
                ),
            },
            "optional": {
                "fold_coverage": ("INT", {"default": 20, "min": 1, "description": "Fold read coverage over references"}),
                "fragment_size": ("INT", {"default": 200, "min": 1, "description": "Average DNA fragment size"}),
                "fragment_sd": ("INT", {"default": 0, "min": 0, "description": "Fragment size standard deviation"}),
                "amplicon": ("BOOLEAN", {"default": False, "description": "Enable amplicon sequencing simulation"}),
                "reads_per_amplicon": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Reads per amplicon for single-end amplicon sequencing"},
                ),
                "read_pairs_per_amplicon": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Read pairs per amplicon for paired-end amplicon sequencing"},
                ),
                "aln": ("BOOLEAN", {"default": False, "description": "Output ART ALN alignment files"}),
                "sam": ("BOOLEAN", {"default": False, "description": "Output SAM alignment file"}),
                "t": (
                    "BOOLEAN",
                    {"default": False, "description": "Use the built-in GS FLX Titanium read profile"},
                ),
                "c": ("INT", {"default": 100, "min": 1, "description": "Number of sequencer flow cycles"}),
                "rndSeed": ("INT", {"default": -1, "description": "Fixed random seed; -1 requests a random seed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ARTSOLiDNode(CommandNode):
    """Simulate SOLiD reads with ART using the Galaxy IUC wrapper options."""

    NODE_ID = "art_solid"
    DISPLAY_NAME = "ART SOLiD"
    REQUIRED_CONDA_PACKAGES = ["art"]
    CATEGORY = "simulation"
    DESCRIPTION = "Simulate SOLiD sequencing reads from DNA or RNA reference sequences with ART."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ART",
        "ART SOLiD",
        "art_solid",
        "art_SOLiD",
        "SOLiD read simulator",
        "color-space read simulation",
        "mate-pair simulation",
    ]
    RETURN_TYPES = ("FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ", "SAM")
    RETURN_NAMES = (
        "output_fq1_single",
        "output_fq1_paired",
        "output_fq2_paired",
        "output_fq1_mate",
        "output_fq2_mate",
        "output_sam",
    )
    REQUIRED_EXECUTABLES = ["art_SOLiD"]
    DOCUMENTATION_URL = "https://www.niehs.nih.gov/research/resources/software/biostatistics/art"
    CITATION_DOIS = [ART_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ART_CITATION_DOI}"]
    CITATION_TEXT = ART_CITATION_TEXT
    VERSION = "2016.06.05+galaxy2016.06.05"
    GENERATE_CHOICES = ["single_end", "paired_end", "mate_pair"]

    @classmethod
    def _generate_choice(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("generate_choice", "single_end") or "single_end")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        choice = cls._generate_choice(inputs)
        cmd = ["art_SOLiD"]
        if inputs.get("sam"):
            cmd.append("-s")
        rnd_seed = int(inputs.get("rndSeed", -1) or -1)
        if rnd_seed > -1:
            cmd.extend(["-r", str(rnd_seed)])
        if inputs.get("amplicon"):
            cmd.extend(["-A", {"single_end": "s", "paired_end": "p", "mate_pair": "m"}.get(choice, "s")])
        cmd.extend([str(inputs.get("input_seq_file", "")), f"{_out(inputs)}/output"])
        if choice == "paired_end":
            cmd.extend(
                [
                    str(inputs.get("LEN_READ_F3", 100)),
                    str(inputs.get("LEN_READ_F5", 100)),
                    str(inputs.get("fold_coverage", 20)),
                    str(inputs.get("fragment_size", 200)),
                    str(inputs.get("fragment_sd", 0)),
                ]
            )
        else:
            cmd.extend(
                [
                    str(inputs.get("LEN_READ", 100)),
                    str(inputs.get("fold_coverage", 20)),
                ]
            )
            if choice == "mate_pair":
                cmd.extend([str(inputs.get("fragment_size", 200)), str(inputs.get("fragment_sd", 0))])
        if inputs.get("amplicon"):
            if choice == "single_end":
                cmd.append(str(inputs.get("reads_per_amplicon", 0)))
            else:
                cmd.append(str(inputs.get("read_pairs_per_amplicon", 0)))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        choice = cls._generate_choice(inputs)
        if choice == "paired_end":
            outputs = [out / "output_F3.fq", out / "output_F5.fq"]
        elif choice == "mate_pair":
            outputs = [out / "output_F3.fq", out / "output_R3.fq"]
        else:
            outputs = [out / "output.fq"]
        if inputs.get("sam"):
            outputs.append(out / "output.sam")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_seq_file", "")).strip():
            return "input_seq_file is required"
        choice = cls._generate_choice(inputs)
        if choice not in cls.GENERATE_CHOICES:
            return f"generate_choice must be one of: {', '.join(cls.GENERATE_CHOICES)}"
        for name, default, minimum in (
            ("fold_coverage", 20, 1),
            ("rndSeed", -1, -1),
        ):
            try:
                value = int(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        read_length_names = ("LEN_READ_F3", "LEN_READ_F5") if choice == "paired_end" else ("LEN_READ",)
        for name in read_length_names:
            try:
                value = int(inputs.get(name, 100))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 1:
                return f"{name} must be >= 1"
        if choice != "single_end":
            try:
                fragment_size = int(inputs.get("fragment_size", 200))
            except (TypeError, ValueError):
                return "fragment_size must be an integer"
            if fragment_size < 1:
                return f"fragment_size must be >= 1 for {choice} input"
            try:
                fragment_sd = int(inputs.get("fragment_sd", 0))
            except (TypeError, ValueError):
                return "fragment_sd must be an integer"
            if fragment_sd < 0:
                return f"fragment_sd must be >= 0 for {choice} input"
        if inputs.get("amplicon"):
            amplicon_count_name = "reads_per_amplicon" if choice == "single_end" else "read_pairs_per_amplicon"
            try:
                amplicon_count = int(inputs.get(amplicon_count_name, 0))
            except (TypeError, ValueError):
                return f"{amplicon_count_name} must be an integer"
            if amplicon_count < 0:
                return f"{amplicon_count_name} must be >= 0"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_seq_file": ("FASTA", {"description": "DNA or RNA reference sequence"}),
                "generate_choice": (
                    "STRING",
                    {
                        "default": "single_end",
                        "options": cls.GENERATE_CHOICES,
                        "description": "Generate single-end, paired-end, or mate-pair SOLiD reads",
                    },
                ),
            },
            "optional": {
                "fold_coverage": ("INT", {"default": 20, "min": 1, "description": "Fold read coverage over references"}),
                "LEN_READ": ("INT", {"default": 100, "min": 1, "description": "Length of F3/R3 reads"}),
                "LEN_READ_F3": ("INT", {"default": 100, "min": 1, "description": "Length of F3 reads"}),
                "LEN_READ_F5": ("INT", {"default": 100, "min": 1, "description": "Length of F5 reads"}),
                "fragment_size": ("INT", {"default": 200, "min": 1, "description": "Average DNA fragment size"}),
                "fragment_sd": ("INT", {"default": 0, "min": 0, "description": "Fragment size standard deviation"}),
                "amplicon": ("BOOLEAN", {"default": False, "description": "Enable amplicon sequencing simulation"}),
                "reads_per_amplicon": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Reads per amplicon for single-end amplicon sequencing"},
                ),
                "read_pairs_per_amplicon": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Read pairs per amplicon for paired or mate-pair amplicon sequencing"},
                ),
                "sam": ("BOOLEAN", {"default": False, "description": "Output SAM alignment file"}),
                "rndSeed": ("INT", {"default": -1, "description": "Fixed random seed; -1 requests a random seed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AmpliCanNode(CommandNode):
    """Analyze genome editing amplicon sequencing data with ampliCan."""

    NODE_ID = "amplican"
    DISPLAY_NAME = "AmpliCan"
    REQUIRED_CONDA_PACKAGES = ["bioconductor-amplican"]
    CATEGORY = "crispr"
    DESCRIPTION = "Analyze CRISPR and other genome editing amplicon sequencing experiments with ampliCan."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AmpliCan",
        "amplican",
        "CRISPR editing analysis",
        "genome editing amplicons",
        "amplicon sequencing",
        "HDR repair",
        "base editing",
    ]
    RETURN_TYPES = ("CSV", "TSV", "HTML_REPORT", "TXT", "FILE", "FASTA", "TXT", "CSV", "CSV", "CSV", "CSV")
    RETURN_NAMES = (
        "config_summary",
        "barcode_reads",
        "output_html",
        "parameters",
        "alignments_rds",
        "alignments_fasta",
        "alignments_txt",
        "events_filtered_shifted",
        "events_filtered_shifted_normalized",
        "raw_events",
        "unassigned_reads",
    )
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://bioconductor.org/packages/amplican"
    CITATION_DOIS = [AMPLICAN_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{AMPLICAN_CITATION_DOI}"]
    CITATION_TEXT = AMPLICAN_CITATION_TEXT
    VERSION = "1.14.0+galaxy1"
    SHELL = True

    OUTPUT_CHOICES = [
        "config_summary",
        "barcode_reads",
        "knit_reports",
        "parameters",
        "alignments_rds",
        "events_filtered_shifted",
        "events_filtered_shifted_normalized",
        "raw_events",
        "unassigned_reads",
    ]
    DEFAULT_OUTPUTS = [
        "config_summary",
        "barcode_reads",
        "knit_reports",
        "alignments_rds",
        "events_filtered_shifted",
        "events_filtered_shifted_normalized",
        "raw_events",
        "unassigned_reads",
    ]
    OUTPUT_FILES = {
        "config_summary": "config_summary.csv",
        "barcode_reads": "barcode_reads_filters.csv",
        "knit_reports": "reports/index.html",
        "parameters": "RunParameters.txt",
        "alignments_rds": "alignments/AlignmentsExperimentSet.rds",
        "events_filtered_shifted": "alignments/events_filtered_shifted.csv",
        "events_filtered_shifted_normalized": "alignments/events_filtered_shifted_normalized.csv",
        "raw_events": "alignments/raw_events.csv",
        "unassigned_reads": "alignments/unassigned_reads.csv",
    }
    ALIGNMENT_FORMATS = ["None", "txt", "fasta"]

    @classmethod
    def _outputs(cls, inputs: dict[str, Any]) -> list[str]:
        outputs = _as_list(inputs.get("outputs"))
        return outputs if outputs else list(cls.DEFAULT_OUTPUTS)

    @classmethod
    def _fastq_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("fastq_files"))

    @classmethod
    def _fastq_identifiers(cls, inputs: dict[str, Any], fastq_files: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("fastq_identifiers"))
        return [
            identifiers[index] if index < len(identifiers) and identifiers[index] else Path(fastq_file).name
            for index, fastq_file in enumerate(fastq_files)
        ]

    @classmethod
    def _r_bool(cls, value: Any, default: bool = True) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        outputs = set(cls._outputs(inputs))
        write_alignment_format = str(inputs.get("write_alignment_format", "txt"))
        return "\n".join(
            [
                "options(show.error.messages = FALSE, error = function() { cat(geterrmessage(), file = stderr()); q(\"no\", 1, FALSE) })",
                'Sys.setlocale("LC_MESSAGES", "en_US.UTF-8")',
                'suppressPackageStartupMessages({ library("amplican") })',
                "amplicanPipeline(",
                f"  {shlex.quote(str(inputs.get('config_file', '')))},",
                f"  {shlex.quote(f'{out}/fastq_folder')},",
                f"  {shlex.quote(f'{out}/output_folder')},",
                f"  knit_reports = {'TRUE' if 'knit_reports' in outputs else 'FALSE'},",
                f'  write_alignments_format = "{write_alignment_format}",',
                f"  average_quality = {inputs.get('average_quality', 0)},",
                f"  min_quality = {inputs.get('min_quality', 20)},",
                "  use_parallel = FALSE,",
                "  scoring_matrix = Biostrings::nucleotideSubstitutionMatrix(",
                f"    match = {inputs.get('match_scoring', 5)},",
                f"    mismatch = {inputs.get('mismatch_scoring', -4)},",
                f"    baseOnly = {cls._r_bool(inputs.get('base_only'), True)},",
                f'    type = "{inputs.get("scoring_type", "DNA")}"',
                "  ),",
                f"  gap_opening = {inputs.get('gap_opening', 25)},",
                f"  gap_extension = {inputs.get('gap_extension', 0)},",
                f"  fastqfiles = {inputs.get('fastq_use', '0')},",
                f"  primer_mismatch = {inputs.get('primer_mismatch', 0)},",
                f"  donor_mismatch = {inputs.get('donor_mismatch', 3)},",
                f"  PRIMER_DIMER = {inputs.get('primer_dimer', 30)},",
                f"  event_filter = {cls._r_bool(inputs.get('event_filter'), True)},",
                f"  cut_buffer = {inputs.get('cut_buffer', 5)},",
                f"  promiscuous_consensus = {cls._r_bool(inputs.get('promiscuous_consensus'), True)},",
                '  normalize = c("guideRNA", "Group")',
                ")",
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        fastq_files = cls._fastq_files(inputs)
        identifiers = cls._fastq_identifiers(inputs, fastq_files)
        commands = [
            _shell_join(["mkdir", "-p", f"{out}/fastq_folder", f"{out}/output_folder"]),
        ]
        for fastq_file, identifier in zip(fastq_files, identifiers, strict=False):
            commands.append(_shell_join(["ln", "-s", fastq_file, f"{out}/fastq_folder/{identifier}"]))
        script_path = f"{out}/amplican_script.R"
        commands.append(f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT")
        commands.append(_shell_join(["Rscript", script_path]))
        if "knit_reports" in cls._outputs(inputs):
            extra_files = f"{out}/output_html_extra_files"
            commands.append(_shell_join(["mkdir", "-p", extra_files]))
            for report in ["amplicon_report.html", "barcode_report.html", "group_report.html", "guide_report.html", "id_report.html"]:
                commands.append(_shell_join(["mv", f"{out}/output_folder/reports/{report}", extra_files]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / cls.OUTPUT_FILES[output] for output in cls._outputs(inputs) if output in cls.OUTPUT_FILES]
        write_alignment_format = str(inputs.get("write_alignment_format", "txt"))
        if write_alignment_format == "fasta":
            outputs.append(out / "alignments" / "alignments.fasta")
        elif write_alignment_format == "txt":
            outputs.append(out / "alignments" / "alignments.txt")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("config_file", "")).strip():
            return "config_file is required"
        fastq_files = cls._fastq_files(inputs)
        if not fastq_files:
            return "at least one FASTQ file is required"
        identifiers = cls._fastq_identifiers(inputs, fastq_files)
        if any(not re.fullmatch(r"[\w\-.]+", identifier) for identifier in identifiers):
            return "fastq_identifiers may contain only letters, numbers, underscores, hyphens, and dots"
        for name in ("average_quality", "min_quality"):
            value = int(inputs.get(name, {"average_quality": 0, "min_quality": 20}[name]))
            if value < 0 or value > 93:
                return f"{name} must be between 0 and 93"
        for name in ("gap_opening", "gap_extension", "primer_mismatch", "donor_mismatch"):
            value = int(inputs.get(name, {"gap_opening": 25, "gap_extension": 0, "primer_mismatch": 0, "donor_mismatch": 3}[name]))
            if value < 0 or value > 40:
                return f"{name} must be between 0 and 40"
        match_scoring = int(inputs.get("match_scoring", 5))
        if match_scoring < 0 or match_scoring > 20:
            return "match_scoring must be between 0 and 20"
        mismatch_scoring = int(inputs.get("mismatch_scoring", -4))
        if mismatch_scoring < -20 or mismatch_scoring > 0:
            return "mismatch_scoring must be between -20 and 0"
        if str(inputs.get("scoring_type", "DNA")) not in {"DNA", "RNA"}:
            return "scoring_type must be one of: DNA, RNA"
        if str(inputs.get("fastq_use", "0")) not in {"0", "0.5", "1", "2"}:
            return "fastq_use must be one of: 0, 0.5, 1, 2"
        primer_dimer = int(inputs.get("primer_dimer", 30))
        if primer_dimer < 0 or primer_dimer > 50:
            return "primer_dimer must be between 0 and 50"
        cut_buffer = int(inputs.get("cut_buffer", 5))
        if cut_buffer < 0 or cut_buffer > 30:
            return "cut_buffer must be between 0 and 30"
        if str(inputs.get("write_alignment_format", "txt")) not in cls.ALIGNMENT_FORMATS:
            return "write_alignment_format must be one of: None, txt, fasta"
        unsupported_outputs = [output for output in cls._outputs(inputs) if output not in cls.OUTPUT_CHOICES]
        if unsupported_outputs:
            return f"outputs contains unsupported values: {', '.join(unsupported_outputs)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "config_file": ("TXT", {"description": "ampliCan configuration file"}),
                "fastq_files": (
                    "FASTQ_LIST",
                    {"multiple": True, "description": "FASTQ or FASTQ.GZ read files referenced by the configuration"},
                ),
            },
            "optional": {
                "fastq_identifiers": (
                    "STRING_LIST",
                    {"default": [], "multiple": True, "advanced": True, "description": "Galaxy element names for staged FASTQ files"},
                ),
                "average_quality": ("INT", {"default": 0, "min": 0, "max": 93, "description": "Minimum average read quality"}),
                "min_quality": ("INT", {"default": 20, "min": 0, "max": 93, "description": "Minimum per-base quality"}),
                "gap_opening": ("INT", {"default": 25, "min": 0, "max": 40, "description": "Alignment gap opening score"}),
                "gap_extension": ("INT", {"default": 0, "min": 0, "max": 40, "description": "Alignment gap extension score"}),
                "primer_mismatch": ("INT", {"default": 0, "min": 0, "max": 40, "description": "Allowed primer mismatches"}),
                "donor_mismatch": (
                    "INT",
                    {"default": 3, "min": 0, "max": 40, "description": "Allowed mismatch events when aligning to donor template"},
                ),
                "match_scoring": ("INT", {"default": 5, "min": 0, "max": 20, "description": "Scoring matrix match value"}),
                "mismatch_scoring": (
                    "INT",
                    {"default": -4, "min": -20, "max": 0, "description": "Scoring matrix mismatch value"},
                ),
                "base_only": ("BOOLEAN", {"default": True, "description": "Use base-only nucleotide substitution matrix"}),
                "scoring_type": ("STRING", {"default": "DNA", "options": ["DNA", "RNA"], "description": "Scoring matrix type"}),
                "fastq_use": (
                    "STRING",
                    {"default": "0", "options": ["0", "0.5", "1", "2"], "description": "Forward/reverse FASTQ files to use"},
                ),
                "primer_dimer": ("INT", {"default": 30, "min": 0, "max": 50, "description": "Primer dimer detection buffer"}),
                "event_filter": ("BOOLEAN", {"default": True, "description": "Enable off-target read detection"}),
                "cut_buffer": ("INT", {"default": 5, "min": 0, "max": 30, "description": "Bases around expected cut sites"}),
                "promiscuous_consensus": (
                    "BOOLEAN",
                    {"default": True, "description": "Allow promiscuous consensus rules for indel confirmation"},
                ),
                "write_alignment_format": (
                    "STRING",
                    {"default": "txt", "options": cls.ALIGNMENT_FORMATS, "description": "Optional alignment output format"},
                ),
                "outputs": (
                    "STRING_LIST",
                    {
                        "default": cls.DEFAULT_OUTPUTS,
                        "multiple": True,
                        "options": cls.OUTPUT_CHOICES,
                        "description": "Additional ampliCan outputs selected in the Galaxy wrapper",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AllegroNode(CommandNode):
    """Run Allegro linkage, haplotype, and IBD sharing analysis."""

    NODE_ID = "allegro"
    DISPLAY_NAME = "Allegro"
    REQUIRED_CONDA_PACKAGES = ["allegro"]
    CATEGORY = "linkage"
    DESCRIPTION = "Multipoint genetic linkage, haplotype, IBD sharing, and simulation analysis."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Allegro",
        "allegro",
        "multipoint linkage analysis",
        "haplotype analysis",
        "IBD sharing",
        "parametric linkage",
        "allele sharing",
        "Genehunter",
    ]
    RETURN_TYPES = ("FILE", "FILE", "FILE", "TXT", "TXT")
    RETURN_NAMES = ("haplotypes", "linkage", "descent", "linear_expression", "combined_crossovers")
    REQUIRED_EXECUTABLES = ["allegro"]
    DOCUMENTATION_URL = "https://www.decode.com/software/allegro/"
    CITATION_DOIS = ALLEGRO_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in ALLEGRO_CITATION_DOIS]
    CITATION_TEXT = ALLEGRO_CITATION_TEXT
    VERSION = "3+galaxy0"
    SHELL = True

    ANALYSIS_MODES = ["haplotypes", "linkage"]
    LINKAGE_TYPES = ["defaults", "allele_sharing", "classical"]
    LINKAGE_MPTSPT = ["mpt", "spt"]
    LINEXP_OPTIONS = ["lin", "exp"]
    SCORING_OPTIONS = ["pairs", "all", "homoz", "mnallele", "robdom", "ps:mm/mf/ff"]
    WEIGHTING_OPTIONS = ["equal", "power:0.5"]
    STEPS_TYPES = ["STEPS", "STEPFILE", "MAXSTEPLENGTH"]
    PAIRWISE_TYPES = ["all", "genotype", "affected", "informative"]
    UNIT_OPTIONS = ["recombination", "centimorgan"]

    @classmethod
    def _out_dir(cls, inputs: dict[str, Any]) -> str:
        return _out(inputs)

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any]) -> dict[str, str]:
        out = cls._out_dir(inputs)
        return {
            "haplotypes": f"{out}/haplotypes.ihaplo",
            "linkage": f"{out}/linkage.fparam",
            "descent": f"{out}/descent.out",
            "linear_expression": f"{out}/linear_expression.txt",
            "combined_crossovers": f"{out}/combined_crossovers.txt",
        }

    @classmethod
    def _is_true(cls, inputs: dict[str, Any], name: str, default: bool = False) -> bool:
        value = inputs.get(name, default)
        if isinstance(value, str):
            return value.lower() in {"true", "1", "yes", "on"}
        return bool(value)

    @classmethod
    def _analysis_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("analysis_mode", "linkage") or "linkage")

    @classmethod
    def _linkage_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("linkage_type", "defaults") or "defaults")

    @classmethod
    def _config_lines(cls, inputs: dict[str, Any]) -> list[str]:
        paths = cls._output_paths(inputs)
        lines = [
            f"PREFILE {inputs.get('inp_ped', '')}",
            f"DATFILE {inputs.get('inp_dat', '')}",
        ]
        if str(inputs.get("inp_map", "")).strip():
            lines.append(f"MAPFILE {inputs.get('inp_map')}")
        lines.append("")

        if cls._analysis_mode(inputs) == "haplotypes":
            lines.append(f"HAPLOTYPE haplo.out {paths['haplotypes']} {paths['descent']} inher.out")
            if cls._is_true(inputs, "crossover"):
                lines.append(f"CROSSOVERRATE combined.out {paths['combined_crossovers']}")
        else:
            linkage_mptspt = str(inputs.get("linkage_mptspt", "mpt") or "mpt")
            linkage_type = cls._linkage_type(inputs)
            opt_xlinked = str(inputs.get("xlinked", "") or "")
            if linkage_type == "allele_sharing":
                lines.append(
                    "MODEL "
                    f"{linkage_mptspt} "
                    f"{inputs.get('linkage_linexp', 'lin')} "
                    f"{inputs.get('linkage_scoring', 'pairs')} "
                    f"{inputs.get('weighting', 'equal')} "
                    f"param.mpt {paths['linear_expression']}"
                )
            else:
                suffix = ""
                if linkage_type == "classical" and cls._is_true(inputs, "custom_freqs"):
                    suffix = f" freq:{inputs.get('par_freq', 0)} pen:{inputs.get('par_pen', 'p0/p1/p2')}"
                het = str(inputs.get("par_het", "") or "het")
                lines.append(f"MODEL {linkage_mptspt} par {opt_xlinked}{suffix} {het} param.mpt {paths['linkage']}")

            steps_type = str(inputs.get("steps_type", "STEPS") or "STEPS")
            if steps_type == "STEPFILE":
                lines.append(f"STEPFILE {inputs.get('stepfile', '')}")
            elif steps_type == "MAXSTEPLENGTH":
                lines.append(f"MAXSTEPLENGTH {inputs.get('max_step_length', 2)}")
            else:
                lines.append(f"STEPS {inputs.get('steps', 2)}")

        if cls._is_true(inputs, "sexspecific"):
            lines.append("SEXSPECIFIC on")
        lines.append(f"ENTROPY {'on' if cls._is_true(inputs, 'entropy') else 'off'}")
        lines.append(f"NPLEXACTP {'on' if cls._is_true(inputs, 'nplexactp') else 'off'}")

        if cls._is_true(inputs, "pairwise"):
            linkage_mptspt = str(inputs.get("linkage_mptspt", "mpt") or "mpt")
            lines.append(f"PAIRWISEIBD {linkage_mptspt} {inputs.get('pairwise_type', 'all')}")

        if cls._is_true(inputs, "simulate"):
            sim_tokens = []
            if str(inputs.get("sim_dloc", "")).strip():
                sim_tokens.append(f"dloc:{inputs.get('sim_dloc')}")
            sim_tokens.extend(
                [
                    f"npre:{inputs.get('sim_npre', 1)}",
                    f"rep:{inputs.get('sim_rep', 1)}",
                    f"err:{inputs.get('sim_err', 0)}",
                    f"yield:{inputs.get('sim_yield', 1)}",
                    f"het:{inputs.get('sim_het', 0)}",
                ]
            )
            lines.append(f"SIMULATE {' '.join(sim_tokens)}")

        lines.extend(["MAXMEMORY 102400", f"UNIT {inputs.get('unit', 'recombination')}", "UNINFORMATIVE"])
        return lines

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = cls._out_dir(inputs)
        conf = f"{out}/allegro.conf"
        config = "\n".join(cls._config_lines(inputs)) + "\n"
        return f"mkdir -p {shlex.quote(out)} && cat > {shlex.quote(conf)} <<'EOF'\n{config}EOF\nallegro {shlex.quote(conf)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        mode = cls._analysis_mode(inputs)
        linkage_type = cls._linkage_type(inputs)
        if mode == "haplotypes":
            outputs = [out / "haplotypes.ihaplo", out / "descent.out"]
            if cls._is_true(inputs, "crossover"):
                outputs.append(out / "combined_crossovers.txt")
            return outputs
        if linkage_type == "allele_sharing":
            return [out / "linear_expression.txt"]
        return [out / "linkage.fparam"]

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, default: str, options: list[str]) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_min(cls, inputs: dict[str, Any], name: str, default: int | float, minimum: int | float) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be numeric"
        if value < minimum:
            return f"{name} must be >= {minimum:g}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("inp_ped", "")).strip():
            return "Pedigree input is required"
        if not str(inputs.get("inp_dat", "")).strip():
            return "Recombination data input is required"
        for name, default, options in [
            ("analysis_mode", "linkage", cls.ANALYSIS_MODES),
            ("linkage_mptspt", "mpt", cls.LINKAGE_MPTSPT),
            ("linkage_type", "defaults", cls.LINKAGE_TYPES),
            ("linkage_linexp", "lin", cls.LINEXP_OPTIONS),
            ("linkage_scoring", "pairs", cls.SCORING_OPTIONS),
            ("weighting", "equal", cls.WEIGHTING_OPTIONS),
            ("steps_type", "STEPS", cls.STEPS_TYPES),
            ("pairwise_type", "all", cls.PAIRWISE_TYPES),
            ("unit", "recombination", cls.UNIT_OPTIONS),
        ]:
            result = cls._validate_choice(inputs, name, default, options)
            if result is not True:
                return result
        if str(inputs.get("steps_type", "STEPS") or "STEPS") == "STEPFILE" and not str(inputs.get("stepfile", "")).strip():
            return "stepfile is required when steps_type is STEPFILE"
        for name, default, minimum in [
            ("steps", 2, 1),
            ("max_step_length", 2, 1),
            ("sim_npre", 1, 1),
            ("sim_rep", 1, 1),
            ("sim_err", 0, 0),
            ("sim_yield", 1, 0),
            ("sim_het", 0, 0),
        ]:
            result = cls._validate_min(inputs, name, default, minimum)
            if result is not True:
                return result
        if cls._is_true(inputs, "custom_freqs"):
            try:
                par_freq = float(inputs.get("par_freq", 0))
            except (TypeError, ValueError):
                return "par_freq must be numeric"
            if not 0 <= par_freq <= 1:
                return "par_freq must be between 0 and 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inp_ped": ("FILE", {"description": "Linkage pedigree input file"}),
                "inp_dat": ("FILE", {"description": "Linkage data/recombination frequency input file"}),
            },
            "optional": {
                "inp_map": ("FILE", {"default": "", "description": "Optional marker map positions file"}),
                "analysis_mode": (
                    "STRING",
                    {"default": "linkage", "options": cls.ANALYSIS_MODES, "description": "Run haplotype reconstruction or linkage analysis"},
                ),
                "crossover": ("BOOLEAN", {"default": False, "description": "Report combined crossover rates for haplotypes"}),
                "linkage_mptspt": (
                    "STRING",
                    {"default": "mpt", "options": cls.LINKAGE_MPTSPT, "description": "Use multipoint or single-point IBD probabilities"},
                ),
                "linkage_type": (
                    "STRING",
                    {"default": "defaults", "options": cls.LINKAGE_TYPES, "description": "Galaxy linkage analysis type"},
                ),
                "linkage_linexp": (
                    "STRING",
                    {"default": "lin", "options": cls.LINEXP_OPTIONS, "description": "Linear or exponential allele-sharing model"},
                ),
                "linkage_scoring": (
                    "STRING",
                    {"default": "pairs", "options": cls.SCORING_OPTIONS, "description": "Allele-sharing scoring function"},
                ),
                "weighting": (
                    "STRING",
                    {"default": "equal", "options": cls.WEIGHTING_OPTIONS, "description": "Allele-sharing weighting function"},
                ),
                "custom_freqs": ("BOOLEAN", {"default": False, "description": "Use custom classical model frequencies"}),
                "par_freq": ("FLOAT", {"default": 0, "min": 0, "max": 1, "description": "Classical model allele frequency"}),
                "par_pen": ("STRING", {"default": "p0/p1/p2", "description": "Classical model penetrance"}),
                "par_het": ("FLOAT", {"default": "", "description": "Optional classical model heterogeneity frequency"}),
                "steps_type": (
                    "STRING",
                    {"default": "STEPS", "options": cls.STEPS_TYPES, "description": "Marker interval calculation mode"},
                ),
                "steps": ("INT", {"default": 2, "min": 1, "description": "Calculations between adjacent markers"}),
                "stepfile": ("FILE", {"default": "", "description": "Positions file for STEPFILE mode"}),
                "max_step_length": ("FLOAT", {"default": 2, "min": 1, "description": "Periodic cM interval for MAXSTEPLENGTH mode"}),
                "xlinked": ("STRING", {"default": "", "options": ["", "X"], "description": "Autosomal or X-linked disease model"}),
                "entropy": ("BOOLEAN", {"default": False, "description": "Calculate entropy"}),
                "nplexactp": ("BOOLEAN", {"default": False, "description": "Use exact non-parametric linkage p-values"}),
                "pairwise": ("BOOLEAN", {"default": False, "description": "Perform pairwise IBD analysis"}),
                "pairwise_type": (
                    "STRING",
                    {"default": "all", "options": cls.PAIRWISE_TYPES, "description": "Pairwise IBD weighting mode"},
                ),
                "simulate": ("BOOLEAN", {"default": False, "description": "Simulate multipoint data"}),
                "sim_dloc": ("FLOAT", {"default": "", "min": 0, "description": "Optional disease locus in cM"}),
                "sim_npre": ("INT", {"default": 1, "min": 1, "description": "Number of prefiles to generate"}),
                "sim_rep": ("INT", {"default": 1, "min": 1, "description": "Family pattern repeat count"}),
                "sim_err": ("FLOAT", {"default": 0, "min": 0, "description": "Simulation error rate"}),
                "sim_yield": ("FLOAT", {"default": 1, "min": 0, "description": "Simulation genotype yield"}),
                "sim_het": ("FLOAT", {"default": 0, "min": 0, "description": "Simulation heterogeneity probability"}),
                "sexspecific": ("BOOLEAN", {"default": False, "description": "Use sex-specific penetrances from the data file"}),
                "unit": (
                    "STRING",
                    {"default": "recombination", "options": cls.UNIT_OPTIONS, "description": "Distance unit used in the data file"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AlphaGenomeIntervalPredictorNode(CommandNode):
    """Predict regulatory tracks for genomic intervals with AlphaGenome."""

    NODE_ID = "alphagenome_interval_predictor"
    DISPLAY_NAME = "AlphaGenome Interval Predictor"
    REQUIRED_CONDA_PACKAGES = ["alphagenome", "cyvcf2", "pandas"]
    CATEGORY = "ai"
    DESCRIPTION = "Predict regulatory tracks for genomic intervals with AlphaGenome."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AlphaGenome",
        "alphagenome",
        "AlphaGenome interval prediction",
        "regulatory track prediction",
        "predict_interval",
        "chromatin prediction",
        "expression prediction",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("predictions",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://www.alphagenomedocs.com/"
    CITATION_DOIS = [ALPHAGENOME_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ALPHAGENOME_CITATION_DOI}"]
    CITATION_TEXT = ALPHAGENOME_CITATION_TEXT
    VERSION = "0.6.1+galaxy1"
    SHELL = True

    ORGANISMS = ["human", "mouse"]
    OUTPUT_TYPES = ["RNA_SEQ", "ATAC", "CAGE", "DNASE", "CHIP_HISTONE", "CHIP_TF", "SPLICE_SITES", "PROCAP"]
    SEQUENCE_LENGTHS = ["16KB", "128KB", "512KB", "1MB"]
    OUTPUT_MODES = ["summary", "binned"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/predictions.tsv"

    @classmethod
    def _output_types(cls, inputs: dict[str, Any], *, use_default: bool = True) -> list[str]:
        if "output_types" not in inputs:
            return ["RNA_SEQ"] if use_default else []
        return _as_list(inputs.get("output_types"))

    @classmethod
    def _int_range(
        cls,
        inputs: dict[str, Any],
        name: str,
        default: int,
        minimum: int,
        maximum: int,
    ) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < minimum or value > maximum:
            return f"{name} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        output_mode = str(inputs.get("output_mode", "summary") or "summary")
        cmd = [
            "python",
            str(inputs.get("script_path", "alphagenome_interval_predictor.py")),
            "--input",
            str(inputs.get("input_bed", "")),
            "--output",
            cls._output_path(inputs),
            "--organism",
            str(inputs.get("organism", "human") or "human"),
            "--output-types",
            *cls._output_types(inputs),
            "--sequence-length",
            str(inputs.get("sequence_length", "1MB") or "1MB"),
            "--max-intervals",
            str(inputs.get("max_intervals", 50)),
            "--output-mode",
            output_mode,
        ]
        if output_mode == "binned":
            cmd.extend(["--bin-size", str(inputs.get("bin_size", 128))])
        _add_if_value(cmd, "--ontology-terms", inputs.get("ontology_terms"))
        _add_if_value(cmd, "--test-fixture", inputs.get("test_fixture"))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "predictions.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_bed", "")).strip():
            return "input_bed is required"
        output_types = cls._output_types(inputs, use_default=True)
        if not output_types:
            return "at least one output type is required"
        unsupported = [value for value in output_types if value not in cls.OUTPUT_TYPES]
        if unsupported:
            return f"output_types contains unsupported values: {', '.join(unsupported)}"
        organism = str(inputs.get("organism", "human") or "human")
        if organism not in cls.ORGANISMS:
            return f"organism must be one of: {', '.join(cls.ORGANISMS)}"
        sequence_length = str(inputs.get("sequence_length", "1MB") or "1MB")
        if sequence_length not in cls.SEQUENCE_LENGTHS:
            return f"sequence_length must be one of: {', '.join(cls.SEQUENCE_LENGTHS)}"
        output_mode = str(inputs.get("output_mode", "summary") or "summary")
        if output_mode not in cls.OUTPUT_MODES:
            return f"output_mode must be one of: {', '.join(cls.OUTPUT_MODES)}"
        max_intervals = cls._int_range(inputs, "max_intervals", 50, 1, 1000)
        if max_intervals is not True:
            return max_intervals
        if output_mode == "binned":
            bin_size = cls._int_range(inputs, "bin_size", 128, 1, 4096)
            if bin_size is not True:
                return bin_size
        ontology_terms = str(inputs.get("ontology_terms", "") or "")
        if ontology_terms and not re.fullmatch(r"[A-Za-z0-9:, ]*", ontology_terms):
            return "ontology_terms may contain only letters, numbers, colons, commas, and spaces"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bed": ("BED", {"description": "BED intervals to characterize with AlphaGenome predict_interval"}),
            },
            "optional": {
                "organism": (
                    "STRING",
                    {"default": "human", "options": cls.ORGANISMS, "description": "AlphaGenome organism assembly context"},
                ),
                "output_types": (
                    "STRING_LIST",
                    {
                        "default": ["RNA_SEQ"],
                        "multiple": True,
                        "options": cls.OUTPUT_TYPES,
                        "description": "AlphaGenome output tracks to predict",
                    },
                ),
                "ontology_terms": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Optional comma-separated UBERON or CL ontology terms for tissue context",
                    },
                ),
                "sequence_length": (
                    "STRING",
                    {
                        "default": "1MB",
                        "options": cls.SEQUENCE_LENGTHS,
                        "description": "Prediction window size around each interval",
                    },
                ),
                "max_intervals": (
                    "INT",
                    {"default": 50, "min": 1, "max": 1000, "description": "Maximum BED intervals to submit"},
                ),
                "output_mode": (
                    "STRING",
                    {
                        "default": "summary",
                        "options": cls.OUTPUT_MODES,
                        "description": "Write compact interval summaries or binned signal profiles",
                    },
                ),
                "bin_size": (
                    "INT",
                    {
                        "default": 128,
                        "min": 1,
                        "max": 4096,
                        "description": "Bin size in base pairs when output_mode is binned",
                    },
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "alphagenome_interval_predictor.py",
                        "advanced": True,
                        "description": "Path to the Galaxy AlphaGenome interval predictor wrapper script",
                    },
                ),
                "test_fixture": (
                    "FILE",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Optional test fixture JSON that bypasses the AlphaGenome API",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AlphaGenomeISMScannerNode(CommandNode):
    """Perform in-silico saturation mutagenesis with AlphaGenome."""

    NODE_ID = "alphagenome_ism_scanner"
    DISPLAY_NAME = "AlphaGenome ISM Scanner"
    REQUIRED_CONDA_PACKAGES = ["alphagenome", "cyvcf2", "pandas"]
    CATEGORY = "ai"
    DESCRIPTION = "Perform in-silico saturation mutagenesis with AlphaGenome."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AlphaGenome",
        "alphagenome",
        "AlphaGenome saturation mutagenesis",
        "in-silico saturation mutagenesis",
        "ISM scanner",
        "score_ism_variants",
        "variant scorer",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("ism_scores",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://www.alphagenomedocs.com/"
    CITATION_DOIS = [ALPHAGENOME_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ALPHAGENOME_CITATION_DOI}"]
    CITATION_TEXT = ALPHAGENOME_CITATION_TEXT
    VERSION = "0.6.1+galaxy1"
    SHELL = True

    ORGANISMS = ["human", "mouse"]
    SCORERS = [
        "RNA_SEQ",
        "RNA_SEQ_ACTIVE",
        "ATAC",
        "ATAC_ACTIVE",
        "DNASE",
        "DNASE_ACTIVE",
        "CAGE",
        "CAGE_ACTIVE",
        "PROCAP",
        "PROCAP_ACTIVE",
        "CHIP_TF",
        "CHIP_TF_ACTIVE",
        "CHIP_HISTONE",
        "CHIP_HISTONE_ACTIVE",
        "SPLICE_SITES",
        "SPLICE_SITE_USAGE",
        "SPLICE_JUNCTIONS",
        "CONTACT_MAPS",
        "POLYADENYLATION",
    ]
    SEQUENCE_LENGTHS = ["16KB", "128KB", "512KB", "1MB"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/ism_scores.tsv"

    @classmethod
    def _scorers(cls, inputs: dict[str, Any], *, use_default: bool = True) -> list[str]:
        if "scorers" not in inputs:
            return ["RNA_SEQ", "ATAC"] if use_default else []
        return _as_list(inputs.get("scorers"))

    @classmethod
    def _int_range(
        cls,
        inputs: dict[str, Any],
        name: str,
        default: int,
        minimum: int,
        maximum: int,
    ) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < minimum or value > maximum:
            return f"{name} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        max_workers = inputs.get("max_workers", 1) or 1
        slots = f"${{GALAXY_SLOTS:-{max_workers}}}"
        cmd = [
            "python",
            str(inputs.get("script_path", "alphagenome_ism_scanner.py")),
            "--input",
            str(inputs.get("input_bed", "")),
            "--output",
            cls._output_path(inputs),
            "--organism",
            str(inputs.get("organism", "human") or "human"),
            "--scorers",
            *cls._scorers(inputs),
            "--sequence-length",
            str(inputs.get("sequence_length", "1MB") or "1MB"),
            "--max-regions",
            str(inputs.get("max_regions", 10)),
            "--max-region-width",
            str(inputs.get("max_region_width", 200)),
            "--max-workers",
            slots,
        ]
        _add_if_value(cmd, "--test-fixture", inputs.get("test_fixture"))
        _add_if_value(cmd, "--mock-ism-results", inputs.get("mock_ism_results"))
        return _shell_join(cmd).replace(shlex.quote(slots), slots)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "ism_scores.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_bed", "")).strip():
            return "input_bed is required"
        scorers = cls._scorers(inputs, use_default=True)
        if not scorers:
            return "at least one scorer is required"
        unsupported = [value for value in scorers if value not in cls.SCORERS]
        if unsupported:
            return f"scorers contains unsupported values: {', '.join(unsupported)}"
        organism = str(inputs.get("organism", "human") or "human")
        if organism not in cls.ORGANISMS:
            return f"organism must be one of: {', '.join(cls.ORGANISMS)}"
        sequence_length = str(inputs.get("sequence_length", "1MB") or "1MB")
        if sequence_length not in cls.SEQUENCE_LENGTHS:
            return f"sequence_length must be one of: {', '.join(cls.SEQUENCE_LENGTHS)}"
        for name, default, minimum, maximum in [
            ("max_regions", 10, 1, 100),
            ("max_region_width", 200, 1, 1000),
            ("max_workers", 1, 1, 128),
        ]:
            result = cls._int_range(inputs, name, default, minimum, maximum)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bed": ("BED", {"description": "BED regions to scan with AlphaGenome saturation mutagenesis"}),
            },
            "optional": {
                "organism": (
                    "STRING",
                    {"default": "human", "options": cls.ORGANISMS, "description": "AlphaGenome organism assembly context"},
                ),
                "scorers": (
                    "STRING_LIST",
                    {
                        "default": ["RNA_SEQ", "ATAC"],
                        "multiple": True,
                        "options": cls.SCORERS,
                        "description": "AlphaGenome recommended variant scorers to run",
                    },
                ),
                "sequence_length": (
                    "STRING",
                    {
                        "default": "1MB",
                        "options": cls.SEQUENCE_LENGTHS,
                        "description": "Prediction window size around each scanned region",
                    },
                ),
                "max_regions": (
                    "INT",
                    {"default": 10, "min": 1, "max": 100, "description": "Maximum BED regions to scan"},
                ),
                "max_region_width": (
                    "INT",
                    {
                        "default": 200,
                        "min": 1,
                        "max": 1000,
                        "description": "Maximum width per scanned region before center trimming",
                    },
                ),
                "max_workers": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 128,
                        "advanced": True,
                        "description": "Fallback worker count used when GALAXY_SLOTS is unset",
                    },
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "alphagenome_ism_scanner.py",
                        "advanced": True,
                        "description": "Path to the Galaxy AlphaGenome ISM scanner wrapper script",
                    },
                ),
                "test_fixture": (
                    "FILE",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Optional fixture JSON that bypasses the AlphaGenome API",
                    },
                ),
                "mock_ism_results": (
                    "FILE",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Optional mock AnnData JSON for exercising ISM post-processing",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AlphaGenomeSequencePredictorNode(CommandNode):
    """Predict regulatory tracks from raw DNA sequences with AlphaGenome."""

    NODE_ID = "alphagenome_sequence_predictor"
    DISPLAY_NAME = "AlphaGenome Sequence Predictor"
    REQUIRED_CONDA_PACKAGES = ["alphagenome", "cyvcf2", "pandas"]
    CATEGORY = "ai"
    DESCRIPTION = "Predict regulatory tracks from DNA sequence with AlphaGenome."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AlphaGenome",
        "alphagenome",
        "AlphaGenome sequence prediction",
        "predict_sequence",
        "synthetic biology",
        "regulatory sequence prediction",
        "designed sequences",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("sequence_predictions",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://www.alphagenomedocs.com/"
    CITATION_DOIS = [ALPHAGENOME_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ALPHAGENOME_CITATION_DOI}"]
    CITATION_TEXT = ALPHAGENOME_CITATION_TEXT
    VERSION = "0.6.1+galaxy1"
    SHELL = True

    ORGANISMS = ["human", "mouse"]
    OUTPUT_TYPES = ["RNA_SEQ", "ATAC", "CAGE", "DNASE", "CHIP_HISTONE", "CHIP_TF", "SPLICE_SITES", "PROCAP"]
    SEQUENCE_LENGTHS = ["16KB", "128KB", "512KB", "1MB"]
    OUTPUT_MODES = ["summary", "binned"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/sequence_predictions.tsv"

    @classmethod
    def _output_types(cls, inputs: dict[str, Any], *, use_default: bool = True) -> list[str]:
        if "output_types" not in inputs:
            return ["RNA_SEQ"] if use_default else []
        return _as_list(inputs.get("output_types"))

    @classmethod
    def _int_range(
        cls,
        inputs: dict[str, Any],
        name: str,
        default: int,
        minimum: int,
        maximum: int,
    ) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < minimum or value > maximum:
            return f"{name} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        output_mode = str(inputs.get("output_mode", "summary") or "summary")
        cmd = [
            "python",
            str(inputs.get("script_path", "alphagenome_sequence_predictor.py")),
            "--input",
            str(inputs.get("input_fasta", "")),
            "--output",
            cls._output_path(inputs),
            "--organism",
            str(inputs.get("organism", "human") or "human"),
            "--output-types",
            *cls._output_types(inputs),
            "--sequence-length",
            str(inputs.get("sequence_length", "16KB") or "16KB"),
            "--max-sequences",
            str(inputs.get("max_sequences", 20)),
            "--output-mode",
            output_mode,
        ]
        if output_mode == "binned":
            cmd.extend(["--bin-size", str(inputs.get("bin_size", 128))])
        _add_if_value(cmd, "--ontology-terms", inputs.get("ontology_terms"))
        _add_if_value(cmd, "--test-fixture", inputs.get("test_fixture"))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "sequence_predictions.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_fasta", "")).strip():
            return "input_fasta is required"
        output_types = cls._output_types(inputs, use_default=True)
        if not output_types:
            return "at least one output type is required"
        unsupported = [value for value in output_types if value not in cls.OUTPUT_TYPES]
        if unsupported:
            return f"output_types contains unsupported values: {', '.join(unsupported)}"
        organism = str(inputs.get("organism", "human") or "human")
        if organism not in cls.ORGANISMS:
            return f"organism must be one of: {', '.join(cls.ORGANISMS)}"
        sequence_length = str(inputs.get("sequence_length", "16KB") or "16KB")
        if sequence_length not in cls.SEQUENCE_LENGTHS:
            return f"sequence_length must be one of: {', '.join(cls.SEQUENCE_LENGTHS)}"
        output_mode = str(inputs.get("output_mode", "summary") or "summary")
        if output_mode not in cls.OUTPUT_MODES:
            return f"output_mode must be one of: {', '.join(cls.OUTPUT_MODES)}"
        max_sequences = cls._int_range(inputs, "max_sequences", 20, 1, 1000)
        if max_sequences is not True:
            return max_sequences
        if output_mode == "binned":
            bin_size = cls._int_range(inputs, "bin_size", 128, 1, 4096)
            if bin_size is not True:
                return bin_size
        ontology_terms = str(inputs.get("ontology_terms", "") or "")
        if ontology_terms and not re.fullmatch(r"[A-Za-z0-9:, ]*", ontology_terms):
            return "ontology_terms may contain only letters, numbers, colons, commas, and spaces"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "FASTA DNA sequences to characterize with AlphaGenome predict_sequence"}),
            },
            "optional": {
                "organism": (
                    "STRING",
                    {"default": "human", "options": cls.ORGANISMS, "description": "AlphaGenome organism assembly context"},
                ),
                "output_types": (
                    "STRING_LIST",
                    {
                        "default": ["RNA_SEQ"],
                        "multiple": True,
                        "options": cls.OUTPUT_TYPES,
                        "description": "AlphaGenome output tracks to predict",
                    },
                ),
                "ontology_terms": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Optional comma-separated UBERON or CL ontology terms for tissue context",
                    },
                ),
                "sequence_length": (
                    "STRING",
                    {
                        "default": "16KB",
                        "options": cls.SEQUENCE_LENGTHS,
                        "description": "Prediction window size; shorter sequences are N-padded and longer sequences are center-trimmed",
                    },
                ),
                "max_sequences": (
                    "INT",
                    {"default": 20, "min": 1, "max": 1000, "description": "Maximum FASTA records to submit"},
                ),
                "output_mode": (
                    "STRING",
                    {
                        "default": "summary",
                        "options": cls.OUTPUT_MODES,
                        "description": "Write compact sequence summaries or binned signal profiles",
                    },
                ),
                "bin_size": (
                    "INT",
                    {
                        "default": 128,
                        "min": 1,
                        "max": 4096,
                        "description": "Bin size in base pairs when output_mode is binned",
                    },
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "alphagenome_sequence_predictor.py",
                        "advanced": True,
                        "description": "Path to the Galaxy AlphaGenome sequence predictor wrapper script",
                    },
                ),
                "test_fixture": (
                    "FILE",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Optional test fixture JSON that bypasses the AlphaGenome API",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AlphaGenomeVariantEffectNode(CommandNode):
    """Annotate VCF variants with AlphaGenome variant-effect scores."""

    NODE_ID = "alphagenome_variant_effect"
    DISPLAY_NAME = "AlphaGenome Variant Effect"
    REQUIRED_CONDA_PACKAGES = ["alphagenome", "cyvcf2", "pandas"]
    CATEGORY = "ai"
    DESCRIPTION = "Annotate VCF variants with AlphaGenome variant-effect scores."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AlphaGenome",
        "alphagenome",
        "AlphaGenome variant effect",
        "predict_variant",
        "regulatory variant effect",
        "VCF annotation",
        "log fold change",
    ]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("annotated_vcf",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://www.alphagenomedocs.com/"
    CITATION_DOIS = [ALPHAGENOME_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ALPHAGENOME_CITATION_DOI}"]
    CITATION_TEXT = ALPHAGENOME_CITATION_TEXT
    VERSION = "0.6.1+galaxy1"
    SHELL = True

    ORGANISMS = ["human", "mouse"]
    OUTPUT_TYPES = [
        "RNA_SEQ",
        "ATAC",
        "CAGE",
        "DNASE",
        "CHIP_HISTONE",
        "CHIP_TF",
        "SPLICE_SITES",
        "SPLICE_SITE_USAGE",
        "SPLICE_JUNCTIONS",
        "CONTACT_MAPS",
        "PROCAP",
    ]
    SEQUENCE_LENGTHS = ["16KB", "128KB", "512KB", "1MB"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/annotated.vcf"

    @classmethod
    def _output_types(cls, inputs: dict[str, Any], *, use_default: bool = True) -> list[str]:
        if "output_types" not in inputs:
            return ["RNA_SEQ"] if use_default else []
        return _as_list(inputs.get("output_types"))

    @classmethod
    def _int_range(
        cls,
        inputs: dict[str, Any],
        name: str,
        default: int,
        minimum: int,
        maximum: int,
    ) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < minimum or value > maximum:
            return f"{name} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "alphagenome_variant_effect.py")),
            "--input",
            str(inputs.get("input_vcf", "")),
            "--output",
            cls._output_path(inputs),
            "--organism",
            str(inputs.get("organism", "human") or "human"),
            "--output-types",
            *cls._output_types(inputs),
            "--sequence-length",
            str(inputs.get("sequence_length", "1MB") or "1MB"),
            "--max-variants",
            str(inputs.get("max_variants", 100)),
        ]
        _add_if_value(cmd, "--ontology-terms", inputs.get("ontology_terms"))
        _add_if_value(cmd, "--test-fixture", inputs.get("test_fixture"))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "annotated.vcf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_vcf", "")).strip():
            return "input_vcf is required"
        output_types = cls._output_types(inputs, use_default=True)
        if not output_types:
            return "at least one output type is required"
        unsupported = [value for value in output_types if value not in cls.OUTPUT_TYPES]
        if unsupported:
            return f"output_types contains unsupported values: {', '.join(unsupported)}"
        organism = str(inputs.get("organism", "human") or "human")
        if organism not in cls.ORGANISMS:
            return f"organism must be one of: {', '.join(cls.ORGANISMS)}"
        sequence_length = str(inputs.get("sequence_length", "1MB") or "1MB")
        if sequence_length not in cls.SEQUENCE_LENGTHS:
            return f"sequence_length must be one of: {', '.join(cls.SEQUENCE_LENGTHS)}"
        max_variants = cls._int_range(inputs, "max_variants", 100, 1, 10000)
        if max_variants is not True:
            return max_variants
        ontology_terms = str(inputs.get("ontology_terms", "") or "")
        if ontology_terms and not re.fullmatch(r"[A-Za-z0-9:, ]*", ontology_terms):
            return "ontology_terms may contain only letters, numbers, colons, commas, and spaces"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_vcf": ("VCF", {"description": "VCF containing variants to score with AlphaGenome predict_variant"}),
            },
            "optional": {
                "organism": (
                    "STRING",
                    {"default": "human", "options": cls.ORGANISMS, "description": "AlphaGenome organism assembly context"},
                ),
                "output_types": (
                    "STRING_LIST",
                    {
                        "default": ["RNA_SEQ"],
                        "multiple": True,
                        "options": cls.OUTPUT_TYPES,
                        "description": "AlphaGenome output tracks used to compute variant effect scores",
                    },
                ),
                "ontology_terms": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Optional comma-separated UBERON or CL ontology terms for tissue context",
                    },
                ),
                "sequence_length": (
                    "STRING",
                    {
                        "default": "1MB",
                        "options": cls.SEQUENCE_LENGTHS,
                        "description": "Prediction window size centered on each variant",
                    },
                ),
                "max_variants": (
                    "INT",
                    {"default": 100, "min": 1, "max": 10000, "description": "Maximum VCF records to score"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "alphagenome_variant_effect.py",
                        "advanced": True,
                        "description": "Path to the Galaxy AlphaGenome variant effect wrapper script",
                    },
                ),
                "test_fixture": (
                    "FILE",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Optional precomputed variant score fixture JSON that bypasses the AlphaGenome API",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AlphaGenomeVariantScorerNode(CommandNode):
    """Score variants with AlphaGenome gene-level quantile-normalized scores."""

    NODE_ID = "alphagenome_variant_scorer"
    DISPLAY_NAME = "AlphaGenome Variant Scorer"
    REQUIRED_CONDA_PACKAGES = ["alphagenome", "cyvcf2", "pandas"]
    CATEGORY = "ai"
    DESCRIPTION = "Score variants with AlphaGenome gene-level quantile-normalized scores."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AlphaGenome",
        "alphagenome",
        "AlphaGenome variant scoring",
        "score_variant",
        "gene-level variant scoring",
        "quantile normalized variant score",
        "tidy_scores",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("variant_scores",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://www.alphagenomedocs.com/"
    CITATION_DOIS = [ALPHAGENOME_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ALPHAGENOME_CITATION_DOI}"]
    CITATION_TEXT = ALPHAGENOME_CITATION_TEXT
    VERSION = "0.6.1+galaxy1"
    SHELL = True

    ORGANISMS = ["human", "mouse"]
    SCORERS = [
        "RNA_SEQ",
        "RNA_SEQ_ACTIVE",
        "ATAC",
        "ATAC_ACTIVE",
        "DNASE",
        "DNASE_ACTIVE",
        "CAGE",
        "CAGE_ACTIVE",
        "PROCAP",
        "PROCAP_ACTIVE",
        "CHIP_TF",
        "CHIP_TF_ACTIVE",
        "CHIP_HISTONE",
        "CHIP_HISTONE_ACTIVE",
        "SPLICE_SITES",
        "SPLICE_SITE_USAGE",
        "SPLICE_JUNCTIONS",
        "CONTACT_MAPS",
        "POLYADENYLATION",
    ]
    SEQUENCE_LENGTHS = ["16KB", "128KB", "512KB", "1MB"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/variant_scores.tsv"

    @classmethod
    def _scorers(cls, inputs: dict[str, Any], *, use_default: bool = True) -> list[str]:
        if "scorers" not in inputs:
            return ["RNA_SEQ", "ATAC", "SPLICE_SITES"] if use_default else []
        return _as_list(inputs.get("scorers"))

    @classmethod
    def _int_range(
        cls,
        inputs: dict[str, Any],
        name: str,
        default: int,
        minimum: int,
        maximum: int,
    ) -> bool | str:
        try:
            value = int(inputs.get(name, default))
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if value < minimum or value > maximum:
            return f"{name} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "python",
            str(inputs.get("script_path", "alphagenome_variant_scorer.py")),
            "--input",
            str(inputs.get("input_vcf", "")),
            "--output",
            cls._output_path(inputs),
            "--organism",
            str(inputs.get("organism", "human") or "human"),
            "--scorers",
            *cls._scorers(inputs),
            "--sequence-length",
            str(inputs.get("sequence_length", "1MB") or "1MB"),
            "--max-variants",
            str(inputs.get("max_variants", 100)),
        ]
        _add_if_value(cmd, "--test-fixture", inputs.get("test_fixture"))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "variant_scores.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_vcf", "")).strip():
            return "input_vcf is required"
        scorers = cls._scorers(inputs, use_default=True)
        if not scorers:
            return "at least one scorer is required"
        unsupported = [value for value in scorers if value not in cls.SCORERS]
        if unsupported:
            return f"scorers contains unsupported values: {', '.join(unsupported)}"
        organism = str(inputs.get("organism", "human") or "human")
        if organism not in cls.ORGANISMS:
            return f"organism must be one of: {', '.join(cls.ORGANISMS)}"
        sequence_length = str(inputs.get("sequence_length", "1MB") or "1MB")
        if sequence_length not in cls.SEQUENCE_LENGTHS:
            return f"sequence_length must be one of: {', '.join(cls.SEQUENCE_LENGTHS)}"
        max_variants = cls._int_range(inputs, "max_variants", 100, 1, 10000)
        if max_variants is not True:
            return max_variants
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_vcf": ("VCF", {"description": "VCF containing variants to score with AlphaGenome score_variant"}),
            },
            "optional": {
                "organism": (
                    "STRING",
                    {"default": "human", "options": cls.ORGANISMS, "description": "AlphaGenome organism assembly context"},
                ),
                "scorers": (
                    "STRING_LIST",
                    {
                        "default": ["RNA_SEQ", "ATAC", "SPLICE_SITES"],
                        "multiple": True,
                        "options": cls.SCORERS,
                        "description": "AlphaGenome recommended variant scorers for gene-level aggregation",
                    },
                ),
                "sequence_length": (
                    "STRING",
                    {
                        "default": "1MB",
                        "options": cls.SEQUENCE_LENGTHS,
                        "description": "Prediction window size centered on each variant before gene-level scoring",
                    },
                ),
                "max_variants": (
                    "INT",
                    {"default": 100, "min": 1, "max": 10000, "description": "Maximum VCF records to score"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "alphagenome_variant_scorer.py",
                        "advanced": True,
                        "description": "Path to the Galaxy AlphaGenome variant scorer wrapper script",
                    },
                ),
                "test_fixture": (
                    "FILE",
                    {
                        "default": "",
                        "advanced": True,
                        "description": "Optional precomputed tidy score fixture JSON that bypasses the AlphaGenome API",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
