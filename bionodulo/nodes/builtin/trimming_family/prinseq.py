"""Focused PRINSEQ trimming node."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_amplicon_trimming_family.evidence import pin_contract

class PrinseqNode(CommandNode):
    """Filter and trim FASTQ reads with PRINSEQ."""

    NODE_ID = "prinseq"
    DISPLAY_NAME = "PRINSEQ"
    REQUIRED_CONDA_PACKAGES = ["prinseq"]
    CATEGORY = "trimming"
    DESCRIPTION = "Filter and trim single-end or paired-end FASTQ reads with PRINSEQ."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "PRINSEQ",
        "prinseq-lite",
        "quality control",
        "quality filter",
        "metagenomic preprocessing",
        "read trimming",
        "N filtering",
    ]
    RETURN_TYPES = (
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ",
        "FASTQ_LIST",
        "FASTQ_LIST",
        "FASTQ_LIST",
    )
    RETURN_NAMES = (
        "good_sequences",
        "rejected_sequences",
        "good_sequences_1",
        "good_sequences_1_singletons",
        "rejected_sequences_1",
        "good_sequences_2",
        "good_sequences_2_singletons",
        "rejected_sequences_2",
        "good_sequences_collection",
        "singletons_collection",
        "rejected_sequences_collection",
    )
    REQUIRED_EXECUTABLES = ["prinseq-lite.pl"]
    DOCUMENTATION_URL = "http://prinseq.sourceforge.net/manual.html"
    CITATION_DOIS = [PRINSEQ_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{PRINSEQ_CITATION_DOI}"]
    CITATION_TEXT = PRINSEQ_CITATION_TEXT
    VERSION = "0.20.4+galaxy2"
    SHELL = True
    RUN_IN_NODE_OUTPUT_DIR = True

    @classmethod
    def _mode(cls, inputs: dict[str, Any]) -> str:
        mode = str(inputs.get("input_mode", "") or "")
        if mode:
            return mode
        return "paired" if inputs.get("paired", False) else "single"

    @classmethod
    def _is_paired(cls, inputs: dict[str, Any]) -> bool:
        return cls._mode(inputs) != "single"

    @classmethod
    def _paired_reads(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        if cls._mode(inputs) == "paired_collection":
            collection = inputs.get("input_collection")
            if isinstance(collection, dict):
                return str(collection.get("forward", "")), str(collection.get("reverse", ""))
            values = _as_list(collection)
            return (values[0] if values else "", values[1] if len(values) > 1 else "")
        return str(inputs.get("input_mate1", "")), str(inputs.get("input_mate2", ""))

    @classmethod
    def _compress_output(cls, inputs: dict[str, Any]) -> bool:
        if isinstance(inputs.get("compress_output"), bool):
            return bool(inputs["compress_output"])
        if cls._is_paired(inputs):
            reads = list(cls._paired_reads(inputs))
        else:
            reads = [str(inputs.get("input_singles", ""))]
        return any(path.endswith(".gz") for path in reads if path)

    @classmethod
    def _planned_names(cls, inputs: dict[str, Any]) -> list[str]:
        mode = cls._mode(inputs)
        if mode != "single":
            names = [
                "good_sequences_1.fastq",
                "good_sequences_1_singletons.fastq",
                "rejected_sequences_1.fastq",
                "good_sequences_2.fastq",
                "good_sequences_2_singletons.fastq",
                "rejected_sequences_2.fastq",
            ]
            if mode == "paired_collection":
                names = [f"collection_{name}" for name in names]
        else:
            names = ["good_sequences.fastq", "rejected_sequences.fastq"]
        if cls._compress_output(inputs):
            names = [f"{name}.gz" for name in names]
        return names

    @classmethod
    def _stage_fastq(cls, source: str, target: str) -> str:
        if source.endswith(".gz"):
            return f"gunzip -c {shlex.quote(source)} > {target}"
        return f"ln -sf {shlex.quote(source)} {target}"

    @classmethod
    def _add_value_flag(cls, cmd: list[str], inputs: dict[str, Any], key: str, flag: str) -> None:
        value = inputs.get(key)
        if value is not None and str(value) != "":
            cmd.extend([flag, str(value)])

    @classmethod
    def _prinseq_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "prinseq-lite.pl",
            "-fastq",
            "fwd.fastq",
        ]
        if cls._is_paired(inputs):
            cmd.extend(["-fastq2", "rev.fastq"])
        if inputs.get("phred64"):
            cmd.append("-phred64")
        cmd.extend(["-out_good", f"{_out(inputs)}/tmp/good_sequences", "-out_bad", f"{_out(inputs)}/tmp/rejected_sequences"])
        filter_options = (
            ("min_len", "-min_len"),
            ("max_len", "-max_len"),
            ("min_qual_score", "-min_qual_score"),
            ("max_qual_score", "-max_qual_score"),
            ("min_qual_mean", "-min_qual_mean"),
            ("max_qual_mean", "-max_qual_mean"),
            ("min_gc", "-min_gc"),
            ("max_gc", "-max_gc"),
            ("ns_max_n", "-ns_max_n"),
            ("ns_max_p", "-ns_max_p"),
            ("lc_method", "-lc_method"),
            ("lc_threshold", "-lc_threshold"),
        )
        trimming_options = (
            ("trim_to_len", "-trim_to_len"),
            ("trim_left", "-trim_left"),
            ("trim_right", "-trim_right"),
            ("trim_left_p", "-trim_left_p"),
            ("trim_right_p", "-trim_right_p"),
            ("trim_tail_left", "-trim_tail_left"),
            ("trim_tail_right", "-trim_tail_right"),
            ("trim_ns_left", "-trim_ns_left"),
            ("trim_ns_right", "-trim_ns_right"),
            ("trim_qual_left", "-trim_qual_left"),
            ("trim_qual_right", "-trim_qual_right"),
            ("trim_qual_type", "-trim_qual_type"),
            ("trim_qual_rule", "-trim_qual_rule"),
            ("trim_qual_window", "-trim_qual_window"),
            ("trim_qual_step", "-trim_qual_step"),
        )
        if inputs.get("apply_filter_treatments", True):
            for key, flag in filter_options:
                cls._add_value_flag(cmd, inputs, key, flag)
            if inputs.get("noniupac"):
                cmd.append("-noniupac")
        if inputs.get("apply_trimming_treatments", True):
            for key, flag in trimming_options:
                cls._add_value_flag(cmd, inputs, key, flag)
        return " ".join(shlex.quote(part) for part in cmd)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        tmp = f"{out}/tmp"
        parts = ["set -eu", f"mkdir -p {shlex.quote(tmp)}"]
        if cls._is_paired(inputs):
            forward, reverse = cls._paired_reads(inputs)
            parts.extend(
                [
                    cls._stage_fastq(forward, "fwd.fastq"),
                    cls._stage_fastq(reverse, "rev.fastq"),
                    (
                        f"touch {shlex.quote(tmp)}/good_sequences_1.fastq {shlex.quote(tmp)}/good_sequences_1_singletons.fastq "
                        f"{shlex.quote(tmp)}/rejected_sequences_1.fastq {shlex.quote(tmp)}/good_sequences_2.fastq "
                        f"{shlex.quote(tmp)}/good_sequences_2_singletons.fastq {shlex.quote(tmp)}/rejected_sequences_2.fastq"
                    ),
                ]
            )
        else:
            parts.extend(
                [
                    cls._stage_fastq(str(inputs.get("input_singles", "")), "fwd.fastq"),
                    f"touch {shlex.quote(tmp)}/good_sequences.fastq {shlex.quote(tmp)}/rejected_sequences.fastq",
                ]
            )
        parts.append(cls._prinseq_command(inputs))

        names = cls._planned_names(inputs)
        for name in names:
            source = name.removeprefix("collection_").removesuffix(".gz")
            source_path = f"{tmp}/{source}"
            target_path = f"{out}/{name}"
            if name.endswith(".gz"):
                parts.append(f"gzip -c {shlex.quote(source_path)} > {shlex.quote(target_path)}")
            else:
                parts.append(f"cp {shlex.quote(source_path)} {shlex.quote(target_path)}")
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / name for name in cls._planned_names(inputs)]

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        def base_name(path: Path) -> str:
            return path.name.removeprefix("collection_").removesuffix(".gz").removesuffix(".fastq")

        if planned_paths and planned_paths[0].name.startswith("collection_"):
            by_name = {base_name(path): path for path in planned_paths}
            return {
                "good_sequences_collection": [by_name["good_sequences_1"], by_name["good_sequences_2"]],
                "singletons_collection": [
                    by_name["good_sequences_1_singletons"],
                    by_name["good_sequences_2_singletons"],
                ],
                "rejected_sequences_collection": [
                    by_name["rejected_sequences_1"],
                    by_name["rejected_sequences_2"],
                ],
            }
        return {base_name(path): path for path in planned_paths}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        mode = cls._mode(inputs)
        if mode not in {"single", "paired", "paired_collection"}:
            return "input_mode must be one of: single, paired, paired_collection"
        if mode == "single":
            if not str(inputs.get("input_singles", "")).strip():
                return "input_singles is required for single mode"
        else:
            forward, reverse = cls._paired_reads(inputs)
            if not forward or not reverse:
                source = "input_collection" if mode == "paired_collection" else "input_mate1 and input_mate2"
                return f"{source} must provide forward and reverse reads"
            if forward.endswith(".gz") != reverse.endswith(".gz"):
                return "paired reads must use the same compression/file type"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "input_mode": (
                    "STRING",
                    {
                        "default": "single",
                        "options": ["single", "paired", "paired_collection"],
                        "description": "Galaxy single, paired datasets, or paired collection mode",
                    },
                ),
                "paired": ("BOOLEAN", {"default": False, "advanced": True, "description": "Legacy paired-mode switch"}),
                "input_singles": ("FASTQ", {"default": "", "description": "Single-end FASTQ input"}),
                "input_mate1": ("FASTQ", {"default": "", "description": "Paired-end mate 1 FASTQ"}),
                "input_mate2": ("FASTQ", {"default": "", "description": "Paired-end mate 2 FASTQ"}),
                "input_collection": (
                    "FASTQ_LIST",
                    {"default": [], "description": "Paired collection mapping or ordered forward/reverse pair"},
                ),
                "compress_output": ("BOOLEAN", {"description": "Override wrapper-style input compression preservation"}),
                "phred64": ("BOOLEAN", {"default": False, "description": "Treat input qualities as Illumina/Phred+64"}),
                "apply_filter_treatments": ("BOOLEAN", {"default": True, "description": "Apply PRINSEQ filtering options"}),
                "apply_trimming_treatments": ("BOOLEAN", {"default": True, "description": "Apply PRINSEQ trimming options"}),
                "min_len": ("INT", {"default": 60, "min": 0, "description": "Minimum sequence length to keep"}),
                "max_len": ("INT", {"default": "", "min": 0, "advanced": True, "description": "Maximum sequence length to keep"}),
                "min_qual_score": ("INT", {"default": "", "min": 0, "max": 40, "advanced": True}),
                "max_qual_score": ("INT", {"default": "", "min": 0, "max": 40, "advanced": True}),
                "min_qual_mean": ("INT", {"default": 15, "min": 0, "max": 40, "description": "Minimum mean quality to keep"}),
                "max_qual_mean": ("INT", {"default": "", "min": 0, "max": 40, "advanced": True}),
                "min_gc": ("INT", {"default": "", "min": 0, "max": 100, "advanced": True}),
                "max_gc": ("INT", {"default": "", "min": 0, "max": 100, "advanced": True}),
                "ns_max_n": ("INT", {"default": "", "min": 0, "advanced": True, "description": "Maximum number of N bases"}),
                "ns_max_p": ("INT", {"default": 2, "min": 0, "max": 100, "description": "Maximum percentage of N bases"}),
                "noniupac": ("BOOLEAN", {"default": False, "description": "Reject bases outside A, C, G, T, and N"}),
                "trim_to_len": ("INT", {"default": "", "min": 0, "advanced": True}),
                "trim_left": ("INT", {"default": "", "min": 0, "advanced": True}),
                "trim_right": ("INT", {"default": "", "min": 0, "advanced": True}),
                "trim_left_p": ("INT", {"default": "", "min": 0, "max": 100, "advanced": True}),
                "trim_right_p": ("INT", {"default": "", "min": 0, "max": 100, "advanced": True}),
                "trim_tail_left": ("INT", {"default": "", "min": 0, "advanced": True}),
                "trim_tail_right": ("INT", {"default": "", "min": 0, "advanced": True}),
                "trim_ns_left": ("INT", {"default": "", "min": 0, "advanced": True}),
                "trim_ns_right": ("INT", {"default": "", "min": 0, "advanced": True}),
                "trim_qual_left": ("INT", {"default": "", "min": 0, "max": 40, "advanced": True}),
                "trim_qual_right": ("INT", {"default": 20, "min": 0, "max": 40, "description": "Right-end quality trimming threshold"}),
                "trim_qual_type": ("STRING", {"default": "min", "options": ["min", "mean", "max", "sum"], "advanced": True}),
                "trim_qual_rule": ("STRING", {"default": "lt", "options": ["lt", "gt", "et"], "advanced": True}),
                "trim_qual_window": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "trim_qual_step": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "lc_method": ("STRING", {"default": "", "options": ["", "dust", "entropy"], "advanced": True}),
                "lc_threshold": ("INT", {"default": "", "min": 0, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(PrinseqNode)
