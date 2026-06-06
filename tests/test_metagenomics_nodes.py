from pathlib import Path

from bionodulo.nodes.builtin.metagenomics import HUMAnNNode


def test_humann_plans_standard_functional_profile_outputs() -> None:
    outputs = HUMAnNNode.PLAN_OUTPUTS(
        {"reads": ["reads_forward.fastq", "reads_reverse.fastq"]},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/humann/output_dir.out",
        "/tmp/run/humann/output_dir.out/reads_forward_genefamilies.tsv",
        "/tmp/run/humann/output_dir.out/reads_forward_pathabundance.tsv",
        "/tmp/run/humann/output_dir.out/reads_forward_pathcoverage.tsv",
    ]


def test_humann_plans_single_read_stem_outputs() -> None:
    outputs = HUMAnNNode.PLAN_OUTPUTS({"reads": "sample.fastq.gz"}, Path("/tmp/run"))

    assert [path.name for path in outputs] == [
        "output_dir.out",
        "sample_genefamilies.tsv",
        "sample_pathabundance.tsv",
        "sample_pathcoverage.tsv",
    ]
