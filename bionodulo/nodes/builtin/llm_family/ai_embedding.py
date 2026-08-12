"""Local, deterministic, or explicit API embedding generation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from bionodulo.core.credentials import resolve_secret_value
from bionodulo.nodes.base import BaseNode

from .adapter import _node_output_dir, require_artifacts, validate_choice


class AIEmbeddingNode(BaseNode):
    """Generate embedding vectors for biological sequences or text."""

    NODE_ID = "ai_embedding"
    DISPLAY_NAME = "AI Embedding"
    CATEGORY = "ai"
    DESCRIPTION = (
        "Generate embedding vectors for biological sequences or text using transformer models "
        "or a deterministic local fallback."
    )
    SEARCH_ALIASES = ["embedding", "vector", "esm", "dnabert", "transformer", "representation", "encode", "features"]
    RETURN_TYPES = ("EMBEDDING", "JSON")
    RETURN_NAMES = ("embeddings_npy", "metadata_json")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["numpy", "biopython", "torch", "transformers", "litellm"]
    EXPERIMENTAL = True
    VERSION = "4.57.1"
    DOCUMENTATION_URL = "https://huggingface.co/docs/transformers/v4.57.1/en/model_doc/auto"
    GIT_URL = "https://github.com/huggingface/transformers"
    GIT_COMMIT = "8cb5963cc22174954e7dca2c0a3320b7dc2f4edc"
    AUDIT_STATUS = "contract-checked-no-model-execution"
    CITATION_URLS = [
        "https://huggingface.co/docs/transformers/v4.57.1/en/model_doc/auto",
        "https://github.com/huggingface/transformers",
    ]
    ENVIRONMENT = {
        "package_constraints": {
            "biopython": "1.87",
            "numpy": "2.4.4",
            "transformers": "4.57.1",
            "litellm": "1.87.1",
        }
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_data": (
                    "STRING",
                    {"default": "", "multiline": True, "description": "FASTA path, text path, or raw text/sequences"},
                ),
                "embedding_model": (
                    "STRING",
                    {
                        "default": "esm2_t6_8M",
                        "options": list(_EMBEDDING_MODEL_REGISTRY),
                    },
                ),
            },
            "optional": {
                "molecule_type": ("STRING", {"default": "auto", "options": ["auto", "protein", "dna", "rna", "text"]}),
                "batch_size": ("INT", {"default": 8, "min": 1, "max": 64}),
                "max_length": ("INT", {"default": 512, "min": 1, "max": 4096}),
                "pooling": ("STRING", {"default": "mean", "options": ["mean", "cls", "max"]}),
                "layer": ("INT", {"default": -1, "min": -33, "max": 36}),
                "normalize": ("BOOLEAN", {"default": True}),
                "compute_device": ("STRING", {"default": "auto", "options": ["auto", "cpu", "cuda", "mps"]}),
                "fallback_backend": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": ["auto", "local", "api", "deterministic_fixture"],
                        "description": (
                            "auto/local failures are fatal; deterministic_fixture is an explicit "
                            "non-scientific workflow-test backend"
                        ),
                    },
                ),
                "api_key": ("STRING", {"default": "", "password": True, "advanced": True}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        out_dir = _node_output_dir(self, context)
        npy_path = out_dir / "embeddings.npy"
        metadata_path = out_dir / "metadata.json"

        input_data = str(kwargs.get("input_data", "") or "")
        embedding_model = validate_choice(
            kwargs.get("embedding_model", "esm2_t6_8M"),
            "embedding_model",
            tuple(_EMBEDDING_MODEL_REGISTRY),
        )
        molecule_type = validate_choice(
            kwargs.get("molecule_type", "auto"),
            "molecule_type",
            ("auto", "protein", "dna", "rna", "text"),
        )
        batch_size = max(1, int(kwargs.get("batch_size", 8) or 8))
        max_length = max(1, int(kwargs.get("max_length", 512) or 512))
        pooling = validate_choice(kwargs.get("pooling", "mean"), "pooling", ("mean", "cls", "max"))
        layer_value = kwargs.get("layer", -1)
        layer = -1 if layer_value is None else int(layer_value)
        normalize = bool(kwargs.get("normalize", True))
        compute_device = validate_choice(
            kwargs.get("compute_device", "auto"),
            "compute_device",
            ("auto", "cpu", "cuda", "mps"),
        )
        fallback_backend = validate_choice(
            kwargs.get("fallback_backend", "auto"),
            "fallback_backend",
            ("auto", "local", "api", "deterministic_fixture"),
        )
        api_key = resolve_secret_value(
            kwargs.get("api_key", ""),
            context,
            "llm_api_key",
            "openai_api_key",
            default=os.environ.get("OPENAI_API_KEY", ""),
        )
        if fallback_backend == "api" and not api_key:
            raise ValueError("api_key is required for the API embedding backend")

        records = _embedding_records(input_data, molecule_type=molecule_type, max_length=max_length)
        if not records:
            embeddings = _empty_embedding_array()
            metadata = _embedding_metadata(
                records=[],
                embeddings=embeddings,
                embedding_model=embedding_model,
                model_name=str(_EMBEDDING_MODEL_REGISTRY[embedding_model]["model"]),
                model_revision=str(_EMBEDDING_MODEL_REGISTRY[embedding_model]["revision"]),
                molecule_type=molecule_type,
                pooling=pooling,
                layer=layer,
                normalize=normalize,
                compute_device=compute_device,
                backend="empty",
                status="NO_INPUT_RECORDS",
            )
        else:
            embeddings, backend, model_name, model_revision, device, status = await _generate_embeddings(
                [record["sequence"] for record in records],
                embedding_model=embedding_model,
                batch_size=batch_size,
                max_length=max_length,
                pooling=pooling,
                layer=layer,
                normalize=normalize,
                compute_device=compute_device,
                fallback_backend=fallback_backend,
                api_key=api_key,
            )
            metadata = _embedding_metadata(
                records=records,
                embeddings=embeddings,
                embedding_model=embedding_model,
                model_name=model_name,
                model_revision=model_revision,
                molecule_type=molecule_type,
                pooling=pooling,
                layer=layer,
                normalize=normalize,
                compute_device=device,
                backend=backend,
                status=status,
            )

        np = _numpy()
        np.save(npy_path, embeddings)
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        require_artifacts(npy_path, metadata_path)
        return {"outputs": {"embeddings_npy": str(npy_path), "metadata_json": str(metadata_path)}}


_EMBEDDING_MODEL_REGISTRY: dict[str, dict[str, str]] = {
    "esm2_t6_8M": {
        "model": "facebook/esm2_t6_8M_UR50D",
        "revision": "c731040fcd8d73dceaa04b0a8e6329b345b0f5df",
        "url": "https://huggingface.co/facebook/esm2_t6_8M_UR50D",
    },
    "esm2_t12_35M": {
        "model": "facebook/esm2_t12_35M_UR50D",
        "revision": "6fbf070e65b0b7291e7bbcd451118c216cff79d8",
        "url": "https://huggingface.co/facebook/esm2_t12_35M_UR50D",
    },
    "esm2_t30_150M": {
        "model": "facebook/esm2_t30_150M_UR50D",
        "revision": "a695f6045e2e32885fa60af20c13cb35398ce30c",
        "url": "https://huggingface.co/facebook/esm2_t30_150M_UR50D",
    },
    "esm2_t33_650M": {
        "model": "facebook/esm2_t33_650M_UR50D",
        "revision": "08e4846e537177426273712802403f7ba8261b6c",
        "url": "https://huggingface.co/facebook/esm2_t33_650M_UR50D",
    },
    "text_embedding": {
        "model": "text-embedding-3-small",
        "revision": "provider-managed",
        "url": "https://platform.openai.com/docs/models/text-embedding-3-small",
    },
}


_DETERMINISTIC_EMBEDDING_DIM = 32
_FIXTURE_MODEL_ID = "product-native/non-scientific-sha256-fixture-v1"
_FIXTURE_REVISION = "1"


def _numpy() -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("AI Embedding requires numpy. Install the numpy package.") from exc
    return np


def _empty_embedding_array() -> Any:
    return _numpy().zeros((0, 0), dtype="float32")


def _embedding_records(input_data: str, *, molecule_type: str, max_length: int) -> list[dict[str, Any]]:
    text = str(input_data or "")
    if not text.strip():
        return []

    if _looks_like_fasta(text, None):
        return _parse_fasta_embedding_records(text, max_length=max_length)

    path = _candidate_input_path(text)
    if path is not None and path.exists():
        content = path.read_text(encoding="utf-8-sig")
        if _looks_like_fasta(content, path):
            return _parse_fasta_embedding_records(content, max_length=max_length)
        return _plain_embedding_records(content, id_prefix="item", max_length=max_length)

    id_prefix = "text" if molecule_type == "text" and "\n\n" in text else "item"
    return _plain_embedding_records(text, id_prefix=id_prefix, max_length=max_length)


def _candidate_input_path(text: str) -> Path | None:
    if "\n" in text or "\r" in text:
        return None
    try:
        return Path(text).expanduser()
    except (OSError, ValueError):
        return None


def _looks_like_fasta(content: str, path: Path | None) -> bool:
    if path is not None and path.suffix.lower() in {".fa", ".faa", ".fasta", ".fna"}:
        return True
    return str(content).lstrip().startswith(">")


def _parse_fasta_embedding_records(content: str, *, max_length: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current_id = ""
    current_description = ""
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_id, current_description, current_lines
        if not current_id:
            return
        sequence = "".join(current_lines).replace(" ", "").replace("\t", "")
        if sequence:
            truncated = sequence[:max_length]
            records.append(
                {
                    "id": current_id,
                    "description": current_description,
                    "sequence": truncated,
                    "original_length": len(sequence),
                    "truncated_length": len(truncated),
                }
            )
        current_id = ""
        current_description = ""
        current_lines = []

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            flush()
            current_description = stripped[1:].strip()
            current_id = current_description.split()[0] if current_description else f"seq_{len(records)}"
        elif current_id:
            current_lines.append(stripped)
    flush()
    return records


def _plain_embedding_records(content: str, *, id_prefix: str, max_length: int) -> list[dict[str, Any]]:
    chunks = [
        line.strip() for line in str(content or "").splitlines() if line.strip() and not line.lstrip().startswith(">")
    ]
    records: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        truncated = chunk[:max_length]
        records.append(
            {
                "id": f"{id_prefix}_{index}",
                "description": f"{id_prefix}_{index}",
                "sequence": truncated,
                "original_length": len(chunk),
                "truncated_length": len(truncated),
            }
        )
    return records


async def _generate_embeddings(
    sequences: list[str],
    *,
    embedding_model: str,
    batch_size: int,
    max_length: int,
    pooling: str,
    layer: int,
    normalize: bool,
    compute_device: str,
    fallback_backend: str,
    api_key: str,
) -> tuple[Any, str, str, str, str, str]:
    model_spec = _EMBEDDING_MODEL_REGISTRY[embedding_model]
    model_name = str(model_spec["model"])
    model_revision = str(model_spec["revision"])
    if fallback_backend == "api":
        if embedding_model != "text_embedding":
            raise ValueError("The API embedding backend is only supported for text_embedding")
        embeddings, provider = await _api_text_embeddings(
            sequences,
            model_name=model_name,
            batch_size=batch_size,
            api_key=api_key,
        )
        if normalize:
            embeddings = _normalize_embeddings(embeddings)
        return (
            embeddings,
            f"api:{provider}",
            model_name,
            model_revision,
            "remote",
            "REMOTE_PROVIDER_MODEL_NOT_BIT_REPRODUCIBLE",
        )

    if fallback_backend == "deterministic_fixture":
        embeddings = _deterministic_embeddings(sequences)
        if normalize:
            embeddings = _normalize_embeddings(embeddings)
        return (
            embeddings,
            "deterministic_fixture",
            _FIXTURE_MODEL_ID,
            _FIXTURE_REVISION,
            "cpu",
            "NON_SCIENTIFIC_FIXTURE_ONLY",
        )

    if embedding_model == "text_embedding":
        if fallback_backend == "local":
            raise ValueError("text_embedding has no local checkpoint contract; select the api backend")
        if not api_key:
            raise ValueError(
                "auto selected the text embedding API, but no api_key is available; "
                "provide credentials or explicitly select deterministic_fixture"
            )
        embeddings, provider = await _api_text_embeddings(
            sequences,
            model_name=model_name,
            batch_size=batch_size,
            api_key=api_key,
        )
        if normalize:
            embeddings = _normalize_embeddings(embeddings)
        return (
            embeddings,
            f"api:{provider}",
            model_name,
            model_revision,
            "remote",
            "REMOTE_PROVIDER_MODEL_NOT_BIT_REPRODUCIBLE",
        )

    # Both auto and local resolve to the same immutable local-model operation.
    # Import, cache, configuration, and inference failures intentionally escape.
    embeddings, device = _local_transformer_embeddings(
        sequences,
        model_name=model_name,
        revision=model_revision,
        batch_size=batch_size,
        max_length=max_length,
        pooling=pooling,
        layer=layer,
        compute_device=compute_device,
    )
    if normalize:
        embeddings = _normalize_embeddings(embeddings)
    return (
        embeddings,
        "local_revision_pinned_transformer",
        model_name,
        model_revision,
        device,
        "IMMUTABLE_MODEL_REVISION",
    )


async def _api_text_embeddings(
    sequences: list[str],
    *,
    model_name: str,
    batch_size: int,
    api_key: str,
) -> tuple[Any, str]:
    import litellm

    np = _numpy()
    vectors: list[list[float]] = []
    for offset in range(0, len(sequences), max(1, batch_size)):
        batch = sequences[offset : offset + max(1, batch_size)]
        response = await litellm.aembedding(model=model_name, input=batch, api_key=api_key)
        data = response.get("data", []) if isinstance(response, dict) else getattr(response, "data", [])
        for item in data:
            embedding = item.get("embedding") if isinstance(item, dict) else getattr(item, "embedding", None)
            if embedding is None:
                raise RuntimeError("Embedding API response did not include an embedding vector")
            vectors.append([float(value) for value in embedding])
    return np.asarray(vectors, dtype="float32"), "litellm"


def _local_transformer_embeddings(
    sequences: list[str],
    *,
    model_name: str,
    revision: str,
    batch_size: int,
    max_length: int,
    pooling: str,
    layer: int,
    compute_device: str,
) -> tuple[Any, str]:
    np = _numpy()
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("torch and transformers are required for local transformer embeddings") from exc

    device = compute_device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    load_args = {"revision": revision, "trust_remote_code": False, "local_files_only": True}
    tokenizer = AutoTokenizer.from_pretrained(model_name, **load_args)
    model = AutoModel.from_pretrained(model_name, **load_args)
    model = model.to(device)
    model.eval()

    batches = []
    with torch.no_grad():
        for offset in range(0, len(sequences), batch_size):
            batch = sequences[offset : offset + batch_size]
            inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=max_length)
            inputs = {key: value.to(device) for key, value in inputs.items()}
            outputs = model(**inputs, output_hidden_states=True)
            hidden = outputs.last_hidden_state if layer == -1 else outputs.hidden_states[layer]
            mask = inputs["attention_mask"].unsqueeze(-1).float()
            if pooling == "cls":
                pooled = hidden[:, 0]
            elif pooling == "max":
                masked = hidden * mask + (1 - mask) * (-1e9)
                pooled = masked.max(dim=1).values
            else:
                pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            batches.append(pooled.cpu().numpy())
    return np.vstack(batches) if batches else _empty_embedding_array(), str(device)


def _deterministic_embeddings(sequences: list[str]) -> Any:
    np = _numpy()
    vectors = []
    for sequence in sequences:
        vector = np.zeros(_DETERMINISTIC_EMBEDDING_DIM, dtype="float32")
        for index, byte in enumerate(str(sequence).encode("utf-8")):
            vector[index % _DETERMINISTIC_EMBEDDING_DIM] += float(byte) / 255.0
        vector[-1] = float(len(str(sequence))) / max(1.0, _DETERMINISTIC_EMBEDDING_DIM)
        vectors.append(vector)
    return np.vstack(vectors) if vectors else _empty_embedding_array()


def _normalize_embeddings(embeddings: Any) -> Any:
    np = _numpy()
    if embeddings.size == 0:
        return embeddings
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return embeddings / norms


def _embedding_metadata(
    *,
    records: list[dict[str, Any]],
    embeddings: Any,
    embedding_model: str,
    model_name: str,
    model_revision: str,
    molecule_type: str,
    pooling: str,
    layer: int,
    normalize: bool,
    compute_device: str,
    backend: str,
    status: str,
) -> dict[str, Any]:
    shape = list(embeddings.shape) if hasattr(embeddings, "shape") else [0, 0]
    return {
        "backend": backend,
        "status": status,
        "scientific_embedding": False if backend == "deterministic_fixture" else None,
        "embedding_model": embedding_model,
        "model_name": model_name,
        "model_revision": model_revision,
        "molecule_type": molecule_type,
        "sequence_count": len(records),
        "sequence_ids": [str(record.get("id", "")) for record in records],
        "original_lengths": [int(record.get("original_length", 0)) for record in records],
        "truncated_lengths": [int(record.get("truncated_length", 0)) for record in records],
        "embedding_shape": shape,
        "embedding_dim": shape[1] if len(shape) > 1 else 0,
        "pooling": pooling,
        "layer": layer,
        "normalize": normalize,
        "device": compute_device,
        "disclaimer": (
            "NON-SCIENTIFIC FIXTURE: SHA-derived vectors are workflow-test artifacts, not model embeddings."
            if backend == "deterministic_fixture"
            else "Model identity and backend status are recorded; downstream scientific validity remains user-owned."
        ),
    }
