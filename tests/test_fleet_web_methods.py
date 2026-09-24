"""The fleet refuses a hostname-grain lead at filing when its class is not a web method
(ark-fleet `scripts/dealer.py`), reading a COPY of the allowlist from its own
`schemas/web_methods.json` because a collect job has no public checkout. A copy drifts, so
this pins it to the one allowlist that decides the claim. `$ARK_FLEET` names the
fleet checkout, and the test skips where it is absent.
"""

import json
import os
from pathlib import Path

import pytest

from ark.evidence_types import REDIRECT_METHOD, WEB_METHODS

FLEET_ROOT = Path(
    os.environ.get("ARK_FLEET") or Path.home() / "Documents/GitHub/ark-fleet"
).expanduser()
FLEET = FLEET_ROOT / "schemas" / "web_methods.json"


def test_the_fleet_copy_of_the_allowlist_is_the_allowlist() -> None:
    if not FLEET.is_file():
        pytest.skip("no ark-fleet clone beside this checkout")
    copy = set(json.loads(FLEET.read_text(encoding="utf-8"))["web_methods"])
    assert copy == WEB_METHODS | {REDIRECT_METHOD}
