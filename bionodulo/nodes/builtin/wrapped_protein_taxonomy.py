"""BioNodulo built-in wrapped tool nodes split by tool family."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

class DiamondMakeDBNode(CommandNode):
    """Build a DIAMOND protein database from FASTA."""

    NODE_ID = "diamond_makedb"
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

class DiamondAlignNode(CommandNode):
    """Align protein or translated nucleotide queries with DIAMOND."""

    NODE_ID = "diamond_align"
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

class GalaxyDiamondMakeDBNode(DiamondMakeDBNode):
    """Galaxy wrapper-compatible DIAMOND makedb node."""

    NODE_ID = "bg_diamond_makedb"
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

class GalaxyDiamondNode(_DiamondGalaxyMixin, CommandNode):
    """Galaxy wrapper-compatible DIAMOND alignment node."""

    NODE_ID = "bg_diamond"
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

class GalaxyDiamondViewNode(_DiamondGalaxyMixin, CommandNode):
    """Galaxy wrapper-compatible DIAMOND view node."""

    NODE_ID = "bg_diamond_view"
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

class HMMERAlimaskNode(CommandNode):
    """Apply an HMMER model or alignment coordinate mask to an MSA."""

    NODE_ID = "hmmer_alimask"
    DISPLAY_NAME = "HMMER alimask"
    REQUIRED_CONDA_PACKAGES = ["hmmer"]
    CATEGORY = "annotation"
    DESCRIPTION = "Append a mask line to a multiple sequence alignment using HMMER alimask."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "hmmer",
        "alimask",
        "alignment mask",
        "model range",
        "Stockholm alignment",
    ]
    RETURN_TYPES = ("ALIGNMENT",)
    RETURN_NAMES = ("masked_alignment",)
    REQUIRED_EXECUTABLES = ["alimask"]
    DOCUMENTATION_URL = "http://hmmer.org/documentation.html"
    CITATION_DOIS = ["10.1093/nar/gkr367"]
    CITATION_URLS = ["https://doi.org/10.1093/nar/gkr367"]
    CITATION_TEXT = "HMMER web server: interactive sequence similarity searching."
    VERSION = "3.4"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        range_flag = "--alirange" if str(inputs.get("range_type", "model")) == "ali" else "--modelrange"
        cmd = [
            "alimask",
            range_flag,
            ",".join(_as_list(inputs.get("ranges"))),
        ]
        input_format = str(inputs.get("input_format", "--amino"))
        if input_format:
            cmd.append(input_format)
        model_construction = str(inputs.get("model_construction", "fast"))
        if model_construction:
            cmd.append(model_construction if model_construction.startswith("--") else f"--{model_construction}")
        if model_construction in {"fast", "--fast"}:
            _add_if_value(cmd, "--symfrac", inputs.get("symfrac", 0.5))
        _add_if_value(cmd, "--fragthresh", inputs.get("fragthresh", 0.5))
        relative_weighting = str(inputs.get("relative_weighting", "--wpb"))
        if relative_weighting:
            cmd.append(relative_weighting)
        if relative_weighting == "--wblosum":
            _add_if_value(cmd, "--wid", inputs.get("wid", 0.62))
        _add_if_value(cmd, "--seed", inputs.get("seed", 42))
        cmd.extend([str(inputs.get("msafile", "")), f"{out}/masked.sto"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "masked.sto"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "msafile": ("ALIGNMENT", {"description": "Multiple sequence alignment to mask"}),
                "range_type": (
                    "STRING",
                    {
                        "default": "model",
                        "options": ["model", "ali"],
                        "description": "Interpret ranges in model or alignment coordinates",
                    },
                ),
                "ranges": (
                    "STRING",
                    {"list": True, "description": "One or more inclusive ranges such as 12-40"},
                ),
            },
            "optional": {
                "input_format": (
                    "STRING",
                    {"default": "--amino", "options": ["--amino", "--dna", "--rna"], "description": "Alignment alphabet"},
                ),
                "model_construction": (
                    "STRING",
                    {
                        "default": "fast",
                        "options": ["fast", "hand"],
                        "description": "How alimask chooses consensus columns for model-coordinate ranges",
                    },
                ),
                "symfrac": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0,
                        "max": 1,
                        "description": "Residue fraction threshold for fast consensus-column assignment",
                        "displayOptions": {"show": {"model_construction": ["fast"]}},
                    },
                ),
                "fragthresh": (
                    "FLOAT",
                    {"default": 0.5, "min": 0, "max": 1, "description": "Sequence-length fraction below which sequences are fragments"},
                ),
                "relative_weighting": (
                    "STRING",
                    {
                        "default": "--wpb",
                        "options": ["--wpb", "--wgsc", "--wblosum", "--wnone", "--wgiven"],
                        "description": "Relative sequence weighting strategy",
                    },
                ),
                "wid": (
                    "FLOAT",
                    {
                        "default": 0.62,
                        "min": 0,
                        "max": 1,
                        "description": "Identity cutoff for BLOSUM-style weighting",
                        "displayOptions": {"show": {"relative_weighting": ["--wblosum"]}},
                    },
                ),
                "seed": ("INT", {"default": 42, "min": 0, "description": "Random seed; 0 chooses a random seed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HMMERHmmalignNode(CommandNode):
    """Align sequences to a profile HMM using hmmalign."""

    NODE_ID = "hmmer_hmmalign"
    DISPLAY_NAME = "HMMER hmmalign"
    REQUIRED_CONDA_PACKAGES = ["hmmer"]
    CATEGORY = "alignment"
    DESCRIPTION = "Align sequences to a profile HMM and write a Stockholm alignment."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "hmmer",
        "hmmalign",
        "profile HMM alignment",
        "Stockholm alignment",
    ]
    RETURN_TYPES = ("ALIGNMENT",)
    RETURN_NAMES = ("alignment",)
    REQUIRED_EXECUTABLES = ["hmmalign"]
    DOCUMENTATION_URL = "http://hmmer.org/documentation.html"
    CITATION_DOIS = ["10.1093/nar/gkr367"]
    CITATION_URLS = ["https://doi.org/10.1093/nar/gkr367"]
    CITATION_TEXT = "HMMER web server: interactive sequence similarity searching."
    VERSION = "3.4"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ["hmmalign"]
        if inputs.get("trim"):
            cmd.append("--trim")
        input_format = str(inputs.get("input_format_select", "--amino"))
        if input_format:
            cmd.append(input_format)
        cmd.extend([
            "--outformat",
            "stockholm",
            str(inputs.get("hmmfile", "")),
            str(inputs.get("seq", "")),
        ])
        _add_shell_redirect(cmd, f"{out}/alignment.sto")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "alignment.sto"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "seq": ("FASTA", {"description": "FASTA sequences to align against the profile HMM"}),
                "hmmfile": ("FILE", {"description": "Single-profile HMM model"}),
                "input_format_select": (
                    "STRING",
                    {
                        "default": "--amino",
                        "options": ["--amino", "--dna", "--rna"],
                        "description": "Alphabet for the sequences and model",
                    },
                ),
            },
            "optional": {
                "trim": (
                    "BOOLEAN",
                    {"default": False, "description": "Trim terminal nonaligned residues from the Stockholm alignment"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HMMERHmmbuildNode(CommandNode):
    """Build a profile HMM from a multiple sequence alignment."""

    NODE_ID = "hmmer_hmmbuild"
    DISPLAY_NAME = "HMMER hmmbuild"
    REQUIRED_CONDA_PACKAGES = ["hmmer"]
    CATEGORY = "annotation"
    DESCRIPTION = "Build a profile HMM from a multiple sequence alignment."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "hmmer",
        "hmmbuild",
        "profile HMM",
        "multiple sequence alignment",
        "HMM profile",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("hmm_profile",)
    REQUIRED_EXECUTABLES = ["hmmbuild"]
    DOCUMENTATION_URL = "http://hmmer.org/documentation.html"
    CITATION_DOIS = ["10.1093/nar/gkr367"]
    CITATION_URLS = ["https://doi.org/10.1093/nar/gkr367"]
    CITATION_TEXT = "HMMER web server: interactive sequence similarity searching."
    VERSION = "3.4"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ["hmmbuild"]
        _add_if_value(cmd, "-n", inputs.get("hmmname"))
        input_format = str(inputs.get("input_format_select", "--amino"))
        if input_format:
            cmd.append(input_format)
        model_construction = str(inputs.get("model_construction", "fast"))
        if model_construction:
            cmd.append(model_construction if model_construction.startswith("--") else f"--{model_construction}")
        if model_construction in {"fast", "--fast"}:
            _add_if_value(cmd, "--symfrac", inputs.get("symfrac", 0.5))
        _add_if_value(cmd, "--fragthresh", inputs.get("fragthresh", 0.5))

        relative_weighting = str(inputs.get("relative_weighting", "--wpb"))
        if relative_weighting:
            cmd.append(relative_weighting)
        if relative_weighting == "--wblosum":
            _add_if_value(cmd, "--wid", inputs.get("wid", 0.62))

        effective_weighting = str(inputs.get("effective_weighting", ""))
        if effective_weighting:
            cmd.append(effective_weighting if effective_weighting.startswith("--") else f"--{effective_weighting}")
        if effective_weighting == "eent":
            _add_if_value(cmd, "--eset", inputs.get("eset", 0))
            _add_if_value(cmd, "--ere", inputs.get("ere", 0))
            _add_if_value(cmd, "--esigma", inputs.get("esigma", 45))
        elif effective_weighting == "eclust":
            _add_if_value(cmd, "--eset", inputs.get("eset", 0))
            _add_if_value(cmd, "--eid", inputs.get("eid", 0.62))

        prior = str(inputs.get("prior", ""))
        if prior:
            cmd.append(prior)

        if str(inputs.get("single_sequence_scoring", "false")) == "singlemx":
            _add_if_value(cmd, "--popen", inputs.get("popen", 0.02))
            _add_if_value(cmd, "--pextend", inputs.get("pextend", 0.4))

        _add_if_value(cmd, "--EmL", inputs.get("eml", 200))
        _add_if_value(cmd, "--EmN", inputs.get("emn", 200))
        _add_if_value(cmd, "--EvL", inputs.get("evl", 200))
        _add_if_value(cmd, "--EvN", inputs.get("evn", 200))
        _add_if_value(cmd, "--EfL", inputs.get("efl", 100))
        _add_if_value(cmd, "--EfN", inputs.get("efn", 200))
        _add_if_value(cmd, "--Eft", inputs.get("eft", 0.04))
        _add_if_value(cmd, "--cpu", max(1, int(inputs.get("threads", 1)) - 1))
        _add_if_value(cmd, "--seed", inputs.get("seed", 42))
        _add_if_value(cmd, "--w_beta", inputs.get("w_beta"))
        _add_if_value(cmd, "--w_length", inputs.get("w_length"))
        _add_if_value(cmd, "--maxinsertlen", inputs.get("maxinsertlen"))
        cmd.extend([f"{out}/profile.hmm", str(inputs.get("msafile", ""))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "profile.hmm"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "msafile": ("ALIGNMENT", {"description": "Stockholm, Clustal, or FASTA multiple sequence alignment"}),
            },
            "optional": {
                "hmmname": ("STRING", {"default": "", "description": "Name for the HMM"}),
                "input_format_select": (
                    "STRING",
                    {"default": "--amino", "options": ["--amino", "--dna", "--rna"], "description": "Alignment alphabet"},
                ),
                "model_construction": (
                    "STRING",
                    {"default": "fast", "options": ["fast", "hand"], "description": "Profile model construction strategy"},
                ),
                "symfrac": (
                    "FLOAT",
                    {
                        "default": 0.5,
                        "min": 0,
                        "max": 1,
                        "description": "Residue fraction threshold for fast consensus-column assignment",
                        "displayOptions": {"show": {"model_construction": ["fast"]}},
                    },
                ),
                "fragthresh": (
                    "FLOAT",
                    {"default": 0.5, "min": 0, "max": 1, "description": "Sequence-length fraction below which sequences are fragments"},
                ),
                "relative_weighting": (
                    "STRING",
                    {
                        "default": "--wpb",
                        "options": ["--wpb", "--wgsc", "--wblosum", "--wnone", "--wgiven"],
                        "description": "Relative sequence weighting strategy",
                    },
                ),
                "wid": (
                    "FLOAT",
                    {
                        "default": 0.62,
                        "min": 0,
                        "max": 1,
                        "description": "Identity cutoff for BLOSUM-style weighting",
                        "displayOptions": {"show": {"relative_weighting": ["--wblosum"]}},
                    },
                ),
                "effective_weighting": (
                    "STRING",
                    {"default": "", "options": ["", "eent", "eclust", "enone"], "description": "Effective sequence weighting strategy"},
                ),
                "eset": (
                    "FLOAT",
                    {
                        "default": 0,
                        "description": "Explicit effective sequence number",
                        "advanced": True,
                        "displayOptions": {"show": {"effective_weighting": ["eent", "eclust"]}},
                    },
                ),
                "ere": (
                    "FLOAT",
                    {
                        "default": 0,
                        "description": "Minimum relative entropy per position for eent",
                        "advanced": True,
                        "displayOptions": {"show": {"effective_weighting": ["eent"]}},
                    },
                ),
                "esigma": (
                    "FLOAT",
                    {
                        "default": 45,
                        "description": "Minimum total relative entropy for eent",
                        "advanced": True,
                        "displayOptions": {"show": {"effective_weighting": ["eent"]}},
                    },
                ),
                "eid": (
                    "FLOAT",
                    {
                        "default": 0.62,
                        "min": 0,
                        "max": 1,
                        "description": "Single-linkage identity cutoff for eclust",
                        "advanced": True,
                        "displayOptions": {"show": {"effective_weighting": ["eclust"]}},
                    },
                ),
                "prior": (
                    "STRING",
                    {"default": "", "options": ["", "--pnone", "--plaplace"], "description": "Alternative prior strategy", "advanced": True},
                ),
                "single_sequence_scoring": (
                    "STRING",
                    {"default": "false", "options": ["false", "singlemx"], "description": "Single-sequence scoring mode", "advanced": True},
                ),
                "popen": (
                    "FLOAT",
                    {
                        "default": 0.02,
                        "min": 0,
                        "max": 0.5,
                        "description": "Gap open probability for singlemx",
                        "advanced": True,
                        "displayOptions": {"show": {"single_sequence_scoring": ["singlemx"]}},
                    },
                ),
                "pextend": (
                    "FLOAT",
                    {
                        "default": 0.4,
                        "min": 0,
                        "max": 1,
                        "description": "Gap extend probability for singlemx",
                        "advanced": True,
                        "displayOptions": {"show": {"single_sequence_scoring": ["singlemx"]}},
                    },
                ),
                "eml": ("INT", {"default": 200, "min": 1, "advanced": True}),
                "emn": ("INT", {"default": 200, "min": 1, "advanced": True}),
                "evl": ("INT", {"default": 200, "min": 1, "advanced": True}),
                "evn": ("INT", {"default": 200, "min": 1, "advanced": True}),
                "efl": ("INT", {"default": 100, "min": 1, "advanced": True}),
                "efn": ("INT", {"default": 200, "min": 1, "advanced": True}),
                "eft": ("FLOAT", {"default": 0.04, "min": 0, "max": 1, "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "seed": ("INT", {"default": 42, "min": 0, "description": "Random seed; 0 chooses a random seed"}),
                "w_beta": ("FLOAT", {"default": "", "advanced": True, "description": "Window-length tail mass"}),
                "w_length": ("INT", {"default": "", "advanced": True, "description": "Window length"}),
                "maxinsertlen": ("INT", {"default": "", "advanced": True, "description": "Pretend all inserts are at most this length"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HMMERHmmconvertNode(CommandNode):
    """Convert HMM profile files between HMMER formats."""

    NODE_ID = "hmmer_hmmconvert"
    DISPLAY_NAME = "HMMER hmmconvert"
    REQUIRED_CONDA_PACKAGES = ["hmmer"]
    CATEGORY = "annotation"
    DESCRIPTION = "Convert HMM profile files between HMMER formats."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "hmmer",
        "hmmconvert",
        "HMMER2",
        "HMMER3",
        "profile conversion",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("converted_profile",)
    REQUIRED_EXECUTABLES = ["hmmconvert"]
    DOCUMENTATION_URL = "http://hmmer.org/documentation.html"
    CITATION_DOIS = ["10.1093/nar/gkr367"]
    CITATION_URLS = ["https://doi.org/10.1093/nar/gkr367"]
    CITATION_TEXT = "HMMER web server: interactive sequence similarity searching."
    VERSION = "3.4"
    SHELL = True

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return "converted.hmm2" if str(inputs.get("format", "-a")) == "-2" else "converted.hmm3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "hmmconvert",
            str(inputs.get("format", "-a")),
            str(inputs.get("hmmfile", "")),
        ]
        _add_shell_redirect(cmd, f"{out}/{cls._output_name(inputs)}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "hmmfile": ("FILE", {"description": "Input profile HMM in HMMER2 or HMMER3 format"}),
                "format": (
                    "STRING",
                    {
                        "default": "-a",
                        "options": ["-a", "-2"],
                        "description": "Output HMMER3 ASCII or backward-compatible HMMER2 ASCII format",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HMMERHmmemitNode(CommandNode):
    """Sample sequences or consensus output from a profile HMM."""

    NODE_ID = "hmmer_hmmemit"
    DISPLAY_NAME = "HMMER hmmemit"
    REQUIRED_CONDA_PACKAGES = ["hmmer"]
    CATEGORY = "annotation"
    DESCRIPTION = "Sample sequences or consensus output from a profile HMM."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "hmmer",
        "hmmemit",
        "emit sequences",
        "consensus sequence",
        "profile sampling",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("emitted_sequences",)
    REQUIRED_EXECUTABLES = ["hmmemit"]
    DOCUMENTATION_URL = "http://hmmer.org/documentation.html"
    CITATION_DOIS = ["10.1093/nar/gkr367"]
    CITATION_URLS = ["https://doi.org/10.1093/nar/gkr367"]
    CITATION_TEXT = "HMMER web server: interactive sequence similarity searching."
    VERSION = "3.4"
    SHELL = True

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return "emitted.sto" if str(inputs.get("output_mode", "fasta")) == "aln" else "emitted.fasta"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_mode = str(inputs.get("output_mode", "fasta"))
        cmd = ["hmmemit"]
        if output_mode == "aln":
            _add_if_value(cmd, "-N", inputs.get("n_alignment", 1))
            cmd.append("-a")
        elif output_mode == "mrcs":
            cmd.append("-c")
        elif output_mode == "mrcsf":
            _add_if_value(cmd, "--minl", inputs.get("minl", 0.7))
            _add_if_value(cmd, "--minu", inputs.get("minu", 0.2))
            cmd.append("-C")
        elif output_mode == "sample":
            _add_if_value(cmd, "-N", inputs.get("n_sample", 1))
            cmd.append("-p")
            _add_if_value(cmd, "-L", inputs.get("length"))
            emission_profile = str(inputs.get("emission_profile", "--local"))
            if emission_profile:
                cmd.append(emission_profile)
        else:
            _add_if_value(cmd, "-N", inputs.get("n_fasta", 1))
        _add_if_value(cmd, "--seed", inputs.get("seed", 42))
        cmd.append(str(inputs.get("hmmfile", "")))
        _add_shell_redirect(cmd, f"{_out(inputs)}/{cls._output_name(inputs)}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "hmmfile": ("FILE", {"description": "Profile HMM file"}),
                "output_mode": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "aln", "mrcs", "mrcsf", "sample"],
                        "description": "Emit FASTA, alignment, consensus, or profile-sampled sequences",
                    },
                ),
            },
            "optional": {
                "n_fasta": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "description": "Number of FASTA sequences to generate",
                        "displayOptions": {"show": {"output_mode": ["fasta"]}},
                    },
                ),
                "n_alignment": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "description": "Number of sequences to include in the emitted alignment",
                        "displayOptions": {"show": {"output_mode": ["aln"]}},
                    },
                ),
                "n_sample": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "description": "Number of profile-sampled sequences to generate",
                        "displayOptions": {"show": {"output_mode": ["sample"]}},
                    },
                ),
                "minl": (
                    "FLOAT",
                    {
                        "default": 0.7,
                        "description": "Fancier consensus lower probability threshold",
                        "displayOptions": {"show": {"output_mode": ["mrcsf"]}},
                    },
                ),
                "minu": (
                    "FLOAT",
                    {
                        "default": 0.2,
                        "description": "Fancier consensus uppercase probability threshold",
                        "displayOptions": {"show": {"output_mode": ["mrcsf"]}},
                    },
                ),
                "length": (
                    "INT",
                    {
                        "default": "",
                        "description": "Expected target length for profile sampling",
                        "displayOptions": {"show": {"output_mode": ["sample"]}},
                    },
                ),
                "emission_profile": (
                    "STRING",
                    {
                        "default": "--local",
                        "options": ["--local", "--unilocal", "--glocal", "--uniglocal"],
                        "description": "Search-profile alignment mode for sampled sequences",
                        "displayOptions": {"show": {"output_mode": ["sample"]}},
                    },
                ),
                "seed": ("INT", {"default": 42, "min": 0, "description": "Random seed; 0 chooses a random seed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HMMERHmmfetchNode(CommandNode):
    """Retrieve selected profile HMM models from a HMM file."""

    NODE_ID = "hmmer_hmmfetch"
    DISPLAY_NAME = "HMMER hmmfetch"
    REQUIRED_CONDA_PACKAGES = ["hmmer"]
    CATEGORY = "annotation"
    DESCRIPTION = "Retrieve selected profile HMM models from a HMM file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "hmmer",
        "hmmfetch",
        "retrieve HMM",
        "profile HMM names",
        "Pfam subset",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("selected_hmm_models",)
    REQUIRED_EXECUTABLES = ["hmmfetch"]
    DOCUMENTATION_URL = "http://hmmer.org/documentation.html"
    CITATION_DOIS = ["10.1093/nar/gkr367"]
    CITATION_URLS = ["https://doi.org/10.1093/nar/gkr367"]
    CITATION_TEXT = "HMMER web server: interactive sequence similarity searching."
    VERSION = "3.4"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "hmmfetch",
            "-f",
            str(inputs.get("hmmfile", "")),
            str(inputs.get("keyfile", "")),
        ]
        _add_shell_redirect(cmd, f"{_out(inputs)}/selected.hmm")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "selected.hmm"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "hmmfile": ("FILE", {"description": "Profile HMM file to retrieve models from"}),
                "keyfile": ("FILE", {"description": "Text or tabular file with one HMM name per line"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HMMERJackhmmerNode(CommandNode):
    """Iteratively search protein sequences against a protein FASTA database."""

    NODE_ID = "hmmer_jackhmmer"
    DISPLAY_NAME = "HMMER jackhmmer"
    REQUIRED_CONDA_PACKAGES = ["hmmer"]
    CATEGORY = "annotation"
    DESCRIPTION = "Iteratively search protein sequences against a protein FASTA database."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "hmmer",
        "jackhmmer",
        "iterative search",
        "profile iteration",
        "PSI-BLAST-like",
    ]
    RETURN_TYPES = ("STATS_FILE", "TSV", "TSV")
    RETURN_NAMES = ("output", "tblout", "domtblout")
    REQUIRED_EXECUTABLES = ["jackhmmer"]
    DOCUMENTATION_URL = "http://hmmer.org/documentation.html"
    CITATION_DOIS = ["10.1093/nar/gkr367"]
    CITATION_URLS = ["https://doi.org/10.1093/nar/gkr367"]
    CITATION_TEXT = "HMMER web server: interactive sequence similarity searching."
    VERSION = "3.4"
    SHELL = True
    DEFAULT_OUTPUT_FORMATS = ("tblout", "domtblout")

    @classmethod
    def _output_formats(cls, inputs: dict[str, Any]) -> list[str]:
        if "output_formats" not in inputs:
            return list(cls.DEFAULT_OUTPUT_FORMATS)
        return _as_list(inputs.get("output_formats"))

    @classmethod
    def _add_output_format_flags(cls, cmd: list[str], inputs: dict[str, Any], out: str) -> None:
        output_formats = set(cls._output_formats(inputs))
        if "tblout" in output_formats:
            cmd.extend(["--tblout", f"{out}/results.tblout"])
        if "domtblout" in output_formats:
            cmd.extend(["--domtblout", f"{out}/domains.domtblout"])

    @classmethod
    def _add_output_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        for key, flag in (("acc", "--acc"), ("noali", "--noali"), ("notextw", "--notextw")):
            if inputs.get(key):
                cmd.append(flag)

    @classmethod
    def _add_single_sequence_scoring(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if str(inputs.get("single_sequence_scoring", "false")) == "singlemx":
            _add_if_value(cmd, "--popen", inputs.get("popen", 0.02))
            _add_if_value(cmd, "--pextend", inputs.get("pextend", 0.4))

    @classmethod
    def _add_thresholds(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        threshold_mode = str(inputs.get("threshold_mode", "evalue"))
        if threshold_mode == "score":
            _add_if_value(cmd, "-T", inputs.get("score_threshold"))
            _add_if_value(cmd, "--incT", inputs.get("incT"))
        else:
            _add_if_value(cmd, "-E", inputs.get("evalue", 10))
            _add_if_value(cmd, "--incE", inputs.get("incE"))

    @classmethod
    def _add_acceleration_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if inputs.get("max"):
            cmd.append("--max")
        _add_if_value(cmd, "--F1", inputs.get("F1", 0.02))
        _add_if_value(cmd, "--F2", inputs.get("F2", 0.001))
        _add_if_value(cmd, "--F3", inputs.get("F3", 1e-5))
        if inputs.get("nobias"):
            cmd.append("--nobias")

    @classmethod
    def _add_weighting_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        relative_weighting = str(inputs.get("relative_weighting", "--wpb"))
        if relative_weighting:
            cmd.append(relative_weighting)
        if relative_weighting == "--wblosum":
            _add_if_value(cmd, "--wid", inputs.get("wid", 0.62))

        effective_weighting = str(inputs.get("effective_weighting", ""))
        if effective_weighting:
            cmd.append(effective_weighting if effective_weighting.startswith("--") else f"--{effective_weighting}")
        if effective_weighting == "eent":
            _add_if_value(cmd, "--eset", inputs.get("eset", 0))
            _add_if_value(cmd, "--ere", inputs.get("ere", 0))
            _add_if_value(cmd, "--esigma", inputs.get("esigma", 45))
        elif effective_weighting == "eclust":
            _add_if_value(cmd, "--eset", inputs.get("eset", 0))
            _add_if_value(cmd, "--eid", inputs.get("eid", 0.62))

        prior = str(inputs.get("prior", ""))
        if prior:
            cmd.append(prior)

    @classmethod
    def _add_calibration_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        _add_if_value(cmd, "--EmL", inputs.get("eml", 200))
        _add_if_value(cmd, "--EmN", inputs.get("emn", 200))
        _add_if_value(cmd, "--EvL", inputs.get("evl", 200))
        _add_if_value(cmd, "--EvN", inputs.get("evn", 200))
        _add_if_value(cmd, "--EfL", inputs.get("efl", 100))
        _add_if_value(cmd, "--EfN", inputs.get("efn", 200))
        _add_if_value(cmd, "--Eft", inputs.get("eft", 0.04))

    @classmethod
    def _add_advanced_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if inputs.get("nonull2"):
            cmd.append("--nonull2")
        _add_if_value(cmd, "-Z", inputs.get("z"))
        _add_if_value(cmd, "--domZ", inputs.get("domz"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ["jackhmmer", "-N", str(inputs.get("iterations", 5))]
        cls._add_output_format_flags(cmd, inputs, out)
        cls._add_output_options(cmd, inputs)
        cls._add_single_sequence_scoring(cmd, inputs)
        cls._add_thresholds(cmd, inputs)
        cls._add_acceleration_options(cmd, inputs)
        cls._add_weighting_options(cmd, inputs)
        cls._add_calibration_options(cmd, inputs)
        cls._add_advanced_options(cmd, inputs)
        _add_if_value(cmd, "--cpu", max(1, int(inputs.get("threads", 1)) - 1))
        _add_if_value(cmd, "--seed", inputs.get("seed", 42))
        cmd.extend([str(inputs.get("seqfile", "")), str(inputs.get("seqdb", ""))])
        _add_shell_redirect(cmd, f"{out}/output.txt")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> dict[str, Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = {"output": out / "output.txt"}
        output_formats = set(cls._output_formats(inputs))
        if "tblout" in output_formats:
            outputs["tblout"] = out / "results.tblout"
        if "domtblout" in output_formats:
            outputs["domtblout"] = out / "domains.domtblout"
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "seqfile": ("FASTA", {"description": "Protein sequence FASTA to search with"}),
                "seqdb": ("FASTA", {"description": "Protein sequence database FASTA"}),
            },
            "optional": {
                "iterations": ("INT", {"default": 5, "min": 1, "description": "Maximum number of iterations"}),
                "output_formats": (
                    "STRING",
                    {
                        "default": ["tblout", "domtblout"],
                        "options": ["tblout", "domtblout"],
                        "list": True,
                        "description": "Additional tabular output files to write",
                    },
                ),
                "acc": ("BOOLEAN", {"default": False, "description": "Prefer accessions over names in output"}),
                "noali": ("BOOLEAN", {"default": False, "description": "Suppress alignment blocks in text output"}),
                "notextw": ("BOOLEAN", {"default": False, "description": "Use unlimited text output line width"}),
                "single_sequence_scoring": (
                    "STRING",
                    {"default": "false", "options": ["false", "singlemx"], "description": "Single-sequence scoring mode"},
                ),
                "popen": (
                    "FLOAT",
                    {
                        "default": 0.02,
                        "min": 0,
                        "max": 0.5,
                        "description": "Gap open probability for singlemx",
                        "displayOptions": {"show": {"single_sequence_scoring": ["singlemx"]}},
                    },
                ),
                "pextend": (
                    "FLOAT",
                    {
                        "default": 0.4,
                        "min": 0,
                        "max": 1,
                        "description": "Gap extend probability for singlemx",
                        "displayOptions": {"show": {"single_sequence_scoring": ["singlemx"]}},
                    },
                ),
                "threshold_mode": (
                    "STRING",
                    {"default": "evalue", "options": ["evalue", "score"], "description": "Reporting threshold mode"},
                ),
                "evalue": (
                    "FLOAT",
                    {
                        "default": 10,
                        "min": 0,
                        "description": "E-value reporting threshold",
                        "displayOptions": {"show": {"threshold_mode": ["evalue"]}},
                    },
                ),
                "incE": (
                    "FLOAT",
                    {
                        "default": "",
                        "description": "E-value inclusion threshold",
                        "advanced": True,
                        "displayOptions": {"show": {"threshold_mode": ["evalue"]}},
                    },
                ),
                "score_threshold": (
                    "FLOAT",
                    {
                        "default": "",
                        "description": "Bit score reporting threshold",
                        "displayOptions": {"show": {"threshold_mode": ["score"]}},
                    },
                ),
                "incT": (
                    "FLOAT",
                    {
                        "default": "",
                        "description": "Bit score inclusion threshold",
                        "advanced": True,
                        "displayOptions": {"show": {"threshold_mode": ["score"]}},
                    },
                ),
                "max": ("BOOLEAN", {"default": False, "description": "Turn all heuristic filters off", "advanced": True}),
                "F1": ("FLOAT", {"default": 0.02, "min": 0, "advanced": True}),
                "F2": ("FLOAT", {"default": 0.001, "min": 0, "advanced": True}),
                "F3": ("FLOAT", {"default": 1e-5, "min": 0, "advanced": True}),
                "nobias": ("BOOLEAN", {"default": False, "description": "Turn off composition bias filter", "advanced": True}),
                "relative_weighting": (
                    "STRING",
                    {
                        "default": "--wpb",
                        "options": ["--wpb", "--wgsc", "--wblosum", "--wnone", "--wgiven"],
                        "description": "Relative sequence weighting strategy",
                        "advanced": True,
                    },
                ),
                "wid": (
                    "FLOAT",
                    {
                        "default": 0.62,
                        "min": 0,
                        "max": 1,
                        "description": "Identity cutoff for BLOSUM-style weighting",
                        "advanced": True,
                        "displayOptions": {"show": {"relative_weighting": ["--wblosum"]}},
                    },
                ),
                "effective_weighting": (
                    "STRING",
                    {"default": "", "options": ["", "eent", "eclust", "enone"], "description": "Effective sequence weighting strategy", "advanced": True},
                ),
                "eset": (
                    "FLOAT",
                    {
                        "default": 0,
                        "description": "Explicit effective sequence number",
                        "advanced": True,
                        "displayOptions": {"show": {"effective_weighting": ["eent", "eclust"]}},
                    },
                ),
                "ere": (
                    "FLOAT",
                    {
                        "default": 0,
                        "description": "Minimum relative entropy per position for eent",
                        "advanced": True,
                        "displayOptions": {"show": {"effective_weighting": ["eent"]}},
                    },
                ),
                "esigma": (
                    "FLOAT",
                    {
                        "default": 45,
                        "description": "Minimum total relative entropy for eent",
                        "advanced": True,
                        "displayOptions": {"show": {"effective_weighting": ["eent"]}},
                    },
                ),
                "eid": (
                    "FLOAT",
                    {
                        "default": 0.62,
                        "min": 0,
                        "max": 1,
                        "description": "Single-linkage identity cutoff for eclust",
                        "advanced": True,
                        "displayOptions": {"show": {"effective_weighting": ["eclust"]}},
                    },
                ),
                "prior": (
                    "STRING",
                    {"default": "", "options": ["", "--pnone", "--plaplace"], "description": "Alternative prior strategy", "advanced": True},
                ),
                "eml": ("INT", {"default": 200, "min": 1, "advanced": True}),
                "emn": ("INT", {"default": 200, "min": 1, "advanced": True}),
                "evl": ("INT", {"default": 200, "min": 1, "advanced": True}),
                "evn": ("INT", {"default": 200, "min": 1, "advanced": True}),
                "efl": ("INT", {"default": 100, "min": 1, "advanced": True}),
                "efn": ("INT", {"default": 200, "min": 1, "advanced": True}),
                "eft": ("FLOAT", {"default": 0.04, "min": 0, "max": 1, "advanced": True}),
                "nonull2": ("BOOLEAN", {"default": False, "description": "Turn off biased composition score corrections", "advanced": True}),
                "z": ("INT", {"default": "", "description": "Comparisons for E-value calculation", "advanced": True}),
                "domz": ("INT", {"default": "", "description": "Significant sequences for domain E-value calculation", "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "seed": ("INT", {"default": 42, "min": 0, "description": "Random seed; 0 chooses a random seed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HMMERPhmmerNode(HMMERJackhmmerNode):
    """Search protein sequences against a protein FASTA database."""

    NODE_ID = "hmmer_phmmer"
    DISPLAY_NAME = "HMMER phmmer"
    DESCRIPTION = "Search protein sequences against a protein FASTA database."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "hmmer",
        "phmmer",
        "protein search",
        "BLASTP-like",
        "sequence homology",
    ]
    RETURN_TYPES = ("STATS_FILE", "TSV", "TSV", "TSV")
    RETURN_NAMES = ("output", "tblout", "domtblout", "pfamtblout")
    REQUIRED_EXECUTABLES = ["phmmer"]
    DEFAULT_OUTPUT_FORMATS = ("tblout", "domtblout", "pfamtblout")

    @classmethod
    def _add_output_format_flags(cls, cmd: list[str], inputs: dict[str, Any], out: str) -> None:
        super()._add_output_format_flags(cmd, inputs, out)
        if "pfamtblout" in set(cls._output_formats(inputs)):
            cmd.extend(["--pfamtblout", f"{out}/pfam.tblout"])

    @classmethod
    def _add_thresholds(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        threshold_mode = str(inputs.get("threshold_mode", "evalue"))
        if threshold_mode == "score":
            _add_if_value(cmd, "-T", inputs.get("score_threshold"))
            _add_if_value(cmd, "--incT", inputs.get("incT"))
            _add_if_value(cmd, "--domT", inputs.get("domT"))
            _add_if_value(cmd, "--incdomT", inputs.get("incdomT"))
        else:
            _add_if_value(cmd, "-E", inputs.get("evalue", 10))
            _add_if_value(cmd, "--incE", inputs.get("incE"))
            _add_if_value(cmd, "--domE", inputs.get("domE", 10))
            _add_if_value(cmd, "--incdomE", inputs.get("incdomE"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ["phmmer"]
        cls._add_output_format_flags(cmd, inputs, out)
        cls._add_output_options(cmd, inputs)
        cls._add_single_sequence_scoring(cmd, inputs)
        cls._add_thresholds(cmd, inputs)
        cls._add_acceleration_options(cmd, inputs)
        cls._add_calibration_options(cmd, inputs)
        cls._add_advanced_options(cmd, inputs)
        _add_if_value(cmd, "--cpu", max(1, int(inputs.get("threads", 1)) - 1))
        _add_if_value(cmd, "--seed", inputs.get("seed", 42))
        cmd.extend([str(inputs.get("seqfile", "")), str(inputs.get("seqdb", ""))])
        _add_shell_redirect(cmd, f"{out}/output.txt")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> dict[str, Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = {"output": out / "output.txt"}
        output_formats = set(cls._output_formats(inputs))
        if "tblout" in output_formats:
            outputs["tblout"] = out / "results.tblout"
        if "domtblout" in output_formats:
            outputs["domtblout"] = out / "domains.domtblout"
        if "pfamtblout" in output_formats:
            outputs["pfamtblout"] = out / "pfam.tblout"
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        jackhmmer_inputs = super().INPUT_TYPES()
        optional = dict(jackhmmer_inputs["optional"])
        optional.pop("iterations")
        for jackhmmer_only in (
            "relative_weighting",
            "wid",
            "effective_weighting",
            "eset",
            "ere",
            "esigma",
            "eid",
            "prior",
        ):
            optional.pop(jackhmmer_only, None)
        optional["output_formats"] = (
            "STRING",
            {
                "default": ["tblout", "domtblout", "pfamtblout"],
                "options": ["tblout", "domtblout", "pfamtblout"],
                "list": True,
                "description": "Additional tabular output files to write",
            },
        )
        optional["domE"] = (
            "FLOAT",
            {
                "default": 10,
                "min": 0,
                "description": "Domain E-value reporting threshold",
                "displayOptions": {"show": {"threshold_mode": ["evalue"]}},
            },
        )
        optional["incdomE"] = (
            "FLOAT",
            {
                "default": "",
                "description": "Domain E-value inclusion threshold",
                "advanced": True,
                "displayOptions": {"show": {"threshold_mode": ["evalue"]}},
            },
        )
        optional["domT"] = (
            "FLOAT",
            {
                "default": "",
                "description": "Domain bit score reporting threshold",
                "displayOptions": {"show": {"threshold_mode": ["score"]}},
            },
        )
        optional["incdomT"] = (
            "FLOAT",
            {
                "default": "",
                "description": "Domain bit score inclusion threshold",
                "advanced": True,
                "displayOptions": {"show": {"threshold_mode": ["score"]}},
            },
        )
        return {
            "required": jackhmmer_inputs["required"],
            "optional": optional,
            "hidden": {"output": ("STRING", {})},
        }

class HMMERNhmmerNode(HMMERJackhmmerNode):
    """Search nucleotide queries against a nucleotide FASTA database."""

    NODE_ID = "hmmer_nhmmer"
    DISPLAY_NAME = "HMMER nhmmer"
    DESCRIPTION = "Search a nucleotide profile HMM or alignment against a nucleotide FASTA database."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "hmmer",
        "nhmmer",
        "DNA search",
        "RNA search",
        "BLASTN-like",
        "nucleotide homology",
    ]
    RETURN_TYPES = ("STATS_FILE", "TSV", "TEXT", "TEXT")
    RETURN_NAMES = ("output", "tblout", "dfamtblout", "aliscoresout")
    REQUIRED_EXECUTABLES = ["nhmmer"]
    DOCUMENTATION_URL = "http://hmmer.org/documentation.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btt403"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btt403"]
    CITATION_TEXT = "nhmmer: DNA homology search with profile HMMs."
    DEFAULT_OUTPUT_FORMATS = ("tblout", "dfamtblout")

    @classmethod
    def _add_output_format_flags(cls, cmd: list[str], inputs: dict[str, Any], out: str) -> None:
        output_formats = set(cls._output_formats(inputs))
        if "tblout" in output_formats:
            cmd.extend(["--tblout", f"{out}/results.tblout"])
        if "dfamtblout" in output_formats:
            cmd.extend(["--dfamtblout", f"{out}/dfam.tblout"])
        if "aliscoresout" in output_formats:
            cmd.extend(["--aliscoresout", f"{out}/alignment_scores.txt"])

    @classmethod
    def _add_thresholds(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        threshold_mode = str(inputs.get("threshold_mode", "evalue"))
        if threshold_mode == "score":
            _add_if_value(cmd, "-T", inputs.get("score_threshold"))
            _add_if_value(cmd, "--incT", inputs.get("incT"))
        elif threshold_mode == "cut":
            cut_mode = str(inputs.get("cut_mode", "none"))
            if cut_mode != "none":
                cmd.append(cut_mode)
        else:
            _add_if_value(cmd, "-E", inputs.get("evalue", 10))
            _add_if_value(cmd, "--incE", inputs.get("incE"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ["nhmmer"]
        cls._add_output_format_flags(cmd, inputs, out)
        cls._add_output_options(cmd, inputs)
        cls._add_single_sequence_scoring(cmd, inputs)
        cls._add_thresholds(cmd, inputs)
        cls._add_acceleration_options(cmd, inputs)
        input_format = str(inputs.get("input_format_select", "--dna"))
        if input_format:
            cmd.append(input_format)
        cls._add_advanced_options(cmd, inputs)
        _add_if_value(cmd, "--w_beta", inputs.get("w_beta"))
        _add_if_value(cmd, "--w_length", inputs.get("w_length"))
        _add_if_value(cmd, "--cpu", max(1, int(inputs.get("threads", 1)) - 1))
        _add_if_value(cmd, "--seed", inputs.get("seed", 42))
        cmd.extend([str(inputs.get("hmmfile", "")), str(inputs.get("seqfile", ""))])
        _add_shell_redirect(cmd, f"{out}/output.txt")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> dict[str, Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = {"output": out / "output.txt"}
        output_formats = set(cls._output_formats(inputs))
        if "tblout" in output_formats:
            outputs["tblout"] = out / "results.tblout"
        if "dfamtblout" in output_formats:
            outputs["dfamtblout"] = out / "dfam.tblout"
        if "aliscoresout" in output_formats:
            outputs["aliscoresout"] = out / "alignment_scores.txt"
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "hmmfile": ("FILE", {"description": "Nucleotide profile HMM, alignment, or single-sequence query"}),
                "seqfile": ("FASTA", {"description": "Target nucleotide FASTA database"}),
            },
            "optional": {
                "output_formats": (
                    "STRING",
                    {
                        "default": ["tblout", "dfamtblout"],
                        "options": ["tblout", "dfamtblout", "aliscoresout"],
                        "list": True,
                        "description": "Additional tabular or positional score output files to write",
                    },
                ),
                "acc": ("BOOLEAN", {"default": False, "description": "Prefer accessions over names in output"}),
                "noali": ("BOOLEAN", {"default": False, "description": "Suppress alignment blocks in text output"}),
                "notextw": ("BOOLEAN", {"default": False, "description": "Use unlimited text output line width"}),
                "single_sequence_scoring": (
                    "STRING",
                    {"default": "false", "options": ["false", "singlemx"], "description": "Single-sequence scoring mode"},
                ),
                "popen": (
                    "FLOAT",
                    {
                        "default": 0.02,
                        "min": 0,
                        "max": 0.5,
                        "description": "Gap open probability for singlemx",
                        "displayOptions": {"show": {"single_sequence_scoring": ["singlemx"]}},
                    },
                ),
                "pextend": (
                    "FLOAT",
                    {
                        "default": 0.4,
                        "min": 0,
                        "max": 1,
                        "description": "Gap extend probability for singlemx",
                        "displayOptions": {"show": {"single_sequence_scoring": ["singlemx"]}},
                    },
                ),
                "threshold_mode": (
                    "STRING",
                    {
                        "default": "evalue",
                        "options": ["evalue", "score", "cut"],
                        "description": "Reporting threshold mode",
                    },
                ),
                "evalue": (
                    "FLOAT",
                    {
                        "default": 10,
                        "min": 0,
                        "description": "E-value reporting threshold",
                        "displayOptions": {"show": {"threshold_mode": ["evalue"]}},
                    },
                ),
                "incE": (
                    "FLOAT",
                    {
                        "default": "",
                        "description": "E-value inclusion threshold",
                        "advanced": True,
                        "displayOptions": {"show": {"threshold_mode": ["evalue"]}},
                    },
                ),
                "score_threshold": (
                    "FLOAT",
                    {
                        "default": "",
                        "description": "Bit score reporting threshold",
                        "displayOptions": {"show": {"threshold_mode": ["score"]}},
                    },
                ),
                "incT": (
                    "FLOAT",
                    {
                        "default": "",
                        "description": "Bit score inclusion threshold",
                        "advanced": True,
                        "displayOptions": {"show": {"threshold_mode": ["score"]}},
                    },
                ),
                "cut_mode": (
                    "STRING",
                    {
                        "default": "none",
                        "options": ["none", "--cut_ga", "--cut_nc", "--cut_tc"],
                        "description": "Use model-specific GA, NC, or TC cutoffs",
                        "advanced": True,
                        "displayOptions": {"show": {"threshold_mode": ["cut"]}},
                    },
                ),
                "max": ("BOOLEAN", {"default": False, "description": "Turn all heuristic filters off", "advanced": True}),
                "F1": ("FLOAT", {"default": 0.02, "min": 0, "advanced": True}),
                "F2": ("FLOAT", {"default": 0.001, "min": 0, "advanced": True}),
                "F3": ("FLOAT", {"default": 1e-5, "min": 0, "advanced": True}),
                "nobias": ("BOOLEAN", {"default": False, "description": "Turn off composition bias filter", "advanced": True}),
                "input_format_select": (
                    "STRING",
                    {
                        "default": "--dna",
                        "options": ["--dna", "--rna"],
                        "description": "Alphabet for the query model and target sequences",
                    },
                ),
                "nonull2": ("BOOLEAN", {"default": False, "description": "Turn off biased composition score corrections", "advanced": True}),
                "z": ("INT", {"default": "", "description": "Comparisons for E-value calculation", "advanced": True}),
                "domz": ("INT", {"default": "", "description": "Significant sequences for domain E-value calculation", "advanced": True}),
                "w_beta": ("FLOAT", {"default": "", "advanced": True, "description": "Tail mass at which nhmmer sets window length"}),
                "w_length": ("INT", {"default": "", "advanced": True, "description": "Override nhmmer window length"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "seed": ("INT", {"default": 42, "min": 0, "description": "Random seed; 0 chooses a random seed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HMMERNhmmscanNode(HMMERNhmmerNode):
    """Search nucleotide sequences against a nucleotide profile HMM database."""

    NODE_ID = "hmmer_nhmmscan"
    DISPLAY_NAME = "HMMER nhmmscan"
    DESCRIPTION = "Search nucleotide sequences against a nucleotide profile HMM database."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "hmmer",
        "nhmmscan",
        "Dfam scan",
        "DNA profile database",
        "nucleotide profiles",
    ]
    REQUIRED_EXECUTABLES = ["nhmmscan", "hmmpress"]

    @classmethod
    def _hmm_database(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get("hmm_source", "history")) == "indexed":
            return str(inputs.get("hmmdb", ""))
        return str(inputs.get("hmmfile", ""))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        hmm_database = cls._hmm_database(inputs)
        cmd: list[str] = []
        if str(inputs.get("hmm_source", "history")) == "history":
            cmd.extend(["hmmpress", hmm_database, "&&"])
        cmd.append("nhmmscan")
        cls._add_output_format_flags(cmd, inputs, out)
        cls._add_output_options(cmd, inputs)
        cls._add_thresholds(cmd, inputs)
        cls._add_acceleration_options(cmd, inputs)
        _add_if_value(cmd, "--B1", inputs.get("B1", 110))
        _add_if_value(cmd, "--B2", inputs.get("B2", 240))
        _add_if_value(cmd, "--B3", inputs.get("B3", 1000))
        cls._add_advanced_options(cmd, inputs)
        _add_if_value(cmd, "--w_beta", inputs.get("w_beta"))
        _add_if_value(cmd, "--w_length", inputs.get("w_length"))
        _add_if_value(cmd, "--cpu", max(1, int(inputs.get("threads", 1)) - 1))
        _add_if_value(cmd, "--seed", inputs.get("seed", 42))
        cmd.extend([hmm_database, str(inputs.get("seqfile", ""))])
        _add_shell_redirect(cmd, f"{out}/output.txt")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "hmm_source": (
                    "STRING",
                    {
                        "default": "history",
                        "options": ["history", "indexed"],
                        "description": "Use a workflow HMM database or an already indexed database path",
                    },
                ),
                "hmmfile": (
                    "FILE",
                    {
                        "default": "",
                        "description": "Nucleotide profile HMM database from the workflow history",
                        "displayOptions": {"show": {"hmm_source": ["history"]}},
                    },
                ),
                "hmmdb": (
                    "FILE",
                    {
                        "default": "",
                        "description": "Pre-indexed nucleotide profile HMM database",
                        "displayOptions": {"show": {"hmm_source": ["indexed"]}},
                    },
                ),
                "seqfile": ("FASTA", {"description": "Nucleotide sequence FASTA queries"}),
            },
            "optional": {
                "output_formats": (
                    "STRING",
                    {
                        "default": ["tblout", "dfamtblout"],
                        "options": ["tblout", "dfamtblout", "aliscoresout"],
                        "list": True,
                        "description": "Additional tabular or positional score output files to write",
                    },
                ),
                "acc": ("BOOLEAN", {"default": False, "description": "Prefer accessions over names in output"}),
                "noali": ("BOOLEAN", {"default": False, "description": "Suppress alignment blocks in text output"}),
                "notextw": ("BOOLEAN", {"default": False, "description": "Use unlimited text output line width"}),
                "threshold_mode": (
                    "STRING",
                    {
                        "default": "evalue",
                        "options": ["evalue", "score", "cut"],
                        "description": "Reporting threshold mode",
                    },
                ),
                "evalue": (
                    "FLOAT",
                    {
                        "default": 10,
                        "min": 0,
                        "description": "E-value reporting threshold",
                        "displayOptions": {"show": {"threshold_mode": ["evalue"]}},
                    },
                ),
                "incE": (
                    "FLOAT",
                    {
                        "default": "",
                        "description": "E-value inclusion threshold",
                        "advanced": True,
                        "displayOptions": {"show": {"threshold_mode": ["evalue"]}},
                    },
                ),
                "score_threshold": (
                    "FLOAT",
                    {
                        "default": "",
                        "description": "Bit score reporting threshold",
                        "displayOptions": {"show": {"threshold_mode": ["score"]}},
                    },
                ),
                "incT": (
                    "FLOAT",
                    {
                        "default": "",
                        "description": "Bit score inclusion threshold",
                        "advanced": True,
                        "displayOptions": {"show": {"threshold_mode": ["score"]}},
                    },
                ),
                "cut_mode": (
                    "STRING",
                    {
                        "default": "none",
                        "options": ["none", "--cut_ga", "--cut_nc", "--cut_tc"],
                        "description": "Use model-specific GA, NC, or TC cutoffs",
                        "advanced": True,
                        "displayOptions": {"show": {"threshold_mode": ["cut"]}},
                    },
                ),
                "max": ("BOOLEAN", {"default": False, "description": "Turn all heuristic filters off", "advanced": True}),
                "F1": ("FLOAT", {"default": 0.02, "min": 0, "advanced": True}),
                "F2": ("FLOAT", {"default": 0.001, "min": 0, "advanced": True}),
                "F3": ("FLOAT", {"default": 1e-5, "min": 0, "advanced": True}),
                "nobias": ("BOOLEAN", {"default": False, "description": "Turn off composition bias filter", "advanced": True}),
                "B1": ("INT", {"default": 110, "min": 1, "description": "MSV biased-composition modifier window length", "advanced": True}),
                "B2": ("INT", {"default": 240, "min": 1, "description": "Viterbi biased-composition modifier window length", "advanced": True}),
                "B3": ("INT", {"default": 1000, "min": 1, "description": "Forward biased-composition modifier window length", "advanced": True}),
                "nonull2": ("BOOLEAN", {"default": False, "description": "Turn off biased composition score corrections", "advanced": True}),
                "z": ("INT", {"default": "", "description": "Comparisons for E-value calculation", "advanced": True}),
                "domz": ("INT", {"default": "", "description": "Significant sequences for domain E-value calculation", "advanced": True}),
                "w_beta": ("FLOAT", {"default": "", "advanced": True, "description": "Tail mass at which nhmmscan sets window length"}),
                "w_length": ("INT", {"default": "", "advanced": True, "description": "Override nhmmscan window length"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "seed": ("INT", {"default": 42, "min": 0, "description": "Random seed; 0 chooses a random seed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HMMERHmmsearchNode(CommandNode):
    """Search sequence databases with profile HMMs using hmmsearch."""

    NODE_ID = "hmmer_hmmsearch"
    DISPLAY_NAME = "HMMER hmmsearch"
    REQUIRED_CONDA_PACKAGES = ["hmmer"]
    CATEGORY = "annotation"
    DESCRIPTION = "Search one or more profile HMMs against a sequence FASTA database."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "hmmer", "hmmsearch", "profile hmm", "domain search"]
    RETURN_TYPES = ("STATS_FILE", "TSV", "TSV", "TSV")
    RETURN_NAMES = ("output", "tblout", "domtblout", "pfamtblout")
    REQUIRED_EXECUTABLES = ["hmmsearch"]
    DOCUMENTATION_URL = "http://hmmer.org/documentation.html"
    CITATION_DOIS = ["10.1093/nar/gkr367"]
    CITATION_URLS = ["https://doi.org/10.1093/nar/gkr367"]
    CITATION_TEXT = "Accelerated profile HMM searches."
    VERSION = "3.4"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["hmmsearch", "--cpu", str(inputs.get("threads", 1))]
        _add_if_value(cmd, "-E", inputs.get("evalue"))
        _add_if_value(cmd, "--incE", inputs.get("incE"))
        _add_if_value(cmd, "--domE", inputs.get("domE"))
        _add_if_value(cmd, "--incdomE", inputs.get("incdomE"))
        if inputs.get("cut_ga"):
            cmd.append("--cut_ga")
        if inputs.get("cut_tc"):
            cmd.append("--cut_tc")
        if inputs.get("cut_nc"):
            cmd.append("--cut_nc")
        if inputs.get("notextw"):
            cmd.append("--notextw")
        out = _out(inputs)
        cmd.extend([
            "--tblout",
            f"{out}/results.tblout",
            "--domtblout",
            f"{out}/domains.domtblout",
            "--pfamtblout",
            f"{out}/pfam.tblout",
            "-o",
            f"{out}/output.txt",
            str(inputs.get("hmmfile", "")),
            str(inputs.get("seqdb", "")),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.txt", out / "results.tblout", out / "domains.domtblout", out / "pfam.tblout"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "hmmfile": ("FILE", {"description": "Profile HMM file"}),
                "seqdb": ("FASTA", {"description": "Sequence database FASTA"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "evalue": ("FLOAT", {"default": 10, "min": 0}),
                "incE": ("FLOAT", {"default": "", "advanced": True}),
                "domE": ("FLOAT", {"default": "", "advanced": True}),
                "incdomE": ("FLOAT", {"default": "", "advanced": True}),
                "cut_ga": ("BOOLEAN", {"default": False, "advanced": True}),
                "cut_tc": ("BOOLEAN", {"default": False, "advanced": True}),
                "cut_nc": ("BOOLEAN", {"default": False, "advanced": True}),
                "notextw": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class HMMERHmmscanNode(HMMERHmmsearchNode):
    """Search sequences against a profile HMM database using hmmscan."""

    NODE_ID = "hmmer_hmmscan"
    DISPLAY_NAME = "HMMER hmmscan"
    DESCRIPTION = "Search protein sequences against a profile HMM database."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "hmmer", "hmmscan", "pfam", "domain annotation"]
    REQUIRED_EXECUTABLES = ["hmmscan"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["hmmscan", "--cpu", str(inputs.get("threads", 1))]
        _add_if_value(cmd, "-E", inputs.get("evalue"))
        _add_if_value(cmd, "--incE", inputs.get("incE"))
        _add_if_value(cmd, "--domE", inputs.get("domE"))
        _add_if_value(cmd, "--incdomE", inputs.get("incdomE"))
        if inputs.get("cut_ga"):
            cmd.append("--cut_ga")
        if inputs.get("cut_tc"):
            cmd.append("--cut_tc")
        if inputs.get("cut_nc"):
            cmd.append("--cut_nc")
        if inputs.get("notextw"):
            cmd.append("--notextw")
        out = _out(inputs)
        cmd.extend([
            "--tblout",
            f"{out}/results.tblout",
            "--domtblout",
            f"{out}/domains.domtblout",
            "--pfamtblout",
            f"{out}/pfam.tblout",
            "-o",
            f"{out}/output.txt",
            str(inputs.get("hmmdb", "")),
            str(inputs.get("seqfile", "")),
        ])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "seqfile": ("FASTA", {"description": "Sequence FASTA"}),
                "hmmdb": ("FILE", {"description": "Profile HMM database"}),
            },
            "optional": HMMERHmmsearchNode.INPUT_TYPES()["optional"],
            "hidden": {"output": ("STRING", {})},
        }

class MMseqs2EasySearchNode(CommandNode):
    """Run MMseqs2 easy-search for sensitive sequence homology search."""

    NODE_ID = "mmseqs2_easy_search"
    DISPLAY_NAME = "MMseqs2 Easy Search"
    REQUIRED_CONDA_PACKAGES = ["mmseqs2"]
    CATEGORY = "alignment"
    DESCRIPTION = "Run MMseqs2 easy-search for protein, nucleotide, or translated homology searches."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "mmseqs2", "mmseqs", "easy-search", "homology", "sequence search"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("search_results",)
    REQUIRED_EXECUTABLES = ["mmseqs"]
    DOCUMENTATION_URL = "https://github.com/soedinglab/MMseqs2/wiki"
    CITATION_DOIS = [
        "10.1038/nbt.3988",
        "10.1038/s41467-018-04964-5",
        "10.1093/bioinformatics/btab184",
    ]
    CITATION_URLS = [
        "https://doi.org/10.1038/nbt.3988",
        "https://doi.org/10.1038/s41467-018-04964-5",
        "https://doi.org/10.1093/bioinformatics/btab184",
    ]
    CITATION_TEXT = "MMseqs2 enables sensitive protein sequence searching for the analysis of massive data sets."
    VERSION = "17-b804f"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = [
            "mmseqs",
            "easy-search",
            str(inputs.get("query_fasta", "")),
            str(inputs.get("target_fasta", inputs.get("target_database", ""))),
            f"{out}/search_results",
            f"{out}/tmp",
            "--search-type",
            str(inputs.get("search_type", 0)),
            "-s",
            str(inputs.get("sensitivity", 5.7)),
            "-e",
            str(inputs.get("evalue", 0.001)),
            "--min-seq-id",
            str(inputs.get("min_seq_id", 0.0)),
            "-c",
            str(inputs.get("cov", 0.0)),
            "--cov-mode",
            str(inputs.get("cov_mode", 0)),
        ]
        _add_if_value(cmd, "--format-output", inputs.get("format_output", "query,target,pident,evalue,bits"))
        _add_if_value(cmd, "--num-iterations", inputs.get("num_iterations", 1))
        cmd.extend(["--threads", str(inputs.get("threads", 1))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "search_results"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query_fasta": ("FASTA", {"description": "Query FASTA/Q file"}),
                "target_fasta": ("FASTA", {"description": "Target FASTA database"}),
            },
            "optional": {
                "search_type": ("INT", {"default": 0, "min": 0, "max": 4, "description": "0 auto, 1 amino acid, 2 translated, 3 nucleotide, 4 translated nucleotide"}),
                "sensitivity": ("FLOAT", {"default": 5.7, "min": 1, "max": 15}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0}),
                "min_seq_id": ("FLOAT", {"default": 0.0, "min": 0, "max": 1}),
                "cov": ("FLOAT", {"default": 0.0, "min": 0, "max": 1}),
                "cov_mode": ("INT", {"default": 0, "min": 0, "max": 5}),
                "format_output": ("STRING", {"default": "query,target,pident,evalue,bits"}),
                "num_iterations": ("INT", {"default": 1, "min": 1, "max": 20, "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MMseqs2EasyClusterNode(CommandNode):
    """Cluster protein or nucleotide sequences with MMseqs2 easy-cluster."""

    NODE_ID = "mmseqs2_easy_cluster"
    DISPLAY_NAME = "MMseqs2 Easy Cluster"
    REQUIRED_CONDA_PACKAGES = ["mmseqs2"]
    CATEGORY = "clustering"
    DESCRIPTION = "Cluster protein or nucleotide sequences with MMseqs2 cascaded clustering."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mmseqs2",
        "mmseqs",
        "easy-cluster",
        "cascaded clustering",
        "sequence clustering",
    ]
    RETURN_TYPES = ("FASTA", "FASTA", "TSV")
    RETURN_NAMES = ("representative_sequences", "clustered_sequences", "cluster_tsv")
    REQUIRED_EXECUTABLES = ["mmseqs"]
    DOCUMENTATION_URL = "https://github.com/soedinglab/MMseqs2/wiki"
    CITATION_DOIS = MMseqs2EasySearchNode.CITATION_DOIS
    CITATION_URLS = MMseqs2EasySearchNode.CITATION_URLS
    CITATION_TEXT = MMseqs2EasySearchNode.CITATION_TEXT
    VERSION = MMseqs2EasySearchNode.VERSION
    SHELL = True

    @classmethod
    def _input_link_name(cls, input_fasta: Any) -> str:
        suffixes = Path(str(input_fasta or "")).suffixes
        if suffixes[-2:] == [".fasta", ".gz"]:
            return "input.fasta.gz"
        if suffixes[-2:] == [".fa", ".gz"]:
            return "input.fa.gz"
        if suffixes and suffixes[-1].lower() in {".fasta", ".fa", ".faa", ".fna", ".ffn", ".gz"}:
            return f"input{suffixes[-1].lower()}"
        return "input.fasta"

    @classmethod
    def _add_dbtype_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        dbtype = str(inputs.get("dbtype", "0"))
        if dbtype == "1":
            _add_if_value(cmd, "--comp-bias-corr-scale", inputs.get("comp_bias_corr_scale", 1))
        elif dbtype == "2":
            _add_if_value(cmd, "--zdrop", inputs.get("zdrop", 40))
        cmd.extend(["--dbtype", dbtype])

    @classmethod
    def _add_prefilter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--add-self-matches",
                str(inputs.get("add_self_matches", 0)),
                "-k",
                str(inputs.get("kmer_length", 0)),
                "--mask",
                str(inputs.get("mask", 1)),
                "--mask-prob",
                str(inputs.get("mask_prob", 0.9)),
                "--mask-lower-case",
                str(inputs.get("mask_lower_case", 0)),
                "--mask-n-repeat",
                str(inputs.get("mask_n_repeat", 0)),
                "--spaced-kmer-mode",
                str(inputs.get("spaced_kmer_mode", 1)),
                "-s",
                str(inputs.get("sensitivity", 5.7)),
                "--max-seqs",
                str(inputs.get("max_seqs", 300)),
                "--split",
                str(inputs.get("split", 0)),
                "--split-mode",
                str(inputs.get("split_mode", 2)),
                "--diag-score",
                str(inputs.get("diag_score", 1)),
                "--exact-kmer-matching",
                str(inputs.get("exact_kmer_matching", 0)),
                "--min-ungapped-score",
                str(inputs.get("min_ungapped_score", 15)),
            ]
        )

    @classmethod
    def _add_align_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "-a",
                str(inputs.get("convertalis", 0)),
                "--alignment-output-mode",
                str(inputs.get("alignment_output_mode", 0)),
                "--wrapped-scoring",
                str(inputs.get("wrapped_scoring", 0)),
                "--min-aln-len",
                str(inputs.get("min_aln_len", 0)),
                "--seq-id-mode",
                str(inputs.get("seq_id_mode", 0)),
                "--alt-ali",
                str(inputs.get("alt_ali", 0)),
                "--score-bias",
                str(inputs.get("score_bias", 0)),
                "--realign",
                str(inputs.get("realign", 0)),
                "--realign-score-bias",
                str(inputs.get("realign_score_bias", -0.2)),
                "--realign-max-seqs",
                str(inputs.get("realign_max_seqs", 2147483647)),
                "--corr-score-weight",
                str(inputs.get("corr_score_weight", 0)),
                "--alignment-mode",
                str(inputs.get("alignment_mode", 0)),
                "-e",
                str(inputs.get("evalue", 0.001)),
                "--min-seq-id",
                str(inputs.get("min_seq_id", 0.3)),
                "-c",
                str(inputs.get("cov", 0.8)),
                "--cov-mode",
                str(inputs.get("cov_mode", 0)),
                "--max-rejected",
                str(inputs.get("max_rejected", 2147483647)),
                "--max-accept",
                str(inputs.get("max_accept", 2147483647)),
            ]
        )

    @classmethod
    def _add_clustering_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--cluster-mode",
                str(inputs.get("cluster_mode", 0)),
                "--max-iterations",
                str(inputs.get("max_iterations", 1000)),
                "--similarity-type",
                str(inputs.get("similarity_type", 2)),
            ]
        )

    @classmethod
    def _add_misc_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--rescore-mode",
                str(inputs.get("rescore_mode", 0)),
                "--shuffle",
                str(inputs.get("shuffle", 1)),
                "--id-offset",
                str(inputs.get("id_offset", 0)),
                "--threads",
                str(inputs.get("threads", 1)),
                "--max-seq-len",
                str(inputs.get("max_seq_len", 65535)),
                "--filter-hits",
                str(inputs.get("filter_hits", 0)),
                "--sort-results",
                str(inputs.get("sort_results", 0)),
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_fasta = str(inputs.get("input_fasta", ""))
        linked_input = cls._input_link_name(input_fasta)
        cmd = ["mmseqs", "easy-cluster", linked_input, f"{out}/result", f"{out}/tmp"]
        cls._add_dbtype_options(cmd, inputs)
        cls._add_prefilter_options(cmd, inputs)
        cls._add_align_options(cmd, inputs)
        cls._add_clustering_options(cmd, inputs)
        cls._add_misc_options(cmd, inputs)
        return f"ln -sf {shlex.quote(input_fasta)} {shlex.quote(linked_input)} && {shlex.join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        selected = set(_as_list(inputs.get("output_selection")))
        if not selected:
            selected = {"file_rep_seq", "file_all_seq", "file_cluster_tsv"}
        outputs = {
            "file_rep_seq": out / "result_rep_seq.fasta",
            "file_all_seq": out / "result_all_seqs.fasta",
            "file_cluster_tsv": out / "result_cluster.tsv",
        }
        return [path for key, path in outputs.items() if key in selected]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Protein or nucleotide FASTA sequences to cluster"}),
            },
            "optional": {
                "dbtype": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2"],
                        "description": "Input data type: automatic, amino acid, or nucleotide",
                    },
                ),
                "comp_bias_corr_scale": (
                    "FLOAT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["1"]}},
                    },
                ),
                "zdrop": (
                    "INT",
                    {
                        "default": 40,
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["2"]}},
                    },
                ),
                "add_self_matches": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "kmer_length": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "mask": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "mask_prob": ("FLOAT", {"default": 0.9, "min": 0, "advanced": True}),
                "mask_lower_case": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "mask_n_repeat": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "spaced_kmer_mode": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "sensitivity": ("FLOAT", {"default": 5.7, "min": 1, "max": 7.5}),
                "max_seqs": ("INT", {"default": 300, "min": 0, "advanced": True}),
                "split": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "split_mode": ("STRING", {"default": "2", "options": ["0", "1", "2"], "advanced": True}),
                "diag_score": ("INT", {"default": 1, "min": 0, "max": 1, "advanced": True}),
                "exact_kmer_matching": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_ungapped_score": ("INT", {"default": 15, "min": 0, "advanced": True}),
                "convertalis": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "alignment_output_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"], "advanced": True}),
                "wrapped_scoring": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_aln_len": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "seq_id_mode": ("STRING", {"default": "0", "options": ["0", "1", "2"], "advanced": True}),
                "alt_ali": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "score_bias": ("FLOAT", {"default": 0, "advanced": True}),
                "realign": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "realign_score_bias": ("FLOAT", {"default": -0.2, "advanced": True}),
                "realign_max_seqs": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "corr_score_weight": ("FLOAT", {"default": 0, "advanced": True}),
                "alignment_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0}),
                "min_seq_id": ("FLOAT", {"default": 0.3, "min": 0, "max": 1}),
                "cov": ("FLOAT", {"default": 0.8, "min": 0, "max": 1}),
                "cov_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"]}),
                "max_rejected": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "max_accept": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "cluster_mode": ("STRING", {"default": "0", "options": ["0", "1", "2"]}),
                "max_iterations": ("INT", {"default": 1000, "min": 0, "advanced": True}),
                "similarity_type": ("STRING", {"default": "2", "options": ["1", "2"], "advanced": True}),
                "rescore_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True}),
                "shuffle": ("INT", {"default": 1, "min": 0, "max": 1, "advanced": True}),
                "id_offset": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "max_seq_len": ("INT", {"default": 65535, "min": 1, "advanced": True}),
                "filter_hits": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "sort_results": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "output_selection": (
                    "STRING",
                    {
                        "default": ["file_rep_seq", "file_all_seq", "file_cluster_tsv"],
                        "options": ["file_rep_seq", "file_all_seq", "file_cluster_tsv"],
                        "list": True,
                        "description": "MMseqs2 easy-cluster output files to keep",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MMseqs2EasyLinclustNode(MMseqs2EasyClusterNode):
    """Cluster very large sequence sets in linear time with MMseqs2 Linclust."""

    NODE_ID = "mmseqs2_easy_linclust_clustering"
    DISPLAY_NAME = "MMseqs2 Easy Linclust"
    DESCRIPTION = "Cluster very large protein or nucleotide datasets in linear time with MMseqs2 Linclust."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mmseqs2",
        "mmseqs",
        "easy-linclust",
        "linclust",
        "linear clustering",
    ]
    CITATION_DOIS = [
        "10.1038/s41467-018-04964-5",
        *MMseqs2EasySearchNode.CITATION_DOIS,
    ]
    CITATION_URLS = [f"{DOI_URL}10.1038/s41467-018-04964-5", *MMseqs2EasySearchNode.CITATION_URLS]
    CITATION_TEXT = "Clustering huge protein sequence sets in linear time."

    @classmethod
    def _add_dbtype_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        dbtype = str(inputs.get("dbtype", "0"))
        if dbtype == "1":
            _add_if_value(cmd, "--comp-bias-corr-scale", inputs.get("comp_bias_corr_scale", 1))
            _add_if_value(cmd, "--kmer-per-seq-scale", inputs.get("kmer_per_seq_scale", 0.0))
        elif dbtype == "2":
            _add_if_value(cmd, "--zdrop", inputs.get("zdrop", 40))
            _add_if_value(cmd, "--kmer-per-seq-scale", inputs.get("kmer_per_seq_scale", 0.0))
            _add_if_value(cmd, "--adjust-kmer-len", inputs.get("adjust_kmer_len", 0))
        cmd.extend(["--dbtype", dbtype])

    @classmethod
    def _add_prefilter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--add-self-matches",
                str(inputs.get("add_self_matches", 0)),
                "-k",
                str(inputs.get("kmer_length", 0)),
                "--mask",
                str(inputs.get("mask", 1)),
                "--mask-prob",
                str(inputs.get("mask_prob", 0.9)),
                "--mask-lower-case",
                str(inputs.get("mask_lower_case", 0)),
                "--mask-n-repeat",
                str(inputs.get("mask_n_repeat", 0)),
                "--spaced-kmer-mode",
                str(inputs.get("spaced_kmer_mode", 0)),
            ]
        )

    @classmethod
    def _add_kmermatcher_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--cluster-weight-threshold",
                str(inputs.get("cluster_weight_threshold", 0.9)),
                "--kmer-per-seq",
                str(inputs.get("kmer_per_seq", 21)),
                "--hash-shift",
                str(inputs.get("hash_shift", 67)),
                "--include-only-extendable",
                str(inputs.get("include_only_extendable", 0)),
                "--ignore-multi-kmer",
                str(inputs.get("ignore_multi_kmer", 0)),
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_fasta = str(inputs.get("input_fasta", ""))
        linked_input = cls._input_link_name(input_fasta)
        effective_inputs = dict(inputs)
        effective_inputs.setdefault("min_seq_id", 0)
        cmd = ["mmseqs", "easy-linclust", linked_input, f"{out}/result", f"{out}/tmp"]
        cls._add_dbtype_options(cmd, effective_inputs)
        cls._add_prefilter_options(cmd, effective_inputs)
        cls._add_align_options(cmd, effective_inputs)
        cls._add_clustering_options(cmd, effective_inputs)
        cls._add_kmermatcher_options(cmd, effective_inputs)
        cls._add_misc_options(cmd, effective_inputs)
        return f"ln -sf {shlex.quote(input_fasta)} {shlex.quote(linked_input)} && {shlex.join(cmd)}"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Protein or nucleotide FASTA sequences to cluster"}),
            },
            "optional": {
                "dbtype": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2"],
                        "description": "Input data type: automatic, amino acid, or nucleotide",
                    },
                ),
                "comp_bias_corr_scale": (
                    "FLOAT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["1"]}},
                    },
                ),
                "zdrop": (
                    "INT",
                    {
                        "default": 40,
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["2"]}},
                    },
                ),
                "kmer_per_seq_scale": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["1", "2"]}},
                    },
                ),
                "adjust_kmer_len": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["2"]}},
                    },
                ),
                "add_self_matches": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "kmer_length": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "mask": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "mask_prob": ("FLOAT", {"default": 0.9, "min": 0, "advanced": True}),
                "mask_lower_case": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "mask_n_repeat": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "spaced_kmer_mode": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "convertalis": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "alignment_output_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"], "advanced": True}),
                "wrapped_scoring": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_aln_len": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "seq_id_mode": ("STRING", {"default": "0", "options": ["0", "1", "2"], "advanced": True}),
                "alt_ali": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "score_bias": ("FLOAT", {"default": 0, "advanced": True}),
                "realign": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "realign_score_bias": ("FLOAT", {"default": -0.2, "advanced": True}),
                "realign_max_seqs": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "corr_score_weight": ("FLOAT", {"default": 0, "advanced": True}),
                "alignment_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0}),
                "min_seq_id": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "cov": ("FLOAT", {"default": 0.8, "min": 0, "max": 1}),
                "cov_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"]}),
                "max_rejected": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "max_accept": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "cluster_mode": ("STRING", {"default": "0", "options": ["0", "1", "2"]}),
                "max_iterations": ("INT", {"default": 1000, "min": 0, "advanced": True}),
                "similarity_type": ("STRING", {"default": "2", "options": ["1", "2"], "advanced": True}),
                "cluster_weight_threshold": ("FLOAT", {"default": 0.9, "min": 0, "advanced": True}),
                "kmer_per_seq": ("INT", {"default": 21, "min": 1, "advanced": True}),
                "hash_shift": ("INT", {"default": 67, "min": 0, "advanced": True}),
                "include_only_extendable": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "ignore_multi_kmer": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "rescore_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True}),
                "shuffle": ("INT", {"default": 1, "min": 0, "max": 1, "advanced": True}),
                "id_offset": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "max_seq_len": ("INT", {"default": 65535, "min": 1, "advanced": True}),
                "filter_hits": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "sort_results": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "output_selection": (
                    "STRING",
                    {
                        "default": ["file_rep_seq", "file_all_seq", "file_cluster_tsv"],
                        "options": ["file_rep_seq", "file_all_seq", "file_cluster_tsv"],
                        "list": True,
                        "description": "MMseqs2 easy-linclust output files to keep",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MMseqs2EasyLinsearchNode(CommandNode):
    """Run MMseqs2 easy-linsearch for linear-time homology search."""

    NODE_ID = "mmseqs2_easy_linsearch"
    DISPLAY_NAME = "MMseqs2 Easy Linsearch"
    REQUIRED_CONDA_PACKAGES = ["mmseqs2"]
    CATEGORY = "alignment"
    DESCRIPTION = "Run fast linear-time homology searches against large MMseqs2 target databases."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mmseqs2",
        "mmseqs",
        "easy-linsearch",
        "linsearch",
        "linear homology search",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("search_results",)
    REQUIRED_EXECUTABLES = ["mmseqs"]
    DOCUMENTATION_URL = MMseqs2EasySearchNode.DOCUMENTATION_URL
    CITATION_DOIS = ["10.1038/nbt.3988"]
    CITATION_URLS = [f"{DOI_URL}10.1038/nbt.3988"]
    CITATION_TEXT = MMseqs2EasySearchNode.CITATION_TEXT
    VERSION = MMseqs2EasySearchNode.VERSION
    SHELL = True

    @classmethod
    def _sequence_link_name(cls, prefix: str, source: Any) -> str:
        suffixes = [suffix.lower() for suffix in Path(str(source or "")).suffixes]
        allowed_exts = {"fasta", "fa", "fastq", "fq", "faa", "fna", "ffn"}
        if len(suffixes) >= 2 and suffixes[-1] == ".gz":
            ext = suffixes[-2].lstrip(".").replace("sanger", "").replace("illumina", "")
            if ext in allowed_exts:
                return f"{prefix}.{ext}.gz"
        if suffixes:
            ext = suffixes[-1].lstrip(".").replace("sanger", "").replace("illumina", "")
            if ext in allowed_exts:
                return f"{prefix}.{ext}"
        return f"{prefix}.fasta"

    @classmethod
    def _add_prefilter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--add-self-matches",
                str(inputs.get("add_self_matches", 0)),
                "--mask",
                str(inputs.get("mask", 1)),
                "--mask-prob",
                str(inputs.get("mask_prob", 0.9)),
                "--mask-lower-case",
                str(inputs.get("mask_lower_case", 0)),
                "--mask-n-repeat",
                str(inputs.get("mask_n_repeat", 0)),
            ]
        )

    @classmethod
    def _add_kmermatcher_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(["--kmer-per-seq", str(inputs.get("kmer_per_seq", 21))])

    @classmethod
    def _add_misc_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--id-offset",
                str(inputs.get("id_offset", 0)),
            ]
        )

    @classmethod
    def _format_fields(cls, inputs: dict[str, Any]) -> str:
        fields = _as_list(
            inputs.get(
                "format_fields",
                ["query", "target", "pident", "evalue", "bits"],
            )
        )
        return ",".join(fields)

    @classmethod
    def _add_output_format_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        format_mode = str(inputs.get("format_mode", "0"))
        format_fields = cls._format_fields(inputs)
        if format_mode in {"0", "2", "4"} and format_fields:
            cmd.extend(["--format-output", format_fields])
        cmd.extend(["--format-mode", format_mode])

    @classmethod
    def _add_search_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--search-type",
                str(inputs.get("search_type", 0)),
                "--threads",
                str(inputs.get("threads", 1)),
                "--max-seq-len",
                str(inputs.get("max_seq_len", 65535)),
            ]
        )

    @classmethod
    def _target_command_part(cls, inputs: dict[str, Any], out: str) -> tuple[list[str], str]:
        if str(inputs.get("target_source", "history")) == "cached":
            database_root = str(inputs.get("target_database", ""))
            if inputs.get("create_linindex"):
                prelude = [
                    f"cp -r {shlex.quote(database_root)}/database* .",
                    f"mmseqs createlinindex database {shlex.quote(f'{out}/tmp')}",
                ]
                return prelude, "database"
            target = f"{database_root.rstrip('/')}/database" if database_root else "database"
            return [], target

        target_fasta = str(inputs.get("target_fasta", ""))
        linked_target = cls._sequence_link_name("target", target_fasta)
        return [f"ln -sf {shlex.quote(target_fasta)} {shlex.quote(linked_target)}"], linked_target

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        query_fasta = str(inputs.get("query_fasta", ""))
        linked_query = cls._sequence_link_name("query", query_fasta)
        prelude = [f"ln -sf {shlex.quote(query_fasta)} {shlex.quote(linked_query)}"]
        target_prelude, target = cls._target_command_part(inputs, out)
        prelude.extend(target_prelude)

        effective_inputs = dict(inputs)
        effective_inputs.setdefault("min_seq_id", 0)
        effective_inputs.setdefault("cov", 0)

        cmd = [
            "mmseqs",
            "easy-linsearch",
            linked_query,
            target,
            f"{out}/search_results",
            f"{out}/tmp",
        ]
        MMseqs2EasyLinclustNode._add_dbtype_options(cmd, effective_inputs)
        cls._add_prefilter_options(cmd, effective_inputs)
        MMseqs2EasyClusterNode._add_align_options(cmd, effective_inputs)
        cls._add_kmermatcher_options(cmd, effective_inputs)
        cls._add_misc_options(cmd, effective_inputs)
        cls._add_output_format_options(cmd, effective_inputs)
        cls._add_search_options(cmd, effective_inputs)
        return f"{' && '.join(prelude)} && {shlex.join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = {"1": "sam", "3": "html"}.get(str(inputs.get("format_mode", "0")), "tsv")
        return [out / f"search_results.{suffix}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query_fasta": ("FASTA", {"description": "Query FASTA/FASTQ file"}),
                "target_source": (
                    "STRING",
                    {
                        "default": "history",
                        "options": ["history", "cached"],
                        "description": "Use a target FASTA from history or a cached MMseqs2 database",
                    },
                ),
                "target_fasta": (
                    "FASTA",
                    {
                        "default": "",
                        "description": "Target FASTA/FASTQ file for history mode",
                        "displayOptions": {"show": {"target_source": ["history"]}},
                    },
                ),
                "target_database": (
                    "FILE",
                    {
                        "default": "",
                        "description": "Cached MMseqs2 database directory containing database* files",
                        "displayOptions": {"show": {"target_source": ["cached"]}},
                    },
                ),
            },
            "optional": {
                "dbtype": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2"],
                        "description": "Input data type: automatic, amino acid, or nucleotide",
                    },
                ),
                "comp_bias_corr_scale": (
                    "FLOAT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["1"]}},
                    },
                ),
                "zdrop": (
                    "INT",
                    {
                        "default": 40,
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["2"]}},
                    },
                ),
                "kmer_per_seq_scale": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["1", "2"]}},
                    },
                ),
                "adjust_kmer_len": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["2"]}},
                    },
                ),
                "add_self_matches": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "mask": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "mask_prob": ("FLOAT", {"default": 0.9, "min": 0, "advanced": True}),
                "mask_lower_case": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "mask_n_repeat": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "convertalis": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "alignment_output_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"], "advanced": True}),
                "wrapped_scoring": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_aln_len": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "seq_id_mode": ("STRING", {"default": "0", "options": ["0", "1", "2"], "advanced": True}),
                "alt_ali": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "score_bias": ("FLOAT", {"default": 0, "advanced": True}),
                "realign": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "realign_score_bias": ("FLOAT", {"default": -0.2, "advanced": True}),
                "realign_max_seqs": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "corr_score_weight": ("FLOAT", {"default": 0, "advanced": True}),
                "alignment_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0}),
                "min_seq_id": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "cov": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "cov_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"]}),
                "max_rejected": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "max_accept": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "kmer_per_seq": ("INT", {"default": 21, "min": 1, "advanced": True}),
                "id_offset": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "format_fields": (
                    "STRING",
                    {
                        "default": ["query", "target", "pident", "evalue", "bits"],
                        "options": [
                            "query",
                            "target",
                            "pident",
                            "alnlen",
                            "mismatch",
                            "gapopen",
                            "qstart",
                            "qend",
                            "tstart",
                            "tend",
                            "evalue",
                            "bits",
                            "qcov",
                            "tcov",
                        ],
                        "list": True,
                        "description": "Comma-separated fields for BLAST tabular-like output modes",
                    },
                ),
                "format_mode": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "4", "2", "1", "3"],
                        "description": "MMseqs2 output format mode: BLAST-like, SAM, or HTML",
                    },
                ),
                "search_type": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2", "3", "4"],
                        "description": "0 auto, 1 amino acid, 2 translated, 3 nucleotide, 4 translated nucleotide",
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "max_seq_len": ("INT", {"default": 65535, "min": 1, "advanced": True}),
                "create_linindex": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "advanced": True,
                        "description": "Create a linear index for copied cached database files before searching",
                        "displayOptions": {"show": {"target_source": ["cached"]}},
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MMseqs2EasyRBHNode(CommandNode):
    """Identify reciprocal best hits with MMseqs2 easy-rbh."""

    NODE_ID = "mmseqs2_easy_rbh"
    DISPLAY_NAME = "MMseqs2 Easy RBH"
    REQUIRED_CONDA_PACKAGES = ["mmseqs2"]
    CATEGORY = "alignment"
    DESCRIPTION = "Identify reciprocal best hits between two sequence sets for ortholog detection."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mmseqs2",
        "mmseqs",
        "easy-rbh",
        "reciprocal best hit",
        "ortholog detection",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("search_results",)
    REQUIRED_EXECUTABLES = ["mmseqs"]
    DOCUMENTATION_URL = MMseqs2EasySearchNode.DOCUMENTATION_URL
    CITATION_DOIS = ["10.1038/nbt.3988"]
    CITATION_URLS = [f"{DOI_URL}10.1038/nbt.3988"]
    CITATION_TEXT = MMseqs2EasySearchNode.CITATION_TEXT
    VERSION = MMseqs2EasySearchNode.VERSION
    SHELL = True

    @classmethod
    def _target_command_part(cls, inputs: dict[str, Any]) -> tuple[list[str], str]:
        if str(inputs.get("target_source", "history")) == "cached":
            database_root = str(inputs.get("target_database", ""))
            target = f"{database_root.rstrip('/')}/database" if database_root else "database"
            return [], target
        target_fasta = str(inputs.get("target_fasta", ""))
        linked_target = MMseqs2EasyLinsearchNode._sequence_link_name("target", target_fasta)
        return [f"ln -s {shlex.quote(target_fasta)} {shlex.quote(linked_target)}"], linked_target

    @classmethod
    def _add_prefilter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--add-self-matches",
                str(inputs.get("add_self_matches", 0)),
                "-k",
                str(inputs.get("kmer_length", 0)),
                "--mask",
                str(inputs.get("mask", 1)),
                "--mask-prob",
                str(inputs.get("mask_prob", 0.9)),
                "--mask-lower-case",
                str(inputs.get("mask_lower_case", 0)),
                "--mask-n-repeat",
                str(inputs.get("mask_n_repeat", 0)),
                "--spaced-kmer-mode",
                str(inputs.get("spaced_kmer_mode", 1)),
            ]
        )

    @classmethod
    def _add_search_common_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "-s",
                str(inputs.get("sensitivity", 5.7)),
                "--max-seqs",
                str(inputs.get("max_seqs", 300)),
                "--split",
                str(inputs.get("split", 0)),
                "--split-mode",
                str(inputs.get("split_mode", 2)),
                "--diag-score",
                str(inputs.get("diag_score", 1)),
                "--exact-kmer-matching",
                str(inputs.get("exact_kmer_matching", 0)),
                "--min-ungapped-score",
                str(inputs.get("min_ungapped_score", 15)),
            ]
        )

    @classmethod
    def _add_common_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--threads",
                str(inputs.get("threads", 1)),
                "--max-seq-len",
                str(inputs.get("max_seq_len", 65535)),
            ]
        )

    @classmethod
    def _add_expert_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--filter-hits",
                str(inputs.get("filter_hits", 0)),
                "--sort-results",
                str(inputs.get("sort_results", 0)),
                "--chain-alignments",
                str(inputs.get("chain_alignments", 0)),
                "--merge-query",
                str(inputs.get("merge_query", 1)),
                "--strand",
                str(inputs.get("strand", 1)),
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        query_fasta = str(inputs.get("query_fasta", ""))
        linked_query = MMseqs2EasyLinsearchNode._sequence_link_name("query", query_fasta)
        prelude = [f"ln -s {shlex.quote(query_fasta)} {shlex.quote(linked_query)}"]
        target_prelude, target = cls._target_command_part(inputs)
        prelude.extend(target_prelude)

        effective_inputs = dict(inputs)
        effective_inputs.setdefault("min_seq_id", 0)
        effective_inputs.setdefault("cov", 0)

        cmd = [
            "mmseqs",
            "easy-rbh",
            linked_query,
            target,
            f"{out}/search_results",
            f"{out}/tmp",
        ]
        MMseqs2EasyClusterNode._add_dbtype_options(cmd, effective_inputs)
        cls._add_prefilter_options(cmd, effective_inputs)
        cls._add_search_common_options(cmd, effective_inputs)
        MMseqs2EasyClusterNode._add_align_options(cmd, effective_inputs)
        MMseqs2EasyLinsearchNode._add_output_format_options(cmd, effective_inputs)
        cmd.extend(["--search-type", str(effective_inputs.get("search_type", 0))])
        cls._add_common_options(cmd, effective_inputs)
        cls._add_expert_options(cmd, effective_inputs)
        return f"{' && '.join(prelude)} && {shlex.join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        suffix = {"1": "sam", "3": "html"}.get(str(inputs.get("format_mode", "0")), "tsv")
        return [out / f"search_results.{suffix}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query_fasta": ("FASTA", {"description": "Query FASTA/FASTQ file"}),
                "target_source": (
                    "STRING",
                    {
                        "default": "history",
                        "options": ["history", "cached"],
                        "description": "Use a target FASTA from history or a cached MMseqs2 database",
                    },
                ),
                "target_fasta": (
                    "FASTA",
                    {
                        "default": "",
                        "description": "Target FASTA file for history mode",
                        "displayOptions": {"show": {"target_source": ["history"]}},
                    },
                ),
                "target_database": (
                    "FILE",
                    {
                        "default": "",
                        "description": "Cached MMseqs2 database directory containing database* files",
                        "displayOptions": {"show": {"target_source": ["cached"]}},
                    },
                ),
            },
            "optional": {
                "dbtype": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2"],
                        "description": "Input data type: automatic, amino acid, or nucleotide",
                    },
                ),
                "comp_bias_corr_scale": (
                    "FLOAT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["1"]}},
                    },
                ),
                "zdrop": (
                    "INT",
                    {
                        "default": 40,
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["2"]}},
                    },
                ),
                "add_self_matches": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "kmer_length": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "mask": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "mask_prob": ("FLOAT", {"default": 0.9, "min": 0, "advanced": True}),
                "mask_lower_case": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "mask_n_repeat": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "spaced_kmer_mode": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "sensitivity": ("FLOAT", {"default": 5.7, "min": 1, "max": 7.5}),
                "max_seqs": ("INT", {"default": 300, "min": 0, "advanced": True}),
                "split": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "split_mode": ("STRING", {"default": "2", "options": ["0", "1", "2"], "advanced": True}),
                "diag_score": ("INT", {"default": 1, "min": 0, "max": 1, "advanced": True}),
                "exact_kmer_matching": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_ungapped_score": ("INT", {"default": 15, "min": 0, "advanced": True}),
                "convertalis": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "alignment_output_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"], "advanced": True}),
                "wrapped_scoring": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_aln_len": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "seq_id_mode": ("STRING", {"default": "0", "options": ["0", "1", "2"], "advanced": True}),
                "alt_ali": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "score_bias": ("FLOAT", {"default": 0, "advanced": True}),
                "realign": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "realign_score_bias": ("FLOAT", {"default": -0.2, "advanced": True}),
                "realign_max_seqs": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "corr_score_weight": ("FLOAT", {"default": 0, "advanced": True}),
                "alignment_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0}),
                "min_seq_id": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "cov": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "cov_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"]}),
                "max_rejected": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "max_accept": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "format_fields": MMseqs2EasyLinsearchNode.INPUT_TYPES()["optional"]["format_fields"],
                "format_mode": MMseqs2EasyLinsearchNode.INPUT_TYPES()["optional"]["format_mode"],
                "search_type": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2", "3", "4"],
                        "description": "0 auto, 1 amino acid, 2 translated, 3 nucleotide, 4 translated nucleotide",
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "max_seq_len": ("INT", {"default": 65535, "min": 1, "advanced": True}),
                "filter_hits": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "sort_results": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "chain_alignments": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "merge_query": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "strand": ("STRING", {"default": "1", "options": ["0", "1", "2"], "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MMseqs2EasyTaxonomyNode(CommandNode):
    """Assign taxonomy to sequences with MMseqs2 easy-taxonomy."""

    NODE_ID = "mmseqs2_easy_taxonomy"
    DISPLAY_NAME = "MMseqs2 Easy Taxonomy"
    REQUIRED_CONDA_PACKAGES = ["mmseqs2"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Assign taxonomy to query sequences against an MMseqs2 taxonomy database using LCA."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mmseqs2",
        "mmseqs",
        "easy-taxonomy",
        "taxonomy assignment",
        "LCA",
        "metagenomic classification",
    ]
    RETURN_TYPES = ("TSV", "TXT", "TSV", "TXT")
    RETURN_NAMES = ("lca_results", "kraken_report", "top_hit_alignments", "top_hit_report")
    REQUIRED_EXECUTABLES = ["mmseqs"]
    DOCUMENTATION_URL = MMseqs2EasySearchNode.DOCUMENTATION_URL
    CITATION_DOIS = ["10.1093/bioinformatics/btab184"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btab184"]
    CITATION_TEXT = "Fast and sensitive taxonomic assignment to metagenomic contigs."
    VERSION = MMseqs2EasySearchNode.VERSION
    SHELL = True

    @classmethod
    def _target_command_part(cls, inputs: dict[str, Any], out: str) -> tuple[list[str], str]:
        database_root = str(inputs.get("target_database", ""))
        if inputs.get("download_tax_db"):
            return [
                f"cp -r {shlex.quote(database_root)}/database* .",
                f"mmseqs createtaxdb database {shlex.quote(f'{out}/tmp')}",
            ], "database"
        target = f"{database_root.rstrip('/')}/database" if database_root else "database"
        return [], target

    @classmethod
    def _add_profile_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--mask-profile",
                str(inputs.get("mask_profile", 1)),
                "--e-profile",
                str(inputs.get("e_profile", 0.001)),
                "--wg",
                str(inputs.get("wg", 0)),
                "--filter-msa",
                str(inputs.get("filter_msa", 1)),
                "--filter-min-enable",
                str(inputs.get("filter_min_enable", 0)),
                "--max-seq-id",
                str(inputs.get("max_seq_id", 0.9)),
                "--qid",
                str(inputs.get("qid", "0")),
                "--qsc",
                str(inputs.get("qsc", -20)),
                "--cov",
                str(inputs.get("profile_cov", 0)),
                "--diff",
                str(inputs.get("diff", 1000)),
                "--pseudo-cnt-mode",
                str(inputs.get("pseudo_cnt_mode", 0)),
                "--exhaustive-search",
                str(inputs.get("exhaustive_search", 0)),
                "--lca-search",
                str(inputs.get("lca_search", 0)),
            ]
        )

    @classmethod
    def _add_taxonomy_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--orf-filter-e",
                str(inputs.get("orf_filter_e", 100)),
                "--orf-filter-s",
                str(inputs.get("orf_filter_s", 2)),
                "--lca-mode",
                str(inputs.get("lca_mode", 3)),
                "--majority",
                str(inputs.get("majority", 0.5)),
                "--vote-mode",
                str(inputs.get("vote_mode", 1)),
                "--tax-lineage",
                str(inputs.get("tax_lineage", 0)),
            ]
        )
        _add_if_value(cmd, "--blacklist", inputs.get("blacklist"))
        _add_if_value(cmd, "--taxon-list", inputs.get("taxon_list"))

    @classmethod
    def _add_expert_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--filter-hits",
                str(inputs.get("filter_hits", 0)),
                "--sort-results",
                str(inputs.get("sort_results", 0)),
                "--chain-alignments",
                str(inputs.get("chain_alignments", 0)),
                "--merge-query",
                str(inputs.get("merge_query", 1)),
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        query_fasta = str(inputs.get("query_fasta", ""))
        linked_query = MMseqs2EasyLinsearchNode._sequence_link_name("query", query_fasta)
        prelude = [f"ln -s {shlex.quote(query_fasta)} {shlex.quote(linked_query)}"]
        target_prelude, target = cls._target_command_part(inputs, out)
        prelude.extend(target_prelude)

        effective_inputs = dict(inputs)
        effective_inputs.setdefault("evalue", 1)
        effective_inputs.setdefault("min_seq_id", 0)
        effective_inputs.setdefault("cov", 0)
        effective_inputs.setdefault("max_rejected", 5)
        effective_inputs.setdefault("max_accept", 30)

        cmd = [
            "mmseqs",
            "easy-taxonomy",
            linked_query,
            target,
            f"{out}/result",
            f"{out}/tmp",
        ]
        MMseqs2EasyClusterNode._add_dbtype_options(cmd, effective_inputs)
        MMseqs2EasyRBHNode._add_prefilter_options(cmd, effective_inputs)
        MMseqs2EasyRBHNode._add_search_common_options(cmd, effective_inputs)
        MMseqs2EasyClusterNode._add_align_options(cmd, effective_inputs)
        cls._add_profile_options(cmd, effective_inputs)
        cls._add_taxonomy_options(cmd, effective_inputs)
        cmd.extend(["--search-type", str(effective_inputs.get("search_type", 0))])
        MMseqs2EasyRBHNode._add_common_options(cmd, effective_inputs)
        cls._add_expert_options(cmd, effective_inputs)
        return f"{' && '.join(prelude)} && {shlex.join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        selected = set(_as_list(inputs.get("output_selection")))
        outputs = [out / "result_lca.tsv"]
        if "output_selection" not in inputs:
            selected = {"report"}
        if "report" in selected:
            outputs.append(out / "result_report.txt")
        if "tophit_aln" in selected:
            outputs.append(out / "result_tophit_aln.tsv")
        if "tophit_report" in selected:
            outputs.append(out / "result_tophit_report.txt")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query_fasta": ("FASTA", {"description": "Query FASTA/FASTQ file"}),
                "database_type": (
                    "STRING",
                    {
                        "default": "amino_acid_tax",
                        "options": ["amino_acid_tax", "nucleotides_tax"],
                        "description": "Taxonomy database type: amino acid or nucleotide",
                    },
                ),
                "target_database": ("FILE", {"default": "", "description": "Cached MMseqs2 taxonomy database directory"}),
            },
            "optional": {
                "dbtype": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2"],
                        "description": "Input data type: automatic, amino acid, or nucleotide",
                    },
                ),
                "comp_bias_corr_scale": (
                    "FLOAT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 1,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["1"]}},
                    },
                ),
                "zdrop": (
                    "INT",
                    {
                        "default": 40,
                        "min": 0,
                        "advanced": True,
                        "displayOptions": {"show": {"dbtype": ["2"]}},
                    },
                ),
                "add_self_matches": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "kmer_length": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "mask": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "mask_prob": ("FLOAT", {"default": 0.9, "min": 0, "advanced": True}),
                "mask_lower_case": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "mask_n_repeat": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "spaced_kmer_mode": ("STRING", {"default": "1", "options": ["0", "1"], "advanced": True}),
                "sensitivity": ("FLOAT", {"default": 5.7, "min": 1, "max": 7.5}),
                "max_seqs": ("INT", {"default": 300, "min": 0, "advanced": True}),
                "split": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "split_mode": ("STRING", {"default": "2", "options": ["0", "1", "2"], "advanced": True}),
                "diag_score": ("INT", {"default": 1, "min": 0, "max": 1, "advanced": True}),
                "exact_kmer_matching": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_ungapped_score": ("INT", {"default": 15, "min": 0, "advanced": True}),
                "convertalis": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "alignment_output_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"], "advanced": True}),
                "wrapped_scoring": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_aln_len": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "seq_id_mode": ("STRING", {"default": "0", "options": ["0", "1", "2"], "advanced": True}),
                "alt_ali": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "score_bias": ("FLOAT", {"default": 0, "advanced": True}),
                "realign": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "realign_score_bias": ("FLOAT", {"default": -0.2, "advanced": True}),
                "realign_max_seqs": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "corr_score_weight": ("FLOAT", {"default": 0, "advanced": True}),
                "alignment_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True}),
                "evalue": ("FLOAT", {"default": 1, "min": 0}),
                "min_seq_id": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "cov": ("FLOAT", {"default": 0, "min": 0, "max": 1}),
                "cov_mode": ("STRING", {"default": "0", "options": ["0", "1", "2", "3", "4", "5"]}),
                "max_rejected": ("INT", {"default": 5, "min": 0, "advanced": True}),
                "max_accept": ("INT", {"default": 30, "min": 0, "advanced": True}),
                "mask_profile": ("INT", {"default": 1, "min": 0, "max": 1, "advanced": True}),
                "e_profile": ("FLOAT", {"default": 0.001, "min": 0, "advanced": True}),
                "wg": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "filter_msa": ("INT", {"default": 1, "min": 0, "max": 1, "advanced": True}),
                "filter_min_enable": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "max_seq_id": ("FLOAT", {"default": 0.9, "min": 0, "max": 1, "advanced": True}),
                "qid": ("STRING", {"default": "0", "advanced": True}),
                "qsc": ("FLOAT", {"default": -20, "min": -50, "max": 100, "advanced": True}),
                "profile_cov": ("FLOAT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "diff": ("INT", {"default": 1000, "min": 0, "advanced": True}),
                "pseudo_cnt_mode": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "exhaustive_search": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "lca_search": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "orf_filter_e": ("FLOAT", {"default": 100, "min": 0, "advanced": True}),
                "orf_filter_s": ("FLOAT", {"default": 2, "min": 0, "advanced": True}),
                "lca_mode": ("STRING", {"default": "3", "options": ["1", "3", "4"]}),
                "majority": ("FLOAT", {"default": 0.5, "min": 0, "max": 1}),
                "vote_mode": ("STRING", {"default": "1", "options": ["0", "1", "2"]}),
                "tax_lineage": ("STRING", {"default": "0", "options": ["0", "1", "2"]}),
                "blacklist": ("STRING", {"default": "", "advanced": True}),
                "taxon_list": ("STRING", {"default": "", "advanced": True}),
                "search_type": (
                    "STRING",
                    {
                        "default": "0",
                        "options": ["0", "1", "2", "3", "4"],
                        "description": "0 auto, 1 amino acid, 2 translated, 3 nucleotide, 4 translated nucleotide",
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
                "max_seq_len": ("INT", {"default": 65535, "min": 1, "advanced": True}),
                "filter_hits": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "sort_results": ("STRING", {"default": "0", "options": ["0", "1"], "advanced": True}),
                "chain_alignments": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "merge_query": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "output_selection": (
                    "STRING",
                    {
                        "default": ["report"],
                        "options": ["report", "tophit_aln", "tophit_report"],
                        "list": True,
                        "description": "Additional MMseqs2 taxonomy outputs to keep",
                    },
                ),
                "download_tax_db": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MMseqs2TaxonomyAssignmentNode(CommandNode):
    """Run the lower-level MMseqs2 taxonomy assignment pipeline."""

    NODE_ID = "mmseqs2_taxonomy_assignment"
    DISPLAY_NAME = "MMseqs2 Taxonomy"
    REQUIRED_CONDA_PACKAGES = ["mmseqs2"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Run the fine-grained MMseqs2 taxonomy workflow with optional taxon filtering and reports."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "mmseqs2",
        "mmseqs",
        "taxonomy",
        "taxonomy assignment",
        "filtertaxseqdb",
        "Kraken report",
        "Krona report",
    ]
    RETURN_TYPES = ("TSV", "TXT", "HTML")
    RETURN_NAMES = ("taxonomy_tsv", "kraken_report", "krona_report")
    REQUIRED_EXECUTABLES = ["mmseqs"]
    DOCUMENTATION_URL = MMseqs2EasySearchNode.DOCUMENTATION_URL
    CITATION_DOIS = ["10.1093/bioinformatics/btab184"]
    CITATION_URLS = [f"{DOI_URL}10.1093/bioinformatics/btab184"]
    CITATION_TEXT = "Fast and sensitive taxonomic assignment to metagenomic contigs."
    VERSION = MMseqs2EasySearchNode.VERSION
    SHELL = True

    @classmethod
    def _database_source(cls, inputs: dict[str, Any]) -> str:
        if inputs.get("download_tax_db"):
            return "database"
        database_root = str(inputs.get("target_database", ""))
        return f"{database_root.rstrip('/')}/database" if database_root else "database"

    @classmethod
    def _add_prefilter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--add-self-matches",
                str(inputs.get("add_self_matches", 0)),
                "-s",
                str(inputs.get("sensitivity", 2)),
                "-k",
                str(inputs.get("kmer_length", 0)),
                "--target-search-mode",
                str(inputs.get("target_search_mode", 0)),
                "--max-seqs",
                str(inputs.get("max_seqs", 300)),
                "--split",
                str(inputs.get("split", 0)),
                "--split-mode",
                str(inputs.get("split_mode", 2)),
                "--diag-score",
                str(inputs.get("diag_score", 1)),
                "--exact-kmer-matching",
                str(inputs.get("exact_kmer_matching", 0)),
                "--mask",
                str(inputs.get("mask", 1)),
                "--mask-prob",
                str(inputs.get("mask_prob", 0.9)),
                "--mask-lower-case",
                str(inputs.get("mask_lower_case", 0)),
                "--mask-n-repeat",
                str(inputs.get("mask_n_repeat", 0)),
                "--min-ungapped-score",
                str(inputs.get("min_ungapped_score", 15)),
                "--spaced-kmer-mode",
                str(inputs.get("spaced_kmer_mode", 1)),
            ]
        )

    @classmethod
    def _add_align_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "-a",
                str(inputs.get("convertalis", 0)),
                "--alignment-mode",
                str(inputs.get("alignment_mode", 1)),
                "--alignment-output-mode",
                str(inputs.get("alignment_output_mode", 0)),
                "--wrapped-scoring",
                str(inputs.get("wrapped_scoring", 0)),
                "-e",
                str(inputs.get("evalue", 1)),
                "--min-seq-id",
                str(inputs.get("min_seq_id", 0)),
                "--min-aln-len",
                str(inputs.get("min_aln_len", 0)),
                "--seq-id-mode",
                str(inputs.get("seq_id_mode", 0)),
                "--alt-ali",
                str(inputs.get("alt_ali", 0)),
                "-c",
                str(inputs.get("cov", 0)),
                "--cov-mode",
                str(inputs.get("cov_mode", 0)),
                "--max-rejected",
                str(inputs.get("max_rejected", 5)),
                "--max-accept",
                str(inputs.get("max_accept", 30)),
                "--score-bias",
                str(inputs.get("score_bias", 0)),
                "--realign",
                str(inputs.get("realign", 0)),
                "--realign-score-bias",
                str(inputs.get("realign_score_bias", -0.2)),
                "--realign-max-seqs",
                str(inputs.get("realign_max_seqs", 2147483647)),
                "--corr-score-weight",
                str(inputs.get("corr_score_weight", 0)),
                "--exhaustive-search-filter",
                str(inputs.get("exhaustive_search_filter", 0)),
            ]
        )

    @classmethod
    def _add_misc_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        MMseqs2EasyTaxonomyNode._add_taxonomy_options(cmd, inputs)
        cmd.extend(
            [
                "--rescore-mode",
                str(inputs.get("rescore_mode", 0)),
                "--allow-deletion",
                str(inputs.get("allow_deletion", 0)),
                "--min-length",
                str(inputs.get("min_length", 30)),
                "--max-length",
                str(inputs.get("max_length", 32734)),
                "--max-gaps",
                str(inputs.get("max_gaps", 2147483647)),
                "--contig-start-mode",
                str(inputs.get("contig_start_mode", 2)),
                "--contig-end-mode",
                str(inputs.get("contig_end_mode", 2)),
                "--orf-start-mode",
                str(inputs.get("orf_start_mode", 1)),
                "--forward-frames",
                str(inputs.get("forward_frames", "1,2,3")),
                "--reverse-frames",
                str(inputs.get("reverse_frames", "1,2,3")),
                "--translation-table",
                str(inputs.get("translation_table", 1)),
                "--translate",
                str(inputs.get("translate", 0)),
                "--use-all-table-starts",
                str(inputs.get("use_all_table_starts", 0)),
                "--id-offset",
                str(inputs.get("id_offset", 0)),
                "--sequence-overlap",
                str(inputs.get("sequence_overlap", 0)),
                "--sequence-split-mode",
                str(inputs.get("sequence_split_mode", 1)),
                "--headers-split-mode",
                str(inputs.get("headers_split_mode", 0)),
                "--search-type",
                str(inputs.get("search_type", 3 if inputs.get("database_type") == "nucleotides_tax" else 0)),
                "--prefilter-mode",
                str(inputs.get("prefilter_mode", 0)),
            ]
        )

    @classmethod
    def _add_common_and_expert_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--threads",
                str(inputs.get("threads", 1)),
                "--max-seq-len",
                str(inputs.get("max_seq_len", 65535)),
                "--filter-hits",
                str(inputs.get("filter_hits", 0)),
                "--sort-results",
                str(inputs.get("sort_results", 0)),
                "--chain-alignments",
                str(inputs.get("chain_alignments", 0)),
                "--merge-query",
                str(inputs.get("merge_query", 1)),
            ]
        )

    @classmethod
    def _taxonomy_command(cls, inputs: dict[str, Any], out: str, taxonomy_database: str) -> list[str]:
        cmd = [
            "mmseqs",
            "taxonomy",
            f"{out}/sequenceDB",
            taxonomy_database,
            f"{out}/output_taxonomy",
            f"{out}/tmp",
        ]
        dbtype = str(inputs.get("dbtype", "0"))
        if dbtype == "1":
            _add_if_value(cmd, "--comp-bias-corr-scale", inputs.get("comp_bias_corr_scale", 1))
        elif dbtype == "2":
            _add_if_value(cmd, "--zdrop", inputs.get("zdrop", 40))
        cls._add_prefilter_options(cmd, inputs)
        cls._add_align_options(cmd, inputs)
        MMseqs2EasyTaxonomyNode._add_profile_options(cmd, inputs)
        cls._add_misc_options(cmd, inputs)
        cls._add_common_and_expert_options(cmd, inputs)
        return cmd

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_fasta = str(inputs.get("input_fasta", ""))
        commands = [
            shlex.join(["ln", "-s", "-f", input_fasta, "input"]),
            shlex.join(
                [
                    "mmseqs",
                    "createdb",
                    "input",
                    f"{out}/sequenceDB",
                    "--dbtype",
                    str(inputs.get("dbtype", 0)),
                    "--shuffle",
                    str(inputs.get("shuffle", 1)),
                ]
            ),
        ]

        if inputs.get("download_tax_db"):
            database_root = str(inputs.get("target_database", ""))
            commands.extend(
                [
                    f"cp -r {shlex.quote(database_root)}/database* .",
                    shlex.join(["mmseqs", "createtaxdb", "database", f"{out}/tmp"]),
                ]
            )

        taxonomy_database = cls._database_source(inputs)
        filter_taxon_list = str(inputs.get("filter_taxon_list", ""))
        if filter_taxon_list:
            filtered_database = f"{out}/database_filtered"
            commands.append(
                shlex.join(
                    [
                        "mmseqs",
                        "filtertaxseqdb",
                        taxonomy_database,
                        filtered_database,
                        "--taxon-list",
                        filter_taxon_list,
                    ]
                )
            )
            taxonomy_database = filtered_database

        commands.append(shlex.join(cls._taxonomy_command(inputs, out, taxonomy_database)))
        commands.append(
            shlex.join(
                [
                    "mmseqs",
                    "createtsv",
                    f"{out}/sequenceDB",
                    f"{out}/output_taxonomy",
                    f"{out}/taxo_result.tsv",
                    "--first-seq-as-repr",
                    str(inputs.get("first_seq_as_repr", 0)),
                    "--target-column",
                    str(inputs.get("target_column", 1)),
                    "--full-header",
                    str(inputs.get("full_header", 0)),
                    "--idx-seq-src",
                    str(inputs.get("idx_seq_src", 0)),
                    "--threads",
                    str(inputs.get("threads", 1)),
                ]
            )
        )

        if inputs.get("keep_kraken_report", True):
            commands.append(
                shlex.join(
                    [
                        "mmseqs",
                        "taxonomyreport",
                        taxonomy_database,
                        f"{out}/output_taxonomy",
                        f"{out}/taxo_result.txt",
                        "--report-mode",
                        "0",
                        "--threads",
                        str(inputs.get("threads", 1)),
                    ]
                )
            )
        if inputs.get("keep_krona_report", True):
            commands.append(
                shlex.join(
                    [
                        "mmseqs",
                        "taxonomyreport",
                        taxonomy_database,
                        f"{out}/output_taxonomy",
                        f"{out}/taxo_result.html",
                        "--report-mode",
                        "1",
                        "--threads",
                        str(inputs.get("threads", 1)),
                    ]
                )
            )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "taxo_result.tsv"]
        if inputs.get("keep_kraken_report", True):
            outputs.append(out / "taxo_result.txt")
        if inputs.get("keep_krona_report", True):
            outputs.append(out / "taxo_result.html")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        taxonomy_optional = dict(MMseqs2EasyTaxonomyNode.INPUT_TYPES()["optional"])
        taxonomy_optional.update(
            {
                "sensitivity": ("FLOAT", {"default": 2, "min": 1, "max": 7.5}),
                "target_search_mode": (
                    "STRING",
                    {"default": "0", "options": ["0", "1"], "advanced": True},
                ),
                "alignment_mode": (
                    "STRING",
                    {"default": "1", "options": ["0", "1", "2", "3", "4"], "advanced": True},
                ),
                "exhaustive_search_filter": (
                    "INT",
                    {"default": 0, "min": 0, "max": 1, "advanced": True},
                ),
                "filter_taxon_list": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Optional taxon list for pre-filtering the taxonomy database",
                    },
                ),
                "rescore_mode": (
                    "STRING",
                    {"default": "0", "options": ["0", "1", "2", "3", "4"], "advanced": True},
                ),
                "allow_deletion": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "min_length": ("INT", {"default": 30, "min": 0, "advanced": True}),
                "max_length": ("INT", {"default": 32734, "min": 0, "advanced": True}),
                "max_gaps": ("INT", {"default": 2147483647, "min": 0, "advanced": True}),
                "contig_start_mode": (
                    "STRING",
                    {"default": "2", "options": ["0", "1", "2"], "advanced": True},
                ),
                "contig_end_mode": (
                    "STRING",
                    {"default": "2", "options": ["0", "1", "2"], "advanced": True},
                ),
                "orf_start_mode": (
                    "STRING",
                    {"default": "1", "options": ["0", "1", "2"], "advanced": True},
                ),
                "forward_frames": ("STRING", {"default": "1,2,3", "advanced": True}),
                "reverse_frames": ("STRING", {"default": "1,2,3", "advanced": True}),
                "translation_table": (
                    "STRING",
                    {
                        "default": "1",
                        "options": [
                            "1",
                            "2",
                            "3",
                            "4",
                            "5",
                            "6",
                            "9",
                            "10",
                            "11",
                            "12",
                            "13",
                            "14",
                            "15",
                            "16",
                            "21",
                            "22",
                            "23",
                            "24",
                            "25",
                            "26",
                            "27",
                            "28",
                            "29",
                            "30",
                            "31",
                        ],
                        "advanced": True,
                    },
                ),
                "translate": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "use_all_table_starts": (
                    "INT",
                    {"default": 0, "min": 0, "max": 1, "advanced": True},
                ),
                "id_offset": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "sequence_overlap": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "sequence_split_mode": (
                    "STRING",
                    {"default": "1", "options": ["0", "1"], "advanced": True},
                ),
                "headers_split_mode": (
                    "STRING",
                    {"default": "0", "options": ["0", "1"], "advanced": True},
                ),
                "prefilter_mode": (
                    "STRING",
                    {"default": "0", "options": ["0", "1", "2"], "advanced": True},
                ),
                "first_seq_as_repr": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "target_column": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "full_header": ("INT", {"default": 0, "min": 0, "max": 1, "advanced": True}),
                "idx_seq_src": (
                    "STRING",
                    {"default": "0", "options": ["0", "1", "2"], "advanced": True},
                ),
                "keep_kraken_report": (
                    "BOOLEAN",
                    {"default": True, "description": "Generate a Kraken-style taxonomy report"},
                ),
                "keep_krona_report": (
                    "BOOLEAN",
                    {"default": True, "description": "Generate a Krona HTML taxonomy report"},
                ),
            }
        )
        taxonomy_optional.pop("output_selection", None)
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Query FASTA/FASTQ file"}),
                "database_type": (
                    "STRING",
                    {
                        "default": "amino_acid_tax",
                        "options": ["amino_acid_tax", "nucleotides_tax"],
                        "description": "Taxonomy database type: amino acid or nucleotide",
                    },
                ),
                "target_database": ("FILE", {"default": "", "description": "Cached MMseqs2 taxonomy database directory"}),
            },
            "optional": taxonomy_optional,
            "hidden": {"output": ("STRING", {})},
        }

class KaijuNode(CommandNode):
    """Classify metagenomic reads with the Galaxy IUC Kaiju wrapper behavior."""

    NODE_ID = "kaiju"
    DISPLAY_NAME = "Kaiju"
    REQUIRED_CONDA_PACKAGES = ["kaiju"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Classify metagenomic reads or report best matching database sequences with Kaiju."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "kaiju",
        "taxonomic classification",
        "metagenomics",
        "protein-level classifier",
        "best matching sequence",
    ]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("taxonomic_classification", "best_matching_sequences")
    REQUIRED_EXECUTABLES = ["kaiju", "kaijup", "kaijux"]
    DOCUMENTATION_URL = "https://github.com/bioinformatics-centre/kaiju"
    CITATION_DOIS = ["10.1038/ncomms11257"]
    CITATION_URLS = [f"{DOI_URL}10.1038/ncomms11257"]
    CITATION_TEXT = "Fast and sensitive taxonomic classification for metagenomics with Kaiju."
    VERSION = "1.10.1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        task = str(inputs.get("task", "tax"))
        protein = bool(inputs.get("protein", False))
        reference = str(inputs.get("reference_database", "")).rstrip("/")

        if task == "tax":
            cmd = [
                "kaiju",
                "-t",
                f"{reference}/nodes.dmp",
                "-o",
                f"{out}/kaiju_taxonomy.tsv",
            ]
        else:
            cmd = [
                "kaijup" if protein else "kaijux",
                "-o",
                f"{out}/kaiju_best_sequences.tsv",
            ]

        cmd.extend(["-f", f"{reference}/database.fmi"])
        if str(inputs.get("input_type", "single")) == "paired":
            cmd.extend(["-i", str(inputs.get("reads_1", "")), "-j", str(inputs.get("reads_2", ""))])
        else:
            cmd.extend(["-i", str(inputs.get("reads", ""))])

        cmd.extend(["-z", str(inputs.get("threads", 1))])
        if protein:
            cmd.append("-p")
        cmd.append("-x" if inputs.get("low_complexity", True) else "-X")

        mode = str(inputs.get("mode", "greedy"))
        cmd.extend(["-a", mode])
        if mode == "greedy":
            cmd.extend(
                [
                    "-e",
                    str(inputs.get("mismatches", 3)),
                    "-m",
                    str(inputs.get("match_length", 11)),
                    "-s",
                    str(inputs.get("match_score", 65)),
                    "-E",
                    str(inputs.get("evalue", 0.01)),
                ]
            )
        if inputs.get("verbose", False):
            cmd.append("-v")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if str(inputs.get("task", "tax")) == "best_sequence":
            return [out / "kaiju_best_sequences.tsv"]
        return [out / "kaiju_taxonomy.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": (
                    "STRING",
                    {"default": "single", "options": ["single", "paired"], "description": "Single or paired read inputs"},
                ),
                "reads": ("FASTQ", {"description": "Single-end FASTA/FASTQ reads"}),
                "reads_1": ("FASTQ", {"description": "Forward reads for paired input"}),
                "reads_2": ("FASTQ", {"description": "Reverse reads for paired input"}),
                "reference_database": (
                    "DIRECTORY",
                    {"description": "Kaiju database directory containing database.fmi and nodes.dmp"},
                ),
            },
            "optional": {
                "task": (
                    "STRING",
                    {"default": "tax", "options": ["tax", "best_sequence"], "description": "Taxonomic classification or best sequence lookup"},
                ),
                "protein": (
                    "BOOLEAN",
                    {"default": False, "description": "Input sequences are protein sequences"},
                ),
                "low_complexity": (
                    "BOOLEAN",
                    {"default": True, "description": "Enable SEG low-complexity filtering"},
                ),
                "mode": (
                    "STRING",
                    {"default": "greedy", "options": ["greedy", "mem"], "description": "Kaiju MEM or greedy search mode"},
                ),
                "mismatches": ("INT", {"default": 3, "min": 0, "description": "Greedy-mode mismatches allowed"}),
                "match_length": ("INT", {"default": 11, "min": 1, "description": "Greedy-mode minimum match length"}),
                "match_score": ("INT", {"default": 65, "min": 1, "description": "Greedy-mode minimum match score"}),
                "evalue": ("FLOAT", {"default": 0.01, "min": 0, "description": "Greedy-mode minimum E-value"}),
                "verbose": (
                    "BOOLEAN",
                    {"default": False, "description": "Include additional classification columns"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class KaijuAddTaxonNamesNode(CommandNode):
    """Append taxon names or taxonomic paths to Kaiju output tables."""

    NODE_ID = "kaiju_add_taxon_names"
    DISPLAY_NAME = "Kaiju Add Taxon Names"
    REQUIRED_CONDA_PACKAGES = ["kaiju"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Append taxon names or taxonomic paths to Kaiju output tables."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "kaiju",
        "kaiju-addTaxonNames",
        "taxon names",
        "Print full taxon path",
        "readable taxonomy",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("taxon_names_table",)
    REQUIRED_EXECUTABLES = ["kaiju-addTaxonNames"]
    DOCUMENTATION_URL = KaijuNode.DOCUMENTATION_URL
    CITATION_DOIS = KaijuNode.CITATION_DOIS
    CITATION_URLS = KaijuNode.CITATION_URLS
    CITATION_TEXT = KaijuNode.CITATION_TEXT
    VERSION = KaijuNode.VERSION

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        reference = str(inputs.get("reference_database", "")).rstrip("/")
        cmd = [
            "kaiju-addTaxonNames",
            "-t",
            f"{reference}/nodes.dmp",
            "-n",
            f"{reference}/names.dmp",
            "-i",
            str(inputs.get("kaiju_table", "")),
            "-o",
            f"{out}/kaiju_taxon_names.tsv",
        ]
        if inputs.get("exclude_unclassified", False):
            cmd.append("-u")
        rank = str(inputs.get("rank", ""))
        if rank:
            cmd.extend(["-r", rank])
        if inputs.get("print_full_taxon_path", False):
            cmd.append("-p")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "kaiju_taxon_names.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "kaiju_table": ("TSV", {"description": "Kaiju output table"}),
                "reference_database": (
                    "DIRECTORY",
                    {"description": "Kaiju database directory containing nodes.dmp and names.dmp"},
                ),
            },
            "optional": {
                "exclude_unclassified": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not count unclassified reads in percentage totals"},
                ),
                "rank": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "phylum", "class", "order", "family", "genus", "species"],
                        "description": "Optional rank whose taxon name should be appended",
                    },
                ),
                "print_full_taxon_path": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Print the full taxon path instead of a rank-specific taxon name",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Kaiju2KronaNode(CommandNode):
    """Convert Kaiju classifications into a Krona import table."""

    NODE_ID = "kaiju2krona"
    DISPLAY_NAME = "Kaiju2Krona"
    REQUIRED_CONDA_PACKAGES = ["kaiju"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Convert Kaiju output into a Krona-compatible taxonomy import table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "kaiju",
        "kaiju2krona",
        "Krona import",
        "selected ranks",
        "taxonomy sunburst",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("krona_import_tsv",)
    REQUIRED_EXECUTABLES = ["kaiju2krona"]
    DOCUMENTATION_URL = KaijuNode.DOCUMENTATION_URL
    CITATION_DOIS = KaijuNode.CITATION_DOIS
    CITATION_URLS = KaijuNode.CITATION_URLS
    CITATION_TEXT = KaijuNode.CITATION_TEXT
    VERSION = KaijuNode.VERSION

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        reference = str(inputs.get("reference_database", "")).rstrip("/")
        cmd = [
            "kaiju2krona",
            "-t",
            f"{reference}/nodes.dmp",
            "-n",
            f"{reference}/names.dmp",
            "-i",
            str(inputs.get("kaiju_table", "")),
            "-o",
            f"{out}/kaiju_krona.tsv",
        ]
        if inputs.get("include_unclassified", False):
            cmd.append("-u")
        selected_ranks = ".".join(_as_list(inputs.get("selected_ranks")))
        if selected_ranks:
            cmd.extend(["-l", selected_ranks])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "kaiju_krona.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        ranks = ["superkingdom", "phylum", "class", "order", "family", "genus", "species"]
        return {
            "required": {
                "kaiju_table": ("TSV", {"description": "Kaiju output table"}),
                "reference_database": (
                    "DIRECTORY",
                    {"description": "Kaiju database directory containing nodes.dmp and names.dmp"},
                ),
            },
            "optional": {
                "include_unclassified": (
                    "BOOLEAN",
                    {"default": False, "description": "Include count for unclassified reads"},
                ),
                "selected_ranks": (
                    "STRING",
                    {
                        "default": [],
                        "options": ranks,
                        "multiple": True,
                        "description": "Taxonomic ranks to print as dot-delimited Krona paths",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class KaijuMergeOutputsNode(CommandNode):
    """Merge Kaiju and Kraken-style classification tables."""

    NODE_ID = "kaiju_merge_outputs"
    DISPLAY_NAME = "Kaiju Merge Outputs"
    REQUIRED_CONDA_PACKAGES = ["kaiju"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Merge Kaiju and Kraken-style classification output tables with conflict resolution."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "kaiju",
        "kaiju-mergeOutputs",
        "merge classifications",
        "conflict resolution",
        "Kraken table",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("merged_classification",)
    REQUIRED_EXECUTABLES = ["kaiju-mergeOutputs"]
    DOCUMENTATION_URL = KaijuNode.DOCUMENTATION_URL
    CITATION_DOIS = KaijuNode.CITATION_DOIS
    CITATION_URLS = KaijuNode.CITATION_URLS
    CITATION_TEXT = KaijuNode.CITATION_TEXT
    VERSION = KaijuNode.VERSION
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        conflict_mode = str(inputs.get("conflict_mode", "lca"))
        cmd = [
            "kaiju-mergeOutputs",
            "-i",
            "kaiju.out.sort",
            "-j",
            "kraken.out.sort",
            "-o",
            f"{out}/kaiju_merged_outputs.tsv",
            "-c",
            conflict_mode,
        ]
        if conflict_mode in {"lca", "lowest"}:
            reference = str(inputs.get("reference_database", "")).rstrip("/")
            cmd.extend(["-t", f"{reference}/nodes.dmp"])
        if inputs.get("use_score", False):
            cmd.append("-s")
        cmd.append("-v")

        commands = [
            f"sort -k2,2 {shlex.quote(str(inputs.get('kaiju_table', '')))} > kaiju.out.sort",
            f"sort -k2,2 {shlex.quote(str(inputs.get('kraken_table', '')))} > kraken.out.sort",
            shlex.join(cmd),
        ]
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "kaiju_merged_outputs.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "kaiju_table": ("TSV", {"description": "Kaiju output table sorted by read identifier before merging"}),
                "kraken_table": (
                    "TSV",
                    {"description": "Second classification table in Kaiju/Kraken column format"},
                ),
            },
            "optional": {
                "reference_database": (
                    "DIRECTORY",
                    {"description": "Kaiju database directory containing nodes.dmp for LCA conflict modes"},
                ),
                "conflict_mode": (
                    "STRING",
                    {
                        "default": "lca",
                        "options": ["1", "2", "lca", "lowest"],
                        "description": "Resolve conflicting taxon IDs from the first input, second input, LCA, or lowest lineage match",
                    },
                ),
                "use_score": (
                    "BOOLEAN",
                    {"default": False, "description": "Use the fourth-column classification score to prefer better-scoring taxa"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class CentrifugeNode(CommandNode):
    """Classify metagenomic reads with Centrifuge."""

    NODE_ID = "centrifuge"
    DISPLAY_NAME = "Centrifuge"
    REQUIRED_CONDA_PACKAGES = ["centrifuge"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Read-based metagenome characterization with Centrifuge."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Centrifuge",
        "metagenomic classification",
        "taxonomic classification",
        "read-based metagenomics",
        "SRA accession",
        "FM index",
    ]
    RETURN_TYPES = ("TSV", "SAM", "TSV")
    RETURN_NAMES = ("tabular_output", "sam_output", "report")
    REQUIRED_EXECUTABLES = ["centrifuge"]
    DOCUMENTATION_URL = "https://ccb.jhu.edu/software/centrifuge/"
    CITATION_DOIS = ["10.1101/gr.210641.116"]
    CITATION_URLS = [f"{DOI_URL}10.1101/gr.210641.116"]
    CITATION_TEXT = "Centrifuge: rapid and sensitive classification of metagenomic sequences."
    VERSION = "1.0.4_beta"
    SHELL = True

    _DEFAULT_TAB_COLUMNS = "readID,seqID,taxID,score,2ndBestScore,hitLength,queryLength,numMatches"
    _TAB_COLUMNS = {
        "readID",
        "seqID",
        "taxID",
        "score",
        "2ndBestScore",
        "hitLength",
        "queryLength",
        "numMatches",
    }

    @classmethod
    def _out_path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f"{_out(inputs)}/{filename}"

    @classmethod
    def _paired_values(cls, inputs: dict[str, Any]) -> list[tuple[str, str]]:
        raw_paired_values = inputs.get("paired_reads")
        if raw_paired_values is None or raw_paired_values == "":
            paired_values: list[Any] = []
        elif (
            isinstance(raw_paired_values, (list, tuple))
            and len(raw_paired_values) >= 2
            and not isinstance(raw_paired_values[0], (dict, list, tuple))
        ):
            paired_values = [raw_paired_values]
        elif isinstance(raw_paired_values, (list, tuple)):
            paired_values = list(raw_paired_values)
        else:
            paired_values = [raw_paired_values]
        pairs: list[tuple[str, str]] = []
        for value in paired_values:
            if isinstance(value, dict):
                forward = value.get("forward", value.get("input_1", value.get("r1", "")))
                reverse = value.get("reverse", value.get("input_2", value.get("r2", "")))
                pairs.append((str(forward), str(reverse)))
            elif isinstance(value, (list, tuple)) and len(value) >= 2:
                pairs.append((str(value[0]), str(value[1])))
            elif value:
                pair_root = str(value).rstrip("/")
                pairs.append((f"{pair_root}/forward", f"{pair_root}/reverse"))
        return pairs

    @classmethod
    def _output_filename(cls, inputs: dict[str, Any]) -> str:
        return "centrifuge_output.sam" if str(inputs.get("out_fmt", "tab")) == "sam" else "centrifuge_output.tsv"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("db", "")).strip():
            return "Centrifuge database is required"
        if not _as_list(inputs.get("unpaired_reads")) and not cls._paired_values(inputs) and not str(inputs.get("sra", "")).strip():
            return "At least one unpaired read, paired read collection, or SRA accession is required"
        if inputs.get("norc", False) and inputs.get("nofw", False):
            return "Centrifuge cannot disable both forward and reverse-complement mapping"
        try:
            min_hitlen = int(inputs.get("min_hitlen", 22))
        except (TypeError, ValueError):
            return "Minimum hit length must be an integer"
        if min_hitlen < 16:
            return "Minimum hit length must be at least 16"

        columns = str(inputs.get("tab_fmt_cols", cls._DEFAULT_TAB_COLUMNS))
        for column in columns.split(","):
            if column and column not in cls._TAB_COLUMNS:
                return f"Unsupported Centrifuge tabular output column: {column}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "centrifuge",
            "--out-fmt",
            str(inputs.get("out_fmt", "tab")),
            "--tab-fmt-cols",
            str(inputs.get("tab_fmt_cols", cls._DEFAULT_TAB_COLUMNS)),
            "--threads",
            str(inputs.get("threads", 1)),
        ]

        for key, flag in (
            ("skip", "--skip"),
            ("upto", "--upto"),
            ("trim5", "--trim5"),
            ("trim3", "--trim3"),
        ):
            _add_if_value(cmd, flag, inputs.get(key))

        for key, flag in (
            ("ignore_quals", "--ignore-quals"),
            ("nofw", "--nofw"),
            ("norc", "--norc"),
            ("non_deterministic", "--non-deterministic"),
        ):
            if inputs.get(key, False):
                cmd.append(flag)

        _add_if_value(cmd, "--seed", inputs.get("seed"))
        cmd.extend(["--min-hitlen", str(inputs.get("min_hitlen", 22))])
        _add_if_value(cmd, "--min-totallen", inputs.get("min_totallen"))
        _add_if_value(cmd, "--host-taxids", inputs.get("host_taxids"))
        _add_if_value(cmd, "--exclude-taxids", inputs.get("exclude_taxids"))
        cmd.extend(["-x", str(inputs.get("db", ""))])

        for read_path in _as_list(inputs.get("unpaired_reads")):
            cmd.extend(["-U", read_path])
        for forward, reverse in cls._paired_values(inputs):
            cmd.extend(["-1", forward, "-2", reverse])
        _add_if_value(cmd, "--sra-acc", inputs.get("sra"))

        cmd.extend(
            [
                "-S",
                cls._out_path(inputs, cls._output_filename(inputs)),
                "--report-file",
                cls._out_path(inputs, "centrifuge_report.tsv"),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [
            out / cls._output_filename(inputs),
            out / "centrifuge_report.tsv",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "db": (
                    "DIRECTORY",
                    {"description": "Centrifuge index filename prefix or database directory"},
                ),
            },
            "optional": {
                "unpaired_reads": (
                    "FASTQ",
                    {"default": [], "multiple": True, "description": "One or more unpaired FASTQ read files"},
                ),
                "paired_reads": (
                    "FASTQ_LIST",
                    {"default": [], "multiple": True, "description": "One or more paired read collections"},
                ),
                "sra": (
                    "STRING",
                    {"default": "", "description": "Comma-separated SRA accessions, e.g. SRR353653,SRR353654"},
                ),
                "out_fmt": (
                    "STRING",
                    {"default": "tab", "options": ["tab", "sam"], "description": "Classification output format"},
                ),
                "tab_fmt_cols": (
                    "STRING",
                    {
                        "default": cls._DEFAULT_TAB_COLUMNS,
                        "description": "Comma-separated output columns for tabular Centrifuge output",
                    },
                ),
                "skip": ("INT", {"default": "", "min": 0, "description": "Initial reads or read pairs to skip"}),
                "upto": ("INT", {"default": "", "min": 0, "description": "Stop after this many reads or read pairs"}),
                "trim5": ("INT", {"default": "", "min": 0, "description": "Trim bases from the 5 prime end"}),
                "trim3": ("INT", {"default": "", "min": 0, "description": "Trim bases from the 3 prime end"}),
                "ignore_quals": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat all quality values as Phred 30"},
                ),
                "nofw": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not align the forward strand"},
                ),
                "norc": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not align the reverse-complement strand"},
                ),
                "seed": ("INT", {"default": "", "min": 0, "advanced": True}),
                "non_deterministic": (
                    "BOOLEAN",
                    {"default": False, "description": "Use non-deterministic random seeding", "advanced": True},
                ),
                "min_hitlen": (
                    "INT",
                    {"default": 22, "min": 16, "description": "Minimum length of partial hits"},
                ),
                "min_totallen": (
                    "INT",
                    {"default": "", "min": 0, "description": "Minimum summed length of partial hits per read"},
                ),
                "host_taxids": (
                    "STRING",
                    {"default": "", "description": "Comma-separated host taxonomic IDs", "advanced": True},
                ),
                "exclude_taxids": (
                    "STRING",
                    {"default": "", "description": "Comma-separated taxonomic IDs to exclude", "advanced": True},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class KrakenNode(CommandNode):
    """Assign taxonomy to reads with classic Kraken."""

    NODE_ID = "kraken"
    DISPLAY_NAME = "Kraken"
    REQUIRED_CONDA_PACKAGES = ["kraken"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Assign taxonomic labels to sequencing reads with Kraken."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Kraken",
        "taxonomic classification",
        "metagenomics",
        "k-mer exact alignment",
        "classified reads",
        "unclassified reads",
        "quick mode",
    ]
    RETURN_TYPES = ("KRAKEN_OUTPUT", "FASTQ", "FASTQ")
    RETURN_NAMES = ("classification", "classified_reads", "unclassified_reads")
    REQUIRED_EXECUTABLES = ["kraken"]
    DOCUMENTATION_URL = "http://ccb.jhu.edu/software/kraken/"
    CITATION_DOIS = ["10.1186/gb-2014-15-3-r46"]
    CITATION_URLS = [f"{DOI_URL}10.1186/gb-2014-15-3-r46"]
    CITATION_TEXT = "Kraken: ultrafast metagenomic sequence classification using exact alignments."
    VERSION = "1.1.1"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/classification.kraken"

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        input_format = str(inputs.get("input_format", "")).lower()
        if input_format in {"fasta", "fastq"}:
            return input_format

        paths = [
            str(inputs.get("input_sequences", "")),
            str(inputs.get("forward_input", "")),
            str(inputs.get("reverse_input", "")),
        ]
        raw_pair = inputs.get("input_pair")
        if isinstance(raw_pair, dict):
            paths.extend([str(raw_pair.get("forward", "")), str(raw_pair.get("reverse", ""))])
        elif isinstance(raw_pair, (list, tuple)):
            paths.extend(str(value) for value in raw_pair)
        if any(Path(path).suffix.lower() in {".fa", ".fasta", ".fna"} for path in paths if path):
            return "fasta"
        return "fastq"

    @classmethod
    def _paired_collection(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        pair = inputs.get("input_pair")
        if isinstance(pair, dict):
            return str(pair.get("forward", "")), str(pair.get("reverse", ""))
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            return str(pair[0]), str(pair[1])
        if pair:
            root = str(pair).rstrip("/")
            return f"{root}/forward", f"{root}/reverse"
        return "", ""

    @classmethod
    def _read_inputs(cls, inputs: dict[str, Any]) -> list[str]:
        input_type = str(inputs.get("input_type", "single"))
        if input_type == "paired":
            return [str(inputs.get("forward_input", "")), str(inputs.get("reverse_input", ""))]
        if input_type == "paired_collection":
            return list(cls._paired_collection(inputs))
        return [str(inputs.get("input_sequences", ""))]

    @classmethod
    def _split_suffix(cls, inputs: dict[str, Any]) -> str:
        return "fasta" if cls._input_format(inputs) == "fasta" else "fastq"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("db", "")).strip():
            return "Kraken database is required"
        input_type = str(inputs.get("input_type", "single"))
        if input_type == "paired":
            if not str(inputs.get("forward_input", "")).strip() or not str(inputs.get("reverse_input", "")).strip():
                return "Forward and reverse reads are required for paired input"
        elif input_type == "paired_collection":
            forward, reverse = cls._paired_collection(inputs)
            if not forward or not reverse:
                return "Paired collection input is required"
        elif not str(inputs.get("input_sequences", "")).strip():
            return "Single-end input sequences are required"

        if str(inputs.get("quick", "no")) == "yes":
            try:
                min_hits = int(inputs.get("min_hits", 1))
            except (TypeError, ValueError):
                return "Quick mode min_hits must be an integer"
            if min_hits < 1:
                return "Quick mode min_hits must be at least 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_type = str(inputs.get("input_type", "single"))
        input_format = cls._input_format(inputs)
        cmd = [
            "kraken",
            "--threads",
            str(inputs.get("threads", 1)),
            "--db",
            str(inputs.get("db", "")),
        ]
        if inputs.get("only_classified_output", False):
            cmd.append("--only-classified-output")
        if str(inputs.get("quick", "no")) == "yes":
            cmd.extend(["--quick", "--min-hits", str(inputs.get("min_hits", 1))])
        cmd.append("--fastq-input" if input_format == "fastq" else "--fasta-input")
        cmd.extend(read for read in cls._read_inputs(inputs) if read)
        if input_type in {"paired", "paired_collection"}:
            cmd.append("--paired")
            if inputs.get("check_names", False):
                cmd.append("--check-names")
        if inputs.get("split_reads", False):
            suffix = cls._split_suffix(inputs)
            cmd.extend(
                [
                    "--classified-out",
                    f"{_out(inputs)}/classified_reads.{suffix}",
                    "--unclassified-out",
                    f"{_out(inputs)}/unclassified_reads.{suffix}",
                ]
            )
        _add_shell_redirect(cmd, cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "classification.kraken"]
        if inputs.get("split_reads", False):
            suffix = cls._split_suffix(inputs)
            outputs.extend([out / f"classified_reads.{suffix}", out / f"unclassified_reads.{suffix}"])
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": (
                    "STRING",
                    {
                        "default": "single",
                        "options": ["single", "paired", "paired_collection"],
                        "description": "Single reads, paired reads, or a paired collection",
                    },
                ),
                "db": ("DIRECTORY", {"description": "Kraken database directory"}),
                "input_sequences": (
                    "FASTQ",
                    {
                        "description": "Single-end FASTA or FASTQ reads",
                        "displayOptions": {"show": {"input_type": ["single"]}},
                    },
                ),
            },
            "optional": {
                "forward_input": (
                    "FASTQ",
                    {
                        "default": "",
                        "description": "Forward reads for paired input",
                        "displayOptions": {"show": {"input_type": ["paired"]}},
                    },
                ),
                "reverse_input": (
                    "FASTQ",
                    {
                        "default": "",
                        "description": "Reverse reads for paired input",
                        "displayOptions": {"show": {"input_type": ["paired"]}},
                    },
                ),
                "input_pair": (
                    "FASTQ_LIST",
                    {
                        "default": [],
                        "description": "Paired read collection as [forward, reverse] or mapping",
                        "displayOptions": {"show": {"input_type": ["paired_collection"]}},
                    },
                ),
                "input_format": (
                    "STRING",
                    {"default": "fastq", "options": ["fastq", "fasta"], "description": "Input read format"},
                ),
                "split_reads": (
                    "BOOLEAN",
                    {"default": False, "description": "Write classified and unclassified read outputs"},
                ),
                "quick": (
                    "STRING",
                    {"default": "no", "options": ["no", "yes"], "description": "Enable Kraken quick operation"},
                ),
                "min_hits": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "description": "Number of hits required for classification in quick mode",
                        "displayOptions": {"show": {"quick": ["yes"]}},
                    },
                ),
                "only_classified_output": (
                    "BOOLEAN",
                    {"default": False, "description": "Print no Kraken output for unclassified sequences"},
                ),
                "check_names": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Verify paired read names match",
                        "displayOptions": {"show": {"input_type": ["paired", "paired_collection"]}},
                    },
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class KrakenReportNode(CommandNode):
    """Generate a classic Kraken taxonomy report."""

    NODE_ID = "kraken_report"
    DISPLAY_NAME = "Kraken Report"
    REQUIRED_CONDA_PACKAGES = ["kraken"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Generate a tabular sample report from classic Kraken classification output."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Kraken Report",
        "kraken-report",
        "sample report",
        "taxonomy summary",
        "classification report",
        "NCBI taxonomy ID",
    ]
    RETURN_TYPES = ("KRAKEN_REPORT",)
    RETURN_NAMES = ("report",)
    REQUIRED_EXECUTABLES = ["kraken-report"]
    DOCUMENTATION_URL = "http://ccb.jhu.edu/software/kraken/"
    CITATION_DOIS = ["10.1186/gb-2014-15-3-r46"]
    CITATION_URLS = [f"{DOI_URL}10.1186/gb-2014-15-3-r46"]
    CITATION_TEXT = "Kraken: ultrafast metagenomic sequence classification using exact alignments."
    VERSION = "1.3.1"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/kraken_report.tsv"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("db", "")).strip():
            return "Kraken database is required"
        if not str(inputs.get("kraken_output", "")).strip():
            return "Kraken classification output is required"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "kraken-report",
            "--db",
            str(inputs.get("db", "")),
            str(inputs.get("kraken_output", "")),
        ]
        _add_shell_redirect(cmd, cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "kraken_report.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "kraken_output": (
                    "KRAKEN_OUTPUT",
                    {"description": "Taxonomy classification produced by Kraken"},
                ),
                "db": ("DIRECTORY", {"description": "Kraken database used for the original classification"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

class KrakenFilterNode(CommandNode):
    """Filter classic Kraken classification output by confidence threshold."""

    NODE_ID = "kraken_filter"
    DISPLAY_NAME = "Kraken Filter"
    REQUIRED_CONDA_PACKAGES = ["kraken"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Filter classic Kraken classification output by confidence score."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Kraken Filter",
        "kraken-filter",
        "confidence threshold",
        "classification filter",
        "taxonomy confidence",
        "unclassified",
    ]
    RETURN_TYPES = ("KRAKEN_OUTPUT",)
    RETURN_NAMES = ("filtered_output",)
    REQUIRED_EXECUTABLES = ["kraken-filter"]
    DOCUMENTATION_URL = "http://ccb.jhu.edu/software/kraken/"
    CITATION_DOIS = ["10.1186/gb-2014-15-3-r46"]
    CITATION_URLS = [f"{DOI_URL}10.1186/gb-2014-15-3-r46"]
    CITATION_TEXT = "Kraken: ultrafast metagenomic sequence classification using exact alignments."
    VERSION = "1.3.1"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/filtered_output.kraken"

    @classmethod
    def _threshold(cls, inputs: dict[str, Any]) -> float:
        return float(inputs.get("threshold", 0))

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("db", "")).strip():
            return "Kraken database is required"
        if not str(inputs.get("input", "")).strip():
            return "Kraken classification output is required"
        try:
            threshold = cls._threshold(inputs)
        except (TypeError, ValueError):
            return "Confidence threshold must be a number between 0 and 1"
        if not 0 <= threshold <= 1:
            return "Confidence threshold must be between 0 and 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "kraken-filter",
            "--db",
            str(inputs.get("db", "")),
            "--threshold",
            str(inputs.get("threshold", 0)),
            str(inputs.get("input", "")),
        ]
        _add_shell_redirect(cmd, cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "filtered_output.kraken"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "KRAKEN_OUTPUT",
                    {"description": "Taxonomy classification produced by Kraken"},
                ),
                "db": ("DIRECTORY", {"description": "Kraken database used for the original classification"}),
            },
            "optional": {
                "threshold": (
                    "FLOAT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 1,
                        "description": "Confidence threshold between 0 and 1",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class KrakenTranslateNode(CommandNode):
    """Convert classic Kraken taxonomy IDs to lineage names."""

    NODE_ID = "kraken_translate"
    DISPLAY_NAME = "Kraken Translate"
    REQUIRED_CONDA_PACKAGES = ["kraken"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Convert Kraken taxonomy IDs into taxonomic lineage names."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Kraken Translate",
        "kraken-translate",
        "taxonomy labels",
        "lineage names",
        "MPA format",
        "standard ranks",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("translated",)
    REQUIRED_EXECUTABLES = ["kraken-translate"]
    DOCUMENTATION_URL = "http://ccb.jhu.edu/software/kraken/"
    CITATION_DOIS = ["10.1186/gb-2014-15-3-r46"]
    CITATION_URLS = [f"{DOI_URL}10.1186/gb-2014-15-3-r46"]
    CITATION_TEXT = "Kraken: ultrafast metagenomic sequence classification using exact alignments."
    VERSION = "1.3.1"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/translated.tsv"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("db", "")).strip():
            return "Kraken database is required"
        if not str(inputs.get("input", "")).strip():
            return "Kraken classification output is required"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "kraken-translate",
            "--db",
            str(inputs.get("db", "")),
        ]
        if inputs.get("mpa_format", False):
            cmd.append("--mpa-format")
        cmd.append(str(inputs.get("input", "")))
        _add_shell_redirect(cmd, cls._output_path(inputs))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "translated.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "TSV",
                    {"description": "Taxonomy classification produced by Kraken"},
                ),
                "db": ("DIRECTORY", {"description": "Kraken database used for the original classification"}),
            },
            "optional": {
                "mpa_format": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Restrict labels to standard rank assignments in MPA format",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class KrakenMpaReportNode(CommandNode):
    """Generate a classic Kraken MPA-style multi-sample report."""

    NODE_ID = "kraken_mpa_report"
    DISPLAY_NAME = "Kraken MPA Report"
    REQUIRED_CONDA_PACKAGES = ["kraken"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Summarize classic Kraken classifications across taxonomic ranks for multiple samples."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Kraken MPA Report",
        "kraken-mpa-report",
        "multiple samples",
        "taxonomic ranks",
        "MetaPhlAn style",
        "show zeros",
        "header line",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output_report",)
    REQUIRED_EXECUTABLES = ["kraken-mpa-report"]
    DOCUMENTATION_URL = "http://ccb.jhu.edu/software/kraken/"
    CITATION_DOIS = ["10.1186/gb-2014-15-3-r46"]
    CITATION_URLS = [f"{DOI_URL}10.1186/gb-2014-15-3-r46"]
    CITATION_TEXT = "Kraken: ultrafast metagenomic sequence classification using exact alignments."
    VERSION = "1.3.1"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_report.tsv"

    @classmethod
    def _sample_names(cls, classifications: list[str], identifiers: list[str]) -> list[str]:
        names: list[str] = []
        for index, classification in enumerate(classifications):
            if index < len(identifiers) and identifiers[index]:
                name_base = str(identifiers[index]).replace("/", "-").replace("\t", "-")
            else:
                name_base = classification
            name = name_base
            duplicate_index = 1
            while name in names:
                name = f"{name_base}_{duplicate_index}"
                duplicate_index += 1
            names.append(name)
        return names

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("db", "")).strip():
            return "Kraken database is required"
        if not _as_list(inputs.get("classification")):
            return "At least one Kraken classification output is required"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        classifications = _as_list(inputs.get("classification"))
        names = cls._sample_names(classifications, _as_list(inputs.get("element_identifiers")))
        setup = [
            f"ln -s {shlex.quote(classification)} {shlex.quote(name)}"
            for classification, name in zip(classifications, names)
            if classification != name
        ]
        cmd = [
            "kraken-mpa-report",
            "--db",
            str(inputs.get("db", "")),
            *names,
        ]
        if inputs.get("show_zeros", False):
            cmd.append("--show-zeros")
        if inputs.get("header_line", False):
            cmd.append("--header-line")
        _add_shell_redirect(cmd, cls._output_path(inputs))
        rendered = _shell_join(cmd)
        if setup:
            return " && ".join([*setup, rendered])
        return rendered

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output_report.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "classification": (
                    "TSV",
                    {"multiple": True, "description": "One or more Kraken classification outputs"},
                ),
                "db": ("DIRECTORY", {"description": "Kraken database used for the original classification"}),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "description": "Optional Galaxy element identifiers for sample names"},
                ),
                "show_zeros": (
                    "BOOLEAN",
                    {"default": False, "description": "Display taxa even if they lack reads in every sample"},
                ),
                "header_line": (
                    "BOOLEAN",
                    {"default": False, "description": "Display a header line indicating sample IDs"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _Beacon2SearchBaseNode(CommandNode):
    """Shared command rendering for Beacon2 import wrappers that query MongoDB collections."""

    REQUIRED_CONDA_PACKAGES = ["beacon2-import"]
    CATEGORY = "metadata"
    REQUIRED_EXECUTABLES = ["beacon2-search"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tools/beacon2-import"
    CITATION_DOIS = [BEACON2_IMPORT_DOI]
    CITATION_URLS = [f"{DOI_URL}{BEACON2_IMPORT_DOI}"]
    CITATION_TEXT = BEACON2_IMPORT_CITATION_TEXT
    VERSION = "2.2.4+galaxy0"
    SHELL = True

    SEARCH_COLLECTION = ""
    OUTPUT_FILENAME = ""
    REQUIRED_QUERY_FLAGS: tuple[tuple[str, str, str, str], ...] = ()
    QUERY_FLAGS: tuple[tuple[str, str, str], ...] = ()
    TYPED_QUERY_FLAGS: tuple[tuple[str, str, str, str], ...] = ()
    QUERY_FLAG_OPTIONS: dict[str, list[str]] = {}

    @classmethod
    def _db_host(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("db_host", "127.0.0.1") or "127.0.0.1")

    @classmethod
    def _db_port(cls, inputs: dict[str, Any]) -> int:
        return int(inputs.get("db_port", 27017) or 27017)

    @classmethod
    def _credentials_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/beacon2_db_auth.json"

    @classmethod
    def _credentials_json(cls, inputs: dict[str, Any]) -> str:
        credentials = {
            "db_auth_source": str(inputs.get("db_auth_source", "admin") or "admin"),
            "db_user": str(inputs.get("db_user", "root") or "root"),
            "db_password": str(inputs.get("db_password", "example") or "example"),
        }
        return json.dumps(credentials, indent=2)

    @classmethod
    def _query_cmd(cls, inputs: dict[str, Any], credentials_path: str) -> list[str]:
        cmd = [
            "beacon2-search",
            cls.SEARCH_COLLECTION,
            "--db-host",
            cls._db_host(inputs),
            "--db-port",
            str(cls._db_port(inputs)),
            "--database",
            str(inputs.get("database", "")),
            "--collection",
            str(inputs.get("collection", "")),
            "--advance-connection",
            "--db-auth-config",
            credentials_path,
        ]
        for key, flag, _type_name, _description in cls.REQUIRED_QUERY_FLAGS:
            cmd.extend([flag, str(inputs.get(key, ""))])
        for key, flag, _description in cls.QUERY_FLAGS:
            value = inputs.get(key)
            if value is not None and str(value) != "":
                cmd.extend([flag, str(value)])
        cmd.extend([">", f"{_out(inputs)}/{cls.OUTPUT_FILENAME}"])
        return cmd

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        credentials_path = cls._credentials_path(inputs)
        config = f"cat > {shlex.quote(credentials_path)} <<'JSON'\n{cls._credentials_json(inputs)}\nJSON\n"
        return " && ".join(
            [
                f"mkdir -p {shlex.quote(out)}",
                f"{config}{_shell_join(cls._query_cmd(inputs, credentials_path))}",
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("database", "")).strip():
            return "database is required"
        if not str(inputs.get("collection", "")).strip():
            return "collection is required"
        try:
            cls._db_port(inputs)
        except (TypeError, ValueError):
            return "db_port must be an integer"
        for key, _flag, type_name, _description in cls.REQUIRED_QUERY_FLAGS:
            value = inputs.get(key)
            if value is None or str(value) == "":
                return f"{key} is required"
            if type_name == "INT":
                try:
                    int(value)
                except (TypeError, ValueError):
                    return f"{key} must be an integer"
        for key, _flag, type_name, _description in cls.TYPED_QUERY_FLAGS:
            value = inputs.get(key)
            if value is not None and str(value) != "":
                if type_name == "INT":
                    try:
                        int(value)
                    except (TypeError, ValueError):
                        return f"{key} must be an integer"
                options = cls.QUERY_FLAG_OPTIONS.get(key)
                if options is not None and str(value) not in options:
                    return f"{key} must be one of: {', '.join(options)}"
        for key, _flag, _description in cls.QUERY_FLAGS:
            value = inputs.get(key)
            options = cls.QUERY_FLAG_OPTIONS.get(key)
            if options is not None and value is not None and str(value) != "" and str(value) not in options:
                return f"{key} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        optional: dict[str, Any] = {
            "db_host": ("STRING", {"default": "127.0.0.1", "description": "Hostname or IP address of the Beacon MongoDB database"}),
            "db_port": ("INT", {"default": 27017, "description": "Port of the Beacon MongoDB database"}),
            "db_auth_source": (
                "STRING",
                {"default": "admin", "advanced": True, "description": "MongoDB authentication source for Beacon2 queries"},
            ),
            "db_user": (
                "STRING",
                {"default": "root", "advanced": True, "description": "MongoDB username for Beacon2 queries"},
            ),
            "db_password": (
                "STRING",
                {"default": "example", "advanced": True, "description": "MongoDB password for Beacon2 queries"},
            ),
        }
        for key, _flag, description in cls.QUERY_FLAGS:
            metadata: dict[str, Any] = {"default": "", "description": description}
            options = cls.QUERY_FLAG_OPTIONS.get(key)
            if options is not None:
                metadata["options"] = options
            optional[key] = ("STRING", metadata)
        for key, _flag, type_name, description in cls.TYPED_QUERY_FLAGS:
            metadata = {"default": "", "description": description}
            options = cls.QUERY_FLAG_OPTIONS.get(key)
            if options is not None:
                metadata["options"] = options
            optional[key] = (type_name, metadata)
        required: dict[str, Any] = {
            "database": ("STRING", {"description": "Targeted Beacon database"}),
            "collection": ("STRING", {"description": "Targeted Beacon collection in the selected database"}),
        }
        for key, _flag, type_name, description in cls.REQUIRED_QUERY_FLAGS:
            required[key] = (type_name, {"description": description})
        return {
            "required": required,
            "optional": optional,
            "hidden": {"output": ("STRING", {})},
        }

class Beacon2AnalysesNode(_Beacon2SearchBaseNode):
    """Query the analyses collection in a Beacon database."""

    NODE_ID = "beacon2_analyses"
    DISPLAY_NAME = "Beacon2 Analyses"
    DESCRIPTION = "Query the analyses collection in a Beacon database for bioinformatic procedures that identify variants."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beacon2",
        "Beacon v2",
        "beacon2_analyses",
        "Beacon2 Analyses",
        "beacon2-search analyses",
        "analyses collection",
        "bioinformatic procedures",
        "variant caller",
        "pipelineName",
    ]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("out_analyses_query",)
    SEARCH_COLLECTION = "analyses"
    OUTPUT_FILENAME = "analyses_query_findings.json"
    QUERY_FLAGS = (
        ("aligner", "--aligner", "Reference to mapping or alignment software, such as bwa-0.7.8"),
        ("analysisDate", "--analysisDate", "Date at which analysis was performed"),
        ("biosampleId", "--biosampleId", "ID of the biosample this analysis reports on"),
        ("identification", "--identification", "Analysis reference ID, external accession, or internal ID"),
        ("individualId", "--individualId", "ID of the individual this analysis reports on"),
        ("pipelineName", "--pipelineName", "Analysis pipeline and version"),
        ("pipelineRef", "--pipelineRef", "Link to the analysis pipeline resource"),
        ("runId", "--runId", "Run identifier, external accession, or internal ID"),
        ("variantCaller", "--variantCaller", "Variant calling software or pipeline"),
    )

class Beacon2BiosamplesNode(_Beacon2SearchBaseNode):
    """Query the biosamples collection in a Beacon database."""

    NODE_ID = "beacon2_biosamples"
    DISPLAY_NAME = "Beacon2 Biosamples"
    DESCRIPTION = "Query the biosamples collection in a Beacon database for samples taken from individuals."
    VERSION = "1.0.0"
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beacon2",
        "Beacon v2",
        "beacon2_biosamples",
        "Beacon2 Biosamples",
        "beacon2-search biosamples",
        "biosamples collection",
        "samples taken from individuals",
        "biosampleStatus",
        "sampleOriginDetail",
        "tumorProgression",
    ]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("out_biosamples_query",)
    SEARCH_COLLECTION = "biosamples"
    OUTPUT_FILENAME = "biosamples_query_findings.json"
    QUERY_FLAGS = (
        ("biosampleStatus", "--biosampleStatus", "Ontology value classifying the sample status"),
        ("collectionDate", "--collectionDate", "Date of biosample collection in ISO8601 format"),
        ("collectionMoment", "--collectionMoment", "Age or duration at sample collection in ISO8601 duration format"),
        ("identification", "--identification", "Biosample identifier, external accession, or internal ID"),
        ("diagnosticMarkers", "--diagnosticMarkers", "Clinically relevant biomarkers"),
        ("histologicalDiagnosis", "--histologicalDiagnosis", "Diagnosis inferred from histological examination"),
        ("obtentionProcedure", "--obtentionProcedure", "Ontology value describing the sample obtention procedure"),
        ("pathologicalStage", "--pathologicalStage", "Pathological stage, if applicable"),
        ("pathologicalTnmFinding", "--pathologicalTnmFinding", "Pathological TNM finding"),
        ("featureType", "--featureType", "Ontology term describing a phenotype feature"),
        ("severity", "--severity", "Ontology class describing condition severity"),
        ("sampleOriginDetail", "--sampleOriginDetail", "Tissue or sample-origin detail"),
        ("sampleOriginType", "--sampleOriginType", "Category of sample origin"),
        ("sampleProcessing", "--sampleProcessing", "Specimen processing status"),
        ("sampleStorage", "--sampleStorage", "Specimen storage status"),
        ("tumorGrade", "--tumorGrade", "Tumor grade term"),
        ("tumorProgression", "--tumorProgression", "Tumor progression category"),
    )

class Beacon2BracketNode(_Beacon2SearchBaseNode):
    """Query Beacon genomic variations by bracketed start and end ranges."""

    NODE_ID = "beacon2_bracket"
    DISPLAY_NAME = "Beacon2 Bracket"
    DESCRIPTION = "Query Beacon genomic variations by sequence ranges for both start and end positions."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beacon2",
        "Beacon v2",
        "beacon2_bracket",
        "Beacon2 Bracket",
        "beacon2-search bracket",
        "bracket query",
        "genomic variation range",
        "copy number variation",
        "structural variant range",
    ]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("out_bracket_query",)
    SEARCH_COLLECTION = "bracket"
    OUTPUT_FILENAME = "bracket_query_findings.json"
    REQUIRED_QUERY_FLAGS = (
        ("start_minimum", "--start-minimum", "INT", "Minimum start position of the genomic variation"),
        ("start_maximum", "--start-maximum", "INT", "Maximum start position of the genomic variation"),
        ("end_minimum", "--end-minimum", "INT", "Minimum end position of the genomic variation"),
        ("end_maximum", "--end-maximum", "INT", "Maximum end position of the genomic variation"),
    )
    QUERY_FLAGS = (
        ("variantType", "--variantType", "Targeted variant type to search for"),
        ("referenceName", "--referenceName", "Reference name such as chr1/1, chr2/2, chr3/3"),
    )

class Beacon2CNVNode(_Beacon2SearchBaseNode):
    """Query Beacon copy number variants from genomicVariations."""

    NODE_ID = "beacon2_cnv"
    DISPLAY_NAME = "Beacon2 CNV"
    DESCRIPTION = "Query copy number variants from the Beacon genomicVariations collection with optional overlap filters."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beacon2",
        "Beacon v2",
        "beacon2_cnv",
        "Beacon2 CNV",
        "beacon2-search cnv",
        "copy number variants",
        "genomicVariations",
        "variantStateId",
        "copy number loss",
        "copy number gain",
    ]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("out_cnv_query",)
    SEARCH_COLLECTION = "cnv"
    OUTPUT_FILENAME = "cnv_query_findings.json"
    VARIANT_STATE_OPTIONS = [
        "",
        "EFO:0030070",
        "EFO:0030071",
        "EFO:0030072",
        "EFO:0030073",
        "EFO:0030067",
        "EFO:0030068",
        "EFO:0020073",
        "EFO:0030069",
    ]
    QUERY_FLAGS = (
        ("variantInternalId", "--variantInternalId", "Variant internal ID, such as 11:52900000-134452384:DEL"),
        ("analysisId", "--analysisId", "Analysis identifier"),
        ("individualId", "--individualId", "Individual identifier"),
        ("start", "--start", "Start position"),
        ("end", "--end", "End position"),
        ("chromosome", "--chromosome", "Chromosome number without chr prefix"),
        ("variantStateId", "--variantStateId", "Copy-number state ontology term"),
        ("sequenceId", "--sequenceId", "Reference sequence ID, such as refseq:NC_000011.10"),
        ("variantType", "--variantType", "Variant type such as DEL or DUP"),
        ("primarySite", "--primarySite", "Primary site, such as breast or brain"),
        ("diseaseType", "--diseaseType", "Disease type"),
        ("gene", "--gene", "Gene name, such as BRCA1"),
    )
    TYPED_QUERY_FLAGS = (
        ("start", "--start", "INT", "Start position"),
        ("end", "--end", "INT", "End position"),
    )
    QUERY_FLAG_OPTIONS = {"variantStateId": VARIANT_STATE_OPTIONS}

class Beacon2CohortsNode(_Beacon2SearchBaseNode):
    """Query the cohorts collection in a Beacon database."""

    NODE_ID = "beacon2_cohorts"
    DISPLAY_NAME = "Beacon2 Cohorts"
    DESCRIPTION = "Query the cohorts collection in a Beacon database for populations or groups sharing common attributes."
    VERSION = "1.0.0"
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beacon2",
        "Beacon v2",
        "beacon2_cohorts",
        "Beacon2 Cohorts",
        "beacon2-search cohorts",
        "cohorts collection",
        "cohortDataTypes",
        "cohortType",
        "genders",
    ]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("out_cohorts_query",)
    SEARCH_COLLECTION = "cohorts"
    OUTPUT_FILENAME = "cohorts_query_findings.json"
    QUERY_FLAGS = (
        ("cohortDataTypes", "--cohortDataTypes", "Type of cohort data, such as clinical history"),
        ("cohortDesign", "--cohortDesign", "Study-design plan or protocol, such as longitudinal study design"),
        ("cohortSize", "--cohortSize", "Count of unique individuals in the cohort"),
        ("identification", "--identification", "Cohort identifier, such as cohort0001"),
        ("cohortType", "--cohortType", "Cohort type by definition, such as study-defined"),
        ("genders", "--genders", "Gender filter for the cohort"),
        ("name", "--name", "Name of the cohort"),
    )
    TYPED_QUERY_FLAGS = (
        ("cohortSize", "--cohortSize", "INT", "Count of unique individuals in the cohort"),
    )
    QUERY_FLAG_OPTIONS = {"genders": ["", "male", "female"]}

class Beacon2DatasetsNode(_Beacon2SearchBaseNode):
    """Query the datasets collection in a Beacon database."""

    NODE_ID = "beacon2_datasets"
    DISPLAY_NAME = "Beacon2 Datasets"
    DESCRIPTION = "Query the datasets collection in a Beacon database for repositories containing variants or individuals."
    VERSION = "1.0.0"
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beacon2",
        "Beacon v2",
        "beacon2_datasets",
        "Beacon2 Datasets",
        "beacon2-search datasets",
        "datasets collection",
        "dataUseConditions",
        "ontologyModifiers",
        "repository",
    ]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("out_datasets_query",)
    SEARCH_COLLECTION = "datasets"
    OUTPUT_FILENAME = "datasets_query_findings.json"
    QUERY_FLAGS = (
        ("dataUseConditions", "--dataUseConditions", "Data-use conditions applying to this dataset"),
        ("ontologyModifiers", "--ontologyModifiers", "Ontology modifiers that further specify the dataset"),
        ("identification", "--identification", "Unique identifier of the dataset"),
        ("name", "--name", "Name of the dataset"),
    )

class Beacon2GeneNode(_Beacon2SearchBaseNode):
    """Query Beacon genomic variants by gene symbol."""

    NODE_ID = "beacon2_gene"
    DISPLAY_NAME = "Beacon2 Gene"
    DESCRIPTION = "Query Beacon genomic variants by HGNC gene symbol."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beacon2",
        "Beacon v2",
        "beacon2_gene",
        "Beacon2 Gene",
        "beacon2-search gene",
        "geneId",
        "HGNC gene symbol",
        "genomic variants",
        "aminoacidChange",
    ]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("out_gene_query",)
    SEARCH_COLLECTION = "gene"
    OUTPUT_FILENAME = "gene_query_findings.json"
    REQUIRED_QUERY_FLAGS = (
        ("geneId", "--geneId", "STRING", "HGNC gene symbol used to query Beacon variants"),
    )
    QUERY_FLAGS = (
        ("alternateBases", "--alternateBases", "Targeted alternate bases to search for"),
        ("variantType", "--variantType", "Targeted variant type to search for"),
        ("aminoacidChange", "--aminoacidChange", "Targeted amino-acid change to search for"),
        ("variantMinLength", "--variantMinLength", "Targeted minimum variant length"),
        ("variantMaxLength", "--variantMaxLength", "Targeted maximum variant length"),
    )
    TYPED_QUERY_FLAGS = (
        ("variantMinLength", "--variantMinLength", "INT", "Targeted minimum variant length"),
        ("variantMaxLength", "--variantMaxLength", "INT", "Targeted maximum variant length"),
    )

class Beacon2IndividualsNode(_Beacon2SearchBaseNode):
    """Query the individuals collection in a Beacon database."""

    NODE_ID = "beacon2_individuals"
    DISPLAY_NAME = "Beacon2 Individuals"
    DESCRIPTION = "Query the individuals collection in a Beacon database for patients or healthy controls."
    VERSION = "1.0.0"
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beacon2",
        "Beacon v2",
        "beacon2_individuals",
        "Beacon2 Individuals",
        "beacon2-search individuals",
        "individuals collection",
        "patients",
        "healthy controls",
        "geographicOrigin",
        "familyHistory",
    ]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("out_individuals_query",)
    SEARCH_COLLECTION = "individuals"
    OUTPUT_FILENAME = "individuals_query_findings.json"
    QUERY_FLAGS = (
        ("ageGroup", "--ageGroup", "Age group or age at onset, such as Adult 18-65 Years Old"),
        ("diseaseCode", "--diseaseCode", "Disease code or label"),
        ("familyHistory", "--familyHistory", "Family-history flag"),
        ("severity", "--severity", "Clinical severity"),
        ("stage", "--stage", "Disease stage"),
        ("ethnicity", "--ethnicity", "Ethnicity term or label"),
        ("geographicOrigin", "--geographicOrigin", "Geographic origin term or label"),
        ("identification", "--identification", "Individual identifier or internal ID"),
        ("assayCode", "--assayCode", "Assay code or label"),
        ("sex", "--sex", "Sex filter"),
    )
    QUERY_FLAG_OPTIONS = {
        "familyHistory": ["", "true", "false"],
        "sex": ["", "male", "female"],
    }

class Beacon2RangeNode(_Beacon2SearchBaseNode):
    """Query Beacon genomic variants by sequence range."""

    NODE_ID = "beacon2_range"
    DISPLAY_NAME = "Beacon2 Range"
    DESCRIPTION = "Query Beacon genomic variants overlapping a start and end position range."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beacon2",
        "Beacon v2",
        "beacon2_range",
        "Beacon2 Range",
        "beacon2-search range",
        "range query",
        "genomic variants",
        "start",
        "end",
        "referenceName",
    ]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("out_ranged_query",)
    SEARCH_COLLECTION = "range"
    OUTPUT_FILENAME = "ranged_query_findings.json"
    REQUIRED_QUERY_FLAGS = (
        ("start", "--start", "INT", "Start position"),
        ("end", "--end", "INT", "End position"),
    )
    QUERY_FLAGS = (
        ("referenceName", "--referenceName", "Reference name such as chr1/1, chr2/2, chr3/3"),
        ("alternateBases", "--alternateBases", "Targeted alternate bases to search for"),
        ("variantType", "--variantType", "Targeted variant type to search for"),
        ("aminoacidChange", "--aminoacidChange", "Targeted amino-acid change to search for"),
        ("variantMinLength", "--variantMinLength", "Targeted minimum variant length"),
        ("variantMaxLength", "--variantMaxLength", "Targeted maximum variant length"),
    )
    TYPED_QUERY_FLAGS = (
        ("variantMinLength", "--variantMinLength", "INT", "Targeted minimum variant length"),
        ("variantMaxLength", "--variantMaxLength", "INT", "Targeted maximum variant length"),
    )

class Beacon2RunsNode(_Beacon2SearchBaseNode):
    """Query the runs collection in a Beacon database."""

    NODE_ID = "beacon2_runs"
    DISPLAY_NAME = "Beacon2 Runs"
    DESCRIPTION = "Query the runs collection in a Beacon database for sequencing and library preparation metadata."
    VERSION = "1.0.0"
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beacon2",
        "Beacon v2",
        "beacon2_runs",
        "Beacon2 Runs",
        "beacon2-search runs",
        "runs collection",
        "sequencing runs",
        "libraryLayout",
        "librarySource",
        "platformModel",
    ]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("out_runs_query",)
    SEARCH_COLLECTION = "runs"
    OUTPUT_FILENAME = "runs_query_findings.json"
    QUERY_FLAGS = (
        ("identification", "--identification", "Run identifier"),
        ("individualId", "--individualId", "Reference to the individual ID, such as TCGA-AO-A0JJ"),
        ("libraryLayout", "--libraryLayout", "Library layout, such as PAIRED or SINGLE"),
        ("librarySelection", "--librarySelection", "Selection method for library preparation, such as RANDOM or RT-PCR"),
        ("librarySource", "--librarySource", "Source of the sequencing or hybridization library"),
        ("libraryStrategy", "--libraryStrategy", "Library strategy, such as WGS"),
        ("platform", "--platform", "General platform technology label, such as Illumina"),
        ("platformModel", "--platformModel", "Experimental platform model or methodology, such as Illumina HiSeq 3000"),
        ("runDate", "--runDate", "Date at which the experiment was performed"),
    )

class Beacon2SequenceNode(_Beacon2SearchBaseNode):
    """Query Beacon for a precise alternate/reference sequence."""

    NODE_ID = "beacon2_sequence"
    DISPLAY_NAME = "Beacon2 Sequence"
    DESCRIPTION = "Query Beacon for the existence of a specified sequence at a genomic position."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Beacon2",
        "Beacon v2",
        "beacon2_sequence",
        "Beacon2 Sequence",
        "beacon2-search sequence",
        "sequence query",
        "alternateBases",
        "referenceBases",
        "SNV",
        "INDEL",
    ]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("out_sequence_query",)
    SEARCH_COLLECTION = "sequence"
    OUTPUT_FILENAME = "sequenced_query_findings.json"
    REQUIRED_QUERY_FLAGS = (
        ("alternateBases", "--alternateBases", "STRING", "Alternate bases to query for"),
        ("referenceBases", "--referenceBases", "STRING", "Reference bases to query against"),
    )
    QUERY_FLAGS = (
        ("referenceName", "--referenceName", "Reference name such as chr1/1, chr2/2, chr3/3"),
        ("start", "--start", "Start position"),
        ("collectionIds", "--collectionIds", "Dataset or collection ID filter"),
    )
    TYPED_QUERY_FLAGS = (
        ("start", "--start", "INT", "Start position"),
    )

class Kaiju2TableNode(CommandNode):
    """Summarize Kaiju classifications by taxonomic rank."""

    NODE_ID = "kaiju2table"
    DISPLAY_NAME = "Kaiju2Table"
    REQUIRED_CONDA_PACKAGES = ["kaiju"]
    CATEGORY = "taxonomy"
    DESCRIPTION = "Convert one or more Kaiju classification outputs into summary tables by taxonomic rank."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "kaiju",
        "kaiju2table",
        "summary table",
        "minimum reporting percentage",
        "taxonomic rank",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("summary_table",)
    REQUIRED_EXECUTABLES = ["kaiju2table"]
    DOCUMENTATION_URL = KaijuNode.DOCUMENTATION_URL
    CITATION_DOIS = KaijuNode.CITATION_DOIS
    CITATION_URLS = KaijuNode.CITATION_URLS
    CITATION_TEXT = KaijuNode.CITATION_TEXT
    VERSION = KaijuNode.VERSION
    SHELL = True

    @classmethod
    def _linked_names(cls, inputs: dict[str, Any], tables: list[str]) -> list[str]:
        labels = _as_list(inputs.get("element_identifiers"))
        names: list[str] = []
        for index, table in enumerate(tables):
            label = labels[index] if index < len(labels) and labels[index] else table
            names.append(_safe_identifier(label))
        return names

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        tables = _as_list(inputs.get("kaiju_tables"))
        linked_names = cls._linked_names(inputs, tables)
        commands = [
            f"ln -sf {shlex.quote(table)} {shlex.quote(linked_name)}"
            for table, linked_name in zip(tables, linked_names, strict=False)
        ]

        reference = str(inputs.get("reference_database", "")).rstrip("/")
        cmd = [
            "kaiju2table",
            "-t",
            f"{reference}/nodes.dmp",
            "-n",
            f"{reference}/names.dmp",
            "-r",
            str(inputs.get("rank", "phylum")),
            "-o",
            f"{out}/kaiju_summary.tsv",
        ]
        _add_if_value(cmd, "-m", inputs.get("minimum_percentage"))
        _add_if_value(cmd, "-c", inputs.get("minimum_reads"))
        if inputs.get("expand_viruses", False):
            cmd.append("-e")
        if inputs.get("exclude_unclassified", False):
            cmd.append("-u")

        tax_path_report = str(inputs.get("tax_path_report", ""))
        if tax_path_report == "full":
            cmd.append("-p")
        elif tax_path_report == "partial":
            selected_ranks = ",".join(_as_list(inputs.get("selected_ranks")))
            if selected_ranks:
                cmd.extend(["-l", selected_ranks])

        cmd.extend(linked_names)
        commands.append(shlex.join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "kaiju_summary.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "kaiju_tables": (
                    "TSV",
                    {"multiple": True, "description": "One or more Kaiju output tables"},
                ),
                "reference_database": (
                    "DIRECTORY",
                    {"description": "Kaiju database directory containing nodes.dmp and names.dmp"},
                ),
                "rank": (
                    "STRING",
                    {
                        "default": "phylum",
                        "options": ["phylum", "class", "order", "family", "genus", "species"],
                        "description": "Taxonomic rank to summarize",
                    },
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional sample labels matching the input table order",
                    },
                ),
                "minimum_percentage": (
                    "FLOAT",
                    {
                        "default": "",
                        "min": 0,
                        "max": 100,
                        "description": "Minimum reporting percentage; cannot be combined with minimum_reads",
                    },
                ),
                "minimum_reads": (
                    "INT",
                    {
                        "default": "",
                        "min": 1,
                        "description": "Minimum required number of reads; cannot be combined with minimum_percentage",
                    },
                ),
                "expand_viruses": (
                    "BOOLEAN",
                    {"default": False, "description": "Always show viruses as full taxon paths"},
                ),
                "exclude_unclassified": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not count unclassified reads in percentage totals"},
                ),
                "tax_path_report": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "full", "partial"],
                        "description": "Report full or selected taxonomic paths instead of only the selected rank",
                    },
                ),
                "selected_ranks": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Ranks included when tax_path_report is partial",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
