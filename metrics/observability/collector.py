"""SSE / observability metrics collector."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConnectionRecord:
    session_id: str
    started_at: str
    ended_at: str | None = None
    duration_ms: int | None = None
    events_sent: int = 0
    bytes_sent: int = 0


class ObservabilityMetricsCollector:
    def __init__(self, storage_path: str = "metrics/observability/data"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._connections: dict[str, ConnectionRecord] = {}
        self._events: list[dict[str, Any]] = []

    def record_connection_start(self, session_id: str) -> None:
        self._connections[session_id] = ConnectionRecord(
            session_id=session_id,
            started_at=datetime.utcnow().isoformat(),
        )

    def record_event_publish(self, session_id: str, event_type: str, size_bytes: int) -> None:
        self._events.append(
            {
                "session_id": session_id,
                "event_type": event_type,
                "size_bytes": size_bytes,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def record_connection_end(self, session_id: str, events_sent: int = 0, bytes_sent: int = 0) -> None:
        record = self._connections.get(session_id)
        if record is None:
            return
        record.ended_at = datetime.utcnow().isoformat()
        record.duration_ms = int(
            (datetime.fromisoformat(record.ended_at) - datetime.fromisoformat(record.started_at)).total_seconds() * 1000
        )
        record.events_sent = events_sent
        record.bytes_sent = bytes_sent
        self._persist_record(record)

    def get_metrics(self) -> dict[str, Any]:
        total_connections = len(self._connections)
        total_events = len(self._events)
        return {
            "connections": [asdict(r) for r in self._connections.values()],
            "events": list(self._events[-100:]),
            "summary": {
                "total_connections": total_connections,
                "total_events_published": total_events,
                "avg_events_per_connection": total_events / total_connections if total_connections else 0,
            },
        }

    def _persist_record(self, record: ConnectionRecord) -> None:
        filepath = self.storage_path / f"{record.session_id}.jsonl"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
