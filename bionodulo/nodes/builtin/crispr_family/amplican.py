"""AmpliCan amplicon-analysis wrapper contract."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_phylogeny_assembly_family.evidence import pin_contract

class AmpliCanNode(CommandNode):
    """Analyze genome editing amplicon sequencing data with ampliCan."""

    NODE_ID = "amplican"
    DISPLAY_NAME = "AmpliCan"
    REQUIRED_CONDA_PACKAGES = ["bioconductor-amplican"]
    CATEGORY = "crispr"
    DESCRIPTION = "Analyze CRISPR and other genome editing amplicon sequencing experiments with ampliCan."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AmpliCan",
        "amplican",
        "CRISPR editing analysis",
        "genome editing amplicons",
        "amplicon sequencing",
        "HDR repair",
        "base editing",
    ]
    RETURN_TYPES = ("CSV", "TSV", "HTML_REPORT", "TXT", "FILE", "FASTA", "TXT", "CSV", "CSV", "CSV", "CSV")
    RETURN_NAMES = (
        "config_summary",
        "barcode_reads",
        "output_html",
        "parameters",
        "alignments_rds",
        "alignments_fasta",
        "alignments_txt",
        "events_filtered_shifted",
        "events_filtered_shifted_normalized",
        "raw_events",
        "unassigned_reads",
    )
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://bioconductor.org/packages/amplican"
    CITATION_DOIS = [AMPLICAN_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{AMPLICAN_CITATION_DOI}"]
    CITATION_TEXT = AMPLICAN_CITATION_TEXT
    VERSION = "1.14.0+galaxy1"
    SHELL = True

    OUTPUT_CHOICES = [
        "config_summary",
        "barcode_reads",
        "knit_reports",
        "parameters",
        "alignments_rds",
        "events_filtered_shifted",
        "events_filtered_shifted_normalized",
        "raw_events",
        "unassigned_reads",
    ]
    DEFAULT_OUTPUTS = [
        "config_summary",
        "barcode_reads",
        "knit_reports",
        "alignments_rds",
        "events_filtered_shifted",
        "events_filtered_shifted_normalized",
        "raw_events",
        "unassigned_reads",
    ]
    OUTPUT_FILES = {
        "config_summary": "config_summary.csv",
        "barcode_reads": "barcode_reads_filters.csv",
        "knit_reports": "reports/index.html",
        "parameters": "RunParameters.txt",
        "alignments_rds": "alignments/AlignmentsExperimentSet.rds",
        "events_filtered_shifted": "alignments/events_filtered_shifted.csv",
        "events_filtered_shifted_normalized": "alignments/events_filtered_shifted_normalized.csv",
        "raw_events": "alignments/raw_events.csv",
        "unassigned_reads": "alignments/unassigned_reads.csv",
    }
    ALIGNMENT_FORMATS = ["None", "txt", "fasta"]

    @classmethod
    def _outputs(cls, inputs: dict[str, Any]) -> list[str]:
        outputs = _as_list(inputs.get("outputs"))
        return outputs if outputs else list(cls.DEFAULT_OUTPUTS)

    @classmethod
    def _fastq_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("fastq_files"))

    @classmethod
    def _fastq_identifiers(cls, inputs: dict[str, Any], fastq_files: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("fastq_identifiers"))
        return [
            identifiers[index] if index < len(identifiers) and identifiers[index] else Path(fastq_file).name
            for index, fastq_file in enumerate(fastq_files)
        ]

    @classmethod
    def _r_bool(cls, value: Any, default: bool = True) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        outputs = set(cls._outputs(inputs))
        write_alignment_format = str(inputs.get("write_alignment_format", "txt"))
        return "\n".join(
            [
                "options(show.error.messages = FALSE, error = function() { cat(geterrmessage(), file = stderr()); q(\"no\", 1, FALSE) })",
                'Sys.setlocale("LC_MESSAGES", "en_US.UTF-8")',
                'suppressPackageStartupMessages({ library("amplican") })',
                "amplicanPipeline(",
                f"  {shlex.quote(str(inputs.get('config_file', '')))},",
                f"  {shlex.quote(f'{out}/fastq_folder')},",
                f"  {shlex.quote(f'{out}/output_folder')},",
                f"  knit_reports = {'TRUE' if 'knit_reports' in outputs else 'FALSE'},",
                f'  write_alignments_format = "{write_alignment_format}",',
                f"  average_quality = {inputs.get('average_quality', 0)},",
                f"  min_quality = {inputs.get('min_quality', 20)},",
                "  use_parallel = FALSE,",
                "  scoring_matrix = Biostrings::nucleotideSubstitutionMatrix(",
                f"    match = {inputs.get('match_scoring', 5)},",
                f"    mismatch = {inputs.get('mismatch_scoring', -4)},",
                f"    baseOnly = {cls._r_bool(inputs.get('base_only'), True)},",
                f'    type = "{inputs.get("scoring_type", "DNA")}"',
                "  ),",
                f"  gap_opening = {inputs.get('gap_opening', 25)},",
                f"  gap_extension = {inputs.get('gap_extension', 0)},",
                f"  fastqfiles = {inputs.get('fastq_use', '0')},",
                f"  primer_mismatch = {inputs.get('primer_mismatch', 0)},",
                f"  donor_mismatch = {inputs.get('donor_mismatch', 3)},",
                f"  PRIMER_DIMER = {inputs.get('primer_dimer', 30)},",
                f"  event_filter = {cls._r_bool(inputs.get('event_filter'), True)},",
                f"  cut_buffer = {inputs.get('cut_buffer', 5)},",
                f"  promiscuous_consensus = {cls._r_bool(inputs.get('promiscuous_consensus'), True)},",
                '  normalize = c("guideRNA", "Group")',
                ")",
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        fastq_files = cls._fastq_files(inputs)
        identifiers = cls._fastq_identifiers(inputs, fastq_files)
        commands = [
            _shell_join(["mkdir", "-p", f"{out}/fastq_folder", f"{out}/output_folder"]),
        ]
        for fastq_file, identifier in zip(fastq_files, identifiers, strict=False):
            commands.append(_shell_join(["ln", "-s", fastq_file, f"{out}/fastq_folder/{identifier}"]))
        script_path = f"{out}/amplican_script.R"
        commands.append(f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT")
        commands.append(_shell_join(["Rscript", script_path]))
        if "knit_reports" in cls._outputs(inputs):
            extra_files = f"{out}/output_html_extra_files"
            commands.append(_shell_join(["mkdir", "-p", extra_files]))
            for report in ["amplicon_report.html", "barcode_report.html", "group_report.html", "guide_report.html", "id_report.html"]:
                commands.append(_shell_join(["mv", f"{out}/output_folder/reports/{report}", extra_files]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / cls.OUTPUT_FILES[output] for output in cls._outputs(inputs) if output in cls.OUTPUT_FILES]
        write_alignment_format = str(inputs.get("write_alignment_format", "txt"))
        if write_alignment_format == "fasta":
            outputs.append(out / "alignments" / "alignments.fasta")
        elif write_alignment_format == "txt":
            outputs.append(out / "alignments" / "alignments.txt")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("config_file", "")).strip():
            return "config_file is required"
        fastq_files = cls._fastq_files(inputs)
        if not fastq_files:
            return "at least one FASTQ file is required"
        identifiers = cls._fastq_identifiers(inputs, fastq_files)
        if any(not re.fullmatch(r"[\w\-.]+", identifier) for identifier in identifiers):
            return "fastq_identifiers may contain only letters, numbers, underscores, hyphens, and dots"
        for name in ("average_quality", "min_quality"):
            value = int(inputs.get(name, {"average_quality": 0, "min_quality": 20}[name]))
            if value < 0 or value > 93:
                return f"{name} must be between 0 and 93"
        for name in ("gap_opening", "gap_extension", "primer_mismatch", "donor_mismatch"):
            value = int(inputs.get(name, {"gap_opening": 25, "gap_extension": 0, "primer_mismatch": 0, "donor_mismatch": 3}[name]))
            if value < 0 or value > 40:
                return f"{name} must be between 0 and 40"
        match_scoring = int(inputs.get("match_scoring", 5))
        if match_scoring < 0 or match_scoring > 20:
            return "match_scoring must be between 0 and 20"
        mismatch_scoring = int(inputs.get("mismatch_scoring", -4))
        if mismatch_scoring < -20 or mismatch_scoring > 0:
            return "mismatch_scoring must be between -20 and 0"
        if str(inputs.get("scoring_type", "DNA")) not in {"DNA", "RNA"}:
            return "scoring_type must be one of: DNA, RNA"
        if str(inputs.get("fastq_use", "0")) not in {"0", "0.5", "1", "2"}:
            return "fastq_use must be one of: 0, 0.5, 1, 2"
        primer_dimer = int(inputs.get("primer_dimer", 30))
        if primer_dimer < 0 or primer_dimer > 50:
            return "primer_dimer must be between 0 and 50"
        cut_buffer = int(inputs.get("cut_buffer", 5))
        if cut_buffer < 0 or cut_buffer > 30:
            return "cut_buffer must be between 0 and 30"
        if str(inputs.get("write_alignment_format", "txt")) not in cls.ALIGNMENT_FORMATS:
            return "write_alignment_format must be one of: None, txt, fasta"
        unsupported_outputs = [output for output in cls._outputs(inputs) if output not in cls.OUTPUT_CHOICES]
        if unsupported_outputs:
            return f"outputs contains unsupported values: {', '.join(unsupported_outputs)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "config_file": ("TXT", {"description": "ampliCan configuration file"}),
                "fastq_files": (
                    "FASTQ_LIST",
                    {"multiple": True, "description": "FASTQ or FASTQ.GZ read files referenced by the configuration"},
                ),
            },
            "optional": {
                "fastq_identifiers": (
                    "STRING_LIST",
                    {"default": [], "multiple": True, "advanced": True, "description": "Galaxy element names for staged FASTQ files"},
                ),
                "average_quality": ("INT", {"default": 0, "min": 0, "max": 93, "description": "Minimum average read quality"}),
                "min_quality": ("INT", {"default": 20, "min": 0, "max": 93, "description": "Minimum per-base quality"}),
                "gap_opening": ("INT", {"default": 25, "min": 0, "max": 40, "description": "Alignment gap opening score"}),
                "gap_extension": ("INT", {"default": 0, "min": 0, "max": 40, "description": "Alignment gap extension score"}),
                "primer_mismatch": ("INT", {"default": 0, "min": 0, "max": 40, "description": "Allowed primer mismatches"}),
                "donor_mismatch": (
                    "INT",
                    {"default": 3, "min": 0, "max": 40, "description": "Allowed mismatch events when aligning to donor template"},
                ),
                "match_scoring": ("INT", {"default": 5, "min": 0, "max": 20, "description": "Scoring matrix match value"}),
                "mismatch_scoring": (
                    "INT",
                    {"default": -4, "min": -20, "max": 0, "description": "Scoring matrix mismatch value"},
                ),
                "base_only": ("BOOLEAN", {"default": True, "description": "Use base-only nucleotide substitution matrix"}),
                "scoring_type": ("STRING", {"default": "DNA", "options": ["DNA", "RNA"], "description": "Scoring matrix type"}),
                "fastq_use": (
                    "STRING",
                    {"default": "0", "options": ["0", "0.5", "1", "2"], "description": "Forward/reverse FASTQ files to use"},
                ),
                "primer_dimer": ("INT", {"default": 30, "min": 0, "max": 50, "description": "Primer dimer detection buffer"}),
                "event_filter": ("BOOLEAN", {"default": True, "description": "Enable off-target read detection"}),
                "cut_buffer": ("INT", {"default": 5, "min": 0, "max": 30, "description": "Bases around expected cut sites"}),
                "promiscuous_consensus": (
                    "BOOLEAN",
                    {"default": True, "description": "Allow promiscuous consensus rules for indel confirmation"},
                ),
                "write_alignment_format": (
                    "STRING",
                    {"default": "txt", "options": cls.ALIGNMENT_FORMATS, "description": "Optional alignment output format"},
                ),
                "outputs": (
                    "STRING_LIST",
                    {
                        "default": cls.DEFAULT_OUTPUTS,
                        "multiple": True,
                        "options": cls.OUTPUT_CHOICES,
                        "description": "Additional ampliCan outputs selected in the Galaxy wrapper",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(AmpliCanNode)

__all__ = ["AmpliCanNode"]
