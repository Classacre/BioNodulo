"""
AI chat assistant for BioNodulo.

Provides workflow-aware chat capabilities supporting multiple LLM providers:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Custom / self-hosted providers (OpenAI-compatible API)
"""

from __future__ import annotations

import json
import os
import re as re_mod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


BIONODULO_SYSTEM_PROMPT = '''You are the BioNodulo AI Assistant, an expert bioinformatics workflow advisor.

BioNodulo is a visual node-based bioinformatics workbench. Users build workflows by connecting nodes on a canvas.

NODE LIBRARY (built-in nodes):

Quality Control:
- fastqc: Generate quality control reports for FASTQ files
- multiqc: Aggregate QC reports from multiple tools
- qualimap: BAM QC and coverage analysis

Trimming:
- fastp: Ultra-fast all-in-one FASTQ preprocessor
- trimmomatic: Flexible read trimming tool
- cutadapt: Adapter removal tool

Alignment:
- bowtie2: Fast gapped read alignment
- bwa_mem: Burrows-Wheeler aligner (MEM algorithm)
- minimap2: Versatile sequence alignment
- star_align: Spliced read aligner for RNA-seq
- hisat2: Hierarchical indexing for spliced alignment

SAM/BAM Processing:
- samtools_sort: Sort BAM files
- samtools_index: Index BAM files
- samtools_flagstat: Alignment statistics
- samtools_view: Convert/filter SAM/BAM
- samtools_merge: Merge multiple BAM files

Variant Calling:
- bcftools_mpileup: Generate VCF/BCF variant calls
- gatk_haplotypecaller: GATK germline SNP/indel caller

Assembly:
- spades: Genome assembler for small genomes
- megahit: Ultra-fast metagenome assembler
- canu: Long-read assembler

Annotation:
- prokka: Rapid prokaryotic genome annotation
- eggnog: Functional annotation via orthology
- interproscan: Protein domain analysis

RNA-Seq:
- salmon_quant: Transcript quantification
- kallisto: Pseudoalignment-based quantification
- featurecounts: Read counting for genomic features

Metagenomics:
- kraken2: Taxonomic classification
- bracken: Species abundance estimation
- metaphlan: Microbial community profiling
- humann: Functional profiling

Phylogenetics:
- iqtree: Efficient phylogenomic tree inference
- fasttree: Approximately maximum-likelihood trees
- raxml: Maximum likelihood phylogeny

Utility:
- file_input: Input file/folder node
- command: Generic shell command wrapper
- collect_files: Gather multiple files into a list
- view_text: Display text content

WORKFLOW HELP:
- When users ask for workflow advice, suggest specific nodes and connections
- Consider tool compatibility (output types must match input types)
- Suggest QC steps before and after major operations
- Recommend appropriate parameters for common use cases
- Warn about common pitfalls (e.g., reference genome format, read groups)

You can also modify workflows by returning a JSON node_blueprint. Users may upload workflow JSON for analysis.
'''


@dataclass
class ChatMessage:
    """A single chat message."""

    role: str
    content: str


@dataclass
class ChatResponse:
    """Response from the AI assistant."""

    reply: str
    workflow: dict[str, Any] | None = None
    node_blueprint: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None


async def chat_with_assistant(
    messages: list[dict[str, str]] | list[ChatMessage],
    workflow: dict[str, Any] | None = None,
    provider: str = "openai",
    model: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    stream: bool = False,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> ChatResponse | AsyncIterator[str]:
    """Send messages to an LLM and get a BioNodulo-aware response.

    Args:
        messages: List of message dicts with ``role`` and ``content`` keys,
            or list of :class:`ChatMessage` objects.
        workflow: Optional current workflow dict for context.
        provider: LLM provider (``"openai"``, ``"anthropic"``, ``"custom"``).
        model: Model name (defaults to provider-specific default).
        api_key: API key for the provider.
        api_base: Custom API base URL (for custom/self-hosted providers).
        stream: If *True*, return an async iterator of response chunks.
        system_prompt: Override the default BioNodulo system prompt.
        temperature: Sampling temperature.
        max_tokens: Maximum response tokens.

    Returns:
        A :class:`ChatResponse` if ``stream=False``, or an async iterator
        of response text chunks if ``stream=True``.

    Raises:
        ValueError: If provider is unsupported or API key is missing.
        RuntimeError: If the API request fails.
    """
    # Normalize messages
    norm_messages: list[dict[str, str]] = []
    for msg in messages:
        if isinstance(msg, ChatMessage):
            norm_messages.append({"role": msg.role, "content": msg.content})
        else:
            norm_messages.append(dict(msg))

    # Add system prompt if not present
    if not any(m.get("role") == "system" for m in norm_messages):
        norm_messages.insert(
            0, {"role": "system", "content": system_prompt or BIONODULO_SYSTEM_PROMPT}
        )

    # Inject workflow context if provided
    if workflow:
        wf_summary = _summarize_workflow(workflow)
        norm_messages.append(
            {"role": "system", "content": "Current workflow context:\n" + wf_summary}
        )

    if provider == "openai":
        return await _chat_openai(
            messages=norm_messages,
            model=model or "gpt-4",
            api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
            api_base=api_base,
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif provider == "anthropic":
        return await _chat_anthropic(
            messages=norm_messages,
            model=model or "claude-3-sonnet-20240229",
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY", ""),
            api_base=api_base,
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif provider == "custom":
        return await _chat_openai(
            messages=norm_messages,
            model=model or "gpt-4",
            api_key=api_key or "",
            api_base=api_base,
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")


async def _chat_openai(
    messages: list[dict[str, str]],
    model: str,
    api_key: str,
    api_base: str | None,
    stream: bool,
    temperature: float,
    max_tokens: int,
) -> ChatResponse | AsyncIterator[str]:
    """Chat via OpenAI API."""
    if not api_key:
        raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY env var or pass api_key.")

    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx is required for AI assistant. Install with: pip install httpx")

    base_url = api_base or "https://api.openai.com/v1"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }

    if stream:
        return _stream_openai(base_url, headers, payload)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120.0,
        )

        if response.status_code != 200:
            raise RuntimeError(f"OpenAI API error {response.status_code}: {response.text}")

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return _parse_response(content)


async def _stream_openai(
    base_url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> AsyncIterator[str]:
    """Stream OpenAI response chunks."""
    import httpx
    async with httpx.AsyncClient() as ac:
        async with ac.stream(
            "POST",
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120.0,
        ) as response:
            if response.status_code != 200:
                text = await response.aread()
                raise RuntimeError(f"OpenAI API error {response.status_code}: {text.decode()}")
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0].get("delta", {})
                        if "content" in delta and delta["content"]:
                            yield delta["content"]
                    except (json.JSONDecodeError, KeyError):
                        continue


async def _chat_anthropic(
    messages: list[dict[str, str]],
    model: str,
    api_key: str,
    api_base: str | None,
    stream: bool,
    temperature: float,
    max_tokens: int,
) -> ChatResponse | AsyncIterator[str]:
    """Chat via Anthropic Claude API."""
    if not api_key:
        raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY env var or pass api_key.")

    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx is required for AI assistant. Install with: pip install httpx")

    # Separate system message from conversation
    system_content = ""
    conversation: list[dict[str, str]] = []
    for msg in messages:
        if msg["role"] == "system":
            system_content += msg["content"] + "\n"
        else:
            conversation.append(msg)

    base_url = api_base or "https://api.anthropic.com"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": model,
        "messages": conversation,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream,
    }
    if system_content:
        payload["system"] = system_content.strip()

    if stream:
        return _stream_anthropic(base_url, headers, payload)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/v1/messages",
            headers=headers,
            json=payload,
            timeout=120.0,
        )

        if response.status_code != 200:
            raise RuntimeError(f"Anthropic API error {response.status_code}: {response.text}")

        data = response.json()
        content = data["content"][0]["text"]
        return _parse_response(content)


async def _stream_anthropic(
    base_url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> AsyncIterator[str]:
    """Stream Anthropic response chunks."""
    import httpx
    async with httpx.AsyncClient() as ac:
        async with ac.stream(
            "POST",
            f"{base_url}/v1/messages",
            headers=headers,
            json=payload,
            timeout=120.0,
        ) as response:
            if response.status_code != 200:
                text = await response.aread()
                raise RuntimeError(f"Anthropic API error {response.status_code}: {text.decode()}")
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue
                try:
                    chunk = json.loads(line[6:])
                    if chunk.get("type") == "content_block_delta":
                        delta = chunk.get("delta", {})
                        if delta.get("type") == "text_delta" and "text" in delta:
                            yield delta["text"]
                except (json.JSONDecodeError, KeyError):
                    continue


def _parse_response(content: str) -> ChatResponse:
    """Parse LLM response content into a structured ChatResponse."""
    reply = content
    workflow = None
    node_blueprint = None
    validation = None

    json_blocks = _extract_json_blocks(content)
    for block in json_blocks:
        try:
            parsed = json.loads(block)
            if "node_type" in parsed and "inputs" in parsed:
                node_blueprint = parsed
            elif "nodes" in parsed and "edges" in parsed:
                workflow = parsed
            elif "valid" in parsed or "errors" in parsed:
                validation = parsed
        except json.JSONDecodeError:
            continue

    if json_blocks:
        reply = re_mod.sub(r"```json\n.*?\n```", "", reply, flags=re_mod.DOTALL).strip()
        reply = re_mod.sub(r"\n{3,}", "\n\n", reply)

    return ChatResponse(
        reply=reply,
        workflow=workflow,
        node_blueprint=node_blueprint,
        validation=validation,
    )


def _extract_json_blocks(content: str) -> list[str]:
    """Extract JSON blocks from markdown-formatted content."""
    blocks: list[str] = []
    for match in re_mod.finditer(r"```json\n(.*?)\n```", content, re_mod.DOTALL):
        blocks.append(match.group(1))
    return blocks


def _summarize_workflow(workflow: dict[str, Any]) -> str:
    """Create a text summary of a workflow for LLM context."""
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    name = workflow.get("name", "Untitled Workflow")

    lines = [f"Workflow: {name}", f"Nodes: {len(nodes)}", f"Edges: {len(edges)}", ""]
    for node in nodes:
        nid = node.get("id", "?")
        ntype = node.get("type", "?")
        widgets = node.get("widgets", {})
        widget_summary = ", ".join(f"{k}={v}" for k, v in list(widgets.items())[:3])
        lines.append(f"  - {nid}: {ntype} ({widget_summary})")
    return "\n".join(lines)
