from datetime import date

import pytest

from app.services.calendar import monthly_due_date


@pytest.mark.parametrize(
    ("year", "month", "day", "expected"),
    [
        (2026, 1, 31, date(2026, 1, 31)),
        (2026, 2, 31, date(2026, 2, 28)),
        (2024, 2, 31, date(2024, 2, 29)),
        (2026, 4, 31, date(2026, 4, 30)),
        (2026, 8, 15, date(2026, 8, 15)),
    ],
)
def test_monthly_due_date_clamps_invalid_dates(
    year: int, month: int, day: int, expected: date
) -> None:
    assert monthly_due_date(year, month, day) == expected


def test_monthly_due_date_rejects_out_of_range_day() -> None:
    with pytest.raises(ValueError):
        monthly_due_date(2026, 1, 0)
