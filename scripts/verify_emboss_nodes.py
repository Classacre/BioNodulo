#!/usr/bin/env python
"""Run generated EMBOSS nodes in the pinned container and report which work.

Generated contracts are cheap; working commands are not. This executes each
node's **own** ``render_command`` argv inside the digest-pinned emboss image with
the network disabled and records, per node:

* the rendered argv,
* exit status, stdout and stderr,
* which of the node's declared ``OUTPUT_FILENAMES`` actually materialised.

A node counts as working only when it exits zero **and** produces every output it
declared. Exit status alone is not enough: a tool that exits zero and writes
nothing is worse than one that fails, because it looks like success.

This is a *smoke* check, not scientific validation. It establishes that the
command runs and its declared output appears. Whether the biology is right needs
an independent oracle.

Usage:
    python scripts/verify_emboss_nodes.py \
        --manifest reports/node-expansion/emboss-generated.json \
        --nodes seqret,getorf,sixpack,... \
        --fixture tests/nodes/emboss_family/fixtures/dna.fasta \
        --image quay.io/biocontainers/emboss:6.6.0--h0f19ade_14 \
        --digest sha256:a9bf499a... \
        --receipt-dir reports/run-receipts/emboss-batch
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bionodulo.nodes.registry import NodeRegistry  # noqa: E402

WORK = "/work"


def to_posix(argument: str) -> str:
    return argument.replace("\\", "/") if ("\\" in argument and "work" in argument) else argument


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--nodes", required=True, help="Comma-separated node ids.")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--receipt-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--input-port", default=None,
                        help="Explicit primary input port name. Overrides manifest lookup; "
                             "needed for families whose port is not named after an ACD param.")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    by_id = {r["node_id"]: r for r in manifest["records"]}

    work = args.receipt_dir / "work"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    (work / "out").mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.fixture, work / args.fixture.name)

    registry = NodeRegistry()
    results = []
    for node_id in [n.strip() for n in args.nodes.split(",") if n.strip()]:
        record = by_id.get(node_id)
        node_class = registry.get(node_id)
        entry: dict = {"node_id": node_id}
        if node_class is None or record is None:
            entry.update(status="missing", detail="node not resolvable")
            results.append(entry)
            continue

        out_dir = work / "out" / node_id
        out_dir.mkdir(parents=True, exist_ok=True)
        inputs: dict = {"output": f"{WORK}/out/{node_id}"}
        # Fill only the inputs the program actually REQUIRES. Injecting the fixture
        # into every declared input made needle, water, matcher and stretcher fail:
        # their optional ``-datafile`` is a substitution matrix, not a sequence, and
        # handing it DNA produced "Unable to read matrix".
        required_names = set(record.get("required_params") or [])
        if args.input_port:
            inputs[args.input_port] = f"{WORK}/{args.fixture.name}"
        else:
            for name in record.get("input_files") or []:
                if name in required_names:
                    inputs[name] = f"{WORK}/{args.fixture.name}"

        # Supply a placeholder for required scalar parameters so the smoke test
        # exercises the command. A node that legitimately needs a user-supplied
        # value still declares it as required; this only stops the harness from
        # reporting a validation failure as a broken command.
        try:
            declared_types = node_class.INPUT_TYPES()
        except Exception:  # noqa: BLE001
            declared_types = {}
        for name, spec in (declared_types.get("required") or {}).items():
            if name in inputs:
                continue
            declared = spec[0] if isinstance(spec, (list, tuple)) else spec
            if declared == "FILE":
                continue
            options = (spec[1] or {}).get("options") if isinstance(spec, tuple) and len(spec) > 1 else None
            if options:
                inputs[name] = options[0]
            elif declared in ("INT", "FLOAT"):
                inputs[name] = 1
            elif declared == "BOOLEAN":
                inputs[name] = True
            else:
                inputs[name] = "1"

        try:
            argv = [to_posix(a) for a in node_class.render_command(inputs)]
        except Exception as exc:  # noqa: BLE001
            entry.update(status="render_failed", detail=f"{type(exc).__name__}: {exc}"[:400])
            results.append(entry)
            continue

        try:
            completed = subprocess.run([
                "docker", "run", "--rm", "--network", "none", "--cpus", "1", "--memory", "2048m",
                "-v", f"{str(work.resolve()).replace(chr(92), '/')}:/work", "-w", WORK,
                "--entrypoint", "sh", f"{args.image}@{args.digest}",
                "-c", 'exec "$@"', "sh", *argv,
            ], capture_output=True, text=True, timeout=args.timeout, check=False)
        except subprocess.TimeoutExpired:
            # Some EMBOSS programs (taxgetdown, dbx*, cache*, embossupdate) fetch
            # remote reference data and simply hang with the network disabled.
            # Record that as a result instead of aborting the whole batch.
            entry.update({
                "argv": argv,
                "exit_code": None,
                "status": "failed",
                "stderr": f"timed out after {args.timeout}s (network disabled; this program "
                          "needs remote or installed reference data)",
                "expected_outputs": list(node_class.OUTPUT_FILENAMES),
                "produced": [],
                "missing_outputs": list(node_class.OUTPUT_FILENAMES),
            })
            results.append(entry)
            print(f"[{entry['status']:6s}] {node_id:26s} timeout", flush=True)
            continue

        # Mirror the executor's stdout capture: a node declaring
        # STDOUT_OUTPUT_INDEX writes that report to the planned output itself, so
        # the command legitimately creates nothing on disk.
        stdout_index = getattr(node_class, "STDOUT_OUTPUT_INDEX", None)
        if isinstance(stdout_index, int) and 0 <= stdout_index < len(node_class.OUTPUT_FILENAMES):
            target = out_dir / node_class.OUTPUT_FILENAMES[stdout_index]
            target.write_text(completed.stdout, encoding="utf-8")

        produced = sorted(p.name for p in out_dir.glob("*") if p.is_file())
        expected = list(node_class.OUTPUT_FILENAMES)
        missing = [name for name in expected if name not in produced]
        entry.update({
            "argv": argv,
            "exit_code": completed.returncode,
            "stdout_chars": len(completed.stdout),
            "stderr": completed.stderr.strip()[:400],
            "expected_outputs": expected,
            "produced": produced,
            "missing_outputs": missing,
            "status": "ok" if completed.returncode == 0 and not missing else "failed",
        })
        results.append(entry)
        print(f"[{entry['status']:6s}] {node_id:26s} exit={completed.returncode} "
              f"produced={len(produced)}/{len(expected)}", flush=True)

    ok = [r for r in results if r["status"] == "ok"]
    receipt = {
        "schema_version": 1,
        "image": args.image,
        "image_digest": args.digest,
        "fixture": args.fixture.name,
        "attempted": len(results),
        "ok": len(ok),
        "failed": len(results) - len(ok),
        "results": results,
        "scope": (
            "Smoke check only: the node's own argv ran in a pinned image and its declared "
            "outputs appeared. No scientific correctness was validated."
        ),
    }
    args.receipt_dir.mkdir(parents=True, exist_ok=True)
    (args.receipt_dir / "batch-receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"attempted": receipt["attempted"], "ok": receipt["ok"],
                      "failed": receipt["failed"]}, indent=2))


if __name__ == "__main__":
    main()
