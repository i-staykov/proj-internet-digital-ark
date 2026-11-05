"""Refuse an agent run whose settings files could bill another credential than its OAuth token.

    python3 -I scripts/agents/billing_guard.py --home "$HOME" --workdir <dir> [--workdir <dir>]

Claude Code applies `apiKeyHelper` and the `env` block of its settings files after it
starts, so dropping variables before `claude` cannot remove what they set. This reads every
settings file a run's `claude` loads: the user's, including `.claude/.config.json`, each
working directory's, and the managed `managed-settings.json` with every `managed-settings.d/*.json`
beside it. A file carrying `apiKeyHelper`, or an `env` key naming an API key, a provider
switch or a cloud credential, fails. So does a file or drop-in folder that exists and cannot
be read: what the guard cannot read cannot be vouched for. A missing file is fine.
`--managed` points the managed read at another folder or file, for tests only.

Prints one FAIL line per file and key and exits 1, or prints `ok` and exits 0. Standard
library only, run with `python3 -I`, so nothing in the login's HOME runs inside it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

MANAGED = "/etc/claude-code"
HELPER = "apiKeyHelper"
ENV_KEY = re.compile(
    r"^(ANTHROPIC_|CLAUDE_CODE_USE_|CLAUDE_CODE_API_KEY|CLAUDE_CODE_OAUTH|AWS_|GOOGLE_|AZURE_|VERTEX_|CLOUD_ML_)"
)


def managed_files(managed: str = MANAGED) -> list[str]:
    """`managed` when it is a file, else its settings file and each drop-in beside it.

    A drop-in folder that exists and cannot be listed is returned as itself, so it fails.
    """
    if os.path.isfile(managed):
        return [managed]
    paths = [os.path.join(managed, "managed-settings.json")]
    drop = os.path.join(managed, "managed-settings.d")
    try:
        paths += [os.path.join(drop, n) for n in sorted(os.listdir(drop)) if n.endswith(".json")]
    except FileNotFoundError:
        pass
    except OSError:
        paths.append(drop)
    return paths


def settings_files(home: str, workdirs: list[str], managed: str = MANAGED) -> list[str]:
    """Every settings file `claude` reads for a run in any of `workdirs`, each once."""
    paths = [
        os.path.join(home, ".claude", "settings.json"),
        os.path.join(home, ".claude", "settings.local.json"),
        os.path.join(home, ".claude", ".config.json"),
        os.path.join(home, ".claude.json"),
    ]
    for workdir in workdirs:
        paths += [
            os.path.join(workdir, ".claude", "settings.json"),
            os.path.join(workdir, ".claude", "settings.local.json"),
        ]
    paths += managed_files(managed)
    return list(dict.fromkeys(paths))


def problems(path: str) -> list[str]:
    """The FAIL lines for one file. A missing file has none."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        return [
            f"FAIL {path} cannot be read as JSON ({type(exc).__name__}), "
            "so it cannot be vouched for"
        ]
    if not isinstance(data, dict):
        return [f"FAIL {path} is not a JSON object, so it cannot be vouched for"]
    bad = []
    if HELPER in data:
        bad.append(f"FAIL {path} sets {HELPER}, which answers in place of the OAuth token")
    env = data.get("env")
    if env is not None and not isinstance(env, dict):
        bad.append(f"FAIL {path} has an env that is not an object, so it cannot be vouched for")
    elif env:
        for key in sorted(k for k in env if ENV_KEY.match(str(k))):
            bad.append(f"FAIL {path} sets env.{key}, which dropping variables cannot remove")
    return bad


def main(argv: list[str] | None = None, managed: str = MANAGED) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    ap.add_argument("--home", required=True, help="the HOME the run's claude runs with")
    ap.add_argument("--workdir", action="append", default=[], help="a directory claude runs in")
    ap.add_argument(
        "--managed", default=managed, help="tests only: the managed folder or file to read"
    )
    args = ap.parse_args(argv)
    bad = [
        line
        for path in settings_files(args.home, args.workdir, args.managed)
        for line in problems(path)
    ]
    print("\n".join(bad) or "ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
