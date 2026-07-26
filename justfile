# ark: common tasks.
#
# Thin wrappers over the `uv run ...` commands in README.md. The raw commands
# remain the reproducibility contract, because they need nothing but uv
# installed; these recipes exist so the order is hard to get wrong, not to hide
# what runs. `just --list` shows everything.
#
# On naming: `ark check` validates the DATA (nine integrity invariants over the
# store) while the test suite validates the CODE. Naming either one plain
# "check" invites running one and believing the other passed, so they are
# `check-data` and `verify-repo` here, and `just check` runs BOTH.

# list available recipes
default:
    @just --list

# sync the locked environment (installs deps into .venv)
setup:
    uv sync

# run any CLI command directly, e.g. `just run stats` or `just run cdx --help`
run *args:
    uv run ark {{args}}

# --- validating the code -----------------------------------------------------

# run the test suite
test:
    uv run pytest

# lint
lint:
    uv run ruff check .

# auto-format the code
fmt:
    uv run ruff format .

# exactly what CI runs: lint + format-check + tests
verify-repo:
    uv run ruff check .
    uv run ruff format --check .
    uv run pytest

# --- validating the data -----------------------------------------------------

# the integrity gate: nine invariants over the store, non-zero exit on any failure
check-data:
    uv run ark check

# the scoreboard: net-new domains and pairs on top of the baseline
stats:
    uv run ark stats

# both kinds of validation, which is what "is everything fine?" should mean
check: verify-repo check-data

# --- reproducing the result --------------------------------------------------
# Stages 1 to 3 need no network and rebuild the store from the files in
# data/raw/; stage 4 queries live services; stage 5 writes the deliverable.

# stage 1: create the stores, load the supplied baseline read-only (~2 min)
baseline:
    uv run ark init
    uv run ark ingest-legacy
    uv run ark legacy-review
    uv run ark audit

# stage 2: ingest every bulk source already downloaded into data/raw/
sources:
    uv run ark ingest early_web         data/raw/early_web/*.cdx.gz
    uv run ark ingest isc_survey        data/raw/isc_survey/*.domains.gz
    uv run ark ingest arquivo_roteiro   data/raw/arquivo/Roteiro.cdxj
    uv run ark ingest arquivo_ia        data/raw/arquivo/IA.cdxj
    uv run ark ingest afnic_fr          data/raw/afnic/*NomsDeDomaineEnPointFr.csv
    uv run ark ingest internet_scout    data/raw/scout/scout_oai.xml
    uv run ark ingest odp               data/raw/odp/*.gz
    uv run ark ingest ukwa_link_source  data/raw/ukwa/host-linkage.tsv.gz
    uv run ark ingest ukwa_link_target  data/raw/ukwa/host-linkage.tsv.gz

# stage 3: grow the candidate pool from the year-unlabelled host lists
candidates:
    uv run ark seed data/raw/webbase/hosts.txt
    uv run ark seed data/raw/ukwa/link_target_candidates.txt

# This is the reproduction path for the two network stages: it re-derives
# evidence from the stored responses, so it needs no network and gives the same
# result every time. To collect MORE, see the network recipes below.
# stage 4: replay the network journals already collected in data/raw/
journals:
    uv run ark ingest cdx_snapshot  data/raw/cdx/cdx_*.jsonl.gz
    uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz

# stage 5: write the deliverable, then prove it
deliver:
    uv run ark export
    uv run ark stats
    uv run ark check

# the whole result from an empty store, no network required
reproduce: baseline sources candidates journals deliver

# --- collecting more (network) -----------------------------------------------
# Each of these appends a journal to data/raw/ and writes no evidence, so they
# never hold the store's write lock and can run concurrently with each other.

# one archive-verification batch: which in-window years hold a capture
cdx-batch n="1200" workers="8":
    uv run ark gaps
    uv run ark cdx data/raw/cdx/gap_candidates.txt -n {{n}} --workers {{workers}} --timeout 70

# one registry-date batch: creation year for domains adjacent to a held year
rdap-batch n="2500":
    uv run ark gaps --creation --out data/raw/rdap/creation_candidates.txt
    uv run ark rdap data/raw/rdap/creation_candidates.txt -n {{n}}

# one page-expansion round over the curated seed list (brief section VII)
expand-round:
    uv run ark download data/raw/expand/seeds_pilot.txt
    uv run ark ingest expansion_links     data/raw/expand/expand_*.jsonl.gz
    uv run ark ingest expansion_directory data/raw/expand/expand_*.jsonl.gz

# --- shipping ----------------------------------------------------------------

# build the delivery archive (refuses to run on a dirty tree)
package:
    bash scripts/package_delivery.sh
