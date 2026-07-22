"""Fail-closed local text and biological-sequence model inference.

The node exposes two explicit contracts:

* a visibly non-scientific deterministic fixture for workflow testing; and
* a locally cached Hugging Face task-classification checkpoint addressed by a
  full immutable revision.

It never adds or resizes a classification head and never substitutes fixture
scores after a checkpoint load failure.  Zero-shot classification remains in
the saved-workflow enum for compatibility, but fails closed until it has a
separate immutable NLI contract.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode

from .adapter import _node_output_dir, require_artifacts, validate_choice
from .ai_embedding import (
    _candidate_input_path,
    _looks_like_fasta,
    _numpy,
    _parse_fasta_embedding_records,
)
from .ai_sequence_classification import (
    TRANSFORMERS_DOCUMENTATION_URL,
    TRANSFORMERS_MODELING_AUTO_SHA256,
    TRANSFORMERS_MODELING_UTILS_SHA256,
    TRANSFORMERS_SOURCE_COMMIT,
    TRANSFORMERS_SOURCE_URL,
    TRANSFORMERS_VERSION,
    _deterministic_classification_scores,
    _require_immutable_revision,
    _validate_loading_info,
    _validate_task_checkpoint_config,
)


FIXTURE_BACKEND = "deterministic_fixture"
LOCAL_BACKEND = "local"
FIXTURE_MODEL_ID = "product-native/non-scientific-model-inference-fixture-v1"
FIXTURE_STATUS = "NON_SCIENTIFIC_FIXTURE_ONLY"
LOCAL_STATUS = "USER_SUPPLIED_TASK_CHECKPOINT_NOT_VALIDATED_BY_BIONODULO"
FIXTURE_LABELS = (
    "fixture_bucket_0",
    "fixture_bucket_1",
    "fixture_bucket_2",
    "fixture_bucket_3",
)
_HF_MODEL_ID = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}$"
)


class ModelInferenceNode(BaseNode):
    """Run an explicit fixture or immutable user-supplied task classifier."""

    NODE_ID = "model_inference"
    DISPLAY_NAME = "Model Inference"
    CATEGORY = "ai"
    DESCRIPTION = (
        "Run a visibly non-scientific fixture or a locally cached, immutable, "
        "task-trained Hugging Face classification checkpoint."
    )
    SEARCH_ALIASES = [
        "model",
        "inference",
        "huggingface",
        "transformers",
        "predict",
        "classification",
        "sequence",
        "zero-shot",
    ]
    RETURN_TYPES = ("JSON", "CSV")
    RETURN_NAMES = ("predictions_json", "scores_csv")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["numpy", "torch", "transformers"]
    EXPERIMENTAL = True
    VERSION = TRANSFORMERS_VERSION
    DOCUMENTATION_URL = TRANSFORMERS_DOCUMENTATION_URL
    GIT_URL = TRANSFORMERS_SOURCE_URL
    GIT_COMMIT = TRANSFORMERS_SOURCE_COMMIT
    AUDIT_STATUS = "contract-checked-no-model-execution"
    SOURCE_AUTHORITIES = {
        "transformers_commit": TRANSFORMERS_SOURCE_COMMIT,
        "transformers_modeling_auto_sha256": TRANSFORMERS_MODELING_AUTO_SHA256,
        "transformers_modeling_utils_sha256": TRANSFORMERS_MODELING_UTILS_SHA256,
    }
    EXIT_SEMANTICS = (
        "Invalid inputs, unavailable checkpoints, incomplete or mismatched task heads, "
        "unsupported zero-shot mode, and inference errors fail the node. Only the "
        "explicit deterministic fixture may run without a model checkpoint."
    )
    ENVIRONMENT = {
        "package_constraints": {
            "numpy": "2.4.4",
            "transformers": TRANSFORMERS_VERSION,
        }
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_data": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "description": "Input file path, FASTA, or raw text",
                    },
                ),
                "model_name": (
                    "STRING",
                    {
                        "default": "",
                        "description": (
                            "Hugging Face namespace/model ID; required only for the local backend"
                        ),
                    },
                ),
                "task": (
                    "STRING",
                    {
                        "default": "text_classification",
                        "options": [
                            "text_classification",
                            "sequence_classification",
                            "zero_shot_classification",
                        ],
                    },
                ),
            },
            "optional": {
                "model_revision": (
                    "STRING",
                    {
                        "default": "",
                        "description": (
                            "Required full 40-character Hugging Face commit for local inference"
                        ),
                    },
                ),
                "candidate_labels": (
                    "STRING",
                    {
                        "default": "",
                        "description": (
                            "Reserved for a future zero-shot contract; task labels currently come "
                            "from the immutable checkpoint config"
                        ),
                        "advanced": True,
                    },
                ),
                "batch_size": ("INT", {"default": 8, "min": 1, "max": 64}),
                "max_length": ("INT", {"default": 512, "min": 1, "max": 4096}),
                "top_k": ("INT", {"default": 1, "min": 1, "max": 100}),
                "confidence_threshold": (
                    "FLOAT",
                    {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05},
                ),
                "compute_device": (
                    "STRING",
                    {"default": "auto", "options": ["auto", "cpu", "cuda", "mps"]},
                ),
                "fallback_backend": (
                    "STRING",
                    {
                        "default": FIXTURE_BACKEND,
                        "options": [FIXTURE_BACKEND, LOCAL_BACKEND],
                        "description": (
                            "Explicit non-scientific fixture or immutable local checkpoint; "
                            "there is no automatic fallback"
                        ),
                    },
                ),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        out_dir = _node_output_dir(self, context)
        json_path = out_dir / "predictions.json"
        csv_path = out_dir / "scores.csv"

        task = validate_choice(
            kwargs.get("task", "text_classification"),
            "task",
            ("text_classification", "sequence_classification", "zero_shot_classification"),
        )
        if task == "zero_shot_classification":
            raise RuntimeError(
                "zero_shot_classification is disabled until BioNodulo has an immutable "
                "NLI checkpoint contract with documented hypothesis construction and labels"
            )
        if str(kwargs.get("candidate_labels", "") or "").strip():
            raise ValueError(
                "candidate_labels is not accepted by the fail-closed classifier contract; "
                "local labels must come from the checkpoint config and the fixture uses fixed buckets"
            )

        batch_size = _bounded_int(kwargs.get("batch_size", 8), "batch_size", 1, 64)
        max_length = _bounded_int(kwargs.get("max_length", 512), "max_length", 1, 4096)
        requested_top_k = _bounded_int(kwargs.get("top_k", 1), "top_k", 1, 100)
        confidence_threshold = _bounded_float(
            kwargs.get("confidence_threshold", 0.0),
            "confidence_threshold",
            0.0,
            1.0,
        )
        compute_device = validate_choice(
            kwargs.get("compute_device", "auto"),
            "compute_device",
            ("auto", "cpu", "cuda", "mps"),
        )
        backend = _normalize_backend(kwargs.get("fallback_backend", FIXTURE_BACKEND))
        records = _model_inference_records(
            str(kwargs.get("input_data", "") or ""),
            task=task,
            max_length=max_length,
        )
        if not records:
            raise ValueError("input_data must contain at least one non-empty text or FASTA record")

        if backend == FIXTURE_BACKEND:
            labels = list(FIXTURE_LABELS)
            predictions = _fixture_model_predictions(
                records,
                task=task,
                labels=labels,
                top_k=requested_top_k,
            )
            resolved_model = FIXTURE_MODEL_ID
            device = "cpu"
            status = FIXTURE_STATUS
            scientific_prediction: bool | None = False
            disclaimer = (
                "NON-SCIENTIFIC FIXTURE: labels and scores are deterministic workflow-test "
                "buckets, not outputs from a trained text or biological classifier."
            )
        else:
            model_name = _require_hugging_face_model_id(kwargs.get("model_name"))
            revision = _require_immutable_revision(kwargs.get("model_revision"))
            predictions, device, labels = _local_transformer_model_predictions(
                records,
                model_name=model_name,
                revision=revision,
                batch_size=batch_size,
                max_length=max_length,
                top_k=requested_top_k,
                compute_device=compute_device,
            )
            resolved_model = f"{model_name}@{revision}"
            backend = "local_revision_pinned_task_classifier"
            status = LOCAL_STATUS
            scientific_prediction = None
            disclaimer = (
                "BioNodulo verified immutable loading and a complete checkpoint head, but has "
                "not validated the user-supplied model's scientific performance or intended domain."
            )

        filtered_predictions = [
            prediction
            for prediction in predictions
            if prediction["top_predictions"]
            and float(prediction["top_predictions"][0].get("confidence", 0.0))
            >= confidence_threshold
        ]
        top_k = min(requested_top_k, len(labels))
        payload = {
            "model_name": resolved_model,
            "resolved_model": resolved_model,
            "task": task,
            "backend": backend,
            "status": status,
            "scientific_prediction": scientific_prediction,
            "device": device,
            "labels": labels,
            "input_count": len(records),
            "returned_predictions": len(filtered_predictions),
            "filtered_out": len(predictions) - len(filtered_predictions),
            "confidence_threshold": confidence_threshold,
            "top_k": top_k,
            "predictions": filtered_predictions,
            "disclaimer": disclaimer,
        }

        json_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _write_model_scores_csv(
            csv_path,
            filtered_predictions,
            backend=backend,
            status=status,
            scientific_prediction=scientific_prediction,
        )
        require_artifacts(json_path, csv_path)
        return {"outputs": {"predictions_json": str(json_path), "scores_csv": str(csv_path)}}


def _bounded_int(value: Any, key: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return value


def _bounded_float(value: Any, key: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number")
    result = float(value)
    if result < minimum or result > maximum:
        raise ValueError(f"{key} must be between {minimum:g} and {maximum:g}")
    return result


def _normalize_backend(value: Any) -> str:
    backend = str(value or FIXTURE_BACKEND)
    if backend == "deterministic":
        return FIXTURE_BACKEND
    if backend == "auto":
        raise ValueError(
            "fallback_backend='auto' is disabled because model load failures must not silently "
            "become fixture predictions; select deterministic_fixture or local explicitly"
        )
    return validate_choice(backend, "fallback_backend", (FIXTURE_BACKEND, LOCAL_BACKEND))


def _require_hugging_face_model_id(value: Any) -> str:
    model_name = str(value or "").strip()
    if not _HF_MODEL_ID.fullmatch(model_name):
        raise ValueError(
            "model_name must be a Hugging Face namespace/model ID, not a mutable local path"
        )
    return model_name


def _model_inference_records(
    input_data: str,
    *,
    task: str,
    max_length: int,
) -> list[dict[str, Any]]:
    text = str(input_data or "")
    if not text.strip():
        return []

    path = _candidate_input_path(text)
    if path is not None and path.exists():
        if not path.is_file():
            raise ValueError(f"input_data path must be a file: {path}")
        content = path.read_text(encoding="utf-8-sig")
    else:
        content = text

    if _looks_like_fasta(
        content,
        path if path is not None and path.exists() else None,
    ) or task.startswith("sequence"):
        fasta_records = _parse_fasta_embedding_records(content, max_length=max_length)
        if fasta_records:
            return [_model_record_from_embedding_record(record) for record in fasta_records]

    records: list[dict[str, Any]] = []
    for index, chunk in enumerate(
        line.strip() for line in content.splitlines() if line.strip()
    ):
        truncated = chunk[:max_length]
        records.append(
            {
                "id": f"item_{index}",
                "text": truncated,
                "original_length": len(chunk),
                "truncated_length": len(truncated),
            }
        )
    return records


def _model_record_from_embedding_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(record.get("id", "")),
        "text": str(record.get("sequence", "")),
        "original_length": int(record.get("original_length", 0)),
        "truncated_length": int(record.get("truncated_length", 0)),
    }


def _local_transformer_model_predictions(
    records: list[dict[str, Any]],
    *,
    model_name: str,
    revision: str,
    batch_size: int,
    max_length: int,
    top_k: int,
    compute_device: str,
) -> tuple[list[dict[str, Any]], str, list[str]]:
    try:
        import torch
        from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("torch and transformers are required for local model inference") from exc

    common_load_args = {
        "revision": revision,
        "trust_remote_code": False,
        "local_files_only": True,
    }
    config = AutoConfig.from_pretrained(model_name, **common_load_args)
    labels = _validate_task_checkpoint_config(config)
    tokenizer = AutoTokenizer.from_pretrained(model_name, **common_load_args)
    model, loading_info = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        config=config,
        output_loading_info=True,
        **common_load_args,
    )
    _validate_loading_info(loading_info)

    device = compute_device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    model.eval()
    bounded_top_k = min(max(1, top_k), len(labels))

    predictions: list[dict[str, Any]] = []
    with torch.no_grad():
        for offset in range(0, len(records), batch_size):
            batch = records[offset : offset + batch_size]
            inputs = tokenizer(
                [str(record["text"]) for record in batch],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=max_length,
            )
            inputs = {key: value.to(device) for key, value in inputs.items()}
            scores = torch.softmax(model(**inputs).logits, dim=-1).cpu().numpy()
            for record, score_row in zip(batch, scores, strict=True):
                predictions.append(
                    _model_prediction(record, labels, score_row, top_k=bounded_top_k)
                )
    return predictions, str(device), labels


def _fixture_model_predictions(
    records: list[dict[str, Any]],
    *,
    task: str,
    labels: list[str],
    top_k: int,
) -> list[dict[str, Any]]:
    np = _numpy()
    bounded_top_k = min(max(1, top_k), len(labels))
    predictions: list[dict[str, Any]] = []
    for record in records:
        scores = _deterministic_classification_scores(
            str(record["text"]),
            labels,
            f"model_inference:{task}",
        )
        predictions.append(
            _model_prediction(
                record,
                labels,
                np.asarray(scores, dtype="float32"),
                top_k=bounded_top_k,
            )
        )
    return predictions


def _model_prediction(
    record: dict[str, Any],
    labels: list[str],
    scores: Any,
    *,
    top_k: int,
) -> dict[str, Any]:
    score_list = [float(value) for value in list(scores)]
    ranked_indices = sorted(
        range(len(score_list)),
        key=lambda index: score_list[index],
        reverse=True,
    )[:top_k]
    top_predictions = [
        {
            "label": labels[index],
            "confidence": score_list[index],
        }
        for index in ranked_indices
    ]
    return {
        "input_id": str(record.get("id", "")),
        "input_length": int(record.get("original_length", 0)),
        "truncated_length": int(record.get("truncated_length", 0)),
        "top_predictions": top_predictions,
    }


def _write_model_scores_csv(
    path: Path,
    predictions: list[dict[str, Any]],
    *,
    backend: str,
    status: str,
    scientific_prediction: bool | None,
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "status",
                "backend",
                "scientific_prediction",
                "input_id",
                "input_length",
                "truncated_length",
                "top_prediction",
                "confidence",
                "all_predictions",
            ]
        )
        rows = predictions or [{"top_predictions": []}]
        for prediction in rows:
            top_predictions = prediction.get("top_predictions", [])
            top = top_predictions[0] if top_predictions else {"label": "", "confidence": 0.0}
            all_predictions = "; ".join(
                f"{item['label']}:{float(item['confidence']):.4f}"
                for item in top_predictions
            )
            writer.writerow(
                [
                    status,
                    backend,
                    "unverified"
                    if scientific_prediction is None
                    else str(scientific_prediction).lower(),
                    prediction.get("input_id", ""),
                    prediction.get("input_length", 0),
                    prediction.get("truncated_length", 0),
                    top.get("label", ""),
                    f"{float(top.get('confidence', 0.0)):.4f}",
                    all_predictions,
                ]
            )
