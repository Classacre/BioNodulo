"""Focused AdapterRemoval trimming node."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class AdapterRemovalNode(CommandNode):
    """Remove adapter sequences and trim FASTQ reads with AdapterRemoval."""

    NODE_ID = "adapter_removal"
    DISPLAY_NAME = "AdapterRemoval"
    REQUIRED_CONDA_PACKAGES = ["adapterremoval"]
    CATEGORY = "trimming"
    DESCRIPTION = "Remove adapter sequences from high-throughput sequencing FASTQ reads, trim low-quality bases, and optionally merge overlapping pairs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AdapterRemoval",
        "adapter_removal",
        "adapterremoval",
        "adapter trimming",
        "FASTQ trimming",
        "read merging",
        "ancient DNA",
    ]
    RETURN_TYPES = ("TEXT", "FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ")
    RETURN_NAMES = (
        "output_settings",
        "output_truncated",
        "output_forward_truncated",
        "output_reverse_truncated",
        "output_interleaved_truncated",
        "output_singleton_truncated",
        "output_collapsed",
        "output_collapsed_truncated",
        "output_discarded",
    )
    REQUIRED_EXECUTABLES = ["AdapterRemoval"]
    DOCUMENTATION_URL = "https://adapterremoval.readthedocs.io/"
    CITATION_DOIS = [ADAPTER_REMOVAL_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ADAPTER_REMOVAL_CITATION_DOI}"]
    CITATION_TEXT = ADAPTER_REMOVAL_CITATION_TEXT
    VERSION = "2.3.4+galaxy0"
    SHELL = True
    RUN_IN_NODE_OUTPUT_DIR = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any], name: str) -> str:
        suffix = ".txt" if name == "output_settings" else ".fastq"
        return f"{_out(inputs)}/{name}{suffix}"

    @classmethod
    def _output_select(cls, inputs: dict[str, Any]) -> set[str]:
        selected: set[str] = set()
        for value in _as_list(inputs.get("output_select")):
            selected.update(part.strip() for part in value.split(",") if part.strip() and part.strip() != "none")
        return selected

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_type", "single") or "single")

    @classmethod
    def _interleaved_output_enabled(cls, inputs: dict[str, Any]) -> bool:
        value = inputs.get("interleaved_output", "no")
        if isinstance(value, bool):
            return value
        return str(value) == "yes"

    @classmethod
    def _read_pair(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        if cls._input_type(inputs) == "paired":
            collection = inputs.get("reads_collection")
            if isinstance(collection, dict):
                return str(collection.get("forward", "")), str(collection.get("reverse", ""))
            reads = _as_list(collection or inputs.get("reads"))
            return (reads[0] if reads else "", reads[1] if len(reads) > 1 else "")
        return str(inputs.get("read1", "")), str(inputs.get("read2", ""))

    @classmethod
    def _read_ext(cls, inputs: dict[str, Any], key: str, path: str) -> str:
        explicit = inputs.get(f"{key}_ext")
        if explicit:
            return str(explicit)
        suffixes = "".join(Path(path).suffixes).lower()
        return "fastqsanger.gz" if suffixes.endswith(".gz") else "fastqsanger"

    @classmethod
    def _read_identifier(cls, inputs: dict[str, Any], key: str, path: str) -> str:
        index = "1" if key == "read1" else "2"
        return f"read{index}{cls._read_ext(inputs, key, path)}"

    @classmethod
    def _append_flag_value(cls, parts: list[str], flag: str, value: Any) -> None:
        if value is not None and str(value) != "":
            parts.extend([flag, str(value)])

    @classmethod
    def _default_int(cls, inputs: dict[str, Any], name: str, default: int) -> Any:
        value = inputs.get(name)
        return default if value is None or str(value) == "" else value

    @classmethod
    def _default_float(cls, inputs: dict[str, Any], name: str, default: float) -> Any:
        value = inputs.get(name)
        return default if value is None or str(value) == "" else value

    @classmethod
    def _add_fastq_options(cls, parts: list[str], inputs: dict[str, Any]) -> None:
        parts.extend(
            [
                "--qualitybase",
                "33",
                "--qualitybase-output",
                "33",
                "--qualitymax",
                str(cls._default_int(inputs, "qualitymax", 41)),
            ]
        )
        if inputs.get("convert_uracils"):
            parts.append("--convert-uracils")
        if inputs.get("mask_degenerate_bases"):
            parts.append("--mask-degenerate-bases")

    @classmethod
    def _add_trimming_options(cls, parts: list[str], inputs: dict[str, Any]) -> None:
        parts.extend(
            [
                "--adapter1",
                str(inputs.get("adapter1") or ADAPTER_REMOVAL_ADAPTER1),
                "--adapter2",
                str(inputs.get("adapter2") or ADAPTER_REMOVAL_ADAPTER2),
            ]
        )
        cls._append_flag_value(parts, "--adapter-list", inputs.get("adapter_list"))
        parts.extend(
            [
                "--minadapteroverlap",
                str(cls._default_int(inputs, "minadapteroverlap", 0)),
                "--mm",
                str(cls._default_float(inputs, "mm", 3.0)),
                "--shift",
                str(cls._default_int(inputs, "shift", 2)),
            ]
        )
        if inputs.get("trim5p"):
            parts.extend(
                [
                    "--trim5p",
                    str(cls._default_int(inputs, "trim5p_mate1", 0)),
                    str(cls._default_int(inputs, "trim5p_mate2", 0)),
                ]
            )
        if inputs.get("trim3p"):
            parts.extend(
                [
                    "--trim3p",
                    str(cls._default_int(inputs, "trim3p_mate1", 0)),
                    str(cls._default_int(inputs, "trim3p_mate2", 0)),
                ]
            )
        if inputs.get("trimns"):
            parts.append("--trimns")
        parts.extend(["--maxns", str(cls._default_int(inputs, "maxns", 1000))])
        if inputs.get("trimqualities"):
            parts.append("--trimqualities")
        if inputs.get("sliding_window"):
            parts.extend(["--trimwindows", str(cls._default_int(inputs, "window_size", 0))])
        parts.extend(["--minquality", str(cls._default_int(inputs, "minquality", 2))])
        if inputs.get("preserve5p"):
            parts.append("--preserve5p")
        parts.extend(
            [
                "--minlength",
                str(cls._default_int(inputs, "minlength", 15)),
                "--maxlength",
                str(cls._default_int(inputs, "maxlength", 4294967295)),
            ]
        )

    @classmethod
    def _add_merging_options(cls, parts: list[str], inputs: dict[str, Any]) -> None:
        if inputs.get("collapse"):
            parts.append("--collapse")
        parts.extend(["--minalignmentlength", str(cls._default_int(inputs, "minalignmentlength", 11))])
        if inputs.get("collapse_deterministic"):
            parts.append("--collapse-deterministic")
        if inputs.get("collapse_conservatively"):
            parts.append("--collapse-conservatively")

    @classmethod
    def _primary_output_names(cls, inputs: dict[str, Any]) -> list[str]:
        input_type = cls._input_type(inputs)
        if input_type == "single":
            return ["output_settings", "output_truncated"]
        if input_type in {"pair", "paired"}:
            if cls._interleaved_output_enabled(inputs):
                return ["output_settings", "output_interleaved_truncated"]
            return ["output_settings", "output_forward_truncated", "output_reverse_truncated"]
        if input_type == "interleaved" and cls._interleaved_output_enabled(inputs):
            return ["output_settings", "output_interleaved_truncated"]
        return ["output_settings"]

    @classmethod
    def _planned_output_names(cls, inputs: dict[str, Any]) -> list[str]:
        names = cls._primary_output_names(inputs)
        selected = cls._output_select(inputs)
        optional_map = {
            "output_singleton": "output_singleton_truncated",
            "output_collapsed": "output_collapsed",
            "output_collapsed_truncated": "output_collapsed_truncated",
            "output_discarded": "output_discarded",
        }
        names.extend(output for option, output in optional_map.items() if option in selected)
        return names

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_type = cls._input_type(inputs)
        read1, read2 = cls._read_pair(inputs)
        read1_identifier = cls._read_identifier(inputs, "read1", read1)
        read2_identifier = cls._read_identifier(inputs, "read2", read2)
        setup = [f"ln -sf {shlex.quote(read1)} {shlex.quote(read1_identifier)}"]
        if input_type in {"pair", "paired"}:
            setup.append(f"ln -sf {shlex.quote(read2)} {shlex.quote(read2_identifier)}")

        parts = ["AdapterRemoval", "--file1", read1_identifier]
        if input_type == "interleaved":
            parts.extend(["--interleaved", "--interleaved-input"])
            if cls._interleaved_output_enabled(inputs):
                parts.extend(["--interleaved-output", cls._output_path(inputs, "output_interleaved_truncated")])
            if inputs.get("combined_output"):
                parts.append("--combined-output")
        elif input_type in {"pair", "paired"}:
            parts.extend(["--file2", read2_identifier])
            if inputs.get("identify_adapters"):
                parts.append("--identify-adapters")
            if cls._interleaved_output_enabled(inputs):
                parts.append("--interleaved-output")
            if inputs.get("combined_output"):
                parts.append("--combined-output")

        parts.extend(["--threads", "${GALAXY_SLOTS:-8}"])
        cls._add_fastq_options(parts, inputs)
        cls._add_trimming_options(parts, inputs)
        cls._add_merging_options(parts, inputs)
        parts.extend(["--settings", cls._output_path(inputs, "output_settings")])

        if input_type == "single":
            parts.extend(["--output1", cls._output_path(inputs, "output_truncated")])
        elif input_type in {"pair", "paired"}:
            if cls._interleaved_output_enabled(inputs):
                parts.extend(["--output1", cls._output_path(inputs, "output_interleaved_truncated")])
            else:
                parts.extend(
                    [
                        "--output1",
                        cls._output_path(inputs, "output_forward_truncated"),
                        "--output2",
                        cls._output_path(inputs, "output_reverse_truncated"),
                    ]
                )

        selected = cls._output_select(inputs)
        optional_flags = [
            ("output_singleton", "--singleton", "output_singleton_truncated"),
            ("output_collapsed", "--outputcollapsed", "output_collapsed"),
            ("output_collapsed_truncated", "--outputcollapsedtruncated", "output_collapsed_truncated"),
            ("output_discarded", "--discarded", "output_discarded"),
        ]
        for option, flag, output_name in optional_flags:
            if option in selected:
                parts.extend([flag, cls._output_path(inputs, output_name)])

        command = " && ".join(setup + [" ".join(shlex.quote(part) for part in parts)])
        return command.replace("'${GALAXY_SLOTS:-8}'", "${GALAXY_SLOTS:-8}")

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [
            out / (f"{name}.txt" if name == "output_settings" else f"{name}.fastq")
            for name in cls._planned_output_names(inputs)
        ]

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        return {
            path.name.removesuffix(".txt").removesuffix(".fastq"): path
            for path in planned_paths
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        if input_type not in {"single", "pair", "paired", "interleaved"}:
            return "input_type must be one of: single, pair, paired, interleaved"
        read1, read2 = cls._read_pair(inputs)
        if input_type in {"single", "interleaved"} and not read1:
            return "read1 is required for single or interleaved mode"
        if input_type == "pair" and (not read1 or not read2):
            return "read1 and read2 are required for pair mode"
        if input_type == "paired" and (not read1 or not read2):
            return "reads_collection must provide forward and reverse reads"
        if input_type in {"pair", "paired"} and read1.endswith(".gz") != read2.endswith(".gz"):
            return "paired reads must use the same compression/file type"
        interleaved_output = inputs.get("interleaved_output", "no")
        if not isinstance(interleaved_output, bool) and str(interleaved_output) not in {"no", "yes"}:
            return "interleaved_output must be one of: no, yes"
        unsupported = cls._output_select(inputs) - {
            "output_singleton",
            "output_collapsed",
            "output_collapsed_truncated",
            "output_discarded",
        }
        if unsupported:
            return f"output_select contains unsupported values: {', '.join(sorted(unsupported))}"
        for name, default, minimum, maximum in (
            ("qualitymax", 41, 0, 93),
            ("minadapteroverlap", 0, 0, None),
            ("shift", 2, 0, 93),
            ("trim5p_mate1", 0, 0, None),
            ("trim5p_mate2", 0, 0, None),
            ("trim3p_mate1", 0, 0, None),
            ("trim3p_mate2", 0, 0, None),
            ("maxns", 1000, 0, None),
            ("window_size", 0, 0, None),
            ("minquality", 2, 0, None),
            ("minlength", 15, 0, None),
            ("maxlength", 4294967295, 0, None),
            ("minalignmentlength", 11, 0, None),
        ):
            try:
                value = int(cls._default_int(inputs, name, default))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum or (maximum is not None and value > maximum):
                return f"{name} must be between {minimum} and {maximum}" if maximum is not None else f"{name} must be >= {minimum}"
        try:
            if float(cls._default_float(inputs, "mm", 3.0)) <= 0:
                return "mm must be greater than 0"
        except (TypeError, ValueError):
            return "mm must be a number"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": (
                    "STRING",
                    {
                        "default": "single",
                        "options": ["single", "pair", "paired", "interleaved"],
                        "description": "Galaxy input mode: single, separate pair, paired collection, or interleaved reads",
                    },
                ),
            },
            "optional": {
                "read1": ("FASTQ", {"default": "", "description": "Single, forward, or interleaved FASTQ reads"}),
                "read2": ("FASTQ", {"default": "", "description": "Reverse FASTQ reads for pair mode"}),
                "reads_collection": ("FASTQ_LIST", {"default": [], "description": "Paired collection as [forward, reverse] or a mapping with forward/reverse keys"}),
                "read1_ext": ("STRING", {"default": "", "description": "Galaxy datatype extension for read1 symlink naming", "advanced": True}),
                "read2_ext": ("STRING", {"default": "", "description": "Galaxy datatype extension for read2 symlink naming", "advanced": True}),
                "interleaved_output": ("STRING", {"default": "no", "options": ["no", "yes"], "description": "Write paired-end reads to one interleaved output"}),
                "identify_adapters": ("BOOLEAN", {"default": False, "description": "Attempt consensus adapter identification from overlapping pairs"}),
                "combined_output": ("BOOLEAN", {"default": False, "description": "Replace discarded or merged reads with a single N in paired output"}),
                "qualitymax": ("INT", {"default": 41, "min": 0, "max": 93, "description": "Maximum Phred score expected in input and output files"}),
                "convert_uracils": ("BOOLEAN", {"default": False, "description": "Convert uracils to thymine"}),
                "mask_degenerate_bases": ("BOOLEAN", {"default": False, "description": "Mask ambiguous IUPAC bases"}),
                "adapter1": ("STRING", {"default": ADAPTER_REMOVAL_ADAPTER1, "description": "Adapter sequence expected in mate 1 reads"}),
                "adapter2": ("STRING", {"default": ADAPTER_REMOVAL_ADAPTER2, "description": "Adapter sequence expected in mate 2 reads"}),
                "adapter_list": ("TSV", {"default": "", "description": "Optional tabular adapter sequence list"}),
                "minadapteroverlap": ("INT", {"default": 0, "min": 0, "description": "Minimum adapter overlap for single-end trimming"}),
                "mm": ("FLOAT", {"default": 3.0, "description": "Mismatch fraction or reciprocal mismatch rate"}),
                "shift": ("INT", {"default": 2, "min": 0, "max": 93, "description": "Allow alignment slip at the 5' end"}),
                "trim5p": ("BOOLEAN", {"default": False, "description": "Trim fixed bases from 5' ends"}),
                "trim5p_mate1": ("INT", {"default": 0, "min": 0, "description": "5' trim length for mate 1"}),
                "trim5p_mate2": ("INT", {"default": 0, "min": 0, "description": "5' trim length for mate 2"}),
                "trim3p": ("BOOLEAN", {"default": False, "description": "Trim fixed bases from 3' ends"}),
                "trim3p_mate1": ("INT", {"default": 0, "min": 0, "description": "3' trim length for mate 1"}),
                "trim3p_mate2": ("INT", {"default": 0, "min": 0, "description": "3' trim length for mate 2"}),
                "trimns": ("BOOLEAN", {"default": False, "description": "Trim consecutive terminal Ns"}),
                "maxns": ("INT", {"default": 1000, "min": 0, "description": "Discard reads with more Ns than this after trimming"}),
                "trimqualities": ("BOOLEAN", {"default": False, "description": "Trim terminal low-quality stretches"}),
                "sliding_window": ("BOOLEAN", {"default": False, "description": "Use sliding-window quality trimming"}),
                "window_size": ("INT", {"default": 0, "min": 0, "description": "Sliding-window size"}),
                "minquality": ("INT", {"default": 2, "min": 0, "description": "Low-quality trimming threshold"}),
                "preserve5p": ("BOOLEAN", {"default": False, "description": "Preserve 5' bases during quality trimming"}),
                "minlength": ("INT", {"default": 15, "min": 0, "description": "Discard reads shorter than this"}),
                "maxlength": ("INT", {"default": 4294967295, "min": 0, "description": "Discard reads longer than this"}),
                "collapse": ("BOOLEAN", {"default": False, "description": "Merge overlapping reads into consensus sequences"}),
                "minalignmentlength": ("INT", {"default": 11, "min": 0, "description": "Minimum mate overlap for collapsing"}),
                "collapse_deterministic": ("BOOLEAN", {"default": False, "description": "Use deterministic consensus bases when collapsing"}),
                "collapse_conservatively": ("BOOLEAN", {"default": False, "description": "Use conservative FASTQ-join inspired collapsing"}),
                "output_select": (
                    "STRING",
                    {
                        "default": "none",
                        "list": True,
                        "options": [
                            "none",
                            "output_singleton",
                            "output_collapsed",
                            "output_collapsed_truncated",
                            "output_discarded",
                        ],
                        "description": "Optional Galaxy outputs to request",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(AdapterRemovalNode)
