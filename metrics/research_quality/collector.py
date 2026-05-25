"""Research quality metrics collector."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ReportQualityRecord:
    session_id: str
    query: str
    total_claims: int
    verified_claims: int
    hallucinated_claims: int
    citation_count: int
    plan_coverage: float
    avg_confidence: float
    recorded_at: str


class ResearchQualityCollector:
    def __init__(self, storage_path: str = "metrics/research_quality/data"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._reports: list[ReportQualityRecord] = []

    def record_report_quality(
        self,
        *,
        session_id: str,
        query: str,
        total_claims: int,
        verified_claims: int,
        hallucinated_claims: int,
        citation_count: int,
        plan_coverage: float,
        avg_confidence: float,
    ) -> None:
        record = ReportQualityRecord(
            session_id=session_id,
            query=query,
            total_claims=total_claims,
            verified_claims=verified_claims,
            hallucinated_claims=hallucinated_claims,
            citation_count=citation_count,
            plan_coverage=plan_coverage,
            avg_confidence=avg_confidence,
            recorded_at=datetime.utcnow().isoformat(),
        )
        self._reports.append(record)
        self._persist_record(record)

    def get_metrics(self) -> dict[str, Any]:
        if not self._reports:
            return {"summary": {}}
        return {
            "reports": [asdict(r) for r in self._reports[-100:]],
            "summary": {
                "total_reports": len(self._reports),
                "avg_claims": sum(r.total_claims for r in self._reports) / len(self._reports),
                "avg_verified_claims": sum(r.verified_claims for r in self._reports) / len(self._reports),
                "avg_hallucinated_claims": sum(r.hallucinated_claims for r in self._reports) / len(self._reports),
                "avg_citation_count": sum(r.citation_count for r in self._reports) / len(self._reports),
                "avg_plan_coverage": sum(r.plan_coverage for r in self._reports) / len(self._reports),
                "avg_confidence": sum(r.avg_confidence for r in self._reports) / len(self._reports),
            },
        }

    def _persist_record(self, record: ReportQualityRecord) -> None:
        filepath = self.storage_path / f"{record.session_id}.jsonl"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
