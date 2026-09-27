"""Check every exact pin in the requirements files against what the packages declare.

Turning Dependabot loose on `requirements.txt` and `requirements-dev.txt` creates one
failure mode nothing else in this repo catches. `scripts/check.py` never reads the
requirements files at all -- it checks that the seven in-repo packages agree on a version
and pin each other exactly, entirely inside the `pyproject.toml` files. The third-party
declarations in those same pyprojects are ranges (`anthropic>=0.91`, and one upper bound,
`ruff>=0.15,<0.17`), while the requirements files carry exact `==` pins. Nothing compares
the two. A bump that walks a pin outside a declared range therefore installs cleanly,
passes the suite, and leaves the package metadata quietly contradicting the environment
it is tested in -- which surfaces later as an unreproducible install, not as a red run.

This closes that gap: for every `==` pin in the requirements files, every range any
`pyproject.toml` in the repo declares for that distribution must accept it. A pin with no
declaration anywhere is a transitive dependency of the pinned set, not a claim this repo
makes, and is skipped.

    python tools/check_pin_bounds.py            # human-readable, non-zero on a violation
    python tools/check_pin_bounds.py --json

Version comparison covers the operators these files actually use (`>=`, `>`, `<=`, `<`,
`==`, `!=`, `~=`) over numeric release segments, with pre-release and local suffixes
dropped. That is deliberately not a full PEP 440 implementation: this repo declares plain
numeric ranges, and a stdlib-only tool is worth more here than the `packaging` dependency
a complete implementation would need. An operator or version it cannot parse is reported
as unparsable rather than silently passing.
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# The requirements files whose exact pins are checked. Both are upstream-held files this
# fork edits directly; see docs/DIVERGENCE.md.
REQUIREMENT_FILES = ("requirements.txt", "requirements-dev.txt")

# The seven in-repo packages pin each other exactly and are installed from local paths,
# never from an index. `scripts/check.py::check_package_versions` already enforces their
# lockstep, and they never appear as an `==` pin in a requirements file (they appear as
# `-e ./path` lines), so they are excluded here rather than double-checked.
IN_REPO_PACKAGES = {
    "commerce-common",
    "shopping-agent-core",
    "shopping-agent-runtime",
    "shopping-agent-sdk",
    "merchant-agent-core",
    "merchant-agent-runtime",
    "merchant-agent-sdk",
}

_PIN_RE = re.compile(r"^([A-Za-z0-9._-]+)\s*==\s*([0-9][0-9A-Za-z.!+_-]*)\s*$")
_SPEC_RE = re.compile(r"^(~=|==|!=|<=|>=|<|>)\s*([0-9][0-9A-Za-z.*!+_-]*)$")
_NAME_RE = re.compile(r"^([A-Za-z0-9._-]+)")
_RELEASE_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)*")


class PinBoundsError(RuntimeError):
    """Raised when a file this check needs cannot be read or parsed."""


def normalize(name: str) -> str:
    """PEP 503 normalization, so `PyYAML`, `pyyaml`, and `py_yaml` compare equal."""
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def release_key(version: str) -> tuple[int, ...] | None:
    """The numeric release segment of a version, or None when it is not numeric."""
    match = _RELEASE_RE.match(version.strip().lstrip("vV"))
    if not match:
        return None
    return tuple(int(part) for part in match.group(0).split("."))


def _pad(left: tuple[int, ...], right: tuple[int, ...]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    width = max(len(left), len(right))
    return left + (0,) * (width - len(left)), right + (0,) * (width - len(right))


def satisfies(version: str, operator: str, bound: str) -> bool | None:
    """Does `version` satisfy `operator bound`? None when either side is unparsable.

    `~=X.Y.Z` is expanded to its two halves (`>=X.Y.Z` and `< X.(Y+1)`), which is what the
    operator means and keeps the caller from special-casing it.
    """
    left = release_key(version)
    right = release_key(bound.replace("*", "0"))
    if left is None or right is None:
        return None
    if operator == "~=":
        if len(right) < 2:
            return None
        lower = satisfies(version, ">=", bound)
        ceiling = ".".join(str(part) for part in (*right[:-2], right[-2] + 1))
        upper = satisfies(version, "<", ceiling)
        return None if lower is None or upper is None else (lower and upper)
    padded_left, padded_right = _pad(left, right)
    if operator == "==":
        # An `==X.Y` declaration constrains only the segments it states.
        depth = len(right)
        return _pad(left, right)[0][:depth] == right
    if operator == "!=":
        depth = len(right)
        return _pad(left, right)[0][:depth] != right
    if operator == ">=":
        return padded_left >= padded_right
    if operator == ">":
        return padded_left > padded_right
    if operator == "<=":
        return padded_left <= padded_right
    if operator == "<":
        return padded_left < padded_right
    return None


def parse_pins(text: str, source: str) -> dict[str, dict[str, str]]:
    """Every `name==version` line in a requirements file, keyed by normalized name.

    `-e ./path` and `-r other.txt` lines carry no version claim of their own and are
    skipped; an environment marker (`; sys_platform == "win32"`) does not change which
    version is pinned, so it is stripped before matching.
    """
    pins: dict[str, dict[str, str]] = {}
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        head = line.split(";", 1)[0].strip()
        match = _PIN_RE.match(head)
        if not match:
            continue
        name, version = match.groups()
        key = normalize(name)
        if key in IN_REPO_PACKAGES:
            continue
        pins[key] = {"name": name, "version": version, "source": source}
    return pins


def parse_declarations(text: str, source: str) -> list[dict[str, str]]:
    """Every third-party requirement a pyproject declares, `dependencies` and extras alike.

    Extras count: `commerce-common[examples]` is how `requirements.txt` installs the demo
    hosts, and `[dev]` declares the one upper bound in the repo (`ruff>=0.15,<0.17`).
    """
    try:
        project = tomllib.loads(text).get("project", {})
    except tomllib.TOMLDecodeError as error:
        raise PinBoundsError(f"{source}: {error}") from error
    requirements = list(project.get("dependencies", []))
    for extra in (project.get("optional-dependencies") or {}).values():
        requirements.extend(extra)

    declarations: list[dict[str, str]] = []
    for requirement in requirements:
        head = requirement.split(";", 1)[0].strip()
        name_match = _NAME_RE.match(head)
        if not name_match:
            continue
        key = normalize(name_match.group(1))
        if key in IN_REPO_PACKAGES:
            continue
        rest = head[name_match.end() :].strip()
        rest = re.sub(r"^\[[^\]]*\]", "", rest).strip()
        for clause in (part.strip() for part in rest.split(",") if part.strip()):
            spec_match = _SPEC_RE.match(clause)
            declarations.append(
                {
                    "package": key,
                    "operator": spec_match.group(1) if spec_match else "",
                    "bound": spec_match.group(2) if spec_match else clause,
                    "source": source,
                    "requirement": requirement,
                }
            )
    return declarations


def collect(root: Path = REPO_ROOT) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    pins: dict[str, dict[str, str]] = {}
    for name in REQUIREMENT_FILES:
        path = root / name
        if not path.is_file():
            raise PinBoundsError(f"missing requirements file: {name}")
        pins.update(parse_pins(path.read_text(encoding="utf-8"), name))

    declarations: list[dict[str, str]] = []
    for path in sorted(root.glob("*/pyproject.toml")) + sorted(root.glob("*/*/pyproject.toml")):
        relative = path.relative_to(root).as_posix()
        declarations.extend(parse_declarations(path.read_text(encoding="utf-8"), relative))
    return pins, declarations


def find_violations(
    pins: dict[str, dict[str, str]], declarations: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Pins a declared range rejects, plus declarations this tool cannot evaluate.

    An unevaluable clause is reported, never skipped: a check that silently ignores what
    it does not understand reports green for the one case most likely to be a real
    problem.
    """
    violations: list[dict[str, str]] = []
    for declaration in declarations:
        pin = pins.get(declaration["package"])
        if pin is None:
            continue
        verdict = (
            satisfies(pin["version"], declaration["operator"], declaration["bound"])
            if declaration["operator"]
            else None
        )
        if verdict is False:
            kind = "out-of-range"
        elif verdict is None:
            kind = "unparsable"
        else:
            continue
        violations.append(
            {
                "kind": kind,
                "package": declaration["package"],
                "pinned": pin["version"],
                "pin_source": pin["source"],
                "declared": declaration["requirement"],
                "declaration_source": declaration["source"],
            }
        )
    return violations


def render(
    pins: dict[str, dict[str, str]],
    declarations: list[dict[str, str]],
    violations: list[dict[str, str]],
) -> str:
    checked = {d["package"] for d in declarations} & set(pins)
    lines = [
        f"{len(pins)} exact pin(s); {len(declarations)} declared range(s); "
        f"{len(checked)} package(s) constrained by both."
    ]
    if not violations:
        lines.append("OK: every pin satisfies every range its packages declare.")
        return "\n".join(lines)
    lines.append("")
    for violation in violations:
        if violation["kind"] == "out-of-range":
            lines.append(
                f"  {violation['package']}: {violation['pin_source']} pins "
                f"{violation['pinned']}, but {violation['declaration_source']} declares "
                f"{violation['declared']!r}"
            )
        else:
            lines.append(
                f"  {violation['package']}: cannot evaluate "
                f"{violation['declared']!r} ({violation['declaration_source']}) against "
                f"pinned {violation['pinned']}"
            )
    lines.append("")
    lines.append(
        "Fix the pin and the declaration together: a Dependabot bump that moves a pin "
        "past a declared bound needs the matching pyproject range raised in the same "
        "change, and a new row in docs/DIVERGENCE.md."
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    try:
        pins, declarations = collect()
    except PinBoundsError as error:
        print(f"pin bounds check failed: {error}")
        return 1
    violations = find_violations(pins, declarations)

    if args.json:
        print(
            json.dumps(
                {
                    "pins": len(pins),
                    "declarations": len(declarations),
                    "violations": violations,
                },
                indent=2,
            )
        )
    else:
        print(render(pins, declarations, violations))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
