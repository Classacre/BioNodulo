"""Workflow AI/LLM nodes."""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any

from bionodulo.ai.llm_backend import LLMConfig, call_llm, render_prompt, resolve_llm_config, safe_json_parse
from bionodulo.nodes.base import BaseNode


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
