"""cas — crispr node(s). One tool per file (extracted from crispr.py)."""
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


class CasOffinderNode(CommandNode):
    """Detect candidate CRISPR guide off-target sites with Cas-OFFinder."""
    NODE_ID = 'cas_offinder'
    DISPLAY_NAME = 'Cas-OFFinder'
    CATEGORY = 'crispr'
    DESCRIPTION = 'Fast off-target detection for CRISPR gRNAs. Multiple PAMs and mismatch tolerance.'
    SEARCH_ALIASES = ['cas-offinder', 'off target', 'crispr safety', 'grna', 'guide rna']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('offtarget_sites',)
    REQUIRED_EXECUTABLES = ['cas-offinder']
    REQUIRED_CONDA_PACKAGES = ['cas-offinder']
    DOCUMENTATION_URL = 'https://github.com/snugel/cas-offinder'
    VERSION = '2.4.1'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        input_file = out_dir / 'cas_offinder_input.txt'
        output_file = out_dir / 'offtarget_sites.txt'
        guide_seq = str(inputs.get('guide_seq', ''))
        pam_sequence = str(inputs.get('pam_sequence', 'NNG'))
        search_pattern = f"{'N' * len(guide_seq)}{pam_sequence}"
        query_sequence = f'{guide_seq}{pam_sequence}'
        input_file.write_text('\n'.join([str(inputs.get('genome_fasta', '')), search_pattern, f"{query_sequence} {inputs.get('mismatches', 3)}"]) + '\n', encoding='utf-8')
        return ['cas-offinder', str(input_file), str(inputs.get('device', 'C')), str(output_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'offtarget_sites.txt']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'guide_seq': ('STRING', {'description': 'Guide RNA sequence without PAM'}), 'genome_fasta': ('FASTA', {'description': 'Target genome FASTA or 2bit directory'}), 'mismatches': ('INT', {'default': 3, 'min': 0, 'max': 10})}, 'optional': {'pam_sequence': ('STRING', {'default': 'NNG', 'description': 'PAM pattern (N=wildcard)'}), 'device': ('STRING', {'default': 'C', 'options': ['C', 'G', 'A'], 'description': 'C=CPU, G=GPU, A=accelerator'})}, 'hidden': {'output': ('STRING', {})}}
