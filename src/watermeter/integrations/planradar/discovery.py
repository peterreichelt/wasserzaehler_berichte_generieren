from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from ...config import AppConfig
from ...exceptions import PlanRadarApiError
from ...shared.normalization import normalize_key, normalize_meter_location, normalize_text
from ...importing.models import AttachmentInfo, DiscoverySummary, MeterReading
from .client import PlanRadarClient


logger = logging.getLogger(__name__)


SEMANTIC_CANDIDATES = {
    "reading_value": ["zahlerstand", "zaehlerstand", "meter reading", "reading"],
    "reading_date": ["datum", "ablesedatum", "date"],
    "meter_reference": ["zahlerplatz", "zaehlerplatz", "zahlernummer", "zaehlernummer", "meter"],
    "notes": ["anmerkung", "bemerkung", "notiz", "note"],
}


@dataclass
class ListEntryNode:
    """Repräsentiert einen Listeneintrag aus einer PlanRadar-Liste."""

    id: str
    name: str
    list_id: str
    parent_id: str | None


@dataclass
class PlanRadarDiscoveryResult:
    """Bündelt Discovery-Ergebnis und die transformierten PlanRadar-Ablesungen."""

    summary: DiscoverySummary
    readings: list[MeterReading]


def _attributes(item: dict[str, Any]) -> dict[str, Any]:
    """Liefert bequem den Attribute-Block eines JSON:API-Objekts."""
    return item.get("attributes") or {}


def load_projects(client: PlanRadarClient, customer_id: str) -> list[dict[str, Any]]:
    """Lädt alle für den Kunden sichtbaren PlanRadar-Projekte."""
    projects_payload = client.get_json(f"/api/v2/{customer_id}/projects/my_projects")
    projects = projects_payload.get("data") or []
    if not isinstance(projects, list):
        raise PlanRadarApiError("PlanRadar hat eine ungültige Projektliste zurückgegeben.")
    return projects


def load_project_detail(client: PlanRadarClient, customer_id: str, project_id: str) -> dict[str, Any]:
    """Lädt die Projekt-Detaildaten inklusive optionalem Titelbild-Link."""
    payload = client.get_json(f"/api/v1/{customer_id}/projects/{project_id}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise PlanRadarApiError(f"PlanRadar hat ungültige Projektdetails für das Projekt '{project_id}' zurückgegeben.")
    return data


def extract_project_image_url(project_detail: dict[str, Any]) -> str | None:
    """Liest den Titelbild-Link aus den Projekt-Detaildaten aus."""
    return normalize_text(_attributes(project_detail).get("project-image")) or None


def _select_project(projects: list[dict[str, Any]], config: AppConfig) -> dict[str, Any]:
    """Bestimmt das Zielprojekt anhand von ID oder Name aus der Config."""
    if config.target_project_id:
        for project in projects:
            if project.get("id") == config.target_project_id:
                return project
        raise PlanRadarApiError(f"Die konfigurierte Projekt-ID '{config.target_project_id}' wurde nicht gefunden.")

    desired = normalize_key(config.target_project_name)
    matches = [project for project in projects if normalize_key(_attributes(project).get("name")) == desired]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise PlanRadarApiError(f"Der konfigurierte Projektname '{config.target_project_name}' wurde nicht gefunden.")
    raise PlanRadarApiError(f"Der Projektname '{config.target_project_name}' passt auf mehrere Projekte.")


def _matches_meter_locations(reading: MeterReading, allowed_meter_locations: set[str] | None) -> bool:
    """Prüft, ob eine Ablesung zu einer Menge erlaubter Zählerplätze gehört."""
    if not allowed_meter_locations:
        return True
    return reading.meter_location in allowed_meter_locations


def _match_semantic_field(field_name: str) -> str | None:
    """Erkennt die fachliche Bedeutung eines Feldnamens über Namensmuster."""
    key = normalize_key(field_name)
    for semantic_name, candidates in SEMANTIC_CANDIDATES.items():
        if any(candidate in key for candidate in candidates):
            return semantic_name
    return None


def _choose_ticket_type(ticket_types: list[dict[str, Any]], config: AppConfig) -> dict[str, Any]:
    """Wählt den fachlich passendsten Ticket Type für Wasserzähler-Ablesungen aus."""
    override_name = config.planradar.mapping_overrides.ticket_type_name
    if override_name:
        desired = normalize_key(override_name)
        for item in ticket_types:
            if normalize_key(_attributes(item).get("name")) == desired:
                return item
        raise PlanRadarApiError(f"Der konfigurierte Ticket-Type-Override '{override_name}' wurde nicht gefunden.")

    best: tuple[int, dict[str, Any] | None] = (-1, None)
    for item in ticket_types:
        attrs = _attributes(item)
        score = 0
        for field in (attrs.get("typed-fields") or {}).values():
            semantic = _match_semantic_field((field or {}).get("name", ""))
            if semantic:
                score += 1
        if normalize_key(attrs.get("name")) == normalize_key("Wasserzählerablesung neu"):
            score += 5
        if score > best[0]:
            best = (score, item)
    if best[1] is None or best[0] < 3:
        raise PlanRadarApiError("Es konnte kein passender Ticket-Typ für Wasserzähler-Ablesungen gefunden werden.")
    return best[1]


def _resolve_field_ids(ticket_type: dict[str, Any], config: AppConfig) -> dict[str, str]:
    """Ordnet die technischen Feld-IDs den fachlichen Zielattributen zu."""
    attrs = _attributes(ticket_type)
    field_ids: dict[str, str] = {}
    typed_fields = attrs.get("typed-fields") or {}
    overrides = config.planradar.mapping_overrides.typed_field_names
    for semantic_name, desired_field_name in overrides.items():
        for field_id, field_meta in typed_fields.items():
            if normalize_key((field_meta or {}).get("name")) == normalize_key(desired_field_name):
                field_ids[semantic_name] = field_id

    for field_id, field_meta in typed_fields.items():
        semantic_name = _match_semantic_field((field_meta or {}).get("name", ""))
        if semantic_name and semantic_name not in field_ids:
            field_ids[semantic_name] = field_id

    for required in ["reading_value", "reading_date", "meter_reference"]:
        if required not in field_ids:
            raise PlanRadarApiError(f"Das erforderliche Feld '{required}' konnte im Ticket-Typ nicht aufgelöst werden.")
    return field_ids


def _index_list_entries(payload: dict[str, Any]) -> dict[str, ListEntryNode]:
    """Baut einen Index aller Listeneinträge aus der Projektliste auf."""
    entries: dict[str, ListEntryNode] = {}
    for item in payload.get("included") or []:
        if item.get("type") != "list-entries":
            continue
        attrs = _attributes(item)
        entries[item["id"]] = ListEntryNode(
            id=item["id"],
            name=normalize_text(attrs.get("name")),
            list_id=normalize_text(attrs.get("list-id")),
            parent_id=attrs.get("parent-id"),
        )
    return entries


def _resolve_meter_reference(
    raw_value: object,
    list_entries: dict[str, ListEntryNode],
    overrides: dict[str, dict[str, str]],
) -> tuple[str | None, str | None, str | None]:
    """Löst einen Listeneintrag in Zählerplatz und Zählernummer auf."""
    if raw_value is None:
        return None, None, None

    raw_id = normalize_text(raw_value)
    if raw_id in overrides:
        override = overrides[raw_id]
        return (
            override.get("meter_location"),
            override.get("meter_number"),
            raw_id,
        )

    node = list_entries.get(raw_id)
    if node:
        if node.parent_id and node.parent_id in list_entries:
            parent = list_entries[node.parent_id]
            return parent.name, node.name, raw_id
        return node.name, None, raw_id

    return normalize_text(raw_value), None, raw_id


def _build_attachment_index(payloads: dict[str, dict[str, Any]]) -> dict[str, list[AttachmentInfo]]:
    """Baut einen Attachment-Index je Ticket-UUID aus der API-Antwort auf."""
    index: dict[str, list[AttachmentInfo]] = {}
    for ticket_uuid, payload in payloads.items():
        include_map = {item["id"]: item for item in payload.get("included") or []}
        attachments: list[AttachmentInfo] = []
        for item in payload.get("data") or []:
            attrs = _attributes(item)
            related = include_map.get(attrs.get("attachable-id"), {})
            related_attrs = _attributes(related)
            attachments.append(
                AttachmentInfo(
                    id=normalize_text(attrs.get("id")),
                    title=normalize_text(attrs.get("title")) or None,
                    url=related_attrs.get("image-url"),
                    thumbnail_url=related_attrs.get("image-url-thumb"),
                    running_number=normalize_text(related_attrs.get("running-number")) or None,
                )
            )
        index[ticket_uuid] = attachments
    return index


def _parse_planradar_date(raw_value: object) -> date:
    """Wandelt ein PlanRadar-Datum in ein Python-Datum um."""
    value = normalize_text(raw_value)
    if not value:
        raise PlanRadarApiError("PlanRadar hat ein leeres Ablesedatum zurückgegeben.")
    return date.fromisoformat(value[:10])


def load_project_readings(
    client: PlanRadarClient,
    config: AppConfig,
    project: dict[str, Any],
    *,
    allowed_meter_locations: set[str] | None = None,
) -> PlanRadarDiscoveryResult:
    """Lädt und transformiert alle relevanten Tickets eines einzelnen Projekts."""
    project_id = project["id"]
    project_name = normalize_text(_attributes(project).get("name"))

    ticket_types_payload = client.get_json(
        f"/api/v2/{config.customer_id}/projects/{project_id}/ticket_types/ticket_type_project"
    )
    included_ticket_types = [
        item for item in (ticket_types_payload.get("included") or []) if item.get("type") == "ticket-types"
    ]
    ticket_type = _choose_ticket_type(included_ticket_types, config)
    ticket_type_id = ticket_type["id"]
    ticket_type_name = normalize_text(_attributes(ticket_type).get("name"))
    field_ids = _resolve_field_ids(ticket_type, config)

    lists_payload = client.get_json(f"/api/v1/{config.customer_id}/projects/{project_id}/lists")
    list_entries = _index_list_entries(lists_payload)
    project_list_ids = [item["id"] for item in (lists_payload.get("data") or [])]

    tickets_payload = client.get_json(f"/api/v2/{config.customer_id}/projects/{project_id}/tickets")
    tickets = [
        item
        for item in (tickets_payload.get("data") or [])
        if _attributes(item).get("ticket-type-id") == ticket_type_id
    ]
    if not tickets:
        raise PlanRadarApiError(
            f"Für das Projekt '{project_name}' und den Ticket-Typ '{ticket_type_name}' wurden keine Tickets gefunden."
        )

    attachment_payloads: dict[str, dict[str, Any]] = {}
    if config.planradar.include_attachments:
        for ticket in tickets:
            ticket_uuid = _attributes(ticket).get("uuid")
            attachment_payloads[ticket_uuid] = client.get_json(
                f"/api/v2/{config.customer_id}/projects/{project_id}/tickets/{ticket_uuid}/attachments"
            )
    attachment_index = _build_attachment_index(attachment_payloads)

    readings: list[MeterReading] = []
    notes: list[str] = []
    overrides = config.planradar.mapping_overrides.list_entry_overrides

    for ticket in tickets:
        attrs = _attributes(ticket)
        typed_values = attrs.get("typed-values") or {}
        meter_location_name, meter_number, raw_meter_id = _resolve_meter_reference(
            typed_values.get(field_ids["meter_reference"]),
            list_entries,
            overrides,
        )
        if not meter_location_name:
            meter_location_name = normalize_text(attrs.get("subject")) or "UNMAPPED"
            notes.append(f"Ticket {attrs.get('uuid')} hat für die Auflösung des Zählerplatzes auf den Betreff zurückgegriffen.")
        reading = MeterReading(
            source="planradar",
            property_name=project_name,
            meter_location=normalize_meter_location(meter_location_name),
            raw_meter_location=meter_location_name,
            meter_number=meter_number,
            reading_date=_parse_planradar_date(typed_values.get(field_ids["reading_date"])),
            reading_value=float(typed_values.get(field_ids["reading_value"])),
            notes=normalize_text(typed_values.get(field_ids.get("notes"))) or normalize_text(attrs.get("subject")) or None,
            project_id=project_id,
            planradar_id=normalize_text(attrs.get("sequential-id")) or None,
            ticket_id=normalize_text(ticket.get("id")) or None,
            ticket_uuid=normalize_text(attrs.get("uuid")),
            ticket_type_id=ticket_type_id,
            raw_payload=ticket,
            attachments=attachment_index.get(attrs.get("uuid"), []),
            extra={"meter_reference_raw_id": raw_meter_id},
        )
        if _matches_meter_locations(reading, allowed_meter_locations):
            readings.append(reading)

    if allowed_meter_locations and not readings:
        notes.append("Für dieses Projekt passen keine PlanRadar-Ablesungen zu den erlaubten Zählerplätzen.")

    summary = DiscoverySummary(
        project_id=project_id,
        project_name=project_name,
        ticket_type_id=ticket_type_id,
        ticket_type_name=ticket_type_name,
        field_ids=field_ids,
        project_list_ids=project_list_ids,
        notes=notes,
    )
    return PlanRadarDiscoveryResult(summary=summary, readings=readings)


def discover_and_load_readings(client: PlanRadarClient, config: AppConfig) -> PlanRadarDiscoveryResult:
    """Führt Discovery, Mapping und Transformation der PlanRadar-Daten aus."""
    projects = load_projects(client, config.customer_id)
    project = _select_project(projects, config)
    allowed_meter_locations = {config.target_meter_location} if config.target_meter_location else None
    return load_project_readings(client, config, project, allowed_meter_locations=allowed_meter_locations)
