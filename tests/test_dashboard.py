import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from replayproof.api import app
from replayproof.synthetic import generate

client = TestClient(app)


def test_dashboard_assets_are_served_without_a_database() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Run replay demo" in response.text
    for path in ("/assets/dashboard.css", "/assets/dashboard.js", "/assets/mark.svg"):
        assert client.get(path).status_code == 200
    assert client.get("/assets/../db.py").status_code == 404


@pytest.mark.skipif(os.getenv("REPLAYPROOF_TEST_DATABASE") != "1", reason="Requires PostgreSQL")
def test_dashboard_reads_preserve_buffering_and_paginate() -> None:
    stream = client.post("/v1/streams", json={"symbol": "DASH_TEST"}).json()
    sid = stream["id"]
    events = generate(2027, 3)
    for event in (events[0], events[2]):
        assert (
            client.post(f"/v1/streams/{sid}/events", json=event.model_dump(mode="json")).status_code
            == 200
        )
    status = client.get(f"/v1/streams/{sid}/status").json()
    assert status["source_event_count"] == 2
    assert status["last_applied_seq"] == 1
    assert status["first_event_time"] and status["last_event_time"]
    first = client.get(f"/v1/streams/{sid}/events?limit=1").json()
    assert first["events"][0]["sequence"] == 3
    assert first["events"][0]["state"] == "buffered"
    assert len(first["events"][0]["payload_sha256"]) == 64
    second = client.get(f"/v1/streams/{sid}/events?limit=1&offset=1").json()
    assert second["events"][0]["sequence"] == 1
    assert second["events"][0]["state"] == "applied"
    assert second["cursor"] == 1
    assert client.get(f"/v1/streams/{sid}/status").json() == status
    assert any(s["id"] == sid for s in client.get("/v1/streams?limit=100").json()["streams"])
    assert client.get("/v1/streams?limit=101").status_code == 422
    assert client.get(f"/v1/streams/{sid}/events?limit=201").status_code == 422
    assert client.get(f"/v1/streams/{sid}/events?offset=-1").status_code == 422
    assert client.get(f"/v1/streams/{uuid4()}/events").status_code == 404


@pytest.mark.skipif(os.getenv("REPLAYPROOF_TEST_DATABASE") != "1", reason="Requires PostgreSQL")
def test_dashboard_reconciliation_history_is_persisted_and_bounded() -> None:
    sid = client.post("/v1/streams", json={"symbol": "DASH_REPORT"}).json()["id"]
    for _ in range(2):
        report = client.post(f"/v1/streams/{sid}/reconcile").json()
        assert report["created_at"]
        assert report["status"] == "matched"
    history = client.get(f"/v1/streams/{sid}/reconciliations?limit=1").json()["runs"]
    assert len(history) == 1
    assert history[0]["id"] == report["id"]
    assert client.get(f"/v1/reconciliations/{report['id']}").json() == report
    assert client.get(f"/v1/streams/{sid}/reconciliations?limit=101").status_code == 422
    assert client.get(f"/v1/streams/{uuid4()}/reconciliations").status_code == 404
