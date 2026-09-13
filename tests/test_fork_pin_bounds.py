"""Contract tests for tools/check_pin_bounds.py.

The check exists to stand between a Dependabot bump and a pin that contradicts a
package's own declared range. These tests pin the behaviours that make it worth
trusting: it reads both requirements files and every pyproject, it rejects a pin that
falls outside a declared bound, it does not invent violations for packages nobody
declares, and it reports what it cannot evaluate instead of passing it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_pin_bounds", REPO_ROOT / "tools" / "check_pin_bounds.py"
)
assert _spec and _spec.loader
checker = importlib.util.module_from_spec(_spec)
sys.modules["check_pin_bounds"] = checker
_spec.loader.exec_module(checker)


def test_the_repos_own_pins_satisfy_every_declared_range() -> None:
    """The live contract: this repo's actual pins and pyprojects must agree.

    This is the assertion a Dependabot pull request has to survive.
    """
    pins, declarations = checker.collect()
    assert pins, "no exact pins found -- the requirements files were not read"
    assert declarations, "no declared ranges found -- the pyprojects were not read"
    assert checker.find_violations(pins, declarations) == []


def test_both_requirements_files_are_read() -> None:
    """requirements-dev.txt is where the dev tools live; missing it would blind the check."""
    assert checker.REQUIREMENT_FILES == ("requirements.txt", "requirements-dev.txt")
    for name in checker.REQUIREMENT_FILES:
        assert (REPO_ROOT / name).is_file()


def test_the_upper_bound_this_repo_actually_declares_is_in_scope() -> None:
    """`ruff>=0.15,<0.17` in commerce-common's [dev] extra is the one ceiling in the repo.

    It sits in an optional-dependencies table, so a check that only read `dependencies`
    would miss the single declaration most likely to be violated by a routine bump.
    """
    _, declarations = checker.collect()
    ceilings = [d for d in declarations if d["package"] == "ruff" and d["operator"] in {"<", "<="}]
    assert ceilings, "the ruff ceiling was not collected from the [dev] extra"


@pytest.mark.parametrize(
    ("version", "operator", "bound", "expected"),
    [
        ("0.16.6", ">=", "0.15", True),
        ("0.16.6", "<", "0.17", True),
        ("0.17.0", "<", "0.17", False),
        ("0.14.9", ">=", "0.15", False),
        ("2.13.4", ">=", "2.7", True),
        ("1.2.0", "~=", "1.2", True),
        ("2.0.0", "~=", "1.2", False),
        ("9.1.1", "!=", "9.1.1", False),
        ("9.1.2", "!=", "9.1.1", True),
        ("0.122.0", ">=", "0.91", True),
    ],
)
def test_version_comparison(version: str, operator: str, bound: str, expected: bool) -> None:
    assert checker.satisfies(version, operator, bound) is expected


def test_an_unparsable_version_is_reported_not_skipped() -> None:
    assert checker.satisfies("not-a-version", ">=", "1.0") is None
    violations = checker.find_violations(
        {"weird": {"name": "weird", "version": "1.0", "source": "requirements.txt"}},
        [
            {
                "package": "weird",
                "operator": "@",
                "bound": "git+https://example.invalid",
                "source": "x/pyproject.toml",
                "requirement": "weird @ git+https://example.invalid",
            }
        ],
    )
    assert [v["kind"] for v in violations] == ["unparsable"]


def test_a_pin_outside_a_declared_bound_is_a_violation() -> None:
    violations = checker.find_violations(
        {"ruff": {"name": "ruff", "version": "0.17.1", "source": "requirements-dev.txt"}},
        [
            {
                "package": "ruff",
                "operator": "<",
                "bound": "0.17",
                "source": "commerce-common/pyproject.toml",
                "requirement": "ruff>=0.15,<0.17",
            }
        ],
    )
    assert len(violations) == 1
    assert violations[0]["kind"] == "out-of-range"
    assert violations[0]["pinned"] == "0.17.1"
    assert "commerce-common" in checker.render({}, [], violations)


def test_a_pin_nobody_declares_is_not_a_violation() -> None:
    """Most of requirements.txt is transitive: pinned, but claimed by no pyproject."""
    assert (
        checker.find_violations(
            {"idna": {"name": "idna", "version": "3.18", "source": "requirements.txt"}}, []
        )
        == []
    )


def test_in_repo_packages_are_excluded_from_both_sides() -> None:
    """scripts/check.py owns the seven siblings' lockstep; double-checking it here would
    duplicate an invariant, and their `-e ./path` lines carry no version to check."""
    pins = checker.parse_pins("commerce-common==0.1.0.dev0\nanthropic==0.122.0\n", "x.txt")
    assert set(pins) == {"anthropic"}
    declarations = checker.parse_declarations(
        '[project]\ndependencies = ["commerce-common==0.1.0.dev0", "pydantic>=2.7"]\n',
        "x/pyproject.toml",
    )
    assert [d["package"] for d in declarations] == ["pydantic"]


def test_editable_and_include_lines_carry_no_pin() -> None:
    pins = checker.parse_pins("-e ./commerce-common[examples]\n-r requirements.txt\n", "x.txt")
    assert pins == {}


def test_an_environment_marker_does_not_hide_the_pin() -> None:
    """tzdata is pinned behind `; sys_platform == "win32"` and must still be checked."""
    pins = checker.parse_pins('tzdata==2026.3; sys_platform == "win32"\n', "x.txt")
    assert pins["tzdata"]["version"] == "2026.3"


def test_names_are_normalized_before_matching() -> None:
    """`PyYAML` in a pyproject and `pyyaml` in requirements.txt are the same package."""
    pins = checker.parse_pins("PyYAML==6.0.3\n", "x.txt")
    declarations = checker.parse_declarations(
        '[project]\ndependencies = ["pyyaml>=6.0"]\n', "x/pyproject.toml"
    )
    assert set(pins) == {"pyyaml"}
    assert checker.find_violations(pins, declarations) == []


def test_extras_in_a_declaration_do_not_break_the_specifier() -> None:
    declarations = checker.parse_declarations(
        '[project]\ndependencies = ["uvicorn[standard]>=0.30"]\n', "x/pyproject.toml"
    )
    assert declarations == [
        {
            "package": "uvicorn",
            "operator": ">=",
            "bound": "0.30",
            "source": "x/pyproject.toml",
            "requirement": "uvicorn[standard]>=0.30",
        }
    ]
