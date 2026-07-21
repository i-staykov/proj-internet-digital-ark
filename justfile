# ark — common tasks.
# These are thin convenience wrappers over `uv run …`; the raw `uv run` commands
# remain the reproducibility contract (they work with only uv installed).

# list available recipes
default:
    @just --list

# sync the locked environment (installs deps into .venv)
setup:
    uv sync

# run the CLI — e.g. `just run trace example.com 1998`
run *args:
    uv run ark {{args}}

# run the test suite
test:
    uv run pytest

# lint
lint:
    uv run ruff check .

# auto-format the code
fmt:
    uv run ruff format .

# everything CI runs: lint + format-check + tests
check:
    uv run ruff check .
    uv run ruff format --check .
    uv run pytest
