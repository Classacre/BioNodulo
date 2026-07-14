"""crispresso2 — crispr node(s). One tool per file (extracted from crispr.py)."""
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


class CRISPRESSONode(CommandNode):
    """Analyze CRISPR amplicon editing outcomes with CRISPResso2."""
    NODE_ID = 'crispresso2'
    DISPLAY_NAME = 'CRISPRESSO2'
    CATEGORY = 'crispr'
    DESCRIPTION = 'Analyze CRISPR editing from amplicon sequencing. Quantifies indels, frameshifts, allele-specific outcomes.'
    SEARCH_ALIASES = ['crispresso', 'crispresso2', 'crispr', 'amplicon', 'indel', 'editing analysis']
    RETURN_TYPES = ('HTML_REPORT', 'DIRECTORY')
    RETURN_NAMES = ('report', 'results_dir')
    REQUIRED_EXECUTABLES = ['CRISPResso']
    REQUIRED_CONDA_PACKAGES = ['crispresso2']
    DOCUMENTATION_URL = 'https://github.com/pinellolab/CRISPResso2'
    VERSION = '2.3.2'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        cmd = ['CRISPResso', '-r1', str(inputs.get('r1', '')), '-a', str(inputs.get('amplicon_seq', '')), '-o', str(out_dir), '--name', str(inputs.get('name', 'crispresso_run'))]
        if inputs.get('r2'):
            cmd.extend(['-r2', str(inputs['r2'])])
        if inputs.get('guide_seq'):
            cmd.extend(['-g', str(inputs['guide_seq'])])
        if inputs.get('quant_window_center'):
            cmd.extend(['-wc', str(inputs['quant_window_center'])])
        if inputs.get('quant_window_size'):
            cmd.extend(['-w', str(inputs['quant_window_size'])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        name = str(inputs.get('name', 'crispresso_run'))
        run_name = f'CRISPResso_on_{name}'
        return [node_out / f'{run_name}.html', node_out / run_name]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'r1': ('FASTQ', {'description': 'Forward FASTQ'}), 'amplicon_seq': ('STRING', {'description': 'Reference amplicon sequence'}), 'name': ('STRING', {'default': 'crispresso_run'})}, 'optional': {'r2': ('FASTQ', {'description': 'Reverse FASTQ (paired)'}), 'guide_seq': ('STRING', {'default': '', 'description': 'gRNA sequence (20bp)'}), 'quant_window_center': ('INT', {'default': -3, 'min': -20, 'max': 20}), 'quant_window_size': ('INT', {'default': 1, 'min': 0, 'max': 100})}, 'hidden': {'output': ('STRING', {})}}
