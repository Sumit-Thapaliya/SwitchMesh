from fastapi.testclient import TestClient

from switchmesh.hub.server import app, approvals, correlator, war_rooms
from switchmesh.hub.switch_client import SwitchClient
from switchmesh.router import SwitchRouter


def test_webhooks_correlate_and_redact():
    client = TestClient(app)
    first = client.post("/webhooks/telegram", json={"text": "checkout FREESHIP failed for user@example.com"})
    second = client.post("/webhooks/sentry", json={"text": "FREESHIP checkout failed for user@example.com"})

    assert first.status_code == second.status_code == 200
    assert first.json()["incident_id"] == second.json()["incident_id"]
    assert "[REDACTED_EMAIL]" in first.json()["payload"]


def test_commands_open_and_approve_incident():
    client = TestClient(app)
    assert client.post("/api/command", json={"command": "war-room INC-101"}).json()["status"] == "opened"
    assert client.post("/api/command", json={"command": "approve INC-101"}).json()["status"] == "approved"
    assert "INC-101" in war_rooms | approvals


def test_client_builds_protocol_requests(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True}

    def fake_post(url, **kwargs):
        calls.append((url, kwargs["json"]))
        return Response()

    monkeypatch.setattr("switchmesh.hub.switch_client.httpx.post", fake_post)
    client = SwitchClient("https://switch.example")
    assert client.register_agent({"name": "hub"}) == {"ok": True}
    assert client.send_message("agent-1", "hello") == {"ok": True}
    assert calls[0][0].endswith("/agents")
    assert calls[1][0].endswith("/agents/agent-1/message")
    assert client.websocket_url("agent-1").endswith("/agents/agent-1/connection/ws?scope=all")


def test_router_discovers_missing_room_ids(monkeypatch):
    router = SwitchRouter(SwitchClient("https://switch.example"))
    monkeypatch.setattr(
        router.client,
        "list_rooms",
        lambda: [{"name": "omnibox-intake", "id": "room-intake"}, {"name": "command-hub", "id": "room-command"}],
    )

    router.connect()

    assert router.intake_room_id == "room-intake"
    assert router.command_room_id == "room-command"
