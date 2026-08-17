"""Evo 2 sequence scoring: forward-pass embeddings plus a likelihood score.

The NIM ``generate`` endpoint requires ``num_tokens >= 1`` (Evo 2 NIM docs
default 100, minimum 1), so true zero-token per-position logprobs of the prompt
are not retrievable. What this node computes instead, and reports as such:

* ``mean_log_prob``: mean natural-log sampled probability over a short
  deterministic continuation window (default 10 sampled bases) -- sequences the
  model continues with high confidence score higher;
* ``embedding``: ``output_layer`` activations from ``/forward``, decoded from
  the base64 NPZ response and saved next to the scores.
"""

from __future__ import annotations

import math
from typing import Any


from .adapter import (
    NIM_DEFAULT_RPM,
    NIM_HOSTED_RPM,
    NIM_REQUEST_TIMEOUT_S,
    NimClient,
    NimInferenceNode,
    decode_base64_npz,
    bounded_float,
    bounded_int,
    fixture_embedding,
    fixture_seed_hex,
    node_output_dir,
    parse_bool,
    require_artifacts,
    resolve_api_key,
    resolve_base_url,
    save_npz,
    write_json,
)
from .nim_evo2_generate import (
    EVO2_CITATION_DOI,
    EVO2_DOCUMENTATION_URL,
    normalize_dna_sequence,
    parse_sequence_input,
)


EVO2_FORWARD_ENDPOINT = "arc/evo2-40b/forward"
EVO2_GENERATE_ENDPOINT = "arc/evo2-40b/generate"
DEFAULT_CONTINUATION_TOKENS = 10
FIXTURE_EMBEDDING_DIM = 32


class NimEvo2ScoreNode(NimInferenceNode):
    """Score a DNA sequence with Evo 2: forward embedding + continuation likelihood."""

    NODE_ID = "nim_evo2_score"
    DISPLAY_NAME = "NIM Evo2 Score"
    DESCRIPTION = (
        "Score one DNA sequence with Evo 2 via the NVIDIA biology NIM: output_layer "
        "activations from /forward saved as NPZ plus a mean-log-sampled-probability "
        "continuation score from /generate (num_tokens>=1 is required by the NIM, so "
        "prompt-only per-position logprobs are not available)."
    )
    SEARCH_ALIASES = ["nim", "nvidia", "evo2", "score", "likelihood", "embedding", "variant effect"]
    RETURN_TYPES = ("JSON", "FILE")
    RETURN_NAMES = ("scores_json", "embedding_npz")
    CITATION_DOIS = [EVO2_CITATION_DOI]
    CITATION_URLS = [f"https://doi.org/{EVO2_CITATION_DOI}"]
    CITATION_TEXT = "Brixi et al. 2026. Genome modelling and design across all domains of life with Evo 2. Nature."
    DOCUMENTATION_URL = EVO2_DOCUMENTATION_URL
    REQUIRED_CONDA_PACKAGES = ["numpy"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sequence": ("STRING", {"default": "", "multiline": True, "description": "DNA sequence, FASTA record, or FASTA file path"}),
            },
            "optional": {
                "alphabet": ("STRING", {"default": "dna", "options": ["dna", "rna"]}),
                "continuation_tokens": ("INT", {"default": DEFAULT_CONTINUATION_TOKENS, "min": 1, "max": 256, "description": "Sampled continuation window used for the likelihood score"}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05}),
                "output_layers": ("STRING", {"default": "[\"output_layer\"]", "multiline": True, "description": "JSON list of /forward layer names, e.g. output_layer, embedding, decoder.layers.N.mlp"}),
                "api_key": ("STRING", {"default": "", "advanced": True}),
                "base_url": ("STRING", {"default": "", "advanced": True}),
                "requests_per_minute": ("FLOAT", {"default": NIM_DEFAULT_RPM, "min": 0, "max": NIM_HOSTED_RPM}),
                "timeout": ("FLOAT", {"default": NIM_REQUEST_TIMEOUT_S, "min": 1, "max": 3600}),
                "fixture_mode": ("BOOLEAN", {"default": False, "description": "Return deterministic non-scientific fixture output without any network call"}),
            },
            "hidden": {"context": ("CONTEXT", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        raw = str(inputs.get("sequence", "") or "")
        if not raw.strip():
            return "sequence must be a non-empty DNA string, FASTA record, or FASTA file path"
        alphabet = str(inputs.get("alphabet", "dna") or "dna").lower()
        if alphabet not in {"dna", "rna"}:
            return "alphabet must be one of: dna, rna"
        try:
            from .adapter import parse_json_list

            _record_id, sequence = parse_sequence_input(raw)
            normalize_dna_sequence(sequence, alphabet)
            layers = parse_json_list(inputs.get("output_layers") or '["output_layer"]', "output_layers")
        except (ValueError, OSError) as exc:
            return str(exc)
        if not layers or not all(isinstance(item, str) and item.strip() for item in layers):
            return "output_layers must be a non-empty JSON list of layer names"
        for field, minimum, maximum, default in (
            ("continuation_tokens", 1, 256, DEFAULT_CONTINUATION_TOKENS),
        ):
            value = inputs.get(field, default)
            if value in (None, ""):
                value = default
            try:
                number = int(value)
            except (TypeError, ValueError):
                return f"{field} must be an integer"
            if number < minimum or number > maximum:
                return f"{field} must be between {minimum} and {maximum}"
        return True

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")
        record_id, raw_sequence = parse_sequence_input(str(kwargs.get("sequence", "")))
        alphabet = str(kwargs.get("alphabet", "dna") or "dna").lower()
        sequence = normalize_dna_sequence(raw_sequence, alphabet)
        continuation_tokens = bounded_int(
            kwargs.get("continuation_tokens"), "continuation_tokens", 1, 256, DEFAULT_CONTINUATION_TOKENS
        )
        temperature = bounded_float(kwargs.get("temperature"), "temperature", 0.0, 2.0, 0.7)
        fixture_mode = parse_bool(kwargs.get("fixture_mode", False), "fixture_mode")

        out_dir = node_output_dir(self, context)
        json_path = out_dir / "evo2_scores.json"
        npz_path = out_dir / "evo2_embedding.npz"

        if fixture_mode:
            seed = fixture_seed_hex("nim_evo2_score", sequence, str(continuation_tokens), str(temperature))
            embedding = fixture_embedding(seed, FIXTURE_EMBEDDING_DIM)
            save_npz(npz_path, {"output_layer": embedding})
            payload = {
                "fixture_mode": True,
                "status": "NON_SCIENTIFIC_FIXTURE_ONLY",
                "model": "arc/evo2-40b",
                "sequence_id": record_id,
                "sequence_length": len(sequence),
                "alphabet": alphabet,
                "mean_log_prob": round(-((int(seed[:4], 16) % 500) + 1) / 100.0, 6),
                "continuation_tokens": continuation_tokens,
                "score_definition": (
                    "mean natural-log sampled probability over a deterministic fixture "
                    "continuation window; not Evo 2 output"
                ),
                "embedding_file": str(npz_path),
                "embedding_dim": FIXTURE_EMBEDDING_DIM,
                "disclaimer": "NON-SCIENTIFIC FIXTURE: deterministic values hashed from the input, not Evo 2 output.",
            }
        else:
            from .adapter import parse_json_list

            layers = [str(item).strip() for item in parse_json_list(kwargs.get("output_layers") or '["output_layer"]', "output_layers") if str(item).strip()]
            if not layers:
                raise ValueError("output_layers must be a non-empty JSON list of layer names")
            api_key = resolve_api_key(kwargs.get("api_key", ""), context)
            client = NimClient(
                base_url=resolve_base_url(kwargs.get("base_url", "")),
                api_key=api_key,
                requests_per_minute=bounded_float(
                    kwargs.get("requests_per_minute"), "requests_per_minute", 0, NIM_HOSTED_RPM, NIM_DEFAULT_RPM
                ),
                timeout=bounded_float(kwargs.get("timeout"), "timeout", 1.0, 3600.0, NIM_REQUEST_TIMEOUT_S),
            )
            generate_body = await client.post_json_ok(
                EVO2_GENERATE_ENDPOINT,
                {
                    "sequence": sequence,
                    "num_tokens": continuation_tokens,
                    "temperature": temperature,
                    "top_k": 3,
                    "enable_sampled_probs": True,
                },
            )
            mean_log_prob = _mean_log_prob(generate_body.get("sampled_probs"))
            forward_body = await client.post_json_ok(
                EVO2_FORWARD_ENDPOINT,
                {"sequence": sequence, "output_layers": layers},
            )
            arrays = decode_base64_npz(forward_body.get("data", ""))
            save_npz(npz_path, arrays)
            payload = {
                "fixture_mode": False,
                "model": "arc/evo2-40b",
                "sequence_id": record_id,
                "sequence_length": len(sequence),
                "alphabet": alphabet,
                "mean_log_prob": mean_log_prob,
                "continuation_tokens": continuation_tokens,
                "score_definition": (
                    "mean natural-log sampled probability over the sampled continuation window; "
                    "the NIM generate endpoint requires num_tokens>=1, so prompt-only "
                    "per-position logprobs are not available"
                ),
                "embedding_file": str(npz_path),
                "embedding_layers": sorted(arrays),
                "elapsed_ms": forward_body.get("elapsed_ms"),
            }

        write_json(json_path, payload)
        require_artifacts(json_path, npz_path)
        return {"outputs": {"scores_json": str(json_path), "embedding_npz": str(npz_path)}}


def _mean_log_prob(sampled_probs: Any) -> float | None:
    if not isinstance(sampled_probs, list) or not sampled_probs:
        return None
    flat: list[float] = []
    for item in sampled_probs:
        if isinstance(item, list):
            flat.extend(float(value) for value in item if isinstance(value, (int, float)) and not isinstance(value, bool))
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            flat.append(float(item))
    if not flat:
        return None
    return round(sum(math.log(max(1e-12, value)) for value in flat) / len(flat), 6)


__all__ = ["NimEvo2ScoreNode"]
