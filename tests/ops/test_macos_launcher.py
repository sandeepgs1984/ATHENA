"""Tests for the thin macOS ATHENA.app launcher (Live Entry M-E4)."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "packaging" / "macos" / "ATHENA.app"
EXECUTABLE = APP / "Contents" / "MacOS" / "ATHENA"
PLIST = APP / "Contents" / "Info.plist"
INSTALLER = REPO / "install-athena-app"
INSTALLER_IMPL = REPO / "scripts" / "macos" / "install-athena-app.sh"


def test_app_template_has_valid_identity_and_executable() -> None:
    assert EXECUTABLE.is_file()
    assert EXECUTABLE.stat().st_mode & 0o111
    text = PLIST.read_text(encoding="utf-8")
    assert "<string>in.athena.workstation</string>" in text
    assert "<key>CFBundleExecutable</key>" in text
    assert "<string>ATHENA</string>" in text
    assert "<key>LSUIElement</key>" in text


def test_launcher_shell_sources_are_syntax_valid() -> None:
    result = subprocess.run(
        [
            "bash",
            "-n",
            str(EXECUTABLE),
            str(INSTALLER),
            str(INSTALLER_IMPL),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS app install")
def test_installer_builds_configured_app_bundle(tmp_path: Path) -> None:
    destination = tmp_path / "ATHENA.app"
    result = subprocess.run(
        [
            str(INSTALLER),
            "--destination",
            str(destination),
            "--no-reveal",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (destination / "Contents" / "MacOS" / "ATHENA").stat().st_mode & 0o111
    repo_file = destination / "Contents" / "Resources" / "repo-root"
    assert repo_file.read_text(encoding="utf-8").strip() == str(REPO)
