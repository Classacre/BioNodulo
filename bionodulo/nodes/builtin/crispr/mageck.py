"""mageck — crispr node(s). One tool per file (extracted from crispr.py)."""
from __future__ import annotations
import csv
from pathlib import Path
import re
from typing import Any
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode
_IUPAC_PAM: dict[str, set[str]] = {'A': {'A'}, 'C': {'C'}, 'G': {'G'}, 'T': {'T'}, 'N': {'A', 'C', 'G', 'T', 'N'}}
def _read_fasta(path: Path) -> dict[str, str]:
    records: dict[str, list[str]] = {}
    current: str | None = None
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith('>'):
                current = stripped[1:].split()[0]
                records.setdefault(current, [])
            elif current is None:
                raise ValueError(f'FASTA sequence found before header in {path}')
            else:
                records[current].append(stripped.upper())
    return {name: ''.join(parts) for name, parts in records.items()}
def _reverse_complement(sequence: str) -> str:
    return sequence.translate(str.maketrans('ACGTNacgtn', 'TGCANtgcan'))[::-1].upper()
def _pam_matches(sequence: str, pam: str) -> bool:
    if len(sequence) != len(pam):
        return False
    return all((base in _IUPAC_PAM[pam_base] for base, pam_base in zip(sequence.upper(), pam, strict=True)))
def _hamming_distance(left: str, right: str) -> int:
    return sum((a != b for a, b in zip(left.upper(), right.upper(), strict=True)))
def _target_region(target: str, records: dict[str, str]) -> tuple[str, int, int]:
    match = re.fullmatch('([^:]+)(?::(\\d+)-(\\d+))?', target.strip())
    if not match:
        raise ValueError('target must be a contig name or contig:start-end region')
    contig = match.group(1)
    if contig not in records:
        raise ValueError(f'Target contig {contig!r} not found in genome')
    start = int(match.group(2) or 1)
    end = int(match.group(3) or len(records[contig]))
    if start < 1 or end < start:
        raise ValueError('target region must use 1-based coordinates with end >= start')
    return (contig, start, min(end, len(records[contig])))
def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, 'node_dir', '.') if context else '.')
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


class MAGeCKCountNode(CommandNode):
    """Count sgRNA reads for pooled CRISPR screens with MAGeCK."""
    NODE_ID = 'mageck_count'
    DISPLAY_NAME = 'MAGeCK Count'
    CATEGORY = 'crispr'
    DESCRIPTION = 'Count sgRNA reads from FASTQ for pooled CRISPR screens. Normalizes and generates count tables.'
    SEARCH_ALIASES = ['mageck', 'count', 'crispr screen', 'sgrna', 'pooled screen']
    RETURN_TYPES = ('TSV', 'TSV')
    RETURN_NAMES = ('count_table', 'normalized_counts')
    REQUIRED_EXECUTABLES = ['mageck']
    REQUIRED_CONDA_PACKAGES = ['mageck']
    DOCUMENTATION_URL = 'https://sourceforge.net/p/mageck/wiki/Home/'
    VERSION = '0.5.9'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        prefix = str(inputs.get('output_prefix', 'mageck_count'))
        cmd = ['mageck', 'count', '-l', str(inputs.get('library_file', '')), '-n', f'{out_dir}/{prefix}']
        fastq_files = inputs.get('fastq_files', [])
        if isinstance(fastq_files, str):
            fastq_files = [fastq_files] if fastq_files else []
        if fastq_files:
            cmd.append('--fastq')
            cmd.extend((str(fastq) for fastq in fastq_files))
        sample_labels = inputs.get('sample_labels', '')
        if isinstance(sample_labels, (list, tuple)):
            sample_labels = ','.join((str(label) for label in sample_labels))
        if sample_labels:
            cmd.extend(['--sample-label', str(sample_labels)])
        if inputs.get('day0_label'):
            cmd.extend(['--day0-label', str(inputs['day0_label'])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        prefix = str(inputs.get('output_prefix', 'mageck_count'))
        return [node_out / f'{prefix}.count.txt', node_out / f'{prefix}.count_normalized.txt']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'library_file': ('FILE', {'description': 'Library file with sgRNA sequences'}), 'fastq_files': ('FASTQ_LIST', {'description': 'FASTQ files from screen'}), 'output_prefix': ('STRING', {'default': 'mageck_count'})}, 'optional': {'sample_labels': ('STRING', {'default': '', 'description': 'Comma-separated labels'}), 'day0_label': ('STRING', {'default': '', 'description': 'Day 0 label for normalization'})}, 'hidden': {'output': ('STRING', {})}}


class MAGeCKTestNode(CommandNode):
    """Rank CRISPR screen genes from MAGeCK count tables."""
    NODE_ID = 'mageck_test'
    DISPLAY_NAME = 'MAGeCK Test'
    CATEGORY = 'crispr'
    DESCRIPTION = 'Identify essential genes from CRISPR screens using negative binomial model. Treatment vs control.'
    SEARCH_ALIASES = ['mageck', 'test', 'crispr screen', 'essential genes', 'gene ranking']
    RETURN_TYPES = ('TSV', 'TSV')
    RETURN_NAMES = ('gene_summary', 'sgrna_summary')
    REQUIRED_EXECUTABLES = ['mageck']
    REQUIRED_CONDA_PACKAGES = ['mageck']
    DOCUMENTATION_URL = 'https://sourceforge.net/p/mageck/wiki/Home/'
    VERSION = '0.5.9'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        prefix = str(inputs.get('output_prefix', 'mageck_test'))
        cmd = ['mageck', 'test', '-k', str(inputs.get('count_table', '')), '-t', str(inputs.get('treatment_labels', '')), '-c', str(inputs.get('control_labels', '')), '-n', f'{out_dir}/{prefix}']
        if inputs.get('norm_method'):
            cmd.extend(['--norm-method', str(inputs['norm_method'])])
        if inputs.get('adjust_method'):
            cmd.extend(['--adjust-method', str(inputs['adjust_method'])])
        if inputs.get('sort_criteria'):
            cmd.extend(['--sort-criteria', str(inputs['sort_criteria'])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        prefix = str(inputs.get('output_prefix', 'mageck_test'))
        return [node_out / f'{prefix}.gene_summary.txt', node_out / f'{prefix}.sgrna_summary.txt']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'count_table': ('TSV', {'description': 'MAGeCK count table'}), 'treatment_labels': ('STRING', {'description': 'Treatment sample labels (comma)'}), 'control_labels': ('STRING', {'description': 'Control sample labels (comma)'}), 'output_prefix': ('STRING', {'default': 'mageck_test'})}, 'optional': {'norm_method': ('STRING', {'default': 'median', 'options': ['median', 'total', 'control', 'none']}), 'adjust_method': ('STRING', {'default': 'fdr', 'options': ['fdr', 'holm', 'pounds']}), 'sort_criteria': ('STRING', {'default': 'neg', 'options': ['neg', 'pos']})}, 'hidden': {'output': ('STRING', {})}}
