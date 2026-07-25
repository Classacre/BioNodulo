"""ProteinMPNN commit-pinned sequence-design contract."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .adapter import path_value, validate_int


class ProteinMPNNDesignNode(CommandNode):
    """Design sequences from one PDB using a complete pinned repository bundle."""

    NODE_ID = "proteinmpnn_design"
    DISPLAY_NAME = "ProteinMPNN Design"
    CATEGORY = "ai"
    DESCRIPTION = "Design protein sequences with a complete source-pinned ProteinMPNN repository bundle."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "ProteinMPNN",
        "inverse folding",
        "protein design",
        "sequence design",
    ]
    RETURN_TYPES = ("DIRECTORY", "FASTA")
    RETURN_NAMES = ("design_dir", "designed_sequences")
    REQUIRED_EXECUTABLES = ["python"]
    REQUIRED_CONDA_PACKAGES = ["numpy", "pytorch"]
    VERSION = "git-8907e6671bfb"
    GIT_URL = "https://github.com/dauparas/ProteinMPNN.git"
    GIT_COMMIT = "8907e6671bfbfc92303b5f79c4b5e6ce47cdef57"
    DOCUMENTATION_URL = "https://github.com/dauparas/ProteinMPNN/tree/8907e6671bfbfc92303b5f79c4b5e6ce47cdef57"
    UPSTREAM_SOURCE = "README.md; protein_mpnn_run.py; protein_mpnn_utils.py; bundled v_48_020 weights"
    PACKAGE_CONSTRAINT = (
        "external complete ProteinMPNN repository bundle at commit "
        "8907e6671bfbfc92303b5f79c4b5e6ce47cdef57 with NumPy and PyTorch"
    )
    ENVIRONMENT = {
        "provisioning": "external_repository_bundle",
        "repository_commit": "8907e6671bfbfc92303b5f79c4b5e6ce47cdef57",
        "model": "v_48_020",
        "seed_zero": "upstream selects a random seed from NumPy; non-deterministic",
    }
    EXPECTED_WEIGHT_SHA256 = {
        "vanilla": "c9cb4a671d79604111231f8dbfc7c590e06f1197453b7a6854ac6661a642f5bd",
        "ca_only": "f28f40170e21858c5ff31ef50b6e63414ff76dc331b19f85aa8586a12031744a",
        "soluble": "7af52d090172c230c7f0e9d21e02203f6b3a38b16db58d3c7a3960e0a9a6e31a",
    }
    EXPECTED_SOURCE_SHA256 = {
        "protein_mpnn_run.py": "61f2c519a7f73fa12da9eb90da97b97ec2f8d5f31d42605639c7600cbd321cbe",
        "protein_mpnn_utils.py": "74c8f9b7553422a7a0bbd705874844ee103c8926c2c96f154a87e0b824071e1b",
    }
    MODEL_NAME = "v_48_020"
    SHELL = False
    EXPERIMENTAL = True
    EXIT_SEMANTICS = (
        "ProteinMPNN exit code 0 plus the native seqs/<PDB stem>.fa is success. The requested sequence count "
        "must be divisible by batch size; seed 0 intentionally retains upstream nondeterminism."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "repository_dir": (
                    "DIRECTORY",
                    {"description": "Complete ProteinMPNN checkout with source and bundled model weights"},
                ),
                "pdb_path": ("FILE", {"description": "Input backbone PDB"}),
            },
            "optional": {
                "pdb_path_chains": ("STRING", {"default": "", "advanced": True}),
                "num_seq_per_target": ("INT", {"default": 1, "min": 1}),
                "batch_size": ("INT", {"default": 1, "min": 1}),
                "sampling_temp": (
                    "STRING",
                    {"default": "0.1", "description": "One or more positive whitespace-separated temperatures"},
                ),
                "ca_only": ("BOOLEAN", {"default": False, "advanced": True}),
                "use_soluble_model": ("BOOLEAN", {"default": False, "advanced": True}),
                "seed": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Zero asks upstream to choose a random seed"},
                ),
                "save_score": ("BOOLEAN", {"default": False, "advanced": True}),
                "save_probs": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _mode(cls, inputs: dict[str, Any]) -> str:
        if inputs.get("ca_only", False):
            return "ca_only"
        if inputs.get("use_soluble_model", False):
            return "soluble"
        return "vanilla"

    @classmethod
    def _weight_path(cls, repository: Path, mode: str) -> Path:
        folder = {
            "vanilla": "vanilla_model_weights",
            "ca_only": "ca_model_weights",
            "soluble": "soluble_model_weights",
        }[mode]
        return repository / folder / f"{cls.MODEL_NAME}.pt"

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def _validate_repository(cls, repository: Path, mode: str) -> bool | str:
        if not repository.is_dir():
            return "Input 'repository_dir' must be an existing directory"
        for relative, expected in cls.EXPECTED_SOURCE_SHA256.items():
            source_path = repository / relative
            if not source_path.is_file():
                return f"ProteinMPNN repository bundle is missing {relative}"
            if cls._sha256(source_path) != expected:
                return f"ProteinMPNN source hash does not match pinned commit for {relative}"
        weight_path = cls._weight_path(repository, mode)
        if not weight_path.is_file():
            return f"ProteinMPNN repository bundle is missing {weight_path.relative_to(repository)}"
        expected = cls.EXPECTED_WEIGHT_SHA256[mode]
        if cls._sha256(weight_path) != expected:
            return f"ProteinMPNN {mode} {cls.MODEL_NAME} weight hash does not match the pinned bundle"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        repository_value = path_value(inputs.get("repository_dir"))
        pdb_value = path_value(inputs.get("pdb_path"))
        if not repository_value:
            return "Input 'repository_dir' must be a non-empty path-like value"
        if not pdb_value:
            return "Input 'pdb_path' must be a non-empty path-like value"
        if not Path(pdb_value).is_file():
            return "Input 'pdb_path' must be an existing file"
        if inputs.get("ca_only", False) and inputs.get("use_soluble_model", False):
            return "ProteinMPNN does not provide a combined CA-only soluble model"
        num_sequences = inputs.get("num_seq_per_target", 1)
        batch_size = inputs.get("batch_size", 1)
        validation = validate_int(num_sequences, "num_seq_per_target", minimum=1)
        if validation is not True:
            return validation
        validation = validate_int(batch_size, "batch_size", minimum=1)
        if validation is not True:
            return validation
        if num_sequences % batch_size:
            return "Input 'num_seq_per_target' must be divisible by 'batch_size'"
        temperatures = str(inputs.get("sampling_temp", "0.1") or "").split()
        if not temperatures:
            return "Input 'sampling_temp' must contain at least one positive number"
        try:
            if any(float(value) <= 0 for value in temperatures):
                raise ValueError
        except ValueError:
            return "Input 'sampling_temp' must contain only positive numbers"
        validation = validate_int(inputs.get("seed", 0), "seed", minimum=0)
        if validation is not True:
            return validation
        return cls._validate_repository(Path(repository_value), cls._mode(inputs))

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        pdb_stem = Path(path_value(inputs.get("pdb_path"))).stem
        return [node_dir, node_dir / "seqs" / f"{pdb_stem}.fa"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        repository = Path(path_value(inputs.get("repository_dir")))
        command = [
            "python",
            str(repository / "protein_mpnn_run.py"),
            "--pdb_path",
            path_value(inputs.get("pdb_path")),
            "--out_folder",
            path_value(inputs.get("output")),
            "--num_seq_per_target",
            str(inputs.get("num_seq_per_target", 1)),
            "--batch_size",
            str(inputs.get("batch_size", 1)),
            "--sampling_temp",
            str(inputs.get("sampling_temp", "0.1")),
            "--model_name",
            cls.MODEL_NAME,
            "--seed",
            str(inputs.get("seed", 0)),
        ]
        chains = str(inputs.get("pdb_path_chains", "") or "").strip()
        if chains:
            command.extend(["--pdb_path_chains", chains])
        if inputs.get("ca_only", False):
            command.append("--ca_only")
        if inputs.get("use_soluble_model", False):
            command.append("--use_soluble_model")
        if inputs.get("save_score", False):
            command.extend(["--save_score", "1"])
        if inputs.get("save_probs", False):
            command.extend(["--save_probs", "1"])
        return command
