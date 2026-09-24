"""Identity joins, immutable inputs and cohort denominators cannot be guessed."""
import hashlib
import json
import pytest

from bionodulo.nodes import generate_registry
from bionodulo.nodes.generation.environments import CondaPrefixReceipt, INCOMPLETE_MARKER, RECEIPT_NAME
from bionodulo.nodes.generation.acquisition import (
    Candidate, _inside, _identity, execution_profile_requests, package_identity, read_verified_snapshot, select_cohort,
)

from .test_node_spec import pixi_environment


def document(specs=None, versions=None):
    return {"hints": {"SoftwareRequirement": {"packages": {"package_name": {
        "version": versions if versions is not None else ["1.2.3"],
        "specs": specs if specs is not None else ["https://identifiers.org/biotools/registry_id"],
    }}}}}


def test_exact_declared_identity_can_differ_from_package_name():
    assert package_identity(document()) == ("registry_id", "package_name", "1.2.3", ("package_name==1.2.3",))


def test_native_profile_requires_locked_utilities_without_replacing_source_requirements():
    requests = ("example==1.0",)
    assert execution_profile_requests(requests) == ("coreutils==9.5",)
    assert execution_profile_requests(requests + ("coreutils==9.5",)) == ()
    with pytest.raises(ValueError, match="conflicts"):
        execution_profile_requests(("coreutils==8.0",))


def test_standard_package_array_form_has_same_identity_without_changing_source():
    value = document()
    package = value["hints"]["SoftwareRequirement"]["packages"].pop("package_name")
    value["hints"]["SoftwareRequirement"]["packages"] = [{"package": "package_name", **package}]
    before = json.dumps(value, sort_keys=True)
    assert package_identity(value) == ("registry_id", "package_name", "1.2.3", ("package_name==1.2.3",))
    assert json.dumps(value, sort_keys=True) == before


def test_package_array_rejects_duplicate_owners():
    package = {"package": "package_name", **document()["hints"]["SoftwareRequirement"]["packages"]["package_name"]}
    with pytest.raises(ValueError, match="duplicate"):
        package_identity({"requirements": {"SoftwareRequirement": {"packages": [package, package]}}})


def test_prior_prefix_is_not_relocated_when_new_groups_use_a_new_root(tmp_path):
    receipt = tmp_path / "receipt.json"
    old = tmp_path / "previous-install"
    new = tmp_path / "new-install"
    assert generate_registry.prior_environment_prefix(receipt, fallback=new) == new
    receipt.write_text(json.dumps({"prefix": str(old)}))
    assert generate_registry.prior_environment_prefix(receipt, fallback=new) == old
    receipt.write_text(json.dumps({"prefix": "relative-install"}))
    with pytest.raises(ValueError, match="absolute"):
        generate_registry.prior_environment_prefix(receipt, fallback=new)


def test_prior_environment_paths_use_retained_evidence_only_when_direct_pair_is_absent(tmp_path):
    group_key = "group"
    retained = tmp_path / "acquisition-evidence" / "environments"
    retained.mkdir(parents=True)
    retained_environment = retained / f"{group_key}.json"
    retained_receipt = retained / f"{group_key}.receipt.json"
    retained_environment.write_text("{}", encoding="utf-8")
    retained_receipt.write_text("{}", encoding="utf-8")

    assert generate_registry.prior_environment_paths(tmp_path, group_key) == (
        retained_environment,
        retained_receipt,
    )

    direct_environment = tmp_path / "environments" / f"{group_key}.json"
    direct_environment.parent.mkdir()
    direct_environment.write_text("{}", encoding="utf-8")
    assert generate_registry.prior_environment_paths(tmp_path, group_key) == (
        direct_environment,
        tmp_path / "environments" / f"{group_key}.receipt.json",
    )


def test_partial_reserved_prefix_is_recovered_without_masking_retained_receipts(monkeypatch, tmp_path):
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    marker = prefix.parent / f".{prefix.name}{INCOMPLETE_MARKER}"
    marker.write_text(
        json.dumps(
            {
                "prefix": str(prefix.absolute()),
                "requests": ["samtools==1.17"],
                "status": "incomplete",
            }
        ),
        encoding="utf-8",
    )
    (prefix.parent / f".{prefix.name}.micromamba-create.stdout.log").write_bytes(b"stdout")
    (prefix.parent / f".{prefix.name}.micromamba-create.stderr.log").write_bytes(b"stderr")
    environment_path = tmp_path / "environment.json"
    receipt_path = tmp_path / "environment.receipt.json"
    environment = pixi_environment(tool_id="samtools", tool_version="1.17")
    lock = environment.locks[0]
    receipt = CondaPrefixReceipt(
        environment_id=environment.environment_id,
        environment_digest=environment.environment_digest(),
        platform=lock.platform.value,
        prefix=str(prefix.resolve()),
        lock_digest=lock.lock_digest(),
        conda_metadata_sha256="sha256:" + "d" * 64,
        installed_inventory_sha256="sha256:" + "e" * 64,
        verified_file_hashes=1,
        unhashed_paths=0,
    )
    recover_calls = []

    def recover(requests, **kwargs):
        recover_calls.append((requests, kwargs))
        return environment, receipt

    monkeypatch.setattr(generate_registry, "recover_conda_environment", recover)
    resumed, recovered = generate_registry.resume_or_recover_environment(
        ("samtools==1.17",),
        prefix=prefix,
        environment_path=environment_path,
        receipt_path=receipt_path,
        recover_incomplete=True,
        micromamba=tmp_path / "micromamba",
    )

    assert recovered is True
    assert resumed == (environment, receipt)
    assert recover_calls == [
        (
            ("samtools==1.17",),
            {"prefix": prefix, "micromamba": tmp_path / "micromamba"},
        )
    ]

    receipt_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="partial prior environment"):
        generate_registry.resume_or_recover_environment(
            ("samtools==1.17",),
            prefix=prefix,
            environment_path=environment_path,
            receipt_path=receipt_path,
            recover_incomplete=True,
            micromamba=tmp_path / "micromamba",
        )
    assert len(recover_calls) == 1


@pytest.mark.parametrize("uri", ["https://bio.tools.evil.test/x", "https://identifiers.org/biotools/x/y",
    "https://bio.tools/x?alias=y", "https://user@bio.tools/x", "http://bio.tools/x", "https://bio.tools/%2fetc"])
def test_untrusted_or_ambiguous_identity_is_not_joined(uri):
    assert _identity(uri) is None


@pytest.mark.parametrize("versions", [[], ["1", "2"], ["1.*"], [">=1.0"], "1.0"])
def test_dependency_solver_never_receives_an_unpinned_requirement(versions):
    with pytest.raises(ValueError):
        package_identity(document(versions=versions))


def test_two_explicit_identities_are_not_silently_attributed_to_one():
    with pytest.raises(ValueError, match="found 2"):
        package_identity(document(specs=["https://bio.tools/a", "https://bio.tools/b"]))


def test_repeated_software_requirements_are_not_collapsed() -> None:
    first = document()["hints"]["SoftwareRequirement"]
    conflicting = document(versions=["2.0"])["hints"]["SoftwareRequirement"]
    with pytest.raises(ValueError, match="conflicting software requirements"):
        package_identity({
            "requirements": [
                {"class": "SoftwareRequirement", **first},
                {"class": "SoftwareRequirement", **conflicting},
            ]
        })


def test_source_paths_cannot_escape_repository(tmp_path):
    with pytest.raises(ValueError, match="escapes"):
        _inside(tmp_path, "../../unrelated.cwl")


def test_snapshot_digest_count_and_unique_ids_are_checked(tmp_path):
    snapshot, manifest = tmp_path / "registry.jsonl", tmp_path / "manifest.json"
    content = b'{"biotoolsID":"one"}\n'
    snapshot.write_bytes(content)
    data = {"sha256": hashlib.sha256(content).hexdigest(), "records": 1, "complete": True}
    manifest.write_text(json.dumps(data))
    assert set(read_verified_snapshot(snapshot, manifest)[0]) == {"one"}
    snapshot.write_bytes(content.replace(b"one", b"two"))
    with pytest.raises(ValueError, match="SHA-256"):
        read_verified_snapshot(snapshot, manifest)
    snapshot.write_bytes(content + b'{"biotoolsID":"ONE"}\n')
    with pytest.raises(ValueError, match="duplicate"):
        read_verified_snapshot(snapshot, manifest)
    snapshot.write_bytes(content)
    data["records"] = 2
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="count"):
        read_verified_snapshot(snapshot, manifest)


def test_cohort_is_order_independent_and_excludes_no_failures_from_original_ledger():
    candidates = [Candidate(path, "https://example.test/x", "sha256:" + "0" * 64, 5,
                            status=status, accession=accession)
                  for path, accession, status in [("a2.cwl", "a", "eligible"), ("bad.cwl", "z", "unsupported"),
                      ("b1.cwl", "b", "eligible"), ("a1.cwl", "a", "eligible")]]
    assert [item.descriptor for item in select_cohort(candidates, 2)] == ["a1.cwl", "b1.cwl"]
    assert select_cohort(candidates, 0) == select_cohort(list(reversed(candidates)), 0)
    assert len(candidates) == 4 and candidates[1].status == "unsupported"


class _ApiResponse:
    def __init__(self, versions: list[str]):
        self.payload = json.dumps({"versions": versions}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _maximum: int) -> bytes:
        return self.payload


def test_exact_version_preflight_rejects_only_conclusive_absence(monkeypatch):
    monkeypatch.setattr(generate_registry, "urlopen", lambda *_args, **_kwargs: _ApiResponse(["0.8.1", "0.9.0"]))
    receipts = []
    with pytest.raises(ValueError, match="bandage==0.8.*absent"):
        generate_registry.preflight_exact_versions(("bandage==0.8",), receipts=receipts)
    assert len(receipts) == 2
    assert all(item["status"] == "200" for item in receipts)
    assert all(item["response_sha256"].startswith("sha256:") for item in receipts)
    assert receipts[0]["observed_versions"] == ["0.8.1", "0.9.0"]
    assert receipts[0]["api_url"].startswith("https://api.anaconda.org/package/")

    calls = 0

    def uncertain(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise generate_registry.URLError("temporary")
        return _ApiResponse([])

    monkeypatch.setattr(generate_registry, "urlopen", uncertain)
    uncertain_receipts = []
    generate_registry.preflight_exact_versions(("bandage==0.8",), receipts=uncertain_receipts)
    assert [item["status"] for item in uncertain_receipts] == ["uncertain", "200"]


def test_resume_requires_environment_and_both_matching_receipts(monkeypatch, tmp_path):
    environment = pixi_environment(tool_id="samtools", tool_version="1.17")
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    environment_path = tmp_path / "environment.json"
    receipt_path = tmp_path / "environment.receipt.json"
    environment_path.write_text(environment.model_dump_json(), encoding="utf-8")
    lock = environment.locks[0]
    receipt = CondaPrefixReceipt(
        environment_id=environment.environment_id,
        environment_digest=environment.environment_digest(),
        platform=lock.platform.value,
        prefix=str(prefix.resolve()),
        lock_digest=lock.lock_digest(),
        conda_metadata_sha256="sha256:" + "d" * 64,
        installed_inventory_sha256="sha256:" + "e" * 64,
        verified_file_hashes=1,
        unhashed_paths=0,
    )
    stdout_log = prefix.parent / f".{prefix.name}.micromamba-create.stdout.log"
    stderr_log = prefix.parent / f".{prefix.name}.micromamba-create.stderr.log"
    stdout_log.write_bytes(b"solver stdout\n")
    stderr_log.write_bytes(b"solver stderr\n")
    annotated = CondaPrefixReceipt(
        **{
            **receipt.to_dict(),
            "solver_stdout_sha256": "sha256:" + hashlib.sha256(stdout_log.read_bytes()).hexdigest(),
            "solver_stderr_sha256": "sha256:" + hashlib.sha256(stderr_log.read_bytes()).hexdigest(),
        }
    )
    receipt_path.write_text(json.dumps(annotated.to_dict()), encoding="utf-8")
    (prefix / RECEIPT_NAME).write_text(json.dumps(annotated.to_dict()), encoding="utf-8")
    monkeypatch.setattr(generate_registry, "verify_conda_prefix", lambda *_args, **_kwargs: receipt)

    resumed = generate_registry.resume_verified_environment(
        ("samtools==1.17",),
        prefix=prefix,
        environment_path=environment_path,
        receipt_path=receipt_path,
    )
    assert resumed == (environment, annotated)

    altered = annotated.to_dict()
    altered["verified_file_hashes"] = 2
    receipt_path.write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(ValueError, match="receipts do not match"):
        generate_registry.resume_verified_environment(
            ("samtools==1.17",),
            prefix=prefix,
            environment_path=environment_path,
            receipt_path=receipt_path,
        )


def test_generation_run_receipt_distinguishes_completion_from_interruption(monkeypatch, tmp_path):
    candidate = Candidate(
        "unsupported.cwl",
        "https://example.test/unsupported.cwl",
        "sha256:" + "0" * 64,
        1,
        status="unsupported",
        reason="fixture",
    )
    source = {
        "repository": "https://github.com/example/tools",
        "revision": "1" * 40,
        "tracked_cwl_descriptors": 1,
        "tracked_files": 1,
    }
    manifest = {
        "source": "https://bio.tools/api/tool/",
        "completed_at": "2026-09-23T00:00:00+00:00",
        "records": 1,
        "sha256": "2" * 64,
        "license": "CC-BY-4.0",
    }
    monkeypatch.setattr(generate_registry, "read_verified_snapshot", lambda *_args: ({}, manifest))
    monkeypatch.setattr(
        generate_registry,
        "scan_repository",
        lambda *_args, **_kwargs: ([candidate], source),
    )

    completed = tmp_path / "completed"
    assert generate_registry.main([
        "--repository", str(tmp_path),
        "--revision", "1" * 40,
        "--source-url", "https://github.com/example/tools",
        "--snapshot", str(tmp_path / "snapshot.jsonl"),
        "--manifest", str(tmp_path / "manifest.json"),
        "--output", str(completed),
    ]) == 0
    completed_receipt = json.loads(next((completed / "runs").glob("*.json")).read_text())
    assert completed_receipt["status"] == "completed"
    assert completed_receipt["completed_at"] is not None

    interrupted = tmp_path / "interrupted"
    cwltool = tmp_path / "cwltool"
    cwltool.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(generate_registry.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("stopped")))
    with pytest.raises(RuntimeError, match="stopped"):
        generate_registry.main([
            "--repository", str(tmp_path),
            "--revision", "1" * 40,
            "--source-url", "https://github.com/example/tools",
            "--snapshot", str(tmp_path / "snapshot.jsonl"),
            "--manifest", str(tmp_path / "manifest.json"),
            "--output", str(interrupted),
            "--realize",
            "--prefix-root", str(tmp_path / "prefixes"),
            "--micromamba", str(tmp_path / "micromamba"),
            "--cwltool", str(cwltool),
        ])
    interrupted_receipt = json.loads(next((interrupted / "runs").glob("*.json")).read_text())
    assert interrupted_receipt["status"] == "in_progress"
    assert interrupted_receipt["completed_at"] is None


def test_receipt_only_generation_retains_hashed_prior_evidence(tmp_path):
    prior = tmp_path / "prior"
    files = {
        "coverage.json": {"counts": {"environment_unavailable": 1}},
        "engine.json": {"version": "3.2.0"},
        "runs/run.json": {
            "status": "completed",
            "availability": [{"api_url": "https://api.anaconda.org/package/bioconda/tool"}],
        },
        "environments/group.receipt.json": {
            "solver_stdout_sha256": "sha256:" + "a" * 64,
            "solver_stderr_sha256": "sha256:" + "b" * 64,
        },
    }
    original = {}
    for relative, value in files.items():
        path = prior / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        original[relative] = path.read_bytes()

    output = tmp_path / "new"
    receipt = generate_registry.retain_prior_generation_evidence(prior, output)
    manifest_path = output / receipt["manifest"]
    assert receipt["manifest_sha256"] == "sha256:" + hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    manifest = json.loads(manifest_path.read_text())
    assert {item["path"] for item in manifest["files"]} == set(files)
    for relative, content in original.items():
        copied = output / "acquisition-evidence" / relative
        assert copied.read_bytes() == content
        item = next(value for value in manifest["files"] if value["path"] == relative)
        assert item["sha256"] == "sha256:" + hashlib.sha256(content).hexdigest()
