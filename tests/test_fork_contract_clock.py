"""The shared merchant contract must not depend on the machine's local timezone.

The demo fixtures are rebased against the UTC date (`weeks_since` uses
`datetime.now(UTC)`), so a contract check that compares them with `date.today()` fails
whenever the local calendar day is ahead of UTC (UTC+8, 00:00-08:00, one day in seven).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from demo_common.tests import contract


class _Merchant:
    """Snapshots shaped like the fixtures: the weekly period ends 7 UTC days ago."""

    async def get_business_snapshot(self, session, period=None):
        today = datetime.now(UTC).date()
        if period is None:
            end = today - timedelta(days=7)
            return SimpleNamespace(
                sales=1.0,
                orders=1,
                period=f"{end - timedelta(days=6)}/{end}",
            )
        end = today - timedelta(days=7)
        start = end - timedelta(days=29)
        prior_end = start - timedelta(days=1)
        return SimpleNamespace(
            period=f"{start}/{end}",
            compare_to=f"{prior_end - timedelta(days=29)}/{prior_end}",
            sales_change_pct=1.0,
        )


async def test_snapshot_period_check_follows_the_utc_date_not_the_local_one(monkeypatch) -> None:
    class LocalDayAhead(date):
        @classmethod
        def today(cls):
            return datetime.now(UTC).date() + timedelta(days=1)

    monkeypatch.setattr(contract, "date", LocalDayAhead)

    await contract.test_snapshot_periods_end_before_boot_and_compare_to_the_prior_block(
        _Merchant(), object()
    )
