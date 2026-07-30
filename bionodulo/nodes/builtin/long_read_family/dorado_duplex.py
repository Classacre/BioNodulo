"""Dorado 0.9.6 duplex basecalling with explicit local model artifacts."""

from __future__ import annotations

from bionodulo.execution.external_binary import env_with_binary

import tempfile
from pathlib import Path
from typing import Any

from .adapter import (
    DoradoCommandNode,
    option_value,
    path_list,
    path_value,
    require_success,
    run_direct_argv,
    valid_dorado_device,
    validate_int,
)


class DoradoDuplexNode(DoradoCommandNode):
    """Run stereo duplex basecalling without implicit model downloads."""

    NODE_ID = "dorado_duplex"
    DISPLAY_NAME = "Dorado Duplex"
    DESCRIPTION = "Run ONT duplex basecalling with explicit simplex and stereo model directories"
    SEARCH_ALIASES = [
        *DoradoCommandNode.SEARCH_ALIASES,
        "duplex",
        "stereo model",
        "double strand",
        "high accuracy",
    ]
    RETURN_TYPES = ("BAM", "BAI")
    RETURN_NAMES = ("duplex_bam", "duplex_bam_index")
    REQUIRED_PATH_INPUTS = ("pod5_dir", "model", "stereo_model")
    UPSTREAM_SOURCE = "dorado/cli/duplex.cpp; dorado/cli/basecall_output_args.cpp; dorado/cli/model_resolution.h"
    DOCUMENTATION_URL = "https://github.com/nanoporetech/dorado/tree/v0.9.6#duplex"
    EXIT_SEMANTICS = (
        "Dorado returns non-zero for invalid CLI, model, input, device, alignment, "
        "or pipeline state. File-output mode writes one timestamped calls_*.bam; "
        "a reference-aligned BAM is sorted and indexed during finalisation."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "pod5_dir": ("DIRECTORY", {"description": "Directory containing POD5 signal files"}),
                "model": (
                    "DIRECTORY",
                    {"description": "Staged local simplex model directory with its official model name"},
                ),
                "stereo_model": (
                    "DIRECTORY",
                    {
                        "description": (
                            "Staged local stereo duplex model directory; explicit input prevents "
                            "Dorado from downloading a missing sibling model"
                        )
                    },
                ),
            },
            "optional": {
                "modified_bases_models": (
                    "DIRECTORY",
                    {"default": [], "multiple": True, "description": "Staged local modified-base model directories"},
                ),
                "pairs": ("CSV", {"default": "", "description": "Space-delimited CSV of read ID pairs"}),
                "read_ids": ("FILE", {"default": "", "description": "Newline-delimited read IDs to basecall"}),
                "reference": (
                    "FILE",
                    {"default": "", "description": "Optional FASTA/FASTQ/MMI reference; enables sorted BAM+BAI output"},
                ),
                "bed_file": ("BED", {"default": "", "description": "Optional BED annotations; requires reference"}),
                "device": (
                    "STRING",
                    {"default": "auto", "description": "auto, cpu, cuda:all, cuda:auto, or cuda:<ids>"},
                ),
                "recursive": ("BOOLEAN", {"default": False}),
                "min_qscore": ("INT", {"default": 0, "min": 0}),
                "threads": ("INT", {"default": 0, "min": 0}),
                "batch_size": ("INT", {"default": 0, "min": 0}),
                "chunk_size": ("INT", {"default": 10000, "min": 1}),
                "overlap": ("INT", {"default": 500, "min": 0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        outputs = [node_dir / "duplex_bam.bam"]
        if inputs.get("reference") not in (None, ""):
            outputs.append(node_dir / "duplex_bam.bam.bai")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        model = path_value(inputs.get("model"))
        model_selector = model.split(",", 1)[0].split("@", 1)[0]
        if "/" not in model and model_selector in {"fast", "hac", "sup", "basespace"}:
            return "Input 'model' must be a staged local simplex model directory, not an automatic selector"
        for key, default, minimum in (
            ("min_qscore", 0, 0),
            ("threads", 0, 0),
            ("batch_size", 0, 0),
            ("chunk_size", 10000, 1),
            ("overlap", 500, 0),
        ):
            validation = validate_int(option_value(inputs, key, default), key, minimum=minimum)
            if validation is not True:
                return validation
        if int(option_value(inputs, "overlap", 500)) >= int(option_value(inputs, "chunk_size", 10000)):
            return "Input 'overlap' must be smaller than 'chunk_size'"
        device = str(option_value(inputs, "device", "auto"))
        if not valid_dorado_device(device):
            return "Input 'device' must be auto, cpu, cuda:all, cuda:auto, or cuda:<ids>"
        mod_models = path_list(inputs.get("modified_bases_models"))
        if inputs.get("modified_bases_models") not in (None, "", []) and not mod_models:
            return "Input 'modified_bases_models' must contain path-like model directories"
        if any("," in path for path in mod_models):
            return "Modified-base model paths cannot contain commas"
        if inputs.get("bed_file") and not inputs.get("reference"):
            return "Input 'bed_file' requires 'reference'"
        for key in ("pairs", "read_ids", "reference", "bed_file"):
            value = inputs.get(key)
            if value not in (None, "") and not path_value(value):
                return f"Input '{key}' must be a non-empty path-like value"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        native_output_dir = str(
            inputs.get(
                "native_output_dir",
                Path(str(inputs.get("output", inputs.get("output_dir", ".")))) / "native_output",
            )
        )
        command = cls.checked_command(
            inputs,
            "dorado",
            "duplex",
            path_value(inputs["model"]),
            path_value(inputs["pod5_dir"]),
            "--stereo-model",
            path_value(inputs["stereo_model"]),
            "--device",
            str(option_value(inputs, "device", "auto")),
            "--min-qscore",
            str(option_value(inputs, "min_qscore", 0)),
            "--threads",
            str(option_value(inputs, "threads", 0)),
            "--batchsize",
            str(option_value(inputs, "batch_size", 0)),
            "--chunksize",
            str(option_value(inputs, "chunk_size", 10000)),
            "--overlap",
            str(option_value(inputs, "overlap", 500)),
        )
        mod_models = path_list(inputs.get("modified_bases_models"))
        if mod_models:
            command.extend(["--modified-bases-models", ",".join(mod_models)])
        for key, flag in (
            ("pairs", "--pairs"),
            ("read_ids", "--read-ids"),
            ("reference", "--reference"),
            ("bed_file", "--bed-file"),
        ):
            if inputs.get(key):
                command.extend([flag, path_value(inputs[key])])
        if option_value(inputs, "recursive", False):
            command.append("--recursive")
        command.extend(["--output-dir", native_output_dir])
        return command

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        """Stabilize Dorado's timestamped BAM and optional source-native index."""
        context = kwargs.pop("context", None)
        output_dir = kwargs.pop("output_dir", None)
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        output_root = Path(output_dir or ".")
        node_out = output_root / self.__class__.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        kwargs["output"] = str(node_out)
        kwargs["output_dir"] = str(node_out)

        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_root)

        with tempfile.TemporaryDirectory(prefix="dorado_duplex_native_", dir=node_out) as temp_dir:
            native_dir = Path(temp_dir)
            kwargs["native_output_dir"] = str(native_dir)
            result = await run_direct_argv(
                self.__class__.render_command(kwargs),
                context=context,
                cwd=node_out,
                env=env_with_binary(self.__class__, self.__class__.ENV_VARS or None),
                stdout_path=node_out / "dorado.stdout.log",
                stderr_path=node_out / "dorado.stderr.log",
            )
            require_success(result, label="Dorado duplex")

            native_bams = sorted(native_dir.glob("calls_*.bam"))
            if len(native_bams) != 1:
                raise RuntimeError(
                    f"Dorado duplex must create exactly one native calls_*.bam; found {len(native_bams)}"
                )
            native_bam = native_bams[0]
            native_index = Path(f"{native_bam}.bai")
            if len(outputs) == 2:
                if not native_index.is_file():
                    raise RuntimeError("Dorado duplex did not create the reference-aligned BAM index")
            native_bam.replace(outputs[0])
            if len(outputs) == 2:
                native_index.replace(outputs[1])

        missing = [output for output in outputs if not output.is_file()]
        if missing:
            raise RuntimeError(f"Dorado duplex did not create expected output(s): {missing}")
        return tuple(str(output) for output in outputs)
