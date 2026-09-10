"""Ingestion contract for validated survey/assessment instruments.

Distinct from events.py's tool telemetry: this is human self-report against a
named, versioned instrument, not something scraped from a dev-tool API. Only
one causal-graph variable currently needs this (software_delivery_skill, via
DORA's capability scales) -- agent_skill was removed because no validated
instrument exists for it; do not add a survey-backed measurement for a
construct without naming the specific validated instrument it comes from.
"""

from __future__ import annotations

from sqlalchemy import JSON, Column
from sqlmodel import Field

from causal_coding.events import Event


class SurveyResponse(Event, table=True):
    __tablename__ = "ingested_survey_responses"

    respondent_id: str
    team_id: str
    instrument: str
    instrument_version: str
    items: dict[str, float] = Field(sa_column=Column(JSON))
    composite_score: float | None = None
