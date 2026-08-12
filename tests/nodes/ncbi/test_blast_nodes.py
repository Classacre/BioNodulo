"""Focused Common URL API submission, polling, and result-parser contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.ncbi_family import NCBIBLASTNode, NCBIBLASTParseNode
from bionodulo.nodes.builtin.ncbi_family import blast
from bionodulo.nodes.builtin.ncbi_family.blast import BLAST_OUTPUT_FORMATS, retrieval_params
from bionodulo.nodes.builtin.ncbi_family.blast_parse import (
    parse_json2_hits,
    parse_xml2_hits,
)


def test_blast_authorities_and_formats() -> None:
    assert NCBIBLASTNode.SOURCE_SHA256 == ("c864df25b8608d705cde6aee9344aba3e3a5ef7b16a0c8ca9e221e418aab83f3")
    assert NCBIBLASTNode.DEVELOPER_SOURCE_SHA256 == ("73dd88056332b1b21de8bfc2cbd272af03cae803c15c0cedf33c9c45a2171682")
    assert "XML" not in BLAST_OUTPUT_FORMATS
    assert {"XML2", "JSON2", "JSONSA", "SAM", "Tabular", "CSV"}.issubset(BLAST_OUTPUT_FORMATS)
    assert retrieval_params("RID1", "Tabular") == {
        "CMD": "Get",
        "RID": "RID1",
        "FORMAT_TYPE": "Text",
        "ALIGNMENT_VIEW": "Tabular",
    }
    assert retrieval_params("RID1", "CSV") == {
        "CMD": "Get",
        "RID": "RID1",
        "FORMAT_TYPE": "CSV",
        "ALIGNMENT_VIEW": "Tabular",
    }
    assert NCBIBLASTParseNode.INPUT_TYPES()["optional"]["input_format"][0] == [
        "auto",
        "JSON2",
        "XML2",
    ]


@pytest.mark.asyncio
async def test_blast_submission_uses_only_documented_put_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    async def fake_request(method: str, params: dict[str, Any]) -> str:
        calls.append((method, params))
        return "RID = TEST_RID\nRTOE = 75\n"

    monkeypatch.setattr(blast, "request_blast_text", fake_request)
    result = await NCBIBLASTNode()._submit_blast_job(
        query=">query\nACGT",
        program="megablast",
        database="nt",
        evalue=0.001,
        max_hits=25,
        email="",
    )

    assert result == ("TEST_RID", 75)
    assert calls == [
        (
            "POST",
            {
                "CMD": "Put",
                "QUERY": ">query\nACGT",
                "PROGRAM": "blastn",
                "DATABASE": "nt",
                "EXPECT": "0.001",
                "HITLIST_SIZE": "25",
                "tool": "bionodulo",
                "MEGABLAST": "on",
            },
        )
    ]


@pytest.mark.asyncio
async def test_blast_polling_honors_rtoe_and_one_minute_per_rid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(["Status=WAITING", '{"BlastOutput2": []}'])
    requests: list[tuple[str, dict[str, Any]]] = []
    sleeps: list[float] = []
    now = [0.0]

    async def fake_request(method: str, params: dict[str, Any]) -> str:
        requests.append((method, params))
        return next(responses)

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(blast, "request_blast_text", fake_request)
    result = await NCBIBLASTNode()._poll_blast_results(
        rid="TEST_RID",
        output_format="JSON2",
        rtoe_seconds=90,
        timeout_minutes=5,
        poll_interval_seconds=60,
        sleep=fake_sleep,
        clock=lambda: now[0],
    )

    assert result == '{"BlastOutput2": []}'
    assert sleeps == [90.0, 60.0]
    assert requests == [
        ("GET", {"CMD": "Get", "RID": "TEST_RID", "FORMAT_TYPE": "JSON2"}),
        ("GET", {"CMD": "Get", "RID": "TEST_RID", "FORMAT_TYPE": "JSON2"}),
    ]


def test_blast_validation_rejects_rapid_rid_polling() -> None:
    validation = NCBIBLASTNode.VALIDATE_INPUTS(
        {
            "query_sequence": "ACGT",
            "program": "blastn",
            "database": "nt",
            "poll_interval_seconds": 30.0,
        }
    )
    assert validation == "Input 'poll_interval_seconds' must be at least 60"


@pytest.mark.asyncio
async def test_blast_run_writes_result_and_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_results = {
        "BlastOutput2": [
            {
                "report": {
                    "results": {
                        "search": {
                            "query_title": "query",
                            "hits": [{"description": [], "hsps": []}],
                            "stat": {"db_num": 1},
                        }
                    }
                }
            }
        ]
    }

    async def fake_submit(self: NCBIBLASTNode, **kwargs: Any) -> tuple[str, int]:
        return "RID42", 12

    async def fake_poll(self: NCBIBLASTNode, **kwargs: Any) -> str:
        return json.dumps(raw_results)

    class Context:
        node_dir = tmp_path

    monkeypatch.setattr(NCBIBLASTNode, "_submit_blast_job", fake_submit)
    monkeypatch.setattr(NCBIBLASTNode, "_poll_blast_results", fake_poll)
    result = await NCBIBLASTNode().run(
        context=Context(),
        query_sequence="ACGT",
        program="blastn",
        database="nt",
        output_format="JSON2",
    )

    results_path = Path(result["outputs"]["blast_results"])
    summary_path = Path(result["outputs"]["blast_summary"])
    assert json.loads(results_path.read_text(encoding="utf-8")) == raw_results
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["rid"] == "RID42"
    assert summary["rtoe_seconds"] == 12
    assert summary["num_hits"] == 1


def test_json2_parser_extracts_first_hsp_per_hit() -> None:
    raw = json.dumps(
        {
            "BlastOutput2": [
                {
                    "report": {
                        "results": {
                            "search": {
                                "query_title": "query 1",
                                "hits": [
                                    {
                                        "description": [
                                            {"id": "ref|X1|", "title": "subject", "sciname": "Example species"}
                                        ],
                                        "hsps": [
                                            {
                                                "identity": 45,
                                                "align_len": 50,
                                                "evalue": 1e-20,
                                                "bit_score": 100.5,
                                                "query_from": 1,
                                                "query_to": 50,
                                                "hit_from": 5,
                                                "hit_to": 54,
                                            }
                                        ],
                                    }
                                ],
                            }
                        }
                    }
                }
            ]
        }
    )

    assert parse_json2_hits(raw) == [
        {
            "query": "query 1",
            "subject_id": "ref|X1|",
            "subject_title": "subject",
            "scientific_name": "Example species",
            "percent_identity": 90.0,
            "evalue": 1e-20,
            "bit_score": 100.5,
            "alignment_length": 50,
            "query_from": 1,
            "query_to": 50,
            "subject_from": 5,
            "subject_to": 54,
        }
    ]


def test_xml2_parser_is_namespace_agnostic() -> None:
    raw = """<?xml version="1.0"?>
<BlastXML2 xmlns="http://www.ncbi.nlm.nih.gov">
  <report><Report><results><Results><search><Search>
    <query-id>Query_1</query-id><query-title>query 1</query-title>
    <hits><Hit><description><HitDescr>
      <id>ref|X1|</id><title>subject</title><sciname>Example species</sciname>
    </HitDescr></description><hsps><Hsp>
      <bit-score>100.5</bit-score><evalue>1e-20</evalue><identity>45</identity>
      <align-len>50</align-len><query-from>1</query-from><query-to>50</query-to>
      <hit-from>5</hit-from><hit-to>54</hit-to>
    </Hsp></hsps></Hit></hits>
  </Search></search></Results></results></Report></report>
</BlastXML2>"""

    hits = parse_xml2_hits(raw)
    assert len(hits) == 1
    assert hits[0]["query"] == "query 1"
    assert hits[0]["subject_id"] == "ref|X1|"
    assert hits[0]["scientific_name"] == "Example species"
    assert hits[0]["percent_identity"] == 90.0
