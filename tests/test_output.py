from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from watermeter.importing.models import AttachmentInfo, DiscoverySummary, MeterReading
from watermeter.importing.output import build_bulk_output_filename, build_output_filename, write_output_workbook


def test_build_output_filename_sanitizes_values() -> None:
    filename = build_output_filename("Neugasse 7, 1452 Gaubendorf", "HAUPT_Z_1")
    assert filename == "Neugasse_7_1452_Gaubendorf__HAUPT_Z_1__combined_readings.xlsx"


def test_build_bulk_output_filename_is_stable() -> None:
    assert build_bulk_output_filename() == "all_properties__combined_readings.xlsx"


def test_output_workbook_contains_attachment_paths(tmp_path: Path) -> None:
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
        ticket_type_id="tt-1",
        attachments=[
            AttachmentInfo(
                id="a1",
                title="Foto 1.jpg",
                url="https://example.invalid/1.jpg",
                local_relative_path=Path("attachments/project/location/ticket-1/Foto_1.jpg"),
            ),
            AttachmentInfo(
                id="a2",
                title="Foto 2.jpg",
                url="https://example.invalid/2.jpg",
                local_relative_path=Path("attachments/project/location/ticket-1/Foto_2.jpg"),
            ),
        ],
    )
    summary = DiscoverySummary(
        project_id="p1",
        project_name="Neugasse 7, 1452 Gaubendorf",
        ticket_type_id="tt-1",
        ticket_type_name="Wasserzählerablesung neu",
        field_ids={},
        project_list_ids=[],
        notes=[],
    )

    output_path = write_output_workbook(tmp_path, "Neugasse 7, 1452 Gaubendorf", "HAUPT_Z_1", [reading], summary)
    workbook = load_workbook(output_path, read_only=True, data_only=True)
    sheet = workbook["combined_readings"]
    rows = list(sheet.iter_rows(values_only=True))
    assert rows[0][8] == "planradar_id"
    assert rows[1][8] == "wddpbya"
    assert rows[0][9] == "ticket_id"
    assert rows[1][9] == "olqdpkgp"
    assert rows[0][12] == "attachment_paths"
    assert rows[1][11] == 2
    assert rows[1][12] == "attachments/project/location/ticket-1/Foto_1.jpg; attachments/project/location/ticket-1/Foto_2.jpg"


def test_bulk_output_workbook_skips_discovery_sheet(tmp_path: Path) -> None:
    reading = MeterReading(
        source="excel_history",
        property_name="Neugasse 7, 1452 Gaubendorf",
        meter_location="HAUPT_Z_1",
        reading_date=date(2026, 3, 18),
        reading_value=6460,
    )

    output_path = write_output_workbook(tmp_path, "ALL_PROPERTIES", "ALL_METER_LOCATIONS", [reading], None)
    workbook = load_workbook(output_path, read_only=True, data_only=True)
    assert workbook.sheetnames == ["combined_readings"]
