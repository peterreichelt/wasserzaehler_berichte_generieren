from __future__ import annotations

from pathlib import Path
from typing import Iterable

from openpyxl import Workbook

from .attachments import attachment_paths_as_string
from .models import DiscoverySummary, MeterReading
from ..shared.normalization import ensure_directory, sanitize_filename


def build_bulk_output_filename() -> str:
    """Definiert den festen Dateinamen für den Sammelmodus.

    Returns:
        str: Stabiler Dateiname für den Sammelmodus.
    """
    return "all_properties__combined_readings.xlsx"


def build_output_filename(project_name: str, meter_location: str) -> str:
    """Baut den Dateinamen für die kombinierte Excel-Ausgabe.

    Args:
        project_name: Projekt- oder Liegenschaftsname.
        meter_location: Zählerplatz.

    Returns:
        str: Bereinigter Dateiname.
    """
    return f"{sanitize_filename(project_name)}__{sanitize_filename(meter_location)}__combined_readings.xlsx"


def write_output_workbook(
    output_dir: Path,
    project_name: str,
    meter_location: str,
    readings: Iterable[MeterReading],
    discovery: DiscoverySummary | None,
) -> Path:
    """Schreibt die kombinierte Datenbasis und Discovery-Metadaten in eine Excel-Datei.

    Args:
        output_dir: Zielordner.
        project_name: Projekt- oder Liegenschaftsname.
        meter_location: Zählerplatz.
        readings: Zu schreibende Ablesungen.
        discovery: Optionale Discovery-Metadaten.

    Returns:
        Path: Pfad zur erzeugten Excel-Datei.
    """
    ensure_directory(output_dir)
    if discovery is None:
        output_path = output_dir / build_bulk_output_filename()
    else:
        output_path = output_dir / build_output_filename(project_name, meter_location)

    workbook = Workbook()
    data_sheet = workbook.active
    data_sheet.title = "combined_readings"
    data_sheet.append(
        [
            "source",
            "property_name",
            "meter_location",
            "meter_number",
            "reading_date",
            "reading_value",
            "unit",
            "notes",
            "planradar_id",
            "ticket_id",
            "ticket_type_id",
            "attachment_count",
            "attachment_paths",
            "raw_meter_location",
        ]
    )
    for reading in readings:
        data_sheet.append(
            [
                reading.source,
                reading.property_name,
                reading.meter_location,
                reading.meter_number,
                reading.reading_date.isoformat(),
                reading.reading_value,
                reading.unit,
                reading.notes,
                reading.project_id,
                reading.ticket_id,
                reading.ticket_type_id,
                len(reading.attachments),
                attachment_paths_as_string(reading.attachments),
                reading.raw_meter_location,
            ]
        )

    if discovery is not None:
        discovery_sheet = workbook.create_sheet("discovery")
        discovery_sheet.append(["key", "value"])
        discovery_sheet.append(["project_id", discovery.project_id])
        discovery_sheet.append(["project_name", discovery.project_name])
        discovery_sheet.append(["ticket_type_id", discovery.ticket_type_id])
        discovery_sheet.append(["ticket_type_name", discovery.ticket_type_name])
        for semantic_name, field_id in discovery.field_ids.items():
            discovery_sheet.append([f"field.{semantic_name}", field_id])
        discovery_sheet.append(["project_list_ids", ", ".join(discovery.project_list_ids)])
        for note in discovery.notes:
            discovery_sheet.append(["note", note])

    workbook.save(output_path)
    return output_path
