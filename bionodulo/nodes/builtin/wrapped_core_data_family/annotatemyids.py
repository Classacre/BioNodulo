"""Focused annotatemyids node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class AnnotateMyIDsNode(CommandNode):
    """Annotate gene identifiers with Bioconductor organism annotation databases."""

    NODE_ID = "annotatemyids"
    DISPLAY_NAME = "annotateMyIDs"
    REQUIRED_CONDA_PACKAGES = [
        "bioconductor-org.hs.eg.db",
        "bioconductor-org.mm.eg.db",
        "bioconductor-org.dm.eg.db",
        "bioconductor-org.dr.eg.db",
        "bioconductor-org.rn.eg.db",
        "bioconductor-org.at.tair.db",
        "bioconductor-org.gg.eg.db",
        "bioconductor-org.bt.eg.db",
    ]
    CATEGORY = "annotation"
    DESCRIPTION = "Annotate a generic set of gene identifiers using Bioconductor organism annotation databases."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "annotateMyIDs",
        "annotatemyids",
        "AnnotationDbi",
        "Bioconductor",
        "org.Hs.eg.db",
        "gene identifier annotation",
        "Ensembl to Entrez",
        "gene symbols",
        "GO annotation",
        "KEGG annotation",
    ]
    RETURN_TYPES = ("TSV", "TXT")
    RETURN_NAMES = ("out_tab", "out_rscript")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://github.com/markdunning/galaxy-annotateMyIDs"
    CITATION_DOIS = ["10.18129/B9.bioc.AnnotationDbi"]
    CITATION_URLS = [
        "https://doi.org/10.18129/B9.bioc.AnnotationDbi",
        "https://github.com/markdunning/galaxy-annotateMyIDs",
    ]
    CITATION_TEXT = (
        "AnnotationDbi provides the Bioconductor interface used to query organism annotation packages; "
        "annotateMyIDs is a Galaxy wrapper by Mark Dunning for generic identifier annotation."
    )
    VERSION = "3.18.0+galaxy0"
    SHELL = True

    ORGANISMS = ["Hs", "Mm", "Rn", "Dm", "Dr", "At", "Gg", "Bt"]
    ID_TYPES = [
        "ENSEMBL",
        "ENSEMBLPROT",
        "ENSEMBLTRANS",
        "ENTREZID",
        "FLYBASE",
        "GO",
        "PATH",
        "MGI",
        "REFSEQ",
        "SYMBOL",
        "ZFIN",
    ]
    OUTPUT_COLUMNS = [
        "ALIAS",
        "ENSEMBL",
        "ENTREZID",
        "EVIDENCE",
        "SYMBOL",
        "GENENAME",
        "REFSEQ",
        "GO",
        "ONTOLOGY",
        "PATH",
    ]
    DEFAULT_OUTPUT_COLUMNS = ["ENSEMBL", "ENTREZID", "SYMBOL", "GENENAME"]

    @classmethod
    def _organism(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("organism", "Hs") or "Hs")

    @classmethod
    def _id_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("id_type", "ENSEMBL") or "ENSEMBL")

    @classmethod
    def _bool_r(cls, inputs: dict[str, Any], key: str, default: bool = False) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no", ""} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _output_cols(cls, inputs: dict[str, Any]) -> list[str]:
        values = _as_list(inputs.get("output_cols"))
        return values or list(cls.DEFAULT_OUTPUT_COLUMNS)

    @classmethod
    def _script_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/annotatemyids.R"

    @classmethod
    def _out_tab_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out_tab.tsv"

    @classmethod
    def _out_rscript_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out_rscript.txt"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        id_type = cls._id_type(inputs)
        organism = cls._organism(inputs)
        output_cols = ",".join(cls._output_cols(inputs))
        return "\n".join(
            [
                'options( show.error.messages=F, error = function () { cat( geterrmessage(), file=stderr() ); q( "no", 1, F ) } )',
                "",
                'loc <- Sys.setlocale("LC_MESSAGES", "en_US.UTF-8")',
                "",
                f'id_type <- "{id_type}"',
                f'organism <- "{organism}"',
                f'output_cols <- "{output_cols}"',
                f"file_has_header <- {cls._bool_r(inputs, 'file_has_header')}",
                f"remove_dups <- {cls._bool_r(inputs, 'remove_dups')}",
                "",
                f"input <- read.table({str(inputs.get('id_file', ''))!r}, header=file_has_header, sep=\"\\t\", quote=\"\")",
                "ids <- as.character(input[, 1])",
                "",
                'if(organism == "Hs"){',
                "    suppressPackageStartupMessages(library(org.Hs.eg.db))",
                "    db <- org.Hs.eg.db",
                '} else if (organism == "Mm"){',
                "    suppressPackageStartupMessages(library(org.Mm.eg.db))",
                "    db <- org.Mm.eg.db",
                '} else if (organism == "Dm"){',
                "    suppressPackageStartupMessages(library(org.Dm.eg.db))",
                "    db <- org.Dm.eg.db",
                '} else if (organism == "Dr"){',
                "    suppressPackageStartupMessages(library(org.Dr.eg.db))",
                "    db <- org.Dr.eg.db",
                '} else if (organism == "Rn"){',
                "    suppressPackageStartupMessages(library(org.Rn.eg.db))",
                "    db <- org.Rn.eg.db",
                '} else if (organism == "At"){',
                "    suppressPackageStartupMessages(library(org.At.tair.db))",
                "    db <- org.At.tair.db",
                '} else if (organism == "Gg"){',
                "    suppressPackageStartupMessages(library(org.Gg.eg.db))",
                "    db <- org.Gg.eg.db",
                '} else if (organism == "Bt"){',
                "    suppressPackageStartupMessages(library(org.Bt.eg.db))",
                "    db <- org.Bt.eg.db",
                "} else {",
                '    cat(paste("Organism type not supported", organism))',
                "}",
                "",
                'cols <- unlist(strsplit(output_cols, ","))',
                "result <- select(db, keys=ids, keytype=id_type, columns=cols)",
                "",
                "if(remove_dups) {",
                f"    result <- result[!duplicated(result${id_type}),]",
                "}",
                "",
                f"write.table(result, file={cls._out_tab_path(inputs)!r}, sep=\"\\t\", row.names=FALSE, quote=FALSE)",
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = cls._script_path(inputs)
        run_script = f"Rscript {shlex.quote(script_path)}"
        if cls._bool_r(inputs, "rscriptOpt") == "TRUE":
            run_script = f"cp {shlex.quote(script_path)} {shlex.quote(cls._out_rscript_path(inputs))} && {run_script}"
        commands = [
            f"mkdir -p {shlex.quote(out)}",
            f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs)}\nRSCRIPT\n{run_script}",
        ]
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "out_tab.tsv"]
        if cls._bool_r(inputs, "rscriptOpt") == "TRUE":
            outputs.append(out / "out_rscript.txt")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("id_file", "")).strip():
            return "id_file is required"
        organism = cls._organism(inputs)
        if organism not in cls.ORGANISMS:
            return f"organism must be one of: {', '.join(cls.ORGANISMS)}"
        id_type = cls._id_type(inputs)
        if id_type not in cls.ID_TYPES:
            return f"id_type must be one of: {', '.join(cls.ID_TYPES)}"
        if "output_cols" in inputs and not _as_list(inputs.get("output_cols")):
            return "output_cols is required"
        output_cols = cls._output_cols(inputs)
        if any(col not in cls.OUTPUT_COLUMNS for col in output_cols):
            return f"output_cols entries must be one of: {', '.join(cls.OUTPUT_COLUMNS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "id_file": ("TSV", {"description": "Tabular file whose first column contains identifiers to annotate"}),
            },
            "optional": {
                "file_has_header": ("BOOLEAN", {"default": False}),
                "organism": ("STRING", {"default": "Hs", "options": cls.ORGANISMS}),
                "id_type": ("STRING", {"default": "ENSEMBL", "options": cls.ID_TYPES}),
                "output_cols": (
                    "STRING",
                    {
                        "default": list(cls.DEFAULT_OUTPUT_COLUMNS),
                        "options": cls.OUTPUT_COLUMNS,
                        "multiple": True,
                        "display": "checkboxes",
                    },
                ),
                "remove_dups": ("BOOLEAN", {"default": False}),
                "rscriptOpt": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(AnnotateMyIDsNode)

__all__ = ['AnnotateMyIDsNode']
