import calendar
from datetime import date


def monthly_due_date(year: int, month: int, requested_day: int) -> date:
    """Clamp a requested monthly due day to the month's final valid day."""
    if not 1 <= requested_day <= 31:
        raise ValueError("requested_day must be between 1 and 31")
    final_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(requested_day, final_day))
