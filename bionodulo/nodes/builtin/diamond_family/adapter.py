"""Shared DIAMOND contracts for focused protein taxonomy nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.taxonomy_family.protein_contracts import ValidatedCommandContract


DIAMOND_GIT_COMMIT = "4c026eae71032c8e71fd1b647086296562892e4a"
TOOLS_IUC_GIT_COMMIT = "8eb66da1f6f16fde92688ee6c500d2bcdc924a47"


class DiamondContractNode(ValidatedCommandContract):
    """DIAMOND 2.2.2 plus the exact Galaxy IUC wrapper authority."""

    GIT_URL = "https://github.com/bbuchfink/diamond.git"
    GIT_COMMIT = DIAMOND_GIT_COMMIT
    SOURCE_URL = f"https://github.com/bbuchfink/diamond/tree/{DIAMOND_GIT_COMMIT}"
    PACKAGE_CONSTRAINT = "diamond==2.2.2"
    GALAXY_WRAPPER_VERSION = "2.2.2+galaxy0"
    GALAXY_WRAPPER_GIT_URL = "https://github.com/galaxyproject/tools-iuc.git"
    GALAXY_WRAPPER_GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    GALAXY_WRAPPER_SOURCE_URL = (
        f"https://github.com/galaxyproject/tools-iuc/tree/{TOOLS_IUC_GIT_COMMIT}/tools/diamond"
    )
    EXIT_SEMANTICS = "DIAMOND or wrapper validation failures must produce a non-zero command result."


class _DiamondMakeDBContract(DiamondContractNode):
    """Build a DIAMOND protein database from FASTA."""

    LEGACY_NODE_ID = "diamond_makedb"
    DISPLAY_NAME = "DIAMOND MakeDB"
    REQUIRED_CONDA_PACKAGES = ["diamond"]
    CATEGORY = "databases"
    DESCRIPTION = "Build a DIAMOND .dmnd protein database from FASTA, optionally with taxonomy files."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "diamond", "makedb", "protein database", "dmnd"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("database",)
    REQUIRED_EXECUTABLES = ["diamond"]
    DOCUMENTATION_URL = "https://github.com/bbuchfink/diamond/wiki"
    CITATION_DOIS = ["10.1038/s41592-021-01101-x"]
    CITATION_URLS = ["https://doi.org/10.1038/s41592-021-01101-x"]
    CITATION_TEXT = "Sensitive protein alignments at tree-of-life scale using DIAMOND."
    VERSION = "2.2.2"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "diamond",
            "makedb",
            "--threads",
            str(inputs.get("threads", 12)),
            "--in",
            str(inputs.get("infile", "")),
            "--db",
            f"{_out(inputs)}/database",
        ]
        _add_if_value(cmd, "--taxonmap", inputs.get("taxonmap"))
        _add_if_value(cmd, "--taxonnodes", inputs.get("taxonnodes"))
        _add_if_value(cmd, "--taxonnames", inputs.get("taxonnames"))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "database.dmnd"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "infile": ("FASTA", {"description": "Protein FASTA reference"}),
                "threads": ("INT", {"default": 12, "min": 1, "max": 128, "display": "slider"}),
            },
            "optional": {
                "taxonmap": ("TSV", {"description": "Protein accession to taxid mapping", "advanced": True}),
                "taxonnodes": ("TSV", {"description": "NCBI nodes.dmp", "advanced": True}),
                "taxonnames": ("TSV", {"description": "NCBI names.dmp", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _DiamondAlignContract(DiamondContractNode):
    """Align protein or translated nucleotide queries with DIAMOND."""

    LEGACY_NODE_ID = "diamond_align"
    DISPLAY_NAME = "DIAMOND Align"
    REQUIRED_CONDA_PACKAGES = ["diamond"]
    CATEGORY = "alignment"
    DESCRIPTION = "Run DIAMOND blastp or blastx searches against a protein database."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "diamond", "blastp", "blastx", "protein alignment", "translated search"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("matches",)
    REQUIRED_EXECUTABLES = ["diamond"]
    DOCUMENTATION_URL = "https://github.com/bbuchfink/diamond/wiki"
    CITATION_DOIS = ["10.1038/s41592-021-01101-x"]
    CITATION_URLS = ["https://doi.org/10.1038/s41592-021-01101-x"]
    CITATION_TEXT = "Sensitive protein alignments at tree-of-life scale using DIAMOND."
    VERSION = "2.2.2"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        outfmt = str(inputs.get("outfmt", "6 qseqid sseqid pident length evalue bitscore")).split()
        cmd = [
            "diamond",
            str(inputs.get("method", "blastp")),
            "--threads",
            str(inputs.get("threads", 12)),
            "--db",
            str(inputs.get("database", "")),
            "--query",
            str(inputs.get("query", "")),
            "--out",
            f"{_out(inputs)}/matches.tsv",
            "--outfmt",
            *outfmt,
        ]
        sensitivity = str(inputs.get("sensitivity", ""))
        if sensitivity:
            cmd.append(sensitivity)
        _add_if_value(cmd, "--evalue", inputs.get("evalue"))
        _add_if_value(cmd, "--max-target-seqs", inputs.get("max_target_seqs"))
        _add_if_value(cmd, "--matrix", inputs.get("matrix"))
        if inputs.get("method") == "blastx":
            _add_if_value(cmd, "--query-gencode", inputs.get("query_gencode"))
            _add_if_value(cmd, "--strand", inputs.get("query_strand"))
            _add_if_value(cmd, "--min-orf", inputs.get("min_orf"))
        if inputs.get("no_self_hits"):
            cmd.append("--no-self-hits")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "matches.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("FASTA", {"description": "Protein or nucleotide query FASTA"}),
                "database": ("FILE", {"description": "DIAMOND .dmnd database"}),
                "method": ("STRING", {"default": "blastp", "options": ["blastp", "blastx"]}),
                "threads": ("INT", {"default": 12, "min": 1, "max": 128, "display": "slider"}),
            },
            "optional": {
                "sensitivity": ("STRING", {"default": "", "options": ["", "--fast", "--sensitive", "--more-sensitive", "--very-sensitive", "--ultra-sensitive"]}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0}),
                "max_target_seqs": ("INT", {"default": 25, "min": 1}),
                "matrix": ("STRING", {"default": "BLOSUM62", "advanced": True}),
                "outfmt": ("STRING", {"default": "6 qseqid sseqid pident length evalue bitscore", "advanced": True}),
                "query_gencode": ("INT", {"default": 1, "advanced": True}),
                "query_strand": ("STRING", {"default": "both", "options": ["both", "plus", "minus"], "advanced": True}),
                "min_orf": ("INT", {"default": 20, "min": 1, "advanced": True}),
                "no_self_hits": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _DiamondGalaxyMixin:
    REQUIRED_CONDA_PACKAGES = ["diamond"]
    REQUIRED_EXECUTABLES = ["diamond"]
    DOCUMENTATION_URL = "https://github.com/bbuchfink/diamond/wiki"
    CITATION_DOIS = [DIAMOND_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{DIAMOND_CITATION_DOI}"]
    CITATION_TEXT = DIAMOND_CITATION_TEXT
    VERSION = "2.2.2+galaxy0"

    @classmethod
    def _outfmt(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("outfmt", "6") or "6")

    @classmethod
    def _output_filename(cls, inputs: dict[str, Any]) -> str:
        return DIAMOND_OUTPUT_FORMATS.get(cls._outfmt(inputs), DIAMOND_OUTPUT_FORMATS["6"])[2]

    @classmethod
    def _selected_fields(cls, inputs: dict[str, Any]) -> list[str]:
        fields = _as_list(inputs.get("fields"))
        if len(fields) == 1 and " " in fields[0]:
            fields = [field for field in fields[0].replace(",", " ").split() if field]
        elif len(fields) == 1 and "," in fields[0]:
            fields = [field for field in fields[0].split(",") if field]
        return fields or DIAMOND_DEFAULT_FIELDS.copy()

    @classmethod
    def _add_output_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        outfmt = cls._outfmt(inputs)
        cmd.extend(["--outfmt", outfmt])
        if outfmt in {"6", "104"}:
            cmd.extend(cls._selected_fields(inputs))
            if outfmt == "6":
                cmd.extend(["--header", str(inputs.get("header", "0") or "0")])
        cmd.extend(["--out", f"{_out(inputs)}/{cls._output_filename(inputs)}"])
        if outfmt == "102" and inputs.get("include_lineage"):
            cmd.append("--include-lineage")

    @classmethod
    def _add_hit_filter_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if str(inputs.get("hit_filter_select", "max") or "max") == "max":
            cmd.extend(["--max-target-seqs", str(inputs.get("max_target_seqs", 25) or 25)])
        else:
            cmd.extend(["--top", str(inputs.get("top", 0) or 0)])

    @classmethod
    def _add_identity_filter_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        _add_if_value(cmd, "--id", inputs.get("id", 0))
        _add_if_value(cmd, "--approx-id", inputs.get("approx_id", 0))
        _add_if_value(cmd, "--query-cover", inputs.get("query_cover", 0))
        _add_if_value(cmd, "--subject-cover", inputs.get("subject_cover", 0))

    @classmethod
    def _add_score_filter_args(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if str(inputs.get("filter_score_select", "evalue") or "evalue") == "evalue":
            cmd.extend(["--evalue", str(inputs.get("evalue", 0.001) or 0.001)])
        else:
            cmd.extend(["--min-score", str(inputs.get("min_score", 0) or 0)])

    @classmethod
    def _add_taxon_filter(cls, cmd: list[str], inputs: dict[str, Any], *, prefix: str = "") -> None:
        selector_key = "tax_exclude_select" if prefix == "tax_exclude_" else "tax_select"
        selector = str(inputs.get(selector_key, "no") or "no")
        key = "taxon_exclude" if prefix == "tax_exclude_" else "taxonlist"
        flag = "--taxon_exclude" if prefix == "tax_exclude_" else "--taxonlist"
        if selector in {"list", "file"}:
            _add_if_value(cmd, flag, inputs.get(key))

    @classmethod
    def _selected_optional_query_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("output_unal"))

    @classmethod
    def _query_ext_is_fastq(cls, inputs: dict[str, Any]) -> bool:
        return "fastq" in Path(str(inputs.get("query", ""))).suffixes or "fastq" in str(inputs.get("query", "")).lower()

    @classmethod
    def _planned_outputs(cls, inputs: dict[str, Any], output_dir: str | Path, node_id: str) -> list[Path]:
        out = Path(output_dir) / node_id
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / cls._output_filename(inputs)]
        selected = cls._selected_optional_query_outputs(inputs)
        query_ext = "fastq" if cls._query_ext_is_fastq(inputs) else "fasta"
        if "--un" in selected:
            outputs.append(out / f"unaligned_queries.{query_ext}")
        if "--al" in selected:
            outputs.append(out / f"aligned_queries.{query_ext}")
        if inputs.get("log"):
            outputs.append(out / "diamond.log")
        return outputs

    @classmethod
    def _validate_common(cls, inputs: dict[str, Any]) -> bool | str:
        outfmt = cls._outfmt(inputs)
        if outfmt not in DIAMOND_OUTPUT_FORMATS:
            return f"outfmt must be one of: {', '.join(DIAMOND_OUTPUT_FORMATS)}"
        selected = cls._selected_optional_query_outputs(inputs)
        unsupported = [name for name in selected if name not in {"--un", "--al"}]
        if unsupported:
            return f"output_unal contains unsupported values: {', '.join(unsupported)}"
        hit_filter = str(inputs.get("hit_filter_select", "max") or "max")
        if hit_filter not in {"max", "top"}:
            return "hit_filter_select must be one of: max, top"
        filter_score = str(inputs.get("filter_score_select", "evalue") or "evalue")
        if filter_score not in {"evalue", "min-score"}:
            return "filter_score_select must be one of: evalue, min-score"
        return True

class _GalaxyDiamondMakeDBContract(_DiamondMakeDBContract):
    """Galaxy wrapper-compatible DIAMOND makedb node."""

    LEGACY_NODE_ID = "bg_diamond_makedb"
    DISPLAY_NAME = "Diamond makedb"
    CATEGORY = "databases"
    DESCRIPTION = "Build a DIAMOND protein database from a FASTA file, optionally including taxonomy data."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "bg_diamond_makedb", "diamond", "Diamond makedb", "makedb", "protein database", "dmnd"]
    VERSION = "2.2.2+galaxy0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "diamond",
            "makedb",
            "--threads",
            str(inputs.get("threads", 12)),
            "--in",
            str(inputs.get("infile", "")),
            "--db",
            f"{_out(inputs)}/database",
        ]
        if str(inputs.get("tax_select", "no") or "no") == "yes":
            _add_if_value(cmd, "--taxonmap", inputs.get("taxonmap"))
            _add_if_value(cmd, "--taxonnodes", inputs.get("taxonnodes"))
            _add_if_value(cmd, "--taxonnames", inputs.get("taxonnames"))
        elif str(inputs.get("tax_select", "no") or "no") == "yes_cached":
            taxonomy_path = str(inputs.get("ncbi_taxonomy", "")).rstrip("/")
            if taxonomy_path:
                cmd.extend(
                    [
                        "--taxonmap",
                        f"{taxonomy_path}/prot.accession2taxid",
                        "--taxonnodes",
                        f"{taxonomy_path}/nodes.dmp",
                        "--taxonnames",
                        f"{taxonomy_path}/names.dmp",
                    ]
                )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "database.dmnd"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("infile", "")).strip():
            return "infile is required"
        tax_select = str(inputs.get("tax_select", "no") or "no")
        if tax_select not in {"no", "yes", "yes_cached"}:
            return "tax_select must be one of: no, yes, yes_cached"
        if tax_select == "yes" and not all(inputs.get(name) for name in ("taxonmap", "taxonnodes", "taxonnames")):
            return "taxonmap, taxonnodes, and taxonnames are required when tax_select=yes"
        if tax_select == "yes_cached" and not str(inputs.get("ncbi_taxonomy", "")).strip():
            return "ncbi_taxonomy is required when tax_select=yes_cached"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "infile": ("FASTA", {"description": "Input reference file in FASTA format"}),
            },
            "optional": {
                "threads": ("INT", {"default": 12, "min": 1, "max": 128, "display": "slider"}),
                "tax_select": (
                    "STRING",
                    {
                        "default": "no",
                        "options": ["no", "yes", "yes_cached"],
                        "description": "Add taxonomy data from history files or a cached NCBI taxonomy directory",
                    },
                ),
                "taxonmap": ("TSV", {"default": "", "description": "Protein accession to taxid mapping", "advanced": True}),
                "taxonnodes": ("TSV", {"default": "", "description": "NCBI taxonomy nodes.dmp", "advanced": True}),
                "taxonnames": ("TSV", {"default": "", "description": "NCBI taxonomy names.dmp", "advanced": True}),
                "ncbi_taxonomy": (
                    "DIRECTORY",
                    {"default": "", "description": "Cached NCBI taxonomy directory for tax_select=yes_cached", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _GalaxyDiamondContract(_DiamondGalaxyMixin, DiamondContractNode):
    """Galaxy wrapper-compatible DIAMOND alignment node."""

    LEGACY_NODE_ID = "bg_diamond"
    DISPLAY_NAME = "Diamond"
    CATEGORY = "alignment"
    DESCRIPTION = "Align protein or translated nucleotide sequences against a protein database with DIAMOND."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "bg_diamond",
        "diamond",
        "Diamond",
        "blastp",
        "blastx",
        "protein alignment",
        "translated search",
        "DAA",
    ]
    RETURN_TYPES = tuple(value[0] for value in DIAMOND_OUTPUT_FORMATS.values()) + ("FASTA", "FASTA", "TXT")
    RETURN_NAMES = tuple(value[1] for value in DIAMOND_OUTPUT_FORMATS.values()) + (
        "unaligned_queries",
        "aligned_queries",
        "log_file",
    )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        method = str(inputs.get("method", "blastp") or "blastp")
        cmd = [
            "diamond",
            method,
            "--threads",
            str(inputs.get("threads", 12)),
            "--db",
            str(inputs.get("database", "")),
            "--query",
            str(inputs.get("query", "")),
        ]
        if method == "blastx":
            _add_if_value(cmd, "--query-gencode", inputs.get("query_gencode", 1))
            _add_if_value(cmd, "--strand", inputs.get("query_strand", "both"))
            _add_if_value(cmd, "--min-orf", inputs.get("min_orf", 1))
            if inputs.get("frameshift"):
                cmd.extend(["--frameshift", str(inputs.get("frameshift"))])
                if inputs.get("range_culling"):
                    cmd.append("--range-culling")
        elif inputs.get("no_self_hits"):
            cmd.append("--no-self-hits")
        cls._add_output_args(cmd, inputs)
        if cls._outfmt(inputs) != "100":
            cmd.extend(["--compress", "0"])
        sensitivity = str(inputs.get("sensitivity", "") or "")
        if sensitivity:
            cmd.append(sensitivity)
        _add_if_value(cmd, "--gapopen", inputs.get("gapopen"))
        _add_if_value(cmd, "--gapextend", inputs.get("gapextend"))
        cmd.extend(
            [
                "--matrix",
                str(inputs.get("matrix", "BLOSUM62") or "BLOSUM62"),
                "--comp-based-stats",
                str(inputs.get("comp_based_stats", "1") or "1"),
                "--masking",
                str(inputs.get("masking", "tantan") or "tantan"),
            ]
        )
        cls._add_hit_filter_args(cmd, inputs)
        cls._add_score_filter_args(cmd, inputs)
        cls._add_identity_filter_args(cmd, inputs)
        _add_if_value(cmd, "--block-size", inputs.get("block_size", 2))
        query_ext = "fastq" if cls._query_ext_is_fastq(inputs) else "fasta"
        selected = cls._selected_optional_query_outputs(inputs)
        if "--un" in selected:
            cmd.extend(["--un", f"{_out(inputs)}/unaligned_queries.{query_ext}", "--unfmt", query_ext])
        if "--al" in selected:
            cmd.extend(["--al", f"{_out(inputs)}/aligned_queries.{query_ext}", "--alfmt", query_ext])
        _add_if_value(cmd, "--max-hsps", inputs.get("max_hsps"))
        cls._add_taxon_filter(cmd, inputs)
        cls._add_taxon_filter(cmd, inputs, prefix="tax_exclude_")
        _add_if_value(cmd, "--seed-cut", inputs.get("seed_cut"))
        if inputs.get("freq_masking"):
            cmd.append("--freq-masking")
        _add_if_value(cmd, "--motif-masking", inputs.get("motif_masking", "0"))
        _add_if_value(cmd, "--soft-masking", inputs.get("soft_masking", "0"))
        if inputs.get("iterate"):
            cmd.append("--iterate")
        if inputs.get("swipe"):
            cmd.append("--swipe")
        cmd.extend(["--algo", str(inputs.get("algo", "0") or "0")])
        _add_if_value(cmd, "--global-ranking", inputs.get("global_ranking"))
        cmd.extend(
            [
                "--index-chunks",
                str(inputs.get("index_chunks", 4) or 4),
                "--file-buffer-size",
                str(inputs.get("file_buffer_size", 67108864) or 67108864),
            ]
        )
        if inputs.get("log"):
            cmd.append("--log")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._planned_outputs(inputs, output_dir, cls.NODE_ID)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("query", "")).strip():
            return "query is required"
        if not str(inputs.get("database", "")).strip():
            return "database is required"
        method = str(inputs.get("method", "blastp") or "blastp")
        if method not in {"blastp", "blastx"}:
            return "method must be one of: blastp, blastx"
        common_validation = cls._validate_common(inputs)
        if common_validation is not True:
            return common_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("FASTA", {"description": "Input query file in FASTA or FASTQ format"}),
                "database": ("FILE", {"description": "DIAMOND .dmnd database or staged Galaxy database path"}),
                "method": ("STRING", {"default": "blastp", "options": ["blastp", "blastx"], "description": "Alignment mode"}),
            },
            "optional": {
                "threads": ("INT", {"default": 12, "min": 1, "max": 128, "display": "slider"}),
                "outfmt": ("STRING", {"default": "6", "options": list(DIAMOND_OUTPUT_FORMATS), "description": "DIAMOND output format"}),
                "fields": (
                    "STRING_LIST",
                    {"default": DIAMOND_DEFAULT_FIELDS.copy(), "multiple": True, "options": DIAMOND_FIELD_OPTIONS},
                ),
                "header": ("STRING", {"default": "0", "options": ["0", "simple", "verbose"], "advanced": True}),
                "sensitivity": ("STRING", {"default": "", "options": DIAMOND_SENSITIVITY_OPTIONS}),
                "filter_score_select": ("STRING", {"default": "evalue", "options": ["evalue", "min-score"]}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0}),
                "min_score": ("INT", {"default": 0, "min": 0}),
                "hit_filter_select": ("STRING", {"default": "max", "options": ["max", "top"]}),
                "max_target_seqs": ("INT", {"default": 25, "min": 0}),
                "top": ("INT", {"default": 0, "min": 0, "max": 100}),
                "id": ("FLOAT", {"default": 0, "min": 0, "max": 100}),
                "approx_id": ("FLOAT", {"default": 0, "min": 0, "max": 100}),
                "query_cover": ("FLOAT", {"default": 0, "min": 0, "max": 100}),
                "subject_cover": ("FLOAT", {"default": 0, "min": 0, "max": 100}),
                "matrix": ("STRING", {"default": "BLOSUM62", "advanced": True}),
                "gapopen": ("INT", {"default": "", "advanced": True}),
                "gapextend": ("INT", {"default": "", "advanced": True}),
                "comp_based_stats": ("STRING", {"default": "1", "options": ["0", "1", "2", "3", "4", "5"], "advanced": True}),
                "masking": ("STRING", {"default": "tantan", "options": ["none", "tantan", "seg"], "advanced": True}),
                "query_gencode": ("INT", {"default": 1, "min": 1, "advanced": True}),
                "query_strand": ("STRING", {"default": "both", "options": ["both", "plus", "minus"], "advanced": True}),
                "min_orf": ("INT", {"default": 1, "min": 1, "advanced": True}),
                "frameshift": ("INT", {"default": "", "advanced": True}),
                "range_culling": ("BOOLEAN", {"default": False, "advanced": True}),
                "tax_select": ("STRING", {"default": "no", "options": ["no", "list", "file"], "advanced": True}),
                "taxonlist": ("STRING", {"default": "", "advanced": True}),
                "tax_exclude_select": ("STRING", {"default": "no", "options": ["no", "list", "file"], "advanced": True}),
                "taxon_exclude": ("STRING", {"default": "", "advanced": True}),
                "output_unal": (
                    "STRING_LIST",
                    {"default": [], "multiple": True, "options": ["--un", "--al"], "description": "Optional query FASTA/FASTQ outputs"},
                ),
                "log": ("BOOLEAN", {"default": False, "description": "Output a DIAMOND log file"}),
                "max_hsps": ("INT", {"default": "", "min": 0, "advanced": True}),
                "seed_cut": ("FLOAT", {"default": "", "min": 0, "advanced": True}),
                "freq_masking": ("BOOLEAN", {"default": False, "advanced": True}),
                "motif_masking": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "soft_masking": ("STRING", {"default": "0", "options": ["0", "seg", "tantan"], "advanced": True}),
                "iterate": ("BOOLEAN", {"default": False, "advanced": True}),
                "swipe": ("BOOLEAN", {"default": False, "advanced": True}),
                "algo": ("STRING", {"default": "0", "options": ["0", "1", "ctg"], "advanced": True}),
                "global_ranking": ("INT", {"default": "", "min": 0, "advanced": True}),
                "block_size": ("FLOAT", {"default": 2, "min": 0, "advanced": True}),
                "index_chunks": ("INT", {"default": 4, "min": 1, "advanced": True}),
                "file_buffer_size": ("INT", {"default": 67108864, "min": 1, "advanced": True}),
                "include_lineage": ("BOOLEAN", {"default": False, "advanced": True}),
                "no_self_hits": ("BOOLEAN", {"default": True, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _GalaxyDiamondViewContract(_DiamondGalaxyMixin, DiamondContractNode):
    """Galaxy wrapper-compatible DIAMOND view node."""

    LEGACY_NODE_ID = "bg_diamond_view"
    DISPLAY_NAME = "Diamond view"
    CATEGORY = "alignment"
    DESCRIPTION = "Generate formatted DIAMOND output from DAA alignment files."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "bg_diamond_view",
        "diamond",
        "Diamond view",
        "DAA",
        "diamond view",
        "BLAST XML",
        "SAM",
    ]
    RETURN_TYPES = tuple(value[0] for value in DIAMOND_OUTPUT_FORMATS.values())
    RETURN_NAMES = tuple(value[1] for value in DIAMOND_OUTPUT_FORMATS.values())

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "diamond",
            "view",
            "--threads",
            str(inputs.get("threads", 1)),
            "--daa",
            str(inputs.get("daa", "")),
        ]
        cls._add_output_args(cmd, inputs)
        cls._add_hit_filter_args(cmd, inputs)
        cls._add_identity_filter_args(cmd, inputs)
        if inputs.get("forwardonly"):
            cmd.append("--forwardonly")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_filename(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("daa", "")).strip():
            return "daa is required"
        common_validation = cls._validate_common(inputs)
        if common_validation is not True:
            return common_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "daa": ("FILE", {"description": "Input DIAMOND DAA alignment file"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "outfmt": ("STRING", {"default": "6", "options": list(DIAMOND_OUTPUT_FORMATS), "description": "DIAMOND output format"}),
                "fields": (
                    "STRING_LIST",
                    {"default": DIAMOND_DEFAULT_FIELDS.copy(), "multiple": True, "options": DIAMOND_FIELD_OPTIONS},
                ),
                "header": ("STRING", {"default": "0", "options": ["0", "simple", "verbose"], "advanced": True}),
                "hit_filter_select": ("STRING", {"default": "max", "options": ["max", "top"]}),
                "max_target_seqs": ("INT", {"default": 25, "min": 0}),
                "top": ("INT", {"default": 0, "min": 0, "max": 100}),
                "id": ("FLOAT", {"default": 0, "min": 0, "max": 100}),
                "approx_id": ("FLOAT", {"default": 0, "min": 0, "max": 100}),
                "query_cover": ("FLOAT", {"default": 0, "min": 0, "max": 100}),
                "subject_cover": ("FLOAT", {"default": 0, "min": 0, "max": 100}),
                "include_lineage": ("BOOLEAN", {"default": False, "advanced": True}),
                "forwardonly": ("BOOLEAN", {"default": False, "description": "Only show alignments of the forward strand"}),
            },
            "hidden": {"output": ("STRING", {})},
        }
