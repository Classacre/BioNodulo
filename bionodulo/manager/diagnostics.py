"""Workflow diagnostics and environment status for BioNodulo.

Provides tools to check if required executables are available and
report on the overall tool installation status.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
from typing import Any

from bionodulo.nodes.base import BaseNode

logger = logging.getLogger(__name__)

# Known bioinformatics executables with their package names
KNOWN_EXECUTABLES: dict[str, str] = {
    "bwa": "bwa",
    "bowtie2": "bowtie2",
    "bowtie2-build": "bowtie2",
    "hisat2": "hisat2",
    "hisat2-build": "hisat2",
    "STAR": "star",
    "minimap2": "minimap2",
    "salmon": "salmon",
    "kallisto": "kallisto",
    "samtools": "samtools",
    "bcftools": "bcftools",
    "gatk": "gatk4",
    "freebayes": "freebayes",
    "vcftools": "vcftools",
    "fastqc": "fastqc",
    "multiqc": "multiqc",
    "qualimap": "qualimap",
    "fastp": "fastp",
    "trimmomatic": "trimmomatic",
    "cutadapt": "cutadapt",
    "spades.py": "spades",
    "megahit": "megahit",
    "canu": "canu",
    "flye": "flye",
    "unicycler": "unicycler",
    "quast": "quast",
    "prokka": "prokka",
    "bakta": "bakta",
    "emapper.py": "eggnog-mapper",
    "mafft": "mafft",
    "clustalo": "clustal-omega",
    "iqtree": "iqtree",
    "iqtree2": "iqtree",
    "FastTree": "fasttree",
    "raxmlHPC": "raxml",
    "featureCounts": "subread",
    "stringtie": "stringtie",
    "kraken2": "kraken2",
    "kraken2-build": "kraken2",
    "bracken": "bracken",
    "metaphlan": "metaphlan",
    "humann": "humann",
    "run_MaxBin.pl": "maxbin2",
    "checkm": "checkm-genome",
    "macs2": "macs2",
    "bedtools": "bedtools",
    "bamCoverage": "deeptools",
    "cellranger": "cellranger",
    "run_MaxBin.pl": "maxbin2",
}


def diagnose_workflow(nodes: list[type[BaseNode]]) -> dict[str, Any]:
    """Check if all required executables for a workflow are available.

    Args:
        nodes: List of node classes to check.

    Returns:
        Dictionary with diagnostic results including missing tools.
    """
    required: set[str] = set()
    for node_cls in nodes:
        if getattr(node_cls, "REQUIRES_EXTERNAL_TOOLS", False):
            required.update(getattr(node_cls, "REQUIRED_EXECUTABLES", []))

    results: dict[str, dict[str, Any]] = {}
    all_available = True
    for exe in sorted(required):
        available = shutil.which(exe) is not None
        results[exe] = {
            "available": available,
            "path": shutil.which(exe),
            "conda_package": KNOWN_EXECUTABLES.get(exe, "unknown"),
        }
        if not available:
            all_available = False

    return {
        "all_available": all_available,
        "required": list(sorted(required)),
        "results": results,
        "missing": [exe for exe, info in results.items() if not info["available"]],
        "install_command": _generate_install_command(results),
    }


def environment_status() -> dict[str, Any]:
    """Check which bioinformatics tools are installed on the system.

    Returns:
        Dictionary with overall status and per-tool availability.
    """
    results: dict[str, dict[str, Any]] = {}
    available_count = 0
    for exe, package in sorted(KNOWN_EXECUTABLES.items()):
        path = shutil.which(exe)
        available = path is not None
        if available:
            available_count += 1
        results[exe] = {
            "available": available,
            "path": path,
            "conda_package": package,
        }

    return {
        "total_known": len(KNOWN_EXECUTABLES),
        "available": available_count,
        "missing": len(KNOWN_EXECUTABLES) - available_count,
        "tools": results,
        "summary": {
            "all_available": available_count == len(KNOWN_EXECUTABLES),
            "percent_ready": round(available_count / len(KNOWN_EXECUTABLES) * 100, 1),
        },
    }


def _generate_install_command(results: dict[str, dict[str, Any]]) -> str:
    """Generate a micromamba install command for missing packages.

    Args:
        results: Diagnostic results dictionary.

    Returns:
        Shell command string to install missing packages.
    """
    missing_packages: set[str] = set()
    for exe, info in results.items():
        if not info["available"] and info["conda_package"] != "unknown":
            missing_packages.add(info["conda_package"])

    if not missing_packages:
        return "# All required tools are already installed"

    return (
        f"micromamba install -c bioconda -c conda-forge "
        f"{' '.join(sorted(missing_packages))}"
    )
