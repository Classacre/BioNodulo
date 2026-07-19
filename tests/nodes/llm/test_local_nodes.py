from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from bionodulo.nodes.builtin.llm_family.ai_embedding import AIEmbeddingNode
from bionodulo.nodes.builtin.llm_family.ai_sequence_classification import AISequenceClassificationNode
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
        fallback_backend="deterministic",
        context=context(tmp_path),
    )
    vectors = np.load(result["outputs"]["embeddings_npy"])
    metadata = json.loads(Path(result["outputs"]["metadata_json"]).read_text(encoding="utf-8"))

    assert vectors.shape == (2, 32)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    assert metadata["backend"] == "deterministic"
    assert metadata["model_name"] == "product-native/sha256-embedding-v1"
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
        classifier="signalp",
        confidence_threshold=0.0,
        fallback_backend="deterministic",
        context=context(tmp_path),
    )
    payload = json.loads(Path(result["outputs"]["classifications_json"]).read_text(encoding="utf-8"))

    assert payload["backend"] == "deterministic"
    assert payload["model"] == "product-native/deterministic-classifier-v1"
    assert payload["returned_predictions"] == 1
    assert "not validated biological predictions" in payload["disclaimer"]


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
