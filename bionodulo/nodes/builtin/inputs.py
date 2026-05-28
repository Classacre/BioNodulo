"""Input nodes for BioNodulo workflows.

Provides nodes for importing bioinformatics data files into workflows.
These nodes serve as workflow entry points for various file formats.

URL-aware: any input that looks like an http(s)/ftp URL is fetched to a
workspace-scoped cache directory on first run; subsequent runs reuse the
cached copy. This replaces the older "Download example data" startup
prompt — templates ship URLs directly in their node params and download on
demand instead of requiring a separate up-front fetch.
"""
from __future__ import annotations

import gzip
import hashlib
import logging
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode

logger = logging.getLogger(__name__)

URL_SCHEMES = {"http", "https", "ftp", "ftps"}
_HTTP_USER_AGENT = "BioNodulo/2.0 (https://github.com/Classacre/BioNodulo; input-node downloader)"
_DOWNLOAD_TIMEOUT_S = 300


def _looks_like_url(value: Any) -> bool:
    """Return True when *value* is a plausible http(s)/ftp URL string."""
    if not isinstance(value, str):
        return False
    if "://" not in value:
        return False
    try:
        parsed = urllib.parse.urlparse(value)
    except ValueError:
        return False
    return parsed.scheme.lower() in URL_SCHEMES and bool(parsed.netloc)


def _safe_filename(url: str) -> str:
    """Derive a safe local filename from a URL.

    Uses the URL's path basename when present; falls back to a short hash so
    multiple URLs at the same path (e.g. ``?download=1`` query variants)
    don't collide in the cache.
    """
    parsed = urllib.parse.urlparse(url)
    name = Path(parsed.path).name or "download"
    # Strip query string from name to avoid weird characters; if the URL had
    # significant query state, append a short hash so distinct URLs map to
    # distinct files.
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "download"
    if parsed.query:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
        stem, *suffix = name.split(".", 1)
        suffix_str = f".{suffix[0]}" if suffix else ""
        name = f"{stem}-{digest}{suffix_str}"
    return name


def _cache_root(context: Any) -> Path:
    """Workspace-scoped URL download cache root.

    Keeping the cache inside the workspace makes provenance obvious (the
    user can `ls` it) and means moving / archiving the workspace also moves
    the cached inputs. The legacy `manager/example_data.py` path is *not*
    reused because templates may now reference any URL, not just curated
    ones.
    """
    if context is not None:
        workspace = getattr(context, "workspace_dir", None)
        if workspace:
            return Path(workspace) / ".bionodulo" / "url_cache"
    return Path.home() / ".bionodulo" / "url_cache"


def _download_to_cache(url: str, context: Any) -> Path:
    """Download *url* into the workspace cache, returning the local path.

    Idempotent: if the destination already exists we return it as-is rather
    than re-downloading. The download writes to a `.part` file and renames
    on success so a half-completed transfer is never picked up as cached.

    URLs ending in ``.gz`` are transparently decompressed; the cached file
    has the ``.gz`` suffix stripped so downstream consumers see the actual
    payload (this matches the example-data downloader's behaviour and is
    what existing templates assume).
    """
    cache_dir = _cache_root(context)
    cache_dir.mkdir(parents=True, exist_ok=True)
    fname = _safe_filename(url)
    gunzip = fname.lower().endswith(".gz")
    if gunzip:
        fname = fname[:-3] or "download"
    dest = cache_dir / fname
    if dest.exists():
        logger.debug("URL cache hit: %s -> %s", url, dest)
        return dest

    logger.info("Downloading URL: %s -> %s", url, dest)
    req = urllib.request.Request(url, headers={"User-Agent": _HTTP_USER_AGENT})
    part_path = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT_S) as response:
            with open(part_path, "wb") as fh:
                shutil.copyfileobj(response, fh)
        if gunzip:
            with gzip.open(part_path, "rb") as gz_fh, open(dest, "wb") as out_fh:
                shutil.copyfileobj(gz_fh, out_fh)
            part_path.unlink(missing_ok=True)
        else:
            part_path.replace(dest)
    except Exception:
        part_path.unlink(missing_ok=True)
        raise
    return dest


class CopyInputNode(CommandNode):
    """Shared copy behavior for workflow input nodes."""

    SOURCE_KEYS: ClassVar[tuple[str, ...]] = ()
    OUTPUT_KEYS: ClassVar[tuple[str, ...]] = ()
    ALLOW_MULTIPLE: ClassVar[bool] = False
    ALLOW_EMPTY: ClassVar[bool] = False
    MISSING_INPUT_MESSAGE: ClassVar[str] = "No input provided"

    @classmethod
    def _source_value(cls, kwargs: dict[str, Any]) -> Any:
        for key in cls.SOURCE_KEYS:
            value = kwargs.get(key)
            if value:
                return value
        return [] if cls.ALLOW_MULTIPLE else None

    @staticmethod
    def _output_dir(context: Any, output_dir: Any) -> Path:
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        if output_dir is None:
            output_dir = "."
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    @staticmethod
    def _resolve_source(source: Any, context: Any) -> Path:
        """Resolve a source path or URL to a concrete local file.

        URLs are downloaded into a workspace-scoped cache directory on
        first use; the cached path is returned. Relative paths are resolved
        against the run workspace directory. Absolute local paths pass
        through unchanged.
        """
        if isinstance(source, str) and _looks_like_url(source):
            return _download_to_cache(source, context)
        src = Path(source)
        if not src.is_absolute() and context is not None:
            workspace = getattr(context, "workspace_dir", Path("."))
            src = (workspace / src).resolve()
        return src

    @classmethod
    def _copy_one(cls, source: Any, out_dir: Path, context: Any) -> Path:
        src = cls._resolve_source(source, context)
        if not src.exists():
            raise FileNotFoundError(f"Source not found: {src}")
        dst = out_dir / src.name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        return dst.resolve()

    @classmethod
    def _format_outputs(cls, copied: list[Path]) -> dict[str, Any]:
        if cls.ALLOW_MULTIPLE:
            return {cls.OUTPUT_KEYS[0]: [str(path) for path in copied]}
        copied_path = str(copied[0])
        return {key: copied_path for key in cls.OUTPUT_KEYS}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Copy input path(s) into the node directory and return copied paths."""
        value = self.__class__._source_value(kwargs)
        if not value and not self.__class__.ALLOW_EMPTY:
            raise ValueError(self.__class__.MISSING_INPUT_MESSAGE)

        values = value if self.__class__.ALLOW_MULTIPLE else [value]
        if isinstance(values, str):
            values = [values]

        context = kwargs.get("context")
        out_dir = self.__class__._output_dir(context, kwargs.get("output_dir"))
        copied = [self.__class__._copy_one(src, out_dir, context) for src in values]
        return {"outputs": self.__class__._format_outputs(copied)}


class InputFASTQNode(CopyInputNode):
    """Input FASTQ read files (single or paired-end)."""
    NODE_ID = "input_fastq"
    DISPLAY_NAME = "Input FASTQ"
    CATEGORY = "input"
    DESCRIPTION = "Import single-end or paired-end FASTQ read files"
    SEARCH_ALIASES = ["reads", "fastq", "input", "import reads"]
    RETURN_TYPES = ("FASTQ_LIST",)
    RETURN_NAMES = ("reads",)
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://en.wikipedia.org/wiki/FASTQ_format"
    COMMAND = ["cp", "-r", "{inputs.reads}", "{output}"]
    SOURCE_KEYS = ("reads",)
    OUTPUT_KEYS = ("reads",)
    ALLOW_MULTIPLE = True
    ALLOW_EMPTY = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {
                    "description": "Path(s) or URL(s) to FASTQ file(s). For paired-end, provide two. URLs (http/https/ftp) are downloaded to the workspace cache on first run.",
                }),
            },
            "optional": {
                "sample_name": ("STRING", {"default": "sample"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Copy reads to the node directory and return the copied paths as a list."""
        reads = kwargs.get("reads", [])
        if isinstance(reads, str):
            reads = [reads]

        # Paired-end naming validation (lenient — warns but doesn't block)
        if len(reads) == 2:
            names = [Path(r).name for r in reads]
            lower_names = [n.lower() for n in names]
            has_r1 = any(marker in n for n in lower_names for marker in ("r1", "_1", "forward", "read1"))
            has_r2 = any(marker in n for n in lower_names for marker in ("r2", "_2", "reverse", "read2"))
            if not (has_r1 and has_r2):
                logger.warning(
                    "Paired-end reads filenames don't follow typical naming (R1/R2, _1/_2, "
                    "forward/reverse, read1/read2). Got: %s",
                    names,
                )

        return await super().run(**kwargs)


class InputFASTANode(CopyInputNode):
    """Input FASTA reference or sequence file."""
    NODE_ID = "input_fasta"
    DISPLAY_NAME = "Input FASTA"
    CATEGORY = "input"
    DESCRIPTION = "Import a FASTA reference or sequence file"
    SEARCH_ALIASES = ["reference", "fasta", "genome", "input ref"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("reference",)
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://en.wikipedia.org/wiki/FASTA_format"
    COMMAND = ["cp", "-r", "{inputs.reference}", "{output}"]
    SOURCE_KEYS = ("reference", "file_path")
    OUTPUT_KEYS = ("reference",)
    MISSING_INPUT_MESSAGE = "No reference or file_path provided"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "Path or URL to FASTA file. http(s)/ftp URLs are downloaded on first use (gzip auto-decompressed)."}),
            },
            "optional": {},
            "hidden": {
                "file_path": ("STRING", {"description": "Alias for reference (backward compatibility)"}),
            },
        }


class InputFileNode(CopyInputNode):
    """Input a generic file."""
    NODE_ID = "input_file"
    DISPLAY_NAME = "Input File"
    CATEGORY = "input"
    DESCRIPTION = "Import any file into the workflow"
    SEARCH_ALIASES = ["file", "input", "import file"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("file",)
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://en.wikipedia.org/wiki/Computer_file"
    COMMAND = ["cp", "-r", "{inputs.file}", "{output}"]
    SOURCE_KEYS = ("file", "file_path")
    OUTPUT_KEYS = ("file",)
    MISSING_INPUT_MESSAGE = "No file or file_path provided"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"description": "Path or URL to a file. http(s)/ftp URLs are downloaded on first use (gzip auto-decompressed)."}),
            },
            "optional": {},
            "hidden": {
                "file_path": ("STRING", {"description": "Alias for file (backward compatibility)"}),
            },
        }


class InputDirectoryNode(CopyInputNode):
    """Input a directory."""
    NODE_ID = "input_directory"
    DISPLAY_NAME = "Input Directory"
    CATEGORY = "input"
    DESCRIPTION = "Import a directory into the workflow"
    SEARCH_ALIASES = ["directory", "folder", "input dir"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("directory",)
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://en.wikipedia.org/wiki/Directory_(computing)"
    COMMAND = ["cp", "-r", "{inputs.directory}", "{output}"]
    SOURCE_KEYS = ("directory", "dir_path")
    OUTPUT_KEYS = ("directory",)
    MISSING_INPUT_MESSAGE = "No directory or dir_path provided"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "directory": ("DIRECTORY", {"description": "Path to directory"}),
            },
            "optional": {},
            "hidden": {},
        }


class InputVCFNode(CopyInputNode):
    """Input VCF variant file."""
    NODE_ID = "input_vcf"
    DISPLAY_NAME = "Input VCF"
    CATEGORY = "input"
    DESCRIPTION = "Import a VCF variant call file"
    SEARCH_ALIASES = ["vcf", "variants", "input variants"]
    RETURN_TYPES = ("VCF", "VCF_GZ")
    RETURN_NAMES = ("vcf", "vcf_gz")
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://samtools.github.io/hts-specs/VCFv4.2.pdf"
    COMMAND = ["cp", "-r", "{inputs.vcf}", "{output}"]
    SOURCE_KEYS = ("vcf", "file_path")
    OUTPUT_KEYS = ("vcf", "vcf_gz")
    MISSING_INPUT_MESSAGE = "No vcf or file_path provided"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": (("VCF", "VCF_GZ"), {"description": "Path or URL to a VCF file. http(s)/ftp URLs are downloaded on first use."}),
            },
            "optional": {},
            "hidden": {},
        }


class InputGFFNode(CopyInputNode):
    """Input GFF/GTF annotation file."""
    NODE_ID = "input_gff"
    DISPLAY_NAME = "Input GFF/GTF"
    CATEGORY = "input"
    DESCRIPTION = "Import a GFF3 or GTF annotation file"
    SEARCH_ALIASES = ["gff", "gtf", "annotation", "input annotation"]
    RETURN_TYPES = ("GFF_GTF",)
    RETURN_NAMES = ("annotation",)
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://github.com/The-Sequence-Ontology/Specifications/blob/master/gff3.md"
    COMMAND = ["cp", "-r", "{inputs.annotation}", "{output}"]
    SOURCE_KEYS = ("annotation", "file_path")
    OUTPUT_KEYS = ("annotation",)
    MISSING_INPUT_MESSAGE = "No annotation or file_path provided"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "annotation": ("GFF_GTF", {"description": "Path or URL to a GFF3/GTF file. http(s)/ftp URLs are downloaded on first use (gzip auto-decompressed)."}),
            },
            "optional": {},
            "hidden": {
                "file_path": ("STRING", {"description": "Alias for annotation (backward compatibility)"}),
            },
        }


class SampleSheetNode(CopyInputNode):
    """Input sample sheet / metadata CSV."""
    NODE_ID = "input_sample_sheet"
    DISPLAY_NAME = "Sample Sheet"
    CATEGORY = "input"
    DESCRIPTION = "Import a sample sheet CSV with sample metadata"
    SEARCH_ALIASES = ["sample sheet", "metadata", "samples", "csv"]
    RETURN_TYPES = ("SAMPLE_SHEET",)
    RETURN_NAMES = ("sample_sheet",)
    REQUIRES_EXTERNAL_TOOLS = False
    COMMAND = ["cp", "-r", "{inputs.sample_sheet}", "{output}"]
    SOURCE_KEYS = ("sample_sheet", "file_path")
    OUTPUT_KEYS = ("sample_sheet",)
    MISSING_INPUT_MESSAGE = "No sample_sheet or file_path provided"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sample_sheet": ("SAMPLE_SHEET", {
                    "description": "Path or URL to sample sheet CSV (columns: sample, fastq_1, fastq_2, condition). http(s) URLs are downloaded on first use.",
                }),
            },
            "optional": {},
            "hidden": {},
        }
