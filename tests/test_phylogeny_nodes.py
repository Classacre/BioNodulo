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


def _context(tmp_path: Path, name: str) -> SimpleNamespace:
    node_dir = tmp_path / name
    node_dir.mkdir()
    return SimpleNamespace(node_dir=node_dir)


def test_muscle_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["muscle"]
    assert node_info["display_name"] == "MUSCLE"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"].startswith("Multiple sequence alignment")
    assert node_info["output"] == ["ALIGNMENT"]
    assert node_info["output_name"] == ["alignment"]
    assert node_info["required_executables"] == ["muscle"]
    assert node_info["required_conda_packages"] == ["muscle"]
    assert "multiple alignment" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"sequences"}
    assert set(inputs["optional"]) == {"maxiters", "diags", "stable"}


def test_muscle_renders_alignment_command_with_optional_flags() -> None:
    node_class = _node_class("muscle")

    cmd = node_class.render_command({
        "sequences": "proteins.faa",
        "maxiters": 8,
        "diags": True,
        "stable": True,
        "output": "/tmp/run/muscle",
    })

    assert cmd == [
        "muscle",
        "-align",
        "proteins.faa",
        "-output",
        "/tmp/run/muscle/alignment.aln.fasta",
        "-maxiters",
        "8",
        "-diags",
        "-stable",
    ]


def test_muscle_omits_disabled_optional_flags_and_plans_outputs() -> None:
    node_class = _node_class("muscle")

    cmd = node_class.render_command({
        "sequences": "dna.fa",
        "maxiters": 0,
        "diags": False,
        "stable": False,
        "output": "/tmp/run/muscle",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "muscle",
        "-align",
        "dna.fa",
        "-output",
        "/tmp/run/muscle/alignment.aln.fasta",
    ]
    assert [str(path) for path in outputs] == ["/tmp/run/muscle/alignment.aln.fasta"]


def test_trimal_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["trimal"]
    assert node_info["display_name"] == "trimAl"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"].startswith("Automated trimming")
    assert node_info["output"] == ["FASTA", "STATS_FILE"]
    assert node_info["output_name"] == ["trimmed", "stats"]
    assert node_info["required_executables"] == ["trimal"]
    assert node_info["required_conda_packages"] == ["trimal"]
    assert "alignment trimming" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"alignment"}
    assert set(inputs["optional"]) == {"automated", "fasta_output", "htmlout"}


def test_trimal_renders_automated_command_with_optional_reports() -> None:
    node_class = _node_class("trimal")

    cmd = node_class.render_command({
        "alignment": "alignment.fasta",
        "automated": "automated1",
        "fasta_output": True,
        "htmlout": True,
        "output": "/tmp/run/trimal",
    })

    assert cmd == [
        "trimal",
        "-in",
        "alignment.fasta",
        "-out",
        "/tmp/run/trimal/trimmed.fasta",
        "-automated1",
        "-fasta",
        "-htmlout",
        "/tmp/run/trimal/stats.html",
    ]


def test_trimal_supports_strict_mode_and_plans_outputs() -> None:
    node_class = _node_class("trimal")

    cmd = node_class.render_command({
        "alignment": "alignment.aln.fasta",
        "automated": "strict",
        "fasta_output": False,
        "htmlout": False,
        "output": "/tmp/run/trimal",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "trimal",
        "-in",
        "alignment.aln.fasta",
        "-out",
        "/tmp/run/trimal/trimmed.fasta",
        "-strict",
    ]
    assert [str(path) for path in outputs] == [
        "/tmp/run/trimal/trimmed.fasta",
        "/tmp/run/trimal/stats.stats.txt",
    ]


def test_raxml_ng_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["raxml_ng"]
    assert node_info["display_name"] == "RAxML-NG"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"].startswith("Maximum likelihood phylogenetic tree inference")
    assert node_info["output"] == ["NEWICK", "FILE"]
    assert node_info["output_name"] == ["tree", "bootstrap"]
    assert node_info["required_executables"] == ["raxml-ng"]
    assert node_info["required_conda_packages"] == ["raxml-ng"]
    assert "raxml-ng" in node_info["search_aliases"]
    assert "maximum likelihood" in node_info["search_aliases"]
    assert "bootstrap" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"alignment", "model", "threads"}
    assert set(inputs["optional"]) == {"seed", "bootstrap_replicates", "outgroup", "tree_search"}


def test_raxml_ng_renders_tree_search_with_bootstrap_command() -> None:
    node_class = _node_class("raxml_ng")

    cmd = node_class.render_command({
        "alignment": "trimmed.fasta",
        "model": "GTR+G",
        "threads": 8,
        "seed": 42,
        "bootstrap_replicates": 100,
        "outgroup": "sampleA,sampleB",
        "tree_search": True,
        "output": "/tmp/run/raxml_ng",
    })

    assert cmd == [
        "raxml-ng",
        "--msa",
        "trimmed.fasta",
        "--model",
        "GTR+G",
        "--prefix",
        "/tmp/run/raxml_ng/raxml_ng",
        "--threads",
        "8",
        "--seed",
        "42",
        "--all",
        "--bs-trees",
        "100",
        "--outgroup",
        "sampleA,sampleB",
    ]


def test_raxml_ng_uses_search_without_bootstraps_and_plans_outputs() -> None:
    node_class = _node_class("raxml_ng")

    cmd = node_class.render_command({
        "alignment": "alignment.phy",
        "model": "LG+G",
        "threads": 2,
        "seed": 0,
        "bootstrap_replicates": 0,
        "outgroup": "",
        "tree_search": True,
        "output": "/tmp/run/raxml_ng",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "raxml-ng",
        "--msa",
        "alignment.phy",
        "--model",
        "LG+G",
        "--prefix",
        "/tmp/run/raxml_ng/raxml_ng",
        "--threads",
        "2",
        "--seed",
        "0",
        "--search",
    ]
    outputs = node_class.PLAN_OUTPUTS({"bootstrap_replicates": 0}, "/tmp/run")
    assert [str(path) for path in outputs] == [
        "/tmp/run/raxml_ng/raxml_ng.raxml.bestTree",
    ]


def test_raxml_ng_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["raxml-ng"] == "raxml-ng"
    assert PACKAGE_MIN_VERSIONS["raxml-ng"] == ">=1.2.2"


def test_modeltest_ng_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["modeltest_ng"]
    assert node_info["display_name"] == "ModelTest-NG"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"].startswith("Select best-fit substitution model")
    assert node_info["output"] == ["TEXT", "TEXT"]
    assert node_info["output_name"] == ["results", "log"]
    assert node_info["required_executables"] == ["modeltest-ng"]
    assert node_info["required_conda_packages"] == ["modeltest-ng"]
    assert "modeltest-ng" in node_info["search_aliases"]
    assert "substitution model" in node_info["search_aliases"]
    assert "phylogeny" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"alignment", "datatype", "threads"}
    assert set(inputs["optional"]) == {"template", "models", "schemes", "ascertainment_bias"}


def test_modeltest_ng_renders_model_selection_command() -> None:
    node_class = _node_class("modeltest_ng")

    cmd = node_class.render_command({
        "alignment": "alignment.fasta",
        "datatype": "nt",
        "threads": 8,
        "template": "",
        "models": "GTR,HKY,JC",
        "schemes": 0,
        "ascertainment_bias": False,
        "output": "/tmp/run/modeltest_ng",
    })

    assert cmd == [
        "modeltest-ng",
        "-i",
        "alignment.fasta",
        "-d",
        "nt",
        "-p",
        "8",
        "-o",
        "/tmp/run/modeltest_ng/modeltest",
        "-m",
        "GTR,HKY,JC",
    ]


def test_modeltest_ng_omits_empty_optional_flags_and_plans_outputs() -> None:
    node_class = _node_class("modeltest_ng")

    cmd = node_class.render_command({
        "alignment": "proteins.phy",
        "datatype": "aa",
        "threads": 2,
        "template": "",
        "models": "",
        "schemes": 0,
        "ascertainment_bias": False,
        "output": "/tmp/run/modeltest_ng",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert "-T" not in cmd
    assert "-m" not in cmd
    assert "-s" not in cmd
    assert "--asc-bias" not in cmd
    assert cmd[:9] == [
        "modeltest-ng",
        "-i",
        "proteins.phy",
        "-d",
        "aa",
        "-p",
        "2",
        "-o",
        "/tmp/run/modeltest_ng/modeltest",
    ]
    assert [str(path) for path in outputs] == [
        "/tmp/run/modeltest_ng/modeltest.out",
        "/tmp/run/modeltest_ng/modeltest.log",
    ]


def test_modeltest_ng_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["modeltest-ng"] == "modeltest-ng"
    assert PACKAGE_MIN_VERSIONS["modeltest-ng"] == ">=0.1.7"


def test_astral_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["astral"]
    assert node_info["display_name"] == "ASTRAL-III"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"] == "Estimate an unrooted species tree from unrooted gene trees with ASTRAL-III."
    assert node_info["output"] == ["PHYLOGENY_TREE", "TXT", "TSV"]
    assert node_info["output_name"] == ["output", "log_output", "branch_annotations"]
    assert node_info["required_executables"] == ["astral"]
    assert node_info["required_conda_packages"] == ["astral-tree"]
    assert node_info["documentation_url"] == "https://github.com/smirarab/ASTRAL"
    assert node_info["citation_dois"] == ["10.1186/s12859-018-2129-y"]
    assert node_info["citation_urls"] == ["https://doi.org/10.1186/s12859-018-2129-y"]
    assert "ASTRAL-III" in node_info["citation_text"]
    assert "species tree" in node_info["search_aliases"]
    assert "gene tree" in node_info["search_aliases"]
    assert "coalescent" in node_info["search_aliases"]
    assert node_info["version"] == "5.7.8+galaxy0"

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"input"}
    assert set(inputs["optional"]) == {"branch_annotate", "lambda"}
    assert inputs["required"]["input"][0] == "PHYLOGENY_TREE"
    assert inputs["optional"]["branch_annotate"][1]["default"] == "3"
    assert inputs["optional"]["branch_annotate"][1]["options"] == ["0", "1", "2", "3", "4", "8", "16", "32", "10"]
    assert inputs["optional"]["lambda"][1]["default"] == 0.5
    assert inputs["optional"]["lambda"][1]["min"] == 0
    assert inputs["optional"]["lambda"][1]["max"] == 10


def test_phylogeny_tree_input_type_is_preserved_for_frontend_sockets() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert registry.object_info("astral")["input"]["required"]["input"][0] == "PHYLOGENY_TREE"


def test_astral_renders_galaxy_command_with_branch_annotations() -> None:
    node_class = _node_class("astral")

    cmd = node_class.render_command({
        "input": "song mammals.gene.tre",
        "branch_annotate": "16",
        "lambda": 2.0,
        "output": "/tmp/run/astral",
    })

    assert node_class.SHELL is True
    assert cmd == (
        "mkdir -p /tmp/run/astral && cd /tmp/run/astral && astral --input 'song mammals.gene.tre' "
        "--branch-annotate 16 --output ./output.tre --lambda 2.0 2>&1 | tee /tmp/run/astral/log_output.txt && "
        "mv ./output.tre /tmp/run/astral/output.tre && mv freqQuad.csv /tmp/run/astral/branch_annotations.tsv"
    )


def test_astral_omits_branch_annotations_unless_requested_and_plans_outputs() -> None:
    node_class = _node_class("astral")

    cmd = node_class.render_command({
        "input": "gene_trees.nwk",
        "branch_annotate": "0",
        "lambda": 0.5,
        "output": "/tmp/run/astral",
    })
    outputs_without_annotations = node_class.PLAN_OUTPUTS({"branch_annotate": "0"}, "/tmp/run")
    outputs_with_annotations = node_class.PLAN_OUTPUTS({"branch_annotate": "32"}, "/tmp/run")

    assert "freqQuad.csv" not in cmd
    assert cmd == (
        "mkdir -p /tmp/run/astral && cd /tmp/run/astral && astral --input gene_trees.nwk "
        "--branch-annotate 0 --output ./output.tre --lambda 0.5 2>&1 | tee /tmp/run/astral/log_output.txt && "
        "mv ./output.tre /tmp/run/astral/output.tre"
    )
    assert [str(path) for path in outputs_without_annotations] == [
        "/tmp/run/astral/output.tre",
        "/tmp/run/astral/log_output.txt",
    ]
    assert [str(path) for path in outputs_with_annotations] == [
        "/tmp/run/astral/output.tre",
        "/tmp/run/astral/log_output.txt",
        "/tmp/run/astral/branch_annotations.tsv",
    ]


def test_astral_validates_required_input_branch_annotation_and_lambda() -> None:
    node_class = _node_class("astral")

    assert node_class.VALIDATE_INPUTS({}) == "input tree file is required"
    assert node_class.VALIDATE_INPUTS({"input": "trees.tre", "branch_annotate": "99"}) == (
        "branch_annotate must be one of: 0, 1, 2, 3, 4, 8, 16, 32, 10"
    )
    assert node_class.VALIDATE_INPUTS({"input": "trees.tre", "lambda": "bad"}) == "lambda must be numeric"
    assert node_class.VALIDATE_INPUTS({"input": "trees.tre", "lambda": -0.1}) == "lambda must be between 0 and 10"
    assert node_class.VALIDATE_INPUTS({"input": "trees.tre", "lambda": 10.1}) == "lambda must be between 0 and 10"
    assert node_class.VALIDATE_INPUTS({"input": "trees.tre", "lambda": 10}) is True
    assert node_class.VALIDATE_INPUTS({"input": "trees.tre"}) is True


def test_astral_environment_metadata_is_declared() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert EXECUTABLE_TO_CONDA_PACKAGE["astral"] == "astral-tree"
    assert PACKAGE_MIN_VERSIONS["astral-tree"] == ">=5.7.8"
    assert workflow_to_packages({"nodes": [{"id": "species", "type": "astral"}]}, registry) == ["astral-tree"]


def test_ebi_clustal_omega_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["ebi_clustal_omega"]
    assert node_info["display_name"] == "EBI Clustal Omega"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"].startswith("Run multiple sequence alignment through EMBL-EBI")
    assert node_info["output"] == ["ALIGNMENT", "NEWICK", "JSON"]
    assert node_info["output_name"] == ["alignment", "tree", "job_metadata"]
    assert node_info["requires_external_tools"] is False
    assert node_info["required_executables"] == []
    assert node_info["required_conda_packages"] == []
    assert "clustal omega" in node_info["search_aliases"]
    assert "web service" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"sequences", "email"}
    assert set(inputs["optional"]) == {
        "sequence_type",
        "output_format",
        "order",
        "dealign",
        "add_formats",
        "iterations",
        "timeout_minutes",
        "poll_interval_seconds",
        "output_name",
    }
    assert inputs["optional"]["iterations"][1]["max"] == 5


@pytest.mark.asyncio
async def test_ebi_clustalo_requests_use_shared_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("ebi_clustal_omega")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    assert isinstance(module.EBI_CLUSTALO_API_CACHE, module.APICache)
    assert isinstance(module.EBI_CLUSTALO_RATE_LIMITER, module.TokenBucketRateLimiter)

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
            text = "clustalo-job\n" if method == "POST" else "FINISHED"
            return httpx.Response(200, text=text, request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)

    post_response = await module._ebi_clustalo_request(
        "POST",
        "run",
        data={"email": "analyst@example.org", "sequence": ">seq1\nMEEP\n"},
        retries=4,
        timeout=8.0,
    )
    get_response = await module._ebi_clustalo_request("GET", "status/clustalo-job", retries=2, timeout=9.0)

    assert post_response.text == "clustalo-job\n"
    assert get_response.text == "FINISHED"
    assert calls == [
        {
            "method": "POST",
            "url": f"{module.EBI_CLUSTALO_BASE_URL}/run",
            "cache": module.EBI_CLUSTALO_API_CACHE,
            "rate_limiter": module.EBI_CLUSTALO_RATE_LIMITER,
            "data": {"email": "analyst@example.org", "sequence": ">seq1\nMEEP\n"},
            "headers": {"User-Agent": module.EBI_CLUSTALO_USER_AGENT},
            "timeout": 8.0,
            "retries": 4,
            "retry_delay": module.RETRY_DELAY_S,
            "cache_ttl": None,
            "follow_redirects": True,
        },
        {
            "method": "GET",
            "url": f"{module.EBI_CLUSTALO_BASE_URL}/status/clustalo-job",
            "cache": module.EBI_CLUSTALO_API_CACHE,
            "rate_limiter": module.EBI_CLUSTALO_RATE_LIMITER,
            "headers": {"User-Agent": module.EBI_CLUSTALO_USER_AGENT},
            "timeout": 9.0,
            "retries": 2,
            "retry_delay": module.RETRY_DELAY_S,
            "cache_ttl": None,
            "follow_redirects": True,
        },
    ]


@pytest.mark.asyncio
async def test_ebi_clustal_omega_submits_polls_and_writes_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("ebi_clustal_omega")
    module = importlib.import_module(node_class.__module__)
    posts: list[tuple[str, dict[str, Any]]] = []
    get_calls: list[str] = []
    sleeps: list[float] = []
    statuses = ["RUNNING", "FINISHED"]

    async def fake_post_text(endpoint: str, data: dict[str, Any], **_: Any) -> str:
        posts.append((endpoint, dict(data)))
        return "clustalo-R20260603-000001-0000-00000000-p1m\n"

    async def fake_get_text(endpoint: str, **_: Any) -> str:
        get_calls.append(endpoint)
        if endpoint == "status/clustalo-R20260603-000001-0000-00000000-p1m":
            return statuses.pop(0)
        if endpoint == "resulttypes/clustalo-R20260603-000001-0000-00000000-p1m":
            return (
                '<?xml version="1.0" encoding="UTF-8"?>'
                "<types>"
                "<type><identifier>out</identifier><label>Tool Output</label></type>"
                "<type><identifier>aln-fasta</identifier><label>Alignment</label></type>"
                "<type><identifier>phylotree</identifier><label>Phylogenetic Tree</label></type>"
                "</types>"
            )
        if endpoint == "result/clustalo-R20260603-000001-0000-00000000-p1m/aln-fasta":
            return ">seq1\nMEEPQSDPSV\n>seq2\nMEEPRSDPSV\n>seq3\nMEEPQADPSV\n"
        if endpoint == "result/clustalo-R20260603-000001-0000-00000000-p1m/phylotree":
            return "(seq1:0.1,(seq2:0.2,seq3:0.3):0.4);\n"
        raise AssertionError(f"Unexpected EBI GET endpoint: {endpoint}")

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(module, "_ebi_clustalo_post_text", fake_post_text)
    monkeypatch.setattr(module, "_ebi_clustalo_get_text", fake_get_text)
    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)

    result = await node_class().run(
        sequences=">seq1\nMEEPQSDPSV\n>seq2\nMEEPRSDPSV\n>seq3\nMEEPQADPSV\n",
        email="analyst@example.org",
        sequence_type="protein",
        output_format="fa",
        order="input",
        dealign=True,
        add_formats=False,
        iterations=2,
        timeout_minutes=2,
        poll_interval_seconds=0.25,
        output_name="tp53 family",
        context=_context(tmp_path, "ebi_clustal"),
    )

    alignment_path = Path(result["outputs"]["alignment"])
    tree_path = Path(result["outputs"]["tree"])
    metadata_path = Path(result["outputs"]["job_metadata"])
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert alignment_path.name == "tp53_family_alignment.fasta"
    assert alignment_path.read_text(encoding="utf-8") == ">seq1\nMEEPQSDPSV\n>seq2\nMEEPRSDPSV\n>seq3\nMEEPQADPSV\n"
    assert tree_path.name == "tp53_family_tree.nwk"
    assert tree_path.read_text(encoding="utf-8") == "(seq1:0.1,(seq2:0.2,seq3:0.3):0.4);\n"
    assert metadata_path.name == "job_metadata.json"
    assert metadata == {
        "alignment": str(alignment_path),
        "alignment_result_type": "aln-fasta",
        "job_id": "clustalo-R20260603-000001-0000-00000000-p1m",
        "params": {
            "dealign": "true",
            "email": "analyst@example.org",
            "guidetreeout": "true",
            "iterations": "2",
            "order": "input",
            "outfmt": "fa",
            "sequence": ">seq1\nMEEPQSDPSV\n>seq2\nMEEPRSDPSV\n>seq3\nMEEPQADPSV\n",
            "stype": "protein",
            "title": "bionodulo_ebi_clustal_omega",
        },
        "result_types": ["out", "aln-fasta", "phylotree"],
        "status_history": ["RUNNING", "FINISHED"],
        "tree": str(tree_path),
        "tree_result_type": "phylotree",
    }
    assert posts == [
        (
            "run",
            {
                "dealign": "true",
                "email": "analyst@example.org",
                "guidetreeout": "true",
                "iterations": "2",
                "order": "input",
                "outfmt": "fa",
                "sequence": ">seq1\nMEEPQSDPSV\n>seq2\nMEEPRSDPSV\n>seq3\nMEEPQADPSV\n",
                "stype": "protein",
                "title": "bionodulo_ebi_clustal_omega",
            },
        )
    ]
    assert get_calls == [
        "status/clustalo-R20260603-000001-0000-00000000-p1m",
        "status/clustalo-R20260603-000001-0000-00000000-p1m",
        "resulttypes/clustalo-R20260603-000001-0000-00000000-p1m",
        "result/clustalo-R20260603-000001-0000-00000000-p1m/aln-fasta",
        "result/clustalo-R20260603-000001-0000-00000000-p1m/phylotree",
    ]
    assert sleeps == [0.25]


def test_ebi_clustal_omega_plans_format_specific_outputs() -> None:
    node_class = _node_class("ebi_clustal_omega")

    default_outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")
    clustal_outputs = node_class.PLAN_OUTPUTS(
        {"output_name": "tp53 family", "output_format": "clustal_num"},
        "/tmp/run",
    )

    assert [str(path) for path in default_outputs] == [
        "/tmp/run/ebi_clustal_omega/clustal_omega_alignment.fasta",
        "/tmp/run/ebi_clustal_omega/clustal_omega_tree.nwk",
        "/tmp/run/ebi_clustal_omega/job_metadata.json",
    ]
    assert [str(path) for path in clustal_outputs] == [
        "/tmp/run/ebi_clustal_omega/tp53_family_alignment.aln",
        "/tmp/run/ebi_clustal_omega/tp53_family_tree.nwk",
        "/tmp/run/ebi_clustal_omega/job_metadata.json",
    ]


@pytest.mark.asyncio
async def test_ebi_clustal_omega_rejects_fewer_than_three_fasta_records() -> None:
    with pytest.raises(ValueError, match="at least three FASTA records"):
        await _node_class("ebi_clustal_omega")().run(
            sequences=">seq1\nMEEPQSDPSV\n>seq2\nMEEPRSDPSV\n",
            email="analyst@example.org",
        )


@pytest.mark.asyncio
async def test_ebi_clustal_omega_rejects_unsupported_iterations(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("ebi_clustal_omega")
    module = importlib.import_module(node_class.__module__)

    async def fail_submit(endpoint: str, data: dict[str, Any], **_: Any) -> str:
        raise AssertionError("unsupported iterations should be rejected before submission")

    monkeypatch.setattr(module, "_ebi_clustalo_post_text", fail_submit)

    with pytest.raises(ValueError, match="iterations"):
        await node_class().run(
            sequences=">seq1\nMEEPQSDPSV\n>seq2\nMEEPRSDPSV\n>seq3\nMEEPQADPSV\n",
            email="analyst@example.org",
            iterations=6,
        )


@pytest.mark.asyncio
async def test_ebi_clustal_omega_reports_failed_job_without_writing_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("ebi_clustal_omega")
    module = importlib.import_module(node_class.__module__)

    async def fake_post_text(endpoint: str, data: dict[str, Any], **_: Any) -> str:
        return "clustalo-failed"

    async def fake_get_text(endpoint: str, **_: Any) -> str:
        return "ERROR"

    monkeypatch.setattr(module, "_ebi_clustalo_post_text", fake_post_text)
    monkeypatch.setattr(module, "_ebi_clustalo_get_text", fake_get_text)
    context = _context(tmp_path, "ebi_clustal_failed")

    with pytest.raises(RuntimeError, match="failed with status ERROR"):
        await node_class().run(
            sequences=">seq1\nMEEPQSDPSV\n>seq2\nMEEPRSDPSV\n>seq3\nMEEPQADPSV\n",
            email="analyst@example.org",
            poll_interval_seconds=0.01,
            context=context,
        )

    assert not (context.node_dir / "ebi_clustal_omega").exists()


@pytest.mark.asyncio
async def test_ebi_clustal_omega_requires_tree_result_when_job_finishes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("ebi_clustal_omega")
    module = importlib.import_module(node_class.__module__)

    async def fake_post_text(endpoint: str, data: dict[str, Any], **_: Any) -> str:
        assert data["guidetreeout"] == "true"
        return "clustalo-no-tree"

    async def fake_get_text(endpoint: str, **_: Any) -> str:
        if endpoint == "status/clustalo-no-tree":
            return "FINISHED"
        if endpoint == "resulttypes/clustalo-no-tree":
            return (
                '<?xml version="1.0" encoding="UTF-8"?>'
                "<types>"
                "<type><identifier>out</identifier><label>Tool Output</label></type>"
                "<type><identifier>aln-fasta</identifier><label>Alignment</label></type>"
                "</types>"
            )
        if endpoint == "result/clustalo-no-tree/aln-fasta":
            return ">seq1\nMEEPQSDPSV\n>seq2\nMEEPRSDPSV\n>seq3\nMEEPQADPSV\n"
        raise AssertionError(f"Unexpected EBI GET endpoint: {endpoint}")

    monkeypatch.setattr(module, "_ebi_clustalo_post_text", fake_post_text)
    monkeypatch.setattr(module, "_ebi_clustalo_get_text", fake_get_text)
    context = _context(tmp_path, "ebi_clustal_no_tree")

    with pytest.raises(RuntimeError, match="did not provide a tree result"):
        await node_class().run(
            sequences=">seq1\nMEEPQSDPSV\n>seq2\nMEEPRSDPSV\n>seq3\nMEEPQADPSV\n",
            email="analyst@example.org",
            context=context,
        )

    assert not (context.node_dir / "ebi_clustal_omega").exists()


def test_phylot_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["phylot"]
    assert node_info["display_name"] == "PhyloT"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"].startswith("Generate taxonomy-derived phylogenetic trees")
    assert node_info["output"] == ["NEWICK", "JSON"]
    assert node_info["output_name"] == ["tree", "request_metadata"]
    assert node_info["requires_external_tools"] is False
    assert node_info["required_executables"] == []
    assert node_info["required_conda_packages"] == []
    assert "taxonomy tree" in node_info["search_aliases"]
    assert "newick" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"taxa"}
    assert set(inputs["optional"]) == {
        "taxonomy_source",
        "output_format",
        "node_identifiers",
        "collapse_internal_nodes",
        "force_binary_tree",
        "interrupt_at",
        "filter_terms",
        "ignore_errors",
        "gtdb_source",
        "include_gtdb_branch_support",
        "include_gtdb_genome_ids",
        "gtdb_version",
        "output_name",
    }


@pytest.mark.asyncio
async def test_phylot_requests_use_shared_http_client(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("phylot")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    assert isinstance(module.PHYLOT_API_CACHE, module.APICache)
    assert isinstance(module.PHYLOT_RATE_LIMITER, module.TokenBucketRateLimiter)

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
            return httpx.Response(200, text="(Homo_sapiens,Mus_musculus);\n", request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)

    response = await module._phylot_request(
        "treeGenerator.cgi",
        data={"treeElements": "Homo sapiens\nMus musculus", "format": "newick"},
        retries=4,
        timeout=8.0,
    )

    assert response.text == "(Homo_sapiens,Mus_musculus);\n"
    assert calls == [
        {
            "method": "POST",
            "url": f"{module.PHYLOT_BASE_URL}/treeGenerator.cgi",
            "cache": module.PHYLOT_API_CACHE,
            "rate_limiter": module.PHYLOT_RATE_LIMITER,
            "data": {"treeElements": "Homo sapiens\nMus musculus", "format": "newick"},
            "headers": {"User-Agent": module.PHYLOT_USER_AGENT},
            "timeout": 8.0,
            "retries": 4,
            "retry_delay": module.RETRY_DELAY_S,
            "cache_ttl": None,
            "follow_redirects": True,
        }
    ]


@pytest.mark.asyncio
async def test_phylot_posts_ncbi_form_and_writes_tree_and_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("phylot")
    module = importlib.import_module(node_class.__module__)
    calls: list[tuple[str, dict[str, str]]] = []

    async def fake_request_text(endpoint: str, data: dict[str, str], **_: Any) -> str:
        calls.append((endpoint, data))
        return "((Homo_sapiens,Mus_musculus)Mammalia,Escherichia_coli);\n"

    monkeypatch.setattr(module, "_phylot_request_text", fake_request_text)

    tree_path, metadata_path = await node_class().run(
        taxa="Homo sapiens, Mus musculus\nEscherichia coli",
        taxonomy_source="ncbi",
        output_format="newick",
        node_identifiers="name",
        collapse_internal_nodes=True,
        force_binary_tree=True,
        interrupt_at="genus",
        filter_terms="unclassified,environmental sample",
        ignore_errors=True,
        output_name="mammals_ecoli",
        context=_context(tmp_path, "phylot"),
    )

    assert Path(tree_path).name == "mammals_ecoli.nwk"
    assert Path(tree_path).read_text(encoding="utf-8") == "((Homo_sapiens,Mus_musculus)Mammalia,Escherichia_coli);\n"
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    assert metadata == {
        "endpoint": "treeGenerator.cgi",
        "format": "newick",
        "taxonomy_source": "ncbi",
        "taxa_count": 3,
        "tree": str(Path(tree_path)),
        "params": {
            "binary": "1",
            "collapse": "1",
            "fileName": "mammals_ecoli",
            "filter": "unclassified,environmental sample",
            "format": "newick",
            "ids": "name",
            "interrupt": "genus",
            "itol": "0",
            "itolProject": "0",
            "noerror": "1",
            "phylot": "1",
            "treeElements": "Homo sapiens\nMus musculus\nEscherichia coli",
        },
    }
    assert calls == [("treeGenerator.cgi", metadata["params"])]


@pytest.mark.asyncio
async def test_phylot_posts_gtdb_form_and_uses_format_extension(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("phylot")
    module = importlib.import_module(node_class.__module__)
    calls: list[tuple[str, dict[str, str]]] = []

    async def fake_request_text(endpoint: str, data: dict[str, str], **_: Any) -> str:
        calls.append((endpoint, data))
        return "#NEXUS\nBegin trees;\nTree tree1 = (s__Escherichia_coli,s__Vibrio_cholerae);\nEnd;\n"

    monkeypatch.setattr(module, "_phylot_request_text", fake_request_text)

    tree_path, metadata_path = await node_class().run(
        taxa=["s__Escherichia coli", "s__Vibrio cholerae"],
        taxonomy_source="gtdb",
        output_format="nexus",
        gtdb_source="ar",
        include_gtdb_branch_support=False,
        include_gtdb_genome_ids=True,
        gtdb_version="232",
        output_name="gtdb_pair",
        context=_context(tmp_path, "phylot_gtdb"),
    )

    assert Path(tree_path).name == "gtdb_pair.nex"
    assert Path(tree_path).read_text(encoding="utf-8").startswith("#NEXUS\n")
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    assert metadata["endpoint"] == "treeGeneratorGTD.cgi"
    assert metadata["format"] == "nexus"
    assert metadata["taxonomy_source"] == "gtdb"
    assert metadata["taxa_count"] == 2
    assert calls == [
        (
            "treeGeneratorGTD.cgi",
            {
                "boot": "0",
                "fileName": "gtdb_pair",
                "filter": "",
                "format": "nexus",
                "gtdb_version": "232",
                "gid": "1",
                "interrupt": "0",
                "itol": "0",
                "itolProject": "0",
                "noerror": "0",
                "phylotgtd": "1",
                "src": "ar",
                "treeElements": "s__Escherichia coli\ns__Vibrio cholerae",
            },
        )
    ]


def test_phylot_plans_outputs_from_output_name_and_format() -> None:
    node_class = _node_class("phylot")

    default_outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")
    nexus_outputs = node_class.PLAN_OUTPUTS(
        {"output_name": "gtdb pair", "output_format": "nexus"},
        "/tmp/run",
    )

    assert [str(path) for path in default_outputs] == [
        "/tmp/run/phylot/phylot_tree.nwk",
        "/tmp/run/phylot/request_metadata.json",
    ]
    assert [str(path) for path in nexus_outputs] == [
        "/tmp/run/phylot/gtdb_pair.nex",
        "/tmp/run/phylot/request_metadata.json",
    ]


@pytest.mark.asyncio
async def test_phylot_rejects_html_error_response_without_writing_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("phylot")
    module = importlib.import_module(node_class.__module__)

    async def fake_request_text(endpoint: str, data: dict[str, str], **_: Any) -> str:
        return """
<!DOCTYPE html>
<html lang="en">
<head><title>phyloT: Invalid IDs</title></head>
<body><h2>Error: Invalid IDs</h2><p>DefinitelyNotATaxon</p></body>
</html>
"""

    monkeypatch.setattr(module, "_phylot_request_text", fake_request_text)
    context = _context(tmp_path, "phylot_error")

    with pytest.raises(RuntimeError, match="Invalid IDs"):
        await node_class().run(
            taxa="DefinitelyNotATaxon,StillNotATaxon",
            context=context,
        )

    assert not (context.node_dir / "phylot").exists()


@pytest.mark.asyncio
async def test_phylot_rejects_empty_taxa(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least two taxa or one subtree"):
        await _node_class("phylot")().run(
            taxa="Homo sapiens",
            context=_context(tmp_path, "phylot_empty"),
        )


def test_phylogenetic_tree_builder_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["phylogenetic_tree_builder"]
    assert node_info["display_name"] == "Phylo Tree Builder"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"].startswith("Build phylogenetic trees using multiple methods")
    assert node_info["output"] == ["NEWICK", "JSON"]
    assert node_info["output_name"] == ["consensus_tree", "individual_trees"]
    assert node_info["requires_external_tools"] is False
    assert node_info["required_conda_packages"] == ["biopython"]
    assert "consensus tree" in node_info["search_aliases"]
    assert "newick" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"tree_files"}
    assert set(inputs["optional"]) == {"methods", "consensus_method"}


@pytest.mark.asyncio
async def test_phylogenetic_tree_builder_writes_consensus_and_manifest(tmp_path: Path) -> None:
    iqtree = tmp_path / "iqtree.treefile"
    raxml = tmp_path / "raxml.bestTree"
    fasttree = tmp_path / "fasttree.nwk"
    iqtree.write_text("((A:0.1,B:0.2):0.3,C:0.4);\n", encoding="utf-8")
    raxml.write_text("((A:0.1,B:0.2):0.3,C:0.4);\n", encoding="utf-8")
    fasttree.write_text("(A:0.1,(B:0.2,C:0.4):0.3);\n", encoding="utf-8")

    consensus_path, manifest_path = await _node_class("phylogenetic_tree_builder")().run(
        tree_files="\n".join([str(iqtree), str(raxml), str(fasttree)]),
        methods="iqtree,raxml_ng,fasttree",
        consensus_method="majority",
        context=_context(tmp_path, "phylo_builder"),
    )

    assert Path(consensus_path).name == "consensus_tree.nwk"

    # Assert the tree, not its spelling. Biopython chooses how many decimal
    # places to write branch lengths and has changed that between releases --
    # the same tree came out as "0.10000" and later as "0.1" -- so comparing the
    # file byte-for-byte tests the library's formatting rather than our output.
    from Bio import Phylo

    consensus = Phylo.read(consensus_path, "newick")
    assert sorted(leaf.name for leaf in consensus.get_terminals()) == ["A", "B", "C"]
    lengths = {
        leaf.name: pytest.approx(leaf.branch_length, abs=1e-6)
        for leaf in consensus.get_terminals()
    }
    assert lengths == {"A": 0.1, "B": 0.2, "C": 0.4}
    # A and B are siblings; C joins above them.
    assert sorted(
        leaf.name for leaf in consensus.common_ancestor(["A", "B"]).get_terminals()
    ) == ["A", "B"]

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    assert manifest["consensus_method"] == "majority"
    assert manifest["selected_tree_index"] == 0
    assert manifest["tree_count"] == 3
    assert [entry["method"] for entry in manifest["trees"]] == ["iqtree", "raxml_ng", "fasttree"]
    assert manifest["trees"][0]["support_count"] == 2


@pytest.mark.asyncio
async def test_phylogenetic_tree_builder_rejects_missing_tree_files(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="At least one tree file is required"):
        await _node_class("phylogenetic_tree_builder")().run(
            tree_files="",
            methods="",
            consensus_method="first",
            context=_context(tmp_path, "phylo_builder"),
        )
