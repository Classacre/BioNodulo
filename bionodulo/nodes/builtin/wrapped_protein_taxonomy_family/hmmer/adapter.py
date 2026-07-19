"""Shared HMMER contracts for focused protein taxonomy nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_protein_taxonomy_family.contracts import ValidatedCommandContract


HMMER_GIT_COMMIT = "9acd8b6758a0ca5d21db6d167e0277484341929b"


class HMMERContractNode(ValidatedCommandContract):
    """HMMER 3.4 command semantics pinned to the released source tree."""

    GIT_URL = "https://github.com/EddyRivasLab/hmmer.git"
    GIT_COMMIT = HMMER_GIT_COMMIT
    SOURCE_URL = f"https://github.com/EddyRivasLab/hmmer/tree/{HMMER_GIT_COMMIT}"
    PACKAGE_CONSTRAINT = "hmmer==3.4"
    EXIT_SEMANTICS = "HMMER parse, input, and search failures must produce a non-zero command result."


class _HMMERAlimaskContract(HMMERContractNode):
    """Apply an HMMER model or alignment coordinate mask to an MSA."""

    LEGACY_NODE_ID = "hmmer_alimask"
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

class _HMMERHmmalignContract(HMMERContractNode):
    """Align sequences to a profile HMM using hmmalign."""

    LEGACY_NODE_ID = "hmmer_hmmalign"
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

class _HMMERHmmbuildContract(HMMERContractNode):
    """Build a profile HMM from a multiple sequence alignment."""

    LEGACY_NODE_ID = "hmmer_hmmbuild"
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

class _HMMERHmmconvertContract(HMMERContractNode):
    """Convert HMM profile files between HMMER formats."""

    LEGACY_NODE_ID = "hmmer_hmmconvert"
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

class _HMMERHmmemitContract(HMMERContractNode):
    """Sample sequences or consensus output from a profile HMM."""

    LEGACY_NODE_ID = "hmmer_hmmemit"
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

class _HMMERHmmfetchContract(HMMERContractNode):
    """Retrieve selected profile HMM models from a HMM file."""

    LEGACY_NODE_ID = "hmmer_hmmfetch"
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

class _HMMERJackhmmerContract(HMMERContractNode):
    """Iteratively search protein sequences against a protein FASTA database."""

    LEGACY_NODE_ID = "hmmer_jackhmmer"
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

class _HMMERPhmmerContract(_HMMERJackhmmerContract):
    """Search protein sequences against a protein FASTA database."""

    LEGACY_NODE_ID = "hmmer_phmmer"
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

class _HMMERNhmmerContract(_HMMERJackhmmerContract):
    """Search nucleotide queries against a nucleotide FASTA database."""

    LEGACY_NODE_ID = "hmmer_nhmmer"
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

class _HMMERNhmmscanContract(_HMMERNhmmerContract):
    """Search nucleotide sequences against a nucleotide profile HMM database."""

    LEGACY_NODE_ID = "hmmer_nhmmscan"
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
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        source = str(inputs.get("hmm_source", "history") or "history")
        if source == "history" and not str(inputs.get("hmmfile", "")).strip():
            return "hmmfile is required when hmm_source=history"
        if source == "indexed" and not str(inputs.get("hmmdb", "")).strip():
            return "hmmdb is required when hmm_source=indexed"
        return True

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

class _HMMERHmmsearchContract(HMMERContractNode):
    """Search sequence databases with profile HMMs using hmmsearch."""

    LEGACY_NODE_ID = "hmmer_hmmsearch"
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

class _HMMERHmmscanContract(_HMMERHmmsearchContract):
    """Search sequences against a profile HMM database using hmmscan."""

    LEGACY_NODE_ID = "hmmer_hmmscan"
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
            "optional": _HMMERHmmsearchContract.INPUT_TYPES()["optional"],
            "hidden": {"output": ("STRING", {})},
        }
