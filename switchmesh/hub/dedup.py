"""Keyword-based incident correlation across incoming signal sources."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]{2,}", re.IGNORECASE)
_STOPWORDS = {
    "about", "after", "again", "and", "are", "been", "from", "have", "into",
    "that", "the", "this", "with", "when", "where", "which", "while", "will",
    "would", "bug", "error", "issue", "report", "reported", "service",
}


def _keywords(report: Any) -> set[str]:
    if isinstance(report, str):
        text = report
    elif isinstance(report, dict):
        text = " ".join(
            str(report.get(key, ""))
            for key in ("title", "summary", "description", "body", "message", "text")
        )
    else:
        text = " ".join(
            str(getattr(report, key, ""))
            for key in ("title", "summary", "description", "body", "message", "text")
        )
    return {
        token.lower()
        for token in _TOKEN_RE.findall(text)
        if token.lower() not in _STOPWORDS
    }


@dataclass
class _Incident:
    incident_id: str
    keywords: set[str]
    reports: list[Any] = field(default_factory=list)


class IncidentCorrelator:
    """Cluster related reports using Jaccard keyword-overlap similarity."""

    def __init__(self, similarity_threshold: float = 0.3, first_incident: int = 101):
        if not 0 <= similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")
        self.similarity_threshold = similarity_threshold
        self._next_number = first_incident
        self._incidents: list[_Incident] = []

    @property
    def incidents(self) -> dict[str, list[Any]]:
        """Return a snapshot of incident IDs and their original reports."""
        return {incident.incident_id: list(incident.reports) for incident in self._incidents}

    def correlate(self, report: Any) -> str:
        """Return the matching incident ID, creating one when no match exists."""
        keywords = _keywords(report)
        best: _Incident | None = None
        best_score = 0.0

        for incident in self._incidents:
            union = keywords | incident.keywords
            score = len(keywords & incident.keywords) / len(union) if union else 1.0
            if score > best_score:
                best, best_score = incident, score

        if best is None or best_score < self.similarity_threshold:
            incident_id = f"INC-{self._next_number}"
            self._next_number += 1
            best = _Incident(incident_id, set(keywords))
            self._incidents.append(best)
        else:
            best.keywords.update(keywords)

        best.reports.append(report)
        return best.incident_id

    add_report = correlate
