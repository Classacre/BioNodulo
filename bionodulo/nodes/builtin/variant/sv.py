"""sv — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class SVStatsNode(CommandNode):
    """Compute summary statistics and size plots from structural-variant VCFs."""
    NODE_ID = 'sv_stats'
    DISPLAY_NAME = 'SV Stats'
    CATEGORY = 'variant'
    DESCRIPTION = 'Compute structural variant statistics, SVTYPE counts, size distribution, and quality summaries.'
    SEARCH_ALIASES = ['sv stats', 'structural variant statistics', 'size distribution', 'svtype counts', 'vcf qc']
    RETURN_TYPES = ('JSON', 'IMAGE')
    RETURN_NAMES = ('stats_json', 'stats_plot')
    REQUIRED_EXECUTABLES = ['python']
    REQUIRED_CONDA_PACKAGES = ['pysam', 'matplotlib']
    DOCUMENTATION_URL = 'https://pysam.readthedocs.io/en/latest/api.html#pysam.VariantFile'
    VERSION = '1.0'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get('output', '.'))
        plot_format = str(inputs.get('plot_format', 'png') or 'png').lower()
        if plot_format not in {'png', 'svg'}:
            plot_format = 'png'
        script = "\nimport json\nimport sys\nfrom collections import Counter\n\nimport matplotlib\nmatplotlib.use('Agg')\nimport matplotlib.pyplot as plt\nimport pysam\n\nsv_vcf, reference, stats_json, stats_plot, min_size, max_size = sys.argv[1:7]\nmin_size = int(min_size)\nmax_size = int(max_size)\n\ncounts = Counter()\nsizes = []\nqualities = []\ntotal_records = 0\npassing_records = 0\n\nwith pysam.VariantFile(sv_vcf) as vcf:\n    for record in vcf:\n        total_records += 1\n        svtype = record.info.get('SVTYPE', 'UNKNOWN')\n        if isinstance(svtype, tuple):\n            svtype = svtype[0] if svtype else 'UNKNOWN'\n        svtype = str(svtype)\n\n        svlen = record.info.get('SVLEN')\n        if isinstance(svlen, tuple):\n            svlen = svlen[0] if svlen else None\n        if svlen is None and record.stop is not None:\n            svlen = record.stop - record.pos\n        try:\n            size = abs(int(svlen)) if svlen is not None else 0\n        except (TypeError, ValueError):\n            size = 0\n\n        if size < min_size or (max_size > 0 and size > max_size):\n            continue\n\n        counts[svtype] += 1\n        sizes.append(size)\n        if record.qual is not None:\n            qualities.append(float(record.qual))\n        if not record.filter.keys() or set(record.filter.keys()) == {'PASS'}:\n            passing_records += 1\n\nsummary = {\n    'reference': reference,\n    'total_records': total_records,\n    'records_in_size_range': sum(counts.values()),\n    'passing_records': passing_records,\n    'svtype_counts': dict(sorted(counts.items())),\n    'size': {\n        'min': min(sizes) if sizes else 0,\n        'max': max(sizes) if sizes else 0,\n        'mean': (sum(sizes) / len(sizes)) if sizes else 0,\n    },\n    'quality': {\n        'min': min(qualities) if qualities else None,\n        'max': max(qualities) if qualities else None,\n        'mean': (sum(qualities) / len(qualities)) if qualities else None,\n    },\n}\n\nwith open(stats_json, 'w', encoding='utf-8') as handle:\n    json.dump(summary, handle, indent=2, sort_keys=True)\n    handle.write('\\n')\n\nfig, axes = plt.subplots(1, 2, figsize=(10, 4))\nlabels = list(summary['svtype_counts'].keys())\nvalues = list(summary['svtype_counts'].values())\naxes[0].bar(labels or ['none'], values or [0], color='#2f6f73')\naxes[0].set_title('SVTYPE counts')\naxes[0].set_ylabel('Records')\naxes[0].tick_params(axis='x', rotation=35)\naxes[1].hist(sizes or [0], bins=min(30, max(1, len(sizes))), color='#a84d3d')\naxes[1].set_title('SV size distribution')\naxes[1].set_xlabel('Absolute SVLEN')\naxes[1].set_ylabel('Records')\nfig.tight_layout()\nfig.savefig(stats_plot)\nplt.close(fig)\n".strip()
        return ['python', '-c', script, str(inputs.get('sv_vcf', '')), str(inputs.get('reference', '')), f'{output}/stats_json.json', f'{output}/stats_plot.{plot_format}', str(inputs.get('min_size', 50)), str(inputs.get('max_size', 0))]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_dir = Path(output_dir)
        node_out = output_dir / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        plot_format = str(inputs.get('plot_format', 'png') or 'png').lower()
        if plot_format not in {'png', 'svg'}:
            plot_format = 'png'
        return [node_out / 'stats_json.json', node_out / f'stats_plot.{plot_format}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'sv_vcf': ('VCF_GZ', {'description': 'Structural variant VCF or VCF.GZ'}), 'reference': ('FASTA', {'description': 'Reference FASTA used for the callset'})}, 'optional': {'min_size': ('INT', {'default': 50, 'min': 0, 'label': 'Minimum SV Size'}), 'max_size': ('INT', {'default': 0, 'min': 0, 'label': 'Maximum SV Size', 'description': '0 disables the upper size filter', 'advanced': True}), 'plot_format': ('STRING', {'default': 'png', 'options': ['png', 'svg'], 'label': 'Plot Format', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
