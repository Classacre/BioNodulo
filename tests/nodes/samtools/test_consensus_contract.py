from __future__ import annotations

from bionodulo.nodes.builtin.samtools_family.consensus import SamtoolsConsensusNode


def _inputs(**overrides: object) -> dict[str, object]:
    inputs: dict[str, object] = {"input": "reads.bam", "threads": 1}
    inputs.update(overrides)
    return inputs


def test_explicit_zero_disables_the_source_default_exclusion_mask() -> None:
    inputs = _inputs(skipped_flags="0")

    assert SamtoolsConsensusNode.VALIDATE_INPUTS(inputs) is True
    command = SamtoolsConsensusNode.render_command(inputs)
    assert command[command.index("--ff") : command.index("--ff") + 2] == ["--ff", "0"]


def test_documented_double_a_and_reference_quality_are_rendered() -> None:
    inputs = _inputs(
        format="fastq",
        reference="reference.fa",
        reference_index="reference.fa.fai",
        reference_quality=30,
        output_all_references=True,
    )

    assert SamtoolsConsensusNode.VALIDATE_INPUTS(inputs) is True
    command = SamtoolsConsensusNode.render_command(inputs)
    assert command[command.index("--ref-qual") : command.index("--ref-qual") + 2] == [
        "--ref-qual",
        "30",
    ]
    assert command.count("-a") == 2


def test_simple_and_manual_bayesian_argv_are_mode_specific() -> None:
    simple_inputs = _inputs(
        mode="simple",
        use_qual=True,
        consensus_fraction=0.9,
        heterozygous_fraction=0.2,
        ambig=True,
    )
    assert SamtoolsConsensusNode.VALIDATE_INPUTS(simple_inputs) is True
    simple = SamtoolsConsensusNode.render_command(simple_inputs)
    assert "-q" in simple
    assert simple[simple.index("-c") : simple.index("-c") + 2] == ["-c", "0.9"]
    assert "--P-het" not in simple

    bayesian_inputs = _inputs(mode="bayesian", config="manual", p_het=0.01, homopoly_score=0.3)
    assert SamtoolsConsensusNode.VALIDATE_INPUTS(bayesian_inputs) is True
    bayesian = SamtoolsConsensusNode.render_command(bayesian_inputs)
    assert bayesian[bayesian.index("--P-het") : bayesian.index("--P-het") + 2] == [
        "--P-het",
        "0.01",
    ]
    assert bayesian[bayesian.index("--homopoly-score") + 1] == "0.3"
    assert "-c" not in bayesian


def test_source_ignored_or_overridden_settings_fail_closed() -> None:
    cases = (
        (_inputs(mode="simple", config="hifi"), "config"),
        (_inputs(mode="simple", cutoff=20), "cutoff"),
        (_inputs(mode="bayesian", use_qual=True), "use_qual"),
        (_inputs(mode="bayesian", consensus_fraction=0.9), "consensus_fraction"),
        (_inputs(mode="bayesian_116", config="hifi"), "force Samtools into bayesian"),
        (_inputs(mode="bayesian", config="hifi", p_het=0.01), "overridden"),
        (_inputs(mode="bayesian", use_mq=False, low_mq=0), "no effect"),
        (_inputs(mode="bayesian", use_mq=False, homopoly_fix=True), "no effect"),
        (_inputs(format="pileup", mark_insertions=True), "FASTA or FASTQ"),
        (_inputs(format="pileup", line_len=100), "line_len"),
        (_inputs(mark_insertions=True, show_insertions=False), "no effect"),
        (_inputs(mode="simple", heterozygous_fraction=0.2), "requires ambig"),
        (
            _inputs(
                region="chr1:1-10",
                bam_index="reads.bam.bai",
                output_all_references=True,
            ),
            "cannot be combined",
        ),
        (_inputs(reference_quality=20), "requires a reference"),
        (
            _inputs(
                reference="reference.fa",
                reference_index="reference.fa.fai",
                reference_quality=20,
            ),
            "FASTQ",
        ),
    )

    for inputs, message in cases:
        result = SamtoolsConsensusNode.VALIDATE_INPUTS(inputs)
        assert result is not True, inputs
        assert message in str(result), (inputs, result)


def test_implicit_indexes_are_only_accepted_when_samtools_can_load_them() -> None:
    cases = (
        (_inputs(input="reads.sam", bam_index="reads.sam.bai"), False),
        (_inputs(bam_index="reads.bam.bai"), False),
        (_inputs(threads=2, bam_index="reads.bam.bai"), True),
        (_inputs(input="reads.cram", threads=2, bam_index="reads.cram.crai"), True),
    )

    for inputs, expected in cases:
        result = SamtoolsConsensusNode.VALIDATE_INPUTS(inputs)
        assert (result is True) is expected, (inputs, result)
