from __future__ import annotations

import logging
from pathlib import Path

from ..config import AppConfig
from ..shared.normalization import ensure_directory, normalize_text, sanitize_filename, sanitize_filename_preserve_extension
from ..integrations.planradar.client import PlanRadarClient
from ..integrations.planradar.discovery import extract_project_image_url, load_project_detail
from .models import AttachmentInfo, MeterReading


logger = logging.getLogger(__name__)


def _detect_attachment_extension(attachment: AttachmentInfo) -> str:
    """Leitet eine sinnvolle Dateiendung aus Titel oder Download-URL ab."""
    for candidate in (attachment.title, attachment.url):
        text = normalize_text(candidate)
        if not text:
            continue
        name = Path(text.split("?", 1)[0]).name
        suffix = Path(name).suffix
        if suffix:
            return suffix.lstrip(".")
    return "bin"


def _detect_url_extension(url: str | None) -> str:
    """Leitet eine sinnvolle Dateiendung aus einer Datei-URL ab."""
    text = normalize_text(url)
    if not text:
        return "bin"
    name = Path(text.split("?", 1)[0]).name
    suffix = Path(name).suffix
    if suffix:
        return suffix.lstrip(".")
    return "bin"


def build_attachment_filename(*, ticket_id: str, attachment_id: str, attachment: AttachmentInfo) -> str:
    """Baut den Dateinamen im Schema TicketID_PhotoID.ImageFormat."""
    extension = sanitize_filename(_detect_attachment_extension(attachment))
    photo_id = attachment.running_number or attachment_id
    return f"{sanitize_filename(ticket_id)}_{sanitize_filename(photo_id)}.{extension}"


def build_attachment_relative_path(
    *,
    project_id: str,
    meter_location: str,
    ticket_id: str,
    filename: str,
) -> Path:
    """Erzeugt den relativen Ablagepfad für eine heruntergeladene Attachment-Datei."""
    return (
        Path("attachments")
        / sanitize_filename(project_id)
        / sanitize_filename(meter_location)
        / sanitize_filename(ticket_id)
        / sanitize_filename_preserve_extension(filename)
    )


def build_cover_image_relative_path(*, cover_image_dir: Path, property_name: str, extension: str) -> Path:
    """Baut den relativen Ablagepfad für ein Projekt-Titelbild."""
    sanitized_property = sanitize_filename(property_name)
    return cover_image_dir / sanitized_property / sanitize_filename_preserve_extension(f"cover.{extension}")


def _remove_cover_image_variants(target_path: Path) -> None:
    """Entfernt alte Titelbilder mit abweichender Endung aus dem Property-Ordner."""
    for extension in ("jpg", "jpeg", "png", "webp", "bin"):
        candidate = target_path.parent / f"cover.{extension}"
        if candidate == target_path:
            continue
        if candidate.exists():
            candidate.unlink()


def attachment_paths_as_string(attachments: list[AttachmentInfo]) -> str:
    """Formatiert alle vorhandenen relativen Attachment-Pfade für die Excel-Ausgabe."""
    return "; ".join(str(item.local_relative_path) for item in attachments if item.local_relative_path)


def download_attachments_for_readings(
    client: PlanRadarClient,
    readings: list[MeterReading],
    config: AppConfig,
) -> None:
    """Lädt Attachments für relevante PlanRadar-Ablesungen herunter."""
    if not config.planradar.include_attachments or not config.planradar.attachments_enabled:
        return

    base_dir = config.output_dir
    ensure_directory(base_dir / "attachments")
    logger.info("Attachments werden nach %s heruntergeladen", base_dir / "attachments")

    for reading in readings:
        if reading.source != "planradar" or not reading.attachments:
            continue
        for attachment in reading.attachments:
            _download_attachment(client, base_dir, reading, attachment, config)


def _download_attachment(
    client: PlanRadarClient,
    base_dir: Path,
    reading: MeterReading,
    attachment: AttachmentInfo,
    config: AppConfig,
) -> None:
    """Lädt genau ein Attachment und merkt sich den relativen Zielpfad im Modell."""
    if not attachment.url:
        logger.warning(
            "Attachment %s für Ticket %s wird übersprungen, weil keine Download-URL verfügbar ist.",
            attachment.id,
            reading.ticket_uuid,
        )
        return

    filename = build_attachment_filename(
        ticket_id=reading.ticket_id or reading.ticket_uuid or "unknown_ticket",
        attachment_id=attachment.id or "unknown_attachment",
        attachment=attachment,
    )
    relative_path = build_attachment_relative_path(
        project_id=reading.project_id or reading.property_name,
        meter_location=reading.meter_location,
        ticket_id=reading.ticket_id or reading.ticket_uuid or "unknown_ticket",
        filename=filename,
    )
    destination = base_dir / relative_path

    try:
        client.download_file(
            attachment.url,
            destination,
            timeout_seconds=config.planradar.attachment_download_timeout_seconds,
        )
    except Exception as exc:
        logger.warning(
            "Attachment %s für Ticket %s konnte nicht heruntergeladen werden: %s",
            attachment.id,
            reading.ticket_uuid,
            exc,
        )
        return

    attachment.local_relative_path = relative_path


def download_project_cover_image(
    client: PlanRadarClient,
    config: AppConfig,
    *,
    project_id: str,
    property_name: str,
) -> Path | None:
    """Lädt das PlanRadar-Titelbild eines Projekts in die Reporting-Asset-Struktur."""
    try:
        project_detail = load_project_detail(client, config.customer_id, project_id)
    except Exception as exc:
        logger.warning("Projektdetails für das Titelbild von Projekt %s konnten nicht geladen werden: %s", project_id, exc)
        return None

    image_url = extract_project_image_url(project_detail)
    if not image_url:
        logger.info("Für %s ist kein Projekt-Titelbild verfügbar.", property_name)
        return None

    extension = sanitize_filename(_detect_url_extension(image_url))
    relative_path = build_cover_image_relative_path(
        cover_image_dir=config.reporting.cover_image_dir,
        property_name=property_name,
        extension=extension,
    )
    destination = relative_path
    ensure_directory(destination.parent)

    try:
        client.download_file(
            image_url,
            destination,
            timeout_seconds=config.planradar.attachment_download_timeout_seconds,
        )
    except Exception as exc:
        logger.warning("Das Projekt-Titelbild für %s konnte nicht heruntergeladen werden: %s", property_name, exc)
        return None

    _remove_cover_image_variants(destination)
    logger.info("Projekt-Titelbild für %s wurde unter %s gespeichert", property_name, destination)
    return destination
