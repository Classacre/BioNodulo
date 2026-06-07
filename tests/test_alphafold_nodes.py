from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.environments.manifest import workflow_to_packages
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_alphafold_db_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["alphafold_db"]["display_name"] == "AlphaFold DB"
    assert info["alphafold_db"]["category"] == "databases"
    assert info["alphafold_db"]["output_name"] == ["structure_mmcif", "structure_metadata"]
    assert info["alphafold"]["display_name"] == "AlphaFold"
    assert info["alphafold"]["category"] == "databases"
    assert info["alphafold"]["output_name"] == ["structure_mmcif", "structure_metadata"]
    assert issubclass(registry.get("alphafold"), registry.get("alphafold_db"))


def test_colabfold_batch_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    node_info = info["colabfold_batch"]
    assert node_info["display_name"] == "ColabFold Batch"
    assert node_info["category"] == "ai"
    assert node_info["description"].startswith("Predict protein structures")
    assert node_info["output"] == ["DIRECTORY"]
    assert node_info["output_name"] == ["prediction_dir"]
    assert node_info["required_executables"] == ["colabfold_batch"]
    assert node_info["required_conda_packages"] == ["colabfold"]
    assert "colabfold" in node_info["search_aliases"]
    assert "protein folding" in node_info["search_aliases"]
    assert "mmseqs2" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"fasta"}
    assert set(inputs["optional"]) == {"msa_only"}


def test_colabfold_batch_renders_prediction_command() -> None:
    node_class = _node_class("colabfold_batch")

    cmd = node_class.render_command({
        "fasta": "input_sequences.fasta",
        "msa_only": False,
        "output": "/tmp/run/colabfold_batch",
    })

    assert cmd == [
        "colabfold_batch",
        "input_sequences.fasta",
        "/tmp/run/colabfold_batch/predictions",
    ]


def test_colabfold_batch_renders_msa_only_flag() -> None:
    node_class = _node_class("colabfold_batch")

    cmd = node_class.render_command({
        "fasta": "input_sequences.fasta",
        "msa_only": True,
        "output": "/tmp/run/colabfold_batch",
    })

    assert cmd == [
        "colabfold_batch",
        "input_sequences.fasta",
        "/tmp/run/colabfold_batch/predictions",
        "--msa-only",
    ]


def test_colabfold_batch_plans_prediction_directory() -> None:
    node_class = _node_class("colabfold_batch")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert outputs == [Path("/tmp/run/colabfold_batch/predictions")]


def test_colabfold_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["colabfold_batch"] == "colabfold"
    assert PACKAGE_MIN_VERSIONS["colabfold"] == ">=1.5.5"


def test_esmfold_predict_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    node_info = info["esmfold_predict"]
    assert node_info["display_name"] == "ESMFold Predict"
    assert node_info["category"] == "ai"
    assert node_info["description"].startswith("Predict protein structures")
    assert node_info["output"] == ["DIRECTORY"]
    assert node_info["output_name"] == ["pdb_dir"]
    assert node_info["required_executables"] == ["esm-fold"]
    assert node_info["required_conda_packages"] == ["fair-esm"]
    assert "esmfold" in node_info["search_aliases"]
    assert "protein folding" in node_info["search_aliases"]
    assert "single sequence" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"fasta"}
    assert set(inputs["optional"]) == {
        "num_recycles",
        "max_tokens_per_batch",
        "chunk_size",
        "cpu_only",
        "cpu_offload",
    }


def test_esmfold_predict_renders_default_command() -> None:
    node_class = _node_class("esmfold_predict")

    cmd = node_class.render_command({
        "fasta": "proteins.fasta",
        "num_recycles": 4,
        "max_tokens_per_batch": 1024,
        "chunk_size": 0,
        "cpu_only": False,
        "cpu_offload": False,
        "output": "/tmp/run/esmfold_predict",
    })

    assert cmd == [
        "esm-fold",
        "-i",
        "proteins.fasta",
        "-o",
        "/tmp/run/esmfold_predict/pdb",
        "--num-recycles",
        "4",
        "--max-tokens-per-batch",
        "1024",
    ]


def test_esmfold_predict_renders_memory_flags() -> None:
    node_class = _node_class("esmfold_predict")

    cmd = node_class.render_command({
        "fasta": "long_proteins.fasta",
        "num_recycles": 3,
        "max_tokens_per_batch": 0,
        "chunk_size": 64,
        "cpu_only": True,
        "cpu_offload": True,
        "output": "/tmp/run/esmfold_predict",
    })

    assert cmd == [
        "esm-fold",
        "-i",
        "long_proteins.fasta",
        "-o",
        "/tmp/run/esmfold_predict/pdb",
        "--num-recycles",
        "3",
        "--max-tokens-per-batch",
        "0",
        "--chunk-size",
        "64",
        "--cpu-only",
        "--cpu-offload",
    ]


def test_esmfold_predict_plans_pdb_directory() -> None:
    node_class = _node_class("esmfold_predict")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert outputs == [Path("/tmp/run/esmfold_predict/pdb")]


def test_esmfold_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["esm-fold"] == "fair-esm"
    assert PACKAGE_MIN_VERSIONS["fair-esm"] == ">=2.0.0"


def test_proteinmpnn_design_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    node_info = info["proteinmpnn_design"]
    assert node_info["display_name"] == "ProteinMPNN Design"
    assert node_info["category"] == "ai"
    assert node_info["description"].startswith("Design protein sequences")
    assert node_info["output"] == ["DIRECTORY", "FASTA"]
    assert node_info["output_name"] == ["design_dir", "designed_sequences"]
    assert node_info["required_executables"] == ["python"]
    assert node_info["required_conda_packages"] == ["numpy", "torch"]
    assert node_info["experimental"] is True
    assert "proteinmpnn" in node_info["search_aliases"]
    assert "inverse folding" in node_info["search_aliases"]
    assert "protein design" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"script_path", "pdb_path"}
    assert set(inputs["optional"]) == {
        "pdb_path_chains",
        "num_seq_per_target",
        "batch_size",
        "sampling_temp",
        "model_name",
        "path_to_model_weights",
        "ca_only",
        "use_soluble_model",
        "seed",
        "save_score",
        "save_probs",
        "score_only",
    }


def test_proteinmpnn_design_renders_basic_command() -> None:
    node_class = _node_class("proteinmpnn_design")

    cmd = node_class.render_command({
        "script_path": "/opt/ProteinMPNN/protein_mpnn_run.py",
        "pdb_path": "input_backbone.pdb",
        "pdb_path_chains": "",
        "num_seq_per_target": 3,
        "batch_size": 2,
        "sampling_temp": "0.1 0.2",
        "model_name": "v_48_020",
        "path_to_model_weights": "",
        "ca_only": False,
        "use_soluble_model": False,
        "seed": 0,
        "save_score": False,
        "save_probs": False,
        "score_only": False,
        "output": "/tmp/run/proteinmpnn_design",
    })

    assert cmd == [
        "python",
        "/opt/ProteinMPNN/protein_mpnn_run.py",
        "--pdb_path",
        "input_backbone.pdb",
        "--out_folder",
        "/tmp/run/proteinmpnn_design",
        "--num_seq_per_target",
        "3",
        "--batch_size",
        "2",
        "--sampling_temp",
        "0.1 0.2",
        "--model_name",
        "v_48_020",
    ]


def test_proteinmpnn_design_renders_advanced_flags() -> None:
    node_class = _node_class("proteinmpnn_design")

    cmd = node_class.render_command({
        "script_path": "/opt/ProteinMPNN/protein_mpnn_run.py",
        "pdb_path": "ca_backbone.pdb",
        "pdb_path_chains": "A B",
        "num_seq_per_target": 1,
        "batch_size": 1,
        "sampling_temp": "0.1",
        "model_name": "v_48_010",
        "path_to_model_weights": "/models/proteinmpnn",
        "ca_only": True,
        "use_soluble_model": True,
        "seed": 42,
        "save_score": True,
        "save_probs": True,
        "score_only": True,
        "output": "/tmp/run/proteinmpnn_design",
    })

    assert cmd == [
        "python",
        "/opt/ProteinMPNN/protein_mpnn_run.py",
        "--pdb_path",
        "ca_backbone.pdb",
        "--out_folder",
        "/tmp/run/proteinmpnn_design",
        "--num_seq_per_target",
        "1",
        "--batch_size",
        "1",
        "--sampling_temp",
        "0.1",
        "--model_name",
        "v_48_010",
        "--pdb_path_chains",
        "A B",
        "--path_to_model_weights",
        "/models/proteinmpnn",
        "--seed",
        "42",
        "--ca_only",
        "--use_soluble_model",
        "--save_score",
        "1",
        "--save_probs",
        "1",
        "--score_only",
        "1",
    ]


def test_proteinmpnn_design_plans_outputs_from_pdb_stem() -> None:
    node_class = _node_class("proteinmpnn_design")

    outputs = node_class.PLAN_OUTPUTS({"pdb_path": "/data/input_backbone.pdb"}, "/tmp/run")

    assert outputs == [
        Path("/tmp/run/proteinmpnn_design"),
        Path("/tmp/run/proteinmpnn_design/seqs/input_backbone.fa"),
    ]


def test_proteinmpnn_environment_metadata_is_declared() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert EXECUTABLE_TO_CONDA_PACKAGE["python"] == "python"
    assert PACKAGE_MIN_VERSIONS["torch"] == ">=2.0"
    assert workflow_to_packages(
        {"nodes": [{"id": "design", "type": "proteinmpnn_design"}]},
        registry,
    ) == ["numpy", "python", "torch"]


@pytest.mark.asyncio
async def test_alphafold_requests_use_shared_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("alphafold_db")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    assert isinstance(module.ALPHAFOLD_API_CACHE, module.APICache)
    assert isinstance(module.ALPHAFOLD_RATE_LIMITER, module.TokenBucketRateLimiter)

    class FakeClient:
        def __init__(self, *, cache: object | None = None, rate_limiter: object | None = None) -> None:
            self.cache = cache
            self.rate_limiter = rate_limiter

        async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
            calls.append(
                {
                    "method": method,
                    "url": url,
                    "cache": self.cache,
                    "rate_limiter": self.rate_limiter,
                    **kwargs,
                }
            )
            request = httpx.Request(method, url, headers=kwargs.get("headers"))
            return httpx.Response(200, json=[{"entryId": "AF-P04637-F1"}], request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)

    response = await module._request("prediction/P04637", retries=4, timeout=8.0)

    assert response.json() == [{"entryId": "AF-P04637-F1"}]
    assert calls == [
        {
            "method": "GET",
            "url": f"{module.ALPHAFOLD_BASE_URL}/prediction/P04637",
            "cache": module.ALPHAFOLD_API_CACHE,
            "rate_limiter": module.ALPHAFOLD_RATE_LIMITER,
            "headers": {"User-Agent": module.ALPHAFOLD_USER_AGENT},
            "timeout": 8.0,
            "retries": 4,
            "retry_delay": module.RETRY_DELAY_S,
            "cache_ttl": module.ALPHAFOLD_CACHE_TTL_S,
            "follow_redirects": True,
        }
    ]


@pytest.mark.asyncio
async def test_alphafold_downloads_use_shared_http_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("alphafold_db")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    class FakeClient:
        def __init__(self, *, cache: object | None = None, rate_limiter: object | None = None) -> None:
            self.cache = cache
            self.rate_limiter = rate_limiter

        async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
            calls.append(
                {
                    "method": method,
                    "url": url,
                    "cache": self.cache,
                    "rate_limiter": self.rate_limiter,
                    **kwargs,
                }
            )
            request = httpx.Request(method, url, headers=kwargs.get("headers"))
            return httpx.Response(200, content=b"data_p04637\n", request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)
    output_path = tmp_path / "P04637.cif"

    await module._download_file("https://alphafold.example/P04637.cif", output_path, retries=2, timeout=9.0)

    assert output_path.read_bytes() == b"data_p04637\n"
    assert calls == [
        {
            "method": "GET",
            "url": "https://alphafold.example/P04637.cif",
            "cache": module.ALPHAFOLD_API_CACHE,
            "rate_limiter": module.ALPHAFOLD_RATE_LIMITER,
            "headers": {"User-Agent": module.ALPHAFOLD_USER_AGENT},
            "timeout": 9.0,
            "retries": 2,
            "retry_delay": module.RETRY_DELAY_S,
            "cache_ttl": None,
            "follow_redirects": True,
        }
    ]


@pytest.mark.asyncio
async def test_alphafold_db_downloads_structure_and_writes_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("alphafold_db")
    module = importlib.import_module(node_class.__module__)
    json_calls: list[str] = []
    download_calls: list[tuple[str, Path]] = []

    async def fake_json(resource: str, **_: Any) -> Any:
        json_calls.append(resource)
        return [
            {
                "entryId": "AF-P04637-F1",
                "uniprotAccession": "P04637",
                "uniprotId": "P53_HUMAN",
                "cifUrl": "https://alphafold.example/P04637.cif",
                "pdbUrl": "https://alphafold.example/P04637.pdb",
                "paeDocUrl": "https://alphafold.example/P04637-pae.json",
                "latestVersion": 4,
            }
        ]

    async def fake_download(url: str, path: Path, **_: Any) -> None:
        download_calls.append((url, path))
        path.write_text(f"downloaded from {url}\n", encoding="utf-8")

    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_download_file", fake_download)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        uniprot_ids="P04637",
        structure_format="mmcif",
        download_pae=True,
        context=context,
    )

    structure_path = Path(result["outputs"]["structure_mmcif"])
    metadata_path = Path(result["outputs"]["structure_metadata"])
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert structure_path.name == "P04637.cif"
    assert structure_path.read_text(encoding="utf-8") == "downloaded from https://alphafold.example/P04637.cif\n"
    assert metadata_path.name == "structure_metadata.json"
    assert metadata == {
        "record_count": 1,
        "structures": [
            {
                "uniprot_id": "P04637",
                "entry_id": "AF-P04637-F1",
                "uniprot_accession": "P04637",
                "uniprot_name": "P53_HUMAN",
                "latest_version": 4,
                "structure_file": str(structure_path),
                "pae_file": str(tmp_path / "alphafold_db" / "P04637_pae.json"),
            }
        ],
        "raw": {"P04637": [{"entryId": "AF-P04637-F1", "uniprotAccession": "P04637", "uniprotId": "P53_HUMAN", "cifUrl": "https://alphafold.example/P04637.cif", "pdbUrl": "https://alphafold.example/P04637.pdb", "paeDocUrl": "https://alphafold.example/P04637-pae.json", "latestVersion": 4}]},
    }
    assert (tmp_path / "alphafold_db" / "P04637_pae.json").read_text(encoding="utf-8") == (
        "downloaded from https://alphafold.example/P04637-pae.json\n"
    )
    assert json_calls == ["prediction/P04637"]
    assert download_calls == [
        ("https://alphafold.example/P04637.cif", tmp_path / "alphafold_db" / "P04637.cif"),
        ("https://alphafold.example/P04637-pae.json", tmp_path / "alphafold_db" / "P04637_pae.json"),
    ]


@pytest.mark.asyncio
async def test_alphafold_db_accepts_format_alias_for_structure_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("alphafold_db")
    module = importlib.import_module(node_class.__module__)
    download_calls: list[tuple[str, Path]] = []

    async def fake_json(resource: str, **_: Any) -> Any:
        return [
            {
                "entryId": "AF-P04637-F1",
                "uniprotAccession": "P04637",
                "uniprotId": "P53_HUMAN",
                "cifUrl": "https://alphafold.example/P04637.cif",
                "pdbUrl": "https://alphafold.example/P04637.pdb",
                "latestVersion": 4,
            }
        ]

    async def fake_download(url: str, path: Path, **_: Any) -> None:
        download_calls.append((url, path))
        path.write_text(f"downloaded from {url}\n", encoding="utf-8")

    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_download_file", fake_download)

    assert node_class.INPUT_TYPES()["optional"]["format"][0] == "STRING"

    result = await node_class().run(
        uniprot_ids="P04637",
        format="pdb",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    structure_path = Path(result["outputs"]["structure_mmcif"])
    assert structure_path.name == "P04637.pdb"
    assert structure_path.read_text(encoding="utf-8") == "downloaded from https://alphafold.example/P04637.pdb\n"
    assert download_calls == [
        ("https://alphafold.example/P04637.pdb", tmp_path / "alphafold_db" / "P04637.pdb"),
    ]


@pytest.mark.asyncio
async def test_alphafold_db_prefers_planned_format_over_structure_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("alphafold_db")
    module = importlib.import_module(node_class.__module__)
    download_calls: list[tuple[str, Path]] = []

    async def fake_json(resource: str, **_: Any) -> Any:
        return [
            {
                "entryId": "AF-P04637-F1",
                "uniprotAccession": "P04637",
                "uniprotId": "P53_HUMAN",
                "cifUrl": "https://alphafold.example/P04637.cif",
                "pdbUrl": "https://alphafold.example/P04637.pdb",
                "latestVersion": 4,
            }
        ]

    async def fake_download(url: str, path: Path, **_: Any) -> None:
        download_calls.append((url, path))
        path.write_text(f"downloaded from {url}\n", encoding="utf-8")

    monkeypatch.setattr(module, "_request_json", fake_json)
    monkeypatch.setattr(module, "_download_file", fake_download)

    result = await node_class().run(
        uniprot_ids="P04637",
        structure_format="mmcif",
        format="pdb",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    structure_path = Path(result["outputs"]["structure_mmcif"])
    assert structure_path.name == "P04637.pdb"
    assert download_calls == [
        ("https://alphafold.example/P04637.pdb", tmp_path / "alphafold_db" / "P04637.pdb"),
    ]
