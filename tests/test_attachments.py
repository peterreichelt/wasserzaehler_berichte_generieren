from __future__ import annotations

from datetime import date
from pathlib import Path

from watermeter.importing.attachments import (
    attachment_paths_as_string,
    build_attachment_filename,
    build_attachment_relative_path,
    build_cover_image_relative_path,
    download_attachments_for_readings,
    download_project_cover_image,
)
from watermeter.config import AppConfig, ExcelConfig, MappingOverrides, PlanRadarConfig
from watermeter.importing.models import AttachmentInfo, MeterReading
from watermeter.reporting.core import resolve_cover_image


class DownloadStubClient:
    def __init__(self, failures: set[str] | None = None) -> None:
        self.failures = failures or set()
        self.downloads: list[tuple[str, Path, float | None]] = []
        self.project_details: dict[str, dict] = {}

    def download_file(self, url: str, destination: Path, *, timeout_seconds: float | None = None) -> None:
        self.downloads.append((url, destination, timeout_seconds))
        if url in self.failures:
            raise RuntimeError("download failed")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"attachment")

    def get_json(self, path: str, *, params=None):  # noqa: ANN001
        return self.project_details[path]


def _build_config(output_dir: Path) -> AppConfig:
    return AppConfig(
        input_excel_path=Path("input.xlsx"),
        output_dir=output_dir,
        customer_id="1531527",
        target_project_id=None,
        target_project_name="Neugasse 7, 1452 Gaubendorf",
        target_meter_location="HAUPT_Z_1",
        log_level="INFO",
        excel=ExcelConfig(sheet_name=None, columns={}),
        planradar=PlanRadarConfig(
            include_attachments=True,
            attachments_enabled=True,
            attachment_download_timeout_seconds=60.0,
            request_pause_seconds=2.1,
            mapping_overrides=MappingOverrides(),
        ),
    )


def test_build_attachment_relative_path_preserves_structure() -> None:
    path = build_attachment_relative_path(
        project_id="wddpbya",
        meter_location="HAUPT_Z_1",
        ticket_id="olqdpkgp",
        filename="olqdpkgp_1.JPG",
    )
    assert str(path) == "attachments/wddpbya/HAUPT_Z_1/olqdpkgp/olqdpkgp_1.JPG"


def test_build_attachment_filename_uses_ticket_and_photo_ids() -> None:
    filename = build_attachment_filename(
        ticket_id="olqdpkgp",
        attachment_id="zawyzwwp",
        attachment=AttachmentInfo(
            id="zawyzwwp",
            title="Foto 1.JPG",
            url="https://example.invalid/1.jpg",
            running_number="1",
        ),
    )
    assert filename == "olqdpkgp_1.JPG"


def test_attachment_paths_as_string_joins_multiple_paths() -> None:
    attachments = [
        AttachmentInfo(id="a1", title="one", url="u1", local_relative_path=Path("attachments/a.jpg")),
        AttachmentInfo(id="a2", title="two", url="u2", local_relative_path=Path("attachments/b.jpg")),
    ]
    assert attachment_paths_as_string(attachments) == "attachments/a.jpg; attachments/b.jpg"


def test_build_cover_image_relative_path_uses_reporting_convention() -> None:
    path = build_cover_image_relative_path(
        cover_image_dir=Path("assets/cover-images"),
        property_name="1452 Gaubendorf, Neugasse 7",
        extension="png",
    )
    assert str(path) == "assets/cover-images/1452_Gaubendorf_Neugasse_7/cover.png"


def test_download_attachments_for_readings_keeps_reading_when_one_download_fails(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    client = DownloadStubClient(failures={"https://example.invalid/failed.jpg"})
    reading = MeterReading(
        source="planradar",
        property_name="Neugasse 7, 1452 Gaubendorf",
        meter_location="HAUPT_Z_1",
        meter_number="W 10710295",
        reading_date=date(2026, 3, 18),
        reading_value=6460,
        project_id="wddpbya",
        planradar_id="2",
        ticket_id="olqdpkgp",
        ticket_uuid="ticket-1",
        attachments=[
            AttachmentInfo(id="ok", title="ok.jpg", url="https://example.invalid/ok.jpg"),
            AttachmentInfo(id="bad", title="bad.jpg", url="https://example.invalid/failed.jpg"),
        ],
    )

    download_attachments_for_readings(client, [reading], config)

    assert reading.attachments[0].local_relative_path is not None
    assert reading.attachments[1].local_relative_path is None
    assert (tmp_path / reading.attachments[0].local_relative_path).exists()


def test_download_project_cover_image_overwrites_existing_file_and_old_extension(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    config.reporting.cover_image_dir = tmp_path / "assets" / "cover-images"
    cover_dir = config.reporting.cover_image_dir / "1452_Gaubendorf_Neugasse_7"
    cover_dir.mkdir(parents=True)
    (cover_dir / "cover.png").write_bytes(b"old-png")
    (cover_dir / "cover.jpg").write_bytes(b"old-jpg")

    client = DownloadStubClient()
    client.project_details = {
        "/api/v1/1531527/projects/p1": {
            "data": {
                "id": "p1",
                "attributes": {"project-image": "https://example.invalid/cover.webp?version=1"},
            }
        }
    }

    stored_path = download_project_cover_image(
        client,
        config,
        project_id="p1",
        property_name="1452 Gaubendorf, Neugasse 7",
    )

    assert stored_path == cover_dir / "cover.webp"
    assert stored_path.exists()
    assert not (cover_dir / "cover.png").exists()
    assert not (cover_dir / "cover.jpg").exists()
    assert resolve_cover_image("1452 Gaubendorf, Neugasse 7", config.reporting) == stored_path


def test_download_project_cover_image_returns_none_without_project_image(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    config.reporting.cover_image_dir = tmp_path / "assets" / "cover-images"
    client = DownloadStubClient()
    client.project_details = {
        "/api/v1/1531527/projects/p1": {
            "data": {
                "id": "p1",
                "attributes": {},
            }
        }
    }

    stored_path = download_project_cover_image(
        client,
        config,
        project_id="p1",
        property_name="Property One",
    )

    assert stored_path is None
