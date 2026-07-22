"""featureCounts 2.1.1 read summarization node."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin._wrapped_tool_utils import (
    BIONODULO_BUILTIN_ALIAS,
    DOI_URL,
    FEATURECOUNTS_CITATION_DOI,
    FEATURECOUNTS_CITATION_TEXT,
    _out,
    _shell_join,
)
from bionodulo.nodes.command_node import CommandNode


def _validate_file(value: str, name: str) -> bool | str:
    path = Path(value)
    if not path.is_file():
        return f"{name} is not a materialized file: {path}"
    try:
        if path.stat().st_size == 0:
            return f"{name} file is empty: {path}"
    except OSError as exc:
        return f"cannot inspect {name} file {path}: {exc}"
    return True


class FeatureCountsNode(CommandNode):
    """Measure gene expression by assigning reads to genomic features with featureCounts."""

    NODE_ID = "featurecounts"
    DISPLAY_NAME = "featureCounts"
    REQUIRED_CONDA_PACKAGES = ["subread", "samtools"]
    CONDA_PACKAGE_CONSTRAINTS = {"subread": "2.1.1", "samtools": "1.23.1"}
    PACKAGE_CONSTRAINTS = ("subread=2.1.1", "samtools=1.23.1")
    CATEGORY = "rna_seq"
    DESCRIPTION = "Measure gene expression by counting SAM/BAM reads assigned to genomic features with featureCounts."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "featureCounts",
        "featurecounts",
        "featureCounts gene counts",
        "subread",
        "gene counts",
        "RNA-seq read counting",
        "GTF annotation",
    ]
    RETURN_TYPES = ("COUNTS", "TSV", "TSV", "BAM", "TSV")
    RETURN_NAMES = ("counts", "summary", "feature_lengths", "annotated_bam", "junction_counts")
    REQUIRED_EXECUTABLES = ["featureCounts", "samtools"]
    DOCUMENTATION_URL = "https://subread.sourceforge.net/SubreadUsersGuide.pdf"
    CITATION_DOIS = [FEATURECOUNTS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{FEATURECOUNTS_CITATION_DOI}"]
    CITATION_TEXT = FEATURECOUNTS_CITATION_TEXT
    VERSION = "2.1.1"
    SOURCE_URL = "https://sourceforge.net/projects/subread/files/subread-2.1.1/subread-2.1.1-source.tar.gz/download"
    SOURCE_SHA256 = "6392d7c66831cdd767e58251892a79a51b6fab8ed0ba9671ad5e85ff1ab01eaa"
    UPSTREAM_CLI_SOURCE = "src/readSummary.c"
    UPSTREAM_MANUAL_SOURCE = "doc/SubreadUsersGuide.tex"
    UPSTREAM_SOURCE = "src/readSummary.c:print_usage; doc/SubreadUsersGuide.tex:featureCounts"
    SOURCE_AUTHORITIES = {
        "source_archive": (SOURCE_URL, SOURCE_SHA256),
        "cli_contract": UPSTREAM_CLI_SOURCE,
        "manual_contract": UPSTREAM_MANUAL_SOURCE,
    }
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    EXIT_SEMANTICS = (
        "A non-zero featureCounts, text-processing, or samtools exit is fatal; success additionally "
        "requires the counts and summary plus every selected optional artifact to exist."
    )
    SHELL = True

    ANNO_SELECT_OPTIONS = ["builtin", "cached", "history"]
    FORMAT_OPTIONS = ["tabdel_short", "tabdel_medium", "tabdel_full"]
    STRAND_OPTIONS = ["0", "1", "2"]
    PAIRED_END_OPTIONS = ["single_end", "PE_individual", "PE_fragments"]
    MULTIFEAT_OPTIONS = ["", "-M", "-O", "-O -M"]
    JUNCTION_OPTIONS = ["", "-J"]
    SPLITONLY_OPTIONS = ["", "--splitOnly", "--nonSplitOnly"]
    READ_REDUCTION_OPTIONS = ["", "--read2pos 5", "--read2pos 3"]
    BUILTIN_GENOME_OPTIONS = ["hg38", "hg19", "mm10", "mm9"]

    @classmethod
    def _alignment(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("alignment", inputs.get("bam", "")))

    @classmethod
    def _annotation_file(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_gene_sets", inputs.get("gtf", inputs.get("annotation", ""))))

    @classmethod
    def _cached_annotation_file(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_gene_sets_cached", ""))

    @classmethod
    def _anno_select(cls, inputs: dict[str, Any]) -> str:
        if inputs.get("gtf") or inputs.get("annotation"):
            return str(inputs.get("anno_select", "history"))
        return str(inputs.get("anno_select", "history"))

    @classmethod
    def _feature_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("gff_feature_type", inputs.get("feature_type", "exon")))

    @classmethod
    def _feature_attribute(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("gff_feature_attribute", inputs.get("attribute", "gene_id")))

    @staticmethod
    def _flag_value(inputs: dict[str, Any], key: str, flag: str) -> str:
        return flag if inputs.get(key) else ""

    @classmethod
    def _sample_label(cls, alignment: str) -> str:
        return str(Path(alignment).name) if alignment else ""

    @classmethod
    def _counts_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["featureCounts"]
        anno_select = cls._anno_select(inputs)
        if anno_select == "builtin":
            genome = str(inputs.get("bgenome", "hg38"))
            cmd.extend(["-a", f"${{FC_PATH}}/annotation/{genome}_RefSeq_exon.txt", "-F", "SAF"])
        elif anno_select == "cached":
            cmd.extend(["-a", cls._cached_annotation_file(inputs), "-F", "GTF"])
        else:
            cmd.extend(["-a", cls._annotation_file(inputs), "-F", "GTF"])
        cmd.extend(
            [
                "-o",
                "output",
                "-T",
                str(inputs.get("threads", 1)),
                "-s",
                str(inputs.get("strand_specificity", inputs.get("strandness", "0"))),
                "-Q",
                str(inputs.get("mapping_quality", 0)),
            ]
        )
        for flag in (
            str(inputs.get("splitonly", "")),
            cls._flag_value(inputs, "primary", "--primary"),
            cls._flag_value(inputs, "ignore_dup", "--ignoreDup"),
        ):
            if flag:
                cmd.extend(flag.split())
        if anno_select != "builtin":
            cmd.extend(["-t", cls._feature_type(inputs), "-g", cls._feature_attribute(inputs)])
            if inputs.get("summarization_level"):
                cmd.append("-f")
        multifeat = str(inputs.get("multifeat", ""))
        if multifeat:
            cmd.extend(multifeat.split())
            if inputs.get("fraction"):
                cmd.append("--fraction")
        junction = str(inputs.get("count_exon_exon_junction_reads", ""))
        if junction:
            cmd.append(junction)
            genome = str(inputs.get("genome", "") or "")
            if genome:
                cmd.extend(["-G", genome])
        for flag in (
            cls._flag_value(inputs, "long_reads", "-L"),
            cls._flag_value(inputs, "by_read_group", "--byReadGroup"),
            cls._flag_value(inputs, "largest_overlap", "--largestOverlap"),
        ):
            if flag:
                cmd.append(flag)
        cmd.extend(
            [
                "--minOverlap",
                str(inputs.get("min_overlap", 1)),
                "--fracOverlap",
                str(inputs.get("frac_overlap", 0)),
                "--fracOverlapFeature",
                str(inputs.get("frac_overlap_feature", 0)),
            ]
        )
        read_reduction = str(inputs.get("read_reduction", ""))
        if read_reduction:
            cmd.extend(read_reduction.split())
        if inputs.get("R"):
            cmd.extend(["-R", "BAM", "--Rpath", _out(inputs)])
        if str(inputs.get("read_extension_5p", 0)) != "0":
            cmd.extend(["--readExtension5", str(inputs["read_extension_5p"])])
        if str(inputs.get("read_extension_3p", 0)) != "0":
            cmd.extend(["--readExtension3", str(inputs["read_extension_3p"])])
        paired_end_status = str(inputs.get("paired_end_status", "single_end"))
        if paired_end_status != "single_end" or inputs.get("count_read_pairs") is not False:
            if paired_end_status == "single_end" and inputs.get("count_read_pairs") is not True:
                pass
            else:
                cmd.append("-p")
                if paired_end_status == "PE_fragments" or inputs.get("count_read_pairs") is True:
                    cmd.append("--countReadPairs")
                if paired_end_status == "PE_fragments" and inputs.get("check_distance"):
                    cmd.extend(
                        [
                            "-P",
                            "-d",
                            str(inputs.get("minimum_fragment_length", 50)),
                            "-D",
                            str(inputs.get("maximum_fragment_length", 600)),
                        ]
                    )
                if inputs.get("only_both_ends"):
                    cmd.append("-B")
                if inputs.get("exclude_chimerics"):
                    cmd.append("-C")
        cmd.append(cls._alignment(inputs))
        return cmd

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        alignment = cls._alignment(inputs)
        label = cls._sample_label(alignment)
        sed_sample = _shell_join(["sed", "-e", f"s|{alignment}|{label}|g"])
        commands = [
            "export FC_PATH=$(command -v featureCounts | sed 's@/bin/featureCounts$@@')",
            _shell_join(cls._counts_command(inputs)).replace("'${FC_PATH}/", "${FC_PATH}/").replace(".txt'", ".txt"),
            f"grep -v '^#' output | {sed_sample} > body.txt",
        ]
        format_value = str(inputs.get("format", "tabdel_short"))
        counts_path = f"{out}/counts.tsv"
        if format_value == "tabdel_medium":
            commands.extend(
                [
                    "cut -f 1,7- body.txt > expression_matrix.txt",
                    "cut -f 6 body.txt > gene_lengths.txt",
                    "paste expression_matrix.txt gene_lengths.txt > expression_matrix.txt.bak",
                    _shell_join(["mv", "-f", "expression_matrix.txt.bak", counts_path]),
                ]
            )
        elif format_value == "tabdel_full":
            commands.append(_shell_join(["cp", "body.txt", counts_path]))
        else:
            commands.append(f"cut -f 1,7- body.txt > {shlex.quote(counts_path)}")
        if inputs.get("include_feature_length_file"):
            commands.append(f"cut -f 1,6 body.txt > {shlex.quote(f'{out}/feature_lengths.tsv')}")
        if str(inputs.get("count_exon_exon_junction_reads", "")) == "-J":
            commands.append(f"{sed_sample} output.jcounts > {shlex.quote(f'{out}/junction_counts.tsv')}")
        if inputs.get("R"):
            threads = str(inputs.get("threads", 1))
            assignment_bam = str(Path(out) / f"{label}.featureCounts.bam")
            commands.append(
                f"samtools sort --no-PG -o {shlex.quote(f'{out}/annotated.bam')} "
                f'-@ {threads} -T "${{TMPDIR:-.}}" {shlex.quote(assignment_bam)}'
            )
        commands.append(f"{sed_sample} output.summary > {shlex.quote(f'{out}/summary.tsv')}")
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "counts.tsv", out / "summary.tsv"]
        if inputs.get("include_feature_length_file"):
            outputs.append(out / "feature_lengths.tsv")
        if inputs.get("R"):
            outputs.append(out / "annotated.bam")
        if str(inputs.get("count_exon_exon_junction_reads", "")) == "-J":
            outputs.append(out / "junction_counts.tsv")
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        """Bind optional physical artifacts to their stable public output names."""

        output_names = {
            "counts.tsv": "counts",
            "summary.tsv": "summary",
            "feature_lengths.tsv": "feature_lengths",
            "annotated.bam": "annotated_bam",
            "junction_counts.tsv": "junction_counts",
        }
        mapped: dict[str, Path] = {}
        for raw_path in planned_paths:
            path = Path(raw_path)
            output_name = output_names.get(path.name)
            if output_name is None:
                raise ValueError(f"featurecounts planned an unknown output artifact: {path.name}")
            if output_name in mapped:
                raise ValueError(f"featurecounts planned duplicate output artifact: {path.name}")
            mapped[output_name] = path

        missing_required = {"counts", "summary"}.difference(mapped)
        if missing_required:
            missing = ", ".join(sorted(missing_required))
            raise ValueError(f"featurecounts did not plan required output(s): {missing}")
        return mapped

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Execute featureCounts and return optional artifacts by stable port name."""

        result = await super().run(**kwargs)
        mapped = self.__class__.MAP_PLANNED_OUTPUTS([Path(path) for path in result])
        return {"outputs": {name: str(path) for name, path in mapped.items()}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._alignment(inputs).strip():
            return "alignment is required"
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        anno_select = cls._anno_select(inputs)
        if anno_select not in cls.ANNO_SELECT_OPTIONS:
            return f"anno_select must be one of: {', '.join(cls.ANNO_SELECT_OPTIONS)}"
        if anno_select == "history" and not cls._annotation_file(inputs).strip():
            return "reference_gene_sets is required for history anno_select"
        if anno_select == "cached" and not cls._cached_annotation_file(inputs).strip():
            return "reference_gene_sets_cached is required for cached anno_select"
        format_value = str(inputs.get("format", "tabdel_short"))
        if format_value not in cls.FORMAT_OPTIONS:
            return f"format must be one of: {', '.join(cls.FORMAT_OPTIONS)}"
        strand = str(inputs.get("strand_specificity", inputs.get("strandness", "0")))
        if strand not in cls.STRAND_OPTIONS:
            return f"strand_specificity must be one of: {', '.join(cls.STRAND_OPTIONS)}"
        paired_end_status = str(inputs.get("paired_end_status", "single_end"))
        if paired_end_status not in cls.PAIRED_END_OPTIONS:
            return f"paired_end_status must be one of: {', '.join(cls.PAIRED_END_OPTIONS)}"
        multifeat = str(inputs.get("multifeat", ""))
        if multifeat not in cls.MULTIFEAT_OPTIONS:
            return f"multifeat must be one of: {', '.join(cls.MULTIFEAT_OPTIONS)}"
        junction = str(inputs.get("count_exon_exon_junction_reads", ""))
        if junction not in cls.JUNCTION_OPTIONS:
            return f"count_exon_exon_junction_reads must be one of: {', '.join(cls.JUNCTION_OPTIONS)}"
        splitonly = str(inputs.get("splitonly", ""))
        if splitonly not in cls.SPLITONLY_OPTIONS:
            return f"splitonly must be one of: {', '.join(cls.SPLITONLY_OPTIONS)}"
        read_reduction = str(inputs.get("read_reduction", ""))
        if read_reduction not in cls.READ_REDUCTION_OPTIONS:
            return f"read_reduction must be one of: {', '.join(cls.READ_REDUCTION_OPTIONS)}"
        mapping_quality = int(inputs.get("mapping_quality", 0))
        if mapping_quality < 0:
            return "mapping_quality must be >= 0"
        for key in ("frac_overlap", "frac_overlap_feature"):
            value = float(inputs.get(key, 0))
            if value < 0 or value > 1:
                return f"{key} must be between 0 and 1"
        min_fragment = int(inputs.get("minimum_fragment_length", 50))
        max_fragment = int(inputs.get("maximum_fragment_length", 600))
        if max_fragment < min_fragment:
            return "maximum_fragment_length must be >= minimum_fragment_length"
        threads = inputs.get("threads", 1)
        if isinstance(threads, bool) or not isinstance(threads, int):
            return "threads must be an integer"
        # Subread 2.1.1 defines FC_MAX_THREADS as 64 in src/subread.h and
        # validates -T against that bound in src/readSummary.c.  Keep the
        # node contract aligned with the executable rather than the former
        # Galaxy slider's narrower 32-thread UI cap.
        if not 1 <= threads <= 64:
            return "threads must be between 1 and 64"
        if inputs.get("long_reads"):
            if threads != 1:
                return "long_reads requires threads=1"
            if paired_end_status != "single_end" or inputs.get("count_read_pairs"):
                return "long_reads supports reads only and cannot use paired-end fragment counting"
        if inputs.get("fraction") and not multifeat:
            return "fraction requires -M, -O, or both via multifeat"
        if inputs.get("check_distance"):
            if paired_end_status != "PE_fragments":
                return "check_distance requires paired_end_status PE_fragments"
            if not inputs.get("only_both_ends"):
                return "check_distance requires only_both_ends because featureCounts -P requires -B"
        validation = _validate_file(cls._alignment(inputs), "alignment")
        if validation is not True:
            return validation
        if anno_select == "history":
            validation = _validate_file(cls._annotation_file(inputs), "reference_gene_sets")
            if validation is not True:
                return validation
        elif anno_select == "cached":
            validation = _validate_file(
                cls._cached_annotation_file(inputs),
                "reference_gene_sets_cached",
            )
            if validation is not True:
                return validation
        genome = str(inputs.get("genome", "") or "")
        if genome:
            validation = _validate_file(genome, "genome")
            if validation is not True:
                return validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": (
                    ("SAM", "BAM"),
                    {"description": "One SAM or BAM alignment file for read counting"},
                ),
            },
            "optional": {
                "anno_select": (
                    "STRING",
                    {
                        "default": "history",
                        "options": cls.ANNO_SELECT_OPTIONS,
                        "description": "Use built-in, cached, or history gene annotations",
                    },
                ),
                "reference_gene_sets": (
                    "GFF_GTF",
                    {"default": "", "description": "History GFF/GTF annotation file"},
                ),
                "reference_gene_sets_cached": (
                    "GFF_GTF",
                    {"default": "", "description": "Cached GFF/GTF annotation path"},
                ),
                "bgenome": (
                    "STRING",
                    {
                        "default": "hg38",
                        "options": cls.BUILTIN_GENOME_OPTIONS,
                        "description": "Built-in featureCounts annotation genome",
                    },
                ),
                "format": (
                    "STRING",
                    {"default": "tabdel_short", "options": cls.FORMAT_OPTIONS, "description": "Counts table format"},
                ),
                "strand_specificity": ("STRING", {"default": "0", "options": cls.STRAND_OPTIONS}),
                "include_feature_length_file": ("BOOLEAN", {"default": False}),
                "gff_feature_type": ("STRING", {"default": "exon", "description": "GFF feature type filter"}),
                "gff_feature_attribute": (
                    "STRING",
                    {"default": "gene_id", "description": "GFF attribute for grouping"},
                ),
                "summarization_level": ("BOOLEAN", {"default": False, "description": "Count at feature level"}),
                "paired_end_status": (
                    "STRING",
                    {"default": "single_end", "options": cls.PAIRED_END_OPTIONS, "advanced": True},
                ),
                "only_both_ends": ("BOOLEAN", {"default": False, "advanced": True}),
                "exclude_chimerics": ("BOOLEAN", {"default": False, "advanced": True}),
                "check_distance": ("BOOLEAN", {"default": False, "advanced": True}),
                "minimum_fragment_length": ("INT", {"default": 50, "min": 0, "advanced": True}),
                "maximum_fragment_length": ("INT", {"default": 600, "min": 1, "advanced": True}),
                "mapping_quality": ("INT", {"default": 0, "min": 0}),
                "splitonly": ("STRING", {"default": "", "options": cls.SPLITONLY_OPTIONS, "advanced": True}),
                "primary": ("BOOLEAN", {"default": False, "advanced": True}),
                "ignore_dup": ("BOOLEAN", {"default": False, "advanced": True}),
                "multifeat": ("STRING", {"default": "", "options": cls.MULTIFEAT_OPTIONS, "advanced": True}),
                "fraction": ("BOOLEAN", {"default": False, "advanced": True}),
                "count_exon_exon_junction_reads": (
                    "STRING",
                    {"default": "", "options": cls.JUNCTION_OPTIONS, "advanced": True},
                ),
                "genome": ("FASTA", {"default": "", "advanced": True}),
                "long_reads": ("BOOLEAN", {"default": False, "advanced": True}),
                "by_read_group": ("BOOLEAN", {"default": False, "advanced": True}),
                "largest_overlap": ("BOOLEAN", {"default": False, "advanced": True}),
                "min_overlap": ("INT", {"default": 1, "advanced": True}),
                "frac_overlap": ("FLOAT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "frac_overlap_feature": ("FLOAT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "read_reduction": ("STRING", {"default": "", "options": cls.READ_REDUCTION_OPTIONS, "advanced": True}),
                "R": ("BOOLEAN", {"default": False, "advanced": True}),
                "read_extension_5p": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "read_extension_3p": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "gtf": ("GFF_GTF", {"default": "", "description": "Compatibility alias for history annotation"}),
                "bam": ("BAM", {"default": "", "description": "Compatibility alias for alignment"}),
                "threads": (
                    "INT",
                    {"default": 1, "min": 1, "max": 64, "display": "slider"},
                ),
                "count_read_pairs": ("BOOLEAN", {"default": False, "advanced": True}),
                "feature_type": ("STRING", {"default": "", "advanced": True}),
                "attribute": ("STRING", {"default": "", "advanced": True}),
                "strandness": ("STRING", {"default": "0", "options": cls.STRAND_OPTIONS, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }
