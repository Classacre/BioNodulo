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
    "Rscript": "r-base",
}


def diagnose_workflow(nodes: list[type[BaseNode]]) -> dict[str, Any]:
    """Check if all required executables and R packages for a workflow are available.

    Args:
        nodes: List of node classes to check.

    Returns:
        Dictionary with diagnostic results including missing tools and R packages.
    """
    required: set[str] = set()
    required_r: set[str] = set()
    for node_cls in nodes:
        if getattr(node_cls, "REQUIRES_EXTERNAL_TOOLS", False):
            required.update(getattr(node_cls, "REQUIRED_EXECUTABLES", []))
        required_r.update(getattr(node_cls, "REQUIRED_R_PACKAGES", []))

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

    # Check R packages
    r_results: dict[str, dict[str, Any]] = {}
    r_available = True
    if required_r:
        try:
            import subprocess
            r_script = "cat(paste(sapply(c(" + ",".join(f"'{p}'" for p in sorted(required_r)) + "), function(p) paste(p, requireNamespace(p, quietly=TRUE), sep=':')), collapse='\\n'))"
            result = subprocess.run(
                ["Rscript", "-e", r_script],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if ":" in line:
                        pkg_name, available_str = line.strip().rsplit(":", 1)
                        available = available_str.strip().lower() == "true"
                        r_results[pkg_name] = {"available": available}
                        if not available:
                            r_available = False
            else:
                r_available = False
                for pkg in sorted(required_r):
                    r_results[pkg] = {"available": False, "error": "Rscript not available"}
        except Exception as exc:
            r_available = False
            for pkg in sorted(required_r):
                r_results[pkg] = {"available": False, "error": str(exc)}

    return {
        "all_available": all_available and r_available,
        "required": list(sorted(required)),
        "results": results,
        "missing": [exe for exe, info in results.items() if not info["available"]],
        "install_command": _generate_install_command(results),
        "required_r_packages": list(sorted(required_r)),
        "r_packages": r_results,
        "missing_r_packages": [pkg for pkg, info in r_results.items() if not info["available"]],
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

    # Check common bioinformatics R packages
    r_packages_check = [
        "ggplot2", "dplyr", "tidyr", "readr", "pheatmap",
        "DESeq2", "edgeR", "limma", "Biostrings", "GenomicRanges",
        "ape", "vegan", "ComplexHeatmap",
    ]
    r_results: dict[str, dict[str, Any]] = {}
    r_available_count = 0
    try:
        import subprocess
        r_script = "cat(paste(sapply(c(" + ",".join(f"'{p}'" for p in r_packages_check) + "), function(p) paste(p, requireNamespace(p, quietly=TRUE), sep=':')), collapse='\\n'))"
        result = subprocess.run(
            ["Rscript", "-e", r_script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if ":" in line:
                    pkg_name, available_str = line.strip().rsplit(":", 1)
                    available = available_str.strip().lower() == "true"
                    if available:
                        r_available_count += 1
                    r_results[pkg_name] = {"available": available}
        else:
            for pkg in r_packages_check:
                r_results[pkg] = {"available": False, "error": "Rscript failed"}
    except Exception as exc:
        for pkg in r_packages_check:
            r_results[pkg] = {"available": False, "error": str(exc)}

    total_available = available_count + r_available_count
    total_known = len(KNOWN_EXECUTABLES) + len(r_packages_check)

    return {
        "total_known": total_known,
        "available": total_available,
        "missing": total_known - total_available,
        "tools": results,
        "r_packages": r_results,
        "summary": {
            "all_available": total_available == total_known,
            "percent_ready": round(total_available / total_known * 100, 1) if total_known else 100,
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
