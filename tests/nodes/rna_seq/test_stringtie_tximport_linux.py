"""Opt-in real HISAT2 BAM -> StringTie -> tximport acceptance test."""

from __future__ import annotations

import asyncio
import csv
import json
import os
import platform
import subprocess
from pathlib import Path

import pytest

from bionodulo.execution.executor import ExecutionContext
from bionodulo.nodes.builtin.rna_seq_family.stringtie import StringTieNode
from bionodulo.nodes.builtin.rna_seq_family.tximport_stringtie import TximportStringTieNode


FIXTURE_ENV = "BIONODULO_STRINGTIE_FIXTURE"
pytestmark = pytest.mark.skipif(
    platform.system() != "Linux" or not os.environ.get(FIXTURE_ENV),
    reason=f"requires Linux and {FIXTURE_ENV}",
)


def _context(node_dir: Path, node_type: str) -> ExecutionContext:
    return ExecutionContext(
        run_id="hisat2-stringtie-tximport",
        node_id=node_type,
        node_type=node_type,
        node_dir=node_dir,
        workspace_dir=node_dir.parent,
        params={},
        api_secrets={},
        emit=lambda _event, _payload: None,
        cancel_event=asyncio.Event(),
    )


def _ctab_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["t_name"]: row for row in csv.DictReader(handle, delimiter="\t")}


def test_real_hisat2_stringtie_tximport_matches_independent_oracles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = Path(os.environ[FIXTURE_ENV])
    bam = fixture / "engine" / "runs" / "real" / "sort" / "samtools_sort" / "sorted_bam.bam"
    annotation = fixture / "annotation.gtf"
    mapping = fixture / "tx2gene.tsv"
    for path in (bam, annotation, mapping):
        assert path.is_file(), path

    tool_bin = Path(os.environ.get("BIONODULO_PHD_BIN", "/opt/bionodulo-phd/bin"))
    r_bin = Path(os.environ.get("BIONODULO_PHD_R_BIN", "/opt/bionodulo-phd/r-env/bin"))
    monkeypatch.setenv("PATH", os.pathsep.join((str(tool_bin), str(r_bin), os.environ.get("PATH", ""))))

    app_stringtie_dir = tmp_path / "app-stringtie"
    app_stringtie = [
        Path(path)
        for path in asyncio.run(StringTieNode().run(
            bam=bam,
            gtf=annotation,
            threads=1,
            reference_abundance=True,
            context=_context(app_stringtie_dir, "stringtie"),
        ))
    ]
    assert app_stringtie[2].name == "t_data.ctab"

    oracle_dir = tmp_path / "oracle-stringtie"
    oracle_dir.mkdir()
    subprocess.run(
        [
            str(tool_bin / "stringtie"),
            str(bam),
            "-G",
            str(annotation),
            "-o",
            str(oracle_dir / "transcripts.gtf"),
            "-A",
            str(oracle_dir / "gene_abundance.tsv"),
            "-p",
            "1",
            "-e",
            "-B",
            "-f",
            "0.01",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    app_rows = _ctab_rows(app_stringtie[2])
    oracle_rows = _ctab_rows(oracle_dir / "t_data.ctab")
    assert app_rows == oracle_rows
    reconstructed = {
        transcript: float(row["cov"]) * float(row["length"]) / 150.0
        for transcript, row in app_rows.items()
    }
    assert reconstructed == {"tx1": 800.0, "tx2": 200.0, "tx3": 400.0}

    app_import_dir = tmp_path / "app-import"
    imported = [
        Path(path)
        for path in asyncio.run(TximportStringTieNode().run(
            ctab_files=[app_stringtie[2]],
            sample_ids=["hisat2_fixture"],
            tx2gene=mapping,
            read_length=150.0,
            counts_from_abundance="no",
            context=_context(app_import_dir, "tximport_stringtie"),
        ))
    ]
    oracle_rds = tmp_path / "oracle-tximport.rds"
    oracle_script = tmp_path / "oracle-tximport.R"
    oracle_script.write_text(
        "library(tximport)\na<-commandArgs(trailingOnly=TRUE)\n"
        "f<-c(hisat2_fixture=a[[1]])\nm<-read.delim(a[[2]],check.names=FALSE)\n"
        "x<-tximport(f,type='stringtie',tx2gene=m,readLength=150,countsFromAbundance='no',txOut=FALSE,dropInfReps=TRUE)\n"
        "saveRDS(x,a[[3]])\n",
        encoding="utf-8",
    )
    subprocess.run(
        [str(r_bin / "Rscript"), "--vanilla", str(oracle_script), str(oracle_dir / "t_data.ctab"), str(mapping), str(oracle_rds)],
        check=True,
        capture_output=True,
        text=True,
    )
    compare_script = tmp_path / "compare.R"
    compare_script.write_text(
        "a<-commandArgs(trailingOnly=TRUE);x<-readRDS(a[[1]]);y<-readRDS(a[[2]])\n"
        "stopifnot(isTRUE(all.equal(x$counts,y$counts,tolerance=1e-12)))\n"
        "stopifnot(isTRUE(all.equal(x$abundance,y$abundance,tolerance=1e-12)))\n"
        "stopifnot(isTRUE(all.equal(x$length,y$length,tolerance=1e-12)))\n",
        encoding="utf-8",
    )
    subprocess.run(
        [str(r_bin / "Rscript"), "--vanilla", str(compare_script), str(oracle_rds), str(imported[3])],
        check=True,
        capture_output=True,
        text=True,
    )
    with imported[0].open(encoding="utf-8", newline="") as handle:
        rows = {row["gene_id"]: float(row["hisat2_fixture"]) for row in csv.DictReader(handle, delimiter="\t")}
    assert rows == {"geneA": 800.0, "geneB": 200.0, "geneC": 400.0}
    metadata = json.loads(imported[4].read_text(encoding="utf-8"))
    assert metadata["sample_ids"] == ["hisat2_fixture"]
    assert metadata["read_length"] == 150
    assert metadata["raw_counts"] is False
