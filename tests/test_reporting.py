from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from watermeter.config import ReportingConfig
from watermeter.exceptions import ReportingError
from watermeter.reporting import (
    MeterReport,
    ReportReading,
    build_chart_plot_data,
    build_chart_segments,
    build_html_for_report,
    build_meter_location_filename_part,
    build_meter_numbers_summary,
    build_meter_reports,
    build_report_filename,
    build_report_output_path,
    group_report_readings,
    make_table_rows,
    paginate_photos,
    paginate_report_pages,
    paginate_table_rows,
    render_report_pdf,
    resolve_cover_image,
    segment_readings,
)
from watermeter.reporting.core import raster_image_file_to_data_uri


def _reading(
    index: int,
    *,
    meter_number: str = "W 1",
    property_name: str = "1452 Gaubendorf, Neugasse 7",
    meter_location: str = "HAUPT_Z_1",
    attachments: list[Path] | None = None,
) -> ReportReading:
    return ReportReading(
        source="excel_history",
        property_name=property_name,
        meter_location=meter_location,
        meter_number=meter_number,
        reading_date=date(2025, 1, 1).fromordinal(date(2025, 1, 1).toordinal() + index),
        reading_value=1000 + index * 10,
        attachment_paths=attachments or [],
    )


def _report_from_readings(readings: list[ReportReading], tmp_path: Path, *, cover: bool = False) -> MeterReport:
    reporting_config = ReportingConfig(max_readings_per_chart_band=13, min_last_chart_band_points=5)
    cover_path = None
    if cover:
        cover_path = tmp_path / "cover.png"
        Image.new("RGB", (1200, 800), "#88AACC").save(cover_path)

    built_report = build_meter_reports(readings, reporting_config)[0]
    return MeterReport(
        property_name=built_report.property_name,
        meter_location=built_report.meter_location,
        meter_numbers=built_report.meter_numbers,
        readings=built_report.readings,
        bands=built_report.bands,
        photo_pages=built_report.photo_pages,
        cover_image_path=cover_path,
        generated_on=date(2026, 4, 19),
        version_code="260419",
    )


def test_group_report_readings_groups_by_property_and_meter_location() -> None:
    readings = [
        _reading(0, property_name="A", meter_location="HAUPT_Z_1"),
        _reading(1, property_name="A", meter_location="HAUPT_Z_1"),
        _reading(2, property_name="A", meter_location="HAUPT_Z_2"),
        _reading(3, property_name="B", meter_location="HAUPT_Z_1"),
    ]
    grouped = group_report_readings(readings)
    assert len(grouped) == 3
    assert len(grouped[("A", "HAUPT_Z_1")]) == 2


def test_build_meter_numbers_summary_keeps_short_lists_complete() -> None:
    summary = build_meter_numbers_summary(["W 010440", "W 66994", "W 85501"])
    assert summary == "W 010440, W 66994, W 85501"


def test_build_meter_numbers_summary_keeps_long_lists_for_client_side_fitting() -> None:
    summary = build_meter_numbers_summary(["W 10710295", "W 250037", "W 255738", "W 264201"])
    assert summary == "W 10710295, W 250037, W 255738, W 264201"


def test_segment_readings_rebalances_small_last_band() -> None:
    readings = [_reading(index) for index in range(14)]
    segments = segment_readings(readings, max_points_per_band=13, min_last_band_points=5)
    assert [len(segment) for segment in segments] == [9, 5]


def test_segment_readings_handles_exact_and_large_sizes() -> None:
    assert [len(segment) for segment in segment_readings([_reading(index) for index in range(5)], 13, 5)] == [5]
    assert [len(segment) for segment in segment_readings([_reading(index) for index in range(13)], 13, 5)] == [13]
    assert [len(segment) for segment in segment_readings([_reading(index) for index in range(17)], 13, 5)] == [12, 5]
    assert [len(segment) for segment in segment_readings([_reading(index) for index in range(26)], 13, 5)] == [13, 13]
    assert [len(segment) for segment in segment_readings([_reading(index) for index in range(27)], 13, 5)] == [13, 9, 5]


def test_paginate_table_rows_uses_one_column_for_small_tables() -> None:
    rows = [{"date": str(index)} for index in range(12)]
    pages = paginate_table_rows(rows)
    assert pages == [{"layout": "one_col", "rows": rows}]


def test_paginate_table_rows_uses_two_columns_and_multiple_pages() -> None:
    rows = [{"date": str(index)} for index in range(35)]
    pages = paginate_table_rows(rows)
    assert [page["layout"] for page in pages] == ["two_col", "two_col"]
    assert len(pages[0]["left_rows"]) == 14
    assert len(pages[0]["right_rows"]) == 14
    assert len(pages[1]["left_rows"]) == 7
    assert len(pages[1]["right_rows"]) == 0


def test_build_chart_plot_data_breaks_connections_over_zero_and_tracks_runs() -> None:
    readings = [_reading(index, meter_number="W 1") for index in range(5)]
    daily_values = [1.2, 0.0, 1.6, 1.1, 0.5]
    meters = ["W 1", "W 1", "W 2", "W 2", "W 3"]
    for reading, daily_value, meter_number in zip(readings, daily_values, meters):
        reading.daily_consumption = daily_value
        reading.meter_number = meter_number

    plot_data = build_chart_plot_data(readings)
    assert [(entry["start_index"], entry["end_index"]) for entry in plot_data["connections"]] == [(0, 1), (2, 3)]
    assert plot_data["runs"] == [
        {"meter_number": "W 1", "start_index": 0, "end_index": 1},
        {"meter_number": "W 2", "start_index": 2, "end_index": 3},
        {"meter_number": "W 3", "start_index": 4, "end_index": 4},
    ]


def test_build_chart_segments_exposes_plot_data() -> None:
    report = _report_from_readings([_reading(index) for index in range(14)], Path("/tmp"))
    segments = build_chart_segments(report)
    assert len(segments) == 2
    assert segments[0]["count"] == 9
    assert "plot_data" in segments[0]
    assert segments[0]["image_data_uri"].startswith("data:image/png;base64,")


def test_build_chart_plot_data_keeps_connection_for_zero_consumption_without_meter_change() -> None:
    readings = [_reading(index, meter_number="W 85501") for index in range(3)]
    for reading, daily_value in zip(readings, [1.2, 0.0, 0.0]):
        reading.daily_consumption = daily_value

    plot_data = build_chart_plot_data(readings)
    assert [(entry["start_index"], entry["end_index"]) for entry in plot_data["connections"]] == [(0, 1), (1, 2)]


def test_build_chart_plot_data_skips_both_connections_around_meter_change() -> None:
    readings = [
        _reading(0, meter_number="W 1"),
        _reading(1, meter_number="W 1"),
        _reading(2, meter_number="W 2"),
        _reading(3, meter_number="W 2"),
    ]
    enrich_values = [1.1, 1.3, 0.0, 0.4]
    meter_changes = [False, False, True, False]
    for reading, daily_value, meter_change in zip(readings, enrich_values, meter_changes):
        reading.daily_consumption = daily_value
        reading.meter_change = meter_change

    plot_data = build_chart_plot_data(readings)
    assert [(entry["start_index"], entry["end_index"]) for entry in plot_data["connections"]] == [(0, 1)]


def test_paginate_report_pages_uses_combined_page_for_small_reports(tmp_path: Path) -> None:
    report = _report_from_readings([_reading(index) for index in range(6)], tmp_path)
    pages = paginate_report_pages(report)
    assert [page["type"] for page in pages] == ["cover", "table_chart_combined"]


def test_paginate_report_pages_uses_separate_table_and_chart_pages_for_large_reports(tmp_path: Path) -> None:
    readings = [_reading(index, meter_number="W 1" if index < 14 else "W 2") for index in range(27)]
    report = _report_from_readings(readings, tmp_path)
    pages = paginate_report_pages(report)
    assert [page["type"] for page in pages] == ["cover", "table", "charts", "charts"]
    assert pages[2]["chart_page_count"] == 2
    assert len(pages[2]["chart_segments"]) == 2
    assert len(pages[3]["chart_segments"]) == 1


def test_resolve_cover_image_prefers_property_cover_file(tmp_path: Path) -> None:
    cover_dir = tmp_path / "covers" / "1452_Gaubendorf_Neugasse_7"
    cover_dir.mkdir(parents=True)
    cover_path = cover_dir / "cover.png"
    Image.new("RGB", (120, 80), "#336699").save(cover_path)

    config = ReportingConfig(cover_image_dir=tmp_path / "covers")
    resolved = resolve_cover_image("1452 Gaubendorf, Neugasse 7", config)
    assert resolved == cover_path


def test_resolve_cover_image_falls_back_to_placeholder(tmp_path: Path) -> None:
    placeholder = tmp_path / "placeholder.png"
    Image.new("RGB", (120, 80), "#CCCCCC").save(placeholder)
    config = ReportingConfig(cover_image_dir=tmp_path / "covers", placeholder_cover_path=placeholder)
    resolved = resolve_cover_image("Unknown Property", config)
    assert resolved == placeholder


def test_resolve_cover_image_uses_default_jpg_before_placeholder(tmp_path: Path) -> None:
    cover_dir = tmp_path / "covers"
    cover_dir.mkdir(parents=True)
    default_cover = cover_dir / "default.jpg"
    placeholder = tmp_path / "placeholder.png"
    Image.new("RGB", (120, 80), "#999999").save(default_cover)
    Image.new("RGB", (120, 80), "#CCCCCC").save(placeholder)

    config = ReportingConfig(cover_image_dir=cover_dir, placeholder_cover_path=placeholder)
    resolved = resolve_cover_image("Unknown Property", config)
    assert resolved == default_cover


def test_paginate_photos_splits_into_four_per_page(tmp_path: Path) -> None:
    image_paths = []
    for index in range(9):
        path = tmp_path / f"photo_{index}.png"
        Image.new("RGB", (50, 50), "#123456").save(path)
        image_paths.append(path)

    readings = [_reading(0, attachments=image_paths[:1])]
    for index, path in enumerate(image_paths[1:], start=1):
        readings.append(_reading(index, attachments=[path]))
    pages = paginate_photos(readings)
    assert [len(page) for page in pages] == [4, 4, 1]


def test_make_table_rows_lists_all_referenced_photo_numbers(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    third = tmp_path / "third.png"
    for path in (first, second, third):
        Image.new("RGB", (50, 50), "#123456").save(path)

    report = _report_from_readings(
        [
            _reading(0, attachments=[first, second]),
            _reading(1, attachments=[third]),
            _reading(2, attachments=[]),
        ],
        tmp_path,
    )

    rows = make_table_rows(report)
    assert rows[0]["photo_no"] == "1, 2"
    assert rows[1]["photo_no"] == "3"
    assert rows[2]["photo_no"] == "—"


def test_make_table_rows_marks_meter_changes_and_includes_meter_number(tmp_path: Path) -> None:
    report = _report_from_readings(
        [
            _reading(0, meter_number="W 1"),
            _reading(1, meter_number="W 2"),
            _reading(2, meter_number="W 2"),
        ],
        tmp_path,
    )

    rows = make_table_rows(report)
    assert rows[0]["meter_number"] == "W 1"
    assert rows[1]["meter_number"] == "W 2"
    assert rows[1]["days"] == "Zählerwechsel"
    assert rows[1]["daily_consumption"] == "Zählerwechsel"


def test_build_meter_reports_creates_bands_and_output_path(tmp_path: Path) -> None:
    config = ReportingConfig(output_dir=tmp_path / "reports", max_readings_per_chart_band=13, min_last_chart_band_points=5)
    readings = [_reading(index, meter_number="W 1" if index < 8 else "W 2") for index in range(17)]
    reports = build_meter_reports(readings, config)
    assert len(reports) == 1
    assert [len(band.readings) for band in reports[0].bands] == [12, 5]
    output_path = build_report_output_path(reports[0], config.output_dir)
    assert output_path.name == "Neugasse_7__1452_Gaubendorf__Zaehlerplatz__Haupt__Z__1.pdf"


def test_build_report_filename_reorders_property_name_and_transliterates_umlauts() -> None:
    report = MeterReport(
        property_name="1593 Oberdörf, Sommergasse 6",
        meter_location="HAUPT_Z_1",
        meter_numbers=["W 1"],
        readings=[],
        bands=[],
        photo_pages=[],
        cover_image_path=None,
        generated_on=date(2026, 4, 19),
        version_code="260419",
    )

    assert build_report_filename(report) == "Sommergasse_6__1593_Oberdoerf__Zaehlerplatz__Haupt__Z__1.pdf"


def test_build_meter_location_filename_part_formats_tokens_for_filename() -> None:
    assert build_meter_location_filename_part("HAUPT_Z_1") == "Haupt__Z__1"


def test_build_html_for_report_renders_template_sections(tmp_path: Path) -> None:
    cover_path = tmp_path / "cover.png"
    Image.new("RGB", (1200, 800), "#88AACC").save(cover_path)
    report = _report_from_readings([_reading(index) for index in range(14)], tmp_path, cover=True)
    html = build_html_for_report(report)
    assert "TECHNISCHER PRÜFBERICHT" in html
    assert "section-title" in html
    assert "data:image/png;base64," in html
    assert "ImmoScan Gebäudedokumentation" in html
    assert "Zählerplatz:" in html
    assert "Zählernummer" in html


def test_raster_image_file_to_data_uri_optimizes_raster_images(tmp_path: Path) -> None:
    image_path = tmp_path / "large.jpg"
    Image.new("RGB", (4000, 3000), "#88AACC").save(image_path, quality=95)
    data_uri = raster_image_file_to_data_uri(image_path, max_width=1200, max_height=900, jpeg_quality=85)
    assert data_uri.startswith("data:image/jpeg;base64,")


def test_build_html_for_report_keeps_full_meter_numbers_on_content_pages(tmp_path: Path) -> None:
    report = _report_from_readings(
        [
            _reading(index, meter_number=meter_number)
            for index, meter_number in enumerate(["W 10710295", "W 250037", "W 255738", "W 264201"])
        ],
        tmp_path,
    )
    html = build_html_for_report(report)
    assert "Zählernummern: W 10710295, W 250037, W 255738, W 264201" in html
    assert (
        '<div class="summary-value summary-value-full summary-fit" data-fit-mode="full" '
        'data-max-font-size="12" data-min-font-size="4">W 10710295, W 250037, W 255738, W 264201</div>'
        in html
    )


def test_render_report_pdf_generates_multipage_pdf_when_playwright_is_available(tmp_path: Path) -> None:
    attachment_one = tmp_path / "attachment_one.png"
    attachment_two = tmp_path / "attachment_two.png"
    Image.new("RGB", (800, 600), "#CC8844").save(attachment_one)
    Image.new("RGB", (800, 600), "#4488CC").save(attachment_two)

    readings = [
        _reading(index, meter_number="W 1", attachments=[attachment_one, attachment_two] if index == 0 else [])
        for index in range(14)
    ]
    report = _report_from_readings(readings, tmp_path, cover=True)
    output_path = tmp_path / "report.pdf"

    try:
        render_report_pdf(report, output_path)
    except ReportingError as exc:
        if "playwright" in str(exc).lower() or "chromium" in str(exc).lower():
            pytest.skip(str(exc))
        raise

    reader = PdfReader(str(output_path))
    assert len(reader.pages) >= 3
    assert output_path.stat().st_size > 0
