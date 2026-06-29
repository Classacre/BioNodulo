"""Variant calling and manipulation nodes for BioNodulo.

Provides nodes for variant calling with bcftools, GATK, FreeBayes,
and filtering with bcftools and VCFtools.
"""
from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class BcftoolsMpileupNode(CommandNode):
    """Call variants with bcftools mpileup + call."""
    NODE_ID = "bcftools_mpileup"
    DISPLAY_NAME = "bcftools mpileup + call"
    REQUIRED_CONDA_PACKAGES = ['bcftools']
    CATEGORY = "variant"
    DESCRIPTION = "Generate VCF variant calls from a BAM alignment using bcftools"
    SEARCH_ALIASES = ["bcftools", "mpileup", "variant call", "snp calling"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/bcftools.html"
    VERSION = "1.22"
    SHELL = False

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", inputs.get("output_dir", ".")))
        parts = [
            "bcftools", "mpileup",
            "-f", shlex.quote(str(inputs.get("reference", ""))),
        ]
        if inputs.get("max_depth"):
            parts.extend(["-d", shlex.quote(str(inputs["max_depth"]))])
        if inputs.get("min_bq"):
            parts.extend(["-Q", shlex.quote(str(inputs["min_bq"]))])
        parts.extend(["-Ou", shlex.quote(str(inputs.get("bam", "")))])
        parts.extend([
            "|", "bcftools", "call",
            "-mv", "-Oz",
            "-o", shlex.quote(f"{output}/vcf.vcf.gz"),
        ])
        if inputs.get("ploidy"):
            parts.extend(["--ploidy", shlex.quote(str(inputs["ploidy"]))])
        # Wrap in bash -c so the entire pipeline runs inside the pixi
        # environment when env_prefix is prepended by the executor.
        return ["bash", "-c", " ".join(parts)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file (sorted and indexed)"}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
            },
            "optional": {
                "max_depth": ("INT", {"default": 250, "min": 1, "label": "Max Depth", "advanced": True}),
                "min_bq": ("INT", {"default": 13, "min": 0, "label": "Min Base Quality", "advanced": True}),
                "ploidy": ("INT", {"default": 2, "min": 1, "max": 8, "display": "slider", "label": "Ploidy", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class Sniffles2Node(CommandNode):
    """Call structural variants from long-read alignments with Sniffles2."""
    NODE_ID = "sniffles2"
    DISPLAY_NAME = "Sniffles2 SV Caller"
    CATEGORY = "variant"
    DESCRIPTION = (
        "Long-read SV caller for PacBio HiFi and ONT. Supports tandem repeat annotation and phased SV output."
    )
    SEARCH_ALIASES = [
        "sniffles2",
        "sniffles",
        "structural variant",
        "long-read sv",
        "nanopore sv",
        "pacbio sv",
        "hifi sv",
    ]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("sv_vcf",)
    REQUIRED_EXECUTABLES = ["sniffles"]
    REQUIRED_CONDA_PACKAGES = ["sniffles"]
    DOCUMENTATION_URL = "https://github.com/fritzsedlazeck/Sniffles"
    VERSION = "2.5.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "sniffles",
            "--input", str(inputs.get("bam", "")),
            "--vcf", f"{inputs.get('output', '.')}/sv_vcf.vcf.gz",
            "--reference", str(inputs.get("reference", "")),
            "--threads", str(inputs.get("threads", 4)),
        ]
        if inputs.get("tandem_repeats"):
            cmd.extend(["--tandem-repeats", str(inputs["tandem_repeats"])])
        if inputs.get("minsvlen"):
            cmd.extend(["--minsvlen", str(inputs["minsvlen"])])
        if inputs.get("minsupport"):
            cmd.extend(["--minsupport", str(inputs["minsupport"])])
        if inputs.get("phase"):
            cmd.append("--phase")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Sorted, indexed BAM from a long-read aligner"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "tandem_repeats": ("BED", {"description": "Tandem repeat annotations", "advanced": True}),
                "minsvlen": ("INT", {"default": 50, "min": 20, "label": "Min SV Length"}),
                "minsupport": ("INT", {"default": 10, "min": 1, "label": "Min Supporting Reads"}),
                "phase": ("BOOLEAN", {"default": False, "description": "Output phased SVs"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class Sniffles2CallNode(Sniffles2Node):
    """Workflow-compatible Sniffles2 structural variant caller alias."""

    NODE_ID = "sniffles2_call"
    DISPLAY_NAME = "Sniffles2 Call"
    DESCRIPTION = "Call structural variants with Sniffles2 for multi-caller SV workflows."
    SEARCH_ALIASES = [
        "sniffles2_call",
        "sniffles2",
        "sniffles",
        "structural variant",
        "sv caller",
        "long-read sv",
        "split-read sv",
    ]


class PBSVNode(CommandNode):
    """Call PacBio HiFi structural variants with pbsv."""
    NODE_ID = "pbsv"
    DISPLAY_NAME = "PBSV Caller"
    CATEGORY = "variant"
    DESCRIPTION = "PacBio structural variant caller for HiFi read alignments."
    SEARCH_ALIASES = [
        "pbsv",
        "pacbio",
        "hifi",
        "hifi sv",
        "structural variant",
        "sv caller",
        "discover",
        "call",
    ]
    RETURN_TYPES = ("VCF", "FILE")
    RETURN_NAMES = ("sv_vcf", "svsig")
    REQUIRED_EXECUTABLES = ["pbsv"]
    REQUIRED_CONDA_PACKAGES = ["pbsv"]
    DOCUMENTATION_URL = "https://github.com/PacificBiosciences/pbsv"
    VERSION = "2.10.0"
    SHELL = True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        sample_name = cls._sample_name(inputs)
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [
            node_out / f"{sample_name}.pbsv.vcf",
            node_out / f"{sample_name}.svsig.gz",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not cls._sample_name(inputs):
            return "Input 'sample_name' must not be empty"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get("output", "."))
        sample_name = cls._sample_name(inputs)
        svsig = f"{out_dir}/{sample_name}.svsig.gz"
        vcf = f"{out_dir}/{sample_name}.pbsv.vcf"
        cmd = [
            "pbsv",
            "discover",
            str(inputs.get("bam", "")),
            svsig,
        ]
        if inputs.get("tandem_repeats"):
            cmd.extend(["--tandem-repeats", str(inputs["tandem_repeats"])])
        cmd.extend([
            "&&",
            "pbsv",
            "call",
        ])
        if inputs.get("ccs"):
            cmd.append("--ccs")
        cmd.extend([
            "-j",
            str(inputs.get("threads", 4)),
            str(inputs.get("reference", "")),
            svsig,
            vcf,
        ])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "PacBio HiFi BAM aligned to the reference"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "sample_name": ("STRING", {"default": "sample"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "tandem_repeats": ("BED", {"description": "Tandem repeat annotations", "advanced": True}),
                "ccs": ("BOOLEAN", {"default": True, "description": "Optimize calling for PacBio CCS/HiFi reads"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def _sample_name(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("sample_name", "sample")).strip()


class SVStatsNode(CommandNode):
    """Compute summary statistics and size plots from structural-variant VCFs."""
    NODE_ID = "sv_stats"
    DISPLAY_NAME = "SV Stats"
    CATEGORY = "variant"
    DESCRIPTION = "Compute structural variant statistics, SVTYPE counts, size distribution, and quality summaries."
    SEARCH_ALIASES = [
        "sv stats",
        "structural variant statistics",
        "size distribution",
        "svtype counts",
        "vcf qc",
    ]
    RETURN_TYPES = ("JSON", "IMAGE")
    RETURN_NAMES = ("stats_json", "stats_plot")
    REQUIRED_EXECUTABLES = ["python"]
    REQUIRED_CONDA_PACKAGES = ["pysam", "matplotlib"]
    DOCUMENTATION_URL = "https://pysam.readthedocs.io/en/latest/api.html#pysam.VariantFile"
    VERSION = "1.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", "."))
        plot_format = str(inputs.get("plot_format", "png") or "png").lower()
        if plot_format not in {"png", "svg"}:
            plot_format = "png"
        script = r"""
import json
import sys
from collections import Counter

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pysam

sv_vcf, reference, stats_json, stats_plot, min_size, max_size = sys.argv[1:7]
min_size = int(min_size)
max_size = int(max_size)

counts = Counter()
sizes = []
qualities = []
total_records = 0
passing_records = 0

with pysam.VariantFile(sv_vcf) as vcf:
    for record in vcf:
        total_records += 1
        svtype = record.info.get('SVTYPE', 'UNKNOWN')
        if isinstance(svtype, tuple):
            svtype = svtype[0] if svtype else 'UNKNOWN'
        svtype = str(svtype)

        svlen = record.info.get('SVLEN')
        if isinstance(svlen, tuple):
            svlen = svlen[0] if svlen else None
        if svlen is None and record.stop is not None:
            svlen = record.stop - record.pos
        try:
            size = abs(int(svlen)) if svlen is not None else 0
        except (TypeError, ValueError):
            size = 0

        if size < min_size or (max_size > 0 and size > max_size):
            continue

        counts[svtype] += 1
        sizes.append(size)
        if record.qual is not None:
            qualities.append(float(record.qual))
        if not record.filter.keys() or set(record.filter.keys()) == {'PASS'}:
            passing_records += 1

summary = {
    'reference': reference,
    'total_records': total_records,
    'records_in_size_range': sum(counts.values()),
    'passing_records': passing_records,
    'svtype_counts': dict(sorted(counts.items())),
    'size': {
        'min': min(sizes) if sizes else 0,
        'max': max(sizes) if sizes else 0,
        'mean': (sum(sizes) / len(sizes)) if sizes else 0,
    },
    'quality': {
        'min': min(qualities) if qualities else None,
        'max': max(qualities) if qualities else None,
        'mean': (sum(qualities) / len(qualities)) if qualities else None,
    },
}

with open(stats_json, 'w', encoding='utf-8') as handle:
    json.dump(summary, handle, indent=2, sort_keys=True)
    handle.write('\n')

fig, axes = plt.subplots(1, 2, figsize=(10, 4))
labels = list(summary['svtype_counts'].keys())
values = list(summary['svtype_counts'].values())
axes[0].bar(labels or ['none'], values or [0], color='#2f6f73')
axes[0].set_title('SVTYPE counts')
axes[0].set_ylabel('Records')
axes[0].tick_params(axis='x', rotation=35)
axes[1].hist(sizes or [0], bins=min(30, max(1, len(sizes))), color='#a84d3d')
axes[1].set_title('SV size distribution')
axes[1].set_xlabel('Absolute SVLEN')
axes[1].set_ylabel('Records')
fig.tight_layout()
fig.savefig(stats_plot)
plt.close(fig)
""".strip()
        return [
            "python",
            "-c",
            script,
            str(inputs.get("sv_vcf", "")),
            str(inputs.get("reference", "")),
            f"{output}/stats_json.json",
            f"{output}/stats_plot.{plot_format}",
            str(inputs.get("min_size", 50)),
            str(inputs.get("max_size", 0)),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_dir = Path(output_dir)
        node_out = output_dir / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        plot_format = str(inputs.get("plot_format", "png") or "png").lower()
        if plot_format not in {"png", "svg"}:
            plot_format = "png"
        return [node_out / "stats_json.json", node_out / f"stats_plot.{plot_format}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sv_vcf": ("VCF_GZ", {"description": "Structural variant VCF or VCF.GZ"}),
                "reference": ("FASTA", {"description": "Reference FASTA used for the callset"}),
            },
            "optional": {
                "min_size": ("INT", {"default": 50, "min": 0, "label": "Minimum SV Size"}),
                "max_size": ("INT", {"default": 0, "min": 0, "label": "Maximum SV Size", "description": "0 disables the upper size filter", "advanced": True}),
                "plot_format": ("STRING", {"default": "png", "options": ["png", "svg"], "label": "Plot Format", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class VCFComparisonNode(CommandNode):
    """Compare two VCF callsets with RTG vcfeval."""
    NODE_ID = "vcf_comparison"
    DISPLAY_NAME = "VCF Comparison"
    CATEGORY = "variant"
    DESCRIPTION = "Compare variant callsets and report precision, recall, F1, and overlap metrics."
    SEARCH_ALIASES = [
        "vcf comparison",
        "benchmark",
        "precision recall",
        "rtg vcfeval",
        "variant evaluation",
    ]
    RETURN_TYPES = ("JSON", "IMAGE")
    RETURN_NAMES = ("comparison", "venn_plot")
    REQUIRED_EXECUTABLES = ["rtg"]
    REQUIRED_CONDA_PACKAGES = ["rtg-tools", "matplotlib"]
    DOCUMENTATION_URL = "https://realtimegenomics.github.io/rtg-tools/rtg_command_reference.html#vcfeval"
    VERSION = "3.12.1"
    SHELL = False

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", "."))
        plot_format = str(inputs.get("plot_format", "png") or "png").lower()
        if plot_format not in {"png", "svg"}:
            plot_format = "png"
        sample = shlex.quote(str(inputs.get("sample", "")).strip())
        squash_ploidy = bool(inputs.get("squash_ploidy", False))
        reference = shlex.quote(str(inputs.get("reference", "")))
        vcf_a = shlex.quote(str(inputs.get("vcf_a", "")))
        vcf_b = shlex.quote(str(inputs.get("vcf_b", "")))
        out_dir = shlex.quote(output)
        comparison_json = shlex.quote(f"{output}/comparison.json")
        venn_plot = shlex.quote(f"{output}/venn_plot.{plot_format}")

        sample_arg = f" --sample {sample}" if sample else ""
        squash_arg = " --squash-ploidy" if squash_ploidy else ""
        script = f"""
set -euo pipefail
mkdir -p {out_dir}
if [ ! -d {out_dir}/reference.sdf ]; then
  rtg format -o {out_dir}/reference.sdf {reference}
fi
rtg vcfeval --baseline {vcf_a} --calls {vcf_b} --template {out_dir}/reference.sdf --output {out_dir}/vcfeval{sample_arg}{squash_arg}
python - "$@" <<'PY'
import csv
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

summary_path, comparison_json, venn_plot = sys.argv[1:4]
metrics = {{}}
try:
    with open(summary_path, encoding='utf-8') as handle:
        for row in csv.reader(handle, delimiter='\\t'):
            if len(row) >= 2:
                key = row[0].strip().lower().replace(' ', '_')
                value = row[1].strip()
                if key:
                    metrics[key] = value
except FileNotFoundError:
    pass

true_positive = int(float(metrics.get('true_positives_baseline', metrics.get('tp_baseline', 0)) or 0))
false_positive = int(float(metrics.get('false_positives', metrics.get('fp', 0)) or 0))
false_negative = int(float(metrics.get('false_negatives', metrics.get('fn', 0)) or 0))
precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0
recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0
f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0

summary = {{
    'metrics': metrics,
    'precision': precision,
    'recall': recall,
    'f1': f1,
    'true_positive': true_positive,
    'false_positive': false_positive,
    'false_negative': false_negative,
}}
with open(comparison_json, 'w', encoding='utf-8') as handle:
    json.dump(summary, handle, indent=2, sort_keys=True)
    handle.write('\\n')

fig, ax = plt.subplots(figsize=(5, 4))
labels = ['TP', 'FP', 'FN']
values = [true_positive, false_positive, false_negative]
ax.bar(labels, values, color=['#2f6f73', '#a84d3d', '#6d5f9a'])
ax.set_title('VCF comparison')
ax.set_ylabel('Variants')
fig.tight_layout()
fig.savefig(venn_plot)
plt.close(fig)
PY
{out_dir}/vcfeval/summary.txt {comparison_json} {venn_plot}
""".strip()
        return ["bash", "-c", script]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_dir = Path(output_dir)
        node_out = output_dir / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        plot_format = str(inputs.get("plot_format", "png") or "png").lower()
        if plot_format not in {"png", "svg"}:
            plot_format = "png"
        return [node_out / "comparison.json", node_out / f"venn_plot.{plot_format}"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf_a": ("VCF_GZ", {"description": "Baseline/truth VCF.GZ"}),
                "vcf_b": ("VCF_GZ", {"description": "Calls VCF.GZ to evaluate"}),
                "reference": ("FASTA", {"description": "Reference FASTA used by both callsets"}),
            },
            "optional": {
                "sample": ("STRING", {"default": "", "description": "Optional sample name to compare", "advanced": True}),
                "squash_ploidy": ("BOOLEAN", {"default": False, "description": "Ignore genotype ploidy differences", "advanced": True}),
                "plot_format": ("STRING", {"default": "png", "options": ["png", "svg"], "label": "Plot Format", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class Strelka2Node(CommandNode):
    """Call germline or somatic small variants with Strelka2."""
    NODE_ID = "strelka2"
    DISPLAY_NAME = "Strelka2"
    CATEGORY = "variant"
    DESCRIPTION = "Call germline or somatic small variants with Strelka2."
    SEARCH_ALIASES = ["strelka2", "strelka", "small variant", "somatic", "germline", "snp", "indel"]
    RETURN_TYPES = ("VCF_GZ", "VCF_GZ")
    RETURN_NAMES = ("snv_vcf", "indel_vcf")
    REQUIRED_EXECUTABLES = ["configureStrelkaGermlineWorkflow.py"]
    REQUIRED_CONDA_PACKAGES = ["strelka"]
    DOCUMENTATION_URL = "https://github.com/Illumina/strelka"
    VERSION = "2.9.10"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get("output", "."))
        run_dir = f"{output}/strelka_run"
        mode = str(inputs.get("mode", "germline") or "germline").lower()
        if mode not in {"germline", "somatic"}:
            mode = "germline"
        threads = int(inputs.get("threads", 4) or 4)
        reference = shlex.quote(str(inputs.get("reference", "")))
        run_dir_q = shlex.quote(run_dir)
        output_q = shlex.quote(output)

        if mode == "somatic":
            configure = [
                "configureStrelkaSomaticWorkflow.py",
                "--tumorBam", shlex.quote(str(inputs.get("bam", ""))),
                "--normalBam", shlex.quote(str(inputs.get("normal_bam", ""))),
                "--referenceFasta", reference,
                "--runDir", run_dir_q,
            ]
            snv_source = f"{run_dir}/results/variants/somatic.snvs.vcf.gz"
            indel_source = f"{run_dir}/results/variants/somatic.indels.vcf.gz"
        else:
            configure = [
                "configureStrelkaGermlineWorkflow.py",
                "--bam", shlex.quote(str(inputs.get("bam", ""))),
                "--referenceFasta", reference,
                "--runDir", run_dir_q,
            ]
            snv_source = f"{run_dir}/results/variants/variants.vcf.gz"
            indel_source = f"{run_dir}/results/variants/indels.vcf.gz"

        if inputs.get("exome"):
            configure.append("--exome")
        if inputs.get("call_regions"):
            configure.extend(["--callRegions", shlex.quote(str(inputs["call_regions"]))])

        script = " ".join(configure)
        script += f"\n{shlex.quote(run_dir)}/runWorkflow.py -m local -j {threads}"
        script += f"\ncp {shlex.quote(snv_source)} {output_q}/snv_vcf.vcf.gz"
        script += f"\ncp {shlex.quote(indel_source)} {output_q}/indel_vcf.vcf.gz"
        return ["bash", "-c", script]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Tumor or germline BAM (sorted and indexed)"}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
            },
            "optional": {
                "normal_bam": ("BAM", {"description": "Matched normal BAM for somatic mode", "advanced": True}),
                "mode": ("STRING", {"default": "germline", "options": ["germline", "somatic"]}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
                "exome": ("BOOLEAN", {"default": False, "description": "Use exome-style calling parameters", "advanced": True}),
                "call_regions": ("BED", {"description": "Optional bgzip/tabix-indexed BED call regions", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class GRIDSSNode(CommandNode):
    """Call structural variants with GRIDSS assembly-based breakend detection."""

    NODE_ID = "gridss"
    DISPLAY_NAME = "GRIDSS SV Caller"
    CATEGORY = "variant"
    DESCRIPTION = "Call structural variants with GRIDSS assembly-based breakend detection."
    SEARCH_ALIASES = [
        "gridss",
        "breakend",
        "bnd",
        "assembly sv",
        "structural variant",
        "complex rearrangement",
    ]
    RETURN_TYPES = ("VCF_GZ", "BAM")
    RETURN_NAMES = ("sv_vcf", "assembly_bam")
    REQUIRED_EXECUTABLES = ["gridss"]
    REQUIRED_CONDA_PACKAGES = ["gridss"]
    DOCUMENTATION_URL = "https://github.com/PapenfussLab/gridss"
    VERSION = "2.13.2"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "sv_vcf.vcf.gz", node_out / "assembly_bam.bam"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        bams = cls._bam_inputs(inputs.get("bams"))
        if not bams:
            return "At least one BAM is required"
        if not str(inputs.get("reference", "")).strip():
            return "Input 'reference' must not be empty"
        if int(inputs.get("threads", 0) or 0) < 1:
            return "Input 'threads' must be at least 1"
        labels = cls._label_inputs(inputs.get("labels"))
        if labels and len(labels) != len(bams):
            return "Number of GRIDSS labels must match number of BAM inputs"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        output = str(inputs.get("output", "."))
        cmd = [
            "gridss",
            "--reference",
            str(inputs.get("reference", "")),
            "--output",
            f"{output}/sv_vcf.vcf.gz",
            "--assembly",
            f"{output}/assembly_bam.bam",
            "--threads",
            str(inputs.get("threads", 4)),
            "--workingdir",
            f"{output}/gridss_working",
        ]
        if inputs.get("blacklist"):
            cmd.extend(["--blacklist", str(inputs["blacklist"])])
        if cls._label_inputs(inputs.get("labels")):
            cmd.extend(["--labels", ",".join(cls._label_inputs(inputs.get("labels")))])
        if inputs.get("steps"):
            cmd.extend(["--steps", str(inputs["steps"])])
        if inputs.get("gridss_jar"):
            cmd.extend(["--jar", str(inputs["gridss_jar"])])
        if inputs.get("jvm_heap"):
            cmd.extend(["--jvmheap", str(inputs["jvm_heap"])])
        cmd.extend(cls._bam_inputs(inputs.get("bams")))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bams": ("BAM", {"description": "One or more sorted, indexed BAM files"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "optional": {
                "blacklist": ("BED", {"description": "Regions to exclude from calling", "advanced": True}),
                "labels": ("STRING", {"default": "", "description": "Comma-separated sample labels", "advanced": True}),
                "steps": ("STRING", {"default": "all", "options": ["all", "setupreference", "preprocess", "assemble", "call"]}),
                "gridss_jar": ("FILE", {"description": "Optional GRIDSS jar override", "advanced": True}),
                "jvm_heap": ("STRING", {"default": "", "description": "Optional JVM heap setting such as 31g", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def _bam_inputs(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [part.strip() for part in str(value).replace("\n", ",").split(",") if part.strip()]

    @classmethod
    def _label_inputs(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [part.strip() for part in str(value).replace("\n", ",").split(",") if part.strip()]


class MELTMobileElementsNode(CommandNode):
    """Call mobile element insertions with MELT Single mode."""

    NODE_ID = "melt_mobile_elements"
    DISPLAY_NAME = "MELT Mobile Elements"
    CATEGORY = "variant"
    DESCRIPTION = "Call mobile element insertions from BAM alignments with MELT Single mode."
    SEARCH_ALIASES = [
        "melt",
        "mobile element",
        "mei",
        "mobile element insertion",
        "transposable element",
        "retrotransposon",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("melt_output",)
    REQUIRED_EXECUTABLES = ["java"]
    REQUIRED_CONDA_PACKAGES = []
    DOCUMENTATION_URL = "https://melt.igs.umaryland.edu/"
    VERSION = "2"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        melt_output = node_out / cls._output_prefix(inputs)
        melt_output.mkdir(parents=True, exist_ok=True)
        return [melt_output]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for name in ("bam", "reference", "melt_jar", "mei_list", "genome_annotation", "output_prefix"):
            if not str(inputs.get(name, "")).strip():
                return f"Input '{name}' must not be empty"
        if int(inputs.get("coverage", 0) or 0) < 1:
            return "Input 'coverage' must be at least 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        out_dir = Path(str(inputs.get("output", "."))) / cls._output_prefix(inputs)
        return [
            "java",
            "-jar",
            str(inputs.get("melt_jar", "")),
            "Single",
            "-bamfile",
            str(inputs.get("bam", "")),
            "-h",
            str(inputs.get("reference", "")),
            "-n",
            str(inputs.get("genome_annotation", "")),
            "-t",
            str(inputs.get("mei_list", "")),
            "-c",
            str(inputs.get("coverage", 30)),
            "-w",
            str(out_dir),
            "-exome",
            "true" if inputs.get("exome", False) else "false",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file (sorted and indexed)"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "melt_jar": ("FILE", {"description": "Path to MELT.jar"}),
                "mei_list": ("FILE", {"description": "MELT MEI list"}),
                "genome_annotation": ("BED", {"description": "MELT genome annotation file"}),
                "output_prefix": ("STRING", {"default": "sample", "description": "MELT sample/output prefix"}),
                "coverage": ("INT", {"default": 30, "min": 1, "max": 500, "display": "slider"}),
            },
            "optional": {
                "exome": ("BOOLEAN", {"default": False, "description": "Use MELT exome mode"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def _output_prefix(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output_prefix", "sample")).strip()


class SURVIVORMergeNode(CommandNode):
    """Merge structural variant callsets into a consensus VCF with SURVIVOR."""
    NODE_ID = "survivor_merge"
    DISPLAY_NAME = "SURVIVOR Merge"
    CATEGORY = "variant"
    DESCRIPTION = "Merge SV calls from multiple VCFs into a consensus callset for multi-caller pipelines."
    SEARCH_ALIASES = ["survivor", "merge sv", "consensus sv", "multi-caller", "structural variant merge"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("merged_sv",)
    REQUIRED_EXECUTABLES = ["SURVIVOR"]
    REQUIRED_CONDA_PACKAGES = ["survivor"]
    DOCUMENTATION_URL = "https://github.com/fritzsedlazeck/SURVIVOR"
    VERSION = "1.0.7"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        vcf_files = inputs.get("vcf_files", [])
        if isinstance(vcf_files, str):
            vcf_files = [vcf_files]

        sample_list = out_dir / "sample_files.txt"
        sample_list.write_text("".join(f"{vcf}\n" for vcf in vcf_files), encoding="utf-8")

        return [
            "SURVIVOR",
            "merge",
            str(sample_list),
            str(inputs.get("max_distance", 1000)),
            str(inputs.get("min_callers", 1)),
            str(inputs.get("use_type", 1)),
            str(inputs.get("use_strand", 1)),
            str(inputs.get("min_sv_size", 30)),
            str(out_dir / "merged_sv.vcf"),
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf_files": ("VCF_GZ", {"description": "List of VCF files to merge"}),
                "max_distance": ("INT", {"default": 1000, "min": 0, "label": "Max Breakpoint Distance (bp)"}),
                "min_callers": ("INT", {"default": 1, "min": 1, "label": "Min Supporting Callers"}),
            },
            "optional": {
                "use_type": ("INT", {"default": 1, "min": 0, "max": 1}),
                "use_strand": ("INT", {"default": 1, "min": 0, "max": 1}),
                "min_sv_size": ("INT", {"default": 30, "min": 10}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CuteSVNode(CommandNode):
    """Call long-read structural variants with cuteSV."""
    NODE_ID = "cutesv"
    DISPLAY_NAME = "cuteSV Caller"
    CATEGORY = "variant"
    DESCRIPTION = "Efficient long-read SV caller for ONT and PacBio HiFi."
    SEARCH_ALIASES = [
        "cutesv",
        "cuteSV",
        "long-read sv",
        "nanopore sv",
        "pacbio sv",
        "structural variant",
    ]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("sv_vcf",)
    REQUIRED_EXECUTABLES = ["cuteSV"]
    REQUIRED_CONDA_PACKAGES = ["cute-sv"]
    DOCUMENTATION_URL = "https://github.com/tjiangHIT/cuteSV"
    VERSION = "2.1.1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get("output", "."))
        cmd = [
            "cuteSV",
            "--threads",
            str(inputs.get("threads", 4)),
            "--sample",
            str(inputs.get("sample_name", "sample")),
        ]
        if inputs.get("max_cluster_bias_ins"):
            cmd.extend(["--max_cluster_bias_INS", str(inputs["max_cluster_bias_ins"])])
        if inputs.get("min_size"):
            cmd.extend(["--min_size", str(inputs["min_size"])])
        if inputs.get("max_size"):
            cmd.extend(["--max_size", str(inputs["max_size"])])
        # cuteSV takes the reference as a positional argument, not a flag:
        #   cuteSV [options] <sorted.bam> <reference.fa> <output.vcf> <work_dir>
        cmd.extend([
            str(inputs.get("bam", "")),
            str(inputs.get("reference", "")),
            f"{out_dir}/sv_vcf.vcf",
            out_dir,
        ])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input sorted, indexed BAM from a long-read aligner"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "sample_name": ("STRING", {"default": "sample"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "max_cluster_bias_ins": ("INT", {"default": 1000, "min": 50, "label": "Max Cluster Bias INS"}),
                "min_size": ("INT", {"default": 30, "min": 10, "label": "Min SV Size"}),
                "max_size": ("INT", {"default": 100000, "min": 1000, "label": "Max SV Size"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class SVIMNode(CommandNode):
    """Call long-read structural variants with SVIM."""
    NODE_ID = "svim"
    DISPLAY_NAME = "SVIM SV Caller"
    CATEGORY = "variant"
    DESCRIPTION = "Long-read SV caller optimized for Oxford Nanopore data."
    SEARCH_ALIASES = ["svim", "long-read sv", "nanopore sv", "structural variant"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("sv_vcf",)
    REQUIRED_EXECUTABLES = ["svim"]
    REQUIRED_CONDA_PACKAGES = ["svim"]
    DOCUMENTATION_URL = "https://github.com/eldariont/svim"
    VERSION = "2.0.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get("output", "."))
        cmd = [
            "svim",
            "alignment",
            "--sample",
            str(inputs.get("sample_name", "sample")),
        ]
        if inputs.get("min_sv_size"):
            cmd.extend(["--min_sv_size", str(inputs["min_sv_size"])])
        if inputs.get("max_sv_size"):
            cmd.extend(["--max_sv_size", str(inputs["max_sv_size"])])
        if inputs.get("sequence_alleles"):
            cmd.append("--sequence_alleles")
        if inputs.get("symbolic_alleles"):
            cmd.append("--symbolic_alleles")
        cmd.extend([
            "--interspersed_duplications_as_insertions",
            "--tandem_duplications_as_insertions",
            out_dir,
            str(inputs.get("bam", "")),
            str(inputs.get("reference", "")),
        ])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input sorted, indexed BAM from a long-read aligner"}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
                "sample_name": ("STRING", {"default": "sample"}),
            },
            "optional": {
                "min_sv_size": ("INT", {"default": 50, "min": 20}),
                "max_sv_size": ("INT", {"default": 50000, "min": 1000}),
                "sequence_alleles": ("BOOLEAN", {"default": True}),
                "symbolic_alleles": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class SmooveNode(CommandNode):
    """Call and genotype structural variants with smoove."""
    NODE_ID = "smoove"
    DISPLAY_NAME = "Smoove SV Caller"
    CATEGORY = "variant"
    DESCRIPTION = "Automated SV calling with smoove (LUMPY wrapper), genotyping, and quality filtering."
    SEARCH_ALIASES = ["smoove", "lumpy", "structural variant", "sv caller", "genotyped sv"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("genotyped_sv",)
    REQUIRED_EXECUTABLES = ["smoove"]
    REQUIRED_CONDA_PACKAGES = ["smoove", "lumpy-sv", "svtyper"]
    DOCUMENTATION_URL = "https://github.com/brentp/smoove"
    VERSION = "0.2.8"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "smoove",
            "call",
            "--name",
            str(inputs.get("sample_name", "sample")),
            "--fasta",
            str(inputs.get("reference", "")),
            "-p",
            str(inputs.get("threads", 4)),
            "--outdir",
            str(inputs.get("output", ".")),
        ]
        if inputs.get("genotype"):
            cmd.append("--genotype")
        if inputs.get("exclude"):
            cmd.extend(["--exclude", str(inputs["exclude"])])
        cmd.append(str(inputs.get("bam", "")))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM (sorted and indexed)"}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
                "sample_name": ("STRING", {"default": "sample"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "exclude": ("BED", {"description": "Exclude regions BED", "advanced": True}),
                "genotype": ("BOOLEAN", {"default": True, "description": "Run svtyper genotyping"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class DellyNode(CommandNode):
    """Call structural variants with DELLY."""
    NODE_ID = "delly"
    DISPLAY_NAME = "DELLY SV Caller"
    CATEGORY = "variant"
    DESCRIPTION = "Paired-end + split-read SV caller. Supports germline, somatic, and long-read modes."
    SEARCH_ALIASES = ["delly", "structural variant", "sv caller", "somatic sv", "long-read sv"]
    RETURN_TYPES = ("BCF",)
    RETURN_NAMES = ("sv_calls",)
    REQUIRED_EXECUTABLES = ["delly"]
    REQUIRED_CONDA_PACKAGES = ["delly"]
    DOCUMENTATION_URL = "https://github.com/dellytools/delly"
    VERSION = "1.2.6"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        mode = inputs.get("mode", "call")
        cmd = [
            "delly",
            "lr" if mode == "lr" else "call",
            "-g",
            str(inputs.get("reference", "")),
            "-o",
            f"{inputs.get('output', '.')}/sv_calls.bcf",
        ]
        if inputs.get("exclude_regions"):
            cmd.extend(["-x", str(inputs["exclude_regions"])])
        if inputs.get("map_qual") is not None:
            cmd.extend(["-q", str(inputs["map_qual"])])
        cmd.append(str(inputs.get("bam", "")))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM (sorted and indexed)"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "mode": ("STRING", {"default": "call", "options": ["call", "lr"]}),
            },
            "optional": {
                "exclude_regions": ("BED", {"description": "Exclude regions BED", "advanced": True}),
                "map_qual": ("INT", {"default": 1, "min": 0, "label": "Min MapQ", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class DellyCallNode(DellyNode):
    """Workflow-compatible DELLY caller that emits an indexed VCF."""

    NODE_ID = "delly_call"
    DISPLAY_NAME = "DELLY Call"
    DESCRIPTION = "Call structural variants with DELLY and convert BCF output to indexed VCF."
    SEARCH_ALIASES = ["delly_call", "delly", "structural variant", "sv caller", "somatic sv", "long-read sv"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("sv_vcf",)
    REQUIRED_EXECUTABLES = ["delly", "bcftools", "tabix"]
    REQUIRED_CONDA_PACKAGES = ["delly", "bcftools", "htslib"]
    SHELL = True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "sv_vcf.vcf.gz"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        bcf = out_dir / "sv_calls.bcf"
        sv_vcf = out_dir / "sv_vcf.vcf.gz"
        mode = inputs.get("mode", "call")
        cmd = [
            "delly",
            "lr" if mode == "lr" else "call",
            "-g",
            str(inputs.get("reference", "")),
            "-o",
            str(bcf),
        ]
        if inputs.get("exclude_regions"):
            cmd.extend(["-x", str(inputs["exclude_regions"])])
        if inputs.get("map_qual") is not None:
            cmd.extend(["-q", str(inputs["map_qual"])])
        cmd.extend([
            str(inputs.get("bam", "")),
            "&&",
            "bcftools",
            "view",
            "-Oz",
            "-o",
            str(sv_vcf),
            str(bcf),
            "&&",
            "tabix",
            "-f",
            "-p",
            "vcf",
            str(sv_vcf),
        ])
        return cmd


class MantaNode(CommandNode):
    """Call paired-end structural variants with Manta."""
    NODE_ID = "manta"
    DISPLAY_NAME = "Manta SV Caller"
    CATEGORY = "variant"
    DESCRIPTION = (
        "Call structural variants (DEL, DUP, INS, INV, BND) from paired-end sequencing. "
        "Supports germline and somatic modes."
    )
    SEARCH_ALIASES = [
        "manta",
        "structural variant",
        "sv caller",
        "illumina sv",
        "germline sv",
        "somatic sv",
    ]
    RETURN_TYPES = ("VCF_GZ", "VCF_GZ")
    RETURN_NAMES = ("candidate_sv", "diploid_sv")
    REQUIRED_EXECUTABLES = ["configManta.py", "runWorkflow.py"]
    REQUIRED_CONDA_PACKAGES = ["manta"]
    DOCUMENTATION_URL = "https://github.com/Illumina/manta"
    VERSION = "1.6.0"
    SHELL = True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        variants_dir = node_out / "results" / "variants"
        variants_dir.mkdir(parents=True, exist_ok=True)
        return [
            variants_dir / "candidateSV.vcf.gz",
            variants_dir / "diploidSV.vcf.gz",
        ]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = str(inputs.get("output", "."))
        cmd = [
            "configManta.py",
            "--bam",
            str(inputs.get("bam", "")),
            "--referenceFasta",
            str(inputs.get("reference", "")),
            "--runDir",
            out_dir,
        ]
        if inputs.get("normal_bam"):
            cmd.extend(["--normalBam", str(inputs["normal_bam"])])
        if inputs.get("exome"):
            cmd.append("--exome")
        if inputs.get("rna"):
            cmd.append("--rna")
        cmd.extend([
            "&&",
            f"{out_dir}/runWorkflow.py",
            "-m",
            "local",
            "-j",
            str(inputs.get("threads", 4)),
        ])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM (sorted and indexed)"}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "normal_bam": ("BAM", {"description": "Normal BAM for somatic mode", "advanced": True}),
                "exome": ("BOOLEAN", {"default": False, "description": "Exome/targeted mode", "advanced": True}),
                "rna": ("BOOLEAN", {"default": False, "description": "RNA-seq mode", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MantaCallNode(MantaNode):
    """Workflow-compatible Manta structural variant caller alias."""

    NODE_ID = "manta_call"
    DISPLAY_NAME = "Manta Call"
    DESCRIPTION = "Call paired-end structural variants with Manta for multi-caller SV workflows."
    SEARCH_ALIASES = ["manta_call", "manta", "structural variant", "sv caller", "illumina sv", "germline sv"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("sv_vcf",)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        variants_dir = node_out / "results" / "variants"
        variants_dir.mkdir(parents=True, exist_ok=True)
        vcf_name = "somaticSV.vcf.gz" if inputs.get("normal_bam") else "diploidSV.vcf.gz"
        return [variants_dir / vcf_name]


class CNVkitBatchNode(CommandNode):
    """Run the CNVkit batch pipeline for copy-number analysis."""
    NODE_ID = "cnvkit_batch"
    DISPLAY_NAME = "CNVkit Batch Pipeline"
    CATEGORY = "variant"
    DESCRIPTION = (
        "Complete CNVkit pipeline: coverage -> reference -> fix -> segment -> call. "
        "For targeted/WGS tumor/normal CNV detection."
    )
    SEARCH_ALIASES = ["cnvkit", "cnv", "copy number", "batch", "cbs"]
    RETURN_TYPES = ("DIRECTORY", "DIRECTORY")
    RETURN_NAMES = ("cnr_files", "cns_files")
    REQUIRED_EXECUTABLES = ["cnvkit.py"]
    REQUIRED_CONDA_PACKAGES = ["cnvkit"]
    DOCUMENTATION_URL = "https://cnvkit.readthedocs.io/"
    VERSION = "0.9.12"
    SHELL = True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [
            node_out / "cnr_files",
            node_out / "cns_files",
        ]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "cnvkit.py",
            "batch",
            str(inputs.get("tumor_bams", "")),
            "--fasta",
            str(inputs.get("reference", "")),
            "--output-reference",
            f"{out_dir}/reference.cnn",
            "--output-dir",
            str(out_dir),
            "--processes",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("normal_bams"):
            cmd.extend(["--normal", str(inputs["normal_bams"])])
        if inputs.get("targets"):
            cmd.extend(["--targets", str(inputs["targets"])])
        if inputs.get("method"):
            cmd.extend(["--method", str(inputs["method"])])
        if inputs.get("diagram"):
            cmd.append("--diagram")
        if inputs.get("scatter"):
            cmd.append("--scatter")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "tumor_bams": ("BAM", {"description": "Tumor BAM file(s)"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "normal_bams": ("BAM", {"description": "Normal BAM for matched analysis"}),
                "targets": ("BED", {"description": "Target regions BED (exome capture baits)"}),
                "method": ("STRING", {"default": "hybrid", "options": ["hybrid", "amplicon", "wgs"]}),
                "diagram": ("BOOLEAN", {"default": False, "description": "Generate diagram plots"}),
                "scatter": ("BOOLEAN", {"default": False, "description": "Generate scatter plots"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CNVkitCallNode(CommandNode):
    """Convert CNVkit segment ratios to copy-number calls."""
    NODE_ID = "cnvkit_call"
    DISPLAY_NAME = "CNVkit Call"
    CATEGORY = "variant"
    DESCRIPTION = (
        "Convert segmented CNV ratios to absolute copy number calls. "
        "Supports purity, ploidy, and BAF integration."
    )
    SEARCH_ALIASES = ["cnvkit", "cnv call", "copy number", "segment", "call"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("cnv_calls",)
    REQUIRED_EXECUTABLES = ["cnvkit.py"]
    REQUIRED_CONDA_PACKAGES = ["cnvkit"]
    DOCUMENTATION_URL = "https://cnvkit.readthedocs.io/"
    VERSION = "0.9.12"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "cnvkit.py",
            "call",
            str(inputs.get("cns_file", "")),
            "-o",
            f"{inputs.get('output', '.')}/cnv_calls.vcf",
        ]
        if inputs.get("vcf"):
            cmd.extend(["--vcf", str(inputs["vcf"])])
        if inputs.get("sample_sex"):
            cmd.extend(["--sample-sex", str(inputs["sample_sex"])])
        if inputs.get("ploidy"):
            cmd.extend(["--ploidy", str(inputs["ploidy"])])
        if inputs.get("purity"):
            cmd.extend(["--purity", str(inputs["purity"])])
        if inputs.get("method"):
            cmd.extend(["--method", str(inputs["method"])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "cns_file": ("FILE", {"description": "CNVkit .cns segment file"}),
            },
            "optional": {
                "vcf": ("VCF_GZ", {"description": "SNV VCF for BAF integration"}),
                "sample_sex": ("STRING", {"default": "", "options": ["", "male", "female"]}),
                "ploidy": ("INT", {"default": 2, "min": 1, "max": 8}),
                "purity": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05, "label": "Tumor Purity"},
                ),
                "method": ("STRING", {"default": "threshold", "options": ["threshold", "clonal", "none"]}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CNVkitPlotNode(CommandNode):
    """Generate CNVkit scatter and heatmap PDF plots."""
    NODE_ID = "cnvkit_plot"
    DISPLAY_NAME = "CNVkit Plot"
    CATEGORY = "variant"
    DESCRIPTION = "Generate scatter plots and heatmaps from CNVkit copy number data."
    SEARCH_ALIASES = ["cnvkit", "cnv plot", "copy number", "scatter", "heatmap", "diagram"]
    RETURN_TYPES = ("PDF_REPORT", "PDF_REPORT")
    RETURN_NAMES = ("scatter_plot", "heatmap_plot")
    REQUIRED_EXECUTABLES = ["cnvkit.py"]
    REQUIRED_CONDA_PACKAGES = ["cnvkit"]
    DOCUMENTATION_URL = "https://cnvkit.readthedocs.io/"
    VERSION = "0.9.12"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cnr_file = str(inputs.get("cnr_file", ""))
        cns_file = str(inputs.get("cns_file", ""))
        scatter = [
            "cnvkit.py",
            "scatter",
            cnr_file,
            "-s",
            cns_file,
            "-o",
            f"{out_dir}/scatter_plot.pdf",
        ]
        if inputs.get("chromosome"):
            scatter.extend(["-c", str(inputs["chromosome"])])
        if inputs.get("gene"):
            scatter.extend(["-g", str(inputs["gene"])])

        heatmap = [
            "cnvkit.py",
            "heatmap",
            cns_file,
            "-o",
            f"{out_dir}/heatmap_plot.pdf",
        ]
        if inputs.get("chromosome"):
            heatmap.extend(["-c", str(inputs["chromosome"])])
        return scatter + ["&&"] + heatmap

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "cnr_file": ("FILE", {"description": "CNVkit .cnr ratio file"}),
                "cns_file": ("FILE", {"description": "CNVkit .cns segment file"}),
            },
            "optional": {
                "chromosome": ("STRING", {"default": "", "description": "Chromosome to plot"}),
                "gene": ("STRING", {"default": "", "description": "Gene to highlight"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CNVnatorNode(CommandNode):
    """Call copy-number variants with CNVnator read-depth analysis."""
    NODE_ID = "cnvnator"
    DISPLAY_NAME = "CNVnator"
    CATEGORY = "variant"
    DESCRIPTION = (
        "Read-depth based CNV caller using mean-shift partitioning. "
        "Multi-step: tree -> hist -> stat -> partition -> call."
    )
    SEARCH_ALIASES = ["cnvnator", "cnv", "read depth", "mean-shift", "copy number"]
    RETURN_TYPES = ("FILE", "FILE")
    RETURN_NAMES = ("cnv_calls", "root_file")
    REQUIRED_EXECUTABLES = ["cnvnator"]
    REQUIRED_CONDA_PACKAGES = ["cnvnator"]
    DOCUMENTATION_URL = "https://github.com/abyzovlab/CNVnator"
    VERSION = "0.4.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        bin_size = str(inputs.get("bin_size", 100))
        root_file = f"{out_dir}/cnvnator.root"
        bam = str(inputs.get("bam", ""))
        chrom_dir = str(inputs.get("chrom_dir", ""))
        cmd = ["cnvnator", "-root", root_file, "-tree", bam, "&&"]
        cmd.extend(["cnvnator", "-root", root_file, "-his", bin_size])
        if chrom_dir:
            cmd.extend(["-d", chrom_dir])
        cmd.extend(["&&", "cnvnator", "-root", root_file, "-stat", bin_size, "&&"])
        cmd.extend(["cnvnator", "-root", root_file, "-partition", bin_size, "&&"])
        cmd.extend([
            "cnvnator",
            "-root",
            root_file,
            "-call",
            bin_size,
            ">",
            f"{out_dir}/cnv_calls.txt",
        ])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input sorted, indexed BAM"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "chrom_dir": ("DIRECTORY", {"description": "Directory with per-chromosome FASTA files"}),
                "bin_size": ("INT", {"default": 100, "min": 10}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class ControlFREECNode(CommandNode):
    """Call copy-number variants with Control-FREEC."""
    NODE_ID = "control_freec"
    DISPLAY_NAME = "Control-FREEC"
    CATEGORY = "variant"
    DESCRIPTION = (
        "CNV caller with tumor purity and ploidy estimation. "
        "Supports WGS/WES with or without matched normal."
    )
    SEARCH_ALIASES = ["control-freec", "freec", "cnv", "copy number", "allelic imbalance"]
    RETURN_TYPES = ("FILE", "FILE")
    RETURN_NAMES = ("cnv_profile", "baf_profile")
    REQUIRED_EXECUTABLES = ["freec"]
    REQUIRED_CONDA_PACKAGES = ["control-freec"]
    DOCUMENTATION_URL = "http://boevalab.com/FREEC/"
    VERSION = "11.6"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        config_file = out_dir / "freec_config.txt"
        lines = [
            "[general]",
            f"chrLenFile = {inputs.get('chrom_lengths', '')}",
            f"ploidy = {inputs.get('ploidy', 2)}",
            f"window = {inputs.get('window', 50000)}",
            f"chrFiles = {inputs.get('chrom_dir', '')}",
            f"outputDir = {out_dir}",
            f"maxThreads = {inputs.get('threads', 4)}",
            "[sample]",
            f"mateFile = {inputs.get('tumor_bam', '')}",
            "inputFormat = BAM",
            "mateOrientation = FR",
        ]
        if inputs.get("normal_bam"):
            lines.extend([
                "[control]",
                f"mateFile = {inputs['normal_bam']}",
                "inputFormat = BAM",
                "mateOrientation = FR",
            ])
        config_file.write_text("\n".join(lines) + "\n")
        return ["freec", "-conf", str(config_file)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "tumor_bam": ("BAM", {"description": "Tumor BAM (sorted, indexed)"}),
                "chrom_lengths": ("FILE", {"description": "Chromosome length file"}),
                "chrom_dir": ("DIRECTORY", {"description": "Per-chromosome FASTA directory"}),
                "window": ("INT", {"default": 50000, "min": 1000}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "normal_bam": ("BAM", {"description": "Normal BAM for matched analysis"}),
                "ploidy": ("INT", {"default": 2, "min": 1, "max": 8}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class BcftoolsIndexNode(CommandNode):
    """Index a VCF/BCF file."""
    NODE_ID = "bcftools_index"
    DISPLAY_NAME = "bcftools Index"
    CATEGORY = "variant"
    DESCRIPTION = "Index a VCF.gz or BCF file for fast random access"
    SEARCH_ALIASES = ["bcftools", "index", "tbi", "csi"]
    RETURN_TYPES = ("VCF_INDEX",)
    RETURN_NAMES = ("index",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    REQUIRED_CONDA_PACKAGES = ['bcftools']
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/bcftools.html"
    VERSION = "1.20"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bcftools", "index",
            "--tbi" if inputs.get("tbi", True) else "--csi",
            "-f",
            str(inputs.get("vcf", "")),
        ]
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "Compressed VCF or BCF file"}),
            },
            "optional": {
                "tbi": ("BOOLEAN", {"default": True, "description": "Use TBI format (vs CSI)"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    async def run(self, **kwargs):
        import shutil
        from pathlib import Path
        result = await super().run(**kwargs)
        vcf = kwargs.get("vcf", "")
        output_dir = kwargs.get("output_dir") or (kwargs.get("context") and getattr(kwargs["context"], "node_dir", "."))
        if vcf and output_dir:
            vcf_path = Path(vcf)
            tbi = vcf_path.with_suffix(vcf_path.suffix + ".tbi")
            csi = vcf_path.with_suffix(vcf_path.suffix + ".csi")
            index_file = tbi if tbi.exists() else csi
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)
            if index_file.exists() and outputs:
                target = outputs[0]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(index_file), str(target))
        return result


class BcftoolsStatsNode(CommandNode):
    """Generate VCF statistics with bcftools."""
    NODE_ID = "bcftools_stats"
    DISPLAY_NAME = "bcftools Stats"
    CATEGORY = "variant"
    DESCRIPTION = "Generate statistics for a VCF file"
    SEARCH_ALIASES = ["bcftools", "stats", "vcf stats"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("stats",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    REQUIRED_CONDA_PACKAGES = ['bcftools']
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/bcftools.html"
    VERSION = "1.20"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bcftools", "stats",
            str(inputs.get("vcf", "")),
        ]
        if inputs.get("samples"):
            cmd.extend(["-s", str(inputs["samples"])])
        cmd.extend([">", f"{inputs.get('output', '.')}/stats.stats.txt"])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "Input VCF file"}),
            },
            "optional": {
                "samples": ("STRING", {"default": "", "description": "Comma-separated sample list"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class BcftoolsNormNode(CommandNode):
    """Normalize VCF records with bcftools norm."""

    NODE_ID = "bcftools_norm"
    DISPLAY_NAME = "bcftools Norm"
    CATEGORY = "variant"
    DESCRIPTION = "Normalize VCF records: left-align indels, split or join multiallelics, and remove duplicates."
    SEARCH_ALIASES = ["bcftools", "norm", "normalize", "left-align", "split multiallelic", "deduplicate"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("normalized_vcf",)
    REQUIRED_EXECUTABLES = ["bcftools"]
    REQUIRED_CONDA_PACKAGES = ["bcftools"]
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/bcftools.html#norm"
    VERSION = "1.20"

    _MULTIALLELIC_MODES = {"none": "", "split": "-any", "join": "+any"}
    _DEDUPLICATE_MODES = {"none": "", "exact": "exact", "snps": "snps", "indels": "indels", "both": "both", "all": "all"}
    _CHECK_REF_MODES = {"exit": "e", "warn": "w", "exclude": "x", "set": "s"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "Input VCF/BCF file"}),
                "reference": ("FASTA", {"description": "Reference FASTA for left alignment"}),
            },
            "optional": {
                "multiallelics": (
                    "STRING",
                    {"default": "split", "options": ["none", "split", "join"], "description": "Split or join multiallelic records"},
                ),
                "deduplicate": (
                    "STRING",
                    {
                        "default": "none",
                        "options": ["none", "exact", "snps", "indels", "both", "all"],
                        "description": "Remove duplicate records by bcftools norm mode",
                    },
                ),
                "check_ref": (
                    "STRING",
                    {"default": "warn", "options": ["exit", "warn", "exclude", "set"], "description": "Reference allele mismatch handling"},
                ),
                "threads": ("INT", {"default": 0, "min": 0, "max": 64, "display": "slider"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        multiallelics = str(inputs.get("multiallelics", "split") or "split")
        deduplicate = str(inputs.get("deduplicate", "none") or "none")
        check_ref = str(inputs.get("check_ref", "warn") or "warn")
        if multiallelics not in cls._MULTIALLELIC_MODES:
            return f"Unsupported multiallelics mode: {multiallelics}"
        if deduplicate not in cls._DEDUPLICATE_MODES:
            return f"Unsupported deduplicate mode: {deduplicate}"
        if check_ref not in cls._CHECK_REF_MODES:
            return f"Unsupported check_ref mode: {check_ref}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        multiallelics = cls._MULTIALLELIC_MODES[str(inputs.get("multiallelics", "split") or "split")]
        deduplicate = cls._DEDUPLICATE_MODES[str(inputs.get("deduplicate", "none") or "none")]
        check_ref = cls._CHECK_REF_MODES[str(inputs.get("check_ref", "warn") or "warn")]
        cmd = [
            "bcftools",
            "norm",
            "-f",
            str(inputs.get("reference", "")),
        ]
        if multiallelics:
            cmd.extend(["-m", multiallelics])
        if deduplicate:
            cmd.extend(["-d", deduplicate])
        cmd.extend(["--check-ref", check_ref])
        threads = int(inputs.get("threads", 0) or 0)
        if threads > 0:
            cmd.extend(["--threads", str(threads)])
        cmd.extend([
            "-Oz",
            "-o",
            f"{inputs.get('output', '.')}/normalized_vcf.vcf.gz",
            str(inputs.get("vcf", "")),
        ])
        return cmd


class GatkHaplotypeCallerNode(CommandNode):
    """Call variants with GATK HaplotypeCaller."""
    NODE_ID = "gatk_haplotype_caller"
    DISPLAY_NAME = "GATK HaplotypeCaller"
    REQUIRED_CONDA_PACKAGES = ['gatk4']
    CATEGORY = "variant"
    DESCRIPTION = "Call germline SNPs and indels with GATK HaplotypeCaller"
    SEARCH_ALIASES = ["gatk", "haplotypecaller", "variant", "snp", "indel"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["gatk"]
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360037225632-HaplotypeCaller"
    VERSION = "4.6.2.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "gatk", "HaplotypeCaller",
            "-R", str(inputs.get("reference", "")),
            "-I", str(inputs.get("bam", "")),
            "-O", f"{inputs.get('output', '.')}/vcf.vcf.gz",
            "--native-pair-hmm-threads", str(inputs.get("threads", 4)),
        ]
        if inputs.get("emit_ref_confidence"):
            cmd.extend(["-ERC", str(inputs["emit_ref_confidence"])])
        if inputs.get("dbsnp"):
            cmd.extend(["--dbsnp", str(inputs["dbsnp"])])
        if inputs.get("stand_call_conf"):
            cmd.extend(["--standard-min-confidence-threshold-for-calling", str(inputs["stand_call_conf"])])
        if inputs.get("min_base_quality"):
            cmd.extend(["--min-base-quality-score", str(inputs["min_base_quality"])])
        if inputs.get("sample_ploidy"):
            cmd.extend(["-ploidy", str(inputs["sample_ploidy"])])
        if inputs.get("intervals"):
            cmd.extend(["-L", str(inputs["intervals"])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM (sorted, indexed, with read groups)"}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "emit_ref_confidence": ("STRING", {"default": "GVCF", "options": ["NONE", "GVCF", "BP_RESOLUTION"], "label": "Emit Ref Confidence", "advanced": True}),
                "dbsnp": ("VCF_GZ", {"description": "Optional dbSNP VCF for annotation", "advanced": True}),
                "stand_call_conf": ("INT", {"default": 30, "min": 0, "max": 100, "display": "slider", "label": "Call Confidence Threshold", "advanced": True}),
                "min_base_quality": ("INT", {"default": 10, "min": 0, "label": "Min Base Quality", "advanced": True}),
                "sample_ploidy": ("INT", {"default": 2, "min": 1, "max": 8, "display": "slider", "label": "Sample Ploidy", "advanced": True}),
                "intervals": ("STRING", {"default": "", "description": "Intervals to process (e.g., chr1:1-1000)", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class GatkGenotypeGVCFsNode(CommandNode):
    """Joint genotype sample GVCFs with GATK GenotypeGVCFs."""
    NODE_ID = "gatk_genotype_gvcfs"
    DISPLAY_NAME = "GATK GenotypeGVCFs"
    REQUIRED_CONDA_PACKAGES = ["gatk4"]
    CATEGORY = "variant"
    DESCRIPTION = "Joint genotype GVCF files from multiple samples with GATK GenotypeGVCFs"
    SEARCH_ALIASES = ["gatk", "genotypegvcfs", "joint genotyping", "gvcf", "cohort genotyping"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["gatk"]
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360036899732-GenotypeGVCFs"
    VERSION = "4.6.2.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        gvcfs = inputs.get("gvcfs", [])
        if isinstance(gvcfs, str):
            gvcfs = [gvcf.strip() for gvcf in gvcfs.split(",") if gvcf.strip()]

        cmd = [
            "gatk",
            "GenotypeGVCFs",
            "-R",
            str(inputs.get("reference", "")),
        ]
        for gvcf in gvcfs:
            cmd.extend(["-V", str(gvcf)])
        if inputs.get("intervals"):
            cmd.extend(["-L", str(inputs["intervals"])])
        if inputs.get("dbsnp"):
            cmd.extend(["--dbsnp", str(inputs["dbsnp"])])
        if inputs.get("standard_min_confidence") is not None:
            cmd.extend([
                "--standard-min-confidence-threshold-for-calling",
                str(inputs["standard_min_confidence"]),
            ])
        cmd.extend(["-O", f"{inputs.get('output', '.')}/vcf.vcf.gz"])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gvcfs": ("VCF_GZ", {"description": "Input GVCF files. Use comma-separated paths for multiple samples."}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
            },
            "optional": {
                "intervals": ("STRING", {"default": "", "description": "Intervals to genotype (e.g., chr1:1-1000)", "advanced": True}),
                "dbsnp": ("VCF_GZ", {"description": "Optional dbSNP VCF for annotation", "advanced": True}),
                "standard_min_confidence": ("INT", {"default": 30, "min": 0, "max": 100, "display": "slider", "label": "Call Confidence Threshold", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class Mutect2Node(CommandNode):
    """Call somatic variants with GATK Mutect2."""
    NODE_ID = "mutect2"
    DISPLAY_NAME = "Mutect2"
    REQUIRED_CONDA_PACKAGES = ["gatk4"]
    CATEGORY = "variant"
    DESCRIPTION = "Call somatic variants from tumor-only or tumor-normal BAM inputs with GATK Mutect2"
    SEARCH_ALIASES = ["mutect2", "gatk", "somatic variant", "tumor normal", "cancer variant"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["gatk"]
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360037593851-Mutect2"
    VERSION = "4.6.2.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "gatk",
            "Mutect2",
            "-R",
            str(inputs.get("reference", "")),
            "-I",
            str(inputs.get("tumor_bam", "")),
        ]
        if inputs.get("tumor_sample"):
            cmd.extend(["-tumor", str(inputs["tumor_sample"])])
        if inputs.get("normal_bam"):
            cmd.extend(["-I", str(inputs["normal_bam"])])
            if inputs.get("normal_sample"):
                cmd.extend(["-normal", str(inputs["normal_sample"])])
        if inputs.get("germline_resource"):
            cmd.extend(["--germline-resource", str(inputs["germline_resource"])])
        if inputs.get("panel_of_normals"):
            cmd.extend(["--panel-of-normals", str(inputs["panel_of_normals"])])
        if inputs.get("intervals"):
            cmd.extend(["-L", str(inputs["intervals"])])
        cmd.extend(["-O", f"{inputs.get('output', '.')}/vcf.vcf.gz"])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "tumor_bam": ("BAM", {"description": "Tumor BAM (sorted, indexed, with read groups)"}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
            },
            "optional": {
                "normal_bam": ("BAM", {"description": "Matched normal BAM for tumor-normal calling", "advanced": True}),
                "tumor_sample": ("STRING", {"default": "", "description": "Tumor sample name in the BAM read groups", "advanced": True}),
                "normal_sample": ("STRING", {"default": "", "description": "Normal sample name in the BAM read groups", "advanced": True}),
                "germline_resource": ("VCF_GZ", {"description": "Population allele frequency resource", "advanced": True}),
                "panel_of_normals": ("VCF_GZ", {"description": "Panel of normals VCF", "advanced": True}),
                "intervals": ("STRING", {"default": "", "description": "Intervals to process (e.g., chr1:1-1000)", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class PlatypusNode(CommandNode):
    """Call haplotype-based variants with Platypus."""
    NODE_ID = "platypus"
    DISPLAY_NAME = "Platypus"
    CATEGORY = "variant"
    DESCRIPTION = "Call haplotype-based variants across SNPs, indels, and complex small variants with Platypus."
    SEARCH_ALIASES = ["platypus", "haplotype", "small variant", "snp", "indel", "variant caller"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["Platypus.py"]
    REQUIRED_CONDA_PACKAGES = ["platypus-variant"]
    DOCUMENTATION_URL = "https://github.com/andyrimmer/Platypus"
    VERSION = "0.8.1"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        bams = inputs.get("bam", "")
        if isinstance(bams, (list, tuple)):
            bam_arg = ",".join(str(bam) for bam in bams)
        else:
            bam_arg = str(bams)

        cmd = [
            "Platypus.py",
            "callVariants",
            f"--bamFiles={bam_arg}",
            f"--refFile={inputs.get('reference', '')}",
            f"--output={inputs.get('output', '.')}/vcf.vcf.gz",
        ]
        if inputs.get("regions"):
            cmd.append(f"--regions={inputs['regions']}")
        if inputs.get("threads"):
            cmd.append(f"--nCPU={inputs['threads']}")
        if inputs.get("min_reads") is not None:
            cmd.append(f"--minReads={inputs['min_reads']}")
        if inputs.get("assemble") is not None:
            cmd.append(f"--assemble={1 if inputs['assemble'] else 0}")
        if inputs.get("filter_duplicates") is not None:
            cmd.append(f"--filterDuplicates={1 if inputs['filter_duplicates'] else 0}")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file or BAM list (sorted and indexed)"}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
            },
            "optional": {
                "regions": ("BED", {"description": "Optional target regions BED", "advanced": True}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
                "min_reads": ("INT", {"default": 2, "min": 1, "label": "Minimum Reads", "advanced": True}),
                "assemble": ("BOOLEAN", {"default": True, "description": "Enable local assembly", "advanced": True}),
                "filter_duplicates": ("BOOLEAN", {"default": True, "description": "Filter duplicate reads", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class DeepVariantNode(CommandNode):
    """Call small variants with DeepVariant."""
    NODE_ID = "deepvariant"
    DISPLAY_NAME = "DeepVariant"
    CATEGORY = "variant"
    DESCRIPTION = "Call small variants with DeepVariant, Google's deep learning-based variant caller."
    SEARCH_ALIASES = ["deepvariant", "deep learning", "small variant", "snp", "indel", "variant caller"]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["run_deepvariant"]
    REQUIRED_CONDA_PACKAGES = ["deepvariant"]
    DOCUMENTATION_URL = "https://github.com/google/deepvariant"
    VERSION = "1.6.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "run_deepvariant",
            f"--model_type={inputs.get('model_type', 'WGS')}",
            f"--ref={inputs.get('reference', '')}",
            f"--reads={inputs.get('bam', '')}",
            f"--output_vcf={inputs.get('output', '.')}/vcf.vcf.gz",
        ]
        if inputs.get("num_shards"):
            cmd.append(f"--num_shards={inputs['num_shards']}")
        if inputs.get("regions"):
            cmd.append(f"--regions={inputs['regions']}")
        if inputs.get("sample_name"):
            cmd.append(f"--sample_name={inputs['sample_name']}")
        if inputs.get("intermediate_results_dir"):
            cmd.append(f"--intermediate_results_dir={inputs['intermediate_results_dir']}")
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file (sorted and indexed)"}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
            },
            "optional": {
                "model_type": ("STRING", {"default": "WGS", "options": ["WGS", "WES", "PACBIO", "ONT_R104"]}),
                "regions": ("STRING", {"default": "", "description": "Optional region string or BED path", "advanced": True}),
                "num_shards": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
                "sample_name": ("STRING", {"default": "", "description": "Optional sample name override", "advanced": True}),
                "intermediate_results_dir": ("DIRECTORY", {"description": "Optional DeepVariant intermediate directory", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class Clair3Node(CommandNode):
    """Call small variants from long-read alignments with Clair3."""

    NODE_ID = "clair3"
    DISPLAY_NAME = "Clair3"
    CATEGORY = "variant"
    DESCRIPTION = "Call small variants from long-read BAM files with Clair3 deep-learning models."
    SEARCH_ALIASES = [
        "clair3",
        "nanopore",
        "pacbio hifi",
        "deep learning",
        "long-read variant caller",
        "small variant",
        "snp",
        "indel",
    ]
    RETURN_TYPES = ("VCF_GZ",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["run_clair3.sh"]
    REQUIRED_CONDA_PACKAGES = ["clair3"]
    DOCUMENTATION_URL = "https://github.com/HKU-BAL/Clair3"
    VERSION = "2.0.1"

    _PLATFORMS = {"ont", "hifi", "ilmn"}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        platform = str(inputs.get("platform", "ont") or "ont").lower()
        if platform not in cls._PLATFORMS:
            return f"Unsupported Clair3 platform: {platform}"
        if int(inputs.get("threads", 4) or 0) <= 0:
            return "Clair3 threads must be greater than zero."
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        cmd = [
            "run_clair3.sh",
            f"--bam_fn={inputs.get('bam', '')}",
            f"--ref_fn={inputs.get('reference', '')}",
            f"--threads={inputs.get('threads', 4)}",
            f"--platform={str(inputs.get('platform', 'ont') or 'ont').lower()}",
            f"--model_path={inputs.get('model_path', '')}",
            f"--output={inputs.get('output', '.')}",
        ]
        if inputs.get("regions_bed"):
            cmd.append(f"--bed_fn={inputs['regions_bed']}")
        if inputs.get("candidate_vcf"):
            cmd.append(f"--vcf_fn={inputs['candidate_vcf']}")
        if inputs.get("contigs"):
            cmd.append(f"--ctg_name={inputs['contigs']}")
        if inputs.get("sample_name"):
            cmd.append(f"--sample_name={inputs['sample_name']}")
        if inputs.get("qual") is not None:
            cmd.append(f"--qual={inputs['qual']}")
        if inputs.get("chunk_size") is not None:
            cmd.append(f"--chunk_size={inputs['chunk_size']}")
        for key in (
            "include_all_ctgs",
            "pileup_only",
            "enable_phasing",
            "haploid_precise",
            "haploid_sensitive",
            "enable_dwell_time",
        ):
            if inputs.get(key):
                cmd.append(f"--{key}")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "merge_output.vcf.gz"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file (sorted and indexed)"}),
                "reference": ("FASTA", {"description": "Reference FASTA (indexed)"}),
                "model_path": ("DIRECTORY", {"description": "Clair3 model directory for the selected platform"}),
            },
            "optional": {
                "platform": ("STRING", {"default": "ont", "options": ["ont", "hifi", "ilmn"]}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
                "regions_bed": ("BED", {"description": "Optional regions BED", "advanced": True}),
                "candidate_vcf": ("VCF_GZ", {"description": "Optional candidate VCF", "advanced": True}),
                "contigs": ("STRING", {"default": "", "description": "Optional comma-separated contig names", "advanced": True}),
                "sample_name": ("STRING", {"default": "", "description": "Optional sample name override", "advanced": True}),
                "qual": ("INT", {"default": 2, "min": 0, "advanced": True}),
                "chunk_size": ("INT", {"default": 5000000, "min": 1, "advanced": True}),
                "include_all_ctgs": ("BOOLEAN", {"default": False, "advanced": True}),
                "pileup_only": ("BOOLEAN", {"default": False, "advanced": True}),
                "enable_phasing": ("BOOLEAN", {"default": False, "advanced": True}),
                "haploid_precise": ("BOOLEAN", {"default": False, "advanced": True}),
                "haploid_sensitive": ("BOOLEAN", {"default": False, "advanced": True}),
                "enable_dwell_time": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class GatkBaseRecalibratorNode(CommandNode):
    """Base quality score recalibration with GATK."""
    NODE_ID = "gatk_base_recalibrator"
    DISPLAY_NAME = "GATK BaseRecalibrator"
    REQUIRED_CONDA_PACKAGES = ['gatk4']
    CATEGORY = "variant"
    DESCRIPTION = "Recalibrate base quality scores using known variants"
    SEARCH_ALIASES = ["gatk", "bqsr", "recalibrate", "base quality"]
    RETURN_TYPES = ("TABLE",)
    RETURN_NAMES = ("recal_table",)
    REQUIRED_EXECUTABLES = ["gatk"]
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360036898312-BaseRecalibrator"
    VERSION = "4.5.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "gatk", "BaseRecalibrator",
            "-I", str(inputs.get("bam", "")),
            "-R", str(inputs.get("reference", "")),
            "-O", f"{inputs.get('output', '.')}/recal_table.out",
        ]
        known = inputs.get("known_sites", "")
        if known:
            if isinstance(known, list):
                for ks in known:
                    cmd.extend(["--known-sites", str(ks)])
            else:
                for ks in str(known).split(","):
                    ks = ks.strip()
                    if ks:
                        cmd.extend(["--known-sites", ks])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "known_sites": ("VCF_GZ", {"description": "Known variants VCF (e.g., dbSNP, Mills). Use comma-separated paths for multiple sites."}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class GatkApplyBQSRNode(CommandNode):
    """Apply BQSR recalibration with GATK."""
    NODE_ID = "gatk_apply_bqsr"
    DISPLAY_NAME = "GATK ApplyBQSR"
    CATEGORY = "variant"
    DESCRIPTION = "Apply base quality score recalibration to a BAM file"
    SEARCH_ALIASES = ["gatk", "apply bqsr", "recalibrate"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("bam",)
    REQUIRED_EXECUTABLES = ["gatk"]
    REQUIRED_CONDA_PACKAGES = ['gatk4']
    DOCUMENTATION_URL = "https://gatk.broadinstitute.org/hc/en-us/articles/360037055952-ApplyBQSR"
    VERSION = "4.5.0"
    COMMAND = [
        "gatk", "ApplyBQSR",
        "-R", "{inputs.reference}",
        "-I", "{inputs.bam}",
        "--bqsr-recal-file", "{inputs.recal_table}",
        "-O", "{output}/bam.bam",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
                "recal_table": (("TABLE", "FILE"), {"description": "Recalibration table from BaseRecalibrator"}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class FreeBayesNode(CommandNode):
    """Call variants with FreeBayes."""
    NODE_ID = "freebayes"
    DISPLAY_NAME = "FreeBayes"
    REQUIRED_CONDA_PACKAGES = ['freebayes']
    CATEGORY = "variant"
    DESCRIPTION = "Bayesian haplotype-based variant caller"
    SEARCH_ALIASES = ["freebayes", "variant caller", "bayesian", "snp"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("vcf",)
    REQUIRED_EXECUTABLES = ["freebayes"]
    DOCUMENTATION_URL = "https://github.com/freebayes/freebayes"
    VERSION = "1.3.10"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["freebayes", "-f", str(inputs.get("reference", ""))]
        if inputs.get("pooled"):
            cmd.append("--pooled-continuous")
        if inputs.get("ploidy"):
            cmd.extend(["-p", str(inputs["ploidy"])])
        if inputs.get("min_mapping_quality") is not None:
            cmd.extend(["--min-mapping-quality", str(inputs["min_mapping_quality"])])
        if inputs.get("min_base_quality") is not None:
            cmd.extend(["--min-base-quality", str(inputs["min_base_quality"])])
        if inputs.get("haplotype_length") is not None:
            cmd.extend(["--haplotype-length", str(inputs["haplotype_length"])])
        cmd.append(str(inputs.get("bam", "")))
        cmd.extend([">", f"{inputs.get('output', '.')}/vcf.vcf"])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file (sorted, indexed)"}),
                "reference": ("FASTA", {"description": "Reference FASTA"}),
            },
            "optional": {
                "pooled": ("BOOLEAN", {"default": False, "description": "Enable pooled calling"}),
                "ploidy": ("INT", {"default": 2, "min": 1, "max": 8, "display": "slider"}),
                "min_mapping_quality": ("INT", {"default": 1, "min": 0, "label": "Min Mapping Quality", "advanced": True}),
                "min_base_quality": ("INT", {"default": 0, "min": 0, "label": "Min Base Quality", "advanced": True}),
                "haplotype_length": ("INT", {"default": 3, "min": 0, "label": "Haplotype Length", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class VcfToolsFilterNode(CommandNode):
    """Filter VCF with VCFtools."""
    NODE_ID = "vcftools_filter"
    DISPLAY_NAME = "VCFtools Filter"
    CATEGORY = "variant"
    DESCRIPTION = "Filter VCF files using VCFtools"
    SEARCH_ALIASES = ["vcftools", "filter", "vcf", "extract"]
    RETURN_TYPES = ("VCF",)
    RETURN_NAMES = ("filtered_vcf",)
    REQUIRED_EXECUTABLES = ["vcftools"]
    REQUIRED_CONDA_PACKAGES = ['vcftools']
    DOCUMENTATION_URL = "https://vcftools.github.io/index.html"
    VERSION = "0.1.17"
    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        vcf = str(inputs.get("vcf", ""))
        cmd = ["vcftools"]
        if vcf.endswith(".gz"):
            cmd.extend(["--gzvcf", vcf])
        else:
            cmd.extend(["--vcf", vcf])
        if inputs.get("maf") is not None and float(inputs.get("maf", 0)) > 0:
            cmd.extend(["--maf", str(inputs["maf"])])
        if inputs.get("min_qual") is not None:
            cmd.extend(["--minQ", str(inputs["min_qual"])])
        if inputs.get("min_dp") is not None:
            cmd.extend(["--min-meanDP", str(inputs["min_dp"])])
        if inputs.get("max_missing") is not None:
            cmd.extend(["--max-missing", str(inputs["max_missing"])])
        if inputs.get("recode_info_all"):
            cmd.append("--recode-INFO-all")
        cmd.extend([
            "--recode",
            "--out", f"{inputs.get('output', '.')}/filtered_vcf",
        ])
        return cmd

    async def run(self, **kwargs):
        import shutil
        from pathlib import Path
        result = await super().run(**kwargs)
        output_dir = kwargs.get("output_dir") or (kwargs.get("context") and getattr(kwargs["context"], "node_dir", "."))
        if output_dir:
            node_out = Path(output_dir) / self.__class__.NODE_ID
            actual = node_out / "filtered_vcf.recode.vcf"
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)
            if actual.exists() and outputs:
                target = outputs[0]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(actual), str(target))
        return result

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF", {"description": "Input VCF file"}),
            },
            "optional": {
                "maf": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01, "description": "Minor allele frequency threshold", "advanced": True}),
                "min_qual": ("INT", {"default": 30, "min": 0, "label": "Min Quality", "advanced": True}),
                "min_dp": ("INT", {"default": 10, "min": 0, "label": "Min Depth", "advanced": True}),
                "max_missing": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01, "label": "Max Missing", "advanced": True}),
                "recode_info_all": ("BOOLEAN", {"default": False, "description": "Recode all INFO fields", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
