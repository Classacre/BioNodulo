"""Stable compatibility ID for the audited embedding operation."""

from __future__ import annotations

from .ai_embedding import AIEmbeddingNode


class EmbeddingGenerationNode(AIEmbeddingNode):
    """Compatibility wrapper for the original embedding generation roadmap node ID."""

    NODE_ID = "embedding_generation"
    DISPLAY_NAME = "Embedding Generation"
    DESCRIPTION = "Generate embedding vectors for biological sequences or text."
    SEARCH_ALIASES = [
        "embedding generation",
        "embedding",
        "vector",
        "esm",
        "dnabert",
        "transformer",
        "representation",
        "encode",
        "features",
    ]
