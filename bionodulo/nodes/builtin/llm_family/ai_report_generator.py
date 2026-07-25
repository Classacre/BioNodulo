"""Provider-backed Markdown report generation and deterministic HTML rendering."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from .adapter import (
    LiteLLMNode,
    _llm_config_from_kwargs,
    _messages,
    _node_output_dir,
    call_llm,
    require_artifacts,
    validate_choice,
)


class AIReportGeneratorNode(LiteLLMNode):
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
                "analysis_data": (
                    "STRING",
                    {"default": "", "multiline": True, "description": "Analysis results to interpret"},
                ),
                "report_title": ("STRING", {"default": "Bioinformatics Analysis Report"}),
            },
            "optional": {
                "report_type": (
                    "STRING",
                    {
                        "default": "analysis",
                        "options": [
                            "analysis",
                            "qc",
                            "variant",
                            "rnaseq",
                            "methylation",
                            "clinical",
                            "methods",
                            "custom",
                        ],
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
        report_type = validate_choice(
            kwargs.get("report_type", "analysis"),
            "report_type",
            tuple(_REPORT_TYPE_PROMPTS),
        )
        output_format = validate_choice(
            kwargs.get("output_format", "html"), "output_format", ("html", "markdown", "both")
        )
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
            require_artifacts(report_path)
            html_path = str(report_path)
            if context is not None and hasattr(context, "register_preview"):
                context.register_preview(report_path, label="AI Report Generator")
        return {"outputs": {"report_html": html_path, "report_markdown": markdown}}


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
