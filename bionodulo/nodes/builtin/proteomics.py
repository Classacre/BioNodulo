"""Proteomics workflow nodes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


def _file_list(value: Any) -> list[str]:
    if isinstance(value, list | tuple):
        return [str(item) for item in value if str(item)]
    text = str(value or "")
    return [text] if text else []


def _sage_enzyme_config(inputs: dict[str, Any]) -> dict[str, Any]:
    enzyme = str(inputs.get("enzyme", "trypsin") or "trypsin").lower()
    config = {
        "missed_cleavages": int(inputs.get("missed_cleavages", 2)),
        "min_len": int(inputs.get("min_peptide_length", 7)),
        "max_len": int(inputs.get("max_peptide_length", 40)),
    }
    if enzyme == "trypsin":
        config.update({"cleave_at": "KR", "restrict": "P"})
    return config


def _sage_config_text(config: dict[str, Any]) -> str:
    enzyme = config["enzyme"]
    enzyme_items = ", ".join(f"{json.dumps(key)}: {json.dumps(value)}" for key, value in enzyme.items())
    return (
        "{\n"
        f'  "database": {json.dumps(config["database"])},\n'
        f'  "mzml_paths": {json.dumps(config["mzml_paths"])},\n'
        f'  "precursor_tol": {json.dumps(config["precursor_tol"])},\n'
        f'  "fragment_tol": {json.dumps(config["fragment_tol"])},\n'
        f'  "enzyme": {{{enzyme_items}}},\n'
        f'  "output_paths": {json.dumps(config["output_paths"])}\n'
        "}\n"
    )


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


class FragPipeWorkflowNode(CommandNode):
    """Run a FragPipe headless proteomics workflow."""

    NODE_ID = "fragpipe"
    DISPLAY_NAME = "FragPipe Workflow"
    CATEGORY = "proteomics"
    DESCRIPTION = "Run FragPipe headless workflows for end-to-end proteomics processing."
    SEARCH_ALIASES = ["fragpipe", "headless", "msfragger", "proteomics", "proteomics workflow", "peptide identification"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("results_dir",)
    REQUIRED_EXECUTABLES = ["fragpipe"]
    REQUIRED_CONDA_PACKAGES = ["fragpipe"]
    DOCUMENTATION_URL = "https://fragpipe.nesvilab.org/"
    VERSION = "24.0"
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not str(inputs.get("workflow_file", "")).strip():
            return "FragPipe Workflow requires a workflow file."
        if not str(inputs.get("manifest_file", "")).strip():
            return "FragPipe Workflow requires a manifest file."
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        return [
            "fragpipe",
            "--headless",
            "--workflow",
            str(inputs.get("workflow_file", "")),
            "--manifest",
            str(inputs.get("manifest_file", "")),
            "--workdir",
            str(out_dir),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "workflow_file": ("FILE", {"description": "FragPipe workflow file (.workflow)"}),
                "manifest_file": ("FILE", {"description": "FragPipe manifest file (.fp-manifest)"}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class SageSearchNode(CommandNode):
    """Run Sage for fast peptide-spectrum matching."""

    NODE_ID = "sage_search"
    DISPLAY_NAME = "Sage Search"
    CATEGORY = "proteomics"
    DESCRIPTION = "Fast Rust-based peptide-spectrum matching for large-scale proteomics searches."
    SEARCH_ALIASES = ["sage", "sage-proteomics", "proteomics", "peptide identification", "database search"]
    RETURN_TYPES = ("TSV", "JSON", "FILE", "FILE")
    RETURN_NAMES = ("results_tsv", "results_json", "config_json", "pin_file")
    REQUIRED_EXECUTABLES = ["sage"]
    REQUIRED_CONDA_PACKAGES = ["sage-proteomics"]
    DOCUMENTATION_URL = "https://github.com/lazear/sage"
    VERSION = "0.14.7"

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not _file_list(inputs.get("spectra_files")):
            return "Sage Search requires at least one spectra file."
        if int(inputs.get("threads", 4) or 0) <= 0:
            return "Sage Search threads must be greater than zero."
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        spectra_files = _file_list(inputs.get("spectra_files"))
        config_file = out_dir / "sage_config.json"
        fasta_db = str(inputs.get("fasta_db", ""))

        config = {
            "database": {"fasta": fasta_db},
            "mzml_paths": spectra_files,
            "precursor_tol": {"ppm": inputs.get("precursor_tol_ppm", 20)},
            "fragment_tol": {"da": inputs.get("fragment_tol_da", 0.05)},
            "enzyme": _sage_enzyme_config(inputs),
            "output_paths": {"results": "results.sage.tsv"},
        }
        config_file.write_text(_sage_config_text(config), encoding="utf-8")

        cmd = [
            "sage",
            str(config_file),
            "-f",
            fasta_db,
            "-o",
            str(out_dir),
        ]
        # NOTE: sage has NO `--threads` option (it auto-parallelises across all
        # cores); passing it makes sage abort with "unexpected argument
        # '--threads'" (exit 2). Concurrency is controlled by the config's
        # `batch_size` / the runtime, not a CLI flag.
        if inputs.get("write_pin", True):
            cmd.append("--write-pin")
        if inputs.get("parquet"):
            cmd.append("--parquet")
        cmd.extend(spectra_files)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        outputs = [
            node_out / "results.sage.tsv",
            node_out / "results.json",
            node_out / "sage_config.json",
        ]
        if inputs.get("write_pin", True):
            outputs.append(node_out / "results.pin")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "spectra_files": ("FILE", {"description": "MS/MS spectra files (.mzML, .mzXML, .mgf)"}),
                "fasta_db": ("FASTA", {"description": "Target-decoy protein database FASTA"}),
            },
            "optional": {
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
                "precursor_tol_ppm": ("FLOAT", {"default": 20.0, "min": 0.0}),
                "fragment_tol_da": ("FLOAT", {"default": 0.05, "min": 0.0}),
                "enzyme": ("STRING", {"default": "trypsin", "options": ["trypsin"]}),
                "missed_cleavages": ("INT", {"default": 2, "min": 0, "max": 10}),
                "min_peptide_length": ("INT", {"default": 7, "min": 4, "max": 60}),
                "max_peptide_length": ("INT", {"default": 40, "min": 4, "max": 100}),
                "write_pin": ("BOOLEAN", {"default": True, "description": "Ask Sage to write Percolator PIN output"}),
                "parquet": ("BOOLEAN", {"default": False, "description": "Ask Sage to write parquet output when supported"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CometNode(CommandNode):
    """Run Comet for peptide identification from MS/MS spectra."""

    NODE_ID = "comet"
    DISPLAY_NAME = "Comet"
    CATEGORY = "proteomics"
    DESCRIPTION = "MS/MS database search for peptide identification from mzML, mzXML, or raw spectra."
    SEARCH_ALIASES = ["comet", "ms/ms", "proteomics", "peptide identification", "database search", "pepxml"]
    RETURN_TYPES = ("FILE", "TSV", "FILE")
    RETURN_NAMES = ("pep_xml", "psm_tsv", "params")
    REQUIRED_EXECUTABLES = ["comet"]
    REQUIRED_CONDA_PACKAGES = ["comet-ms"]
    DOCUMENTATION_URL = "https://uwpr.github.io/Comet/"
    VERSION = "2024.01"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        params_file = out_dir / "comet.params"
        output_stem = out_dir / "comet"
        spectra_files = inputs.get("spectra_files", [])
        if isinstance(spectra_files, str):
            spectra_files = [spectra_files] if spectra_files else []

        params_lines = [
            f"database_name = {inputs.get('fasta_db', '')}",
            f"num_threads = {inputs.get('threads', 4)}",
            f"peptide_mass_tolerance_lower = {inputs.get('peptide_mass_tolerance_lower', -20)}",
            f"peptide_mass_tolerance_upper = {inputs.get('peptide_mass_tolerance_upper', 20)}",
            f"peptide_mass_units = {inputs.get('peptide_mass_units', 2)}",
            f"fragment_bin_tol = {inputs.get('fragment_bin_tol', 0.02)}",
            f"fragment_bin_offset = {inputs.get('fragment_bin_offset', 0.0)}",
            f"search_enzyme_number = {inputs.get('search_enzyme_number', 1)}",
            f"allowed_missed_cleavage = {inputs.get('allowed_missed_cleavage', 2)}",
            f"decoy_search = {inputs.get('decoy_search', 1)}",
            "output_pepxmlfile = 1",
            f"output_txtfile = {1 if inputs.get('output_txtfile', True) else 0}",
        ]
        params_file.write_text("\n".join(params_lines) + "\n")

        return [
            "comet",
            "-P",
            str(params_file),
            "-D",
            str(inputs.get("fasta_db", "")),
            "-N",
            str(output_stem),
        ] + [str(spectra_file) for spectra_file in spectra_files]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [
            node_out / "comet.pep.xml",
            node_out / "comet.txt",
            node_out / "comet.params",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "spectra_files": ("FILE", {"description": "MS/MS spectra files (.mzML, .mzXML, .mgf, .raw)"}),
                "fasta_db": ("FASTA", {"description": "Target-decoy protein database FASTA"}),
            },
            "optional": {
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
                "peptide_mass_tolerance_lower": ("FLOAT", {"default": -20.0}),
                "peptide_mass_tolerance_upper": ("FLOAT", {"default": 20.0}),
                "peptide_mass_units": ("INT", {"default": 2, "min": 0, "max": 2, "label": "0=amu, 1=mmu, 2=ppm"}),
                "fragment_bin_tol": ("FLOAT", {"default": 0.02, "min": 0.0}),
                "fragment_bin_offset": ("FLOAT", {"default": 0.0}),
                "search_enzyme_number": ("INT", {"default": 1, "min": 0, "max": 10}),
                "allowed_missed_cleavage": ("INT", {"default": 2, "min": 0, "max": 10}),
                "decoy_search": ("INT", {"default": 1, "min": 0, "max": 2}),
                "output_txtfile": ("BOOLEAN", {"default": True}),
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


class OpenMSFeatureFinderNode(CommandNode):
    """Detect peptide features from centroided LC-MS data with OpenMS."""
    NODE_ID = "openms_feature_finder"
    DISPLAY_NAME = "OpenMS FeatureFinder"
    CATEGORY = "proteomics"
    DESCRIPTION = "Detect peptide features (RT, m/z, intensity) from centroided LC-MS using OpenMS."
    SEARCH_ALIASES = ["openms", "feature finder", "lc-ms", "peptide feature", "topp"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("feature_xml",)
    REQUIRED_EXECUTABLES = ["FeatureFinderCentroided"]
    REQUIRED_CONDA_PACKAGES = ["openms"]
    DOCUMENTATION_URL = "https://openms.readthedocs.io/"
    VERSION = "3.2.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "FeatureFinderCentroided",
            "-in",
            str(inputs.get("mzml_file", "")),
            "-out",
            f"{out_dir}/feature_xml.featureXML",
        ]
        if inputs.get("ini_file"):
            cmd.extend(["-ini", str(inputs["ini_file"])])
        else:
            cmd.extend([
                "-algorithm:min_peak_width",
                str(inputs.get("min_peak_width", 0.2)),
                "-algorithm:signal_to_noise",
                str(inputs.get("signal_to_noise", 1.0)),
            ])
        if inputs.get("threads"):
            cmd.extend(["-threads", str(inputs["threads"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "feature_xml.featureXML"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mzml_file": ("FILE", {"description": "Centroided mzML file"}),
            },
            "optional": {
                "ini_file": ("FILE", {"description": "OpenMS INI params", "advanced": True}),
                "min_peak_width": ("FLOAT", {"default": 0.2, "min": 0.05}),
                "signal_to_noise": ("FLOAT", {"default": 1.0, "min": 0.1}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class OpenMSFeatureNode(OpenMSFeatureFinderNode):
    """Compatibility wrapper for the original OpenMS feature roadmap node ID."""

    NODE_ID = "openms_feature"
    DISPLAY_NAME = "OpenMS Feature"
    DESCRIPTION = "Detect peptide features from centroided LC-MS data with OpenMS FeatureFinder."
    SEARCH_ALIASES = ["openms feature", "openms", "feature finder", "lc-ms", "peptide feature", "topp"]


class DIANNNode(CommandNode):
    """Analyze DIA proteomics data with DIA-NN."""

    NODE_ID = "dia_nn"
    DISPLAY_NAME = "DIA-NN"
    CATEGORY = "proteomics"
    DESCRIPTION = "Analyze DIA (Data Independent Acquisition) proteomics data with DIA-NN."
    SEARCH_ALIASES = ["dia", "dia-nn", "diann", "data independent acquisition", "proteomics", "quantification"]
    RETURN_TYPES = ("TSV", "JSON")
    RETURN_NAMES = ("report", "stats")
    REQUIRED_EXECUTABLES = ["diann"]
    REQUIRED_CONDA_PACKAGES = ["diann"]
    DOCUMENTATION_URL = "https://github.com/vdemichev/DiaNN"
    VERSION = "1.8"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        report = out_dir / "report.tsv"
        stats = out_dir / "stats.json"
        raw_files = inputs.get("raw_files", [])
        if isinstance(raw_files, str):
            raw_files = [raw_files] if raw_files else []

        cmd = [
            "diann",
            "--lib",
            str(inputs.get("library", "")),
            "--fasta",
            str(inputs.get("fasta", "")),
            "--out",
            str(report),
            "--threads",
            str(inputs.get("threads", 4)),
            "--qvalue",
            str(inputs.get("qvalue", 0.01)),
        ]
        if inputs.get("mass_accuracy"):
            cmd.extend(["--mass-acc", str(inputs["mass_accuracy"])])
        if inputs.get("use_predictor"):
            cmd.append("--predictor")
        for raw_file in raw_files:
            cmd.extend(["--f", str(raw_file)])
        cmd.extend([
            "&&",
            "python",
            "-c",
            "import csv, json, sys; rows=list(csv.DictReader(open(sys.argv[1]), delimiter='\\t')); "
            "json.dump({'rows': len(rows), 'columns': list(rows[0]) if rows else []}, open(sys.argv[2], 'w'))",
            str(report),
            str(stats),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "report.tsv", node_out / "stats.json"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "raw_files": ("FILE", {"description": "DIA raw files (.mzML, .raw, .dia)"}),
                "library": ("FILE", {"description": "Spectral library TSV"}),
                "fasta": ("FASTA", {"description": "Protein FASTA database"}),
            },
            "optional": {
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
                "qvalue": ("FLOAT", {"default": 0.01, "min": 0.001, "max": 0.1, "step": 0.001}),
                "mass_accuracy": ("FLOAT", {"default": 0, "min": 0}),
                "use_predictor": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class DIANNAliasNode(DIANNNode):
    """Compatibility alias for the DIA-NN node ID without punctuation."""

    NODE_ID = "diann"
    DISPLAY_NAME = "DIA-NN"
    DESCRIPTION = "Analyze DIA proteomics data with DIA-NN."
    SEARCH_ALIASES = ["diann", "dia-nn", "dia", "data independent acquisition", "proteomics", "quantification"]
