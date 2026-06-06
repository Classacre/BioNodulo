"""Workflow AI/LLM nodes."""
from __future__ import annotations

import base64
import csv
import hashlib
import html
import importlib
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx

from bionodulo.ai.llm_backend import LLMConfig, call_llm, render_prompt, resolve_llm_config, safe_json_parse
from bionodulo.core.credentials import resolve_secret_value
from bionodulo.nodes.base import BaseNode

NCBI_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_USER_AGENT = "BioNodulo/2.0 (AI literature search node)"
NCBI_REQUEST_TIMEOUT_S = 30.0
NCBI_MAX_RETRIES = 3


def _parse_json_object(value: Any, field_name: str) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be a JSON object") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return parsed


def _llm_config_from_kwargs(kwargs: dict[str, Any]) -> LLMConfig:
    return resolve_llm_config(
        provider=kwargs.get("provider"),
        model=kwargs.get("model"),
        api_key=kwargs.get("api_key"),
        api_base=kwargs.get("api_base"),
        temperature=kwargs.get("temperature"),
        max_tokens=kwargs.get("max_tokens"),
        timeout=kwargs.get("timeout"),
        context=kwargs.get("context"),
    )


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _resolve_ncbi_api_key(explicit: Any, context: Any) -> str:
    return resolve_secret_value(explicit, context, "ncbi_api_key", "NCBI_API_KEY", default=os.environ.get("NCBI_API_KEY", ""))


def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value not in (None, "")}


async def _request_json(
    endpoint: str,
    params: dict[str, Any],
    *,
    retries: int = NCBI_MAX_RETRIES,
    timeout: float = NCBI_REQUEST_TIMEOUT_S,
) -> dict[str, Any]:
    response = await _request(endpoint, params, retries=retries, timeout=timeout)
    return response.json()


async def _request_text(
    endpoint: str,
    params: dict[str, Any],
    *,
    retries: int = NCBI_MAX_RETRIES,
    timeout: float = NCBI_REQUEST_TIMEOUT_S,
) -> str:
    response = await _request(endpoint, params, retries=retries, timeout=timeout)
    return response.text


async def _request(endpoint: str, params: dict[str, Any], *, retries: int, timeout: float) -> httpx.Response:
    url = f"{NCBI_BASE_URL}/{endpoint}"
    clean = _clean_params(params)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": NCBI_USER_AGENT}) as client:
                response = await client.get(url, params=clean)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status = exc.response.status_code
            if status < 500 or attempt >= retries - 1:
                body = exc.response.text[:500]
                raise RuntimeError(f"NCBI literature search failed with HTTP {status}: {body}") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt >= retries - 1:
                raise RuntimeError(f"NCBI literature search request failed: {exc}") from exc
    raise RuntimeError(f"NCBI literature search request failed: {last_error}")


class LLMPromptNode(BaseNode):
    """Send a templated prompt to a configured LLM."""

    NODE_ID = "llm_prompt"
    DISPLAY_NAME = "LLM Prompt"
    CATEGORY = "ai"
    DESCRIPTION = "Render a prompt template and run it through an LLM provider"
    SEARCH_ALIASES = ["llm", "ai", "prompt", "openai", "anthropic", "litellm", "chatgpt"]
    RETURN_TYPES = ("STRING", "JSON")
    RETURN_NAMES = ("response", "metadata")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["litellm"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "prompt": ("STRING", {"default": "", "multiline": True, "description": "Prompt template"}),
            },
            "optional": {
                "variables": ("JSON", {"default": "{}", "multiline": True, "description": "Template variables as JSON"}),
                "system_prompt": ("STRING", {"default": "", "multiline": True, "description": "Optional system prompt"}),
                "provider": (["openai", "anthropic", "openrouter", "litellm", "custom"], {"default": "openai"}),
                "model": ("STRING", {"default": "", "description": "Provider model name"}),
                "api_key": ("STRING", {"default": "", "password": True, "description": "Optional API key override"}),
                "api_base": ("STRING", {"default": "", "description": "Optional compatible API base URL"}),
                "temperature": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 2.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 1024, "min": 1, "max": 128000, "step": 1}),
                "timeout": ("FLOAT", {"default": 60.0, "min": 1.0, "max": 600.0, "step": 1.0}),
                "json_mode": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        variables = _parse_json_object(kwargs.get("variables"), "variables")
        prompt = render_prompt(str(kwargs.get("prompt", "")), variables)
        messages = _messages(prompt=prompt, system_prompt=str(kwargs.get("system_prompt", "") or ""))
        config = _llm_config_from_kwargs(kwargs)
        json_mode = bool(kwargs.get("json_mode", False))
        response = await call_llm(config, messages, json_mode=json_mode)
        metadata: dict[str, Any] = {
            "provider": config.provider,
            "model": response.model or config.model,
            "json_mode": json_mode,
            "usage": response.usage,
        }
        if response.error:
            metadata["error"] = response.error
        parsed = safe_json_parse(response.content)
        if parsed:
            metadata["parsed_json"] = parsed
        return (response.content, metadata)


class LLMDecisionNode(BaseNode):
    """Use an LLM to classify input into configured labels."""

    NODE_ID = "llm_decision"
    DISPLAY_NAME = "LLM Decision"
    CATEGORY = "ai"
    DESCRIPTION = "Use an LLM to classify input data and return a workflow decision label"
    SEARCH_ALIASES = ["llm", "ai", "decision", "classify", "route", "branch", "condition"]
    RETURN_TYPES = ("STRING", "BOOLEAN", "JSON")
    RETURN_NAMES = ("label", "matched", "decision_json")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["litellm"]
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_data": ("STRING", {"default": "", "multiline": True, "description": "Data to analyze"}),
                "criteria": ("STRING", {"default": "", "multiline": True, "description": "Decision criteria"}),
                "labels": ("STRING", {"default": "pass, fail", "description": "Comma-separated allowed labels"}),
            },
            "optional": {
                "default_label": ("STRING", {"default": "fail", "description": "Fallback label when output is invalid"}),
                "system_prompt": ("STRING", {"default": "", "multiline": True, "description": "Optional system prompt"}),
                "provider": (["openai", "anthropic", "openrouter", "litellm", "custom"], {"default": "openai"}),
                "model": ("STRING", {"default": "", "description": "Provider model name"}),
                "api_key": ("STRING", {"default": "", "password": True, "description": "Optional API key override"}),
                "api_base": ("STRING", {"default": "", "description": "Optional compatible API base URL"}),
                "temperature": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 2.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 256, "min": 1, "max": 128000, "step": 1}),
                "timeout": ("FLOAT", {"default": 60.0, "min": 1.0, "max": 600.0, "step": 1.0}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, bool, dict[str, Any]]:
        labels = _parse_labels(kwargs.get("labels"))
        default_label = str(kwargs.get("default_label", "") or labels[-1]).strip().lower()
        if default_label not in labels:
            raise ValueError("default_label must be one of labels")

        prompt = (
            f"{kwargs.get('criteria', '')}\n\n"
            f"Allowed labels: {', '.join(labels)}\n"
            "Return a JSON object with keys label, confidence, and reason.\n\n"
            f"Input data:\n{kwargs.get('input_data', '')}"
        )
        system_prompt = str(kwargs.get("system_prompt", "") or "You are a strict workflow classifier.")
        config = _llm_config_from_kwargs(kwargs)
        response = await call_llm(config, _messages(prompt=prompt, system_prompt=system_prompt), json_mode=True)
        parsed = safe_json_parse(response.content)
        raw_label = str(parsed.get("label", "")).strip().lower()
        if raw_label in labels:
            parsed.setdefault("matched", True)
            parsed["label"] = raw_label
            return (raw_label, True, parsed)

        reason = parsed.get("reason", response.content)
        return (
            default_label,
            False,
            {"label": default_label, "matched": False, "raw_label": raw_label, "reason": reason},
        )


class AIVariantInterpretationNode(BaseNode):
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

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "variant_table": ("FILE", {"description": "CSV or TSV table with variant annotations"}),
            },
            "optional": {
                "framework": ("STRING", {"default": "ACMG", "options": ["ACMG", "research", "clinical_actionable"]}),
                "gene_context": ("STRING", {"default": "", "multiline": True, "description": "Optional disease or panel context"}),
                "include_literature": ("BOOLEAN", {"default": True}),
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
        framework = str(kwargs.get("framework", "ACMG") or "ACMG")
        gene_context = str(kwargs.get("gene_context", "") or "")
        include_literature = bool(kwargs.get("include_literature", True))

        if variants:
            config = _llm_config_from_kwargs(kwargs)
            messages = _variant_interpretation_messages(
                variants=variants,
                framework=framework,
                gene_context=gene_context,
                include_literature=include_literature,
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
        return {"outputs": {"interpretation_json": str(json_path), "scores_csv": str(csv_path)}}


class AISequenceAnalysisNode(BaseNode):
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
        analysis_type = str(kwargs.get("analysis_type", "comprehensive") or "comprehensive")
        molecule_type = str(kwargs.get("molecule_type", "auto") or "auto")

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


class AILiteratureSearchNode(BaseNode):
    """Search PubMed and synthesize biomedical literature with an LLM."""

    NODE_ID = "ai_literature_search"
    DISPLAY_NAME = "AI Literature Search"
    CATEGORY = "ai"
    DESCRIPTION = "Search PubMed for papers relevant to a research question and synthesize findings with citations."
    SEARCH_ALIASES = ["pubmed", "literature", "search", "papers", "references", "biomedical", "review", "citations"]
    RETURN_TYPES = ("JSON", "STRING")
    RETURN_NAMES = ("papers_json", "summary_text")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["litellm"]
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "research_question": (
                    "STRING",
                    {
                        "default": "What is known about the role of BRCA1 in ovarian cancer?",
                        "multiline": True,
                        "description": "Research question or topic to search for",
                    },
                ),
            },
            "optional": {
                "databases": ("STRING", {"default": "pubmed", "options": ["pubmed", "pubmed+biorxiv", "pubmed+arxiv"]}),
                "max_results": ("INT", {"default": 10, "min": 1, "max": 100}),
                "year_range": ("STRING", {"default": "", "description": "Year filter such as 2020:2026"}),
                "search_depth": ("STRING", {"default": "standard", "options": ["quick", "standard", "deep"]}),
                "include_abstracts": ("BOOLEAN", {"default": True}),
                "ncbi_api_key": ("STRING", {"default": "", "advanced": True, "password": True}),
                "email": ("STRING", {"default": "", "advanced": True}),
                "provider": (["openai", "anthropic", "openrouter", "litellm", "custom"], {"default": "openai"}),
                "model": ("STRING", {"default": "", "description": "Provider model name"}),
                "api_key": ("STRING", {"default": "", "password": True, "description": "Optional LLM API key override"}),
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
        question = str(kwargs.get("research_question", "") or "").strip()
        if not question:
            raise ValueError("AI Literature Search requires a research_question")
        databases = str(kwargs.get("databases", "pubmed") or "pubmed")
        if not databases.startswith("pubmed"):
            raise ValueError("AI Literature Search currently supports PubMed-backed searches")
        max_results = max(1, min(int(kwargs.get("max_results", 10) or 10), 100))
        year_range = str(kwargs.get("year_range", "") or "").strip()
        search_depth = str(kwargs.get("search_depth", "standard") or "standard")
        include_abstracts = bool(kwargs.get("include_abstracts", True))
        api_key = _resolve_ncbi_api_key(kwargs.get("ncbi_api_key", ""), context)
        email = str(kwargs.get("email", "") or os.environ.get("BIONODULO_EMAIL", "bionodulo@example.com")).strip()

        config = _llm_config_from_kwargs(kwargs)
        queries, query_usage = await _literature_queries(question, search_depth, config)
        search_result = await _search_pubmed_literature(
            queries=queries,
            max_results=max_results,
            year_range=year_range,
            api_key=api_key,
            email=email,
            include_abstracts=include_abstracts,
        )

        if search_result["papers"]:
            summary, synthesis_usage = await _synthesize_literature(question, search_result["papers"], config)
        else:
            summary = "No papers found for the given research question."
            synthesis_usage = {}

        out_dir = _node_output_dir(self, context)
        json_path = out_dir / "papers.json"
        summary_path = out_dir / "summary.txt"
        payload = {
            "research_question": question,
            "databases": databases,
            "max_results": max_results,
            "year_range": year_range,
            "search_depth": search_depth,
            "include_abstracts": include_abstracts,
            "queries_used": queries,
            "query_translations": search_result["query_translations"],
            "papers_found": len(search_result["papers"]),
            "papers": search_result["papers"],
            "summary": summary,
            "model": config.model,
            "usage": {"query_generation": query_usage, "synthesis": synthesis_usage},
            "papers_json_path": str(json_path),
            "summary_path": str(summary_path),
        }
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary_path.write_text(summary, encoding="utf-8")
        return {"outputs": {"papers_json": payload, "summary_text": summary}}


class AIDataExtractionNode(BaseNode):
    """Extract structured biological entities from unstructured text with an LLM."""

    NODE_ID = "ai_data_extraction"
    DISPLAY_NAME = "AI Data Extraction"
    CATEGORY = "ai"
    DESCRIPTION = (
        "Extract structured biological entities from unstructured text into JSON and CSV outputs."
    )
    SEARCH_ALIASES = [
        "extract",
        "ner",
        "entities",
        "parse",
        "genes",
        "variants",
        "diseases",
        "text-mining",
        "biocuration",
    ]
    RETURN_TYPES = ("JSON", "CSV")
    RETURN_NAMES = ("extracted_json", "extracted_csv")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["litellm"]
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "description": "Unstructured text to extract entities from",
                    },
                ),
                "extraction_schema": (
                    "STRING",
                    {
                        "default": "genes_variants_diseases",
                        "options": [
                            "genes_variants_diseases",
                            "drugs_targets",
                            "clinical_trial",
                            "pathway_interactions",
                            "custom",
                        ],
                    },
                ),
            },
            "optional": {
                "custom_entities": ("STRING", {"default": "", "multiline": True}),
                "input_file": ("FILE", {"description": "Optional text file to read instead of input_text"}),
                "output_format": ("STRING", {"default": "both", "options": ["json", "csv", "both"]}),
                "include_context": ("BOOLEAN", {"default": True}),
                "normalize_ids": ("BOOLEAN", {"default": True}),
                "provider": (["openai", "anthropic", "openrouter", "litellm", "custom"], {"default": "openai"}),
                "model": ("STRING", {"default": "", "description": "Provider model name"}),
                "api_key": ("STRING", {"default": "", "password": True, "description": "Optional API key override"}),
                "api_base": ("STRING", {"default": "", "description": "Optional compatible API base URL"}),
                "temperature": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0, "step": 0.05}),
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
        json_path = out_dir / "extracted.json"
        csv_path = out_dir / "extracted.csv"

        input_text = _read_data_extraction_text(kwargs.get("input_text", ""), kwargs.get("input_file", ""))
        extraction_schema = str(kwargs.get("extraction_schema", "genes_variants_diseases") or "genes_variants_diseases")
        custom_entities = _parse_custom_entities(str(kwargs.get("custom_entities", "") or ""))
        output_format = str(kwargs.get("output_format", "both") or "both").lower()
        include_context = bool(kwargs.get("include_context", True))
        normalize_ids = bool(kwargs.get("normalize_ids", True))

        config = _llm_config_from_kwargs({**kwargs, "context": context})
        response = await call_llm(
            config,
            _messages(
                system_prompt=(
                    "You are an expert biomedical entity extraction system. Extract only entities supported "
                    "by the supplied text and return valid JSON."
                ),
                prompt=_data_extraction_prompt(
                    text=input_text,
                    extraction_schema=extraction_schema,
                    custom_entities=custom_entities,
                    include_context=include_context,
                    normalize_ids=normalize_ids,
                ),
            ),
            json_mode=True,
        )
        entities = safe_json_parse(response.content) or {"raw_extraction": response.content}
        payload = {
            "extraction_schema": extraction_schema,
            "source_text_length": _data_extraction_source_text_length(input_text),
            "entities": entities,
            "usage": response.usage,
            "model": response.model or config.model,
        }
        if extraction_schema == "custom":
            payload["custom_entities"] = [entity["name"] for entity in custom_entities]

        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_extraction_csv(csv_path, entities)

        return {
            "outputs": {
                "extracted_json": str(json_path) if output_format in {"json", "both"} else "",
                "extracted_csv": str(csv_path) if output_format in {"csv", "both"} else "",
            }
        }


class AIPipelineAdvisorNode(BaseNode):
    """Recommend bioinformatics workflow structure and parameters with an LLM."""

    NODE_ID = "ai_pipeline_advisor"
    DISPLAY_NAME = "AI Pipeline Advisor"
    CATEGORY = "ai"
    DESCRIPTION = "Recommend bioinformatics pipeline nodes and parameters from experiment metadata."
    SEARCH_ALIASES = ["pipeline", "advisor", "recommend", "parameters", "workflow", "planning", "metadata"]
    RETURN_TYPES = ("JSON", "STRING")
    RETURN_NAMES = ("recommendations_json", "rationale_text")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["litellm"]
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "experiment_type": ("STRING", {"default": "bulk_rnaseq", "description": "Experiment or assay type"}),
                "metadata": ("JSON", {"default": "{}", "multiline": True, "description": "Experimental metadata as JSON"}),
            },
            "optional": {
                "analysis_goal": ("STRING", {"default": "", "multiline": True}),
                "available_inputs": ("STRING", {"default": "", "multiline": True}),
                "constraints": ("STRING", {"default": "", "multiline": True}),
                "output_format": ("STRING", {"default": "both", "options": ["json", "rationale", "both"]}),
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
        json_path = out_dir / "recommendations.json"
        rationale_path = out_dir / "rationale.txt"

        experiment_type = str(kwargs.get("experiment_type", "") or "").strip()
        if not experiment_type:
            raise ValueError("AI Pipeline Advisor requires an experiment_type")
        metadata = _parse_json_object(kwargs.get("metadata"), "metadata")
        analysis_goal = str(kwargs.get("analysis_goal", "") or "").strip()
        available_inputs = str(kwargs.get("available_inputs", "") or "").strip()
        constraints = str(kwargs.get("constraints", "") or "").strip()
        output_format = str(kwargs.get("output_format", "both") or "both").lower()

        config = _llm_config_from_kwargs({**kwargs, "context": context})
        response = await call_llm(
            config,
            _messages(
                system_prompt=(
                    "You are a senior bioinformatics workflow architect. Recommend practical BioNodulo "
                    "pipeline steps, parameters, quality controls, and risks from the supplied metadata."
                ),
                prompt=_pipeline_advisor_prompt(
                    experiment_type=experiment_type,
                    metadata=metadata,
                    analysis_goal=analysis_goal,
                    available_inputs=available_inputs,
                    constraints=constraints,
                ),
            ),
            json_mode=True,
        )
        recommendations = safe_json_parse(response.content) or {"raw_recommendations": response.content}
        rationale = _pipeline_advisor_rationale(recommendations, response.content)
        payload = {
            "experiment_type": experiment_type,
            "metadata": metadata,
            "analysis_goal": analysis_goal,
            "available_inputs": available_inputs,
            "constraints": constraints,
            "recommendations": recommendations,
            "rationale": rationale,
            "usage": response.usage,
            "model": response.model or config.model,
        }

        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rationale_path.write_text(rationale, encoding="utf-8")
        return {
            "outputs": {
                "recommendations_json": str(json_path) if output_format in {"json", "both"} else "",
                "rationale_text": str(rationale_path) if output_format in {"rationale", "both"} else "",
            }
        }


class AIEmbeddingNode(BaseNode):
    """Generate embedding vectors for biological sequences or text."""

    NODE_ID = "ai_embedding"
    DISPLAY_NAME = "AI Embedding"
    CATEGORY = "ai"
    DESCRIPTION = (
        "Generate embedding vectors for biological sequences or text using transformer models "
        "or a deterministic local fallback."
    )
    SEARCH_ALIASES = ["embedding", "vector", "esm", "dnabert", "transformer", "representation", "encode", "features"]
    RETURN_TYPES = ("EMBEDDING", "JSON")
    RETURN_NAMES = ("embeddings_npy", "metadata_json")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["numpy", "biopython", "torch", "transformers"]
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_data": ("STRING", {"default": "", "multiline": True, "description": "FASTA path, text path, or raw text/sequences"}),
                "embedding_model": (
                    "STRING",
                    {
                        "default": "esm2_t6_8M",
                        "options": [
                            "esm2_t6_8M",
                            "esm2_t12_35M",
                            "esm2_t30_150M",
                            "esm2_t33_650M",
                            "dnabert",
                            "dnabert2",
                            "text_embedding",
                        ],
                    },
                ),
            },
            "optional": {
                "molecule_type": ("STRING", {"default": "auto", "options": ["auto", "protein", "dna", "rna", "text"]}),
                "batch_size": ("INT", {"default": 8, "min": 1, "max": 64}),
                "max_length": ("INT", {"default": 512, "min": 1, "max": 4096}),
                "pooling": ("STRING", {"default": "mean", "options": ["mean", "cls", "max"]}),
                "layer": ("INT", {"default": -1, "min": -33, "max": 36}),
                "normalize": ("BOOLEAN", {"default": True}),
                "compute_device": ("STRING", {"default": "auto", "options": ["auto", "cpu", "cuda", "mps"]}),
                "fallback_backend": ("STRING", {"default": "auto", "options": ["auto", "deterministic", "local"]}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        out_dir = _node_output_dir(self, context)
        npy_path = out_dir / "embeddings.npy"
        metadata_path = out_dir / "metadata.json"

        input_data = str(kwargs.get("input_data", "") or "")
        embedding_model = str(kwargs.get("embedding_model", "esm2_t6_8M") or "esm2_t6_8M")
        molecule_type = str(kwargs.get("molecule_type", "auto") or "auto")
        batch_size = max(1, int(kwargs.get("batch_size", 8) or 8))
        max_length = max(1, int(kwargs.get("max_length", 512) or 512))
        pooling = str(kwargs.get("pooling", "mean") or "mean")
        layer_value = kwargs.get("layer", -1)
        layer = -1 if layer_value is None else int(layer_value)
        normalize = bool(kwargs.get("normalize", True))
        compute_device = str(kwargs.get("compute_device", "auto") or "auto")
        fallback_backend = str(kwargs.get("fallback_backend", "auto") or "auto")

        records = _embedding_records(input_data, molecule_type=molecule_type, max_length=max_length)
        if not records:
            embeddings = _empty_embedding_array()
            metadata = _embedding_metadata(
                records=[],
                embeddings=embeddings,
                embedding_model=embedding_model,
                model_name=_EMBEDDING_MODEL_REGISTRY.get(embedding_model, embedding_model),
                molecule_type=molecule_type,
                pooling=pooling,
                layer=layer,
                normalize=normalize,
                compute_device=compute_device,
                backend="empty",
            )
        else:
            embeddings, backend, model_name, device = _generate_embeddings(
                [record["sequence"] for record in records],
                embedding_model=embedding_model,
                batch_size=batch_size,
                max_length=max_length,
                pooling=pooling,
                layer=layer,
                normalize=normalize,
                compute_device=compute_device,
                fallback_backend=fallback_backend,
            )
            metadata = _embedding_metadata(
                records=records,
                embeddings=embeddings,
                embedding_model=embedding_model,
                model_name=model_name,
                molecule_type=molecule_type,
                pooling=pooling,
                layer=layer,
                normalize=normalize,
                compute_device=device,
                backend=backend,
            )

        np = _numpy()
        np.save(npy_path, embeddings)
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {"outputs": {"embeddings_npy": str(npy_path), "metadata_json": str(metadata_path)}}


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


class AISequenceClassificationNode(BaseNode):
    """Classify biological sequences with local models or deterministic fallback."""

    NODE_ID = "ai_sequence_classification"
    DISPLAY_NAME = "AI Sequence Classification"
    CATEGORY = "ai"
    DESCRIPTION = (
        "Classify biological sequences using pretrained ML models or a deterministic local fallback."
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

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Input FASTA file with sequences to classify"}),
                "classifier": (
                    "STRING",
                    {
                        "default": "deeploc",
                        "options": ["deeploc", "signalp", "tmhmm", "disorder", "solubility", "custom"],
                        "description": "Classification model to use",
                    },
                ),
            },
            "optional": {
                "custom_model": ("STRING", {"default": "", "description": "HuggingFace model name for custom classifier"}),
                "batch_size": ("INT", {"default": 8, "min": 1, "max": 64}),
                "max_length": ("INT", {"default": 1024, "min": 1, "max": 4096}),
                "confidence_threshold": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05}),
                "compute_device": ("STRING", {"default": "auto", "options": ["auto", "cpu", "cuda", "mps"]}),
                "top_k": ("INT", {"default": 1, "min": 1, "max": 10}),
                "fallback_backend": ("STRING", {"default": "auto", "options": ["auto", "deterministic", "local"]}),
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

        classifier = str(kwargs.get("classifier", "deeploc") or "deeploc")
        custom_model = str(kwargs.get("custom_model", "") or "").strip()
        batch_size = max(1, int(kwargs.get("batch_size", 8) or 8))
        max_length = max(1, int(kwargs.get("max_length", 1024) or 1024))
        confidence_threshold = float(kwargs.get("confidence_threshold", 0.5) or 0.0)
        compute_device = str(kwargs.get("compute_device", "auto") or "auto")
        top_k = max(1, int(kwargs.get("top_k", 1) or 1))
        fallback_backend = str(kwargs.get("fallback_backend", "auto") or "auto")

        classifier_spec = _classification_spec(classifier, custom_model)
        labels = list(classifier_spec["labels"])
        top_k = min(top_k, max(1, len(labels)))
        records = _classification_records(kwargs.get("input_fasta", ""), max_length=max_length)
        predictions, backend, device = _generate_classifications(
            records,
            classifier=classifier,
            model_name=str(classifier_spec["model"]),
            labels=labels,
            batch_size=batch_size,
            max_length=max_length,
            top_k=top_k,
            compute_device=compute_device,
            fallback_backend=fallback_backend,
        )
        filtered_predictions = [
            prediction
            for prediction in predictions
            if prediction["top_predictions"]
            and float(prediction["top_predictions"][0].get("confidence", 0.0)) >= confidence_threshold
        ]
        payload = {
            "classifier": classifier,
            "model": classifier_spec["model"],
            "backend": "empty" if not records else backend,
            "device": device,
            "labels": labels,
            "total_sequences": len(records),
            "returned_predictions": len(filtered_predictions),
            "filtered_out": len(predictions) - len(filtered_predictions),
            "confidence_threshold": confidence_threshold,
            "top_k": top_k,
            "predictions": filtered_predictions,
        }

        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_classifications_csv(csv_path, filtered_predictions)
        return {"outputs": {"classifications_json": str(json_path), "classifications_csv": str(csv_path)}}


class AIImageAnalysisNode(BaseNode):
    """Analyze scientific images with a vision-capable LLM."""

    NODE_ID = "ai_image_analysis"
    DISPLAY_NAME = "AI Image Analysis"
    CATEGORY = "ai"
    DESCRIPTION = (
        "Analyze bioinformatics images such as gels, microscopy, karyograms, plots, and colony plates "
        "using multimodal LLMs."
    )
    SEARCH_ALIASES = [
        "image",
        "vision",
        "gel",
        "microscopy",
        "karyotype",
        "karyogram",
        "plot",
        "analyze",
        "multimodal",
        "colony",
        "western",
    ]
    RETURN_TYPES = ("JSON", "STRING")
    RETURN_NAMES = ("analysis_json", "description_text")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["litellm"]
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_image": ("IMAGE", {"description": "Image file to analyze"}),
                "analysis_task": (
                    "STRING",
                    {
                        "default": "general",
                        "options": [
                            "general",
                            "gel_electrophoresis",
                            "microscopy",
                            "karyogram",
                            "plot",
                            "western_blot",
                            "colony_counting",
                            "custom",
                        ],
                    },
                ),
            },
            "optional": {
                "custom_prompt": ("STRING", {"default": "", "multiline": True}),
                "expected_ladder": ("STRING", {"default": "", "description": "Gel ladder sizes, comma-separated"}),
                "scale_bar": ("STRING", {"default": "", "description": "Microscopy scale bar, e.g. 20um"}),
                "provider": (["openai", "anthropic", "openrouter", "litellm", "custom"], {"default": "openai"}),
                "model": ("STRING", {"default": "", "description": "Vision model override"}),
                "api_key": ("STRING", {"default": "", "password": True, "description": "Optional API key override"}),
                "api_base": ("STRING", {"default": "", "description": "Optional compatible API base URL"}),
                "temperature": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 1.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 128000, "step": 1}),
                "timeout": ("FLOAT", {"default": 60.0, "min": 1.0, "max": 600.0, "step": 1.0}),
                "json_mode": ("BOOLEAN", {"default": True}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        out_dir = _node_output_dir(self, context)
        json_path = out_dir / "analysis.json"

        image_path = Path(str(kwargs.get("input_image", "") or ""))
        analysis_task = str(kwargs.get("analysis_task", "general") or "general")
        if not image_path.exists():
            description = f"Image not found: {image_path}"
            payload = {
                "input_image": str(image_path),
                "analysis_task": analysis_task,
                "error": description,
                "analysis": {},
            }
            json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return {"outputs": {"analysis_json": str(json_path), "description_text": description}}

        mime_type = _image_mime_type(image_path)
        image_bytes = image_path.read_bytes()
        prompt = _image_analysis_prompt(
            analysis_task=analysis_task,
            custom_prompt=str(kwargs.get("custom_prompt", "") or ""),
            expected_ladder=str(kwargs.get("expected_ladder", "") or ""),
            scale_bar=str(kwargs.get("scale_bar", "") or ""),
        )
        config = _llm_config_from_kwargs({
            **kwargs,
            "context": context,
            "model": _vision_model_override(str(kwargs.get("provider", "openai") or "openai"), kwargs.get("model")),
        })
        json_mode = bool(kwargs.get("json_mode", True))
        messages = _image_analysis_messages(prompt=prompt, image_bytes=image_bytes, mime_type=mime_type)
        response = await call_llm(config, messages, json_mode=json_mode)
        parsed = safe_json_parse(response.content) if json_mode else {}
        description = str(parsed.get("description") or parsed.get("summary") or response.content)
        analysis = parsed or {"description": response.content}
        payload = {
            "input_image": str(image_path),
            "analysis_task": analysis_task,
            "mime_type": mime_type,
            "image_size_bytes": len(image_bytes),
            "model": response.model or config.model,
            "usage": response.usage,
            "analysis": analysis,
            "description": description,
        }
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {"outputs": {"analysis_json": str(json_path), "description_text": description}}


class ModelInferenceNode(BaseNode):
    """Run local Hugging Face model inference or deterministic fallback."""

    NODE_ID = "model_inference"
    DISPLAY_NAME = "Model Inference"
    CATEGORY = "ai"
    DESCRIPTION = (
        "Run inference with local Hugging Face Transformer models on text or biological sequences."
    )
    SEARCH_ALIASES = [
        "model",
        "inference",
        "huggingface",
        "transformers",
        "predict",
        "classification",
        "sequence",
        "zero-shot",
    ]
    RETURN_TYPES = ("JSON", "CSV")
    RETURN_NAMES = ("predictions_json", "scores_csv")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["numpy", "torch", "transformers"]
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_data": ("STRING", {"default": "", "multiline": True, "description": "Input file path, FASTA, or raw text"}),
                "model_name": ("STRING", {"default": "facebook/bart-large-mnli", "description": "Local Hugging Face model name or path"}),
                "task": (
                    "STRING",
                    {
                        "default": "text_classification",
                        "options": [
                            "text_classification",
                            "sequence_classification",
                            "token_classification",
                            "zero_shot_classification",
                            "feature_extraction",
                        ],
                    },
                ),
            },
            "optional": {
                "candidate_labels": ("STRING", {"default": "positive, negative", "description": "Comma-separated output labels"}),
                "batch_size": ("INT", {"default": 8, "min": 1, "max": 64}),
                "max_length": ("INT", {"default": 512, "min": 1, "max": 4096}),
                "top_k": ("INT", {"default": 1, "min": 1, "max": 20}),
                "confidence_threshold": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "compute_device": ("STRING", {"default": "auto", "options": ["auto", "cpu", "cuda", "mps"]}),
                "fallback_backend": ("STRING", {"default": "auto", "options": ["auto", "deterministic", "local"]}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        out_dir = _node_output_dir(self, context)
        json_path = out_dir / "predictions.json"
        csv_path = out_dir / "scores.csv"

        input_data = str(kwargs.get("input_data", "") or "")
        model_name = str(kwargs.get("model_name", "facebook/bart-large-mnli") or "facebook/bart-large-mnli")
        task = str(kwargs.get("task", "text_classification") or "text_classification")
        labels = _model_inference_labels(kwargs.get("candidate_labels"))
        batch_size = max(1, int(kwargs.get("batch_size", 8) or 8))
        max_length = max(1, int(kwargs.get("max_length", 512) or 512))
        top_k = max(1, min(int(kwargs.get("top_k", 1) or 1), max(1, len(labels))))
        confidence_threshold = float(kwargs.get("confidence_threshold", 0.0) or 0.0)
        compute_device = str(kwargs.get("compute_device", "auto") or "auto")
        fallback_backend = str(kwargs.get("fallback_backend", "auto") or "auto")

        records = _model_inference_records(input_data, task=task, max_length=max_length)
        predictions, backend, device = _generate_model_predictions(
            records,
            model_name=model_name,
            task=task,
            labels=labels,
            batch_size=batch_size,
            max_length=max_length,
            top_k=top_k,
            compute_device=compute_device,
            fallback_backend=fallback_backend,
        )
        filtered_predictions = [
            prediction
            for prediction in predictions
            if prediction["top_predictions"]
            and float(prediction["top_predictions"][0].get("confidence", 0.0)) >= confidence_threshold
        ]
        payload = {
            "model_name": model_name,
            "task": task,
            "backend": "empty" if not records else backend,
            "device": device,
            "labels": labels,
            "input_count": len(records),
            "returned_predictions": len(filtered_predictions),
            "filtered_out": len(predictions) - len(filtered_predictions),
            "confidence_threshold": confidence_threshold,
            "top_k": top_k,
            "predictions": filtered_predictions,
        }

        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_model_scores_csv(csv_path, filtered_predictions)
        return {"outputs": {"predictions_json": str(json_path), "scores_csv": str(csv_path)}}


class FineTuneLLMNode(BaseNode):
    """Prepare a reproducible LoRA fine-tuning package for local LLM training."""

    NODE_ID = "fine_tune_llm"
    DISPLAY_NAME = "Fine-Tune LLM"
    CATEGORY = "ai"
    DESCRIPTION = (
        "Prepare LoRA fine-tuning artifacts for small local language models with an optional local backend."
    )
    SEARCH_ALIASES = [
        "fine-tune",
        "finetune",
        "training",
        "lora",
        "peft",
        "adapter",
        "instruction",
        "domain-adaptation",
    ]
    RETURN_TYPES = ("DIRECTORY", "JSON")
    RETURN_NAMES = ("model_path", "metrics_json")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["torch", "transformers", "datasets", "peft", "accelerate"]
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "training_data": ("FILE", {"description": "Training data file in JSONL, CSV, or plain text format"}),
                "base_model": ("STRING", {"default": "distilgpt2", "description": "Local Hugging Face model name or path"}),
                "epochs": ("INT", {"default": 1, "min": 1, "max": 100}),
            },
            "optional": {
                "validation_data": ("FILE", {"default": "", "description": "Optional validation data file"}),
                "training_format": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": ["auto", "prompt_response", "jsonl", "csv", "text"],
                    },
                ),
                "text_column": ("STRING", {"default": "text"}),
                "prompt_column": ("STRING", {"default": "prompt"}),
                "response_column": ("STRING", {"default": "response"}),
                "output_adapter_name": ("STRING", {"default": "fine_tuned_adapter"}),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 128}),
                "learning_rate": ("FLOAT", {"default": 0.0002, "min": 0.0, "max": 1.0, "step": 0.00001}),
                "max_length": ("INT", {"default": 512, "min": 1, "max": 8192}),
                "lora_rank": ("INT", {"default": 8, "min": 1, "max": 256}),
                "lora_alpha": ("INT", {"default": 16, "min": 1, "max": 512}),
                "lora_dropout": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0, "step": 0.01}),
                "compute_device": ("STRING", {"default": "auto", "options": ["auto", "cpu", "cuda", "mps"]}),
                "training_backend": ("STRING", {"default": "dry_run", "options": ["dry_run", "local"]}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        out_dir = _node_output_dir(self, context)
        metrics_path = out_dir / "metrics.json"

        training_data = str(kwargs.get("training_data", "") or "")
        validation_data = str(kwargs.get("validation_data", "") or "")
        base_model = str(kwargs.get("base_model", "distilgpt2") or "distilgpt2")
        epochs = max(1, int(kwargs.get("epochs", 1) or 1))
        training_format = str(kwargs.get("training_format", "auto") or "auto")
        text_column = str(kwargs.get("text_column", "text") or "text")
        prompt_column = str(kwargs.get("prompt_column", "prompt") or "prompt")
        response_column = str(kwargs.get("response_column", "response") or "response")
        output_adapter_name = _safe_adapter_name(kwargs.get("output_adapter_name", "fine_tuned_adapter"))
        batch_size = max(1, int(kwargs.get("batch_size", 1) or 1))
        learning_rate = float(kwargs.get("learning_rate", 0.0002) or 0.0002)
        max_length = max(1, int(kwargs.get("max_length", 512) or 512))
        lora_rank = max(1, int(kwargs.get("lora_rank", 8) or 8))
        lora_alpha = max(1, int(kwargs.get("lora_alpha", 16) or 16))
        lora_dropout = max(0.0, min(float(kwargs.get("lora_dropout", 0.05) or 0.0), 1.0))
        compute_device = str(kwargs.get("compute_device", "auto") or "auto")
        training_backend = str(kwargs.get("training_backend", "dry_run") or "dry_run")
        model_dir = out_dir / output_adapter_name

        train_examples, resolved_format = _fine_tune_examples(
            training_data,
            training_format=training_format,
            text_column=text_column,
            prompt_column=prompt_column,
            response_column=response_column,
        )
        validation_examples, _ = _fine_tune_examples(
            validation_data,
            training_format=training_format,
            text_column=text_column,
            prompt_column=prompt_column,
            response_column=response_column,
            required=False,
        )

        config = {
            "base_model": base_model,
            "output_adapter_name": output_adapter_name,
            "training_backend": training_backend,
            "training_format": resolved_format,
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "max_length": max_length,
            "lora": {
                "rank": lora_rank,
                "alpha": lora_alpha,
                "dropout": lora_dropout,
            },
            "columns": {
                "text": text_column,
                "prompt": prompt_column,
                "response": response_column,
            },
            "compute_device": compute_device,
        }

        if training_backend == "local":
            _ensure_local_fine_tune_backend()

        model_dir.mkdir(parents=True, exist_ok=True)
        config_path = model_dir / "training_config.json"
        train_examples_path = model_dir / "training_examples.jsonl"
        validation_examples_path = model_dir / "validation_examples.jsonl"
        readme_path = model_dir / "README.md"
        adapter_config_path = model_dir / "adapter_config.json"

        config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_fine_tune_examples(train_examples_path, train_examples)
        _write_fine_tune_examples(validation_examples_path, validation_examples)
        adapter_config_path.write_text(
            json.dumps(_fine_tune_adapter_config(config), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        readme_path.write_text(_fine_tune_readme(config, len(train_examples), len(validation_examples)), encoding="utf-8")

        metrics = _fine_tune_metrics(
            config,
            train_examples=train_examples,
            validation_examples=validation_examples,
            model_dir=model_dir,
            metrics_path=metrics_path,
            config_path=config_path,
            train_examples_path=train_examples_path,
            validation_examples_path=validation_examples_path,
            adapter_config_path=adapter_config_path,
            readme_path=readme_path,
        )
        metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {"outputs": {"model_path": str(model_dir), "metrics_json": str(metrics_path)}}


class AIReportGeneratorNode(BaseNode):
    """Generate AI-assisted workflow reports."""

    NODE_ID = "ai_report_generator"
    DISPLAY_NAME = "AI Report Generator"
    CATEGORY = "ai"
    DESCRIPTION = "Generate formatted HTML and Markdown reports with AI interpretation of analysis results."
    SEARCH_ALIASES = ["report", "html", "markdown", "summary", "interpret", "write", "document", "publication"]
    RETURN_TYPES = ("HTML_REPORT", "STRING")
    RETURN_NAMES = ("report_html", "report_markdown")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["litellm"]
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "analysis_data": ("STRING", {"default": "", "multiline": True, "description": "Analysis results to interpret"}),
                "report_title": ("STRING", {"default": "Bioinformatics Analysis Report"}),
            },
            "optional": {
                "report_type": (
                    "STRING",
                    {
                        "default": "analysis",
                        "options": ["analysis", "qc", "variant", "rnaseq", "methylation", "clinical", "methods", "custom"],
                    },
                ),
                "additional_files": ("STRING", {"default": "", "multiline": True}),
                "output_format": ("STRING", {"default": "html", "options": ["html", "markdown", "both"]}),
                "include_visualizations": ("BOOLEAN", {"default": True}),
                "include_methods": ("BOOLEAN", {"default": True}),
                "author_name": ("STRING", {"default": ""}),
                "provider": (["openai", "anthropic", "openrouter", "litellm", "custom"], {"default": "openai"}),
                "model": ("STRING", {"default": "", "description": "Provider model name"}),
                "api_key": ("STRING", {"default": "", "password": True, "description": "Optional API key override"}),
                "api_base": ("STRING", {"default": "", "description": "Optional compatible API base URL"}),
                "temperature": ("FLOAT", {"default": 0.3, "min": 0.0, "max": 1.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 8192, "min": 256, "max": 128000, "step": 1}),
                "timeout": ("FLOAT", {"default": 60.0, "min": 1.0, "max": 600.0, "step": 1.0}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        title = str(kwargs.get("report_title", "Bioinformatics Analysis Report") or "Bioinformatics Analysis Report")
        report_type = str(kwargs.get("report_type", "analysis") or "analysis")
        output_format = str(kwargs.get("output_format", "html") or "html").lower()
        prompt = _report_prompt(
            title=title,
            report_type=report_type,
            analysis_data=str(kwargs.get("analysis_data", "") or ""),
            additional_files=str(kwargs.get("additional_files", "") or ""),
            include_visualizations=bool(kwargs.get("include_visualizations", True)),
            include_methods=bool(kwargs.get("include_methods", True)),
            author_name=str(kwargs.get("author_name", "") or ""),
        )
        config = _llm_config_from_kwargs(kwargs)
        response = await call_llm(
            config,
            _messages(
                system_prompt="You are an expert scientific report writer. Return clear Markdown with headings.",
                prompt=prompt,
            ),
            json_mode=False,
        )
        markdown = response.content
        html_path = ""
        if output_format in {"html", "both"}:
            out_dir = _node_output_dir(self, context)
            report_path = out_dir / "report.html"
            report_path.write_text(_report_html(title, markdown), encoding="utf-8")
            html_path = str(report_path)
            if context is not None and hasattr(context, "register_preview"):
                context.register_preview(report_path, label="AI Report Generator")
        return {"outputs": {"report_html": html_path, "report_markdown": markdown}}


def _messages(*, prompt: str, system_prompt: str = "") -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": prompt})
    return messages


_IMAGE_ANALYSIS_PROMPTS = {
    "general": (
        "Describe this scientific image in detail. Identify the image type, visible labels, key features, "
        "and cautious interpretation of the findings."
    ),
    "gel_electrophoresis": (
        "Analyze this gel electrophoresis image. Estimate lane count, band positions, ladder relationship, "
        "smearing or artifacts, and lane-by-lane observations. Return structured JSON when possible."
    ),
    "microscopy": (
        "Analyze this microscopy image. Estimate cell count or density, morphology, staining patterns, "
        "notable abnormalities, and limitations. Return structured JSON when possible."
    ),
    "karyogram": (
        "Analyze this karyogram. Estimate chromosome count, visible abnormalities, sex chromosome pattern, "
        "and uncertainty. Return structured JSON when possible."
    ),
    "plot": (
        "Analyze this scientific plot. Identify plot type, axes, trends, outliers, labels, and limitations. "
        "Return structured JSON when possible."
    ),
    "western_blot": (
        "Analyze this Western blot. Estimate lane count, band positions, relative intensity, artifacts, "
        "and lane-by-lane observations. Return structured JSON when possible."
    ),
    "colony_counting": (
        "Analyze this colony plate image. Estimate colony count, size distribution, morphology, density, "
        "and uncertainty. Return structured JSON when possible."
    ),
}
_VISION_MODEL_BY_PROVIDER = {
    "anthropic": "claude-3-5-sonnet-20241022",
    "openai": "gpt-4o",
    "openrouter": "openai/gpt-4o",
    "litellm": "gpt-4o",
    "custom": "gpt-4o",
}
_IMAGE_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
}


def _vision_model_override(provider: str, model: Any) -> str:
    value = str(model or "").strip()
    if value:
        return value
    return _VISION_MODEL_BY_PROVIDER.get(str(provider or "openai").strip().lower(), "gpt-4o")


def _image_analysis_prompt(
    *,
    analysis_task: str,
    custom_prompt: str,
    expected_ladder: str,
    scale_bar: str,
) -> str:
    task = str(analysis_task or "general")
    prompt = str(custom_prompt or "").strip() if task == "custom" else ""
    if not prompt:
        prompt = _IMAGE_ANALYSIS_PROMPTS.get(task, _IMAGE_ANALYSIS_PROMPTS["general"])
    context_lines = []
    if expected_ladder.strip():
        context_lines.append(f"Expected ladder sizes: {expected_ladder.strip()}")
    if scale_bar.strip():
        context_lines.append(f"Scale bar: {scale_bar.strip()}")
    if context_lines:
        prompt = f"{prompt}\n\nAdditional context:\n" + "\n".join(context_lines)
    return prompt


def _image_analysis_messages(prompt: str, image_bytes: bytes, mime_type: str) -> list[dict[str, Any]]:
    data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    return [
        {
            "role": "system",
            "content": (
                "You are an expert scientific image analysis assistant. Provide cautious, structured findings and "
                "call out uncertainty instead of overclaiming."
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]


def _image_mime_type(path: Path) -> str:
    return _IMAGE_MIME_BY_SUFFIX.get(path.suffix.lower(), "image/png")


def _pipeline_advisor_prompt(
    *,
    experiment_type: str,
    metadata: dict[str, Any],
    analysis_goal: str,
    available_inputs: str,
    constraints: str,
) -> str:
    sections = [
        f"Experiment type: {experiment_type}",
        f"Metadata:\n{json.dumps(metadata, indent=2, sort_keys=True)}",
    ]
    if analysis_goal:
        sections.append(f"Analysis goal: {analysis_goal}")
    if available_inputs:
        sections.append(f"Available inputs: {available_inputs}")
    if constraints:
        sections.append(f"Constraints: {constraints}")
    sections.append(
        "Return a JSON object with keys recommended_pipeline, recommended_nodes, "
        "parameter_recommendations, quality_controls, warnings, and rationale. "
        "recommended_nodes should be an ordered array of objects with node_id, reason, and optional parameters."
    )
    return "\n\n".join(sections)


def _pipeline_advisor_rationale(recommendations: dict[str, Any], raw_content: str) -> str:
    rationale = recommendations.get("rationale") if isinstance(recommendations, dict) else ""
    if isinstance(rationale, list):
        return "\n".join(str(item) for item in rationale if str(item).strip())
    if str(rationale or "").strip():
        return str(rationale).strip()
    return str(raw_content or "").strip()


_EMBEDDING_MODEL_REGISTRY = {
    "esm2_t6_8M": "facebook/esm2_t6_8M_UR50D",
    "esm2_t12_35M": "facebook/esm2_t12_35M_UR50D",
    "esm2_t30_150M": "facebook/esm2_t30_150M_UR50D",
    "esm2_t33_650M": "facebook/esm2_t33_650M_UR50D",
    "dnabert": "zhihan1996/DNABERT-2-117M",
    "dnabert2": "zhihan1996/DNABERT-2-117M",
    "text_embedding": "text-embedding-3-small",
}
_DETERMINISTIC_EMBEDDING_DIM = 32


def _numpy() -> Any:
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("AI Embedding requires numpy. Install the numpy package.") from exc
    return np


def _empty_embedding_array() -> Any:
    return _numpy().zeros((0, 0), dtype="float32")


def _embedding_records(input_data: str, *, molecule_type: str, max_length: int) -> list[dict[str, Any]]:
    text = str(input_data or "")
    if not text.strip():
        return []

    if _looks_like_fasta(text, None):
        return _parse_fasta_embedding_records(text, max_length=max_length)

    path = _candidate_input_path(text)
    if path is not None and path.exists():
        content = path.read_text(encoding="utf-8-sig")
        if _looks_like_fasta(content, path):
            return _parse_fasta_embedding_records(content, max_length=max_length)
        return _plain_embedding_records(content, id_prefix="item", max_length=max_length)

    id_prefix = "text" if molecule_type == "text" and "\n\n" in text else "item"
    return _plain_embedding_records(text, id_prefix=id_prefix, max_length=max_length)


def _candidate_input_path(text: str) -> Path | None:
    if "\n" in text or "\r" in text:
        return None
    try:
        return Path(text).expanduser()
    except (OSError, ValueError):
        return None


def _looks_like_fasta(content: str, path: Path | None) -> bool:
    if path is not None and path.suffix.lower() in {".fa", ".faa", ".fasta", ".fna"}:
        return True
    return str(content).lstrip().startswith(">")


def _parse_fasta_embedding_records(content: str, *, max_length: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current_id = ""
    current_description = ""
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_id, current_description, current_lines
        if not current_id:
            return
        sequence = "".join(current_lines).replace(" ", "").replace("\t", "")
        if sequence:
            truncated = sequence[:max_length]
            records.append({
                "id": current_id,
                "description": current_description,
                "sequence": truncated,
                "original_length": len(sequence),
                "truncated_length": len(truncated),
            })
        current_id = ""
        current_description = ""
        current_lines = []

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            flush()
            current_description = stripped[1:].strip()
            current_id = current_description.split()[0] if current_description else f"seq_{len(records)}"
        elif current_id:
            current_lines.append(stripped)
    flush()
    return records


def _plain_embedding_records(content: str, *, id_prefix: str, max_length: int) -> list[dict[str, Any]]:
    chunks = [line.strip() for line in str(content or "").splitlines() if line.strip() and not line.lstrip().startswith(">")]
    records: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        truncated = chunk[:max_length]
        records.append({
            "id": f"{id_prefix}_{index}",
            "description": f"{id_prefix}_{index}",
            "sequence": truncated,
            "original_length": len(chunk),
            "truncated_length": len(truncated),
        })
    return records


def _generate_embeddings(
    sequences: list[str],
    *,
    embedding_model: str,
    batch_size: int,
    max_length: int,
    pooling: str,
    layer: int,
    normalize: bool,
    compute_device: str,
    fallback_backend: str,
) -> tuple[Any, str, str, str]:
    model_name = _EMBEDDING_MODEL_REGISTRY.get(embedding_model, embedding_model)
    if fallback_backend != "deterministic":
        try:
            embeddings, device = _local_transformer_embeddings(
                sequences,
                model_name=model_name,
                batch_size=batch_size,
                max_length=max_length,
                pooling=pooling,
                layer=layer,
                compute_device=compute_device,
            )
            if normalize:
                embeddings = _normalize_embeddings(embeddings)
            return embeddings, "local_transformer", model_name, device
        except Exception:
            if fallback_backend == "local":
                raise

    embeddings = _deterministic_embeddings(sequences)
    if normalize:
        embeddings = _normalize_embeddings(embeddings)
    device = "cpu" if compute_device == "auto" else compute_device
    return embeddings, "deterministic", model_name, device


def _local_transformer_embeddings(
    sequences: list[str],
    *,
    model_name: str,
    batch_size: int,
    max_length: int,
    pooling: str,
    layer: int,
    compute_device: str,
) -> tuple[Any, str]:
    np = _numpy()
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("torch and transformers are required for local transformer embeddings") from exc

    device = compute_device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, local_files_only=True)
    model = AutoModel.from_pretrained(model_name, trust_remote_code=True, local_files_only=True)
    model = model.to(device)
    model.eval()

    batches = []
    with torch.no_grad():
        for offset in range(0, len(sequences), batch_size):
            batch = sequences[offset: offset + batch_size]
            inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=max_length)
            inputs = {key: value.to(device) for key, value in inputs.items()}
            outputs = model(**inputs, output_hidden_states=True)
            hidden = outputs.last_hidden_state if layer == -1 else outputs.hidden_states[layer]
            mask = inputs["attention_mask"].unsqueeze(-1).float()
            if pooling == "cls":
                pooled = hidden[:, 0]
            elif pooling == "max":
                masked = hidden * mask + (1 - mask) * (-1e9)
                pooled = masked.max(dim=1).values
            else:
                pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            batches.append(pooled.cpu().numpy())
    return np.vstack(batches) if batches else _empty_embedding_array(), str(device)


def _deterministic_embeddings(sequences: list[str]) -> Any:
    np = _numpy()
    vectors = []
    for sequence in sequences:
        vector = np.zeros(_DETERMINISTIC_EMBEDDING_DIM, dtype="float32")
        for index, byte in enumerate(str(sequence).encode("utf-8")):
            vector[index % _DETERMINISTIC_EMBEDDING_DIM] += float(byte) / 255.0
        vector[-1] = float(len(str(sequence))) / max(1.0, _DETERMINISTIC_EMBEDDING_DIM)
        vectors.append(vector)
    return np.vstack(vectors) if vectors else _empty_embedding_array()


def _normalize_embeddings(embeddings: Any) -> Any:
    np = _numpy()
    if embeddings.size == 0:
        return embeddings
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return embeddings / norms


def _embedding_metadata(
    *,
    records: list[dict[str, Any]],
    embeddings: Any,
    embedding_model: str,
    model_name: str,
    molecule_type: str,
    pooling: str,
    layer: int,
    normalize: bool,
    compute_device: str,
    backend: str,
) -> dict[str, Any]:
    shape = list(embeddings.shape) if hasattr(embeddings, "shape") else [0, 0]
    return {
        "backend": backend,
        "embedding_model": embedding_model,
        "model_name": model_name,
        "molecule_type": molecule_type,
        "sequence_count": len(records),
        "sequence_ids": [str(record.get("id", "")) for record in records],
        "original_lengths": [int(record.get("original_length", 0)) for record in records],
        "truncated_lengths": [int(record.get("truncated_length", 0)) for record in records],
        "embedding_shape": shape,
        "embedding_dim": shape[1] if len(shape) > 1 else 0,
        "pooling": pooling,
        "layer": layer,
        "normalize": normalize,
        "device": compute_device,
    }


_CLASSIFIER_REGISTRY: dict[str, dict[str, Any]] = {
    "deeploc": {
        "model": "ElnaggarLab/ankh-base",
        "labels": [
            "Cytoplasm",
            "Nucleus",
            "Extracellular",
            "Mitochondrion",
            "Cell membrane",
            "Endoplasmic reticulum",
            "Plastid",
            "Golgi apparatus",
            "Lysosome/Vacuole",
            "Peroxisome",
        ],
    },
    "signalp": {
        "model": "ElnaggarLab/ankh-base",
        "labels": ["NO_SP", "SP", "LIPO", "TAT"],
    },
    "tmhmm": {
        "model": "facebook/esm2_t12_35M_UR50D",
        "labels": ["TM", "non-TM"],
    },
    "disorder": {
        "model": "facebook/esm2_t6_8M_UR50D",
        "labels": ["ordered", "disordered"],
    },
    "solubility": {
        "model": "facebook/esm2_t12_35M_UR50D",
        "labels": ["soluble", "insoluble"],
    },
}
_CUSTOM_CLASSIFICATION_LABELS = ["class_0", "class_1"]


def _classification_spec(classifier: str, custom_model: str) -> dict[str, Any]:
    if classifier == "custom":
        if not custom_model:
            raise ValueError("AI Sequence Classification requires custom_model when classifier is custom")
        return {
            "model": custom_model,
            "labels": _CUSTOM_CLASSIFICATION_LABELS,
        }
    return _CLASSIFIER_REGISTRY.get(classifier, _CLASSIFIER_REGISTRY["deeploc"])


def _classification_records(input_fasta: Any, *, max_length: int) -> list[dict[str, Any]]:
    path = Path(str(input_fasta or ""))
    if not path.exists():
        raise FileNotFoundError(f"Sequence classification FASTA not found: {path}")
    content = path.read_text(encoding="utf-8-sig")
    return _parse_fasta_embedding_records(content, max_length=max_length)


def _generate_classifications(
    records: list[dict[str, Any]],
    *,
    classifier: str,
    model_name: str,
    labels: list[str],
    batch_size: int,
    max_length: int,
    top_k: int,
    compute_device: str,
    fallback_backend: str,
) -> tuple[list[dict[str, Any]], str, str]:
    if not records:
        return [], "empty", "cpu" if compute_device == "auto" else compute_device
    if fallback_backend != "deterministic":
        try:
            predictions, device = _local_transformer_classifications(
                records,
                model_name=model_name,
                labels=labels,
                batch_size=batch_size,
                max_length=max_length,
                top_k=top_k,
                compute_device=compute_device,
            )
            return predictions, "local_transformer", device
        except Exception:
            if fallback_backend == "local":
                raise
    device = "cpu" if compute_device == "auto" else compute_device
    return _deterministic_classifications(records, classifier=classifier, labels=labels, top_k=top_k), "deterministic", device


def _local_transformer_classifications(
    records: list[dict[str, Any]],
    *,
    model_name: str,
    labels: list[str],
    batch_size: int,
    max_length: int,
    top_k: int,
    compute_device: str,
) -> tuple[list[dict[str, Any]], str]:
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("torch and transformers are required for local sequence classification") from exc

    device = compute_device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        trust_remote_code=True,
        local_files_only=True,
        num_labels=len(labels),
        ignore_mismatched_sizes=True,
    )
    model = model.to(device)
    model.eval()

    predictions: list[dict[str, Any]] = []
    with torch.no_grad():
        for offset in range(0, len(records), batch_size):
            batch = records[offset: offset + batch_size]
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
                predictions.append(_classification_prediction(record, labels, score_row, top_k=top_k))
    return predictions, str(device)


def _deterministic_classifications(
    records: list[dict[str, Any]],
    *,
    classifier: str,
    labels: list[str],
    top_k: int,
) -> list[dict[str, Any]]:
    np = _numpy()
    predictions: list[dict[str, Any]] = []
    for record in records:
        scores = _deterministic_classification_scores(str(record["sequence"]), labels, classifier)
        predictions.append(_classification_prediction(record, labels, np.asarray(scores, dtype="float32"), top_k=top_k))
    return predictions


def _deterministic_classification_scores(sequence: str, labels: list[str], classifier: str) -> list[float]:
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


def _write_classifications_csv(path: Path, predictions: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "sequence_id",
            "sequence_length",
            "truncated_length",
            "top_prediction",
            "confidence",
            "all_predictions",
        ])
        for prediction in predictions:
            top_predictions = prediction.get("top_predictions", [])
            top = top_predictions[0] if top_predictions else {"label": "", "confidence": 0.0}
            all_predictions = "; ".join(
                f"{item['label']}:{float(item['confidence']):.4f}" for item in top_predictions
            )
            writer.writerow([
                prediction.get("sequence_id", ""),
                prediction.get("sequence_length", 0),
                prediction.get("truncated_length", 0),
                top.get("label", ""),
                f"{float(top.get('confidence', 0.0)):.4f}",
                all_predictions,
            ])


def _model_inference_labels(value: Any) -> list[str]:
    labels = [label.strip() for label in str(value or "positive, negative").split(",") if label.strip()]
    return labels or ["positive", "negative"]


def _model_inference_records(input_data: str, *, task: str, max_length: int) -> list[dict[str, Any]]:
    text = str(input_data or "")
    if not text.strip():
        return []

    path = _candidate_input_path(text)
    if path is not None and path.exists():
        content = path.read_text(encoding="utf-8-sig")
    else:
        content = text

    if _looks_like_fasta(content, path if path is not None and path.exists() else None) or task.startswith("sequence"):
        fasta_records = _parse_fasta_embedding_records(content, max_length=max_length)
        if fasta_records:
            return [_model_record_from_embedding_record(record) for record in fasta_records]

    records: list[dict[str, Any]] = []
    for index, chunk in enumerate(line.strip() for line in content.splitlines() if line.strip()):
        truncated = chunk[:max_length]
        records.append({
            "id": f"item_{index}",
            "text": truncated,
            "original_length": len(chunk),
            "truncated_length": len(truncated),
        })
    return records


def _model_record_from_embedding_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(record.get("id", "")),
        "text": str(record.get("sequence", "")),
        "original_length": int(record.get("original_length", 0)),
        "truncated_length": int(record.get("truncated_length", 0)),
    }


def _generate_model_predictions(
    records: list[dict[str, Any]],
    *,
    model_name: str,
    task: str,
    labels: list[str],
    batch_size: int,
    max_length: int,
    top_k: int,
    compute_device: str,
    fallback_backend: str,
) -> tuple[list[dict[str, Any]], str, str]:
    if not records:
        return [], "empty", "cpu" if compute_device == "auto" else compute_device
    if fallback_backend != "deterministic":
        try:
            predictions, device = _local_transformer_model_predictions(
                records,
                model_name=model_name,
                labels=labels,
                batch_size=batch_size,
                max_length=max_length,
                top_k=top_k,
                compute_device=compute_device,
            )
            return predictions, "local_transformer", device
        except Exception:
            if fallback_backend == "local":
                raise
    device = "cpu" if compute_device == "auto" else compute_device
    return _deterministic_model_predictions(records, task=task, labels=labels, top_k=top_k), "deterministic", device


def _local_transformer_model_predictions(
    records: list[dict[str, Any]],
    *,
    model_name: str,
    labels: list[str],
    batch_size: int,
    max_length: int,
    top_k: int,
    compute_device: str,
) -> tuple[list[dict[str, Any]], str]:
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("torch and transformers are required for local model inference") from exc

    device = compute_device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        trust_remote_code=True,
        local_files_only=True,
        num_labels=len(labels),
        ignore_mismatched_sizes=True,
    )
    model = model.to(device)
    model.eval()

    predictions: list[dict[str, Any]] = []
    with torch.no_grad():
        for offset in range(0, len(records), batch_size):
            batch = records[offset: offset + batch_size]
            inputs = tokenizer(
                [str(record["text"]) for record in batch],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=max_length,
            )
            inputs = {key: value.to(device) for key, value in inputs.items()}
            scores = torch.softmax(model(**inputs).logits, dim=-1).cpu().numpy()
            for record, score_row in zip(batch, scores, strict=True):
                predictions.append(_model_prediction(record, labels, score_row, top_k=top_k))
    return predictions, str(device)


def _deterministic_model_predictions(
    records: list[dict[str, Any]],
    *,
    task: str,
    labels: list[str],
    top_k: int,
) -> list[dict[str, Any]]:
    np = _numpy()
    predictions: list[dict[str, Any]] = []
    for record in records:
        scores = _deterministic_classification_scores(str(record["text"]), labels, task)
        predictions.append(_model_prediction(record, labels, np.asarray(scores, dtype="float32"), top_k=top_k))
    return predictions


def _model_prediction(record: dict[str, Any], labels: list[str], scores: Any, *, top_k: int) -> dict[str, Any]:
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
        "input_id": str(record.get("id", "")),
        "input_length": int(record.get("original_length", 0)),
        "truncated_length": int(record.get("truncated_length", 0)),
        "top_predictions": top_predictions,
    }


def _write_model_scores_csv(path: Path, predictions: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "input_id",
            "input_length",
            "truncated_length",
            "top_prediction",
            "confidence",
            "all_predictions",
        ])
        for prediction in predictions:
            top_predictions = prediction.get("top_predictions", [])
            top = top_predictions[0] if top_predictions else {"label": "", "confidence": 0.0}
            all_predictions = "; ".join(
                f"{item['label']}:{float(item['confidence']):.4f}" for item in top_predictions
            )
            writer.writerow([
                prediction.get("input_id", ""),
                prediction.get("input_length", 0),
                prediction.get("truncated_length", 0),
                top.get("label", ""),
                f"{float(top.get('confidence', 0.0)):.4f}",
                all_predictions,
            ])


def _safe_adapter_name(value: Any) -> str:
    raw = str(value or "fine_tuned_adapter").strip() or "fine_tuned_adapter"
    safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in raw)
    return safe.strip("._") or "fine_tuned_adapter"


def _fine_tune_examples(
    value: Any,
    *,
    training_format: str,
    text_column: str,
    prompt_column: str,
    response_column: str,
    required: bool = True,
) -> tuple[list[dict[str, Any]], str]:
    source = str(value or "").strip()
    if not source:
        if required:
            raise ValueError("Fine-Tune LLM requires training_data")
        return [], _resolved_fine_tune_format(source, training_format)

    path = Path(source)
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Fine-Tune LLM training data not found: {path}")
        return [], _resolved_fine_tune_format(source, training_format)

    content = path.read_text(encoding="utf-8-sig")
    resolved_format = _resolved_fine_tune_format(str(path), training_format)
    if resolved_format in {"jsonl", "prompt_response"}:
        return _jsonl_fine_tune_examples(
            content,
            text_column=text_column,
            prompt_column=prompt_column,
            response_column=response_column,
        ), resolved_format
    if resolved_format == "csv":
        return _csv_fine_tune_examples(
            content,
            text_column=text_column,
            prompt_column=prompt_column,
            response_column=response_column,
        ), resolved_format
    return _text_fine_tune_examples(content), "text"


def _resolved_fine_tune_format(source: str, training_format: str) -> str:
    requested = str(training_format or "auto").lower()
    if requested == "auto":
        suffix = Path(str(source)).suffix.lower()
        if suffix in {".jsonl", ".json"}:
            return "prompt_response"
        if suffix in {".csv", ".tsv"}:
            return "csv"
        return "text"
    if requested == "jsonl":
        return "jsonl"
    if requested in {"prompt_response", "csv", "text"}:
        return requested
    return "text"


def _jsonl_fine_tune_examples(
    content: str,
    *,
    text_column: str,
    prompt_column: str,
    response_column: str,
) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for index, line in enumerate(content.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Fine-Tune LLM JSONL line {index + 1} is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"Fine-Tune LLM JSONL line {index + 1} must be a JSON object")
        examples.append(_fine_tune_example_from_mapping(
            parsed,
            index=index,
            text_column=text_column,
            prompt_column=prompt_column,
            response_column=response_column,
        ))
    return examples


def _csv_fine_tune_examples(
    content: str,
    *,
    text_column: str,
    prompt_column: str,
    response_column: str,
) -> list[dict[str, Any]]:
    first_line = content.splitlines()[0] if content.splitlines() else ""
    dialect = "excel-tab" if "\t" in first_line else "excel"
    reader = csv.DictReader(content.splitlines(), dialect=dialect)
    examples: list[dict[str, Any]] = []
    for index, row in enumerate(reader):
        examples.append(_fine_tune_example_from_mapping(
            dict(row),
            index=index,
            text_column=text_column,
            prompt_column=prompt_column,
            response_column=response_column,
        ))
    return examples


def _text_fine_tune_examples(content: str) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for index, line in enumerate(line.strip() for line in content.splitlines() if line.strip()):
        examples.append(_fine_tune_text_example(line, index=index, source="text"))
    return examples


def _fine_tune_example_from_mapping(
    row: dict[str, Any],
    *,
    index: int,
    text_column: str,
    prompt_column: str,
    response_column: str,
) -> dict[str, Any]:
    prompt = str(row.get(prompt_column, "") or "").strip()
    response = str(row.get(response_column, "") or "").strip()
    if prompt or response:
        text = f"### Prompt\n{prompt}\n\n### Response\n{response}".strip()
        example = _fine_tune_text_example(text, index=index, source="prompt_response")
        example["prompt"] = prompt
        example["response"] = response
        return example

    text = str(row.get(text_column, "") or row.get("text", "") or "").strip()
    if not text:
        text = json.dumps(row, sort_keys=True)
    return _fine_tune_text_example(text, index=index, source="text")


def _fine_tune_text_example(text: str, *, index: int, source: str) -> dict[str, Any]:
    content = str(text or "").strip()
    return {
        "id": f"example_{index}",
        "text": content,
        "source": source,
        "char_count": len(content),
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }


def _write_fine_tune_examples(path: Path, examples: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example, sort_keys=True) + "\n")


def _fine_tune_adapter_config(config: dict[str, Any]) -> dict[str, Any]:
    lora = config["lora"]
    return {
        "adapter_type": "lora",
        "base_model_name_or_path": config["base_model"],
        "bias": "none",
        "inference_mode": False,
        "lora_alpha": lora["alpha"],
        "lora_dropout": lora["dropout"],
        "r": lora["rank"],
        "task_type": "CAUSAL_LM",
    }


def _fine_tune_readme(config: dict[str, Any], train_count: int, validation_count: int) -> str:
    return (
        f"# {config['output_adapter_name']}\n\n"
        "This directory contains a reproducible BioNodulo fine-tuning package.\n\n"
        f"- Base model: `{config['base_model']}`\n"
        f"- Backend: `{config['training_backend']}`\n"
        f"- Training records: {train_count}\n"
        f"- Validation records: {validation_count}\n"
        f"- Epochs: {config['epochs']}\n"
        f"- Batch size: {config['batch_size']}\n"
        f"- Learning rate: {config['learning_rate']}\n"
    )


def _fine_tune_metrics(
    config: dict[str, Any],
    *,
    train_examples: list[dict[str, Any]],
    validation_examples: list[dict[str, Any]],
    model_dir: Path,
    metrics_path: Path,
    config_path: Path,
    train_examples_path: Path,
    validation_examples_path: Path,
    adapter_config_path: Path,
    readme_path: Path,
) -> dict[str, Any]:
    train_chars = sum(int(example.get("char_count", 0)) for example in train_examples)
    validation_chars = sum(int(example.get("char_count", 0)) for example in validation_examples)
    steps_per_epoch = (len(train_examples) + config["batch_size"] - 1) // config["batch_size"]
    estimated_steps = steps_per_epoch * config["epochs"] if train_examples else 0
    estimated_loss = _deterministic_fine_tune_loss(train_examples, config)
    return {
        "backend": config["training_backend"],
        "base_model": config["base_model"],
        "training_format": config["training_format"],
        "train_records": len(train_examples),
        "validation_records": len(validation_examples),
        "train_characters": train_chars,
        "validation_characters": validation_chars,
        "epochs": config["epochs"],
        "batch_size": config["batch_size"],
        "learning_rate": config["learning_rate"],
        "estimated_steps": estimated_steps,
        "estimated_train_loss": estimated_loss,
        "device": "cpu" if config["compute_device"] == "auto" else config["compute_device"],
        "lora": config["lora"],
        "artifacts": {
            "model_dir": str(model_dir),
            "metrics": str(metrics_path),
            "training_config": str(config_path),
            "training_examples": str(train_examples_path),
            "validation_examples": str(validation_examples_path),
            "adapter_config": str(adapter_config_path),
            "readme": str(readme_path),
        },
    }


def _deterministic_fine_tune_loss(examples: list[dict[str, Any]], config: dict[str, Any]) -> float:
    if not examples:
        return 0.0
    digest = hashlib.sha256()
    digest.update(str(config["base_model"]).encode("utf-8"))
    for example in examples:
        digest.update(str(example.get("sha256", "")).encode("utf-8"))
    seed = int(digest.hexdigest()[:8], 16)
    size_factor = min(1.0, sum(int(example.get("char_count", 0)) for example in examples) / 10000.0)
    base = 1.0 + (seed % 1000) / 1000.0
    return round(max(0.05, base - (0.25 * size_factor)), 4)


def _ensure_local_fine_tune_backend() -> None:
    missing: list[str] = []
    for module_name in ("torch", "transformers", "datasets", "peft", "accelerate"):
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(module_name)
    if missing:
        raise RuntimeError(
            "local fine-tuning requires torch, transformers, datasets, peft, and accelerate; "
            f"missing: {', '.join(missing)}"
        )
    raise RuntimeError("local fine-tuning is not yet implemented; use training_backend='dry_run'")


_EXTRACTION_SCHEMAS: dict[str, dict[str, Any]] = {
    "genes_variants_diseases": {
        "description": "Extract genes, variants, and diseases",
        "entities": [
            {
                "name": "genes",
                "type": "list",
                "fields": ["gene_symbol", "full_name", "normalized_id", "context"],
            },
            {
                "name": "variants",
                "type": "list",
                "fields": ["hgvs", "gene", "significance", "context"],
            },
            {
                "name": "diseases",
                "type": "list",
                "fields": ["disease_name", "mondo_id", "context"],
            },
        ],
    },
    "drugs_targets": {
        "description": "Extract drug-target relationships",
        "entities": [
            {
                "name": "drugs",
                "type": "list",
                "fields": ["drug_name", "drug_class", "mechanism", "context"],
            },
            {
                "name": "targets",
                "type": "list",
                "fields": ["target_gene", "target_protein", "context"],
            },
            {
                "name": "relationships",
                "type": "list",
                "fields": ["drug", "target", "relationship_type", "evidence", "context"],
            },
        ],
    },
    "clinical_trial": {
        "description": "Extract clinical trial details",
        "entities": [
            {"name": "trial_id", "type": "string"},
            {"name": "phase", "type": "string"},
            {"name": "interventions", "type": "list", "fields": ["type", "name", "context"]},
            {"name": "conditions", "type": "list", "fields": ["condition", "context"]},
            {"name": "endpoints", "type": "list", "fields": ["endpoint_type", "description", "context"]},
            {"name": "patient_count", "type": "integer"},
        ],
    },
    "pathway_interactions": {
        "description": "Extract pathway and interaction information",
        "entities": [
            {
                "name": "pathways",
                "type": "list",
                "fields": ["pathway_name", "source_database", "context"],
            },
            {
                "name": "interactions",
                "type": "list",
                "fields": ["entity_a", "entity_b", "interaction_type", "confidence", "context"],
            },
        ],
    },
}


def _read_data_extraction_text(input_text: Any, input_file: Any) -> str:
    file_value = str(input_file or "").strip()
    if file_value:
        path = Path(file_value)
        if not path.exists():
            raise FileNotFoundError(f"Data extraction input file not found: {path}")
        return path.read_text(encoding="utf-8-sig")
    return str(input_text or "")


def _data_extraction_source_text_length(text: str) -> int:
    return len(text) + 2 if text else 0


def _parse_custom_entities(value: str) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    for line in value.splitlines():
        text = line.strip()
        if not text:
            continue
        if ":" in text:
            name, description = text.split(":", 1)
        else:
            name, description = text, ""
        name = name.strip()
        if name:
            entities.append({"name": name, "description": description.strip()})
    return entities


def _data_extraction_schema(schema_name: str, custom_entities: list[dict[str, str]]) -> dict[str, Any]:
    if schema_name == "custom":
        entities = [
            {
                "name": entity["name"],
                "type": "list",
                "fields": ["value", "context"],
                "description": entity.get("description", ""),
            }
            for entity in custom_entities
        ]
        return {"description": "Custom entity extraction", "entities": entities}
    return _EXTRACTION_SCHEMAS.get(schema_name, _EXTRACTION_SCHEMAS["genes_variants_diseases"])


def _data_extraction_prompt(
    *,
    text: str,
    extraction_schema: str,
    custom_entities: list[dict[str, str]],
    include_context: bool,
    normalize_ids: bool,
) -> str:
    schema = _data_extraction_schema(extraction_schema, custom_entities)
    entity_lines = []
    for entity in schema.get("entities", []):
        name = str(entity.get("name", "entity")).strip()
        entity_type = str(entity.get("type", "list")).strip()
        if entity_type == "list":
            fields = ", ".join(str(field) for field in entity.get("fields", ["value"]))
            description = str(entity.get("description", "") or "").strip()
            suffix = f" ({description})" if description else ""
            entity_lines.append(f"- {name}: list of objects with fields {fields}{suffix}")
        else:
            entity_lines.append(f"- {name}: {entity_type}")

    instructions = [
        f"Extraction schema: {extraction_schema}",
        str(schema.get("description", "") or "").strip(),
        "Extract the following entities from the text below:",
        "\n".join(entity_lines),
    ]
    if include_context:
        instructions.append("Include the surrounding text context for each extracted entity.")
    if normalize_ids:
        instructions.append(
            "Add normalized database IDs where possible, such as HGNC for genes, ClinVar for variants, "
            "MONDO for diseases, and ChEMBL or DrugBank for drugs."
        )
    instructions.extend([
        "Return a JSON object with a top-level key for each entity type.",
        "Use empty arrays or empty strings when no entity of that type is found.",
        f"Text:\n{text}",
    ])
    return "\n\n".join(part for part in instructions if part)


def _write_extraction_csv(path: Path, entities: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["entity_type", "field", "value", "context"])
        for row in _flatten_extraction_rows(entities):
            writer.writerow(row)


def _flatten_extraction_rows(entities: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for entity_type, entity_value in entities.items():
        if isinstance(entity_value, list):
            for item in entity_value:
                if isinstance(item, dict):
                    context = str(item.get("context", "") or "")
                    for field, value in item.items():
                        if field == "context" or value in (None, ""):
                            continue
                        rows.append([str(entity_type), str(field), _csv_value(value), context])
                elif item not in (None, ""):
                    rows.append([str(entity_type), "value", _csv_value(item), ""])
        elif isinstance(entity_value, dict):
            context = str(entity_value.get("context", "") or "")
            for field, value in entity_value.items():
                if field == "context" or value in (None, ""):
                    continue
                rows.append([str(entity_type), str(field), _csv_value(value), context])
        elif entity_value not in (None, ""):
            rows.append([str(entity_type), "value", _csv_value(entity_value), ""])
    return rows


def _csv_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _parse_labels(value: Any) -> list[str]:
    labels = [label.strip().lower() for label in str(value or "").split(",") if label.strip()]
    if not labels:
        raise ValueError("labels must include at least one label")
    return labels


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
) -> list[dict[str, str]]:
    variant_lines = []
    for index, variant in enumerate(variants, start=1):
        fields = ", ".join(f"{key}={value}" for key, value in variant.items() if value)
        variant_lines.append(f"{index}. {fields}")
    literature_instruction = (
        "Include known literature or database evidence where relevant."
        if include_literature
        else "Do not invent literature references; use only the supplied variant table context."
    )
    prompt = (
        f"Interpret these variants using the {framework} framework.\n"
        f"Gene or disease context: {gene_context or 'general variant interpretation'}.\n"
        f"{literature_instruction}\n\n"
        "Variants:\n"
        f"{chr(10).join(variant_lines)}\n\n"
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


def _normalise_interpretations(parsed: dict[str, Any], variants: list[dict[str, str]]) -> list[dict[str, Any]]:
    raw_items = parsed.get("interpretations", []) if isinstance(parsed, dict) else []
    if not isinstance(raw_items, list):
        raw_items = []

    interpretations: list[dict[str, Any]] = []
    for index, variant in enumerate(variants):
        raw = raw_items[index] if index < len(raw_items) and isinstance(raw_items[index], dict) else {}
        variant_id = str(raw.get("variant_id") or _variant_id(variant))
        interpretations.append({
            "variant_id": variant_id,
            "gene": str(raw.get("gene") or variant.get("gene") or variant.get("Gene") or ""),
            "pathogenicity": str(raw.get("pathogenicity") or "Unable to interpret"),
            "confidence": _coerce_confidence(raw.get("confidence")),
            "summary": str(raw.get("summary") or raw.get("justification") or ""),
            "evidence": raw.get("evidence", []),
            "source_variant": variant,
        })
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
            writer.writerow({
                "variant_id": interpretation.get("variant_id", ""),
                "gene": interpretation.get("gene", ""),
                "pathogenicity": interpretation.get("pathogenicity", ""),
                "confidence": interpretation.get("confidence", 0.0),
                "summary": interpretation.get("summary", ""),
            })


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
            records.append({
                "id": identifier,
                "description": current_header,
                "sequence": sequence[:max_seq_length],
                "length": str(len(sequence)),
            })
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
    instruction = custom_prompt.strip() if analysis_type == "custom" and custom_prompt.strip() else _SEQUENCE_ANALYSIS_PROMPTS.get(
        analysis_type,
        _SEQUENCE_ANALYSIS_PROMPTS["comprehensive"],
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


async def _literature_queries(question: str, search_depth: str, config: LLMConfig) -> tuple[list[str], dict[str, Any]]:
    desired = {"quick": 1, "standard": 3, "deep": 5}.get(search_depth, 3)
    prompt = (
        f"Research question:\n{question}\n\n"
        f"Generate up to {desired} PubMed search queries that cover the question with precise biomedical terms. "
        "Return a JSON object with a queries array. Each item must be a valid PubMed search query."
    )
    response = await call_llm(
        config,
        _messages(
            system_prompt="You are a biomedical literature search expert. Generate concise PubMed queries only.",
            prompt=prompt,
        ),
        json_mode=True,
    )
    parsed = safe_json_parse(response.content)
    queries = _normalise_literature_queries(parsed, question, desired)
    return queries, response.usage


def _normalise_literature_queries(parsed: dict[str, Any], question: str, max_queries: int) -> list[str]:
    raw_queries: Any = parsed.get("queries", []) if isinstance(parsed, dict) else []
    if isinstance(raw_queries, str):
        raw_queries = [raw_queries]
    queries: list[str] = []
    if isinstance(raw_queries, list):
        for raw_query in raw_queries:
            query = str(raw_query or "").strip()
            if query and query not in queries:
                queries.append(query)
            if len(queries) >= max_queries:
                break
    return queries or [question]


async def _search_pubmed_literature(
    *,
    queries: list[str],
    max_results: int,
    year_range: str,
    api_key: str,
    email: str,
    include_abstracts: bool,
) -> dict[str, Any]:
    papers_by_pmid: dict[str, dict[str, Any]] = {}
    query_translations: list[str] = []
    for query in queries:
        if len(papers_by_pmid) >= max_results:
            break
        remaining = max_results - len(papers_by_pmid)
        search_payload = await _request_json(
            "esearch.fcgi",
            _pubmed_esearch_params(
                query=query,
                max_results=remaining,
                year_range=year_range,
                api_key=api_key,
                email=email,
            ),
        )
        result = search_payload.get("esearchresult", {})
        translation = str(result.get("querytranslation", "") or "")
        if translation:
            query_translations.append(translation)
        pmids = [str(item) for item in result.get("idlist", []) if str(item)]
        new_pmids = [pmid for pmid in pmids if pmid not in papers_by_pmid]
        if not new_pmids:
            continue
        summaries = await _pubmed_summaries(new_pmids, api_key=api_key, email=email)
        abstracts = await _pubmed_abstracts(new_pmids, api_key=api_key, email=email) if include_abstracts else {}
        for pmid in new_pmids:
            summary = summaries.get(pmid, {})
            if not summary:
                continue
            paper = _paper_from_summary(pmid, summary)
            paper["abstract"] = abstracts.get(pmid, "")
            papers_by_pmid[pmid] = paper
            if len(papers_by_pmid) >= max_results:
                break
    return {"papers": list(papers_by_pmid.values())[:max_results], "query_translations": query_translations}


def _pubmed_esearch_params(
    *,
    query: str,
    max_results: int,
    year_range: str,
    api_key: str,
    email: str,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
        "sort": "relevance",
        "tool": "bionodulo",
        "email": email,
    }
    start, end = _parse_year_range(year_range)
    if start and end:
        params.update({"mindate": start, "maxdate": end, "datetype": "pdat"})
    if api_key:
        params["api_key"] = api_key
    return params


async def _pubmed_summaries(pmids: list[str], *, api_key: str, email: str) -> dict[str, dict[str, Any]]:
    params: dict[str, Any] = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
        "tool": "bionodulo",
        "email": email,
    }
    if api_key:
        params["api_key"] = api_key
    payload = await _request_json("esummary.fcgi", params)
    result = payload.get("result", {})
    if not isinstance(result, dict):
        return {}
    summaries: dict[str, dict[str, Any]] = {}
    for pmid in pmids:
        item = result.get(pmid, {})
        if isinstance(item, dict):
            summaries[pmid] = item
    return summaries


async def _pubmed_abstracts(pmids: list[str], *, api_key: str, email: str) -> dict[str, str]:
    params: dict[str, Any] = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "abstract",
        "retmode": "xml",
        "tool": "bionodulo",
        "email": email,
    }
    if api_key:
        params["api_key"] = api_key
    return _parse_pubmed_abstracts(await _request_text("efetch.fcgi", params))


def _parse_pubmed_abstracts(xml_text: str) -> dict[str, str]:
    if not str(xml_text or "").strip():
        return {}
    root = ET.fromstring(xml_text)
    abstracts: dict[str, str] = {}
    for article in root.findall(".//PubmedArticle"):
        pmid = "".join(article.findtext(".//PMID", default="").split())
        if not pmid:
            continue
        parts = []
        for abstract_text in article.findall(".//AbstractText"):
            label = abstract_text.attrib.get("Label", "")
            text = "".join(abstract_text.itertext()).strip()
            if text:
                parts.append(f"{label}: {text}" if label else text)
        abstracts[pmid] = " ".join(parts)[:2500]
    return abstracts


def _paper_from_summary(pmid: str, summary: dict[str, Any]) -> dict[str, Any]:
    authors = summary.get("authors", [])
    author_names = []
    if isinstance(authors, list):
        author_names = [str(author.get("name", "")).strip() for author in authors if isinstance(author, dict)]
    doi = _extract_doi(str(summary.get("elocationid", "") or ""))
    pubdate = str(summary.get("pubdate", "") or "")
    return {
        "pmid": pmid,
        "title": str(summary.get("title", "") or ""),
        "journal": str(summary.get("fulljournalname") or summary.get("source") or ""),
        "year": _extract_year(pubdate),
        "pubdate": pubdate,
        "authors": [name for name in author_names if name][:5],
        "doi": doi,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def _parse_year_range(value: str) -> tuple[str, str]:
    text = str(value or "").strip()
    if ":" not in text:
        return "", ""
    start, end = [part.strip() for part in text.split(":", 1)]
    return (start, end) if start and end else ("", "")


def _extract_year(value: str) -> str:
    for token in str(value or "").replace("/", " ").split():
        if len(token) >= 4 and token[:4].isdigit():
            return token[:4]
    return ""


def _extract_doi(value: str) -> str:
    text = str(value or "").strip()
    if text.lower().startswith("doi:"):
        return text[4:].strip()
    return text


async def _synthesize_literature(
    question: str,
    papers: list[dict[str, Any]],
    config: LLMConfig,
) -> tuple[str, dict[str, Any]]:
    response = await call_llm(
        config,
        _messages(
            system_prompt=(
                "You are a biomedical research assistant. Synthesize only the supplied papers, cite PMIDs, "
                "and distinguish strong evidence from gaps."
            ),
            prompt=_literature_synthesis_prompt(question, papers),
        ),
        json_mode=False,
    )
    return response.content, response.usage


def _literature_synthesis_prompt(question: str, papers: list[dict[str, Any]]) -> str:
    return (
        f"Research question: {question}\n\n"
        "Relevant papers:\n"
        f"{_literature_context(papers)}\n\n"
        "Write a concise synthesis with: overview, key findings with PMID citations, limitations or contradictions, "
        "and suggested next research steps."
    )


def _literature_context(papers: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    total = 0
    for paper in papers:
        block = (
            f"[PMID:{paper.get('pmid', '')}] {paper.get('title', '')} "
            f"({paper.get('year', '')}; {paper.get('journal', '')})\n"
            f"Authors: {', '.join(paper.get('authors', []))}\n"
            f"Abstract: {str(paper.get('abstract', ''))[:900]}"
        )
        if total + len(block) > 10000:
            break
        blocks.append(block)
        total += len(block)
    return "\n\n".join(blocks)


_REPORT_TYPE_PROMPTS = {
    "analysis": "Generate a comprehensive bioinformatics analysis report with executive summary, results, limitations, and recommendations.",
    "qc": "Generate a quality control report assessing overall quality, per-metric interpretation, and recommendations.",
    "variant": "Generate a variant analysis report with summary statistics, notable variants, interpretation, and limitations.",
    "rnaseq": "Generate an RNA-seq report covering sample quality, expression findings, pathway results, and interpretation.",
    "methylation": "Generate a methylation analysis report covering DMRs, global methylation patterns, and interpretation.",
    "clinical": "Generate a cautious clinical-style report with findings, evidence level, limitations, and review recommendations.",
    "methods": "Generate a publication-style methods section with software, parameters, thresholds, and statistical methods.",
    "custom": "Generate a clear scientific report from the supplied analysis data.",
}


def _report_prompt(
    *,
    title: str,
    report_type: str,
    analysis_data: str,
    additional_files: str,
    include_visualizations: bool,
    include_methods: bool,
    author_name: str,
) -> str:
    sections = [
        _REPORT_TYPE_PROMPTS.get(report_type, _REPORT_TYPE_PROMPTS["analysis"]),
        f"Report title: {title}",
        f"Author: {author_name or 'BioNodulo AI'}",
        f"Analysis data:\n{analysis_data[:8000]}",
    ]
    file_context = _read_report_additional_files(additional_files)
    if file_context:
        sections.append(f"Additional file context:\n{file_context}")
    if include_methods:
        sections.append("Include a Methods section describing the analysis approach.")
    if include_visualizations:
        sections.append("Mention where visualizations, plots, or summary tables would improve the report.")
    sections.append("Generate the report in Markdown format with clear headings and concise scientific language.")
    return "\n\n".join(sections)


def _read_report_additional_files(value: str) -> str:
    blocks: list[str] = []
    for raw_path in str(value or "").replace(",", "\n").splitlines():
        raw_path = raw_path.strip()
        if not raw_path:
            continue
        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(f"AI report additional file not found: {path}")
        blocks.append(f"--- {path.name} ---\n{path.read_text(encoding='utf-8', errors='replace')[:5000]}")
    return "\n\n".join(blocks)


def _report_html(title: str, markdown: str) -> str:
    body = _markdown_to_basic_html(markdown)
    safe_title = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>
body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; max-width: 960px; margin: 0 auto; padding: 28px; color: #172033; line-height: 1.6; }}
h1 {{ border-bottom: 3px solid #2563eb; padding-bottom: 8px; }}
h2 {{ border-bottom: 1px solid #cbd5e1; padding-bottom: 4px; margin-top: 28px; }}
code {{ background: #f1f5f9; padding: 2px 4px; border-radius: 3px; }}
pre {{ background: #f8fafc; border: 1px solid #cbd5e1; padding: 12px; overflow-x: auto; }}
.footer {{ margin-top: 40px; border-top: 1px solid #cbd5e1; color: #64748b; font-size: 13px; padding-top: 12px; }}
</style>
</head>
<body>
{body}
<div class="footer">Generated by BioNodulo AI Report Generator. AI-generated content requires independent review.</div>
</body>
</html>
"""


def _markdown_to_basic_html(markdown: str) -> str:
    html_lines: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            html_lines.append(f"<p>{'<br>'.join(paragraph)}</p>")
            paragraph.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            flush_paragraph()
            continue
        if line.startswith("#"):
            flush_paragraph()
            level = min(len(line) - len(line.lstrip("#")), 6)
            text = line[level:].strip()
            html_lines.append(f"<h{level}>{html.escape(text)}</h{level}>")
            continue
        if line.startswith("- "):
            flush_paragraph()
            html_lines.append(f"<ul><li>{html.escape(line[2:].strip())}</li></ul>")
            continue
        paragraph.append(html.escape(line))
    flush_paragraph()
    return "\n".join(html_lines)
