"""Opt-in, real Linux tools and executor acceptance tests; no command mocks.

Run with BIONODULO_REAL_TOOLCHAINS=1 in the pinned environment documented in
phd-implementation-2026-09-23. Missing binaries then fail rather than skip.
Synthetic unique transcripts give hand-computable read counts, including a
spliced case with unequal transcript lengths and a reverse-strand gene;
independent upstream commands additionally check adapter fidelity. These are
bounded algorithm fixtures, not validation of a biological study.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.registry import NodeRegistry

pytestmark = pytest.mark.skipif(
    os.environ.get("BIONODULO_REAL_TOOLCHAINS") != "1",
    reason="explicit real scientific toolchain environment required",
)


def command(args, cwd):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=180)
    log = cwd / "oracle-commands.jsonl"
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"argv": args, "exit": result.returncode,
                                 "stdout": result.stdout, "stderr": result.stderr}) + "\n")
    assert result.returncode == 0, result.stderr + result.stdout
    return result.stdout


def engine(root):
    return WorkflowExecutor(
        workspace_dir=root, registry=NodeRegistry.create_isolated(),
        settings=SimpleNamespace(execution=SimpleNamespace(
            max_workers=1, env_isolation="off", content_hashing="strong"), api_secrets={}),
    )


def edge(source, output, target, input_name):
    return {"source": source, "source_output": output, "target": target, "target_input": input_name}


def run(root, workflow):
    result = asyncio.run(engine(root / "engine").execute("real", workflow, force=True))
    (root / "app-result.json").write_text(json.dumps(result, indent=2, default=str))
    assert result["status"] == "completed", json.dumps(result, default=str)[-14000:]
    return result


def table(path, key):
    with Path(path).open(encoding="utf-8") as handle:
        return {row[key]: row for row in csv.DictReader(
            (line for line in handle if not line.startswith("#")), delimiter="\t")}


def verify_runtime_versions(root):
    """Record the binaries resolved on this PATH; reject a different release."""
    checks = {
        "STAR": (["--version"], r"^2\.7\.11b\s*$"),
        "hisat2": (["--version"], r"\bversion 2\.2\.2\b"),
        "samtools": (["--version"], r"^samtools 1\.23\.1\s"),
        "featureCounts": (["-v"], r"\bfeatureCounts v2\.1\.1\b"),
        "salmon": (["--version"], r"^salmon 2\.3\.4\s"),
        "stringtie": (["--version"], r"^3\.0\.3\s*$"),
    }
    receipt = {}
    for binary, (args, expected) in checks.items():
        resolved = shutil.which(binary)
        assert resolved, f"missing pinned executable: {binary}"
        version = subprocess.run([resolved, *args], text=True, capture_output=True, timeout=30)
        output = version.stdout + version.stderr
        assert version.returncode == 0 and re.search(expected, output), (binary, output)
        with Path(resolved).resolve().open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        receipt[binary] = {"path": resolved, "sha256": digest, "version_output": output}
    # HISAT2 is a Python launcher; record the actual align/build binaries too.
    for binary in ("hisat2-align-s", "hisat2-build", "hisat2-build-s", "Rscript"):
        resolved = shutil.which(binary)
        assert resolved, binary
        with Path(resolved).resolve().open("rb") as handle:
            receipt[binary] = {"path": resolved, "sha256": hashlib.file_digest(handle, "sha256").hexdigest()}
    r_versions = command(["Rscript", "--vanilla", "-e",
                          'cat(as.character(getRversion()), as.character(packageVersion("tximport")), '
                          'as.character(packageVersion("jsonlite")), sep="\\t")'], root)
    assert r_versions.strip().split("\t") == ["4.5.3", "1.38.2", "2.0.0"]
    receipt["R_packages"] = {"R": "4.5.3", "tximport": "1.38.2", "jsonlite": "2.0.0"}
    (root / "runtime-versions.json").write_text(json.dumps(receipt, indent=2))


@pytest.fixture(params=["single_exon", "spliced_unequal_lengths"])
def fixture(tmp_path, monkeypatch, request):
    # Keep reference caches and tool-created configuration in the test workspace.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    verify_runtime_versions(tmp_path)
    rng = random.Random(20260923)
    expected = {"geneA": 800, "geneB": 200, "geneC": 400}
    genomes, transcripts, annotation, reads, tx2gene = [], [], [], [], []
    complement = str.maketrans("ACGT", "TGCA")
    gene_lengths = {}
    for index, (gene, count) in enumerate(expected.items()):
        chrom, tx = f"chr{index + 1}", f"tx{index + 1}"
        genome = "".join(rng.choice("ACGT") for _ in range(4000))
        strand = "-" if index == 2 else "+"
        length = 800 if request.param == "single_exon" else 600 + 200 * index
        gene_lengths[gene] = length
        exons = [(1000, 1800)] if request.param == "single_exon" else [(1000, 1300), (1800, 1800 + length - 300)]
        if len(exons) == 2:
            # Canonical intron motifs on the transcript strand.
            donor, acceptor = ("GT", "AG") if strand == "+" else ("CT", "AC")
            genome = genome[:1300] + donor + genome[1302:1798] + acceptor + genome[1800:]
        transcript = "".join(genome[start:end] for start, end in exons)
        if strand == "-":
            transcript = transcript.translate(complement)[::-1]
        genomes.append(f">{chrom}\n{genome}\n")
        transcripts.append(f">{tx}\n{transcript}\n")
        for start, end in exons:
            annotation.append(f'{chrom}\tfixture\texon\t{start + 1}\t{end}\t.\t{strand}\t.\tgene_id "{gene}"; transcript_id "{tx}";\n')
        tx2gene.append(f"{tx}\t{gene}\n")
        junction = 300 if strand == "+" else length - 300
        starts = [start for start in range(length - 149)
                  if len(exons) == 1 or not (start < junction < start + 150)
                  or min(junction - start, start + 150 - junction) >= 30]
        for n in range(count):
            start = rng.choice(starts)
            sequence = transcript[start:start + 150]
            reads.append(f"@{gene}_{n}\n{sequence}\n+\n{'I' * 150}\n")
    rng.shuffle(reads)
    contents = {"reference.fa": "".join(genomes), "transcripts.fa": "".join(transcripts),
                "annotation.gtf": "".join(annotation), "reads.fastq": "".join(reads),
                "tx2gene.tsv": "transcript_id\tgene_id\n" + "".join(tx2gene)}
    for name, content in contents.items():
        (tmp_path / name).write_text(content, encoding="ascii")
    (tmp_path / "truth.json").write_text(json.dumps({
        "seed": 20260923, "counts": expected, "read_length": 150,
        "fixture": request.param, "gene_lengths": gene_lengths, "negative_strand": "geneC",
        "sha256": {name: hashlib.sha256(content.encode("ascii")).hexdigest()
                   for name, content in contents.items()},
    }, indent=2))
    return tmp_path, expected


@pytest.mark.parametrize("aligner", ["star", "hisat2"])
def test_real_alignment_counting_matches_truth_and_independent_cli(fixture, aligner):
    root, expected = fixture
    required = ["samtools", "featureCounts", "STAR" if aligner == "star" else "hisat2",
                "STAR" if aligner == "star" else "hisat2-build"]
    assert all(shutil.which(binary) for binary in required), required
    reference, gtf, reads = (str(root / name) for name in ("reference.fa", "annotation.gtf", "reads.fastq"))
    index_type = "star_index" if aligner == "star" else "hisat2_build"
    params = {"reference": reference, "threads": 1}
    if aligner == "star":
        params.update(gtf=gtf, genome_sa_index_nbases=4, sjdb_overhang=149)
    nodes = [{"id": "index", "type": index_type, "params": params},
             {"id": "align", "type": f"{aligner}_align", "params": {"reads": [reads], "threads": 1}},
             {"id": "counts", "type": "featurecounts", "params": {
                 "gtf": gtf, "threads": 1, "strand_specificity": "0",
                 "include_feature_length_file": True, "format": "tabdel_short"}},
             {"id": "stats", "type": "samtools_flagstat", "params": {"threads": 1}}]
    edges = [edge("index", "index", "align", "index")]
    alignment_node, alignment_port = "align", "alignment"
    if aligner == "hisat2":
        assert shutil.which("stringtie") and shutil.which("Rscript"), "pinned StringTie and R required"
        nodes.append({"id": "sort", "type": "samtools_sort", "params": {"threads": 1, "memory_per_thread": "64M"}})
        edges.append(edge("align", "alignment", "sort", "alignment"))
        alignment_node, alignment_port = "sort", "sorted_bam"
        nodes[1]["params"]["dta"] = True
        nodes.extend([
            {"id": "stringtie", "type": "stringtie", "params": {
                "gtf": gtf, "threads": 1, "reference_abundance": True}},
            {"id": "import", "type": "tximport_stringtie", "params": {
                "sample_ids": ["sample1"], "tx2gene": str(root / "tx2gene.tsv"),
                "reference_gtf": gtf,
                "read_length": 150.0, "counts_from_abundance": "no"}},
        ])
        edges.extend([edge("sort", "sorted_bam", "stringtie", "bam"),
                      edge("stringtie", "transcript_abundance", "import", "ctab_files")])
    edges.extend([edge(alignment_node, alignment_port, "counts", "alignment"),
                  edge(alignment_node, alignment_port, "stats", "bam")])
    result = run(root, {"name": f"Real {aligner} counting fixture", "nodes": nodes, "edges": edges})
    observed = table(result["outputs"]["counts"]["counts"], "Geneid")
    actual_counts = {gene: int(next(value for key, value in row.items() if key != "Geneid"))
                     for gene, row in observed.items()}
    assert actual_counts == expected
    lengths = table(result["outputs"]["counts"]["feature_lengths"], "Geneid")
    truth = json.loads((root / "truth.json").read_text())
    assert {gene: int(row["Length"]) for gene, row in lengths.items()} == truth["gene_lengths"]
    bam = result["outputs"][alignment_node][alignment_port]
    command(["samtools", "quickcheck", "-v", bam], root)
    assert int(command(["samtools", "view", "-c", "-F", "4", bam], root)) == sum(expected.values())
    assert f"{sum(expected.values())} + 0 mapped" in Path(result["outputs"]["stats"]["stats"]).read_text()
    oracle = root / "oracle"
    oracle.mkdir()
    if aligner == "star":
        index = oracle / "index"
        index.mkdir()
        command(["STAR", "--runMode", "genomeGenerate", "--genomeDir", str(index),
                 "--genomeFastaFiles", reference, "--sjdbGTFfile", gtf,
                 "--runThreadN", "1", "--genomeSAindexNbases", "4", "--sjdbOverhang", "149"], root)
        command(["STAR", "--genomeDir", str(index), "--readFilesIn", reads,
                 "--outFileNamePrefix", str(oracle) + "/", "--outSAMtype", "BAM", "SortedByCoordinate",
                 "--runThreadN", "1", "--twopassMode", "Basic"], root)
        oracle_bam = oracle / "Aligned.sortedByCoord.out.bam"
    else:
        prefix = str(oracle / "index")
        command(["hisat2-build", "-p", "1", reference, prefix], root)
        command(["hisat2", "--dta", "-p", "1", "-x", prefix, "-U", reads, "-S", str(oracle / "alignment.sam")], root)
        oracle_bam = oracle / "sorted.bam"
        command(["samtools", "sort", "-@", "1", "-m", "64M", "-o", str(oracle_bam), str(oracle / "alignment.sam")], root)
    command(["featureCounts", "-a", gtf, "-o", str(oracle / "counts.tsv"), "-T", "1", "-s", "0", str(oracle_bam)], root)
    direct = table(oracle / "counts.tsv", "Geneid")
    assert {gene: int(row[str(oracle_bam)]) for gene, row in direct.items()} == expected
    # Compare alignment content independent of generated timestamps / @PG paths.
    app_sam = sorted(command(["samtools", "view", bam], root).splitlines())
    cli_sam = sorted(command(["samtools", "view", str(oracle_bam)], root).splitlines())
    assert app_sam == cli_sam
    if truth["fixture"] == "spliced_unequal_lengths":
        assert sum("N" in row.split("\t")[5] for row in app_sam) > 100
    if aligner == "hisat2":
        # Quantification is indispensable: alignments are not tximport inputs.
        command(["stringtie", str(oracle_bam), "-G", gtf,
                 "-o", str(oracle / "transcripts.gtf"), "-A", str(oracle / "genes.tsv"),
                 "-p", "1", "-e", "-B", "-f", "0.01"], root)
        observed_ctab = table(result["outputs"]["stringtie"]["transcript_abundance"], "t_name")
        assert observed_ctab == table(oracle / "t_data.ctab", "t_name")
        assert {tx: float(row["cov"]) * float(row["length"]) / 150
                for tx, row in observed_ctab.items()} == {"tx1": 800, "tx2": 200, "tx3": 400}
        direct_r = oracle / "direct-stringtie-tximport.R"
        direct_r.write_text('''args <- commandArgs(TRUE)
mapping <- read.delim(args[2], check.names=FALSE)
txi <- tximport::tximport(c(sample1=args[1]), type="stringtie", tx2gene=mapping,
                         readLength=150, countsFromAbundance="no", dropInfReps=TRUE)
saveRDS(txi, args[3])
app <- readRDS(args[4])
for (kind in c("counts", "abundance", "length")) {
  stopifnot(isTRUE(all.equal(txi[[kind]], app[[kind]], tolerance=1e-12)))
}
''', encoding="ascii")
        command(["Rscript", "--vanilla", str(direct_r), str(oracle / "t_data.ctab"),
                 str(root / "tx2gene.tsv"), str(oracle / "direct-tximport.rds"),
                 result["outputs"]["import"]["tximport_object"]], root)
        imported = table(result["outputs"]["import"]["gene_count_scale"], "gene_id")
        assert {gene: float(row["sample1"]) for gene, row in imported.items()} == expected
        metadata = json.loads(Path(result["outputs"]["import"]["import_metadata"]).read_text())
        assert metadata["sample_ids"] == ["sample1"]
        assert metadata["read_length"] == 150
        assert metadata["raw_counts"] is False


def test_real_salmon_quantification_matches_truth_and_independent_cli(fixture):
    root, counts = fixture
    assert shutil.which("salmon"), "pinned Salmon required"
    assert shutil.which("Rscript"), "pinned R/tximport environment required"
    workflow = {"name": "Real Salmon fixture", "nodes": [
        {"id": "index", "type": "salmon_index", "params": {
            "transcripts": [str(root / "transcripts.fa")], "threads": 1, "kmer": 31}},
        {"id": "quant", "type": "salmon_quant", "params": {
            "reads": [str(root / "reads.fastq")], "threads": 1, "single_end": True, "lib_type": "U"}},
        {"id": "import", "type": "tximport_salmon", "params": {
            "sample_ids": ["sample1"], "tx2gene": str(root / "tx2gene.tsv"),
            "counts_from_abundance": "no"}},
    ], "edges": [edge("index", "index", "quant", "index"),
                 edge("quant", "counts", "import", "quant_files")]}
    result = run(root, workflow)
    observed = table(result["outputs"]["quant"]["counts"], "Name")
    truth = json.loads((root / "truth.json").read_text())
    for tx, gene in zip(("tx1", "tx2", "tx3"), counts):
        assert float(observed[tx]["NumReads"]) == pytest.approx(counts[gene], abs=0.01)
        assert float(observed[tx]["Length"]) == truth["gene_lengths"][gene]
    assert sum(float(row["TPM"]) for row in observed.values()) == pytest.approx(1e6, abs=0.1)
    oracle = root / "oracle"
    oracle.mkdir()
    command(["salmon", "index", "-t", str(root / "transcripts.fa"), "-i", str(oracle / "index"), "-p", "1", "-k", "31"], root)
    command(["salmon", "quant", "-i", str(oracle / "index"), "-l", "U", "-r", str(root / "reads.fastq"), "-o", str(oracle / "quant"), "-p", "1"], root)
    direct = table(oracle / "quant/quant.sf", "Name")
    assert observed.keys() == direct.keys()
    for tx in observed:
        for key in ("Length", "EffectiveLength", "TPM", "NumReads"):
            assert float(observed[tx][key]) == pytest.approx(float(direct[tx][key]), rel=1e-7, abs=1e-5)
    # A distinct upstream R process imports the independent CLI's quant.sf.
    # Check all matrices, preserving the RDS for proper downstream length offsets.
    oracle_script = oracle / "direct-tximport.R"
    oracle_script.write_text('''args <- commandArgs(TRUE)
files <- c(sample1 = args[1])
mapping <- read.delim(args[2], check.names = FALSE)
txi <- tximport::tximport(files, type="salmon", tx2gene=mapping,
                         countsFromAbundance="no", dropInfReps=TRUE)
saveRDS(txi, file.path(args[3], "direct-tximport.rds"))
for (kind in c("counts", "abundance", "length")) {
  d <- data.frame(gene_id=rownames(txi[[kind]]), txi[[kind]], check.names=FALSE)
  write.table(d, file.path(args[3], paste0(kind, ".tsv")), sep="\\t", quote=FALSE, row.names=FALSE)
}
''', encoding="ascii")
    command(["Rscript", "--vanilla", str(oracle_script), str(oracle / "quant/quant.sf"),
             str(root / "tx2gene.tsv"), str(oracle)], root)
    for port, oracle_name in (("gene_count_scale", "counts"),
                              ("gene_abundance_tpm", "abundance"),
                              ("gene_effective_length", "length")):
        imported = table(result["outputs"]["import"][port], "gene_id")
        reference = table(oracle / f"{oracle_name}.tsv", "gene_id")
        assert imported.keys() == reference.keys() == counts.keys()
        for gene in imported:
            assert float(imported[gene]["sample1"]) == pytest.approx(
                float(reference[gene]["sample1"]), rel=1e-10, abs=1e-8)
            if oracle_name == "counts":
                assert float(imported[gene]["sample1"]) == pytest.approx(counts[gene], abs=0.01)
    assert Path(result["outputs"]["import"]["tximport_object"]).stat().st_size > 0
