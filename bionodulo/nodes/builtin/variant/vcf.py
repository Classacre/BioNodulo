"""vcf — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class VCFComparisonNode(CommandNode):
    """Compare two VCF callsets with RTG vcfeval."""
    NODE_ID = 'vcf_comparison'
    DISPLAY_NAME = 'VCF Comparison'
    CATEGORY = 'variant'
    DESCRIPTION = 'Compare variant callsets and report precision, recall, F1, and overlap metrics.'
    SEARCH_ALIASES = ['vcf comparison', 'benchmark', 'precision recall', 'rtg vcfeval', 'variant evaluation']
    RETURN_TYPES = ('JSON', 'IMAGE')
    RETURN_NAMES = ('comparison', 'venn_plot')
    REQUIRED_EXECUTABLES = ['rtg']
    REQUIRED_CONDA_PACKAGES = ['rtg-tools', 'matplotlib']
    DOCUMENTATION_URL = 'https://realtimegenomics.github.io/rtg-tools/rtg_command_reference.html#vcfeval'
    VERSION = '3.12.1'
    SHELL = False

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get('output', '.'))
        plot_format = str(inputs.get('plot_format', 'png') or 'png').lower()
        if plot_format not in {'png', 'svg'}:
            plot_format = 'png'
        sample = shlex.quote(str(inputs.get('sample', '')).strip())
        squash_ploidy = bool(inputs.get('squash_ploidy', False))
        reference = shlex.quote(str(inputs.get('reference', '')))
        vcf_a = shlex.quote(str(inputs.get('vcf_a', '')))
        vcf_b = shlex.quote(str(inputs.get('vcf_b', '')))
        out_dir = shlex.quote(output)
        comparison_json = shlex.quote(f'{output}/comparison.json')
        venn_plot = shlex.quote(f'{output}/venn_plot.{plot_format}')
        sample_arg = f' --sample {sample}' if sample else ''
        squash_arg = ' --squash-ploidy' if squash_ploidy else ''
        script = f"""\nset -euo pipefail\nmkdir -p {out_dir}\nif [ ! -d {out_dir}/reference.sdf ]; then\n  rtg format -o {out_dir}/reference.sdf {reference}\nfi\nrtg vcfeval --baseline {vcf_a} --calls {vcf_b} --template {out_dir}/reference.sdf --output {out_dir}/vcfeval{sample_arg}{squash_arg}\npython - "$@" <<'PY'\nimport csv\nimport json\nimport sys\n\nimport matplotlib\nmatplotlib.use('Agg')\nimport matplotlib.pyplot as plt\n\nsummary_path, comparison_json, venn_plot = sys.argv[1:4]\nmetrics = {{}}\ntry:\n    with open(summary_path, encoding='utf-8') as handle:\n        for row in csv.reader(handle, delimiter='\\t'):\n            if len(row) >= 2:\n                key = row[0].strip().lower().replace(' ', '_')\n                value = row[1].strip()\n                if key:\n                    metrics[key] = value\nexcept FileNotFoundError:\n    pass\n\ntrue_positive = int(float(metrics.get('true_positives_baseline', metrics.get('tp_baseline', 0)) or 0))\nfalse_positive = int(float(metrics.get('false_positives', metrics.get('fp', 0)) or 0))\nfalse_negative = int(float(metrics.get('false_negatives', metrics.get('fn', 0)) or 0))\nprecision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0\nrecall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0\nf1 = 2 * precision * recall / (precision + recall) if precision + recall else 0\n\nsummary = {{\n    'metrics': metrics,\n    'precision': precision,\n    'recall': recall,\n    'f1': f1,\n    'true_positive': true_positive,\n    'false_positive': false_positive,\n    'false_negative': false_negative,\n}}\nwith open(comparison_json, 'w', encoding='utf-8') as handle:\n    json.dump(summary, handle, indent=2, sort_keys=True)\n    handle.write('\\n')\n\nfig, ax = plt.subplots(figsize=(5, 4))\nlabels = ['TP', 'FP', 'FN']\nvalues = [true_positive, false_positive, false_negative]\nax.bar(labels, values, color=['#2f6f73', '#a84d3d', '#6d5f9a'])\nax.set_title('VCF comparison')\nax.set_ylabel('Variants')\nfig.tight_layout()\nfig.savefig(venn_plot)\nplt.close(fig)\nPY\n{out_dir}/vcfeval/summary.txt {comparison_json} {venn_plot}\n""".strip()
        return ['bash', '-c', script]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_dir = Path(output_dir)
        node_out = output_dir / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        plot_format = str(inputs.get('plot_format', 'png') or 'png').lower()
        if plot_format not in {'png', 'svg'}:
            plot_format = 'png'
        return [node_out / 'comparison.json', node_out / f'venn_plot.{plot_format}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'vcf_a': ('VCF_GZ', {'description': 'Baseline/truth VCF.GZ'}), 'vcf_b': ('VCF_GZ', {'description': 'Calls VCF.GZ to evaluate'}), 'reference': ('FASTA', {'description': 'Reference FASTA used by both callsets'})}, 'optional': {'sample': ('STRING', {'default': '', 'description': 'Optional sample name to compare', 'advanced': True}), 'squash_ploidy': ('BOOLEAN', {'default': False, 'description': 'Ignore genotype ploidy differences', 'advanced': True}), 'plot_format': ('STRING', {'default': 'png', 'options': ['png', 'svg'], 'label': 'Plot Format', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
