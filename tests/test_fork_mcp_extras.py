"""commerce-common's mcp extras must not resolve an mcp release its server cannot import.

``commerce_common.mcp_server`` (and both managed-agent servers) import
``mcp.server.fastmcp``. mcp 2.x removed that module: importing it raises
``ModuleNotFoundError``. ``requirements.txt`` pins mcp 1.x, but a project that installs
``commerce-common[mcp]`` (or ``[sdk]``/``[dev]``) resolves through the extras alone, so an
uncapped ``mcp>=1.2`` installs 2.x and the server fails at import. The property pinned here:
while the server still imports the v1 module, every extra that names mcp excludes mcp 2.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement

COMMON = Path(__file__).resolve().parents[1] / "commerce-common"
V1_ONLY_IMPORT = "from mcp.server.fastmcp import"


def _mcp_requirements() -> dict[str, Requirement]:
    data = tomllib.loads((COMMON / "pyproject.toml").read_text(encoding="utf-8"))
    found: dict[str, Requirement] = {}
    for extra, specs in data["project"]["optional-dependencies"].items():
        for spec in specs:
            requirement = Requirement(spec)
            if requirement.name == "mcp":
                found[extra] = requirement
    return found


def test_the_server_still_imports_the_v1_only_module() -> None:
    """Precondition for the cap. When this fails, the server moved off v1: drop the cap."""
    source = (COMMON / "commerce_common" / "mcp_server.py").read_text(encoding="utf-8")
    assert V1_ONLY_IMPORT in source


def test_every_mcp_extra_excludes_mcp_2() -> None:
    requirements = _mcp_requirements()
    assert {"sdk", "mcp", "dev"} <= requirements.keys(), requirements
    for extra, requirement in requirements.items():
        assert not requirement.specifier.contains("2.0.0"), f"[{extra}] allows mcp 2"
        assert requirement.specifier.contains("1.30.0"), f"[{extra}] rejects the pinned mcp"
