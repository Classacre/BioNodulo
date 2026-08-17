"""Contract, fixture-mode, and mocked-HTTP coverage for the NIM family."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from bionodulo.nodes.builtin.nim_family import adapter as nim_adapter
from bionodulo.nodes.builtin.nim_family import (
    nim_boltz2_predict,
    nim_esm2_embed,
    nim_evo2_generate,
    nim_evo2_score,
    nim_test,
)
from bionodulo.nodes.builtin.nim_family.adapter import NimClient, NimError
from bionodulo.nodes.registry import NodeRegistry


NODE_IDS = ["nim_evo2_generate", "nim_evo2_score", "nim_esm2_embed", "nim_boltz2_predict", "nim_test"]


@pytest.fixture(scope="module")
def registry() -> NodeRegistry:
    result = NodeRegistry.create_isolated()
    result.load_builtin_nodes()
    return result


@pytest.fixture(autouse=True)
def clean_nim_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("NVIDIA_API_KEY", "BIONODULO_NIM_API_KEY", "BIONODULO_NIM_BASE_URL", "BIONODULO_NIM_STATUS_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def no_rate_limit_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    class NoWaitLimiter:
        def __init__(self, *, rate_per_second: float, burst: int = 1, **_kwargs: Any) -> None:
            self.rate_per_second = float(rate_per_second)
            self.burst = burst

        async def acquire(self) -> None:
            return None

    monkeypatch.setattr(nim_adapter, "TokenBucketRateLimiter", NoWaitLimiter)


def context(tmp_path: Path, secret: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(node_dir=tmp_path, resolve_secret=lambda key: secret if key == "nim_api_key" else None)


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, status_code: int, body: Any = "", headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        if isinstance(body, (bytes, bytearray)):
            self.content = bytes(body)
            self.text = body.decode("utf-8", errors="replace")
        else:
            self.text = body if isinstance(body, str) else json.dumps(body)
            self.content = self.text.encode("utf-8")

    def json(self) -> Any:
        return json.loads(self.text)


class FakeAsyncClient:
    calls: list[dict[str, Any]] = []
    responses: list[httpx.Response | FakeResponse] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def request(self, method: str, url: str, headers: dict[str, str] | None = None, json: Any = None) -> Any:
        FakeAsyncClient.calls.append({"method": method, "url": url, "headers": dict(headers or {}), "json": json})
        item = FakeAsyncClient.responses.pop(0)
        if callable(item):
            item = item(method, url, dict(headers or {}), json)
        return item

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None


@pytest.fixture
def fake_http(monkeypatch: pytest.MonkeyPatch) -> type[FakeAsyncClient]:
    FakeAsyncClient.calls = []
    FakeAsyncClient.responses = []
    monkeypatch.setattr(nim_adapter.httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


def no_sleep(seconds: float) -> Any:
    async def _sleep(_seconds: float) -> None:
        return None

    return _sleep


def test_nim_family_is_registered_with_contract_metadata(registry: NodeRegistry) -> None:
    for node_id in NODE_IDS:
        node_class = registry.get(node_id)
        assert node_class is not None, f"{node_id} is not registered"
        assert node_class.CATEGORY == "ai"
        assert node_class.REQUIRES_EXTERNAL_TOOLS is False
        assert len(node_class.RETURN_NAMES) == len(node_class.RETURN_TYPES)
        optional = node_class.INPUT_TYPES().get("optional", {})
        assert "fixture_mode" in optional
        assert optional["fixture_mode"][0] == "BOOLEAN"
    info = registry.object_info()
    assert info["nim_evo2_generate"]["output_name"] == ["generation_json", "generated_fasta"]
    assert nim_evo2_generate.NimEvo2GenerateNode.CITATION_DOIS == ["10.1038/s41586-026-10176-5"]
    assert nim_esm2_embed.NimESM2EmbedNode.CITATION_DOIS == ["10.1126/science.ade2574"]
    assert nim_boltz2_predict.NimBoltz2PredictNode.CITATION_DOIS == ["10.1101/2025.06.14.659707"]


def test_validate_rejects_empty_and_invalid_sequences() -> None:
    for node_class in (
        nim_evo2_generate.NimEvo2GenerateNode,
        nim_evo2_score.NimEvo2ScoreNode,
        nim_esm2_embed.NimESM2EmbedNode,
    ):
        verdict = node_class.VALIDATE_INPUTS({"sequence" if node_class.NODE_ID != "nim_esm2_embed" else "sequences": "   "})
        assert isinstance(verdict, str) and verdict
    assert (
        nim_evo2_generate.NimEvo2GenerateNode.VALIDATE_INPUTS({"sequence": "ACGU"})
        == "Evo 2 accepts DNA characters A, C, G, T only (alphabet=dna); found: U"
    )
    assert nim_esm2_embed.NimESM2EmbedNode.VALIDATE_INPUTS({"sequences": "MVLZ"}) == (
        "ESM 2 accepts amino acids ARNDCQEGHILKMFPSTWYVXBOU only; found: Z"
    )
    assert nim_boltz2_predict.NimBoltz2PredictNode.VALIDATE_INPUTS({"polymers": ""}).startswith("polymers must be")
    assert nim_boltz2_predict.NimBoltz2PredictNode.VALIDATE_INPUTS(
        {"polymers": '{"A": {"type": "protein", "sequence": "MVL"}}', "ligands": '{"x": {"ccd": "ATP", "smiles": "CCO"}}'}
    ).startswith("ligand 'x'")


def test_rna_input_is_transcribed_to_dna_in_request_body(tmp_path: Path, fake_http: type[FakeAsyncClient]) -> None:
    fake_http.responses = [
        FakeResponse(200, {"sequence": "ACGTACGTTTTT", "sampled_probs": [0.9, 0.8], "elapsed_ms": 5}),
    ]
    result = await_result(
        nim_evo2_generate.NimEvo2GenerateNode().run(
            sequence="ACGU", num_tokens=8, alphabet="rna", api_key="nvapi-test", context=context(tmp_path)
        )
    )
    payload = read_json(result["generation_json"])
    assert payload["prompt"] == "ACGT"
    assert fake_http.calls[0]["json"] == {
        "sequence": "ACGT",
        "num_tokens": 8,
        "temperature": 0.7,
        "top_k": 3,
        "enable_sampled_probs": True,
    }
    assert fake_http.calls[0]["url"] == "https://health.api.nvidia.com/v1/biology/arc/evo2-40b/generate"
    assert fake_http.calls[0]["headers"]["Authorization"] == "Bearer nvapi-test"


def await_result(coroutine: Any) -> dict[str, Any]:
    import asyncio

    return asyncio.run(coroutine)["outputs"]


def test_base_url_override_targets_self_hosted_nim(tmp_path: Path, fake_http: type[FakeAsyncClient]) -> None:
    fake_http.responses = [FakeResponse(200, {"sequence": "ACGTA", "sampled_probs": [0.5], "elapsed_ms": 1})]
    await_result(
        nim_test.NimTestNode().run(
            api_key="nvapi-test",
            base_url="http://localhost:8000/v1/biology/",
            context=context(tmp_path),
        )
    )
    assert fake_http.calls[0]["url"] == "http://localhost:8000/v1/biology/arc/evo2-40b/generate"


@pytest.mark.parametrize(
    "node_id",
    NODE_IDS,
)
def test_fixture_mode_runs_without_network_or_key(tmp_path: Path, node_id: str, fake_http: type[FakeAsyncClient]) -> None:
    assert fake_http.calls == []
    if node_id == "nim_evo2_generate":
        result = await_result(
            nim_evo2_generate.NimEvo2GenerateNode().run(sequence="ACGTACGT", num_tokens=20, fixture_mode=True, context=context(tmp_path))
        )
        payload = read_json(result["generation_json"])
        fasta = Path(result["generated_fasta"]).read_text(encoding="utf-8")
        assert payload["status"] == "NON_SCIENTIFIC_FIXTURE_ONLY"
        assert len(payload["generated_sequence"]) == 20
        assert payload["full_sequence"].startswith("ACGTACGT")
        assert set(payload["generated_sequence"]) <= {"A", "C", "G", "T"}
        assert fasta.startswith(">evo2_generated num_tokens=20\n")
    elif node_id == "nim_evo2_score":
        result = await_result(nim_evo2_score.NimEvo2ScoreNode().run(sequence="ACGTTT", fixture_mode=True, context=context(tmp_path)))
        payload = read_json(result["scores_json"])
        assert payload["mean_log_prob"] < 0
        assert Path(result["embedding_npz"]).exists()
    elif node_id == "nim_esm2_embed":
        result = await_result(
            nim_esm2_embed.NimESM2EmbedNode().run(sequences=">a\nMVLSPADK\n>b\nGIVEQC", fixture_mode=True, context=context(tmp_path))
        )
        payload = read_json(result["embeddings_json"])
        assert [item["id"] for item in payload["embeddings"]] == ["a", "b"]
        assert all(len(item["mean_pooled_embedding"]) == 32 for item in payload["embeddings"])
        tsv = Path(result["embeddings_tsv"]).read_text(encoding="utf-8").splitlines()
        assert tsv[0] == "id\tlength\tdim\tmean_pooled_embedding" and len(tsv) == 3
        assert Path(result["raw_npz"]).exists()
    elif node_id == "nim_boltz2_predict":
        result = await_result(
            nim_boltz2_predict.NimBoltz2PredictNode().run(
                polymers='{"A": {"type": "protein", "sequence": "MVL", "count": 1}}',
                ligands='{"ATP": {"ccd": "ATP"}}',
                fixture_mode=True,
                context=context(tmp_path),
            )
        )
        payload = read_json(result["prediction_json"])
        assert payload["mode"] == "fixture" and payload["confidence_scores"]
        assert Path(result["structure_file"]).exists()
    else:
        result = await_result(nim_test.NimTestNode().run(fixture_mode=True, context=context(tmp_path)))
        assert read_json(result["health_json"])["ok"] is True
    assert fake_http.calls == []


def test_fixture_outputs_are_deterministic(tmp_path: Path) -> None:
    first = await_result(
        nim_evo2_generate.NimEvo2GenerateNode().run(sequence="ACGT", num_tokens=16, fixture_mode=True, context=context(tmp_path))
    )
    second = await_result(
        nim_evo2_generate.NimEvo2GenerateNode().run(sequence="ACGT", num_tokens=16, fixture_mode=True, context=context(tmp_path))
    )
    assert read_json(first["generation_json"]) == read_json(second["generation_json"])


def test_missing_api_key_fails_closed_without_network(tmp_path: Path, fake_http: type[FakeAsyncClient]) -> None:
    with pytest.raises(NimError, match="API key is required"):
        await_result(nim_test.NimTestNode().run(context=context(tmp_path)))
    assert fake_http.calls == []


def test_api_key_resolution_prefers_node_param_then_secret_then_env(tmp_path: Path, fake_http: type[FakeAsyncClient], monkeypatch: pytest.MonkeyPatch) -> None:
    fake_http.responses = [FakeResponse(200, {"sequence": "ACGTA", "sampled_probs": [0.5], "elapsed_ms": 1})]
    await_result(nim_test.NimTestNode().run(api_key="nvapi-param", context=context(tmp_path)))
    assert fake_http.calls[-1]["headers"]["Authorization"] == "Bearer nvapi-param"

    fake_http.responses = [FakeResponse(200, {"sequence": "ACGTA", "sampled_probs": [0.5], "elapsed_ms": 1})]
    await_result(nim_test.NimTestNode().run(context=context(tmp_path, secret="nvapi-secret")))
    assert fake_http.calls[-1]["headers"]["Authorization"] == "Bearer nvapi-secret"

    fake_http.responses = [FakeResponse(200, {"sequence": "ACGTA", "sampled_probs": [0.5], "elapsed_ms": 1})]
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-env")
    await_result(nim_test.NimTestNode().run(context=context(tmp_path)))
    assert fake_http.calls[-1]["headers"]["Authorization"] == "Bearer nvapi-env"


def test_429_retry_once_then_succeeds_honoring_retry_after(fake_http: type[FakeAsyncClient]) -> None:
    fake_http.responses = [
        FakeResponse(429, {"error": "slow down"}, {"Retry-After": "2"}),
        FakeResponse(200, {"sequence": "ACGTA", "sampled_probs": [0.5], "elapsed_ms": 1}),
    ]
    sleeps: list[float] = []

    async def recording_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    client = NimClient(
        base_url="https://health.api.nvidia.com/v1/biology",
        api_key="nvapi-test",
        sleeper=recording_sleep,
        retry_delay=5.0,
    )
    body = client_loop(client.post_json_ok("arc/evo2-40b/generate", {"sequence": "ACGT", "num_tokens": 1}))
    assert body["sequence"] == "ACGTA"
    assert len(fake_http.calls) == 2
    assert sleeps == [2.0]
    assert client.rate_limiter is not None and client.rate_limiter.rate_per_second == pytest.approx(0.5)


def client_loop(coroutine: Any) -> Any:
    import asyncio

    return asyncio.run(coroutine)


def test_retry_exhaustion_raises_and_5xx_retries(fake_http: type[FakeAsyncClient]) -> None:
    fake_http.responses = [FakeResponse(503, {"error": "down"})] * 3
    client = NimClient(
        base_url="https://health.api.nvidia.com/v1/biology",
        api_key="nvapi-test",
        sleeper=no_sleep(0),
    )
    with pytest.raises(RuntimeError, match="HTTP 503"):
        client_loop(client.post_json_ok("meta/esm2-650m", {"sequences": ["MVL"]}))
    assert len(fake_http.calls) == 3


def test_error_messages_redact_the_api_key(tmp_path: Path, fake_http: type[FakeAsyncClient]) -> None:
    fake_http.responses = [FakeResponse(401, '{"error": "invalid key nvapi-SECRETKEY for tenant"}')]
    with pytest.raises(RuntimeError) as excinfo:
        await_result(nim_test.NimTestNode().run(api_key="nvapi-SECRETKEY", context=context(tmp_path)))
    message = str(excinfo.value)
    assert "nvapi-SECRETKEY" not in message
    assert "***" in message


def test_output_json_redacts_secret_shaped_keys(tmp_path: Path, fake_http: type[FakeAsyncClient]) -> None:
    fake_http.responses = [FakeResponse(200, {"sequence": "ACGTA", "sampled_probs": [0.5], "elapsed_ms": 1, "api_key": "nvapi-echo"})]
    result = await_result(nim_test.NimTestNode().run(api_key="nvapi-test", context=context(tmp_path)))
    payload = read_json(result["health_json"])
    rendered = json.dumps(payload)
    assert "nvapi-echo" not in rendered
    assert payload["response_keys"] == ["api_key", "elapsed_ms", "sampled_probs", "sequence"]


def test_evo2_score_network_path_decodes_base64_npz(tmp_path: Path, fake_http: type[FakeAsyncClient]) -> None:
    import numpy as np

    activations = np.arange(16, dtype="float32").reshape(4, 4)
    buffer = io.BytesIO()
    np.savez(buffer, output_layer=activations)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    fake_http.responses = [
        FakeResponse(200, {"sequence": "ACGTT", "sampled_probs": [0.5, 0.25], "elapsed_ms": 3}),
        FakeResponse(200, {"data": encoded, "elapsed_ms": 4}),
    ]
    result = await_result(nim_evo2_score.NimEvo2ScoreNode().run(sequence="ACGT", api_key="nvapi-test", context=context(tmp_path)))
    payload = read_json(result["scores_json"])
    assert payload["mean_log_prob"] == pytest.approx((np.log(0.5) + np.log(0.25)) / 2, abs=1e-5)
    assert payload["embedding_layers"] == ["output_layer"]
    saved = np.load(result["embedding_npz"])
    assert saved["output_layer"].shape == (4, 4)
    generate_call, forward_call = fake_http.calls
    assert generate_call["json"]["num_tokens"] == 10
    assert forward_call["json"] == {"sequence": "ACGT", "output_layers": ["output_layer"]}
    assert forward_call["url"].endswith("/arc/evo2-40b/forward")


def test_esm2_embed_handles_json_and_binary_npz_responses(tmp_path: Path, fake_http: type[FakeAsyncClient]) -> None:
    import numpy as np

    fake_http.responses = [
        FakeResponse(200, {"embeddings": [[[1.0, 3.0], [2.0, 4.0]]]}, {"content-type": "application/json"}),
    ]
    result = await_result(
        nim_esm2_embed.NimESM2EmbedNode().run(sequences=">a\nMV", api_key="nvapi-test", format="json", context=context(tmp_path))
    )
    payload = read_json(result["embeddings_json"])
    assert payload["embeddings"][0]["mean_pooled_embedding"] == pytest.approx([1.5, 3.5])
    assert fake_http.calls[0]["json"] == {"sequences": ["MV"], "format": "json"}

    buffer = io.BytesIO()
    np.savez(buffer, embedding_0=np.ones((2, 3)))
    fake_http.responses = [
        FakeResponse(200, buffer.getvalue(), {"content-type": "application/octet-stream"}),
    ]
    result = await_result(
        nim_esm2_embed.NimESM2EmbedNode().run(sequences=">a\nMV", api_key="nvapi-test", format="npz", context=context(tmp_path))
    )
    payload = read_json(result["embeddings_json"])
    assert payload["embeddings"][0]["mean_pooled_embedding"] == pytest.approx([1.0, 1.0, 1.0])
    saved = np.load(result["raw_npz"])
    assert saved["a"].shape == (2, 3)


def test_esm2_chunks_more_than_32_sequences_per_request(tmp_path: Path, fake_http: type[FakeAsyncClient]) -> None:
    import numpy as np

    sequences = "\n".join(f">s{index}\nMVL" for index in range(40))
    for _ in range(2):
        buffer = io.BytesIO()
        np.savez(buffer, **{f"embedding_{index}": np.ones((2, 3)) for index in range(32 if len(fake_http.responses) == 0 else 8)})
        fake_http.responses.append(FakeResponse(200, buffer.getvalue(), {"content-type": "application/octet-stream"}))
    result = await_result(
        nim_esm2_embed.NimESM2EmbedNode().run(sequences=sequences, api_key="nvapi-test", context=context(tmp_path))
    )
    payload = read_json(result["embeddings_json"])
    assert payload["sequence_count"] == 40
    assert len(payload["embeddings"]) == 40
    assert len(fake_http.calls) == 2
    assert len(fake_http.calls[0]["json"]["sequences"]) == 32
    assert len(fake_http.calls[1]["json"]["sequences"]) == 8


def test_boltz2_immediate_200_returns_structure(tmp_path: Path, fake_http: type[FakeAsyncClient]) -> None:
    fake_http.responses = [
        FakeResponse(
            200,
            {"structures": [{"structure": "data_boltz", "format": "mmcif"}], "confidence_scores": [0.88], "metrics": {}},
        ),
    ]
    result = await_result(
        nim_boltz2_predict.NimBoltz2PredictNode().run(
            polymers='{"A": {"type": "protein", "sequence": "MVL"}}',
            api_key="nvapi-test",
            context=context(tmp_path),
        )
    )
    payload = read_json(result["prediction_json"])
    assert payload["mode"] == "synchronous"
    assert payload["confidence_scores"] == [0.88]
    assert Path(result["structure_file"]).read_text(encoding="utf-8") == "data_boltz"
    body = fake_http.calls[0]["json"]
    assert body["polymers"] == [{"id": "A", "molecule_type": "protein", "sequence": "MVL", "count": 1}]
    assert body["output_format"] == "mmcif"
    assert "ligands" not in body


def test_boltz2_202_polls_status_until_complete(tmp_path: Path, fake_http: type[FakeAsyncClient], monkeypatch: pytest.MonkeyPatch) -> None:
    final = {
        "structures": [{"structure": "data_async", "format": "mmcif"}],
        "confidence_scores": [0.71],
    }
    fake_http.responses = [
        FakeResponse(202, {"request_id": "req-42"}),
        FakeResponse(200, {"status": "pending"}),
        FakeResponse(200, {"status": "pending"}),
        FakeResponse(200, {"status": "complete", "response": final}),
    ]
    polls_slept: list[float] = []

    async def recording_sleep(seconds: float) -> None:
        polls_slept.append(seconds)

    def fast_client(**kwargs: Any) -> NimClient:
        return NimClient(sleeper=recording_sleep, **kwargs)

    monkeypatch.setattr(nim_boltz2_predict, "NimClient", fast_client)
    result = await_result(
        nim_boltz2_predict.NimBoltz2PredictNode().run(
            polymers='{"A": {"type": "rna", "sequence": "GAGA"}}',
            ligands='{"inhib": {"smiles": "CCO(=O)N"}}',
            api_key="nvapi-test",
            poll_seconds=10,
            context=context(tmp_path),
        )
    )
    payload = read_json(result["prediction_json"])
    assert payload["mode"] == "async-poll"
    assert Path(result["structure_file"]).read_text(encoding="utf-8") == "data_async"
    submit, first_poll, second_poll, last_poll = fake_http.calls
    assert submit["url"].endswith("/mit/boltz2/predict")
    assert submit["json"]["polymers"][0]["molecule_type"] == "rna"
    assert submit["json"]["ligands"] == [{"id": "inhib", "ccd": "", "smiles": "CCO(=O)N", "count": 1}]
    for poll in (first_poll, second_poll, last_poll):
        assert poll["method"] == "GET"
        assert poll["url"] == "https://health.api.nvidia.com/v1/status/req-42"
        assert poll["headers"]["NVCF-POLL-SECONDS"] == "10"
    assert polls_slept == [10.0, 10.0]


def test_boltz2_poll_timeout_fails_closed(tmp_path: Path, fake_http: type[FakeAsyncClient], monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = iter(float(value) for value in range(0, 1000000, 500))

    def fast_clock() -> float:
        return next(ticks)

    def fast_client(**kwargs: Any) -> NimClient:
        return NimClient(clock=fast_clock, sleeper=no_sleep(0), **kwargs)

    monkeypatch.setattr(nim_boltz2_predict, "NimClient", fast_client)
    fake_http.responses = [
        FakeResponse(202, {"request_id": "req-1"}),
        lambda *_args: FakeResponse(200, {"status": "pending"}),
    ]
    with pytest.raises(RuntimeError, match="did not finish within 10s"):
        await_result(
            nim_boltz2_predict.NimBoltz2PredictNode().run(
                polymers='{"A": {"type": "protein", "sequence": "MVL"}}',
                api_key="nvapi-test",
                poll_timeout=10,
                poll_seconds=1,
                context=context(tmp_path),
            )
        )


def test_nim_client_rate_limiter_defaults_and_caps(tmp_path: Path) -> None:
    default = NimClient(base_url="https://x.test", api_key="k")
    assert default.rate_limiter is not None
    assert default.rate_limiter.rate_per_second == pytest.approx(30 / 60.0)
    off = NimClient(base_url="https://x.test", api_key="k", requests_per_minute=0)
    assert off.rate_limiter is None
    with pytest.raises(ValueError, match="requests_per_minute must be between 0 and 40"):
        client_loop(
            nim_test.NimTestNode().run(api_key="nvapi-test", requests_per_minute=100, context=context(tmp_path))
        )
