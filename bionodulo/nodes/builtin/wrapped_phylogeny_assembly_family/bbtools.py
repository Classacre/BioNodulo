"""BBTools wrapper contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

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
    VERSION = "39.08+galaxy4"
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

        outputs_select = cls._selected(inputs, "outputs_select")
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
        outputs_select = cls._selected(inputs, "outputs_select")
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
        if not cls._selected(inputs, "outputs_select"):
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
                    {"default": [], "options": ["outu", "outm", "outs"], "description": "Required read outputs to write"},
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
    VERSION = "39.08+galaxy4"
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
    VERSION = "39.08+galaxy4"
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
    VERSION = "39.08+galaxy4"
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
    VERSION = "39.08+galaxy4"
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
    VERSION = "39.08+galaxy4"
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

pin_contract(BBToolsBBDukNode)
pin_contract(BBToolsBBMergeNode)
pin_contract(BBToolsBBNormNode)
pin_contract(BBToolsTadpoleNode)
pin_contract(BBToolsCallVariantsNode)
pin_contract(BBToolsBBMapNode)

__all__ = ["BBToolsBBDukNode","BBToolsBBMergeNode","BBToolsBBNormNode","BBToolsTadpoleNode","BBToolsCallVariantsNode","BBToolsBBMapNode"]
