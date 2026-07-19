"""Local or deterministic text and sequence model inference."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode

from .adapter import _node_output_dir, require_artifacts, validate_choice
from .ai_embedding import _candidate_input_path, _looks_like_fasta, _numpy, _parse_fasta_embedding_records
from .ai_sequence_classification import _deterministic_classification_scores


class ModelInferenceNode(BaseNode):
    """Run local Hugging Face model inference or deterministic fallback."""

    NODE_ID = "model_inference"
    DISPLAY_NAME = "Model Inference"
    CATEGORY = "ai"
    DESCRIPTION = "Run inference with local Hugging Face Transformer models on text or biological sequences."
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
    VERSION = "4.57.1"
    DOCUMENTATION_URL = "https://huggingface.co/docs/transformers/v4.57.1/en/main_classes/pipelines"
    GIT_URL = "https://github.com/huggingface/transformers"
    GIT_COMMIT = "8cb5963cc22174954e7dca2c0a3320b7dc2f4edc"
    ENVIRONMENT = {
        "package_constraints": {
            "numpy": "2.4.4",
            "transformers": "4.57.1",
        }
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_data": (
                    "STRING",
                    {"default": "", "multiline": True, "description": "Input file path, FASTA, or raw text"},
                ),
                "model_name": (
                    "STRING",
                    {"default": "facebook/bart-large-mnli", "description": "Local Hugging Face model name or path"},
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
                "candidate_labels": (
                    "STRING",
                    {"default": "positive, negative", "description": "Comma-separated output labels"},
                ),
                "batch_size": ("INT", {"default": 8, "min": 1, "max": 64}),
                "max_length": ("INT", {"default": 512, "min": 1, "max": 4096}),
                "top_k": ("INT", {"default": 1, "min": 1, "max": 20}),
                "confidence_threshold": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "compute_device": ("STRING", {"default": "auto", "options": ["auto", "cpu", "cuda", "mps"]}),
                "fallback_backend": ("STRING", {"default": "auto", "options": ["auto", "deterministic", "local"]}),
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

        input_data = str(kwargs.get("input_data", "") or "")
        model_name = str(kwargs.get("model_name", "facebook/bart-large-mnli") or "facebook/bart-large-mnli")
        if not model_name.strip():
            raise ValueError("model_name must be non-empty")
        task = validate_choice(
            kwargs.get("task", "text_classification"),
            "task",
            ("text_classification", "sequence_classification", "zero_shot_classification"),
        )
        labels = _model_inference_labels(kwargs.get("candidate_labels"))
        batch_size = max(1, int(kwargs.get("batch_size", 8) or 8))
        max_length = max(1, int(kwargs.get("max_length", 512) or 512))
        top_k = max(1, min(int(kwargs.get("top_k", 1) or 1), max(1, len(labels))))
        confidence_threshold = float(kwargs.get("confidence_threshold", 0.0) or 0.0)
        compute_device = validate_choice(
            kwargs.get("compute_device", "auto"),
            "compute_device",
            ("auto", "cpu", "cuda", "mps"),
        )
        fallback_backend = validate_choice(
            kwargs.get("fallback_backend", "auto"),
            "fallback_backend",
            ("auto", "deterministic", "local"),
        )

        records = _model_inference_records(input_data, task=task, max_length=max_length)
        predictions, backend, device = _generate_model_predictions(
            records,
            model_name=model_name,
            task=task,
            labels=labels,
            batch_size=batch_size,
            max_length=max_length,
            top_k=top_k,
            compute_device=compute_device,
            fallback_backend=fallback_backend,
        )
        filtered_predictions = [
            prediction
            for prediction in predictions
            if prediction["top_predictions"]
            and float(prediction["top_predictions"][0].get("confidence", 0.0)) >= confidence_threshold
        ]
        payload = {
            "model_name": model_name,
            "resolved_model": (
                model_name if backend == "local_transformer" else "product-native/deterministic-classifier-v1"
            ),
            "task": task,
            "backend": "empty" if not records else backend,
            "device": device,
            "labels": labels,
            "input_count": len(records),
            "returned_predictions": len(filtered_predictions),
            "filtered_out": len(predictions) - len(filtered_predictions),
            "confidence_threshold": confidence_threshold,
            "top_k": top_k,
            "predictions": filtered_predictions,
            "disclaimer": (
                "Deterministic fallback scores are reproducible workflow fixtures, not model inference. "
                "Select the local backend with a compatible cached model for scientific use."
            ),
        }

        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_model_scores_csv(csv_path, filtered_predictions)
        require_artifacts(json_path, csv_path)
        return {"outputs": {"predictions_json": str(json_path), "scores_csv": str(csv_path)}}


def _model_inference_labels(value: Any) -> list[str]:
    labels = [label.strip() for label in str(value or "positive, negative").split(",") if label.strip()]
    return labels or ["positive", "negative"]


def _model_inference_records(input_data: str, *, task: str, max_length: int) -> list[dict[str, Any]]:
    text = str(input_data or "")
    if not text.strip():
        return []

    path = _candidate_input_path(text)
    if path is not None and path.exists():
        content = path.read_text(encoding="utf-8-sig")
    else:
        content = text

    if _looks_like_fasta(content, path if path is not None and path.exists() else None) or task.startswith("sequence"):
        fasta_records = _parse_fasta_embedding_records(content, max_length=max_length)
        if fasta_records:
            return [_model_record_from_embedding_record(record) for record in fasta_records]

    records: list[dict[str, Any]] = []
    for index, chunk in enumerate(line.strip() for line in content.splitlines() if line.strip()):
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


def _generate_model_predictions(
    records: list[dict[str, Any]],
    *,
    model_name: str,
    task: str,
    labels: list[str],
    batch_size: int,
    max_length: int,
    top_k: int,
    compute_device: str,
    fallback_backend: str,
) -> tuple[list[dict[str, Any]], str, str]:
    if not records:
        return [], "empty", "cpu" if compute_device == "auto" else compute_device
    if fallback_backend != "deterministic":
        try:
            predictions, device = _local_transformer_model_predictions(
                records,
                model_name=model_name,
                labels=labels,
                batch_size=batch_size,
                max_length=max_length,
                top_k=top_k,
                compute_device=compute_device,
            )
            return predictions, "local_transformer", device
        except Exception:
            if fallback_backend == "local":
                raise
    device = "cpu" if compute_device == "auto" else compute_device
    return _deterministic_model_predictions(records, task=task, labels=labels, top_k=top_k), "deterministic", device


def _local_transformer_model_predictions(
    records: list[dict[str, Any]],
    *,
    model_name: str,
    labels: list[str],
    batch_size: int,
    max_length: int,
    top_k: int,
    compute_device: str,
) -> tuple[list[dict[str, Any]], str]:
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("torch and transformers are required for local model inference") from exc

    device = compute_device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=False, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        trust_remote_code=False,
        local_files_only=True,
        num_labels=len(labels),
    )
    model = model.to(device)
    model.eval()

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
                predictions.append(_model_prediction(record, labels, score_row, top_k=top_k))
    return predictions, str(device)


def _deterministic_model_predictions(
    records: list[dict[str, Any]],
    *,
    task: str,
    labels: list[str],
    top_k: int,
) -> list[dict[str, Any]]:
    np = _numpy()
    predictions: list[dict[str, Any]] = []
    for record in records:
        scores = _deterministic_classification_scores(str(record["text"]), labels, task)
        predictions.append(_model_prediction(record, labels, np.asarray(scores, dtype="float32"), top_k=top_k))
    return predictions


def _model_prediction(record: dict[str, Any], labels: list[str], scores: Any, *, top_k: int) -> dict[str, Any]:
    score_list = [float(value) for value in list(scores)]
    ranked_indices = sorted(range(len(score_list)), key=lambda index: score_list[index], reverse=True)[:top_k]
    top_predictions = [
        {
            "label": labels[index] if index < len(labels) else f"class_{index}",
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


def _write_model_scores_csv(path: Path, predictions: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "input_id",
                "input_length",
                "truncated_length",
                "top_prediction",
                "confidence",
                "all_predictions",
            ]
        )
        for prediction in predictions:
            top_predictions = prediction.get("top_predictions", [])
            top = top_predictions[0] if top_predictions else {"label": "", "confidence": 0.0}
            all_predictions = "; ".join(f"{item['label']}:{float(item['confidence']):.4f}" for item in top_predictions)
            writer.writerow(
                [
                    prediction.get("input_id", ""),
                    prediction.get("input_length", 0),
                    prediction.get("truncated_length", 0),
                    top.get("label", ""),
                    f"{float(top.get('confidence', 0.0)):.4f}",
                    all_predictions,
                ]
            )
