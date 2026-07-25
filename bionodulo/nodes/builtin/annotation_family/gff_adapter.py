"""GTF/GFF annotation conversion and comparison nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_beacon_ucsc_family.adapter import (
    GFFCOMPARE_GIT_COMMIT,
    GFFCOMPARE_GIT_URL,
    GFFREAD_GIT_COMMIT,
    GFFREAD_GIT_URL,
    KENT_357_GIT_COMMIT,
    KENT_GIT_URL,
    pin_contract,
)

class GtfToBed12Node(CommandNode):
    """Convert GTF gene annotations to BED12."""

    LEGACY_NODE_ID = "gtftobed12"
    DISPLAY_NAME = "Convert GTF to BED12"
    REQUIRED_CONDA_PACKAGES = ["ucsc-gtftogenepred", "ucsc-genepredtobed"]
    CATEGORY = "genomics"
    DESCRIPTION = "Convert a GTF gene annotation to blocked BED12 using UCSC gtfToGenePred and genePredToBed."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "gtfToBed12",
        "gtftobed12",
        "GTF to BED12",
        "gtfToGenePred",
        "genePredToBed",
        "gene annotation conversion",
        "transcript info",
    ]
    RETURN_TYPES = ("BED", "TSV")
    RETURN_NAMES = ("bed_file", "transcript_info_file")
    REQUIRED_EXECUTABLES = ["gtfToGenePred", "genePredToBed"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/utils/gtfToGenePred/gtfToGenePred.c"
    CITATION_DOIS = [UCSC_GENOME_BROWSER_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_GENOME_BROWSER_CITATION_DOI}"]
    CITATION_TEXT = UCSC_GENOME_BROWSER_CITATION_TEXT
    VERSION = "357"
    SHELL = True

    ADVANCED_OPTIONS = ["default", "advanced"]
    FLAG_INPUTS = (
        ("ignoreGroupsWithoutExons", "-ignoreGroupsWithoutExons"),
        ("simple", "-simple"),
        ("allErrors", "-allErrors"),
        ("impliedStopAfterCds", "-impliedStopAfterCds"),
        ("includeVersion", "-includeVersion"),
    )

    @classmethod
    def _advanced_options_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("advanced_options_selector", "default") or "default")

    @classmethod
    def _bed_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/converted.bed"

    @classmethod
    def _genepred_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/temp.genePred"

    @classmethod
    def _transcript_info_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/transcript_info.tsv"

    @classmethod
    def _writes_transcript_info(cls, inputs: dict[str, Any]) -> bool:
        return cls._advanced_options_selector(inputs) == "advanced" and bool(inputs.get("infoOut", False))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        gtf_cmd = ["gtfToGenePred"]
        if cls._advanced_options_selector(inputs) == "advanced":
            for name, flag in cls.FLAG_INPUTS:
                if inputs.get(name):
                    gtf_cmd.append(flag)
            if inputs.get("infoOut"):
                gtf_cmd.append(f"-infoOut={cls._transcript_info_path(inputs)}")
            for prefix in _as_list(inputs.get("sourcePrefixes")):
                gtf_cmd.append(f"-sourcePrefix={prefix}")
        gtf_cmd.extend([str(inputs.get("gtf_file", "")), cls._genepred_path(inputs)])
        bed_cmd = ["genePredToBed", cls._genepred_path(inputs), cls._bed_path(inputs)]
        return f"{_shell_join(gtf_cmd)} && {_shell_join(bed_cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "converted.bed"]
        if cls._writes_transcript_info(inputs):
            outputs.append(out / "transcript_info.tsv")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("gtf_file", "")).strip():
            return "gtf_file is required"
        selector = cls._advanced_options_selector(inputs)
        if selector not in cls.ADVANCED_OPTIONS:
            return f"advanced_options_selector must be one of: {', '.join(cls.ADVANCED_OPTIONS)}"
        prefixes = _as_list(inputs.get("sourcePrefixes"))
        if selector != "advanced" and prefixes:
            return "sourcePrefixes can only be used when advanced_options_selector is advanced"
        if any(not prefix.strip() for prefix in prefixes):
            return "sourcePrefixes cannot contain blank values"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gtf_file": ("GTF", {"description": "GTF gene annotation file to convert to BED12"}),
            },
            "optional": {
                "advanced_options_selector": (
                    "STRING",
                    {
                        "default": "default",
                        "options": cls.ADVANCED_OPTIONS,
                        "description": "Use default conversion settings or expose gtfToGenePred advanced options",
                    },
                ),
                "sourcePrefixes": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Only process GTF entries whose source field starts with one of these prefixes",
                    },
                ),
                "ignoreGroupsWithoutExons": (
                    "BOOLEAN",
                    {"default": False, "description": "Skip transcript groups that do not contain exons"},
                ),
                "simple": (
                    "BOOLEAN",
                    {"default": False, "description": "Check only column validity instead of the full GTF hierarchy"},
                ),
                "allErrors": (
                    "BOOLEAN",
                    {"default": False, "description": "Skip groups with errors rather than aborting at the first error"},
                ),
                "impliedStopAfterCds": (
                    "BOOLEAN",
                    {"default": False, "description": "Assume an implied stop codon after the CDS"},
                ),
                "includeVersion": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Include gene_version and transcript_version attributes in output identifiers",
                    },
                ),
                "infoOut": (
                    "BOOLEAN",
                    {"default": False, "description": "Write a transcript information table from gtfToGenePred"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class GffReadNode(CommandNode):
    """Filter, convert, and extract sequence from GFF/GTF/BED annotations."""

    LEGACY_NODE_ID = "gffread"
    DISPLAY_NAME = "gffread"
    REQUIRED_CONDA_PACKAGES = ["gffread"]
    CATEGORY = "annotation"
    DESCRIPTION = "Filter, convert, cluster, and extract sequences from GFF3, GTF, or BED annotations."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "gffread",
        "GffRead",
        "GFF Utilities",
        "GTF to GFF3",
        "GFF3 to GTF",
        "GFF to BED",
        "annotation conversion",
        "extract transcript FASTA",
        "transcript clustering",
    ]
    RETURN_TYPES = ("GFF3", "GTF", "BED", "FASTA", "FASTA", "FASTA", "TXT")
    RETURN_NAMES = (
        "output_gff",
        "output_gtf",
        "output_bed",
        "output_exons",
        "output_cds",
        "output_pep",
        "output_dupinfo",
    )
    REQUIRED_EXECUTABLES = ["gffread"]
    DOCUMENTATION_URL = "https://github.com/gpertea/gffread"
    CITATION_DOIS = [GFFREAD_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{GFFREAD_CITATION_DOI}"]
    CITATION_TEXT = GFFREAD_CITATION_TEXT
    VERSION = "0.12.7"
    SHELL = True

    GFF_FORMATS = ["none", "gff", "gtf", "bed"]
    FILTERING_OPTIONS = ["-U", "-C", "-G", "-O", "--no-pseudo"]
    REFERENCE_SOURCES = ["none", "cached", "history"]
    REF_FILTERING_OPTIONS = ["-N", "-J", "-V", "-H"]
    FA_OUTPUTS = ["exons", "cds", "pep", "project_coords", "stop_star"]
    MERGE_SELS = ["none", "merge", "cluster"]
    MERGE_OPTIONS = ["force_exons", "merge_close_exons", "collapse_contained", "relaxed_containment", "dupinfo"]
    MERGE_OPTION_FLAGS = {
        "force_exons": "--force-exons",
        "merge_close_exons": "-Z",
        "collapse_contained": "-K",
        "relaxed_containment": "-Q",
    }
    RANGE_PATTERN = re.compile(r"^([+-]?[\w.-]+:)?\d+\.\.\d+$")

    @classmethod
    def _gff_fmt(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("gff_fmt", "none") or "none")

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        fmt = cls._gff_fmt(inputs)
        return "gff" if fmt == "none" else fmt

    @classmethod
    def _output_filename(cls, inputs: dict[str, Any]) -> str:
        return f"output.{cls._output_format(inputs)}"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._output_filename(inputs)}"

    @classmethod
    def _writes_annotation_output(cls, inputs: dict[str, Any]) -> bool:
        sequence_outputs = {"exons", "cds", "pep"}.intersection(cls._selected_fa_outputs(inputs))
        return cls._gff_fmt(inputs) != "none" or not sequence_outputs

    @classmethod
    def _reference_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("reference_genome_source", "none") or "none")

    @classmethod
    def _dupinfo_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/dupinfo.txt"

    @classmethod
    def _quoted_dupinfo_option(cls, inputs: dict[str, Any]) -> str:
        return "'" + f"-d={cls._dupinfo_path(inputs)}".replace("'", "'\"'\"'") + "'"

    @classmethod
    def _selected_fa_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("fa_outputs"))

    @classmethod
    def _selected_merge_options(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("merge_options"))

    @classmethod
    def _add_reference(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        source = cls._reference_source(inputs)
        if source == "history":
            cmd.extend(["-g", "genomeref.fa"])
        elif source == "cached":
            cmd.extend(["-g", str(inputs.get("fasta_index_path", inputs.get("fasta_index", "")))])
        if source != "none":
            cmd.extend(_as_list(inputs.get("ref_filtering")))

    @classmethod
    def _add_merge_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        merge_sel = str(inputs.get("merge_sel", "none") or "none")
        if merge_sel == "merge":
            cmd.append("--merge")
        elif merge_sel == "cluster":
            cmd.append("--cluster-only")
        if merge_sel == "none":
            return
        for option in cls._selected_merge_options(inputs):
            if option == "dupinfo":
                cmd.extend(["-d", cls._dupinfo_path(inputs)])
            else:
                cmd.append(cls.MERGE_OPTION_FLAGS[option])

    @classmethod
    def _add_fasta_outputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        out = _out(inputs)
        for value in cls._selected_fa_outputs(inputs):
            if value == "exons":
                cmd.extend(["-w", f"{out}/exons.fa"])
            elif value == "cds":
                cmd.extend(["-x", f"{out}/cds.fa"])
            elif value == "pep":
                cmd.extend(["-y", f"{out}/pep.fa"])
            elif value == "project_coords":
                cmd.append("-W")
            elif value == "stop_star":
                cmd.append("-S")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["gffread", str(inputs.get("input", ""))]
        if str(inputs.get("input_format", "")).lower() == "bed" or str(inputs.get("input", "")).lower().endswith(".bed"):
            cmd.append("--in-bed")
        cls._add_reference(cmd, inputs)
        cmd.extend(_as_list(inputs.get("filtering")))
        if str(inputs.get("maxintron", "")) not in {"", "0"}:
            cmd.extend(["-i", str(inputs.get("maxintron"))])
        if str(inputs.get("region_filter", "none") or "none") == "filter":
            cmd.extend(["-r", str(inputs.get("range", ""))])
            if inputs.get("discard_partial"):
                cmd.append("-R")
        cls._add_merge_options(cmd, inputs)
        if inputs.get("chr_replace"):
            cmd.append(f"-m={inputs.get('chr_replace')}")
        if inputs.get("full_gff_attribute_preservation"):
            cmd.append("-F")
        if inputs.get("decode_url"):
            cmd.append("-D")
        if inputs.get("expose"):
            cmd.append("-E")
        cls._add_fasta_outputs(cmd, inputs)
        gff_fmt = cls._gff_fmt(inputs)
        if gff_fmt != "none":
            if gff_fmt != "bed" and inputs.get("tname"):
                cmd.extend(["-t", str(inputs.get("tname"))])
            if gff_fmt == "gtf":
                cmd.append("-T")
            elif gff_fmt == "bed":
                cmd.append("--bed")
            elif inputs.get("ensembl"):
                cmd.append("-L")
            cmd.extend(["-o", cls._output_path(inputs)])
        elif cls._writes_annotation_output(inputs):
            cmd.extend(["-o", cls._output_path(inputs)])

        command = _shell_join(cmd)
        if cls._reference_source(inputs) == "history":
            reference = f"{_out(inputs)}/genomeref.fa"
            command = command.replace("-g genomeref.fa", f"-g {shlex.quote(reference)}")
            setup = _shell_join(["ln", "-s", str(inputs.get("genome_fasta", "")), reference])
            return f"{setup} && {command}"
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        if cls._writes_annotation_output(inputs):
            outputs.append(out / cls._output_filename(inputs))
        fa_outputs = cls._selected_fa_outputs(inputs)
        if "exons" in fa_outputs:
            outputs.append(out / "exons.fa")
        if "cds" in fa_outputs:
            outputs.append(out / "cds.fa")
        if "pep" in fa_outputs:
            outputs.append(out / "pep.fa")
        if str(inputs.get("merge_sel", "none") or "none") != "none" and "dupinfo" in cls._selected_merge_options(inputs):
            outputs.append(out / "dupinfo.txt")
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        """Bind the selected dynamic artifacts to stable public output ports."""
        output_names = {
            "output.gff": "output_gff",
            "output.gtf": "output_gtf",
            "output.bed": "output_bed",
            "exons.fa": "output_exons",
            "cds.fa": "output_cds",
            "pep.fa": "output_pep",
            "dupinfo.txt": "output_dupinfo",
        }
        mapped: dict[str, Path] = {}
        for path in map(Path, planned_paths):
            output_name = output_names.get(path.name)
            if output_name is None:
                raise ValueError(f"gffread planned an unknown output artifact: {path.name}")
            if output_name in mapped:
                raise ValueError(f"gffread planned duplicate output artifact: {path.name}")
            mapped[output_name] = path
        if not mapped:
            raise ValueError("gffread must plan at least one physical output artifact")
        return mapped

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        result = await super().run(**kwargs)
        mapped = self.__class__.MAP_PLANNED_OUTPUTS([Path(path) for path in result])
        return {"outputs": {name: str(path) for name, path in mapped.items()}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        gff_fmt = cls._gff_fmt(inputs)
        if gff_fmt not in cls.GFF_FORMATS:
            return f"gff_fmt must be one of: {', '.join(cls.GFF_FORMATS)}"
        filtering = _as_list(inputs.get("filtering"))
        if any(value not in cls.FILTERING_OPTIONS for value in filtering):
            return f"filtering values must be one of: {', '.join(cls.FILTERING_OPTIONS)}"
        ref_filtering = _as_list(inputs.get("ref_filtering"))
        if any(value not in cls.REF_FILTERING_OPTIONS for value in ref_filtering):
            return f"ref_filtering values must be one of: {', '.join(cls.REF_FILTERING_OPTIONS)}"
        source = cls._reference_source(inputs)
        if source not in cls.REFERENCE_SOURCES:
            return f"reference_genome_source must be one of: {', '.join(cls.REFERENCE_SOURCES)}"
        if source == "history" and not str(inputs.get("genome_fasta", "")).strip():
            return "genome_fasta is required when reference_genome_source is history"
        if source == "cached" and not str(inputs.get("fasta_index_path", inputs.get("fasta_index", ""))).strip():
            return "fasta_index_path is required when reference_genome_source is cached"
        fa_outputs = cls._selected_fa_outputs(inputs)
        if any(value not in cls.FA_OUTPUTS for value in fa_outputs):
            return f"fa_outputs values must be one of: {', '.join(cls.FA_OUTPUTS)}"
        if fa_outputs and source == "none":
            return "reference_genome_source cannot be none when FASTA outputs are requested"
        if ref_filtering and source == "none":
            return "reference_genome_source cannot be none when reference filters are requested"
        if str(inputs.get("region_filter", "none") or "none") == "filter":
            region = str(inputs.get("range", "") or "")
            if not region:
                return "range is required when region_filter is filter"
            if not cls.RANGE_PATTERN.match(region):
                return "range must use gffread coordinate syntax like chr1:100..200"
        maxintron = inputs.get("maxintron", "")
        if str(maxintron) != "":
            try:
                maxintron_value = int(maxintron)
            except (TypeError, ValueError):
                return "maxintron must be an integer"
            if maxintron_value < 0:
                return "maxintron must be greater than or equal to 0"
        merge_sel = str(inputs.get("merge_sel", "none") or "none")
        if merge_sel not in cls.MERGE_SELS:
            return f"merge_sel must be one of: {', '.join(cls.MERGE_SELS)}"
        merge_options = cls._selected_merge_options(inputs)
        if any(value not in cls.MERGE_OPTIONS for value in merge_options):
            return f"merge_options values must be one of: {', '.join(cls.MERGE_OPTIONS)}"
        if merge_sel == "none" and merge_options:
            return "merge_options can only be used when merge_sel is merge or cluster"
        if merge_sel == "cluster":
            unsupported = [value for value in merge_options if value in {"collapse_contained", "relaxed_containment", "dupinfo"}]
            if unsupported:
                return "cluster merge_options only supports force_exons and merge_close_exons"
        if inputs.get("ensembl") and (gff_fmt != "gff" or str(inputs.get("input_format", "auto")) != "gtf"):
            return "ensembl conversion requires gff output and input_format set to gtf"
        tname = str(inputs.get("tname", "") or "")
        if "\n" in tname or "\r" in tname:
            return "tname must be a single line"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("GFF_GTF", {"description": "Input BED, GFF3, or GTF feature annotation file"}),
            },
            "optional": {
                "gff_fmt": (
                    "STRING",
                    {"default": "none", "options": cls.GFF_FORMATS, "description": "Annotation output format"},
                ),
                "input_format": (
                    "STRING",
                    {"default": "auto", "options": ["auto", "bed", "gff", "gtf"], "description": "Input format override"},
                ),
                "filtering": (
                    "STRING",
                    {
                        "default": [],
                        "options": cls.FILTERING_OPTIONS,
                        "multiple": True,
                        "description": "Transcript and feature filters",
                    },
                ),
                "region_filter": (
                    "STRING",
                    {"default": "none", "options": ["none", "filter"], "description": "Restrict output to a coordinate range"},
                ),
                "range": (
                    "STRING",
                    {"default": "", "description": "Coordinate range using gffread syntax such as chr1:100..200"},
                ),
                "discard_partial": (
                    "BOOLEAN",
                    {"default": False, "description": "Discard transcripts not fully contained in the coordinate range"},
                ),
                "maxintron": (
                    "INT",
                    {"default": "", "min": 0, "description": "Discard transcripts with introns larger than this length"},
                ),
                "chr_replace": (
                    "TSV",
                    {"description": "Two-column reference sequence replacement table"},
                ),
                "reference_genome_source": (
                    "STRING",
                    {
                        "default": "none",
                        "options": cls.REFERENCE_SOURCES,
                        "description": "Reference genome source for FASTA outputs or reference-based filters",
                    },
                ),
                "genome_fasta": ("FASTA", {"description": "Reference FASTA selected from history"}),
                "fasta_index_path": ("FASTA", {"description": "Cached reference FASTA path"}),
                "ref_filtering": (
                    "STRING",
                    {
                        "default": [],
                        "options": cls.REF_FILTERING_OPTIONS,
                        "multiple": True,
                        "description": "Reference-based CDS and splice-site filters",
                    },
                ),
                "fa_outputs": (
                    "STRING",
                    {
                        "default": [],
                        "options": cls.FA_OUTPUTS,
                        "multiple": True,
                        "description": "FASTA sequence outputs and FASTA formatting flags",
                    },
                ),
                "merge_sel": (
                    "STRING",
                    {"default": "none", "options": cls.MERGE_SELS, "description": "Transcript merge or cluster mode"},
                ),
                "merge_options": (
                    "STRING",
                    {
                        "default": [],
                        "options": cls.MERGE_OPTIONS,
                        "multiple": True,
                        "description": "Merge and cluster handling options",
                    },
                ),
                "full_gff_attribute_preservation": (
                    "BOOLEAN",
                    {"default": False, "description": "Preserve all GFF attributes when possible"},
                ),
                "decode_url": ("BOOLEAN", {"default": False, "description": "Decode URL-encoded characters"}),
                "expose": ("BOOLEAN", {"default": False, "description": "Expose warning diagnostics from gffread"}),
                "tname": (
                    "STRING",
                    {"default": "", "description": "Track name to use in the second column of GFF output"},
                ),
                "ensembl": (
                    "BOOLEAN",
                    {"default": False, "description": "Use gffread -L for Ensembl GTF to GFF3 conversion"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class GffCompareNode(CommandNode):
    """Compare and track GFF/GTF transcript annotations."""

    LEGACY_NODE_ID = "gffcompare"
    DISPLAY_NAME = "GffCompare"
    REQUIRED_CONDA_PACKAGES = ["gffcompare", "samtools"]
    CATEGORY = "annotation"
    DESCRIPTION = "Compare, classify, merge, and track GFF/GTF transcript annotations."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "gffcompare",
        "GffCompare",
        "GFF Utilities",
        "CuffCompare",
        "transcript tracking",
        "transcript classification",
        "GTF comparison",
        "GFF comparison",
        "annotation mode",
        "RefMap",
        "TMAP",
    ]
    RETURN_TYPES = ("GTF", "GTF", "TXT", "TSV", "TSV", "TSV", "TSV")
    RETURN_NAMES = (
        "transcripts_annotated",
        "transcripts_combined",
        "transcripts_stats",
        "transcripts_loci",
        "transcripts_tracking",
        "tmap_output",
        "refmap_output",
    )
    REQUIRED_EXECUTABLES = ["gffcompare", "samtools"]
    DOCUMENTATION_URL = "https://github.com/gpertea/gffcompare"
    CITATION_DOIS = [GFFREAD_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{GFFREAD_CITATION_DOI}"]
    CITATION_TEXT = GFFREAD_CITATION_TEXT
    VERSION = "0.12.10"
    SHELL = True
    RUN_IN_NODE_OUTPUT_DIR = True

    YES_NO_OPTIONS = ["no", "yes"]
    SOURCES = ["history", "cached"]
    DISCARD_SINGLE_EXON_OPTIONS = ["", "-M", "-N"]
    DUPLICATION_OPTIONS = ["", "-D"]

    @classmethod
    def _gffinputs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("gffinputs"))

    @classmethod
    def _staged_input_names(cls, inputs: dict[str, Any]) -> list[str]:
        labels = _as_list(inputs.get("element_identifiers"))
        names: list[str] = []
        seen: dict[str, int] = {}
        for index, input_path in enumerate(cls._gffinputs(inputs)):
            label = labels[index] if index < len(labels) and labels[index] else input_path
            name = _safe_element_identifier(label).replace(".", "_")
            if not name:
                name = f"input_{index + 1}"
            count = seen.get(name, 0)
            seen[name] = count + 1
            if count:
                name = f"{name}_{count}"
            names.append(name)
        return names

    @classmethod
    def _annotation_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("annotation_selector", "no") or "no")

    @classmethod
    def _ref_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ref_source", "history") or "history")

    @classmethod
    def _seq_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("seq_selector", "no") or "no")

    @classmethod
    def _seq_source(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("seq_source", "history") or "history")

    @classmethod
    def _out_prefix(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/gffcmp"

    @classmethod
    def _uses_annotation_mode(cls, inputs: dict[str, Any]) -> bool:
        return (
            len(cls._gffinputs(inputs)) == 1
            and cls._annotation_selector(inputs) == "yes"
            and not inputs.get("A")
            and not inputs.get("C")
            and not inputs.get("X")
            and cls._duplication_selector(inputs) == ""
            and not inputs.get("S")
        )

    @classmethod
    def _duplication_selector(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("duplication_selector", "") or "")

    @classmethod
    def _refmap_tmap(cls, inputs: dict[str, Any]) -> bool:
        return bool(inputs.get("refmap_tmap", True))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        setup = [_shell_join(["mkdir", "-p", out])]
        staged_names = cls._staged_input_names(inputs)
        for source, staged_name in zip(cls._gffinputs(inputs), staged_names, strict=False):
            setup.append(_shell_join(["ln", "-s", source, staged_name]))
        if cls._annotation_selector(inputs) == "yes":
            ref = (
                inputs.get("reference_annotation")
                if cls._ref_source(inputs) == "history"
                else inputs.get("reference_index_path", inputs.get("reference_index"))
            )
            setup.append(_shell_join(["ln", "-s", str(ref or ""), "reference_annotation"]))
        if cls._seq_selector(inputs) == "yes":
            seq = (
                inputs.get("ref_genome")
                if cls._seq_source(inputs) == "history"
                else inputs.get("seq_index_path", inputs.get("seq_index"))
            )
            setup.append(_shell_join(["ln", "-s", str(seq or ""), "ref_seq.fa"]))
            if cls._seq_source(inputs) == "history":
                setup.append(_shell_join(["samtools", "faidx", "ref_seq.fa"]))

        cmd = ["gffcompare", "-V", "-o", cls._out_prefix(inputs)]
        if cls._annotation_selector(inputs) == "yes":
            cmd.extend(["-r", "reference_annotation"])
            if inputs.get("R"):
                cmd.append("-R")
            if inputs.get("Q"):
                cmd.append("-Q")
            if inputs.get("strict_match"):
                cmd.extend(["--strict-match", "-e", str(inputs.get("e", 100))])
            discard_single_exon = str(inputs.get("discard_single_exon", "") or "")
            if discard_single_exon:
                cmd.append(discard_single_exon)
            duplication_selector = cls._duplication_selector(inputs)
            if duplication_selector:
                cmd.append(duplication_selector)
                if inputs.get("S"):
                    cmd.append("-S")
            if inputs.get("no_merge"):
                cmd.append("--no-merge")
        if not cls._refmap_tmap(inputs):
            cmd.append("-T")
        if cls._seq_selector(inputs) == "yes":
            cmd.extend(["-s", "ref_seq.fa"])
        cmd.extend(["-d", str(inputs.get("max_dist_group", 100))])
        if inputs.get("chr_stats"):
            cmd.append("--chr-stats")
        cmd.extend(["-p", str(inputs.get("p", "TCONS") or "TCONS")])
        for flag in ("A", "C", "X", "K"):
            if inputs.get(flag):
                cmd.append(f"-{flag}")
        cmd.extend(staged_names)
        commands = [*setup, _shell_join(cmd)]
        if cls._refmap_tmap(inputs) and len(staged_names) == 1:
            native_tmap = f"{cls._out_prefix(inputs)}.{staged_names[0]}.tmap"
            commands.append(_shell_join(["mv", native_tmap, f"{out}/output.tmap"]))
            if cls._annotation_selector(inputs) == "yes":
                native_refmap = f"{cls._out_prefix(inputs)}.{staged_names[0]}.refmap"
                commands.append(_shell_join(["mv", native_refmap, f"{out}/output.refmap"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / ("gffcmp.annotated.gtf" if cls._uses_annotation_mode(inputs) else "gffcmp.combined.gtf"),
            out / "gffcmp.stats",
            out / "gffcmp.loci",
            out / "gffcmp.tracking",
        ]
        if cls._refmap_tmap(inputs):
            staged_names = cls._staged_input_names(inputs)
            if len(staged_names) == 1:
                outputs.append(out / "output.tmap")
                if cls._annotation_selector(inputs) == "yes":
                    outputs.append(out / "output.refmap")
            else:
                for staged_name in staged_names:
                    outputs.append(out / f"gffcmp.{staged_name}.tmap")
                if cls._annotation_selector(inputs) == "yes":
                    for staged_name in staged_names:
                        outputs.append(out / f"gffcmp.{staged_name}.refmap")
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        """Map fixed reports and variable per-input maps to their stable ports."""
        mapped: dict[str, Any] = {}
        tmap: list[Path] = []
        refmap: list[Path] = []
        for path in map(Path, planned_paths):
            if path.name == "gffcmp.annotated.gtf":
                mapped["transcripts_annotated"] = path
            elif path.name == "gffcmp.combined.gtf":
                mapped["transcripts_combined"] = path
            elif path.name == "gffcmp.stats":
                mapped["transcripts_stats"] = path
            elif path.name == "gffcmp.loci":
                mapped["transcripts_loci"] = path
            elif path.name == "gffcmp.tracking":
                mapped["transcripts_tracking"] = path
            elif path.name.endswith(".tmap"):
                tmap.append(path)
            elif path.name.endswith(".refmap"):
                refmap.append(path)
            else:
                raise ValueError(f"gffcompare planned an unknown output artifact: {path.name}")
        if tmap:
            mapped["tmap_output"] = tmap[0] if len(tmap) == 1 else tmap
        if refmap:
            mapped["refmap_output"] = refmap[0] if len(refmap) == 1 else refmap
        required = {"transcripts_stats", "transcripts_loci", "transcripts_tracking"}
        if not ({"transcripts_annotated", "transcripts_combined"}.intersection(mapped)):
            raise ValueError("gffcompare did not plan its primary transcript output")
        if missing := required.difference(mapped):
            raise ValueError(f"gffcompare did not plan required output(s): {', '.join(sorted(missing))}")
        return mapped

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        result = await super().run(**kwargs)
        mapped = self.__class__.MAP_PLANNED_OUTPUTS([Path(path) for path in result])
        return {
            "outputs": {
                name: [str(path) for path in value] if isinstance(value, list) else str(value)
                for name, value in mapped.items()
            }
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._gffinputs(inputs):
            return "at least one gffinputs value is required"
        annotation_selector = cls._annotation_selector(inputs)
        if annotation_selector not in cls.YES_NO_OPTIONS:
            return f"annotation_selector must be one of: {', '.join(cls.YES_NO_OPTIONS)}"
        ref_source = cls._ref_source(inputs)
        if ref_source not in cls.SOURCES:
            return f"ref_source must be one of: {', '.join(cls.SOURCES)}"
        if annotation_selector == "yes":
            if ref_source == "history" and not str(inputs.get("reference_annotation", "")).strip():
                return "reference_annotation is required when ref_source is history"
            reference_index = str(inputs.get("reference_index_path", inputs.get("reference_index", ""))).strip()
            if ref_source == "cached" and not reference_index:
                return "reference_index_path is required when ref_source is cached"
        seq_selector = cls._seq_selector(inputs)
        if seq_selector not in cls.YES_NO_OPTIONS:
            return f"seq_selector must be one of: {', '.join(cls.YES_NO_OPTIONS)}"
        seq_source = cls._seq_source(inputs)
        if seq_source not in cls.SOURCES:
            return f"seq_source must be one of: {', '.join(cls.SOURCES)}"
        if seq_selector == "yes":
            if seq_source == "history" and not str(inputs.get("ref_genome", "")).strip():
                return "ref_genome is required when seq_source is history"
            seq_index = str(inputs.get("seq_index_path", inputs.get("seq_index", ""))).strip()
            if seq_source == "cached" and not seq_index:
                return "seq_index_path is required when seq_source is cached"
        discard_single_exon = str(inputs.get("discard_single_exon", "") or "")
        if discard_single_exon not in cls.DISCARD_SINGLE_EXON_OPTIONS:
            return f"discard_single_exon must be one of: {', '.join(cls.DISCARD_SINGLE_EXON_OPTIONS)}"
        duplication_selector = cls._duplication_selector(inputs)
        if duplication_selector not in cls.DUPLICATION_OPTIONS:
            return f"duplication_selector must be one of: {', '.join(cls.DUPLICATION_OPTIONS)}"
        if inputs.get("S") and duplication_selector != "-D":
            return "S requires duplication_selector=-D"
        for name in ("e", "max_dist_group"):
            value = inputs.get(name, "")
            if str(value) == "":
                continue
            try:
                number = int(value)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if number < 0:
                return f"{name} must be greater than or equal to 0"
        prefix = str(inputs.get("p", "TCONS") or "TCONS")
        if not re.fullmatch(r"[0-9A-Za-z_-]+", prefix):
            return "p must contain only letters, digits, underscores, and hyphens"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gffinputs": ("GFF_GTF", {"multiple": True, "description": "One or more GTF/GFF3 transcript annotations to compare"}),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "description": "Optional Galaxy collection labels for stable query filenames"},
                ),
                "annotation_selector": (
                    "STRING",
                    {"default": "no", "options": cls.YES_NO_OPTIONS, "description": "Use a reference annotation for classification"},
                ),
                "ref_source": (
                    "STRING",
                    {"default": "history", "options": cls.SOURCES, "description": "Reference annotation source"},
                ),
                "reference_annotation": ("GFF_GTF", {"description": "Reference annotation from history"}),
                "reference_index_path": ("GFF_GTF", {"description": "Cached reference annotation path"}),
                "R": ("BOOLEAN", {"default": False, "description": "Apply Sn correction using only overlapped reference transcripts"}),
                "Q": ("BOOLEAN", {"default": False, "description": "Apply Sp correction using only query transcripts overlapping references"}),
                "strict_match": ("BOOLEAN", {"default": False, "description": "Require stricter transcript-level matching"}),
                "e": ("INT", {"default": 100, "min": 0, "description": "Allowed terminal exon end variation for strict matching"}),
                "discard_single_exon": (
                    "STRING",
                    {"default": "", "options": cls.DISCARD_SINGLE_EXON_OPTIONS, "description": "Discard single-exon transfrags or reference transcripts"},
                ),
                "duplication_selector": (
                    "STRING",
                    {"default": "", "options": cls.DUPLICATION_OPTIONS, "description": "Discard duplicate query transfrags"},
                ),
                "S": ("BOOLEAN", {"default": False, "description": "Use strict duplicate checking when duplicate filtering is enabled"}),
                "no_merge": ("BOOLEAN", {"default": False, "description": "Disable close-exon merging"}),
                "seq_selector": (
                    "STRING",
                    {"default": "no", "options": cls.YES_NO_OPTIONS, "description": "Use genomic sequence data for repeat classification"},
                ),
                "seq_source": ("STRING", {"default": "history", "options": cls.SOURCES, "description": "Reference sequence source"}),
                "ref_genome": ("FASTA", {"description": "Reference genome FASTA from history"}),
                "seq_index_path": ("FASTA", {"description": "Cached reference genome FASTA path"}),
                "max_dist_group": ("INT", {"default": 100, "min": 0, "description": "Maximum distance for grouping transcript start sites"}),
                "chr_stats": ("BOOLEAN", {"default": False, "description": "Report stats per reference contig or chromosome"}),
                "refmap_tmap": ("BOOLEAN", {"default": True, "description": "Generate TMAP and RefMap files for each input"}),
                "p": ("STRING", {"default": "TCONS", "description": "Name prefix for consensus transcripts"}),
                "A": ("BOOLEAN", {"default": False, "description": "Discard contained transfrags except alternate TSS cases"}),
                "C": ("BOOLEAN", {"default": False, "description": "Discard matching and contained transfrags"}),
                "X": ("BOOLEAN", {"default": False, "description": "Discard contained transfrags with ends inside container introns"}),
                "K": ("BOOLEAN", {"default": False, "description": "Keep redundant transfrags matching a reference when using -C/-A/-X"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(
    [GtfToBed12Node],
    runtime_version="357",
    runtime_git_url=KENT_GIT_URL,
    runtime_git_commit=KENT_357_GIT_COMMIT,
    package_constraint="ucsc-gtftogenepred==357; ucsc-genepredtobed==357",
)
pin_contract(
    [GffReadNode],
    runtime_version="0.12.7",
    runtime_git_url=GFFREAD_GIT_URL,
    runtime_git_commit=GFFREAD_GIT_COMMIT,
    package_constraint="gffread==0.12.7",
)
pin_contract(
    [GffCompareNode],
    runtime_version="0.12.10",
    runtime_git_url=GFFCOMPARE_GIT_URL,
    runtime_git_commit=GFFCOMPARE_GIT_COMMIT,
    package_constraint="gffcompare==0.12.10; samtools==1.22.1 in the wrapper",
)
GffCompareNode.BIONODULO_SAMTOOLS_CONSTRAINT = "samtools==1.23.1"
GffCompareNode.ENVIRONMENT_PIN_NOTE = (
    "The wrapper used samtools 1.22.1; BioNodulo intentionally retains the verified 1.23.1 foundation pin."
)
