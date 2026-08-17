"""Boltz-2 biomolecular structure prediction via the NVIDIA biology NIM.

The hosted NIM answers ``POST /v1/biology/mit/boltz2/predict`` either
synchronously (200 with the result) or asynchronously (202 plus a request id
polled at ``GET /v1/status/{request_id}`` with the ``NVCF-POLL-SECONDS``
header). Both paths are handled here.
"""

from __future__ import annotations

import re
from typing import Any


from .adapter import (
    NIM_DEFAULT_RPM,
    NIM_HOSTED_RPM,
    NIM_POLL_SECONDS_DEFAULT,
    NIM_REQUEST_TIMEOUT_S,
    NimClient,
    NimInferenceNode,
    bounded_float,
    bounded_int,
    fixture_seed_hex,
    node_output_dir,
    parse_bool,
    parse_json_object,
    require_artifacts,
    resolve_api_key,
    resolve_base_url,
    resolve_status_url,
    write_json,
)


BOLTZ2_ENDPOINT = "mit/boltz2/predict"
BOLTZ2_DOCUMENTATION_URL = "https://docs.nvidia.com/nim/bionemo/boltz2/1.1.0/inference.html"
BOLTZ2_CITATION_DOI = "10.1101/2025.06.14.659707"
BOLTZ2_GITHUB_URL = "https://github.com/jwohlwend/boltz"
BOLTZ2_DEFAULT_TIMEOUT_S = 600.0
BOLTZ2_MAX_POLYMERS = 12
BOLTZ2_MAX_LIGANDS = 20
MOLECULE_TYPES = ("protein", "dna", "rna")
PROTEIN_ALPHABET = frozenset("ARNDCQEGHILKMFPSTWYVXBOU")
NUCLEIC_ALPHABET = frozenset("ACGTU")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,16}$")
MOCK_MMCIF_PREFIX = "data_fixture_structure\n#\n"


def parse_polymers(value: Any) -> list[dict[str, Any]]:
    parsed = parse_json_object(value, "polymers")
    if not parsed:
        raise ValueError("polymers must be a non-empty JSON object of {name: {type, sequence, count}}")
    polymers: list[dict[str, Any]] = []
    for name, spec in parsed.items():
        if not _SAFE_ID.fullmatch(str(name)):
            raise ValueError(f"polymer id {name!r} must be 1-16 characters of letters, digits, '_', '-', '.'")
        spec_map = spec if isinstance(spec, dict) else {}
        molecule_type = str(spec_map.get("type", "protein") or "protein").lower()
        if molecule_type not in MOLECULE_TYPES:
            raise ValueError(f"polymer {name!r} type must be one of: {', '.join(MOLECULE_TYPES)}")
        sequence = "".join(str(spec_map.get("sequence", "")).upper().split())
        if not sequence:
            raise ValueError(f"polymer {name!r} sequence is empty")
        alphabet = PROTEIN_ALPHABET if molecule_type == "protein" else NUCLEIC_ALPHABET
        invalid = sorted(set(sequence) - alphabet)
        if invalid:
            raise ValueError(f"polymer {name!r} sequence has invalid characters for {molecule_type}: {''.join(invalid)}")
        count = _count_value(spec_map.get("count", 1), f"polymer {name!r} count")
        polymers.append({"id": str(name), "molecule_type": molecule_type, "sequence": sequence, "count": count})
    if len(polymers) > BOLTZ2_MAX_POLYMERS:
        raise ValueError(f"Boltz 2 accepts at most {BOLTZ2_MAX_POLYMERS} polymers; got {len(polymers)}")
    return polymers


def parse_ligands(value: Any) -> list[dict[str, Any]]:
    parsed = parse_json_object(value, "ligands")
    if not parsed:
        return []
    ligands: list[dict[str, Any]] = []
    for name, spec in parsed.items():
        if not _SAFE_ID.fullmatch(str(name)):
            raise ValueError(f"ligand id {name!r} must be 1-16 characters of letters, digits, '_', '-', '.'")
        spec_map = spec if isinstance(spec, dict) else {}
        ccd = str(spec_map.get("ccd", "") or "").strip()
        smiles = str(spec_map.get("smiles", "") or "").strip()
        if bool(ccd) == bool(smiles):
            raise ValueError(f"ligand {name!r} must specify exactly one of ccd or smiles")
        ligands.append({"id": str(name), "ccd": ccd, "smiles": smiles, "count": _count_value(spec_map.get("count", 1), f"ligand {name!r} count")})
    if len(ligands) > BOLTZ2_MAX_LIGANDS:
        raise ValueError(f"Boltz 2 accepts at most {BOLTZ2_MAX_LIGANDS} ligands; got {len(ligands)}")
    return ligands


def _count_value(value: Any, field_name: str) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if count < 1 or count > 100:
        raise ValueError(f"{field_name} must be between 1 and 100")
    return count


class NimBoltz2PredictNode(NimInferenceNode):
    """Predict biomolecular complexes with Boltz-2 via the NVIDIA biology NIM."""

    NODE_ID = "nim_boltz2_predict"
    DISPLAY_NAME = "NIM Boltz2 Predict"
    DESCRIPTION = (
        "Predict protein/DNA/RNA complex structures (optionally with CCD or SMILES ligands) "
        "with MIT Boltz-2 via the NVIDIA biology NIM. Handles both immediate 200 responses "
        "and 202 + /v1/status/{id} polling with the NVCF-POLL-SECONDS header. "
        "Self-hosted NIM containers: set base_url to http://localhost:8000/v1/biology."
    )
    SEARCH_ALIASES = ["nim", "nvidia", "boltz", "boltz2", "structure", "folding", "complex", "affinity", "mmcif"]
    RETURN_TYPES = ("JSON", "FILE")
    RETURN_NAMES = ("prediction_json", "structure_file")
    CITATION_DOIS = [BOLTZ2_CITATION_DOI]
    CITATION_URLS = [f"https://doi.org/{BOLTZ2_CITATION_DOI}", BOLTZ2_GITHUB_URL]
    CITATION_TEXT = "Passaro et al. 2025. Boltz-2: Towards Accurate and Efficient Binding Affinity Prediction. bioRxiv."
    DOCUMENTATION_URL = BOLTZ2_DOCUMENTATION_URL

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "polymers": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "description": 'JSON object {"A": {"type": "protein", "sequence": "MVL...", "count": 1}, "B": {"type": "rna", "sequence": "GAGA...", "count": 1}}',
                    },
                ),
            },
            "optional": {
                "ligands": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "description": 'JSON object {"ATP": {"ccd": "ATP", "count": 1}} or {"inhib": {"smiles": "CCO...", "count": 1}}',
                    },
                ),
                "recycling_steps": ("INT", {"default": 3, "min": 1, "max": 6}),
                "sampling_steps": ("INT", {"default": 50, "min": 10, "max": 1000}),
                "diffusion_samples": ("INT", {"default": 1, "min": 1, "max": 5}),
                "poll_seconds": ("INT", {"default": NIM_POLL_SECONDS_DEFAULT, "min": 1, "max": 60}),
                "poll_timeout": ("FLOAT", {"default": BOLTZ2_DEFAULT_TIMEOUT_S, "min": 10, "max": 86400, "description": "Total async wait budget in seconds"}),
                "api_key": ("STRING", {"default": "", "advanced": True}),
                "base_url": ("STRING", {"default": "", "advanced": True}),
                "status_url": ("STRING", {"default": "", "advanced": True, "description": "Override async status base URL (default https://health.api.nvidia.com/v1/status)"}),
                "requests_per_minute": ("FLOAT", {"default": NIM_DEFAULT_RPM, "min": 0, "max": NIM_HOSTED_RPM}),
                "timeout": ("FLOAT", {"default": NIM_REQUEST_TIMEOUT_S, "min": 1, "max": 3600, "description": "Per-request HTTP timeout"}),
                "fixture_mode": ("BOOLEAN", {"default": False, "description": "Return deterministic non-scientific fixture output without any network call"}),
            },
            "hidden": {"context": ("CONTEXT", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("polymers", "") or "").strip():
            return "polymers must be a non-empty JSON object of {name: {type, sequence, count}}"
        try:
            parse_polymers(inputs.get("polymers"))
            parse_ligands(inputs.get("ligands"))
        except ValueError as exc:
            return str(exc)
        for field, minimum, maximum, default in (
            ("recycling_steps", 1, 6, 3),
            ("sampling_steps", 10, 1000, 50),
            ("diffusion_samples", 1, 5, 1),
            ("poll_seconds", 1, 60, NIM_POLL_SECONDS_DEFAULT),
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
        polymers = parse_polymers(kwargs.get("polymers"))
        ligands = parse_ligands(kwargs.get("ligands"))
        poll_seconds = bounded_int(kwargs.get("poll_seconds"), "poll_seconds", 1, 60, NIM_POLL_SECONDS_DEFAULT)
        poll_timeout = bounded_float(kwargs.get("poll_timeout"), "poll_timeout", 10.0, 86400.0, BOLTZ2_DEFAULT_TIMEOUT_S)
        fixture_mode = parse_bool(kwargs.get("fixture_mode", False), "fixture_mode")

        out_dir = node_output_dir(self, context)
        json_path = out_dir / "boltz2_prediction.json"
        structure_path = out_dir / "boltz2_structure_0.mmcif"

        payload_body = {
            "polymers": polymers,
            **({"ligands": ligands} if ligands else {}),
            "recycling_steps": bounded_int(kwargs.get("recycling_steps"), "recycling_steps", 1, 6, 3),
            "sampling_steps": bounded_int(kwargs.get("sampling_steps"), "sampling_steps", 10, 1000, 50),
            "diffusion_samples": bounded_int(kwargs.get("diffusion_samples"), "diffusion_samples", 1, 5, 1),
            "output_format": "mmcif",
        }

        if fixture_mode:
            seed = fixture_seed_hex("nim_boltz2_predict", repr(payload_body))
            structure_path.write_text(MOCK_MMCIF_PREFIX + f"# fixture seed {seed[:16]}\n", encoding="utf-8")
            payload = {
                "fixture_mode": True,
                "status": "NON_SCIENTIFIC_FIXTURE_ONLY",
                "model": "mit/boltz2",
                "mode": "fixture",
                "polymers": [polymer["id"] for polymer in polymers],
                "ligands": [ligand["id"] for ligand in ligands],
                "confidence_scores": [round((int(seed[:4], 16) % 1000) / 1000.0, 3)],
                "structure_file": str(structure_path),
                "structure_format": "mmcif",
                "disclaimer": "NON-SCIENTIFIC FIXTURE: deterministic placeholder mmCIF text, not Boltz-2 output.",
            }
        else:
            api_key = resolve_api_key(kwargs.get("api_key", ""), context)
            base_url = resolve_base_url(kwargs.get("base_url", ""))
            client = NimClient(
                base_url=base_url,
                api_key=api_key,
                requests_per_minute=bounded_float(
                    kwargs.get("requests_per_minute"), "requests_per_minute", 0, NIM_HOSTED_RPM, NIM_DEFAULT_RPM
                ),
                timeout=bounded_float(kwargs.get("timeout"), "timeout", 1.0, 3600.0, NIM_REQUEST_TIMEOUT_S),
            )
            response = await client.post_json(BOLTZ2_ENDPOINT, payload_body)
            if response.status_code >= 400:
                raise RuntimeError(f"Boltz 2 submit failed with HTTP {response.status_code}: {response.text[:500]}")
            mode = "synchronous"
            body = _json_or_empty(response)
            if response.status_code == 202 or not _looks_final(body):
                request_id = _request_id(body, response.headers)
                if not request_id:
                    raise RuntimeError("Boltz 2 returned 202 without a request id to poll")
                mode = "async-poll"
                body = await client.poll_until_done(
                    f"{resolve_status_url(kwargs.get('status_url', ''), base_url)}/{request_id}",
                    poll_seconds=poll_seconds,
                    timeout_s=poll_timeout,
                )
            structures = body.get("structures") or []
            if not structures:
                raise RuntimeError("Boltz 2 response contains no structures")
            first = structures[0] if isinstance(structures[0], dict) else {"structure": str(structures[0])}
            content = str(first.get("structure", ""))
            structure_path.write_text(content, encoding="utf-8")
            payload = {
                "fixture_mode": False,
                "model": "mit/boltz2",
                "endpoint": BOLTZ2_ENDPOINT,
                "mode": mode,
                "polymers": [polymer["id"] for polymer in polymers],
                "ligands": [ligand["id"] for ligand in ligands],
                "confidence_scores": body.get("confidence_scores"),
                "metrics": body.get("metrics"),
                "structure_count": len(structures),
                "structure_file": str(structure_path),
                "structure_format": first.get("format", "mmcif"),
            }

        write_json(json_path, payload)
        require_artifacts(json_path, structure_path)
        return {"outputs": {"prediction_json": str(json_path), "structure_file": str(structure_path)}}


def _json_or_empty(response: Any) -> dict[str, Any]:
    try:
        parsed = response.json()
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _looks_final(body: dict[str, Any]) -> bool:
    return bool(body.get("structures")) or bool(body.get("confidence_scores"))


def _request_id(body: dict[str, Any], headers: Any) -> str:
    for key in ("request_id", "req_id", "id", "requestId"):
        value = body.get(key)
        if value:
            return str(value)
    for header in ("x-nvcf-reqid", "nvcf-reqid", "x-request-id", "request-id"):
        value = headers.get(header)
        if value:
            return str(value)
    return ""


__all__ = ["BOLTZ2_CITATION_DOI", "BOLTZ2_DOCUMENTATION_URL", "NimBoltz2PredictNode"]
