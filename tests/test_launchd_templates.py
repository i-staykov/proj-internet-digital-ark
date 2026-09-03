"""The launchd templates name a script that exists and a PATH that finds the tools.

The installed cycle job once pointed at a script that had moved and exited 127 four
times a day while `launchctl list` looked normal; launchd's bare PATH fails the same
silent way. Both are decidable from the template alone.
"""

import plistlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = sorted((ROOT / "scripts" / "harness").glob("com.ark.*.plist.template"))
HOME = "/var/empty"


def rendered(template: Path) -> dict:
    text = template.read_text().replace("ARK_ROOT", str(ROOT)).replace("ARK_HOME", HOME)
    return plistlib.loads(text.encode())


def test_two_jobs_are_shipped():
    names = [t.name.removesuffix(".plist.template") for t in TEMPLATES]
    assert names == ["com.ark.bank", "com.ark.cycle"]


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.name)
def test_label_matches_the_file_and_the_script_exists(template: Path):
    plist = rendered(template)
    assert plist["Label"] == template.name.removesuffix(".plist.template")
    shell, script = plist["ProgramArguments"]
    assert shell == "/bin/bash"
    assert Path(script).is_file(), script
    assert plist["WorkingDirectory"] == str(ROOT)
    assert plist["StandardErrorPath"].startswith(str(ROOT / "data" / "logs"))


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda t: t.name)
def test_path_finds_the_tools_launchd_would_not(template: Path):
    env = rendered(template)["EnvironmentVariables"]
    path = env["PATH"].split(":")
    assert "/opt/homebrew/bin" in path
    assert f"{HOME}/.local/bin" in path
    assert env["HOME"] == HOME


def test_templates_contain_no_rendered_paths():
    for template in TEMPLATES:
        text = template.read_text()
        assert str(ROOT) not in text, template.name
        assert "ARK_ROOT" in text and "ARK_HOME" in text, template.name
