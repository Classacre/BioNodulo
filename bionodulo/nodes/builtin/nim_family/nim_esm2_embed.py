"""ESM-2 650M protein embeddings via the NVIDIA biology NIM."""

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
    fixture_embedding,
    fixture_seed_hex,
    load_npz_bytes,
    mean_pool,
    node_output_dir,
    parse_bool,
    require_artifacts,
    resolve_api_key,
    resolve_base_url,
    save_npz,
    write_json,
)


ESM2_ENDPOINT = "meta/esm2-650m"
ESM2_DOCUMENTATION_URL = "https://docs.api.nvidia.com/nim/reference/meta-esm2-650m-infer"
ESM2_CITATION_DOI = "10.1126/science.ade2574"
ESM2_MAX_SEQUENCE_LENGTH = 1024
ESM2_MAX_SEQUENCES_PER_REQUEST = 32
ESM2_ALPHABET = frozenset("ARNDCQEGHILKMFPSTWYVXBOU")
ESM2_ALPHABET_TEXT = "ARNDCQEGHILKMFPSTWYVXBOU"
FIXTURE_EMBEDDING_DIM = 32


def parse_protein_records(value: str) -> list[dict[str, str]]:
    text = str(value or "")
    if not text.strip():
        raise ValueError("sequences input is empty")
    stripped = text.lstrip()
    if stripped.startswith(">"):
        records = _fasta_records(text)
        if not records:
            raise ValueError("sequences FASTA input contains no records")
        return records
    candidate = text.strip()
    if "\n" not in candidate and "\r" not in candidate:
        path = Path(candidate).expanduser()
        if path_probe_is_file(text):
            return parse_protein_records(path.read_text(encoding="utf-8-sig"))
    records = []
    for index, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line or line.startswith(">"):
            continue
        records.append({"id": f"seq_{index}", "sequence": line})
    if not records:
        raise ValueError("sequences input is empty")
    return records


def _fasta_records(content: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current_id = ""
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_id, current_lines
        if current_id:
            sequence = "".join(current_lines)
            if sequence:
                records.append({"id": current_id, "sequence": sequence})
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


def validate_protein_sequence(sequence: str) -> str:
    cleaned = "".join(str(sequence).upper().split())
    if not cleaned:
        raise ValueError("protein sequence is empty")
    invalid = sorted(set(cleaned) - ESM2_ALPHABET)
    if invalid:
        raise ValueError(f"ESM 2 accepts amino acids {ESM2_ALPHABET_TEXT} only; found: {''.join(invalid)}")
    if len(cleaned) > ESM2_MAX_SEQUENCE_LENGTH:
        raise ValueError(f"ESM 2 sequences must be at most {ESM2_MAX_SEQUENCE_LENGTH} AA; got {len(cleaned)}")
    return cleaned


class NimESM2EmbedNode(NimInferenceNode):
    """Mean-pooled ESM 2 650M protein embeddings via the NVIDIA biology NIM."""

    NODE_ID = "nim_esm2_embed"
    DISPLAY_NAME = "NIM ESM2 Embed"
    DESCRIPTION = (
        "Embed protein sequences with Meta ESM2 650M via the NVIDIA biology NIM. "
        "Sequences are validated (<=1024 AA, standard alphabet), chunked at 32 per request, "
        "and mean-pooled per sequence into JSON/TSV plus the raw NPZ response."
    )
    SEARCH_ALIASES = ["nim", "nvidia", "esm2", "protein", "embedding", "language model", "plm"]
    RETURN_TYPES = ("JSON", "FILE", "TSV")
    RETURN_NAMES = ("embeddings_json", "raw_npz", "embeddings_tsv")
    CITATION_DOIS = [ESM2_CITATION_DOI]
    CITATION_URLS = [f"https://doi.org/{ESM2_CITATION_DOI}"]
    CITATION_TEXT = "Lin et al. 2023. Evolutionary-scale prediction of atomic-level protein structure with a language model. Science."
    DOCUMENTATION_URL = ESM2_DOCUMENTATION_URL
    REQUIRED_CONDA_PACKAGES = ["numpy"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sequences": ("STRING", {"default": "", "multiline": True, "description": "Protein sequences: one per line, FASTA text, or a FASTA file path"}),
            },
            "optional": {
                "format": ("STRING", {"default": "npz", "options": ["npz", "json"]}),
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
        raw = str(inputs.get("sequences", "") or "")
        if not raw.strip():
            return "sequences must be a non-empty FASTA text, one-sequence-per-line text, or FASTA file path"
        fmt = str(inputs.get("format", "npz") or "npz").lower()
        if fmt not in {"npz", "json"}:
            return "format must be one of: npz, json"
        try:
            records = parse_protein_records(raw)
            for record in records:
                validate_protein_sequence(record["sequence"])
        except (ValueError, OSError) as exc:
            return str(exc)
        return True

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")
        records = parse_protein_records(str(kwargs.get("sequences", "")))
        for record in records:
            record["sequence"] = validate_protein_sequence(record["sequence"])
        fmt = str(kwargs.get("format", "npz") or "npz").lower()
        fixture_mode = parse_bool(kwargs.get("fixture_mode", False), "fixture_mode")

        out_dir = node_output_dir(self, context)
        json_path = out_dir / "esm2_embeddings.json"
        tsv_path = out_dir / "esm2_embeddings.tsv"
        npz_path = out_dir / "esm2_raw.npz"

        if fixture_mode:
            embeddings = [
                {
                    "id": record["id"],
                    "length": len(record["sequence"]),
                    "mean_pooled_embedding": fixture_embedding(
                        fixture_seed_hex("nim_esm2_embed", record["id"], record["sequence"]), FIXTURE_EMBEDDING_DIM
                    ),
                }
                for record in records
            ]
            payload = {
                "fixture_mode": True,
                "status": "NON_SCIENTIFIC_FIXTURE_ONLY",
                "model": "meta/esm2-650m",
                "sequence_count": len(records),
                "embedding_dim": FIXTURE_EMBEDDING_DIM,
                "embeddings": embeddings,
                "raw_npz": str(npz_path),
                "disclaimer": "NON-SCIENTIFIC FIXTURE: deterministic values hashed from the input, not ESM 2 output.",
            }
            save_npz(npz_path, {record["id"]: embedding["mean_pooled_embedding"] for record, embedding in zip(records, embeddings, strict=True)})
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
            per_sequence: list[list[float] | None] = [None] * len(records)
            raw_arrays: dict[str, Any] = {}
            for offset in range(0, len(records), ESM2_MAX_SEQUENCES_PER_REQUEST):
                chunk = records[offset : offset + ESM2_MAX_SEQUENCES_PER_REQUEST]
                response = await client.post_json(ESM2_ENDPOINT, {"sequences": [record["sequence"] for record in chunk], "format": fmt})
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"ESM 2 endpoint failed with HTTP {response.status_code}: {response.text[:300]}"
                    )
                content_type = str(response.headers.get("content-type", "")).split(";", 1)[0].strip().lower()
                arrays = _arrays_from_json(response.json(), chunk) if "json" in content_type else load_npz_bytes(response.content)
                aligned = _align_arrays(arrays, chunk)
                for position, (record, array) in enumerate(zip(chunk, aligned, strict=True)):
                    raw_key = record["id"] if len(chunk) == len(set(item["id"] for item in chunk)) else f"{record['id']}_{position}"
                    raw_arrays[raw_key] = array
                    per_sequence[offset + position] = mean_pool(array) if array is not None else None
            embeddings = [
                {
                    "id": record["id"],
                    "length": len(record["sequence"]),
                    "mean_pooled_embedding": vector if vector is not None else [],
                }
                for record, vector in zip(records, per_sequence, strict=True)
            ]
            save_npz(npz_path, raw_arrays)
            payload = {
                "fixture_mode": False,
                "model": "meta/esm2-650m",
                "endpoint": ESM2_ENDPOINT,
                "format": fmt,
                "sequence_count": len(records),
                "embedding_dim": len(embeddings[0]["mean_pooled_embedding"]) if embeddings else 0,
                "embeddings": embeddings,
                "raw_npz": str(npz_path),
            }

        write_json(json_path, payload)
        _write_tsv(tsv_path, payload["embeddings"])
        require_artifacts(json_path, tsv_path, npz_path)
        return {"outputs": {"embeddings_json": str(json_path), "raw_npz": str(npz_path), "embeddings_tsv": str(tsv_path)}}


def _arrays_from_json(body: Any, chunk: list[dict[str, str]]) -> dict[str, Any]:
    np = _numpy_or_raise()
    if not isinstance(body, dict):
        raise RuntimeError("ESM 2 JSON response must be an object")
    values = body.get("embeddings", body.get("data", body.get("results")))
    if values is None:
        raise RuntimeError("ESM 2 JSON response has no embeddings/data field")
    if isinstance(values, dict):
        return dict(values)
    if not isinstance(values, list):
        raise RuntimeError("ESM 2 JSON embeddings field must be a list or object")
    return {str(index): np.asarray(values[index], dtype="float64") for index in range(len(values))}


def _align_arrays(arrays: dict[str, Any], chunk: list[dict[str, str]]) -> list[Any]:
    by_id = {record["id"]: arrays[record["id"]] for record in chunk if record["id"] in arrays}
    if len(by_id) == len(chunk):
        return [by_id[record["id"]] for record in chunk]
    positional = list(arrays.values())
    if len(positional) == len(chunk):
        return positional
    if len(chunk) == 1 and len(positional) >= 1:
        return [positional[0]]
    raise RuntimeError(
        f"ESM 2 response carries {len(positional)} arrays for {len(chunk)} requested sequences; cannot align"
    )


def _numpy_or_raise() -> Any:
    from .adapter import _numpy

    return _numpy()


def _write_tsv(path: Path, embeddings: list[dict[str, Any]]) -> None:
    lines = ["id\tlength\tdim\tmean_pooled_embedding"]
    for item in embeddings:
        vector = item.get("mean_pooled_embedding") or []
        rendered = ",".join(f"{float(value):.8f}" for value in vector)
        lines.append(f"{item['id']}\t{item['length']}\t{len(vector)}\t{rendered}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = ["ESM2_CITATION_DOI", "ESM2_DOCUMENTATION_URL", "NimESM2EmbedNode", "validate_protein_sequence"]
