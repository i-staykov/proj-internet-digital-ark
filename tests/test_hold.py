"""`hold.sh holds`, which `just sync` and `just bank` ask before they run: 0 while the hold file
lists the name, or with no name exists, 1 otherwise."""

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_holds_is_true_only_while_the_hold_file_holds(tmp_path):
    script = tmp_path / "scripts/harness/hold.sh"  # a copy, so no local.env is read
    script.parent.mkdir(parents=True)
    shutil.copy(ROOT / "scripts/harness/hold.sh", script)

    def holds(*name: str) -> int:
        env = os.environ | {"ARK_STATE_DIR": str(tmp_path)}
        return subprocess.run(["bash", script, "holds", *name], env=env).returncode

    assert (holds(), holds("ark-sync.timer")) == (1, 1)
    (tmp_path / "hold").write_text("human\n2026-01-01T00:00:00Z\nark-sync.timer\n")
    assert (holds(), holds("ark-sync.timer"), holds("pause-platform")) == (0, 0, 1)
