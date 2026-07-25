"""Focused ampvis2 import, export, merge, and metadata nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_amplicon_trimming_family.evidence import pin_contract

class Ampvis2ExportFastaNode(CommandNode):
    """Export sequences from ampvis2 datasets as FASTA."""

    LEGACY_NODE_ID = "ampvis2_export_fasta"
    DISPLAY_NAME = "ampvis2 export fasta"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Export sequences from an ampvis2 RDS dataset as FASTA."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 export fasta",
        "amp_export_fasta",
        "export FASTA",
        "amplicon sequences",
        "taxonomy FASTA headers",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_export_fasta.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.fasta"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        return "\n".join(
            [
                "library(ampvis2, quietly = TRUE)",
                f'data <- readRDS("{inputs.get("data", "")}")',
                f'amp_export_fasta(data, filename = "{cls._output_path(inputs)}", tax = {cls._r_bool(inputs.get("tax"), False)})',
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/export_fasta.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.fasta"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data": ("FILE", {"description": "Ampvis2 RDS dataset containing sequence information"}),
            },
            "optional": {
                "tax": ("BOOLEAN", {"default": False, "description": "Append taxonomic strings to FASTA headers"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2ExportOtuNode(CommandNode):
    """Export OTU, taxonomy, metadata, and phyloseq artifacts from ampvis2."""

    LEGACY_NODE_ID = "ampvis2_export_otu"
    DISPLAY_NAME = "ampvis2 export otu"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Export OTU, taxonomy, metadata, and phyloseq tables from an ampvis2 object."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 export otu",
        "amp_export_otutable",
        "OTU table export",
        "taxonomy mapping",
        "metadata mapping",
        "phyloseq object",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV", "TSV", "FILE")
    RETURN_NAMES = ("otu_long", "otu_short", "tax", "meta", "phyloseq")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_export_otutable.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True
    RUN_IN_NODE_OUTPUT_DIR = True

    OUTPUT_OPTIONS = ["otu_long", "otu_short", "tax", "meta", "phyloseq"]
    DEFAULT_OUTPUTS = ["otu_short", "tax", "meta"]
    OUTPUT_FILES = {
        "otu_long": "otu_long.tsv",
        "otu_short": "otu_short.tsv",
        "tax": "tax.tsv",
        "meta": "meta.tsv",
        "phyloseq": "phyloseq.rds",
    }

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        outputs = _as_list(inputs.get("output_selection"))
        return outputs if outputs else cls.DEFAULT_OUTPUTS.copy()

    @classmethod
    def _path(cls, inputs: dict[str, Any], output_name: str) -> str:
        return f"{_out(inputs)}/{cls.OUTPUT_FILES[output_name]}"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        norm = cls._r_bool(inputs.get("norm"), False)
        otu_source = "data_norm$abund" if norm == "TRUE" else "data$abund"
        norm_lines = ["data_norm <- normaliseTo100(data)"] if norm == "TRUE" else []
        return "\n".join(
            [
                "library(ampvis2, quietly = TRUE)",
                "library(phyloseq)",
                "library(tibble)",
                "",
                f'data <- readRDS("{inputs.get("data", "")}")',
                "",
                'amp_export_otutable(data, filename = "tmp_otu", sep = "\\t", extension = "tsv", normalise = '
                f"{norm})",
                "",
                "tax_table <- data$tax",
                "tax_table <- tax_table[,c(8,(ncol(tax_table)-6):(ncol(tax_table) - 1))]",
                f'write.table(tax_table, "{cls._path(inputs, "tax")}", sep = "\\t", row.names=FALSE, quote = FALSE)',
                "",
                *norm_lines,
                f"otu_table <- {otu_source}",
                "otu_table <- cbind(OTU = rownames(otu_table), otu_table)",
                f'write.table(otu_table, "{cls._path(inputs, "otu_short")}", sep = "\\t", row.names=FALSE, quote = FALSE)',
                "",
                "meta_data = data$metadata",
                f'write.table(meta_data, "{cls._path(inputs, "meta")}", sep = "\\t", row.names = FALSE, quote = FALSE)',
                "",
                "otu_table <- apply(otu_table, 2, as.numeric)",
                "meta_data[] <- lapply(meta_data, as.character)",
                "OTU <- otu_table(otu_table, taxa_are_rows = TRUE)",
                "TAX <- tax_table(tax_table)",
                "META <- sample_data(meta_data)",
                'colnames(TAX) <- c("Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species")',
                "physeq <- phyloseq(OTU, TAX, META)",
                f'saveRDS(physeq, "{cls._path(inputs, "phyloseq")}")',
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/export_otu.R"
        commands = [
            f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs)}\nRSCRIPT",
            _shell_join(["Rscript", script_path]),
            _shell_join(["mv", "tmp_otu.tsv", cls._path(inputs, "otu_long")]),
        ]
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILES[output] for output in cls._selected_outputs(inputs)]

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        reverse = {filename: name for name, filename in cls.OUTPUT_FILES.items()}
        return {reverse[path.name]: path for path in planned_paths}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        outputs = _as_list(inputs.get("output_selection"))
        if "output_selection" in inputs and not outputs:
            return "at least one output_selection value is required"
        unsupported_outputs = [output for output in outputs if output not in cls.OUTPUT_OPTIONS]
        if unsupported_outputs:
            return f"output_selection contains unsupported values: {', '.join(unsupported_outputs)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data": ("FILE", {"description": "Ampvis2 RDS dataset"}),
            },
            "optional": {
                "norm": ("BOOLEAN", {"default": False, "description": "Transform OTU read counts to percent per sample"}),
                "output_selection": (
                    "STRING_LIST",
                    {
                        "default": cls.DEFAULT_OUTPUTS.copy(),
                        "multiple": True,
                        "options": cls.OUTPUT_OPTIONS,
                        "description": "Output files to emit",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2LoadNode(CommandNode):
    """Load OTU, ASV, BIOM, or phyloseq data into an ampvis2 object."""

    LEGACY_NODE_ID = "ampvis2_load"
    DISPLAY_NAME = "ampvis2 load"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Load OTU, ASV, BIOM, or phyloseq data into an ampvis2 RDS object."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 load",
        "amp_load",
        "OTU table",
        "ASV table",
        "BIOM",
        "phyloseq",
        "metadata list",
        "taxonomy list",
    ]
    RETURN_TYPES = ("FILE", "TSV", "TSV")
    RETURN_NAMES = ("ampvis", "metadata_list_out", "taxonomy_list_out")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_load.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True
    RUN_IN_NODE_OUTPUT_DIR = True

    OTUTABLE_TYPES = ["tabular", "dada2_sequencetable", "biom1", "biom2", "phyloseq"]
    WRITE_LIST_OPTIONS = ["tax", "metadata"]
    DEFAULT_WRITE_LISTS = ["tax", "metadata"]
    LIST_OUTPUT_FILES = {
        "tax": "taxonomy_list.tsv",
        "metadata": "metadata_list.tsv",
    }

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _otutable_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("otutable_type", "tabular") or "tabular")

    @classmethod
    def _selected_write_lists(cls, inputs: dict[str, Any]) -> list[str]:
        if "write_lists" in inputs:
            return _as_list(inputs.get("write_lists"))
        return cls.DEFAULT_WRITE_LISTS.copy()

    @classmethod
    def _staging_commands(cls, inputs: dict[str, Any]) -> list[str]:
        otutable_type = cls._otutable_type(inputs)
        commands = []
        if otutable_type in {"biom1", "biom2"}:
            commands.append(_shell_join(["ln", "-s", str(inputs.get("otutable", "")), "otutable.biom"]))
        elif otutable_type != "phyloseq":
            if inputs.get("asv_otu_col_empty"):
                commands.append(
                    _shell_join(["sed", "-e", "1 s/^\\t/ASV\\t/", str(inputs.get("otutable", "")), ">", "otutable.tsv"])
                )
            else:
                commands.append(_shell_join(["ln", "-s", str(inputs.get("otutable", "")), "otutable.tsv"]))
        if str(inputs.get("taxonomy", "")).strip():
            if inputs.get("asv_otu_col_empty"):
                commands.append(
                    _shell_join(["sed", "-e", "1 s/^\\t/ASV\\t/", str(inputs.get("taxonomy", "")), ">", "taxonomy.tsv"])
                )
            else:
                commands.append(_shell_join(["ln", "-s", str(inputs.get("taxonomy", "")), "taxonomy.tsv"]))
        return commands

    @classmethod
    def _metadata_lines(cls, inputs: dict[str, Any]) -> list[str]:
        metadata = str(inputs.get("metadata", "")).strip()
        if not metadata:
            return []
        return [
            f'metadata <- read.table("{metadata}", header = TRUE, sep = "\\t", colClasses = "character", check.names=F)',
            'if(colnames(metadata)[1] == ""){',
            '    colnames(metadata)[1] <- "SampleID"',
            "}",
            'if(exists("SampleID", where = metadata)){',
            '    rownames(metadata) <- metadata[["SampleID"]]',
            "}else{",
            "    rownames(metadata) <- metadata[[1]]",
            "}",
            "",
        ]

    @classmethod
    def _amp_load_otutable_line(cls, inputs: dict[str, Any]) -> str:
        otutable_type = cls._otutable_type(inputs)
        if otutable_type == "phyloseq":
            return "    otutable = otutable,"
        if otutable_type in {"biom1", "biom2"}:
            return '    otutable = "otutable.biom",'
        return '    otutable = "otutable.tsv",'

    @classmethod
    def _amp_load_lines(cls, inputs: dict[str, Any]) -> list[str]:
        lines = [
            "data <- amp_load(",
            cls._amp_load_otutable_line(inputs),
        ]
        if str(inputs.get("metadata", "")).strip():
            lines.append("    metadata = metadata,")
        if str(inputs.get("taxonomy", "")).strip():
            lines.append('    taxonomy = "taxonomy.tsv",')
        if str(inputs.get("fasta", "")).strip():
            lines.append(f'    fasta = "{inputs.get("fasta")}",')
        if str(inputs.get("tree", "")).strip():
            lines.append(f'    tree = "{inputs.get("tree")}",')
        if str(inputs.get("otutable_OTUcolname", "")).strip():
            lines.append(f'    otutable_OTUcolname = c("{inputs.get("otutable_OTUcolname")}"),')
        if str(inputs.get("taxonomy_OTUcolname", "")).strip():
            lines.append(f'    taxonomy_OTUcolname = c("{inputs.get("taxonomy_OTUcolname")}"),')
        lines.extend(
            [
                f"    pruneSingletons = {cls._r_bool(inputs.get('pruneSingletons'), False)}",
                ")",
            ]
        )
        return lines

    @classmethod
    def _asv_sequence_lines(cls, inputs: dict[str, Any]) -> list[str]:
        if not inputs.get("asv_sequences"):
            return []
        return [
            "",
            "library(ape, quietly = TRUE)",
            "",
            'seq <- as.DNAbin(strsplit(rownames(data$abund), ""))',
            'names(seq) <- paste0("ASV", seq_along(seq))',
            "data$refseq <- seq",
            "data <- matchOTUs(data, seq)",
        ]

    @classmethod
    def _metadata_list_lines(cls, out: str) -> list[str]:
        return [
            "classes <- sapply(data$metadata, class)",
            'data$metadata[is.na(data$metadata)] <- "NA"',
            "for(name in names(data$metadata)){",
            '    if(classes[[name]] == "character" && all(data$metadata[[name]] == rownames(data$metadata))){',
            "        sample_names <- TRUE;",
            "    }else{",
            "        sample_names <- FALSE;",
            "    }",
            "    for(m in unique(data$metadata[[name]])){",
            f'        write(paste(name, m, sample_names, classes[[name]], sep="\\t"), file="{out}/metadata_list.tsv", append=T);',
            "    }",
            "}",
        ]

    @classmethod
    def _taxonomy_list_lines(cls, out: str) -> list[str]:
        return [
            "for(level in colnames(data$tax)){",
            "    for(u in unique(data$tax[level])){",
            f'        write(paste(u, level, sep="\\t"), file="{out}/taxonomy_list.tsv", append=T)',
            "    }",
            "}",
        ]

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        lines = [
            "library(ampvis2, quietly = TRUE)",
            "library(readr, quietly = TRUE)",
            "",
            *cls._metadata_lines(inputs),
        ]
        if cls._otutable_type(inputs) == "phyloseq":
            lines.extend(
                [
                    f'otutable <- readRDS("{inputs.get("otutable", "")}")',
                    "print(class(otutable))",
                    "",
                ]
            )
        lines.extend(cls._amp_load_lines(inputs))
        lines.extend(cls._asv_sequence_lines(inputs))
        if cls._r_bool(inputs.get("guess_column_types"), True) == "TRUE":
            lines.extend(
                [
                    "",
                    "data$metadata <- readr::type_convert(data$metadata, guess_integer=TRUE)",
                ]
            )
        lines.extend(
            [
                "",
                f'saveRDS(data, "{out}/ampvis.rds")',
            ]
        )
        for list_name in cls._selected_write_lists(inputs):
            if list_name == "metadata":
                lines.extend(["", *cls._metadata_list_lines(out)])
            elif list_name == "tax":
                lines.extend(["", *cls._taxonomy_list_lines(out)])
        lines.extend(["", "data"])
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/load.R"
        commands = [
            *cls._staging_commands(inputs),
            f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT",
            _shell_join(["Rscript", script_path]),
        ]
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "ampvis.rds"]
        selected_lists = set(cls._selected_write_lists(inputs))
        outputs.extend(
            out / cls.LIST_OUTPUT_FILES[list_name]
            for list_name in ("metadata", "tax")
            if list_name in selected_lists
        )
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        names = {
            "ampvis.rds": "ampvis",
            "metadata_list.tsv": "metadata_list_out",
            "taxonomy_list.tsv": "taxonomy_list_out",
        }
        return {names[path.name]: path for path in planned_paths}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("otutable", "")).strip():
            return "otutable is required"
        otutable_type = cls._otutable_type(inputs)
        if otutable_type not in cls.OTUTABLE_TYPES:
            return f"otutable_type must be one of: {', '.join(cls.OTUTABLE_TYPES)}"
        unsupported_lists = [name for name in _as_list(inputs.get("write_lists")) if name not in cls.WRITE_LIST_OPTIONS]
        if unsupported_lists:
            return f"write_lists contains unsupported values: {', '.join(unsupported_lists)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "otutable": ("FILE", {"description": "OTU, ASV, BIOM, or phyloseq dataset"}),
            },
            "optional": {
                "otutable_type": (
                    "STRING",
                    {
                        "default": "tabular",
                        "options": cls.OTUTABLE_TYPES,
                        "description": "Galaxy datatype of the OTU table input",
                    },
                ),
                "asv_sequences": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat ASV identifiers as ASV sequences and store them in the ampvis2 object"},
                ),
                "metadata": ("TSV", {"default": "", "description": "Optional sample metadata table"}),
                "guess_column_types": (
                    "BOOLEAN",
                    {"default": True, "description": "Guess metadata column types with readr::type_convert"},
                ),
                "taxonomy": ("TSV", {"default": "", "description": "Optional taxonomy table"}),
                "fasta": ("FASTA", {"default": "", "description": "Optional FASTA file containing OTU or ASV sequences"}),
                "tree": ("FILE", {"default": "", "description": "Optional phylogenetic tree in Newick format"}),
                "pruneSingletons": ("BOOLEAN", {"default": False, "description": "Remove singleton OTUs"}),
                "write_lists": (
                    "STRING_LIST",
                    {
                        "default": cls.DEFAULT_WRITE_LISTS.copy(),
                        "multiple": True,
                        "options": cls.WRITE_LIST_OPTIONS,
                        "description": "Auxiliary metadata and taxonomy list outputs for downstream ampvis2 tools",
                    },
                ),
                "asv_otu_col_empty": (
                    "BOOLEAN",
                    {"default": False, "description": "Replace an empty OTU/ASV column header with ASV before loading"},
                ),
                "otutable_OTUcolname": (
                    "STRING",
                    {"default": "", "description": "OTU column name in the OTU table"},
                ),
                "taxonomy_OTUcolname": (
                    "STRING",
                    {"default": "", "description": "OTU column name in the taxonomy table"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2MergeAmpvis2Node(CommandNode):
    """Merge multiple ampvis2 RDS datasets into one ampvis2 object."""

    LEGACY_NODE_ID = "ampvis2_merge_ampvis2"
    DISPLAY_NAME = "ampvis2 merge ampvis2 data sets"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Merge multiple ampvis2 RDS datasets into a single ampvis2 object."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 merge ampvis2 data sets",
        "amp_merge_ampvis2",
        "merge ampvis2 objects",
        "RDS merge",
        "by reference sequence",
        "DNA reference sequences",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_merge_ampvis2.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _data_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("data"))

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.rds"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        data_lines = [f'    readRDS("{data_file}"),' for data_file in cls._data_files(inputs)]
        return "\n".join(
            [
                "library(ampvis2, quietly = TRUE)",
                "merged <- amp_merge_ampvis2(",
                *data_lines,
                f"    by_refseq = {cls._r_bool(inputs.get('by_refseq'), True)}",
                ")",
                f'saveRDS(merged, "{cls._output_path(inputs)}")',
                "merged",
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/merge_ampvis2.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.rds"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._data_files(inputs):
            return "at least one ampvis2 data set is required"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data": (
                    "FILE",
                    {"multiple": True, "description": "Ampvis2 RDS datasets generated with ampvis2: load"},
                ),
            },
            "optional": {
                "by_refseq": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "description": "Merge by exact DNA reference sequence matches and use those sequences as output names",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2MergeReplicatesNode(CommandNode):
    """Merge replicate samples in an ampvis2 object by metadata group."""

    LEGACY_NODE_ID = "ampvis2_mergereplicates"
    DISPLAY_NAME = "ampvis2 merge replicates"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Merge replicate samples in an ampvis2 RDS dataset by averaging OTU abundances."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 merge replicates",
        "amp_mergereplicates",
        "amp_merge_replicates",
        "replicate samples",
        "average OTU abundances",
        "metadata groups",
    ]
    RETURN_TYPES = ("FILE", "TSV")
    RETURN_NAMES = ("ampvis", "metadata_list_out")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_merge_replicates.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    ROUND_OPTIONS = ["", "up", "down"]

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        round_value = str(inputs.get("round", "") or "")
        lines = [
            "library(ampvis2, quietly = TRUE)",
            f'data <- readRDS("{inputs.get("data", "")}")',
            "data <- amp_mergereplicates(",
            "    data,",
            f'    merge_var = "{inputs.get("merge_var", "")}"{"," if round_value else ""}',
        ]
        if round_value:
            lines.append(f'    round = "{round_value}"')
        lines.extend(
            [
                ")",
                f'saveRDS(data, "{out}/ampvis.rds")',
                *Ampvis2LoadNode._metadata_list_lines(out),
                "data",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/mergereplicates.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "ampvis.rds", out / "metadata_list.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        if not str(inputs.get("metadata_list", "")).strip():
            return "metadata_list is required"
        if not str(inputs.get("merge_var", "")).strip():
            return "merge_var is required"
        round_value = str(inputs.get("round", "") or "")
        if round_value not in cls.ROUND_OPTIONS:
            return f"round must be one of: {', '.join(cls.ROUND_OPTIONS)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data": ("FILE", {"description": "Ampvis2 RDS dataset generated with ampvis2: load"}),
                "metadata_list": ("TSV", {"description": "Metadata list generated by ampvis2: load"}),
                "merge_var": ("STRING", {"description": "Discrete metadata variable defining replicate sample groups"}),
            },
            "optional": {
                "round": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.ROUND_OPTIONS,
                        "description": "Round merged read count decimals up, down, or not at all",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2SetMetadataNode(CommandNode):
    """Set ampvis2 metadata column classes and regenerate metadata selectors."""

    LEGACY_NODE_ID = "ampvis2_setmetadata"
    DISPLAY_NAME = "ampvis2 set metadata"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Manually set ampvis2 sample metadata column types and regenerate the metadata list."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 set metadata",
        "metadata type conversion",
        "metadata classes",
        "as.numeric metadata",
        "as.integer metadata",
        "lubridate as_date",
        "sample metadata list",
    ]
    RETURN_TYPES = ("FILE", "TSV")
    RETURN_NAMES = ("ampvis", "metadata_list_out")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/blob/main/tools/ampvis2/setmetadata.xml"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    TYPE_INPUTS = ("character", "numbers", "integers", "dates")

    @classmethod
    def _column_names(cls, inputs: dict[str, Any], name: str) -> list[str]:
        return [str(value).strip() for value in _as_list(inputs.get(name)) if str(value).strip()]

    @classmethod
    def _raw_column_names(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value]
        return [str(value).strip()]

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        lines = [
            "library(lubridate, quietly = TRUE)",
            f'data <- readRDS("{inputs.get("data", "")}")',
        ]
        for column in cls._column_names(inputs, "character"):
            lines.append(f"data$metadata${column} <- as.character(data$metadata${column})")
        for column in cls._column_names(inputs, "numbers"):
            lines.append(f"data$metadata${column} <- as.numeric(data$metadata${column})")
        for column in cls._column_names(inputs, "integers"):
            lines.append(f"data$metadata${column} <- as.integer(data$metadata${column})")
        for column in cls._column_names(inputs, "dates"):
            lines.append(f"data$metadata${column} <- as_date(data$metadata${column})")
        lines.extend(
            [
                f'saveRDS(data, "{out}/ampvis.rds")',
                *Ampvis2LoadNode._metadata_list_lines(out),
                "data",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/setmetadata.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "ampvis.rds", out / "metadata_list.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        if not str(inputs.get("metadata_list", "")).strip():
            return "metadata_list is required"
        raw_values = [column for name in cls.TYPE_INPUTS for column in cls._raw_column_names(inputs.get(name))]
        if any(not column for column in raw_values):
            return "metadata column names must be non-empty"
        seen: set[str] = set()
        duplicates: list[str] = []
        for column in raw_values:
            if column in seen and column not in duplicates:
                duplicates.append(column)
            seen.add(column)
        if duplicates:
            return f"metadata columns can only be assigned to one type: {', '.join(duplicates)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data": ("FILE", {"description": "Ampvis2 RDS dataset generated with ampvis2: load"}),
                "metadata_list": ("TSV", {"description": "Metadata list generated by ampvis2: load"}),
            },
            "optional": {
                "character": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Metadata variables to keep or cast as character values",
                    },
                ),
                "numbers": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Metadata variables to cast with as.numeric",
                    },
                ),
                "integers": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Discrete numerical metadata variables to cast with as.integer",
                    },
                ),
                "dates": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Date metadata variables to cast with lubridate::as_date",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(Ampvis2ExportFastaNode)
pin_contract(Ampvis2ExportOtuNode)
pin_contract(Ampvis2LoadNode)
pin_contract(Ampvis2MergeAmpvis2Node)
pin_contract(Ampvis2MergeReplicatesNode)
pin_contract(Ampvis2SetMetadataNode)
