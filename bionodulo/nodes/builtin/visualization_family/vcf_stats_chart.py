"""Stable owner for the ``vcf_stats_chart`` node."""

from .adapter import _VCFStatsChartContract


class VCFStatsChartNode(_VCFStatsChartContract):
    """Summarize VCF records into one chart and one deterministic JSON file."""

    NODE_ID = "vcf_stats_chart"
    UPSTREAM_SYMBOL = "VCFStatsChartNode"
