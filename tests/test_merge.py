from datetime import date

from watermeter.importing.merge import combine_readings
from watermeter.importing.models import MeterReading


def test_combine_readings_sorts_chronologically() -> None:
    older = MeterReading(
        source="excel_history",
        property_name="P",
        meter_location="HAUPT_Z_1",
        meter_number="W 1",
        reading_date=date(2025, 12, 5),
        reading_value=100,
    )
    newer = MeterReading(
        source="planradar",
        property_name="P",
        meter_location="HAUPT_Z_1",
        meter_number="W 1",
        reading_date=date(2026, 3, 18),
        reading_value=120,
    )
    combined = combine_readings([newer], [older])
    assert [item.reading_value for item in combined] == [100, 120]
