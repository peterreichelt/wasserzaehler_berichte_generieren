from pathlib import Path

import pytest

from watermeter.config import load_config
from watermeter.exceptions import ConfigError


def test_load_config_normalizes_meter_location(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
input_excel_path: input.xlsx
output_dir: output
customer_id: 1531527
target_project_name: Neugasse 7, 1452 Gaubendorf
target_meter_location: Haupt_Z_1
""",
        encoding="utf-8",
    )
    config = load_config(config_file)
    assert config.target_meter_location == "HAUPT_Z_1"
    assert config.excel.columns["meter_number"] == "A"
    assert config.is_focused_mode is True


def test_load_config_allows_bulk_mode_when_selectors_are_empty(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
input_excel_path: input.xlsx
output_dir: output
customer_id: 1531527
target_project_id:
target_project_name: "   "
target_meter_location:
""",
        encoding="utf-8",
    )
    config = load_config(config_file)
    assert config.is_bulk_mode is True
    assert config.target_project_name is None
    assert config.target_meter_location is None
    assert config.reporting.output_dir == Path("output/reports")
    assert config.reporting.max_readings_per_chart_band == 13


def test_load_config_rejects_mixed_mode_configuration(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
input_excel_path: input.xlsx
output_dir: output
customer_id: 1531527
target_project_name: Neugasse 7, 1452 Gaubendorf
target_meter_location:
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(config_file)


def test_load_config_parses_reporting_section(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
input_excel_path: input.xlsx
output_dir: output
customer_id: 1531527
target_project_id:
target_project_name:
target_meter_location:
reporting:
  enabled: true
  input_workbook_path: output/custom.xlsx
  output_dir: reports/pdf
  cover_image_dir: assets/covers
  placeholder_cover_path: assets/placeholder.png
  max_readings_per_chart_band: 11
  min_last_chart_band_points: 4
""",
        encoding="utf-8",
    )
    config = load_config(config_file)
    assert config.reporting.enabled is True
    assert config.reporting.input_workbook_path == Path("output/custom.xlsx")
    assert config.reporting.output_dir == Path("reports/pdf")
    assert config.reporting.cover_image_dir == Path("assets/covers")
    assert config.reporting.placeholder_cover_path == Path("assets/placeholder.png")
    assert config.reporting.max_readings_per_chart_band == 11
    assert config.reporting.min_last_chart_band_points == 4
