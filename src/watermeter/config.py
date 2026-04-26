from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ConfigError
from .shared.normalization import normalize_meter_location, normalize_text


DEFAULT_EXCEL_COLUMNS = {
    "meter_number": "A",
    "reading_date": "B",
    "reading_value": "C",
    "property_name": "I",
    "meter_location": "N",
}


@dataclass
class ExcelConfig:
    """Bündelt die Excel-spezifischen Einstellungen des Imports."""

    sheet_name: str | None
    columns: dict[str, str]


@dataclass
class MappingOverrides:
    """Enthält optionale projektspezifische Overrides für die API-Zuordnung."""

    ticket_type_name: str | None = None
    typed_field_names: dict[str, str] = field(default_factory=dict)
    list_entry_overrides: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass
class PlanRadarConfig:
    """Kapselt die Einstellungen für den PlanRadar-Zugriff."""

    include_attachments: bool
    attachments_enabled: bool
    attachment_download_timeout_seconds: float
    request_pause_seconds: float
    mapping_overrides: MappingOverrides


@dataclass
class ReportingConfig:
    """Enthält die Einstellungen für die PDF-Report-Erzeugung."""

    enabled: bool = False
    input_workbook_path: Path | None = None
    output_dir: Path = Path("output/reports")
    cover_image_dir: Path = Path("assets/cover-images")
    placeholder_cover_path: Path | None = None
    max_readings_per_chart_band: int = 13
    min_last_chart_band_points: int = 5


@dataclass
class AppConfig:
    """Fasst die vollständige Laufzeitkonfiguration der Anwendung zusammen."""

    input_excel_path: Path
    output_dir: Path
    customer_id: str
    target_project_id: str | None
    target_project_name: str | None
    target_meter_location: str | None
    log_level: str
    excel: ExcelConfig
    planradar: PlanRadarConfig
    reporting: ReportingConfig = field(default_factory=ReportingConfig)

    @property
    def is_bulk_mode(self) -> bool:
        """Kennzeichnet den Sammelmodus ohne feste Projekt- und Zählerplatzwahl."""
        return not self.target_project_id and not self.target_project_name and not self.target_meter_location

    @property
    def is_focused_mode(self) -> bool:
        """Kennzeichnet den fokussierten Modus mit genau einem Projekt und Zählerplatz."""
        return not self.is_bulk_mode


def _require_string(data: dict[str, Any], key: str) -> str:
    """Liest einen Pflichtwert als nichtleeren String aus der Konfiguration.

    Args:
        data: Geladene Konfigurationsdaten.
        key: Name des Konfigurationsschlüssels.

    Returns:
        str: Bereinigter Stringwert.
    """
    value = data.get(key)
    if isinstance(value, (int, float)):
        value = str(value)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"Der Konfigurationsschlüssel '{key}' ist erforderlich und muss ein nichtleerer String sein.")
    return value.strip()


def _optional_string(data: dict[str, Any], key: str) -> str | None:
    """Liest einen optionalen Stringwert aus der Konfiguration.

    Args:
        data: Geladene Konfigurationsdaten.
        key: Name des Konfigurationsschlüssels.

    Returns:
        str | None: Bereinigter Stringwert oder `None`.
    """
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        value = str(value)
    if not isinstance(value, str):
        raise ConfigError(f"Der Konfigurationsschlüssel '{key}' muss ein String sein, wenn er gesetzt ist.")
    if not value.strip():
        return None
    return value.strip()


def load_config(path: str | Path) -> AppConfig:
    """Lädt und validiert die YAML-Konfiguration der Anwendung.

    Args:
        path: Pfad zur YAML-Datei.

    Returns:
        AppConfig: Vollständig validierte Anwendungskonfiguration.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Die Konfigurationsdatei existiert nicht: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ConfigError("Die Wurzel der Konfiguration muss ein YAML-Objekt sein.")

    input_excel_path = Path(_require_string(raw, "input_excel_path"))
    output_dir = Path(_require_string(raw, "output_dir"))
    customer_id = _require_string(raw, "customer_id")
    target_project_id = _optional_string(raw, "target_project_id")
    target_project_name = _optional_string(raw, "target_project_name")
    target_meter_location_raw = _optional_string(raw, "target_meter_location")
    target_meter_location = (
        normalize_meter_location(target_meter_location_raw) if target_meter_location_raw else None
    )
    project_selector_count = int(bool(target_project_id)) + int(bool(target_project_name))
    is_bulk_mode = project_selector_count == 0 and target_meter_location is None
    is_focused_mode = project_selector_count == 1 and target_meter_location is not None
    if not is_bulk_mode and not is_focused_mode:
        raise ConfigError(
            "Verwenden Sie entweder den fokussierten Modus mit genau einem von "
            "'target_project_id'/'target_project_name' plus 'target_meter_location' "
            "oder den Sammelmodus mit allen drei leeren Selektoren."
        )
    log_level = normalize_text(raw.get("log_level") or "INFO").upper()

    excel_raw = raw.get("excel") or {}
    if not isinstance(excel_raw, dict):
        raise ConfigError("'excel' muss ein Mapping sein, wenn es gesetzt ist.")
    columns = dict(DEFAULT_EXCEL_COLUMNS)
    custom_columns = excel_raw.get("columns") or {}
    if custom_columns:
        if not isinstance(custom_columns, dict):
            raise ConfigError("'excel.columns' muss ein Mapping sein.")
        columns.update({str(key): str(value) for key, value in custom_columns.items()})
    excel_config = ExcelConfig(
        sheet_name=_optional_string(excel_raw, "sheet_name"),
        columns=columns,
    )

    pr_raw = raw.get("planradar") or {}
    if not isinstance(pr_raw, dict):
        raise ConfigError("'planradar' muss ein Mapping sein, wenn es gesetzt ist.")
    overrides_raw = pr_raw.get("mapping_overrides") or {}
    if not isinstance(overrides_raw, dict):
        raise ConfigError("'planradar.mapping_overrides' muss ein Mapping sein.")
    attachments_raw = pr_raw.get("attachments") or {}
    if not isinstance(attachments_raw, dict):
        raise ConfigError("'planradar.attachments' muss ein Mapping sein.")
    mapping_overrides = MappingOverrides(
        ticket_type_name=_optional_string(overrides_raw, "ticket_type_name"),
        typed_field_names={str(k): str(v) for k, v in (overrides_raw.get("typed_field_names") or {}).items()},
        list_entry_overrides={
            str(k): {str(inner_k): str(inner_v) for inner_k, inner_v in value.items()}
            for k, value in (overrides_raw.get("list_entry_overrides") or {}).items()
        },
    )

    planradar_config = PlanRadarConfig(
        include_attachments=bool(pr_raw.get("include_attachments", True)),
        attachments_enabled=bool(attachments_raw.get("enabled", True)),
        attachment_download_timeout_seconds=float(attachments_raw.get("download_timeout_seconds", 60.0)),
        request_pause_seconds=float(pr_raw.get("request_pause_seconds", 2.1)),
        mapping_overrides=mapping_overrides,
    )

    reporting_raw = raw.get("reporting") or {}
    if not isinstance(reporting_raw, dict):
        raise ConfigError("'reporting' muss ein Mapping sein, wenn es gesetzt ist.")
    reporting_max_points = int(reporting_raw.get("max_readings_per_chart_band", 13))
    reporting_min_last = int(reporting_raw.get("min_last_chart_band_points", 5))
    if reporting_max_points < 5:
        raise ConfigError("'reporting.max_readings_per_chart_band' muss mindestens 5 sein.")
    if reporting_min_last < 1:
        raise ConfigError("'reporting.min_last_chart_band_points' muss mindestens 1 sein.")
    if reporting_min_last > reporting_max_points:
        raise ConfigError(
            "'reporting.min_last_chart_band_points' darf "
            "'reporting.max_readings_per_chart_band' nicht überschreiten."
        )
    placeholder_cover_raw = _optional_string(reporting_raw, "placeholder_cover_path")
    reporting_config = ReportingConfig(
        enabled=bool(reporting_raw.get("enabled", False)),
        input_workbook_path=(
            Path(input_workbook_path_raw)
            if (input_workbook_path_raw := _optional_string(reporting_raw, "input_workbook_path"))
            else None
        ),
        output_dir=Path(_optional_string(reporting_raw, "output_dir") or "output/reports"),
        cover_image_dir=Path(_optional_string(reporting_raw, "cover_image_dir") or "assets/cover-images"),
        placeholder_cover_path=Path(placeholder_cover_raw) if placeholder_cover_raw else None,
        max_readings_per_chart_band=reporting_max_points,
        min_last_chart_band_points=reporting_min_last,
    )

    return AppConfig(
        input_excel_path=input_excel_path,
        output_dir=output_dir,
        customer_id=customer_id,
        target_project_id=target_project_id,
        target_project_name=target_project_name,
        target_meter_location=target_meter_location,
        log_level=log_level,
        excel=excel_config,
        planradar=planradar_config,
        reporting=reporting_config,
    )
