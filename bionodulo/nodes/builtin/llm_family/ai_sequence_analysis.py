"""LLM-assisted analysis of explicit FASTA records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapter import LiteLLMNode, _llm_config_from_kwargs, _messages, call_llm, safe_json_parse, validate_choice


class AISequenceAnalysisNode(LiteLLMNode):
    """Analyze FASTA sequences with an LLM."""

    NODE_ID = "ai_sequence_analysis"
    DISPLAY_NAME = "AI Sequence Analysis"
    CATEGORY = "ai"
    DESCRIPTION = "Analyze biological sequences with an LLM for motifs, domains, function, and structure."
    SEARCH_ALIASES = ["sequence", "fasta", "motif", "domain", "protein", "dna", "rna", "function", "llm-sequence"]
    RETURN_TYPES = ("JSON", "STRING")
    RETURN_NAMES = ("analysis_json", "summary_text")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["litellm", "biopython"]
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Input FASTA file with sequences to analyze"}),
                "analysis_type": (
                    "STRING",
                    {
                        "default": "comprehensive",
                        "options": ["comprehensive", "motifs", "domains", "function", "structure", "custom"],
                    },
                ),
            },
            "optional": {
                "custom_prompt": ("STRING", {"default": "", "multiline": True}),
                "max_sequences": ("INT", {"default": 10, "min": 1, "max": 100}),
                "max_seq_length": ("INT", {"default": 2000, "min": 1, "max": 10000}),
                "molecule_type": ("STRING", {"default": "auto", "options": ["auto", "protein", "dna", "rna"]}),
                "provider": (["openai", "anthropic", "openrouter", "litellm", "custom"], {"default": "openai"}),
                "model": ("STRING", {"default": "", "description": "Provider model name"}),
                "api_key": ("STRING", {"default": "", "password": True, "description": "Optional API key override"}),
                "api_base": ("STRING", {"default": "", "description": "Optional compatible API base URL"}),
                "temperature": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 1.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 128000, "step": 1}),
                "timeout": ("FLOAT", {"default": 60.0, "min": 1.0, "max": 600.0, "step": 1.0}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        sequences = _read_fasta_records(
            kwargs.get("input_fasta", ""),
            max_sequences=int(kwargs.get("max_sequences", 10) or 10),
            max_seq_length=int(kwargs.get("max_seq_length", 2000) or 2000),
        )
        analysis_type = validate_choice(
            kwargs.get("analysis_type", "comprehensive"),
            "analysis_type",
            ("comprehensive", "motifs", "domains", "function", "structure", "custom"),
        )
        molecule_type = validate_choice(
            kwargs.get("molecule_type", "auto"),
            "molecule_type",
            ("auto", "protein", "dna", "rna"),
        )
        if analysis_type == "custom" and not str(kwargs.get("custom_prompt", "") or "").strip():
            raise ValueError("custom_prompt is required when analysis_type is custom")

        if not sequences:
            payload = {
                "input_fasta": str(kwargs.get("input_fasta", "")),
                "analysis_type": analysis_type,
                "sequence_count": 0,
                "molecule_type": molecule_type,
                "sequences": [],
                "analysis": {},
                "usage": {},
            }
            return (json.dumps(payload, indent=2, sort_keys=True), "No sequences found in FASTA input.")

        prompt = _sequence_analysis_prompt(
            sequences=sequences,
            analysis_type=analysis_type,
            molecule_type=molecule_type,
            custom_prompt=str(kwargs.get("custom_prompt", "") or ""),
        )
        config = _llm_config_from_kwargs(kwargs)
        response = await call_llm(
            config,
            _messages(
                system_prompt=(
                    "You are a bioinformatics sequence analysis assistant. Provide cautious, structured findings "
                    "and distinguish evidence from speculation."
                ),
                prompt=prompt,
            ),
            json_mode=True,
        )
        analysis = safe_json_parse(response.content)
        summary = str(analysis.get("summary") or analysis.get("summary_text") or response.content)
        payload = {
            "input_fasta": str(kwargs.get("input_fasta", "")),
            "analysis_type": analysis_type,
            "sequence_count": len(sequences),
            "molecule_type": molecule_type,
            "sequences": sequences,
            "analysis": analysis,
            "usage": response.usage,
            "model": response.model or config.model,
        }
        return (json.dumps(payload, indent=2, sort_keys=True), summary)


_SEQUENCE_ANALYSIS_PROMPTS = {
    "comprehensive": (
        "Analyze the biological sequences comprehensively. Identify likely molecule type, motifs, domains, "
        "functional hints, and notable limitations."
    ),
    "motifs": "Identify conserved motifs, repeat elements, and biologically meaningful sequence patterns.",
    "domains": "Predict functional domains and structural features for the supplied sequences.",
    "function": "Predict likely molecular function and biological process annotations for the supplied sequences.",
    "structure": "Analyze structural features such as transmembrane regions, signal peptides, and disorder.",
}


def _read_fasta_records(path_value: Any, *, max_sequences: int, max_seq_length: int) -> list[dict[str, str]]:
    path = Path(str(path_value))
    if not path.exists():
        raise FileNotFoundError(f"FASTA input not found: {path}")

    records: list[dict[str, str]] = []
    current_header = ""
    current_lines: list[str] = []

    def flush_record() -> None:
        nonlocal current_header, current_lines
        if not current_header:
            return
        sequence = "".join(current_lines).replace(" ", "").replace("\t", "").upper()
        if sequence:
            identifier = current_header.split()[0]
            records.append(
                {
                    "id": identifier,
                    "description": current_header,
                    "sequence": sequence[:max_seq_length],
                    "length": str(len(sequence)),
                }
            )
        current_header = ""
        current_lines = []

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            flush_record()
            current_header = stripped[1:].strip()
            if len(records) >= max_sequences:
                break
        elif current_header:
            current_lines.append(stripped)
    if len(records) < max_sequences:
        flush_record()
    return records[:max_sequences]


def _sequence_analysis_prompt(
    *,
    sequences: list[dict[str, str]],
    analysis_type: str,
    molecule_type: str,
    custom_prompt: str,
) -> str:
    instruction = (
        custom_prompt.strip()
        if analysis_type == "custom" and custom_prompt.strip()
        else _SEQUENCE_ANALYSIS_PROMPTS.get(
            analysis_type,
            _SEQUENCE_ANALYSIS_PROMPTS["comprehensive"],
        )
    )
    sequence_blocks = []
    for record in sequences:
        sequence_blocks.append(
            f">{record['description']}\n"
            f"length={record['length']} truncated_length={len(record['sequence'])}\n"
            f"{record['sequence']}"
        )
    return (
        f"{instruction}\n"
        f"Molecule type hint: {molecule_type}\n\n"
        "Sequences:\n"
        f"{chr(10).join(sequence_blocks)}\n\n"
        "Return a JSON object with keys summary and sequences. Each sequence item should include id, "
        "molecule_type, findings, and confidence where possible."
    )
