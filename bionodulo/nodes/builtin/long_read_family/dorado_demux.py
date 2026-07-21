"""Dorado 0.9.6 barcode classification and demultiplexing."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .adapter import (
    DoradoCommandNode,
    option_value,
    path_value,
    require_success,
    run_direct_argv,
    validate_int,
)


_SAFE_BARCODE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class DoradoDemuxNode(DoradoCommandNode):
    """Emit Dorado's per-barcode files and native tab-delimited summary."""

    NODE_ID = "dorado_demux"
    DISPLAY_NAME = "Dorado Demux"
    DESCRIPTION = "Classify or split Dorado reads into source-native per-barcode files"
    SEARCH_ALIASES = [
        *DoradoCommandNode.SEARCH_ALIASES,
        "demux",
        "demultiplex",
        "barcoding",
        "barcode classification",
    ]
    RETURN_TYPES = ("DIRECTORY", "TSV", "BAM")
    RETURN_NAMES = ("demux_dir", "barcode_summary", "selected_bam")
    REQUIRED_PATH_INPUTS = ("reads",)
    UPSTREAM_SOURCE = "dorado/cli/demux.cpp; dorado/summary/summary.cpp"
    DOCUMENTATION_URL = "https://github.com/nanoporetech/dorado/tree/v0.9.6#barcode-classification"
    NATIVE_SUMMARY_FILENAME = "barcoding_summary.txt"
    SELECTED_BAM_FILENAME = "selected_barcode.bam"
    EXIT_SEMANTICS = (
        "Dorado returns non-zero for invalid CLI, input, barcode, and pipeline errors. "
        "Dorado treats an empty input directory as success, but this wrapper fails closed "
        "when the required native summary or requested unique barcode BAM is absent."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": (
                    ("BAM", "CRAM", "SAM", "FASTQ", "DIRECTORY"),
                    {"description": "One HTS file or a directory containing HTS files"},
                ),
                "selected_barcode": (
                    "STRING",
                    {
                        "description": (
                            "Exact BC tag or sample-sheet alias to expose as one deterministic BAM; "
                            "fails if zero or multiple run-specific files match"
                        ),
                    },
                ),
            },
            "optional": {
                "kit_name": ("STRING", {"default": ""}),
                "no_classify": (
                    "BOOLEAN",
                    {"default": False, "description": "Split existing barcode classifications"},
                ),
                "sample_sheet": ("CSV", {"default": ""}),
                "barcode_arrangement": ("FILE", {"default": ""}),
                "barcode_sequences": ("FASTA", {"default": ""}),
                "barcode_both_ends": ("BOOLEAN", {"default": False}),
                "no_trim": ("BOOLEAN", {"default": False}),
                "sort_bam": ("BOOLEAN", {"default": False}),
                "recursive": ("BOOLEAN", {"default": False}),
                "threads": ("INT", {"default": 0, "min": 0}),
                "max_reads": ("INT", {"default": 0, "min": 0}),
                "read_ids": ("FILE", {"default": ""}),
            },
            "hidden": {
                "output": ("STRING", {}),
                "emit_fastq": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": (
                            "Legacy compatibility input; rejected because Dorado 0.9.6 FASTQ "
                            "demux output cannot retain BC tags used by the required summary"
                        ),
                    },
                ),
            },
        }

    @classmethod
    def PLAN_OUTPUTS(
        cls,
        inputs: dict[str, Any],
        output_dir: str | Path,
    ) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        demux_dir = node_dir / "demux"
        return [
            demux_dir,
            demux_dir / cls.NATIVE_SUMMARY_FILENAME,
            demux_dir / cls.SELECTED_BAM_FILENAME,
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        kit_name = str(inputs.get("kit_name", "") or "").strip()
        no_classify = bool(option_value(inputs, "no_classify", False))
        if bool(kit_name) == no_classify:
            return "Specify exactly one of 'kit_name' or 'no_classify'"
        if no_classify and inputs.get("sample_sheet"):
            return "Input 'sample_sheet' cannot be used with 'no_classify'"
        if inputs.get("barcode_arrangement") and not kit_name:
            return "Input 'barcode_arrangement' requires 'kit_name'"
        if inputs.get("barcode_sequences") and not inputs.get("barcode_arrangement"):
            return "Input 'barcode_sequences' requires 'barcode_arrangement'"
        if option_value(inputs, "emit_fastq", False):
            return (
                "Input 'emit_fastq' is not supported because Dorado 0.9.6 FASTQ output "
                "drops barcode metadata required by 'barcode_summary'; demultiplex to BAM "
                "and convert the selected BAM with Samtools Fastx"
            )
        if option_value(inputs, "sort_bam", False) and not (option_value(inputs, "no_trim", False) or no_classify):
            return "Input 'sort_bam' requires 'no_trim' or 'no_classify'"
        selected_barcode = str(option_value(inputs, "selected_barcode", "") or "").strip()
        if not selected_barcode:
            return "Input 'selected_barcode' is required"
        if not _SAFE_BARCODE_NAME.fullmatch(selected_barcode):
            return (
                "Input 'selected_barcode' must be 1-128 ASCII letters, digits, dots, "
                "underscores, or hyphens and cannot start with punctuation"
            )
        for key, default in (("threads", 0), ("max_reads", 0)):
            validation = validate_int(option_value(inputs, key, default), key, minimum=0)
            if validation is not True:
                return validation
        for key in ("sample_sheet", "barcode_arrangement", "barcode_sequences", "read_ids"):
            value = inputs.get(key)
            if value not in (None, "") and not path_value(value):
                return f"Input '{key}' must be a non-empty path-like value"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(
            str(
                inputs.get(
                    "native_output_dir",
                    Path(str(inputs.get("output", inputs.get("output_dir", ".")))) / "demux",
                )
            )
        )
        command = cls.checked_command(
            inputs,
            "dorado",
            "demux",
            "--output-dir",
            str(output),
        )
        if option_value(inputs, "no_classify", False):
            command.append("--no-classify")
        else:
            command.extend(["--kit-name", str(inputs["kit_name"]).strip()])
        for key, flag in (
            ("sample_sheet", "--sample-sheet"),
            ("barcode_arrangement", "--barcode-arrangement"),
            ("barcode_sequences", "--barcode-sequences"),
        ):
            if inputs.get(key):
                command.extend([flag, path_value(inputs[key])])
        if option_value(inputs, "emit_fastq", False):
            command.append("--emit-fastq")
        command.append("--emit-summary")
        if option_value(inputs, "barcode_both_ends", False):
            command.append("--barcode-both-ends")
        if option_value(inputs, "no_trim", False):
            command.append("--no-trim")
        if option_value(inputs, "sort_bam", False):
            command.append("--sort-bam")
        if option_value(inputs, "recursive", False):
            command.append("--recursive")
        threads = option_value(inputs, "threads", 0)
        if threads:
            command.extend(["--threads", str(threads)])
        max_reads = option_value(inputs, "max_reads", 0)
        if max_reads:
            command.extend(["--max-reads", str(max_reads)])
        if inputs.get("read_ids"):
            command.extend(["--read-ids", path_value(inputs["read_ids"])])
        command.append(path_value(inputs["reads"]))
        return command

    async def run(self, **kwargs: Any) -> tuple[str, str, str]:
        """Run BAM demultiplexing and bind one requested barcode to a stable port."""
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
        demux_dir, summary_path, selected_path = outputs
        # Executor retries reuse the node workspace. Remove only this node's
        # previously published output so a partial prior attempt cannot poison
        # the retry; the replacement below publishes the new directory at once.
        if demux_dir.is_symlink() or demux_dir.is_file():
            demux_dir.unlink()
        elif demux_dir.is_dir():
            shutil.rmtree(demux_dir)

        selected_barcode = str(option_value(kwargs, "selected_barcode", "") or "").strip()
        with tempfile.TemporaryDirectory(prefix="dorado_demux_native_", dir=node_out) as temp_dir:
            native_dir = Path(temp_dir)
            kwargs["native_output_dir"] = str(native_dir)
            command = self.__class__.render_command(kwargs)
            result = await run_direct_argv(
                command,
                context=context,
                cwd=node_out,
                env=self.__class__.ENV_VARS or None,
                stdout_path=node_out / "dorado.stdout.log",
                stderr_path=node_out / "dorado.stderr.log",
            )
            require_success(result, label="Dorado demux")

            native_summary = native_dir / self.__class__.NATIVE_SUMMARY_FILENAME
            if not native_summary.is_file() or native_summary.stat().st_size == 0:
                raise RuntimeError(
                    "Dorado demux did not create the required native barcode summary; "
                    "the input may have contained no readable records"
                )
            suffix = f"_{selected_barcode}.bam"
            matches = sorted(path for path in native_dir.iterdir() if path.is_file() and path.name.endswith(suffix))
            if len(matches) != 1:
                raise RuntimeError(
                    "Dorado demux must create exactly one BAM for selected barcode "
                    f"'{selected_barcode}'; found {len(matches)}"
                )
            if matches[0].stat().st_size == 0:
                raise RuntimeError(f"Dorado demux created an empty BAM for selected barcode '{selected_barcode}'")

            # Keep the complete source-native directory while exposing one
            # deterministic BAM path. Hard-link when supported; copy only on
            # filesystems that do not provide links. Both happen inside the
            # unpublished directory so failures cannot expose partial outputs.
            native_selected = native_dir / self.__class__.SELECTED_BAM_FILENAME
            try:
                os.link(matches[0], native_selected)
            except OSError:
                shutil.copy2(matches[0], native_selected)

            native_dir.replace(demux_dir)

        if (
            not demux_dir.is_dir()
            or not summary_path.is_file()
            or not selected_path.is_file()
            or selected_path.stat().st_size == 0
        ):
            raise RuntimeError("Dorado demux did not create its required output artifacts")
        return str(demux_dir), str(summary_path), str(selected_path)
