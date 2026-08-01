# ark: common tasks.
#
# Thin wrappers over the `uv run ...` commands in README.md. The raw commands
# remain the reproducibility contract, because they need nothing but uv
# installed; these recipes exist so the order is hard to get wrong, not to hide
# what runs. `just --list` shows everything.
#
# On naming: `ark check` validates the DATA (ten integrity invariants over the
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

# the integrity gate: ten invariants over the store, non-zero exit on any failure
check-data:
    uv run ark check

# the scoreboard: net-new domains and pairs on top of the baseline
stats:
    uv run ark stats

# both kinds of validation, which is what "is everything fine?" should mean
check: verify-repo check-data

# --- reproducing the result --------------------------------------------------
# All six stages are offline. Stages 1 to 3 read the bulk files in data/raw/,
# stage 4 replays the journals the collectors already wrote, stage 5 rebuilds the
# hostname/URL seed pool, and stage 6 writes and proves the deliverable. To
# collect NEW evidence, see the network recipes further down.

# stage 1: create the stores, load the supplied baseline read-only (~2 min)
baseline:
    uv run ark init
    uv run ark ingest-legacy
    uv run ark legacy-review
    uv run ark audit

# stage 2: ingest every bulk source already downloaded into data/raw/
sources:
    uv run ark ingest early_web         data/raw/early_web/*.cdx.gz
    uv run ark ingest isc_survey        data/raw/isc_survey/*.gz
    uv run ark ingest arquivo_roteiro   data/raw/arquivo/Roteiro.cdxj
    uv run ark ingest arquivo_ia        data/raw/arquivo/IA.cdxj
    uv run ark ingest afnic_fr          data/raw/afnic/*NomsDeDomaineEnPointFr.csv
    uv run ark ingest internet_scout    data/raw/scout/scout_oai.xml
    uv run ark ingest odp               data/raw/odp/*.gz
    uv run ark ingest ukwa_link_source  data/raw/ukwa/host-linkage.tsv.gz
    uv run ark ingest ukwa_link_target  data/raw/ukwa/host-linkage.tsv.gz
    uv run ark ingest ncsa_whats_new    data/raw/ncsa-whats-new/ncsa_1996_domain_date_pairs.tsv

# stage 3: grow the candidate pool from the year-unlabelled host lists
candidates:
    uv run ark seed data/raw/webbase/hosts.txt
    uv run ark seed legacy-data/deduplicated_urls_2001-2002.txt
    uv run ark seed seeds/100hot_hosts.txt

# This is the reproduction path for the two network stages: it re-derives
# evidence from the stored responses, so it needs no network and gives the same
# result every time. To collect MORE, see the network recipes below.
# stage 4: replay the network journals already collected in data/raw/
journals:
    uv run ark ingest cdx_snapshot  data/raw/cdx/cdx_*.jsonl.gz
    uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz
    uv run ark ingest expansion_links     data/raw/expand/expand_*.jsonl.gz --round 1
    uv run ark ingest expansion_directory data/raw/expand/round2/expand_round2.jsonl.gz --round 2
    uv run ark ingest expansion_directory data/raw/expand/wwwvl/expand_wwwvl_corroborated.jsonl.gz --round 3
    uv run ark ingest expansion_links     data/raw/expand/wwwvl/expand_wwwvl_unverified.jsonl.gz --round 3
    uv run ark ingest expansion_directory data/raw/expand/round4/expand_round4_corroborated.jsonl.gz --round 4
    uv run ark ingest expansion_links     data/raw/expand/round4/expand_round4_unverified.jsonl.gz --round 4

# stage 5: rebuild the auxiliary seed pool, the hostnames and URLs that the
# registered-domain counting unit drops. Reads the same source files again.
seeds:
    uv run ark seed-pool isc_survey       data/raw/isc_survey/*.gz
    uv run ark seed-pool odp              data/raw/odp/*.gz
    uv run ark seed-pool internet_scout   data/raw/scout/scout_oai.xml
    uv run ark seed-pool ukwa_link_source data/raw/ukwa/host-linkage.tsv.gz
    uv run ark seed-pool early_web        data/raw/early_web/*.cdx.gz

# stage 6: write the deliverable, then prove it
deliver:
    uv run ark export
    uv run ark stats
    uv run ark check

# tier 3: the whole result from an empty store. Needs the bulk sources in
# data/raw/ AND the supplied baseline in legacy-data/, since the annual masters
# are baseline plus additions and net-new is defined against it.
reproduce: baseline sources candidates journals seeds deliver

# tier 2: regenerate every result file from a provenance export instead, which
# needs no source data at all. About a minute, and byte-identical.
rebuild dir="output/provenance":
    uv run ark rebuild {{dir}}
    uv run ark check

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

# one page-expansion round (brief section VII). Pass a seed list and a round
# number, e.g. `just expand-round seeds/expansion/seeds_round4.txt 5`. The split
# step is not optional: it keeps a curated page's transcription typos out of
# master evidence by demoting names no other source attests.
expand-round seeds round:
    uv run ark download {{seeds}} -n 250 --workers 3 --captures 2 \
        --out data/raw/expand/round{{round}}/expand_round{{round}}.jsonl.gz
    uv run python scripts/split_expansion_journal.py \
        data/raw/expand/round{{round}}/expand_round{{round}}.jsonl.gz --write
    uv run ark ingest expansion_directory \
        data/raw/expand/round{{round}}/expand_round{{round}}_corroborated.jsonl.gz --round {{round}}
    uv run ark ingest expansion_links \
        data/raw/expand/round{{round}}/expand_round{{round}}_unverified.jsonl.gz --round {{round}}

# --- the English-website standard (brief feedback v3 section 6) ---------------
# Admission now needs more than existence: the site must have been English in
# that year, judged from archived body text. These write journals like the other
# collectors and never open the store.

# write the (domain, year) work list, capture-backed pairs first, years interleaved
lang-targets:
    uv run ark lang-targets

# one classification batch
lang-batch n="400" workers="2" min_delay="1.5":
    uv run ark lang data/raw/lang/lang_targets.txt -n {{n}} --workers {{workers}} \
        --samples 2 --delay 2.0 --min-delay {{min_delay}}

# fold journals into domain_language, then write the admitted subset and table
lang-ingest:
    uv run ark ingest-lang data/raw/lang/lang_*.jsonl.gz
    uv run ark lang-report

# run it in batches for a long stretch (seconds, batch, workers, floor)
lang-supervise seconds="27000" batch="400" workers="2" min_delay="1.5":
    bash scripts/supervise_lang.sh {{seconds}} {{batch}} {{workers}} {{min_delay}}

# --- this round's new sources -------------------------------------------------

# measure a Usenet archive's yield against the store BEFORE ingesting it.
# The one source assessed without doing this was estimated at 27,276 net-new
# domains and measured at 53, so this is not optional caution.
# measure a Usenet archive's net-new yield before committing to it
usenet-measure *archives:
    uv run python scripts/measure_usenet_yield.py {{archives}}

# split and ingest whatever has finished downloading
usenet-ingest tag="auto":
    bash scripts/ingest_new_usenet.sh {{tag}}

# the Tucows software catalogue: release date plus vendor home page
tucows:
    uv run python scripts/split_tucows.py --write
    uv run ark ingest tucows_dated data/raw/tucows/tucows_dated.jsonl.gz
    uv run ark ingest tucows_candidates data/raw/tucows/tucows_candidates.jsonl.gz

# One loop rather than several, because DuckDB takes a single writer.
# fold everything the collectors have finished into the store, on a loop
maintain iterations="26" pause="900":
    bash scripts/maintain_phase3.sh {{iterations}} {{pause}}

# --- shipping ----------------------------------------------------------------

# build the delivery archive (refuses a dirty tree or a stale output/)
package:
    bash scripts/package_delivery.sh

# check a built delivery the way a reviewer would: checksums, pair counts, and
# that every shipped pair traces to an observation
verify-delivery dir="output/internet-digital-ark-1996-2001":
    bash scripts/verify_delivery.sh {{dir}}
