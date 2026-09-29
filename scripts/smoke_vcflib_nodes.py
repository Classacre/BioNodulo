#!/usr/bin/env python
"""Run real vcflib operations in the pinned image and record what happened.

Generation is not admission. This executes a chain of vcflib tools on a small VCF
fixture inside the digest-pinned container and reports, per tool, the exit code and
how many non-header output lines came back. It is a smoke test, not a scientific
validation: the fixture is three hand-written records, so a tool that returns
plausible output has been shown to run, not to be correct.

Usage:
    python scripts/smoke_vcflib_nodes.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dump_tool_help import _shell_quote, run_in_image  # noqa: E402

IMAGE = ("quay.io/biocontainers/vcflib@sha256:"
         "838ddab39b0af484f51c1b08f032f47e4ca9e402a8d36d1d4c6f7c46e031d034")

VCF_LINES = [
    "##fileformat=VCFv4.2",
    "##contig=<ID=chr1,length=1000>",
    # INFO fields must be typed or vcffilter refuses to compare them
    # ("cannot compare (>) objects of dissimilar types").
    '##INFO=<ID=DP,Number=1,Type=Integer,Description="Total Depth">',
    '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
    '##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Depth">',
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\ts1\ts2",
    "chr1\t100\trs1\tA\tG\t50\tPASS\tDP=30\tGT:DP\t0/1:15\t1/1:15",
    "chr1\t200\trs2\tC\tT\t60\tPASS\tDP=40\tGT:DP\t0/0:20\t0/1:20",
    "chr1\t300\trs3\tG\tA\t70\tPASS\tDP=25\tGT:DP\t1/1:10\t0/1:15",
]
# A reference FASTA so vcfcheck has something to verify REF against.
FASTA_LINES = [
    ">chr1",
    "N" * 99 + "A" + "N" * 99 + "C" + "N" * 99 + "G" + "N" * 690,
]
# The GPAT++ tools need genotype likelihoods and one sample per tree leaf, so they
# get their own four-sample fixture with PL.
GPA_FOUR = [
    "##fileformat=VCFv4.2",
    "##contig=<ID=chr1,length=1000>",
    '##INFO=<ID=DP,Number=1,Type=Integer,Description="Total Depth">',
    '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
    '##FORMAT=<ID=PL,Number=G,Type=Integer,Description="Phred-scaled likelihoods">',
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\ta\tb\tc\td",
    "chr1\t100\trs1\tA\tG\t50\tPASS\tDP=30\tGT:PL\t0/1:10,20,30\t1/1:40,30,0\t0/0:0,30,40\t0/1:20,10,20",
    "chr1\t200\trs2\tC\tT\t60\tPASS\tDP=40\tGT:PL\t0/0:0,40,50\t0/1:10,30,40\t1/1:50,20,0\t0/0:0,25,35",
    "chr1\t300\trs3\tG\tA\t70\tPASS\tDP=25\tGT:PL\t1/1:45,25,0\t0/1:15,20,25\t0/0:0,35,45\t1/1:40,15,0",
]

# (label, argv, whether a nonzero exit is expected)
KNOWN_DEFECTS = {
    "vcfinfosummarize": (
        "segfaults (exit 139) on every valid invocation in the pinned 1.0.15 image, "
        "with -f/-i and with -a/-m; `vcfinfosummarize --help` exits 0, so the crash "
        "is in the tool rather than in the node's command"
    ),
}
CHAIN: list[tuple[str, list[str], bool]] = [
    ("vcf2tsv", ["vcf2tsv", "-g", "t.vcf"], False),
    ("vcfcheck", ["vcfcheck", "-f", "ref.fa", "t.vcf"], False),
    ("vcffilter", ["vcffilter", "-f", "DP > 20", "t.vcf"], False),
    ("vcffilter QUAL", ["vcffilter", "-f", "QUAL > 55", "t.vcf"], False),
    ("vcfcat", ["vcfcat", "t.vcf", "u.vcf"], False),
    ("vcfstats", ["vcfstats", "t.vcf"], False),
    ("vcfnumalt", ["vcfnumalt", "t.vcf"], False),
    ("vcffixup", ["vcffixup", "t.vcf"], False),
    ("vcflength", ["vcflength", "t.vcf"], False),
    ("vcfcountalleles", ["vcfcountalleles", "t.vcf"], False),
    ("vcfhetcount", ["vcfhetcount", "t.vcf"], False),
    ("vcfallelicprimitives", ["vcfallelicprimitives", "t.vcf"], False),
    ("vcfbreakmulti", ["vcfbreakmulti", "t.vcf"], False),
    ("vcfkeepsamples", ["vcfkeepsamples", "t.vcf", "s1"], False),
    ("vcfremovesamples", ["vcfremovesamples", "t.vcf", "s2"], False),
    ("vcfecho", ["vcfecho", "t.vcf"], False),
    ("vcfsort", ["vcfsort", "t.vcf"], False),
    ("vcfstreamsort", ["vcfstreamsort", "t.vcf"], False),
    ("vcfuniq", ["vcfuniq", "t.vcf"], False),
    # vcfinfosummarize segfaults in the pinned image on every valid invocation
    # (exit 139). Kept in the chain rather than removed, so the manifest records a
    # real failure instead of a clean sweep.
    ("vcfinfosummarize", ["vcfinfosummarize", "-f", "DP", "-i", "SUMM", "t.vcf"], False),
    ("vcfgenosamplenames", ["vcfgenosamplenames", "t.vcf"], False),
    ("vcfnumalt", ["vcfnumalt", "t.vcf"], False),
    # The GPAT++ dialect. These take their input through --file rather than a
    # positional argument, which is why the generator maps that flag to the input port.
    ("abba-baba", ["abba-baba", "--tree", "0,1,2,3", "--file", "q.vcf", "--type", "PL"], False),
    ("genotypeSummary", ["genotypeSummary", "--target", "0,1,2,3", "--file", "q.vcf",
                         "--type", "PL", "--snp"], False),
    ("pFst", ["pFst", "--target", "0,1", "--background", "2,3", "--file", "q.vcf",
              "--type", "PL"], False),
    # A probed value flag: --info-filter takes an expression while --filter-sites is a
    # switch. Before the probe both were typed as switches and the expression was lost.
    # (--keep-info is also a switch but is only legal alongside --genotype-filter.)
    ("vcffilter probed", ["vcffilter", "--info-filter", "DP > 20", "--filter-sites", "t.vcf"],
     False),
    # Reads stdin, so it is one of the tools the generator deliberately skips. Run
    # it with a redirect here to show the mechanism works and the skip is about the
    # node contract, not the tool.
    ("vcfdistance (stdin)", None, False),
]


def build_setup() -> str:
    """Write the fixtures with printf so no host mount is needed."""
    def printf(path: str, lines: list[str]) -> str:
        payload = "\\n".join(line.replace("\\", "\\\\").replace("%", "%%")
                             for line in lines)
        return f"printf '{payload}\\n' > {path};"
    return "cd /tmp && " + printf("t.vcf", VCF_LINES) + printf("u.vcf", VCF_LINES) \
        + printf("q.vcf", GPA_FOUR) + printf("ref.fa", FASTA_LINES)


def main() -> int:
    setup = build_setup()
    code, out = run_in_image(IMAGE, ["sh", "-c", setup + " wc -l t.vcf ref.fa"], 90)
    if code != 0:
        print(f"fixture setup failed (exit {code}):\n{out[:500]}")
        return 1
    print(f"fixtures written: {out.strip().splitlines()[:2]}")

    results = []
    for label, argv, expect_fail in CHAIN:
        # Quote every token. Joining with spaces let `-f "DP > 20"` become a shell
        # redirect, which failed vcffilter and looked like a tool defect.
        if argv is None:
            command = setup + " vcfdistance < t.vcf"
        else:
            command = setup + " " + _shell_quote(argv)
        exit_code, output = run_in_image(IMAGE, ["sh", "-c", command], 120)
        body = [line for line in output.splitlines()
                if line.strip() and not line.startswith(("#", "##"))]
        ok = exit_code == 0 or expect_fail
        results.append({
            "tool": label,
            "argv": argv,
            "exit_code": exit_code,
            "output_lines": len(body),
            "first_line": body[0][:160] if body else "",
            "ran": ok,
            "known_defect": KNOWN_DEFECTS.get(label),
        })
        flag = "ok " if ok else "FAIL"
        print(f"{flag} {label:24s} exit={exit_code:<3d} lines={len(body):<4d} "
              f"{body[0][:70] if body else '(no non-header output)'}")

    ran = sum(1 for r in results if r["ran"])
    failed = [r for r in results if not r["ran"]]
    manifest = {
        "schema_version": 1,
        "image": IMAGE,
        "fixture": "3-record VCF on chr1 plus a 1000 bp reference FASTA",
        "scope": (
            "Smoke test only. Exit 0 with plausible output shows the tool runs in the "
            "pinned image; it is not evidence that the output is scientifically correct."
        ),
        "tools_run": len(results),
        "tools_exited_zero": ran,
        "failures": [{"tool": r["tool"], "exit_code": r["exit_code"],
                      "known_defect": r["known_defect"]} for r in failed],
        "results": results,
    }
    out_path = Path("reports/node-expansion/vcflib-smoke.json")
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\n{ran}/{len(results)} tools exited 0")
    for r in failed:
        print(f"  failed: {r['tool']} exit={r['exit_code']} "
              f"known_defect={'yes' if r['known_defect'] else 'NO'}")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
