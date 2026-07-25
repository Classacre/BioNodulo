"""ColabFold 1.5.5 batch prediction contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from bionodulo.nodes.command_node import CommandNode

from .adapter import path_value, validate_int


class ColabFoldBatchNode(CommandNode):
    """Run ColabFold with an explicit MSA-network policy."""

    NODE_ID = "colabfold_batch"
    DISPLAY_NAME = "ColabFold Batch"
    CATEGORY = "ai"
    DESCRIPTION = "Predict protein structures with source-pinned ColabFold 1.5.5."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "ColabFold",
        "AlphaFold",
        "protein folding",
        "MMseqs2",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("prediction_dir",)
    REQUIRED_EXECUTABLES = ["colabfold_batch"]
    REQUIRED_CONDA_PACKAGES = ["colabfold"]
    CONDA_PACKAGE_CONSTRAINTS = {"colabfold": "1.5.5"}
    VERSION = "1.5.5"
    GIT_URL = "https://github.com/sokrypton/ColabFold.git"
    GIT_COMMIT = "675f93a44eee6589a003164b047e7d4183073d1e"
    SOURCE_TAG = "v1.5.5"
    DOCUMENTATION_URL = "https://github.com/sokrypton/ColabFold/tree/v1.5.5#running-colabfold"
    UPSTREAM_SOURCE = "README.md; pyproject.toml; colabfold/batch.py; colabfold/download.py"
    PACKAGE_CONSTRAINT = "Bioconda colabfold=1.5.5; upstream Python range >=3.9,<3.12"
    ENVIRONMENT = {
        "package": "colabfold=1.5.5",
        "python": ">=3.9,<3.12",
        "platform": "linux-64",
        "msa_api": "https://api.colabfold.com when explicitly acknowledged",
        "model_weights": "downloaded implicitly by colabfold_batch when absent",
    }
    SHELL = False
    EXPERIMENTAL = True
    EXIT_SEMANTICS = (
        "ColabFold exit code 0 is accepted only when every input query has a non-empty A3M in MSA-only "
        "mode, or its own done marker and non-empty relaxed/unrelaxed PDB in prediction mode."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "fasta": (
                    "FASTA",
                    {"default": "", "description": "Protein FASTA used when no precomputed A3M is supplied"},
                ),
                "precomputed_msa": (
                    "FILE",
                    {"default": "", "description": "A3M input that avoids a public MSA API query"},
                ),
                "allow_public_msa_api": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Acknowledge submission of sequences to the public ColabFold MSA service",
                    },
                ),
                "msa_only": ("BOOLEAN", {"default": False, "advanced": True}),
                "msa_mode": (
                    "STRING",
                    {
                        "default": "mmseqs2_uniref_env",
                        "options": ["mmseqs2_uniref_env", "mmseqs2_uniref", "single_sequence"],
                    },
                ),
                "model_type": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": [
                            "auto",
                            "alphafold2",
                            "alphafold2_ptm",
                            "alphafold2_multimer_v1",
                            "alphafold2_multimer_v2",
                            "alphafold2_multimer_v3",
                            "deepfold_v1",
                        ],
                    },
                ),
                "num_models": ("INT", {"default": 5, "min": 1, "max": 5}),
                "num_recycle": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Zero uses the upstream model default"},
                ),
                "random_seed": ("INT", {"default": 0, "min": 0, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        fasta = path_value(inputs.get("fasta"))
        precomputed_msa = path_value(inputs.get("precomputed_msa"))
        if not fasta and not precomputed_msa:
            return "Provide at least one of 'fasta' or 'precomputed_msa'"
        if fasta and precomputed_msa:
            return "Inputs 'fasta' and 'precomputed_msa' are mutually exclusive"
        if fasta and Path(fasta).suffix.lower() not in {".fa", ".faa", ".fasta"}:
            return "Input 'fasta' must use a ColabFold-supported .fa, .faa, or .fasta suffix"
        if precomputed_msa and Path(precomputed_msa).suffix.lower() != ".a3m":
            return "Input 'precomputed_msa' must use the .a3m suffix"
        input_path = Path(precomputed_msa or fasta)
        if input_path.exists():
            try:
                cls._expected_job_names(inputs)
            except (OSError, ValueError) as exc:
                return str(exc)
        msa_mode = str(inputs.get("msa_mode", "mmseqs2_uniref_env"))
        if msa_mode not in {"mmseqs2_uniref_env", "mmseqs2_uniref", "single_sequence"}:
            return "Input 'msa_mode' is not supported by ColabFold 1.5.5"
        if inputs.get("msa_only", False) and precomputed_msa:
            return "Input 'msa_only' cannot be combined with an already precomputed MSA"
        if not precomputed_msa and msa_mode != "single_sequence" and not inputs.get("allow_public_msa_api", False):
            return "Set 'allow_public_msa_api' or provide 'precomputed_msa' to avoid implicit sequence submission"
        model_type = str(inputs.get("model_type", "auto"))
        if model_type not in {
            "auto",
            "alphafold2",
            "alphafold2_ptm",
            "alphafold2_multimer_v1",
            "alphafold2_multimer_v2",
            "alphafold2_multimer_v3",
            "deepfold_v1",
        }:
            return "Input 'model_type' is not supported by ColabFold 1.5.5"
        validation = validate_int(inputs.get("num_models", 5), "num_models", minimum=1, maximum=5)
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("num_recycle", 0), "num_recycle", minimum=0)
        if validation is not True:
            return validation
        return validate_int(inputs.get("random_seed", 0), "random_seed", minimum=0)

    @staticmethod
    def _safe_job_name(value: str) -> str:
        return "".join(char if char.isalnum() or char in {"_", ".", "-"} else "_" for char in value)

    @classmethod
    def _expected_job_names(cls, inputs: dict[str, Any]) -> list[str]:
        precomputed_msa = path_value(inputs.get("precomputed_msa"))
        fasta = path_value(inputs.get("fasta"))
        input_path = Path(precomputed_msa or fasta)
        if not input_path.is_file():
            raise ValueError(f"ColabFold input file does not exist: {input_path}")

        if precomputed_msa:
            raw_names = [input_path.stem]
        else:
            raw_names = [
                line.strip()[1:]
                for line in input_path.read_text(encoding="utf-8").splitlines()
                if line.strip().startswith(">")
            ]
            if not raw_names:
                raise ValueError("Input FASTA contains no query records")

        job_names = [cls._safe_job_name(name) for name in raw_names]
        if any(not name for name in job_names):
            raise ValueError("ColabFold query names must not be empty after filename sanitisation")
        if len(set(job_names)) != len(job_names):
            raise ValueError("ColabFold query names must remain unique after filename sanitisation")
        return job_names

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / "predictions"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        result_dir = Path(path_value(inputs.get("output"))) / "predictions"
        input_path = path_value(inputs.get("precomputed_msa")) or path_value(inputs.get("fasta"))
        command = [
            "colabfold_batch",
            input_path,
            str(result_dir),
            "--overwrite-existing-results",
        ]
        if not path_value(inputs.get("precomputed_msa")):
            command.extend(["--msa-mode", str(inputs.get("msa_mode", "mmseqs2_uniref_env"))])
        if inputs.get("msa_only", False):
            command.append("--msa-only")
        else:
            command.extend(
                [
                    "--model-type",
                    str(inputs.get("model_type", "auto")),
                    "--num-models",
                    str(inputs.get("num_models", 5)),
                    "--random-seed",
                    str(inputs.get("random_seed", 0)),
                ]
            )
            if int(inputs.get("num_recycle", 0)):
                command.extend(["--num-recycle", str(inputs["num_recycle"])])
        return command

    @classmethod
    def VALIDATE_RESULT_DIRECTORY(
        cls,
        result_dir: str | Path,
        *,
        msa_only: bool,
        expected_job_names: Sequence[str] | None = None,
    ) -> bool | str:
        path = Path(result_dir)
        if not path.is_dir():
            return "ColabFold did not create its prediction directory"
        if expected_job_names is not None:
            expected = list(expected_job_names)
            if not expected:
                return "ColabFold input contains no queries"
            if msa_only:
                missing = [
                    job_name
                    for job_name in expected
                    if not (path / f"{job_name}.a3m").is_file()
                    or (path / f"{job_name}.a3m").stat().st_size == 0
                ]
                if missing:
                    return f"ColabFold MSA-only mode did not complete query(s): {', '.join(missing)}"
                return True

            incomplete: list[str] = []
            for job_name in expected:
                has_done_marker = (path / f"{job_name}.done.txt").is_file()
                pdb_candidates = [
                    *path.glob(f"{job_name}_unrelaxed_*.pdb"),
                    *path.glob(f"{job_name}_relaxed_*.pdb"),
                ]
                has_pdb = any(candidate.is_file() and candidate.stat().st_size > 0 for candidate in pdb_candidates)
                if not has_done_marker or not has_pdb:
                    incomplete.append(job_name)
            if incomplete:
                return f"ColabFold prediction mode did not complete query(s): {', '.join(incomplete)}"
            return True
        if msa_only:
            if not any(path.rglob("*.a3m")):
                return "ColabFold MSA-only mode did not create an A3M file"
            return True
        if not any(path.rglob("*.pdb")):
            return "ColabFold prediction mode did not create a PDB file"
        if not any(path.rglob("*.done.txt")):
            return "ColabFold prediction mode did not create an upstream done marker"
        return True

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        expected_job_names = self.__class__._expected_job_names(kwargs)
        result = await super().run(**kwargs)
        paths = tuple(result)
        validation = self.__class__.VALIDATE_RESULT_DIRECTORY(
            paths[0],
            msa_only=bool(kwargs.get("msa_only", False)),
            expected_job_names=expected_job_names,
        )
        if validation is not True:
            raise RuntimeError(str(validation))
        return paths
