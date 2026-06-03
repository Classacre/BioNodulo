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
