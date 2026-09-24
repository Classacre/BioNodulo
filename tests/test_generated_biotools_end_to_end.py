"""Actual generated bio.tools nodes through discovery, readiness and API queue.

Opt in with BIONODULO_GENERATED_E2E_ROOT containing catalog.json/prefixes.json
and BIONODULO_GENERATED_E2E_CASES pointing at independently authored scientific
fixtures. Neither the registry, subprocess, execution queue nor result is mocked.
The cases select descriptors from the generated catalog, never construct wrappers.
"""
from __future__ import annotations

import hashlib
import csv
import gzip
import json
import os
from pathlib import Path
import shutil
import struct
import time
import zipfile

from fastapi.testclient import TestClient
import pytest

from bionodulo.nodes.contract.model import NodeSpec
from bionodulo.nodes.registry import NodeRegistry


GENERATED = os.environ.get("BIONODULO_GENERATED_E2E_ROOT")
CASES = os.environ.get("BIONODULO_GENERATED_E2E_CASES")
pytestmark = pytest.mark.skipif(not (GENERATED and CASES), reason="real generated catalog and independent fixture manifest required")


def _cases():
    if not CASES:
        return []
    cases = json.loads(Path(CASES).read_text())["cases"]
    compositions = Path(CASES).with_name("workflow-cases.json")
    return cases + (json.loads(compositions.read_text())["cases"] if compositions.exists() else [])


def _fasta(path: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    name = None
    for line in path.read_text().splitlines():
        if line.startswith(">"):
            name = line[1:].split()[0]
            assert name not in records, f"duplicate output FASTA identifier: {name}"
            records[name] = ""
        elif line.strip():
            assert name is not None, "sequence without a FASTA header"
            records[name] += line.strip()
    return records


def _artifact(path: Path):
    assert not path.is_symlink(), path
    if path.is_dir():
        entries = []
        for child in sorted(path.rglob("*")):
            assert not child.is_symlink() and (child.is_file() or child.is_dir()), child
            item = {"path": child.relative_to(path).as_posix(), "kind": "directory" if child.is_dir() else "file"}
            if child.is_file():
                item.update(sha256=hashlib.sha256(child.read_bytes()).hexdigest(), bytes=child.stat().st_size)
            entries.append(item)
        return {"path": str(path), "kind": "directory", "entries": entries,
                "sha256": hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()}
    assert path.is_file(), path
    return {"path": str(path), "kind": "file", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}


def _bam_alignments(path: Path):
    """Decode core fields independently of the tool under test (SAM/BAM 1.6)."""
    with gzip.open(path, "rb") as stream:
        assert stream.read(4) == b"BAM\x01"
        stream.read(struct.unpack("<i", stream.read(4))[0])
        references = []
        for _ in range(struct.unpack("<i", stream.read(4))[0]):
            references.append(stream.read(struct.unpack("<i", stream.read(4))[0])[:-1].decode())
            stream.read(4)
        records = []
        while size := stream.read(4):
            block_size = struct.unpack("<i", size)[0]
            block = stream.read(block_size)
            assert len(block) == block_size and block_size >= 32
            reference, position, bin_mapq_name, flag_cigar, length, mate_reference, mate_position, template_length = struct.unpack_from("<iiIIiiii", block)
            name_length, cigar_length = bin_mapq_name & 255, flag_cigar & 65535
            name = block[32:32 + name_length - 1].decode()
            offset = 32 + name_length
            cigar = "".join(f"{value >> 4}{'MIDNSHP=XB'[value & 15]}" for value in struct.unpack_from(f"<{cigar_length}I", block, offset)) or "*"
            offset += cigar_length * 4
            packed = block[offset:offset + (length + 1) // 2]
            sequence = "".join("=ACMGRSVTWYHKDBN"[nibble] for byte in packed for nibble in (byte >> 4, byte & 15))[:length] or "*"
            offset += len(packed)
            qualities = block[offset:offset + length]
            quality = "*" if not qualities or all(value == 255 for value in qualities) else "".join(chr(value + 33) for value in qualities)
            records.append([name, str(flag_cigar >> 16), references[reference] if reference >= 0 else "*", str(position + 1),
                            str((bin_mapq_name >> 8) & 255), cigar,
                            "*" if mate_reference < 0 else ("=" if mate_reference == reference else references[mate_reference]),
                            str(mate_position + 1), str(template_length), sequence, quality])
        return records


def _assert_output(value, oracle):
    paths = [Path(item) for item in value] if isinstance(value, list) else [Path(value)]
    assert all(path.exists() and not path.is_symlink() for path in paths), paths
    if "count" in oracle:
        assert len(paths) == oracle["count"]
    if "text" in oracle:
        assert len(paths) == 1 and paths[0].read_text() == oracle["text"]
    if "json_value" in oracle:
        assert len(paths) == 1
        actual = json.loads(paths[0].read_text())
        assert type(actual) is type(oracle["json_value"]) and actual == oracle["json_value"]
    if "sha256" in oracle:
        assert len(paths) == 1 and hashlib.sha256(paths[0].read_bytes()).hexdigest() == oracle["sha256"]
    if "fasta_records" in oracle:
        assert len(paths) == 1 and _fasta(paths[0]) == oracle["fasta_records"]
    if "zip_members" in oracle:
        assert len(paths) == 1
        with zipfile.ZipFile(paths[0]) as archive:
            for name, expected in oracle["zip_members"].items():
                assert archive.read(name).decode() == expected
    if "contains" in oracle:
        assert len(paths) == 1
        for text in oracle["contains"]:
            assert text in paths[0].read_text()
    if "json_fields" in oracle:
        assert len(paths) == 1
        actual = json.loads(paths[0].read_text())
        for key, expected in oracle["json_fields"].items():
            assert actual[key] == expected, (key, actual[key], expected)
    if "tsv_rows" in oracle:
        assert len(paths) == 1
        with paths[0].open() as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        key_column = oracle["tsv_rows"]["key"]
        indexed = {row[key_column]: row for row in rows}
        expected_rows = oracle["tsv_rows"]["rows"]
        assert len(indexed) == len(rows) and set(indexed) == set(expected_rows)
        for key, expected_row in expected_rows.items():
            for column, expected in expected_row.items():
                actual = indexed[key][column]
                assert (float(actual) == pytest.approx(expected, abs=1e-6) if isinstance(expected, (int, float)) else actual == expected), (key, column, actual, expected)
    if "directory_files" in oracle:
        assert len(paths) == 1 and paths[0].is_dir()
        assert oracle["directory_files"], "directory oracle needs independently checked contents"
        for relative, child_oracle in oracle["directory_files"].items():
            child = paths[0] / relative
            assert child.resolve().is_relative_to(paths[0].resolve()), relative
            _assert_output(str(child), child_oracle)
    if "sam_sequences" in oracle:
        assert len(paths) == 1
        sequences = {}
        for line in paths[0].read_text().splitlines():
            if line.startswith("@SQ\t"):
                tags = dict(field.split(":", 1) for field in line.split("\t")[1:])
                assert tags["SN"] not in sequences
                sequences[tags.pop("SN")] = tags
        assert set(sequences) == set(oracle["sam_sequences"])
        for name, expected in oracle["sam_sequences"].items():
            for key, value in expected.items():
                assert sequences[name][key] == str(value)
    if "sam_alignments" in oracle:
        assert len(paths) == 1
        records = [line.split("\t")[:11] for line in paths[0].read_text().splitlines() if line and not line.startswith("@")]
        if oracle.get("sam_alignment_order") == "exact":
            assert records == oracle["sam_alignments"]
        else:
            assert sorted(records) == sorted(oracle["sam_alignments"])
    if "bam_alignments" in oracle:
        assert len(paths) == 1
        assert sorted(_bam_alignments(paths[0])) == sorted(oracle["bam_alignments"])
    assert set(oracle) & {"text", "json_value", "sha256", "fasta_records", "zip_members", "contains", "count", "json_fields", "tsv_rows", "directory_files", "sam_sequences", "sam_alignments", "bam_alignments"}, "existence alone is not a scientific oracle"
    return [_artifact(path) for path in paths]


def _stage_fixture(value, destination, before, *, kind=None, array=False):
    """Copy explicit CWL filesystem objects, including objects nested in records."""
    if array:
        return [_stage_fixture(item, destination / str(index), before, kind=kind) for index, item in enumerate(value)]
    if kind in {"file", "directory"} and isinstance(value, str):
        value = {"class": kind.title(), "location": value}
    if isinstance(value, list):
        return [_stage_fixture(item, destination / str(index), before) for index, item in enumerate(value)]
    if not isinstance(value, dict):
        return value
    if value.get("class") not in {"File", "Directory"}:
        return {key: _stage_fixture(item, destination / key, before) for key, item in value.items()}
    location = value.get("location", value.get("path"))
    assert isinstance(location, str)
    source = Path(location) if Path(location).is_absolute() else Path(CASES).parent / location
    basename = value.get("basename", source.name)
    assert isinstance(basename, str) and Path(basename).name == basename
    target = destination / basename
    target.parent.mkdir(parents=True, exist_ok=True)
    artifact = _artifact(source)
    if artifact["kind"] == "directory":
        assert value["class"] == "Directory"
        shutil.copytree(source, target)
        for item in artifact["entries"]:
            if item["kind"] == "file":
                before[str((source / item["path"]).resolve())] = item["sha256"]
                before[str((target / item["path"]).resolve())] = item["sha256"]
    else:
        assert value["class"] == "File"
        shutil.copyfile(source, target)
        before[str(source.resolve())] = artifact["sha256"]
        before[str(target.resolve())] = artifact["sha256"]
    staged = {key: item for key, item in value.items() if key not in {"location", "path", "secondaryFiles"}}
    staged["location"] = str(target.resolve())
    if "secondaryFiles" in value:
        secondaries = value["secondaryFiles"]
        staged["secondaryFiles"] = [_stage_fixture(item, target.parent, before) for item in (secondaries if isinstance(secondaries, list) else [secondaries])]
    return staged


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["id"])
def test_generated_descriptor_through_product_queue(case, tmp_path, monkeypatch):
    bundle = Path(GENERATED) / "catalog.json"
    specs = [NodeSpec.model_validate_json(json.dumps(value)) for value in json.loads(bundle.read_text())["specs"]]
    steps = case.get("steps", [{"id": "generated", "descriptor": case.get("descriptor"), "inputs": case.get("inputs", {})}])
    selected = {}
    for step in steps:
        candidate = next((spec for spec in specs if spec.cwl_reference.source_uri.endswith("/" + step["descriptor"])), None)
        if candidate is None:
            pytest.skip(f"descriptor has no generated runtime; see generation failure ledger: {step['descriptor']}")
        selected[step["id"]] = candidate
    root = tmp_path / "app"
    root.mkdir()
    (root / "bionodulo.json").write_text(json.dumps({"execution": {
        "env_isolation": "auto", "max_workers": 1, "content_hashing": "strong",
    }}))
    for key, value in {
        "BIONODULO_ROOT": str(root), "BIONODULO_EDITOR_MODE": "0", "BIONODULO_CLOUD_MODE": "0",
        "BIONODULO_SESSION_TOKEN": "", "BIONODULO_PROXY_SECRET": "", "BIONODULO_REDIS_URL": "",
        "BIONODULO_EXECUTION_BACKEND": "local", "BIONODULO_DECLARATIVE_CATALOG": str(bundle),
        "BIONODULO_CWL_ENVIRONMENTS": (Path(GENERATED) / "prefixes.json").read_text(),
        "BIONODULO_ALLOW_UNVERIFIED_CWL": "1", "LC_ALL": "C",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(NodeRegistry, "_instance", None)
    before = {}
    workflow = {"name": case["id"], "nodes": [], "edges": []}
    for step in steps:
        candidate = selected[step["id"]]
        mappings = {item.cwl_id: item for item in candidate.cwl_reference.input_mappings}
        params = {}
        for key, value in step["inputs"].items():
            mapping = mappings[key]
            if isinstance(value, dict) and "from_step" in value:
                source = selected[value["from_step"]]
                source_port = next(item.port_id for item in source.cwl_reference.output_mappings if item.cwl_id == value["output"])
                workflow["edges"].append({"source": value["from_step"], "source_output": source_port,
                    "target": step["id"], "target_input": mapping.port_id})
                continue
            value = _stage_fixture(value, root / "fixture-inputs" / step["id"] / mapping.port_id,
                                   before, kind=mapping.kind, array=mapping.array)
            params[mapping.port_id] = value
        workflow["nodes"].append({"id": step["id"], "type": candidate.identity.machine_id, "params": params})
    from server import create_app
    with TestClient(create_app()) as client:
        info = client.get("/api/object_info").json()
        for candidate in selected.values():
            metadata = info[candidate.identity.machine_id]["declarative_runtime"]
            assert metadata["biotools_accession"] == candidate.cwl_reference.biotools_accession
            assert metadata["verification"] == "unverified"
        validation = client.post("/api/workflow/validate", json={"workflow": workflow})
        assert validation.status_code == 200 and validation.json()["valid"], validation.text
        readiness = client.post("/api/manager/resolve", json={"workflow": workflow})
        assert readiness.status_code == 200 and readiness.json()["execution_ready"], readiness.text
        prefixes = os.environ["BIONODULO_CWL_ENVIRONMENTS"]
        monkeypatch.setenv("BIONODULO_CWL_ENVIRONMENTS", "{}")
        missing = client.post("/api/manager/resolve", json={"workflow": workflow})
        assert missing.status_code == 200 and not missing.json()["execution_ready"], missing.text
        monkeypatch.setenv("BIONODULO_CWL_ENVIRONMENTS", prefixes)
        response = client.post("/api/runs", json={"workflow": workflow})
        assert response.status_code == 200, response.text
        run_id = response.json()["run_id"]
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            details = client.get(f"/api/runs/{run_id}").json()
            if details["status"] not in {"queued", "pending", "running"}:
                break
            time.sleep(0.1)
        evidence_dir = Path(os.environ.get("BIONODULO_GENERATED_E2E_EVIDENCE", str(root / "evidence")))
        evidence_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = evidence_dir / f"{case['id']}.json"
        evidence = {"case": case, "workflow": workflow, "run": details, "readiness": readiness.json(),
                    "missing_prefix_readiness": missing.json(), "verification": "fixture_not_yet_checked"}
        logs = []
        for source in sorted((root / "runs").rglob("*")):
            if source.is_file() and source.name in {"cwltool.stderr.log", "cwltool-result.json"}:
                destination = evidence_dir / "logs" / case["id"] / source.relative_to(root / "runs")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                logs.append(_artifact(destination))
        evidence["execution_logs"] = logs
        evidence_path.write_text(json.dumps(evidence, indent=2, default=str))
        assert details["status"] == "completed", details
        checks = {}
        for key, oracle in case["expected_outputs"].items():
            step_id, output_id = key.split(".", 1) if "steps" in case else ("generated", key)
            output_port = next(item.port_id for item in selected[step_id].cwl_reference.output_mappings if item.cwl_id == output_id)
            checks[key] = _assert_output(details["result"]["outputs"][step_id][output_port], oracle)
        assert checks, "case must check at least one independent output oracle"
        for key, artifacts in checks.items():
            for index, artifact in enumerate(artifacts):
                destination = evidence_dir / "outputs" / case["id"] / key / f"{index}-{Path(artifact['path']).name}"
                destination.parent.mkdir(parents=True, exist_ok=True)
                if artifact["kind"] == "directory":
                    shutil.copytree(artifact["path"], destination)
                else:
                    shutil.copyfile(artifact["path"], destination)
                assert _artifact(destination)["sha256"] == artifact["sha256"]
                artifact["retained_copy"] = str(destination)
        for path, digest in before.items():
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, "source input changed"
        for step_id, candidate in selected.items():
            reference = candidate.cwl_reference
            receipt = details["result"]["metadata"]["cwl_reference"][step_id]
            assert receipt["source_content_sha256"] == reference.source_content_sha256
            assert receipt["biotools_accession"] == reference.biotools_accession
            assert receipt["contract_digest"] == candidate.contract_digest()
        assert details["result"]["metadata"]["semantics"]["verification"] == "unverified"
        crate = client.get(f"/api/runs/{run_id}/ro-crate")
        assert crate.status_code == 200, crate.text
        evidence.update({"outputs": checks, "crate": crate.json(), "verification": "independent_fixture_passed"})
        evidence_path.write_text(json.dumps(evidence, indent=2, default=str))
