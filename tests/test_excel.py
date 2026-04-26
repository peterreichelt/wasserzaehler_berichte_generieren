from datetime import date
from pathlib import Path

from openpyxl import Workbook

from watermeter.config import ExcelConfig
from watermeter.importing.excel import load_historical_readings
from watermeter.importing.merge import filter_readings


def _create_workbook(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Tabelle1"
    sheet.append(["W 010440", date(2026, 3, 1), 100, None, 12, None, None, None, "Neugasse 7, 1452 Gaubendorf", None, None, None, None, "Haupt_Z_2"])
    sheet.append(["W 10710295", date(2026, 3, 18), 6460, None, 20, None, None, None, "Neugasse 7, 1452 Gaubendorf", None, None, None, None, "Haupt_Z_1"])
    workbook.save(path)


def test_excel_loading_and_filtering(tmp_path: Path) -> None:
    workbook_path = tmp_path / "history.xlsx"
    _create_workbook(workbook_path)
    config = ExcelConfig(
        sheet_name="Tabelle1",
        columns={
            "meter_number": "A",
            "reading_date": "B",
            "reading_value": "C",
            "property_name": "I",
            "meter_location": "N",
        },
    )
    rows = load_historical_readings(workbook_path, config)
    filtered = filter_readings(rows, property_name="Neugasse 7, 1452 Gaubendorf", meter_location="HAUPT_Z_1")
    assert len(rows) == 2
    assert len(filtered) == 1
    assert filtered[0].meter_number == "W 10710295"
