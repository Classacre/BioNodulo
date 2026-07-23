"""UCSC FASTA utility nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_beacon_ucsc_family.adapter import (
    KENT_482_GIT_COMMIT,
    KENT_GIT_URL,
    pin_contract,
)

class FaSplitNode(CommandNode):
    """Split a FASTA file into multiple FASTA files."""

    LEGACY_NODE_ID = "fasplit"
    DISPLAY_NAME = "faSplit"
    REQUIRED_CONDA_PACKAGES = ["ucsc-fasplit"]
    CATEGORY = "genomics"
    DESCRIPTION = "Split a FASTA file into multiple FASTA files."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "fasplit",
        "faSplit",
        "split FASTA",
        "FASTA chunks",
        "by sequence name",
        "gap boundaries",
    ]
    RETURN_TYPES = ("DIRECTORY", "TXT")
    RETURN_NAMES = ("output_list", "lift_file")
    REQUIRED_EXECUTABLES = ["faSplit"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/utils/faSplit/faSplit.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    SPLIT_TYPES = ["sequence", "base", "size", "byname", "about", "gap"]
    MODES_WITH_COUNT = {"sequence", "base", "size", "about", "gap"}

    @classmethod
    def _split_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("split_type", "sequence") or "sequence")

    @classmethod
    def _output_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_list"

    @classmethod
    def _lift_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/fasplit.lft"

    @classmethod
    def _count(cls, inputs: dict[str, Any]) -> int:
        value = inputs.get("count")
        if value not in (None, ""):
            return int(value)
        return 100 if cls._split_type(inputs) == "size" else 10

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        split_type = cls._split_type(inputs)
        out_dir = cls._output_dir(inputs)
        cmd = ["faSplit"]
        if str(inputs.get("maxN", "")) != "" and split_type in {"size", "gap"}:
            cmd.append(f"-maxN={inputs.get('maxN')}")
        if inputs.get("oneFile") and split_type in {"size", "gap"}:
            cmd.append("-oneFile")
        if str(inputs.get("extra", "")) != "" and split_type == "size":
            cmd.append(f"-extra={inputs.get('extra')}")
        if inputs.get("lift") and split_type in {"size", "gap"}:
            cmd.append(f"-lift={cls._lift_path(inputs)}")
        if str(inputs.get("minGapSize", "")) != "" and split_type == "gap":
            cmd.append(f"-minGapSize={inputs.get('minGapSize')}")
        if inputs.get("noGapDrops") and split_type == "gap":
            cmd.append("-noGapDrops")
        if str(inputs.get("outDirDepth", "")) != "":
            cmd.append(f"-outDirDepth={inputs.get('outDirDepth')}")
        if str(inputs.get("prefixLength", "")) != "" and split_type == "byname":
            cmd.append(f"-prefixLength={inputs.get('prefixLength')}")
        cmd.extend([split_type, str(inputs.get("input", ""))])
        if split_type in cls.MODES_WITH_COUNT:
            cmd.append(str(cls._count(inputs)))
        cmd.append(f"{out_dir}/")
        return f"mkdir -p {shlex.quote(out_dir)} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        output_list = node_out / "output_list"
        output_list.mkdir(parents=True, exist_ok=True)
        outputs = [output_list]
        if inputs.get("lift") and cls._split_type(inputs) in {"size", "gap"}:
            outputs.append(node_out / "fasplit.lft")
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        mapped: dict[str, Path] = {}
        for path in map(Path, planned_paths):
            if path.name == "output_list":
                mapped["output_list"] = path
            elif path.name == "fasplit.lft":
                mapped["lift_file"] = path
            else:
                raise ValueError(f"fasplit planned an unknown output artifact: {path.name}")
        if "output_list" not in mapped:
            raise ValueError("fasplit did not plan its output_list directory")
        return mapped

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        result = await super().run(**kwargs)
        mapped = self.__class__.MAP_PLANNED_OUTPUTS([Path(path) for path in result])
        return {"outputs": {name: str(path) for name, path in mapped.items()}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        split_type = cls._split_type(inputs)
        if split_type not in cls.SPLIT_TYPES:
            return f"split_type must be one of: {', '.join(cls.SPLIT_TYPES)}"
        if split_type in cls.MODES_WITH_COUNT:
            try:
                count = cls._count(inputs)
            except (TypeError, ValueError):
                return "count must be an integer"
            if count < 1:
                return "count must be greater than or equal to 1"
        minimums = {
            "maxN": 0,
            "extra": 0,
            "minGapSize": 1,
            "outDirDepth": 0,
            "prefixLength": 1,
        }
        for name, minimum in minimums.items():
            value = inputs.get(name, "")
            if str(value) != "" and int(value) < minimum:
                return f"{name} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "FASTA file to split"}),
            },
            "optional": {
                "split_type": (
                    "STRING",
                    {
                        "default": "sequence",
                        "options": cls.SPLIT_TYPES,
                        "description": "Split by sequence records, bases, chunk size, sequence name, approximate bytes, or gap boundaries",
                    },
                ),
                "count": (
                    "INT",
                    {
                        "default": "",
                        "min": 1,
                        "description": "Mode-specific count; defaults to 100 for size and 10 for other counted modes",
                    },
                ),
                "maxN": (
                    "INT",
                    {"default": "", "min": 0, "description": "Suppress size/gap pieces with more than this many Ns"},
                ),
                "oneFile": (
                    "BOOLEAN",
                    {"default": False, "description": "Write size/gap pieces into one FASTA file"},
                ),
                "extra": (
                    "INT",
                    {"default": "", "min": 0, "description": "Add overlapping bases to size-mode pieces"},
                ),
                "lift": (
                    "BOOLEAN",
                    {"default": False, "description": "Write a lift file describing how pieces reconstruct the input"},
                ),
                "minGapSize": (
                    "INT",
                    {"default": "", "min": 1, "description": "Minimum N run length considered a gap in gap mode"},
                ),
                "noGapDrops": (
                    "BOOLEAN",
                    {"default": False, "description": "Keep gap-only pieces when splitting by gap"},
                ),
                "outDirDepth": (
                    "INT",
                    {"default": "", "min": 0, "description": "Create nested numeric output directories"},
                ),
                "prefixLength": (
                    "INT",
                    {"default": "", "min": 1, "description": "Group byname output by sequence-name prefix length"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
class FaToVcfNode(CommandNode):
    """Convert FASTA alignments to VCF single-nucleotide differences."""

    LEGACY_NODE_ID = "fatovcf"
    DISPLAY_NAME = "faToVcf"
    REQUIRED_CONDA_PACKAGES = ["ucsc-fatovcf"]
    CATEGORY = "variant"
    DESCRIPTION = "Convert a FASTA alignment file to Variant Call Format single-nucleotide differences."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "UCSC Genome Browser Utilities",
        "fatovcf",
        "faToVcf",
        "FASTA alignment to VCF",
        "single-nucleotide diffs",
        "ambiguous bases",
        "mask sites",
    ]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("out",)
    REQUIRED_EXECUTABLES = ["faToVcf"]
    DOCUMENTATION_URL = "https://github.com/ucscGenomeBrowser/kent/blob/master/src/hg/utils/faToVcf/faToVcf.c"
    CITATION_DOIS = [UCSC_UTILS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{UCSC_UTILS_CITATION_DOI}"]
    CITATION_TEXT = UCSC_UTILS_CITATION_TEXT
    VERSION = "482+galaxy0"

    REFERENCE_MODES = ["", "customRef"]
    AMBIGUOUS_MODES = ["", "-ambiguousToN", "-resolveAmbiguous"]

    @classmethod
    def _reference_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("refSeq", "") or "")

    @classmethod
    def _ambiguous_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ambiguous", "") or "")

    @classmethod
    def _staged_input_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/in.fa"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out.vcf"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged_input = cls._staged_input_path(inputs)
        setup = _shell_join(["ln", "-s", str(inputs.get("in_fasta", "")), staged_input])
        cmd = ["faToVcf", staged_input, cls._output_path(inputs)]
        if cls._reference_mode(inputs) == "customRef":
            cmd.append(f"-ref={inputs.get('ref', '')}")
        if ambiguous := cls._ambiguous_mode(inputs):
            cmd.append(ambiguous)
        if str(inputs.get("excludeFile", "")) != "":
            cmd.append(f"-excludeFile={inputs.get('excludeFile')}")
        cmd.append(f"-maxDiff={inputs.get('maxDiff', 0)}")
        if str(inputs.get("maskSites", "")) != "":
            cmd.append(f"-maskSites={inputs.get('maskSites')}")
        if int(inputs.get("windowSize", 0) or 0) > 0:
            cmd.append(f"-windowSize={inputs.get('windowSize')}")
            cmd.append(f"-minAmbigInWindow={inputs.get('minAmbigInWindow', 2)}")
        if inputs.get("includeNoAltN"):
            cmd.append("-includeNoAltN")
        cmd.append(f"-minAc={inputs.get('minAc', 0)}")
        cmd.append(f"-minAf={inputs.get('minAf', 0.0)}")
        if int(inputs.get("startOffset", 0) or 0) > 0:
            cmd.append(f"-startOffset={inputs.get('startOffset')}")
        if inputs.get("includeRef"):
            cmd.append("-includeRef")
        if inputs.get("noGenotypes"):
            cmd.append("-noGenotypes")
        if str(inputs.get("vcfChrom", "")) != "":
            cmd.append(f"-vcfChrom={inputs.get('vcfChrom')}")
        return f"{setup} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out.vcf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("in_fasta", "")).strip():
            return "in_fasta is required"
        reference_mode = cls._reference_mode(inputs)
        if reference_mode not in cls.REFERENCE_MODES:
            return f"refSeq must be one of: {', '.join(cls.REFERENCE_MODES)}"
        if reference_mode == "customRef" and not str(inputs.get("ref", "")).strip():
            return "ref is required when refSeq is customRef"
        ambiguous = cls._ambiguous_mode(inputs)
        if ambiguous not in cls.AMBIGUOUS_MODES:
            return f"ambiguous must be one of: {', '.join(cls.AMBIGUOUS_MODES)}"
        minimums = {
            "maxDiff": 0,
            "windowSize": 0,
            "minAmbigInWindow": 1,
            "minAc": 0,
            "startOffset": 0,
        }
        for name, minimum in minimums.items():
            value = inputs.get(name, "")
            if str(value) != "" and int(value) < minimum:
                return f"{name} must be greater than or equal to {minimum}"
        min_af = inputs.get("minAf", "")
        if str(min_af) != "" and not 0.0 <= float(min_af) <= 1.0:
            return "minAf must be between 0.0 and 1.0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_fasta": ("FASTA", {"description": "FASTA alignment with same-length sequences"}),
            },
            "optional": {
                "refSeq": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.REFERENCE_MODES,
                        "description": "Use the first sequence or a custom sequence as the reference",
                    },
                ),
                "ref": (
                    "STRING",
                    {"default": "", "description": "Reference sequence name used when refSeq is customRef"},
                ),
                "ambiguous": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.AMBIGUOUS_MODES,
                        "description": "Treat IUPAC ambiguous bases as no-calls or resolve compatible ambiguous calls",
                    },
                ),
                "excludeFile": (
                    "FILE",
                    {"description": "Optional file listing sequence names to exclude"},
                ),
                "maxDiff": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Exclude sequences with more than this many mismatches"},
                ),
                "maskSites": (
                    "VCF",
                    {"description": "Optional VCF of positions to mask"},
                ),
                "windowSize": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Window radius used for ambiguity masking"},
                ),
                "minAmbigInWindow": (
                    "INT",
                    {"default": 2, "min": 1, "description": "Minimum ambiguous bases in a window before masking"},
                ),
                "includeNoAltN": (
                    "BOOLEAN",
                    {"default": False, "description": "Include no-alternate positions with missing calls"},
                ),
                "minAc": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Minimum alternate allele count"},
                ),
                "minAf": (
                    "FLOAT",
                    {"default": 0.0, "min": 0.0, "max": 1.0, "description": "Minimum alternate allele frequency"},
                ),
                "startOffset": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Offset added to each VCF position"},
                ),
                "includeRef": (
                    "BOOLEAN",
                    {"default": False, "description": "Include the reference sequence in genotype columns"},
                ),
                "noGenotypes": (
                    "BOOLEAN",
                    {"default": False, "description": "Output an 8-column VCF without genotype columns"},
                ),
                "vcfChrom": (
                    "STRING",
                    {"default": "", "description": "Sequence name to use in the VCF CHROM column"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }


_KENT_482_NODES = [FaSplitNode, FaToVcfNode]
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
