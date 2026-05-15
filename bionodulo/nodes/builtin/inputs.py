"""Input nodes for BioNodulo workflows.

Provides nodes for importing bioinformatics data files into workflows.
These nodes serve as workflow entry points for various file formats.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Optional, Union

from bionodulo.nodes.command_node import CommandNode


class InputFASTQNode(CommandNode):
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
        import shutil

        reads = kwargs.get("reads", [])
        if isinstance(reads, str):
            reads = [reads]
        context = kwargs.get("context")
        output_dir = kwargs.get("output_dir")

        # Resolve relative paths against workspace root
        if context is not None:
            workspace = getattr(context, "workspace_dir", Path("."))
            resolved = []
            for r in reads:
                p = Path(r)
                if not p.is_absolute():
                    p = (workspace / p).resolve()
                resolved.append(str(p))
            reads = resolved

        # Use node_dir from context when output_dir is not explicitly provided
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        if output_dir is None:
            output_dir = "."

        # Copy files to the output directory so the run is self-contained
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        copied = []
        for src in reads:
            src_path = Path(src)
            dst = out_dir / src_path.name
            if src_path.is_dir():
                shutil.copytree(src_path, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src_path, dst)
            copied.append(str(dst.resolve()))

        return {"outputs": {"reads": copied}}


class InputFASTANode(CommandNode):
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

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": ("FASTA", {"description": "Path to FASTA file"}),
            },
            "optional": {},
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Copy FASTA to node directory, supporting file_path alias."""
        import shutil
        reference = kwargs.get("reference") or kwargs.get("file_path")
        if not reference:
            raise ValueError("No reference or file_path provided")
        context = kwargs.get("context")
        output_dir = kwargs.get("output_dir")
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        if output_dir is None:
            output_dir = "."
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        src = Path(reference)
        if not src.is_absolute() and context is not None:
            workspace = getattr(context, "workspace_dir", Path("."))
            src = (workspace / src).resolve()
        dst = out_dir / src.name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        return {"outputs": {"reference": str(dst.resolve())}}


class InputFileNode(CommandNode):
    """Input a generic file."""
    NODE_ID = "input_file"
    DISPLAY_NAME = "Input File"
    CATEGORY = "input"
    DESCRIPTION = "Import any file into the workflow"
    SEARCH_ALIASES = ["file", "input", "import file"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("file",)
    REQUIRES_EXTERNAL_TOOLS = False
    COMMAND = ["cp", "-r", "{inputs.file}", "{output}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"description": "Path to file"}),
            },
            "optional": {},
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Copy file to node directory, supporting file_path alias."""
        import shutil
        file_path = kwargs.get("file") or kwargs.get("file_path")
        if not file_path:
            raise ValueError("No file or file_path provided")
        context = kwargs.get("context")
        output_dir = kwargs.get("output_dir")
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        if output_dir is None:
            output_dir = "."
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        src = Path(file_path)
        if not src.is_absolute() and context is not None:
            workspace = getattr(context, "workspace_dir", Path("."))
            src = (workspace / src).resolve()
        dst = out_dir / src.name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        return {"outputs": {"file": str(dst.resolve())}}


class InputDirectoryNode(CommandNode):
    """Input a directory."""
    NODE_ID = "input_directory"
    DISPLAY_NAME = "Input Directory"
    CATEGORY = "input"
    DESCRIPTION = "Import a directory into the workflow"
    SEARCH_ALIASES = ["directory", "folder", "input dir"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("directory",)
    REQUIRES_EXTERNAL_TOOLS = False
    COMMAND = ["cp", "-r", "{inputs.directory}", "{output}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "directory": ("DIRECTORY", {"description": "Path to directory"}),
            },
            "optional": {},
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Copy directory to node directory."""
        import shutil
        directory = kwargs.get("directory") or kwargs.get("dir_path")
        if not directory:
            raise ValueError("No directory or dir_path provided")
        context = kwargs.get("context")
        output_dir = kwargs.get("output_dir")
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        if output_dir is None:
            output_dir = "."
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        src = Path(directory)
        if not src.is_absolute() and context is not None:
            workspace = getattr(context, "workspace_dir", Path("."))
            src = (workspace / src).resolve()
        dst = out_dir / src.name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        return {"outputs": {"directory": str(dst.resolve())}}


class InputVCFNode(CommandNode):
    """Input VCF variant file."""
    NODE_ID = "input_vcf"
    DISPLAY_NAME = "Input VCF"
    CATEGORY = "input"
    DESCRIPTION = "Import a VCF variant call file"
    SEARCH_ALIASES = ["vcf", "variants", "input variants"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("vcf",)
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = "https://samtools.github.io/hts-specs/VCFv4.2.pdf"
    COMMAND = ["cp", "-r", "{inputs.vcf}", "{output}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF", {"description": "Path to VCF file"}),
            },
            "optional": {},
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Copy VCF to node directory, supporting file_path alias."""
        import shutil
        vcf = kwargs.get("vcf") or kwargs.get("file_path")
        if not vcf:
            raise ValueError("No vcf or file_path provided")
        context = kwargs.get("context")
        output_dir = kwargs.get("output_dir")
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        if output_dir is None:
            output_dir = "."
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        src = Path(vcf)
        if not src.is_absolute() and context is not None:
            workspace = getattr(context, "workspace_dir", Path("."))
            src = (workspace / src).resolve()
        dst = out_dir / src.name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        return {"outputs": {"vcf": str(dst.resolve())}}


class InputGFFNode(CommandNode):
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

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "annotation": ("GFF_GTF", {"description": "Path to GFF3 or GTF file"}),
            },
            "optional": {},
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Copy GFF/GTF to node directory, supporting file_path alias."""
        import shutil
        annotation = kwargs.get("annotation") or kwargs.get("file_path")
        if not annotation:
            raise ValueError("No annotation or file_path provided")
        context = kwargs.get("context")
        output_dir = kwargs.get("output_dir")
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        if output_dir is None:
            output_dir = "."
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        src = Path(annotation)
        if not src.is_absolute() and context is not None:
            workspace = getattr(context, "workspace_dir", Path("."))
            src = (workspace / src).resolve()
        dst = out_dir / src.name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        return {"outputs": {"annotation": str(dst.resolve())}}


class SampleSheetNode(CommandNode):
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

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Copy sample sheet to node directory."""
        import shutil
        sample_sheet = kwargs.get("sample_sheet") or kwargs.get("file_path")
        if not sample_sheet:
            raise ValueError("No sample_sheet or file_path provided")
        context = kwargs.get("context")
        output_dir = kwargs.get("output_dir")
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        if output_dir is None:
            output_dir = "."
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        src = Path(sample_sheet)
        if not src.is_absolute() and context is not None:
            workspace = getattr(context, "workspace_dir", Path("."))
            src = (workspace / src).resolve()
        dst = out_dir / src.name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        return {"outputs": {"sample_sheet": str(dst.resolve())}}
