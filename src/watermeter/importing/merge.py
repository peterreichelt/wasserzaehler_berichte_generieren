from __future__ import annotations

from collections.abc import Iterable

from .models import MeterReading
from ..shared.normalization import property_signature


def filter_readings(
    readings: Iterable[MeterReading],
    *,
    property_name: str | None = None,
    meter_location: str | None = None,
) -> list[MeterReading]:
    """Filtert Ablesungen nach Liegenschaft und Zählerplatz.

    Args:
        readings: Zu filternde Ablesungen.
        property_name: Optionale Liegenschaft.
        meter_location: Optionaler Zählerplatz.

    Returns:
        list[MeterReading]: Gefilterte Ablesungen.
    """
    filtered: list[MeterReading] = []
    property_key = property_signature(property_name) if property_name else None
    for reading in readings:
        if property_key and property_signature(reading.property_name) != property_key:
            continue
        if meter_location and reading.meter_location != meter_location:
            continue
        filtered.append(reading)
    return filtered


def combine_readings(*collections: Iterable[MeterReading]) -> list[MeterReading]:
    """Führt mehrere Ablesungsquellen zusammen und sortiert sie chronologisch.

    Args:
        *collections: Beliebig viele Ablesungsquellen.

    Returns:
        list[MeterReading]: Zusammengeführte Ablesungen.
    """
    combined = [item for collection in collections for item in collection]
    combined.sort(key=lambda item: (item.reading_date, item.source, item.meter_number or "", item.reading_value))
    return combined


def collect_excel_meter_locations(readings: Iterable[MeterReading]) -> dict[str, set[str]]:
    """Leitet eindeutige Excel-Gruppen aus Liegenschaft und Zählerplatz ab.

    Args:
        readings: Historische Excel-Ablesungen.

    Returns:
        dict[str, set[str]]: Signatur der Liegenschaft auf erlaubte Zählerplätze.
    """
    groups: dict[str, set[str]] = {}
    for reading in readings:
        groups.setdefault(property_signature(reading.property_name), set()).add(reading.meter_location)
    return groups
