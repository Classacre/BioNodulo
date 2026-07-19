"""fair-esm 2.0.0 ESMFold API-wrapper contract."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from .adapter import PythonScriptNode, validate_int


class ESMFoldPredictNode(PythonScriptNode):
    """Predict one PDB per validated FASTA record with the official ESMFold API."""

    NODE_ID = "esmfold_predict"
    DISPLAY_NAME = "ESMFold Predict"
    CATEGORY = "ai"
    DESCRIPTION = "Predict protein structures with the fair-esm 2.0.0 ESMFold API."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "ESMFold",
        "ESM",
        "protein folding",
        "single sequence",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("pdb_dir",)
    REQUIRED_EXECUTABLES = ["python"]
    REQUIRED_CONDA_PACKAGES: list[str] = []
    CONDA_PACKAGE_CONSTRAINTS = {"python": "<=3.9", "fair-esm": "2.0.0", "pytorch": "1.12.*"}
    VERSION = "2.0.0"
    GIT_URL = "https://github.com/facebookresearch/esm.git"
    GIT_COMMIT = "0b59d87ebef95948c735b1f7aad463dc6dfa991b"
    SOURCE_TAG = "v2.0.0"
    DOCUMENTATION_URL = "https://github.com/facebookresearch/esm/tree/v2.0.0#esmfold"
    UPSTREAM_SOURCE = "README.md; environment.yml; scripts/esmfold_inference.py; esm/pretrained.py"
    PACKAGE_CONSTRAINT = (
        "fair-esm==2.0.0 with Python<=3.9, PyTorch 1.12, CUDA/nvcc, dllogger, and OpenFold "
        "commit 4b41059694619831a7db195b7e0988fc4ff3a307"
    )
    ENVIRONMENT = {
        "provisioning": "external_gpu_python_environment",
        "python": "<=3.9",
        "fair-esm": "2.0.0",
        "pytorch": "1.12.*",
        "openfold_commit": "4b41059694619831a7db195b7e0988fc4ff3a307",
        "cuda": "required for GPU and CPU-offload modes; nvcc required to install OpenFold",
        "model_weights": "esmfold_v1 downloaded implicitly through the PyTorch cache when absent",
    }
    OUTPUT_FILENAMES = ("pdb",)
    SCRIPT_FILENAME = "esmfold_predict.py"
    REQUIRED_PATH_INPUTS = ("fasta",)
    EXPERIMENTAL = True
    EXIT_SEMANTICS = (
        "Python exit code 0 plus exactly one PDB for every safe unique FASTA header is success; "
        "unsafe/duplicate headers, model errors, partial batches, or extra/missing PDBs fail the node."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fasta": ("FASTA", {"description": "Protein FASTA with safe unique record headers"}),
            },
            "optional": {
                "num_recycles": ("INT", {"default": 4, "min": 0}),
                "max_tokens_per_batch": ("INT", {"default": 1024, "min": 1}),
                "chunk_size": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Zero disables axial-attention chunking"},
                ),
                "cpu_only": ("BOOLEAN", {"default": False, "advanced": True}),
                "cpu_offload": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if inputs.get("cpu_only", False) and inputs.get("cpu_offload", False):
            return "Inputs 'cpu_only' and 'cpu_offload' are mutually exclusive"
        validation = validate_int(inputs.get("num_recycles", 4), "num_recycles", minimum=0)
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("max_tokens_per_batch", 1024), "max_tokens_per_batch", minimum=1)
        if validation is not True:
            return validation
        return validate_int(inputs.get("chunk_size", 0), "chunk_size", minimum=0)

    @classmethod
    def build_script(cls, inputs: dict[str, Any], outputs: list[Path]) -> str:
        fasta = json.dumps(str(inputs.get("fasta", "")), ensure_ascii=True)
        pdb_dir = json.dumps(str(outputs[0]), ensure_ascii=True)
        chunk_size = int(inputs.get("chunk_size", 0))
        chunk_literal = repr(chunk_size or None)
        return textwrap.dedent(
            f"""\
            import re
            from pathlib import Path

            import torch
            import esm
            from esm.data import read_fasta


            def enable_cpu_offloading(model):
                from torch.distributed.fsdp import CPUOffload, FullyShardedDataParallel
                from torch.distributed.fsdp.wrap import enable_wrap, wrap

                torch.distributed.init_process_group(
                    backend="nccl", init_method="tcp://localhost:9999", world_size=1, rank=0
                )
                with enable_wrap(
                    wrapper_cls=FullyShardedDataParallel,
                    cpu_offload=CPUOffload(offload_params=True),
                ):
                    for layer_name, layer in model.layers.named_children():
                        setattr(model.layers, layer_name, wrap(layer))
                    return wrap(model)


            def init_model_on_gpu_with_cpu_offloading(model):
                model = model.eval()
                model_esm = enable_cpu_offloading(model.esm)
                del model.esm
                model.cuda()
                model.esm = model_esm
                return model


            def sequence_batches(sequences, max_tokens):
                headers, batch, token_count = [], [], 0
                for header, sequence in sequences:
                    if batch and token_count + len(sequence) > max_tokens:
                        yield headers, batch
                        headers, batch, token_count = [], [], 0
                    headers.append(header)
                    batch.append(sequence)
                    token_count += len(sequence)
                if batch:
                    yield headers, batch


            fasta_path = Path({fasta})
            pdb_path = Path({pdb_dir})
            sequences = list(read_fasta(fasta_path))
            if not sequences:
                raise ValueError("Input FASTA contains no protein records")
            safe_header = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*").fullmatch
            headers = [header for header, _sequence in sequences]
            invalid_headers = [header for header in headers if safe_header(header) is None]
            if invalid_headers:
                raise ValueError(f"Unsafe FASTA header(s): {{invalid_headers}}")
            if len(set(headers)) != len(headers):
                raise ValueError("FASTA headers must be unique")
            if any(not sequence for _header, sequence in sequences):
                raise ValueError("FASTA records must contain non-empty protein sequences")
            sequences.sort(key=lambda item: len(item[1]))
            pdb_path.mkdir(parents=True, exist_ok=False)

            model = esm.pretrained.esmfold_v1().eval()
            model.set_chunk_size({chunk_literal})
            if {bool(inputs.get("cpu_only", False))!r}:
                model.cpu()
            elif {bool(inputs.get("cpu_offload", False))!r}:
                model = init_model_on_gpu_with_cpu_offloading(model)
            else:
                model.cuda()

            for batch_headers, batch_sequences in sequence_batches(
                sequences, {int(inputs.get("max_tokens_per_batch", 1024))}
            ):
                output = model.infer(batch_sequences, num_recycles={int(inputs.get("num_recycles", 4))})
                output = {{key: value.cpu() for key, value in output.items()}}
                pdbs = model.output_to_pdb(output)
                if len(pdbs) != len(batch_headers):
                    raise RuntimeError("ESMFold returned a partial prediction batch")
                for header, pdb_string in zip(batch_headers, pdbs):
                    (pdb_path / f"{{header}}.pdb").write_text(pdb_string, encoding="utf-8")

            expected = {{f"{{header}}.pdb" for header in headers}}
            actual = {{path.name for path in pdb_path.glob("*.pdb")}}
            if actual != expected:
                raise RuntimeError(f"Expected PDB files {{sorted(expected)}}, found {{sorted(actual)}}")
            """
        )
