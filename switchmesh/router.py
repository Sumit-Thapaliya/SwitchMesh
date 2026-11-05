"""Environment-driven SwitchMesh room routing with automatic discovery."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .hub.switch_client import SwitchClient


@dataclass
class SwitchRouter:
    client: SwitchClient
    intake_room_id: str | None = None
    command_room_id: str | None = None

    @classmethod
    def from_env(cls) -> "SwitchRouter":
        return cls(
            client=SwitchClient(
                os.getenv("SWITCH_BRIDGE_URL", "http://127.0.0.1:8000"),
                token=os.getenv("SWITCH_REGISTRATION_TOKEN") or None,
            ),
            intake_room_id=os.getenv("SWITCH_INTAKE_ROOM_ID") or None,
            command_room_id=os.getenv("SWITCH_COMMAND_ROOM_ID") or None,
        )

    def connect(self) -> "SwitchRouter":
        """Connect to the bridge and discover any room IDs omitted in env."""
        if not self.intake_room_id or not self.command_room_id:
            discovered = self.client.discover_rooms()
            self.intake_room_id = self.intake_room_id or discovered["intake_room_id"]
            self.command_room_id = self.command_room_id or discovered["command_room_id"]
        return self
