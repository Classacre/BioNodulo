from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_ncbi_nodes_are_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["ncbi_esearch"]["display_name"] == "NCBI ESearch"
    assert info["ncbi_esearch"]["category"] == "databases"
    assert info["ncbi_efetch"]["display_name"] == "NCBI EFetch"
    assert info["ncbi_efetch"]["category"] == "databases"
    assert info["ncbi_blast"]["display_name"] == "NCBI BLAST"
    assert info["ncbi_blast"]["category"] == "databases"
    assert info["ncbi_blast"]["output_name"] == ["blast_results", "blast_summary"]
    assert info["geo_query"]["display_name"] == "GEO Query"
    assert info["geo_query"]["category"] == "databases"
    assert info["geo_query"]["output_name"] == ["geo_metadata", "sample_table"]
    assert info["sra_download"]["display_name"] == "SRA Download"
    assert info["sra_download"]["category"] == "databases"
    assert info["sra_download"]["output_name"] == ["fastq_files", "download_report"]
    assert info["sra_download"]["required_executables"] == ["prefetch", "fasterq-dump"]
    assert registry.get("sra_download").REQUIRES_EXTERNAL_TOOLS is True
    assert info["sra_fetch"]["display_name"] == "SRA Fetch"
    assert info["sra_fetch"]["category"] == "databases"
    assert info["sra_fetch"]["output_name"] == ["fastq_files", "download_report"]
    assert info["sra_fetch"]["required_executables"] == ["prefetch", "fasterq-dump"]
    assert registry.get("sra_fetch").REQUIRES_EXTERNAL_TOOLS is True
    assert issubclass(registry.get("sra_fetch"), registry.get("sra_download"))


@pytest.mark.asyncio
async def test_ncbi_request_uses_shared_http_client_with_api_key_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_class = _node_class("ncbi_esearch")
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
            request = httpx.Request(method, url, params=kwargs.get("params"), headers=kwargs.get("headers"))
            return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(module, "APIHttpClient", FakeClient)

    response = await module._request(
        "esearch.fcgi",
        {"db": "gene", "term": "TP53", "retmode": "json", "api_key": "secret-key", "empty": ""},
        retries=4,
        timeout=6.5,
    )

    assert response.json() == {"ok": True}
    assert len(calls) == 1
    assert calls[0]["method"] == "GET"
    assert calls[0]["url"] == f"{module.NCBI_BASE_URL}/esearch.fcgi"
    assert calls[0]["params"] == {
        "db": "gene",
        "term": "TP53",
        "retmode": "json",
        "api_key": "secret-key",
    }
    assert calls[0]["headers"] == {"User-Agent": module.NCBI_USER_AGENT}
    assert calls[0]["timeout"] == 6.5
    assert calls[0]["retries"] == 4
    assert calls[0]["retry_delay"] == module.RETRY_DELAY_S
    assert calls[0]["cache_ttl"] == module.NCBI_CACHE_TTL_S
    assert calls[0]["cache"] is module.NCBI_API_CACHE
    assert calls[0]["rate_limiter"] is module.NCBI_API_KEY_RATE_LIMITER


@pytest.mark.asyncio
async def test_ncbi_esearch_returns_ids_count_and_query_translation(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("ncbi_esearch")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_json(endpoint: str, params: dict[str, Any], **_: Any) -> dict[str, Any]:
        calls.append({"endpoint": endpoint, "params": dict(params)})
        return {
            "esearchresult": {
                "count": "2",
                "idlist": ["7157", "22059"],
                "querytranslation": "TP53[All Fields]",
            }
        }

    monkeypatch.setattr(module, "_request_json", fake_json)
    context = SimpleNamespace(resolve_secret=lambda key: "secret-key" if key == "ncbi_api_key" else None)

    result = await node_class().run(
        query="TP53",
        database="gene",
        max_results=5,
        sort="relevance",
        api_key="",
        context=context,
    )

    assert result["outputs"] == {
        "id_list": ["7157", "22059"],
        "total_count": 2,
        "query_translation": "TP53[All Fields]",
    }
    assert calls == [
        {
            "endpoint": "esearch.fcgi",
            "params": {
                "db": "gene",
                "term": "TP53",
                "retmode": "json",
                "retmax": 5,
                "sort": "relevance",
                "api_key": "secret-key",
            },
        }
    ]


@pytest.mark.asyncio
async def test_ncbi_esearch_resolves_api_key_credential_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    node_class = _node_class("ncbi_esearch")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_json(endpoint: str, params: dict[str, Any], **_: Any) -> dict[str, Any]:
        calls.append({"endpoint": endpoint, "params": dict(params)})
        return {"esearchresult": {"count": "0", "idlist": [], "querytranslation": "BRCA1[All Fields]"}}

    monkeypatch.setattr(module, "_request_json", fake_json)
    context = SimpleNamespace(resolve_secret=lambda key: "resolved-ncbi-key" if key == "ncbi_prod" else None)

    await node_class().run(
        query="BRCA1",
        database="gene",
        max_results=1,
        sort="relevance",
        api_key="credential://ncbi_prod",
        context=context,
    )

    assert calls[0]["params"]["api_key"] == "resolved-ncbi-key"
    assert "credential://ncbi_prod" not in json.dumps(calls, sort_keys=True)


@pytest.mark.asyncio
async def test_ncbi_efetch_writes_records_and_returns_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("ncbi_efetch")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_text(endpoint: str, params: dict[str, Any], **_: Any) -> str:
        calls.append({"endpoint": endpoint, "params": dict(params)})
        return ">NM_000546.6 TP53\nATGC\n"

    monkeypatch.setattr(module, "_request_text", fake_text)
    context = SimpleNamespace(node_dir=tmp_path, resolve_secret=lambda _key: None)

    result = await node_class().run(
        id_list=["NM_000546.6"],
        database="nuccore",
        rettype="fasta",
        retmode="text",
        api_key="explicit-key",
        output_name="tp53.fasta",
        context=context,
    )

    records_path = Path(result["outputs"]["records"])
    assert records_path.read_text(encoding="utf-8") == ">NM_000546.6 TP53\nATGC\n"
    assert result["outputs"]["metadata"] == {
        "database": "nuccore",
        "ids": ["NM_000546.6"],
        "rettype": "fasta",
        "retmode": "text",
        "record_count": 1,
        "records_path": str(records_path),
    }
    assert calls == [
        {
            "endpoint": "efetch.fcgi",
            "params": {
                "db": "nuccore",
                "id": "NM_000546.6",
                "rettype": "fasta",
                "retmode": "text",
                "api_key": "explicit-key",
            },
        }
    ]


@pytest.mark.asyncio
async def test_ncbi_blast_submits_polls_and_writes_results(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("ncbi_blast")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []
    sleeps: list[float] = []

    result_json = (
        '{"BlastOutput2":[{"report":{"results":{"search":{'
        '"query_title":"query","hits":[{"description":[{"title":"TP53 hit"}]}],'
        '"stat":{"db_num":1}}}}}]}'
    )
    responses = [
        "RID = TESTRID123\nRTOE = 7\n",
        "Status=WAITING\n",
        "Status=READY\n",
        result_json,
    ]

    async def fake_blast_request_text(method: str, params: dict[str, Any], **_: Any) -> str:
        calls.append({"method": method, "params": dict(params)})
        return responses.pop(0)

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(module, "_blast_request_text", fake_blast_request_text)
    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)
    context = SimpleNamespace(node_dir=tmp_path)

    result = await node_class().run(
        query_sequence="ATGCATGC",
        program="blastn",
        database="nt",
        evalue=1e-5,
        max_hits=25,
        output_format="JSON2",
        timeout_minutes=2,
        context=context,
    )

    results_path = Path(result["outputs"]["blast_results"])
    summary_path = Path(result["outputs"]["blast_summary"])
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert results_path.name == "blast_results.json"
    assert results_path.read_text(encoding="utf-8") == result_json
    assert summary_path.name == "blast_summary.json"
    assert summary == {
        "rid": "TESTRID123",
        "rtoe_seconds": 7,
        "program": "blastn",
        "database": "nt",
        "format": "JSON2",
        "num_hits": 1,
        "query": "query",
        "stat": {"db_num": 1},
        "results_path": str(results_path),
    }
    assert sleeps == [60.0, 60.0]
    assert calls == [
        {
            "method": "POST",
            "params": {
                "CMD": "Put",
                "QUERY": ">query\nATGCATGC",
                "PROGRAM": "blastn",
                "DATABASE": "nt",
                "EXPECT": "1e-05",
                "HITLIST_SIZE": "25",
                "FORMAT_TYPE": "JSON2",
                "tool": "bionodulo",
                "email": "bionodulo@example.com",
            },
        },
        {
            "method": "GET",
            "params": {
                "CMD": "Get",
                "RID": "TESTRID123",
                "FORMAT_OBJECT": "SearchInfo",
            },
        },
        {
            "method": "GET",
            "params": {
                "CMD": "Get",
                "RID": "TESTRID123",
                "FORMAT_OBJECT": "SearchInfo",
            },
        },
        {
            "method": "GET",
            "params": {
                "CMD": "Get",
                "RID": "TESTRID123",
                "FORMAT_TYPE": "JSON2",
            },
        },
    ]


@pytest.mark.asyncio
async def test_ncbi_blast_uses_megablast_api_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("ncbi_blast")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_blast_request_text(method: str, params: dict[str, Any], **_: Any) -> str:
        calls.append({"method": method, "params": dict(params)})
        if params["CMD"] == "Put":
            return "RID = MEGABLAST1\n"
        if params.get("FORMAT_OBJECT") == "SearchInfo":
            return "Status=READY\n"
        return "No hits"

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(module, "_blast_request_text", fake_blast_request_text)
    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)

    await node_class().run(
        query_sequence=">query\nATGC",
        program="megablast",
        database="nt",
        output_format="Text",
        timeout_minutes=1,
        context=SimpleNamespace(node_dir=tmp_path),
    )

    assert calls[0]["params"]["PROGRAM"] == "blastn"
    assert calls[0]["params"]["MEGABLAST"] == "on"


@pytest.mark.asyncio
async def test_ncbi_blast_rejects_invalid_program() -> None:
    node_class = _node_class("ncbi_blast")

    with pytest.raises(ValueError, match="Unsupported BLAST program"):
        await node_class().run(query_sequence="ATGC", program="diamond", database="nt")


@pytest.mark.asyncio
async def test_geo_query_search_writes_metadata_and_sample_table(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("geo_query")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_json(endpoint: str, params: dict[str, Any], **_: Any) -> dict[str, Any]:
        calls.append({"endpoint": endpoint, "params": dict(params)})
        if endpoint == "esearch.fcgi":
            return {"esearchresult": {"count": "2", "idlist": ["200001", "200002"]}}
        return {
            "result": {
                "uids": ["200001", "200002"],
                "200001": {
                    "uid": "200001",
                    "accession": "GSE100001",
                    "title": "Breast cancer RNA-seq cohort",
                    "entryType": "GSE",
                    "gdsType": "Expression profiling by high throughput sequencing",
                    "n_samples": "12",
                    "taxon": "Homo sapiens",
                    "GPL": "GPL11154",
                    "PDAT": "2025/01/02",
                },
                "200002": {
                    "uid": "200002",
                    "accession": "GSE100002",
                    "title": "Control RNA-seq cohort",
                    "entryType": "GSE",
                    "gdsType": "Expression profiling by high throughput sequencing",
                    "n_samples": "8",
                    "taxon": "Homo sapiens",
                    "GPL": "GPL18573",
                    "PDAT": "2025/01/03",
                },
            }
        }

    monkeypatch.setattr(module, "_request_json", fake_json)
    context = SimpleNamespace(
        node_dir=tmp_path,
        resolve_secret=lambda key: "secret-key" if key == "ncbi_api_key" else None,
    )

    result = await node_class().run(
        accession="",
        query_type="search",
        search_query="breast cancer RNA-seq",
        max_results=2,
        api_key="",
        context=context,
    )

    metadata_path = Path(result["outputs"]["geo_metadata"])
    table_path = Path(result["outputs"]["sample_table"])
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert metadata_path.name == "geo_search_results.json"
    assert table_path.name == "geo_results.tsv"
    assert metadata["query"] == "breast cancer RNA-seq"
    assert metadata["query_type"] == "search"
    assert metadata["uids"] == ["200001", "200002"]
    assert metadata["record_count"] == 2
    assert [entry["accession"] for entry in metadata["summaries"]] == ["GSE100001", "GSE100002"]
    assert table_path.read_text(encoding="utf-8") == (
        "uid\taccession\ttitle\tentry_type\tgds_type\tn_samples\torganism\tplatform\tpublication_date\n"
        "200001\tGSE100001\tBreast cancer RNA-seq cohort\tGSE\tExpression profiling by high throughput sequencing\t12\tHomo sapiens\tGPL11154\t2025/01/02\n"
        "200002\tGSE100002\tControl RNA-seq cohort\tGSE\tExpression profiling by high throughput sequencing\t8\tHomo sapiens\tGPL18573\t2025/01/03\n"
    )
    assert calls == [
        {
            "endpoint": "esearch.fcgi",
            "params": {
                "db": "gds",
                "term": "breast cancer RNA-seq",
                "retmode": "json",
                "retmax": 2,
                "tool": "bionodulo",
                "email": "bionodulo@example.com",
                "api_key": "secret-key",
            },
        },
        {
            "endpoint": "esummary.fcgi",
            "params": {
                "db": "gds",
                "id": "200001,200002",
                "retmode": "json",
                "tool": "bionodulo",
                "email": "bionodulo@example.com",
                "api_key": "secret-key",
            },
        },
    ]


@pytest.mark.asyncio
async def test_geo_query_accession_lookup_uses_accession_search(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("geo_query")
    module = importlib.import_module(node_class.__module__)
    calls: list[dict[str, Any]] = []

    async def fake_json(endpoint: str, params: dict[str, Any], **_: Any) -> dict[str, Any]:
        calls.append({"endpoint": endpoint, "params": dict(params)})
        if endpoint == "esearch.fcgi":
            return {"esearchresult": {"count": "1", "idlist": ["300001"]}}
        return {
            "result": {
                "uids": ["300001"],
                "300001": {
                    "uid": "300001",
                    "accession": "GSE300001",
                    "title": "Single GEO series",
                    "entryType": "GSE",
                    "gdsType": "Series",
                    "n_samples": "3",
                },
            }
        }

    monkeypatch.setattr(module, "_request_json", fake_json)
    context = SimpleNamespace(node_dir=tmp_path, resolve_secret=lambda _key: None)

    result = await node_class().run(
        accession="GSE300001",
        query_type="series",
        max_results=5,
        context=context,
    )

    metadata = json.loads(Path(result["outputs"]["geo_metadata"]).read_text(encoding="utf-8"))

    assert metadata["query"] == "GSE300001[ACCN] AND gse[ETYP]"
    assert metadata["query_type"] == "series"
    assert metadata["uids"] == ["300001"]
    assert metadata["record_count"] == 1
    assert calls[0] == {
        "endpoint": "esearch.fcgi",
        "params": {
            "db": "gds",
            "term": "GSE300001[ACCN] AND gse[ETYP]",
            "retmode": "json",
            "retmax": 5,
            "tool": "bionodulo",
            "email": "bionodulo@example.com",
        },
    }


@pytest.mark.asyncio
async def test_geo_query_rejects_empty_search() -> None:
    node_class = _node_class("geo_query")

    with pytest.raises(ValueError, match="requires search_query or accession"):
        await node_class().run(accession="", query_type="search", search_query="")


@pytest.mark.asyncio
async def test_sra_download_prefetches_dumps_and_reports_fastq_files(tmp_path: Path) -> None:
    node_class = _node_class("sra_download")
    commands: list[dict[str, Any]] = []

    async def fake_run_command(cmd: list[str], cwd: str) -> dict[str, Any]:
        commands.append({"cmd": list(cmd), "cwd": cwd})
        if cmd[0] == "fasterq-dump":
            accession = cmd[-1]
            Path(cwd, f"{accession}_1.fastq").write_text("@read/1\nACGT\n+\n!!!!\n", encoding="utf-8")
            Path(cwd, f"{accession}_2.fastq").write_text("@read/2\nTGCA\n+\n!!!!\n", encoding="utf-8")
        return {"returncode": 0, "stdout": "", "stderr": ""}

    context = SimpleNamespace(node_dir=tmp_path, run_command=fake_run_command)

    result = await node_class().run(
        accessions="SRR000001, SRR000002",
        split_files=True,
        threads=8,
        skip_technical=True,
        output_format="fastq",
        context=context,
    )

    out_dir = tmp_path / "sra_download"
    fastq_files = result["outputs"]["fastq_files"]
    report_path = Path(result["outputs"]["download_report"])
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert [Path(path).name for path in fastq_files] == [
        "SRR000001_1.fastq",
        "SRR000001_2.fastq",
        "SRR000002_1.fastq",
        "SRR000002_2.fastq",
    ]
    assert report_path == out_dir / "download_report.json"
    assert report == [
        {
            "accession": "SRR000001",
            "status": "completed",
            "files": [str(out_dir / "SRR000001_1.fastq"), str(out_dir / "SRR000001_2.fastq")],
        },
        {
            "accession": "SRR000002",
            "status": "completed",
            "files": [str(out_dir / "SRR000002_1.fastq"), str(out_dir / "SRR000002_2.fastq")],
        },
    ]
    assert commands == [
        {"cmd": ["prefetch", "-O", str(out_dir), "SRR000001"], "cwd": str(out_dir)},
        {
            "cmd": [
                "fasterq-dump",
                "--outdir",
                str(out_dir),
                "--threads",
                "8",
                "--split-files",
                "--skip-technical",
                "SRR000001",
            ],
            "cwd": str(out_dir),
        },
        {"cmd": ["prefetch", "-O", str(out_dir), "SRR000002"], "cwd": str(out_dir)},
        {
            "cmd": [
                "fasterq-dump",
                "--outdir",
                str(out_dir),
                "--threads",
                "8",
                "--split-files",
                "--skip-technical",
                "SRR000002",
            ],
            "cwd": str(out_dir),
        },
    ]


@pytest.mark.asyncio
async def test_sra_download_continues_after_prefetch_failure(tmp_path: Path) -> None:
    node_class = _node_class("sra_download")
    commands: list[list[str]] = []

    async def fake_run_command(cmd: list[str], cwd: str) -> dict[str, Any]:
        commands.append(list(cmd))
        if cmd[0] == "prefetch" and cmd[-1] == "SRRFAILED":
            return {"returncode": 1, "stdout": "", "stderr": "cannot download accession"}
        if cmd[0] == "fasterq-dump":
            Path(cwd, f"{cmd[-1]}.fastq").write_text("@read\nACGT\n+\n!!!!\n", encoding="utf-8")
        return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await node_class().run(
        accessions=["SRRFAILED", "SRROK"],
        split_files=False,
        threads=2,
        skip_technical=False,
        output_format="fastq",
        context=SimpleNamespace(node_dir=tmp_path, run_command=fake_run_command),
    )

    report = json.loads(Path(result["outputs"]["download_report"]).read_text(encoding="utf-8"))

    assert [Path(path).name for path in result["outputs"]["fastq_files"]] == ["SRROK.fastq"]
    assert report[0] == {
        "accession": "SRRFAILED",
        "status": "prefetch_failed",
        "files": [],
        "error": "cannot download accession",
    }
    assert report[1]["status"] == "completed"
    assert commands == [
        ["prefetch", "-O", str(tmp_path / "sra_download"), "SRRFAILED"],
        ["prefetch", "-O", str(tmp_path / "sra_download"), "SRROK"],
        [
            "fasterq-dump",
            "--outdir",
            str(tmp_path / "sra_download"),
            "--threads",
            "2",
            "SRROK",
        ],
    ]


@pytest.mark.asyncio
async def test_sra_download_rejects_empty_accessions_and_bad_format() -> None:
    node_class = _node_class("sra_download")

    with pytest.raises(ValueError, match="requires at least one accession"):
        await node_class().run(accessions="")

    with pytest.raises(ValueError, match="Unsupported SRA output_format"):
        await node_class().run(accessions="SRR000001", output_format="bam")
