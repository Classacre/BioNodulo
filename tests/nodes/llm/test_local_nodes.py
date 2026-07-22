from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from bionodulo.nodes.builtin.llm_family import ai_embedding, ai_sequence_classification
from bionodulo.nodes.builtin.llm_family.ai_embedding import AIEmbeddingNode
from bionodulo.nodes.builtin.llm_family.ai_sequence_classification import (
    FIXTURE_CLASSIFIER,
    FIXTURE_LABELS,
    AISequenceClassificationNode,
)
from bionodulo.nodes.builtin.llm_family.embedding_generation import EmbeddingGenerationNode
from bionodulo.nodes.builtin.llm_family.fine_tune_llm import FineTuneLLMNode
from bionodulo.nodes.builtin.llm_family.model_inference import ModelInferenceNode


def context(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(node_dir=tmp_path, resolve_secret=lambda _key: None)


@pytest.mark.asyncio
async def test_embedding_nodes_write_deterministic_vectors_with_honest_model_identity(tmp_path: Path) -> None:
    fasta = tmp_path / "proteins.fasta"
    fasta.write_text(">a\nMTEYKLVVVG\n>b\nGAGGVGKSAL\n", encoding="utf-8")

    result = await AIEmbeddingNode().run(
        input_data=str(fasta),
        embedding_model="esm2_t6_8M",
        molecule_type="protein",
        fallback_backend="deterministic_fixture",
        context=context(tmp_path),
    )
    vectors = np.load(result["outputs"]["embeddings_npy"])
    metadata = json.loads(Path(result["outputs"]["metadata_json"]).read_text(encoding="utf-8"))

    assert vectors.shape == (2, 32)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    assert metadata["backend"] == "deterministic_fixture"
    assert metadata["status"] == "NON_SCIENTIFIC_FIXTURE_ONLY"
    assert metadata["scientific_embedding"] is False
    assert metadata["model_name"] == "product-native/non-scientific-sha256-fixture-v1"
    assert "NON-SCIENTIFIC FIXTURE" in metadata["disclaimer"]
    assert issubclass(EmbeddingGenerationNode, AIEmbeddingNode)
    assert EmbeddingGenerationNode.NODE_ID == "embedding_generation"


@pytest.mark.asyncio
async def test_api_embedding_backend_requires_explicit_or_resolved_credentials(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="api_key is required"):
        await AIEmbeddingNode().run(
            input_data="one line",
            embedding_model="text_embedding",
            molecule_type="text",
            fallback_backend="api",
            api_key="",
            context=context(tmp_path),
        )


@pytest.mark.asyncio
async def test_sequence_classification_writes_reproducible_fixture_outputs(tmp_path: Path) -> None:
    fasta = tmp_path / "protein.fasta"
    fasta.write_text(">protein\nMKKLLFAIPLVVPFYSHS\n", encoding="utf-8")

    result = await AISequenceClassificationNode().run(
        input_fasta=str(fasta),
        classifier=FIXTURE_CLASSIFIER,
        confidence_threshold=0.0,
        context=context(tmp_path),
    )
    payload = json.loads(Path(result["outputs"]["classifications_json"]).read_text(encoding="utf-8"))

    assert payload["backend"] == "deterministic_fixture"
    assert payload["status"] == "NON_SCIENTIFIC_FIXTURE_ONLY"
    assert payload["scientific_prediction"] is False
    assert payload["model"] == "product-native/non-scientific-sequence-fixture-v1"
    assert payload["labels"] == list(FIXTURE_LABELS)
    assert payload["returned_predictions"] == 1
    assert "NON-SCIENTIFIC FIXTURE" in payload["disclaimer"]
    with Path(result["outputs"]["classifications_csv"]).open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["status"] == "NON_SCIENTIFIC_FIXTURE_ONLY"
    assert row["backend"] == "deterministic_fixture"
    assert row["scientific_prediction"] == "false"
    assert row["top_prediction"].startswith("fixture_bucket_")


@pytest.mark.parametrize("classifier", ("deeploc", "signalp", "tmhmm", "disorder", "solubility"))
@pytest.mark.asyncio
async def test_named_scientific_classifiers_fail_closed(classifier: str, tmp_path: Path) -> None:
    fasta = tmp_path / "protein.fasta"
    fasta.write_text(">protein\nMKKLLFAIPLVVPFYSHS\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="no immutable task-trained"):
        await AISequenceClassificationNode().run(
            input_fasta=str(fasta),
            classifier=classifier,
            context=context(tmp_path),
        )


@pytest.mark.parametrize("backend", ("auto", "local"))
@pytest.mark.asyncio
async def test_embedding_auto_and_local_propagate_model_failures(
    backend: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_local(*_args, **_kwargs):
        raise RuntimeError("pinned model is unavailable")

    monkeypatch.setattr(ai_embedding, "_local_transformer_embeddings", fail_local)
    with pytest.raises(RuntimeError, match="pinned model is unavailable"):
        await AIEmbeddingNode().run(
            input_data="MTEYKLVVVG",
            embedding_model="esm2_t6_8M",
            molecule_type="protein",
            fallback_backend=backend,
            context=context(tmp_path),
        )


@pytest.mark.asyncio
async def test_custom_classifier_requires_immutable_revision_and_propagates_load_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fasta = tmp_path / "protein.fasta"
    fasta.write_text(">protein\nMTEYKLVVVG\n", encoding="utf-8")

    with pytest.raises(ValueError, match="full immutable 40-character"):
        await AISequenceClassificationNode().run(
            input_fasta=str(fasta),
            classifier="custom",
            custom_model="example/task-classifier",
            custom_revision="main",
            context=context(tmp_path),
        )

    def fail_local(*_args, **_kwargs):
        raise RuntimeError("checkpoint head is missing")

    monkeypatch.setattr(ai_sequence_classification, "_local_transformer_classifications", fail_local)
    with pytest.raises(RuntimeError, match="checkpoint head is missing"):
        await AISequenceClassificationNode().run(
            input_fasta=str(fasta),
            classifier="custom",
            custom_model="example/task-classifier",
            custom_revision="a" * 40,
            context=context(tmp_path),
        )


def test_custom_classifier_uses_checkpoint_labels_and_rejects_base_or_partial_heads() -> None:
    task_config = SimpleNamespace(
        architectures=["BertForSequenceClassification"],
        num_labels=2,
        id2label={0: "cytosol", 1: "secreted"},
    )
    assert ai_sequence_classification._validate_task_checkpoint_config(task_config) == ["cytosol", "secreted"]

    base_config = SimpleNamespace(
        architectures=["EsmForMaskedLM"],
        num_labels=2,
        id2label={0: "cytosol", 1: "secreted"},
    )
    with pytest.raises(RuntimeError, match="generic base or masked-language-model encoders"):
        ai_sequence_classification._validate_task_checkpoint_config(base_config)
    with pytest.raises(RuntimeError, match="refusing a missing, mismatched, or random head"):
        ai_sequence_classification._validate_loading_info({"missing_keys": ["classifier.weight"]})


@pytest.mark.asyncio
async def test_model_inference_writes_deterministic_outputs_and_rejects_unsupported_tasks(tmp_path: Path) -> None:
    result = await ModelInferenceNode().run(
        input_data="BRCA1 regulates repair.\nTP53 responds to damage.",
        model_name="facebook/bart-large-mnli",
        task="text_classification",
        candidate_labels="repair, apoptosis",
        confidence_threshold=0.0,
        fallback_backend="deterministic",
        context=context(tmp_path),
    )
    payload = json.loads(Path(result["outputs"]["predictions_json"]).read_text(encoding="utf-8"))

    assert payload["backend"] == "deterministic"
    assert payload["resolved_model"] == "product-native/deterministic-classifier-v1"
    assert payload["returned_predictions"] == 2
    with pytest.raises(ValueError, match="task must be one of"):
        await ModelInferenceNode().run(
            input_data="text",
            model_name="model",
            task="feature_extraction",
            fallback_backend="deterministic",
            context=context(tmp_path),
        )


@pytest.mark.asyncio
async def test_fine_tune_node_writes_package_without_claiming_training(tmp_path: Path) -> None:
    training = tmp_path / "training.jsonl"
    training.write_text('{"prompt": "Explain TP53", "response": "DNA damage response"}\n', encoding="utf-8")

    result = await FineTuneLLMNode().run(
        training_data=str(training),
        base_model="distilgpt2",
        epochs=1,
        training_format="prompt_response",
        output_adapter_name="adapter",
        training_backend="dry_run",
        context=context(tmp_path),
    )
    model_dir = Path(result["outputs"]["model_path"])
    metrics = json.loads(Path(result["outputs"]["metrics_json"]).read_text(encoding="utf-8"))

    assert model_dir.is_dir()
    assert (model_dir / "training_config.json").is_file()
    assert (model_dir / "adapter_config.json").is_file()
    assert metrics["backend"] == "dry_run"
    assert metrics["train_records"] == 1
    assert "local_training" not in metrics


@pytest.mark.asyncio
async def test_fine_tune_node_rejects_empty_training_data(tmp_path: Path) -> None:
    training = tmp_path / "empty.txt"
    training.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="at least one example"):
        await FineTuneLLMNode().run(
            training_data=str(training),
            base_model="distilgpt2",
            epochs=1,
            training_backend="dry_run",
            context=context(tmp_path),
        )
