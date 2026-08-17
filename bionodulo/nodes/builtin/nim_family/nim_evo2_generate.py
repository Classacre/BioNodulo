"""Evo 2 DNA sequence generation via the NVIDIA biology NIM."""

from __future__ import annotations

from pathlib import Path
from typing import Any


from bionodulo.nodes.base import path_probe_is_file
from .adapter import (
    NIM_DEFAULT_RPM,
    NIM_HOSTED_RPM,
    NIM_REQUEST_TIMEOUT_S,
    NimClient,
    NimInferenceNode,
    bounded_float,
    bounded_int,
    fixture_seed_hex,
    fixture_sequence,
    node_output_dir,
    parse_bool,
    require_artifacts,
    resolve_api_key,
    resolve_base_url,
    write_json,
)


EVO2_ENDPOINT = "arc/evo2-40b/generate"
EVO2_DOCUMENTATION_URL = "https://docs.nvidia.com/nim/bionemo/evo2/latest/endpoints.html"
EVO2_CITATION_DOI = "10.1038/s41586-026-10176-5"
DNA_ALPHABET = "ACGT"


def normalize_dna_sequence(sequence: str, alphabet: str) -> str:
    cleaned = "".join(str(sequence).upper().split())
    if alphabet == "rna":
        cleaned = cleaned.replace("U", "T")
    invalid = sorted(set(cleaned) - set(DNA_ALPHABET))
    if invalid:
        raise ValueError(
            f"Evo 2 accepts DNA characters A, C, G, T only (alphabet={alphabet}); found: {''.join(invalid)}"
        )
    return cleaned


def parse_sequence_input(value: str) -> tuple[str, str]:
    text = str(value or "")
    if not text.strip():
        raise ValueError("sequence input is empty")
    stripped = text.lstrip()
    if stripped.startswith(">"):
        records = _fasta_records(text)
        if not records:
            raise ValueError("sequence FASTA input contains no records")
        record_id, sequence = records[0]
        if len(records) > 1:
            raise ValueError("Evo 2 processes one sequence per call; pass a single FASTA record")
        return record_id, sequence
    candidate = text.strip()
    if "\n" not in candidate and "\r" not in candidate:
        path = Path(candidate).expanduser()
        if path_probe_is_file(text):
            content = path.read_text(encoding="utf-8-sig")
            return parse_sequence_input(content)
    joined = "".join(line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith(">"))
    if not joined:
        raise ValueError("sequence input is empty")
    return "", joined


def _fasta_records(content: str) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    current_id = ""
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_id, current_lines
        if current_id:
            sequence = "".join(current_lines)
            if sequence:
                records.append((current_id, sequence))
        current_id = ""
        current_lines = []

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            flush()
            description = stripped[1:].strip()
            current_id = description.split()[0] if description else f"seq_{len(records)}"
        elif current_id:
            current_lines.append(stripped)
    flush()
    return records


class NimEvo2GenerateNode(NimInferenceNode):
    """Generate DNA bases with Evo 2 through the NVIDIA biology NIM."""

    NODE_ID = "nim_evo2_generate"
    DISPLAY_NAME = "NIM Evo2 Generate"
    DESCRIPTION = (
        "Generate nucleotides with Arc Institute Evo 2 (40B) via the NVIDIA biology NIM. "
        "One sequence per call; loop over inputs for batches. Self-hosted NIM containers: "
        "set base_url to http://localhost:8000/v1/biology (no netguard hop, like the LLM lane)."
    )
    SEARCH_ALIASES = ["nim", "nvidia", "evo2", "dna", "generation", "language model", "design"]
    RETURN_TYPES = ("JSON", "FASTA")
    RETURN_NAMES = ("generation_json", "generated_fasta")
    CITATION_DOIS = [EVO2_CITATION_DOI]
    CITATION_URLS = [f"https://doi.org/{EVO2_CITATION_DOI}"]
    CITATION_TEXT = "Brixi et al. 2026. Genome modelling and design across all domains of life with Evo 2. Nature."
    DOCUMENTATION_URL = EVO2_DOCUMENTATION_URL

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sequence": ("STRING", {"default": "", "multiline": True, "description": "Prompt DNA sequence, FASTA record, or FASTA file path"}),
                "num_tokens": ("INT", {"default": 100, "min": 1, "max": 100000}),
            },
            "optional": {
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05}),
                "top_k": ("INT", {"default": 3, "min": 1, "max": 6}),
                "alphabet": ("STRING", {"default": "dna", "options": ["dna", "rna"]}),
                "api_key": ("STRING", {"default": "", "advanced": True, "description": "NVIDIA NIM API key; defaults to nim_api_key secret or BIONODULO_NIM_API_KEY/NVIDIA_API_KEY"}),
                "base_url": ("STRING", {"default": "", "advanced": True, "description": "Override NIM base URL (self-hosted container: http://localhost:8000/v1/biology)"}),
                "requests_per_minute": ("FLOAT", {"default": NIM_DEFAULT_RPM, "min": 0, "max": NIM_HOSTED_RPM, "description": "Token-bucket rate limit; hosted NIM allows 40 RPM"}),
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
            _record_id, sequence = parse_sequence_input(raw)
            normalize_dna_sequence(sequence, alphabet)
        except (ValueError, OSError) as exc:
            return str(exc)
        for field, minimum, maximum, default in (
            ("num_tokens", 1, 100000, 100),
            ("top_k", 1, 6, 3),
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
        try:
            bounded_float(inputs.get("temperature", 0.7), "temperature", 0.0, 2.0, 0.7)
        except ValueError as exc:
            return str(exc)
        return True

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")
        record_id, sequence = parse_sequence_input(str(kwargs.get("sequence", "")))
        alphabet = str(kwargs.get("alphabet", "dna") or "dna").lower()
        prompt = normalize_dna_sequence(sequence, alphabet)
        num_tokens = bounded_int(kwargs.get("num_tokens"), "num_tokens", 1, 100000, 100)
        temperature = bounded_float(kwargs.get("temperature"), "temperature", 0.0, 2.0, 0.7)
        top_k = bounded_int(kwargs.get("top_k"), "top_k", 1, 6, 3)
        fixture_mode = parse_bool(kwargs.get("fixture_mode", False), "fixture_mode")

        out_dir = node_output_dir(self, context)
        json_path = out_dir / "evo2_generation.json"
        fasta_path = out_dir / "evo2_generated.fasta"

        if fixture_mode:
            seed = fixture_seed_hex("nim_evo2_generate", prompt, str(num_tokens), str(temperature), str(top_k))
            generated = fixture_sequence(seed, DNA_ALPHABET, num_tokens)
            full = prompt + generated
            mean_log_prob = round(-((int(seed[:4], 16) % 500) + 1) / 100.0, 6)
            payload = {
                "fixture_mode": True,
                "status": "NON_SCIENTIFIC_FIXTURE_ONLY",
                "model": "arc/evo2-40b",
                "prompt": prompt,
                "generated_sequence": generated,
                "full_sequence": full,
                "num_tokens": num_tokens,
                "temperature": temperature,
                "top_k": top_k,
                "alphabet": alphabet,
                "mean_log_prob": mean_log_prob,
                "disclaimer": "NON-SCIENTIFIC FIXTURE: deterministic synthetic bases hashed from the input, not Evo 2 output.",
            }
        else:
            api_key = resolve_api_key(kwargs.get("api_key", ""), context)
            client = NimClient(
                base_url=resolve_base_url(kwargs.get("base_url", "")),
                api_key=api_key,
                requests_per_minute=bounded_float(
                    kwargs.get("requests_per_minute"), "requests_per_minute", 0, NIM_HOSTED_RPM, NIM_DEFAULT_RPM
                ),
                timeout=bounded_float(kwargs.get("timeout"), "timeout", 1.0, 3600.0, NIM_REQUEST_TIMEOUT_S),
            )
            body = await client.post_json_ok(
                EVO2_ENDPOINT,
                {
                    "sequence": prompt,
                    "num_tokens": num_tokens,
                    "temperature": temperature,
                    "top_k": top_k,
                    "enable_sampled_probs": True,
                },
            )
            returned = str(body.get("sequence", ""))
            if returned.startswith(prompt):
                generated = returned[len(prompt) :]
                full = returned
            else:
                generated = returned
                full = prompt + returned
            sampled_probs = body.get("sampled_probs")
            mean_log_prob = _mean_log_prob(sampled_probs, len(generated))
            payload = {
                "fixture_mode": False,
                "model": "arc/evo2-40b",
                "endpoint": EVO2_ENDPOINT,
                "prompt": prompt,
                "generated_sequence": generated,
                "full_sequence": full,
                "num_tokens": num_tokens,
                "temperature": temperature,
                "top_k": top_k,
                "alphabet": alphabet,
                "mean_log_prob": mean_log_prob,
                "elapsed_ms": body.get("elapsed_ms"),
            }

        fasta_header = record_id or "evo2_generated"
        fasta_path.write_text(f">{fasta_header} num_tokens={num_tokens}\n{_wrap60(payload['full_sequence'])}\n", encoding="utf-8")
        write_json(json_path, payload)
        require_artifacts(json_path, fasta_path)
        return {"outputs": {"generation_json": str(json_path), "generated_fasta": str(fasta_path)}}


def _wrap60(sequence: str) -> str:
    return "\n".join(sequence[i : i + 60] for i in range(0, len(sequence), 60))


def _mean_log_prob(sampled_probs: Any, generated_length: int) -> float | None:
    if not isinstance(sampled_probs, list) or not sampled_probs:
        return None
    import math

    flat: list[float] = []
    for item in sampled_probs:
        if isinstance(item, list):
            flat.extend(float(value) for value in item if _is_number(value))
        elif _is_number(item):
            flat.append(float(item))
    if not flat:
        return None
    window = flat[-generated_length:] if generated_length > 0 else flat
    if not window:
        return None
    total = sum(math.log(max(1e-12, value)) for value in window)
    return round(total / len(window), 6)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


__all__ = ["EVO2_CITATION_DOI", "EVO2_DOCUMENTATION_URL", "NimEvo2GenerateNode", "normalize_dna_sequence", "parse_sequence_input"]
