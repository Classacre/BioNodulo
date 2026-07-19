"""UCSC MAF selection and extraction nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_beacon_ucsc_family.adapter import (
    KENT_482_GIT_COMMIT,
    KENT_490_GIT_COMMIT,
    KENT_GIT_URL,
    pin_contract,
    ucsc_db_command,
)

class UcscMafFilterNode(CommandNode):
    """Filter UCSC MAF alignment blocks."""

    NODE_ID = "ucsc_maffilter"
    DISPLAY_NAME = "mafFilter"
    REQUIRED_CONDA_PACKAGES = ["ucsc-maffilter"]
    CATEGORY = "genomics"
    DESCRIPTION = "Filter UCSC MAF alignment blocks by size, score, species, and component criteria."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_mafFilter",
        "ucsc_maffilter",
        "mafFilter",
        "MAF block filter",
        "multiple alignment format",
        "species filter",
        "component filter",
        "rejected MAF blocks",
    ]
    RETURN_TYPES = ("FILE", "FILE")
    RETURN_NAMES = ("output_maf", "rejected_maf")
    REQUIRED_EXECUTABLES = ["mafFilter"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/ratStuff/mafFilter/mafFilter.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    FACTOR_OPTIONS = ["no", "yes"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.maf"

    @classmethod
    def _reject_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/rejected.maf"

    @classmethod
    def _factor_enabled(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("factor_enabled", "no") or "no")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["mafFilter"]
        if inputs.get("tolerate"):
            cmd.append("-tolerate")
        for name, default in (("minCol", 1), ("minRow", 2), ("maxRow", 100)):
            cmd.append(f"-{name}={inputs.get(name, default)}")
        if cls._factor_enabled(inputs) == "yes":
            cmd.append("-factor")
            cmd.append(f"-minFactor={inputs.get('minFactor', 5)}")
        elif str(inputs.get("minScore", "")) != "":
            cmd.append(f"-minScore={inputs.get('minScore')}")
        if inputs.get("reject"):
            cmd.append(f"-reject={cls._reject_path(inputs)}")
        if str(inputs.get("needComp", "")) != "":
            cmd.append(f"-needComp={inputs.get('needComp')}")
        if inputs.get("overlap"):
            cmd.append("-overlap")
        if str(inputs.get("componentFilter", "")) != "":
            cmd.append(f"-componentFilter={inputs.get('componentFilter')}")
        if str(inputs.get("speciesFilter", "")) != "":
            cmd.append(f"-speciesFilter={inputs.get('speciesFilter')}")
        cmd.append(str(inputs.get("input_maf", "")))
        return f"{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "output.maf"]
        if inputs.get("reject", False):
            outputs.append(out / "rejected.maf")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_maf", "")).strip():
            return "input_maf is required"
        for name, minimum in (("minCol", 1), ("minRow", 1), ("maxRow", 1)):
            value = inputs.get(name, "")
            if str(value) != "" and int(value) < minimum:
                return f"{name} must be greater than or equal to {minimum}"
        factor_enabled = cls._factor_enabled(inputs)
        if factor_enabled not in cls.FACTOR_OPTIONS:
            return f"factor_enabled must be one of: {', '.join(cls.FACTOR_OPTIONS)}"
        if factor_enabled == "yes":
            if str(inputs.get("minFactor", "")) != "" and int(inputs.get("minFactor")) < 0:
                return "minFactor must be greater than or equal to 0"
            if str(inputs.get("minScore", "")) != "":
                return "minScore cannot be used when factor_enabled is yes"
        if str(inputs.get("minScore", "")) != "" and float(inputs.get("minScore")) < 0:
            return "minScore must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_maf": ("FILE", {"description": "UCSC MAF multiple-alignment file to filter"}),
            },
            "optional": {
                "tolerate": (
                    "BOOLEAN",
                    {"default": False, "description": "Ignore bad input instead of aborting"},
                ),
                "minCol": (
                    "INT",
                    {"default": 1, "min": 1, "description": "Filter out blocks with fewer columns"},
                ),
                "minRow": (
                    "INT",
                    {"default": 2, "min": 1, "description": "Filter out blocks with fewer rows"},
                ),
                "maxRow": (
                    "INT",
                    {"default": 100, "min": 1, "description": "Filter out blocks with at least this many rows"},
                ),
                "factor_enabled": (
                    "STRING",
                    {
                        "default": "no",
                        "options": cls.FACTOR_OPTIONS,
                        "description": "Enable factor-based score filtering instead of minimum score filtering",
                    },
                ),
                "minFactor": (
                    "INT",
                    {"default": 5, "min": 0, "description": "Factor used with factor-based score filtering"},
                ),
                "minScore": (
                    "FLOAT",
                    {"default": "", "min": 0, "description": "Minimum allowed MAF block score"},
                ),
                "reject": (
                    "BOOLEAN",
                    {"default": False, "description": "Write rejected MAF blocks to a second output"},
                ),
                "needComp": (
                    "STRING",
                    {"default": "", "description": "Require this species component in every alignment block"},
                ),
                "overlap": (
                    "BOOLEAN",
                    {"default": False, "description": "Reject overlapping reference blocks in ordered input"},
                ),
                "componentFilter": (
                    "FILE",
                    {"description": "File listing components required for a block to pass"},
                ),
                "speciesFilter": (
                    "FILE",
                    {"description": "File listing species required for a block to pass"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscMafFetchNode(CommandNode):
    """Fetch UCSC MAF records overlapping BED intervals."""

    NODE_ID = "ucsc_maffetch"
    DISPLAY_NAME = "mafFetch"
    REQUIRED_CONDA_PACKAGES = ["ucsc-maffetch"]
    CATEGORY = "genomics"
    DESCRIPTION = "Fetch UCSC MAF records overlapping BED regions from an indexed UCSC table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_mafFetch",
        "ucsc_maffetch",
        "mafFetch",
        "MAF indexed lookup",
        "multiple alignment format",
        "BED overlap",
        "UCSC MAF table",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["mafFetch"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/mouseStuff/mafFetch/mafFetch.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.maf"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "mafFetch",
            str(inputs.get("genome", "")),
            str(inputs.get("track", "")),
            str(inputs.get("bed_file", "")),
            cls._output_path(inputs),
        ]
        return ucsc_db_command(inputs, cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.maf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("bed_file", "genome", "track"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bed_file": ("BED", {"description": "BED6 or BED12 intervals used to fetch overlapping MAF records"}),
                "genome": ("STRING", {"description": "UCSC genome database name"}),
                "track": ("STRING", {"description": "UCSC MAF table name, such as multiz46way"}),
            },
            "optional": {
                "ucsc_db_connection": (
                    "FILE",
                    {"description": "Optional UCSC database config; defaults to the pinned public Galaxy config"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscMafAddIRowsNode(CommandNode):
    """Add i rows to UCSC MAF alignments."""

    NODE_ID = "ucsc_mafaddirows"
    DISPLAY_NAME = "mafAddIRows"
    REQUIRED_CONDA_PACKAGES = ["ucsc-mafaddirows"]
    CATEGORY = "genomics"
    DESCRIPTION = "Add UCSC MAF i rows or N/dash sequence rows using a twoBit reference."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_mafAddIRows",
        "ucsc_mafaddirows",
        "mafAddIRows",
        "MAF i rows",
        "multiple alignment format",
        "twoBit reference",
        "N BED files",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_maf",)
    REQUIRED_EXECUTABLES = ["mafAddIRows"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/ratStuff/mafAddIRows/mafAddIRows.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"
    SHELL = True
    RUN_IN_NODE_OUTPUT_DIR = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.maf"

    @classmethod
    def _nbed_links(cls, inputs: dict[str, Any]) -> list[str]:
        commands: list[str] = []
        out = _out(inputs)
        manifest = f"{out}/bed.txt"
        labels = _as_list(inputs.get("nBed_element_identifiers"))
        if labels:
            commands.append(_shell_join(["rm", "-f", manifest]))
        for bed, label in zip(_as_list(inputs.get("nBeds")), labels, strict=True):
            identifier = _safe_label(Path(label).name)
            staged = f"{out}/{identifier}"
            commands.append(_shell_join(["ln", "-s", bed, staged]))
            commands.append(f"echo {shlex.quote(identifier)} >> {shlex.quote(manifest)}")
        return commands

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "mafAddIRows",
            str(inputs.get("input_maf", "")),
            str(inputs.get("twoBitFile", "")),
            cls._output_path(inputs),
        ]
        if _as_list(inputs.get("nBeds")):
            cmd.append(f"-nBeds={_out(inputs)}/bed.txt")
        if inputs.get("addN"):
            cmd.append("-addN")
        if inputs.get("addDash"):
            cmd.append("-addDash")
        parts = cls._nbed_links(inputs) + [_shell_join(cmd)]
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.maf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_maf", "")).strip():
            return "input_maf is required"
        if not str(inputs.get("twoBitFile", "")).strip():
            return "twoBitFile is required"
        if inputs.get("addN") and inputs.get("addDash"):
            return "addN and addDash cannot both be enabled"
        beds = _as_list(inputs.get("nBeds"))
        labels = _as_list(inputs.get("nBed_element_identifiers"))
        if beds and len(labels) != len(beds):
            return "nBed_element_identifiers must provide one logical species filename for each nBeds file"
        if labels and not beds:
            return "nBed_element_identifiers cannot be used without nBeds"
        if any(not Path(label).name.endswith(".bed") for label in labels):
            return "each nBed_element_identifiers value must end in .bed"
        safe_labels = [_safe_label(Path(label).name) for label in labels]
        if len(safe_labels) != len(set(safe_labels)):
            return "nBed_element_identifiers must be unique after filename sanitization"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_maf": ("FILE", {"description": "MAF file with a single target sequence"}),
                "twoBitFile": ("FILE", {"description": "twoBit reference genome file"}),
            },
            "optional": {
                "nBeds": (
                    "BED",
                    {"multiple": True, "default": [], "description": "BED files, one per species, containing N locations"},
                ),
                "nBed_element_identifiers": (
                    "STRING",
                    {
                        "multiple": True,
                        "default": [],
                        "description": "Required logical .bed names whose basenames identify the species for nBeds",
                    },
                ),
                "addN": ("BOOLEAN", {"default": False, "description": "Add rows of Ns into MAF blocks"}),
                "addDash": ("BOOLEAN", {"default": False, "description": "Add rows of dashes into MAF blocks"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscMafFragNode(CommandNode):
    """Extract one UCSC MAF alignment region from a database track."""

    NODE_ID = "ucsc_maffrag"
    DISPLAY_NAME = "mafFrag"
    REQUIRED_CONDA_PACKAGES = ["ucsc-maffrag"]
    CATEGORY = "genomics"
    DESCRIPTION = "Extract UCSC MAF sequences for one genomic region from a database track."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_mafFrag",
        "ucsc_maffrag",
        "mafFrag",
        "MAF region extract",
        "multiple alignment format",
        "UCSC MAF track",
        "single region",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["mafFrag"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/ratStuff/mafFrag/mafFrag.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"
    SHELL = True

    STRAND_OPTIONS = [".", "+", "-"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.maf"

    @classmethod
    def _strand(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("strand", ".") or ".")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        output_path = cls._output_path(inputs)
        cmd = [
            "mafFrag",
            str(inputs.get("genome", "")),
            str(inputs.get("track", "")),
            str(inputs.get("chrom", "")),
            str(inputs.get("start", "")),
            str(inputs.get("end", "")),
            cls._strand(inputs),
            cls._output_path(inputs),
        ]
        if str(inputs.get("outName", "")) != "":
            cmd.append(f"-outName={inputs.get('outName')}")
        return f"{_shell_join(['touch', output_path])} && {ucsc_db_command(inputs, cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.maf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("genome", "track", "chrom"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"
        if str(inputs.get("start", "")) == "":
            return "start is required"
        if str(inputs.get("end", "")) == "":
            return "end is required"
        strand = cls._strand(inputs)
        if strand not in cls.STRAND_OPTIONS:
            return f"strand must be one of: {', '.join(cls.STRAND_OPTIONS)}"
        try:
            start = int(inputs.get("start"))
        except (TypeError, ValueError):
            return "start must be an integer"
        try:
            end = int(inputs.get("end"))
        except (TypeError, ValueError):
            return "end must be an integer"
        if start < 0:
            return "start must be greater than or equal to 0"
        if end <= start:
            return "end must be greater than start"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genome": ("STRING", {"description": "UCSC genome database name, such as hg19 or hg38"}),
                "track": ("STRING", {"description": "UCSC MAF table name, such as multiz46way"}),
                "chrom": ("STRING", {"description": "Chromosome or sequence name to extract"}),
                "start": ("INT", {"min": 0, "description": "0-based start coordinate"}),
                "end": ("INT", {"min": 1, "description": "0-based end coordinate"}),
                "strand": (
                    "STRING",
                    {
                        "default": ".",
                        "options": cls.STRAND_OPTIONS,
                        "description": "Region strand: no strand, forward, or reverse",
                    },
                ),
            },
            "optional": {
                "ucsc_db_connection": (
                    "FILE",
                    {"description": "Optional UCSC database config; defaults to the pinned public Galaxy config"},
                ),
                "outName": (
                    "STRING",
                    {"default": "", "description": "Override the database.chrom sequence name in the output MAF"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscMafFragsNode(CommandNode):
    """Extract UCSC MAF alignments for BED regions from a database track."""

    NODE_ID = "ucsc_maffrags"
    DISPLAY_NAME = "mafFrags"
    REQUIRED_CONDA_PACKAGES = ["ucsc-maffrags"]
    CATEGORY = "genomics"
    DESCRIPTION = "Extract UCSC MAF alignments for multiple BED regions from a database track."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_mafFrags",
        "ucsc_maffrags",
        "mafFrags",
        "BED region MAF extraction",
        "multiple alignment format",
        "BED12 exons",
        "UCSC MAF track",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["mafFrags"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/ratStuff/mafFrags/mafFrags.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.maf"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "mafFrags",
            str(inputs.get("genome", "")),
            str(inputs.get("track", "")),
            str(inputs.get("bed_file", "")),
        ]
        for flag in ("bed12", "thickOnly", "meFirst", "txStarts", "refCoords"):
            if inputs.get(flag):
                cmd.append(f"-{flag}")
        if str(inputs.get("orgs", "")) != "":
            cmd.append(f"-orgs={inputs.get('orgs')}")
        cmd.append(cls._output_path(inputs))
        return ucsc_db_command(inputs, cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.maf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("bed_file", "genome", "track"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"
        if inputs.get("bed12") and (inputs.get("txStarts") or inputs.get("refCoords")):
            return "bed12 cannot be combined with txStarts or refCoords"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bed_file": ("BED", {"description": "BED6 or BED12 regions to extract from the UCSC MAF track"}),
                "genome": ("STRING", {"description": "UCSC genome database name, such as hg19 or hg38"}),
                "track": ("STRING", {"description": "UCSC MAF table name, such as multiz46way"}),
            },
            "optional": {
                "bed12": ("BOOLEAN", {"default": False, "description": "Treat the input BED as BED12 exon blocks"}),
                "thickOnly": (
                    "BOOLEAN",
                    {"default": False, "description": "When using BED12, extract only thickStart to thickEnd regions"},
                ),
                "meFirst": (
                    "BOOLEAN",
                    {"default": False, "description": "Place the reference genome sequence first in each MAF block"},
                ),
                "txStarts": (
                    "BOOLEAN",
                    {"default": False, "description": "Add txstart r-lines using BED names and reference coordinates"},
                ),
                "refCoords": (
                    "BOOLEAN",
                    {"default": False, "description": "Use actual reference genome coordinates in the output MAF"},
                ),
                "orgs": (
                    "TXT",
                    {"description": "Optional organism order file used with the UCSC -orgs option"},
                ),
                "ucsc_db_connection": (
                    "FILE",
                    {"description": "Optional UCSC database config; defaults to the pinned public Galaxy config"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class UcscMafGeneNode(CommandNode):
    """Extract FASTA gene alignments from UCSC MAF and genePred inputs."""

    NODE_ID = "ucsc_mafgene"
    DISPLAY_NAME = "mafGene"
    REQUIRED_CONDA_PACKAGES = ["ucsc-mafgene"]
    CATEGORY = "genomics"
    DESCRIPTION = "Extract FASTA protein or nucleotide alignments from UCSC MAF and genePred inputs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "ucsc_mafGene",
        "ucsc_mafgene",
        "mafGene",
        "genePred protein alignments",
        "multiple alignment format",
        "species list",
        "UTR alignment",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["mafGene"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/ratStuff/mafGene/mafGene.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "490+galaxy0"
    SHELL = True
    RUN_IN_NODE_OUTPUT_DIR = True

    SELECTION_TYPES = ["all", "single", "list", "bed", "chrom"]
    MAF_FORMATS = ["bigMaf", "bb"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.fasta"

    @classmethod
    def _selection_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("selection_type", "all") or "all")

    @classmethod
    def _maf_name(cls, inputs: dict[str, Any]) -> str:
        suffix = ".bigMaf" if str(inputs.get("maf_format", "bigMaf")) == "bigMaf" else ".bb"
        return f"{_out(inputs)}/input{suffix}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        maf_name = cls._maf_name(inputs)
        genepred_name = f"{_out(inputs)}/input.gp"
        twobit_name = f"{_out(inputs)}/input.2bit"
        setup = [
            _shell_join(["ln", "-s", str(inputs.get("twoBitFile", "")), twobit_name]),
            _shell_join(["ln", "-s", str(inputs.get("maf_file", "")), maf_name]),
            _shell_join(["ln", "-s", str(inputs.get("genepred_file", "")), genepred_name]),
        ]
        cmd = [
            "mafGene",
            f"-twoBit={twobit_name}",
            str(inputs.get("db_name", "")),
            maf_name,
            genepred_name,
            str(inputs.get("species_list", "")),
            cls._output_path(inputs),
        ]
        selection_type = cls._selection_type(inputs)
        if selection_type == "single":
            cmd.append(f"-geneName={inputs.get('gene_name')}")
        elif selection_type == "list":
            cmd.append(f"-geneList={inputs.get('gene_list')}")
        elif selection_type == "bed":
            cmd.append(f"-geneBeds={inputs.get('gene_beds')}")
        elif selection_type == "chrom":
            cmd.append(f"-chrom={inputs.get('chrom')}")
        for flag in ("exons", "noTrans", "uniqAA", "includeUtr", "noDash"):
            if inputs.get(flag):
                cmd.append(f"-{flag}")
        cmd.append("-useFile")
        if str(inputs.get("delay", "")) != "":
            cmd.append(f"-delay={inputs.get('delay')}")
        return " && ".join(setup + [ucsc_db_command(inputs, cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.fasta"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for name in ("twoBitFile", "db_name", "maf_file", "genepred_file", "species_list"):
            if not str(inputs.get(name, "")).strip():
                return f"{name} is required"
        selection_type = cls._selection_type(inputs)
        if selection_type not in cls.SELECTION_TYPES:
            return f"selection_type must be one of: {', '.join(cls.SELECTION_TYPES)}"
        required_for_mode = {
            "single": "gene_name",
            "list": "gene_list",
            "bed": "gene_beds",
            "chrom": "chrom",
        }
        required_name = required_for_mode.get(selection_type)
        if required_name and not str(inputs.get(required_name, "")).strip():
            return f"{required_name} is required when selection_type is {selection_type}"
        if inputs.get("includeUtr") and not inputs.get("noTrans"):
            return "includeUtr requires noTrans"
        maf_format = str(inputs.get("maf_format", "bigMaf") or "bigMaf")
        if maf_format not in cls.MAF_FORMATS:
            return f"maf_format must be one of: {', '.join(cls.MAF_FORMATS)}"
        if "useFile" in inputs and not inputs.get("useFile"):
            return "useFile cannot be disabled because genepred_file is an explicit file input"
        delay = inputs.get("delay", "")
        if str(delay) != "":
            try:
                delay_value = int(delay)
            except (TypeError, ValueError):
                return "delay must be an integer"
            if delay_value < 0:
                return "delay must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "twoBitFile": ("FILE", {"description": "twoBit reference genome used to fill alignment gaps"}),
                "db_name": ("STRING", {"description": "UCSC genome database name, such as hg38 or sacCer3"}),
                "maf_file": ("FILE", {"description": "bigMaf or bigBed alignment file; plain MAF is not supported by mafGene"}),
                "genepred_file": ("FILE", {"description": "Explicit genePred file"}),
                "species_list": (
                    "FILE",
                    {"description": "Species list file with one species name per line"},
                ),
            },
            "optional": {
                "selection_type": (
                    "STRING",
                    {
                        "default": "all",
                        "options": cls.SELECTION_TYPES,
                        "description": "Select all genes, one gene, a gene list, BED-defined genes, or one chromosome",
                    },
                ),
                "maf_format": (
                    "STRING",
                    {
                        "default": "bigMaf",
                        "options": cls.MAF_FORMATS,
                        "description": "Logical alignment file type used to preserve the suffix mafGene inspects",
                    },
                ),
                "gene_name": ("STRING", {"default": "", "description": "Gene name used when selection_type is single"}),
                "gene_list": (
                    "FILE",
                    {"default": "", "description": "File containing gene names used when selection_type is list"},
                ),
                "gene_beds": ("BED", {"description": "BED4 file of genes used when selection_type is bed"}),
                "chrom": ("STRING", {"default": "", "description": "Chromosome name used when selection_type is chrom"}),
                "exons": ("BOOLEAN", {"default": False, "description": "Output exon alignments instead of full genes"}),
                "noTrans": (
                    "BOOLEAN",
                    {"default": False, "description": "Keep nucleotide alignments instead of translating to amino acids"},
                ),
                "uniqAA": (
                    "BOOLEAN",
                    {"default": False, "description": "Emit a unique pseudo-amino-acid code for every codon"},
                ),
                "includeUtr": (
                    "BOOLEAN",
                    {"default": False, "description": "Include untranslated regions; requires noTrans"},
                ),
                "noDash": ("BOOLEAN", {"default": False, "description": "Skip output rows containing only dashes"}),
                "useFile": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "description": "Compatibility flag; explicit genepred_file contracts always require -useFile",
                    },
                ),
                "delay": (
                    "INT",
                    {"default": "", "min": 0, "description": "Optional delay in seconds between genes"},
                ),
                "ucsc_db_connection": (
                    "FILE",
                    {"description": "Optional UCSC database config; defaults to the pinned public Galaxy config"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


_KENT_482_NODES = [
    UcscMafFilterNode,
    UcscMafFetchNode,
    UcscMafAddIRowsNode,
    UcscMafFragNode,
    UcscMafFragsNode,
]
pin_contract(
    _KENT_482_NODES,
    runtime_version="482",
    runtime_git_url=KENT_GIT_URL,
    runtime_git_commit=KENT_482_GIT_COMMIT,
)
for _node_class in _KENT_482_NODES:
    _node_class.PACKAGE_CONSTRAINT = "; ".join(
        f"{package}==482" for package in _node_class.REQUIRED_CONDA_PACKAGES
    )
pin_contract(
    [UcscMafGeneNode],
    runtime_version="490",
    runtime_git_url=KENT_GIT_URL,
    runtime_git_commit=KENT_490_GIT_COMMIT,
    package_constraint="ucsc-mafgene==490",
)
