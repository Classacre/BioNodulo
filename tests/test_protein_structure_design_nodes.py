from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.environments.manifest import workflow_to_packages
from bionodulo.nodes.registry import NodeRegistry


def _registry() -> NodeRegistry:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    return registry


def _node_class(node_id: str) -> type:
    node_class = _registry().get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def _proteinmpnn_bundle(tmp_path: Path, *, mode: str = "vanilla") -> tuple[Path, Path]:
    repository = tmp_path / "ProteinMPNN"
    repository.mkdir()
    (repository / "protein_mpnn_run.py").write_text("# pinned entrypoint\n", encoding="ascii")
    (repository / "protein_mpnn_utils.py").write_text("# pinned helpers\n", encoding="ascii")
    folder = {
        "vanilla": "vanilla_model_weights",
        "ca_only": "ca_model_weights",
        "soluble": "soluble_model_weights",
    }[mode]
    weights = repository / folder
    weights.mkdir()
    (weights / "v_48_020.pt").write_bytes(b"test weight")
    pdb = tmp_path / "backbone.pdb"
    pdb.write_text("ATOM\n", encoding="ascii")
    return repository, pdb


def _attested_bundle_digest(node_class: type, *, mode: str = "vanilla"):
    def digest(path: Path) -> str:
        source_digest = node_class.EXPECTED_SOURCE_SHA256.get(path.name)
        if source_digest is not None:
            return source_digest
        return node_class.EXPECTED_WEIGHT_SHA256[mode]

    return digest


def test_structure_design_wave_resolves_to_focused_modules() -> None:
    registry = _registry()
    expected_modules = {
        "colabfold_batch": "bionodulo.nodes.builtin.protein_structure_design_family.colabfold_batch",
        "esmfold_predict": "bionodulo.nodes.builtin.protein_structure_design_family.esmfold_predict",
        "proteinmpnn_design": "bionodulo.nodes.builtin.protein_structure_design_family.proteinmpnn_design",
    }
    assert {node_id: registry.get(node_id).__module__ for node_id in expected_modules} == expected_modules


def test_colabfold_contract_pins_package_and_records_implicit_downloads() -> None:
    node_class = _node_class("colabfold_batch")
    assert node_class.VERSION == "1.5.5"
    assert node_class.GIT_COMMIT == "675f93a44eee6589a003164b047e7d4183073d1e"
    assert node_class.CONDA_PACKAGE_CONSTRAINTS == {"colabfold": "1.5.5"}
    assert node_class.ENVIRONMENT["msa_api"] == "https://api.colabfold.com when explicitly acknowledged"
    assert "implicitly" in node_class.ENVIRONMENT["model_weights"]
    assert node_class.INPUT_TYPES()["required"] == {}
    assert {"fasta", "precomputed_msa"} <= set(node_class.INPUT_TYPES()["optional"])


def test_colabfold_refuses_implicit_public_msa_submission() -> None:
    validation = _node_class("colabfold_batch").VALIDATE_INPUTS({"fasta": "proteins.fasta"})
    assert validation == "Set 'allow_public_msa_api' or provide 'precomputed_msa' to avoid implicit sequence submission"


def test_colabfold_requires_at_least_one_authoritative_input() -> None:
    validation = _node_class("colabfold_batch").VALIDATE_INPUTS({})
    assert validation == "Provide at least one of 'fasta' or 'precomputed_msa'"


def test_colabfold_rejects_ambiguous_dual_inputs() -> None:
    validation = _node_class("colabfold_batch").VALIDATE_INPUTS(
        {"fasta": "proteins.fasta", "precomputed_msa": "proteins.a3m"}
    )
    assert validation == "Inputs 'fasta' and 'precomputed_msa' are mutually exclusive"


def test_colabfold_renders_acknowledged_prediction_command() -> None:
    command = _node_class("colabfold_batch").render_command(
        {
            "fasta": "proteins.fasta",
            "allow_public_msa_api": True,
            "msa_mode": "mmseqs2_uniref",
            "model_type": "alphafold2_ptm",
            "num_models": 3,
            "num_recycle": 4,
            "random_seed": 17,
            "output": "/tmp/run/colabfold_batch",
        }
    )
    assert command == [
        "colabfold_batch",
        "proteins.fasta",
        "/tmp/run/colabfold_batch/predictions",
        "--overwrite-existing-results",
        "--msa-mode",
        "mmseqs2_uniref",
        "--model-type",
        "alphafold2_ptm",
        "--num-models",
        "3",
        "--random-seed",
        "17",
        "--num-recycle",
        "4",
    ]


def test_colabfold_uses_precomputed_msa_without_network_mode() -> None:
    command = _node_class("colabfold_batch").render_command(
        {
            "precomputed_msa": "proteins.a3m",
            "output": "/tmp/run/colabfold_batch",
        }
    )
    assert command[1] == "proteins.a3m"
    assert "--msa-mode" not in command


def test_colabfold_single_sequence_mode_needs_no_public_api_acknowledgement() -> None:
    command = _node_class("colabfold_batch").render_command(
        {
            "fasta": "proteins.fasta",
            "msa_mode": "single_sequence",
            "output": "/tmp/run/colabfold_batch",
        }
    )
    mode_index = command.index("--msa-mode")
    assert command[mode_index : mode_index + 2] == ["--msa-mode", "single_sequence"]


def test_colabfold_output_planning_and_evidence_validation(tmp_path: Path) -> None:
    node_class = _node_class("colabfold_batch")
    output = node_class.PLAN_OUTPUTS({}, tmp_path)[0]
    assert output == tmp_path / "colabfold_batch" / "predictions"
    assert not output.exists()
    output.mkdir()
    assert node_class.VALIDATE_RESULT_DIRECTORY(output, msa_only=False) == (
        "ColabFold prediction mode did not create a PDB file"
    )
    (output / "query_unrelaxed_rank_001.pdb").write_text("MODEL\n", encoding="ascii")
    (output / "query.done.txt").write_text("done\n", encoding="ascii")
    assert node_class.VALIDATE_RESULT_DIRECTORY(output, msa_only=False) is True


@pytest.mark.parametrize("msa_only", [True, False])
def test_colabfold_requires_evidence_for_every_fasta_query(tmp_path: Path, msa_only: bool) -> None:
    node_class = _node_class("colabfold_batch")
    fasta = tmp_path / "queries.fasta"
    fasta.write_text(">query one\nAAAA\n>query/two\nCCCC\n", encoding="ascii")
    expected = node_class._expected_job_names({"fasta": fasta})
    assert expected == ["query_one", "query_two"]

    result_dir = tmp_path / "predictions"
    result_dir.mkdir()
    (result_dir / "query_one.a3m").write_text(">query_one\nAAAA\n", encoding="ascii")
    if not msa_only:
        (result_dir / "query_one_unrelaxed_rank_001_model.pdb").write_text("MODEL\n", encoding="ascii")
        (result_dir / "query_one.done.txt").touch()

    validation = node_class.VALIDATE_RESULT_DIRECTORY(
        result_dir,
        msa_only=msa_only,
        expected_job_names=expected,
    )
    assert "query_two" in str(validation)

    (result_dir / "query_two.a3m").write_text(">query_two\nCCCC\n", encoding="ascii")
    if not msa_only:
        (result_dir / "query_two_unrelaxed_rank_001_model.pdb").write_text("MODEL\n", encoding="ascii")
        (result_dir / "query_two.done.txt").touch()
    assert node_class.VALIDATE_RESULT_DIRECTORY(
        result_dir,
        msa_only=msa_only,
        expected_job_names=expected,
    ) is True


def test_esmfold_uses_python_api_and_records_exact_external_environment() -> None:
    node_class = _node_class("esmfold_predict")
    assert node_class.VERSION == "2.0.0"
    assert node_class.GIT_COMMIT == "0b59d87ebef95948c735b1f7aad463dc6dfa991b"
    assert node_class.REQUIRED_EXECUTABLES == ["python"]
    assert node_class.REQUIRED_CONDA_PACKAGES == []
    assert "esm-fold" not in node_class.REQUIRED_EXECUTABLES
    assert node_class.ENVIRONMENT["python"] == "<=3.9"
    assert node_class.ENVIRONMENT["openfold_commit"] == "4b41059694619831a7db195b7e0988fc4ff3a307"
    assert "implicitly" in node_class.ENVIRONMENT["model_weights"]
    assert workflow_to_packages({"nodes": [{"id": "fold", "type": "esmfold_predict"}]}, _registry()) == ["python"]


def test_esmfold_wrapper_validates_headers_and_exact_pdb_set(tmp_path: Path) -> None:
    node_class = _node_class("esmfold_predict")
    output_dir = tmp_path / "esmfold_predict"
    command = node_class.render_command(
        {
            "fasta": "/data/proteins.fasta",
            "num_recycles": 3,
            "max_tokens_per_batch": 512,
            "chunk_size": 64,
            "cpu_only": True,
            "output": str(output_dir),
        }
    )
    script_path = output_dir / "esmfold_predict.py"
    script = script_path.read_text()
    compile(script, str(script_path), "exec")
    assert command == ["python", str(script_path)]
    assert 'safe_header = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*").fullmatch' in script
    assert "if len(set(headers)) != len(headers):" in script
    assert "model = esm.pretrained.esmfold_v1().eval()" in script
    assert "model.set_chunk_size(64)" in script
    assert "if actual != expected:" in script


def test_esmfold_rejects_conflicting_memory_modes() -> None:
    validation = _node_class("esmfold_predict").VALIDATE_INPUTS(
        {"fasta": "proteins.fasta", "cpu_only": True, "cpu_offload": True}
    )
    assert validation == "Inputs 'cpu_only' and 'cpu_offload' are mutually exclusive"


def test_esmfold_accepts_zero_recycles_without_an_invented_upper_bound(tmp_path: Path) -> None:
    node_class = _node_class("esmfold_predict")
    assert node_class.VALIDATE_INPUTS({"fasta": "proteins.fasta", "num_recycles": 0}) is True
    assert node_class.VALIDATE_INPUTS({"fasta": "proteins.fasta", "num_recycles": 100}) is True
    output_dir = tmp_path / "esmfold_predict"
    node_class.render_command({"fasta": "proteins.fasta", "num_recycles": 0, "output": str(output_dir)})
    assert "num_recycles=0" in (output_dir / "esmfold_predict.py").read_text()


def test_esmfold_planning_does_not_precreate_success_directory(tmp_path: Path) -> None:
    output = _node_class("esmfold_predict").PLAN_OUTPUTS({}, tmp_path)[0]
    assert output == tmp_path / "esmfold_predict" / "pdb"
    assert not output.exists()


def test_proteinmpnn_contract_requires_repository_bundle_and_omits_score_only() -> None:
    node_class = _node_class("proteinmpnn_design")
    inputs = node_class.INPUT_TYPES()
    assert node_class.VERSION == "git-8907e6671bfb"
    assert node_class.GIT_COMMIT == "8907e6671bfbfc92303b5f79c4b5e6ce47cdef57"
    assert set(inputs["required"]) == {"repository_dir", "pdb_path"}
    assert "script_path" not in inputs["required"]
    assert "score_only" not in inputs["optional"]


def test_proteinmpnn_renders_pinned_design_mode_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("proteinmpnn_design")
    repository, pdb = _proteinmpnn_bundle(tmp_path)
    monkeypatch.setattr(
        node_class,
        "_sha256",
        staticmethod(_attested_bundle_digest(node_class)),
    )
    command = node_class.render_command(
        {
            "repository_dir": repository,
            "pdb_path": pdb,
            "pdb_path_chains": "A B",
            "num_seq_per_target": 4,
            "batch_size": 2,
            "sampling_temp": "0.1 0.2",
            "seed": 42,
            "save_score": True,
            "save_probs": True,
            "output": "/tmp/run/proteinmpnn_design",
        }
    )
    assert command == [
        "python",
        str(repository / "protein_mpnn_run.py"),
        "--pdb_path",
        str(pdb),
        "--out_folder",
        "/tmp/run/proteinmpnn_design",
        "--num_seq_per_target",
        "4",
        "--batch_size",
        "2",
        "--sampling_temp",
        "0.1 0.2",
        "--model_name",
        "v_48_020",
        "--seed",
        "42",
        "--pdb_path_chains",
        "A B",
        "--save_score",
        "1",
        "--save_probs",
        "1",
    ]
    assert "--score_only" not in command


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"num_seq_per_target": 3, "batch_size": 2}, "divisible"),
        ({"ca_only": True, "use_soluble_model": True}, "combined CA-only soluble"),
    ],
)
def test_proteinmpnn_rejects_upstream_silent_or_invalid_modes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, object],
    message: str,
) -> None:
    node_class = _node_class("proteinmpnn_design")
    repository, pdb = _proteinmpnn_bundle(tmp_path)
    monkeypatch.setattr(
        node_class,
        "_sha256",
        staticmethod(_attested_bundle_digest(node_class)),
    )
    validation = node_class.VALIDATE_INPUTS({"repository_dir": repository, "pdb_path": pdb, **overrides})
    assert message in str(validation)


def test_proteinmpnn_rejects_incomplete_or_unattested_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("proteinmpnn_design")
    repository, pdb = _proteinmpnn_bundle(tmp_path)
    monkeypatch.setattr(node_class, "_sha256", staticmethod(_attested_bundle_digest(node_class)))
    (repository / "protein_mpnn_utils.py").unlink()
    assert "missing protein_mpnn_utils.py" in str(
        node_class.VALIDATE_INPUTS({"repository_dir": repository, "pdb_path": pdb})
    )
    (repository / "protein_mpnn_utils.py").write_text("# restored\n", encoding="ascii")

    def invalid_weight_digest(path: Path) -> str:
        return node_class.EXPECTED_SOURCE_SHA256.get(path.name, "0" * 64)

    monkeypatch.setattr(node_class, "_sha256", staticmethod(invalid_weight_digest))
    assert "weight hash does not match" in str(
        node_class.VALIDATE_INPUTS({"repository_dir": repository, "pdb_path": pdb})
    )


def test_proteinmpnn_rejects_unpinned_source_files(tmp_path: Path) -> None:
    node_class = _node_class("proteinmpnn_design")
    repository, pdb = _proteinmpnn_bundle(tmp_path)
    validation = node_class.VALIDATE_INPUTS({"repository_dir": repository, "pdb_path": pdb})
    assert "source hash does not match pinned commit" in str(validation)


def test_proteinmpnn_outputs_and_weight_attestations_are_exact(tmp_path: Path) -> None:
    node_class = _node_class("proteinmpnn_design")
    outputs = node_class.PLAN_OUTPUTS({"pdb_path": "/data/input_backbone.pdb"}, tmp_path)
    assert outputs == [
        tmp_path / "proteinmpnn_design",
        tmp_path / "proteinmpnn_design" / "seqs" / "input_backbone.fa",
    ]
    assert node_class.EXPECTED_WEIGHT_SHA256 == {
        "vanilla": "c9cb4a671d79604111231f8dbfc7c590e06f1197453b7a6854ac6661a642f5bd",
        "ca_only": "f28f40170e21858c5ff31ef50b6e63414ff76dc331b19f85aa8586a12031744a",
        "soluble": "7af52d090172c230c7f0e9d21e02203f6b3a38b16db58d3c7a3960e0a9a6e31a",
    }
    assert node_class.EXPECTED_SOURCE_SHA256 == {
        "protein_mpnn_run.py": "61f2c519a7f73fa12da9eb90da97b97ec2f8d5f31d42605639c7600cbd321cbe",
        "protein_mpnn_utils.py": "74c8f9b7553422a7a0bbd705874844ee103c8926c2c96f154a87e0b824071e1b",
    }


def test_proteinmpnn_environment_package_names_remain_canonical() -> None:
    registry = _registry()
    workflow = {"nodes": [{"id": "design", "type": "proteinmpnn_design"}]}
    assert workflow_to_packages(workflow, registry) == ["numpy", "python", "pytorch"]
