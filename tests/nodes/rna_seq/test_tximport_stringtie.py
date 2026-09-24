from __future__ import annotations

import asyncio
import csv
import json
import os
import subprocess
from pathlib import Path

import pytest

from bionodulo.execution.executor import ExecutionContext
from bionodulo.nodes.builtin.rna_seq_family.tximport_stringtie import TximportStringTieNode


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "fixtures" / "tximport_stringtie"


def _inputs() -> dict[str, object]:
    return {
        "ctab_files": [str(FIXTURE / "sample1" / "t_data.ctab"), str(FIXTURE / "sample2" / "t_data.ctab")],
        "sample_ids": ["control", "treated"],
        "tx2gene": str(FIXTURE / "tx2gene.tsv"),
        "reference_gtf": str(FIXTURE / "reference.gtf"),
        "read_length": 150.0,
        "counts_from_abundance": "no",
    }


def _r_configuration() -> tuple[Path, Path]:
    executable = Path(os.environ.get("TXIMPORT_RSCRIPT", r"C:\Program Files\R\R-4.5.1\bin\Rscript.exe"))
    library = Path(os.environ.get("TXIMPORT_R_LIB", r"D:\AI\BioNodulo\phd-implementation-2026-09-23\r-library-tximport"))
    if not executable.is_file() or not (library / "tximport").is_dir():
        pytest.skip("isolated R/tximport integration environment is unavailable")
    return executable, library


def test_stringtie_import_requires_explicit_read_length_and_valid_modes(tmp_path: Path) -> None:
    assert "read_length" in str(TximportStringTieNode.VALIDATE_INPUTS({**_inputs(), "read_length": None}))
    assert "explicit positive" in str(TximportStringTieNode.VALIDATE_INPUTS({**_inputs(), "read_length": 0}))
    assert "transcript-level DTU" in str(TximportStringTieNode.VALIDATE_INPUTS({**_inputs(), "counts_from_abundance": "dtuScaledTPM"}))
    inputs = _inputs()
    outputs = TximportStringTieNode.PLAN_OUTPUTS(inputs, tmp_path)
    TximportStringTieNode.PREPARE_EXECUTION(inputs, outputs)
    command = TximportStringTieNode.render_command(inputs)
    assert command[0:3] == ["Rscript", "--vanilla", str(TximportStringTieNode.SCRIPT_PATH)]
    assert command[5] == str((FIXTURE / "reference.gtf").resolve())
    assert command[6:8] == ["150.0", "no"]


def test_stringtie_import_rejects_reference_and_mapping_mismatch(tmp_path: Path) -> None:
    altered = tmp_path / "t_data.ctab"
    content = (FIXTURE / "sample2" / "t_data.ctab").read_text(encoding="utf-8")
    altered.write_text(content.replace("tx2\t1\t800", "tx2\t1\t801"), encoding="utf-8")
    inputs = {**_inputs(), "ctab_files": [str(FIXTURE / "sample1" / "t_data.ctab"), str(altered)]}
    assert "same transcript reference" in str(TximportStringTieNode.VALIDATE_INPUTS(inputs))

    mapping = tmp_path / "tx2gene.tsv"
    mapping.write_text("transcript_id\tgene_id\ntx1\tgeneA\n", encoding="utf-8")
    assert "missing 2 StringTie transcript" in str(TximportStringTieNode.VALIDATE_INPUTS({**_inputs(), "tx2gene": str(mapping)}))

    contradictory = tmp_path / "contradictory.tsv"
    contradictory.write_text(
        "transcript_id\tgene_id\ntx1\tWRONG_A\ntx2\tgeneB\ntx3\tgeneC\n",
        encoding="utf-8",
    )
    assert "contradicts reference_gtf" in str(
        TximportStringTieNode.VALIDATE_INPUTS({**_inputs(), "tx2gene": str(contradictory)})
    )


def test_stringtie_coverage_formula_fixture_is_exact() -> None:
    with (FIXTURE / "sample1" / "t_data.ctab").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    reconstructed = {row["t_name"]: float(row["cov"]) * float(row["length"]) / 150.0 for row in rows}
    assert reconstructed == {"tx1": 800.0, "tx2": 800.0 / 3.0, "tx3": 400.0 / 3.0}


@pytest.mark.parametrize("mode", TximportStringTieNode.COUNTS_FROM_ABUNDANCE)
@pytest.mark.asyncio
async def test_real_stringtie_import_matches_direct_upstream_oracle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    executable, library = _r_configuration()
    monkeypatch.setenv("R_LIBS_USER", str(library))
    monkeypatch.setenv("PATH", str(executable.parent) + os.pathsep + os.environ.get("PATH", ""))
    node_dir = tmp_path / "app-executor"
    node_dir.mkdir()
    context = ExecutionContext(
        run_id="stringtie-import-fixture",
        node_id="stringtie-import-node",
        node_type="tximport_stringtie",
        node_dir=node_dir,
        workspace_dir=tmp_path,
        params={},
        api_secrets={},
        emit=lambda _event, _payload: None,
        cancel_event=asyncio.Event(),
    )
    outputs = [Path(path) for path in await TximportStringTieNode().run(**{**_inputs(), "counts_from_abundance": mode}, context=context)]

    oracle = tmp_path / f"oracle-{mode}.rds"
    script = tmp_path / f"oracle-{mode}.R"
    script.write_text(
        "library(tximport)\na<-commandArgs(trailingOnly=TRUE)\n"
        "f<-c(control=a[[1]],treated=a[[2]])\nm<-read.delim(a[[3]],check.names=FALSE)\n"
        "x<-tximport(f,type='stringtie',tx2gene=m,readLength=150,countsFromAbundance=a[[4]],txOut=FALSE,dropInfReps=TRUE)\n"
        "saveRDS(x,a[[5]])\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["R_LIBS_USER"] = str(library)
    subprocess.run([str(executable), "--vanilla", str(script), str(FIXTURE / "sample1" / "t_data.ctab"), str(FIXTURE / "sample2" / "t_data.ctab"), str(FIXTURE / "tx2gene.tsv"), mode, str(oracle)], check=True, env=env, capture_output=True, text=True)
    compare = tmp_path / "compare.R"
    compare.write_text(
        "a<-commandArgs(trailingOnly=TRUE)\nx<-readRDS(a[[1]]);y<-readRDS(a[[2]])\n"
        "stopifnot(isTRUE(all.equal(x$counts,y$counts,tolerance=1e-12)))\n"
        "stopifnot(isTRUE(all.equal(x$abundance,y$abundance,tolerance=1e-12)))\n"
        "stopifnot(isTRUE(all.equal(x$length,y$length,tolerance=1e-12)))\n",
        encoding="utf-8",
    )
    subprocess.run([str(executable), "--vanilla", str(compare), str(oracle), str(outputs[3])], check=True, env=env, capture_output=True, text=True)
    metadata = json.loads(outputs[4].read_text(encoding="utf-8"))
    assert metadata["read_length"] == 150
    assert metadata["abundance_units"] == "FPKM"
    assert metadata["coverage_to_count_formula"] == "coverage * transcript_length / read_length"
    assert metadata["raw_counts"] is False
    assert metadata["reference_gtf_sha256"] == __import__("hashlib").sha256(
        (FIXTURE / "reference.gtf").read_bytes()
    ).hexdigest()


def test_real_r_runner_rejects_tx2gene_that_contradicts_reference_gtf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable, library = _r_configuration()
    monkeypatch.setenv("R_LIBS_USER", str(library))
    manifest = tmp_path / "sample_manifest.tsv"
    manifest.write_text(
        "sample_id\tctab_file\n"
        f"sample1\t{(FIXTURE / 'sample1' / 't_data.ctab').resolve()}\n",
        encoding="utf-8",
    )
    contradictory = tmp_path / "contradictory.tsv"
    contradictory.write_text(
        "transcript_id\tgene_id\ntx1\tWRONG_A\ntx2\tgeneB\ntx3\tgeneC\n",
        encoding="utf-8",
    )
    outputs = [
        tmp_path / "counts.tsv",
        tmp_path / "abundance.tsv",
        tmp_path / "length.tsv",
        tmp_path / "tximport.rds",
        tmp_path / "metadata.json",
    ]
    env = os.environ.copy()
    env["R_LIBS_USER"] = str(library)
    result = subprocess.run(
        [
            str(executable),
            "--vanilla",
            str(TximportStringTieNode.SCRIPT_PATH),
            str(manifest),
            str(contradictory),
            str(FIXTURE / "reference.gtf"),
            "150",
            "no",
            *(str(path) for path in outputs),
        ],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "contradicts reference GTF for transcript tx1" in result.stderr
    assert not any(path.exists() for path in outputs)
