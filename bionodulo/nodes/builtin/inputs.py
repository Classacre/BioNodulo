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
