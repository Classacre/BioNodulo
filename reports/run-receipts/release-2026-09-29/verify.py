"""Recheck the bounded release smoke sample and its independent expectations."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
IMAGE = "quay.io/biocontainers/unikmer@sha256:92654c4223ba021d9d11493de3d1aae84cef2710037a8d052cd33ed4cea29136"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def view(path: Path) -> list[str]:
    work = path.parents[2]
    rel = path.relative_to(work).as_posix()
    result = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "-v",
         f"{work.resolve().as_posix()}:/work", "--entrypoint", "unikmer",
         IMAGE, "view", f"/work/{rel}"],
        capture_output=True, text=True, check=True, timeout=120,
    )
    return result.stdout.splitlines()


def main() -> None:
    node_ids = ["unikmer-encode", "unikmer-count", "unikmer-count-taxid",
                "unikmer-split", "unikmer-grep", "unikmer-tsplit",
                "taxonkit-list", "seqfu-shred", "csvtk-cut", "seqkit-mutate",
                "vcflib-vcfuniq", "htslib-tabix-query", "emboss-water",
                "emboss-water-brief-false"]
    checks = {}
    for name in node_ids:
        receipt = json.loads((ROOT / name / "receipt.json").read_text(encoding="utf-8"))
        work = ROOT / name
        checks[f"{name}_receipt"] = (
            receipt["status"] == "completed"
            and receipt["exit_code"] == 0
            and receipt["execution"]["digest_stable"]
            and not receipt["missing_planned_outputs"]
            and not receipt["output_verification_error"]
            and all(sha(work / item["path"]) == item["sha256"]
                    for item in receipt["artifacts"])
        )

    source = (ROOT / "fixtures/mini.fa").read_text(encoding="ascii").splitlines()[1]
    expected_kmers = {source[i:i + 3] for i in range(len(source) - 2)}
    count_output = ROOT / "unikmer-count/work/out/unikmer_count/unikmer_count.out"
    generated_fixture = ROOT / "fixtures/mini.unik"
    checks["count_matches_independent_fixture"] = sha(count_output) == sha(generated_fixture)
    chunk_dir = ROOT / "unikmer-split/work/out/unikmer_split"
    chunk_paths = sorted(chunk_dir.glob("*.unik"))
    checks["split_kmer_set"] = (
        len(chunk_paths) == 2
        and set(kmer for path in chunk_paths for kmer in view(path)) == expected_kmers
    )
    grep_path = ROOT / "unikmer-grep/work/out/unikmer_grep/output.unik"
    checks["grep_selects_query"] = (
        grep_path.is_file() and set(view(grep_path)) == {"ACG"}
    )
    tsplit_path = ROOT / "unikmer-tsplit/work/out/unikmer_tsplit/tsplit.taxid-562.k3.unik"
    checks["tsplit_taxid_and_kmers"] = (
        tsplit_path.is_file() and set(view(tsplit_path)) == expected_kmers
    )
    taxon_output = (ROOT / "taxonkit-list/work/out/taxonkit_list/taxonkit_list.out")
    checks["taxonkit_subtree"] = taxon_output.read_text(encoding="utf-8").rstrip().splitlines() == [
        "2 [superkingdom] Bacteria", "  562 [species] Escherichia coli"]
    shred_dir = ROOT / "seqfu-shred/work/out/seqfu_shred"
    reads = []
    for name in ["output_R1.fq", "output_R2.fq"]:
        lines = (shred_dir / name).read_text(encoding="ascii").splitlines()
        checks[f"shred_{name}"] = (
            len(lines) == 8 and all(lines[i].startswith("@read1_") and
                                    lines[i + 1] == "ACGTACGT" and
                                    lines[i + 2] == "+" and
                                    lines[i + 3] == "I" * 8
                                    for i in (0, 4))
        )
        reads.append(lines)
    checks["shred_paired_count"] = len(reads[0]) == len(reads[1]) == 8

    table = (ROOT / "csvtk-cut/work/mini_table.tsv").read_text(encoding="ascii").splitlines()
    selected = (ROOT / "csvtk-cut/work/out/csvtk_cut/selected.tsv").read_text(encoding="ascii").splitlines()
    indexes = [table[0].split("\t").index(name) for name in ("gene", "sample")]
    checks["csvtk_selected_columns"] = selected == [
        "\t".join(row.split("\t")[index] for index in indexes) for row in table]
    mutated = (ROOT / "seqkit-mutate/work/out/seqkit_mutate/seqkit_mutate.out").read_text(encoding="ascii").splitlines()
    checks["seqkit_point_mutation"] = mutated == [">read1", source[0] + "T" + source[2:]]
    vcf_input = (ROOT / "vcflib-vcfuniq/work/mini.vcf").read_text(encoding="ascii").splitlines()
    vcf_output = (ROOT / "vcflib-vcfuniq/work/out/vcflib_vcfuniq/vcflib_vcfuniq.out").read_text(encoding="ascii").splitlines()
    checks["vcflib_preserves_unique_records"] = vcf_output == vcf_input
    queried = (ROOT / "htslib-tabix-query/work/out/tabix_query/records.tsv").read_text(encoding="ascii").splitlines()
    expected_region = [line for line in vcf_input if not line.startswith("#") and
                       line.split("\t")[0] == "chr1" and
                       100 <= int(line.split("\t")[1]) <= 200]
    checks["htslib_region_query"] = queried == expected_region
    alignment = (ROOT / "emboss-water/work/out/emboss_water/outfile.out").read_text(encoding="ascii")
    checks["emboss_identical_alignment"] = (
        re.search(r"# Length:\s*12\b", alignment) is not None and
        re.search(r"# Identity:\s*12/12\s*\(100\.0%\)", alignment) is not None
    )
    explicit_false = json.loads((ROOT / "emboss-water-brief-false/receipt.json").read_text(encoding="utf-8"))
    false_alignment = (ROOT / "emboss-water-brief-false/work/out/emboss_water/outfile.out").read_text(encoding="ascii")
    checks["emboss_explicit_false"] = (
        explicit_false["rendered_command"][-3:] == ["-brief", "N", "-auto"]
        and re.search(r"# Identity:\s*12/12\s*\(100\.0%\)", false_alignment) is not None
    )

    result = {"schema_version": 1, "checks": checks,
              "passed": all(checks.values()),
              "scope": "Pinned local Docker command execution and independent tiny-fixture content checks; no app queue or cloud claim."}
    (ROOT / "oracle.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
