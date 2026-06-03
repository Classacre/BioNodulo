"""Workflow AI/LLM nodes."""
from __future__ import annotations

import csv
import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx

from bionodulo.ai.llm_backend import LLMConfig, call_llm, render_prompt, resolve_llm_config, safe_json_parse
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
    value = str(explicit or "").strip()
    if value:
        return value
    if context is not None and hasattr(context, "resolve_secret"):
        secret = context.resolve_secret("ncbi_api_key") or context.resolve_secret("NCBI_API_KEY")
        if secret:
            return str(secret).strip()
    return os.environ.get("NCBI_API_KEY", "")


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
