"""LLM-assisted interpretation of explicit variant tables."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from .adapter import (
    LiteLLMNode,
    _llm_config_from_kwargs,
    _messages,
    _node_output_dir,
    call_llm,
    require_artifacts,
    safe_json_parse,
    validate_choice,
)


class AIVariantInterpretationNode(LiteLLMNode):
    """Interpret tabular variant annotations with an LLM."""

    NODE_ID = "ai_variant_interpretation"
    DISPLAY_NAME = "AI Variant Interpretation"
    CATEGORY = "ai"
    DESCRIPTION = "Use an LLM to interpret annotated variants with ACMG-style clinical context."
    SEARCH_ALIASES = ["variant", "interpretation", "pathogenicity", "clinical", "acmg", "significance", "vcf"]
    RETURN_TYPES = ("JSON", "CSV")
    RETURN_NAMES = ("interpretation_json", "scores_csv")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["litellm", "pandas"]
    EXPERIMENTAL = True
    AUDIT_STATUS = "contract-checked-no-provider-execution"
    ACMG_GUIDELINE_VERSION = "2015"
    ACMG_GUIDELINE_DOI = "10.1038/gim.2015.30"
    ACMG_GUIDELINE_URL = "https://doi.org/10.1038/gim.2015.30"
    CITATION_DOIS = [ACMG_GUIDELINE_DOI]
    CITATION_URLS = [ACMG_GUIDELINE_URL]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "variant_table": ("FILE", {"description": "CSV or TSV table with variant annotations"}),
            },
            "optional": {
                "framework": ("STRING", {"default": "ACMG", "options": ["ACMG", "research", "clinical_actionable"]}),
                "gene_context": (
                    "STRING",
                    {"default": "", "multiline": True, "description": "Optional disease or panel context"},
                ),
                "include_literature": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Use only explicitly supplied literature_evidence; no retrieval is performed",
                    },
                ),
                "literature_evidence": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "description": "Retrieved or curated evidence with identifiers/citations",
                    },
                ),
                "max_variants": ("INT", {"default": 50, "min": 1, "max": 500}),
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

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        out_dir = _node_output_dir(self, context)
        json_path = out_dir / "interpretation_json.json"
        csv_path = out_dir / "scores_csv.csv"

        variants = _read_variant_table(kwargs.get("variant_table", ""), int(kwargs.get("max_variants", 50) or 50))
        framework = validate_choice(
            kwargs.get("framework", "ACMG"),
            "framework",
            ("ACMG", "research", "clinical_actionable"),
        )
        gene_context = str(kwargs.get("gene_context", "") or "")
        include_literature = bool(kwargs.get("include_literature", False))
        literature_evidence = _literature_evidence_text(kwargs.get("literature_evidence", ""))
        if include_literature and not literature_evidence:
            raise ValueError(
                "include_literature requires explicit retrieved or supplied literature_evidence; "
                "this node does not retrieve evidence"
            )

        if variants:
            config = _llm_config_from_kwargs(kwargs)
            messages = _variant_interpretation_messages(
                variants=variants,
                framework=framework,
                gene_context=gene_context,
                include_literature=include_literature,
                literature_evidence=literature_evidence,
            )
            response = await call_llm(config, messages, json_mode=True)
            parsed = safe_json_parse(response.content)
            interpretations = _normalise_interpretations(parsed, variants)
            usage = response.usage
            model = response.model or config.model
        else:
            interpretations = []
            usage = {}
            model = ""

        payload = {
            "variant_table": str(kwargs.get("variant_table", "")),
            "variant_count": len(variants),
            "framework": framework,
            "gene_context": gene_context,
            "include_literature": include_literature,
            "literature_evidence_supplied": bool(literature_evidence),
            "literature_evidence_sha256": (
                hashlib.sha256(literature_evidence.encode("utf-8")).hexdigest() if literature_evidence else ""
            ),
            "model": model,
            "usage": usage,
            "interpretations": interpretations,
            "disclaimer": (
                "AI-generated variant interpretations are decision support only and require validation "
                "against curated resources and qualified clinical review."
            ),
        }
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_scores_csv(csv_path, interpretations)
        require_artifacts(json_path, csv_path)
        return {"outputs": {"interpretation_json": str(json_path), "scores_csv": str(csv_path)}}


def _read_variant_table(path_value: Any, max_variants: int) -> list[dict[str, str]]:
    path = Path(str(path_value))
    if not path.exists():
        raise FileNotFoundError(f"Variant table not found: {path}")
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return []
    sample = text[:4096]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters="\t,;").delimiter
    except csv.Error:
        delimiter = "\t" if sample.count("\t") >= sample.count(",") else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    variants: list[dict[str, str]] = []
    for row in reader:
        normalized = {str(key or "").strip(): str(value or "").strip() for key, value in row.items()}
        if any(normalized.values()):
            variants.append(normalized)
        if len(variants) >= max_variants:
            break
    return variants


def _variant_interpretation_messages(
    *,
    variants: list[dict[str, str]],
    framework: str,
    gene_context: str,
    include_literature: bool,
    literature_evidence: str,
) -> list[dict[str, str]]:
    variant_lines = []
    for index, variant in enumerate(variants, start=1):
        fields = ", ".join(f"{key}={value}" for key, value in variant.items() if value)
        variant_lines.append(f"{index}. {fields}")
    literature_instruction = (
        "Use only the supplied literature evidence below; cite its explicit identifiers and do not add other sources."
        if include_literature
        else "Do not use or invent literature references; use only the supplied variant table context."
    )
    evidence_section = f"\nSupplied literature evidence:\n{literature_evidence}\n" if include_literature else ""
    prompt = (
        f"Interpret these variants using the {framework} framework.\n"
        f"Gene or disease context: {gene_context or 'general variant interpretation'}.\n"
        f"{literature_instruction}\n\n"
        "Variants:\n"
        f"{chr(10).join(variant_lines)}\n"
        f"{evidence_section}\n"
        "Return a JSON object with an interpretations array. Each item must include variant_id, gene, "
        "pathogenicity, confidence, summary, and evidence."
    )
    return _messages(
        system_prompt=(
            "You are a clinical bioinformatics assistant. Provide cautious, evidence-based variant interpretation "
            "and avoid definitive clinical claims without sufficient evidence."
        ),
        prompt=prompt,
    )


def _literature_evidence_text(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, sort_keys=True)
    return str(value or "").strip()


def _normalise_interpretations(parsed: dict[str, Any], variants: list[dict[str, str]]) -> list[dict[str, Any]]:
    raw_items = parsed.get("interpretations", []) if isinstance(parsed, dict) else []
    if not isinstance(raw_items, list):
        raw_items = []

    interpretations: list[dict[str, Any]] = []
    for index, variant in enumerate(variants):
        raw = raw_items[index] if index < len(raw_items) and isinstance(raw_items[index], dict) else {}
        variant_id = str(raw.get("variant_id") or _variant_id(variant))
        interpretations.append(
            {
                "variant_id": variant_id,
                "gene": str(raw.get("gene") or variant.get("gene") or variant.get("Gene") or ""),
                "pathogenicity": str(raw.get("pathogenicity") or "Unable to interpret"),
                "confidence": _coerce_confidence(raw.get("confidence")),
                "summary": str(raw.get("summary") or raw.get("justification") or ""),
                "evidence": raw.get("evidence", []),
                "source_variant": variant,
            }
        )
    return interpretations


def _variant_id(variant: dict[str, str]) -> str:
    chrom = variant.get("chrom") or variant.get("CHROM") or variant.get("#CHROM") or ""
    pos = variant.get("pos") or variant.get("POS") or ""
    ref = variant.get("ref") or variant.get("REF") or ""
    alt = variant.get("alt") or variant.get("ALT") or ""
    if chrom and pos and ref and alt:
        return f"{chrom}:{pos}:{ref}>{alt}"
    return variant.get("id") or variant.get("ID") or "variant"


def _coerce_confidence(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _write_scores_csv(path: Path, interpretations: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["variant_id", "gene", "pathogenicity", "confidence", "summary"])
        writer.writeheader()
        for interpretation in interpretations:
            writer.writerow(
                {
                    "variant_id": interpretation.get("variant_id", ""),
                    "gene": interpretation.get("gene", ""),
                    "pathogenicity": interpretation.get("pathogenicity", ""),
                    "confidence": interpretation.get("confidence", 0.0),
                    "summary": interpretation.get("summary", ""),
                }
            )
