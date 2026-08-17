"""Dorado 0.9.6 simplex basecalling with explicit local model artifacts."""

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


class DoradoBasecallerNode(DoradoCommandNode):
    """Basecall POD5 data without implicit model downloads or GPU assumptions."""

    NODE_ID = "dorado_basecaller"
    REQUIRES_GPU = True
    DISPLAY_NAME = "Dorado Basecaller"
    DESCRIPTION = "Basecall ONT POD5 data with explicit local Dorado model directories"
    SEARCH_ALIASES = [
        *DoradoCommandNode.SEARCH_ALIASES,
        "basecaller",
        "POD5",
        "modified bases",
        "methylation",
    ]
    RETURN_TYPES = ("BAM", "BAI")
    RETURN_NAMES = ("basecalled_bam", "basecalled_bam_index")
    OUTPUT_FILENAMES = ("basecalled_bam.bam", "basecalled_bam.bam.bai")
    REQUIRED_PATH_INPUTS = ("pod5_dir", "model", "reference")
    UPSTREAM_SOURCE = (
        "dorado/cli/basecaller.cpp; dorado/cli/model_resolution.h; "
        "dorado/cli/basecall_output_args.cpp; dorado/utils/hts_file.cpp"
    )
    DOCUMENTATION_URL = "https://github.com/nanoporetech/dorado/tree/v0.9.6#simplex-basecalling"
    TRIM_MODES = ("all", "adapters", "none")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "pod5_dir": (
                    "DIRECTORY",
                    {"description": "Directory containing POD5 signal files"},
                ),
                "model": (
                    "DIRECTORY",
                    {
                        "description": (
                            "Staged local simplex model directory; automatic model names "
                            "and downloads are intentionally not accepted"
                        )
                    },
                ),
                "reference": (
                    "FILE",
                    {
                        "description": (
                            "FASTA, FASTQ, or minimap2 MMI reference; file-output mode "
                            "sorts and indexes the aligned BAM"
                        )
                    },
                ),
            },
            "optional": {
                "modified_bases_models": (
                    "DIRECTORY",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Staged local modified-base model directories",
                    },
                ),
                "kit_name": ("STRING", {"default": ""}),
                "trim": (
                    "STRING",
                    {"default": "all", "options": list(cls.TRIM_MODES)},
                ),
                "min_qscore": ("INT", {"default": 0, "min": 0}),
                "device": (
                    "STRING",
                    {
                        "default": "auto",
                        "description": "Dorado Linux device: auto, cpu, cuda:all, cuda:auto, or cuda:<ids>",
                    },
                ),
                "recursive": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        model = path_value(inputs.get("model"))
        model_selector = model.split(",", 1)[0].split("@", 1)[0]
        if "/" not in model and model_selector in {"fast", "hac", "sup"}:
            return "Input 'model' must be a staged local model directory, not an automatic selector"
        trim = str(option_value(inputs, "trim", "all"))
        if trim not in cls.TRIM_MODES:
            return f"Input 'trim' must be one of: {', '.join(cls.TRIM_MODES)}"
        validation = validate_int(option_value(inputs, "min_qscore", 0), "min_qscore", minimum=0)
        if validation is not True:
            return validation
        device = str(option_value(inputs, "device", "auto"))
        if not valid_dorado_device(device):
            return "Input 'device' must be auto, cpu, cuda:all, cuda:auto, or cuda:<ids>"
        raw_mod_models = inputs.get("modified_bases_models")
        if raw_mod_models not in (None, "", []):
            mod_models = path_list(raw_mod_models)
            if not mod_models:
                return "Input 'modified_bases_models' must contain path-like model directories"
            if any("," in model for model in mod_models):
                return "Modified-base model paths cannot contain commas"
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
            "basecaller",
            path_value(inputs["model"]),
            path_value(inputs["pod5_dir"]),
        )
        command.extend(["--device", str(option_value(inputs, "device", "auto"))])
        if option_value(inputs, "recursive", False):
            command.append("--recursive")
        command.extend(["--min-qscore", str(option_value(inputs, "min_qscore", 0))])
        command.extend(["--reference", path_value(inputs["reference"])])
        mod_models = path_list(inputs.get("modified_bases_models"))
        if mod_models:
            command.extend(["--modified-bases-models", ",".join(mod_models)])
        if inputs.get("kit_name"):
            command.extend(["--kit-name", str(inputs["kit_name"])])
        command.extend(["--trim", str(option_value(inputs, "trim", "all"))])
        command.extend(["--output-dir", native_output_dir])
        return command

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        """Run Dorado in file-output mode and stabilize its timestamped BAM name."""
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

        with tempfile.TemporaryDirectory(prefix="dorado_native_", dir=node_out) as temp_dir:
            native_dir = Path(temp_dir)
            kwargs["native_output_dir"] = str(native_dir)
            command = self.__class__.render_command(kwargs)
            result = await run_direct_argv(
                command,
                context=context,
                cwd=node_out,
                env=env_with_binary(self.__class__, self.__class__.ENV_VARS or None),
                stdout_path=node_out / "dorado.stdout.log",
                stderr_path=node_out / "dorado.stderr.log",
            )
            require_success(result, label="Dorado basecaller")

            native_bams = sorted(native_dir.glob("calls_*.bam"))
            if len(native_bams) != 1:
                raise RuntimeError(
                    f"Dorado basecaller must create exactly one native calls_*.bam; found {len(native_bams)}"
                )
            native_index = Path(f"{native_bams[0]}.bai")
            if not native_index.is_file():
                raise RuntimeError("Dorado basecaller did not create the source-native sorted BAM index")
            native_bams[0].replace(outputs[0])
            native_index.replace(outputs[1])

        missing = [output for output in outputs if not output.is_file()]
        if missing:
            raise RuntimeError(f"Dorado basecaller did not create expected output(s): {missing}")
        return tuple(str(output) for output in outputs)
