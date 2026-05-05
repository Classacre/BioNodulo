from bionodulo.execution.events import make_event


def test_event_formatting():
    event = make_event("executing", {"run_id": "run-1", "node_id": "fastqc-1"})

    assert event == {"type": "executing", "data": {"run_id": "run-1", "node_id": "fastqc-1"}}
