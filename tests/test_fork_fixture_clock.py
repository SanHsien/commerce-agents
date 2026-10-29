"""The storefront fixture re-dating must not depend on the machine's local timezone.

In-flight orders are re-dated relative to ``dates_anchored_to`` against the UTC date,
matching how ``weeks_since`` uses ``datetime.now(UTC)`` and how timestamps in orders
are serialized in UTC (ending in 'Z'). When ``redate_in_flight_orders`` used
``datetime.now().date()`` (local calendar day), the computed delta differed by one day
whenever the local calendar day is ahead of UTC (e.g. UTC+8, 00:00-08:00).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from demo_common import storefront_fixtures


def test_redate_in_flight_orders_follows_utc_date_not_local_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Scenario: UTC is 2026-10-25 20:00:00 (UTC date: 2026-10-25).
    # Local time is UTC+8, so 2026-10-26 04:00:00 (local date: 2026-10-26).
    utc_now = datetime(2026, 10, 25, 20, 0, 0, tzinfo=UTC)
    local_now = datetime(2026, 10, 26, 4, 0, 0)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return local_now
            if tz == UTC:
                return utc_now
            return local_now

    monkeypatch.setattr(storefront_fixtures, "datetime", FrozenDateTime)

    # Fixture anchored to 5 days before the UTC date.
    raw: dict[str, Any] = {
        "dates_anchored_to": "2026-10-20",
        "orders": [
            {
                "status": "delayed",
                "placed_at": "2026-10-20T12:00:00Z",
                "estimated_delivery": "2026-10-23 (was 2026-10-20)",
            },
            {
                "status": "delivered",
                "placed_at": "2026-01-01T10:00:00Z",
                "estimated_delivery": "2026-01-04",
            },
        ],
    }

    result = storefront_fixtures.redate_in_flight_orders(raw)
    delayed, delivered = result["orders"]

    # Elapsed days in UTC is (2026-10-25 - 2026-10-20) = 5 days.
    # Before the fix (using local date 2026-10-26), delta was 6 days, placing the order at
    # 2026-10-26T12:00:00Z instead of 2026-10-25T12:00:00Z.
    assert delayed["placed_at"] == "2026-10-25T12:00:00Z"
    assert delayed["estimated_delivery"] == "2026-10-28 (was 2026-10-25)"
    assert delivered["estimated_delivery"] == "2026-01-04"
