"""Tests for structured JSON logging on stdout."""

import json
from fastapi.testclient import TestClient


def test_request_log_line(client: TestClient, capsys):
    """Verify request prints one JSON log line with all required fields."""
    headers = {"X-API-Key": "test-api-key", "X-Forwarded-For": "198.51.100.42"}
    payload = {"prompt": "Testing log line", "strategy": "fixed", "tier": "lite"}

    resp = client.post("/api/v1/complete", headers=headers, json=payload)
    assert resp.status_code == 200

    captured = capsys.readouterr()
    log_lines = [line for line in captured.out.splitlines() if line.startswith('{"event": "complete"')]
    assert len(log_lines) >= 1

    entry = json.loads(log_lines[-1])
    required_fields = [
        "event",
        "request_id",
        "strategy",
        "tier",
        "model",
        "status",
        "input_tokens",
        "output_tokens",
        "thinking_tokens",
        "total_cost_usd",
        "latency_ms",
        "attempts",
        "client_ip",
    ]
    for field in required_fields:
        assert field in entry, f"Missing log line field: {field}"

    assert entry["event"] == "complete"
    assert entry["status"] == 200
    assert entry["tier"] == "lite"
    assert entry["strategy"] == "fixed"
    assert entry["client_ip"] == "198.51.100.42"
