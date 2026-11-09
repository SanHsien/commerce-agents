"""The screenshot tour must launch updated Chrome Stable with the Chromium sandbox on.

Playwright leaves the sandbox off by default, and the old launcher fell back to bundled
Chromium or Edge whenever Chrome would not start. The properties pinned here: one launch
call, the ``chrome`` channel, the sandbox enabled, and no fallback when that launch fails.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

TOUR = Path(__file__).resolve().parents[1] / "scripts" / "screenshot_tour.py"


def _load_tour(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    # Playwright is optional (the dev requirements do not install it), so stub the two names
    # the script imports; the launcher under test never touches them.
    sync_api = ModuleType("playwright.sync_api")
    sync_api.TimeoutError = TimeoutError  # type: ignore[attr-defined]
    sync_api.sync_playwright = lambda: None  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "playwright", ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)
    spec = importlib.util.spec_from_file_location("screenshot_tour_under_test", TOUR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Chromium:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[dict] = []
        self.fail = fail

    def launch(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("chrome is not installed")
        return "browser"


class _Playwright:
    def __init__(self, fail: bool = False) -> None:
        self.chromium = _Chromium(fail)


def test_launch_uses_chrome_stable_with_the_sandbox_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    playwright = _Playwright()
    assert _load_tour(monkeypatch).launch_browser(playwright) == "browser"
    assert playwright.chromium.calls == [{"channel": "chrome", "chromium_sandbox": True}]


def test_launch_failure_is_surfaced_not_retried_on_an_unsandboxed_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    playwright = _Playwright(fail=True)
    with pytest.raises(RuntimeError, match="chrome is not installed"):
        _load_tour(monkeypatch).launch_browser(playwright)
    assert len(playwright.chromium.calls) == 1
