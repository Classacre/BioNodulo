"""Phylogenetic analysis nodes for BioNodulo.

Provides nodes for multiple sequence alignment (MAFFT, Clustal-Omega)
and tree inference (IQ-TREE, FastTree, RAxML).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from io import StringIO
from typing import Any
from xml.etree import ElementTree as ET

import httpx
from Bio import Phylo

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin.api.http import APICache, APIHttpClient, TokenBucketRateLimiter
from bionodulo.nodes.command_node import CommandNode


EBI_CLUSTALO_BASE_URL = "https://www.ebi.ac.uk/Tools/services/rest/clustalo"
EBI_CLUSTALO_USER_AGENT = "BioNodulo/2.0 (workflow node; EMBL-EBI Clustal Omega)"
EBI_CLUSTALO_CACHE_TTL_S = 300.0
EBI_CLUSTALO_RATE_LIMIT_PER_SECOND = 1.0
EBI_CLUSTALO_API_CACHE = APICache.from_environment(default_ttl_seconds=EBI_CLUSTALO_CACHE_TTL_S)
EBI_CLUSTALO_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=EBI_CLUSTALO_RATE_LIMIT_PER_SECOND, burst=1)
EBI_CLUSTALO_SEQUENCE_TYPES = ("protein", "dna", "rna")
EBI_CLUSTALO_OUTPUT_FORMATS = ("fa", "clustal", "clustal_num", "msf", "nexus", "phylip", "selex", "stockholm", "vienna")
EBI_CLUSTALO_MAX_ITERATIONS = 5
EBI_CLUSTALO_ALIGNMENT_EXTENSIONS = {
    "fa": ".fasta",
    "clustal": ".aln",
    "clustal_num": ".aln",
    "msf": ".msf",
    "nexus": ".nex",
    "phylip": ".phy",
    "selex": ".slx",
    "stockholm": ".stk",
    "vienna": ".vie",
}
EBI_CLUSTALO_RUNNING_STATUSES = {"PENDING", "RUNNING", "QUEUED"}
EBI_CLUSTALO_FAILED_STATUSES = {"FAILURE", "ERROR", "NOT_FOUND", "CANCELLED"}
PHYLOT_BASE_URL = "https://phylot.biobyte.de"
PHYLOT_USER_AGENT = "BioNodulo/2.0 (workflow node; PhyloT)"
PHYLOT_CACHE_TTL_S = 300.0
PHYLOT_RATE_LIMIT_PER_SECOND = 1.0
PHYLOT_API_CACHE = APICache.from_environment(default_ttl_seconds=PHYLOT_CACHE_TTL_S)
PHYLOT_RATE_LIMITER = TokenBucketRateLimiter(rate_per_second=PHYLOT_RATE_LIMIT_PER_SECOND, burst=1)
PHYLOT_OUTPUT_FORMATS = ("newick", "nexus", "phyloxml")
PHYLOT_FORMAT_EXTENSIONS = {
    "newick": ".nwk",
    "nexus": ".nex",
    "phyloxml": ".xml",
}
PHYLOT_NCBI_NODE_IDENTIFIERS = ("name", "id", "nameid", "idname")
PHYLOT_INTERRUPT_LEVELS = ("0", "species", "genus", "family", "order", "class", "phylum")
PHYLOT_GTDB_SOURCES = ("bac", "ar")
PHYLOT_GTDB_VERSIONS = ("202", "207", "214", "220", "232")
MAX_RETRIES = 3
RETRY_DELAY_S = 1.0
REQUEST_TIMEOUT_S = 60.0


def _phylogeny_node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _split_text_list(value: Any) -> list[str]:
    items: list[str] = []
    for chunk in str(value or "").replace(",", "\n").splitlines():
        stripped = chunk.strip()
        if stripped:
            items.append(stripped)
    return items


def _coerce_phylot_taxa(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return _split_text_list(text)


def _safe_filename(value: str, default: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return name or default


def _count_fasta_records(value: str) -> int:
    return sum(1 for line in value.splitlines() if line.lstrip().startswith(">"))


def _html_to_text(value: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _validate_phylot_tree_response(text: str) -> None:
    stripped = text.strip()
    if not stripped:
        raise RuntimeError("PhyloT returned an empty tree response")
    if re.search(r"(?is)<\s*(?:!doctype\s+html|html|body|head|title|h[1-6])\b", stripped):
        summary = _html_to_text(stripped)[:500] or "HTML error response"
        raise RuntimeError(f"PhyloT returned an error page: {summary}")


async def _phylot_request_text(
    endpoint: str,
    data: dict[str, str],
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> str:
    response = await _phylot_request(endpoint, data=data, retries=retries, timeout=timeout)
    return response.text


async def _phylot_request(
    endpoint: str,
    *,
    data: dict[str, str],
    retries: int,
    timeout: float,
) -> httpx.Response:
    endpoint = endpoint.lstrip("/")
    url = f"{PHYLOT_BASE_URL}/{endpoint}"
    client = APIHttpClient(cache=PHYLOT_API_CACHE, rate_limiter=PHYLOT_RATE_LIMITER)
    try:
        return await client.request(
            "POST",
            url,
            data=data,
            headers={"User-Agent": PHYLOT_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=None,
            follow_redirects=True,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f"PhyloT {endpoint} failed with HTTP {status}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"PhyloT {endpoint} request failed: {exc}") from exc


async def _ebi_clustalo_post_text(
    endpoint: str,
    data: dict[str, Any],
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> str:
    response = await _ebi_clustalo_request("POST", endpoint, data=data, retries=retries, timeout=timeout)
    return response.text


async def _ebi_clustalo_get_text(
    endpoint: str,
    *,
    retries: int = MAX_RETRIES,
    timeout: float = REQUEST_TIMEOUT_S,
) -> str:
    response = await _ebi_clustalo_request("GET", endpoint, retries=retries, timeout=timeout)
    return response.text


async def _ebi_clustalo_request(
    method: str,
    endpoint: str,
    *,
    data: dict[str, Any] | None = None,
    retries: int,
    timeout: float,
) -> httpx.Response:
    endpoint = endpoint.lstrip("/")
    url = f"{EBI_CLUSTALO_BASE_URL}/{endpoint}"
    client = APIHttpClient(cache=EBI_CLUSTALO_API_CACHE, rate_limiter=EBI_CLUSTALO_RATE_LIMITER)
    method = method.upper()
    request_kwargs: dict[str, Any] = {}
    if method == "POST":
        request_kwargs["data"] = data
    try:
        return await client.request(
            method,
            url,
            **request_kwargs,
            headers={"User-Agent": EBI_CLUSTALO_USER_AGENT},
            timeout=timeout,
            retries=retries,
            retry_delay=RETRY_DELAY_S,
            cache_ttl=None,
            follow_redirects=True,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        body = exc.response.text[:500]
        raise RuntimeError(f"EBI Clustal Omega {endpoint} failed with HTTP {status}: {body}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"EBI Clustal Omega {endpoint} request failed: {exc}") from exc


def _ebi_clustalo_result_types(xml_text: str) -> list[str]:
    identifiers: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return identifiers
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == "identifier" and element.text:
            identifiers.append(element.text.strip())
    return [identifier for identifier in identifiers if identifier]


def _ebi_clustalo_alignment_result_type(output_format: str, result_types: list[str]) -> str:
    preferred = {
        "fa": "aln-fasta",
        "clustal": "aln-clustal",
        "clustal_num": "aln-clustal_num",
        "msf": "aln-msf",
        "nexus": "aln-nexus",
        "phylip": "aln-phylip",
        "selex": "aln-selex",
        "stockholm": "aln-stockholm",
        "vienna": "aln-vienna",
    }[output_format]
    if preferred in result_types:
        return preferred
    for result_type in result_types:
        if result_type.startswith("aln-"):
            return result_type
    return preferred


def _validate_ebi_clustalo_result(text: str, label: str) -> None:
    stripped = text.strip()
    if not stripped:
        raise RuntimeError(f"EBI Clustal Omega returned an empty {label} response")
    if re.search(r"(?is)<\s*(?:!doctype\s+html|html|body|head|title|h[1-6]|error)\b", stripped):
        summary = _html_to_text(stripped)[:500] or f"{label} error response"
        raise RuntimeError(f"EBI Clustal Omega returned an error page for {label}: {summary}")


def _canonical_newick(path: Path) -> str:
    tree = Phylo.read(str(path), "newick")
    handle = StringIO()
    Phylo.write(tree, handle, "newick")
    return handle.getvalue().strip()


class MAFFTNode(CommandNode):
    """Multiple sequence alignment with MAFFT."""
    NODE_ID = "mafft"
    DISPLAY_NAME = "MAFFT"
    REQUIRED_CONDA_PACKAGES = ['mafft']
    CATEGORY = "phylogeny"
    DESCRIPTION = "Multiple sequence alignment with MAFFT (fast FFT-based)"
    SEARCH_ALIASES = ["mafft", "align", "msa", "multiple alignment"]
    RETURN_TYPES = ("ALIGNMENT",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["mafft"]
    DOCUMENTATION_URL = "https://mafft.cbrc.jp/alignment/software/"
    VERSION = "7.520"
    COMMAND = [
        "mafft",
        "--thread", "{inputs.threads}",
        "{inputs.input}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "Input sequences FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "strategy": ("STRING", {"default": "auto", "description": "Alignment strategy: auto, linsi, ginsi, einsi"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        strategy = inputs.get("strategy", "auto")
        cmd = ["mafft", "--thread", str(inputs.get("threads", 4))]
        flag = f"--{strategy}" if not strategy.startswith("--") else strategy
        cmd.append(flag)
        cmd.append(str(inputs.get("input", "")))
        return cmd

    async def run(self, **kwargs: Any) -> Any:
        """Run MAFFT and capture stdout to the output file."""
        import shutil
        from pathlib import Path

        context = kwargs.get("context")
        output_dir = kwargs.get("output_dir")
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")

        # Run the command (stdout is captured to stdout.log by subprocess_runner)
        result = await super().run(**kwargs)

        # Copy stdout.log to the expected output path
        if output_dir:
            stdout_log = Path(output_dir) / "stdout.log"
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)
            if stdout_log.exists() and outputs:
                target = outputs[0]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(stdout_log), str(target))

        return result


class ClustalONode(CommandNode):
    """Multiple sequence alignment with Clustal Omega."""
    NODE_ID = "clustalo"
    DISPLAY_NAME = "Clustal Omega"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Scalable multiple protein sequence alignment"
    SEARCH_ALIASES = ["clustal", "clustalo", "clustal omega", "msa"]
    RETURN_TYPES = ("ALIGNMENT",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["clustalo"]
    REQUIRED_CONDA_PACKAGES = ['clustal-omega']
    DOCUMENTATION_URL = "http://www.clustal.org/omega/"
    VERSION = "1.2.4"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "clustalo",
            "-i", str(inputs.get("input", "")),
            "-o", f"{inputs.get('output', '.')}/alignment.fasta",
            "--threads", str(inputs.get("threads", 4)),
            "--force",
        ]
        if inputs.get("outfmt"):
            cmd.extend(["--outfmt", str(inputs["outfmt"])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "Input sequences FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "outfmt": ("STRING", {"default": "fasta"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MUSCLENode(CommandNode):
    """Multiple sequence alignment with MUSCLE."""

    NODE_ID = "muscle"
    DISPLAY_NAME = "MUSCLE"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Multiple sequence alignment with MUSCLE, especially for protein sequences."
    SEARCH_ALIASES = ["muscle", "align", "msa", "multiple alignment", "protein alignment"]
    RETURN_TYPES = ("ALIGNMENT",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["muscle"]
    REQUIRED_CONDA_PACKAGES = ["muscle"]
    DOCUMENTATION_URL = "https://drive5.com/muscle/"
    VERSION = "5.3"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sequences": ("FASTA", {"description": "Input sequences FASTA"}),
            },
            "optional": {
                "maxiters": ("INT", {"default": 0, "min": 0, "description": "Maximum refinement iterations; 0 uses MUSCLE default"}),
                "diags": ("BOOLEAN", {"default": False, "description": "Use diagonal optimization for similar sequences"}),
                "stable": ("BOOLEAN", {"default": False, "description": "Preserve input sequence order in output"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "muscle",
            "-align",
            str(inputs.get("sequences", "")),
            "-output",
            f"{inputs.get('output', '.')}/alignment.aln.fasta",
        ]
        if inputs.get("maxiters"):
            cmd.extend(["-maxiters", str(inputs["maxiters"])])
        if inputs.get("diags"):
            cmd.append("-diags")
        if inputs.get("stable"):
            cmd.append("-stable")
        return cmd


class TrimAlNode(CommandNode):
    """Automated multiple sequence alignment trimming with trimAl."""

    NODE_ID = "trimal"
    DISPLAY_NAME = "trimAl"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Automated trimming of multiple sequence alignments before tree inference."
    SEARCH_ALIASES = ["trimal", "trimAl", "alignment trimming", "msa trim", "phylogeny"]
    RETURN_TYPES = ("FASTA", "STATS_FILE")
    RETURN_NAMES = ("trimmed", "stats")
    REQUIRED_EXECUTABLES = ["trimal"]
    REQUIRED_CONDA_PACKAGES = ["trimal"]
    DOCUMENTATION_URL = "http://trimal.cgenomics.org/"
    VERSION = "1.4.1"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": ("ALIGNMENT", {"description": "Input multiple sequence alignment"}),
            },
            "optional": {
                "automated": (
                    "STRING",
                    {
                        "default": "automated1",
                        "options": ["automated1", "strict", "strictplus", "gappyout"],
                        "description": "trimAl automated trimming strategy",
                    },
                ),
                "fasta_output": ("BOOLEAN", {"default": True, "description": "Write FASTA-formatted trimmed alignment"}),
                "htmlout": ("BOOLEAN", {"default": False, "description": "Also write an HTML trimming report"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get("output", "."))
        automated = str(inputs.get("automated", "automated1") or "automated1")
        if automated not in {"automated1", "strict", "strictplus", "gappyout"}:
            raise ValueError(f"Unsupported trimAl automated mode: {automated}")

        cmd = [
            "trimal",
            "-in",
            str(inputs.get("alignment", "")),
            "-out",
            f"{out_dir}/trimmed.fasta",
            f"-{automated}",
        ]
        if inputs.get("fasta_output", True):
            cmd.append("-fasta")
        if inputs.get("htmlout"):
            cmd.extend(["-htmlout", f"{out_dir}/stats.html"])
        return cmd


class IQTREENode(CommandNode):
    """Phylogenetic tree inference with IQ-TREE."""
    NODE_ID = "iqtree"
    DISPLAY_NAME = "IQ-TREE"
    REQUIRED_CONDA_PACKAGES = ['iqtree']
    CATEGORY = "phylogeny"
    DESCRIPTION = "Efficient phylogenomic inference with maximum likelihood"
    SEARCH_ALIASES = ["iqtree", "maximum likelihood", "tree", "phylogeny"]
    RETURN_TYPES = ("PHYLOGENY_TREE",)
    RETURN_NAMES = ("tree",)
    REQUIRED_EXECUTABLES = ["iqtree"]
    DOCUMENTATION_URL = "http://www.iqtree.org/"
    VERSION = "2.3.4"
    COMMAND = [
        "iqtree",
        "-s", "{inputs.alignment}",
        "-nt", "{inputs.threads}",
        "-pre", "{output}/tree",
        "-m", "{inputs.model}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": ("ALIGNMENT", {"description": "Multiple sequence alignment"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "model": ("STRING", {"default": "MFP", "description": "Substitution model: MFP, GTR+I+G, LG+I+G, etc."}),
                "bootstrap": ("INT", {"default": 1000, "min": 0, "max": 10000, "step": 100, "display": "slider"}),
                "alrt": ("INT", {"default": 1000, "min": 0}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "iqtree",
            "-s", str(inputs.get("alignment", "")),
            "-nt", str(inputs.get("threads", 4)),
            "-pre", f"{inputs.get('output', '.')}/tree",
            "-m", str(inputs.get("model", "MFP")),
        ]
        if inputs.get("bootstrap"):
            cmd.extend(["-bb", str(inputs["bootstrap"])])
        if inputs.get("alrt"):
            cmd.extend(["-alrt", str(inputs["alrt"])])
        return cmd


class FastTreeNode(CommandNode):
    """Fast phylogenetic tree inference with FastTree."""
    NODE_ID = "fasttree"
    DISPLAY_NAME = "FastTree"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Approximately maximum-likelihood phylogenetic tree inference"
    SEARCH_ALIASES = ["fasttree", "quick tree", "approximate ml"]
    RETURN_TYPES = ("PHYLOGENY_TREE",)
    RETURN_NAMES = ("tree",)
    REQUIRED_EXECUTABLES = ["FastTree"]
    REQUIRED_CONDA_PACKAGES = ['fasttree']
    DOCUMENTATION_URL = "http://www.microbesonline.org/fasttree/"
    VERSION = "2.1.11"
    COMMAND = [
        "FastTree",
        "-gamma",
        "-boot", "100",
        "{inputs.alignment}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": ("ALIGNMENT", {"description": "Multiple sequence alignment (protein or nucleotide)"}),
            },
            "optional": {
                "nucleotide": ("BOOLEAN", {"default": False, "description": "Use nucleotide model instead of protein"}),
                "gtr": ("BOOLEAN", {"default": False, "description": "Use GTR model for nucleotides"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["FastTree"]
        if inputs.get("nucleotide"):
            cmd.append("-nt")
        if inputs.get("gtr"):
            cmd.append("-gtr")
        cmd.extend(["-gamma", "-boot", "100"])
        cmd.append(str(inputs.get("alignment", "")))
        return cmd

    async def run(self, **kwargs: Any) -> Any:
        """Run FastTree and capture stdout to the output file."""
        import shutil
        from pathlib import Path

        context = kwargs.get("context")
        output_dir = kwargs.get("output_dir")
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")

        result = await super().run(**kwargs)

        if output_dir:
            stdout_log = Path(output_dir) / "stdout.log"
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)
            if stdout_log.exists() and outputs:
                target = outputs[0]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(stdout_log), str(target))

        return result


class RAxMLNode(CommandNode):
    """Phylogenetic tree inference with RAxML."""
    NODE_ID = "raxml"
    DISPLAY_NAME = "RAxML"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Maximum likelihood phylogenetic inference with RAxML"
    SEARCH_ALIASES = ["raxml", "maximum likelihood", "tree", "evolution"]
    RETURN_TYPES = ("PHYLOGENY_TREE",)
    RETURN_NAMES = ("tree",)
    REQUIRED_EXECUTABLES = ["raxmlHPC"]
    REQUIRED_CONDA_PACKAGES = ['raxml']
    DOCUMENTATION_URL = "https://github.com/stamatak/standard-RAxML"
    VERSION = "8.2.12"
    COMMAND = [
        "raxmlHPC",
        "-s", "{inputs.alignment}",
        "-n", "{inputs.prefix}",
        "-m", "{inputs.model}",
        "-p", "12345",
        "-T", "{inputs.threads}",
        "-w", "{output}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": ("ALIGNMENT", {"description": "Phylip-formatted alignment"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
                "model": ("STRING", {"default": "GTRGAMMA", "description": "Substitution model"}),
                "prefix": ("STRING", {"default": "tree"}),
            },
            "optional": {
                "bootstrap": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "raxmlHPC",
            "-s", str(inputs.get("alignment", "")),
            "-n", str(inputs.get("prefix", "tree")),
            "-m", str(inputs.get("model", "GTRGAMMA")),
            "-p", "12345",
            "-T", str(inputs.get("threads", 4)),
            "-w", os.path.abspath(str(inputs.get("output", "."))),
        ]
        if inputs.get("bootstrap"):
            cmd.extend(["-b", "12345", "-#", "100"])
        return cmd


class RAxMLNGNode(CommandNode):
    """Phylogenetic tree inference with RAxML-NG."""

    NODE_ID = "raxml_ng"
    DISPLAY_NAME = "RAxML-NG"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Maximum likelihood phylogenetic tree inference with RAxML-NG."
    SEARCH_ALIASES = ["raxml-ng", "raxml", "maximum likelihood", "phylogeny", "bootstrap"]
    RETURN_TYPES = ("NEWICK", "FILE")
    RETURN_NAMES = ("tree", "bootstrap")
    REQUIRED_EXECUTABLES = ["raxml-ng"]
    REQUIRED_CONDA_PACKAGES = ["raxml-ng"]
    DOCUMENTATION_URL = "https://github.com/amkozlov/raxml-ng"
    VERSION = "1.2.2"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": ("FASTA", {"description": "Multiple sequence alignment"}),
                "model": ("STRING", {"default": "GTR+G", "description": "Substitution model, e.g. GTR+G or LG+G"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "seed": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "bootstrap_replicates": ("INT", {"default": 100, "min": 0, "max": 10000, "step": 100}),
                "outgroup": ("STRING", {"default": "", "description": "Comma-separated outgroup taxa", "advanced": True}),
                "tree_search": ("BOOLEAN", {"default": True, "description": "Run ML tree search; disable for evaluation only"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        prefix = f"{inputs.get('output', '.')}/raxml_ng"
        cmd = [
            "raxml-ng",
            "--msa",
            str(inputs.get("alignment", "")),
            "--model",
            str(inputs.get("model", "GTR+G")),
            "--prefix",
            prefix,
            "--threads",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("seed"):
            cmd.extend(["--seed", str(inputs["seed"])])
        if inputs.get("tree_search", True):
            cmd.append("--all")
            if inputs.get("bootstrap_replicates"):
                cmd.extend(["--bs-trees", str(inputs["bootstrap_replicates"])])
        else:
            cmd.append("--evaluate")
        if inputs.get("outgroup"):
            cmd.extend(["--outgroup", str(inputs["outgroup"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        prefix = Path(output_dir) / cls.NODE_ID / "raxml_ng"
        prefix.parent.mkdir(parents=True, exist_ok=True)
        return [
            Path(f"{prefix}.raxml.bestTree"),
            Path(f"{prefix}.raxml.bootstraps"),
        ]


class ModelTestNGNode(CommandNode):
    """Substitution model selection with ModelTest-NG."""

    NODE_ID = "modeltest_ng"
    DISPLAY_NAME = "ModelTest-NG"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Select best-fit substitution model for phylogenetic analysis."
    SEARCH_ALIASES = ["modeltest-ng", "modeltest", "substitution model", "model selection", "phylogeny"]
    RETURN_TYPES = ("STRING", "JSON")
    RETURN_NAMES = ("best_model", "model_stats")
    REQUIRED_EXECUTABLES = ["modeltest-ng"]
    REQUIRED_CONDA_PACKAGES = ["modeltest-ng"]
    DOCUMENTATION_URL = "https://github.com/ddarriba/modeltest"
    VERSION = "0.1.7"
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": ("FASTA", {"description": "Multiple sequence alignment"}),
                "datatype": ("STRING", {"default": "nt", "options": ["nt", "aa"]}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "template": ("STRING", {"default": "", "options": ["", "raxml", "phyml", "mrbayes", "paup"]}),
                "models": ("STRING", {"default": "", "description": "Optional comma-separated model subset"}),
                "schemes": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "ascertainment_bias": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get("output", "."))
        output_prefix = f"{out_dir}/modeltest"
        best_model = f"{out_dir}/best_model.txt"
        model_stats = f"{out_dir}/model_stats.json"
        cmd = [
            "modeltest-ng",
            "-i",
            str(inputs.get("alignment", "")),
            "-d",
            str(inputs.get("datatype", "nt")),
            "-p",
            str(inputs.get("threads", 4)),
            "-o",
            output_prefix,
        ]
        if inputs.get("template"):
            cmd.extend(["-T", str(inputs["template"])])
        if inputs.get("models"):
            cmd.extend(["-m", str(inputs["models"])])
        if inputs.get("schemes"):
            cmd.extend(["-s", str(inputs["schemes"])])
        if inputs.get("ascertainment_bias"):
            cmd.append("--asc-bias")

        best_model_payload = f"'best_model\\tSee {output_prefix}.out\\n'"
        model_stats_payload = (
            f"'{{\\n  \"modeltest_output\": \"{output_prefix}.out\",\\n"
            f"  \"ranking\": \"{output_prefix}.ranking\"\\n}}\\n'"
        )
        cmd.extend(["&&", "printf", best_model_payload, ">", best_model])
        cmd.extend(["&&", "printf", model_stats_payload, ">", model_stats])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "best_model.txt", node_out / "model_stats.json"]


class ASTRALNode(CommandNode):
    """Species tree inference from discordant gene trees with ASTRAL."""

    NODE_ID = "astral"
    DISPLAY_NAME = "ASTRAL Species Tree"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Species tree inference from discordant gene trees via coalescent quartet summarization."
    SEARCH_ALIASES = ["astral", "species tree", "coalescent", "gene tree", "quartet", "ils", "phylogenomics"]
    RETURN_TYPES = ("NEWICK", "FILE")
    RETURN_NAMES = ("species_tree", "astral_log")
    REQUIRED_EXECUTABLES = ["astral"]
    REQUIRED_CONDA_PACKAGES = ["astral-tree"]
    DOCUMENTATION_URL = "https://github.com/smirarab/ASTRAL"
    VERSION = "5.7.8"
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gene_trees": ("FILE", {"description": "Gene trees, one Newick tree per line"}),
            },
            "optional": {
                "multi_individuals": ("FILE", {"description": "Multi-individual mapping file for ASTRAL -a"}),
                "boot_trees": ("FILE", {"description": "Bootstrap gene trees for local posterior support"}),
                "num_reps": ("INT", {"default": 100, "min": 10, "description": "Number of bootstrap replicates"}),
                "exact": ("BOOLEAN", {"default": False, "description": "Use exact search mode"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not str(inputs.get("gene_trees", "")).strip():
            return "Required input 'gene_trees' must be a nonempty file path"
        num_reps = inputs.get("num_reps")
        if num_reps is not None and num_reps < 10:
            return "Input 'num_reps' must be at least 10"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get("output", "."))
        cmd = [
            "astral",
            "-i",
            str(inputs.get("gene_trees", "")),
            "-o",
            f"{out_dir}/species_tree.nwk",
        ]
        if inputs.get("multi_individuals"):
            cmd.extend(["-a", str(inputs["multi_individuals"])])
        if inputs.get("boot_trees"):
            cmd.extend(["-b", str(inputs["boot_trees"]), "-r", str(inputs.get("num_reps", 100))])
        if inputs.get("exact"):
            cmd.append("-x")
        cmd.extend([">", f"{out_dir}/astral_log.log", "2>&1"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "species_tree.nwk", node_out / "astral_log.log"]


class EBIClustalOmegaNode(BaseNode):
    """Run Clustal Omega through the EMBL-EBI Job Dispatcher service."""

    NODE_ID = "ebi_clustal_omega"
    DISPLAY_NAME = "EBI Clustal Omega"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Run multiple sequence alignment through EMBL-EBI Clustal Omega web services."
    SEARCH_ALIASES = ["ebi", "clustal omega", "clustalo", "msa", "alignment", "web service"]
    RETURN_TYPES = ("ALIGNMENT", "NEWICK", "JSON")
    RETURN_NAMES = ("alignment", "tree", "job_metadata")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    DOCUMENTATION_URL = "https://www.ebi.ac.uk/Tools/services/rest/clustalo"
    VERSION = "1.0.0"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sequences": ("FASTA", {"description": "Three or more sequences in FASTA format"}),
                "email": ("STRING", {"default": "", "description": "Email address required by EMBL-EBI Job Dispatcher"}),
            },
            "optional": {
                "sequence_type": ("STRING", {"default": "protein", "options": list(EBI_CLUSTALO_SEQUENCE_TYPES)}),
                "output_format": ("STRING", {"default": "fa", "options": list(EBI_CLUSTALO_OUTPUT_FORMATS)}),
                "order": ("STRING", {"default": "aligned", "options": ["aligned", "input"]}),
                "dealign": ("BOOLEAN", {"default": False, "advanced": True}),
                "add_formats": ("BOOLEAN", {"default": False, "advanced": True}),
                "iterations": ("INT", {"default": 0, "min": 0, "max": EBI_CLUSTALO_MAX_ITERATIONS, "advanced": True}),
                "timeout_minutes": ("INT", {"default": 30, "min": 1, "max": 240}),
                "poll_interval_seconds": ("FLOAT", {"default": 10.0, "min": 0.1, "advanced": True}),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        sequences = str(kwargs.get("sequences", "") or "")
        if _count_fasta_records(sequences) < 3:
            raise ValueError("EBI Clustal Omega requires at least three FASTA records")
        email = str(kwargs.get("email", "") or "").strip()
        if not email:
            raise ValueError("EBI Clustal Omega requires an email address")

        sequence_type = str(kwargs.get("sequence_type", "protein") or "protein").lower()
        if sequence_type not in EBI_CLUSTALO_SEQUENCE_TYPES:
            raise ValueError(f"Unsupported sequence_type: {sequence_type}")
        output_format = str(kwargs.get("output_format", "fa") or "fa").lower()
        if output_format not in EBI_CLUSTALO_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported output_format: {output_format}")
        order = str(kwargs.get("order", "aligned") or "aligned").lower()
        if order not in {"aligned", "input"}:
            raise ValueError(f"Unsupported order: {order}")

        output_name = _safe_filename(str(kwargs.get("output_name", "") or ""), "clustal_omega")
        timeout_minutes = int(kwargs.get("timeout_minutes", 30) or 30)
        poll_interval_seconds = float(kwargs.get("poll_interval_seconds", 10.0) or 10.0)
        params = self._submit_params(
            sequences=sequences,
            email=email,
            sequence_type=sequence_type,
            output_format=output_format,
            order=order,
            kwargs=kwargs,
        )
        job_id = await self._submit_job(params)
        status_history = await self._poll_job(
            job_id=job_id,
            timeout_minutes=timeout_minutes,
            poll_interval_seconds=poll_interval_seconds,
        )
        result_types = _ebi_clustalo_result_types(await _ebi_clustalo_get_text(f"resulttypes/{job_id}"))
        alignment_result_type = _ebi_clustalo_alignment_result_type(output_format, result_types)
        tree_result_type = "phylotree" if "phylotree" in result_types else "guidetree"
        if tree_result_type not in result_types:
            raise RuntimeError(f"EBI Clustal Omega job {job_id} did not provide a tree result")

        alignment_text = await _ebi_clustalo_get_text(f"result/{job_id}/{alignment_result_type}")
        _validate_ebi_clustalo_result(alignment_text, "alignment")
        tree_text = await _ebi_clustalo_get_text(f"result/{job_id}/{tree_result_type}")
        _validate_ebi_clustalo_result(tree_text, "tree")

        alignment_path, tree_path, metadata_path = self.PLAN_OUTPUTS(
            {"output_name": output_name, "output_format": output_format},
            Path(getattr(context, "node_dir", ".") if context else "."),
        )
        alignment_path.write_text(alignment_text if alignment_text.endswith("\n") else alignment_text + "\n", encoding="utf-8")
        tree_path.write_text(tree_text if tree_text.endswith("\n") else tree_text + "\n", encoding="utf-8")
        metadata = {
            "alignment": str(alignment_path),
            "alignment_result_type": alignment_result_type,
            "job_id": job_id,
            "params": params,
            "result_types": result_types,
            "status_history": status_history,
            "tree": str(tree_path),
            "tree_result_type": tree_result_type,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {
            "outputs": {
                "alignment": str(alignment_path),
                "tree": str(tree_path),
                "job_metadata": str(metadata_path),
            }
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_format = str(inputs.get("output_format", "fa") or "fa").lower()
        if output_format not in EBI_CLUSTALO_OUTPUT_FORMATS:
            output_format = "fa"
        output_name = _safe_filename(str(inputs.get("output_name", "") or ""), "clustal_omega")
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [
            node_out / f"{output_name}_alignment{EBI_CLUSTALO_ALIGNMENT_EXTENSIONS[output_format]}",
            node_out / f"{output_name}_tree.nwk",
            node_out / "job_metadata.json",
        ]

    def _submit_params(
        self,
        *,
        sequences: str,
        email: str,
        sequence_type: str,
        output_format: str,
        order: str,
        kwargs: dict[str, Any],
    ) -> dict[str, str]:
        params = {
            "email": email,
            "title": "bionodulo_ebi_clustal_omega",
            "sequence": sequences,
            "stype": sequence_type,
            "outfmt": output_format,
            "order": order,
            "guidetreeout": "true",
        }
        if bool(kwargs.get("dealign", False)):
            params["dealign"] = "true"
        if bool(kwargs.get("add_formats", False)):
            params["addformats"] = "true"
        iterations = int(kwargs.get("iterations", 0) or 0)
        if not 0 <= iterations <= EBI_CLUSTALO_MAX_ITERATIONS:
            raise ValueError(f"EBI Clustal Omega iterations must be between 0 and {EBI_CLUSTALO_MAX_ITERATIONS}")
        if iterations:
            params["iterations"] = str(iterations)
        return params

    async def _submit_job(self, params: dict[str, str]) -> str:
        job_id = (await _ebi_clustalo_post_text("run", params)).strip()
        if not job_id:
            raise RuntimeError("EBI Clustal Omega did not return a job ID")
        return job_id

    async def _poll_job(
        self,
        *,
        job_id: str,
        timeout_minutes: int,
        poll_interval_seconds: float,
    ) -> list[str]:
        started = time.monotonic()
        history: list[str] = []
        while True:
            elapsed_minutes = (time.monotonic() - started) / 60
            if elapsed_minutes > timeout_minutes:
                raise RuntimeError(f"EBI Clustal Omega job {job_id} timed out after {timeout_minutes} minutes")
            status = (await _ebi_clustalo_get_text(f"status/{job_id}")).strip().upper()
            history.append(status)
            if status == "FINISHED":
                return history
            if status in EBI_CLUSTALO_FAILED_STATUSES:
                raise RuntimeError(f"EBI Clustal Omega job {job_id} failed with status {status}")
            if status in EBI_CLUSTALO_RUNNING_STATUSES:
                await asyncio.sleep(poll_interval_seconds)
                continue
            raise RuntimeError(f"EBI Clustal Omega job {job_id} returned unrecognised status: {status}")


class PhyloTNode(BaseNode):
    """Generate taxonomy-derived trees through the PhyloT web service."""

    NODE_ID = "phylot"
    DISPLAY_NAME = "PhyloT"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Generate taxonomy-derived phylogenetic trees from taxon names, taxonomy IDs, or accessions via PhyloT."
    SEARCH_ALIASES = ["phylot", "taxonomy tree", "newick", "ncbi taxonomy", "gtdb", "tree generator"]
    RETURN_TYPES = ("NEWICK", "JSON")
    RETURN_NAMES = ("tree", "request_metadata")
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://phylot.biobyte.de/help.cgi"
    VERSION = "1.0.0"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "taxa": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "description": "Taxon names, taxonomy IDs, accessions, or subtree requests separated by newlines or commas",
                    },
                ),
            },
            "optional": {
                "taxonomy_source": ("STRING", {"default": "ncbi", "options": ["ncbi", "gtdb"]}),
                "output_format": ("STRING", {"default": "newick", "options": list(PHYLOT_OUTPUT_FORMATS)}),
                "node_identifiers": ("STRING", {"default": "name", "options": list(PHYLOT_NCBI_NODE_IDENTIFIERS)}),
                "collapse_internal_nodes": ("BOOLEAN", {"default": False}),
                "force_binary_tree": ("BOOLEAN", {"default": False}),
                "interrupt_at": ("STRING", {"default": "0", "options": list(PHYLOT_INTERRUPT_LEVELS)}),
                "filter_terms": ("STRING", {"default": "", "advanced": True}),
                "ignore_errors": ("BOOLEAN", {"default": False, "advanced": True}),
                "gtdb_source": ("STRING", {"default": "bac", "options": list(PHYLOT_GTDB_SOURCES), "advanced": True}),
                "include_gtdb_branch_support": ("BOOLEAN", {"default": True, "advanced": True}),
                "include_gtdb_genome_ids": ("BOOLEAN", {"default": False, "advanced": True}),
                "gtdb_version": ("STRING", {"default": "232", "options": list(PHYLOT_GTDB_VERSIONS), "advanced": True}),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        taxa = _coerce_phylot_taxa(kwargs.get("taxa"))
        if len(taxa) < 2 and not any("|subtree" in item.lower() for item in taxa):
            raise ValueError("PhyloT requires at least two taxa or one subtree request")

        taxonomy_source = str(kwargs.get("taxonomy_source", "ncbi") or "ncbi").lower()
        if taxonomy_source not in {"ncbi", "gtdb"}:
            raise ValueError(f"Unsupported taxonomy_source: {taxonomy_source}")

        output_format = str(kwargs.get("output_format", "newick") or "newick").lower()
        if output_format not in PHYLOT_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported output_format: {output_format}")

        interrupt_at = str(kwargs.get("interrupt_at", "0") or "0").lower()
        if interrupt_at not in PHYLOT_INTERRUPT_LEVELS:
            raise ValueError(f"Unsupported interrupt_at: {interrupt_at}")

        output_name = _safe_filename(str(kwargs.get("output_name", "") or ""), "phylot_tree")
        endpoint, params = self._request_params(
            taxa=taxa,
            taxonomy_source=taxonomy_source,
            output_format=output_format,
            output_name=output_name,
            interrupt_at=interrupt_at,
            kwargs=kwargs,
        )

        tree_text = await _phylot_request_text(endpoint, params)
        _validate_phylot_tree_response(tree_text)
        out_dir = _phylogeny_node_output_dir(self, context)
        tree_path = out_dir / f"{output_name}{PHYLOT_FORMAT_EXTENSIONS[output_format]}"
        metadata_path = out_dir / "request_metadata.json"
        tree_path.write_text(tree_text if tree_text.endswith("\n") else tree_text + "\n", encoding="utf-8")

        metadata = {
            "endpoint": endpoint,
            "format": output_format,
            "taxonomy_source": taxonomy_source,
            "taxa_count": len(taxa),
            "tree": str(tree_path),
            "params": params,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return str(tree_path), str(metadata_path)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_format = str(inputs.get("output_format", "newick") or "newick").lower()
        if output_format not in PHYLOT_OUTPUT_FORMATS:
            output_format = "newick"
        output_name = _safe_filename(str(inputs.get("output_name", "") or ""), "phylot_tree")
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [
            node_out / f"{output_name}{PHYLOT_FORMAT_EXTENSIONS[output_format]}",
            node_out / "request_metadata.json",
        ]

    def _request_params(
        self,
        *,
        taxa: list[str],
        taxonomy_source: str,
        output_format: str,
        output_name: str,
        interrupt_at: str,
        kwargs: dict[str, Any],
    ) -> tuple[str, dict[str, str]]:
        common = {
            "itol": "0",
            "itolProject": "0",
            "treeElements": "\n".join(taxa),
            "filter": str(kwargs.get("filter_terms", "") or ""),
            "interrupt": interrupt_at,
            "format": output_format,
            "fileName": output_name,
            "noerror": "1" if bool(kwargs.get("ignore_errors", False)) else "0",
        }
        if taxonomy_source == "gtdb":
            gtdb_source = str(kwargs.get("gtdb_source", "bac") or "bac").lower()
            if gtdb_source not in PHYLOT_GTDB_SOURCES:
                raise ValueError(f"Unsupported gtdb_source: {gtdb_source}")
            gtdb_version = str(kwargs.get("gtdb_version", "232") or "232")
            if gtdb_version not in PHYLOT_GTDB_VERSIONS:
                raise ValueError(f"Unsupported gtdb_version: {gtdb_version}")
            params = {
                "phylotgtd": "1",
                **common,
                "src": gtdb_source,
                "boot": "1" if bool(kwargs.get("include_gtdb_branch_support", True)) else "0",
                "gid": "1" if bool(kwargs.get("include_gtdb_genome_ids", False)) else "0",
                "gtdb_version": gtdb_version,
            }
            return "treeGeneratorGTD.cgi", params

        node_identifiers = str(kwargs.get("node_identifiers", "name") or "name").lower()
        if node_identifiers not in PHYLOT_NCBI_NODE_IDENTIFIERS:
            raise ValueError(f"Unsupported node_identifiers: {node_identifiers}")
        params = {
            "phylot": "1",
            **common,
            "ids": node_identifiers,
            "collapse": "1" if bool(kwargs.get("collapse_internal_nodes", False)) else "0",
            "binary": "1" if bool(kwargs.get("force_binary_tree", False)) else "0",
        }
        return "treeGenerator.cgi", params


class PhylogeneticTreeBuilderNode(BaseNode):
    """Create a consensus tree manifest from one or more phylogenetic tree outputs."""

    NODE_ID = "phylogenetic_tree_builder"
    DISPLAY_NAME = "Phylo Tree Builder"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Build phylogenetic trees using multiple methods with consensus from existing Newick outputs."
    SEARCH_ALIASES = ["phylo tree builder", "consensus tree", "newick", "tree consensus", "phylogeny"]
    RETURN_TYPES = ("NEWICK", "JSON")
    RETURN_NAMES = ("consensus_tree", "individual_trees")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["biopython"]
    DOCUMENTATION_URL = "https://biopython.org/wiki/Phylo"
    VERSION = "1.0.0"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "tree_files": ("FILE", {"description": "Newline- or comma-separated Newick tree files"}),
            },
            "optional": {
                "methods": ("STRING", {"default": "", "description": "Names corresponding to tree_files"}),
                "consensus_method": ("STRING", {"default": "majority", "options": ["majority", "first"]}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        tree_files = [Path(path) for path in _split_text_list(kwargs.get("tree_files"))]
        if not tree_files:
            raise ValueError("At least one tree file is required")

        methods = _split_text_list(kwargs.get("methods"))
        consensus_method = str(kwargs.get("consensus_method", "majority") or "majority")
        if consensus_method not in {"majority", "first"}:
            raise ValueError(f"Unsupported consensus method: {consensus_method}")

        entries: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        first_index: dict[str, int] = {}
        for index, path in enumerate(tree_files):
            if not path.exists():
                raise ValueError(f"Tree file not found: {path}")
            newick = _canonical_newick(path)
            counts[newick] = counts.get(newick, 0) + 1
            first_index.setdefault(newick, index)
            entries.append({
                "method": methods[index] if index < len(methods) else f"tree_{index + 1}",
                "path": str(path),
                "newick": newick,
            })

        if consensus_method == "first":
            selected_newick = entries[0]["newick"]
        else:
            selected_newick = min(counts, key=lambda item: (-counts[item], first_index[item], item))
        selected_index = first_index[selected_newick]

        for entry in entries:
            entry["support_count"] = counts[entry["newick"]]
            entry["selected"] = entry["newick"] == selected_newick

        out_dir = _phylogeny_node_output_dir(self, context)
        consensus_path = out_dir / "consensus_tree.nwk"
        manifest_path = out_dir / "individual_trees.json"
        consensus_path.write_text(selected_newick + "\n", encoding="utf-8")
        manifest_path.write_text(
            json.dumps({
                "consensus_method": consensus_method,
                "selected_tree_index": selected_index,
                "tree_count": len(entries),
                "trees": entries,
            }, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return str(consensus_path), str(manifest_path)
