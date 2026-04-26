import json
from pathlib import Path

from watermeter.config import AppConfig, ExcelConfig, MappingOverrides, PlanRadarConfig
from watermeter.integrations.planradar.discovery import discover_and_load_readings, extract_project_image_url


class StubClient:
    def __init__(self, fixture_dir: Path) -> None:
        self.fixture_dir = fixture_dir

    def get_json(self, path: str, *, params=None):  # noqa: ANN001
        mapping = {
            "/api/v2/1531527/projects/my_projects": "projects.json",
            "/api/v2/1531527/projects/wddpbya/ticket_types/ticket_type_project": "ticket_type_project.json",
            "/api/v1/1531527/projects/wddpbya/lists": "project_lists.json",
            "/api/v2/1531527/projects/wddpbya/tickets": "tickets.json",
            "/api/v2/1531527/projects/wddpbya/tickets/7cc96fc4-6afb-45ac-b10f-fa589328d494/attachments": "attachments_7cc96fc4.json",
            "/api/v2/1531527/projects/wddpbya/tickets/051b5031-2fd8-4991-91d0-ba7effba4f9b/attachments": "attachments_051b5031.json",
        }
        file_name = mapping[path]
        return json.loads((self.fixture_dir / file_name).read_text(encoding="utf-8"))


def test_discovery_maps_list_entry_to_meter_location_and_number() -> None:
    fixture_dir = Path(__file__).parent / "fixtures" / "planradar"
    client = StubClient(fixture_dir)
    config = AppConfig(
        input_excel_path=Path("input.xlsx"),
        output_dir=Path("output"),
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

    result = discover_and_load_readings(client, config)
    assert result.summary.ticket_type_name == "Wasserzählerablesung neu"
    assert len(result.readings) == 1
    first = result.readings[0]
    assert first.project_id == "wddpbya"
    assert first.planradar_id == "2"
    assert first.ticket_id == "olqdpkgp"
    assert first.meter_location == "HAUPT_Z_1"
    assert first.meter_number == "W 10710295"
    assert first.attachments == []


def test_extract_project_image_url_reads_project_image_attribute() -> None:
    project_detail = {
        "id": "p1",
        "attributes": {
            "project-image": "https://example.invalid/cover.jpg",
        },
    }

    assert extract_project_image_url(project_detail) == "https://example.invalid/cover.jpg"
