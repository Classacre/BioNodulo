"""Phylogenetic analysis nodes for BioNodulo.

Provides nodes for multiple sequence alignment (MAFFT, Clustal-Omega)
and tree inference (IQ-TREE, FastTree, RAxML).
"""
from __future__ import annotations

import json
import os
import re
import shlex
from pathlib import Path
from io import StringIO
from typing import Any
from xml.etree import ElementTree as ET

import httpx

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
    # Lazy import — biopython is a runtime dep (REQUIRED_CONDA_PACKAGES), not in
    # the slim worker base image, so keep node-module import light (§38).
    from Bio import Phylo

    tree = Phylo.read(str(path), "newick")
    handle = StringIO()
    Phylo.write(tree, handle, "newick")
    return handle.getvalue().strip()


class _ClustalOContract(CommandNode):
    """Multiple sequence alignment with Clustal Omega."""
    LEGACY_NODE_ID = "clustalo"
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


class _MUSCLEContract(CommandNode):
    """Multiple sequence alignment with MUSCLE."""

    LEGACY_NODE_ID = "muscle"
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


class _TrimAlContract(CommandNode):
    """Automated multiple sequence alignment trimming with trimAl."""

    LEGACY_NODE_ID = "trimal"
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


class _FastTreeContract(CommandNode):
    """Fast phylogenetic tree inference with FastTree."""
    LEGACY_NODE_ID = "fasttree"
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


class _RAxMLContract(CommandNode):
    """Phylogenetic tree inference with RAxML."""
    LEGACY_NODE_ID = "raxml"
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


class _RAxMLNGContract(CommandNode):
    """Phylogenetic tree inference with RAxML-NG."""

    LEGACY_NODE_ID = "raxml_ng"
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


class _ModelTestNGContract(CommandNode):
    """Substitution model selection with ModelTest-NG."""

    LEGACY_NODE_ID = "modeltest_ng"
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


class _ASTRALContract(CommandNode):
    """Estimate species trees from gene trees with ASTRAL-III."""

    LEGACY_NODE_ID = "astral"
    DISPLAY_NAME = "ASTRAL-III"
    CATEGORY = "phylogeny"
    DESCRIPTION = "Estimate an unrooted species tree from unrooted gene trees with ASTRAL-III."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "ASTRAL",
        "ASTRAL-III",
        "astral",
        "species tree",
        "gene tree",
        "quartet support",
        "coalescent",
        "incomplete lineage sorting",
        "phylogenomics",
    ]
    RETURN_TYPES = ("PHYLOGENY_TREE", "TXT", "TSV")
    RETURN_NAMES = ("output", "log_output", "branch_annotations")
    REQUIRED_EXECUTABLES = ["astral"]
    REQUIRED_CONDA_PACKAGES = ["astral-tree"]
    DOCUMENTATION_URL = "https://github.com/smirarab/ASTRAL"
    CITATION_DOIS = ["10.1186/s12859-018-2129-y"]
    CITATION_URLS = ["https://doi.org/10.1186/s12859-018-2129-y"]
    CITATION_TEXT = (
        "ASTRAL-III: polynomial time species tree reconstruction from partially resolved gene trees."
    )
    VERSION = "5.7.8+galaxy0"
    SHELL = True

    BRANCH_ANNOTATE_OPTIONS = ["0", "1", "2", "3", "4", "8", "16", "32", "10"]

    @classmethod
    def _branch_annotate(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("branch_annotate", "3") or "3")

    @classmethod
    def _lambda_value(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get("lambda", 0.5)

    @classmethod
    def _export_branch_annotations(cls, inputs: dict[str, Any]) -> bool:
        return cls._branch_annotate(inputs) in {"16", "32"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("PHYLOGENY_TREE", {"description": "Newick gene tree file"}),
            },
            "optional": {
                "branch_annotate": (
                    "STRING",
                    {
                        "default": "3",
                        "options": cls.BRANCH_ANNOTATE_OPTIONS,
                        "description": "ASTRAL -t branch annotation mode",
                    },
                ),
                "lambda": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0,
                        "max": 10,
                        "description": "Yule prior lambda parameter for branch lengths and posterior probabilities",
                    },
                ),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input tree file is required"
        branch_annotate = cls._branch_annotate(inputs)
        if branch_annotate not in cls.BRANCH_ANNOTATE_OPTIONS:
            return f"branch_annotate must be one of: {', '.join(cls.BRANCH_ANNOTATE_OPTIONS)}"
        try:
            lambda_value = float(cls._lambda_value(inputs))
        except (TypeError, ValueError):
            return "lambda must be numeric"
        if lambda_value < 0 or lambda_value > 10:
            return "lambda must be between 0 and 10"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out_dir = str(inputs.get("output", "."))
        cmd = [
            "astral",
            "--input",
            str(inputs.get("input", "")),
            "--branch-annotate",
            cls._branch_annotate(inputs),
            "--output",
            "./output.tre",
            "--lambda",
            str(cls._lambda_value(inputs)),
            "2>&1",
            "|",
            "tee",
            f"{out_dir}/log_output.txt",
        ]
        commands = [
            f"mkdir -p {shlex.quote(out_dir)}",
            f"cd {shlex.quote(out_dir)}",
            " ".join(shlex.quote(part) for part in cmd)
            .replace("'2>&1'", "2>&1")
            .replace("'|'", "|"),
            f"mv ./output.tre {shlex.quote(f'{out_dir}/output.tre')}",
        ]
        if cls._export_branch_annotations(inputs):
            commands.append(f"mv freqQuad.csv {shlex.quote(f'{out_dir}/branch_annotations.tsv')}")
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        outputs = [node_out / "output.tre", node_out / "log_output.txt"]
        if cls._export_branch_annotations(inputs):
            outputs.append(node_out / "branch_annotations.tsv")
        return outputs






