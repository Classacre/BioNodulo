"""Local or deterministic biological sequence classification."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode

from .adapter import _node_output_dir, require_artifacts, validate_choice
from .ai_embedding import _numpy, _parse_fasta_embedding_records


class AISequenceClassificationNode(BaseNode):
    """Classify biological sequences with local models or deterministic fallback."""

    NODE_ID = "ai_sequence_classification"
    DISPLAY_NAME = "AI Sequence Classification"
    CATEGORY = "ai"
    DESCRIPTION = "Classify biological sequences using pretrained ML models or a deterministic local fallback."
    SEARCH_ALIASES = [
        "classify",
        "classification",
        "deeploc",
        "signalp",
        "tmhmm",
        "localization",
        "prediction",
        "annotation",
        "subcellular",
    ]
    RETURN_TYPES = ("JSON", "CSV")
    RETURN_NAMES = ("classifications_json", "classifications_csv")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["numpy", "biopython", "torch", "transformers"]
    EXPERIMENTAL = True
    VERSION = "4.57.1"
    DOCUMENTATION_URL = "https://huggingface.co/docs/transformers/v4.57.1/en/main_classes/pipelines"
    GIT_URL = "https://github.com/huggingface/transformers"
    GIT_COMMIT = "8cb5963cc22174954e7dca2c0a3320b7dc2f4edc"
    ENVIRONMENT = {
        "package_constraints": {
            "biopython": "1.87",
            "numpy": "2.4.4",
            "transformers": "4.57.1",
        }
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Input FASTA file with sequences to classify"}),
                "classifier": (
                    "STRING",
                    {
                        "default": "deeploc",
                        "options": ["deeploc", "signalp", "tmhmm", "disorder", "solubility", "custom"],
                        "description": "Classification model to use",
                    },
                ),
            },
            "optional": {
                "custom_model": (
                    "STRING",
                    {"default": "", "description": "HuggingFace model name for custom classifier"},
                ),
                "batch_size": ("INT", {"default": 8, "min": 1, "max": 64}),
                "max_length": ("INT", {"default": 1024, "min": 1, "max": 4096}),
                "confidence_threshold": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05}),
                "compute_device": ("STRING", {"default": "auto", "options": ["auto", "cpu", "cuda", "mps"]}),
                "top_k": ("INT", {"default": 1, "min": 1, "max": 10}),
                "fallback_backend": ("STRING", {"default": "auto", "options": ["auto", "deterministic", "local"]}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        out_dir = _node_output_dir(self, context)
        json_path = out_dir / "classifications.json"
        csv_path = out_dir / "classifications.csv"

        classifier = validate_choice(
            kwargs.get("classifier", "deeploc"),
            "classifier",
            (*_CLASSIFIER_REGISTRY, "custom"),
        )
        custom_model = str(kwargs.get("custom_model", "") or "").strip()
        batch_size = max(1, int(kwargs.get("batch_size", 8) or 8))
        max_length = max(1, int(kwargs.get("max_length", 1024) or 1024))
        confidence_threshold = float(kwargs.get("confidence_threshold", 0.5) or 0.0)
        compute_device = validate_choice(
            kwargs.get("compute_device", "auto"),
            "compute_device",
            ("auto", "cpu", "cuda", "mps"),
        )
        top_k = max(1, int(kwargs.get("top_k", 1) or 1))
        fallback_backend = validate_choice(
            kwargs.get("fallback_backend", "auto"),
            "fallback_backend",
            ("auto", "deterministic", "local"),
        )

        classifier_spec = _classification_spec(classifier, custom_model)
        labels = list(classifier_spec["labels"])
        top_k = min(top_k, max(1, len(labels)))
        records = _classification_records(kwargs.get("input_fasta", ""), max_length=max_length)
        predictions, backend, device = _generate_classifications(
            records,
            classifier=classifier,
            model_name=str(classifier_spec["model"]),
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
            "classifier": classifier,
            "model": (
                classifier_spec["model"]
                if backend == "local_transformer"
                else "product-native/deterministic-classifier-v1"
            ),
            "backend": "empty" if not records else backend,
            "device": device,
            "labels": labels,
            "total_sequences": len(records),
            "returned_predictions": len(filtered_predictions),
            "filtered_out": len(predictions) - len(filtered_predictions),
            "confidence_threshold": confidence_threshold,
            "top_k": top_k,
            "predictions": filtered_predictions,
            "disclaimer": (
                "Deterministic fallback scores are reproducible workflow fixtures, not validated biological "
                "predictions. Use a compatible locally cached classification model for scientific inference."
            ),
        }

        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_classifications_csv(csv_path, filtered_predictions)
        require_artifacts(json_path, csv_path)
        return {"outputs": {"classifications_json": str(json_path), "classifications_csv": str(csv_path)}}


_CLASSIFIER_REGISTRY: dict[str, dict[str, Any]] = {
    "deeploc": {
        "model": "ElnaggarLab/ankh-base",
        "labels": [
            "Cytoplasm",
            "Nucleus",
            "Extracellular",
            "Mitochondrion",
            "Cell membrane",
            "Endoplasmic reticulum",
            "Plastid",
            "Golgi apparatus",
            "Lysosome/Vacuole",
            "Peroxisome",
        ],
    },
    "signalp": {
        "model": "ElnaggarLab/ankh-base",
        "labels": ["NO_SP", "SP", "LIPO", "TAT"],
    },
    "tmhmm": {
        "model": "facebook/esm2_t12_35M_UR50D",
        "labels": ["TM", "non-TM"],
    },
    "disorder": {
        "model": "facebook/esm2_t6_8M_UR50D",
        "labels": ["ordered", "disordered"],
    },
    "solubility": {
        "model": "facebook/esm2_t12_35M_UR50D",
        "labels": ["soluble", "insoluble"],
    },
}


_CUSTOM_CLASSIFICATION_LABELS = ["class_0", "class_1"]


def _classification_spec(classifier: str, custom_model: str) -> dict[str, Any]:
    if classifier == "custom":
        if not custom_model:
            raise ValueError("AI Sequence Classification requires custom_model when classifier is custom")
        return {
            "model": custom_model,
            "labels": _CUSTOM_CLASSIFICATION_LABELS,
        }
    return _CLASSIFIER_REGISTRY.get(classifier, _CLASSIFIER_REGISTRY["deeploc"])


def _classification_records(input_fasta: Any, *, max_length: int) -> list[dict[str, Any]]:
    path = Path(str(input_fasta or ""))
    if not path.exists():
        raise FileNotFoundError(f"Sequence classification FASTA not found: {path}")
    content = path.read_text(encoding="utf-8-sig")
    return _parse_fasta_embedding_records(content, max_length=max_length)


def _generate_classifications(
    records: list[dict[str, Any]],
    *,
    classifier: str,
    model_name: str,
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
            predictions, device = _local_transformer_classifications(
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
    return (
        _deterministic_classifications(records, classifier=classifier, labels=labels, top_k=top_k),
        "deterministic",
        device,
    )


def _local_transformer_classifications(
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
        raise RuntimeError("torch and transformers are required for local sequence classification") from exc

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
                [str(record["sequence"]) for record in batch],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=max_length,
            )
            inputs = {key: value.to(device) for key, value in inputs.items()}
            scores = torch.softmax(model(**inputs).logits, dim=-1).cpu().numpy()
            for record, score_row in zip(batch, scores, strict=True):
                predictions.append(_classification_prediction(record, labels, score_row, top_k=top_k))
    return predictions, str(device)


def _deterministic_classifications(
    records: list[dict[str, Any]],
    *,
    classifier: str,
    labels: list[str],
    top_k: int,
) -> list[dict[str, Any]]:
    np = _numpy()
    predictions: list[dict[str, Any]] = []
    for record in records:
        scores = _deterministic_classification_scores(str(record["sequence"]), labels, classifier)
        predictions.append(_classification_prediction(record, labels, np.asarray(scores, dtype="float32"), top_k=top_k))
    return predictions


def _deterministic_classification_scores(sequence: str, labels: list[str], classifier: str) -> list[float]:
    raw_scores: list[float] = []
    sequence_bytes = str(sequence).encode("utf-8")
    classifier_seed = sum(classifier.encode("utf-8")) or 1
    for label_index, label in enumerate(labels):
        label_seed = sum(str(label).encode("utf-8")) + ((label_index + 1) * classifier_seed)
        score = float((label_seed % 97) + 1)
        for byte_index, byte in enumerate(sequence_bytes):
            score += ((byte + label_seed + byte_index) % 31) / 31.0
        raw_scores.append(score)
    total = sum(raw_scores) or 1.0
    return [score / total for score in raw_scores]


def _classification_prediction(record: dict[str, Any], labels: list[str], scores: Any, *, top_k: int) -> dict[str, Any]:
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
        "sequence_id": str(record.get("id", "")),
        "sequence_length": int(record.get("original_length", 0)),
        "truncated_length": int(record.get("truncated_length", 0)),
        "top_predictions": top_predictions,
    }


def _write_classifications_csv(path: Path, predictions: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "sequence_id",
                "sequence_length",
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
                    prediction.get("sequence_id", ""),
                    prediction.get("sequence_length", 0),
                    prediction.get("truncated_length", 0),
                    top.get("label", ""),
                    f"{float(top.get('confidence', 0.0)):.4f}",
                    all_predictions,
                ]
            )
