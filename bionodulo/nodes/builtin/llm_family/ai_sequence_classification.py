"""Fail-closed biological sequence classification contracts.

The named scientific modes remain visible for saved-workflow compatibility, but
they cannot run until BioNodulo has an immutable task-trained model contract.
Generic protein encoders and deterministic fixture scores are never substituted
for DeepLoc, SignalP, TMHMM, disorder, or solubility predictors.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode

from .adapter import _node_output_dir, require_artifacts, validate_choice
from .ai_embedding import _numpy, _parse_fasta_embedding_records


TRANSFORMERS_VERSION = "4.57.1"
TRANSFORMERS_SOURCE_URL = "https://github.com/huggingface/transformers"
TRANSFORMERS_SOURCE_COMMIT = "8cb5963cc22174954e7dca2c0a3320b7dc2f4edc"
TRANSFORMERS_MODELING_AUTO_SOURCE = "src/transformers/models/auto/modeling_auto.py"
TRANSFORMERS_MODELING_AUTO_SHA256 = "6e4fa67c88e02a8b84d46d7b1719e760f197073b7b233bcf30eeb596f5a5f07a"
TRANSFORMERS_MODELING_UTILS_SOURCE = "src/transformers/modeling_utils.py"
TRANSFORMERS_MODELING_UTILS_SHA256 = "bf1c6b2a43cf7c36fb79f37c981424dd6ae78eb863fcaa5d2a37e76c9828611d"
TRANSFORMERS_DOCUMENTATION_URL = (
    "https://huggingface.co/docs/transformers/v4.57.1/en/main_classes/model#transformers.PreTrainedModel.from_pretrained"
)

FIXTURE_CLASSIFIER = "non_scientific_fixture"
FIXTURE_MODEL_ID = "product-native/non-scientific-sequence-fixture-v1"
FIXTURE_LABELS = ("fixture_bucket_0", "fixture_bucket_1", "fixture_bucket_2", "fixture_bucket_3")
FIXTURE_STATUS = "NON_SCIENTIFIC_FIXTURE_ONLY"
CUSTOM_STATUS = "USER_SUPPLIED_TASK_CHECKPOINT_NOT_VALIDATED_BY_BIONODULO"
IMMUTABLE_HF_REVISION = re.compile(r"^[0-9a-fA-F]{40}$")

# These are authorities for the names only. No model artifact from these tools
# is shipped or downloaded by this node, so every named mode fails closed.
NAMED_CLASSIFIER_AUTHORITIES: dict[str, dict[str, str]] = {
    "deeploc": {
        "tool": "DeepLoc",
        "version": "2.1",
        "url": "https://services.healthtech.dtu.dk/services/DeepLoc-2.1/",
        "status": "disabled_without_revision_pinned_task_model",
    },
    "signalp": {
        "tool": "SignalP",
        "version": "6.0",
        "url": "https://services.healthtech.dtu.dk/services/SignalP-6.0/",
        "status": "disabled_without_revision_pinned_task_model",
    },
    "tmhmm": {
        "tool": "TMHMM",
        "version": "2.0d",
        "url": "https://services.healthtech.dtu.dk/services/TMHMM-2.0/",
        "status": "disabled_without_revision_pinned_task_model",
    },
    "disorder": {
        "tool": "disorder predictor",
        "version": "unresolved",
        "url": "",
        "status": "disabled_without_identified_task_model_authority",
    },
    "solubility": {
        "tool": "solubility predictor",
        "version": "unresolved",
        "url": "",
        "status": "disabled_without_identified_task_model_authority",
    },
}


class AISequenceClassificationNode(BaseNode):
    """Run an explicit fixture or an immutable user-supplied task classifier."""

    NODE_ID = "ai_sequence_classification"
    DISPLAY_NAME = "AI Sequence Classification"
    CATEGORY = "ai"
    DESCRIPTION = (
        "Run a visibly non-scientific fixture or a locally cached, immutable, task-trained "
        "Hugging Face sequence-classification checkpoint."
    )
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
    VERSION = TRANSFORMERS_VERSION
    DOCUMENTATION_URL = TRANSFORMERS_DOCUMENTATION_URL
    GIT_URL = TRANSFORMERS_SOURCE_URL
    GIT_COMMIT = TRANSFORMERS_SOURCE_COMMIT
    AUDIT_STATUS = "contract-checked-no-model-execution"
    SOURCE_AUTHORITIES = {
        "transformers_commit": TRANSFORMERS_SOURCE_COMMIT,
        "transformers_modeling_auto_sha256": TRANSFORMERS_MODELING_AUTO_SHA256,
        "transformers_modeling_utils_sha256": TRANSFORMERS_MODELING_UTILS_SHA256,
        "named_classifiers": NAMED_CLASSIFIER_AUTHORITIES,
    }
    ENVIRONMENT = {
        "package_constraints": {
            "biopython": "1.87",
            "numpy": "2.4.4",
            "transformers": TRANSFORMERS_VERSION,
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
                        "default": FIXTURE_CLASSIFIER,
                        "options": [FIXTURE_CLASSIFIER, *NAMED_CLASSIFIER_AUTHORITIES, "custom"],
                        "description": (
                            "Named scientific modes fail closed until a pinned task model exists; "
                            "the fixture mode is explicitly non-scientific"
                        ),
                    },
                ),
            },
            "optional": {
                "custom_model": (
                    "STRING",
                    {"default": "", "description": "Locally cached Hugging Face task-classifier model ID"},
                ),
                "custom_revision": (
                    "STRING",
                    {"default": "", "description": "Required immutable 40-character Hugging Face commit"},
                ),
                "batch_size": ("INT", {"default": 8, "min": 1, "max": 64}),
                "max_length": ("INT", {"default": 1024, "min": 1, "max": 4096}),
                "confidence_threshold": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05}),
                "compute_device": ("STRING", {"default": "auto", "options": ["auto", "cpu", "cuda", "mps"]}),
                "top_k": ("INT", {"default": 1, "min": 1, "max": 100}),
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
            kwargs.get("classifier", FIXTURE_CLASSIFIER),
            "classifier",
            (FIXTURE_CLASSIFIER, *NAMED_CLASSIFIER_AUTHORITIES, "custom"),
        )
        if classifier in NAMED_CLASSIFIER_AUTHORITIES:
            raise RuntimeError(_disabled_named_classifier_message(classifier))

        batch_size = max(1, int(kwargs.get("batch_size", 8) or 8))
        max_length = max(1, int(kwargs.get("max_length", 1024) or 1024))
        confidence_threshold = float(kwargs.get("confidence_threshold", 0.5) or 0.0)
        compute_device = validate_choice(
            kwargs.get("compute_device", "auto"),
            "compute_device",
            ("auto", "cpu", "cuda", "mps"),
        )
        requested_top_k = max(1, int(kwargs.get("top_k", 1) or 1))
        records = _classification_records(kwargs.get("input_fasta", ""), max_length=max_length)

        if classifier == "custom":
            model_name = str(kwargs.get("custom_model", "") or "").strip()
            revision = _require_immutable_revision(kwargs.get("custom_revision", ""))
            if not model_name:
                raise ValueError("AI Sequence Classification requires custom_model when classifier is custom")
            predictions, device, labels = _local_transformer_classifications(
                records,
                model_name=model_name,
                revision=revision,
                batch_size=batch_size,
                max_length=max_length,
                top_k=requested_top_k,
                compute_device=compute_device,
            )
            backend = "local_revision_pinned_task_classifier"
            model_identity = f"{model_name}@{revision}"
            status = CUSTOM_STATUS
            scientific_prediction: bool | None = None
            disclaimer = (
                "BioNodulo verified immutable loading and a complete checkpoint head, but has not validated "
                "the user-supplied model's scientific performance or intended domain."
            )
        else:
            labels = list(FIXTURE_LABELS)
            predictions = _fixture_classifications(records, labels=labels, top_k=requested_top_k)
            device = "cpu"
            backend = "deterministic_fixture"
            model_identity = FIXTURE_MODEL_ID
            status = FIXTURE_STATUS
            scientific_prediction = False
            disclaimer = (
                "NON-SCIENTIFIC FIXTURE: labels and scores are deterministic workflow-test buckets, "
                "not biological predictions and not outputs from DeepLoc, SignalP, TMHMM, or another model."
            )

        filtered_predictions = [
            prediction
            for prediction in predictions
            if prediction["top_predictions"]
            and float(prediction["top_predictions"][0].get("confidence", 0.0)) >= confidence_threshold
        ]
        top_k = min(requested_top_k, max(1, len(labels)))
        payload = {
            "classifier": classifier,
            "model": model_identity,
            "backend": backend,
            "status": status,
            "scientific_prediction": scientific_prediction,
            "device": device,
            "labels": labels,
            "total_sequences": len(records),
            "returned_predictions": len(filtered_predictions),
            "filtered_out": len(predictions) - len(filtered_predictions),
            "confidence_threshold": confidence_threshold,
            "top_k": top_k,
            "predictions": filtered_predictions,
            "disclaimer": disclaimer,
        }

        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_classifications_csv(
            csv_path,
            filtered_predictions,
            backend=backend,
            status=status,
            scientific_prediction=scientific_prediction,
        )
        require_artifacts(json_path, csv_path)
        return {"outputs": {"classifications_json": str(json_path), "classifications_csv": str(csv_path)}}


def _disabled_named_classifier_message(classifier: str) -> str:
    authority = NAMED_CLASSIFIER_AUTHORITIES[classifier]
    source = f" Authority: {authority['url']}" if authority["url"] else ""
    return (
        f"Classifier '{classifier}' is disabled: BioNodulo has no immutable task-trained "
        f"{authority['tool']} {authority['version']} model contract and will not substitute a generic encoder "
        f"or deterministic fixture.{source}"
    )


def _require_immutable_revision(value: Any) -> str:
    revision = str(value or "").strip()
    if not IMMUTABLE_HF_REVISION.fullmatch(revision):
        raise ValueError("custom_revision must be a full immutable 40-character hexadecimal Hugging Face commit")
    return revision.lower()


def _classification_records(input_fasta: Any, *, max_length: int) -> list[dict[str, Any]]:
    path = Path(str(input_fasta or ""))
    if not path.is_file():
        raise FileNotFoundError(f"Sequence classification FASTA not found: {path}")
    content = path.read_text(encoding="utf-8-sig")
    return _parse_fasta_embedding_records(content, max_length=max_length)


def _checkpoint_labels(config: Any) -> list[str]:
    try:
        num_labels = int(config.num_labels)
    except (AttributeError, TypeError, ValueError) as exc:
        raise RuntimeError("Custom classifier config must declare num_labels") from exc
    if num_labels < 2:
        raise RuntimeError("Custom classifier config must declare at least two labels")

    raw_labels = getattr(config, "id2label", None)
    if not isinstance(raw_labels, dict):
        raise RuntimeError("Custom classifier config must contain a complete id2label mapping")
    labels: dict[int, str] = {}
    for raw_index, raw_label in raw_labels.items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Custom classifier id2label keys must be integer indices") from exc
        label = str(raw_label or "").strip()
        if not label:
            raise RuntimeError("Custom classifier id2label values must be non-empty")
        labels[index] = label
    expected = list(range(num_labels))
    if sorted(labels) != expected:
        raise RuntimeError("Custom classifier id2label must cover every class index exactly once")
    return [labels[index] for index in expected]


def _validate_task_checkpoint_config(config: Any) -> list[str]:
    architectures = getattr(config, "architectures", None)
    if not isinstance(architectures, (list, tuple)) or not any(
        str(name).endswith("ForSequenceClassification") for name in architectures
    ):
        raise RuntimeError(
            "Custom model config must identify a task-trained *ForSequenceClassification architecture; "
            "generic base or masked-language-model encoders are not accepted"
        )
    return _checkpoint_labels(config)


def _validate_loading_info(loading_info: Any) -> None:
    if not isinstance(loading_info, dict):
        raise RuntimeError("Transformers did not return checkpoint loading information")
    problems = {
        key: list(loading_info.get(key, []) or [])
        for key in ("missing_keys", "unexpected_keys", "mismatched_keys", "error_msgs")
    }
    populated = {key: values for key, values in problems.items() if values}
    if populated:
        rendered = "; ".join(f"{key}={values}" for key, values in populated.items())
        raise RuntimeError(
            "Custom classifier checkpoint did not load exactly; refusing a missing, mismatched, or random head: "
            f"{rendered}"
        )


def _local_transformer_classifications(
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
        raise RuntimeError("torch and transformers are required for local sequence classification") from exc

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
                [str(record["sequence"]) for record in batch],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=max_length,
            )
            inputs = {key: value.to(device) for key, value in inputs.items()}
            scores = torch.softmax(model(**inputs).logits, dim=-1).cpu().numpy()
            for record, score_row in zip(batch, scores, strict=True):
                predictions.append(_classification_prediction(record, labels, score_row, top_k=bounded_top_k))
    return predictions, str(device), labels


def _fixture_classifications(
    records: list[dict[str, Any]],
    *,
    labels: list[str],
    top_k: int,
) -> list[dict[str, Any]]:
    np = _numpy()
    bounded_top_k = min(max(1, top_k), len(labels))
    predictions: list[dict[str, Any]] = []
    for record in records:
        scores = _deterministic_classification_scores(str(record["sequence"]), labels, FIXTURE_CLASSIFIER)
        predictions.append(
            _classification_prediction(record, labels, np.asarray(scores, dtype="float32"), top_k=bounded_top_k)
        )
    return predictions


def _deterministic_classification_scores(sequence: str, labels: list[str], classifier: str) -> list[float]:
    """Return reproducible fixture buckets; callers must label them non-scientific."""

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


def _write_classifications_csv(
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
                "sequence_id",
                "sequence_length",
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
                f"{item['label']}:{float(item['confidence']):.4f}" for item in top_predictions
            )
            writer.writerow(
                [
                    status,
                    backend,
                    "unverified" if scientific_prediction is None else str(scientific_prediction).lower(),
                    prediction.get("sequence_id", ""),
                    prediction.get("sequence_length", 0),
                    prediction.get("truncated_length", 0),
                    top.get("label", ""),
                    f"{float(top.get('confidence', 0.0)):.4f}",
                    all_predictions,
                ]
            )
