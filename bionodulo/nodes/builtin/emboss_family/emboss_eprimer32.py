"""EMBOSS eprimer32: Pick PCR primers and hybridization oligos.

Generated from the suite's own ACD definition for eprimer32 in the pinned
emboss==6.6.0 image. ACD SHA-256: 6940e4b37302d01322c76f0bcfb3c51110f79042fd609dc2a363eaae60fdcd11

Generation is not admission: this node renders a command but has no real queued
run or independent oracle, so it is a contract, not a verified operation.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossEprimer32Node(EmbossBase):
    """Pick PCR primers and hybridization oligos"""

    NODE_ID = 'emboss_eprimer32'
    DISPLAY_NAME = 'EMBOSS eprimer32'
    CATEGORY = "emboss"
    DESCRIPTION = 'Pick PCR primers and hybridization oligos'
    SEARCH_ALIASES = ["emboss", 'eprimer32']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('outfile',)
    OUTPUT_FILENAMES = ('outfile.out',)
    REQUIRED_EXECUTABLES = ['eprimer32']
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/eprimer32.html"
    PATH_INPUTS = ('sequence', 'mishyblibraryfile', 'mispriminglibraryfile')
    REQUIRED_PATH_INPUTS = ('sequence',)
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": 'https://bio.tools/eprimer32',
        "topics": [{'uri': 'http://edamontology.org/topic_0077', 'label': 'Nucleic acid analysis'}],
        "operations": [{'uri': 'http://edamontology.org/operation_0308', 'label': 'PCR primer design'}, {'uri': 'http://edamontology.org/operation_0309', 'label': 'Microarray probe design'}],
        "reviewed_at": "2026-09-26",
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                'sequence': ((("FASTA", "FILE")), {"description": 'Primary input file'}),
            },
            "optional": {
                "primer": ('STRING', {'default': 'Y', 'description': 'Pick PCR primer(s)'}),
                "task": ('STRING', {'options': ['1'], 'default': '1', 'description': 'Select task'}),
                "hybridprobe": ('STRING', {'default': 'N', 'description': 'Pick hybridization probe'}),
                "numreturn": ('INT', {'min': 0, 'default': 5, 'description': 'Number of results to return'}),
                "includedregion": ('STRING', {'description': 'Included region(s)'}),
                "targetregion": ('STRING', {'description': 'Target region(s)'}),
                "excludedregion": ('STRING', {'description': 'Excluded region(s)'}),
                "forwardinput": ('STRING', {'description': 'Forward input primer sequence to check'}),
                "reverseinput": ('STRING', {'description': 'Reverse input primer sequence to check'}),
                "okleftregion": ('STRING', {'description': 'Possible left primer of pair location'}),
                "okrightregion": ('STRING', {'description': 'Possible right primer of pair location'}),
                "gcclamp": ('INT', {'min': 0, 'default': 0, 'description': 'GC clamp'}),
                "optsize": ('INT', {'min': 0, 'default': 20, 'description': 'Primer optimum size'}),
                "minsize": ('INT', {'min': 1, 'default': 18, 'description': 'Primer minimum size'}),
                "maxsize": ('INT', {'max': 35, 'default': 27, 'description': 'Primer maximum size'}),
                "opttm": ('FLOAT', {'default': 60.0, 'description': 'Primer optimum Tm'}),
                "mintm": ('FLOAT', {'default': 57.0, 'description': 'Primer minimum Tm'}),
                "maxtm": ('FLOAT', {'default': 63.0, 'description': 'Primer maximum Tm'}),
                "maxdifftm": ('FLOAT', {'default': 100.0, 'description': 'Maximum difference in Tm of primers'}),
                "ogcpercent": ('FLOAT', {'default': 50.0, 'description': 'Primer optimum GC percent'}),
                "mingc": ('FLOAT', {'default': 20.0, 'description': 'Primer minimum GC percent'}),
                "maxgc": ('FLOAT', {'default': 80.0, 'description': 'Primer maximum GC percent'}),
                "saltconc": ('FLOAT', {'default': 50.0, 'description': 'Salt concentration (mM)'}),
                "dnaconc": ('FLOAT', {'default': 50.0, 'description': 'DNA concentration (nM)'}),
                "maxpolyx": ('INT', {'min': 0, 'default': 5, 'description': 'Maximum polynucleotide repeat'}),
                "psizeopt": ('INT', {'min': 0, 'default': 200, 'description': 'Product optimum size'}),
                "prange": ('STRING', {'default': '100-300', 'description': 'Product size range'}),
                "ptmopt": ('FLOAT', {'default': 0.0, 'description': 'Product optimum Tm'}),
                "ptmmin": ('FLOAT', {'default': -1000000.0, 'description': 'Product minimum Tm'}),
                "ptmmax": ('FLOAT', {'default': 1000000.0, 'description': 'Product maximum Tm'}),
                "oexcludedregion": ('STRING', {'description': 'Internal oligo excluded region'}),
                "oligoinput": ('STRING', {'description': 'Internal oligo input sequence (if any)'}),
                "osizeopt": ('INT', {'min': 0, 'default': 20, 'description': 'Internal oligo optimum size'}),
                "ominsize": ('INT', {'min': 0, 'default': 18, 'description': 'Internal oligo minimum size'}),
                "omaxsize": ('INT', {'max': 35, 'default': 27, 'description': 'Internal oligo maximum size'}),
                "otmopt": ('FLOAT', {'default': 60.0, 'description': 'Internal oligo optimum Tm'}),
                "otmmin": ('FLOAT', {'default': 57.0, 'description': 'Internal oligo minimum Tm'}),
                "otmmax": ('FLOAT', {'default': 63.0, 'description': 'Internal oligo maximum Tm'}),
                "ogcopt": ('FLOAT', {'default': 50.0, 'description': 'Internal oligo optimum GC percent'}),
                "ogcmin": ('FLOAT', {'default': 20.0, 'description': 'Internal oligo minimum GC'}),
                "ogcmax": ('FLOAT', {'default': 80.0, 'description': 'Internal oligo maximum GC'}),
                "osaltconc": ('FLOAT', {'default': 50.0, 'description': 'Internal oligo salt concentration (mM)'}),
                "odnaconc": ('FLOAT', {'default': 50.0, 'description': 'Internal oligo DNA concentration (nM)'}),
                "oanyself": ('FLOAT', {'default': 12.0, 'description': 'Internal oligo maximum self complementarity'}),
                "oendself": ('FLOAT', {'default': 12.0, 'description': "Internal oligo maximum 3' self complementarity"}),
                "opolyxmax": ('INT', {'min': 0, 'default': 5, 'description': 'Internal oligo maximum polynucleotide repeat'}),
                "omishybmax": ('FLOAT', {'default': 12.0, 'description': 'Internal oligo maximum mishybridization'}),
                "explainflag": ('BOOLEAN', {'default': False, 'description': 'Explain flag'}),
                "fileflag": ('BOOLEAN', {'default': False, 'description': 'Create results files for each sequence'}),
                "pickanyway": ('BOOLEAN', {'default': False, 'description': 'Pick anyway'}),
                "maxmispriming": ('FLOAT', {'default': 12.0, 'description': 'Primer maximum mispriming'}),
                "pairmaxmispriming": ('FLOAT', {'default': 24.0, 'description': 'Primer pair maximum mispriming'}),
                "numnsaccepted": ('INT', {'min': 0, 'default': 0, 'description': 'Maximum Ns accepted in a primer'}),
                "selfany": ('FLOAT', {'default': 8.0, 'description': 'Maximum self complementarity'}),
                "selfend": ('FLOAT', {'default': 3.0, 'description': "Maximum 3' self complementarity"}),
                "scorrection": ('STRING', {'options': ['0'], 'default': '1', 'description': 'Select task'}),
                "tmformula": ('STRING', {'options': ['0'], 'default': '1', 'description': 'Select formula'}),
                "maxendstability": ('FLOAT', {'default': 9.0, 'description': "Maximum 3' end stability"}),
                'mishyblibraryfile': ("FILE", {"description": 'Primer3 internal oligo mishybridizing library file (optional)'}),
                'mispriminglibraryfile': ("FILE", {"description": 'Primer3 mispriming library file (optional)'}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ['eprimer32']
        for name in cls.PATH_INPUTS:
            value = inputs.get(name)
            if value not in (None, ""):
                command.extend([f"-{name}", str(value)])
        output_dir = cls.output_dir(inputs)
        graph_flag = None
        # A stdout-only program has no output qualifier at all; its planned file
        # is filled by the executor's stdout capture instead.
        declared: list[str] = [] if False else list(['outfile'])
        for index, flag in enumerate(declared):
            if flag == graph_flag:
                command.extend([f"-{flag}", "png", "-goutfile", str(output_dir / flag)])
            else:
                command.extend([f"-{flag}", str(output_dir / cls.OUTPUT_FILENAMES[index])])
        # Request the plot even when it is not a required output, so EMBOSS does
        # not fall back to an interactive device and hang.
        if graph_flag and graph_flag not in declared:
            command.extend([f"-{graph_flag}", "png", "-goutfile", str(output_dir / graph_flag)])
        # Required scalar parameters must be rendered too. Emitting only the
        # optional ones silently dropped inputs like fuzznuc's ``-pattern`` and
        # made the tool fail with "Bad value for '-pattern'".
        declared_types = cls.INPUT_TYPES()
        for category in ("required", "optional"):
            for name, spec in declared_types.get(category, {}).items():
                if name in cls.PATH_INPUTS:
                    continue
                value = inputs.get(name)
                if value in (None, ""):
                    continue
                declared = spec[0] if isinstance(spec, (list, tuple)) else spec
                if declared == "FILE":
                    continue
                default = spec[1].get("default") if isinstance(spec, tuple) and len(spec) > 1 else None
                if declared == "BOOLEAN":
                    command.extend([f"-{name}", "Y" if value else "N"])
                    continue
                if value == default:
                    continue
                command.extend([f"-{name}", str(value)])
        # EMBOSS prompts for confirmation on some programs; -auto makes it
        # non-interactive, which is required in a batch runner.
        command.append("-auto")
        return command
