from __future__ import annotations

from typing import Any

from bionodulo.nodes.base import BaseNode


class InputFASTQNode(BaseNode):
    NODE_ID = "input_fastq"
    DISPLAY_NAME = "Input FASTQ"
    CATEGORY = "Input"
    DESCRIPTION = "Declare one or more FASTQ or FASTQ.GZ files."
    SEARCH_ALIASES = ["fastq", "reads", "sequencing reads", "input reads"]
    RETURN_TYPES = ("FASTQ_LIST",)
    RETURN_NAMES = ("reads",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "files": ("FASTQ_LIST", {"description": "FASTQ/FASTQ.GZ file paths", "default": ["examples/data/sample_R1.fastq.gz", "examples/data/sample_R2.fastq.gz"]})
            },
            "optional": {},
            "hidden": {},
        }

    def run(self, context: Any = None, **kwargs: Any) -> dict[str, Any]:
        return {"reads": kwargs.get("files", [])}

    @classmethod
    def PLAN_OUTPUTS(cls, node_dir: Any, params: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        return {"reads": params.get("files", [])}


class InputFASTANode(BaseNode):
    NODE_ID = "input_fasta"
    DISPLAY_NAME = "Input FASTA"
    CATEGORY = "Input"
    DESCRIPTION = "Declare a reference FASTA file."
    SEARCH_ALIASES = ["fasta", "reference", "genome"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("fasta",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {"file": ("FASTA", {"description": "FASTA path", "default": "reference.fa"})}, "optional": {}, "hidden": {}}

    def run(self, context: Any = None, **kwargs: Any) -> dict[str, Any]:
        return {"fasta": kwargs.get("file")}

    @classmethod
    def PLAN_OUTPUTS(cls, node_dir: Any, params: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        return {"fasta": params.get("file")}


class InputFileNode(BaseNode):
    NODE_ID = "input_file"
    DISPLAY_NAME = "Input File"
    CATEGORY = "Input"
    DESCRIPTION = "Declare a generic input file."
    SEARCH_ALIASES = ["file", "input"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("file",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {"file": ("FILE", {"default": "data/file.txt"})}, "optional": {}, "hidden": {}}

    def run(self, context: Any = None, **kwargs: Any) -> dict[str, Any]:
        return {"file": kwargs.get("file")}

    @classmethod
    def PLAN_OUTPUTS(cls, node_dir: Any, params: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        return {"file": params.get("file")}


class InputDirectoryNode(BaseNode):
    NODE_ID = "input_directory"
    DISPLAY_NAME = "Input Directory"
    CATEGORY = "Input"
    DESCRIPTION = "Declare an input directory."
    SEARCH_ALIASES = ["directory", "folder", "input dir"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("directory",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {"directory": ("DIRECTORY", {"default": "data"})}, "optional": {}, "hidden": {}}

    def run(self, context: Any = None, **kwargs: Any) -> dict[str, Any]:
        return {"directory": kwargs.get("directory")}

    @classmethod
    def PLAN_OUTPUTS(cls, node_dir: Any, params: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        return {"directory": params.get("directory")}


class SampleSheetNode(BaseNode):
    NODE_ID = "sample_sheet"
    DISPLAY_NAME = "Sample Sheet"
    CATEGORY = "Input"
    DESCRIPTION = "Declare a CSV/TSV sample sheet."
    SEARCH_ALIASES = ["samples", "metadata", "manifest"]
    RETURN_TYPES = ("SAMPLE_SHEET",)
    RETURN_NAMES = ("sample_sheet",)

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {"required": {"file": ("SAMPLE_SHEET", {"default": "samples.csv"})}, "optional": {}, "hidden": {}}

    def run(self, context: Any = None, **kwargs: Any) -> dict[str, Any]:
        return {"sample_sheet": kwargs.get("file")}

    @classmethod
    def PLAN_OUTPUTS(cls, node_dir: Any, params: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        return {"sample_sheet": params.get("file")}
