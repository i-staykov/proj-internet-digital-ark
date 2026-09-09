"""The fleet host's single CDX slot, and the sweep shapes it refuses.

C-77 caps the CDX channel at two clients and both are this laptop's sweeps, so a price or
verify leg on the VPS takes one extra seat and only for an exact-host sample. The properties
worth a test are the ones that would otherwise fail silently and expensively: a shape that
walks a namespace must be refused before any request is made, and a host with no lock must
refuse rather than query unserialised. Neither test reaches the network.
"""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLOT = ROOT / "scripts" / "harness" / "cdx_slot.sh"
REFUSED_SHAPE = 5
NO_LOCK = 3


def run(*args, slot: Path, dry: bool = False) -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/bin:/bin", "ARK_CDX_SLOT": str(slot)}
    if dry:
        env["ARK_CDX_DRY_RUN"] = "1"
    return subprocess.run(
        ["bash", str(SLOT), *args], cwd=ROOT, capture_output=True, text=True, env=env
    )


def test_a_sweep_shape_is_refused_before_any_request(tmp_path):
    slot = tmp_path / "cdx.slot"
    for host in ("*.example.com", "example.com/search", "-example.com", "example..com", "com"):
        result = run(host, slot=slot)
        assert result.returncode == REFUSED_SHAPE, f"{host}: {result.stderr}"
    # A caller cannot smuggle the walk in through the extra query either.
    walked = run("www.example.com", "matchType=domain", slot=slot)
    assert walked.returncode == REFUSED_SHAPE, walked.stderr
    assert not slot.exists(), "a refused shape must not even take the slot"


def test_an_exact_host_composes_one_bounded_question(tmp_path):
    """No request is made here: the dry run is the shape, which is what can be wrong."""
    result = run("www.example.com", "from=1996&to=2001", slot=tmp_path / "cdx.slot", dry=True)
    assert result.returncode == 0, result.stderr
    asked = result.stdout.strip()
    assert "url=www.example.com" in asked
    assert "matchType=exact" in asked
    assert "limit=200" in asked
    assert asked.endswith("from=1996&to=2001")


def test_a_host_without_a_lock_refuses_rather_than_querying(tmp_path):
    """An unserialised query is the third client the limit exists to prevent."""
    if shutil.which("flock") is not None:
        return
    result = run("www.example.com", slot=tmp_path / "cdx.slot")
    assert result.returncode == NO_LOCK
    assert "flock" in result.stderr


def test_the_query_it_builds_is_one_exact_page():
    text = SLOT.read_text(encoding="utf-8")
    assert "matchType=exact" in text
    assert "flock -w" in text
    assert "retry-after" in text.lower()
