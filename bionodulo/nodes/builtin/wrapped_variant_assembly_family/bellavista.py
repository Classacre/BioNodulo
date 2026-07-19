"""Focused bellavista node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class BellavistaPrepareNode(CommandNode):
    """Prepare BellaVista spatial transcriptomics inputs."""

    NODE_ID = "bellavista_prepare"
    DISPLAY_NAME = "Bellavista"
    CATEGORY = "visualization"
    DESCRIPTION = "Prepare large images for bellavista visualizer."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Bellavista",
        "BellaVista",
        "bellavista_prepare",
        "spatial transcriptomics",
        "imaging-based spatial transcriptomics",
        "MERSCOPE",
        "Xenium",
        "OME-Zarr",
        "visualizer",
    ]
    RETURN_TYPES = ("TGZ", "JSON")
    RETURN_NAMES = ("bellavista_output", "config")
    REQUIRED_EXECUTABLES = ["bash", "cat", "chmod", "cp", "mkdir", "tar"]
    DOCUMENTATION_URL = "https://github.com/pkosurilab/BellaVista"
    CITATION_DOIS = ["10.1016/j.bpj.2024.11.3199"]
    CITATION_URLS = [f"{DOI_URL}10.1016/j.bpj.2024.11.3199", "https://github.com/pkosurilab/BellaVista"]
    CITATION_TEXT = "Open-source Visualization for Imaging-Based Spatial Transcriptomics."
    VERSION = "0.0.2"
    ENVIRONMENT = {"container": "quay.io/bgruening/bellavista:0.0.2-3"}
    SHELL = True
    TECHNOLOGIES = ["Xenium", "MERSCOPE"]

    @classmethod
    def _bool(cls, inputs: dict[str, Any], name: str, default: bool) -> bool:
        value = inputs.get(name, default)
        if isinstance(value, str):
            return value.lower() in {"true", "yes", "1"}
        return bool(value)

    @classmethod
    def _technology(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("technology", "MERSCOPE") or "MERSCOPE")

    @classmethod
    def _staged_name(cls, path: Any) -> str:
        return _safe_name(str(path))

    @classmethod
    def _selected_genes(cls, inputs: dict[str, Any]) -> list[str]:
        genes = str(inputs.get("selected_genes", "") or "")
        return [gene.strip() for gene in genes.split(",") if gene.strip()]

    @classmethod
    def _config_payload(cls, inputs: dict[str, Any]) -> dict[str, Any]:
        plot_transcripts = cls._bool(inputs, "plot_transcripts", True)
        plot_cell_seg = cls._bool(inputs, "plot_cell_seg", True)
        plot_nuclear_seg = cls._bool(inputs, "plot_nuclear_seg", False)
        plot_all_genes = str(inputs.get("plot_all_genes", "Yes") or "Yes")
        input_files: dict[str, Any] = {
            "images": [cls._staged_name(image) for image in _as_list(inputs.get("images"))],
        }
        if plot_cell_seg:
            input_files["cell_segmentation"] = cls._staged_name(inputs.get("cell_segmentation", ""))
        if plot_nuclear_seg:
            input_files["nuclear_segmentation"] = cls._staged_name(inputs.get("nuclear_segmentation", ""))
        if cls._technology(inputs) == "MERSCOPE":
            input_files["um_to_px_transform"] = "micron_to_mosaic_pixel_transform.csv"
        if plot_transcripts:
            input_files["transcript_filename"] = cls._staged_name(inputs.get("transcript_filename", ""))
        input_files["z_plane"] = int(inputs.get("z_plane", 0))

        visualization_parameters: dict[str, Any] = {
            "plot_image": True,
            "plot_transcripts": plot_transcripts,
            "plot_cell_seg": plot_cell_seg,
            "plot_nuclear_seg": plot_nuclear_seg,
            "genes_visible_on_startup": False,
            "plot_allgenes": plot_all_genes == "Yes",
        }
        if plot_all_genes != "Yes":
            visualization_parameters["selected_genes"] = cls._selected_genes(inputs)
        visualization_parameters.update(
            {
                "rotate_angle": int(inputs.get("rotate_angle", 0)),
                "transcript_point_size": int(inputs.get("transcript_point_size", 1)),
            }
        )

        return {
            "system": cls._technology(inputs),
            "data_folder": "./",
            "create_bellavista_inputs": True,
            "visualization_parameters": visualization_parameters,
            "input_files": input_files,
        }

    @classmethod
    def _config_json(cls, inputs: dict[str, Any]) -> str:
        return json.dumps(cls._config_payload(inputs), separators=(",", ":"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_dir = f"{out}/input"
        config_path = f"{input_dir}/config.json"
        commands = [
            f"export TIME_LIMIT_SECONDS={shlex.quote(str(inputs.get('timeout', 3600)))}",
            f"export BELLAVISTA_DIR={shlex.quote(f'{input_dir}/')}",
            _shell_join(["mkdir", "-p", input_dir, f"{input_dir}/BellaVista_output"]),
            _shell_join(["chmod", "-R", "777", f"{input_dir}/"]),
        ]
        if cls._bool(inputs, "plot_transcripts", True):
            commands.append(
                _shell_join(["cp", str(inputs.get("transcript_filename", "")), f"{input_dir}/{cls._staged_name(inputs.get('transcript_filename', ''))}"])
            )
        for image in _as_list(inputs.get("images")):
            commands.append(_shell_join(["cp", image, f"{input_dir}/{cls._staged_name(image)}"]))
        if cls._bool(inputs, "plot_cell_seg", True):
            commands.append(
                _shell_join(["cp", str(inputs.get("cell_segmentation", "")), f"{input_dir}/{cls._staged_name(inputs.get('cell_segmentation', ''))}"])
            )
        if cls._bool(inputs, "plot_nuclear_seg", False):
            commands.append(
                _shell_join(
                    [
                        "cp",
                        str(inputs.get("nuclear_segmentation", "")),
                        f"{input_dir}/{cls._staged_name(inputs.get('nuclear_segmentation', ''))}",
                    ]
                )
            )
        if cls._technology(inputs) == "MERSCOPE":
            commands.append(
                _shell_join(["cp", str(inputs.get("um_to_px_transform", "")), f"{input_dir}/micron_to_mosaic_pixel_transform.csv"])
            )
        config_json = cls._config_json(inputs)
        commands.extend(
            [
                f"printf %s {shlex.quote(config_json)} > {shlex.quote(config_path)}",
                _shell_join(["cat", config_path]),
                _shell_join(["cp", config_path, f"{input_dir}/config_orig.json"]),
                f"cd {shlex.quote(f'{input_dir}/')} && {_shell_join(['bash', str(inputs.get('script_path', 'bellavista.bash'))])}",
                f"cd {shlex.quote(out)} && {_shell_join(['tar', '-czf', f'{out}/bellavista.tar.gz', 'input/'])}",
            ]
        )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "input").mkdir(parents=True, exist_ok=True)
        outputs = [out / "bellavista.tar.gz"]
        if cls._bool(inputs, "config", True):
            outputs.append(out / "input" / "config_orig.json")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "images": ("FILE", {"is_list": True, "description": "TIFF or OME-TIFF image files to prepare"}),
            },
            "optional": {
                "technology": (
                    "STRING",
                    {
                        "default": "MERSCOPE",
                        "options": cls.TECHNOLOGIES,
                        "description": "Spatial transcriptomic technology represented by the input data",
                    },
                ),
                "um_to_px_transform": (
                    "CSV",
                    {
                        "default": "",
                        "description": "MERSCOPE micron-to-mosaic-pixel transform CSV",
                    },
                ),
                "plot_transcripts": ("BOOLEAN", {"default": True, "description": "Include transcript spatial locations"}),
                "transcript_filename": (
                    "FILE",
                    {"default": "", "description": "Transcript spatial locations in CSV or Parquet format"},
                ),
                "plot_all_genes": ("STRING", {"default": "Yes", "options": ["Yes", "No"]}),
                "selected_genes": ("STRING", {"default": "", "description": "Comma-separated genes to visualize"}),
                "plot_cell_seg": ("BOOLEAN", {"default": True, "description": "Include cell segmentation data"}),
                "cell_segmentation": ("FILE", {"default": "", "description": "Cell segmentation Parquet or Zarr data"}),
                "plot_nuclear_seg": ("BOOLEAN", {"default": False, "description": "Include nuclear segmentation data"}),
                "nuclear_segmentation": ("FILE", {"default": "", "description": "Nuclear segmentation Parquet or Zarr data"}),
                "z_plane": ("INT", {"default": 0, "min": 0, "description": "Image z-plane to visualize"}),
                "transcript_point_size": ("INT", {"default": 1, "min": 0, "description": "Transcript point size"}),
                "rotate_angle": ("INT", {"default": 0, "min": -180, "max": 180, "description": "Image rotation angle"}),
                "config": ("BOOLEAN", {"default": True, "description": "Also return the generated config JSON"}),
                "timeout": ("INT", {"default": 3600, "min": 0, "max": 21600, "advanced": True}),
                "script_path": (
                    "FILE",
                    {"default": "bellavista.bash", "advanced": True, "description": "Path to the Galaxy Bellavista helper script"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("images")):
            return "images is required"
        technology = cls._technology(inputs)
        if technology not in cls.TECHNOLOGIES:
            return f"technology must be one of: {', '.join(cls.TECHNOLOGIES)}"
        if technology == "MERSCOPE" and not inputs.get("um_to_px_transform"):
            return "um_to_px_transform is required for MERSCOPE"
        if cls._bool(inputs, "plot_transcripts", True) and not inputs.get("transcript_filename"):
            return "transcript_filename is required when plot_transcripts is true"
        if str(inputs.get("plot_all_genes", "Yes") or "Yes") == "No" and not cls._selected_genes(inputs):
            return "selected_genes is required when plot_all_genes is No"
        if cls._bool(inputs, "plot_cell_seg", True) and not inputs.get("cell_segmentation"):
            return "cell_segmentation is required when plot_cell_seg is true"
        if cls._bool(inputs, "plot_nuclear_seg", False) and not inputs.get("nuclear_segmentation"):
            return "nuclear_segmentation is required when plot_nuclear_seg is true"
        return True

pin_contract(BellavistaPrepareNode)

__all__ = ['BellavistaPrepareNode']
