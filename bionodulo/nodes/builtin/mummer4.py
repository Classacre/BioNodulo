"""Galaxy parity MUMmer4 nodes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


MUMMER4_DOI = "10.1371/journal.pcbi.1005944"
MUMMER4_CITATION_TEXT = "MUMmer4: A fast and versatile genome alignment system."
MUMMER4_DOCS = "https://mummer4.github.io/manual/manual.html"


def _out(inputs: dict[str, Any]) -> str:
    return str(inputs.get("output", inputs.get("output_dir", ".")))


def _bool(inputs: dict[str, Any], key: str) -> bool:
    return bool(inputs.get(key))


def _add_value(cmd: list[str], flag: str, value: Any) -> None:
    if value is not None and str(value) != "":
        cmd.extend([flag, str(value)])


def _add_select(cmd: list[str], value: Any) -> None:
    if value is not None and str(value) != "":
        cmd.append(str(value))


def _add_bool(cmd: list[str], enabled: Any, flag: str) -> None:
    if enabled:
        cmd.append(flag)


def _link_inputs(cmd: list[str], reference: Any, query: Any) -> None:
    cmd.extend([
        "ln",
        "-s",
        str(reference),
        "reference.fa",
        "&&",
        "ln",
        "-s",
        str(query),
        "query.fa",
        "&&",
    ])


def _add_plot_args(cmd: list[str], inputs: dict[str, Any], *, prefix: str = "", include_sequences: bool = False) -> None:
    breaklen = inputs.get(f"{prefix}breaklen", inputs.get("plot_breaklen", 20))
    _add_value(cmd, "-b", breaklen)
    _add_select(cmd, inputs.get(f"{prefix}color", inputs.get("plot_color", "")))
    _add_select(cmd, inputs.get(f"{prefix}coverage", inputs.get("coverage_plot", "")))
    _add_bool(cmd, inputs.get(f"{prefix}filter", inputs.get("filter_plot", False)), "--filter")
    _add_bool(cmd, inputs.get(f"{prefix}fat", inputs.get("fat", False)), "--fat")
    if inputs.get(f"{prefix}plot_ids", inputs.get("plot_ids", False)):
        _add_value(cmd, "-IdR", inputs.get(f"{prefix}ref_id", inputs.get("ref_id", "")))
        _add_value(cmd, "-IdQ", inputs.get(f"{prefix}query_id", inputs.get("query_id", "")))
    if include_sequences and inputs.get(f"{prefix}seq_input", inputs.get("seq_input", False)):
        _add_value(cmd, "-R", inputs.get("reference_sequence", ""))
        _add_value(cmd, "-Q", inputs.get("query_sequence", ""))
        _add_bool(cmd, inputs.get(f"{prefix}layout", inputs.get("layout", False)), "--layout")
    _add_value(cmd, "-s", inputs.get(f"{prefix}size", inputs.get("plot_size", "small")))
    cmd.extend(["-terminal", "png"])
    _add_value(cmd, "-title", inputs.get(f"{prefix}title", inputs.get("title", "Title")))
    _add_bool(cmd, inputs.get(f"{prefix}snp", inputs.get("snp", False)), "--SNP")
    if inputs.get(f"{prefix}custom_range", inputs.get("custom_range", False)):
        cmd.extend([
            "-x",
            f"[{inputs.get(f'{prefix}min_x', inputs.get('min_x', 0))}:{inputs.get(f'{prefix}max_x', inputs.get('max_x', 100))}]",
            "-y",
            f"[{inputs.get(f'{prefix}min_y', inputs.get('min_y', 0))}:{inputs.get(f'{prefix}max_y', inputs.get('max_y', 100))}]",
        ])


class _Mummer4BaseNode(CommandNode):
    CATEGORY = "genomics"
    REQUIRED_CONDA_PACKAGES = ["mummer4"]
    DOCUMENTATION_URL = MUMMER4_DOCS
    CITATION_DOIS = [MUMMER4_DOI]
    CITATION_URLS = [f"https://doi.org/{MUMMER4_DOI}"]
    CITATION_TEXT = MUMMER4_CITATION_TEXT
    VERSION = "4.0.1"
    SHELL = True


class Mummer4NucmerNode(_Mummer4BaseNode):
    """Align nucleotide sequences with MUMmer4 nucmer."""

    NODE_ID = "mummer4_nucmer"
    DISPLAY_NAME = "MUMmer4 Nucmer"
    DESCRIPTION = "Align two nucleotide FASTA files with nucmer and optionally generate delta, BAM/CRAM, and dotplot outputs."
    SEARCH_ALIASES = ["Galaxy", "MUMmer4", "nucmer", "genome alignment", "delta alignment", "dotplot"]
    RETURN_TYPES = ("FILE", "BAM", "CRAM", "IMAGE")
    RETURN_NAMES = ("delta", "bam_alignment", "cram_alignment", "plot")
    REQUIRED_EXECUTABLES = ["nucmer", "mummerplot", "gnuplot", "samtools"]
    REQUIRED_CONDA_PACKAGES = ["mummer4", "gnuplot", "samtools"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        out_format = str(inputs.get("out_format", "delta"))
        threads = str(inputs.get("threads", 1))
        cmd: list[str] = []
        _link_inputs(cmd, inputs.get("reference_sequence", ""), inputs.get("query_sequence", ""))
        cmd.append("nucmer")
        _add_select(cmd, inputs.get("anchoring", ""))
        if out_format != "delta":
            cmd.append("--sam-long=outsam.sam")
        cmd.extend([
            "-b",
            str(inputs.get("breaklen", 200)),
            "-c",
            str(inputs.get("mincluster", 65)),
            "-D",
            str(inputs.get("diagdiff", 5)),
            "-d",
            str(inputs.get("diagfactor", 0.12)),
        ])
        _add_bool(cmd, inputs.get("noextend"), "--noextend")
        _add_select(cmd, inputs.get("direction", ""))
        cmd.extend([
            "-g",
            str(inputs.get("maxgap", 90)),
            "-l",
            str(inputs.get("minmatch", 20)),
            "-L",
            str(inputs.get("minalign", 0)),
        ])
        _add_bool(cmd, inputs.get("nooptimize"), "--nooptimize")
        _add_bool(cmd, inputs.get("nosimplify"), "--nosimplify")
        cmd.extend(["--threads", threads])
        _add_bool(cmd, inputs.get("banded"), "--banded")
        _add_bool(cmd, inputs.get("large"), "--large")
        _add_bool(cmd, inputs.get("genome"), "-G")
        if inputs.get("max_chunk"):
            _add_value(cmd, "-M", inputs.get("max_chunk"))
        cmd.extend(["reference.fa", "query.fa"])
        if out_format == "delta":
            cmd.extend(["&&", "mv", "out.delta", f"{out}/out.delta"])
            if inputs.get("plot"):
                cmd.extend(["&&", "mummerplot"])
                _add_plot_args(cmd, inputs, prefix="plot_")
                cmd.extend([f"{out}/out.delta", "&&", "gnuplot", "<", "out.gp", "&&", "mv", "out.png", f"{out}/out.png"])
            return cmd
        cmd.extend([
            "&&",
            "samtools",
            "dict",
            "reference.fa",
            ">",
            "outsamhead",
            "&&",
            "tail",
            "-n",
            "+3",
            "outsam.sam",
            ">>",
            "outsamhead",
            "&&",
            "samtools",
            "sort",
            "-@",
            threads,
            "-T",
            "${TMPDIR:-.}",
            "outsamhead",
            "|",
        ])
        if out_format == "cram-long":
            cmd.extend(["samtools", "view", "-C", "--reference", "reference.fa", "-o", f"{out}/outsam.cram", "-"])
        else:
            cmd.extend(["samtools", "calmd", "-b", "--threads", threads, "-", "reference.fa", ">", f"{out}/outsam.bam"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        out_format = str(inputs.get("out_format", "delta"))
        if out_format == "bam-long":
            return [out / "outsam.bam"]
        if out_format == "cram-long":
            return [out / "outsam.cram"]
        paths = [out / "out.delta"]
        if inputs.get("plot"):
            paths.append(out / "out.png")
        return paths

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference_sequence": ("FASTA", {"description": "Reference FASTA"}),
                "query_sequence": ("FASTA", {"description": "Query FASTA"}),
                "out_format": ("STRING", {"default": "delta", "options": ["delta", "bam-long", "cram-long"]}),
            },
            "optional": {
                "plot": ("BOOLEAN", {"default": False, "description": "Generate a MUMmer dotplot for delta output"}),
                "anchoring": ("STRING", {"default": "", "options": ["", "--mum", "--maxmatch"]}),
                "breaklen": ("INT", {"default": 200, "min": 0}),
                "mincluster": ("INT", {"default": 65, "min": 1}),
                "diagdiff": ("INT", {"default": 5, "min": 0}),
                "diagfactor": ("FLOAT", {"default": 0.12, "min": 0}),
                "noextend": ("BOOLEAN", {"default": False}),
                "direction": ("STRING", {"default": "", "options": ["", "-f", "-r"]}),
                "maxgap": ("INT", {"default": 90, "min": 0}),
                "minmatch": ("INT", {"default": 20, "min": 1}),
                "minalign": ("INT", {"default": 0, "min": 0}),
                "nooptimize": ("BOOLEAN", {"default": False, "advanced": True}),
                "nosimplify": ("BOOLEAN", {"default": False, "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128}),
                "banded": ("BOOLEAN", {"default": False, "advanced": True}),
                "large": ("BOOLEAN", {"default": False, "advanced": True}),
                "genome": ("BOOLEAN", {"default": False, "advanced": True}),
                "max_chunk": ("INT", {"default": "", "advanced": True}),
                **_plot_input_types("plot_"),
            },
            "hidden": {"output": ("STRING", {})},
        }


class Mummer4DnadiffNode(_Mummer4BaseNode):
    """Evaluate sequence differences with MUMmer4 dnadiff."""

    NODE_ID = "mummer4_dnadiff"
    DISPLAY_NAME = "MUMmer4 DNAdiff"
    DESCRIPTION = "Compare two FASTA sequences with dnadiff and return the report plus optional delta, coordinates, SNP, and difference tables."
    SEARCH_ALIASES = ["Galaxy", "MUMmer4", "dnadiff", "genome difference", "assembly comparison"]
    RETURN_TYPES = ("STATS_FILE", "DIRECTORY")
    RETURN_NAMES = ("report", "all_outputs")
    REQUIRED_EXECUTABLES = ["dnadiff"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd: list[str] = []
        _link_inputs(cmd, inputs.get("reference_sequence", ""), inputs.get("query_sequence", ""))
        cmd.extend(["dnadiff", "-p", f"{out}/out", "reference.fa", "query.fa"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        paths = [out / "out.report"]
        if str(inputs.get("report_only", "yes")) == "no":
            paths.extend([
                out / "out.delta",
                out / "out.1delta",
                out / "out.mdelta",
                out / "out.1coords",
                out / "out.mcoords",
                out / "out.snps",
                out / "out.rdiff",
                out / "out.qdiff",
            ])
        return paths

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference_sequence": ("FASTA", {"description": "Reference FASTA"}),
                "query_sequence": ("FASTA", {"description": "Query FASTA"}),
            },
            "optional": {
                "report_only": ("STRING", {"default": "yes", "options": ["yes", "no"], "description": "Return only the general report or all dnadiff files"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class Mummer4DeltaFilterNode(_Mummer4BaseNode):
    """Filter nucmer delta alignments."""

    NODE_ID = "mummer4_delta_filter"
    DISPLAY_NAME = "MUMmer4 Delta Filter"
    DESCRIPTION = "Filter nucmer delta alignments by alignment strategy, identity, length, uniqueness, and overlap."
    SEARCH_ALIASES = ["Galaxy", "MUMmer4", "delta-filter", "filter delta", "alignment filter"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("filtered_delta",)
    REQUIRED_EXECUTABLES = ["delta-filter"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ["delta-filter"]
        _add_select(cmd, inputs.get("alignment", "-m"))
        cmd.extend([
            "-i",
            str(inputs.get("min_identity", 0)),
            "-l",
            str(inputs.get("min_length", 0)),
        ])
        _add_select(cmd, inputs.get("overlap", "-q"))
        cmd.extend([
            "-u",
            str(inputs.get("min_uniqueness", 0)),
            "-o",
            str(inputs.get("max_overlap", 100)),
            str(inputs.get("delta", "")),
            ">",
            f"{out}/delta-filter.txt",
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "delta-filter.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"delta": ("FILE", {"description": "Nucmer delta file"})},
            "optional": {
                "alignment": ("STRING", {"default": "-m", "options": ["-m", "-1", "-g"]}),
                "min_identity": ("FLOAT", {"default": 0, "min": 0, "max": 100}),
                "min_length": ("INT", {"default": 0, "min": 0}),
                "overlap": ("STRING", {"default": "-q", "options": ["-q", "-r"]}),
                "min_uniqueness": ("FLOAT", {"default": 0, "min": 0, "max": 100}),
                "max_overlap": ("FLOAT", {"default": 100, "min": 0, "max": 100}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class Mummer4ShowCoordsNode(_Mummer4BaseNode):
    """Render MUMmer delta coordinates as tabular output."""

    NODE_ID = "mummer4_show_coords"
    DISPLAY_NAME = "MUMmer4 Show Coordinates"
    DESCRIPTION = "Parse nucmer delta alignments with show-coords into tabular alignment coordinate summaries."
    SEARCH_ALIASES = ["Galaxy", "MUMmer4", "show-coords", "alignment coordinates", "delta coordinates"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("coordinates",)
    REQUIRED_EXECUTABLES = ["show-coords"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        direction = _bool(inputs, "direction")
        output_name = "show-coords_extend.tsv" if direction else "show-coords.tsv"
        cmd = ["show-coords"]
        _add_bool(cmd, inputs.get("merge"), "-b")
        _add_bool(cmd, direction, "-d")
        cmd.extend([
            "-c",
            "-H",
            "-I",
            str(inputs.get("identity", 75.0)),
            "-l",
            "-L",
            str(inputs.get("min_alignment_length", 100)),
        ])
        _add_bool(cmd, inputs.get("annotate"), "-o")
        _add_select(cmd, inputs.get("sort", "-q"))
        cmd.extend(["-T", str(inputs.get("delta", "")), ">", f"{out}/{output_name}"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        name = "show-coords_extend.tsv" if inputs.get("direction") else "show-coords.tsv"
        return [out / name]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"delta": ("FILE", {"description": "Nucmer delta file"})},
            "optional": {
                "merge": ("BOOLEAN", {"default": False}),
                "identity": ("FLOAT", {"default": 75.0, "min": 0, "max": 100}),
                "direction": ("BOOLEAN", {"default": False}),
                "min_alignment_length": ("INT", {"default": 100, "min": 0}),
                "annotate": ("BOOLEAN", {"default": False}),
                "sort": ("STRING", {"default": "-q", "options": ["-q", "-r"]}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class Mummer4MummerNode(_Mummer4BaseNode):
    """Find maximal exact matches with MUMmer."""

    NODE_ID = "mummer4_mummer"
    DISPLAY_NAME = "MUMmer4 Mummer"
    DESCRIPTION = "Find maximal matches between FASTA sequences with mummer and optionally generate a 2-D dotplot."
    SEARCH_ALIASES = ["Galaxy", "MUMmer4", "mummer", "maximal matches", "suffix tree", "dotplot"]
    RETURN_TYPES = ("TSV", "IMAGE")
    RETURN_NAMES = ("alignment", "plot")
    REQUIRED_EXECUTABLES = ["mummer", "mummerplot", "gnuplot"]
    REQUIRED_CONDA_PACKAGES = ["mummer4", "gnuplot"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        threads = str(inputs.get("threads", 1))
        cmd = ["mummer"]
        _add_select(cmd, inputs.get("anchoring", ""))
        cmd.extend(["-l", str(inputs.get("min", 20))])
        _add_select(cmd, inputs.get("direction", "-b"))
        _add_bool(cmd, inputs.get("force"), "-F")
        _add_bool(cmd, inputs.get("chars"), "-n")
        _add_bool(cmd, inputs.get("print_length"), "-L")
        _add_bool(cmd, inputs.get("substring"), "-s")
        _add_bool(cmd, inputs.get("position"), "-c")
        cmd.extend(["-threads", threads, "-qthreads", threads])
        if inputs.get("advanced"):
            cmd.extend([
                "-k",
                str(inputs.get("suffix", 1)),
                "-suflink",
                str(inputs.get("suflink", 0)),
                "-child",
                str(inputs.get("child", 0)),
                "-skip",
                str(inputs.get("skip", 10)),
                "-kmer",
                str(inputs.get("kmer", 1)),
            ])
        cmd.extend([str(inputs.get("reference_sequence", "")), str(inputs.get("query_sequence", "")), ">", f"{out}/mummer.tsv"])
        if inputs.get("plot"):
            cmd.extend(["&&", "mummerplot"])
            _add_plot_args(cmd, inputs, prefix="plot_")
            cmd.extend([f"{out}/mummer.tsv", "&&", "gnuplot", "<", "out.gp", "&&", "mv", "out.png", f"{out}/out.png"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        paths = [out / "mummer.tsv"]
        if inputs.get("plot"):
            paths.append(out / "out.png")
        return paths

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference_sequence": ("FASTA", {"description": "Reference FASTA"}),
                "query_sequence": ("FASTA", {"description": "Query FASTA"}),
            },
            "optional": {
                "anchoring": ("STRING", {"default": "", "options": ["", "-mum", "-maxmatch"]}),
                "min": ("INT", {"default": 20, "min": 1}),
                "direction": ("STRING", {"default": "-b", "options": ["-b", "-r"]}),
                "force": ("BOOLEAN", {"default": False}),
                "chars": ("BOOLEAN", {"default": False}),
                "print_length": ("BOOLEAN", {"default": False}),
                "substring": ("BOOLEAN", {"default": False}),
                "position": ("BOOLEAN", {"default": False}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128}),
                "advanced": ("BOOLEAN", {"default": False, "advanced": True}),
                "suffix": ("INT", {"default": 1, "advanced": True}),
                "suflink": ("INT", {"default": 0, "advanced": True}),
                "child": ("INT", {"default": 0, "advanced": True}),
                "skip": ("INT", {"default": 10, "advanced": True}),
                "kmer": ("INT", {"default": 1, "advanced": True}),
                "plot": ("BOOLEAN", {"default": False}),
                **_plot_input_types("plot_"),
            },
            "hidden": {"output": ("STRING", {})},
        }


class Mummer4MummerplotNode(_Mummer4BaseNode):
    """Generate MUMmer dotplots."""

    NODE_ID = "mummer4_mummerplot"
    DISPLAY_NAME = "MUMmer4 Mummerplot"
    DESCRIPTION = "Generate a 2-D dotplot or coverage plot from MUMmer or nucmer alignment output."
    SEARCH_ALIASES = ["Galaxy", "MUMmer4", "mummerplot", "mummerplot dotplot", "dotplot", "coverage plot", "gnuplot"]
    RETURN_TYPES = ("IMAGE", "FILE", "FILE", "FILE", "FILE")
    RETURN_NAMES = ("plot", "gnuplot", "forward_plot", "reverse_plot", "highlight_plot")
    REQUIRED_EXECUTABLES = ["mummerplot", "gnuplot"]
    REQUIRED_CONDA_PACKAGES = ["mummer4", "gnuplot"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd: list[str] = []
        _link_inputs(cmd, inputs.get("reference_sequence", ""), inputs.get("query_sequence", ""))
        cmd.append("mummerplot")
        _add_plot_args(cmd, inputs, include_sequences=True)
        cmd.extend([str(inputs.get("delta", "")), "&&", "gnuplot", "<", "out.gp", "&&", "mv", "out.png", f"{out}/out.png"])
        if str(inputs.get("extra_outs", "plot")) == "all":
            for name in ("out.gp", "out.fplot", "out.rplot", "out.hplot"):
                cmd.extend(["&&", "mv", name, f"{out}/{name}"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        paths = [out / "out.png"]
        if str(inputs.get("extra_outs", "plot")) == "all":
            paths.extend([out / "out.gp", out / "out.fplot", out / "out.rplot", out / "out.hplot"])
        return paths

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "delta": ("FILE", {"description": "MUMmer or nucmer match/delta file"}),
                "reference_sequence": ("FASTA", {"description": "Reference FASTA"}),
                "query_sequence": ("FASTA", {"description": "Query FASTA"}),
            },
            "optional": {
                **_plot_input_types(""),
                "seq_input": ("BOOLEAN", {"default": False, "description": "Pass ordered reference/query FASTA files to mummerplot"}),
                "layout": ("BOOLEAN", {"default": False, "description": "Layout a delta multiplot intelligibly"}),
                "extra_outs": ("STRING", {"default": "plot", "options": ["plot", "all"], "description": "Return just plot or all mummerplot intermediate files"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


def _plot_input_types(prefix: str) -> dict[str, tuple[str, dict[str, Any]]]:
    return {
        f"{prefix}breaklen": ("INT", {"default": 20, "min": 0, "description": "Plot breakpoint highlight length", "advanced": True}),
        f"{prefix}color": ("STRING", {"default": "", "options": ["", "-color"], "description": "Disable percent-similarity color gradient", "advanced": True}),
        f"{prefix}coverage": ("STRING", {"default": "", "options": ["", "-c"], "description": "Generate coverage plot instead of dotplot", "advanced": True}),
        f"{prefix}filter": ("BOOLEAN", {"default": False, "description": "Plot only best delta alignments", "advanced": True}),
        f"{prefix}fat": ("BOOLEAN", {"default": False, "description": "Layout using fattest alignment only", "advanced": True}),
        f"{prefix}plot_ids": ("BOOLEAN", {"default": False, "description": "Limit plot to a specific reference/query ID", "advanced": True}),
        f"{prefix}ref_id": ("STRING", {"default": "", "description": "Reference sequence ID for plotting", "advanced": True}),
        f"{prefix}query_id": ("STRING", {"default": "", "description": "Query sequence ID for plotting", "advanced": True}),
        f"{prefix}size": ("STRING", {"default": "small", "options": ["small", "medium", "large"], "description": "Plot size"}),
        f"{prefix}title": ("STRING", {"default": "Title", "description": "Plot title"}),
        f"{prefix}snp": ("BOOLEAN", {"default": False, "description": "Highlight SNP locations", "advanced": True}),
        f"{prefix}custom_range": ("BOOLEAN", {"default": False, "description": "Use custom x/y axis ranges", "advanced": True}),
        f"{prefix}min_x": ("INT", {"default": 0, "advanced": True}),
        f"{prefix}max_x": ("INT", {"default": 100, "advanced": True}),
        f"{prefix}min_y": ("INT", {"default": 0, "advanced": True}),
        f"{prefix}max_y": ("INT", {"default": 100, "advanced": True}),
    }
