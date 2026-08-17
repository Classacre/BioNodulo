from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bionodulo.api.routes import router


class FakeQueue:
    def __init__(self, runs: dict[str, dict[str, Any]], events: dict[str, list[dict[str, Any]]]) -> None:
        self._runs = runs
        self._events = events

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self._runs.get(run_id)

    def get_run_events(self, run_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        return self._events.get(run_id, [])[-limit:]


def _client(queue: Any) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.run_queue = queue
    return TestClient(app)


def test_run_events_endpoint_returns_ordered_events() -> None:
    queue = FakeQueue(
        runs={"run-1": {"run_id": "run-1", "status": "completed"}},
        events={
            "run-1": [
                {"run_id": "run-1", "seq": 1, "ts": 1.0, "type": "queue_submit", "payload": {}},
                {"run_id": "run-1", "seq": 2, "ts": 2.0, "type": "queue_finish", "payload": {}},
            ]
        },
    )

    response = _client(queue).get("/api/runs/run-1/events")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "run-1"
    assert body["event_count"] == 2
    assert [event["seq"] for event in body["events"]] == [1, 2]


def test_run_events_endpoint_limits_results() -> None:
    events = [
        {"run_id": "r", "seq": seq, "ts": float(seq), "type": "tick", "payload": {}}
        for seq in range(1, 6)
    ]
    queue = FakeQueue(runs={"r": {"run_id": "r"}}, events={"r": events})

    body = _client(queue).get("/api/runs/r/events?limit=2").json()

    assert [event["seq"] for event in body["events"]] == [4, 5]
    assert body["event_count"] == 2


def test_run_events_endpoint_404_for_unknown_run() -> None:
    response = _client(FakeQueue(runs={}, events={})).get("/api/runs/nope/events")

    assert response.status_code == 404
