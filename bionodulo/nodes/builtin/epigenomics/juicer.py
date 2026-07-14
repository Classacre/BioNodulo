"""juicer — epigenomics node(s). One tool per file (extracted from epigenomics.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
DSS_DMR_SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'dss_dmr.R'
def _safe_output_stem(value: Any, default: str) -> str:
    stem = '_'.join(str(value or '').strip().split())
    stem = ''.join((char if char.isalnum() or char in '._-' else '_' for char in stem))
    stem = stem.strip('._-')
    return stem or default
def _split_path_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace('\n', ',').split(',') if part.strip()]
def _split_window_sizes(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace(',', ' ').split() if part.strip()]
def _split_base_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple)) else [value]
    bases: list[str] = []
    for item in values:
        bases.extend((part.strip() for part in str(item).replace(',', ' ').split() if part.strip()))
    return bases


class JuicerNode(CommandNode):
    """Run the Juicer Hi-C processing pipeline."""
    NODE_ID = 'juicer'
    DISPLAY_NAME = 'Juicer Pipeline'
    CATEGORY = 'epigenomics'
    DESCRIPTION = 'Process Hi-C data with Juicer. Generates .hic files with HiCCUPS loop calling and Arrowhead TAD calling.'
    SEARCH_ALIASES = ['juicer', 'hic', 'juicebox', 'hiccups', 'arrowhead', 'tad', 'loops']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('hic_file',)
    REQUIRED_EXECUTABLES = ['juicer.sh']
    REQUIRED_CONDA_PACKAGES = ['juicer']
    DOCUMENTATION_URL = 'https://github.com/aidenlab/juicer'
    VERSION = '2.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['juicer.sh', '-g', str(inputs.get('genome_id', '')), '-d', str(inputs.get('fastq_dir', '')), '-s', str(inputs.get('restriction_site', 'none')), '-p', str(inputs.get('chrom_sizes', '')), '-D', str(inputs.get('output', '.'))]
        if inputs.get('restriction_sites_bed'):
            cmd.extend(['-y', str(inputs['restriction_sites_bed'])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'hic_file.hic']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'fastq_dir': ('DIRECTORY', {'description': '_R1.fastq.gz and _R2.fastq.gz files'}), 'genome_id': ('STRING', {'description': 'Genome ID (hg38, mm10)'}), 'chrom_sizes': ('FILE', {'description': 'Chromosome sizes'}), 'restriction_site': ('STRING', {'default': 'none', 'description': 'Enzyme site (e.g., GATC)'})}, 'optional': {'restriction_sites_bed': ('BED', {'description': 'Restriction sites BED'})}, 'hidden': {'output': ('STRING', {})}}
