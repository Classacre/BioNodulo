"""Focused biapy node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin._variant_assembly_contracts import pin_contract

class BiaPyNode(CommandNode):
    """Run BiaPy deep-learning workflows for bioimage analysis."""

    NODE_ID = "biapy"
    DISPLAY_NAME = "Build a workflow with BiaPy"
    CATEGORY = "ai"
    DESCRIPTION = "Run BiaPy deep-learning workflows for bioimage analysis."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BiaPy",
        "biapy",
        "Build a workflow with BiaPy",
        "accessible deep learning on bioimages",
        "bioimage analysis",
        "image segmentation",
        "object detection",
        "image denoising",
        "BioImage Model Zoo",
    ]
    RETURN_TYPES = ("DIRECTORY", "DIRECTORY", "DIRECTORY", "DIRECTORY", "DIRECTORY", "YAML")
    RETURN_NAMES = ("predictions_raw", "predictions_post_proc", "test_metrics", "train_charts", "train_logs", "config_file")
    REQUIRED_EXECUTABLES = ["biapy", "ln", "mkdir", "mktemp", "mv", "python3"]
    DOCUMENTATION_URL = "https://biapy.readthedocs.io/"
    CITATION_DOIS = ["10.1038/s41592-025-02699-y"]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41592-025-02699-y"]
    CITATION_TEXT = "BiaPy: accessible deep learning on bioimages."
    VERSION = "3.6.8"
    ENVIRONMENT = {"container": "biapyx/biapy:3.6.8-11.8"}
    SHELL = True
    MODES = ["custom_cfg", "create_new_cfg"]
    WORKFLOWS = ["semantic", "instance", "detection", "denoising", "sr", "cls", "sr2", "i2i"]
    PHASES = ["train_test", "train", "test"]
    MODEL_SOURCES = ["biapy", "biapy_pretrained", "bmz_pretrained"]
    OUTPUT_OPTIONS = ["raw", "post_proc", "metrics", "tcharts", "tlogs", "checkpoint"]

    @classmethod
    def _phase(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("phase", inputs.get("phases", "train_test")) or "train_test")

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        outputs = _as_list(inputs.get("selected_outputs"))
        return outputs or ["raw"]

    @classmethod
    def _file_ext(cls, path: str, default: str = "dat") -> str:
        suffixes = Path(path).suffixes
        if not suffixes:
            return default
        if len(suffixes) >= 2 and suffixes[-1] == ".gz":
            return "".join(suffixes[-2:]).lstrip(".")
        return suffixes[-1].lstrip(".") or default

    @classmethod
    def _stage_files(cls, command_parts: list[str], files: list[str], directory: str, prefix: str) -> None:
        if not files:
            return
        command_parts.append(_shell_join(["mkdir", "-p", directory]))
        for index, path in enumerate(files):
            staged = f"{directory}/{prefix}-{index}.{cls._file_ext(path)}"
            command_parts.append(_shell_join(["ln", "-fs", path, staged]))

    @classmethod
    def _yaml_command(cls, inputs: dict[str, Any], out: str) -> str:
        mode = str(inputs.get("selected_mode", "custom_cfg") or "custom_cfg")
        script = str(inputs.get("create_yaml_script", "create_yaml.py"))
        config = f"{out}/config.yaml"
        threads = f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"
        train_raw_dir = f"{out}/dataset/train/raw"
        train_gt_dir = f"{out}/dataset/train/gt"
        test_raw_dir = f"{out}/dataset/test/raw"
        test_gt_dir = f"{out}/dataset/test/gt"
        checkpoint_file = f"{out}/output/my_experiment/checkpoints/checkpoint.safetensors"
        cmd = ["python3", script]
        if mode == "custom_cfg":
            cmd.extend(["--input_config_path", str(inputs.get("config_path", "")), "--num_cpus", threads])
        else:
            cmd.extend(
                [
                    "--new_config",
                    "--num_cpus",
                    threads,
                    "--out_config_path",
                    config,
                    "--biapy_version",
                    cls.VERSION,
                    "--workflow",
                    str(inputs.get("workflow", "semantic")),
                    "--dims",
                    str(inputs.get("is_3d", inputs.get("dims", "2d"))),
                    "--obj_slices",
                    str(inputs.get("obj_slices", "")),
                    "--obj_size",
                    str(inputs.get("obj_size", "0-25")),
                    "--img_channel",
                    str(inputs.get("img_channel", 1)),
                ]
            )
            model_source = str(inputs.get("model_source", "biapy") or "biapy")
            if model_source == "biapy_pretrained":
                cmd.extend(["--model_source", "biapy", "--model", checkpoint_file])
            elif model_source == "bmz_pretrained":
                cmd.extend(["--model_source", "bmz", "--model", str(inputs.get("bmz_model_name", ""))])
            else:
                cmd.extend(["--model_source", "biapy"])
        if mode == "custom_cfg":
            cmd.extend(["--out_config_path", config, "--biapy_version", cls.VERSION])
        phase = cls._phase(inputs)
        if phase in {"train_test", "train"} and _as_list(inputs.get("raw_train")):
            cmd.extend(["--raw_train", train_raw_dir])
            if _as_list(inputs.get("gt_train")):
                cmd.extend(["--gt_train", train_gt_dir])
        if phase in {"train_test", "test"} and _as_list(inputs.get("raw_test")):
            cmd.extend(["--test_raw_path", test_raw_dir])
            if _as_list(inputs.get("gt_test")):
                cmd.extend(["--test_gt_path", test_gt_dir])
        if mode == "custom_cfg" and inputs.get("biapy_model_path"):
            cmd.extend(["--model", checkpoint_file, "--model_source", "biapy"])
        return _shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}")

    @classmethod
    def _raw_output_command(cls, out: str) -> str:
        result_dir = f"{out}/output/my_experiment/results/my_experiment_1"
        raw_dir = f"{out}/raw"
        candidates = [
            "per_image_instances",
            "full_image_instances",
            "per_image_binarized",
            "full_image_binarized",
            "full_image",
            "per_image_local_max_check",
            "as_3d_stack_binarized",
            "per_image",
        ]
        body = [f"mkdir -p {shlex.quote(raw_dir)} && {{ "]
        for index, candidate in enumerate(candidates):
            keyword = "if" if index == 0 else "elif"
            source = f"{result_dir}/{candidate}"
            body.append(f"{keyword} [ -d {shlex.quote(source)} ]; then mv {shlex.quote(source)}/* {shlex.quote(raw_dir)}/; ")
        predictions = f"{result_dir}/predictions.csv"
        body.append(f"elif [ -f {shlex.quote(predictions)} ]; then mv {shlex.quote(predictions)} {shlex.quote(raw_dir)}/; fi; }}")
        return "".join(body)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        checkpoint_file = f"{out}/output/my_experiment/checkpoints/checkpoint.safetensors"
        phase = cls._phase(inputs)
        outputs = cls._selected_outputs(inputs)
        command_parts = [
            "set -xeu",
            "export OPENCV_IO_ENABLE_OPENEXR=0",
            "WORKTMP=$(mktemp -d galaxy-torchinductor.XXXXXX)",
            "export TORCHINDUCTOR_CACHE_DIR=$WORKTMP/torchinductor",
            "mkdir -p $TORCHINDUCTOR_CACHE_DIR",
            _shell_join(["mkdir", "-p", f"{out}/output", f"{out}/output/my_experiment/checkpoints"]),
        ]
        if inputs.get("biapy_model_path"):
            command_parts.append(_shell_join(["ln", "-fs", str(inputs.get("biapy_model_path")), checkpoint_file]))
        command_parts.append(cls._yaml_command(inputs, out))
        if phase in {"train_test", "train"}:
            cls._stage_files(command_parts, _as_list(inputs.get("raw_train")), f"{out}/dataset/train/raw", "training")
            cls._stage_files(command_parts, _as_list(inputs.get("gt_train")), f"{out}/dataset/train/gt", "training-gt")
        if phase in {"train_test", "test"}:
            cls._stage_files(command_parts, _as_list(inputs.get("raw_test")), f"{out}/dataset/test/raw", "test")
            cls._stage_files(command_parts, _as_list(inputs.get("gt_test")), f"{out}/dataset/test/gt", "test-gt")
        command_parts.append(
            _shell_join(
                [
                    "biapy",
                    "--config",
                    f"{out}/config.yaml",
                    "--result_dir",
                    f"{out}/output",
                    "--name",
                    "my_experiment",
                    "--run_id",
                    "1",
                    "--gpu",
                    '${GALAXY_BIAPY_GPU_STRING:-""}',
                ]
            ).replace("'${GALAXY_BIAPY_GPU_STRING:-\"\"}'", '${GALAXY_BIAPY_GPU_STRING:-""}')
        )
        if phase in {"train_test", "test"}:
            if "raw" in outputs:
                command_parts.append(cls._raw_output_command(out))
            if "post_proc" in outputs:
                command_parts.append(_shell_join(["mkdir", "-p", f"{out}/post_proc"]))
            if "metrics" in outputs and _as_list(inputs.get("gt_test")):
                command_parts.append(
                    f"{_shell_join(['mkdir', '-p', f'{out}/metrics'])} && "
                    f"mv {shlex.quote(f'{out}/output/my_experiment/results/my_experiment_1/test_results_metrics.csv')} "
                    f"{shlex.quote(f'{out}/metrics/')} 2>/dev/null || true"
                )
        if phase in {"train_test", "train"}:
            if "tcharts" in outputs:
                command_parts.append(_shell_join(["mkdir", "-p", f"{out}/train_charts"]))
            if "tlogs" in outputs:
                command_parts.append(_shell_join(["mkdir", "-p", f"{out}/train_logs"]))
        if "checkpoint" in outputs:
            command_parts.append(_shell_join(["mkdir", "-p", f"{out}/checkpoints"]))
        return " && ".join(command_parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        selected = cls._selected_outputs(inputs)
        mapping = {
            "raw": out / "raw",
            "post_proc": out / "post_proc",
            "metrics": out / "metrics",
            "tcharts": out / "train_charts",
            "tlogs": out / "train_logs",
        }
        for option in ["raw", "post_proc", "metrics", "tcharts", "tlogs"]:
            if option in selected:
                path = mapping[option]
                path.mkdir(parents=True, exist_ok=True)
                outputs.append(path)
        outputs.append(out / "config.yaml")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "selected_mode": (
                    "STRING",
                    {"default": "custom_cfg", "options": cls.MODES, "description": "Reuse an existing YAML config or create one"},
                ),
                "config_path": ("YAML", {"default": "", "description": "Existing BiaPy YAML configuration"}),
                "biapy_model_path": ("FILE", {"default": "", "description": "Optional BiaPy safetensors checkpoint"}),
                "workflow": (
                    "STRING",
                    {"default": "semantic", "options": cls.WORKFLOWS, "description": "BiaPy workflow type"},
                ),
                "phase": ("STRING", {"default": "train_test", "options": cls.PHASES}),
                "is_3d": ("STRING", {"default": "2d", "options": ["2d", "3d", "2d_stack"]}),
                "obj_slices": ("STRING", {"default": "", "options": ["", "1-5", "5-10", "10-20", "20-60", "60+"]}),
                "obj_size": ("STRING", {"default": "0-25", "options": ["0-25", "25-100", "100-200", "200-500", "500+"]}),
                "img_channel": ("INT", {"default": 1, "min": 1, "max": 10}),
                "model_source": ("STRING", {"default": "biapy", "options": cls.MODEL_SOURCES}),
                "bmz_model_name": ("STRING", {"default": ""}),
                "raw_train": ("FILE", {"default": [], "is_list": True, "description": "Training raw images"}),
                "gt_train": ("FILE", {"default": [], "is_list": True, "description": "Training target images"}),
                "raw_test": ("FILE", {"default": [], "is_list": True, "description": "Test raw images"}),
                "gt_test": ("FILE", {"default": [], "is_list": True, "description": "Optional test target images"}),
                "selected_outputs": (
                    "STRING",
                    {
                        "default": ["raw"],
                        "options": cls.OUTPUT_OPTIONS,
                        "multiple": True,
                        "description": "BiaPy output collections to expose",
                    },
                ),
                "create_yaml_script": (
                    "FILE",
                    {"default": "create_yaml.py", "advanced": True, "description": "Path to the Galaxy create_yaml.py helper"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        mode = str(inputs.get("selected_mode", "custom_cfg") or "custom_cfg")
        if mode not in cls.MODES:
            return f"selected_mode must be one of: {', '.join(cls.MODES)}"
        if mode == "custom_cfg":
            if not str(inputs.get("config_path", "")).strip():
                return "config_path is required for custom_cfg mode"
            return True
        workflow = str(inputs.get("workflow", "semantic") or "semantic")
        if workflow not in cls.WORKFLOWS:
            return f"workflow must be one of: {', '.join(cls.WORKFLOWS)}"
        phase = cls._phase(inputs)
        if phase not in cls.PHASES:
            return f"phase must be one of: {', '.join(cls.PHASES)}"
        if phase in {"train_test", "train"} and not _as_list(inputs.get("raw_train")):
            return "raw_train is required when phase includes train"
        if phase in {"train_test", "test"} and not _as_list(inputs.get("raw_test")):
            return "raw_test is required when phase includes test"
        model_source = str(inputs.get("model_source", "biapy") or "biapy")
        if model_source not in cls.MODEL_SOURCES:
            return f"model_source must be one of: {', '.join(cls.MODEL_SOURCES)}"
        if model_source == "biapy_pretrained" and not str(inputs.get("biapy_model_path", "")).strip():
            return "biapy_model_path is required for BiaPy pretrained models"
        if model_source == "bmz_pretrained" and not str(inputs.get("bmz_model_name", "")).strip():
            return "bmz_model_name is required for BioImage Model Zoo models"
        return True

pin_contract(BiaPyNode)

__all__ = ['BiaPyNode']
