"""Real-time Engine — WebSocket fan-out for live telemetry and anomaly alerts.

Channels:
  • center:<id>  — coordinator/invigilator alert feed for a center
  • admin        — NTA command-center live status
"""
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.channels: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, channel: str, ws: WebSocket):
        await ws.accept()
        self.channels[channel].append(ws)

    def disconnect(self, channel: str, ws: WebSocket):
        if ws in self.channels[channel]:
            self.channels[channel].remove(ws)

    async def broadcast(self, channel: str, message: dict):
        dead = []
        for ws in list(self.channels.get(channel, [])):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(channel, ws)


manager = ConnectionManager()
