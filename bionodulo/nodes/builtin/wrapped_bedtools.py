"""BioNodulo built-in wrapped tool nodes split by tool family."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

class BEDToolsCoverageNode(CommandNode):
    """Compute depth and breadth of B features across A intervals."""

    NODE_ID = "bedtools_coveragebed"
    DISPLAY_NAME = "BEDTools Coverage"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Compute interval coverage depth and breadth using bedtools coverage."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "coverage", "coveragebed", "depth", "breadth", "interval coverage"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("coverage",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/coverage.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btq033"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btq033"]
    CITATION_TEXT = "BEDTools: a flexible suite of utilities for comparing genomic features."
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "coverage"]
        if inputs.get("d"):
            cmd.append("-d")
        if inputs.get("hist"):
            cmd.append("-hist")
        if inputs.get("split"):
            cmd.append("-split")
        if inputs.get("strandedness"):
            cmd.append("-s")
        if inputs.get("mean"):
            cmd.append("-mean")
        _add_if_value(cmd, "-f", inputs.get("overlap_a"))
        _add_if_value(cmd, "-F", inputs.get("overlap_b"))
        if inputs.get("reciprocal_overlap"):
            cmd.append("-r")
        if inputs.get("a_or_b"):
            cmd.append("-e")
        cmd.extend(["-a", str(inputs.get("inputA", "")), "-b", *_as_list(inputs.get("inputB"))])
        if inputs.get("sorted"):
            cmd.append("-sorted")
        if str(inputs.get("inputA", "")).lower().endswith((".gff", ".gff3")):
            cmd.extend(["|", "sort", "-k1,1", "-k4,2n"])
        else:
            cmd.extend(["|", "sort", "-k1,1", "-k2,2n"])
        _add_shell_redirect(cmd, f"{_out(inputs)}/coverage.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "coverage.bed"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "File A intervals on which coverage is calculated"}),
                "inputB": ("BED_LIST", {"description": "One or more file B interval or BAM inputs"}),
            },
            "optional": {
                "split": ("BOOLEAN", {"default": False, "description": "Treat split BED12/BAM alignments as distinct intervals"}),
                "strandedness": ("BOOLEAN", {"default": False, "description": "Require same-strand overlaps"}),
                "d": ("BOOLEAN", {"default": False, "description": "Report depth at each position"}),
                "hist": ("BOOLEAN", {"default": False, "description": "Report coverage histogram"}),
                "mean": ("BOOLEAN", {"default": False, "description": "Report mean depth"}),
                "overlap_a": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of A"}),
                "overlap_b": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of B"}),
                "reciprocal_overlap": ("BOOLEAN", {"default": False, "advanced": True}),
                "a_or_b": ("BOOLEAN", {"default": False, "advanced": True}),
                "sorted": ("BOOLEAN", {"default": False, "description": "Use sorted input mode"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsGenomeCoverageNode(CommandNode):
    """Compute genome-wide interval coverage with bedtools genomecov."""

    NODE_ID = "bedtools_genomecoveragebed"
    DISPLAY_NAME = "BEDTools Genome Coverage"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Compute genome-wide coverage from BAM or interval files with bedtools genomecov."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "genomecov", "genome coverage", "bedgraph", "coverage histogram"]
    RETURN_TYPES = ("BEDGRAPH", "TSV")
    RETURN_NAMES = ("genome_coverage_bedgraph", "genome_coverage_histogram")
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/genomecov.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btq033"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btq033"]
    CITATION_TEXT = "BEDTools: a flexible suite of utilities for comparing genomic features."
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        report = str(inputs.get("report", inputs.get("report_select", "bg")))
        output_name = "genome_coverage.tsv" if report == "hist" else "genome_coverage.bedgraph"
        input_type = str(inputs.get("input_type", inputs.get("input_type_select", "bed")))
        cmd = ["bedtools", "genomecov"]
        if input_type == "bam":
            cmd.extend(["-ibam", str(inputs.get("input", ""))])
        else:
            cmd.extend(["-i", str(inputs.get("input", ""))])
            _add_if_value(cmd, "-g", inputs.get("genome"))
        if inputs.get("split"):
            cmd.append("-split")
        strand = str(inputs.get("strand", ""))
        if strand:
            cmd.extend(["-strand", strand.replace("-strand ", "")])
        if report == "bg":
            cmd.append("-bga" if inputs.get("zero_regions") else "-bg")
            _add_if_value(cmd, "-scale", inputs.get("scale", 1.0))
        else:
            _add_if_value(cmd, "-max", inputs.get("max"))
        if inputs.get("d"):
            cmd.append("-d")
        if inputs.get("dz"):
            cmd.append("-dz")
        if inputs.get("five"):
            cmd.append("-5")
        if inputs.get("three"):
            cmd.append("-3")
        _add_shell_redirect(cmd, f"{_out(inputs)}/{output_name}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        report = str(inputs.get("report", inputs.get("report_select", "bg")))
        if report == "hist":
            return [out / "genome_coverage.tsv"]
        return [out / "genome_coverage.bedgraph"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": ("STRING", {"default": "bed", "options": ["bed", "bam"]}),
                "input": ("FILE", {"description": "Sorted BED/GFF/VCF/BAM input"}),
                "report": ("STRING", {"default": "bg", "options": ["bg", "hist"], "description": "BedGraph or histogram output"}),
            },
            "optional": {
                "genome": ("TSV", {"description": "Genome chromosome sizes file required for BED-like input"}),
                "zero_regions": ("BOOLEAN", {"default": False, "description": "Report zero-coverage regions with -bga"}),
                "scale": ("FLOAT", {"default": 1.0, "min": 0}),
                "max": ("INT", {"default": "", "min": 0, "description": "Histogram max depth bin"}),
                "split": ("BOOLEAN", {"default": False, "description": "Treat split BED12/BAM alignments as distinct intervals"}),
                "strand": ("STRING", {"default": "", "options": ["", "+", "-"], "description": "Restrict coverage to one strand"}),
                "d": ("BOOLEAN", {"default": False, "description": "Report 1-based per-position depth"}),
                "dz": ("BOOLEAN", {"default": False, "description": "Report 0-based non-zero per-position depth"}),
                "five": ("BOOLEAN", {"default": False, "description": "Calculate coverage of 5' positions"}),
                "three": ("BOOLEAN", {"default": False, "description": "Calculate coverage of 3' positions"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsSubtractNode(CommandNode):
    """Remove portions of A intervals that overlap B intervals."""

    NODE_ID = "bedtools_subtractbed"
    DISPLAY_NAME = "BEDTools Subtract"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Remove intervals or overlapping bases from one feature set using bedtools subtract."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "subtract", "subtractbed", "interval subtraction", "blacklist"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("subtracted",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/subtract.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btq033"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btq033"]
    CITATION_TEXT = "BEDTools: a flexible suite of utilities for comparing genomic features."
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        strand_flags = {"same": "-s", "opposite": "-S", "-s": "-s", "-S": "-S"}
        remove_flags = {
            "remove_feature": "-A",
            "remove_feature_sum": "-N",
            "-A": "-A",
            "-N": "-N",
        }
        cmd = ["bedtools", "subtract"]
        strand = str(inputs.get("strand", ""))
        if strand_flags.get(strand):
            cmd.append(strand_flags[strand])
        cmd.extend(["-a", str(inputs.get("inputA", "")), "-b", str(inputs.get("inputB", ""))])
        _add_if_value(cmd, "-f", inputs.get("overlap"))
        remove_if_overlap = str(inputs.get("remove_if_overlap", inputs.get("removeIfOverlap", "")))
        if remove_flags.get(remove_if_overlap):
            cmd.append(remove_flags[remove_if_overlap])
        _add_shell_redirect(cmd, f"{_out(inputs)}/subtracted.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "subtracted.bed"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Intervals to subtract from"}),
                "inputB": ("BED", {"description": "Intervals used to mask or remove A bases"}),
            },
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap required as a fraction of A"}),
                "remove_if_overlap": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "remove_feature", "remove_feature_sum"],
                        "description": "Remove entire A feature on any overlap, or on cumulative overlap with -f",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsMergeNode(CommandNode):
    """Combine overlapping or nearby intervals with bedtools merge."""

    NODE_ID = "bedtools_mergebed"
    DISPLAY_NAME = "BEDTools Merge"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Combine overlapping or nearby intervals into flattened regions with optional column summaries."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "merge", "mergebed", "combine intervals", "flatten intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("merged",)
    REQUIRED_EXECUTABLES = ["mergeBed"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/merge.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btq033"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btq033"]
    CITATION_TEXT = "BEDTools: a flexible suite of utilities for comparing genomic features."
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        strand_flags = {
            "same": ["-s"],
            "forward": ["-S", "+"],
            "reverse": ["-S", "-"],
            "-s": ["-s"],
            "-S +": ["-S", "+"],
            "-S -": ["-S", "-"],
        }
        cmd = ["mergeBed", "-i", str(inputs.get("input", ""))]
        cmd.extend(strand_flags.get(str(inputs.get("strand", "")), []))
        cmd.extend(["-d", str(inputs.get("distance", 0))])
        if inputs.get("header"):
            cmd.append("-header")
        columns = str(inputs.get("columns", inputs.get("cols", ""))).strip()
        operations = str(inputs.get("operations", inputs.get("operation", ""))).strip()
        if columns and operations:
            cmd.extend(["-c", columns, "-o", operations])
        if str(inputs.get("input", "")).lower().endswith(".bam"):
            cmd.append("-bed")
        _add_shell_redirect(cmd, f"{_out(inputs)}/merged.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "merged.bed"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "Presorted BED/GFF/VCF/BAM intervals to merge"}),
                "distance": ("INT", {"default": 0, "description": "Maximum distance between intervals to merge"}),
            },
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "forward", "reverse"]}),
                "header": ("BOOLEAN", {"default": False, "description": "Print input header before results"}),
                "columns": ("STRING", {"default": "", "description": "Comma-separated columns to summarize"}),
                "operations": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Comma-separated operations such as sum,mean,count,collapse,distinct",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsSortNode(CommandNode):
    """Sort genomic intervals with bedtools sort."""

    NODE_ID = "bedtools_sortbed"
    DISPLAY_NAME = "BEDTools Sort"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Order BED, GFF, VCF, or bedGraph intervals by coordinate, size, score, or a genome file."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "sort", "sortbed", "coordinate sort", "genome order"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("sorted_intervals",)
    REQUIRED_EXECUTABLES = ["sortBed"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/sort.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btq033"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btq033"]
    CITATION_TEXT = "BEDTools: a flexible suite of utilities for comparing genomic features."
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["sortBed", "-i", str(inputs.get("input", ""))]
        sort_by = str(inputs.get("sort_by", inputs.get("option", "")))
        if sort_by:
            cmd.append(sort_by)
        _add_if_value(cmd, "-g", inputs.get("genome"))
        output_ext = _bedtools_ext(inputs.get("input"))
        _add_shell_redirect(cmd, f"{_out(inputs)}/sorted.{output_ext}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"sorted.{_bedtools_ext(inputs.get('input'))}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "BED, GFF, VCF, bedGraph, or EncodePeak intervals to sort"}),
            },
            "optional": {
                "sort_by": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "-sizeA", "-sizeD", "-chrThenSizeA", "-chrThenSizeD", "-chrThenScoreA", "-chrThenScoreD"],
                    },
                ),
                "genome": ("TSV", {"description": "Optional genome chromosome sizes file for sort order"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsGetFastaNode(CommandNode):
    """Extract FASTA or tabular sequences for genomic intervals."""

    NODE_ID = "bedtools_getfastabed"
    DISPLAY_NAME = "BEDTools getfasta"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Extract sequences from a FASTA file using BED, GFF, VCF, or bedGraph intervals."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "getfasta", "getfastabed", "extract sequence", "fasta intervals"]
    RETURN_TYPES = ("FASTA", "TSV")
    RETURN_NAMES = ("extracted_fasta", "extracted_tsv")
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/getfasta.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btq033"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btq033"]
    CITATION_TEXT = "BEDTools: a flexible suite of utilities for comparing genomic features."
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_name = "extracted.tsv" if inputs.get("tab") else "extracted.fasta"
        cmd = ["ln", "-s", str(inputs.get("fasta", "")), "input.fasta", "&&", "bedtools", "getfasta"]
        if inputs.get("name"):
            cmd.append("-name")
        if inputs.get("name_only", inputs.get("nameOnly")):
            cmd.append("-nameOnly")
        if inputs.get("tab"):
            cmd.append("-tab")
        if inputs.get("strand"):
            cmd.append("-s")
        if inputs.get("split"):
            cmd.append("-split")
        cmd.extend([
            "-fi",
            "input.fasta",
            "-bed",
            str(inputs.get("input", "")),
            "-fo",
            f"{_out(inputs)}/{output_name}",
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if inputs.get("tab"):
            return [out / "extracted.tsv"]
        return [out / "extracted.fasta"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "Intervals used to extract sequence"}),
                "fasta": ("FASTA", {"description": "Reference FASTA file"}),
            },
            "optional": {
                "name": ("BOOLEAN", {"default": False, "description": "Use BED name and coordinates in FASTA headers"}),
                "name_only": ("BOOLEAN", {"default": False, "description": "Use only the BED name in FASTA headers"}),
                "tab": ("BOOLEAN", {"default": False, "description": "Emit tab-delimited name and sequence output"}),
                "strand": ("BOOLEAN", {"default": False, "description": "Reverse complement antisense features"}),
                "split": ("BOOLEAN", {"default": False, "description": "Use BED12 blocks rather than full interval spans"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsComplementNode(CommandNode):
    """Report genome intervals not covered by the input feature file."""

    NODE_ID = "bedtools_complementbed"
    DISPLAY_NAME = "BEDTools Complement"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Extract genome intervals not represented by an interval file using bedtools complement."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "complement", "complementbed", "genome gaps", "uncovered intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("complement",)
    REQUIRED_EXECUTABLES = ["complementBed"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/complement.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["complementBed", "-i", str(inputs.get("input", ""))]
        _bedtools_add_genome(cmd, inputs)
        _add_shell_redirect(cmd, f"{_out(inputs)}/complement.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "complement.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "Sorted interval file whose uncovered genome intervals are reported"}),
                "genome": ("TSV", {"description": "Two-column chromosome sizes genome file"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsFlankNode(CommandNode):
    """Create flanking intervals around each input feature."""

    NODE_ID = "bedtools_flankbed"
    DISPLAY_NAME = "BEDTools Flank"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Create new intervals from the flanks of existing intervals with bedtools flank."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "flank", "flankbed", "upstream", "downstream"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("flanks",)
    REQUIRED_EXECUTABLES = ["flankBed"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/flank.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["flankBed"]
        if inputs.get("pct"):
            cmd.append("-pct")
        if inputs.get("strand"):
            cmd.append("-s")
        _bedtools_add_genome(cmd, inputs)
        cmd.extend(["-i", str(inputs.get("input", ""))])
        _bedtools_add_lr_or_b(cmd, inputs)
        _add_shell_redirect(cmd, f"{_out(inputs)}/flanks.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "flanks.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "Intervals to flank"}),
                "genome": ("TSV", {"description": "Two-column chromosome sizes genome file"}),
            },
            "optional": {
                "addition_mode": ("STRING", {"default": "b", "options": ["b", "lr"]}),
                "both": ("FLOAT", {"default": 1, "min": 0, "description": "Symmetric flank size"}),
                "left": ("FLOAT", {"default": 0, "min": 0, "description": "Left/upstream flank size"}),
                "right": ("FLOAT", {"default": 0, "min": 0, "description": "Right/downstream flank size"}),
                "pct": ("BOOLEAN", {"default": False, "description": "Interpret sizes as fractions of feature length"}),
                "strand": ("BOOLEAN", {"default": False, "description": "Interpret left/right relative to feature strand"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsSlopNode(CommandNode):
    """Expand input intervals while respecting chromosome bounds."""

    NODE_ID = "bedtools_slopbed"
    DISPLAY_NAME = "BEDTools Slop"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Adjust interval sizes with bedtools slop while clipping to chromosome boundaries."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "slop", "slopbed", "extend intervals", "resize intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("slopped",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/slop.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "slop"]
        if inputs.get("pct"):
            cmd.append("-pct")
        if inputs.get("strand"):
            cmd.append("-s")
        _bedtools_add_genome(cmd, inputs)
        cmd.extend(["-i", str(inputs.get("inputA", ""))])
        _bedtools_add_lr_or_b(cmd, inputs)
        if inputs.get("header"):
            cmd.append("-header")
        _add_shell_redirect(cmd, f"{_out(inputs)}/slopped.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "slopped.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Intervals to resize"}),
                "genome": ("TSV", {"description": "Two-column chromosome sizes genome file"}),
            },
            "optional": {
                "addition_mode": ("STRING", {"default": "b", "options": ["b", "lr"]}),
                "both": ("FLOAT", {"default": 1, "min": 0, "description": "Symmetric extension size"}),
                "left": ("FLOAT", {"default": 0, "min": 0, "description": "Left/upstream extension size"}),
                "right": ("FLOAT", {"default": 0, "min": 0, "description": "Right/downstream extension size"}),
                "pct": ("BOOLEAN", {"default": False, "description": "Interpret sizes as fractions of feature length"}),
                "strand": ("BOOLEAN", {"default": False, "description": "Interpret left/right relative to feature strand"}),
                "header": ("BOOLEAN", {"default": False, "description": "Print the input header before results"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsWindowNode(CommandNode):
    """Find B intervals near A intervals within symmetric or asymmetric windows."""

    NODE_ID = "bedtools_windowbed"
    DISPLAY_NAME = "BEDTools Window"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Find intervals in B that overlap a window around each interval in A."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "window", "windowbed", "nearby intervals", "proximal features"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("window_matches",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/window.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "window"]
        input_a = str(inputs.get("inputA", ""))
        if input_a.lower().endswith(".bam"):
            cmd.extend(["-abam", input_a])
            if inputs.get("bed"):
                cmd.append("-bed")
        else:
            cmd.extend(["-a", input_a])
        cmd.extend(["-b", str(inputs.get("inputB", ""))])
        strand_flag = _bedtools_strand_flag(inputs.get("strand"), same="-sm", opposite="-Sm")
        if strand_flag:
            cmd.append(strand_flag)
        if str(inputs.get("addition_mode", "window")) == "lr":
            cmd.extend(["-l", str(inputs.get("left", 1000)), "-r", str(inputs.get("right", 1000))])
        else:
            cmd.extend(["-w", str(inputs.get("window", inputs.get("w", 1000)))])
        if inputs.get("original"):
            cmd.append("-u")
        if inputs.get("number"):
            cmd.append("-c")
        if inputs.get("nooverlaps"):
            cmd.append("-v")
        if inputs.get("header"):
            cmd.append("-header")
        _add_shell_redirect(cmd, f"{_out(inputs)}/window.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "window.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("FILE", {"description": "A intervals or BAM alignments"}),
                "inputB": ("BED", {"description": "B intervals to search near A"}),
            },
            "optional": {
                "addition_mode": ("STRING", {"default": "window", "options": ["window", "lr"]}),
                "window": ("INT", {"default": 1000, "min": 0, "description": "Symmetric window size"}),
                "left": ("INT", {"default": 1000, "min": 0, "description": "Left/upstream window size"}),
                "right": ("INT", {"default": 1000, "min": 0, "description": "Right/downstream window size"}),
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "bed": ("BOOLEAN", {"default": False, "description": "Write BED output for BAM input"}),
                "original": ("BOOLEAN", {"default": False, "description": "Report each A feature once if any B hit is found"}),
                "number": ("BOOLEAN", {"default": False, "description": "Report number of B hits for each A feature"}),
                "nooverlaps": ("BOOLEAN", {"default": False, "description": "Report only A features with no B hits"}),
                "header": ("BOOLEAN", {"default": False, "description": "Print the input header before results"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsMapNode(CommandNode):
    """Map statistics from overlapping B intervals onto A intervals."""

    NODE_ID = "bedtools_map"
    DISPLAY_NAME = "BEDTools Map"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Apply summary operations to columns from B intervals that overlap each A interval."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "map", "mapbed", "interval statistics", "overlap summary"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("mapped",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/map.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bedtools",
            "map",
            "-a",
            str(inputs.get("inputA", "")),
            "-b",
            str(inputs.get("inputB", "")),
        ]
        strand_flag = _bedtools_strand_flag(inputs.get("strand"))
        if strand_flag:
            cmd.append(strand_flag)
        columns = str(inputs.get("columns", inputs.get("cols", ""))).strip()
        operations = str(inputs.get("operations", inputs.get("operation", ""))).strip()
        if columns and operations:
            cmd.extend(["-c", columns, "-o", operations])
        _add_if_value(cmd, "-f", inputs.get("overlap"))
        _add_if_value(cmd, "-F", inputs.get("overlap_b", inputs.get("overlapB")))
        if inputs.get("reciprocal"):
            cmd.append("-r")
        if inputs.get("split"):
            cmd.append("-split")
        if inputs.get("header"):
            cmd.append("-header")
        _bedtools_add_genome(cmd, inputs)
        _add_shell_redirect(cmd, f"{_out(inputs)}/mapped.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "mapped.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Sorted A intervals"}),
                "inputB": ("BED", {"description": "Sorted B intervals with columns to summarize"}),
                "columns": ("STRING", {"default": "5", "description": "Comma-separated B columns to summarize"}),
                "operations": ("STRING", {"default": "mean", "description": "Comma-separated summary operations"}),
            },
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of A"}),
                "overlap_b": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of B"}),
                "reciprocal": ("BOOLEAN", {"default": False, "description": "Require reciprocal overlap"}),
                "split": ("BOOLEAN", {"default": False, "description": "Treat split BED12/BAM entries as distinct intervals"}),
                "header": ("BOOLEAN", {"default": False, "description": "Print the input header before results"}),
                "genome": ("TSV", {"description": "Optional genome chromosome sizes file"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsMultiIntersectNode(CommandNode):
    """Identify shared intervals across multiple interval files."""

    NODE_ID = "bedtools_multiintersectbed"
    DISPLAY_NAME = "BEDTools Multiple Intersect"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Identify common intervals among multiple sorted interval files with bedtools multiinter."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "multiinter", "multiintersect", "multiple intersect", "shared intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("multiintersect",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/multiinter.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        files = _as_list(inputs.get("inputs"))
        names = _as_list(inputs.get("names"))
        cmd = ["bedtools", "multiinter"]
        if inputs.get("header"):
            cmd.append("-header")
        if inputs.get("cluster"):
            cmd.append("-cluster")
        cmd.extend(["-filler", str(inputs.get("filler", "N/A"))])
        if inputs.get("empty"):
            cmd.append("-empty")
            _bedtools_add_genome(cmd, inputs)
        cmd.extend(["-i", *files])
        if names:
            cmd.extend(["-names", *names])
        _add_shell_redirect(cmd, f"{_out(inputs)}/multiintersect.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "multiintersect.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputs": ("BED_LIST", {"description": "Two or more sorted interval files"}),
            },
            "optional": {
                "names": ("STRING_LIST", {"description": "Optional custom labels matching the inputs order"}),
                "header": ("BOOLEAN", {"default": False, "description": "Add output header"}),
                "cluster": ("BOOLEAN", {"default": False, "description": "Invoke clustering algorithm"}),
                "filler": ("STRING", {"default": "N/A", "description": "Text for no-coverage values"}),
                "empty": ("BOOLEAN", {"default": False, "description": "Report regions with zero coverage across all files"}),
                "genome": ("TSV", {"description": "Genome chromosome sizes file required when empty is enabled"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsClusterNode(CommandNode):
    """Assign cluster IDs to overlapping or nearby intervals."""

    NODE_ID = "bedtools_clusterbed"
    DISPLAY_NAME = "BEDTools Cluster"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Cluster overlapping or nearby sorted intervals without flattening them."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "cluster", "clusterbed", "overlap clusters", "nearby intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("clustered",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/cluster.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "cluster"]
        if inputs.get("strand"):
            cmd.append("-s")
        cmd.extend(["-d", str(inputs.get("distance", 0)), "-i", str(inputs.get("inputA", ""))])
        _add_shell_redirect(cmd, f"{_out(inputs)}/clustered.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "clustered.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Sorted interval file to cluster"}),
            },
            "optional": {
                "strand": ("BOOLEAN", {"default": False, "description": "Only cluster features on the same strand"}),
                "distance": ("INT", {"default": 0, "description": "Maximum distance between features in the same cluster"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsJaccardNode(CommandNode):
    """Calculate Jaccard similarity between two interval sets."""

    NODE_ID = "bedtools_jaccard"
    DISPLAY_NAME = "BEDTools Jaccard"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Calculate intersection, union, Jaccard similarity, and intersection counts for two sorted interval sets."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "jaccard", "jaccardbed", "interval similarity", "set overlap"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("jaccard",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/jaccard.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "jaccard"]
        if inputs.get("strand"):
            cmd.append("-s")
        if inputs.get("split"):
            cmd.append("-split")
        if inputs.get("reciprocal"):
            cmd.append("-r")
        _add_if_value(cmd, "-f", inputs.get("overlap"))
        _add_if_value(cmd, "-F", inputs.get("overlap_b", inputs.get("overlapB")))
        cmd.extend(["-a", str(inputs.get("inputA", "")), "-b", str(inputs.get("inputB", ""))])
        _add_shell_redirect(cmd, f"{_out(inputs)}/jaccard.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "jaccard.tsv", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Sorted interval file A"}),
                "inputB": ("BED", {"description": "Sorted interval file B"}),
            },
            "optional": {
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of A"}),
                "overlap_b": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of B"}),
                "reciprocal": ("BOOLEAN", {"default": False, "description": "Require reciprocal overlap"}),
                "strand": ("BOOLEAN", {"default": False, "description": "Require same-strand overlaps"}),
                "split": ("BOOLEAN", {"default": False, "description": "Treat split BED12/BAM entries as distinct intervals"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsFisherNode(CommandNode):
    """Perform Fisher's exact test on overlap between two interval sets."""

    NODE_ID = "bedtools_fisher"
    DISPLAY_NAME = "BEDTools Fisher"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Calculate Fisher's exact test statistics for overlaps between two feature files."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "fisher", "fisherbed", "overlap significance", "exact test"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("fisher",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/fisher.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "fisher"]
        strand_flag = _bedtools_strand_flag(inputs.get("strand"))
        if strand_flag:
            cmd.append(strand_flag)
        if inputs.get("split"):
            cmd.append("-split")
        cmd.extend(["-a", str(inputs.get("inputA", "")), "-b", str(inputs.get("inputB", ""))])
        _add_if_value(cmd, "-f", inputs.get("overlap"))
        _bedtools_add_genome(cmd, inputs)
        if inputs.get("reciprocal"):
            cmd.append("-r")
        if inputs.get("merge"):
            cmd.append("-m")
        _add_shell_redirect(cmd, f"{_out(inputs)}/fisher.txt")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "fisher.txt", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Interval file A"}),
                "inputB": ("BED", {"description": "Interval file B"}),
                "genome": ("TSV", {"description": "Two-column chromosome sizes genome file"}),
            },
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "split": ("BOOLEAN", {"default": False, "description": "Treat split BED12/BAM entries as distinct intervals"}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of A"}),
                "reciprocal": ("BOOLEAN", {"default": False, "description": "Require reciprocal overlap"}),
                "merge": ("BOOLEAN", {"default": False, "description": "Merge overlapping intervals before testing"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsRelativeDistanceNode(CommandNode):
    """Calculate relative distance distribution between two interval sets."""

    NODE_ID = "bedtools_reldistbed"
    DISPLAY_NAME = "BEDTools Relative Distance"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Calculate the relative distance distribution between intervals in two feature sets."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "reldist", "reldistbed", "relative distance", "spatial correlation"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("relative_distance",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/reldist.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI, "10.1371/journal.pcbi.1002529"]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}", f"{DOI_URL}10.1371/journal.pcbi.1002529"]
    CITATION_TEXT = (
        f"{BEDTOOLS_CITATION_TEXT}; Exploring Massive, Genome Scale Datasets with the GenometriCorr Package."
    )
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bedtools",
            "reldist",
            "-a",
            str(inputs.get("inputA", "")),
            "-b",
            str(inputs.get("inputB", "")),
        ]
        if inputs.get("detail"):
            cmd.append("-detail")
        _add_shell_redirect(cmd, f"{_out(inputs)}/relative_distance.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "relative_distance.tsv", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Interval file A"}),
                "inputB": ("BED", {"description": "Interval file B"}),
            },
            "optional": {
                "detail": ("BOOLEAN", {"default": False, "description": "Report relative distance for each A interval"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsSpacingNode(CommandNode):
    """Report distances between adjacent intervals."""

    NODE_ID = "bedtools_spacingbed"
    DISPLAY_NAME = "BEDTools Spacing"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Report the spacing between adjacent intervals in a sorted interval file."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "spacing", "spacingbed", "distance between intervals", "adjacent intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("spacing",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/spacing.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "spacing", "-i", str(inputs.get("input", ""))]
        _add_shell_redirect(cmd, f"{_out(inputs)}/spacing.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "spacing.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "Sorted interval file"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsGroupByNode(CommandNode):
    """Group rows by columns and summarize values in other columns."""

    NODE_ID = "bedtools_groupbybed"
    DISPLAY_NAME = "BEDTools GroupBy"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Group intervals by one or more columns and summarize selected columns with bedtools groupby."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "groupby", "groupbybed", "summarize intervals", "aggregate columns"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("grouped",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/groupby.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bedtools",
            "groupby",
            "-i",
            str(inputs.get("inputA", "")),
            "-g",
            str(inputs.get("group", "1,2,3")),
            "-c",
            str(inputs.get("columns", inputs.get("cols", ""))),
            "-o",
            str(inputs.get("operation", "sum")),
        ]
        _add_shell_redirect(cmd, f"{_out(inputs)}/grouped.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "grouped.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Interval or tabular file to group"}),
                "columns": ("STRING", {"default": "4", "description": "Comma-separated columns to summarize"}),
                "group": ("STRING", {"default": "1,2,3", "description": "Columns or ranges to group by"}),
                "operation": (
                    "STRING",
                    {
                        "default": "sum",
                        "options": [
                            "sum",
                            "min",
                            "max",
                            "absmin",
                            "absmax",
                            "mean",
                            "median",
                            "mode",
                            "antimode",
                            "stdev",
                            "sstdev",
                            "collapse",
                            "count",
                            "distinct",
                            "first",
                            "last",
                            "freqasc",
                            "freqdesc",
                        ],
                    },
                ),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsBamToBedNode(CommandNode):
    """Convert BAM alignments to BED, BED12, or BEDPE records."""

    NODE_ID = "bedtools_bamtobed"
    DISPLAY_NAME = "BEDTools BAM to BED"
    REQUIRED_CONDA_PACKAGES = ["bedtools", "samtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert BAM alignments to BED, BED12, or paired BEDPE records with bedtools bamtobed."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "bamtobed", "bam to bed", "bed12", "bedpe"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("converted_bed",)
    REQUIRED_EXECUTABLES = ["bedtools", "samtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/bamtobed.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        option_aliases = {
            "": "",
            "bed": "",
            "bed6": "",
            "bed12": "-bed12",
            "-bed12": "-bed12",
            "bedpe": "-bedpe",
            "-bedpe": "-bedpe",
        }
        option = option_aliases.get(str(inputs.get("option", "")), str(inputs.get("option", "")))
        out = _out(inputs)
        bedtools_input = str(inputs.get("input", ""))
        cmd: list[str] = []
        if option == "-bedpe":
            bedtools_input = f"{out}/input.bam"
            cmd.extend(
                [
                    "samtools",
                    "sort",
                    "-n",
                    "-@",
                    str(inputs.get("threads", 4)),
                    "-T",
                    f"{out}/tmp",
                    str(inputs.get("input", "")),
                    ">",
                    bedtools_input,
                    "&&",
                ]
            )
        cmd.extend(["bedtools", "bamtobed"])
        if option:
            cmd.append(option)
        if inputs.get("ed_score"):
            cmd.append("-ed")
        if inputs.get("split"):
            cmd.append("-split")
        tag = str(inputs.get("tag", "")).strip()
        if tag:
            cmd.extend(["-tag", tag])
        cmd.extend(["-i", bedtools_input])
        _add_shell_redirect(cmd, f"{out}/converted.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "converted.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM alignment file to convert"}),
                "option": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "bed12", "bedpe"],
                        "description": "Output BED flavor: BED6, blocked BED12, or paired BEDPE",
                    },
                ),
            },
            "optional": {
                "split": ("BOOLEAN", {"default": False, "description": "Split spliced alignments into distinct BED records"}),
                "ed_score": ("BOOLEAN", {"default": False, "description": "Use BAM edit distance as the BED score"}),
                "tag": ("STRING", {"default": "", "description": "Numeric BAM tag to use as the BED score"}),
                "threads": ("INT", {"default": 4, "min": 1, "description": "Threads for BEDPE name sorting"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsBed12ToBed6Node(CommandNode):
    """Expand BED12 blocked features into BED6 intervals."""

    NODE_ID = "bedtools_bed12tobed6"
    DISPLAY_NAME = "BEDTools BED12 to BED6"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert blocked BED12 features into discrete BED6 features with bed12ToBed6."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "bed12tobed6", "bed12 to bed6", "blocked bed", "exons"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("bed6",)
    REQUIRED_EXECUTABLES = ["bed12ToBed6"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/bed12tobed6.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bed12ToBed6", "-i", str(inputs.get("input", ""))]
        _add_shell_redirect(cmd, f"{_out(inputs)}/bed6.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "bed6.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "BED12 file to expand into BED6 blocks"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsBedToBamNode(CommandNode):
    """Convert BED features to BAM alignments."""

    NODE_ID = "bedtools_bedtobam"
    DISPLAY_NAME = "BEDTools BED to BAM"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert BED annotations to BAM format with optional BED12 spliced alignment handling."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "bedtobam", "bed to bam", "bed12", "annotation bam"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("converted_bam",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/bedtobam.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "bedtobam"]
        if inputs.get("bed12"):
            cmd.append("-bed12")
        cmd.extend(["-mapq", str(inputs.get("mapq", 255))])
        _bedtools_add_genome(cmd, inputs)
        cmd.extend(["-i", str(inputs.get("input", ""))])
        _add_shell_redirect(cmd, f"{_out(inputs)}/converted.bam")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "converted.bam", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "BED feature file to convert"}),
                "genome": ("TSV", {"description": "Two-column chromosome sizes genome file"}),
            },
            "optional": {
                "bed12": ("BOOLEAN", {"default": False, "description": "Convert blocked BED12 records into spliced BAM alignments"}),
                "mapq": ("INT", {"default": 255, "min": 0, "max": 255, "description": "Mapping quality value for output alignments"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsBedpeToBamNode(CommandNode):
    """Convert BEDPE paired features to BAM alignments."""

    NODE_ID = "bedtools_bedpetobam"
    DISPLAY_NAME = "BEDTools BEDPE to BAM"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert BEDPE paired feature records to an unsorted BAM file with bedtools bedpetobam."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "bedpetobam", "bedpe to bam", "paired intervals", "paired-end"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("paired_bam",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/bedpetobam.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bedtools",
            "bedpetobam",
            "-mapq",
            str(inputs.get("mapq", 255)),
            "-i",
            str(inputs.get("input", "")),
        ]
        _bedtools_add_genome(cmd, inputs)
        _add_shell_redirect(cmd, f"{_out(inputs)}/paired.bam")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "paired.bam", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "BEDPE or BED-like paired feature file"}),
                "genome": ("TSV", {"description": "Two-column chromosome sizes genome file"}),
            },
            "optional": {
                "mapq": ("INT", {"default": 255, "min": 0, "max": 255, "description": "Mapping quality value for output alignments"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsMakeWindowsNode(CommandNode):
    """Create fixed-size or fixed-count windows over genomes or intervals."""

    NODE_ID = "bedtools_makewindowsbed"
    DISPLAY_NAME = "BEDTools Make Windows"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Create adjacent or sliding windows across a genome file or BED interval file with bedtools makewindows."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "makewindows", "makewindowsbed", "sliding windows", "genome windows"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("windows",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/makewindows.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        source = str(inputs.get("type", inputs.get("type_select", "bed")))
        action = str(inputs.get("action", inputs.get("action_select", "windowsize")))
        cmd = ["bedtools", "makewindows"]
        if source == "genome":
            _bedtools_add_genome(cmd, inputs)
        else:
            cmd.extend(["-b", str(inputs.get("input", ""))])
        if action == "number":
            cmd.extend(["-n", str(inputs.get("number", 1))])
        else:
            cmd.extend(["-w", str(inputs.get("windowsize", 1))])
            _add_if_value(cmd, "-s", inputs.get("step_size"))
        sourcename = str(inputs.get("sourcename", "")).strip()
        if sourcename:
            sourcename = sourcename.replace("-i ", "")
            cmd.extend(["-i", sourcename])
        _add_shell_redirect(cmd, f"{_out(inputs)}/windows.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "windows.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "type": ("STRING", {"default": "bed", "options": ["bed", "genome"], "description": "Create windows over BED intervals or a genome file"}),
                "action": ("STRING", {"default": "windowsize", "options": ["windowsize", "number"], "description": "Window by fixed size or fixed count"}),
            },
            "optional": {
                "input": ("BED", {"description": "BED intervals used when type is bed"}),
                "genome": ("TSV", {"description": "Genome chromosome sizes file used when type is genome"}),
                "windowsize": ("INT", {"default": 1, "min": 1, "description": "Window size in bases"}),
                "step_size": ("INT", {"default": "", "min": 1, "description": "Step size for sliding windows"}),
                "number": ("INT", {"default": 1, "min": 1, "description": "Number of windows per input interval"}),
                "sourcename": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "src", "winnum", "srcwinnum"],
                        "description": "ID naming style for generated windows",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsAnnotateNode(CommandNode):
    """Annotate intervals with coverage from multiple feature files."""

    NODE_ID = "bedtools_annotatebed"
    DISPLAY_NAME = "BEDTools Annotate"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Annotate one interval file with coverage fractions or counts from multiple BED-like files."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "annotate", "annotatebed", "coverage annotation", "multiple feature types"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("annotated",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/annotate.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        files = _as_list(inputs.get("beds", inputs.get("files")))
        names = _as_list(inputs.get("names"))
        cmd = ["bedtools", "annotate", "-i", str(inputs.get("inputA", ""))]
        cmd.extend(["-files", *files])
        if names:
            cmd.extend(["-names", *names])
        strand_flag = _bedtools_strand_flag(inputs.get("strand"))
        if strand_flag:
            cmd.append(strand_flag)
        if inputs.get("counts"):
            cmd.append("-counts")
        if inputs.get("both"):
            cmd.append("-both")
        _add_shell_redirect(cmd, f"{_out(inputs)}/annotated.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "annotated.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Intervals to annotate"}),
                "beds": ("BED_LIST", {"description": "One or more annotation interval files"}),
            },
            "optional": {
                "names": ("STRING_LIST", {"description": "Optional labels matching the annotation files"}),
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "counts": ("BOOLEAN", {"default": False, "description": "Report counts instead of only coverage fractions"}),
                "both": ("BOOLEAN", {"default": False, "description": "Report counts followed by coverage fractions"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsExpandNode(CommandNode):
    """Replicate rows by expanding comma-separated column values."""

    NODE_ID = "bedtools_expandbed"
    DISPLAY_NAME = "BEDTools Expand"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Replicate BED-like records by expanding comma-separated values in selected columns."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "expand", "expandbed", "split columns", "comma-separated values"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("expanded",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/expand.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bedtools",
            "expand",
            "-c",
            str(inputs.get("columns", inputs.get("cols", ""))),
            "-i",
            str(inputs.get("input", "")),
        ]
        _add_shell_redirect(cmd, f"{_out(inputs)}/expanded.{_bedtools_ext(inputs.get('input'))}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, f"expanded.{_bedtools_ext(inputs.get('input'))}", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "BED-like file containing comma-separated values"}),
                "columns": ("STRING", {"default": "4", "description": "Comma-separated columns to expand"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsMaskFastaNode(CommandNode):
    """Mask FASTA sequences over selected intervals."""

    NODE_ID = "bedtools_maskfastabed"
    DISPLAY_NAME = "BEDTools Mask FASTA"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Mask FASTA sequence bases that overlap intervals from a BED-like file."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "maskfasta", "maskfastabed", "soft mask", "masked genome"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("masked_fasta",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/maskfasta.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "maskfasta"]
        if inputs.get("soft"):
            cmd.append("-soft")
        cmd.extend([
            "-mc",
            str(inputs.get("mask_character", inputs.get("mc", "N"))),
            "-fi",
            str(inputs.get("fasta", "")),
            "-bed",
            str(inputs.get("input", "")),
            "-fo",
            f"{_out(inputs)}/masked.fasta",
        ])
        if inputs.get("full_header", inputs.get("fullheader")):
            cmd.append("-fullHeader")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "masked.fasta", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "Intervals used to mask the FASTA"}),
                "fasta": ("FASTA", {"description": "FASTA sequences to mask"}),
            },
            "optional": {
                "soft": ("BOOLEAN", {"default": False, "description": "Soft-mask by converting bases to lowercase"}),
                "mask_character": ("STRING", {"default": "N", "description": "Hard-mask replacement character"}),
                "full_header": ("BOOLEAN", {"default": False, "description": "Match and emit the full FASTA header"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsMultiCovNode(CommandNode):
    """Count alignments from multiple BAM files over intervals."""

    NODE_ID = "bedtools_multicovtbed"
    DISPLAY_NAME = "BEDTools MultiCov"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Count overlapping alignments from multiple sorted and indexed BAM files for each interval."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "multicov", "multicovbed", "bam counts", "interval read counts"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("multicov",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/multicov.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "multicov", "-bed", str(inputs.get("input", "")), "-bams", *_as_list(inputs.get("bams"))]
        strand_flag = _bedtools_strand_flag(inputs.get("strand"))
        if strand_flag:
            cmd.append(strand_flag)
        _add_if_value(cmd, "-f", inputs.get("overlap"))
        if inputs.get("reciprocal"):
            cmd.append("-r")
        if inputs.get("split"):
            cmd.append("-split")
        cmd.extend(["-q", str(inputs.get("q", 0))])
        if inputs.get("duplicate"):
            cmd.append("-D")
        if inputs.get("failed"):
            cmd.append("-F")
        if inputs.get("proper"):
            cmd.append("-p")
        _add_shell_redirect(cmd, f"{_out(inputs)}/multicov.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "multicov.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "Sorted intervals to count over"}),
                "bams": ("BAM_LIST", {"description": "Sorted and indexed BAM files"}),
            },
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction"}),
                "reciprocal": ("BOOLEAN", {"default": False, "description": "Require reciprocal overlap"}),
                "split": ("BOOLEAN", {"default": False, "description": "Treat split or spliced alignments as separate intervals"}),
                "q": ("INT", {"default": 0, "min": 0, "max": 255, "description": "Minimum mapping quality"}),
                "duplicate": ("BOOLEAN", {"default": False, "description": "Include duplicate reads"}),
                "failed": ("BOOLEAN", {"default": False, "description": "Include failed-QC reads"}),
                "proper": ("BOOLEAN", {"default": False, "description": "Only count proper pairs"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsNucNode(CommandNode):
    """Profile nucleotide content for intervals in a FASTA file."""

    NODE_ID = "bedtools_nucbed"
    DISPLAY_NAME = "BEDTools Nucleotide Content"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Compute nucleotide content, optional sequence output, and motif counts for FASTA intervals."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "nuc", "nucbed", "nucleotide content", "gc content"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("nucleotide_content",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/nuc.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "nuc"]
        if inputs.get("strand"):
            cmd.append("-s")
        if inputs.get("seq"):
            cmd.append("-seq")
        pattern = str(inputs.get("pattern", "")).strip()
        if pattern:
            cmd.extend(["-pattern", pattern])
            if inputs.get("ignore_case"):
                cmd.append("-C")
        cmd.extend(["-fi", str(inputs.get("fasta", "")), "-bed", str(inputs.get("input", ""))])
        _add_shell_redirect(cmd, f"{_out(inputs)}/nucleotide_content.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "nucleotide_content.tsv", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BED", {"description": "Intervals whose nucleotide content is profiled"}),
                "fasta": ("FASTA", {"description": "Reference FASTA file"}),
            },
            "optional": {
                "strand": ("BOOLEAN", {"default": False, "description": "Profile sequence according to strand"}),
                "seq": ("BOOLEAN", {"default": False, "description": "Print the extracted sequence"}),
                "pattern": ("STRING", {"default": "", "description": "Sequence pattern to count"}),
                "ignore_case": ("BOOLEAN", {"default": False, "description": "Ignore case when matching pattern"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsRandomNode(CommandNode):
    """Generate random BED intervals across a genome."""

    NODE_ID = "bedtools_randombed"
    DISPLAY_NAME = "BEDTools Random"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Generate a random set of BED6 intervals across chromosomes defined by a genome file."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "random", "randombed", "random intervals", "null intervals"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("random_intervals",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/random.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "random"]
        _bedtools_add_genome(cmd, inputs)
        cmd.extend(["-l", str(inputs.get("length", 100)), "-n", str(inputs.get("intervals", inputs.get("n", 1000000)))])
        _add_if_value(cmd, "-seed", inputs.get("seed"))
        _add_shell_redirect(cmd, f"{_out(inputs)}/random.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "random.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genome": ("TSV", {"description": "Genome chromosome sizes file"}),
            },
            "optional": {
                "length": ("INT", {"default": 100, "min": 1, "description": "Length of each random interval"}),
                "intervals": ("INT", {"default": 1000000, "min": 1, "description": "Number of intervals to generate"}),
                "seed": ("INT", {"default": "", "description": "Optional random seed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsShuffleNode(CommandNode):
    """Randomly redistribute interval locations across a genome."""

    NODE_ID = "bedtools_shufflebed"
    DISPLAY_NAME = "BEDTools Shuffle"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Shuffle feature locations across a genome, optionally constraining or excluding target regions."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "shuffle", "shufflebed", "randomize intervals", "permutation"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("shuffled",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/shuffle.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "shuffle"]
        _bedtools_add_genome(cmd, inputs)
        cmd.extend(["-i", str(inputs.get("inputA", inputs.get("input", "")))])
        if inputs.get("bedpe"):
            cmd.append("-bedpe")
        _add_if_value(cmd, "-seed", inputs.get("seed"))
        if inputs.get("exclude"):
            cmd.extend(["-excl", str(inputs.get("exclude"))])
            _add_if_value(cmd, "-f", inputs.get("overlap"))
        if inputs.get("include"):
            cmd.extend(["-incl", str(inputs.get("include"))])
        if inputs.get("chrom"):
            cmd.append("-chrom")
        if inputs.get("chromfirst"):
            cmd.append("-chromFirst")
        if inputs.get("no_overlap"):
            cmd.append("-noOverlapping")
        if inputs.get("allow_beyond"):
            cmd.append("-allowBeyondChromEnd")
        cmd.extend(["-maxTries", str(inputs.get("maxtries", inputs.get("max_tries", 1000)))])
        _add_shell_redirect(cmd, f"{_out(inputs)}/shuffled.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "shuffled.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Intervals to randomly redistribute"}),
                "genome": ("TSV", {"description": "Genome chromosome sizes file"}),
            },
            "optional": {
                "bedpe": ("BOOLEAN", {"default": False, "description": "Input is BEDPE format"}),
                "seed": ("INT", {"default": "", "description": "Optional random seed"}),
                "exclude": ("BED", {"description": "Regions where shuffled intervals must not be placed"}),
                "include": ("BED", {"description": "Regions where shuffled intervals must be placed"}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Maximum tolerated overlap with excluded regions"}),
                "chrom": ("BOOLEAN", {"default": False, "description": "Keep intervals on their original chromosome"}),
                "chromfirst": ("BOOLEAN", {"default": False, "description": "Choose chromosome uniformly before choosing position"}),
                "no_overlap": ("BOOLEAN", {"default": False, "description": "Do not allow shuffled intervals to overlap each other"}),
                "allow_beyond": ("BOOLEAN", {"default": False, "description": "Allow intervals to extend beyond chromosome end"}),
                "maxtries": ("INT", {"default": 1000, "min": 1, "description": "Maximum placement attempts per interval"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsUnionBedGraphNode(CommandNode):
    """Combine intervals from multiple BedGraph files."""

    NODE_ID = "bedtools_unionbedgraph"
    DISPLAY_NAME = "BEDTools Union BedGraph"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Merge multiple sorted BedGraph files into a common set of intervals with one value column per input."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "unionbedg", "unionbedgraph", "bedgraph union", "coverage tracks"]
    RETURN_TYPES = ("BEDGRAPH",)
    RETURN_NAMES = ("union_bedgraph",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/unionbedg.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        files = _as_list(inputs.get("inputs", inputs.get("bedgraphs")))
        names = _as_list(inputs.get("names"))
        cmd = ["bedtools", "unionbedg"]
        if inputs.get("header"):
            cmd.append("-header")
        cmd.extend(["-filler", str(inputs.get("filler", "N/A"))])
        if inputs.get("empty"):
            cmd.append("-empty")
            _bedtools_add_genome(cmd, inputs)
        cmd.extend(["-i", *files])
        if names:
            cmd.extend(["-names", *names])
        _add_shell_redirect(cmd, f"{_out(inputs)}/union.bedgraph")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "union.bedgraph", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputs": ("BEDGRAPH_LIST", {"description": "Sorted non-overlapping BedGraph files"}),
            },
            "optional": {
                "names": ("STRING_LIST", {"description": "Optional column labels matching the input files"}),
                "header": ("BOOLEAN", {"default": False, "description": "Print a header row"}),
                "filler": ("STRING", {"default": "N/A", "description": "Value for no coverage in a file"}),
                "empty": ("BOOLEAN", {"default": False, "description": "Report regions with zero coverage across all files"}),
                "genome": ("TSV", {"description": "Genome chromosome sizes file required when empty is enabled"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsClosestBedNode(CommandNode):
    """Find closest features, optionally reporting signed distances."""

    NODE_ID = "bedtools_closestbed"
    DISPLAY_NAME = "BEDTools ClosestBed"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Find closest or overlapping features in one or more B interval files for every interval in A."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "closest", "closestbed", "nearest interval", "nearest feature"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("closest",)
    REQUIRED_EXECUTABLES = ["closestBed"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/closest.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["closestBed"]
        strand_flag = _bedtools_strand_flag(inputs.get("strand"))
        if strand_flag:
            cmd.append(strand_flag)
        if inputs.get("distance"):
            cmd.append("-d")
        distance_mode = str(inputs.get("distance_mode", inputs.get("addition2_select", ""))).strip()
        if distance_mode:
            cmd.extend(["-D", distance_mode])
            if inputs.get("ignore_upstream"):
                cmd.append("-iu")
            if inputs.get("ignore_downstream"):
                cmd.append("-id")
            if inputs.get("first_upstream"):
                cmd.append("-fu")
            if inputs.get("first_downstream"):
                cmd.append("-fd")
        if inputs.get("ignore_overlaps", inputs.get("io")):
            cmd.append("-io")
        cmd.extend(["-mdb", str(inputs.get("mdb", "each")), "-t", str(inputs.get("ties", "all"))])
        _add_if_value(cmd, "-k", inputs.get("k"))
        cmd.extend(["-a", str(inputs.get("inputA", "")), "-b", *_as_list(inputs.get("inputB"))])
        _add_shell_redirect(cmd, f"{_out(inputs)}/closest.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "closest.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BED", {"description": "Query intervals"}),
                "inputB": ("BED_LIST", {"description": "One or more databases of intervals to search"}),
            },
            "optional": {
                "ties": ("STRING", {"default": "all", "options": ["all", "first", "last"], "description": "How equally close B records are handled"}),
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "distance": ("BOOLEAN", {"default": False, "description": "Report distance as an extra column"}),
                "distance_mode": ("STRING", {"default": "", "options": ["", "ref", "a", "b"], "description": "Report signed upstream/downstream distances"}),
                "ignore_upstream": ("BOOLEAN", {"default": False, "description": "Ignore upstream features when using -D"}),
                "ignore_downstream": ("BOOLEAN", {"default": False, "description": "Ignore downstream features when using -D"}),
                "first_upstream": ("BOOLEAN", {"default": False, "description": "Choose first upstream feature when using -D"}),
                "first_downstream": ("BOOLEAN", {"default": False, "description": "Choose first downstream feature when using -D"}),
                "ignore_overlaps": ("BOOLEAN", {"default": False, "description": "Ignore B features that overlap A"}),
                "mdb": ("STRING", {"default": "each", "options": ["each", "all"], "description": "Resolve closest hits per B file or across all B files"}),
                "k": ("INT", {"default": "", "min": 1, "description": "Report the k closest hits"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsIntersectBedNode(CommandNode):
    """Find interval intersections with Galaxy wrapper-compatible options."""

    NODE_ID = "bedtools_intersectbed"
    DISPLAY_NAME = "BEDTools Intersect Intervals"
    REQUIRED_CONDA_PACKAGES = ["bedtools", "samtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Find overlaps between A and one or more B BED-like or BAM files with configurable reporting modes."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "intersect", "intersectbed", "overlap intervals", "feature intersection"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("intersect",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/intersect.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "intersect", "-a", str(inputs.get("inputA", "")), "-b", *_as_list(inputs.get("inputB"))]
        names = _as_list(inputs.get("names"))
        if names:
            cmd.extend(["-names", *names])
        if inputs.get("split"):
            cmd.append("-split")
        strand_flag = _bedtools_strand_flag(inputs.get("strand"))
        if strand_flag:
            cmd.append(strand_flag)
        _add_if_value(cmd, "-f", inputs.get("overlap"))
        if inputs.get("reciprocal"):
            cmd.append("-r")
        else:
            _add_if_value(cmd, "-F", inputs.get("overlap_b", inputs.get("overlapB")))
            if inputs.get("either_fraction", inputs.get("disjoint")):
                cmd.append("-e")
        if inputs.get("invert"):
            cmd.append("-v")
        if inputs.get("once"):
            cmd.append("-u")
        if inputs.get("header"):
            cmd.append("-header")
        for mode in _as_list(inputs.get("overlap_mode")):
            if mode and mode != "None":
                cmd.append(mode)
        if inputs.get("sorted"):
            cmd.append("-sorted")
            _bedtools_add_genome(cmd, inputs)
        if inputs.get("bed"):
            cmd.append("-bed")
        if inputs.get("count"):
            cmd.append("-c")
        _add_shell_redirect(cmd, f"{_out(inputs)}/intersect.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "intersect.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("FILE", {"description": "A file: BED-like, BAM, VCF, or GFF"}),
                "inputB": ("FILE_LIST", {"description": "One or more B files to intersect with A"}),
            },
            "optional": {
                "names": ("STRING_LIST", {"description": "Optional labels for B files"}),
                "overlap_mode": ("STRING_LIST", {"description": "Reporting flags such as -wa, -wb, -wo, -wao, or -loj"}),
                "split": ("BOOLEAN", {"default": False, "description": "Treat split BED12/BAM alignments as distinct intervals"}),
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of A"}),
                "overlap_b": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of B"}),
                "reciprocal": ("BOOLEAN", {"default": False, "description": "Require reciprocal overlap"}),
                "either_fraction": ("BOOLEAN", {"default": False, "description": "Allow either A or B overlap fraction to be satisfied"}),
                "invert": ("BOOLEAN", {"default": False, "description": "Report A records with no overlaps"}),
                "once": ("BOOLEAN", {"default": False, "description": "Report each A record once if any overlap exists"}),
                "count": ("BOOLEAN", {"default": False, "description": "Report overlap count for each A record"}),
                "bed": ("BOOLEAN", {"default": False, "description": "When A is BAM, write BED output"}),
                "sorted": ("BOOLEAN", {"default": False, "description": "Use sorted input algorithm"}),
                "genome": ("TSV", {"description": "Genome chromosome sizes file for sorted mode"}),
                "header": ("BOOLEAN", {"default": False, "description": "Print the A file header before results"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsBedToIgvNode(CommandNode):
    """Create IGV batch scripts for interval snapshots."""

    NODE_ID = "bedtools_bedtoigv"
    DISPLAY_NAME = "BEDTools BED to IGV"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Create an IGV batch script that takes snapshots at intervals from a BED-like file."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "bedtoigv", "bedToIgv", "IGV snapshots", "batch script"]
    RETURN_TYPES = ("TEXT",)
    RETURN_NAMES = ("igv_batch_script",)
    REQUIRED_EXECUTABLES = ["bedToIgv"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/blob/main/tools/bedtools/bedToIgv.xml"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedToIgv", "-i", str(inputs.get("input", ""))]
        _add_if_value(cmd, "-sort", inputs.get("sort"))
        if inputs.get("clps"):
            cmd.append("-clps")
        if inputs.get("name"):
            cmd.append("-name")
        cmd.extend(["-slop", str(inputs.get("slop", 0)), "-img", str(inputs.get("img", "png"))])
        _add_shell_redirect(cmd, f"{_out(inputs)}/igv_batch_script.txt")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "igv_batch_script.txt", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "BED-like interval file to convert into IGV snapshot commands"}),
            },
            "optional": {
                "sort": ("STRING", {"default": "", "options": ["", "base", "position", "strand", "quality", "sample", "readGroup"], "description": "BAM sorting mode to apply before snapshots"}),
                "clps": ("BOOLEAN", {"default": False, "description": "Collapse aligned reads before each snapshot"}),
                "name": ("BOOLEAN", {"default": False, "description": "Use column 4 interval names as image filenames"}),
                "slop": ("INT", {"default": 0, "min": 0, "description": "Flanking base pairs on each side of each interval"}),
                "img": ("STRING", {"default": "png", "options": ["png", "eps", "svg"], "description": "Snapshot image format"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsLinksNode(CommandNode):
    """Create UCSC Genome Browser links for each interval."""

    NODE_ID = "bedtools_links"
    DISPLAY_NAME = "BEDTools LinksBed"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Create an HTML page with UCSC Genome Browser links for intervals in a BED-like file."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "links", "linksbed", "linksbed ucsc", "UCSC links", "genome browser"]
    RETURN_TYPES = ("HTML",)
    RETURN_NAMES = ("links_html",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/links.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bedtools",
            "links",
            "-base",
            str(inputs.get("basename", "http://genome.ucsc.edu")),
            "-org",
            str(inputs.get("org", "human")),
            "-db",
            str(inputs.get("db", "hg19")),
            "-i",
            str(inputs.get("input", "")),
        ]
        _add_shell_redirect(cmd, f"{_out(inputs)}/links.html")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "links.html", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "BED-like interval file to link into a genome browser"}),
            },
            "optional": {
                "basename": ("STRING", {"default": "http://genome.ucsc.edu", "description": "Base URL for the UCSC Genome Browser instance"}),
                "org": ("STRING", {"default": "human", "description": "UCSC organism name"}),
                "db": ("STRING", {"default": "hg19", "description": "UCSC genome build"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsOverlapBedNode(CommandNode):
    """Compute overlap or distance between coordinate pairs on each row."""

    NODE_ID = "bedtools_overlapbed"
    DISPLAY_NAME = "BEDTools OverlapBed"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Compute the amount of overlap or distance between two feature coordinate ranges on each input row."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "overlap", "overlapbed", "overlapbed custom score", "overlap distance", "custom overlap score"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("overlap",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/overlap.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cols = inputs.get("cols", "")
        if isinstance(cols, (list, tuple)):
            cols = ",".join(str(col) for col in cols)
        cmd = ["bedtools", "overlap", "-i", str(inputs.get("input", "")), "-cols", str(cols)]
        _add_shell_redirect(cmd, f"{_out(inputs)}/overlap.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "overlap.bed", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "Input rows containing two coordinate ranges"}),
                "cols": ("STRING", {"default": "", "description": "Comma-separated 1-based columns: start1,end1,start2,end2"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDToolsTagBedNode(CommandNode):
    """Tag BAM alignments using overlapping interval annotations."""

    NODE_ID = "bedtools_tagbed"
    DISPLAY_NAME = "BEDTools TagBed"
    REQUIRED_CONDA_PACKAGES = ["bedtools"]
    CATEGORY = "genomics"
    DESCRIPTION = "Annotate BAM alignments with tags populated from one or more overlapping interval files."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedtools", "tag", "tagbed", "tagbed bam tags", "BAM tags", "alignment annotation"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("tagged_bam",)
    REQUIRED_EXECUTABLES = ["bedtools"]
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/tag.html"
    CITATION_DOIS = [BEDTOOLS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDTOOLS_CITATION_DOI}"]
    CITATION_TEXT = BEDTOOLS_CITATION_TEXT
    VERSION = "2.31.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["bedtools", "tag", "-i", str(inputs.get("inputA", "")), "-files", *_as_list(inputs.get("inputB"))]
        _add_if_value(cmd, "-f", inputs.get("overlap"))
        strand_flag = _bedtools_strand_flag(inputs.get("strand"))
        if strand_flag:
            cmd.append(strand_flag)
        cmd.extend(["-tag", str(inputs.get("tag", "YB"))])
        for field_flag in str(inputs.get("field", "-labels")).split():
            if field_flag:
                cmd.append(field_flag)
        _add_shell_redirect(cmd, f"{_out(inputs)}/tagged.bam")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "tagged.bam", output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("BAM", {"description": "BAM alignments to annotate"}),
                "inputB": ("FILE_LIST", {"description": "BED-like annotation files used to populate tags"}),
            },
            "optional": {
                "strand": ("STRING", {"default": "", "options": ["", "same", "opposite"]}),
                "overlap": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum overlap fraction of each alignment"}),
                "tag": ("STRING", {"default": "YB", "description": "BAM tag name to populate"}),
                "field": ("STRING", {"default": "-labels", "options": ["-labels", "-scores", "-names", "-labels -intervals"], "description": "Annotation field used as tag value"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDOPSSortBedNode(CommandNode):
    """Sort BED records into BEDOPS canonical order."""

    NODE_ID = "bedops_sort_bed"
    DISPLAY_NAME = "BEDOPS Sort BED"
    REQUIRED_CONDA_PACKAGES = ["bedops"]
    CATEGORY = "genomics"
    DESCRIPTION = "Sort one or more BED files into BEDOPS canonical order, optionally emitting only unique or duplicate records."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bedops", "sort-bed", "BEDOPS sort-bed", "sort BED", "unique BED", "duplicate BED"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("sorted_bed",)
    REQUIRED_EXECUTABLES = ["sort-bed"]
    DOCUMENTATION_URL = "https://bedops.readthedocs.io/en/latest/content/reference/file-management/sorting/sort-bed.html"
    CITATION_DOIS = [BEDOPS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEDOPS_CITATION_DOI}"]
    CITATION_TEXT = BEDOPS_CITATION_TEXT
    VERSION = "2.4.42"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "sort-bed",
            "--max-mem",
            f"{int(inputs.get('memory_mb', 1024) or 1024)}M",
            "--tmpdir",
            str(inputs.get("tmpdir") or "."),
        ]
        if inputs.get("unique"):
            cmd.append("--unique")
        if inputs.get("duplicates"):
            cmd.append("--duplicates")
        cmd.extend(_as_list(inputs.get("inputs")))
        _add_shell_redirect(cmd, f"{_out(inputs)}/sorted.bed")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [_bedtools_common_output(cls.NODE_ID, "sorted.bed", output_dir)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not _as_list(inputs.get("inputs")):
            return "at least one BED input is required"
        if inputs.get("unique") and inputs.get("duplicates"):
            return "unique and duplicates modes are mutually exclusive"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputs": ("BED_LIST", {"description": "One or more BED files to sort"}),
            },
            "optional": {
                "unique": ("BOOLEAN", {"default": False, "description": "Output only unique BED elements"}),
                "duplicates": ("BOOLEAN", {"default": False, "description": "Output only duplicate BED elements"}),
                "memory_mb": ("INT", {"default": 1024, "min": 1, "description": "Maximum memory for sort-bed in MB"}),
                "tmpdir": (
                    "DIRECTORY",
                    {"description": "Temporary directory for sorting files larger than memory", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BEDOPSSortBedGalaxyNode(BEDOPSSortBedNode):
    """Galaxy wrapper-ID compatible alias for BEDOPS sort-bed."""

    NODE_ID = "bedops-sort-bed"
    DISPLAY_NAME = "BEDOPS sort-bed"
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "bedops-sort-bed",
        "bedops",
        "sort-bed",
        "BEDOPS sort-bed",
        "sort BED",
        "unique BED",
        "duplicate BED",
    ]
