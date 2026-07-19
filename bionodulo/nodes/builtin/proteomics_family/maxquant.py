"""MaxQuant 2.0.3.0 execution from a version-matched mqpar template."""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .adapter import ProteomicsCommandNode, path_list, path_value, require_file, stage_file, validate_int


def _required_xml_child(root: ET.Element, name: str) -> ET.Element:
    child = root.find(name)
    if child is None:
        raise ValueError(f"MaxQuant mqpar template is missing <{name}>")
    return child


def _sample_name(path: Path) -> str:
    name = path.name
    for suffix in (".thermo.raw", ".mzXML", ".mzML", ".raw"):
        if name.lower().endswith(suffix.lower()):
            return name[: -len(suffix)]
    return path.stem


class MaxQuantNode(ProteomicsCommandNode):
    """Run a complete, version-matched MaxQuant mqpar configuration."""

    NODE_ID = "maxquant"
    DISPLAY_NAME = "MaxQuant"
    DESCRIPTION = "Run MaxQuant 2.0.3.0 from a version-matched mqpar.xml template."
    SEARCH_ALIASES = ["BioNodulo builtin", "MaxQuant", "proteomics", "LFQ", "protein quantification"]
    RETURN_TYPES = ("DIRECTORY", "TSV", "FILE")
    RETURN_NAMES = ("results_dir", "protein_groups", "mqpar")
    REQUIRED_EXECUTABLES = ["maxquant"]
    REQUIRED_CONDA_PACKAGES = ["maxquant"]
    REQUIRED_PATH_INPUTS = ("fasta_db", "mqpar_template")
    REQUIRED_PATH_LIST_INPUTS = ("raw_files",)
    VERSION = "2.0.3.0"
    GIT_URL = "https://github.com/galaxyproteomics/tools-galaxyp.git"
    GIT_COMMIT = "c0fc669c7b8eb762ae6d2ad8753b941951e139c0"
    DOCUMENTATION_URL = (
        "https://github.com/galaxyproteomics/tools-galaxyp/tree/"
        "c0fc669c7b8eb762ae6d2ad8753b941951e139c0/tools/maxquant"
    )
    UPSTREAM_SOURCE = "tools/maxquant/maxquant_mqpar.xml, modify_mqpar.py, and mqparam.py"
    PACKAGE_AUTHORITY = (
        "Bioconda maxquant 2.0.3.0 recipe at "
        "0f45cb6931cc383705d156ad4e7e8c7e5015b505"
    )
    CITATION_DOIS = ["10.1038/s41592-018-0018-y"]
    CITATION_URLS = ["https://doi.org/10.1038/s41592-018-0018-y"]
    CITATION_TEXT = "MaxQuant computational platform for mass spectrometry-based shotgun proteomics."
    RUN_IN_NODE_OUTPUT_DIR = True
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "raw_files": (
                    "FILE_LIST",
                    {"multiple": True, "description": "One or more RAW, mzML, or mzXML files"},
                ),
                "fasta_db": ("FASTA", {"description": "Protein FASTA database"}),
                "mqpar_template": (
                    "FILE",
                    {"description": "mqpar.xml created by MaxQuant 2.0.3.0"},
                ),
            },
            "optional": {
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        raw_files = path_list(inputs.get("raw_files"))
        if len({Path(path).name for path in raw_files}) != len(raw_files):
            return "Input 'raw_files' must have unique basenames"
        return validate_int(inputs.get("threads", 4), "threads", minimum=1, maximum=128)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        combined = node_dir / "combined"
        return [combined, combined / "txt" / "proteinGroups.txt", node_dir / "mqpar.xml"]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        cls.require_valid_inputs(inputs)
        node_dir = outputs[0].parent
        staged_dir = node_dir / "inputs"
        raw_files = [stage_file(path, "raw_files", staged_dir) for path in path_list(inputs["raw_files"])]
        fasta = stage_file(inputs["fasta_db"], "fasta_db", staged_dir)
        template = require_file(inputs["mqpar_template"], "mqpar_template")

        try:
            tree = ET.parse(template)
        except ET.ParseError as exc:
            raise ValueError(f"MaxQuant mqpar template is not valid XML: {exc}") from exc
        root = tree.getroot()
        if root.tag != "MaxQuantParams":
            raise ValueError("MaxQuant mqpar template root must be <MaxQuantParams>")
        version = _required_xml_child(root, "maxQuantVersion").text or ""
        if version.strip() != cls.VERSION:
            raise ValueError(f"MaxQuant mqpar version must be {cls.VERSION}, not {version.strip() or 'missing'}")

        parameter_groups = _required_xml_child(root, "parameterGroups")
        if not list(parameter_groups):
            raise ValueError("MaxQuant mqpar template must contain one parameterGroup")
        first_group = copy.deepcopy(list(parameter_groups)[0])
        parameter_groups.clear()
        parameter_groups.append(first_group)

        values: dict[str, tuple[str, list[str]]] = {
            "filePaths": ("string", [str(path.absolute()) for path in raw_files]),
            "experiments": ("string", [_sample_name(path) for path in raw_files]),
            "fractions": ("short", ["32767"] * len(raw_files)),
            "ptms": ("boolean", ["False"] * len(raw_files)),
            "paramGroupIndices": ("int", ["0"] * len(raw_files)),
            "referenceChannel": ("string", [""] * len(raw_files)),
        }
        for name, (child_tag, entries) in values.items():
            parent = _required_xml_child(root, name)
            parent.clear()
            for entry in entries:
                ET.SubElement(parent, child_tag).text = entry

        fasta_files = _required_xml_child(root, "fastaFiles")
        if not list(fasta_files):
            raise ValueError("MaxQuant mqpar template must contain one FastaFileInfo")
        fasta_info = copy.deepcopy(list(fasta_files)[0])
        fasta_path = fasta_info.find("fastaFilePath")
        if fasta_path is None:
            raise ValueError("MaxQuant mqpar FastaFileInfo is missing fastaFilePath")
        fasta_path.text = str(fasta.absolute())
        fasta_files.clear()
        fasta_files.append(fasta_info)
        _required_xml_child(root, "numThreads").text = str(inputs.get("threads", 4))

        ET.indent(tree, space="\t")
        tree.write(outputs[2], encoding="utf-8", xml_declaration=True)
        inputs["_maxquant_mqpar"] = str(outputs[2])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        mqpar = str(inputs.get("_maxquant_mqpar", Path(path_value(inputs.get("output", "."))) / "mqpar.xml"))
        return ["maxquant", mqpar]
