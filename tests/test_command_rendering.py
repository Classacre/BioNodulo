from bionodulo.nodes.builtin.trimming import FastpNode


def test_command_template_rendering():
    command = FastpNode.render_command(
        inputs={"reads": ["R1.fastq.gz", "R2.fastq.gz"]},
        outputs={
            "trimmed_reads": ["trimmed_R1.fastq.gz", "trimmed_R2.fastq.gz"],
            "html_report": "fastp.html",
            "json_report": "fastp.json",
        },
        params={"threads": 4},
    )

    assert command[:2] == ["fastp", "-i"]
    assert "R1.fastq.gz" in command
    assert "trimmed_R2.fastq.gz" in command
    assert command[-1] == "4"
