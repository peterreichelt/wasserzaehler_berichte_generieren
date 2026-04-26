from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class AttachmentInfo:
    """Repräsentiert ein einzelnes herunterladbares Attachment."""

    id: str
    title: str | None
    url: str | None
    thumbnail_url: str | None = None
    running_number: str | None = None
    local_relative_path: Path | None = None


@dataclass
class MeterReading:
    """Beschreibt eine normierte Ablesung aus Excel oder PlanRadar."""

    source: str
    property_name: str
    meter_location: str
    reading_date: date
    reading_value: float
    meter_number: str | None = None
    unit: str | None = None
    notes: str | None = None
    project_id: str | None = None
    planradar_id: str | None = None
    ticket_id: str | None = None
    ticket_uuid: str | None = None
    ticket_type_id: str | None = None
    raw_meter_location: str | None = None
    raw_payload: dict[str, object] | None = None
    attachments: list[AttachmentInfo] = field(default_factory=list)
    extra: dict[str, object] = field(default_factory=dict)


@dataclass
class DiscoverySummary:
    """Fasst die Ergebnisse der API-Discovery für den Lauf zusammen."""

    project_id: str
    project_name: str
    ticket_type_id: str
    ticket_type_name: str
    field_ids: dict[str, str]
    project_list_ids: list[str]
    notes: list[str]
