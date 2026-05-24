"""Input nodes for BioNodulo workflows.

Provides nodes for importing bioinformatics data files into workflows.
These nodes serve as workflow entry points for various file formats.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode

logger = logging.getLogger(__name__)


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
                    "description": "Path(s) to FASTQ file(s). For paired-end, provide two files.",
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
                "reference": ("FASTA", {"description": "Path to FASTA file"}),
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
                "file": ("FILE", {"description": "Path to file"}),
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
                "vcf": (("VCF", "VCF_GZ"), {"description": "Path to VCF file"}),
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
                "annotation": ("GFF_GTF", {"description": "Path to GFF3 or GTF file"}),
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
                    "description": "Path to sample sheet CSV (columns: sample, fastq_1, fastq_2, condition)",
                }),
            },
            "optional": {},
            "hidden": {},
        }
