"""Small client for the Switch Agent Protocol."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

import httpx


class SwitchClient:
    def __init__(self, base_url: str, *, token: str | None = None, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}{path}",
            json=payload,
            headers=self._headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def _get(self, path: str) -> Any:
        response = httpx.get(
            f"{self.base_url}{path}",
            headers=self._headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def register_agent(self, agent: dict[str, Any]) -> dict[str, Any]:
        return self._post("/agents", agent)

    def list_rooms(self) -> list[dict[str, Any]]:
        """Return rooms visible to the connected Switch agent."""
        result = self._get("/rooms")
        if isinstance(result, dict):
            result = result.get("rooms", [])
        return list(result or [])

    def discover_rooms(self) -> dict[str, str]:
        """Discover the standard intake and command rooms by display name."""
        rooms = self.list_rooms()
        discovered = {
            room.get("name"): room.get("id") or room.get("room_id")
            for room in rooms
            if room.get("name") in {"omnibox-intake", "command-hub"}
        }
        missing = {name for name in ("omnibox-intake", "command-hub") if not discovered.get(name)}
        if missing:
            raise LookupError(f"Switch rooms not found: {', '.join(sorted(missing))}")
        return {"intake_room_id": discovered["omnibox-intake"], "command_room_id": discovered["command-hub"]}

    def create_room(self, name: str, description: str = "", **extra: Any) -> dict[str, Any]:
        return self._post("/rooms", {"name": name, "description": description, **extra})

    def link_rooms(self, source_room_id: str, target_room_id: str, label: str) -> dict[str, Any]:
        return self._post(
            "/rooms/links",
            {"source_room_id": source_room_id, "target_room_id": target_room_id, "label": label},
        )

    def send_message(self, agent_id: str, body: str, **extra: Any) -> dict[str, Any]:
        return self._post(f"/agents/{agent_id}/message", {"body": body, **extra})

    def websocket_url(self, agent_id: str, *, scope: str = "all") -> str:
        scheme = "wss" if self.base_url.startswith("https://") else "ws"
        host = self.base_url.split("://", 1)[-1]
        return f"{scheme}://{host}/agents/{agent_id}/connection/ws?scope={scope}"

    async def serve_connection(
        self,
        websocket: Any,
        *,
        agent_id: str,
        scope: str = "all",
        on_event: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
    ) -> None:
        """Serve a Starlette-style WebSocket and answer cursor pings promptly.

        The endpoint accepts ``{"type": "cursor", "cursor": ...}`` (and
        ``ping``) messages and immediately returns a matching ``pong``.
        """

        await websocket.accept()
        while True:
            try:
                message = await websocket.receive_json()
            except Exception:
                return
            if on_event is not None:
                result = on_event(message)
                if asyncio.iscoroutine(result):
                    await result
            if message.get("type") in {"cursor", "ping"}:
                await websocket.send_json(
                    {
                        "type": "pong",
                        "agent_id": agent_id,
                        "scope": scope,
                        "cursor": message.get("cursor"),
                        "timestamp": time.time(),
                    }
                )
