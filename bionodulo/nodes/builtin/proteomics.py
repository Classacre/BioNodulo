"""Proteomics workflow nodes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class MaxQuantNode(CommandNode):
    """Run MaxQuant for quantitative proteomics."""
    NODE_ID = "maxquant"
    DISPLAY_NAME = "MaxQuant"
    CATEGORY = "proteomics"
    DESCRIPTION = "Quantitative proteomics: LFQ, TMT/iTRAQ, SILAC. Requires Mono on Linux. Industry standard."
    SEARCH_ALIASES = ["maxquant", "proteomics", "lfq", "tmt", "protein quantification"]
    RETURN_TYPES = ("DIRECTORY", "CSV")
    RETURN_NAMES = ("results_dir", "protein_groups")
    REQUIRED_EXECUTABLES = ["MaxQuantCmd.exe"]
    REQUIRED_CONDA_PACKAGES = ["maxquant"]
    DOCUMENTATION_URL = "https://maxquant.org/"
    VERSION = "2.6.3"
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        fasta = str(inputs.get("fasta_db", ""))
        raw_files = inputs.get("raw_files", [])
        if isinstance(raw_files, str):
            raw_files = [raw_files]
        mqpar = f"{out_dir}/mqpar.xml"
        script = f"""
import xml.etree.ElementTree as ET
root = ET.Element('MaxQuantParams')
ET.SubElement(root, 'fastaFilePath').text = '{fasta}'
raws = ET.SubElement(root, 'filePaths')
for rf in {raw_files!r}:
    ET.SubElement(raws, 'string').text = rf
ET.SubElement(root, 'configFolder').text = '{out_dir}'
exps = ET.SubElement(root, 'experiments')
for raw_file in {raw_files!r}:
    import os
    ET.SubElement(exps, 'string').text = os.path.basename(raw_file.replace('.raw', '').replace('.mzML', ''))
ET.SubElement(root, 'lfqMode').text = '{"true" if inputs.get("lfq", True) else "false"}'
ET.SubElement(root, 'minPeptideLen').text = '{inputs.get("min_peptide_length", 7)}'
ET.SubElement(root, 'matchBetweenRuns').text = '{"true" if inputs.get("match_between_runs", True) else "false"}'
ET.SubElement(root, 'peptideFdr').text = '{inputs.get("peptide_fdr", 0.01)}'
ET.SubElement(root, 'proteinFdr').text = '{inputs.get("protein_fdr", 0.01)}'
ET.ElementTree(root).write('{mqpar}', xml_declaration=True, encoding='UTF-8')
"""
        cmd = ["python", "-c", script, "&&"]
        if inputs.get("use_mono", True):
            cmd.extend(["mono", "MaxQuantCmd.exe", mqpar])
        else:
            cmd.extend(["MaxQuantCmd.exe", mqpar])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "results_dir", node_out / "protein_groups.csv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "raw_files": ("FILE", {"description": "MS raw files (.raw, .mzML, .mzXML)"}),
                "fasta_db": ("FASTA", {"description": "Protein database FASTA (with contaminants)"}),
            },
            "optional": {
                "lfq": ("BOOLEAN", {"default": True, "description": "Label-free quantification"}),
                "min_peptide_length": ("INT", {"default": 7, "min": 4, "max": 20}),
                "use_mono": ("BOOLEAN", {"default": True, "description": "Mono runtime (Linux)"}),
                "match_between_runs": ("BOOLEAN", {"default": True}),
                "peptide_fdr": ("FLOAT", {"default": 0.01, "min": 0.001, "max": 0.1, "step": 0.001}),
                "protein_fdr": ("FLOAT", {"default": 0.01, "min": 0.001, "max": 0.1, "step": 0.001}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MSFraggerNode(CommandNode):
    """Run MSFragger for peptide identification."""
    NODE_ID = "msfragger"
    DISPLAY_NAME = "MSFragger"
    CATEGORY = "proteomics"
    DESCRIPTION = "Ultra-fast peptide identification. Supports open search for PTM discovery and closed search."
    SEARCH_ALIASES = ["msfragger", "fragpipe", "proteomics", "peptide identification", "database search"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("pepxml",)
    REQUIRED_EXECUTABLES = ["msfragger"]
    REQUIRED_CONDA_PACKAGES = ["msfragger"]
    DOCUMENTATION_URL = "https://msfragger.nesvilab.org/"
    VERSION = "4.1"
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(inputs.get("output", "."))
        out_dir.mkdir(parents=True, exist_ok=True)
        params_file = out_dir / "fragger.params"
        raw_files = inputs.get("raw_files", [])
        if isinstance(raw_files, str):
            raw_files = [raw_files]

        params_lines = [
            f"database_name = {inputs.get('fasta_db', '')}",
            f"num_threads = {inputs.get('threads', 4)}",
            f"precursor_mass_lower = -{inputs.get('prec_tol_low', 20)}",
            f"precursor_mass_upper = {inputs.get('prec_tol_high', 20)}",
            f"precursor_mass_units = {inputs.get('prec_tol_units', 1)}",
            f"fragment_mass_tolerance = {inputs.get('frag_tol', 20)}",
            f"fragment_mass_units = {inputs.get('frag_tol_units', 1)}",
            f"calibrate_mass = {inputs.get('calibrate_mass', 'none')}",
        ]
        if not inputs.get("open_search"):
            params_lines.extend([
                "variable_mod_01 = 15.99490 M",
                "variable_mod_02 = 42.01060 [^",
            ])
        params_lines.append("output_format = pepxml")
        params_file.write_text("\n".join(params_lines) + "\n")
        return ["msfragger", str(params_file)] + [str(raw_file) for raw_file in raw_files]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "pepxml.pepXML"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "raw_files": ("FILE", {"description": "MS raw files (.mzML, .mzXML, .raw)"}),
                "fasta_db": ("FASTA", {"description": "Target-decoy protein DB FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "optional": {
                "open_search": ("BOOLEAN", {"default": False, "description": "Open search for PTM discovery"}),
                "prec_tol_low": ("FLOAT", {"default": 20.0}),
                "prec_tol_high": ("FLOAT", {"default": 20.0}),
                "prec_tol_units": ("INT", {"default": 1, "min": 0, "max": 1, "label": "0=Da, 1=ppm"}),
                "frag_tol": ("FLOAT", {"default": 20.0}),
                "frag_tol_units": ("INT", {"default": 1, "min": 0, "max": 1}),
                "calibrate_mass": ("STRING", {"default": "none", "options": ["none", "coarse", "iterative"]}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class PercolatorNode(CommandNode):
    """Run Percolator for PSM validation and FDR estimation."""
    NODE_ID = "percolator"
    DISPLAY_NAME = "Percolator"
    CATEGORY = "proteomics"
    DESCRIPTION = "Semi-supervised ML for PSM validation and FDR estimation. Superior to target-decoy alone."
    SEARCH_ALIASES = ["percolator", "psm validation", "fdr", "peptide spectrum match"]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("percolator_psms", "percolator_proteins")
    REQUIRED_EXECUTABLES = ["percolator"]
    REQUIRED_CONDA_PACKAGES = ["percolator"]
    DOCUMENTATION_URL = "https://github.com/percolator/percolator"
    VERSION = "3.7.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "percolator",
            str(inputs.get("pin_file", "")),
            "-X",
            f"{out_dir}/percolator_psms.tsv",
            "--protein-decoy-pattern",
            str(inputs.get("decoy_prefix", "decoy")),
            "--decoy-xml-output",
            "--no-split-large-instances",
        ]
        if inputs.get("fdr_psm"):
            cmd.extend(["--post-processing-tdc", "--fdr", str(inputs["fdr_psm"])])
        if inputs.get("fdr_protein"):
            cmd.extend(["--picked-protein", str(inputs.get("fasta_db", ""))])
            cmd.extend(["--protein-fdr", str(inputs["fdr_protein"])])
        if inputs.get("enzyme"):
            cmd.extend(["--enzyme", str(inputs["enzyme"])])
        cmd.extend(["-l", f"{out_dir}/percolator_proteins.tsv"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "percolator_psms.tsv", node_out / "percolator_proteins.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "pin_file": ("FILE", {"description": "PIN file from search engine"}),
                "fasta_db": ("FASTA", {"description": "Protein DB FASTA"}),
            },
            "optional": {
                "decoy_prefix": ("STRING", {"default": "decoy"}),
                "fdr_psm": ("FLOAT", {"default": 0.01, "min": 0.001, "max": 0.1, "step": 0.001}),
                "fdr_protein": ("FLOAT", {"default": 0.01, "min": 0.001, "max": 0.1, "step": 0.001}),
                "enzyme": ("STRING", {"default": "trypsin", "options": ["trypsin", "chymotrypsin", "lys-c", "argc"]}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
